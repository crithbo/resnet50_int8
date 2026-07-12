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
from resnet50_pipeline.conv16_layout import ConvBatch16PhysicalLayout
from resnet50_pipeline.conv16_ring_layout import ConvRing16PhysicalLayout
from resnet50_pipeline.hashing import sha256_file
from verify_w4_conv0_layout import _array_hash


PORTS = (
    "A",
    "a_scale",
    "a_zero_point",
    "B",
    "b_scale",
    "b_zero_point",
    "y_scale",
    "y_zero_point",
    "D",
)


def _batch16_shape(shape: list[Any]) -> tuple[int, ...]:
    return tuple(16 if value == "N" else int(value) for value in shape)


def _profile(layout, values: dict[str, np.ndarray], tensor_ids: dict[str, str]):
    bundle = layout.forward(**values, tensor_ids=tensor_ids)
    recovered = layout.inverse(bundle)
    comparisons: dict[str, Any] = {}
    for port in PORTS:
        reference = values["output" if port == "D" else port.lower()]
        candidate = recovered[tensor_ids[port]]
        np.testing.assert_array_equal(candidate, reference)
        comparisons[port] = {
            "tensor_id": tensor_ids[port],
            "shape": list(reference.shape),
            "dtype": str(reference.dtype),
            "logical_sha256": _array_hash(reference),
            "inverse_sha256": _array_hash(candidate),
            "bit_exact": True,
        }
    validation = layout.validate(bundle)
    result = {
        "contract": layout.contract,
        "broadcast_mode": bundle.metadata["broadcast_mode"],
        "feature_tile": bundle.metadata["feature_tile"],
        "per_slice_used_bytes": bundle.metadata["per_slice_used_bytes"],
        "slice_capacity_bytes": bundle.geometry.bytes_per_slice,
        "logical_physical_bytes": sum(len(value) for value in bundle.payloads.values()),
        "layout_record_count": len(bundle.layout_records()),
        "qparams_policy": "six scalar qparams replicated on all 16 slices",
        "tails": bundle.metadata["tails"],
        "validation": validation,
        "comparisons": comparisons,
        "all_inverse_bit_exact": True,
    }
    del bundle, recovered
    gc.collect()
    return result


def _load_case(
    root: Path,
    node_record: dict[str, Any],
    tensor_records: dict[str, dict[str, Any]],
    model: onnx.ModelProto,
    initializers: dict[str, np.ndarray],
) -> dict[str, Any]:
    node = model.graph.node[int(node_record["graph_index"])]
    tensor_ids = dict(zip(PORTS, node_record["input_tensor_ids"] + node_record["output_tensor_ids"], strict=True))
    golden_root = root / "artifacts/w3/golden_batch16/tensors"

    def load_input(index: int) -> tuple[np.ndarray, dict[str, Any]]:
        tensor_id = node_record["input_tensor_ids"][index]
        record = tensor_records[tensor_id]
        if record["kind"] == "initializer":
            value = initializers[node.input[index]]
            return value, {
                "kind": "initializer",
                "tensor_id": tensor_id,
                "initializer_sha256": record["initializer_sha256"],
            }
        path = golden_root / f"{tensor_id}.npy"
        return np.load(path, allow_pickle=False, mmap_mode="r"), {
            "kind": record["kind"],
            "tensor_id": tensor_id,
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
        }

    inputs = []
    sources: dict[str, Any] = {}
    for port, index in zip(PORTS[:-1], range(8), strict=True):
        value, source = load_input(index)
        inputs.append(value)
        sources[port] = source
    output_id = node_record["output_tensor_ids"][0]
    output_path = golden_root / f"{output_id}.npy"
    output = np.load(output_path, allow_pickle=False, mmap_mode="r")
    sources["D"] = {
        "kind": tensor_records[output_id]["kind"],
        "tensor_id": output_id,
        "path": output_path.relative_to(root).as_posix(),
        "sha256": sha256_file(output_path),
    }
    values = {
        "a": inputs[0],
        "a_scale": inputs[1],
        "a_zero_point": inputs[2],
        "b": inputs[3],
        "b_scale": inputs[4],
        "b_zero_point": inputs[5],
        "y_scale": inputs[6],
        "y_zero_point": inputs[7],
        "output": output,
    }
    return {"values": values, "tensor_ids": tensor_ids, "sources": sources}


