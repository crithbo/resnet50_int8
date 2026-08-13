#!/usr/bin/env python3
"""Classify repeated ARM tags using exact, binary-known SA output beats."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:/%+\[\]$-]+$")
HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


def parse_line(line: str) -> tuple[dict[str, str] | None, str | None]:
    if not line.startswith("CODEX_PROBE_V1 "):
        return None, None
    fields: dict[str, str] = {}
    for token in line.rstrip("\n").split(" ")[1:]:
        if "=" not in token:
            return None, "malformed logger token"
        key, value = token.split("=", 1)
        if not key or not value or not TOKEN_RE.fullmatch(value):
            return None, "invalid logger token"
        fields[key] = value
    if not {"kind", "boundary", "instance"}.issubset(fields):
        return None, "logger record lacks identity"
    return fields, None


def integer(row: dict[str, str], key: str) -> int:
    try:
        return int(row[key], 0)
    except (KeyError, ValueError):
        return -1


def hexadecimal(row: dict[str, str], key: str) -> int:
    value = row.get(key, "")
    if not HEX_RE.fullmatch(value):
        return -1
    return int(value, 16)


def evaluate(log: Path, contract: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    raw_count = 0
    target_rows: list[dict[str, str]] = []
    wrong_instance_rows = 0
    boundary_ids = set(contract["boundary_ids"])
    expected_instances = set(contract["expected_instances"])
    for line_number, line in enumerate(log.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        row, error = parse_line(line)
        if error:
            errors.append(f"line {line_number}: {error}")
            continue
        if row is None or row.get("boundary") not in boundary_ids:
            continue
        raw_count += 1
        if row.get("instance") in expected_instances:
            target_rows.append(row)
        else:
            wrong_instance_rows += 1

    enabled_instances = {row["instance"] for row in target_rows if row.get("kind") == "ENABLED"}
    if enabled_instances != expected_instances:
        errors.append("exact target ENABLED instance set differs")
    lane_by_instance = {value: index for index, value in enumerate(contract["expected_instances"])}
    accepted_lanes: list[dict[str, Any]] = []
    for row in target_rows:
        if row.get("kind") not in {"EVENT", "RING_PROGRESS"}:
            continue
        if hexadecimal(row, "mask") & 1 == 0:
            continue
        if integer(row, "payload_known") != 1:
            errors.append("accepted SA payload is not binary-known")
            continue
        if integer(row, "payload_width") != int(contract["payload_width_bits"]):
            errors.append("accepted SA payload width differs from contract")
            continue
        payload = hexadecimal(row, "payload")
        if payload < 0 or payload.bit_length() > int(contract["payload_width_bits"]):
            errors.append("accepted SA payload is malformed or over-width")
            continue
        ready = payload & 1
        data = (payload >> 1) & ((1 << int(contract["lane_data_width_bits"])) - 1)
        tag = payload >> (1 + int(contract["lane_data_width_bits"]))
        if ready != 1 or tag & int(contract["lane_valid_mask"], 0) == 0:
            errors.append("accepted SA payload does not decode to valid+ready")
            continue
        accepted_lanes.append({
            "time": integer(row, "time"),
            "seq": integer(row, "seq"),
            "lane": lane_by_instance[row["instance"]],
            "instance": row["instance"],
            "tag": tag,
            "data_hex": f"{data:0{int(contract['lane_data_width_bits']) // 4}x}",
            "payload": row.get("payload"),
        })
    # EVENT and final RING_PROGRESS may describe the same transaction; identity is
    # time plus complete payload so the final ring cannot fabricate a replay.
    unique = {(row["time"], row["lane"], row["payload"]): row for row in accepted_lanes}
    accepted_lanes = sorted(unique.values(), key=lambda row: (row["time"], row["lane"], row["seq"]))
    by_time: dict[int, dict[int, dict[str, Any]]] = {}
    for row in accepted_lanes:
        by_time.setdefault(row["time"], {})[row["lane"]] = row
    accepted: list[dict[str, Any]] = []
    complete_non_target_beats: list[dict[str, Any]] = []
    for time, lanes in sorted(by_time.items()):
        if set(lanes) != set(range(int(contract["lane_count"]))):
            continue
        # RTL packs lane 7 at the MSB and lane 0 at the LSB.
        lane_count = int(contract["lane_count"])
        data_hex = "".join(lanes[index]["data_hex"] for index in reversed(range(lane_count)))
        valid_vector = sum(((lanes[index]["tag"] >> 6) & 1) << index for index in range(lane_count))
        any_last = int(any((lanes[index]["tag"] >> 5) & 1 for index in range(lane_count)))
        any_same = int(any((lanes[index]["tag"] >> 4) & 1 for index in range(lane_count)))
        lane0_last_index = lanes[0]["tag"] & 0xF
        group_tag = (valid_vector << 6) | (any_last << 5) | (any_same << 4) | lane0_last_index
        beat = {
            "time": time,
            "group_tag": f"0x{group_tag:x}",
            "data_hex": data_hex,
            "lanes": [lanes[index] for index in range(lane_count)],
        }
        if group_tag == int(contract["target_group_tag"], 0):
            accepted.append(beat)
        else:
            complete_non_target_beats.append(beat)
    if len(accepted) < 2:
        errors.append(f"only {len(accepted)} complete exact target accepted SA beats, expected at least 2")

    selected = accepted[-2:]
    data_distinct = len(selected) == 2 and selected[0]["data_hex"] != selected[1]["data_hex"]
    data_identical = len(selected) == 2 and selected[0]["data_hex"] == selected[1]["data_hex"]
    if errors:
        decision = "EVIDENCE_INCOMPLETE"
        candidates: list[str] = []
    elif data_distinct:
        decision = "DISTINCT_SA_DATA_BEATS_SHARE_ARM_TAG"
        candidates = ["legitimate_distinct_sa_beats_same_tag"]
    else:
        decision = "IDENTICAL_SA_DATA_BEAT_REACCEPT_OR_VALUE_COLLISION"
        candidates = ["held_sa_beat_reaccepted", "distinct_equal_value_sa_beats"]
    return {
        "schema": "conv-native-four-lane-p37-sa-epoch-decision-v1",
        "decision": decision,
        "matching_candidate_ids": candidates,
        "expected_instances": contract["expected_instances"],
        "boundary_ids": contract["boundary_ids"],
        "payload_width_bits": contract["payload_width_bits"],
        "target_group_tag": contract["target_group_tag"],
        "accepted_lane_rows": accepted_lanes,
        "accepted_complete_beats": accepted,
        "complete_non_target_beats": complete_non_target_beats,
        "selected_last_two": selected,
        "selected_data_distinct": data_distinct,
        "selected_data_identical": data_identical,
        "wrong_instance_rows_ignored": wrong_instance_rows,
        "raw_boundary_record_count": raw_count,
        "errors": errors,
        "natural_terminal_claimed": False,
        "formal_d_claimed": False,
        "claim_boundary": (
            "Exact group0 SA_Outport accepted output lanes, reconstructed with the public group-tag OR/selection formula; X/Z, width drift, wrong instance, "
            "missing rows and malformed payload fail closed. Equal data remains ambiguous rather than being called replay."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(args.log, json.loads(args.contract.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": report["decision"], "errors": len(report["errors"]), "output": str(args.output)}, sort_keys=True))
    return 0 if report["decision"] != "EVIDENCE_INCOMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
