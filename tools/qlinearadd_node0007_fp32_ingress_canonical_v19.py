from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "qlinearadd-node0007-fp32-ingress-canonical-v19"
MARKER = "# QADD_FP32_INGRESS_OBSERVER_V19"
QUALIFIED = (
    "mse0_req",
    "mse1_req",
    "mse0_rdata",
    "mse1_rdata",
    "mse0_buf",
    "mse1_buf",
    "buf0_wr",
    "buf2_wr",
    "buf0_arm_req",
    "buf2_arm_req",
    "buf0_array",
    "buf2_array",
    "ga0_capture",
    "ga1_capture",
    "ga_pair",
    "ga_accept",
    "ga_output",
)
LEVELS = ("buf_valid", "buf_arm_ready")
PAIRED_PROGRESS = (
    ("mse_req_pair", "mse0_req", "mse1_req"),
    ("mse_rdata_pair", "mse0_rdata", "mse1_rdata"),
    ("mse_buffer_pair", "mse0_buf", "mse1_buf"),
    ("buffer_write_pair", "buf0_wr", "buf2_wr"),
    ("buffer_arm_pair", "buf0_arm_req", "buf2_arm_req"),
    ("buffer_array_pair", "buf0_array", "buf2_array"),
    ("ga_capture_pair", "ga0_capture", "ga1_capture"),
)
SCALAR_PROGRESS = ("ga_pair", "ga_accept", "ga_output")
RECORD_RE = re.compile(
    r"^(?P<time>\d+)\s+\|\s+QADD_FP32_INGRESS\s+\|\s+(?P<body>.+)$"
)
BASE_RE = re.compile(
    r"^(?P<time>\d+)\s+\|\s+"
    r"(?P<event>EXEC_START|HEARTBEAT|COMP_FINISH)\s+\|"
)


