from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .add16_layout import (
    QLinearAddBatch16PhysicalLayout,
    QLinearAddChannel16PhysicalLayout,
)
from .add28_layout import QLinearAddPhysicalLayout
from .avgpool16_layout import (
    GlobalAveragePoolBatch16PhysicalLayout,
    GlobalAveragePoolChannel16PhysicalLayout,
)
from .compare import compare_logical_tensor, compare_request, load_comparison_request
from .conv28_layout import QLinearConvPhysicalLayout
from .conv16_layout import ConvBatch16PhysicalLayout
from .conv16_ring_layout import ConvRing16PhysicalLayout
from .errors import ContractError
from .hashing import sha256_file
from .hardware_approval import validate_hardware_approval_file
from .matmul16_layout import (
    QLinearMatMulBatch16PhysicalLayout,
    QLinearMatMulRing16PhysicalLayout,
)
from .matmul28_layout import QLinearMatMulPhysicalLayout
from .maxpool16_layout import (
    MaxPoolBatch16PhysicalLayout,
    MaxPoolChannel16PhysicalLayout,
)
from .pool28_layout import GlobalAveragePoolPhysicalLayout, MaxPoolPhysicalLayout
from .simple_layout import (
    DequantizeLinearPhysicalLayout,
    QuantizeLinearPhysicalLayout,
    ZeroCopyViewLayout,
)
from .simple16_layout import (
    DequantizeLinearPhysicalLayout as LegacyDequantizeLinearPhysicalLayout,
    QuantizeLinearPhysicalLayout as LegacyQuantizeLinearPhysicalLayout,
    ZeroCopyViewLayout as LegacyZeroCopyViewLayout,
)
from .target_config_audit import (
    ADD_DEQUANT_TEMPLATE,
    AVGPOOL_TEMPLATE,
    OFFICIAL_CONFIG_COMMIT,
    OFFICIAL_CONFIG_REPOSITORY,
    OFFICIAL_CONFIG_SLICE_COUNT,
    QUANT_TEMPLATE,
    SECOND_MAXPOOL_TEMPLATE,
)
from .w4_evidence import architecture_evidence_basis_sha256
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
    "current_target_layout_interfaces_complete",
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


