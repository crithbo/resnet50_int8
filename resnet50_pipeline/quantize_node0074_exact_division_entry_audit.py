"""Validate the fail-closed exact-binary32-division audit for node0074.

This module creates no hardware target or server package.  It binds a real
typed/W3 node0074 instance to the current native entry inventory, proves a
same-scale reciprocal/MUL counterexample, and keeps all node0074-owned
Flatten endpoint fields unresolved.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


SCHEMA = "resnet50-quantize-node0074-exact-division-entry-audit-v1"
REPORT_SCHEMA = "resnet50-quantize-node0074-exact-division-entry-audit-report-v1"


class ExactDivisionEntryAuditError(ValueError):
    """Raised when the fail-closed capability audit no longer holds."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ExactDivisionEntryAuditError(f"JSON root must be an object: {path}")
    return value


def _f32_from_bits(bits: str) -> np.float32:
    return np.asarray(int(bits, 16), dtype=np.uint32).view(np.float32)


def _f32_bits(value: np.float32) -> str:
    bits = np.asarray(value, dtype=np.float32).view(np.uint32).item()
    return f"0x{int(bits):08x}"


def _section_content_sha256(section: dict[str, Any]) -> str:
    content = dict(section)
    content.pop("owner_section_content_sha256", None)
    serialized = json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _quantize(scaled: np.ndarray | np.float32) -> np.ndarray:
    return np.clip(np.rint(scaled), 0, 255).astype(np.uint8)


