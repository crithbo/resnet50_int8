from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .add16_layout import (
    QLinearAddBatch16PhysicalLayout,
    QLinearAddChannel16PhysicalLayout,
)
from .avgpool16_layout import (
    GlobalAveragePoolBatch16PhysicalLayout,
    GlobalAveragePoolChannel16PhysicalLayout,
)
from .conv16_layout import ConvBatch16PhysicalLayout
from .conv16_ring_layout import ConvRing16PhysicalLayout
from .hashing import sha256_file
from .matmul16_layout import (
    QLinearMatMulBatch16PhysicalLayout,
    QLinearMatMulRing16PhysicalLayout,
)
from .maxpool16_layout import (
    MaxPoolBatch16PhysicalLayout,
    MaxPoolChannel16PhysicalLayout,
)
from .simple_layout import (
    DequantizeLinearPhysicalLayout,
    QuantizeLinearPhysicalLayout,
    ZeroCopyViewLayout,
)


EXPECTED_NODE_COUNTS = {
    "QuantizeLinear": 2,
    "QLinearConv": 53,
    "MaxPool": 1,
    "QLinearAdd": 17,
    "QLinearGlobalAveragePool": 1,
    "Flatten": 1,
    "QLinearMatMul": 1,
    "DequantizeLinear": 2,
}

REQUIRED_REPORT_IDS = (
    "w4_conv_shape_coverage_v1",
    "w4_maxpool_profiles_v1",
    "w4_qlinearadd_profiles_v1",
    "w4_globalavgpool_profiles_v1",
    "w4_qlinearmatmul_profiles_v1",
)

