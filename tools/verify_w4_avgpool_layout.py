from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from onnx import numpy_helper

from resnet50_pipeline.add16_layout import (
    QLinearAddBatch16PhysicalLayout,
    QLinearAddChannel16PhysicalLayout,
)
from resnet50_pipeline.avgpool16_layout import (
    GlobalAveragePoolBatch16PhysicalLayout,
    GlobalAveragePoolChannel16PhysicalLayout,
)
from resnet50_pipeline.hashing import sha256_file
from verify_w4_add_layout import _load_case as load_add_case
from verify_w4_conv0_layout import _array_hash


PORTS = (
    "A",
    "x_scale",
    "x_zero_point",
    "y_scale",
    "y_zero_point",
    "multiplier",
    "P",
    "D",
)


def _source(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
    }


def _profile(
    add_layout,
    pool_layout,
    add_case: dict[str, Any],
    pool_values: dict[str, np.ndarray],
    tensor_ids: dict[str, str],
) -> dict[str, Any]:
    producer = add_layout.forward(
        **add_case["values"], tensor_ids=add_case["tensor_ids"]
    )
    np.testing.assert_array_equal(add_case["values"]["output"], pool_values["activation"])
    input_bases = tuple(
        producer.region("D", slice_id).base_address for slice_id in range(16)
    )
    bundle = pool_layout.forward(
        **pool_values,
        tensor_ids=tensor_ids,
        input_base_addresses=input_bases,
    )
    producer_alias = pool_layout.prove_input_compatibility(
        producer, bundle, require_same_base=True
    )
    recovered = pool_layout.inverse(bundle)
    expected = {
        "A": pool_values["activation"],
        "x_scale": pool_values["x_scale"],
        "x_zero_point": pool_values["x_zero_point"],
        "y_scale": pool_values["y_scale"],
        "y_zero_point": pool_values["y_zero_point"],
        "multiplier": np.array([bundle.metadata["multiplier"]], dtype=np.float32),
        "P": pool_values["accumulator"],
        "D": pool_values["output"],
    }
    comparisons: dict[str, Any] = {}
    for port in PORTS:
        candidate = recovered[tensor_ids[port]]
        reference = expected[port]
        np.testing.assert_array_equal(candidate, reference)
        comparisons[port] = {
            "tensor_id": tensor_ids[port],
            "shape": list(reference.shape),
            "dtype": str(reference.dtype),
            "logical_sha256": _array_hash(reference),
            "inverse_sha256": _array_hash(candidate),
            "bit_exact": True,
        }
    flatten = pool_layout.prove_flatten_output_alias(
        bundle,
        output_shape=(pool_values["output"].shape[0], pool_values["output"].shape[1]),
        axis=1,
    )
    reduction = pool_layout.explain_reduction(bundle, batch=0, channel=0)
    result = {
        "add_contract": add_layout.contract,
        "pool_contract": pool_layout.contract,
        "channel_tile": bundle.metadata["channel_tile"],
        "spatial_size": bundle.metadata["spatial_size"],
        "multiplier": bundle.metadata["multiplier"],
        "per_slice_used_bytes_with_alias": bundle.metadata["per_slice_used_bytes"],
        "slice_capacity_bytes": bundle.geometry.bytes_per_slice,
        "logical_physical_bytes": sum(len(value) for value in bundle.payloads.values()),
        "layout_record_count": len(bundle.layout_records()),
        "validation": pool_layout.validate(bundle),
        "producer_add_d_to_pool_a": producer_alias,
        "pool_d_to_flatten": flatten,
        "reduction_probe": {
            "batch": reduction["batch"],
            "channel": reduction["channel"],
            "spatial_size": reduction["spatial_size"],
            "input_element_count": len(reduction["input_elements"]),
            "input_slice_ids": sorted(
                {item["slice_id"] for item in reduction["input_elements"]}
            ),
            "sum_slice_id": reduction["sum_slice_id"],
            "sum_addresses": list(reduction["sum_addresses"]),
            "formula": reduction["formula"],
        },
        "comparisons": comparisons,
        "all_inverse_bit_exact": True,
    }
    del producer, bundle, recovered
    gc.collect()
    return result


