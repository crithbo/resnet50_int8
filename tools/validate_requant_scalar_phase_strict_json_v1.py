#!/usr/bin/env python3
"""Validate local Requant scalar-phase strict JSON materialization."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5_requant_scalar_phase_strict_json_v1"
)
INVENTORY = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5_complete_json_regeneration_v1/requantize_uint8/stage_inventory.json"
)
LOWERING = ROOT / "contracts/resnet50_r5_lowering_bundle.json"
LOWERING_SHA256 = "bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432"
FORBIDDEN_NAMES = {
    "PREPARE_AND_RUN.sh",
    "TEST_PACKAGE_MANIFEST.json",
    "SERVER_RESULT_GATE.json",
}
FORBIDDEN_SUFFIXES = {".zip", ".bit", ".bin"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def bits_sha(bits: list[str]) -> str:
    raw = b"".join(struct.pack("<I", int(item, 16)) for item in bits)
    return hashlib.sha256(raw).hexdigest()


def check_tiles(tiles: list[dict[str, Any]], total: int, label: str) -> list[str]:
    errors: list[str] = []
    cursor = 0
    for index, tile in enumerate(tiles):
        if tile != {
            "tile_id": index,
            "linear_start": cursor,
            "count": min(32768, total - cursor),
        }:
            errors.append(f"{label}: noncanonical tile {index}: {tile}")
            break
        if not (0 < tile["count"] <= 32768):
            errors.append(f"{label}: illegal LC tile count {tile['count']}")
        cursor += tile["count"]
    if cursor != total:
        errors.append(f"{label}: tile coverage {cursor} != {total}")
    return errors


def validate_candidate(
    candidate: dict[str, Any], stage: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    stage_id = stage["identity"]["hw_op_id"]
    if candidate.get("schema") != "requant_scalar_phase_strict_json_v1":
        errors.append(f"{stage_id}: candidate schema")
        return errors
    if candidate.get("family") != "requantize_uint8":
        errors.append(f"{stage_id}: family")
    if candidate["identity"]["hw_op_id"] != stage_id:
        errors.append(f"{stage_id}: identity")

    shape = list(stage["shape"]["output"])
    if candidate["typed_io"]["input"]["shape"] != shape:
        errors.append(f"{stage_id}: input shape")
    if candidate["typed_io"]["output"]["shape"] != shape:
        errors.append(f"{stage_id}: output shape")
    element_count = math.prod(shape)
    qparams = candidate["qparams"]
    bits = qparams["multiplier_bits"]
    expected_multiplier = stage["qparams"]["requant_multiplier"]
    if len(bits) != expected_multiplier["element_count"]:
        errors.append(f"{stage_id}: multiplier count")
    if bits_sha(bits) != expected_multiplier["value_sha256"]:
        errors.append(f"{stage_id}: multiplier payload SHA")
    if qparams["multiplier_payload_sha256"] != expected_multiplier["value_sha256"]:
        errors.append(f"{stage_id}: declared multiplier SHA")
    expected_zp = int(stage["qparams"]["y_zero_point"]["scalar"])
    if qparams["y_zero_point"] != expected_zp:
        errors.append(f"{stage_id}: zero point")

    graph = candidate["numeric_graph"]
    expected_chain = [
        ("PE00", "mul"),
        ("PE01", "sfu_activation"),
        ("PE10", "add"),
        ("PE11", "int32_sub"),
        ("PE12", "int32_sum"),
    ]
    actual_chain = [(item["pe"], item["opcode"]) for item in graph["pe_chain"]]
    if actual_chain != expected_chain:
        errors.append(f"{stage_id}: five-PE chain")
    if graph["pe_chain"][4]["input2_constant_int32"] != expected_zp:
        errors.append(f"{stage_id}: integer zp placement")
    lut = graph["clamp_lut"]
    if len(lut["breakpoint_bits_rank_order"]) != 65:
        errors.append(f"{stage_id}: breakpoint count")
    if len(lut["slope_bits_by_address"]) != 66:
        errors.append(f"{stage_id}: slope count")
    if len(lut["intercept_bits_by_address"]) != 66:
        errors.append(f"{stage_id}: intercept count")
    if lut["reachable_coefficient_addresses"] != [0, 32, 65]:
        errors.append(f"{stage_id}: reachable coefficient addresses")
    if not graph["magic_wrap_counterexample_retained"]["excluded_by_exact_clamp"]:
        errors.append(f"{stage_id}: magic-wrap counterexample waived")

    schedule = candidate["physical_schedule"]
    coverage = schedule["coverage"]
    if coverage["logical_element_count"] != element_count:
        errors.append(f"{stage_id}: logical coverage")
    if coverage["input_int32_bytes"] != element_count * 4:
        errors.append(f"{stage_id}: input byte coverage")
    if coverage["output_uint8_bytes"] != element_count:
        errors.append(f"{stage_id}: output byte coverage")
    if not coverage["each_logical_element_exactly_once"]:
        errors.append(f"{stage_id}: exact-once coverage")

    regions = schedule["operator_relative_address_space"]["regions"]
    ordered = [
        regions["input_int32"],
        regions["multiplier_fp32"],
        regions["output_uint8"],
    ]
    if ordered[0]["base"] != 0:
        errors.append(f"{stage_id}: input base")
    for previous, current in zip(ordered, ordered[1:]):
        if current["base"] % 16:
            errors.append(f"{stage_id}: unaligned region")
        if current["base"] < previous["base"] + previous["size_bytes"]:
            errors.append(f"{stage_id}: overlapping regions")
    if schedule["limits"]["maximum_stream_stride"] > 1048575:
        errors.append(f"{stage_id}: stream stride overflow")
    if not schedule["limits"]["all_lc_end_le_32768"]:
        errors.append(f"{stage_id}: LC bound claim")

    onnx_type = stage["identity"]["onnx_op_type"]
    if onnx_type == "QLinearConv":
        batch, channels, height, width = shape
        spatial = batch * height * width
        if schedule["mode"] != "CONV_SCALAR_CHANNEL_PHASE":
            errors.append(f"{stage_id}: Conv schedule mode")
        if schedule["loops"]["channel_phase_count"] != channels:
            errors.append(f"{stage_id}: channel phases")
        errors.extend(
            check_tiles(
                schedule["loops"]["spatial_tiles"],
                spatial,
                stage_id,
            )
        )
        expected_substages = channels * len(schedule["loops"]["spatial_tiles"])
        if schedule["loops"]["operator_substage_count"] != expected_substages:
            errors.append(f"{stage_id}: substage count")
        stream = schedule["streams"]["multiplier_B"]
        if stream["transaction_bytes"] != 4 or stream["idx_size"] != [3, 0, "NULL"]:
            errors.append(f"{stage_id}: scalar B transaction")
        if stream["address_equation"] != "multiplier_base + 4*channel":
            errors.append(f"{stage_id}: multiplier address equation")
        if schedule["buffers"]["buffer2_B"]["buf_spatial_size"] != 4:
            errors.append(f"{stage_id}: buffer2 spatial size")
        if schedule["buffers"]["buffer2_B"]["mask"] != [1, 0, 0, 0, 0, 0, 0, 0]:
            errors.append(f"{stage_id}: buffer2 lane mask")
        if schedule["ga_inports"]["inport1_B"]["mask"] != [1, 0, 0, 0, 0, 0, 0, 0]:
            errors.append(f"{stage_id}: GA B lane mask")
        if schedule["pe00_multiplier_input"]["mode"] != "keep":
            errors.append(f"{stage_id}: PE00 keep")
        if schedule["pe00_multiplier_input"]["keep_last_index"] != 1:
            errors.append(f"{stage_id}: PE00 keep boundary")
    elif onnx_type == "QLinearMatMul":
        if schedule["mode"] != "MATMUL_LINEAR_SCALAR_CONSTANT":
            errors.append(f"{stage_id}: MatMul schedule mode")
        if len(bits) != 1 or qparams["multiplier_axis"] is not None:
            errors.append(f"{stage_id}: scalar multiplier")
        if schedule["pe00_multiplier_input"]["mode"] != "constant":
            errors.append(f"{stage_id}: scalar constant supply")
        errors.extend(
            check_tiles(
                schedule["loops"]["spatial_tiles"],
                element_count,
                stage_id,
            )
        )
    else:
        errors.append(f"{stage_id}: unexpected ONNX type {onnx_type}")

    claim = candidate["local_strict_claim"]
    if not claim["candidate_complete"]:
        errors.append(f"{stage_id}: candidate not complete")
    for name in (
        "backend_bound",
        "mapping_generated",
        "bitstream_generated",
        "execplan_generated",
        "sca_generated",
        "server_package_generated",
        "dynamic_execution_claimed",
    ):
        if claim[name]:
            errors.append(f"{stage_id}: forbidden claim {name}")
    if any(
        isinstance(value, str) and "UNRESOLVED" in value.upper()
        for value in walk(candidate)
    ):
        errors.append(f"{stage_id}: unresolved marker")
    return errors


def validate(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    if sha256_file(LOWERING) != LOWERING_SHA256:
        errors.append("lowering SHA drift")
    inventory = load_json(INVENTORY)
    stages = inventory["stages"]
    stage_ids = [stage["identity"]["hw_op_id"] for stage in stages]
    family_set = load_json(root / "family_set.json")
    if family_set["family_scope"]["expected_stage_ids"] != stage_ids:
        errors.append("family-set ordered exact stage scope mismatch")
    if family_set["family_scope"]["lowering_sha256"] != LOWERING_SHA256:
        errors.append("family-set lowering SHA mismatch")
    if len(family_set["candidate_contracts"]) != 54:
        errors.append("family-set candidate count")

    candidate_errors: dict[str, list[str]] = {}
    total_ledger_leaves = 0
    for stage in stages:
        stage_id = stage["identity"]["hw_op_id"]
        candidate_dir = root / "candidates" / stage_id
        candidate = load_json(candidate_dir / "complete_json.json")
        stage_errors = validate_candidate(candidate, stage)
        if stage_errors:
            candidate_errors[stage_id] = stage_errors
            errors.extend(stage_errors)
        ledger = load_json(candidate_dir / "field_provenance_ledger.json")
        if ledger["candidate_json_sha256"] != sha256_file(
            candidate_dir / "complete_json.json"
        ):
            errors.append(f"{stage_id}: ledger candidate SHA")
        total_ledger_leaves += len(ledger["entries"])
        if any(item["status"] != "RESOLVED" for item in ledger["entries"]):
            errors.append(f"{stage_id}: unresolved ledger entry")

    forbidden = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            forbidden.append(path.relative_to(root).as_posix())
        lower_parts = {part.lower() for part in path.parts}
        if {"mapping", "bitstream", "execplan", "sca"} & lower_parts:
            forbidden.append(path.relative_to(root).as_posix())
    if forbidden:
        errors.append(f"forbidden output files: {sorted(set(forbidden))}")

    return {
        "schema": "requant_scalar_phase_strict_json_validation_v1",
        "pass": not errors,
        "errors": errors,
        "candidate_error_stage_count": len(candidate_errors),
        "candidate_errors": candidate_errors,
        "stage_count": len(stages),
        "strict_json_count": sum(
            (root / "candidates" / stage_id / "complete_json.json").is_file()
            for stage_id in stage_ids
        ),
        "conv_stage_count": sum(
            stage["identity"]["onnx_op_type"] == "QLinearConv" for stage in stages
        ),
        "matmul_stage_count": sum(
            stage["identity"]["onnx_op_type"] == "QLinearMatMul" for stage in stages
        ),
        "total_ledger_leaf_count": total_ledger_leaves,
        "unresolved_leaf_count": 0 if not errors else None,
        "forbidden_output_count": len(set(forbidden)),
        "claim_boundary": (
            "Local strict Requant scalar-phase JSON validation only; "
            "no backend or dynamic execution surface is validated."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = validate(args.artifact_root.resolve())
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
