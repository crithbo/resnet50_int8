from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from resnet50_pipeline.conv28_layout import (
    PORT_ORDER,
    Conv28PhysicalPlan,
    QLinearConvPhysicalLayout,
)
from resnet50_pipeline.profile28 import (
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
)
from resnet50_pipeline.topology28 import HIGH_RING_OWNERS, LOW_RING_OWNERS


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _array_hash(array: np.ndarray) -> str:
    canonical = np.ascontiguousarray(array)
    return _sha256(canonical.tobytes(order="C"))


def _plan_report(plan: Conv28PhysicalPlan) -> dict[str, Any]:
    return {
        "contract": plan.contract,
        "profile_id": plan.profile_id,
        "activation_shape": list(plan.activation_shape),
        "weight_shape": list(plan.weight_shape),
        "output_shape": list(plan.output_shape),
        "strides": list(plan.strides),
        "pads": list(plan.pads),
        "dilations": list(plan.dilations),
        "c_tile": plan.c_tile,
        "k_tile": plan.k_tile,
        "c_padded": plan.c_padded,
        "storage_sample_count": plan.storage_sample_count,
        "capacity": plan.capacity_report(),
        "ports": {
            port.port: {
                "logical_shape": list(port.logical_shape),
                "dtype": port.dtype,
                "owner_axis": port.owner_axis,
                "physical_shape": list(port.physical_shape),
                "physical_axis_order": port.physical_axis_order,
                "payload_bytes": port.payload_bytes,
                "offset_bytes": port.offset_bytes,
                "tail_rule": port.tail_rule,
            }
            for port in plan.ports
        },
    }


def _small_case() -> dict[str, np.ndarray]:
    activation = np.arange(16 * 5 * 3 * 2, dtype=np.uint16).astype(
        np.uint8
    ).reshape(16, 5, 3, 2)
    weight = (
        np.arange(7 * 5 * 2, dtype=np.int16) % 101 - 50
    ).astype(np.int8).reshape(7, 5, 2, 1)
    output_shape = (16, 7, 2, 2)
    return {
        "activation": activation,
        "weight": weight,
        "bias": np.arange(7, dtype=np.int32) - 3,
        "w_scale": np.linspace(0.125, 0.875, 7, dtype=np.float32),
        "w_zero_point": (np.arange(7, dtype=np.int16) - 3).astype(np.int8),
        "x_scale": np.array([0.25], dtype=np.float32),
        "x_zero_point": np.array([113], dtype=np.uint8),
        "y_scale": np.array([0.5], dtype=np.float32),
        "y_zero_point": np.array([127], dtype=np.uint8),
        "accumulator": np.arange(np.prod(output_shape), dtype=np.int32).reshape(
            output_shape
        ),
        "output": np.arange(np.prod(output_shape), dtype=np.uint16).astype(
            np.uint8
        ).reshape(output_shape),
    }


def _roundtrip(profile_id: str) -> dict[str, Any]:
    layout = QLinearConvPhysicalLayout(profile_id=profile_id)
    values = _small_case()
    bundle = layout.forward(**values)
    recovered = layout.inverse(bundle)
    sources = {
        "A": values["activation"],
        "B": values["weight"],
        "bias": values["bias"],
        "w_scale": values["w_scale"],
        "w_zero_point": values["w_zero_point"],
        "x_scale": values["x_scale"],
        "x_zero_point": values["x_zero_point"],
        "y_scale": values["y_scale"],
        "y_zero_point": values["y_zero_point"],
        "P": values["accumulator"],
        "D": values["output"],
    }
    comparisons: dict[str, Any] = {}
    for port in PORT_ORDER:
        candidate = recovered[bundle.tensor_ids[port]]
        np.testing.assert_array_equal(candidate, sources[port])
        comparisons[port] = {
            "logical_sha256": _array_hash(sources[port]),
            "inverse_sha256": _array_hash(candidate),
            "bit_exact": True,
        }
    physical = b"".join(
        bundle.read(port, slice_id)
        for port in PORT_ORDER
        for slice_id in range(28)
    )
    return {
        "contract": layout.contract,
        "profile_id": profile_id,
        "validation": layout.validate(bundle),
        "layout_record_count": len(bundle.layout_records()),
        "physical_sha256": _sha256(physical),
        "physical_bytes": len(physical),
        "comparisons": comparisons,
        "all_inverse_bit_exact": True,
    }


