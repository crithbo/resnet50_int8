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
from .compare import compare_logical_tensor, compare_request, load_comparison_request
from .conv16_layout import ConvBatch16PhysicalLayout
from .conv16_ring_layout import ConvRing16PhysicalLayout
from .errors import ContractError
from .hashing import sha256_file
from .hardware_approval import validate_hardware_approval_file
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
from .w4_profiles import PROFILE_POLICIES


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
    "w4_network_candidate_dry_run_v1",
)

CURRENT_TARGET_FAMILY = "rtl28"
CURRENT_TARGET_SLICE_COUNT = 28
CURRENT_TARGET_REQUIRED_LAYOUT_FAMILIES = (
    "simple",
    "view",
    "conv",
    "maxpool",
    "add",
    "global_average_pool",
    "matmul",
)
CURRENT_TARGET_SOFTWARE_CRITERIA = (
    "formal_node_coverage_78_of_78",
    "logical_quantized_edge_qparam_identities_exact",
    "logical_result_comparator_ready",
    "current_target_architecture_is_28_slice",
    "target28_operator_layout_evidence_complete",
    "target28_all_93_edges_physically_verified",
    "target28_profile_cost_evidence_complete",
)

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


def _comparison_interface(root: Path) -> dict[str, Any]:
    callables = {
        "compare_logical_tensor": callable(compare_logical_tensor),
        "compare_request": callable(compare_request),
        "load_comparison_request": callable(load_comparison_request),
    }
    schemas = {
        name: (root / "schemas" / name).is_file()
        for name in (
            "comparison_request.schema.json",
            "comparison_report.schema.json",
        )
    }
    return {
        "domain": "logical_tensor_after_inverse_layout",
        "required_pairs": [
            ["golden", "simulator"],
            ["golden", "hardware"],
            ["simulator", "hardware"],
        ],
        "integer_policy": "bit_exact",
        "float_policy": "manifest_declared_atol_rtol",
        "failure_categories": [
            "missing",
            "load_error",
            "layout_inverse_failure",
            "shape_mismatch",
            "dtype_mismatch",
            "tolerance_required",
            "value_mismatch",
        ],
        "callables": callables,
        "schemas": schemas,
        "interface_ready": all(callables.values()) and all(schemas.values()),
        "hardware_results_available": False,
    }


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


def _hardware_approval_status(
    root: Path, approval_path: Path | None
) -> dict[str, Any]:
    path = approval_path or root / "contracts/hardware_approval.json"
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        display_path = path.relative_to(root).as_posix()
    except ValueError:
        display_path = str(path)
    if not path.is_file():
        return {
            "present": False,
            "valid": False,
            "path": display_path,
            "validation_error": None,
        }
    try:
        result = validate_hardware_approval_file(
            path, root / "contracts/architecture.json"
        )
    except (ContractError, OSError, json.JSONDecodeError) as error:
        return {
            "present": True,
            "valid": False,
            "path": display_path,
            "sha256": sha256_file(path),
            "validation_error": str(error),
        }
    result["path"] = display_path
    result["present"] = True
    result["validation_error"] = None
    return result


