from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

BASE = re.compile(
    r"^(?P<time>\d+)\s+\|\s+"
    r"(?P<event>EXEC_START|HEARTBEAT|COMP_FINISH|FINAL)\s+\|\s*(?P<body>.*)$"
)
QUALIFIED = (
    "gexec", "gconfig", "req", "rdata", "wdata",
    "buf4_wr", "buf4_rd", "buf5_wr", "buf5_rd",
)


def fields(body: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for token in body.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        try:
            result[key] = int(value, 0)
        except ValueError:
            pass
    return result

PAIR = re.compile(r"^(?P<time>\d+)\s+\|\s+C_PAIR_SNAPSHOT\s+\|\s*(?P<body>.*)$")
PAIR_EFFECTIVE = ("mse0_qwr", "mse1_qwr", "mse4_qwr", "mse0_ag", "mse1_ag", "ga_in", "ga_out")
PAIR_RAW = ("mse0_hs0", "mse0_hs1", "mse0_hs2", "mse1_hs0", "mse1_hs1", "mse1_hs2", "mse4_hs0", "mse4_hs1", "mse4_hs2")


def decide(observer: Path, contract: Path) -> dict[str, Any]:
    text = observer.read_text(encoding="utf-8", errors="replace") if observer.is_file() else ""
    cfg = json.loads(contract.read_text(encoding="utf-8"))
    stages = list(cfg["stage_names"])
    lines = text.splitlines()
    parsed = [{"line": n, "time": int(m["time"]), "event": m["event"], **fields(m["body"])} for n, line in enumerate(lines, 1) if (m := BASE.match(line))]
    pairs = [{"line": n, "time": int(m["time"]), **fields(m["body"])} for n, line in enumerate(lines, 1) if (m := PAIR.match(line))]
    starts = [x for x in parsed if x["event"] == "EXEC_START"]
    finishes = [x for x in parsed if x["event"] == "COMP_FINISH"]
    ordered_complete = len(starts) == len(stages) and len(finishes) == len(stages) and all(starts[i]["line"] < finishes[i]["line"] and (i + 1 == len(stages) or finishes[i]["line"] < starts[i + 1]["line"]) for i in range(len(stages)))
    marker = "# Native NDP return observer v4" in text
    pair_marker = "QADD_C_PAIR_DIAG enabled" in text
    pair_monotonic = all(all(b.get(k, 0) >= a.get(k, 0) for k in PAIR_EFFECTIVE + PAIR_RAW) for a, b in zip(pairs, pairs[1:]))
    flat_effective = [all(b.get(k, 0) == a.get(k, 0) for k in PAIR_EFFECTIVE) for a, b in zip(pairs, pairs[1:])]
    raw_advance = [any(b.get(k, 0) > a.get(k, 0) for k in PAIR_RAW) for a, b in zip(pairs, pairs[1:])]
    trailing_stall = 0
    for flat, raw in reversed(list(zip(flat_effective, raw_advance))):
        if flat and raw:
            trailing_stall += 1
        else:
            break
    if not marker or not pair_marker or len(starts) != len(stages) or not pairs:
        decision, boundary, reason = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE", "SPLIT_C_PAIR_OBSERVER_BINDING_OR_STAGE_SCOPE", "base/pair marker, exact stage starts, or pair snapshots are absent"
    elif ordered_complete:
        decision, boundary, reason = "SPLIT_SEGMENT_COMPLETED", "OP_FP32_ADD_COMP_FINISH", "all four ordered stages reached qualified COMP_FINISH"
    elif not pair_monotonic:
        decision, boundary, reason = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE", "SPLIT_C_PAIR_COUNTER_MONOTONICITY", "a source-clock qualified pair counter regressed"
    elif trailing_stall >= int(cfg.get("minimum_pair_stall_windows", 3)):
        decision, boundary, reason = "LONG_RUNNING_HANG", "OP_FP32_ADD_MSE_PAIRING_BEFORE_GA_INPUT_ACCEPT", "raw MSE input handshakes continued while MSE queue/AG and GA accept/output counters were flat for the required trailing windows"
    else:
        decision, boundary, reason = "SPLIT_SEGMENT_PROGRESS_NOT_TERMINAL", "OP_FP32_ADD_PAIR_CHAIN_STILL_AMBIGUOUS", "pair evidence has not reached terminal or the declared hang conjunction"
    record: dict[str, Any] = {
        "schema": "qlinearadd-node0007-split-c-pair-canonical-v27",
        "version": 1,
        "segment_id": "C",
        "decision": decision,
        "boundary": boundary,
        "reason": reason,
        "ordered_final_scope": {"stage_names": stages, "expected_stage_count": len(stages), "observed_start_count": len(starts), "observed_finish_count": len(finishes), "ordered_complete": ordered_complete, "natural_segment_terminal_requires_all_comp_finish": True},
        "pair_scope": {"snapshot_count": len(pairs), "source_clock": "clk_sg qualified counters; clk_db snapshots only", "effective_counters": list(PAIR_EFFECTIVE), "raw_handshake_counters": list(PAIR_RAW), "pair_monotonic": pair_monotonic, "trailing_stall_windows": trailing_stall, "required_stall_windows": int(cfg.get("minimum_pair_stall_windows", 3)), "last_snapshot": pairs[-1] if pairs else {}},
        "content_summary": {"marker_present": marker, "pair_marker_present": pair_marker, "level_is_progress": False, "stall_window_cycles": int(cfg["stall_window_cycles"])},
    }
    record["content_digest"] = {"algorithm": "sha256", "scope": "canonical_record_without_content_digest", "value": hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    return record


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--observer-log", type=Path, required=True)
    p.add_argument("--progress-contract", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    try:
        value = decide(a.observer_log, a.progress_contract)
        a.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    except Exception as exc:
        print(f"split-C pair canonical failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
