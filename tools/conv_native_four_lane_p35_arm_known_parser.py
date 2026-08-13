#!/usr/bin/env python3
"""Decode live ARM token state and fail closed on any X/Z payload."""

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


def normalize_parent(instance: str) -> str:
    for marker in (".u_Buffer.", ".u_Array_Request_Manager."):
        if marker in instance:
            return instance.split(marker, 1)[0]
    return instance


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


def decode_payload(row: dict[str, str], layout: list[dict[str, Any]]) -> dict[str, int] | None:
    value = hexadecimal(row, "payload")
    if value < 0:
        return None
    decoded: dict[str, int] = {}
    remaining = sum(int(field["width_bits"]) for field in layout)
    if value.bit_length() > remaining:
        return None
    for field in reversed(layout):
        width = int(field["width_bits"])
        decoded[field["name"]] = value & ((1 << width) - 1)
        value >>= width
    return decoded


def evaluate(log: Path, contract: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    rows: list[dict[str, str]] = []
    raw_count = 0
    for line_number, line in enumerate(log.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        row, error = parse_line(line)
        if error:
            errors.append(f"line {line_number}: {error}")
            continue
        if row is None:
            continue
        raw_count += 1
        if normalize_parent(row["instance"]) == contract["target_parent"]:
            rows.append(row)
    enabled = {row["boundary"] for row in rows if row["kind"] == "ENABLED"}
    missing = sorted(set(contract["required_boundaries"]) - enabled)
    buffer_boundary = contract["buffer_boundary"]
    arm_boundary = contract["arm_boundary"]
    final_boundary = contract["final_boundary"]
    clear_rows = [row for row in rows if row["kind"] == "TRIGGER" and row["boundary"] == buffer_boundary and hexadecimal(row, "mask") & 1]
    final_rows = [row for row in rows if row["kind"] == "TRIGGER" and row["boundary"] == final_boundary]
    if len(clear_rows) != 1:
        errors.append(f"target clear trigger count is {len(clear_rows)}, expected 1")
    if len(final_rows) != 1:
        errors.append(f"target final trigger count is {len(final_rows)}, expected 1")
    clear_time = integer(clear_rows[0], "time") if len(clear_rows) == 1 else -1
    final_time = integer(final_rows[0], "time") if len(final_rows) == 1 else -1
    if clear_time >= 0 and final_time >= 0 and clear_time >= final_time:
        errors.append("target clear/final temporal order is invalid")
    buffer_accepts = [
        row for row in rows
        if row["kind"] == "EVENT" and row["boundary"] == buffer_boundary
        and clear_time < integer(row, "time") < final_time
        and hexadecimal(row, "mask") & (1 << int(contract["buffer_arm_accept_bit"]))
    ]
    arm_accepts = [
        row for row in rows
        if row["kind"] == "EVENT" and row["boundary"] == arm_boundary
        and clear_time < integer(row, "time") < final_time
        and hexadecimal(row, "mask") & 1
    ]
    buffer_accepts.sort(key=lambda row: (integer(row, "time"), integer(row, "seq")))
    arm_accepts.sort(key=lambda row: (integer(row, "time"), integer(row, "seq")))
    buffer_times = [integer(row, "time") for row in buffer_accepts]
    arm_times = [integer(row, "time") for row in arm_accepts]
    if not buffer_accepts:
        errors.append("target interval lacks live Buffer ARM accepts")
    if buffer_times != arm_times:
        errors.append("Buffer and ARM live accepted-write times differ")
    decoded: list[dict[str, int]] = []
    unknown_rows: list[dict[str, Any]] = []
    for row in arm_accepts:
        value = decode_payload(row, contract["arm_payload_layout_msb_to_lsb"])
        if value is None:
            unknown_rows.append({"time": integer(row, "time"), "payload": row.get("payload")})
        else:
            decoded.append(value)
    if unknown_rows:
        errors.append(f"ARM payload contains X/Z or exceeds declared width at {len(unknown_rows)} accepted rows")
    state_fields = contract["token_state_fields"]
    state_vectors = [{name: row[name] for name in state_fields} for row in decoded]
    stable_reaccept = len(state_vectors) >= 2 and len({json.dumps(row, sort_keys=True) for row in state_vectors}) == 1
    reset_or_wrap = any(hexadecimal(row, "mask") & (1 << int(contract["reset_class_bit"])) for row in arm_accepts)
    progressing = len(state_vectors) >= 2 and not stable_reaccept
    if missing or errors:
        decision, candidates = "EVIDENCE_INCOMPLETE", []
    elif reset_or_wrap:
        decision, candidates = "TARGET_ARM_ROW2_RESET_OR_WRAP", ["arm_reset_or_wrap"]
    elif stable_reaccept:
        decision, candidates = "TARGET_ARM_ROW2_STABLE_TOKEN_REACCEPT", ["arm_stable_token_reaccept"]
    elif progressing:
        decision, candidates = "TARGET_ARM_ROW2_DISTINCT_TOKEN_STATE_PROGRESS", ["arm_distinct_token_progress"]
    else:
        decision, candidates = "TARGET_ARM_ROW2_SINGLE_ACCEPT_ONLY", ["arm_single_accept"]
    return {
        "schema": "conv-native-four-lane-p35-arm-known-decision-v1",
        "decision": decision,
        "matching_candidate_ids": candidates,
        "target_parent": contract["target_parent"],
        "target_clear_time": None if clear_time < 0 else clear_time,
        "target_final_time": None if final_time < 0 else final_time,
        "buffer_accept_rows": buffer_accepts,
        "arm_accept_rows": arm_accepts,
        "arm_accept_payloads_decoded": decoded,
        "unknown_payload_rows": unknown_rows,
        "token_state_vectors": state_vectors,
        "stable_token_reaccept": stable_reaccept,
        "reset_or_wrap": reset_or_wrap,
        "token_state_progress": progressing,
        "enabled_boundaries": sorted(enabled),
        "missing_enabled_boundaries": missing,
        "raw_record_count": raw_count,
        "target_record_count": len(rows),
        "errors": errors,
        "natural_terminal_claimed": False,
        "formal_d_claimed": False,
        "claim_boundary": "Binary-known live exact-target Buffer/ARM records inside one clear/final epoch only; no final-block ring dependency or functional claim.",
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