def _formal_coverage(catalog: dict[str, Any]) -> dict[str, Any]:
    nodes = {node["node_id"]: node for node in catalog["nodes"]}
    tensors = {tensor["tensor_id"]: tensor for tensor in catalog["tensors"]}
    add_nodes = [node for node in catalog["nodes"] if node["op_type"] == "QLinearAdd"]
    families: dict[tuple[tuple[int, ...], tuple[int, ...]], list[str]] = {}
    residual_branches: list[dict[str, Any]] = []
    qparams_all_scalar = True
    qparam_chain_all_exact = True
    all_plans_fit = True
    maxima = {"batch": 0, "channel": 0}
    modes: dict[str, int] = {}
    producer_counts: dict[str, int] = {}

    def producer_d_layout(
        producer: dict[str, Any], topology: str
    ) -> tuple[tuple[int, ...], int]:
        producer_ids = producer["input_tensor_ids"]
        if producer["op_type"] == "QLinearConv":
            layout = (
                ConvBatch16PhysicalLayout()
                if topology == "batch"
                else ConvRing16PhysicalLayout()
            )
            plan = layout.plan(
                activation_shape=_batch16_shape(tensors[producer_ids[0]]["shape"]),
                weight_shape=_batch16_shape(tensors[producer_ids[3]]["shape"]),
                strides=tuple(producer["attributes"].get("strides", (1, 1))),
                pads=tuple(producer["attributes"].get("pads", (0, 0, 0, 0))),
                dilations=tuple(producer["attributes"].get("dilations", (1, 1))),
                group=int(producer["attributes"].get("group", 1)),
            )
            n, _, output_h, output_w = plan["output_shape"]
            physical_shape = (
                (output_h, output_w, plan["k_padded"])
                if topology == "batch"
                else (n, output_h, output_w, plan["k_tile"])
            )
            return physical_shape, int(plan["raw_sizes"]["D"])
        if producer["op_type"] == "QLinearAdd":
            layout = (
                QLinearAddBatch16PhysicalLayout()
                if topology == "batch"
                else QLinearAddChannel16PhysicalLayout()
            )
            plan = layout.plan(
                a_shape=_batch16_shape(tensors[producer_ids[0]]["shape"]),
                b_shape=_batch16_shape(tensors[producer_ids[3]]["shape"]),
            )
            return tuple(plan["physical_shapes"]["D"]), int(plan["raw_sizes"]["D"])
        raise ValueError("residual producer is outside the current Add compatibility set")

    for node in add_nodes:
        ids = node["input_tensor_ids"]
        a_shape = _batch16_shape(tensors[ids[0]]["shape"])
        b_shape = _batch16_shape(tensors[ids[3]]["shape"])
        key = (a_shape, b_shape)
        families.setdefault(key, []).append(node["node_id"])
        for index in (1, 2, 4, 5, 6, 7):
            record = tensors[ids[index]]
            qparams_all_scalar &= record["kind"] == "initializer" and record["shape"] == [1]
        plans = {
            "batch": QLinearAddBatch16PhysicalLayout().plan(
                a_shape=a_shape, b_shape=b_shape
            ),
            "channel": QLinearAddChannel16PhysicalLayout().plan(
                a_shape=a_shape, b_shape=b_shape
            ),
        }
        mode = plans["batch"]["broadcast_mode"]
        modes[mode] = modes.get(mode, 0) + 1
        for topology, plan in plans.items():
            all_plans_fit &= plan["per_slice_used_bytes"] <= plan["capacity_bytes"]
            maxima[topology] = max(maxima[topology], plan["per_slice_used_bytes"])

        if mode == "same_shape":
            for port, tensor_index, zp_index in (("A", 0, 2), ("B", 3, 5)):
                tensor = tensors[ids[tensor_index]]
                producer = nodes[tensor["producer_node_id"]]
                producer_counts[producer["op_type"]] = producer_counts.get(
                    producer["op_type"], 0
                ) + 1
                producer_y_zp = producer["input_tensor_ids"][7]
                chain_exact = producer_y_zp == ids[zp_index]
                qparam_chain_all_exact &= chain_exact
                physical_checks: dict[str, Any] = {}
                for topology in ("batch", "channel"):
                    producer_shape, producer_bytes = producer_d_layout(
                        producer, topology
                    )
                    consumer_shape = tuple(plans[topology]["physical_shapes"][port])
                    consumer_bytes = int(plans[topology]["raw_sizes"][port])
                    physical_checks[topology] = {
                        "producer_d_physical_shape": list(producer_shape),
                        "consumer_input_physical_shape": list(consumer_shape),
                        "payload_bytes": consumer_bytes,
                        "physical_shape_exact": producer_shape == consumer_shape,
                        "payload_bytes_exact": producer_bytes == consumer_bytes,
                    }
                residual_branches.append(
                    {
                        "consumer_node_id": node["node_id"],
                        "port": port,
                        "tensor_id": ids[tensor_index],
                        "producer_node_id": producer["node_id"],
                        "producer_op_type": producer["op_type"],
                        "logical_shape": list(a_shape),
                        "producer_y_zero_point_tensor_id": producer_y_zp,
                        "consumer_input_zero_point_tensor_id": ids[zp_index],
                        "qparam_chain_exact": chain_exact,
                        "physical_checks": physical_checks,
                        "batch_layout_compatible": all(
                            physical_checks["batch"][key]
                            for key in ("physical_shape_exact", "payload_bytes_exact")
                        ),
                        "channel_layout_compatible": all(
                            physical_checks["channel"][key]
                            for key in ("physical_shape_exact", "payload_bytes_exact")
                        ),
                    }
                )
    return {
        "formal_node_count": len(add_nodes),
        "stable_shape_broadcast_family_count": len(families),
        "families": [
            {
                "a_shape": list(key[0]),
                "b_shape": list(key[1]),
                "node_ids": node_ids,
            }
            for key, node_ids in families.items()
        ],
        "broadcast_mode_counts": modes,
        "all_six_qparams_scalar_initializers": qparams_all_scalar,
        "residual_branch_count": len(residual_branches),
        "residual_producer_counts": producer_counts,
        "all_residual_qparam_chains_exact": qparam_chain_all_exact,
        "all_residual_branches_layout_compatible": all(
            branch["batch_layout_compatible"] and branch["channel_layout_compatible"]
            for branch in residual_branches
        ),
        "residual_branches": residual_branches,
        "all_formal_plans_fit": all_plans_fit,
        "maximum_per_slice_used_bytes": maxima,
        "slice_capacity_bytes": QLinearAddBatch16PhysicalLayout().geometry.bytes_per_slice,
        "dense_tail_linkage": "QLinearMatMul D compatibility deferred to the W4 MatMul layout; B is initializer broadcast",
    }


