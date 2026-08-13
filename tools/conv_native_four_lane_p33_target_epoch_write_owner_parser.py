#!/usr/bin/env python3
"""Correlate p33 Buffer5 clear-window records by exact target and epoch."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:/%+\[\]$-]+$")


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
    """Decode logger fields emitted by Verilog %0h (no 0x prefix)."""
    try:
        return int(row[key], 16)
    except (KeyError, ValueError):
        return -1


def evaluate(log: Path, contract: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    target_parent = contract["target_parent"]
    required = set(contract["required_boundaries"])
    target_rows: list[dict[str, str]] = []
    raw_count = 0
    for line_number, line in enumerate(log.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        row, error = parse_line(line)
        if error:
            errors.append(f"line {line_number}: {error}")
            continue
        if row is None:
            continue
        raw_count += 1
        if normalize_parent(row["instance"]) == target_parent:
            target_rows.append(row)

    enabled = {row["boundary"] for row in target_rows if row["kind"] == "ENABLED"}
    missing_enabled = sorted(required - enabled)
    clear_boundary = contract["clear_window_boundary"]
    final_boundary = contract["final_boundary"]
    clear_rows = [
        row for row in target_rows
        if row["kind"] == "TRIGGER" and row["boundary"] == clear_boundary
    ]
    final_rows = [
        row for row in target_rows
        if row["kind"] == "TRIGGER" and row["boundary"] == final_boundary
    ]
    if len(clear_rows) != 1:
        errors.append(f"target clear trigger count is {len(clear_rows)}, expected 1")
    if len(final_rows) != 1:
        errors.append(f"target final trigger count is {len(final_rows)}, expected 1")
    clear_time = integer(clear_rows[0], "time") if len(clear_rows) == 1 else -1
    final_time = integer(final_rows[0], "time") if len(final_rows) == 1 else -1
    if clear_time >= 0 and final_time >= 0 and clear_time >= final_time:
        errors.append("target clear/final temporal order is invalid")

    post_rows = [
        row for row in target_rows
        if row["kind"] == "RING_POST"
        and row["boundary"] == clear_boundary
        and clear_time < integer(row, "time") <= final_time
    ]
    post_rows.sort(key=lambda row: (integer(row, "time"), integer(row, "seq")))
    post_state_bit = int(contract["post_state_class_bit"])
    owner_bits = {key: int(value) for key, value in contract["accepted_write_owner_bits"].items()}
    post_state_rows = [row for row in post_rows if hexadecimal(row, "mask") & (1 << post_state_bit)]
    if not post_rows:
        errors.append("target clear window lacks bounded RING_POST records")
    if len(post_state_rows) != 1:
        errors.append(f"target post-state row count is {len(post_state_rows)}, expected 1")
    post_state_time = integer(post_state_rows[0], "time") if len(post_state_rows) == 1 else -1
    owner_rows = {
        owner: [
            row for row in post_rows
            if hexadecimal(row, "mask") & (1 << bit)
            and (post_state_time < 0 or integer(row, "time") <= post_state_time)
        ]
        for owner, bit in owner_bits.items()
    }
    owner_bitmap = sum((1 << index) for index, owner in enumerate(contract["owner_order"]) if owner_rows[owner])
    candidate = next(
        (row for row in contract["candidates"] if int(row["owner_bitmap"]) == owner_bitmap),
        None,
    )
    if missing_enabled:
        decision = "EVIDENCE_INCOMPLETE"
        reason = "target instance lacks required ENABLED records"
    elif errors:
        decision = "EVIDENCE_INCOMPLETE"
        reason = "target clear-window correlation failed"
    elif candidate is None:
        decision = "EVIDENCE_INCOMPLETE"
        reason = "accepted-write owner bitmap is undeclared"
    else:
        decision = candidate["root_cause_class"]
        reason = "exact target clear-to-post window matches one declared accepted-write owner bitmap"
    return {
        "schema": "conv-native-four-lane-p33-target-epoch-write-owner-decision-v1",
        "decision": decision,
        "reason": reason,
        "matching_candidate_ids": [] if candidate is None or decision == "EVIDENCE_INCOMPLETE" else [candidate["candidate_id"]],
        "target_parent": target_parent,
        "target_clear_time": None if clear_time < 0 else clear_time,
        "target_final_time": None if final_time < 0 else final_time,
        "target_post_state_time": None if post_state_time < 0 else post_state_time,
        "accepted_write_owner_bitmap": owner_bitmap,
        "accepted_write_owner_rows": owner_rows,
        "target_window_rows": post_rows,
        "target_trigger_rows": clear_rows + final_rows,
        "enabled_boundaries": sorted(enabled),
        "missing_enabled_boundaries": missing_enabled,
        "raw_record_count": raw_count,
        "target_record_count": len(target_rows),
        "errors": errors,
        "natural_terminal_claimed": False,
        "formal_d_claimed": False,
        "claim_boundary": "Exact target and one clear-to-post window only; no natural terminal, formal D, E3, E4 or E5 claim.",
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
