from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

from .errors import ContractError
from .hashing import sha256_file
from .profile28 import (
    DEEPSEEK_HYBRID28_PROFILE,
    GROUP_SAMPLE_COUNTS,
    OPERATOR_COMMUNICATION_DOMAINS,
    SUPPORTED_NETWORK_PROFILES,
)


APPROVAL_SCHEMA_VERSION = "0.3"
APPROVAL_CONTRACT_TYPE = "w4_hardware_baseline_approval"
APPROVAL_SCOPE = "w4_profile_and_physical_layout_only"
TARGET_FAMILY = "rtl28"
TARGET_SLICE_COUNT = 28
TARGET_RTL_REPOSITORY = "https://github.com/xlsjdjdk/Trassic2.0_RTL"
TARGET_RTL_COMMIT = "e3bdebba95dec36ee8eba43caa92a326a88392cd"
TARGET_ARCHITECTURE_ID = "trassic2_rtl28_candidate_v1"
TARGET_ARCHITECTURE_SCHEMA_VERSION = "0.2"
TARGET_TOPOLOGY_ID = "rtl28_high7x4_low28_e3bdebba"
TARGET_TOP_MODULE = "NDP_Top_new"
TARGET_FILELIST = "code/NDP_rtl/filelists/NDP_Top_filelist.f"
TARGET_ISA_VERSION = "trassic2-command64-rtl-e3bdebba-v1"
TARGET_REGISTER_MAP_VERSION = "ndp-sim-register-map-groups1-006ca83f-v1"
TARGET_CONFIG_REPOSITORY = "https://github.com/uSFrances/ndp-sim.git"
TARGET_CONFIG_COMMIT = "e299b2804448242d1589b3e58ed7c5a9a5eca09f"
TARGET_DRAM = {
    "bank_count": 4,
    "row_count": 6144,
    "col_count": 64,
    "subword_bytes": 16,
    "address_unit": "byte",
    "address_order": "slice_owner, local_bank, row, column, byte_offset",
}

REQUIRED_PROFILE_KEYS = {
    "simple",
    "view",
    "conv",
    "maxpool",
    "add",
    "global_average_pool",
    "matmul",
}
PROFILE_LAYOUTS = {
    DEEPSEEK_HYBRID28_PROFILE: {
        "simple": "w4_simple_group4x7_28_candidate_v1",
        "view": "w4_zero_copy_view_group4x7_28_candidate_v1",
        "conv": "w4_conv_group4x7_28_candidate_v1",
        "maxpool": "w4_maxpool_group4x7_28_candidate_v1",
        "add": "w4_qlinearadd_group4x7_28_candidate_v1",
        "global_average_pool": "w4_globalavgpool_group4x7_28_candidate_v1",
        "matmul": "w4_qlinearmatmul_group4x7_28_candidate_v1",
    }
}
ALTERNATIVE_LAYOUTS = {
    "simple": "w4_simple_global_ring28_candidate_v1",
    "view": "w4_zero_copy_view_global_ring28_candidate_v1",
    "conv": "w4_conv_global_ring28_candidate_v1",
    "maxpool": "w4_maxpool_global_ring28_candidate_v1",
    "add": "w4_qlinearadd_global_ring28_candidate_v1",
    "global_average_pool": "w4_globalavgpool_global_ring28_candidate_v1",
    "matmul": "w4_qlinearmatmul_global_ring28_candidate_v1",
}
KNOWN_LAYOUT_IDS = frozenset(
    {*PROFILE_LAYOUTS[DEEPSEEK_HYBRID28_PROFILE].values(), *ALTERNATIVE_LAYOUTS.values()}
)
PROFILE_BINDINGS = {
    DEEPSEEK_HYBRID28_PROFILE: {
        family: {
            "layout_id": layout_id,
            "communication_domain": OPERATOR_COMMUNICATION_DOMAINS[family],
        }
        for family, layout_id in PROFILE_LAYOUTS[DEEPSEEK_HYBRID28_PROFILE].items()
    }
}
REQUIRED_W5_DEFERRALS = {
    "int8_conv_sa_bias_psum_requant_configuration",
    "int8_matmul_tail_psum_requant_configuration",
    "typed_qparams_to_register_or_stream_binding",
    "target_numerical_simulator_execution",
    "hardware_runtime_load_wait_dump_protocol",
}
EXPECTED_CONTRACT_LAYERS = {
    "common_baseline": {
        "contract_id": "deepseek-rtl28-physical-baseline-e299b280-v1",
        "path": "contracts/deepseek_rtl28_physical_baseline.json",
    },
    "resnet_delta": {
        "contract_id": "resnet50-rtl28-w4-deepseek-hybrid-delta-v1",
        "path": "contracts/resnet50_rtl28_w4_delta.json",
    },
}


