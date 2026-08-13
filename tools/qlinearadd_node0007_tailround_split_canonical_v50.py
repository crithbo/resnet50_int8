#!/usr/bin/env python3
"""Canonical one-stage progress decision for the QAdd tail-round split."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


BASE = re.compile(r"^(?P<time>\d+)\s+\|\s+(?P<event>[A-Z0-9_]+)\s+\|\s*(?P<body>.*)$")
QUALIFIED = (
    "mse0_addr", "mse0_req", "mse0_meta", "mse0_consume", "mse0_buf",
    "ga_in", "ga_out", "buf5_wr", "buf5_rd", "bag_enq", "bag_deq",
    "rdag_enq", "rdag_deq", "rdag_rreq", "wr_req", "wr_prepared",
    "wr_ob_enq0", "wr_ob_enq1", "wr_ob_deq0", "wr_ob_deq1",
    "mse4_req0", "mse4_req1", "mse4_wdata0", "mse4_wdata1",
)


def integer(token: str) -> int:
    return int(token, 16) if token.lower().startswith("0x") else int(token, 10)


def fields(body: str) -> dict[str, int]:
    return {key: integer(value) for key, value in re.findall(r"(\w+)=(0x[0-9a-fA-F]+|\d+)", body)}


def decide_text(text: str, stall_window_cycles: int = 1_048_576) -> dict[str, Any]:
    starts: list[dict[str, int]] = []
    finishes: list[dict[str, int]] = []
    flow: list[dict[str, int]] = []
    state: list[dict[str, int]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        match = BASE.match(line)
        if not match:
            continue
        row = {"line": line_no, "time": int(match["time"]), **fields(match["body"])}
        event = match["event"]
        if event == "EXEC_START": starts.append(row)
        elif event == "COMP_FINISH": finishes.append(row)
        elif event == "TAILROUND_FLOW": flow.append(row)
        elif event == "TAILROUND_STATE": state.append(row)
    ordered_complete = len(starts) == 1 and len(finishes) == 1
    monotonic = all(all(b.get(k, 0) >= a.get(k, 0) for k in QUALIFIED) for a, b in zip(flow, flow[1:]))
    advancing = sum(any(b.get(k, 0) > a.get(k, 0) for k in QUALIFIED) for a, b in zip(flow, flow[1:]))
    frozen = sum(all(b.get(k, 0) == a.get(k, 0) for k in QUALIFIED) for a, b in zip(flow, flow[1:]))
    marker = "# QADD_TAILROUND_FLOW_V47" in text
    if not marker or len(starts) != 1 or not flow:
        decision, boundary, reason = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE", "TAILROUND_SPLIT_OBSERVER_BINDING_OR_SCOPE", "marker, one-stage start scope, or flow snapshots absent"
    elif ordered_complete:
        decision, boundary, reason = "TAILROUND_SPLIT_NATURAL_TERMINAL_OBSERVED", "OP_TAIL_ROUND_COMP_FINISH", "the isolated tail-round stage reached COMP_FINISH"
    elif not monotonic:
        decision, boundary, reason = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE", "TAILROUND_QUALIFIED_COUNTER_REGRESSION", "a stage-local qualified counter regressed"
    elif frozen >= 3:
        decision, boundary, reason = "LONG_RUNNING_HANG_AT_OP_TAIL_ROUND", "AFTER_LAST_TAILROUND_QUALIFIED_ADVANCE", "three or more complete stall windows had no qualified advance"
    elif advancing:
        decision, boundary, reason = "STILL_PROGRESSING_NOT_FINISHED", "AFTER_LAST_TAILROUND_QUALIFIED_ADVANCE", "qualified tail-round transactions advanced but terminal is absent"
    else:
        decision, boundary, reason = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE", "TAILROUND_QUALIFIED_PROGRESS_ABSENT", "insufficient qualified snapshots to adjudicate"
    record: dict[str, Any] = {
        "schema": "qlinearadd-node0007-tailround-split-canonical-v50",
        "decision": decision, "reason": reason, "boundary": boundary,
        "claim_boundary": "isolated tail_round diagnostic; not upstream producer/barrier/lifetime or E3/E4/E5",
        "ordered_scope": {"expected_starts": 1, "observed_starts": len(starts), "observed_finishes": len(finishes), "ordered_complete": ordered_complete},
        "qualified": {"counter_names": list(QUALIFIED), "snapshot_count": len(flow), "monotonic": monotonic, "advancing_windows": advancing, "frozen_windows": frozen, "stall_window_cycles": stall_window_cycles, "level_is_progress": False, "last_snapshot": ({k: flow[-1].get(k, 0) for k in QUALIFIED} if flow else {})},
        "state": {"snapshot_count": len(state), "last_snapshot": state[-1] if state else {}, "excluded_from_progress": True},
    }
    record["content_digest"] = {"algorithm": "sha256", "scope": "canonical_record_without_content_digest", "value": hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    return record


def self_test() -> dict[str, Any]:
    start = "1 | EXEC_START | stage=1"
    base = "mse0_addr=1 mse0_req=1 mse0_meta=1 mse0_consume=1 mse0_buf=1 ga_in=0 ga_out=0 buf5_wr=0 buf5_rd=0 bag_enq=0 bag_deq=0 rdag_enq=0 rdag_deq=0 rdag_rreq=0 wr_req=0 wr_prepared=0 wr_ob_enq0=0 wr_ob_enq1=0 wr_ob_deq0=0 wr_ob_deq1=0 mse4_req0=02 mse4_req1=1 mse4_wdata0=0 mse4_wdata1=0"
    cases = {
        "zero_padded_decimal_and_stable_level": "# QADD_TAILROUND_FLOW_V47\n" + start + "\n10 | TAILROUND_FLOW | " + base + "\n11 | TAILROUND_STATE | bag_full=1\n12 | TAILROUND_FLOW | " + base + "\n13 | TAILROUND_FLOW | " + base + "\n14 | TAILROUND_FLOW | " + base + "\n15 | TAILROUND_FLOW | " + base,
        "simultaneous_events": "# QADD_TAILROUND_FLOW_V47\n" + start + "\n10 | TAILROUND_FLOW | " + base + "\n11 | TAILROUND_FLOW | " + base.replace("ga_in=0 ga_out=0", "ga_in=1 ga_out=1"),
        "terminal": "# QADD_TAILROUND_FLOW_V47\n" + start + "\n10 | TAILROUND_FLOW | " + base + "\n20 | COMP_FINISH | stage=1",
        "wrong_scope": "# QADD_TAILROUND_FLOW_V47\n" + start + "\n2 | EXEC_START | stage=2\n10 | TAILROUND_FLOW | " + base,
    }
    expected = {"zero_padded_decimal_and_stable_level": "LONG_RUNNING_HANG_AT_OP_TAIL_ROUND", "simultaneous_events": "STILL_PROGRESSING_NOT_FINISHED", "terminal": "TAILROUND_SPLIT_NATURAL_TERMINAL_OBSERVED", "wrong_scope": "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"}
    observed = {name: decide_text(value)["decision"] for name, value in cases.items()}
    return {"pass": observed == expected, "observed": observed, "expected": expected}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observer-log", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    result = self_test() if args.self_test else decide_text(args.observer_log.read_text(encoding="utf-8", errors="replace"))
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("pass", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
