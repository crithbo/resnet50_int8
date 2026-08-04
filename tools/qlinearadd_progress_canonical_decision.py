from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "qlinearadd-progress-canonical-decision-v1"
QUALIFIED_COUNTERS = ("gexec", "req", "rdata", "wdata")
RAW_STATE_COUNTERS = ("buf4_wr", "buf4_rd", "buf5_wr", "buf5_rd")
SUMMARY_RE = re.compile(
    r"^(?P<time>\d+)\s+\|\s+"
    r"(?P<event>EXEC_START|HEARTBEAT|COMP_FINISH)\s+\|\s+"
    r"slice=(?P<slice>\d+)\s+"
    r"active_cycles=(?P<active_cycles>\d+)\s+"
    r"gexec=(?P<gexec>\d+)\s+gconfig=(?P<gconfig>\d+)\s+"
    r"req=(?P<req>\d+)\s+rdata=(?P<rdata>\d+)\s+wdata=(?P<wdata>\d+)\s+"
    r"buf4_wr=(?P<buf4_wr>\d+)\s+buf4_rd=(?P<buf4_rd>\d+)\s+"
    r"buf5_wr=(?P<buf5_wr>\d+)\s+buf5_rd=(?P<buf5_rd>\d+)\s*$"
)


class CanonicalDecisionError(ValueError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def parse_samples(observer_text: str) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for line_number, line in enumerate(observer_text.splitlines(), start=1):
        match = SUMMARY_RE.fullmatch(line)
        if match is None:
            continue
        values = match.groupdict()
        sample = {
            "line_number": line_number,
            "time": int(values["time"]),
            "event": values["event"],
            "slice": int(values["slice"]),
            "active_cycles": int(values["active_cycles"]),
            "qualified": {
                name: int(values[name]) for name in QUALIFIED_COUNTERS
            },
            "raw_state": {
                name: int(values[name]) for name in RAW_STATE_COUNTERS
            },
        }
        samples.append(sample)
    return samples


def _deepest_boundary(delta: dict[str, int]) -> str:
    if delta["wdata"] > 0:
        return "MSE_WRITE_DATA_ACCEPTED"
    if delta["rdata"] > 0:
        return "MSE_READ_DATA_ACCEPTED"
    if delta["req"] > 0:
        return "MSE_REQUEST_ACCEPTED"
    if delta["gexec"] > 0:
        return "START_COMP_ACCEPTED"
    return "NO_QUALIFIED_EVENT_ADVANCE"


def decide(
    observer_payload: bytes,
    *,
    stall_window_cycles: int,
    minimum_monotonic_windows: int,
) -> dict[str, Any]:
    text = observer_payload.decode("utf-8", errors="replace")
    marker_present = "# Native NDP return observer v4" in text
    samples = parse_samples(text)
    heartbeats = [sample for sample in samples if sample["event"] == "HEARTBEAT"]
    finish = [sample for sample in samples if sample["event"] == "COMP_FINISH"]

    monotonic = True
    windows: list[dict[str, Any]] = []
    consecutive_advancing = 0
    max_consecutive_advancing = 0
    last_advance_boundary = "START_COMP_OR_OBSERVER_BINDING"
    flat_start_cycles: int | None = None
    for index, (before, after) in enumerate(zip(heartbeats, heartbeats[1:]), start=1):
        delta = {
            name: after["qualified"][name] - before["qualified"][name]
            for name in QUALIFIED_COUNTERS
        }
        if any(value < 0 for value in delta.values()):
            monotonic = False
        advanced = any(value > 0 for value in delta.values())
        boundary = _deepest_boundary(delta)
        if advanced:
            consecutive_advancing += 1
            max_consecutive_advancing = max(
                max_consecutive_advancing, consecutive_advancing
            )
            flat_start_cycles = after["active_cycles"]
            last_advance_boundary = boundary
        else:
            consecutive_advancing = 0
            if flat_start_cycles is None:
                flat_start_cycles = before["active_cycles"]
        windows.append(
            {
                "index": index,
                "start_line": before["line_number"],
                "end_line": after["line_number"],
                "start_time": before["time"],
                "end_time": after["time"],
                "start_active_cycles": before["active_cycles"],
                "end_active_cycles": after["active_cycles"],
                "qualified_delta": delta,
                "qualified_advanced": advanced,
                "deepest_advanced_boundary": boundary,
            }
        )

    last = heartbeats[-1] if heartbeats else None
    flat_cycles = (
        0
        if last is None or flat_start_cycles is None
        else last["active_cycles"] - flat_start_cycles
    )
    if not marker_present:
        decision = "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS"
        reason = "observer time-0 enabled marker is absent"
        boundary = "OBSERVER_TIME0_BINDING"
    elif not monotonic:
        decision = "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS"
        reason = "a qualified counter decreased between heartbeat windows"
        boundary = "QUALIFIED_COUNTER_MONOTONICITY"
    elif finish:
        decision = "NATURAL_TERMINAL_OBSERVED"
        reason = "a unique COMP_FINISH edge-qualified summary was observed"
        boundary = "SLICE_CMPT_FINISH"
    elif max_consecutive_advancing >= minimum_monotonic_windows:
        decision = "STILL_PROGRESSING_NOT_FINISHED"
        reason = (
            f"{max_consecutive_advancing} consecutive heartbeat windows "
            "advanced at least one qualified handshake counter"
        )
        boundary = last_advance_boundary
    elif last is not None and flat_cycles >= stall_window_cycles:
        decision = f"LONG_RUNNING_HANG_AT_{last_advance_boundary}"
        reason = (
            f"all qualified counters remained flat for {flat_cycles} active "
            f"cycles, meeting stall_window={stall_window_cycles}"
        )
        boundary = last_advance_boundary
    else:
        decision = "INSUFFICIENT_PROGRESS_EVIDENCE"
        reason = (
            "fewer than the required consecutive qualified-progress windows "
            "and no complete qualified-counter stall window"
        )
        boundary = (
            last_advance_boundary if heartbeats else "OBSERVER_SAMPLE_STREAM"
        )

    last_qualified = (
        {name: 0 for name in QUALIFIED_COUNTERS}
        if last is None
        else dict(last["qualified"])
    )
    last_raw_state = (
        {name: 0 for name in RAW_STATE_COUNTERS}
        if last is None
        else dict(last["raw_state"])
    )
    record = {
        "schema": SCHEMA,
        "version": 1,
        "decision": decision,
        "reason": reason,
        "boundary": boundary,
        "sample_range": {
            "first_line": samples[0]["line_number"] if samples else None,
            "last_line": samples[-1]["line_number"] if samples else None,
            "first_time": samples[0]["time"] if samples else None,
            "last_time": samples[-1]["time"] if samples else None,
            "sample_count": len(samples),
            "heartbeat_count": len(heartbeats),
            "window_count": len(windows),
        },
        "qualified_counter_names": list(QUALIFIED_COUNTERS),
        "counter_snapshot": {
            "qualified": last_qualified,
            "raw_state_not_used_for_progress": last_raw_state,
            "max_consecutive_advancing_windows": max_consecutive_advancing,
            "flat_qualified_cycles": flat_cycles,
        },
        "windows": windows,
        "content_summary": {
            "observer_sha256": _sha256(observer_payload),
            "marker_present": marker_present,
            "qualified_monotonic": monotonic,
            "stall_window_cycles": stall_window_cycles,
            "minimum_monotonic_windows": minimum_monotonic_windows,
            "summary_only_lines_ignored": sum(
                1
                for line in text.splitlines()
                if "| SUMMARY_ONLY |" in line
            ),
        },
    }
    digest_payload = json.dumps(
        record, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    record["content_digest"] = {
        "algorithm": "sha256",
        "scope": "canonical_record_without_content_digest",
        "value": _sha256(digest_payload),
    }
    validate_record(record)
    return record


def validate_record(record: dict[str, Any]) -> None:
    required = {
        "schema",
        "version",
        "decision",
        "reason",
        "boundary",
        "sample_range",
        "qualified_counter_names",
        "counter_snapshot",
        "windows",
        "content_summary",
        "content_digest",
    }
    if set(record) != required:
        raise CanonicalDecisionError("canonical record field exact-set differs")
    if record["schema"] != SCHEMA or record["version"] != 1:
        raise CanonicalDecisionError("canonical schema/version differs")
    if not isinstance(record["decision"], str) or not record["decision"]:
        raise CanonicalDecisionError("canonical decision is absent")
    if not isinstance(record["reason"], str) or not record["reason"].strip():
        raise CanonicalDecisionError("canonical reason is absent")
    if not isinstance(record["boundary"], str) or not record["boundary"].strip():
        raise CanonicalDecisionError("canonical boundary is absent")
    if record["qualified_counter_names"] != list(QUALIFIED_COUNTERS):
        raise CanonicalDecisionError("qualified counter set differs")
    digest = record["content_digest"]
    if (
        not isinstance(digest, dict)
        or set(digest) != {"algorithm", "scope", "value"}
        or digest["algorithm"] != "sha256"
        or digest["scope"] != "canonical_record_without_content_digest"
        or not re.fullmatch(r"[0-9a-f]{64}", str(digest["value"]))
    ):
        raise CanonicalDecisionError("canonical content digest differs")
    digest_source = dict(record)
    digest_source.pop("content_digest")
    expected_digest = _sha256(
        json.dumps(
            digest_source, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )
    if digest["value"] != expected_digest:
        raise CanonicalDecisionError("canonical content digest mismatch")
    snapshot = record["counter_snapshot"]
    if set(snapshot["qualified"]) != set(QUALIFIED_COUNTERS):
        raise CanonicalDecisionError("qualified counter snapshot differs")
    if set(snapshot["raw_state_not_used_for_progress"]) != set(
        RAW_STATE_COUNTERS
    ):
        raise CanonicalDecisionError("raw-state snapshot differs")
    for window in record["windows"]:
        if set(window["qualified_delta"]) != set(QUALIFIED_COUNTERS):
            raise CanonicalDecisionError("window qualified delta differs")


def load_unique_record(payload: bytes) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except Exception as exc:
        raise CanonicalDecisionError(
            "canonical decision payload is not one complete JSON object"
        ) from exc
    if not isinstance(value, dict):
        raise CanonicalDecisionError("multiple/non-object canonical candidates")
    validate_record(value)
    return value


def fail_closed_record(
    *,
    reason: str,
    boundary: str,
    observer_payload: bytes,
    stall_window_cycles: int,
    minimum_monotonic_windows: int,
) -> dict[str, Any]:
    record = decide(
        observer_payload,
        stall_window_cycles=stall_window_cycles,
        minimum_monotonic_windows=minimum_monotonic_windows,
    )
    record["decision"] = "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS"
    record["reason"] = reason
    record["boundary"] = boundary
    record.pop("content_digest")
    record["content_digest"] = {
        "algorithm": "sha256",
        "scope": "canonical_record_without_content_digest",
        "value": _sha256(
            json.dumps(
                record, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ),
    }
    validate_record(record)
    return record


def main() -> int:
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser()
    parser.add_argument("--observer-log", type=Path, required=True)
    parser.add_argument("--progress-contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract = json.loads(args.progress_contract.read_text(encoding="utf-8"))
    stall_window = int(contract["stall_window_cycles"])
    minimum_windows = int(contract["minimum_monotonic_windows_for_progress"])
    if args.observer_log.is_file():
        payload = args.observer_log.read_bytes()
        record = decide(
            payload,
            stall_window_cycles=stall_window,
            minimum_monotonic_windows=minimum_windows,
        )
    else:
        payload = b""
        record = fail_closed_record(
            reason="observer log is absent; no progress decision is publishable",
            boundary="OBSERVER_RETURN_BINDING",
            observer_payload=payload,
            stall_window_cycles=stall_window,
            minimum_monotonic_windows=minimum_windows,
        )
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    load_unique_record(args.output.read_bytes())
    print(json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
