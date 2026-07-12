from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import onnx
import torch
import torch.nn.functional as torch_functional
from onnx import numpy_helper

from ..hashing import sha256_file
from ..lowering import LoweringManifest
from ..model import ModelGraphCatalog


def _attributes(node: onnx.NodeProto) -> dict[str, Any]:
    return {
        item.name: onnx.helper.get_attribute_value(item)
        for item in node.attribute
    }


def _checked_int32(value: np.ndarray, name: str) -> np.ndarray:
    minimum = int(value.min())
    maximum = int(value.max())
    limits = np.iinfo(np.int32)
    if minimum < limits.min or maximum > limits.max:
        raise OverflowError(f"{name} exceeds int32: min={minimum}, max={maximum}")
    return value.astype(np.int32, copy=False)


def _requantize(value: np.ndarray, multiplier: np.ndarray, zero_point: int) -> np.ndarray:
    scales = np.asarray(multiplier, dtype=np.float32).reshape(-1)
    if value.ndim < 2 or scales.size not in {1, value.shape[1]}:
        raise ValueError("requant multiplier must be scalar or match axis 1")
    shape = [1] * value.ndim
    shape[1] = scales.size
    scaled = value.astype(np.float32) * scales.reshape(shape)
    return np.clip(np.rint(scaled).astype(np.int64) + int(zero_point), 0, 255).astype(
        np.uint8
    )


def conv_accumulator(
    activation: np.ndarray,
    weight: np.ndarray,
    bias: np.ndarray,
    x_zero_point: int,
    w_zero_point: np.ndarray,
    attributes: dict[str, Any],
) -> np.ndarray:
    centered_activation = activation.astype(np.int32) - int(x_zero_point)
    weight_zp = np.asarray(w_zero_point, dtype=np.int32).reshape(-1)
    if weight_zp.size == 1:
        weight_zp = np.repeat(weight_zp, weight.shape[0])
    centered_weight = weight.astype(np.int32) - weight_zp.reshape(-1, 1, 1, 1)
    pads = [int(item) for item in attributes.get("pads", [0, 0, 0, 0])]
    if pads != [pads[0], pads[1], pads[0], pads[1]]:
        centered_activation = np.pad(
            centered_activation,
            ((0, 0), (0, 0), (pads[0], pads[2]), (pads[1], pads[3])),
        )
        padding: int | tuple[int, int] = 0
    else:
        padding = (pads[0], pads[1])
    result = torch_functional.conv2d(
        torch.from_numpy(np.ascontiguousarray(centered_activation)),
        torch.from_numpy(np.ascontiguousarray(centered_weight)),
        torch.from_numpy(np.ascontiguousarray(bias.astype(np.int32))),
        stride=tuple(int(item) for item in attributes.get("strides", [1, 1])),
        padding=padding,
        dilation=tuple(int(item) for item in attributes.get("dilations", [1, 1])),
        groups=int(attributes.get("group", 1)),
    ).numpy()
    return _checked_int32(result, "Conv accumulator")


def matmul_accumulator(
    left: np.ndarray,
    right: np.ndarray,
    left_zero_point: int,
    right_zero_point: np.ndarray,
) -> np.ndarray:
    centered_left = left.astype(np.int32) - int(left_zero_point)
    centered_right = right.astype(np.int32) - np.asarray(
        right_zero_point, dtype=np.int32
    )
    result = centered_left.astype(np.int64) @ centered_right.astype(np.int64)
    return _checked_int32(result, "MatMul accumulator")


def global_average_sum(activation: np.ndarray, zero_point: int) -> np.ndarray:
    centered = activation.astype(np.int32) - int(zero_point)
    result = np.sum(centered, axis=tuple(range(2, activation.ndim)), keepdims=True, dtype=np.int64)
    return _checked_int32(result, "GlobalAveragePool sum")


def _quantize_linear(value: np.ndarray, scale: np.ndarray, zero_point: np.ndarray) -> np.ndarray:
    scale_value = np.asarray(scale, dtype=np.float32)
    zero = np.asarray(zero_point)
    rounded = np.rint(value.astype(np.float32) / scale_value).astype(np.int64)
    limits = np.iinfo(zero.dtype)
    return np.clip(rounded + zero.astype(np.int64), limits.min, limits.max).astype(zero.dtype)


def _dequantize_linear(value: np.ndarray, scale: np.ndarray, zero_point: np.ndarray) -> np.ndarray:
    return (
        (value.astype(np.int32) - np.asarray(zero_point, dtype=np.int32))
        .astype(np.float32)
        * np.asarray(scale, dtype=np.float32)
    ).astype(np.float32)


