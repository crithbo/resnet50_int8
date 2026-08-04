"""Fail-closed validator for the shared exact UINT8 quant-tail proposal."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np


SCHEMA = "exact-uint8-quant-tail-capability-v1"
REPORT_SCHEMA = "exact-uint8-quant-tail-capability-report-v1"
MAGIC_BITS = 0x4B400000
MAGIC_FLOAT = np.float32(12582912.0)


class QuantTailCapabilityError(ValueError):
    """Raised when proposal evidence or a counterexample no longer holds."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _u32(value: np.float32) -> int:
    return int(np.asarray(value, dtype=np.float32).view(np.uint32))


def _f32_from_bits(bits: int) -> np.float32:
    return np.asarray(bits, dtype=np.uint32).view(np.float32)


def _saturate_decoded(raw: int) -> int:
    raw &= 0xFFFFFFFF
    if raw & 0x80000000:
        return 0
    if raw & 0x7FFFFF00:
        return 255
    return raw & 0xFF


def expected_from_scaled(scaled: float, zero_point: int) -> int:
    rounded = int(np.rint(np.float32(scaled)))
    return max(0, min(255, rounded + int(zero_point)))


def oracle_bias_patch(scaled: float, zero_point: int) -> int:
    bias = np.float32(MAGIC_FLOAT + np.float32(zero_point))
    biased = np.float32(np.float32(scaled) + bias)
    return _saturate_decoded(_u32(biased) - MAGIC_BITS)


def proposed_subtract_patch(scaled: float, zero_point: int) -> int:
    biased = np.float32(np.float32(scaled) + MAGIC_FLOAT)
    subtract = (MAGIC_BITS - int(zero_point)) & 0xFFFFFFFF
    return _saturate_decoded(_u32(biased) - subtract)


def _round_fraction_to_f32(value: Fraction) -> np.float32:
    approximate = np.float32(float(value))
    candidates = {
        _u32(approximate): approximate,
        _u32(np.nextafter(approximate, np.float32(-np.inf), dtype=np.float32)): np.nextafter(
            approximate, np.float32(-np.inf), dtype=np.float32
        ),
        _u32(np.nextafter(approximate, np.float32(np.inf), dtype=np.float32)): np.nextafter(
            approximate, np.float32(np.inf), dtype=np.float32
        ),
    }
    ranked = sorted(
        candidates.items(),
        key=lambda item: (
            abs(value - Fraction.from_float(float(item[1]))),
            item[0] & 1,
        ),
    )
    return ranked[0][1]


def one_round_fused_magic(value: np.float32, multiplier: np.float32, zero_point: int) -> int:
    """Model a correctly-rounded binary32 FMA using exact rational arithmetic.

    The model is a discriminator, not a claim that the target RTL implements
    this result.
    """

    exact = (
        Fraction.from_float(float(value)) * Fraction.from_float(float(multiplier))
        + Fraction.from_float(float(MAGIC_FLOAT))
    )
    fused = _round_fraction_to_f32(exact)
    subtract = (MAGIC_BITS - int(zero_point)) & 0xFFFFFFFF
    return _saturate_decoded(_u32(fused) - subtract)


def sequential_multiplier_tail(value: np.float32, multiplier: np.float32, zero_point: int) -> int:
    scaled = np.float32(value * multiplier)
    return expected_from_scaled(float(scaled), zero_point)


def quantize_division_tail(x: np.float32, scale: np.float32, zero_point: int) -> int:
    scaled = np.float32(x / scale)
    return expected_from_scaled(float(scaled), zero_point)


def _read_receipts(
    root: Path,
    contract: dict[str, Any],
    field: str = "read_receipt",
    gate: str = "historical_provenance_only",
) -> list[dict[str, Any]]:
    receipts = []
    for item in contract[field]:
        path = root / item["path"]
        current_sha256 = _sha256(path) if path.is_file() else None
        receipts.append(
            {
                "path": item["path"],
                "recorded_sha256": item["sha256"],
                "current_sha256": current_sha256,
                "current_match": current_sha256 == item["sha256"],
                "gate": gate,
            }
        )
    return receipts


def _validate_semantic_source_identities(
    root: Path, contract: dict[str, Any]
) -> list[dict[str, Any]]:
    receipts = []
    for item in contract["semantic_source_identities"]:
        path = root / item["path"]
        if not path.is_file():
            raise QuantTailCapabilityError(f"missing semantic source identity: {item['path']}")
        actual = _sha256(path)
        if actual != item["sha256"]:
            raise QuantTailCapabilityError(
                "semantic source identity changed: "
                f"{item['path']} expected={item['sha256']} actual={actual}"
            )
        receipts.append(
            {
                "path": item["path"],
                "sha256": actual,
                "matched": True,
                "gate": "current_match_fail_closed",
            }
        )
    return receipts