def _legacy16_evidence_status(
    report_payloads: dict[str, dict[str, Any]],
    network_profiles: dict[str, Any],
) -> dict[str, Any]:
    roundtrip_claims = (
        report_payloads["w4_conv_shape_coverage_v1"][
            "all_family_roundtrips_bit_exact"
        ],
        report_payloads["w4_conv_shape_coverage_v1"][
            "all_batch_ring_logical_bit_exact"
        ],
        report_payloads["w4_maxpool_profiles_v1"][
            "all_profiles_inverse_bit_exact"
        ],
        report_payloads["w4_qlinearadd_profiles_v1"][
            "all_representatives_inverse_bit_exact"
        ],
        report_payloads["w4_globalavgpool_profiles_v1"][
            "all_profiles_inverse_bit_exact"
        ],
        report_payloads["w4_qlinearmatmul_profiles_v1"][
            "all_profiles_inverse_bit_exact"
        ],
    )
    capacity_claims = tuple(
        profile["dry_run_cost"]["all_standalone_node_plans_fit"]
        for profile in network_profiles.values()
    )
    criteria = {
        "minimal_real_and_tail_roundtrip_regression": all(roundtrip_claims),
        "all_candidate_capacity_checks_pass": all(capacity_claims),
        "all_93_edges_physically_verified": all(
            profile["transition_audit"]["edge_count"] == 93
            and profile["transition_audit"][
                "all_policy_relations_physically_verified"
            ]
            for profile in network_profiles.values()
        ),
        "both_profile_dry_runs_fit_candidate_capacity": all(capacity_claims),
        "candidate_lifetimes_and_aliases_conflict_free": all(
            profile["memory_lifecycle"]["all_allocations_fit"]
            and profile["memory_lifecycle"][
                "all_lifetime_overlaps_address_disjoint"
            ]
            and profile["memory_lifecycle"]["all_alias_actions_conflict_free"]
            and profile["memory_lifecycle"][
                "all_residual_branches_distinct_and_disjoint"
            ]
            for profile in network_profiles.values()
        ),
    }
    return {
        "target_family": "legacy16",
        "slice_count": 16,
        "current_gate_eligible": False,
        "criteria": criteria,
        "software_evidence_ready": all(criteria.values()),
    }


def _current_target_evidence_status(
    architecture: dict[str, Any], hardware_approval: dict[str, Any]
) -> dict[str, Any]:
    declared_slice_count = architecture.get("target", {}).get("slice_count")
    target_layouts = {
        layout_id: record
        for layout_id, record in architecture.get("candidate_layouts", {}).items()
        if record.get("target_family") == CURRENT_TARGET_FAMILY
        and record.get("slice_count") == CURRENT_TARGET_SLICE_COUNT
        and record.get("status") in {"candidate", "approved"}
        and record.get("current_gate_eligible") is True
    }
    target_layout_ids = sorted(target_layouts)
    target_layout_families = {
        record.get("operator_family") for record in target_layouts.values()
    }
    target_reports = {
        report_id: record
        for report_id, record in architecture.get("candidate_evidence", {}).items()
        if record.get("target_family") == CURRENT_TARGET_FAMILY
        and record.get("slice_count") == CURRENT_TARGET_SLICE_COUNT
        and record.get("current_gate_eligible") is True
    }
    registered_layout_evidence_complete = set(
        CURRENT_TARGET_REQUIRED_LAYOUT_FAMILIES
    ).issubset(target_layout_families)
    approved_profile_layouts_complete = bool(
        hardware_approval.get("layout_evidence_complete", False)
    )
    layout_evidence_complete = bool(
        registered_layout_evidence_complete and approved_profile_layouts_complete
    )
    edge_evidence_complete = any(
        record.get("evidence_kind") == "network_physical_edge_audit"
        and record.get("edge_count") == 93
        for record in target_reports.values()
    )
    cost_evidence_complete = any(
        record.get("evidence_kind") == "network_profile_cost"
        for record in target_reports.values()
    )
    clean_elaboration_approved = bool(
        hardware_approval.get("clean_elaboration_approved", False)
    )
    architecture_matches_target = declared_slice_count == CURRENT_TARGET_SLICE_COUNT
    approval_current_gate_eligible = bool(
        hardware_approval.get("valid", False)
        and architecture_matches_target
        and layout_evidence_complete
        and edge_evidence_complete
        and cost_evidence_complete
        and clean_elaboration_approved
    )
    reasons = []
    if not hardware_approval.get("valid", False):
        reasons.append("hardware_approval_missing_or_structurally_invalid")
    if not architecture_matches_target:
        reasons.append("architecture_contract_is_not_current_28_slice_target")
    if not layout_evidence_complete:
        reasons.append("target28_operator_layout_evidence_incomplete")
    if not edge_evidence_complete:
        reasons.append("target28_network_93_edge_evidence_missing")
    if not cost_evidence_complete:
        reasons.append("target28_profile_cost_evidence_missing")
    if not clean_elaboration_approved:
        reasons.append("target28_clean_elaboration_not_approved")
    return {
        "target_family": CURRENT_TARGET_FAMILY,
        "slice_count": CURRENT_TARGET_SLICE_COUNT,
        "declared_architecture_slice_count": declared_slice_count,
        "architecture_matches_target": architecture_matches_target,
        "layout_evidence_ids": target_layout_ids,
        "layout_evidence_families": sorted(
            family for family in target_layout_families if family is not None
        ),
        "registered_layout_evidence_complete": registered_layout_evidence_complete,
        "approved_profile_layouts_complete": approved_profile_layouts_complete,
        "layout_evidence_complete": layout_evidence_complete,
        "eligible_report_ids": sorted(target_reports),
        "network_93_edge_evidence_complete": edge_evidence_complete,
        "profile_cost_evidence_complete": cost_evidence_complete,
        "clean_elaboration_approved": clean_elaboration_approved,
        "hardware_approval_structurally_valid": bool(
            hardware_approval.get("valid", False)
        ),
        "hardware_approval_current_gate_eligible": approval_current_gate_eligible,
        "eligibility_reasons": reasons,
    }