def _qlinear_add(inputs: list[np.ndarray]) -> np.ndarray:
    left = (inputs[0].astype(np.int32) - int(inputs[2])).astype(np.float32)
    right = (inputs[3].astype(np.int32) - int(inputs[5])).astype(np.float32)
    real_sum = left * np.float32(inputs[1]) + right * np.float32(inputs[4])
    shifted = np.rint(real_sum / np.float32(inputs[6])).astype(np.int64) + int(inputs[7])
    return np.clip(shifted, 0, 255).astype(np.uint8)


def _max_pool(value: np.ndarray, attributes: dict[str, Any]) -> np.ndarray:
    kernel = tuple(int(item) for item in attributes["kernel_shape"])
    strides = tuple(int(item) for item in attributes.get("strides", kernel))
    dilations = tuple(int(item) for item in attributes.get("dilations", [1, 1]))
    pads = [int(item) for item in attributes.get("pads", [0, 0, 0, 0])]
    if pads != [pads[0], pads[1], pads[0], pads[1]]:
        padded = np.pad(
            value,
            ((0, 0), (0, 0), (pads[0], pads[2]), (pads[1], pads[3])),
            constant_values=np.iinfo(value.dtype).min,
        )
        padding: int | tuple[int, int] = 0
    else:
        padded = value
        padding = (pads[0], pads[1])
    return torch_functional.max_pool2d(
        torch.from_numpy(np.ascontiguousarray(padded.astype(np.int32))),
        kernel_size=kernel,
        stride=strides,
        padding=padding,
        dilation=dilations,
        ceil_mode=bool(attributes.get("ceil_mode", 0)),
    ).numpy().astype(value.dtype)


