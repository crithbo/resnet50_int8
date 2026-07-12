from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .conv16_layout import ConvBatch16PhysicalLayout
from .conv16_ring_layout import ConvRing16PhysicalLayout


@dataclass(frozen=True)
class ConvShapeFamily:
    family_id: str
    node_ids: tuple[str, ...]
    onnx_names: tuple[str, ...]
    activation_shape: tuple[int, int, int, int]
    weight_shape: tuple[int, int, int, int]
    output_shape: tuple[int, int, int, int]
    strides: tuple[int, int]
    pads: tuple[int, int, int, int]
    dilations: tuple[int, int]
    group: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _concrete_shape(shape: list[int | str], batch_size: int) -> tuple[int, ...]:
    result: list[int] = []
    for index, value in enumerate(shape):
        if isinstance(value, int):
            result.append(value)
        elif index == 0:
            result.append(batch_size)
        else:
            raise ValueError(f"non-batch symbolic Conv dimension is unsupported: {shape}")
    if any(value <= 0 for value in result):
        raise ValueError(f"Conv shape dimensions must be positive: {shape}")
    return tuple(result)


def conv_shape_families(
    catalog: dict[str, Any], *, batch_size: int = 16
) -> tuple[ConvShapeFamily, ...]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    tensors = {item["tensor_id"]: item for item in catalog["tensors"]}
    grouped: dict[str, dict[str, Any]] = {}
    for node in catalog["nodes"]:
        if node["op_type"] != "QLinearConv":
            continue
        activation_shape = _concrete_shape(
            tensors[node["input_tensor_ids"][0]]["shape"], batch_size
        )
        weight_shape = _concrete_shape(
            tensors[node["input_tensor_ids"][3]]["shape"], batch_size
        )
        output_shape = _concrete_shape(
            tensors[node["output_tensor_ids"][0]]["shape"], batch_size
        )
        attributes = node["attributes"]
        signature = {
            "activation_shape": activation_shape,
            "weight_shape": weight_shape,
            "output_shape": output_shape,
            "strides": tuple(int(value) for value in attributes.get("strides", (1, 1))),
            "pads": tuple(int(value) for value in attributes.get("pads", (0, 0, 0, 0))),
            "dilations": tuple(
                int(value) for value in attributes.get("dilations", (1, 1))
            ),
            "group": int(attributes.get("group", 1)),
        }
        encoded = json.dumps(signature, sort_keys=True, separators=(",", ":"))
        entry = grouped.setdefault(
            encoded,
            {"signature": signature, "node_ids": [], "onnx_names": []},
        )
        entry["node_ids"].append(node["node_id"])
        entry["onnx_names"].append(node["onnx_name"])

    families: list[ConvShapeFamily] = []
    for encoded, entry in sorted(grouped.items()):
        signature = entry["signature"]
        families.append(
            ConvShapeFamily(
                family_id="conv-family-" + hashlib.sha256(encoded.encode()).hexdigest()[:12],
                node_ids=tuple(entry["node_ids"]),
                onnx_names=tuple(entry["onnx_names"]),
                **signature,
            )
        )
    if len({family.family_id for family in families}) != len(families):
        raise ValueError("Conv family stable ID collision")
    return tuple(families)


def load_conv_shape_families(path: Path, *, batch_size: int = 16) -> tuple[ConvShapeFamily, ...]:
    return conv_shape_families(
        json.loads(path.read_text(encoding="utf-8")), batch_size=batch_size
    )


