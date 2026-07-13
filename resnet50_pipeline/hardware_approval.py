from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

from .errors import ContractError
from .hashing import sha256_file
from .profile28 import (
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
    SUPPORTED_PROFILES,
)


TARGET_FAMILY = "rtl28"
TARGET_SLICE_COUNT = 28
TARGET_RTL_REPOSITORY = "https://github.com/xlsjdjdk/Trassic2.0_RTL"
TARGET_RTL_COMMIT = "e3bdebba95dec36ee8eba43caa92a326a88392cd"
TARGET_ARCHITECTURE_ID = "trassic2_rtl28_candidate_v1"
TARGET_ARCHITECTURE_SCHEMA_VERSION = "0.2"
TARGET_TOPOLOGY_ID = "rtl28_high7x4_low28_e3bdebba"
TARGET_TOP_MODULE = "NDP_Top_new"
TARGET_FILELIST = "code/NDP_rtl/filelists/NDP_Top_filelist.f"
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
REQUIRED_PHYSICAL_OBJECTS = {
    "activation",
    "weight",
    "bias",
    "qparams",
    "psum",
    "output",
}
PROFILE_LAYOUTS = {
    GROUP4X7_BATCH_CHANNEL28_PROFILE: {
        "simple": "w4_simple_group4x7_28_candidate_v1",
        "view": "w4_zero_copy_view_group4x7_28_candidate_v1",
        "conv": "w4_conv_group4x7_28_candidate_v1",
        "maxpool": "w4_maxpool_group4x7_28_candidate_v1",
        "add": "w4_qlinearadd_group4x7_28_candidate_v1",
        "global_average_pool": "w4_globalavgpool_group4x7_28_candidate_v1",
        "matmul": "w4_qlinearmatmul_group4x7_28_candidate_v1",
    },
    GLOBAL_RING28_PROFILE: {
        "simple": "w4_simple_global_ring28_candidate_v1",
        "view": "w4_zero_copy_view_global_ring28_candidate_v1",
        "conv": "w4_conv_global_ring28_candidate_v1",
        "maxpool": "w4_maxpool_global_ring28_candidate_v1",
        "add": "w4_qlinearadd_global_ring28_candidate_v1",
        "global_average_pool": "w4_globalavgpool_global_ring28_candidate_v1",
        "matmul": "w4_qlinearmatmul_global_ring28_candidate_v1",
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


def _validate_target_version(value: dict[str, Any], target: dict[str, Any]) -> str:
    required = {
        "repository",
        "rtl_commit",
        "top_module",
        "filelist",
        "architecture_id",
        "architecture_schema_version",
        "isa_version",
        "register_map_version",
    }
    _require_keys(value, required, "target_version")
    rtl = target["rtl"]
    exact = {
        "repository": TARGET_RTL_REPOSITORY,
        "top_module": TARGET_TOP_MODULE,
        "filelist": TARGET_FILELIST,
        "architecture_id": TARGET_ARCHITECTURE_ID,
        "architecture_schema_version": TARGET_ARCHITECTURE_SCHEMA_VERSION,
    }
    for field, expected in exact.items():
        actual = _nonempty_string(value[field], f"target_version.{field}")
        if actual != expected:
            raise ContractError(
                f"target_version.{field} must match architecture contract {expected}"
            )
    rtl_commit = _nonempty_string(value["rtl_commit"], "target_version.rtl_commit")
    if not re.fullmatch(r"[0-9a-f]{40}", rtl_commit):
        raise ContractError("target_version.rtl_commit must be a full lowercase Git hash")
    if rtl_commit != rtl["commit"]:
        raise ContractError(
            f"target_version.rtl_commit must match architecture contract {rtl['commit']}"
        )
    _nonempty_string(value["isa_version"], "target_version.isa_version")
    _nonempty_string(
        value["register_map_version"], "target_version.register_map_version"
    )
    return rtl_commit


def _validate_clean_elaboration(value: Any) -> None:
    if not isinstance(value, dict):
        raise ContractError("clean_elaboration must be an object")
    _require_keys(
        value,
        {"status", "tool", "tool_version", "log_uri", "log_sha256"},
        "clean_elaboration",
    )
    if value["status"] != "approved":
        raise ContractError("clean_elaboration.status must be approved")
    for field in ("tool", "tool_version", "log_uri"):
        _nonempty_string(value[field], f"clean_elaboration.{field}")
    _require_sha256(value["log_sha256"], "clean_elaboration.log_sha256")


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
    exact_scalars = {
        "target_family": target["target_family"],
        "slice_count": target["slice_count"],
        "topology_id": target["topology"]["topology_id"],
        "instruction_mask_bits": target["instruction_mask_bits"],
    }
    for field, expected in exact_scalars.items():
        if value[field] != expected:
            raise ContractError(
                f"architecture.{field} must match architecture contract {expected!r}"
            )
    for field, target_field in (
        ("specialized_array", "specialized"),
        ("general_array", "general"),
    ):
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
    dram_fields = {
        "bank_count",
        "row_count",
        "col_count",
        "subword_bytes",
        "address_unit",
        "address_order",
    }
    _require_keys(dram, dram_fields, "architecture.dram")
    candidate_memory = contract["candidate_memory"]
    for field in dram_fields:
        if candidate_memory.get(field) != TARGET_DRAM[field]:
            raise ContractError(
                f"architecture contract candidate_memory.{field} is not the RTL28 candidate"
            )
        if dram[field] != TARGET_DRAM[field]:
            raise ContractError(
                f"architecture.dram.{field} must match the RTL28 candidate"
            )


def _validate_operator_layouts(
    value: Any, network_profile: str, architecture: dict[str, Any]
) -> bool:
    if not isinstance(value, dict):
        raise ContractError("operator_layouts must be an object")
    _require_keys(value, REQUIRED_PROFILE_KEYS, "operator_layouts")
    if value != PROFILE_LAYOUTS[network_profile]:
        raise ContractError(
            f"operator_layouts do not match selected profile {network_profile}"
        )
    known_layouts = {
        **architecture.get("planned_layouts", {}),
        **architecture.get("candidate_layouts", {}),
    }
    current_gate_eligible = True
    for family, layout_id in value.items():
        if layout_id not in known_layouts:
            raise ContractError(
                f"operator_layouts.{family} references unknown current layout {layout_id}"
            )
        record = known_layouts[layout_id]
        if (
            record.get("target_family") != TARGET_FAMILY
            or record.get("slice_count") != TARGET_SLICE_COUNT
            or record.get("operator_family") != family
        ):
            raise ContractError(
                f"operator_layouts.{family} does not describe the current RTL28 family"
            )
        current_gate_eligible &= bool(record.get("current_gate_eligible", False))
    return current_gate_eligible


def _validate_physical_objects(value: Any) -> None:
    if not isinstance(value, dict):
        raise ContractError("physical_objects must be an object")
    _require_keys(value, REQUIRED_PHYSICAL_OBJECTS, "physical_objects")
    required = {"owner", "axis_order", "alignment_bytes", "tail_rule", "address_unit"}
    for name in REQUIRED_PHYSICAL_OBJECTS:
        spec = value[name]
        if not isinstance(spec, dict):
            raise ContractError(f"physical_objects.{name} must be an object")
        _require_keys(spec, required, f"physical_objects.{name}")
        for field in ("owner", "axis_order", "tail_rule", "address_unit"):
            _nonempty_string(spec[field], f"physical_objects.{name}.{field}")
        _positive_int(spec["alignment_bytes"], f"physical_objects.{name}.alignment_bytes")


def _validate_numeric_semantics(value: Any) -> None:
    if not isinstance(value, dict):
        raise ContractError("numeric_semantics must be an object")
    required = {
        "accumulator_bits",
        "overflow",
        "requant",
        "qparams_transport",
        "psum_lifecycle",
    }
    _require_keys(value, required, "numeric_semantics")
    if _positive_int(value["accumulator_bits"], "numeric_semantics.accumulator_bits") < 32:
        raise ContractError("numeric_semantics.accumulator_bits must be at least 32")
    if value["overflow"] not in {"wrap", "saturate", "error"}:
        raise ContractError("numeric_semantics.overflow is unsupported")
    requant = value["requant"]
    if not isinstance(requant, dict):
        raise ContractError("numeric_semantics.requant must be an object")
    _require_keys(
        requant,
        {"multiplier_encoding", "rounding", "saturation", "zero_point_stage"},
        "numeric_semantics.requant",
    )
    if requant["rounding"] != "nearest_even" or requant["saturation"] != "uint8":
        raise ContractError(
            "approved requant must reproduce nearest-even uint8 model semantics"
        )
    for field in ("multiplier_encoding", "zero_point_stage"):
        _nonempty_string(requant[field], f"numeric_semantics.requant.{field}")
    _nonempty_string(value["qparams_transport"], "numeric_semantics.qparams_transport")
    _nonempty_string(value["psum_lifecycle"], "numeric_semantics.psum_lifecycle")


def _validate_isa(value: Any, instruction_mask_bits: int) -> None:
    if not isinstance(value, dict):
        raise ContractError("isa must be an object")
    _require_keys(value, {"opcodes", "field_widths", "instruction_mask_semantics"}, "isa")
    opcodes = value["opcodes"]
    if not isinstance(opcodes, dict) or not opcodes:
        raise ContractError("isa.opcodes must be a non-empty object")
    if any(not isinstance(item, int) or isinstance(item, bool) or item < 0 for item in opcodes.values()):
        raise ContractError("isa.opcodes values must be non-negative integers")
    widths = value["field_widths"]
    if not isinstance(widths, dict) or not widths:
        raise ContractError("isa.field_widths must be a non-empty object")
    for name, width in widths.items():
        _positive_int(width, f"isa.field_widths.{name}")
    if widths.get("slice_mask") != instruction_mask_bits:
        raise ContractError(
            f"isa.field_widths.slice_mask must equal {instruction_mask_bits}"
        )
    _nonempty_string(value["instruction_mask_semantics"], "isa.instruction_mask_semantics")


def _validate_runtime_protocol(value: Any) -> None:
    if not isinstance(value, dict):
        raise ContractError("runtime_protocol must be an object")
    fields = {"load_config", "load_data", "start", "wait", "status", "error", "dump"}
    _require_keys(value, fields, "runtime_protocol")
    for field in fields:
        _nonempty_string(value[field], f"runtime_protocol.{field}")


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


def validate_hardware_approval(
    value: dict[str, Any], architecture: dict[str, Any]
) -> dict[str, Any]:
    required_root = {
        "schema_version",
        "contract_type",
        "status",
        "approval_id",
        "authority",
        "target_version",
        "clean_elaboration",
        "architecture",
        "network_profile",
        "operator_layouts",
        "physical_objects",
        "numeric_semantics",
        "isa",
        "runtime_protocol",
        "evidence",
    }
    _require_keys(value, required_root, "hardware approval")
    if value["schema_version"] != "0.2":
        raise ContractError("hardware approval schema_version must be 0.2")
    if value["contract_type"] != "hardware_approval" or value["status"] != "approved":
        raise ContractError(
            "hardware approval must have contract_type=hardware_approval and status=approved"
        )
    approval_id = _nonempty_string(value["approval_id"], "approval_id")

    if architecture.get("schema_version") != TARGET_ARCHITECTURE_SCHEMA_VERSION:
        raise ContractError("hardware approval requires architecture schema_version 0.2")
    target = architecture.get("target")
    if not isinstance(target, dict):
        raise ContractError("architecture contract is missing current target")
    if (
        target.get("architecture_id") != TARGET_ARCHITECTURE_ID
        or target.get("target_family") != TARGET_FAMILY
        or target.get("slice_count") != TARGET_SLICE_COUNT
    ):
        raise ContractError("architecture contract is not the current RTL28 target")

    authority = value["authority"]
    if not isinstance(authority, dict):
        raise ContractError("authority must be an object")
    _require_keys(authority, {"name", "organization", "approved_at"}, "authority")
    _nonempty_string(authority["name"], "authority.name")
    _nonempty_string(authority["organization"], "authority.organization")
    try:
        dt.date.fromisoformat(
            _nonempty_string(authority["approved_at"], "authority.approved_at")
        )
    except ValueError as error:
        raise ContractError("authority.approved_at must be an ISO date") from error

    version = value["target_version"]
    if not isinstance(version, dict):
        raise ContractError("target_version must be an object")
    rtl_commit = _validate_target_version(version, target)
    _validate_clean_elaboration(value["clean_elaboration"])
    _validate_architecture(value["architecture"], architecture)

    network_profile = value["network_profile"]
    if network_profile not in SUPPORTED_PROFILES:
        supported = ", ".join(sorted(SUPPORTED_PROFILES))
        raise ContractError(
            f"network_profile must be an exact profile28 ID: {supported}"
        )
    layout_evidence_complete = _validate_operator_layouts(
        value["operator_layouts"], network_profile, architecture
    )
    _validate_physical_objects(value["physical_objects"])
    _validate_numeric_semantics(value["numeric_semantics"])
    _validate_isa(value["isa"], target["instruction_mask_bits"])
    _validate_runtime_protocol(value["runtime_protocol"])
    evidence_count = _validate_evidence(value["evidence"])

    return {
        "valid": True,
        "approval_id": approval_id,
        "target_family": TARGET_FAMILY,
        "slice_count": TARGET_SLICE_COUNT,
        "architecture_id": TARGET_ARCHITECTURE_ID,
        "network_profile": network_profile,
        "operator_layouts": dict(value["operator_layouts"]),
        "rtl_commit": rtl_commit,
        "isa_version": version["isa_version"],
        "register_map_version": version["register_map_version"],
        "clean_elaboration_approved": True,
        "layout_evidence_complete": layout_evidence_complete,
        "physical_object_count": len(REQUIRED_PHYSICAL_OBJECTS),
        "evidence_count": evidence_count,
    }


def validate_hardware_approval_file(path: Path, architecture_path: Path) -> dict[str, Any]:
    value = load_hardware_approval(path)
    architecture = json.loads(architecture_path.read_text(encoding="utf-8"))
    result = validate_hardware_approval(value, architecture)
    return {**result, "path": str(path), "sha256": sha256_file(path)}