class DecisionError(ValueError):
    pass


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def tokens(body: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in body.split():
        if "=" not in token:
            raise DecisionError(f"malformed token: {token}")
        key, value = token.split("=", 1)
        if key in result:
            raise DecisionError(f"duplicate token: {key}")
        result[key] = value
    return result


def integer(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise DecisionError(f"malformed integer: {value}") from exc


def parse(payload: bytes) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    text = payload.decode("utf-8", errors="replace")
    expected = {"slice", "stage_seq", "snapshot_cycles", *QUALIFIED, *LEVELS}
    samples: list[dict[str, Any]] = []
    base: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        base_match = BASE_RE.match(line)
        if base_match:
            base.append(
                {
                    "line": line_number,
                    "time": int(base_match.group("time")),
                    "event": base_match.group("event"),
                }
            )
        match = RECORD_RE.fullmatch(line)
        if not match:
            continue
        fields = tokens(match.group("body"))
        if set(fields) != expected:
            raise DecisionError("FP32 ingress observer field exact-set differs")
        samples.append(
            {
                "line": line_number,
                "time": int(match.group("time")),
                "slice": integer(fields["slice"]),
                "stage_seq": integer(fields["stage_seq"]),
                "snapshot_cycles": integer(fields["snapshot_cycles"]),
                "qualified": {name: integer(fields[name]) for name in QUALIFIED},
                "levels": {name: integer(fields[name]) for name in LEVELS},
            }
        )
    return text, samples, base


def frontier(counters: dict[str, int]) -> tuple[str, str]:
    paired = (
        ("mse0_req", "mse1_req", "MSE0_MSE1_REQUEST_ACCEPT"),
        ("mse0_rdata", "mse1_rdata", "MSE0_MSE1_RDATA_ACCEPT"),
        ("mse0_buf", "mse1_buf", "MSE0_MSE1_TO_BUFFER_ACCEPT"),
        ("buf0_wr", "buf2_wr", "BUFFER0_BUFFER2_WRITE_ACCEPT"),
        ("buf0_arm_req", "buf2_arm_req", "BUFFER0_BUFFER2_ARM_READ_ACCEPT"),
        ("buf0_array", "buf2_array", "BUFFER0_BUFFER2_ARRAY_DELIVERY"),
        ("ga0_capture", "ga1_capture", "GA_DUAL_OPERAND_CAPTURE"),
    )
    for left, right, boundary in paired:
        if counters[left] == 0 or counters[right] == 0:
            missing = ",".join(
                name for name in (left, right) if counters[name] == 0
            )
            return boundary, f"qualified paired frontier is missing {missing}"
    if counters["ga_pair"] == 0:
        return "GA_DUAL_TAG_MASK_MATCH", "both ingress paths advanced but no qualified GA pair match occurred"
    if counters["ga_accept"] == 0:
        return "GA_FIRST_CONSUMER_ACCEPT", "GA pair matched but the consumer accepted no input"
    if counters["ga_output"] == 0:
        return "GA_FIRST_OUTPUT", "GA accepted input but emitted no output"
    return "POST_GA_FIRST_OUTPUT", "the first qualified GA output was observed"


def progress_metrics(counters: dict[str, int]) -> dict[str, int]:
    result = {
        name: min(counters[left], counters[right])
        for name, left, right in PAIRED_PROGRESS
    }
    result.update({name: counters[name] for name in SCALAR_PROGRESS})
    return result


def decide(
    payload: bytes,
    *,
    stall_window_cycles: int,
    minimum_progress_windows: int,
) -> dict[str, Any]:
    text, samples, base = parse(payload)
    marker_present = MARKER in text
    last_stage = max((sample["stage_seq"] for sample in samples), default=None)
    scoped = (
        []
        if last_stage is None
        else [sample for sample in samples if sample["stage_seq"] == last_stage]
    )
    windows: list[dict[str, Any]] = []
    monotonic = True
    max_advancing = 0
    advancing = 0
    flat_start: int | None = None
    for index, (before, after) in enumerate(zip(scoped, scoped[1:]), start=1):
        qualified_delta = {
            name: after["qualified"][name] - before["qualified"][name]
            for name in QUALIFIED
        }
        before_progress = progress_metrics(before["qualified"])
        after_progress = progress_metrics(after["qualified"])
        delta = {
            name: after_progress[name] - before_progress[name]
            for name in before_progress
        }
        if after["snapshot_cycles"] < before["snapshot_cycles"] or any(
            value < 0 for value in qualified_delta.values()
        ):
            monotonic = False
        advanced = any(value > 0 for value in delta.values())
        if advanced:
            advancing += 1
            max_advancing = max(max_advancing, advancing)
            flat_start = after["snapshot_cycles"]
        else:
            advancing = 0
            if flat_start is None:
                flat_start = before["snapshot_cycles"]
        windows.append(
            {
                "index": index,
                "start_line": before["line"],
                "end_line": after["line"],
                "start_snapshot_cycles": before["snapshot_cycles"],
                "end_snapshot_cycles": after["snapshot_cycles"],
                "qualified_delta": qualified_delta,
                "paired_progress_delta": delta,
                "qualified_advanced": advanced,
            }
        )
    last = scoped[-1] if scoped else None
    flat_cycles = (
        0
        if last is None or flat_start is None
        else last["snapshot_cycles"] - flat_start
    )
    ordered_terminal = bool(base and base[-1]["event"] == "COMP_FINISH")
    if not marker_present:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "FP32_INGRESS_FEATURE_TIME0_MARKER"
        reason = "runtime-enabled FP32 ingress marker is absent"
    elif not scoped:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "FP32_INGRESS_RETURN_BINDING"
        reason = "no FP32 ingress snapshots were returned"
    elif not monotonic:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "FP32_INGRESS_QUALIFIED_COUNTER_MONOTONICITY"
        reason = "a qualified counter or source snapshot cycle decreased in the final stage"
    elif ordered_terminal:
        decision = "NATURAL_TERMINAL_OBSERVED"
        boundary = "ORDERED_FINAL_STAGE_COMP_FINISH"
        reason = "the final ordered base event is COMP_FINISH"
    elif last["qualified"]["ga_output"] > 0:
        decision = "FP32_ADD_FIRST_OUTPUT_OBSERVED_CONTINUE_STANDARD_PROGRESS"
        boundary = "GA_FIRST_OUTPUT"
        reason = "the first qualified GA output advanced"
    elif max_advancing >= minimum_progress_windows:
        boundary, detail = frontier(last["qualified"])
        decision = "STILL_PROGRESSING_NOT_FINISHED"
        reason = f"{max_advancing} consecutive final-stage windows advanced; {detail}"
    elif flat_cycles >= stall_window_cycles:
        boundary, detail = frontier(last["qualified"])
        decision = f"LONG_RUNNING_HANG_AT_{boundary}"
        reason = (
            f"{detail}; final-stage qualified counters were flat for "
            f"{flat_cycles} source/snapshot cycles"
        )
    else:
        boundary, detail = frontier(last["qualified"])
        decision = "INSUFFICIENT_FP32_INGRESS_EVIDENCE"
        reason = detail

    record: dict[str, Any] = {
        "schema": SCHEMA,
        "version": 1,
        "decision": decision,
        "reason": reason,
        "boundary": boundary,
        "ordered_final_scope": {
            "last_stage_seq": last_stage,
            "base_last_event": base[-1]["event"] if base else None,
            "natural_terminal_requires_final_event": True,
        },
        "sample_range": {
            "all_stage_samples": len(samples),
            "final_stage_samples": len(scoped),
            "window_count": len(windows),
            "first_line": scoped[0]["line"] if scoped else None,
            "last_line": scoped[-1]["line"] if scoped else None,
        },
        "qualified_counter_names": list(QUALIFIED),
        "paired_progress_metric_names": [
            name for name, _, _ in PAIRED_PROGRESS
        ]
        + list(SCALAR_PROGRESS),
        "counter_snapshot": (
            {name: 0 for name in QUALIFIED}
            if last is None
            else dict(last["qualified"])
        ),
        "level_snapshot_not_progress": (
            {name: None for name in LEVELS}
            if last is None
            else dict(last["levels"])
        ),
        "windows": windows,
        "content_summary": {
            "observer_sha256": digest(payload),
            "marker_present": marker_present,
            "qualified_monotonic": monotonic,
            "stall_window_cycles": stall_window_cycles,
            "minimum_progress_windows": minimum_progress_windows,
            "max_consecutive_advancing_windows": max_advancing,
            "flat_qualified_cycles": flat_cycles,
            "individual_mse_levels_or_unpaired_inputs_count_as_progress": False,
        },
    }
    record["content_digest"] = {
        "algorithm": "sha256",
        "scope": "canonical_record_without_content_digest",
        "value": digest(
            json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        ),
    }
    return record


def validate_record(record: dict[str, Any]) -> None:
    required = {
        "schema",
        "version",
        "decision",
        "reason",
        "boundary",
        "ordered_final_scope",
        "sample_range",
        "qualified_counter_names",
        "paired_progress_metric_names",
        "counter_snapshot",
        "level_snapshot_not_progress",
        "windows",
        "content_summary",
        "content_digest",
    }
    if set(record) != required:
        raise DecisionError("canonical record field exact-set differs")
    if record["schema"] != SCHEMA or record["version"] != 1:
        raise DecisionError("canonical schema/version differs")
    if not record["decision"] or not record["reason"] or not record["boundary"]:
        raise DecisionError("canonical decision/reason/boundary is incomplete")
    content = dict(record)
    stored = content.pop("content_digest")
    expected = digest(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    )
    if (
        stored.get("algorithm") != "sha256"
        or stored.get("scope") != "canonical_record_without_content_digest"
        or stored.get("value") != expected
    ):
        raise DecisionError("canonical content digest differs")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observer-log", type=Path, required=True)
    parser.add_argument("--progress-contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        contract = json.loads(args.progress_contract.read_text(encoding="utf-8"))
        payload = (
            args.observer_log.read_bytes()
            if args.observer_log.is_file()
            else b""
        )
        record = decide(
            payload,
            stall_window_cycles=int(contract["stall_window_cycles"]),
            minimum_progress_windows=int(
                contract.get("minimum_monotonic_windows", 3)
            ),
        )
        validate_record(record)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except Exception as exc:
        print(f"canonical decision failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