def _current_evidence_artifact_checks(
    root: Path, architecture: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    basis_sha256 = architecture_evidence_basis_sha256(architecture)
    checks: dict[str, dict[str, Any]] = {}
    for evidence_id, record in architecture.get("candidate_evidence", {}).items():
        if record.get("current_gate_eligible") is not True:
            continue
        path = root / record.get("path", "")
        present = path.is_file()
        actual_size = path.stat().st_size if present else None
        actual_sha256 = sha256_file(path) if present else None
        payload: dict[str, Any] = {}
        parse_valid = False
        if present:
            try:
                payload = _load_json(path)
                parse_valid = isinstance(payload, dict)
            except (json.JSONDecodeError, OSError):
                pass
        common_semantics_match = bool(
            parse_valid
            and record.get("architecture_basis_sha256") == basis_sha256
            and payload.get("architecture_basis_sha256") == basis_sha256
            and payload.get("evidence_kind") == record.get("evidence_kind")
            and payload.get("target_family") == CURRENT_TARGET_FAMILY
            and payload.get("slice_count") == CURRENT_TARGET_SLICE_COUNT
            and payload.get("status") == "candidate_software_evidence"
            and payload.get("current_gate_eligible") is True
            and payload.get("all_scenarios_pass") is True
            and payload.get("hardware_approval") is False
            and payload.get("g4_passed") is False
            and payload.get("w5_authorized") is False
        )
        if record.get("evidence_kind") == "network_physical_edge_audit":
            kind_semantics_match = bool(
                record.get("edge_count") == payload.get("edge_count") == 93
                and record.get("qparam_edge_count")
                == payload.get("qparam_edge_count")
                == 91
                and record.get("residual_add_count")
                == payload.get("residual_add_count")
                == 16
            )
        elif record.get("evidence_kind") == "network_profile_cost":
            kind_semantics_match = bool(
                record.get("scenario_count") == payload.get("scenario_count") == 2
            )
        else:
            kind_semantics_match = False
        sha256_match = actual_sha256 == record.get("sha256")
        size_match = actual_size == record.get("size_bytes")
        checks[evidence_id] = {
            "path": record.get("path"),
            "present": present,
            "expected_sha256": record.get("sha256"),
            "actual_sha256": actual_sha256,
            "sha256_match": sha256_match,
            "expected_size_bytes": record.get("size_bytes"),
            "actual_size_bytes": actual_size,
            "size_match": size_match,
            "parse_valid": parse_valid,
            "architecture_basis_match": record.get(
                "architecture_basis_sha256"
            )
            == basis_sha256,
            "semantics_match": common_semantics_match and kind_semantics_match,
            "usable": bool(
                present
                and sha256_match
                and size_match
                and common_semantics_match
                and kind_semantics_match
            ),
        }
    return checks


def _plugin_interfaces() -> list[dict[str, Any]]:
    plugins = (
        (
            "w4_simple_group4x7_28_candidate_v1:Quantize",
            "rtl28",
            QuantizeLinearPhysicalLayout,
        ),
        (
            "w4_simple_group4x7_28_candidate_v1:Dequantize",
            "rtl28",
            DequantizeLinearPhysicalLayout,
        ),
        ("w4_zero_copy_view_group4x7_28_candidate_v1", "rtl28", ZeroCopyViewLayout),
        ("w4_simple_global_ring28_candidate_v1:Quantize", "rtl28", QuantizeLinearPhysicalLayout),
        ("w4_simple_global_ring28_candidate_v1:Dequantize", "rtl28", DequantizeLinearPhysicalLayout),
        ("w4_zero_copy_view_global_ring28_candidate_v1", "rtl28", ZeroCopyViewLayout),
        ("w4_conv_group4x7_28_candidate_v1", "rtl28", QLinearConvPhysicalLayout),
        ("w4_conv_global_ring28_candidate_v1", "rtl28", QLinearConvPhysicalLayout),
        ("w4_maxpool_group4x7_28_candidate_v1", "rtl28", MaxPoolPhysicalLayout),
        ("w4_maxpool_global_ring28_candidate_v1", "rtl28", MaxPoolPhysicalLayout),
        (
            "w4_qlinearadd_group4x7_28_candidate_v1",
            "rtl28",
            QLinearAddPhysicalLayout,
        ),
        (
            "w4_qlinearadd_global_ring28_candidate_v1",
            "rtl28",
            QLinearAddPhysicalLayout,
        ),
        (
            "w4_globalavgpool_group4x7_28_candidate_v1",
            "rtl28",
            GlobalAveragePoolPhysicalLayout,
        ),
        (
            "w4_globalavgpool_global_ring28_candidate_v1",
            "rtl28",
            GlobalAveragePoolPhysicalLayout,
        ),
        (
            "w4_qlinearmatmul_group4x7_28_candidate_v1",
            "rtl28",
            QLinearMatMulPhysicalLayout,
        ),
        (
            "w4_qlinearmatmul_global_ring28_candidate_v1",
            "rtl28",
            QLinearMatMulPhysicalLayout,
        ),
        ("w4_batch_slice_candidate_v1:Quantize", "legacy16", LegacyQuantizeLinearPhysicalLayout),
        ("w4_batch_slice_candidate_v1:Dequantize", "legacy16", LegacyDequantizeLinearPhysicalLayout),
        ("w4_zero_copy_view_candidate_v1", "legacy16", LegacyZeroCopyViewLayout),
        ("w4_conv_batch16_candidate_v1", "legacy16", ConvBatch16PhysicalLayout),
        ("w4_conv_ring16_candidate_v1", "legacy16", ConvRing16PhysicalLayout),
        ("w4_maxpool_batch16_candidate_v1", "legacy16", MaxPoolBatch16PhysicalLayout),
        ("w4_maxpool_channel16_candidate_v1", "legacy16", MaxPoolChannel16PhysicalLayout),
        ("w4_qlinearadd_batch16_candidate_v1", "legacy16", QLinearAddBatch16PhysicalLayout),
        ("w4_qlinearadd_channel16_candidate_v1", "legacy16", QLinearAddChannel16PhysicalLayout),
        (
            "w4_globalavgpool_batch16_candidate_v1",
            "legacy16",
            GlobalAveragePoolBatch16PhysicalLayout,
        ),
        (
            "w4_globalavgpool_channel16_candidate_v1",
            "legacy16",
            GlobalAveragePoolChannel16PhysicalLayout,
        ),
        ("w4_qlinearmatmul_batch16_candidate_v1", "legacy16", QLinearMatMulBatch16PhysicalLayout),
        ("w4_qlinearmatmul_ring16_candidate_v1", "legacy16", QLinearMatMulRing16PhysicalLayout),
    )
    required = ("forward", "inverse", "explain_coordinate", "validate")
    results = []
    for layout_id, target_family, cls in plugins:
        methods = {name: callable(getattr(cls, name, None)) for name in required}
        results.append(
            {
                "layout_id": layout_id,
                "target_family": target_family,
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
            "validation_scope": "structure_only",
            "gate_authority_eligible": False,
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
            "validation_scope": "structure_only",
            "gate_authority_eligible": False,
        }
    result["path"] = display_path
    result["present"] = True
    result["validation_error"] = None
    result["gate_authority_eligible"] = not str(
        result.get("approval_id", "")
    ).startswith("synthetic-")
    result["validation_scope"] = (
        "authority_and_structure"
        if result["gate_authority_eligible"]
        else "structure_only"
    )
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
    architecture: dict[str, Any],
    hardware_approval: dict[str, Any],
    evidence_artifact_checks: dict[str, dict[str, Any]] | None = None,
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
        and (
            evidence_artifact_checks is None
            or evidence_artifact_checks.get(report_id, {}).get("usable") is True
        )
        for report_id, record in target_reports.items()
    )
    cost_evidence_complete = any(
        record.get("evidence_kind") == "network_profile_cost"
        and (
            evidence_artifact_checks is None
            or evidence_artifact_checks.get(report_id, {}).get("usable") is True
        )
        for report_id, record in target_reports.items()
    )
    clean_elaboration_approved = bool(
        hardware_approval.get("clean_elaboration_approved", False)
    )
    gate_authority_eligible = bool(
        hardware_approval.get("gate_authority_eligible", False)
    )
    architecture_matches_target = declared_slice_count == CURRENT_TARGET_SLICE_COUNT
    approval_current_gate_eligible = bool(
        hardware_approval.get("valid", False)
        and gate_authority_eligible
        and architecture_matches_target
        and layout_evidence_complete
        and edge_evidence_complete
        and cost_evidence_complete
        and clean_elaboration_approved
    )
    reasons = []
    if not hardware_approval.get("valid", False):
        reasons.append("hardware_approval_missing_or_structurally_invalid")
    if not gate_authority_eligible:
        reasons.append("hardware_approval_not_gate_authority_eligible")
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
        "hardware_approval_gate_authority_eligible": gate_authority_eligible,
        "hardware_approval_current_gate_eligible": approval_current_gate_eligible,
        "eligibility_reasons": reasons,
    }