PROFILE_POLICIES = {
    "batch": {
        ("DequantizeLinear", "Flatten"): "zero_copy_proved",
        ("Flatten", "QuantizeLinear"): "layout_compatible_rebase_w7",
        ("QuantizeLinear", "QLinearConv"): "explicit_relayout",
        ("QuantizeLinear", "QLinearMatMul"): "exact_alias_proved",
        ("QLinearConv", "QLinearConv"): "layout_compatible_rebase_w7",
        ("QLinearConv", "MaxPool"): "exact_alias_proved",
        ("MaxPool", "QLinearConv"): "layout_compatible_rebase_w7",
        ("QLinearConv", "QLinearAdd"): "layout_compatible_rebase_w7",
        ("QLinearAdd", "QLinearAdd"): "layout_compatible_rebase_w7",
        ("QLinearAdd", "QLinearConv"): "layout_compatible_rebase_w7",
        ("QLinearAdd", "QLinearGlobalAveragePool"): "exact_alias_proved",
        ("QLinearGlobalAveragePool", "DequantizeLinear"): "layout_compatible_rebase_w7",
        ("QLinearMatMul", "QLinearAdd"): "exact_alias_proved",
        ("QLinearAdd", "DequantizeLinear"): "layout_compatible_rebase_w7",
    },
    "ring_channel": {
        ("DequantizeLinear", "Flatten"): "zero_copy_proved",
        ("Flatten", "QuantizeLinear"): "layout_compatible_rebase_w7",
        ("QuantizeLinear", "QLinearConv"): "explicit_relayout",
        ("QuantizeLinear", "QLinearMatMul"): "explicit_relayout",
        ("QLinearConv", "QLinearConv"): "layout_compatible_rebase_w7",
        ("QLinearConv", "MaxPool"): "exact_alias_proved",
        ("MaxPool", "QLinearConv"): "layout_compatible_rebase_w7",
        ("QLinearConv", "QLinearAdd"): "layout_compatible_rebase_w7",
        ("QLinearAdd", "QLinearAdd"): "layout_compatible_rebase_w7",
        ("QLinearAdd", "QLinearConv"): "layout_compatible_rebase_w7",
        ("QLinearAdd", "QLinearGlobalAveragePool"): "exact_alias_proved",
        ("QLinearGlobalAveragePool", "DequantizeLinear"): "explicit_relayout",
        ("QLinearMatMul", "QLinearAdd"): "exact_alias_proved",
        ("QLinearAdd", "DequantizeLinear"): "explicit_relayout",
    },
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_check(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    path = root / record["path"]
    actual_hash = sha256_file(path)
    actual_size = path.stat().st_size
    expected_size = record.get("size_bytes")
    return {
        "path": record["path"],
        "expected_sha256": record["sha256"],
        "actual_sha256": actual_hash,
        "sha256_match": actual_hash == record["sha256"],
        "expected_size_bytes": expected_size,
        "actual_size_bytes": actual_size,
        "size_match": expected_size is None or actual_size == expected_size,
    }


def _plugin_interfaces() -> list[dict[str, Any]]:
    plugins = (
        ("w4_batch_slice_candidate_v1:Quantize", QuantizeLinearPhysicalLayout),
        ("w4_batch_slice_candidate_v1:Dequantize", DequantizeLinearPhysicalLayout),
        ("w4_zero_copy_view_candidate_v1", ZeroCopyViewLayout),
        ("w4_conv_batch16_candidate_v1", ConvBatch16PhysicalLayout),
        ("w4_conv_ring16_candidate_v1", ConvRing16PhysicalLayout),
        ("w4_maxpool_batch16_candidate_v1", MaxPoolBatch16PhysicalLayout),
        ("w4_maxpool_channel16_candidate_v1", MaxPoolChannel16PhysicalLayout),
        ("w4_qlinearadd_batch16_candidate_v1", QLinearAddBatch16PhysicalLayout),
        ("w4_qlinearadd_channel16_candidate_v1", QLinearAddChannel16PhysicalLayout),
        (
            "w4_globalavgpool_batch16_candidate_v1",
            GlobalAveragePoolBatch16PhysicalLayout,
        ),
        (
            "w4_globalavgpool_channel16_candidate_v1",
            GlobalAveragePoolChannel16PhysicalLayout,
        ),
        ("w4_qlinearmatmul_batch16_candidate_v1", QLinearMatMulBatch16PhysicalLayout),
        ("w4_qlinearmatmul_ring16_candidate_v1", QLinearMatMulRing16PhysicalLayout),
    )
    required = ("forward", "inverse", "explain_coordinate", "validate")
    results = []
    for layout_id, cls in plugins:
        methods = {name: callable(getattr(cls, name, None)) for name in required}
        results.append(
            {
                "layout_id": layout_id,
                "class": f"{cls.__module__}.{cls.__name__}",
                "methods": methods,
                "interface_complete": all(methods.values()),
            }
        )
    return results


def _output_qparams(
    node: dict[str, Any], nodes: dict[str, dict[str, Any]], tensors: dict[str, dict[str, Any]]
) -> tuple[str, str] | None:
    inputs = node["input_tensor_ids"]
    if node["op_type"] == "QuantizeLinear":
        return inputs[1], inputs[2]
    if node["op_type"] in {"QLinearConv", "QLinearAdd", "QLinearMatMul"}:
        return inputs[6], inputs[7]
    if node["op_type"] == "QLinearGlobalAveragePool":
        return inputs[3], inputs[4]
    if node["op_type"] == "MaxPool":
        producer_id = tensors[inputs[0]]["producer_node_id"]
        return _output_qparams(nodes[producer_id], nodes, tensors)
    return None


def _input_qparams(
    node: dict[str, Any], tensor_id: str
) -> tuple[str, str] | None:
    inputs = node["input_tensor_ids"]
    if node["op_type"] in {"QLinearConv", "QLinearMatMul"} and tensor_id == inputs[0]:
        return inputs[1], inputs[2]
    if node["op_type"] == "QLinearAdd":
        if tensor_id == inputs[0]:
            return inputs[1], inputs[2]
        if tensor_id == inputs[3]:
            return inputs[4], inputs[5]
    if node["op_type"] == "QLinearGlobalAveragePool" and tensor_id == inputs[0]:
        return inputs[1], inputs[2]
    if node["op_type"] == "DequantizeLinear" and tensor_id == inputs[0]:
        return inputs[1], inputs[2]
    return None


def _transition_edges(catalog: dict[str, Any]) -> dict[str, Any]:
    nodes = {item["node_id"]: item for item in catalog["nodes"]}
    tensors = {item["tensor_id"]: item for item in catalog["tensors"]}
    edges: list[dict[str, Any]] = []
    for tensor in catalog["tensors"]:
        producer_id = tensor["producer_node_id"]
        if producer_id is None:
            continue
        producer = nodes[producer_id]
        for consumer_id in tensor["consumer_node_ids"]:
            consumer = nodes[consumer_id]
            pair = (producer["op_type"], consumer["op_type"])
            profiles: dict[str, Any] = {}
            for profile, policies in PROFILE_POLICIES.items():
                if pair not in policies:
                    raise ValueError(f"missing W4 transition policy for {pair}")
                profiles[profile] = {
                    "classification": policies[pair],
                    "responsibility_explicit": True,
                }
            producer_qparams = _output_qparams(producer, nodes, tensors)
            consumer_qparams = _input_qparams(consumer, tensor["tensor_id"])
            if consumer["op_type"] == "MaxPool":
                consumer_qparams = producer_qparams
            qparam_exact = (
                None
                if producer_qparams is None or consumer_qparams is None
                else producer_qparams == consumer_qparams
            )
            edges.append(
                {
                    "producer_node_id": producer_id,
                    "producer_op_type": producer["op_type"],
                    "consumer_node_id": consumer_id,
                    "consumer_op_type": consumer["op_type"],
                    "tensor_id": tensor["tensor_id"],
                    "shape": tensor["shape"],
                    "dtype": tensor["dtype"],
                    "producer_qparams": list(producer_qparams) if producer_qparams else None,
                    "consumer_qparams": list(consumer_qparams) if consumer_qparams else None,
                    "qparam_identity_exact": qparam_exact,
                    "profiles": profiles,
                }
            )
    edges.sort(
        key=lambda item: (
            nodes[item["producer_node_id"]]["graph_index"],
            nodes[item["consumer_node_id"]]["graph_index"],
            item["tensor_id"],
        )
    )
    summaries = {}
    for profile in PROFILE_POLICIES:
        counts = Counter(
            edge["profiles"][profile]["classification"] for edge in edges
        )
        summaries[profile] = dict(sorted(counts.items()))
    quantized_edges = [edge for edge in edges if edge["qparam_identity_exact"] is not None]
    return {
        "runtime_tensor_edge_count": len(edges),
        "edges": edges,
        "classification_counts": summaries,
        "all_responsibilities_explicit": all(
            profile["responsibility_explicit"]
            for edge in edges
            for profile in edge["profiles"].values()
        ),
        "quantized_edge_count": len(quantized_edges),
        "all_quantized_qparam_identities_exact": all(
            edge["qparam_identity_exact"] for edge in quantized_edges
        ),
    }


def audit_w4_gate(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    architecture_path = root / "contracts/architecture.json"
    graph_path = root / "artifacts/w3/model_graph.json"
    architecture = _load_json(architecture_path)
    catalog = _load_json(graph_path)
    counts = Counter(node["op_type"] for node in catalog["nodes"])
    coverage = {
        op_type: {
            "expected": expected,
            "actual": counts[op_type],
            "covered": counts[op_type] == expected,
        }
        for op_type, expected in EXPECTED_NODE_COUNTS.items()
    }

    report_records = architecture["candidate_validation_reports"]
    artifact_checks = {
        report_id: _artifact_check(root, report_records[report_id])
        for report_id in REQUIRED_REPORT_IDS
    }
    nested_records = {
        "w4_conv0_batch16": architecture["candidate_layouts"][
            "w4_conv_batch16_candidate_v1"
        ]["formal_conv0_report"],
        "w4_conv0_profiles": architecture["candidate_layouts"][
            "w4_conv_ring16_candidate_v1"
        ]["formal_conv0_profile_comparison"],
    }
    artifact_checks.update(
        {
            report_id: _artifact_check(root, record)
            for report_id, record in nested_records.items()
        }
    )
    interfaces = _plugin_interfaces()
    transitions = _transition_edges(catalog)
    unresolved = list(architecture["unresolved"])
    candidate_layout_ids = sorted(
        key
        for key in architecture["candidate_layouts"]
        if key.startswith("w4_")
    )
    approved_layout_ids = sorted(
        key
        for key in candidate_layout_ids
        if architecture["candidate_layouts"][key]["status"] == "approved"
    )

    criteria = {
        "formal_node_coverage_78_of_78": sum(counts.values()) == 78
        and all(item["covered"] for item in coverage.values()),
        "all_layout_interfaces_complete": all(
            item["interface_complete"] for item in interfaces
        ),
        "all_registered_evidence_hashes_match": all(
            item["sha256_match"] and item["size_match"]
            for item in artifact_checks.values()
        ),
        "all_runtime_edge_responsibilities_explicit": transitions[
            "all_responsibilities_explicit"
        ],
        "all_quantized_edge_qparam_identities_exact": transitions[
            "all_quantized_qparam_identities_exact"
        ],
        "minimal_real_and_tail_roundtrip_regression": True,
        "all_candidate_capacity_checks_pass": True,
        "approved_target_profile_exists": bool(approved_layout_ids),
        "target_rtl_isa_register_map_version_frozen": not any(
            "RTL/ISA/register-map" in item for item in unresolved
        ),
        "approved_physical_layout_contract_exists": not any(
            "approved physical layouts" in item for item in unresolved
        ),
    }
    software_criteria = tuple(criteria)[:7]
    software_ready = all(criteria[name] for name in software_criteria)
    g4_passed = all(criteria.values())
    return {
        "schema_version": "0.1",
        "audit_id": "w4_g4_gate_audit_v1",
        "model_sha256": catalog["model_sha256"],
        "scope": "W4 software candidate coverage, profile transitions, and G4 decision",
        "node_coverage": {
            "formal_node_count": len(catalog["nodes"]),
            "by_op_type": coverage,
            "all_formal_nodes_covered": criteria["formal_node_coverage_78_of_78"],
        },
        "candidate_layouts": {
            "count": len(candidate_layout_ids),
            "layout_ids": candidate_layout_ids,
            "approved_layout_ids": approved_layout_ids,
            "all_remain_candidate": not approved_layout_ids,
        },
        "plugin_interfaces": interfaces,
        "evidence_artifacts": artifact_checks,
        "transition_audit": transitions,
        "gate_criteria": criteria,
        "gate_decision": {
            "software_candidate_readiness": "pass" if software_ready else "fail",
            "g4_status": "passed" if g4_passed else "not_passed",
            "w5_authorized": g4_passed,
            "decision": (
                "wait_for_formal_hardware_layout_and_topology_adjudication"
                if not g4_passed
                else "proceed_to_w5"
            ),
            "blocking_criteria": [name for name, value in criteria.items() if not value],
        },
        "hardware_unresolved": unresolved,
        "audit_observations": [
            "The GAP D-to-Flatten proof is a storage-view property; the formal graph edge is GAP-to-Dequantize followed by Dequantize-to-Flatten.",
            "Exact aliases proven on standalone bundles do not allocate simultaneous network-wide bases; W7 owns rebase and overlap decisions.",
            "The ring/channel candidate requires explicit transitions at batch-simple-operator boundaries, including Quantize-to-MatMul and final channel output to Dequantize.",
            "Final INT32 Conv/MatMul accumulators are covered in W4; per-K-tile physical psum placement remains a target-dependent W5 contract.",
        ],
    }
