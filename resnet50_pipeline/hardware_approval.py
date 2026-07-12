from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

from .errors import ContractError
from .hashing import sha256_file


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
    "batch": {
        "simple": "w4_batch_slice_candidate_v1",
        "view": "w4_zero_copy_view_candidate_v1",
        "conv": "w4_conv_batch16_candidate_v1",
        "maxpool": "w4_maxpool_batch16_candidate_v1",
        "add": "w4_qlinearadd_batch16_candidate_v1",
        "global_average_pool": "w4_globalavgpool_batch16_candidate_v1",
        "matmul": "w4_qlinearmatmul_batch16_candidate_v1",
    },
    "ring_channel": {
        "simple": "w4_batch_slice_candidate_v1",
        "view": "w4_zero_copy_view_candidate_v1",
        "conv": "w4_conv_ring16_candidate_v1",
        "maxpool": "w4_maxpool_channel16_candidate_v1",
        "add": "w4_qlinearadd_channel16_candidate_v1",
        "global_average_pool": "w4_globalavgpool_channel16_candidate_v1",
        "matmul": "w4_qlinearmatmul_ring16_candidate_v1",
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
    if value["schema_version"] != "0.1":
        raise ContractError("hardware approval schema_version must be 0.1")
    if value["contract_type"] != "hardware_approval" or value["status"] != "approved":
        raise ContractError("hardware approval must have contract_type=hardware_approval and status=approved")
    approval_id = _nonempty_string(value["approval_id"], "approval_id")

    authority = value["authority"]
    if not isinstance(authority, dict):
        raise ContractError("authority must be an object")
    _require_keys(authority, {"name", "organization", "approved_at"}, "authority")
    _nonempty_string(authority["name"], "authority.name")
    _nonempty_string(authority["organization"], "authority.organization")
    try:
        dt.date.fromisoformat(_nonempty_string(authority["approved_at"], "authority.approved_at"))
    except ValueError as error:
        raise ContractError("authority.approved_at must be an ISO date") from error

    version = value["target_version"]
    if not isinstance(version, dict):
        raise ContractError("target_version must be an object")
    _require_keys(version, {"rtl_commit", "isa_version", "register_map_version"}, "target_version")
    rtl_commit = _nonempty_string(version["rtl_commit"], "target_version.rtl_commit")
    if not re.fullmatch(r"[0-9a-f]{40}", rtl_commit):
        raise ContractError("target_version.rtl_commit must be a full lowercase Git hash")
    _nonempty_string(version["isa_version"], "target_version.isa_version")
    _nonempty_string(version["register_map_version"], "target_version.register_map_version")

    hardware = value["architecture"]
    if not isinstance(hardware, dict):
        raise ContractError("architecture must be an object")
    _require_keys(hardware, {"slice_count", "pe_array", "neighbor_transfer_count", "dram"}, "architecture")
    if _positive_int(hardware["slice_count"], "architecture.slice_count") != 16:
        raise ContractError("approved architecture must contain exactly 16 slices")
    pe_array = hardware["pe_array"]
    if not isinstance(pe_array, dict):
        raise ContractError("architecture.pe_array must be an object")
    _require_keys(pe_array, {"rows", "cols"}, "architecture.pe_array")
    _positive_int(pe_array["rows"], "architecture.pe_array.rows")
    _positive_int(pe_array["cols"], "architecture.pe_array.cols")
    neighbor_count = hardware["neighbor_transfer_count"]
    if not isinstance(neighbor_count, int) or isinstance(neighbor_count, bool) or neighbor_count < 0:
        raise ContractError("architecture.neighbor_transfer_count must be a non-negative integer")
    dram = hardware["dram"]
    if not isinstance(dram, dict):
        raise ContractError("architecture.dram must be an object")
    _require_keys(dram, {"bank_count", "row_count", "col_count", "subword_bytes", "address_unit", "address_order"}, "architecture.dram")
    for field in ("bank_count", "row_count", "col_count", "subword_bytes"):
        _positive_int(dram[field], f"architecture.dram.{field}")
    _nonempty_string(dram["address_unit"], "architecture.dram.address_unit")
    _nonempty_string(dram["address_order"], "architecture.dram.address_order")

    network_profile = value["network_profile"]
    if network_profile not in {"batch", "ring_channel", "mixed"}:
        raise ContractError("network_profile must be batch, ring_channel or mixed")
    operator_layouts = value["operator_layouts"]
    if not isinstance(operator_layouts, dict):
        raise ContractError("operator_layouts must be an object")
    _require_keys(operator_layouts, REQUIRED_PROFILE_KEYS, "operator_layouts")
    known_layouts = set(architecture["candidate_layouts"])
    for family in REQUIRED_PROFILE_KEYS:
        layout_id = _nonempty_string(operator_layouts[family], f"operator_layouts.{family}")
        if layout_id not in known_layouts:
            raise ContractError(f"operator_layouts.{family} references unknown layout {layout_id}")
    if network_profile in PROFILE_LAYOUTS and operator_layouts != PROFILE_LAYOUTS[network_profile]:
        raise ContractError(f"operator_layouts do not match the selected {network_profile} profile")

    physical_objects = value["physical_objects"]
    if not isinstance(physical_objects, dict):
        raise ContractError("physical_objects must be an object")
    _require_keys(physical_objects, REQUIRED_PHYSICAL_OBJECTS, "physical_objects")
    for name in REQUIRED_PHYSICAL_OBJECTS:
        spec = physical_objects[name]
        if not isinstance(spec, dict):
            raise ContractError(f"physical_objects.{name} must be an object")
        _require_keys(spec, {"owner", "axis_order", "alignment_bytes", "tail_rule", "address_unit"}, f"physical_objects.{name}")
        for field in ("owner", "axis_order", "tail_rule", "address_unit"):
            _nonempty_string(spec[field], f"physical_objects.{name}.{field}")
        _positive_int(spec["alignment_bytes"], f"physical_objects.{name}.alignment_bytes")

    numeric = value["numeric_semantics"]
    if not isinstance(numeric, dict):
        raise ContractError("numeric_semantics must be an object")
    _require_keys(numeric, {"accumulator_bits", "overflow", "requant", "qparams_transport", "psum_lifecycle"}, "numeric_semantics")
    if _positive_int(numeric["accumulator_bits"], "numeric_semantics.accumulator_bits") < 32:
        raise ContractError("numeric_semantics.accumulator_bits must be at least 32")
    if numeric["overflow"] not in {"wrap", "saturate", "error"}:
        raise ContractError("numeric_semantics.overflow is unsupported")
    requant = numeric["requant"]
    if not isinstance(requant, dict):
        raise ContractError("numeric_semantics.requant must be an object")
    _require_keys(requant, {"multiplier_encoding", "rounding", "saturation", "zero_point_stage"}, "numeric_semantics.requant")
    if requant["rounding"] != "nearest_even" or requant["saturation"] != "uint8":
        raise ContractError("approved requant must reproduce nearest-even uint8 model semantics")
    for field in ("multiplier_encoding", "zero_point_stage"):
        _nonempty_string(requant[field], f"numeric_semantics.requant.{field}")
    _nonempty_string(numeric["qparams_transport"], "numeric_semantics.qparams_transport")
    _nonempty_string(numeric["psum_lifecycle"], "numeric_semantics.psum_lifecycle")

    isa = value["isa"]
    if not isinstance(isa, dict):
        raise ContractError("isa must be an object")
    _require_keys(isa, {"opcodes", "field_widths", "instruction_mask_semantics"}, "isa")
    opcodes = isa["opcodes"]
    if not isinstance(opcodes, dict) or not opcodes:
        raise ContractError("isa.opcodes must be a non-empty object")
    if any(
        not isinstance(item, int) or isinstance(item, bool) or item < 0
        for item in opcodes.values()
    ):
        raise ContractError("isa.opcodes values must be non-negative integers")
    field_widths = isa["field_widths"]
    if not isinstance(field_widths, dict) or not field_widths:
        raise ContractError("isa.field_widths must be a non-empty object")
    for name, width in field_widths.items():
        _positive_int(width, f"isa.field_widths.{name}")
    _nonempty_string(isa["instruction_mask_semantics"], "isa.instruction_mask_semantics")

    protocol = value["runtime_protocol"]
    if not isinstance(protocol, dict):
        raise ContractError("runtime_protocol must be an object")
    protocol_fields = {"load_config", "load_data", "start", "wait", "status", "error", "dump"}
    _require_keys(protocol, protocol_fields, "runtime_protocol")
    for field in protocol_fields:
        _nonempty_string(protocol[field], f"runtime_protocol.{field}")

    evidence = value["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise ContractError("evidence must be a non-empty array")
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            raise ContractError(f"evidence[{index}] must be an object")
        _require_keys(item, {"uri", "sha256"}, f"evidence[{index}]")
        _nonempty_string(item["uri"], f"evidence[{index}].uri")
        digest = _nonempty_string(item["sha256"], f"evidence[{index}].sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ContractError(f"evidence[{index}].sha256 must be lowercase SHA-256")

    return {
        "valid": True,
        "approval_id": approval_id,
        "network_profile": network_profile,
        "operator_layouts": dict(operator_layouts),
        "rtl_commit": rtl_commit,
        "isa_version": version["isa_version"],
        "register_map_version": version["register_map_version"],
        "physical_object_count": len(REQUIRED_PHYSICAL_OBJECTS),
        "evidence_count": len(evidence),
    }


def validate_hardware_approval_file(
    path: Path, architecture_path: Path
) -> dict[str, Any]:
    value = load_hardware_approval(path)
    architecture = json.loads(architecture_path.read_text(encoding="utf-8"))
    result = validate_hardware_approval(value, architecture)
    return {
        **result,
        "path": str(path),
        "sha256": sha256_file(path),
    }