def audit_w4_gate(
    project_root: Path, hardware_approval_path: Path | None = None
) -> dict[str, Any]:
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

    report_records = architecture["legacy_evidence"]
    report_payloads = {
        report_id: _load_json(root / report_records[report_id]["path"])
        for report_id in REQUIRED_REPORT_IDS
    }
    artifact_checks = {
        report_id: _artifact_check(root, report_records[report_id])
        for report_id in REQUIRED_REPORT_IDS
    }
    nested_records = {
        "w4_conv0_batch16": architecture["legacy_layouts"][
            "w4_conv_batch16_candidate_v1"
        ]["formal_conv0_report"],
        "w4_conv0_profiles": architecture["legacy_layouts"][
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
    comparison_interface = _comparison_interface(root)
    transitions = _transition_edges(catalog)
    network_report = report_payloads["w4_network_candidate_dry_run_v1"]
    network_profiles = network_report["profiles"]
    hardware_approval = _hardware_approval_status(root, hardware_approval_path)
    legacy16_evidence = _legacy16_evidence_status(
        report_payloads, network_profiles
    )
    current_target_evidence = _current_target_evidence_status(
        architecture, hardware_approval
    )
    hardware_approval["validation_scope"] = "structure_only"
    hardware_approval["current_gate_eligible"] = current_target_evidence[
        "hardware_approval_current_gate_eligible"
    ]
    hardware_approval["current_gate_eligibility_reasons"] = list(
        current_target_evidence["eligibility_reasons"]
    )
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

    reusable_criteria = {
        "formal_node_coverage_78_of_78": sum(counts.values()) == 78
        and all(item["covered"] for item in coverage.values()),
        "legacy16_layout_interfaces_complete": all(
            item["interface_complete"] for item in interfaces
        ),
        "legacy16_registered_evidence_hashes_match": all(
            item["sha256_match"] and item["size_match"]
            for item in artifact_checks.values()
        ),
        "legacy16_runtime_edge_responsibilities_explicit": transitions[
            "all_responsibilities_explicit"
        ],
        "logical_quantized_edge_qparam_identities_exact": transitions[
            "all_quantized_qparam_identities_exact"
        ],
        "logical_result_comparator_ready": comparison_interface["interface_ready"],
    }
    criteria = {
        "formal_node_coverage_78_of_78": reusable_criteria[
            "formal_node_coverage_78_of_78"
        ],
        "logical_quantized_edge_qparam_identities_exact": reusable_criteria[
            "logical_quantized_edge_qparam_identities_exact"
        ],
        "logical_result_comparator_ready": reusable_criteria[
            "logical_result_comparator_ready"
        ],
        "current_target_architecture_is_28_slice": current_target_evidence[
            "architecture_matches_target"
        ],
        "target28_operator_layout_evidence_complete": current_target_evidence[
            "layout_evidence_complete"
        ],
        "target28_all_93_edges_physically_verified": current_target_evidence[
            "network_93_edge_evidence_complete"
        ],
        "target28_profile_cost_evidence_complete": current_target_evidence[
            "profile_cost_evidence_complete"
        ],
        "target28_clean_elaboration_approved": current_target_evidence[
            "clean_elaboration_approved"
        ],
        "approved_target_profile_exists": current_target_evidence[
            "hardware_approval_current_gate_eligible"
        ],
        "target_rtl_isa_register_map_version_frozen": current_target_evidence[
            "hardware_approval_current_gate_eligible"
        ],
        "approved_physical_layout_contract_exists": current_target_evidence[
            "hardware_approval_current_gate_eligible"
        ],
    }
    software_ready = all(
        criteria[name] for name in CURRENT_TARGET_SOFTWARE_CRITERIA
    )
    g4_passed = all(criteria.values())
    return {
        "schema_version": "0.2",
        "audit_id": "w4_28_g4_gate_fail_closed_v1",
        "model_sha256": catalog["model_sha256"],
        "scope": "Current 28-slice G4 decision with legacy16 evidence isolated",
        "node_coverage": {
            "formal_node_count": len(catalog["nodes"]),
            "by_op_type": coverage,
            "all_formal_nodes_covered": reusable_criteria[
                "formal_node_coverage_78_of_78"
            ],
        },
        "candidate_layouts": {
            "count": len(candidate_layout_ids),
            "layout_ids": candidate_layout_ids,
            "approved_layout_ids": approved_layout_ids,
            "all_remain_candidate": not approved_layout_ids,
        },
        "plugin_interfaces": interfaces,
        "logical_result_comparator": comparison_interface,
        "evidence_artifacts": artifact_checks,
        "transition_audit": transitions,
        "candidate_network_dry_run_summary": {
            profile_name: {
                "edge_count": profile["transition_audit"]["edge_count"],
                "explicit_relayout_edge_count": profile["transition_audit"][
                    "explicit_relayout_edge_count"
                ],
                "logical_io_bytes": profile["dry_run_cost"]["logical_io_bytes"],
                "candidate_bundle_bytes_all_slices": profile["dry_run_cost"][
                    "candidate_bundle_bytes_all_slices"
                ],
                "explicit_relayout_read_write_bytes": profile["dry_run_cost"][
                    "explicit_relayout_read_write_bytes"
                ],
                "estimated_ring_neighbor_bytes": profile["dry_run_cost"][
                    "estimated_ring_neighbor_bytes"
                ],
                "activation_high_water_bytes_per_slice": profile[
                    "memory_lifecycle"
                ]["high_water_bytes_per_slice"],
                "residual_branch_check_count": len(
                    profile["memory_lifecycle"]["residual_branch_checks"]
                ),
            }
            for profile_name, profile in network_profiles.items()
        },
        "hardware_approval": hardware_approval,
        "legacy16_evidence": legacy16_evidence,
        "current_target_evidence": current_target_evidence,
        "reusable_criteria": reusable_criteria,
        "gate_criteria": criteria,
        "gate_decision": {
            "software_candidate_readiness": "pass" if software_ready else "fail",
            "legacy16_software_evidence": (
                "pass" if legacy16_evidence["software_evidence_ready"] else "fail"
            ),
            "g4_status": "passed" if g4_passed else "not_passed",
            "w5_authorized": g4_passed,
            "decision": (
                "complete_target28_contract_layout_edge_cost_and_elaboration_evidence"
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
            "The logical result comparator is ready for two-way or three-way reports, but no absent simulator/hardware output is treated as a numerical pass.",
            "Legacy16 layout, edge, capacity, lifetime and cost evidence is diagnostic only and cannot satisfy any current 28-slice G4 criterion.",
            "A structurally valid hardware approval remains ineligible for G4 until the current 28-slice architecture, operator layouts, 93-edge audit, profile cost evidence and clean elaboration are all present.",
        ],
    }
