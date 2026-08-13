#!/usr/bin/env python3
"""Correlate p32 Buffer5 source-bound records by exact instance and epoch."""

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


def evaluate(log: Path, contract: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    target_parent = contract["target_parent"]
    required_boundaries = set(contract["required_boundaries"])
    target_rows: list[dict[str, str]] = []
    all_record_count = 0
    for line_number, line in enumerate(log.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        row, error = parse_line(line)
        if error:
            errors.append(f"line {line_number}: {error}")
            continue
        if row is None:
            continue
        all_record_count += 1
        if normalize_parent(row["instance"]) == target_parent:
            target_rows.append(row)
    enabled = {row["boundary"] for row in target_rows if row["kind"] == "ENABLED"}
    missing_enabled = sorted(required_boundaries - enabled)
    triggers = [row for row in target_rows if row["kind"] == "TRIGGER"]
    by_boundary = {
        boundary: [row for row in triggers if row["boundary"] == boundary]
        for boundary in required_boundaries
    }
    clear_rows = by_boundary[contract["clear_boundary"]]
    final_rows = by_boundary[contract["final_boundary"]]
    if len(clear_rows) != 1:
        errors.append(f"target clear trigger count is {len(clear_rows)}, expected 1")
    if len(final_rows) != 1:
        errors.append(f"target final trigger count is {len(final_rows)}, expected 1")
    clear_time = integer(clear_rows[0], "time") if len(clear_rows) == 1 else -1
    final_time = integer(final_rows[0], "time") if len(final_rows) == 1 else -1
    state_rows = [
        row
        for boundary in contract["post_state_boundaries"]
        for row in by_boundary[boundary]
        if clear_time >= 0 and final_time >= 0 and clear_time < integer(row, "time") <= final_time
    ]
    out_of_epoch_state_rows = [
        row
        for boundary in contract["post_state_boundaries"]
        for row in by_boundary[boundary]
        if not (clear_time >= 0 and final_time >= 0 and clear_time < integer(row, "time") <= final_time)
    ]
    if clear_time >= 0 and final_time >= 0 and clear_time >= final_time:
        errors.append("target clear/final temporal order is invalid")
    if len(state_rows) > 1:
        errors.append("multiple target post-clear state classes occur in one epoch")
    if out_of_epoch_state_rows:
        errors.append("target post-state evidence escapes the bounded clear-to-final epoch")
    observed_boundary = state_rows[0]["boundary"] if len(state_rows) == 1 else None
    candidate = next(
        (item for item in contract["candidates"] if item["observed_boundary"] == observed_boundary),
        None,
    )
    if missing_enabled:
        decision = "EVIDENCE_INCOMPLETE"
        reason = "target instance lacks required ENABLED records"
    elif errors:
        decision = "EVIDENCE_INCOMPLETE"
        reason = "target instance/epoch correlation failed"
    elif candidate is None:
        decision = "EVIDENCE_INCOMPLETE"
        reason = "no declared target post-clear candidate matches"
    else:
        decision = candidate["root_cause_class"]
        reason = "exact target parent and ordered clear->post-state->final epoch match one candidate"
    return {
        "schema": "conv-native-four-lane-p32-target-epoch-decision-v1",
        "decision": decision,
        "reason": reason,
        "matching_candidate_ids": [] if candidate is None or decision == "EVIDENCE_INCOMPLETE" else [candidate["candidate_id"]],
        "target_parent": target_parent,
        "target_clear_time": None if clear_time < 0 else clear_time,
        "target_final_time": None if final_time < 0 else final_time,
        "observed_post_state_boundary": observed_boundary,
        "target_state_rows": state_rows,
        "out_of_epoch_target_state_rows": out_of_epoch_state_rows,
        "target_trigger_rows": triggers,
        "enabled_boundaries": sorted(enabled),
        "missing_enabled_boundaries": missing_enabled,
        "raw_record_count": all_record_count,
        "target_record_count": len(target_rows),
        "errors": errors,
        "natural_terminal_claimed": False,
        "formal_d_claimed": False,
        "claim_boundary": "Exact target-instance and one bounded clear-to-final epoch only; no natural terminal, formal D, E3, E4 or E5 claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    report = evaluate(args.log, contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": report["decision"], "errors": len(report["errors"]), "output": str(args.output)}, sort_keys=True))
    return 0 if report["decision"] != "EVIDENCE_INCOMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
