#!/usr/bin/env python3
"""Validate the 17 local QLinearAdd one-lane nine-PE strict candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5_qlinearadd_slow_composite_strict_json_v1"
)
INVENTORY = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5_complete_json_regeneration_v1/qlinearadd/stage_inventory.json"
)
LOWERING = ROOT / "contracts/resnet50_r5_lowering_bundle.json"
LOWERING_SHA256 = "bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432"
EXPECTED_PE_CHAIN = [
    ("PE00", "add", "A_ADD_NEG_ZP"),
    ("PE01", "mul", "A_MUL_SCALE"),
    ("PE02", "add", "B_ADD_NEG_ZP"),
    ("PE03", "mul", "B_MUL_SCALE"),
    ("PE12", "add", "A_PLUS_B"),
    ("PE13", "sfu_activation", "REACHABLE_DOMAIN_SFU"),
    ("PE22", "mac", "MAGIC_ADD"),
    ("PE23", "int32_sub", "MAGIC_INT32_SUB"),
    ("PE32", "int32_mac", "ADD_OUTPUT_ZERO_POINT"),
]
EXPECTED_SELECTORS = [4, 4, 1, 3, 4, 3, 4, 3]
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


def check_tiles(
    tiles: list[dict[str, Any]], total: int, label: str
) -> list[str]:
    errors: list[str] = []
    cursor = 0
    for index, tile in enumerate(tiles):
        expected = {
            "tile_id": index,
            "group_start": cursor,
            "group_count": min(32768, total - cursor),
        }
        if tile != expected:
            errors.append(f"{label}: noncanonical tile {index}: {tile}")
            break
        if not (0 < tile["group_count"] <= 32768):
            errors.append(f"{label}: illegal LC tile")
        cursor += tile["group_count"]
    if cursor != total:
        errors.append(f"{label}: tile coverage {cursor} != {total}")
    return errors


def validate_candidate(
    candidate: dict[str, Any],
    stage: dict[str, Any],
    dp_row: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    stage_id = stage["identity"]["hw_op_id"]
    if candidate.get("schema") != "qlinearadd_slow_composite_strict_json_v1":
        return [f"{stage_id}: candidate schema"]
    if candidate.get("family") != "qlinearadd":
        errors.append(f"{stage_id}: family")
    if candidate["identity"]["hw_op_id"] != stage_id:
        errors.append(f"{stage_id}: identity")
    for name, typed_name in (("a", "A"), ("b", "B"), ("y", "Y")):
        if candidate["typed_io"][typed_name]["shape"] != stage["shapes"][name]:
            errors.append(f"{stage_id}: {typed_name} shape")
        if candidate["typed_io"][typed_name]["dtype"] != "uint8":
            errors.append(f"{stage_id}: {typed_name} dtype")
    for name in (
        "a_scale",
        "a_zero_point",
        "b_scale",
        "b_zero_point",
        "y_scale",
        "y_zero_point",
    ):
        if candidate["qparams"][name] != stage["qparams"][name]:
            errors.append(f"{stage_id}: qparam {name}")

    graph = candidate["numeric_graph"]
    chain = [
        (item["pe"], item["opcode"], item["role"])
        for item in graph["pe_chain"]
    ]
    if chain != EXPECTED_PE_CHAIN:
        errors.append(f"{stage_id}: nine-PE chain")
    selectors = [
        item["consumer_src_id"] for item in graph["selector_edges"]
    ]
    if selectors != EXPECTED_SELECTORS:
        errors.append(f"{stage_id}: selector chain")
    terminal = graph["terminal"]
    if (
        terminal["source_pe"],
        terminal["outport_id"],
        terminal["src_id"],
        terminal["int32_to_uint8_saturating"],
    ) != ("PE32", 6, 1, True):
        errors.append(f"{stage_id}: terminal route")
    if graph["operation_order"] != stage["dag"]["W3_order"]:
        errors.append(f"{stage_id}: W3 order")
    if not graph["single_fma_dequant_forbidden"]:
        errors.append(f"{stage_id}: single-FMA negative waived")
    if not graph["reciprocal_approximation_forbidden"]:
        errors.append(f"{stage_id}: reciprocal negative waived")
    sfu = graph["reachable_domain_sfu"]
    if sfu["breakpoint_bits"] != dp_row["hardware_breakpoint_bits"]:
        errors.append(f"{stage_id}: SFU breakpoint table")
    if sfu["segments"] != dp_row["hardware_segments"]:
        errors.append(f"{stage_id}: SFU coefficient table")
    if (
        sfu["breakpoint_count"],
        sfu["segment_count"],
        sfu["reachable_pair_count"],
        sfu["dispatch_mismatch_count"],
    ) != (65, 66, 65536, 0):
        errors.append(f"{stage_id}: SFU proof summary")
    if sfu["ordered_domain_target_sha256"] != dp_row[
        "ordered_domain_target_sha256"
    ]:
        errors.append(f"{stage_id}: SFU ordered-domain SHA")

    schedule = candidate["physical_schedule"]
    a_count = math.prod(stage["shapes"]["a"])
    b_count = math.prod(stage["shapes"]["b"])
    y_count = math.prod(stage["shapes"]["y"])
    groups = y_count // 4
    if y_count % 4:
        errors.append(f"{stage_id}: non-four-byte tail unsupported")
    coverage = schedule["coverage"]
    if (
        coverage["A_elements"],
        coverage["B_elements"],
        coverage["Y_elements"],
        coverage["logical_group_count"],
    ) != (a_count, b_count, y_count, groups):
        errors.append(f"{stage_id}: coverage counts")
    if (
        coverage["active_buffer_bank_byte_set"] != "[0,4)"
        or coverage["producer_windows"] != ["[0,4)"]
        or coverage["consumer_required_set"] != "[0,4)"
        or coverage["gap_bytes"] != 0
        or coverage["overlap_bytes"] != 0
    ):
        errors.append(f"{stage_id}: active bank window conservation")
    errors.extend(check_tiles(schedule["loops"]["tiles"], groups, stage_id))
    if not schedule["loops"]["all_lc_end_le_32768"]:
        errors.append(f"{stage_id}: LC bound")
    if schedule["limits"]["maximum_stream_stride"] > 1048575:
        errors.append(f"{stage_id}: stream stride")
    for stream_name in ("A", "B", "Y"):
        stream = schedule["streams"][stream_name]
        if stream["transaction_bytes"] != 4:
            errors.append(f"{stage_id}: {stream_name} transaction")
        if stream["idx_size"] != [3, 0, "NULL"]:
            errors.append(f"{stage_id}: {stream_name} idx_size")
    low_mask = [1, 0, 0, 0, 0, 0, 0, 0]
    for buffer_name in ("buffer0_A", "buffer2_B", "buffer5_Y"):
        buffer = schedule["buffers"][buffer_name]
        if (
            buffer["buf_spatial_stride"] != [0, 1, 2, 3]
            or buffer["buf_spatial_size"] != 4
            or buffer["mask"] != low_mask
        ):
            errors.append(f"{stage_id}: {buffer_name} one-lane supply")
    if not all(schedule["paired_readiness"].values()):
        errors.append(f"{stage_id}: paired readiness")

    regions = schedule["operator_relative_address_space"]["regions"]
    ordered_regions = [regions["A_uint8"], regions["B_uint8"], regions["Y_uint8"]]
    if ordered_regions[0] != {"base": 0, "size_bytes": a_count}:
        errors.append(f"{stage_id}: A local address")
    for previous, current in zip(ordered_regions, ordered_regions[1:]):
        if current["base"] % 16:
            errors.append(f"{stage_id}: local region alignment")
        if current["base"] < previous["base"] + previous["size_bytes"]:
            errors.append(f"{stage_id}: local region overlap")
    replay = schedule["broadcast_replay"]
    if replay["materialized_by_host"] or replay[
        "host_precomputed_internal_tensor"
    ]:
        errors.append(f"{stage_id}: host replay forbidden")
    if stage_id == "hwop-0076-00":
        if schedule["mode"] != "NODE0076_HARDWARE_B_REPLAY_ONE_LANE_9PE":
            errors.append(f"{stage_id}: broadcast mode")
        if replay["invocation_count"] != 16:
            errors.append(f"{stage_id}: broadcast invocation count")
        if replay["B_address_equation"] != "B_base + 4*(group_index % 250)":
            errors.append(f"{stage_id}: broadcast B address")
        if "invocation 15" not in schedule["lifetime"]["B"]:
            errors.append(f"{stage_id}: broadcast B lifetime")
    else:
        if schedule["mode"] != "ELEMENTWISE_ONE_LANE_9PE":
            errors.append(f"{stage_id}: elementwise mode")
        if replay["invocation_count"] != 1:
            errors.append(f"{stage_id}: elementwise invocation count")
        if replay["B_address_equation"] != "B_base + 4*group_index":
            errors.append(f"{stage_id}: elementwise B address")
    if "final Buffer5 accepted write" not in schedule["loops"][
        "terminal_equation"
    ]:
        errors.append(f"{stage_id}: accepted terminal")

    claim = candidate["local_strict_claim"]
    if not claim["candidate_complete"]:
        errors.append(f"{stage_id}: candidate incomplete")
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
    stages = inventory["targets"]
    stage_ids = [stage["identity"]["hw_op_id"] for stage in stages]
    dp = load_json(
        root
        / "inputs/qadd_slow_composite_proof/"
        "reachable_domain_sfu_segment_dp.json"
    )
    dp_by_id = {row["stage_id"]: row for row in dp["rows"]}
    family_set = load_json(root / "family_set.json")
    if family_set["family_scope"]["expected_stage_ids"] != stage_ids:
        errors.append("family-set ordered exact stage scope mismatch")
    if family_set["family_scope"]["lowering_sha256"] != LOWERING_SHA256:
        errors.append("family-set lowering SHA mismatch")
    if len(family_set["candidate_contracts"]) != 17:
        errors.append("family-set candidate count")

    candidate_errors: dict[str, list[str]] = {}
    total_leaves = 0
    for stage in stages:
        stage_id = stage["identity"]["hw_op_id"]
        candidate_dir = root / "candidates" / stage_id
        candidate_path = candidate_dir / "complete_json.json"
        candidate = load_json(candidate_path)
        stage_errors = validate_candidate(candidate, stage, dp_by_id[stage_id])
        if stage_errors:
            candidate_errors[stage_id] = stage_errors
            errors.extend(stage_errors)
        ledger = load_json(candidate_dir / "field_provenance_ledger.json")
        if ledger["candidate_json_sha256"] != sha256_file(candidate_path):
            errors.append(f"{stage_id}: ledger candidate SHA")
        candidate_leaf_count = sum(1 for _ in leaf_iter(candidate))
        if len(ledger["entries"]) != candidate_leaf_count:
            errors.append(f"{stage_id}: ledger leaf count")
        total_leaves += len(ledger["entries"])
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
        "schema": "qlinearadd_slow_composite_strict_json_validation_v1",
        "pass": not errors,
        "errors": errors,
        "candidate_error_stage_count": len(candidate_errors),
        "candidate_errors": candidate_errors,
        "stage_count": 17,
        "strict_json_count": sum(
            (root / "candidates" / stage_id / "complete_json.json").is_file()
            for stage_id in stage_ids
        ),
        "same_shape_stage_count": 16,
        "broadcast_stage_count": 1,
        "total_ledger_leaf_count": total_leaves,
        "unresolved_leaf_count": 0 if not errors else None,
        "forbidden_output_count": len(set(forbidden)),
        "claim_boundary": (
            "Local strict QLinearAdd one-lane 9PE JSON validation only; "
            "backend and dynamic execution are excluded."
        ),
    }


def leaf_iter(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        if not value:
            yield pointer or "/", value
        for key in sorted(value):
            token = key.replace("~", "~0").replace("/", "~1")
            yield from leaf_iter(value[key], f"{pointer}/{token}")
    elif isinstance(value, list):
        if not value:
            yield pointer or "/", value
        for index, child in enumerate(value):
            yield from leaf_iter(child, f"{pointer}/{index}")
    else:
        yield pointer or "/", value


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
