from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ContractError
from .hashing import combined_hash, sha256_file
from .hardware_approval import (
    ALTERNATIVE_LAYOUTS,
    KNOWN_LAYOUT_IDS,
    PROFILE_LAYOUTS,
    TARGET_ARCHITECTURE_ID,
    TARGET_ARCHITECTURE_SCHEMA_VERSION,
    TARGET_DRAM,
    TARGET_FAMILY,
    TARGET_FILELIST,
    TARGET_RTL_COMMIT,
    TARGET_RTL_REPOSITORY,
    TARGET_SLICE_COUNT,
    TARGET_TOPOLOGY_ID,
    TARGET_TOP_MODULE,
)
from .profile28 import (
    DEEPSEEK_HYBRID28_PROFILE,
    GROUP_SAMPLE_COUNTS,
    OPERATOR_COMMUNICATION_DOMAINS,
    SUPPORTED_PROFILES,
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
from .topology28 import HIGH_RING_OWNERS, LOW_RING_OWNERS
from .typed_config_parameters import (
    TypedConfigParameterError,
    validate_typed_config_parameter_contract,
)
from .w4_evidence import LEGACY16_METADATA, architecture_evidence_basis_sha256

ALLOWED_CONTRACT_STATUSES = {
    "candidate",
    "provisionally_approved",
    "approved",
    "approved_for_w0_only",
}

SUPPORTED_CONTRACT_SCHEMA_VERSIONS = {
    "architecture": {TARGET_ARCHITECTURE_SCHEMA_VERSION},
    "quantization": {"0.1"},
    "backend": {"0.2"},
}

CURRENT_W4_EVIDENCE_REQUIREMENTS = {
    "w4_rtl28_network_physical_edges_v1": {
        "evidence_kind": "network_physical_edge_audit",
        "path_kind": "network-physical-edge-audit",
        "metric_fields": {
            "edge_count": 93,
            "qparam_edge_count": 91,
            "residual_add_count": 16,
        },
    },
    "w4_rtl28_network_profile_cost_v1": {
        "evidence_kind": "network_profile_cost",
        "path_kind": "network-profile-cost",
        "metric_fields": {"scenario_count": 2},
    },
}


def _require_keys(value: dict[str, Any], required: set[str], location: str) -> None:
    missing = sorted(required - set(value))
    if missing:
        raise ContractError(f"{location} missing required fields: {missing}")
    unexpected = sorted(set(value) - required)
    if unexpected:
        raise ContractError(f"{location} contains unexpected fields: {unexpected}")


def _validate_layout_registry(
    registry: Any, location: str, allowed_statuses: set[str]
) -> None:
    if not isinstance(registry, dict):
        raise ContractError(f"{location} must be an object")
    for layout_id, record in registry.items():
        if not isinstance(record, dict):
            raise ContractError(f"{location}.{layout_id} must be an object")
        if record.get("target_family") != TARGET_FAMILY:
            raise ContractError(f"{location}.{layout_id} must target {TARGET_FAMILY}")
        if record.get("slice_count") != TARGET_SLICE_COUNT:
            raise ContractError(
                f"{location}.{layout_id} must contain {TARGET_SLICE_COUNT} slices"
            )
        if record.get("operator_family") not in OPERATOR_COMMUNICATION_DOMAINS:
            raise ContractError(f"{location}.{layout_id} has an unknown operator_family")
        if record.get("status") not in allowed_statuses:
            raise ContractError(f"{location}.{layout_id} has invalid status")
        if not isinstance(record.get("current_gate_eligible"), bool):
            raise ContractError(
                f"{location}.{layout_id}.current_gate_eligible must be boolean"
            )


def _validate_current_w4_evidence(
    architecture: dict[str, Any], root: Path | None
) -> None:
    registry = architecture["candidate_evidence"]
    basis_sha256 = architecture_evidence_basis_sha256(architecture)
    for evidence_id, requirement in CURRENT_W4_EVIDENCE_REQUIREMENTS.items():
        record = registry.get(evidence_id)
        if not isinstance(record, dict):
            raise ContractError(f"candidate_evidence must register {evidence_id}")
        expected_fields = {
            "target_family",
            "slice_count",
            "status",
            "current_gate_eligible",
            "evidence_kind",
            "architecture_basis_sha256",
            "path",
            "sha256",
            "size_bytes",
            "all_scenarios_pass",
            "hardware_approval",
            "g4_passed",
            "w5_authorized",
            *requirement["metric_fields"],
        }
        _require_keys(record, expected_fields, f"candidate_evidence.{evidence_id}")
        expected_values = {
            "target_family": TARGET_FAMILY,
            "slice_count": TARGET_SLICE_COUNT,
            "status": "candidate_software_evidence",
            "current_gate_eligible": True,
            "evidence_kind": requirement["evidence_kind"],
            "architecture_basis_sha256": basis_sha256,
            "all_scenarios_pass": True,
            "hardware_approval": False,
            "g4_passed": False,
            "w5_authorized": False,
            **requirement["metric_fields"],
        }
        for field, expected in expected_values.items():
            if record.get(field) != expected:
                raise ContractError(
                    f"candidate_evidence.{evidence_id}.{field} must be {expected!r}"
                )
        digest = record["sha256"]
        if not isinstance(digest, str) or len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise ContractError(
                f"candidate_evidence.{evidence_id}.sha256 must be lowercase SHA-256"
            )
        if not isinstance(record["size_bytes"], int) or record["size_bytes"] <= 0:
            raise ContractError(
                f"candidate_evidence.{evidence_id}.size_bytes must be positive"
            )
        expected_path = (
            f"artifacts/w4/rtl28/{basis_sha256}/"
            f"{requirement['path_kind']}-{digest}.json"
        )
        if record["path"] != expected_path:
            raise ContractError(
                f"candidate_evidence.{evidence_id}.path must be {expected_path}"
            )
        if root is None:
            continue
        path = root.parent / expected_path
        if not path.is_file():
            raise ContractError(f"registered RTL28 W4 evidence is missing: {path}")
        if path.stat().st_size != record["size_bytes"]:
            raise ContractError(f"RTL28 W4 evidence size mismatch: {evidence_id}")
        if sha256_file(path) != digest:
            raise ContractError(f"RTL28 W4 evidence hash mismatch: {evidence_id}")
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ContractError(
                f"RTL28 W4 evidence is invalid JSON: {evidence_id}"
            ) from error
        for field, expected in expected_values.items():
            if report.get(field) != expected:
                raise ContractError(
                    f"RTL28 W4 evidence {evidence_id}.{field} must be {expected!r}"
                )
        scenarios = report.get("scenarios")
        if not isinstance(scenarios, dict) or set(scenarios) != {
            "group4x7_only",
            "group4x7_to_global_head",
        }:
            raise ContractError(
                f"RTL28 W4 evidence {evidence_id} must contain both scenarios"
            )
        if requirement["evidence_kind"] == "network_physical_edge_audit":
            for scenario_id, scenario in scenarios.items():
                transition = scenario.get("transition_audit", {})
                memory = scenario.get("memory_lifecycle", {})
                if (
                    transition.get("edge_count") != 93
                    or transition.get("qparam_edge_count") != 91
                    or transition.get("residual_add_count") != 16
                    or transition.get("all_qparam_identities_exact") is not True
                    or transition.get("all_residual_adds_compatible") is not True
                    or transition.get("all_edge_policies_verified") is not True
                    or memory.get("runtime_tensor_count") != 79
                    or len(memory.get("alias_edge_checks", ())) != 93
                    or len(memory.get("residual_branch_checks", ())) != 16
                    or memory.get("all_allocations_fit") is not True
                    or memory.get("all_lifetime_overlaps_address_disjoint") is not True
                    or memory.get("all_alias_actions_conflict_free") is not True
                    or memory.get(
                        "all_residual_branches_distinct_live_and_disjoint"
                    )
                    is not True
                ):
                    raise ContractError(
                        f"RTL28 edge evidence scenario failed: {scenario_id}"
                    )
        else:
            for scenario_id, scenario in scenarios.items():
                if (
                    scenario.get("node_count") != 78
                    or scenario.get("all_standalone_node_plans_fit") is not True
                ):
                    raise ContractError(
                        f"RTL28 cost evidence scenario failed: {scenario_id}"
                    )
def validate_architecture_contract(value: dict[str, Any], root: Path | None = None) -> None:
    required_root = {
        "schema_version",
        "contract_type",
        "status",
        "scope",
        "target",
        "candidate_memory",
        "planned_layouts",
        "candidate_layouts",
        "fixture_layouts",
        "legacy_target",
        "legacy_layouts",
        "candidate_evidence",
        "legacy_evidence",
        "unresolved",
    }
    _require_keys(value, required_root, "architecture contract")
    if value["scope"] != "target_rtl28":
        raise ContractError("architecture scope must be target_rtl28")

    target = value["target"]
    if not isinstance(target, dict):
        raise ContractError("architecture.target must be an object")
    _require_keys(
        target,
        {
            "architecture_id",
            "target_family",
            "slice_count",
            "status",
            "rtl",
            "arrays",
            "instruction_mask_bits",
            "topology",
            "profiles",
        },
        "architecture.target",
    )
    if (
        target["architecture_id"] != TARGET_ARCHITECTURE_ID
        or target["target_family"] != TARGET_FAMILY
        or target["slice_count"] != TARGET_SLICE_COUNT
        or target["status"] != "approved_for_w4_baseline"
    ):
        raise ContractError("architecture target identity must be the approved RTL28 W4 baseline")
    if target["instruction_mask_bits"] != TARGET_SLICE_COUNT:
        raise ContractError("architecture instruction mask must contain 28 bits")

    rtl = target["rtl"]
    if not isinstance(rtl, dict):
        raise ContractError("architecture.target.rtl must be an object")
    _require_keys(
        rtl,
        {"repository", "commit", "top_module", "filelist", "clean_elaboration_status"},
        "architecture.target.rtl",
    )
    if (
        rtl["repository"] != TARGET_RTL_REPOSITORY
        or rtl["commit"] != TARGET_RTL_COMMIT
        or rtl["top_module"] != TARGET_TOP_MODULE
        or rtl["filelist"] != TARGET_FILELIST
    ):
        raise ContractError("architecture RTL identity is not the selected candidate")
    if rtl["clean_elaboration_status"] != "operator_confirmed_known_good_no_log_claim":
        raise ContractError("architecture must record the named baseline without claiming an elaboration log")

    arrays = target["arrays"]
    if not isinstance(arrays, dict) or set(arrays) != {"specialized", "general"}:
        raise ContractError("architecture arrays must contain specialized and general")
    expected_arrays = {"specialized": (8, 8), "general": (4, 4)}
    for name, expected in expected_arrays.items():
        record = arrays[name]
        if (
            not isinstance(record, dict)
            or (record.get("rows"), record.get("cols")) != expected
            or record.get("status") != "approved_by_deepseek_inheritance"
        ):
            raise ContractError(f"architecture {name} array must match RTL evidence")

    topology = target["topology"]
    if not isinstance(topology, dict):
        raise ContractError("architecture topology must be an object")
    if topology.get("topology_id") != TARGET_TOPOLOGY_ID:
        raise ContractError("architecture topology_id is not the selected RTL28 map")
    if topology.get("status") != "approved_by_deepseek_inheritance":
        raise ContractError("architecture topology must use the inherited DeepSeek baseline")
    if topology.get("high_ring_owners") != [list(item) for item in HIGH_RING_OWNERS]:
        raise ContractError("architecture HIGH topology differs from topology28")
    if topology.get("low_ring_owners") != list(LOW_RING_OWNERS):
        raise ContractError("architecture LOW topology differs from topology28")

    profiles = target["profiles"]
    if not isinstance(profiles, dict):
        raise ContractError("architecture profiles must be an object")
    expected_profile_fields = {
        "default",
        "approved",
        "physical_layout_alternatives",
        "instruction_mask",
        "operator_communication_domains",
        "batch_group_sample_counts",
        "transition_policy",
        "source",
    }
    _require_keys(profiles, expected_profile_fields, "architecture.target.profiles")
    if profiles.get("default") != DEEPSEEK_HYBRID28_PROFILE:
        raise ContractError("architecture default profile must be the DeepSeek hybrid28 profile")
    if profiles.get("approved") != [DEEPSEEK_HYBRID28_PROFILE]:
        raise ContractError("architecture must approve exactly the DeepSeek hybrid28 profile")
    if set(profiles.get("physical_layout_alternatives", [])) != set(SUPPORTED_PROFILES):
        raise ContractError("architecture physical alternatives must preserve both RTL28 layouts")
    if profiles.get("instruction_mask") != "0b1111111111111111111111111111":
        raise ContractError("architecture network profile must use the full 28-bit instruction mask")
    if profiles.get("operator_communication_domains") != OPERATOR_COMMUNICATION_DOMAINS:
        raise ContractError("architecture operator communication domains are invalid")
    if profiles.get("batch_group_sample_counts") != list(GROUP_SAMPLE_COUNTS):
        raise ContractError("architecture batch groups must be [3,3,2,2,2,2,2]")

    memory = value["candidate_memory"]
    if not isinstance(memory, dict):
        raise ContractError("candidate_memory must be an object")
    expected_memory = {
        "status": "approved_for_w4_physical_contract",
        "geometry_status": "approved_by_deepseek_inheritance",
        "address_order_status": "approved_by_deepseek_inheritance",
        **TARGET_DRAM,
    }
    for field, expected in expected_memory.items():
        if memory.get(field) != expected:
            raise ContractError(f"candidate_memory.{field} differs from RTL28 evidence")

    _validate_layout_registry(value["planned_layouts"], "planned_layouts", {"planned"})
    _validate_layout_registry(
        value["candidate_layouts"], "candidate_layouts", {"candidate", "approved"}
    )
    expected_layout_ids = set(KNOWN_LAYOUT_IDS)
    planned_ids = set(value["planned_layouts"])
    candidate_ids = set(value["candidate_layouts"])
    if planned_ids & candidate_ids:
        raise ContractError("planned_layouts and candidate_layouts must be disjoint")
    if planned_ids | candidate_ids != expected_layout_ids:
        raise ContractError(
            "planned/candidate layouts do not match the frozen profile28 layout IDs"
        )
    for profile, mapping in PROFILE_LAYOUTS.items():
        for family, layout_id in mapping.items():
            registry = (
                value["candidate_layouts"]
                if layout_id in candidate_ids
                else value["planned_layouts"]
            )
            if registry[layout_id]["operator_family"] != family:
                raise ContractError(f"planned layout family mismatch for {profile}:{family}")
            record = registry[layout_id]
            if (
                record.get("status") != "approved"
                or record.get("current_gate_eligible") is not True
                or record.get("network_profile_id") != profile
                or record.get("communication_domain")
                != OPERATOR_COMMUNICATION_DOMAINS[family]
            ):
                raise ContractError(f"selected layout is not approved for {profile}:{family}")
    for family, layout_id in ALTERNATIVE_LAYOUTS.items():
        record = value["candidate_layouts"][layout_id]
        if (
            record.get("operator_family") != family
            or record.get("status") != "candidate"
            or record.get("current_gate_eligible") is not False
        ):
            raise ContractError(f"LOW-28 alternative must remain gate-ineligible: {family}")

    fixture_layouts = value["fixture_layouts"]
    if not isinstance(fixture_layouts, dict) or not fixture_layouts:
        raise ContractError("fixture_layouts must preserve the W2 functional fixture")
    if any(record.get("current_gate_eligible") is not False for record in fixture_layouts.values()):
        raise ContractError("fixture layouts cannot be current-gate eligible")

    legacy_target = value["legacy_target"]
    if (
        not isinstance(legacy_target, dict)
        or legacy_target.get("target_family") != "legacy16"
        or legacy_target.get("slice_count") != 16
        or legacy_target.get("current_gate_eligible") is not False
    ):
        raise ContractError("legacy16 target must be explicit and gate-ineligible")
    if not isinstance(value["legacy_layouts"], dict) or not value["legacy_layouts"]:
        raise ContractError("legacy_layouts must preserve old16 evidence")
    if any(layout_id in value["candidate_layouts"] for layout_id in value["legacy_layouts"]):
        raise ContractError("legacy layout leaked into current candidate_layouts")
    if not isinstance(value["legacy_evidence"], dict) or not value["legacy_evidence"]:
        raise ContractError("legacy_evidence must preserve old16 reports")
    for evidence_id, record in value["legacy_evidence"].items():
        if not isinstance(record, dict):
            raise ContractError(f"legacy_evidence.{evidence_id} must be an object")
        for field in ("target_family", "slice_count", "current_gate_eligible"):
            if record.get(field) != LEGACY16_METADATA[field]:
                raise ContractError(
                    f"legacy_evidence.{evidence_id}.{field} must remain legacy16"
                )
        if record.get("status") != LEGACY16_METADATA["status"]:
            raise ContractError(
                f"legacy_evidence.{evidence_id}.status must remain superseded"
            )

    legacy_report_records = dict(value["legacy_evidence"])
    legacy_report_records.update(
        {
            "w4_conv0_batch16_layout_v1": value["legacy_layouts"][
                "w4_conv_batch16_candidate_v1"
            ]["formal_conv0_report"],
            "w4_conv0_profile_comparison_v1": value["legacy_layouts"][
                "w4_conv_ring16_candidate_v1"
            ]["formal_conv0_profile_comparison"],
        }
    )
    index_record = legacy_target.get("evidence_index")
    if not isinstance(index_record, dict):
        raise ContractError("legacy_target.evidence_index must be an object")
    if set(index_record) != {"path", "size_bytes", "sha256"}:
        raise ContractError("legacy_target.evidence_index fields are invalid")
    for evidence_id, record in legacy_report_records.items():
        if not isinstance(record.get("path"), str) or not record["path"]:
            raise ContractError(f"legacy report {evidence_id} has no path")
        if not isinstance(record.get("size_bytes"), int) or record["size_bytes"] <= 0:
            raise ContractError(f"legacy report {evidence_id} has invalid size")
        digest = record.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ContractError(f"legacy report {evidence_id} has invalid SHA-256")

    if root is not None:
        evidence_index_path = root.parent / index_record["path"]
        if not evidence_index_path.is_file():
            raise ContractError("legacy16 evidence index is missing")
        if evidence_index_path.stat().st_size != index_record["size_bytes"]:
            raise ContractError("legacy16 evidence index size mismatch")
        if sha256_file(evidence_index_path) != index_record["sha256"]:
            raise ContractError("legacy16 evidence index hash mismatch")
        try:
            legacy_index = json.loads(evidence_index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ContractError("legacy16 evidence index is invalid JSON") from error
        for field, expected in LEGACY16_METADATA.items():
            if legacy_index.get(field) != expected:
                raise ContractError(
                    f"legacy16 evidence index {field} must be {expected!r}"
                )
        indexed_reports = legacy_index.get("reports")
        if not isinstance(indexed_reports, dict) or set(indexed_reports) != set(
            legacy_report_records
        ):
            raise ContractError("legacy16 evidence index does not list exactly nine reports")
        for evidence_id, record in legacy_report_records.items():
            indexed = indexed_reports[evidence_id]
            identity = {
                field: record[field] for field in ("path", "size_bytes", "sha256")
            }
            if indexed != identity:
                raise ContractError(
                    f"legacy16 evidence index differs for {evidence_id}"
                )
            report_path = root.parent / record["path"]
            if not report_path.is_file():
                raise ContractError(f"legacy16 evidence is missing: {report_path}")
            if report_path.stat().st_size != record["size_bytes"]:
                raise ContractError(f"legacy16 evidence size mismatch: {evidence_id}")
            if sha256_file(report_path) != record["sha256"]:
                raise ContractError(f"legacy16 evidence hash mismatch: {evidence_id}")
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise ContractError(
                    f"legacy16 evidence is invalid JSON: {evidence_id}"
                ) from error
            for field, expected in LEGACY16_METADATA.items():
                if report.get(field) != expected:
                    raise ContractError(
                        f"legacy16 evidence {evidence_id}.{field} must be {expected!r}"
                    )

    candidate_evidence = value["candidate_evidence"]
    if not isinstance(candidate_evidence, dict) or "rtl28_static_audit_v1" not in candidate_evidence:
        raise ContractError("candidate_evidence must register the RTL28 static audit")
    rtl_evidence = candidate_evidence["rtl28_static_audit_v1"]
    if (
        rtl_evidence.get("target_family") != TARGET_FAMILY
        or rtl_evidence.get("slice_count") != TARGET_SLICE_COUNT
        or rtl_evidence.get("status") != "candidate_unapproved"
        or rtl_evidence.get("current_gate_eligible") is not False
        or rtl_evidence.get("clean_elaboration") is not False
    ):
        raise ContractError("RTL28 static evidence must remain candidate and gate-ineligible")
    if root is not None:
        evidence_path = root.parent / rtl_evidence["path"]
        if not evidence_path.is_file():
            raise ContractError(f"registered RTL28 evidence is missing: {evidence_path}")
        if evidence_path.stat().st_size != rtl_evidence["size_bytes"]:
            raise ContractError("registered RTL28 evidence size mismatch")
        if sha256_file(evidence_path) != rtl_evidence["sha256"]:
            raise ContractError("registered RTL28 evidence hash mismatch")

    _validate_current_w4_evidence(value, root)

    unresolved = value["unresolved"]
    if not isinstance(unresolved, list) or not unresolved or any(
        not isinstance(item, str) or not item for item in unresolved
    ):
        raise ContractError("architecture unresolved list must contain explicit blockers")


def validate_backend_contract(
    value: dict[str, Any], architecture: dict[str, Any], root: Path | None = None
) -> None:
    _require_keys(
        value,
        {"schema_version", "contract_type", "status", "backends", "unresolved"},
        "backend contract",
    )
    backends = value["backends"]
    if not isinstance(backends, dict):
        raise ContractError("backend.backends must be an object")
    expected_names = {
        "mock",
        "ndp_conv_functional",
        "rtl28_candidate_evidence",
        "target_config_toolchain",
        "target_simulator",
        "target_hardware",
    }
    if set(backends) != expected_names:
        raise ContractError("backend registry does not contain the exact expected roles")

    ndp = backends["ndp_conv_functional"]
    if not isinstance(ndp, dict):
        raise ContractError("backend.ndp_conv_functional must be an object")
    if (
        ndp.get("status") != "operator_confirmed_conv_simulator_component"
        or ndp.get("role")
        != "conv_functional_simulator_with_typed_1x1_accumulate_requant_json_adapter"
        or ndp.get("source_repository")
        != "https://github.com/runoobb/NDPFuncModel.git"
        or ndp.get("source_commit")
        != "cb262bb9cef35107776c802e624736a279f288e3"
        or ndp.get("is_target_backend") is not False
        or ndp.get("identity_confirmed") is not True
        or ndp.get("entrypoint") != "tools/physical_image_probe.py"
        or ndp.get("consumes_target_json_or_bitstream") is not True
        or ndp.get("consumes_target_json") is not True
        or ndp.get("consumes_target_bitstream") is not False
        or ndp.get("config_adapter_available") is not True
        or ndp.get("slice_counts") != [1, 4, 28]
    ):
        raise ContractError(
            "NDPFuncModel Conv simulator identity/config-adapter boundary differs"
        )
    ndp_limitations = set(ndp.get("limitations", []))
    if not {
        "real_1x1_config_only",
        "not_cycle_accurate_lc_stream_buffer_interpreter",
        "not_bitstream_interpreter",
        "bulk_tile_and_full_use_physical_dram_equivalent_kernel",
        "not_target_hardware",
        "not_hardware_approved",
    }.issubset(ndp_limitations):
        raise ContractError("NDPFuncModel limitations must preserve the config/runtime boundary")

    architecture_evidence = architecture["candidate_evidence"]["rtl28_static_audit_v1"]
    rtl = backends["rtl28_candidate_evidence"]
    if not isinstance(rtl, dict):
        raise ContractError("backend.rtl28_candidate_evidence must be an object")
    expected_rtl = {
        "status": "candidate_evidence_only",
        "role": "static_rtl_evidence_not_executable_backend",
        "source_repository": TARGET_RTL_REPOSITORY,
        "source_commit": TARGET_RTL_COMMIT,
        "snapshot_path": architecture_evidence["path"],
        "snapshot_sha256": architecture_evidence["sha256"],
        "architecture_id": TARGET_ARCHITECTURE_ID,
        "slice_count": TARGET_SLICE_COUNT,
        "clean_elaboration": False,
        "is_target_backend": False,
        "can_execute": False,
    }
    for field, expected in expected_rtl.items():
        if rtl.get(field) != expected:
            raise ContractError(
                f"backend.rtl28_candidate_evidence.{field} differs from locked evidence"
            )
    if not {
        "candidate_unapproved",
        "not_cleanly_elaborated",
        "not_target_simulator",
        "not_hardware_approval",
    }.issubset(set(rtl.get("limitations", []))):
        raise ContractError("RTL28 evidence limitations must remain fail-closed")
    if root is not None:
        snapshot_path = root.parent / rtl["snapshot_path"]
        if not snapshot_path.is_file() or sha256_file(snapshot_path) != rtl["snapshot_sha256"]:
            raise ContractError("backend RTL28 evidence snapshot is missing or hash-mismatched")

    config_toolchain = backends["target_config_toolchain"]
    if not isinstance(config_toolchain, dict):
        raise ContractError("backend.target_config_toolchain must be an object")
    expected_config_toolchain = {
        "status": "approved_configuration_source",
        "role": "official_target_json_bitstream_execplan_configuration_source",
        "approved": True,
        "authority_basis": "operator_confirmed_2026-07-14",
        "source_repository": OFFICIAL_CONFIG_REPOSITORY,
        "source_commit": OFFICIAL_CONFIG_COMMIT,
        "architecture_id": TARGET_ARCHITECTURE_ID,
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
        "typed_config_parameter_contract_validated": True,
        "resnet50_operator_coverage_complete": False,
    }
    for field, expected in expected_config_toolchain.items():
        if config_toolchain.get(field) != expected:
            raise ContractError(
                f"backend.target_config_toolchain.{field} differs from the approved configuration source"
            )
    if set(config_toolchain.get("limitations", [])) != {
        "not_target_numerical_simulator",
        "not_hardware_execution",
        "resnet_operator_coverage_incomplete",
        "audited_static_template_families_only",
        "avgpool_requantization_absent",
        "uint8_maxpool_semantics_unresolved",
        "quant_rounding_target_execution_unconfirmed",
        "add_dequant_qlinearadd_requantization_absent",
        "execplan_qparam_binding_absent",
        "matmul_int8_psum_requant_tail_absent",
        "sum_cross_slice_and_completion_unproven",
        "sum_metadata_conflict_unresolved",
        "typed_parameter_contract_formula_only",
        "does_not_approve_rtl_or_layout",
    }:
        raise ContractError("target configuration source limitations must remain fail-closed")
    audit_identity = {
        field: config_toolchain.get(field)
        for field in ("audit_path", "audit_sha256", "audit_size_bytes")
    }
    if (
        not isinstance(audit_identity["audit_path"], str)
        or not isinstance(audit_identity["audit_sha256"], str)
        or len(audit_identity["audit_sha256"]) != 64
        or not isinstance(audit_identity["audit_size_bytes"], int)
        or audit_identity["audit_size_bytes"] <= 0
    ):
        raise ContractError("target configuration audit identity is invalid")
    if root is not None:
        audit_path = root.parent / audit_identity["audit_path"]
        if not audit_path.is_file():
            raise ContractError("target configuration authority audit is missing")
        if audit_path.stat().st_size != audit_identity["audit_size_bytes"]:
            raise ContractError("target configuration authority audit size mismatch")
        if sha256_file(audit_path) != audit_identity["audit_sha256"]:
            raise ContractError("target configuration authority audit hash mismatch")
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ContractError("target configuration authority audit is invalid JSON") from error
        if (
            audit.get("schema_version") != "0.4"
            or audit.get("status") != "configuration_source_verified"
            or audit.get("source", {}).get("repository") != OFFICIAL_CONFIG_REPOSITORY
            or audit.get("source", {}).get("commit") != OFFICIAL_CONFIG_COMMIT
            or audit.get("source", {}).get("slice_count") != OFFICIAL_CONFIG_SLICE_COUNT
            or audit.get("inventory", {}).get("json_count") != 42
            or audit.get("inventory", {}).get("named_conv_template_count") != 0
            or audit.get("register_map_audit", {}).get("declared_width_alignment_status") != "passed"
            or audit.get("maxpool_probe", {}).get("determinism", {}).get("status") != "passed"
            or audit.get("maxpool_probe", {}).get("differential_sensitivity", {}).get("status") != "passed"
            or audit.get("maxpool_probe", {}).get("fail_closed", {}).get("status") != "passed"
            or audit.get("pool_family_probe", {}).get("status") != "passed"
            or audit.get("pool_family_probe", {}).get("template_count") != 3
            or audit.get("pool_family_probe", {}).get("linkage", {}).get("status") != "passed"
            or audit.get("pool_family_probe", {})
            .get("linkage", {})
            .get("maxpool_template_delta", {})
            .get("status")
            != "fully_explained"
            or audit.get("pool_family_probe", {})
            .get("linkage", {})
            .get("maxpool_template_delta", {})
            .get("unexpected_paths")
            != []
            or audit.get("pool_family_probe", {}).get("numerical_scope", {}).get("status")
            != "not_validated"
            or audit.get("pool_family_probe", {})
            .get("encoder_probes", {})
            .get(SECOND_MAXPOOL_TEMPLATE, {})
            .get("determinism", {})
            .get("status")
            != "passed"
            or audit.get("pool_family_probe", {})
            .get("encoder_probes", {})
            .get(SECOND_MAXPOOL_TEMPLATE, {})
            .get("differential_sensitivity", {})
            .get("status")
            != "passed"
            or audit.get("pool_family_probe", {})
            .get("encoder_probes", {})
            .get(SECOND_MAXPOOL_TEMPLATE, {})
            .get("fail_closed", {})
            .get("status")
            != "passed"
            or audit.get("pool_family_probe", {})
            .get("encoder_probes", {})
            .get(AVGPOOL_TEMPLATE, {})
            .get("determinism", {})
            .get("status")
            != "passed"
            or audit.get("pool_family_probe", {})
            .get("encoder_probes", {})
            .get(AVGPOOL_TEMPLATE, {})
            .get("differential_sensitivity", {})
            .get("status")
            != "passed"
            or audit.get("pool_family_probe", {})
            .get("encoder_probes", {})
            .get(AVGPOOL_TEMPLATE, {})
            .get("fail_closed", {})
            .get("status")
            != "passed"
            or audit.get("ga_quant_add_probe", {}).get("status")
            != "passed_with_numerical_gaps"
            or audit.get("ga_quant_add_probe", {}).get("template_count") != 2
            or audit.get("ga_quant_add_probe", {}).get("crosswalk", {}).get("status")
            != "passed"
            or audit.get("ga_quant_add_probe", {})
            .get("resnet_scalar_qparams", {})
            .get("operator_counts")
            != {"QuantizeLinear": 2, "DequantizeLinear": 2, "QLinearAdd": 17}
            or audit.get("ga_quant_add_probe", {})
            .get("resnet_scalar_qparams", {})
            .get("static_template_comparison", {})
            .get("quantize_linear_direct_match_count")
            != 0
            or audit.get("ga_quant_add_probe", {})
            .get("resnet_scalar_qparams", {})
            .get("static_template_comparison", {})
            .get("dequantize_linear_fixed_branch_match_count")
            != 0
            or audit.get("ga_quant_add_probe", {})
            .get("resnet_scalar_qparams", {})
            .get("static_template_comparison", {})
            .get("qlinearadd_branch_affine_match_count")
            != 0
            or audit.get("ga_quant_add_probe", {})
            .get("execplan_qparam_binding", {})
            .get("status")
            != "gap_confirmed"
            or audit.get("ga_quant_add_probe", {})
            .get("execplan_qparam_binding", {})
            .get("ga_constant_qparams_patched")
            is not False
            or audit.get("ga_quant_add_probe", {}).get("numerical_scope", {}).get("status")
            != "not_validated"
            or any(
                audit.get("ga_quant_add_probe", {})
                .get("encoder_probes", {})
                .get(template_name, {})
                .get(probe_name, {})
                .get("status")
                != "passed"
                for template_name in (QUANT_TEMPLATE, ADD_DEQUANT_TEMPLATE)
                for probe_name in ("determinism", "differential_sensitivity", "fail_closed")
            )
            or audit.get("matmul_config_probe", {}).get("status")
            != "candidate_preflight_only"
            or audit.get("matmul_config_probe", {})
            .get("inventory", {})
            .get("candidate_count")
            != 6
            or audit.get("matmul_config_probe", {})
            .get("inventory", {})
            .get("named_int8_template_count")
            != 0
            or audit.get("matmul_config_probe", {})
            .get("crosswalk", {})
            .get("handler_binding", {})
            .get("status")
            != "partial_binding_only"
            or audit.get("matmul_config_probe", {})
            .get("crosswalk", {})
            .get("resnet_qlinearmatmul_gap", {})
            .get("complete_compatible_template_exists")
            is not False
            or audit.get("matmul_config_probe", {})
            .get("encoder_probe", {})
            .get("determinism", {})
            .get("status")
            != "passed"
            or audit.get("matmul_config_probe", {})
            .get("encoder_probe", {})
            .get("differential_sensitivity", {})
            .get("status")
            != "passed"
            or audit.get("matmul_config_probe", {})
            .get("encoder_probe", {})
            .get("fail_closed", {})
            .get("status")
            != "passed"
            or audit.get("matmul_config_probe", {}).get("numerical_status")
            != "not_validated"
            or audit.get("matmul_config_probe", {}).get("no_gate_authority") is not True
            or audit.get("sum_config_probe", {})
            .get("authority", {})
            .get("status")
            != "candidate_preflight_only"
            or audit.get("sum_config_probe", {}).get("scope", {}).get("template_count")
            != 11
            or audit.get("sum_config_probe", {})
            .get("handler_gaps", {})
            .get("fp16_remote_4slice_metadata_conflict")
            is not True
            or audit.get("sum_config_probe", {})
            .get("handler_gaps", {})
            .get("output_shape_not_used_by_any_sum_handler")
            is not True
            or len(audit.get("sum_config_probe", {}).get("encoder_probe", {})) != 11
            or any(
                record.get("status") != "encoding_deterministic"
                or record.get("numerical_status") != "not_validated"
                or record.get("no_gate_authority") is not True
                for record in audit.get("sum_config_probe", {})
                .get("encoder_probe", {})
                .values()
            )
            or audit.get("sum_config_probe", {})
            .get("authority", {})
            .get("hardware_status")
            != "not_validated"
            or audit.get("sum_config_probe", {})
            .get("authority", {})
            .get("no_gate_authority")
            is not True
        ):
            raise ContractError("target configuration authority audit semantics are invalid")

    typed_identity = {
        field: config_toolchain.get(field)
        for field in (
            "typed_parameter_contract_path",
            "typed_parameter_contract_sha256",
            "typed_parameter_contract_size_bytes",
        )
    }
    if (
        not isinstance(typed_identity["typed_parameter_contract_path"], str)
        or not isinstance(typed_identity["typed_parameter_contract_sha256"], str)
        or len(typed_identity["typed_parameter_contract_sha256"]) != 64
        or not isinstance(typed_identity["typed_parameter_contract_size_bytes"], int)
        or typed_identity["typed_parameter_contract_size_bytes"] <= 0
    ):
        raise ContractError("typed configuration parameter contract identity is invalid")
    if root is not None:
        typed_path = root.parent / typed_identity["typed_parameter_contract_path"]
        if not typed_path.is_file():
            raise ContractError("typed configuration parameter contract is missing")
        if typed_path.stat().st_size != typed_identity["typed_parameter_contract_size_bytes"]:
            raise ContractError("typed configuration parameter contract size mismatch")
        if sha256_file(typed_path) != typed_identity["typed_parameter_contract_sha256"]:
            raise ContractError("typed configuration parameter contract hash mismatch")
        try:
            typed_contract = json.loads(typed_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ContractError(
                "typed configuration parameter contract is invalid JSON"
            ) from error
        try:
            validate_typed_config_parameter_contract(typed_contract)
        except TypedConfigParameterError as error:
            raise ContractError(
                "typed configuration parameter contract semantics are invalid"
            ) from error
        if (
            typed_contract.get("source", {}).get("target_config_authority_sha256")
            != audit_identity["audit_sha256"]
        ):
            raise ContractError(
                "typed configuration parameter contract targets a different authority audit"
            )

    simulator = backends["target_simulator"]
    if not isinstance(simulator, dict):
        raise ContractError("backend.target_simulator must be an object")
    if (
        simulator.get("status")
        != "operator_confirmed_conv_backend_config_bound_candidate"
        or simulator.get("approved") is not False
        or simulator.get("identity_confirmed") is not True
        or simulator.get("implementation_available") is not True
        or simulator.get("backend") != "ndp_conv_functional"
        or simulator.get("supported_ops") != ["QLinearConv"]
        or simulator.get("entrypoint")
        != "NDPFuncModel/tools/physical_image_probe.py"
        or simulator.get("consumes_target_json_or_bitstream") is not True
        or simulator.get("consumes_target_json") is not True
        or simulator.get("consumes_target_bitstream") is not False
        or simulator.get("config_adapter_available") is not True
        or simulator.get("can_dump_physical_output") is not True
        or simulator.get("g6_ready") is not False
    ):
        raise ContractError(
            "target simulator must preserve the config-bound candidate boundary"
        )
    hardware = backends["target_hardware"]
    if not isinstance(hardware, dict):
        raise ContractError("backend.target_hardware must be an object")
    if (
        hardware.get("status")
        != "operator_confirmed_deepseek_json_execution_runtime_interface_deferred"
        or hardware.get("approved") is not False
        or hardware.get("implementation_available") is not True
        or hardware.get("deepseek_json_execution_confirmed") is not True
        or hardware.get("confirmation_basis") != "operator_confirmed_2026-07-14"
        or hardware.get("runtime_interface_available_to_project") is not False
        or hardware.get("exact_conv_1x1_candidate_executed") is not False
        or hardware.get("exact_candidate_validation_status")
        != "deferred_by_operator"
        or hardware.get("architecture_id") != TARGET_ARCHITECTURE_ID
        or hardware.get("candidate_evidence_backend") != "rtl28_candidate_evidence"
        or hardware.get("w4_physical_baseline_approved") is not True
        or hardware.get("w4_approval_path") != "contracts/hardware_approval.json"
    ):
        raise ContractError("target hardware must separate W4 physical approval from W8 runtime approval")
    approval_digest = hardware.get("w4_approval_sha256")
    if not isinstance(approval_digest, str) or len(approval_digest) != 64:
        raise ContractError("target hardware W4 approval hash must be lowercase SHA-256")
    if root is not None:
        approval_path = root.parent / hardware["w4_approval_path"]
        if not approval_path.is_file() or sha256_file(approval_path) != approval_digest:
            raise ContractError("target hardware W4 approval file/hash mismatch")

    unresolved = value["unresolved"]
    if not isinstance(unresolved, list) or not unresolved or any(
        not isinstance(item, str) or not item for item in unresolved
    ):
        raise ContractError("backend unresolved list must contain explicit blockers")
    expected_unresolved = {
        "execplan typed qparam transport",
        "hardware load/start/wait/error/dump protocol for later exact-candidate validation",
    }
    if set(unresolved) != expected_unresolved:
        raise ContractError("backend unresolved list differs from the current blocker set")


@dataclass(frozen=True)
class ContractSet:
    documents: dict[str, dict[str, Any]]
    hashes: dict[str, str]

    @property
    def digest(self) -> str:
        return combined_hash(f"{name}:{self.hashes[name]}" for name in sorted(self.hashes))


def load_contracts(root: Path) -> ContractSet:
    required = ("architecture", "quantization", "backend")
    documents: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for name in required:
        path = root / f"{name}.json"
        if not path.is_file():
            raise ContractError(f"missing required contract: {path}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema_version") not in SUPPORTED_CONTRACT_SCHEMA_VERSIONS[name]:
            raise ContractError(f"unsupported contract schema in {path}")
        if value.get("contract_type") != name:
            raise ContractError(f"contract_type mismatch in {path}")
        if value.get("status") not in ALLOWED_CONTRACT_STATUSES:
            raise ContractError(f"invalid contract status in {path}")
        documents[name] = value
        hashes[name] = sha256_file(path)
    validate_architecture_contract(documents["architecture"], root)
    validate_backend_contract(documents["backend"], documents["architecture"], root)
    return ContractSet(documents=documents, hashes=hashes)