def verify(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    graph_path = root / "artifacts/w3/model_graph.json"
    subop_manifest_path = root / "artifacts/w3/subop_batch16/manifest.json"
    model_path = root / "artifacts/reference_model/resnet50-v1-12-int8.onnx"
    golden_root = root / "artifacts/w3/golden_batch16/tensors"
    subop_root = root / "artifacts/w3/subop_batch16/tensors"
    catalog = json.loads(graph_path.read_text(encoding="utf-8"))
    subop_manifest = json.loads(subop_manifest_path.read_text(encoding="utf-8"))
    nodes = {item["node_id"]: item for item in catalog["nodes"]}
    tensors = {item["tensor_id"]: item for item in catalog["tensors"]}
    node = nodes["node-0071"]
    producer_node = nodes[tensors[node["input_tensor_ids"][0]]["producer_node_id"]]
    if producer_node["node_id"] != "node-0070" or producer_node["op_type"] != "QLinearAdd":
        raise ValueError("formal GlobalAveragePool producer is not node-0070 QLinearAdd")
    replay = subop_manifest["node_replays"][node["node_id"]]
    if replay["formula"] != "int32_internal_then_requant" or not replay["matches_ort"]:
        raise ValueError("W3 GlobalAveragePool replay evidence is not valid")
    internal_id = "tensor-internal-node-0071-sum"
    internal = subop_manifest["internal_tensors"][internal_id]
    if not internal["requant_matches_ort"]:
        raise ValueError("W3 GlobalAveragePool requant evidence is not valid")

    model = onnx.load(model_path, load_external_data=True)
    initializers = {
        item.name: np.ascontiguousarray(
            numpy_helper.to_array(item, base_dir=str(model_path.parent))
        )
        for item in model.graph.initializer
    }
    node_proto = model.graph.node[int(node["graph_index"])]
    input_ids = node["input_tensor_ids"]
    output_id = node["output_tensor_ids"][0]
    activation_path = golden_root / f"{input_ids[0]}.npy"
    accumulator_path = subop_root / f"{internal_id}.npy"
    output_path = golden_root / f"{output_id}.npy"
    activation = np.load(activation_path, allow_pickle=False, mmap_mode="r")
    accumulator = np.load(accumulator_path, allow_pickle=False, mmap_mode="r")
    output = np.load(output_path, allow_pickle=False, mmap_mode="r")

    def initializer(index: int) -> np.ndarray:
        return initializers[node_proto.input[index]]

    pool_values = {
        "activation": activation,
        "x_scale": initializer(1),
        "x_zero_point": initializer(2),
        "y_scale": initializer(3),
        "y_zero_point": initializer(4),
        "accumulator": accumulator,
        "output": output,
        "channels_last": int(node["attributes"].get("channels_last", 0)),
    }
    tensor_ids = {
        "A": input_ids[0],
        "x_scale": input_ids[1],
        "x_zero_point": input_ids[2],
        "y_scale": input_ids[3],
        "y_zero_point": input_ids[4],
        "multiplier": "tensor-internal-node-0071-multiplier",
        "P": internal_id,
        "D": output_id,
    }
    add_case = load_add_case(root, producer_node, tensors, model, initializers)
    if producer_node["input_tensor_ids"][7] != input_ids[2]:
        raise ValueError("producer Add y_zero_point does not match pool x_zero_point")

    batch = _profile(
        QLinearAddBatch16PhysicalLayout(),
        GlobalAveragePoolBatch16PhysicalLayout(),
        add_case,
        pool_values,
        tensor_ids,
    )
    channel = _profile(
        QLinearAddChannel16PhysicalLayout(),
        GlobalAveragePoolChannel16PhysicalLayout(),
        add_case,
        pool_values,
        tensor_ids,
    )
    for port in PORTS:
        if (
            batch["comparisons"][port]["inverse_sha256"]
            != channel["comparisons"][port]["inverse_sha256"]
        ):
            raise ValueError(f"GlobalAveragePool profiles recover different {port}")
    return {
        "schema_version": "0.1",
        "model_sha256": catalog["model_sha256"],
        "node_id": node["node_id"],
        "onnx_name": node["onnx_name"],
        "attributes": node["attributes"],
        "input_shape": list(activation.shape),
        "sum_shape": list(accumulator.shape),
        "output_shape": list(output.shape),
        "producer_node_id": producer_node["node_id"],
        "producer_op_type": producer_node["op_type"],
        "producer_output_zero_point_tensor_id": producer_node["input_tensor_ids"][7],
        "pool_input_zero_point_tensor_id": input_ids[2],
        "producer_qparam_chain_exact": True,
        "w3_replay": replay,
        "w3_internal_sum": internal,
        "source_files": {
            "model_graph": _source(graph_path, root),
            "subop_manifest": _source(subop_manifest_path, root),
            "activation": _source(activation_path, root),
            "accumulator": _source(accumulator_path, root),
            "output": _source(output_path, root),
        },
        "profiles": {"batch": batch, "channel": channel},
        "all_profiles_inverse_bit_exact": True,
        "all_profiles_logical_bit_exact": True,
        "all_add_d_to_pool_a_exact_alias": True,
        "all_pool_d_to_flatten_zero_copy": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify W4 GlobalAveragePool layouts from existing W3 evidence"
    )
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
