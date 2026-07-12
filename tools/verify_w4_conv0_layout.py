from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from onnx import numpy_helper

from resnet50_pipeline.conv16_layout import ConvBatch16PhysicalLayout
from resnet50_pipeline.hashing import sha256_file


def _array_hash(array: np.ndarray) -> str:
    canonical = np.ascontiguousarray(array.astype(array.dtype.newbyteorder("<"), copy=False))
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


def _load_graph_catalog(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    node = next(item for item in value["nodes"] if item["node_id"] == "node-0001")
    tensors = {item["tensor_id"]: item for item in value["tensors"]}
    return node, tensors


def load_formal_conv0_case(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    model_path = root / "artifacts/reference_model/resnet50-v1-12-int8.onnx"
    graph_path = root / "artifacts/w3/model_graph.json"
    golden_root = root / "artifacts/w3/golden_batch16/tensors"
    subop_root = root / "artifacts/w3/subop_batch16/tensors"
    node_record, tensors = _load_graph_catalog(graph_path)
    model = onnx.load(model_path, load_external_data=True)
    node = model.graph.node[int(node_record["graph_index"])]
    if node.op_type != "QLinearConv":
        raise ValueError("node-0001 is not QLinearConv in the formal model")
    initializers = {
        item.name: np.ascontiguousarray(numpy_helper.to_array(item, base_dir=str(model_path.parent)))
        for item in model.graph.initializer
    }

    input_ids = node_record["input_tensor_ids"]
    output_id = node_record["output_tensor_ids"][0]
    activation_path = golden_root / f"{input_ids[0]}.npy"
    output_path = golden_root / f"{output_id}.npy"
    accumulator_id = "tensor-internal-node-0001-accumulate"
    accumulator_path = subop_root / f"{accumulator_id}.npy"
    activation = np.load(activation_path, allow_pickle=False)
    accumulator = np.load(accumulator_path, allow_pickle=False)
    output = np.load(output_path, allow_pickle=False)
    initializer = lambda index: initializers[node.input[index]]
    weight = initializer(3)
    w_scale = initializer(4)
    w_zero_point = initializer(5)
    bias = initializer(8)
    x_scale = initializer(1)
    x_zero_point = initializer(2)
    y_scale = initializer(6)
    y_zero_point = initializer(7)
    attributes = {
        item.name: onnx.helper.get_attribute_value(item) for item in node.attribute
    }
    tensor_ids = {
        "A": input_ids[0],
        "x_scale": input_ids[1],
        "x_zero_point": input_ids[2],
        "B": input_ids[3],
        "w_scale": input_ids[4],
        "w_zero_point": input_ids[5],
        "y_scale": input_ids[6],
        "y_zero_point": input_ids[7],
        "bias": input_ids[8],
        "multiplier": "tensor-internal-node-0001-multiplier",
        "P": accumulator_id,
        "D": output_id,
    }
    values = {
        "activation": activation,
        "weight": weight,
        "bias": bias,
        "w_scale": w_scale,
        "w_zero_point": w_zero_point,
        "x_scale": x_scale,
        "x_zero_point": x_zero_point,
        "y_scale": y_scale,
        "y_zero_point": y_zero_point,
        "accumulator": accumulator,
        "output": output,
        "strides": tuple(attributes.get("strides", (1, 1))),
        "pads": tuple(attributes.get("pads", (0, 0, 0, 0))),
        "dilations": tuple(attributes.get("dilations", (1, 1))),
        "group": int(attributes.get("group", 1)),
        "tensor_ids": tensor_ids,
    }
    expected = {
        input_ids[0]: activation,
        input_ids[1]: x_scale.reshape(1),
        input_ids[2]: x_zero_point.reshape(1),
        input_ids[3]: weight,
        input_ids[4]: w_scale.reshape(-1),
        input_ids[5]: w_zero_point.reshape(-1),
        input_ids[6]: y_scale.reshape(1),
        input_ids[7]: y_zero_point.reshape(1),
        input_ids[8]: bias,
        accumulator_id: accumulator,
        output_id: output,
    }
    return {
        "root": root,
        "model_path": model_path,
        "node_record": node_record,
        "tensors": tensors,
        "activation_path": activation_path,
        "accumulator_path": accumulator_path,
        "output_path": output_path,
        "values": values,
        "expected": expected,
        "tensor_ids": tensor_ids,
    }


def verify(project_root: Path) -> dict[str, Any]:
    case = load_formal_conv0_case(project_root)
    root = case["root"]
    model_path = case["model_path"]
    node_record = case["node_record"]
    tensors = case["tensors"]
    activation_path = case["activation_path"]
    accumulator_path = case["accumulator_path"]
    output_path = case["output_path"]
    values = case["values"]
    tensor_ids = case["tensor_ids"]
    expected = case["expected"]
    layout = ConvBatch16PhysicalLayout()
    bundle = layout.forward(
        **values,
    )
    recovered = layout.inverse(bundle)
    comparisons: dict[str, Any] = {}
    for tensor_id, reference in expected.items():
        candidate = recovered[tensor_id]
        np.testing.assert_array_equal(candidate, reference)
        comparisons[tensor_id] = {
            "onnx_name": tensors.get(tensor_id, {}).get("onnx_name"),
            "shape": list(reference.shape),
            "dtype": str(reference.dtype),
            "element_bytes_sha256": _array_hash(reference),
            "inverse_element_bytes_sha256": _array_hash(candidate),
            "bit_exact": True,
        }
    multiplier_id = tensor_ids["multiplier"]
    expected_multiplier = (
        np.float32(values["x_scale"].reshape(-1)[0])
        * values["w_scale"].astype(np.float32).reshape(-1)
        / np.float32(values["y_scale"].reshape(-1)[0])
    ).astype(np.float32)
    np.testing.assert_array_equal(recovered[multiplier_id], expected_multiplier)
    comparisons[multiplier_id] = {
        "shape": list(expected_multiplier.shape),
        "dtype": "float32",
        "element_bytes_sha256": _array_hash(expected_multiplier),
        "inverse_element_bytes_sha256": _array_hash(recovered[multiplier_id]),
        "bit_exact": True,
    }
    validation = layout.validate(bundle)
    return {
        "schema_version": "0.1",
        "contract": layout.contract,
        "status": layout.status,
        "node_id": node_record["node_id"],
        "onnx_name": node_record["onnx_name"],
        "model_sha256": sha256_file(model_path),
        "source_files": {
            "activation": {"path": activation_path.relative_to(root).as_posix(), "sha256": sha256_file(activation_path)},
            "accumulator": {"path": accumulator_path.relative_to(root).as_posix(), "sha256": sha256_file(accumulator_path)},
            "output": {"path": output_path.relative_to(root).as_posix(), "sha256": sha256_file(output_path)},
        },
        "attributes": {
            "strides": list(bundle.metadata["strides"]),
            "pads": list(bundle.metadata["pads"]),
            "dilations": list(bundle.metadata["dilations"]),
            "group": bundle.metadata["group"],
        },
        "c_padded": bundle.metadata["c_padded"],
        "k_padded": bundle.metadata["k_padded"],
        "per_slice_used_bytes": bundle.metadata["per_slice_used_bytes"],
        "slice_capacity_bytes": bundle.geometry.bytes_per_slice,
        "logical_physical_bytes": sum(len(value) for value in bundle.payloads.values()),
        "layout_record_count": len(bundle.layout_records()),
        "validation": validation,
        "comparisons": comparisons,
        "all_inverse_bit_exact": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify W4 Conv0 batch16 relayout")
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.project_root)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output
        if not output.is_absolute():
            output = args.project_root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