def _validate_identities(
    project_root: Path, sources: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    validated = []
    for source in sources:
        path = project_root / source["path"]
        if not path.is_file():
            raise ExactDivisionEntryAuditError(f"missing locked source: {source['path']}")
        actual = _sha256(path)
        if actual != source["sha256"]:
            raise ExactDivisionEntryAuditError(
                f"locked source changed: {source['path']} "
                f"expected={source['sha256']} actual={actual}"
            )
        validated.append(
            {
                "path": source["path"],
                "sha256": actual,
                "gate": "current_match_fail_closed",
            }
        )
    return validated


def _validate_mutable_receipts(
    project_root: Path, receipts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result = []
    for receipt in receipts:
        path = project_root / receipt["path"]
        current = _sha256(path) if path.is_file() else None
        result.append(
            {
                "path": receipt["path"],
                "recorded_sha256": receipt["sha256"],
                "current_sha256": current,
                "current_match": current == receipt["sha256"],
                "gate": "historical_provenance_only",
            }
        )
    return result


def _validate_reuse(
    project_root: Path, reused: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    validated = []
    for item in reused:
        path = project_root / item["path"]
        if _sha256(path) != item["sha256"]:
            raise ExactDivisionEntryAuditError(
                f"approved reuse identity changed: {item['path']}"
            )
        if item["class"] != "APPROVED_EQUIVALENT" or item["retested"] is not False:
            raise ExactDivisionEntryAuditError(
                f"reuse boundary changed: {item['path']}"
            )
        validated.append(dict(item))
    return validated


def _validate_native_matrix(contract: dict[str, Any]) -> dict[str, Any]:
    rows = {row["entry"]: row for row in contract["native_entry_matrix"]}
    required = {
        "direct_binary32_division",
        "prefill_sum_rec_fp32MN_fp32MN",
        "decode_sum_rec_fp32N_fp32N",
        "REC_then_MUL",
        "quant_from_buffer_int32MN_uint8MN",
    }
    if set(rows) != required:
        raise ExactDivisionEntryAuditError("native entry matrix changed")
    direct = rows["direct_binary32_division"]
    if any(direct[field] is not None for field in ("configuration", "opcode", "typed_handler", "mapper")):
        raise ExactDivisionEntryAuditError("a direct division entry requires a new audit")
    if direct["verdict"] != "ABSENT":
        raise ExactDivisionEntryAuditError("direct division verdict changed")
    if rows["REC_then_MUL"]["verdict"] != "CONTRADICTED":
        raise ExactDivisionEntryAuditError("REC/MUL must remain contradicted")
    return {
        "entry_count": len(rows),
        "direct_binary32_division": "ABSENT",
        "nearest_native_entries": [
            "prefill_sum_rec_fp32MN_fp32MN",
            "decode_sum_rec_fp32N_fp32N",
            "REC_then_MUL",
            "quant_from_buffer_int32MN_uint8MN",
        ],
        "complete_equivalent_route": False,
        "passed": True,
    }


def _validate_counterexample(contract: dict[str, Any]) -> dict[str, Any]:
    expected = contract["same_scale_sequential_reciprocal_counterexample"]
    x = _f32_from_bits(expected["x_bits"])
    scale = _f32_from_bits(expected["scale_bits"])
    reciprocal = np.float32(np.float32(1.0) / scale)
    divided = np.float32(x / scale)
    multiplied = np.float32(x * reciprocal)
    divide_q = int(_quantize(divided))
    multiply_q = int(_quantize(multiplied))
    actual = {
        "x_bits": _f32_bits(x),
        "scale_bits": _f32_bits(scale),
        "reciprocal_bits": _f32_bits(reciprocal),
        "binary32_divide_bits": _f32_bits(divided),
        "divide_then_rne_uint8": divide_q,
        "binary32_reciprocal_mul_bits": _f32_bits(multiplied),
        "reciprocal_mul_then_rne_uint8": multiply_q,
    }
    for field, value in actual.items():
        if expected[field] != value:
            raise ExactDivisionEntryAuditError(
                f"same-scale counterexample changed at {field}: "
                f"expected={expected[field]!r} actual={value!r}"
            )
    if divide_q != 159 or multiply_q != 158:
        raise ExactDivisionEntryAuditError("counterexample no longer separates outputs")
    return {**actual, "separation": divide_q - multiply_q, "passed": True}


def _validate_w3(contract: dict[str, Any], project_root: Path) -> dict[str, Any]:
    node = contract["node"]
    x_path = project_root / "artifacts/w3/golden_batch16/tensors/tensor-9b1363d3baf474c8.npy"
    y_path = project_root / "artifacts/w3/golden_batch16/tensors/tensor-6fbd5707d5f08110.npy"
    x = np.load(x_path).astype(np.float32, copy=False)
    golden = np.load(y_path)
    if list(x.shape) != node["input"]["shape"] or x.dtype != np.float32:
        raise ExactDivisionEntryAuditError("formal node0074 input identity changed")
    if list(golden.shape) != node["output"]["shape"] or golden.dtype != np.uint8:
        raise ExactDivisionEntryAuditError("formal node0074 output identity changed")
    scale = _f32_from_bits(node["qparams"]["scale_bits"])
    reciprocal = np.float32(np.float32(1.0) / scale)
    divided = np.divide(x, scale, dtype=np.float32)
    multiplied = np.multiply(x, reciprocal, dtype=np.float32)
    divide_q = _quantize(divided)
    multiply_q = _quantize(multiplied)
    observation = {
        "input_elements": int(x.size),
        "exact_division_matches_formal_output": bool(np.array_equal(divide_q, golden)),
        "exact_division_vs_sequential_reciprocal_mul_scaled_bit_mismatches": int(
            np.count_nonzero(divided.view(np.uint32) != multiplied.view(np.uint32))
        ),
        "exact_division_vs_sequential_reciprocal_mul_final_uint8_mismatches": int(
            np.count_nonzero(divide_q != multiply_q)
        ),
    }
    expected = contract["frozen_w3_route_observation"]
    for field, value in observation.items():
        if expected[field] != value:
            raise ExactDivisionEntryAuditError(
                f"frozen W3 route observation changed at {field}: "
                f"expected={expected[field]!r} actual={value!r}"
            )
    return {
        **observation,
        "authorizes_target": False,
        "reason": expected["interpretation"],
        "passed": True,
    }


def _validate_endpoint(contract: dict[str, Any]) -> dict[str, Any]:
    endpoint = contract["endpoint_binding"]
    if endpoint["blocked_by"] != "B_QUANT_NODE0074_EXACT_DIVISION":
        raise ExactDivisionEntryAuditError("endpoint must remain behind exact division")
    if endpoint["required_read_elements"] * 4 != endpoint["required_read_bytes"]:
        raise ExactDivisionEntryAuditError("endpoint byte coverage equation changed")
    owned = endpoint["node0074_owned_fields"]
    expected_fields = {
        "final_storage_identity",
        "final_producer_base",
        "final_view_offset",
        "final_consumer_base",
        "final_read_coverage",
        "final_accepted_lifetime",
    }
    if set(owned) != expected_fields or any(value is not None for value in owned.values()):
        raise ExactDivisionEntryAuditError(
            "node0074 endpoint fields must remain unresolved, with no provisional address"
        )
    if endpoint["provisional_address_allowed"] is not False:
        raise ExactDivisionEntryAuditError("provisional endpoint address is forbidden")
    if endpoint["target_endpoint_claimed"] is not False:
        raise ExactDivisionEntryAuditError("blocked endpoint cannot be claimed")
    return {
        "chain": endpoint["chain"],
        "required_read_bytes": endpoint["required_read_bytes"],
        "node0074_owned_fields": owned,
        "all_owned_fields_null": True,
        "provisional_address_allowed": False,
        "target_endpoint_claimed": False,
        "passed": True,
    }


def _validate_canonical_endpoint(
    contract: dict[str, Any], contract_path: Path, project_root: Path
) -> dict[str, Any]:
    path = (
        project_root
        / "contracts/operator_config/resnet50_node0072_node0074_shared_endpoint_v1.json"
    )
    canonical = _load_json(path)
    sections = canonical["owner_sections"]
    if "Flatten_View" in sections:
        raise ExactDivisionEntryAuditError(
            "Flatten projection must not become a second canonical fact section here"
        )
    dequant = sections["DequantizeLinear"]
    dequant_hash = _section_content_sha256(dequant)
    if (
        dequant["owner_section_content_sha256"]
        != "e372f7b0fa434845a8199830c3c46a9467fc71d5687fa103750a86408191b371"
        or dequant_hash != dequant["owner_section_content_sha256"]
    ):
        raise ExactDivisionEntryAuditError(
            "canonical DequantizeLinear owner section changed"
        )
    quantize = sections["QuantizeLinear"]
    quantize_hash = _section_content_sha256(quantize)
    if quantize_hash != quantize["owner_section_content_sha256"]:
        raise ExactDivisionEntryAuditError(
            "canonical QuantizeLinear owner section content hash changed"
        )
    if quantize["audit_contract"]["sha256"] != _sha256(contract_path):
        raise ExactDivisionEntryAuditError(
            "canonical QuantizeLinear section is not bound to this audit contract"
        )
    if quantize["consumer_owned_endpoint_fields"] != contract["endpoint_binding"][
        "node0074_owned_fields"
    ]:
        raise ExactDivisionEntryAuditError(
            "canonical consumer-owned endpoint fields diverge from the audit"
        )
    if (
        quantize["numeric_capability"]["blocker_id"]
        != "B_QUANT_NODE0074_EXACT_DIVISION"
        or quantize["endpoint_claim"]["provisional_address_allowed"] is not False
        or any(quantize["generated_outputs"].values())
    ):
        raise ExactDivisionEntryAuditError(
            "canonical QuantizeLinear fail-closed boundary changed"
        )
    return {
        "path": path.relative_to(project_root).as_posix(),
        "sha256": _sha256(path),
        "dequant_owner_section_content_sha256": dequant_hash,
        "quantize_owner_section_content_sha256": quantize_hash,
        "quantize_only_update": True,
        "consumer_owned_fields_all_null": True,
        "integrated_endpoint_closed": False,
        "passed": True,
    }


def validate_contract(contract_path: Path, project_root: Path) -> dict[str, Any]:
    contract = _load_json(contract_path)
    if contract.get("schema") != SCHEMA:
        raise ExactDivisionEntryAuditError(
            f"unexpected contract schema: {contract.get('schema')}"
        )
    expected_outputs = {
        "target_json": False,
        "mapping": False,
        "bitstream": False,
        "execplan": False,
        "sca": False,
        "server_package": False,
        "candidate_release": False,
    }
    if contract["outputs"] != expected_outputs:
        raise ExactDivisionEntryAuditError("forbidden output boundary changed")
    accounting = contract["analysis_accounting"]
    if (
        accounting["accepted_numeric_analysis_repeated"] is not False
        or accounting["node0004_analysis_repeated"] is not False
        or accounting["accepted_primitive_retested"] is not False
        or accounting["reuse_assets_consumed"] is not True
    ):
        raise ExactDivisionEntryAuditError("analysis/reuse accounting changed")
    source_identities = _validate_identities(
        project_root,
        contract["semantic_source_identities"] + contract["native_config_identities"],
    )
    reused = _validate_reuse(project_root, contract["reused_evidence"])
    receipts = _validate_mutable_receipts(project_root, contract["mutable_read_receipt"])
    native = _validate_native_matrix(contract)
    counterexample = _validate_counterexample(contract)
    w3 = _validate_w3(contract, project_root)
    endpoint = _validate_endpoint(contract)
    canonical_endpoint = _validate_canonical_endpoint(
        contract, contract_path, project_root
    )
    blocker = contract["blockers"]["instance"]
    if (
        blocker["id"] != "B_QUANT_NODE0074_EXACT_DIVISION"
        or blocker["status"] != "OPEN_NO_DIRECT_OR_EQUIVALENT_ENTRY"
    ):
        raise ExactDivisionEntryAuditError("instance first blocker changed")
    return {
        "schema": REPORT_SCHEMA,
        "status": contract["status"],
        "claim_boundary": contract["claim_boundary"],
        "contract": {
            "path": contract_path.relative_to(project_root).as_posix(),
            "sha256": _sha256(contract_path),
        },
        "semantic_source_identities": source_identities,
        "mutable_read_receipts": receipts,
        "reused_evidence": reused,
        "native_entry_audit": native,
        "same_scale_sequential_reciprocal_counterexample": counterexample,
        "frozen_w3_route_observation": w3,
        "endpoint_binding": endpoint,
        "canonical_endpoint_integration": canonical_endpoint,
        "first_unavoidable_break": blocker,
        "analysis_accounting": accounting,
        "generated_outputs": contract["outputs"],
        "rule_delta_proposal": contract["rule_delta_proposal"],
        "package_release": contract["package_release"],
        "passed": True,
    }


def write_report(
    contract_path: Path, project_root: Path, report_path: Path
) -> dict[str, Any]:
    report = validate_contract(contract_path, project_root)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report