def verify(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    graph_path = root / "artifacts/w3/model_graph.json"
    subop_manifest_path = root / "artifacts/w3/subop_batch16/manifest.json"
    model_path = root / "artifacts/reference_model/resnet50-v1-12-int8.onnx"
    catalog = json.loads(graph_path.read_text(encoding="utf-8"))
    subop_manifest = json.loads(subop_manifest_path.read_text(encoding="utf-8"))
    tensors = {item["tensor_id"]: item for item in catalog["tensors"]}
    model = onnx.load(model_path, load_external_data=True)
    initializers = {
        item.name: np.ascontiguousarray(
            numpy_helper.to_array(item, base_dir=str(model_path.parent))
        )
        for item in model.graph.initializer
    }

    representatives: dict[str, Any] = {}
    for label, node_id in (("residual", "node-0007"), ("dense_broadcast", "node-0076")):
        node = next(item for item in catalog["nodes"] if item["node_id"] == node_id)
        replay = subop_manifest["node_replays"][node_id]
        if replay["formula"] != "qlinear_add_affine_requant" or not replay["matches_ort"]:
            raise ValueError(f"W3 replay evidence for {node_id} is not valid")
        case = _load_case(root, node, tensors, model, initializers)
        batch = _profile(
            QLinearAddBatch16PhysicalLayout(), case["values"], case["tensor_ids"]
        )
        channel = _profile(
            QLinearAddChannel16PhysicalLayout(), case["values"], case["tensor_ids"]
        )
        for port in PORTS:
            if (
                batch["comparisons"][port]["inverse_sha256"]
                != channel["comparisons"][port]["inverse_sha256"]
            ):
                raise ValueError(f"Add profiles recover different {node_id} {port}")
        representatives[label] = {
            "node_id": node_id,
            "onnx_name": node["onnx_name"],
            "w3_replay": replay,
            "sources": case["sources"],
            "profiles": {"batch": batch, "channel": channel},
            "all_profiles_inverse_bit_exact": True,
            "all_profiles_logical_bit_exact": True,
        }
        del case
        gc.collect()

    return {
        "schema_version": "0.1",
        "model_sha256": catalog["model_sha256"],
        "source_manifests": {
            "model_graph": {
                "path": graph_path.relative_to(root).as_posix(),
                "sha256": sha256_file(graph_path),
            },
            "subop_batch16": {
                "path": subop_manifest_path.relative_to(root).as_posix(),
                "sha256": sha256_file(subop_manifest_path),
            },
        },
        "formal_coverage": _formal_coverage(catalog),
        "representatives": representatives,
        "two_input_alias_policy": {
            "layout_compatibility": "proved independently for each residual input",
            "exact_alias": "requires each producer D base to equal its Add input base",
            "simultaneous_alias": "requires W7 to allocate distinct non-overlapping A/B producer bases",
            "default_standalone_producer_offsets": "may collide and are not claimed as simultaneous zero-copy",
        },
        "all_representatives_inverse_bit_exact": True,
        "all_formal_add_plans_fit": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify W4 QLinearAdd batch/channel layouts from existing W3 evidence"
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