def generate_subop_golden(
    model_path: Path,
    runtime_root: Path,
    output_root: Path,
    graph: ModelGraphCatalog,
    lowering: LoweringManifest,
) -> dict[str, Any]:
    runtime_manifest = json.loads(
        (runtime_root / "manifest.json").read_text(encoding="utf-8")
    )
    if runtime_manifest["model_sha256"] != graph.model_sha256:
        raise ValueError("runtime golden model hash differs from graph catalog")
    by_name = {item.onnx_name: item for item in graph.tensors}
    model = onnx.load(model_path, load_external_data=True)
    initializers = {
        item.name: np.array(
            numpy_helper.to_array(item, base_dir=str(model_path.parent)), copy=True
        )
        for item in model.graph.initializer
    }

    def tensor_value(name: str) -> np.ndarray:
        tensor = by_name[name]
        if tensor.kind == "initializer":
            return initializers[name]
        record = runtime_manifest["tensors"].get(tensor.tensor_id)
        if record is None:
            raise KeyError(f"runtime tensor is unavailable: {name}")
        return np.load(runtime_root / record["path"], allow_pickle=False)

    root = output_root.resolve()
    root.parent.mkdir(parents=True, exist_ok=True)
    if root.exists():
        raise FileExistsError(f"subop golden root already exists: {root}")
    torch.set_num_threads(1)
    records: dict[str, dict[str, Any]] = {}
    node_replays: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix=f".{root.name}-", dir=root.parent) as temporary:
        staging = Path(temporary) / root.name
        tensor_dir = staging / "tensors"
        tensor_dir.mkdir(parents=True)
        for node_proto, node_info in zip(model.graph.node, graph.nodes, strict=True):
            if node_proto.op_type not in {
                "QLinearConv",
                "QLinearGlobalAveragePool",
                "QLinearMatMul",
            }:
                inputs = [tensor_value(name) for name in node_proto.input if name]
                if node_proto.op_type == "QuantizeLinear":
                    replayed = _quantize_linear(inputs[0], inputs[1], inputs[2])
                    formula = "quantize_nearest_even"
                elif node_proto.op_type == "DequantizeLinear":
                    replayed = _dequantize_linear(inputs[0], inputs[1], inputs[2])
                    formula = "dequantize_affine"
                elif node_proto.op_type == "MaxPool":
                    replayed = _max_pool(inputs[0], _attributes(node_proto))
                    formula = "max_pool_uint8"
                elif node_proto.op_type == "QLinearAdd":
                    replayed = _qlinear_add(inputs)
                    formula = "qlinear_add_affine_requant"
                elif node_proto.op_type == "Flatten":
                    axis = int(_attributes(node_proto).get("axis", 1))
                    replayed = inputs[0].reshape(
                        int(np.prod(inputs[0].shape[:axis])),
                        int(np.prod(inputs[0].shape[axis:])),
                    )
                    formula = "view_flatten"
                else:
                    raise ValueError(f"no independent replay for {node_proto.op_type}")
                expected_output = tensor_value(node_proto.output[0])
                if not np.array_equal(replayed, expected_output):
                    mismatch = int(np.count_nonzero(replayed != expected_output))
                    raise ValueError(
                        f"{node_info.node_id} {node_proto.op_type} replay mismatch: {mismatch} elements"
                    )
                node_replays[node_info.node_id] = {
                    "op_type": node_proto.op_type,
                    "formula": formula,
                    "output_tensor_id": node_info.output_tensor_ids[0],
                    "matches_ort": True,
                }
                continue
            inputs = list(node_proto.input)
            if node_proto.op_type == "QLinearConv":
                accumulator = conv_accumulator(
                    tensor_value(inputs[0]),
                    tensor_value(inputs[3]),
                    tensor_value(inputs[8]),
                    int(tensor_value(inputs[2])),
                    tensor_value(inputs[5]),
                    _attributes(node_proto),
                )
                multiplier = (
                    np.float32(tensor_value(inputs[1]))
                    * tensor_value(inputs[4]).astype(np.float32)
                    / np.float32(tensor_value(inputs[6]))
                )
                output_zero_point = int(tensor_value(inputs[7]))
            elif node_proto.op_type == "QLinearGlobalAveragePool":
                activation = tensor_value(inputs[0])
                accumulator = global_average_sum(activation, int(tensor_value(inputs[2])))
                spatial_size = int(np.prod(activation.shape[2:]))
                multiplier = np.array(
                    np.float32(tensor_value(inputs[1]))
                    / (np.float32(tensor_value(inputs[3])) * spatial_size),
                    dtype=np.float32,
                )
                output_zero_point = int(tensor_value(inputs[4]))
            else:
                accumulator = matmul_accumulator(
                    tensor_value(inputs[0]),
                    tensor_value(inputs[3]),
                    int(tensor_value(inputs[2])),
                    tensor_value(inputs[5]),
                )
                multiplier = (
                    np.float32(tensor_value(inputs[1]))
                    * tensor_value(inputs[4]).astype(np.float32)
                    / np.float32(tensor_value(inputs[6]))
                )
                output_zero_point = int(tensor_value(inputs[7]))
            expected_output = tensor_value(node_proto.output[0])
            requantized = _requantize(accumulator, multiplier, output_zero_point)
            if not np.array_equal(requantized, expected_output):
                mismatch = int(np.count_nonzero(requantized != expected_output))
                raise ValueError(
                    f"{node_info.node_id} {node_proto.op_type} requant mismatch: {mismatch} elements"
                )
            node_replays[node_info.node_id] = {
                "op_type": node_proto.op_type,
                "formula": "int32_internal_then_requant",
                "output_tensor_id": node_info.output_tensor_ids[0],
                "matches_ort": True,
            }
            first_hw_op = lowering.for_node(node_info.node_id)[0]
            internal_tensor_id = first_hw_op.output_tensor_ids[0]
            path = tensor_dir / f"{internal_tensor_id}.npy"
            np.save(path, accumulator, allow_pickle=False)
            records[internal_tensor_id] = {
                "path": path.relative_to(staging).as_posix(),
                "sha256": sha256_file(path),
                "dtype": "int32",
                "shape": list(accumulator.shape),
                "minimum": int(accumulator.min()),
                "maximum": int(accumulator.max()),
                "node_id": node_info.node_id,
                "onnx_name": node_info.onnx_name,
                "op_type": node_info.op_type,
                "producer_hw_op_id": first_hw_op.hw_op_id,
                "requant_output_tensor_id": node_info.output_tensor_ids[0],
                "requant_matches_ort": True,
            }
        if set(records) != set(lowering.internal_tensor_ids):
            raise ValueError("subop generator did not produce every internal tensor")
        if set(node_replays) != {item.node_id for item in graph.nodes}:
            raise ValueError("independent formulas did not replay every ONNX node")
        manifest = {
            "schema_version": "0.1",
            "model_sha256": graph.model_sha256,
            "runtime_manifest_sha256": sha256_file(runtime_root / "manifest.json"),
            "internal_tensors": records,
            "node_replays": node_replays,
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(staging, root)
    return manifest
