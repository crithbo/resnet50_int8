from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


BASE = re.compile(
    r"^(?P<time>\d+)\s+\|\s+"
    r"(?P<event>EXEC_START|HEARTBEAT|COMP_FINISH)\s+\|\s*(?P<body>.*)$"
)
QUALIFIED = (
    "gexec",
    "gconfig",
    "req",
    "rdata",
    "wdata",
    "buf4_wr",
    "buf4_rd",
    "buf5_wr",
    "buf5_rd",
)


def fields(body: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for token in body.split():
        if "=" in token:
            key, value = token.split("=", 1)
            try:
                result[key] = int(value, 0)
            except ValueError:
                pass
    return result


def decide(observer: Path, contract: Path) -> dict[str, Any]:
    text = observer.read_text(encoding="utf-8", errors="replace")
    cfg = json.loads(contract.read_text(encoding="utf-8"))
    parsed = [
        {
            "line": line_no,
            "time": int(match["time"]),
            "event": match["event"],
            **fields(match["body"]),
        }
        for line_no, line in enumerate(text.splitlines(), 1)
        if (match := BASE.match(line))
    ]
    starts = [item for item in parsed if item["event"] == "EXEC_START"]
    finishes = [item for item in parsed if item["event"] == "COMP_FINISH"]
    beats = [item for item in parsed if item["event"] == "HEARTBEAT"]
    one_stage = len(starts) == 1
    monotonic = all(
        after.get("active_cycles", 0) >= before.get("active_cycles", 0)
        and all(after.get(key, 0) >= before.get(key, 0) for key in QUALIFIED)
        for before, after in zip(beats, beats[1:])
    )
    advancing = []
    for before, after in zip(beats, beats[1:]):
        delta = {
            key: after.get(key, 0) - before.get(key, 0)
            for key in QUALIFIED
        }
        advancing.append(
            {
                "start_active_cycles": before.get("active_cycles", 0),
                "end_active_cycles": after.get("active_cycles", 0),
                "qualified_delta": delta,
                "qualified_advanced": any(value > 0 for value in delta.values()),
            }
        )
    stall_window = int(cfg["stall_window_cycles"])
    flat_cycles = 0
    if beats:
        last_advance = beats[0].get("active_cycles", 0)
        for window in advancing:
            if window["qualified_advanced"]:
                last_advance = window["end_active_cycles"]
        flat_cycles = beats[-1].get("active_cycles", 0) - last_advance

    marker = "# Native NDP return observer v4" in text
    if not marker or not one_stage:
        decision, boundary, reason = (
            "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
            "B_DEQUANT_BASE_OBSERVER_BINDING",
            "base observer marker or unique isolated-stage start is absent",
        )
    elif finishes and finishes[-1]["line"] > starts[-1]["line"]:
        decision, boundary, reason = (
            "B_DEQUANT_CONTROL_COMPLETED",
            "OP_B_DEQUANT_COMP_FINISH",
            "the isolated B-dequant control reached qualified COMP_FINISH",
        )
    elif not monotonic:
        decision, boundary, reason = (
            "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
            "B_DEQUANT_BASE_COUNTER_MONOTONICITY",
            "a base qualified counter regressed",
        )
    elif flat_cycles >= stall_window:
        decision, boundary, reason = (
            "LONG_RUNNING_HANG_AT_B_DEQUANT_BASE_FRONTIER",
            "OP_B_DEQUANT_AFTER_LAST_BASE_QUALIFIED_EVENT",
            "base qualified counters were flat for the declared stall window",
        )
    elif any(item["qualified_advanced"] for item in advancing):
        decision, boundary, reason = (
            "B_DEQUANT_CONTROL_PROGRESS_NOT_TERMINAL",
            "OP_B_DEQUANT_AFTER_BASE_QUALIFIED_PROGRESS",
            "base qualified counters advanced without COMP_FINISH",
        )
    else:
        decision, boundary, reason = (
            "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
            "B_DEQUANT_BASE_QUALIFIED_EVENT_ABSENT",
            "no usable base qualified progress window was returned",
        )
    record: dict[str, Any] = {
        "schema": "qlinearadd-node0007-b-dequant-control-canonical-v22",
        "version": 1,
        "decision": decision,
        "boundary": boundary,
        "reason": reason,
        "ordered_final_scope": {
            "expected_stage": "op_b_dequant",
            "expected_stage_count": 1,
            "one_stage_bound": one_stage,
            "base_last_event": parsed[-1]["event"] if parsed else None,
            "natural_segment_terminal_requires_comp_finish": True,
        },
        "content_summary": {
            "marker_present": marker,
            "heartbeat_samples": len(beats),
            "qualified_monotonic": monotonic,
            "advancing_windows": sum(
                item["qualified_advanced"] for item in advancing
            ),
            "flat_qualified_cycles": flat_cycles,
            "stall_window_cycles": stall_window,
            "level_is_progress": False,
        },
        "qualified_counter_names": list(QUALIFIED),
        "counter_snapshot": (
            {key: beats[-1].get(key, 0) for key in QUALIFIED} if beats else {}
        ),
        "windows": advancing,
    }
    digest = hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    record["content_digest"] = {
        "algorithm": "sha256",
        "scope": "canonical_record_without_content_digest",
        "value": digest,
    }
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observer-log", type=Path, required=True)
    parser.add_argument("--progress-contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = decide(args.observer_log, args.progress_contract)
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except Exception as exc:
        print(f"canonical decision failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