def _validate_counterexamples(contract: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {item["id"]: item for item in contract["counterexamples"]}
    checks: list[dict[str, Any]] = []

    odd = by_id["CE_ODD_ZP_TIE_PARITY"]
    scaled = odd["inputs"]["scaled_fp32"]
    zero_point = odd["inputs"]["zero_point"]
    observed = {
        "expected_uint8": expected_from_scaled(scaled, zero_point),
        "oracle_bias_patch_uint8": oracle_bias_patch(scaled, zero_point),
        "proposed_subtract_patch_uint8": proposed_subtract_patch(scaled, zero_point),
    }
    for key, value in observed.items():
        if value != odd[key]:
            raise QuantTailCapabilityError(f"odd-zp counterexample changed: {key}={value}")
    checks.append({"id": odd["id"], "passed": True, "observed": observed})

    fma = by_id["CE_FMA_VS_SEQUENTIAL_ROUND"]
    value = np.float32(fma["inputs"]["int32"])
    multiplier = _f32_from_bits(int(fma["inputs"]["multiplier_bits"], 16))
    observed = {
        "expected_sequential_uint8": sequential_multiplier_tail(value, multiplier, 0),
        "one_round_fused_model_uint8": one_round_fused_magic(value, multiplier, 0),
    }
    for key, result in observed.items():
        if result != fma[key]:
            raise QuantTailCapabilityError(f"FMA discriminator changed: {key}={result}")
    checks.append({"id": fma["id"], "passed": True, "observed": observed})

    division = by_id["CE_FP32_DIVISION_VS_RECIPROCAL_FMA"]
    x = _f32_from_bits(int(division["inputs"]["x_fp32_bits"], 16))
    scale = _f32_from_bits(int(division["inputs"]["scale_fp32_bits"], 16))
    reciprocal = _f32_from_bits(int(division["inputs"]["reciprocal_fp32_bits"], 16))
    observed = {
        "expected_divide_then_rne_uint8": quantize_division_tail(x, scale, 0),
        "reciprocal_fma_magic_uint8": one_round_fused_magic(x, reciprocal, 0),
    }
    for key, result in observed.items():
        if result != division[key]:
            raise QuantTailCapabilityError(f"division discriminator changed: {key}={result}")
    checks.append({"id": division["id"], "passed": True, "observed": observed})

    domain = by_id["CE_MAGIC_DOMAIN_UNDERFLOW"]
    observed_value = proposed_subtract_patch(
        domain["inputs"]["scaled_fp32"], domain["inputs"]["zero_point"]
    )
    if observed_value != domain["magic_decode_then_saturate_uint8"]:
        raise QuantTailCapabilityError(f"magic domain counterexample changed: {observed_value}")
    checks.append(
        {
            "id": domain["id"],
            "passed": True,
            "observed": {"magic_decode_then_saturate_uint8": observed_value},
        }
    )

    negative = by_id["CE_INT32_NEGATIVE_CONVERSION"]
    if negative["expected_fp32_bits"] != "0xbf800000" or negative["observed_rtl_static_bits"] != "0xcf000000":
        raise QuantTailCapabilityError("negative INT32 conversion evidence changed")
    checks.append({"id": negative["id"], "passed": True, "observed": negative["inputs"]})
    return checks


def validate_capability_contract(contract_path: Path, project_root: Path) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("schema") != SCHEMA:
        raise QuantTailCapabilityError(f"unexpected schema: {contract.get('schema')}")
    if contract["pure_configuration_decision"]["unconditional_shared_solution_exists"] is not False:
        raise QuantTailCapabilityError("proposal must remain fail-closed")
    if contract["scope"]["target_artifacts_generated"] is not False:
        raise QuantTailCapabilityError("target artifact generation is forbidden")
    if contract["scope"]["server_files_inspected"] is not False:
        raise QuantTailCapabilityError("server inspection is forbidden")
    if len(contract["capability_matrix"]) != 12:
        raise QuantTailCapabilityError("capability matrix must contain 12 independent cells")
    if not any(item.get("first_hardware_unknown") for item in contract["capability_matrix"]):
        raise QuantTailCapabilityError("first hardware unknown is missing")

    read_receipts = _read_receipts(project_root, contract)
    final_refresh_receipts = _read_receipts(
        project_root,
        contract,
        field="final_refresh_receipt",
        gate="final_validation_snapshot_provenance_only",
    )
    semantic_receipts = _validate_semantic_source_identities(project_root, contract)
    counterexamples = _validate_counterexamples(contract)
    report = {
        "schema": REPORT_SCHEMA,
        "status": "PASS_PROPOSAL_VALID_NO_UNCONDITIONAL_PURE_CONFIG",
        "contract": {
            "path": contract_path.relative_to(project_root).as_posix(),
            "sha256": _sha256(contract_path),
        },
        "read_receipt_count": len(read_receipts),
        "read_receipts": read_receipts,
        "final_refresh_receipt_count": len(final_refresh_receipts),
        "final_refresh_receipts": final_refresh_receipts,
        "semantic_source_identity_count": len(semantic_receipts),
        "semantic_source_identities": semantic_receipts,
        "capability_cell_count": len(contract["capability_matrix"]),
        "consumer_count": len(contract["consumer_matrix"]),
        "counterexample_count": len(counterexamples),
        "counterexamples": counterexamples,
        "first_hardware_unknown": "CE_FMA_VS_SEQUENTIAL_ROUND",
        "pure_configuration_decision": contract["pure_configuration_decision"]["decision"],
        "target_artifacts_generated": False,
        "server_files_inspected": False,
        "server_package_generated": False,
    }
    return report


def write_report(contract_path: Path, project_root: Path, output_path: Path) -> dict[str, Any]:
    report = validate_capability_contract(contract_path, project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report