def validate_family_plans(
    family: ConvShapeFamily,
    batch_layout: ConvBatch16PhysicalLayout,
    ring_layout: ConvRing16PhysicalLayout,
) -> dict[str, Any]:
    kwargs = {
        "activation_shape": family.activation_shape,
        "weight_shape": family.weight_shape,
        "strides": family.strides,
        "pads": family.pads,
        "dilations": family.dilations,
        "group": family.group,
    }
    batch_plan = batch_layout.plan(**kwargs)
    ring_plan = ring_layout.plan(**kwargs)
    if batch_plan["output_shape"] != family.output_shape:
        raise ValueError(f"batch profile output mismatch for {family.family_id}")
    if ring_plan["output_shape"] != family.output_shape:
        raise ValueError(f"ring profile output mismatch for {family.family_id}")
    channels = family.activation_shape[1]
    outputs = family.weight_shape[0]
    c_tile = int(ring_plan["c_tile"])
    k_tile = int(ring_plan["k_tile"])
    c_owner = [min(channel // c_tile, 15) for channel in range(channels)]
    k_owner = [min(output // k_tile, 15) for output in range(outputs)]
    if any(owner < 0 or owner >= 16 for owner in c_owner + k_owner):
        raise ValueError(f"owner mapping escapes 16 slices for {family.family_id}")
    c_coverage = [0] * channels
    k_coverage = [0] * outputs
    for slice_id in range(16):
        for channel in range(slice_id * c_tile, min(channels, (slice_id + 1) * c_tile)):
            c_coverage[channel] += 1
        for output in range(slice_id * k_tile, min(outputs, (slice_id + 1) * k_tile)):
            k_coverage[output] += 1
    if c_coverage != [1] * channels or k_coverage != [1] * outputs:
        raise ValueError(f"C/K owner coverage is not exact for {family.family_id}")
    for owner in range(16):
        order = [(owner + step) % 16 for step in range(16)]
        if sorted(order) != list(range(16)):
            raise ValueError(f"ring traversal is not a permutation for {family.family_id}")
    return {
        "batch": {
            "per_slice_used_bytes": batch_plan["per_slice_used_bytes"],
            "capacity_bytes": batch_plan["capacity_bytes"],
            "capacity_margin_bytes": batch_plan["capacity_bytes"]
            - batch_plan["per_slice_used_bytes"],
            "c_padded": batch_plan["c_padded"],
            "k_padded": batch_plan["k_padded"],
        },
        "ring": {
            "per_slice_used_bytes": ring_plan["per_slice_used_bytes"],
            "capacity_bytes": ring_plan["capacity_bytes"],
            "capacity_margin_bytes": ring_plan["capacity_bytes"]
            - ring_plan["per_slice_used_bytes"],
            "c_tile": c_tile,
            "k_tile": k_tile,
            "c_padded": ring_plan["c_padded"],
            "k_padded": ring_plan["k_padded"],
            "active_c_slices": len(set(c_owner)),
            "active_k_slices": len(set(k_owner)),
            "all_owner_ranges_exact": True,
            "all_ring_orders_are_permutations": True,
        },
    }


def deterministic_layout_case(
    family: ConvShapeFamily, *, batch_size: int = 1
) -> dict[str, Any]:
    if batch_size <= 0 or batch_size > 16:
        raise ValueError("layout pattern batch_size must be 1..16")
    _, channels, height, width = family.activation_shape
    outputs, weight_channels, kernel_h, kernel_w = family.weight_shape
    _, _, output_h, output_w = family.output_shape

    def patterned(shape: tuple[int, ...], modulo: int, offset: int, dtype: np.dtype):
        size = int(np.prod(shape, dtype=np.int64))
        values = (np.arange(size, dtype=np.int64) % modulo) + offset
        return values.astype(dtype).reshape(shape)

    activation = patterned(
        (batch_size, channels, height, width), 251, 1, np.dtype("uint8")
    )
    weight = patterned(
        (outputs, weight_channels, kernel_h, kernel_w),
        255,
        -127,
        np.dtype("int8"),
    )
    bias = patterned((outputs,), 200001, -100000, np.dtype("int32"))
    w_scale = (
        np.float32(0.01)
        + (np.arange(outputs, dtype=np.float32) % np.float32(17)) * np.float32(0.001)
    ).astype(np.float32)
    w_zero_point = patterned((outputs,), 7, -3, np.dtype("int8"))
    accumulator = patterned(
        (batch_size, outputs, output_h, output_w),
        2000001,
        -1000000,
        np.dtype("int32"),
    )
    output = patterned(
        (batch_size, outputs, output_h, output_w), 253, 2, np.dtype("uint8")
    )
    return {
        "activation": activation,
        "weight": weight,
        "bias": bias,
        "w_scale": w_scale,
        "w_zero_point": w_zero_point,
        "x_scale": np.array([0.025], dtype=np.float32),
        "x_zero_point": np.array([111], dtype=np.uint8),
        "y_scale": np.array([0.04], dtype=np.float32),
        "y_zero_point": np.array([99], dtype=np.uint8),
        "accumulator": accumulator,
        "output": output,
        "strides": family.strides,
        "pads": family.pads,
        "dilations": family.dilations,
        "group": family.group,
    }
