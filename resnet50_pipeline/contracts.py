from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ContractError
from .hashing import combined_hash, sha256_file
from .hardware_approval import (
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
    DEFAULT_PROFILE,
    GROUP_SAMPLE_COUNTS,
    SUPPORTED_PROFILES,
)
from .topology28 import HIGH_RING_OWNERS, LOW_RING_OWNERS
from .w4_evidence import LEGACY16_METADATA

ALLOWED_CONTRACT_STATUSES = {
    "candidate",
    "provisionally_approved",
    "approved",
    "approved_for_w0_only",
}

SUPPORTED_CONTRACT_SCHEMA_VERSIONS = {
    "architecture": {TARGET_ARCHITECTURE_SCHEMA_VERSION},
    "quantization": {"0.1"},
    "backend": {"0.1"},
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
        if record.get("operator_family") not in PROFILE_LAYOUTS[DEFAULT_PROFILE]:
            raise ContractError(f"{location}.{layout_id} has an unknown operator_family")
        if record.get("status") not in allowed_statuses:
            raise ContractError(f"{location}.{layout_id} has invalid status")
        if not isinstance(record.get("current_gate_eligible"), bool):
            raise ContractError(
                f"{location}.{layout_id}.current_gate_eligible must be boolean"
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
        or target["status"] != "candidate_unapproved"
    ):
        raise ContractError("architecture target identity must be the current RTL28 candidate")
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
    if rtl["clean_elaboration_status"] != "blocked_not_clean":
        raise ContractError("candidate architecture must not claim clean elaboration")

    arrays = target["arrays"]
    if not isinstance(arrays, dict) or set(arrays) != {"specialized", "general"}:
        raise ContractError("architecture arrays must contain specialized and general")
    expected_arrays = {"specialized": (8, 8), "general": (4, 4)}
    for name, expected in expected_arrays.items():
        record = arrays[name]
        if (
            not isinstance(record, dict)
            or (record.get("rows"), record.get("cols")) != expected
            or record.get("status") != "candidate_unapproved"
        ):
            raise ContractError(f"architecture {name} array must match RTL evidence")

    topology = target["topology"]
    if not isinstance(topology, dict):
        raise ContractError("architecture topology must be an object")
    if topology.get("topology_id") != TARGET_TOPOLOGY_ID:
        raise ContractError("architecture topology_id is not the selected RTL28 map")
    if topology.get("status") != "candidate_unapproved":
        raise ContractError("architecture topology must remain candidate_unapproved")
    if topology.get("high_ring_owners") != [list(item) for item in HIGH_RING_OWNERS]:
        raise ContractError("architecture HIGH topology differs from topology28")
    if topology.get("low_ring_owners") != list(LOW_RING_OWNERS):
        raise ContractError("architecture LOW topology differs from topology28")

    profiles = target["profiles"]
    if not isinstance(profiles, dict):
        raise ContractError("architecture profiles must be an object")
    if profiles.get("default") != DEFAULT_PROFILE:
        raise ContractError("architecture default profile must be the seven-small-ring profile")
    if set(profiles.get("candidates", [])) != set(SUPPORTED_PROFILES):
        raise ContractError("architecture profiles must use exact profile28 IDs")
    if profiles.get("batch_group_sample_counts") != list(GROUP_SAMPLE_COUNTS):
        raise ContractError("architecture batch groups must be [3,3,2,2,2,2,2]")

    memory = value["candidate_memory"]
    if not isinstance(memory, dict):
        raise ContractError("candidate_memory must be an object")
    expected_memory = {
        "status": "candidate_unapproved",
        "geometry_status": "candidate_unapproved",
        "address_order_status": "candidate_unapproved",
        **TARGET_DRAM,
    }
    for field, expected in expected_memory.items():
        if memory.get(field) != expected:
            raise ContractError(f"candidate_memory.{field} differs from RTL28 evidence")

    _validate_layout_registry(value["planned_layouts"], "planned_layouts", {"planned"})
    _validate_layout_registry(
        value["candidate_layouts"], "candidate_layouts", {"candidate", "approved"}
    )
    expected_layout_ids = {
        layout for mapping in PROFILE_LAYOUTS.values() for layout in mapping.values()
    }
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
        "target_simulator",
        "target_hardware",
    }
    if set(backends) != expected_names:
        raise ContractError("backend registry does not contain the exact expected roles")

    ndp = backends["ndp_conv_functional"]
    if not isinstance(ndp, dict):
        raise ContractError("backend.ndp_conv_functional must be an object")
    if (
        ndp.get("status") != "approved_for_w2_g2_only"
        or ndp.get("role") != "w2_functional_reference_only"
        or ndp.get("source_repository")
        != "https://github.com/runoobb/NDPFuncModel.git"
        or ndp.get("source_commit")
        != "35eab40e5314bf603481dd6268bc96ab2ca514a6"
        or ndp.get("is_target_backend") is not False
    ):
        raise ContractError("NDPFuncModel must remain a W2-only functional reference")
    ndp_limitations = set(ndp.get("limitations", []))
    if not {
        "not_target_json_or_bitstream",
        "not_target_simulator",
        "not_target_hardware",
        "not_hardware_approved",
    }.issubset(ndp_limitations):
        raise ContractError("NDPFuncModel limitations must exclude every target backend role")

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

    simulator = backends["target_simulator"]
    if not isinstance(simulator, dict):
        raise ContractError("backend.target_simulator must be an object")
    if (
        simulator.get("status") != "unapproved_missing_authoritative_binding"
        or simulator.get("approved") is not False
        or simulator.get("implementation_available") is not False
    ):
        raise ContractError("target simulator must remain explicitly unapproved")
    hardware = backends["target_hardware"]
    if not isinstance(hardware, dict):
        raise ContractError("backend.target_hardware must be an object")
    if (
        hardware.get("status") != "unapproved_missing_hardware_approval"
        or hardware.get("approved") is not False
        or hardware.get("implementation_available") is not False
        or hardware.get("architecture_id") != TARGET_ARCHITECTURE_ID
        or hardware.get("candidate_evidence_backend") != "rtl28_candidate_evidence"
    ):
        raise ContractError("target hardware must remain explicitly unapproved")

    unresolved = value["unresolved"]
    if not isinstance(unresolved, list) or not unresolved or any(
        not isinstance(item, str) or not item for item in unresolved
    ):
        raise ContractError("backend unresolved list must contain explicit blockers")


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