def _shape(value: list[int | str]) -> tuple[int, ...]:
    return tuple(16 if item == "N" else int(item) for item in value)


def _formal_cases(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tensors = {item["tensor_id"]: item for item in catalog["tensors"]}
    conv_nodes = [item for item in catalog["nodes"] if item["op_type"] == "QLinearConv"]

    def case(node: dict[str, Any]) -> dict[str, Any]:
        activation = _shape(tensors[node["input_tensor_ids"][0]]["shape"])
        weight = _shape(tensors[node["input_tensor_ids"][3]]["shape"])
        expected_output = _shape(tensors[node["output_tensor_ids"][0]]["shape"])
        attributes = node["attributes"]
        return {
            "node_id": node["node_id"],
            "onnx_name": node["onnx_name"],
            "activation_shape": activation,
            "weight_shape": weight,
            "expected_output_shape": expected_output,
            "strides": tuple(attributes.get("strides", (1, 1))),
            "pads": tuple(attributes.get("pads", (0, 0, 0, 0))),
            "dilations": tuple(attributes.get("dilations", (1, 1))),
            "group": int(attributes.get("group", 1)),
        }

    conv0 = case(conv_nodes[0])
    downsample = next(
        case(node)
        for node in conv_nodes
        if node["attributes"].get("kernel_shape") == [1, 1]
        and node["attributes"].get("strides") == [2, 2]
    )
    terminal = next(
        case(node)
        for node in reversed(conv_nodes)
        if _shape(tensors[node["input_tensor_ids"][0]]["shape"])
        == (16, 512, 7, 7)
        and _shape(tensors[node["input_tensor_ids"][3]]["shape"])
        == (2048, 512, 1, 1)
    )
    return {"conv0": conv0, "downsample_1x1": downsample, "terminal_1x1": terminal}


def verify(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    graph_path = root / "artifacts/w3/model_graph.json"
    catalog = json.loads(graph_path.read_text(encoding="utf-8"))
    cases = _formal_cases(catalog)
    formal: dict[str, Any] = {}
    for name, item in cases.items():
        profiles: dict[str, Any] = {}
        for profile_id in (
            GROUP4X7_BATCH_CHANNEL28_PROFILE,
            GLOBAL_RING28_PROFILE,
        ):
            layout = QLinearConvPhysicalLayout(profile_id=profile_id)
            plan = layout.formal_plan(
                activation_shape=item["activation_shape"],
                weight_shape=item["weight_shape"],
                strides=item["strides"],
                pads=item["pads"],
                dilations=item["dilations"],
                group=item["group"],
            )
            if plan.output_shape != item["expected_output_shape"]:
                raise ValueError(f"formal {name} output shape differs from W3 metadata")
            profiles[profile_id] = _plan_report(plan)
        formal[name] = {
            "node_id": item["node_id"],
            "onnx_name": item["onnx_name"],
            "profiles": profiles,
        }
    return {
        "schema_version": "0.1",
        "evidence_scope": "small_deterministic_candidate_software_report",
        "status": "candidate_unapproved",
        "target_family": "rtl28",
        "hardware_approval": False,
        "g4_authority": False,
        "w5_authorized": False,
        "geometry_status": "candidate_unapproved",
        "address_order_status": "candidate_unapproved",
        "model_sha256": catalog["model_sha256"],
        "model_graph_sha256": _sha256(graph_path.read_bytes()),
        "topology": {
            "high_ring_owners": [list(item) for item in HIGH_RING_OWNERS],
            "low_ring_owners": list(LOW_RING_OWNERS),
            "numeric_adjacency_or_modulo_used": False,
        },
        "formal_plans": formal,
        "small_roundtrips": {
            profile: _roundtrip(profile)
            for profile in (
                GROUP4X7_BATCH_CHANNEL28_PROFILE,
                GLOBAL_RING28_PROFILE,
            )
        },
        "all_small_inverse_bit_exact": True,
        "note": (
            "This report is software candidate evidence only; it is not a hardware "
            "approval, does not pass G4, and does not authorize W5."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate small deterministic RTL28 Conv candidate evidence"
    )
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="explicit optional output path; omitted means stdout only",
    )
    args = parser.parse_args()
    report = verify(args.project_root)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(encoded.encode("utf-8"))
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