def _target_config_toolchain_status(root: Path) -> dict[str, Any]:
    backend_path = root / "contracts" / "backend.json"
    reasons: list[str] = []
    try:
        backend = _load_json(backend_path)
        record = backend.get("backends", {}).get("target_config_toolchain", {})
    except (OSError, json.JSONDecodeError):
        record = {}
        reasons.append("backend_contract_missing_or_invalid")
    expected = {
        "status": "approved_configuration_source",
        "approved": True,
        "source_repository": OFFICIAL_CONFIG_REPOSITORY,
        "source_commit": OFFICIAL_CONFIG_COMMIT,
        "slice_count": OFFICIAL_CONFIG_SLICE_COUNT,
        "authoritative_paths": ["jsons", "bitstream", "model_execplan"],
        "is_target_configuration_source": True,
        "can_encode_bitstream": True,
        "can_generate_execplan": True,
        "can_execute_numerical_model": False,
        "maxpool_encoder_probe_validated": True,
        "pool_family_encoder_probe_validated": True,
        "ga_quant_add_dequant_probe_validated": True,
        "matmul_gemv_config_probe_validated": True,
        "sum_family_config_probe_validated": True,
        "resnet50_operator_coverage_complete": False,
    }
    for field, value in expected.items():
        if record.get(field) != value:
            reasons.append(f"backend_field_mismatch:{field}")

    audit_path = root / str(record.get("audit_path", ""))
    audit: dict[str, Any] = {}
    if not audit_path.is_file():
        reasons.append("authority_audit_missing")
    else:
        if audit_path.stat().st_size != record.get("audit_size_bytes"):
            reasons.append("authority_audit_size_mismatch")
        if sha256_file(audit_path) != record.get("audit_sha256"):
            reasons.append("authority_audit_hash_mismatch")
        try:
            audit = _load_json(audit_path)
        except (OSError, json.JSONDecodeError):
            reasons.append("authority_audit_invalid_json")
    if audit:
        semantic_checks = {
            "audit_schema": audit.get("schema_version") == "0.4",
            "audit_status": audit.get("status") == "configuration_source_verified",
            "source_repository": audit.get("source", {}).get("repository")
            == OFFICIAL_CONFIG_REPOSITORY,
            "source_commit": audit.get("source", {}).get("commit")
            == OFFICIAL_CONFIG_COMMIT,
            "slice_count": audit.get("source", {}).get("slice_count")
            == OFFICIAL_CONFIG_SLICE_COUNT,
            "register_map_alignment": audit.get("register_map_audit", {}).get(
                "declared_width_alignment_status"
            )
            == "passed",
            "maxpool_determinism": audit.get("maxpool_probe", {})
            .get("determinism", {})
            .get("status")
            == "passed",
            "maxpool_sensitivity": audit.get("maxpool_probe", {})
            .get("differential_sensitivity", {})
            .get("status")
            == "passed",
            "maxpool_fail_closed": audit.get("maxpool_probe", {})
            .get("fail_closed", {})
            .get("status")
            == "passed",
            "pool_family_status": audit.get("pool_family_probe", {}).get("status")
            == "passed",
            "pool_family_linkage": audit.get("pool_family_probe", {})
            .get("linkage", {})
            .get("status")
            == "passed",
            "maxpool_delta_explained": audit.get("pool_family_probe", {})
            .get("linkage", {})
            .get("maxpool_template_delta", {})
            .get("status")
            == "fully_explained"
            and audit.get("pool_family_probe", {})
            .get("linkage", {})
            .get("maxpool_template_delta", {})
            .get("unexpected_paths")
            == [],
            "second_maxpool_determinism": audit.get("pool_family_probe", {})
            .get("encoder_probes", {})
            .get(SECOND_MAXPOOL_TEMPLATE, {})
            .get("determinism", {})
            .get("status")
            == "passed",
            "second_maxpool_sensitivity": audit.get("pool_family_probe", {})
            .get("encoder_probes", {})
            .get(SECOND_MAXPOOL_TEMPLATE, {})
            .get("differential_sensitivity", {})
            .get("status")
            == "passed",
            "second_maxpool_fail_closed": audit.get("pool_family_probe", {})
            .get("encoder_probes", {})
            .get(SECOND_MAXPOOL_TEMPLATE, {})
            .get("fail_closed", {})
            .get("status")
            == "passed",
            "avgpool_determinism": audit.get("pool_family_probe", {})
            .get("encoder_probes", {})
            .get(AVGPOOL_TEMPLATE, {})
            .get("determinism", {})
            .get("status")
            == "passed",
            "avgpool_sensitivity": audit.get("pool_family_probe", {})
            .get("encoder_probes", {})
            .get(AVGPOOL_TEMPLATE, {})
            .get("differential_sensitivity", {})
            .get("status")
            == "passed",
            "avgpool_fail_closed": audit.get("pool_family_probe", {})
            .get("encoder_probes", {})
            .get(AVGPOOL_TEMPLATE, {})
            .get("fail_closed", {})
            .get("status")
            == "passed",
            "pool_numerical_scope_fail_closed": audit.get("pool_family_probe", {})
            .get("numerical_scope", {})
            .get("status")
            == "not_validated",
            "ga_quant_add_status": audit.get("ga_quant_add_probe", {}).get("status")
            == "passed_with_numerical_gaps",
            "ga_quant_add_crosswalk": audit.get("ga_quant_add_probe", {})
            .get("crosswalk", {})
            .get("status")
            == "passed",
            "ga_resnet_qparam_counts": audit.get("ga_quant_add_probe", {})
            .get("resnet_scalar_qparams", {})
            .get("operator_counts")
            == {"QuantizeLinear": 2, "DequantizeLinear": 2, "QLinearAdd": 17},
            "ga_static_constants_do_not_match_resnet": audit.get("ga_quant_add_probe", {})
            .get("resnet_scalar_qparams", {})
            .get("static_template_comparison", {})
            .get("quantize_linear_direct_match_count")
            == 0
            and audit.get("ga_quant_add_probe", {})
            .get("resnet_scalar_qparams", {})
            .get("static_template_comparison", {})
            .get("dequantize_linear_fixed_branch_match_count")
            == 0
            and audit.get("ga_quant_add_probe", {})
            .get("resnet_scalar_qparams", {})
            .get("static_template_comparison", {})
            .get("qlinearadd_branch_affine_match_count")
            == 0,
            "ga_execplan_qparam_gap": audit.get("ga_quant_add_probe", {})
            .get("execplan_qparam_binding", {})
            .get("status")
            == "gap_confirmed"
            and audit.get("ga_quant_add_probe", {})
            .get("execplan_qparam_binding", {})
            .get("ga_constant_qparams_patched")
            is False,
            "ga_numerical_scope_fail_closed": audit.get("ga_quant_add_probe", {})
            .get("numerical_scope", {})
            .get("status")
            == "not_validated",
            "quant_encoder_probe": all(
                audit.get("ga_quant_add_probe", {})
                .get("encoder_probes", {})
                .get(QUANT_TEMPLATE, {})
                .get(probe_name, {})
                .get("status")
                == "passed"
                for probe_name in ("determinism", "differential_sensitivity", "fail_closed")
            ),
            "add_dequant_encoder_probe": all(
                audit.get("ga_quant_add_probe", {})
                .get("encoder_probes", {})
                .get(ADD_DEQUANT_TEMPLATE, {})
                .get(probe_name, {})
                .get("status")
                == "passed"
                for probe_name in ("determinism", "differential_sensitivity", "fail_closed")
            ),
            "matmul_candidate_scope_fail_closed": audit.get(
                "matmul_config_probe", {}
            ).get("status")
            == "candidate_preflight_only"
            and audit.get("matmul_config_probe", {})
            .get("inventory", {})
            .get("candidate_count")
            == 6
            and audit.get("matmul_config_probe", {})
            .get("inventory", {})
            .get("named_int8_template_count")
            == 0
            and audit.get("matmul_config_probe", {})
            .get("crosswalk", {})
            .get("resnet_qlinearmatmul_gap", {})
            .get("complete_compatible_template_exists")
            is False
            and audit.get("matmul_config_probe", {}).get("numerical_status")
            == "not_validated"
            and audit.get("matmul_config_probe", {}).get("no_gate_authority") is True,
            "matmul_encoder_probe": all(
                audit.get("matmul_config_probe", {})
                .get("encoder_probe", {})
                .get(probe_name, {})
                .get("status")
                == "passed"
                for probe_name in ("determinism", "differential_sensitivity", "fail_closed")
            ),
            "sum_candidate_scope_fail_closed": audit.get("sum_config_probe", {})
            .get("authority", {})
            .get("status")
            == "candidate_preflight_only"
            and audit.get("sum_config_probe", {}).get("scope", {}).get("template_count")
            == 11
            and audit.get("sum_config_probe", {})
            .get("handler_gaps", {})
            .get("fp16_remote_4slice_metadata_conflict")
            is True
            and audit.get("sum_config_probe", {})
            .get("handler_gaps", {})
            .get("output_shape_not_used_by_any_sum_handler")
            is True
            and audit.get("sum_config_probe", {})
            .get("authority", {})
            .get("hardware_status")
            == "not_validated"
            and audit.get("sum_config_probe", {})
            .get("authority", {})
            .get("no_gate_authority")
            is True,
            "sum_encoder_probe": len(
                audit.get("sum_config_probe", {}).get("encoder_probe", {})
            )
            == 11
            and all(
                record.get("status") == "encoding_deterministic"
                and record.get("numerical_status") == "not_validated"
                and record.get("no_gate_authority") is True
                for record in audit.get("sum_config_probe", {})
                .get("encoder_probe", {})
                .values()
            ),
        }
        reasons.extend(
            f"authority_audit_semantic_mismatch:{name}"
            for name, passed in semantic_checks.items()
            if not passed
        )
    return {
        "version_frozen": not reasons,
        "source_repository": record.get("source_repository"),
        "source_commit": record.get("source_commit"),
        "audit_path": record.get("audit_path"),
        "audit_sha256": record.get("audit_sha256"),
        "can_execute_numerical_model": record.get("can_execute_numerical_model"),
        "pool_family_encoder_probe_validated": record.get(
            "pool_family_encoder_probe_validated"
        ),
        "ga_quant_add_dequant_probe_validated": record.get(
            "ga_quant_add_dequant_probe_validated"
        ),
        "matmul_gemv_config_probe_validated": record.get(
            "matmul_gemv_config_probe_validated"
        ),
        "sum_family_config_probe_validated": record.get(
            "sum_family_config_probe_validated"
        ),
        "resnet50_operator_coverage_complete": record.get(
            "resnet50_operator_coverage_complete"
        ),
        "reasons": reasons,
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
    target_config_toolchain = _target_config_toolchain_status(root)
    legacy16_evidence = _legacy16_evidence_status(
        report_payloads, network_profiles
    )
    current_evidence_artifacts = _current_evidence_artifact_checks(
        root, architecture
    )
    current_target_evidence = _current_target_evidence_status(
        architecture, hardware_approval, current_evidence_artifacts
    )
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
            item["interface_complete"]
            for item in interfaces
            if item["target_family"] == "legacy16"
        ),
        "current_target_layout_interfaces_complete": all(
            item["interface_complete"]
            for item in interfaces
            if item["target_family"] == "rtl28"
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
        "current_target_layout_interfaces_complete": reusable_criteria[
            "current_target_layout_interfaces_complete"
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
        "target_rtl_isa_register_map_version_frozen": target_config_toolchain[
            "version_frozen"
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
        "target_family": CURRENT_TARGET_FAMILY,
        "slice_count": CURRENT_TARGET_SLICE_COUNT,
        "architecture_id": architecture["target"]["architecture_id"],
        "architecture_sha256": sha256_file(architecture_path),
        "profile_ids": sorted(architecture["target"]["profiles"]["candidates"]),
        "current_gate_eligible": g4_passed,
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
        "current_evidence_artifacts": current_evidence_artifacts,
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
        "target_config_toolchain": target_config_toolchain,
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