def _require_keys(value: dict[str, Any], required: set[str], location: str) -> None:
    missing = sorted(required - set(value))
    if missing:
        raise ContractError(f"{location} missing required fields: {missing}")
    unexpected = sorted(set(value) - required)
    if unexpected:
        raise ContractError(f"{location} contains unexpected fields: {unexpected}")


def _nonempty_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{location} must be a non-empty string")
    return value.strip()


def _positive_int(value: Any, location: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ContractError(f"{location} must be a positive integer")
    return value


def _require_sha256(value: Any, location: str) -> str:
    digest = _nonempty_string(value, location)
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ContractError(f"{location} must be lowercase SHA-256")
    return digest


def _safe_project_path(root: Path, relative: str, location: str) -> Path:
    raw = Path(_nonempty_string(relative, location))
    if raw.is_absolute():
        raise ContractError(f"{location} must be project-relative")
    path = (root / raw).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise ContractError(f"{location} escapes the project root") from error
    return path


def load_hardware_approval(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ContractError(f"hardware approval contract does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ContractError(f"hardware approval is not valid JSON: {path}") from error
    if not isinstance(value, dict):
        raise ContractError("hardware approval root must be an object")
    return value


def _validate_target_version(value: Any, target: dict[str, Any]) -> str:
    if not isinstance(value, dict):
        raise ContractError("target_version must be an object")
    required = {
        "repository",
        "rtl_commit",
        "top_module",
        "filelist",
        "architecture_id",
        "architecture_schema_version",
        "isa_version",
        "register_map_version",
        "config_repository",
        "config_commit",
    }
    _require_keys(value, required, "target_version")
    exact = {
        "repository": TARGET_RTL_REPOSITORY,
        "rtl_commit": target["rtl"]["commit"],
        "top_module": TARGET_TOP_MODULE,
        "filelist": TARGET_FILELIST,
        "architecture_id": TARGET_ARCHITECTURE_ID,
        "architecture_schema_version": TARGET_ARCHITECTURE_SCHEMA_VERSION,
        "isa_version": TARGET_ISA_VERSION,
        "register_map_version": TARGET_REGISTER_MAP_VERSION,
        "config_repository": TARGET_CONFIG_REPOSITORY,
        "config_commit": TARGET_CONFIG_COMMIT,
    }
    for field, expected in exact.items():
        actual = _nonempty_string(value[field], f"target_version.{field}")
        if actual != expected:
            raise ContractError(f"target_version.{field} must be {expected}")
    if not re.fullmatch(r"[0-9a-f]{40}", value["rtl_commit"]):
        raise ContractError("target_version.rtl_commit must be a full lowercase Git hash")
    return value["rtl_commit"]


def _validate_authority(value: Any) -> str:
    if not isinstance(value, dict):
        raise ContractError("authority must be an object")
    _require_keys(value, {"kind", "authority_id", "role", "recorded_at"}, "authority")
    kind = _nonempty_string(value["kind"], "authority.kind")
    if kind not in {"project_operator", "synthetic_fixture"}:
        raise ContractError("authority.kind is unsupported")
    _nonempty_string(value["authority_id"], "authority.authority_id")
    _nonempty_string(value["role"], "authority.role")
    try:
        dt.date.fromisoformat(_nonempty_string(value["recorded_at"], "authority.recorded_at"))
    except ValueError as error:
        raise ContractError("authority.recorded_at must be an ISO date") from error
    return kind


def _validate_baseline_confirmation(value: Any) -> tuple[str, str]:
    if not isinstance(value, dict):
        raise ContractError("baseline_confirmation must be an object")
    _require_keys(
        value,
        {
            "status",
            "basis",
            "inherited_project",
            "elaboration_log_claimed",
            "decision_uri",
            "decision_sha256",
        },
        "baseline_confirmation",
    )
    if value["status"] != "operator_confirmed_known_good":
        raise ContractError("baseline_confirmation.status must confirm the known-good baseline")
    if value["basis"] != "operator_statement_and_completed_deepseek_bringup":
        raise ContractError("baseline_confirmation.basis is unsupported")
    if value["inherited_project"] != "deepseek_full_network":
        raise ContractError("baseline_confirmation.inherited_project must be deepseek_full_network")
    if value["elaboration_log_claimed"] is not False:
        raise ContractError("the inherited baseline must not fabricate a clean elaboration log")
    uri = _nonempty_string(value["decision_uri"], "baseline_confirmation.decision_uri")
    digest = _require_sha256(value["decision_sha256"], "baseline_confirmation.decision_sha256")
    return uri, digest


def _validate_architecture(value: Any, contract: dict[str, Any]) -> None:
    if not isinstance(value, dict):
        raise ContractError("architecture must be an object")
    required = {
        "target_family",
        "slice_count",
        "topology_id",
        "specialized_array",
        "general_array",
        "instruction_mask_bits",
        "dram",
    }
    _require_keys(value, required, "architecture")
    target = contract["target"]
    expected_scalars = {
        "target_family": TARGET_FAMILY,
        "slice_count": TARGET_SLICE_COUNT,
        "topology_id": TARGET_TOPOLOGY_ID,
        "instruction_mask_bits": TARGET_SLICE_COUNT,
    }
    for field, expected in expected_scalars.items():
        if value[field] != expected:
            raise ContractError(f"architecture.{field} must be {expected!r}")
    for field, target_field in (("specialized_array", "specialized"), ("general_array", "general")):
        shape = value[field]
        if not isinstance(shape, dict):
            raise ContractError(f"architecture.{field} must be an object")
        _require_keys(shape, {"rows", "cols"}, f"architecture.{field}")
        expected = target["arrays"][target_field]
        if (shape["rows"], shape["cols"]) != (expected["rows"], expected["cols"]):
            raise ContractError(f"architecture.{field} must match architecture contract")
    dram = value["dram"]
    if not isinstance(dram, dict):
        raise ContractError("architecture.dram must be an object")
    _require_keys(dram, set(TARGET_DRAM), "architecture.dram")
    for field, expected in TARGET_DRAM.items():
        if dram[field] != expected or contract["candidate_memory"].get(field) != expected:
            raise ContractError(f"architecture.dram.{field} must match the RTL28 contract")


def _validate_operator_bindings(
    value: Any, network_profile: str, architecture: dict[str, Any]
) -> bool:
    if not isinstance(value, dict):
        raise ContractError("operator_bindings must be an object")
    _require_keys(value, REQUIRED_PROFILE_KEYS, "operator_bindings")
    expected = PROFILE_BINDINGS[network_profile]
    if value != expected:
        raise ContractError(f"operator_bindings do not match selected profile {network_profile}")
    known_layouts = architecture.get("candidate_layouts", {})
    for family, binding in value.items():
        layout_id = binding["layout_id"]
        record = known_layouts.get(layout_id)
        if not isinstance(record, dict):
            raise ContractError(f"operator_bindings.{family} references unknown layout {layout_id}")
        if (
            record.get("target_family") != TARGET_FAMILY
            or record.get("slice_count") != TARGET_SLICE_COUNT
            or record.get("operator_family") != family
            or record.get("status") != "approved"
            or record.get("current_gate_eligible") is not True
        ):
            raise ContractError(f"operator_bindings.{family} is not the approved RTL28 W4 layout")
    return True


def _validate_contract_layers(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        raise ContractError("contract_layers must be an object")
    _require_keys(value, set(EXPECTED_CONTRACT_LAYERS), "contract_layers")
    normalized: dict[str, dict[str, str]] = {}
    for name, expected in EXPECTED_CONTRACT_LAYERS.items():
        item = value[name]
        if not isinstance(item, dict):
            raise ContractError(f"contract_layers.{name} must be an object")
        _require_keys(item, {"contract_id", "path", "sha256"}, f"contract_layers.{name}")
        for field in ("contract_id", "path"):
            if _nonempty_string(item[field], f"contract_layers.{name}.{field}") != expected[field]:
                raise ContractError(f"contract_layers.{name}.{field} must be {expected[field]}")
        normalized[name] = {
            "contract_id": item["contract_id"],
            "path": item["path"],
            "sha256": _require_sha256(item["sha256"], f"contract_layers.{name}.sha256"),
        }
    return normalized


def _validate_evidence(value: Any) -> int:
    if not isinstance(value, list) or not value:
        raise ContractError("evidence must be a non-empty array")
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ContractError(f"evidence[{index}] must be an object")
        _require_keys(item, {"kind", "uri", "sha256"}, f"evidence[{index}]")
        _nonempty_string(item["kind"], f"evidence[{index}].kind")
        _nonempty_string(item["uri"], f"evidence[{index}].uri")
        _require_sha256(item["sha256"], f"evidence[{index}].sha256")
    return len(value)


def _validate_local_evidence(root: Path, entries: Any, location: str) -> None:
    if not isinstance(entries, list) or not entries:
        raise ContractError(f"{location} must be a non-empty array")
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise ContractError(f"{location}[{index}] must be an object")
        _require_keys(item, {"path", "sha256"}, f"{location}[{index}]")
        path = _safe_project_path(root, item["path"], f"{location}[{index}].path")
        digest = _require_sha256(item["sha256"], f"{location}[{index}].sha256")
        if not path.is_file() or sha256_file(path) != digest:
            raise ContractError(f"{location}[{index}] file/hash mismatch: {item['path']}")


def _validate_deepseek_baseline(value: Any, root: Path) -> None:
    if not isinstance(value, dict):
        raise ContractError("DeepSeek common baseline must be an object")
    _require_keys(
        value,
        {
            "schema_version",
            "contract_type",
            "contract_id",
            "status",
            "source",
            "execution_model",
            "physical_conventions",
            "w4_scope",
            "w5_exclusions",
            "evidence",
        },
        "DeepSeek common baseline",
    )
    if (
        value["schema_version"] != "0.1"
        or value["contract_type"] != "deepseek_rtl28_physical_baseline"
        or value["contract_id"] != EXPECTED_CONTRACT_LAYERS["common_baseline"]["contract_id"]
        or value["status"] != "approved_as_inherited_w4_baseline"
    ):
        raise ContractError("DeepSeek common baseline identity is invalid")
    source = value["source"]
    if source.get("repository") != TARGET_CONFIG_REPOSITORY or source.get("commit") != TARGET_CONFIG_COMMIT:
        raise ContractError("DeepSeek common baseline source is not the locked configuration repository")
    execution = value["execution_model"]
    exact_execution = {
        "slice_count": 28,
        "instruction_mask": "0b1111111111111111111111111111",
        "high_ring_count": 7,
        "high_ring_size": 4,
        "low_ring_size": 28,
        "deepseek_layer0_operator_count": 43,
        "deepseek_ring4_gemm_count": 7,
        "deepseek_remote_sum4_count": 1,
        "deepseek_remote_sum28_count": 3,
        "deepseek_local_gemm_count": 2,
    }
    for field, expected in exact_execution.items():
        if execution.get(field) != expected:
            raise ContractError(f"DeepSeek execution_model.{field} must be {expected!r}")
    conventions = value["physical_conventions"]
    if (
        conventions.get("address_unit") != "byte"
        or conventions.get("minimum_alignment_bytes") != 16
        or conventions.get("address_remapping_entry_count") != 26
        or conventions.get("physical_record_bits") != 128
    ):
        raise ContractError("DeepSeek physical conventions are incomplete")
    _validate_local_evidence(root, value["evidence"], "DeepSeek common baseline.evidence")


def _validate_resnet_delta(value: Any, root: Path) -> None:
    if not isinstance(value, dict):
        raise ContractError("ResNet W4 delta must be an object")
    required = {
        "schema_version",
        "contract_type",
        "contract_id",
        "status",
        "network_profile",
        "instruction_mask",
        "batch_group_sample_counts",
        "transition_policy",
        "selected_low28_families",
        "operator_bindings",
        "physical_objects",
        "approved_w4_claims",
        "deferred_to_w5",
        "evidence",
    }
    _require_keys(value, required, "ResNet W4 delta")
    if (
        value["schema_version"] != "0.1"
        or value["contract_type"] != "resnet50_rtl28_w4_physical_delta"
        or value["contract_id"] != EXPECTED_CONTRACT_LAYERS["resnet_delta"]["contract_id"]
        or value["status"] != "approved_for_w4_physical_layout"
    ):
        raise ContractError("ResNet W4 delta identity is invalid")
    if value["network_profile"] != DEEPSEEK_HYBRID28_PROFILE:
        raise ContractError("ResNet W4 delta profile is invalid")
    if value["instruction_mask"] != "0b1111111111111111111111111111":
        raise ContractError("ResNet W4 delta must use the full 28-bit mask")
    if value["batch_group_sample_counts"] != list(GROUP_SAMPLE_COUNTS):
        raise ContractError("ResNet W4 delta batch groups are invalid")
    if value["selected_low28_families"] != []:
        raise ContractError("current ResNet W4 delta must not select LOW-28")
    if value["operator_bindings"] != PROFILE_BINDINGS[DEEPSEEK_HYBRID28_PROFILE]:
        raise ContractError("ResNet W4 delta operator bindings are invalid")
    physical = value["physical_objects"]
    expected_objects = {"activation", "weight", "bias", "qparams", "psum", "output"}
    _require_keys(physical, expected_objects, "ResNet W4 delta.physical_objects")
    fields = {"owner", "axis_order", "alignment_bytes", "tail_rule", "address_unit"}
    for name, item in physical.items():
        if not isinstance(item, dict):
            raise ContractError(f"ResNet W4 delta.physical_objects.{name} must be an object")
        _require_keys(item, fields, f"ResNet W4 delta.physical_objects.{name}")
        if _positive_int(item["alignment_bytes"], f"ResNet W4 delta.physical_objects.{name}.alignment_bytes") != 16:
            raise ContractError("all ResNet W4 physical objects must be 16-byte aligned")
        for field in fields - {"alignment_bytes"}:
            _nonempty_string(item[field], f"ResNet W4 delta.physical_objects.{name}.{field}")
    _validate_local_evidence(root, value["evidence"], "ResNet W4 delta.evidence")


def validate_hardware_approval(value: dict[str, Any], architecture: dict[str, Any]) -> dict[str, Any]:
    required_root = {
        "schema_version",
        "contract_type",
        "status",
        "approval_scope",
        "approval_id",
        "authority",
        "target_version",
        "baseline_confirmation",
        "architecture",
        "network_profile",
        "operator_bindings",
        "contract_layers",
        "deferred_to_w5",
        "evidence",
    }
    _require_keys(value, required_root, "hardware approval")
    if value["schema_version"] != APPROVAL_SCHEMA_VERSION:
        raise ContractError(f"hardware approval schema_version must be {APPROVAL_SCHEMA_VERSION}")
    if value["contract_type"] != APPROVAL_CONTRACT_TYPE or value["status"] != "approved":
        raise ContractError("hardware approval identity/status is invalid")
    if value["approval_scope"] != APPROVAL_SCOPE:
        raise ContractError("hardware approval may approve only the W4 physical baseline scope")
    approval_id = _nonempty_string(value["approval_id"], "approval_id")
    authority_kind = _validate_authority(value["authority"])

    if architecture.get("schema_version") != TARGET_ARCHITECTURE_SCHEMA_VERSION:
        raise ContractError("hardware approval requires architecture schema_version 0.2")
    target = architecture.get("target")
    if not isinstance(target, dict) or (
        target.get("architecture_id") != TARGET_ARCHITECTURE_ID
        or target.get("target_family") != TARGET_FAMILY
        or target.get("slice_count") != TARGET_SLICE_COUNT
    ):
        raise ContractError("architecture contract is not the current RTL28 target")
    rtl_commit = _validate_target_version(value["target_version"], target)
    decision_uri, decision_sha256 = _validate_baseline_confirmation(value["baseline_confirmation"])
    _validate_architecture(value["architecture"], architecture)

    network_profile = value["network_profile"]
    if network_profile not in SUPPORTED_NETWORK_PROFILES:
        raise ContractError("network_profile must be the DeepSeek-compatible hybrid28 profile")
    layout_evidence_complete = _validate_operator_bindings(
        value["operator_bindings"], network_profile, architecture
    )
    contract_layers = _validate_contract_layers(value["contract_layers"])
    deferrals = value["deferred_to_w5"]
    if not isinstance(deferrals, list) or not REQUIRED_W5_DEFERRALS.issubset(deferrals):
        raise ContractError("deferred_to_w5 must preserve all unresolved numerical/runtime work")
    if any(not isinstance(item, str) or not item for item in deferrals):
        raise ContractError("deferred_to_w5 entries must be non-empty strings")
    evidence_count = _validate_evidence(value["evidence"])

    return {
        "valid": True,
        "approval_id": approval_id,
        "approval_scope": APPROVAL_SCOPE,
        "authority_kind": authority_kind,
        "target_family": TARGET_FAMILY,
        "slice_count": TARGET_SLICE_COUNT,
        "architecture_id": TARGET_ARCHITECTURE_ID,
        "network_profile": network_profile,
        "operator_bindings": dict(value["operator_bindings"]),
        "rtl_commit": rtl_commit,
        "isa_version": TARGET_ISA_VERSION,
        "register_map_version": TARGET_REGISTER_MAP_VERSION,
        "hardware_baseline_confirmed": True,
        "clean_elaboration_claimed": False,
        "layout_evidence_complete": layout_evidence_complete,
        "contract_layers": contract_layers,
        "decision_uri": decision_uri,
        "decision_sha256": decision_sha256,
        "evidence_count": evidence_count,
        "referenced_contracts_verified": False,
        "gate_authority_eligible": False,
    }


def validate_hardware_approval_file(path: Path, architecture_path: Path) -> dict[str, Any]:
    value = load_hardware_approval(path)
    architecture = json.loads(architecture_path.read_text(encoding="utf-8"))
    result = validate_hardware_approval(value, architecture)
    if result["authority_kind"] == "synthetic_fixture":
        return {**result, "path": str(path), "sha256": sha256_file(path)}

    root = architecture_path.resolve().parents[1]
    decision_path = _safe_project_path(root, result["decision_uri"], "baseline_confirmation.decision_uri")
    if not decision_path.is_file() or sha256_file(decision_path) != result["decision_sha256"]:
        raise ContractError("baseline confirmation decision file/hash mismatch")
    for name, reference in result["contract_layers"].items():
        contract_path = _safe_project_path(root, reference["path"], f"contract_layers.{name}.path")
        if not contract_path.is_file() or sha256_file(contract_path) != reference["sha256"]:
            raise ContractError(f"contract_layers.{name} file/hash mismatch")
        try:
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ContractError(f"contract_layers.{name} is invalid JSON") from error
        if name == "common_baseline":
            _validate_deepseek_baseline(payload, root)
        else:
            _validate_resnet_delta(payload, root)
    return {
        **result,
        "path": str(path),
        "sha256": sha256_file(path),
        "referenced_contracts_verified": True,
        "gate_authority_eligible": True,
    }
