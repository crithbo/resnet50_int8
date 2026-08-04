from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


BASE = re.compile(
    r"^(?P<time>\d+)\s+\|\s+"
    r"(?P<event>EXEC_START|HEARTBEAT|COMP_FINISH)\s+\|"
)
SAMPLE = re.compile(
    r"^(?P<time>\d+)\s+\|\s+QADD_FP32_INGRESS\s+\|\s+(?P<body>.+)$"
)
QUALIFIED = (
    "mse0_req",
    "mse0_rdata",
    "mse0_buf",
    "buf0_wr",
    "buf0_arm_req",
    "buf0_array",
    "ga0_capture",
    "ga_accept",
    "ga_output",
)


class DecisionError(ValueError):
    pass


def parse_fields(body: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for token in body.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        result[key] = int(value, 0)
    required = {"stage_seq", "snapshot_cycles", *QUALIFIED}
    if not required <= set(result):
        raise DecisionError(f"sample fields absent: {sorted(required - set(result))}")
    return result


def content_digest(record: dict[str, Any]) -> str:
    payload = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def decide(observer: Path, contract: Path) -> dict[str, Any]:
    text = observer.read_text(encoding="utf-8", errors="replace")
    cfg = json.loads(contract.read_text(encoding="utf-8"))
    marker = "# QADD_FP32_INGRESS_OBSERVER_V19 enabled=1" in text
    base = [
        {"line": index, "time": int(match["time"]), "event": match["event"]}
        for index, line in enumerate(text.splitlines(), 1)
        if (match := BASE.match(line))
    ]
    samples = [
        {"line": index, "time": int(match["time"]), **parse_fields(match["body"])}
        for index, line in enumerate(text.splitlines(), 1)
        if (match := SAMPLE.match(line))
    ]
    starts = [item for item in base if item["event"] == "EXEC_START"]
    finishes = [item for item in base if item["event"] == "COMP_FINISH"]
    one_stage = (
        len(starts) == 1
        and all(item["stage_seq"] == 1 for item in samples)
    )
    monotonic = all(
        after["snapshot_cycles"] >= before["snapshot_cycles"]
        and all(after[key] >= before[key] for key in QUALIFIED)
        for before, after in zip(samples, samples[1:])
    )
    windows = []
    for before, after in zip(samples, samples[1:]):
        delta = {key: after[key] - before[key] for key in QUALIFIED}
        windows.append(
            {
                "start_line": before["line"],
                "end_line": after["line"],
                "start_snapshot_cycles": before["snapshot_cycles"],
                "end_snapshot_cycles": after["snapshot_cycles"],
                "qualified_delta": delta,
                "qualified_advanced": any(value > 0 for value in delta.values()),
            }
        )
    advancing = sum(item["qualified_advanced"] for item in windows)
    stall = int(cfg["stall_window_cycles"])
    flat = 0
    if samples:
        last_advance = samples[0]["snapshot_cycles"]
        for item in windows:
            if item["qualified_advanced"]:
                last_advance = item["end_snapshot_cycles"]
        flat = samples[-1]["snapshot_cycles"] - last_advance

    if not marker or not starts or not one_stage:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "B_DEQUANT_STAGE_IDENTITY"
        reason = "marker/start/one-stage binding is absent or ambiguous"
    elif finishes and finishes[-1]["line"] > starts[-1]["line"]:
        decision = "B_DEQUANT_SEGMENT_COMPLETED"
        boundary = "OP_B_DEQUANT_COMP_FINISH"
        reason = "the isolated B-dequant segment reached qualified COMP_FINISH"
    elif not monotonic:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "B_DEQUANT_COUNTER_MONOTONICITY"
        reason = "a qualified source-domain counter regressed"
    elif flat >= stall:
        decision = "LONG_RUNNING_HANG_AT_B_DEQUANT_QUALIFIED_FRONTIER"
        boundary = "OP_B_DEQUANT_AFTER_LAST_QUALIFIED_EVENT"
        reason = "no qualified event advanced for at least one declared stall window"
    elif advancing:
        decision = "B_DEQUANT_QUALIFIED_PROGRESS_NOT_TERMINAL"
        boundary = "OP_B_DEQUANT_AFTER_QUALIFIED_PROGRESS"
        reason = "qualified B-dequant ingress/GA events advanced without COMP_FINISH"
    else:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "B_DEQUANT_QUALIFIED_EVENT_ABSENT"
        reason = "the isolated stage started but no qualified sample advanced"

    snapshot = (
        {key: samples[-1][key] for key in QUALIFIED} if samples else {}
    )
    record: dict[str, Any] = {
        "schema": "qlinearadd-node0007-b-dequant-canonical-v21",
        "version": 1,
        "decision": decision,
        "reason": reason,
        "boundary": boundary,
        "ordered_final_scope": {
            "expected_stage": "op_b_dequant",
            "expected_stage_count": 1,
            "one_stage_bound": one_stage,
            "base_last_event": base[-1]["event"] if base else None,
            "natural_segment_terminal_requires_comp_finish": True,
        },
        "content_summary": {
            "marker_present": marker,
            "qualified_monotonic": monotonic,
            "sample_count": len(samples),
            "window_count": len(windows),
            "advancing_windows": advancing,
            "flat_qualified_cycles": flat,
            "stall_window_cycles": stall,
            "level_is_progress": False,
        },
        "qualified_counter_names": list(QUALIFIED),
        "counter_snapshot": snapshot,
        "windows": windows,
    }
    record["content_digest"] = {
        "algorithm": "sha256",
        "scope": "canonical_record_without_content_digest",
        "value": content_digest(record),
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
        args.output.parent.mkdir(parents=True, exist_ok=True)
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
