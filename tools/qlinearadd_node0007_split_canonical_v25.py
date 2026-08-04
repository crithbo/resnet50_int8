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
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        try:
            result[key] = int(value, 0)
        except ValueError:
            pass
    return result


def decide(observer: Path, contract: Path) -> dict[str, Any]:
    text = (
        observer.read_text(encoding="utf-8", errors="replace")
        if observer.is_file()
        else ""
    )
    cfg = json.loads(contract.read_text(encoding="utf-8"))
    stages = list(cfg["stage_names"])
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
    ordered_complete = (
        len(starts) == len(stages)
        and len(finishes) == len(stages)
        and all(
            starts[index]["line"] < finishes[index]["line"]
            and (
                index + 1 == len(stages)
                or finishes[index]["line"] < starts[index + 1]["line"]
            )
            for index in range(len(stages))
        )
    )
    stage_windows: list[dict[str, Any]] = []
    monotonic = True
    advancing_windows = 0
    for index, start in enumerate(starts):
        end_line = (
            starts[index + 1]["line"] if index + 1 < len(starts) else 1 << 60
        )
        local = [
            beat for beat in beats if start["line"] < beat["line"] < end_line
        ]
        local_monotonic = all(
            after.get("active_cycles", 0) >= before.get("active_cycles", 0)
            and all(after.get(key, 0) >= before.get(key, 0) for key in QUALIFIED)
            for before, after in zip(local, local[1:])
        )
        local_advancing = sum(
            any(after.get(key, 0) > before.get(key, 0) for key in QUALIFIED)
            for before, after in zip(local, local[1:])
        )
        monotonic = monotonic and local_monotonic
        advancing_windows += local_advancing
        stage_windows.append(
            {
                "stage_index": index,
                "stage": stages[index] if index < len(stages) else None,
                "heartbeat_samples": len(local),
                "qualified_monotonic": local_monotonic,
                "advancing_windows": local_advancing,
                "last_snapshot": (
                    {key: local[-1].get(key, 0) for key in QUALIFIED}
                    if local
                    else {}
                ),
            }
        )
    marker = "# Native NDP return observer v4" in text
    if not marker or len(starts) != len(stages):
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "SPLIT_OBSERVER_BINDING_OR_STAGE_SCOPE"
        reason = "observer marker or exact ordered EXEC_START count is absent"
    elif ordered_complete:
        decision = "SPLIT_SEGMENT_COMPLETED"
        boundary = f"{stages[-1].upper()}_COMP_FINISH"
        reason = "every ordered stage reached qualified COMP_FINISH"
    elif not monotonic:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "SPLIT_QUALIFIED_COUNTER_MONOTONICITY"
        reason = "a qualified counter regressed within a stage"
    elif advancing_windows:
        decision = "SPLIT_SEGMENT_PROGRESS_NOT_TERMINAL"
        boundary = "AFTER_LAST_QUALIFIED_ADVANCE"
        reason = "qualified counters advanced but the ordered segment did not finish"
    else:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "SPLIT_QUALIFIED_PROGRESS_ABSENT"
        reason = "no qualified progress window is available"
    record: dict[str, Any] = {
        "schema": "qlinearadd-node0007-split-canonical-v25",
        "version": 1,
        "segment_id": cfg["segment_id"],
        "decision": decision,
        "boundary": boundary,
        "reason": reason,
        "ordered_final_scope": {
            "stage_names": stages,
            "expected_stage_count": len(stages),
            "observed_start_count": len(starts),
            "observed_finish_count": len(finishes),
            "ordered_complete": ordered_complete,
            "natural_segment_terminal_requires_all_comp_finish": True,
        },
        "content_summary": {
            "marker_present": marker,
            "heartbeat_samples": len(beats),
            "qualified_monotonic": monotonic,
            "advancing_windows": advancing_windows,
            "level_is_progress": False,
            "stall_window_cycles": int(cfg["stall_window_cycles"]),
        },
        "qualified_counter_names": list(QUALIFIED),
        "stage_windows": stage_windows,
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
        print(f"split canonical decision failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
