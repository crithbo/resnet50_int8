from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True
SCHEMA = "gap-node0071-canonical-diagnostic-decision-v1"
VERSION = 1
PREFIX = "CANONICAL_DECISION_JSON="
QUALIFIED_COUNTERS = (
    "gexec_fire",
    "request_handshake",
    "read_data_handshake",
    "write_data_handshake",
    "mse4_request_handshake_ch0",
    "mse4_request_handshake_ch1",
    "mse4_write_data_handshake_ch0",
    "mse4_write_data_handshake_ch1",
)
MAIN = re.compile(
    r"^(?P<time>\d+) \| (?P<event>[^|]+) \| "
    r"slice=(?P<slice>\d+) active_cycles=(?P<active>\d+) "
    r"gexec=(?P<gexec>\d+) gconfig=(?P<gconfig>\d+) "
    r"req=(?P<req>\d+) rdata=(?P<rdata>\d+) "
    r"wdata=(?P<wdata>\d+) "
    r"buf4_wr=\d+ buf4_rd=\d+ buf5_wr=\d+ buf5_rd=\d+$"
)
SG = re.compile(
    r"^(?P<time>\d+) \| SG_COUNTS \| event=(?P<event>\S+) "
    r"ga_input=\d+ ga_output=\d+ "
    r"mse4_req0=(?P<req0>\d+) mse4_req1=(?P<req1>\d+) "
    r"mse4_wdata0=(?P<wdata0>\d+) "
    r"mse4_wdata1=(?P<wdata1>\d+) "
    r"mse4_outstanding0=-?\d+ mse4_outstanding1=-?\d+$"
)


class DecisionError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def parse_summaries(text: str) -> list[dict[str, Any]]:
    partial: dict[tuple[int, str], dict[str, Any]] = {}
    order: list[tuple[int, str]] = []
    for line in text.splitlines():
        main = MAIN.match(line)
        if main:
            key = (int(main["time"]), main["event"])
            if key not in partial:
                order.append(key)
            partial.setdefault(key, {})["main"] = {
                key_name: int(main[group])
                for key_name, group in (
                    ("gexec_fire", "gexec"),
                    ("request_handshake", "req"),
                    ("read_data_handshake", "rdata"),
                    ("write_data_handshake", "wdata"),
                )
            }
            partial[key]["active_cycles"] = int(main["active"])
            continue
        sg = SG.match(line)
        if sg:
            key = (int(sg["time"]), sg["event"])
            if key not in partial:
                order.append(key)
            partial.setdefault(key, {})["sg"] = {
                key_name: int(sg[group])
                for key_name, group in (
                    ("mse4_request_handshake_ch0", "req0"),
                    ("mse4_request_handshake_ch1", "req1"),
                    ("mse4_write_data_handshake_ch0", "wdata0"),
                    ("mse4_write_data_handshake_ch1", "wdata1"),
                )
            }
    records: list[dict[str, Any]] = []
    for key in order:
        value = partial[key]
        if "main" not in value or "sg" not in value:
            continue
        snapshot = {**value["main"], **value["sg"]}
        records.append(
            {
                "time_ps": key[0],
                "event": key[1],
                "active_cycles": value["active_cycles"],
                "qualified": snapshot,
            }
        )
    return records


def delta(
    first: dict[str, int], last: dict[str, int]
) -> dict[str, int]:
    return {key: last[key] - first[key] for key in QUALIFIED_COUNTERS}


def boundary(snapshot: dict[str, int]) -> str:
    if (
        snapshot["mse4_write_data_handshake_ch0"]
        + snapshot["mse4_write_data_handshake_ch1"]
        > 0
    ):
        return "MSE4_WRITE_DATA_ACCEPTED"
    if snapshot["write_data_handshake"] > 0:
        return "ANY_MSE_WRITE_DATA_ACCEPTED"
    if snapshot["read_data_handshake"] > 0:
        return "ANY_MSE_READ_DATA_ACCEPTED"
    if snapshot["request_handshake"] > 0:
        return "ANY_MSE_REQUEST_ACCEPTED"
    if snapshot["gexec_fire"] > 0:
        return "START_COMP_DISPATCH_FIRE"
    return "NO_QUALIFIED_PROGRESS"


def make_decision(
    observer_text: str,
    sim_text: str,
    signal: str,
    simulation_status: int,
    stall_window_cycles: int,
    heartbeat_cycles: int,
) -> dict[str, Any]:
    records = parse_summaries(observer_text)
    natural_terminal = (
        simulation_status == 0
        and "Simulation completed successfully!" in sim_text
    )
    if records:
        start = records[0]
        end = records[-1]
        total_delta = delta(start["qualified"], end["qualified"])
        window_deltas = [
            delta(records[index - 1]["qualified"], records[index]["qualified"])
            for index in range(1, len(records))
        ]
        progress_flags = [
            any(value > 0 for value in item.values())
            for item in window_deltas
        ]
        last_change_index = 0
        for index, changed in enumerate(progress_flags, start=1):
            if changed:
                last_change_index = index
        flat_span_cycles = (
            end["active_cycles"]
            - records[last_change_index]["active_cycles"]
        )
        last_boundary = boundary(end["qualified"])
    else:
        empty = {key: 0 for key in QUALIFIED_COUNTERS}
        start = {
            "time_ps": 0,
            "event": "NONE",
            "active_cycles": 0,
            "qualified": empty,
        }
        end = start
        total_delta = dict(empty)
        progress_flags = []
        flat_span_cycles = 0
        last_boundary = "OBSERVER_SUMMARY_UNAVAILABLE"

    if natural_terminal and records:
        decision = "FUNCTIONAL_EXECUTION_COMPLETED"
        reason = "natural terminal and a complete final qualified snapshot exist"
    elif len(progress_flags) >= 2 and all(progress_flags[-2:]):
        decision = "STILL_PROGRESSING_NOT_FINISHED"
        reason = (
            "qualified handshake/edge counters advanced in each of the "
            "latest two complete windows without natural terminal"
        )
    elif records and flat_span_cycles >= stall_window_cycles:
        decision = f"LONG_RUNNING_HANG_AT_{last_boundary}"
        reason = (
            "no qualified handshake/edge counter advanced for at least "
            "the declared stall window"
        )
    elif records:
        decision = "INSUFFICIENT_PROGRESS_WINDOW"
        reason = (
            "complete qualified snapshots exist but neither two-window "
            "progress nor a full flat stall window is established"
        )
    else:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        reason = (
            "no complete observer summary containing all participating "
            "qualified counters is available"
        )

    payload = {
        "schema": SCHEMA,
        "version": VERSION,
        "decision": decision,
        "reason": reason,
        "boundary": last_boundary,
        "signal": signal,
        "natural_terminal": natural_terminal,
        "sample_range": {
            "first_complete_summary_index": 0 if records else None,
            "last_complete_summary_index":
                len(records) - 1 if records else None,
            "complete_summary_count": len(records),
        },
        "window_range": {
            "start_time_ps": start["time_ps"],
            "end_time_ps": end["time_ps"],
            "span_ps": end["time_ps"] - start["time_ps"],
            "start_active_cycle": start["active_cycles"],
            "end_active_cycle": end["active_cycles"],
            "active_cycle_span":
                end["active_cycles"] - start["active_cycles"],
            "flat_since_last_qualified_progress_cycles":
                flat_span_cycles,
            "stall_window_cycles": stall_window_cycles,
            "heartbeat_cycles": heartbeat_cycles,
        },
        "qualified_counter_snapshot": {
            "participating_counters": list(QUALIFIED_COUNTERS),
            "start": start["qualified"],
            "end": end["qualified"],
            "delta": total_delta,
        },
        "raw_state_excluded_from_progress": [
            "ready",
            "enable",
            "valid_without_handshake",
            "buffer_occupancy",
            "buf4_wr",
            "buf4_rd",
            "buf5_wr",
            "buf5_rd",
            "sg_ga_input",
            "sg_ga_output",
            "deep_level_samples",
        ],
        "content_digest": {
            "observer_sha256": digest_bytes(observer_text.encode("utf-8")),
            "sim_log_sha256": digest_bytes(sim_text.encode("utf-8")),
        },
    }
    digest_payload = dict(payload)
    digest_payload.pop("content_digest")
    payload["content_digest"]["decision_payload_sha256"] = digest_bytes(
        canonical_bytes(digest_payload)
    )
    return payload


def validate_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["canonical candidate is not an object"]
    required = (
        "schema",
        "version",
        "decision",
        "reason",
        "boundary",
        "sample_range",
        "window_range",
        "qualified_counter_snapshot",
        "content_digest",
    )
    for key in required:
        if key not in record:
            errors.append(f"missing required field: {key}")
    if not isinstance(record.get("reason"), str) or not record.get("reason"):
        errors.append("reason is empty or absent")
    if (
        not isinstance(record.get("boundary"), str)
        or not record.get("boundary")
    ):
        errors.append("boundary is empty or absent")
    snapshot = record.get("qualified_counter_snapshot")
    if not isinstance(snapshot, dict) or not all(
        key in snapshot
        for key in ("participating_counters", "start", "end", "delta")
    ):
        errors.append("qualified counter snapshot/delta differs")
    return errors


def validate_decision_stream(text: str) -> dict[str, Any]:
    candidates: list[Any] = []
    parse_errors: list[str] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if not line.startswith(PREFIX):
            continue
        try:
            candidates.append(json.loads(line[len(PREFIX):]))
        except json.JSONDecodeError:
            parse_errors.append(f"invalid JSON candidate at line {index}")
    candidate_errors = [
        error
        for candidate in candidates
        for error in validate_record(candidate)
    ]
    errors = parse_errors + candidate_errors
    if len(candidates) != 1:
        errors.append(
            f"canonical candidate count differs: {len(candidates)}"
        )
    return {
        "valid": not errors,
        "status": (
            "CANONICAL_DECISION_VALID"
            if not errors
            else "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS"
        ),
        "candidate_count": len(candidates),
        "errors": errors,
        "decision": candidates[0] if len(candidates) == 1 else None,
    }


def negative_controls() -> dict[str, Any]:
    summaries = "\n".join(
        [
            (
                f"{time} | HEARTBEAT | slice=0 active_cycles={time} "
                "gexec=1 gconfig=1 req=4 rdata=4 wdata=0 "
                "buf4_wr=999 buf4_rd=999 buf5_wr=999 buf5_rd=999"
            )
            + "\n"
            + (
                f"{time} | SG_COUNTS | event=HEARTBEAT "
                "ga_input=999 ga_output=999 mse4_req0=0 mse4_req1=0 "
                "mse4_wdata0=0 mse4_wdata1=0 "
                "mse4_outstanding0=0 mse4_outstanding1=0"
            )
            for time in (100, 200, 300, 400, 500)
        ]
    )
    raw_high = "\n".join(
        f"{cycle} | RAW_STATE | ready=1 enable=1 valid=1 occupancy=7"
        for cycle in range(64)
    )
    high_record = make_decision(
        raw_high + "\n" + summaries,
        "",
        "INT",
        125,
        1000,
        100,
    )
    progressing = "\n".join(
        (
            f"{active} | HEARTBEAT | slice=0 active_cycles={active} "
            f"gexec=1 gconfig=1 req={count} rdata={count} wdata=0 "
            "buf4_wr=999 buf4_rd=999 buf5_wr=999 buf5_rd=999\n"
            f"{active} | SG_COUNTS | event=HEARTBEAT "
            "ga_input=999 ga_output=999 mse4_req0=0 mse4_req1=0 "
            "mse4_wdata0=0 mse4_wdata1=0 "
            "mse4_outstanding0=0 mse4_outstanding1=0"
        )
        for active, count in ((0, 0), (100, 1), (200, 2))
    )
    still_record = make_decision(
        progressing, "", "INT", 125, 1000, 100
    )
    flat_full_window = "\n".join(
        (
            f"{active} | HEARTBEAT | slice=0 active_cycles={active} "
            "gexec=1 gconfig=1 req=4 rdata=4 wdata=0 "
            "buf4_wr=999 buf4_rd=999 buf5_wr=999 buf5_rd=999\n"
            f"{active} | SG_COUNTS | event=HEARTBEAT "
            "ga_input=999 ga_output=999 mse4_req0=0 mse4_req1=0 "
            "mse4_wdata0=0 mse4_wdata1=0 "
            "mse4_outstanding0=0 mse4_outstanding1=0"
        )
        for active in (0, 500, 1000)
    )
    hang_record = make_decision(
        flat_full_window, "", "INT", 125, 1000, 500
    )
    base = make_decision(summaries, "", "INT", 125, 1000, 100)
    base_line = PREFIX + json.dumps(base, separators=(",", ":"))
    conflict = dict(base)
    conflict["decision"] = "STILL_PROGRESSING_NOT_FINISHED"
    missing_reason = dict(base)
    missing_reason.pop("reason")
    missing_boundary = dict(base)
    missing_boundary.pop("boundary")
    controls = {
        "continuous_high_level": {
            "failed_closed": (
                high_record["decision"] != "STILL_PROGRESSING_NOT_FINISHED"
                and sum(
                    high_record["qualified_counter_snapshot"]["delta"].values()
                )
                == 0
            ),
            "decision": high_record["decision"],
            "qualified_delta":
                high_record["qualified_counter_snapshot"]["delta"],
        },
        "summary_only_append_with_canonical_prefix": {
            "failed_closed": not validate_decision_stream(
                base_line + "\n" + PREFIX + '{"summary":"only"}\n'
            )["valid"],
        },
        "conflicting_double_decision": {
            "failed_closed": not validate_decision_stream(
                base_line
                + "\n"
                + PREFIX
                + json.dumps(conflict, separators=(",", ":"))
                + "\n"
            )["valid"],
        },
        "missing_reason": {
            "failed_closed": not validate_decision_stream(
                PREFIX
                + json.dumps(missing_reason, separators=(",", ":"))
                + "\n"
            )["valid"],
        },
        "missing_boundary": {
            "failed_closed": not validate_decision_stream(
                PREFIX
                + json.dumps(missing_boundary, separators=(",", ":"))
                + "\n"
            )["valid"],
        },
        "nonprefixed_summary_append_does_not_override": {
            "pass": validate_decision_stream(
                base_line + "\nSUMMARY_ONLY decision=HANG\n"
            )["valid"],
        },
        "qualified_two_window_progress_positive": {
            "pass": (
                still_record["decision"]
                == "STILL_PROGRESSING_NOT_FINISHED"
            ),
        },
        "qualified_flat_full_cycle_window_positive": {
            "pass": hang_record["decision"].startswith(
                "LONG_RUNNING_HANG_AT_"
            ),
            "flat_cycles":
                hang_record["window_range"][
                    "flat_since_last_qualified_progress_cycles"
                ],
        },
    }
    if not all(
        value.get("failed_closed", value.get("pass", False))
        for value in controls.values()
    ):
        raise DecisionError("canonical decision negative control failed")
    return controls


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    observe = sub.add_parser("observe")
    observe.add_argument("--observer-log", type=Path, required=True)
    observe.add_argument("--sim-log", type=Path, required=True)
    observe.add_argument("--signal", required=True)
    observe.add_argument("--simulation-status", type=int, required=True)
    observe.add_argument("--stall-window-cycles", type=int, required=True)
    observe.add_argument("--heartbeat-cycles", type=int, required=True)
    observe.add_argument("--output", type=Path, required=True)
    sub.add_parser("self-test")
    args = parser.parse_args()
    if args.command == "self-test":
        result = {
            "schema": "gap-node0071-canonical-decision-self-test-v1",
            "status": "PASS",
            "negative_controls": negative_controls(),
        }
    else:
        observer_text = (
            args.observer_log.read_text(encoding="utf-8", errors="replace")
            if args.observer_log.is_file()
            else ""
        )
        sim_text = (
            args.sim_log.read_text(encoding="utf-8", errors="replace")
            if args.sim_log.is_file()
            else ""
        )
        result = make_decision(
            observer_text,
            sim_text,
            args.signal,
            args.simulation_status,
            args.stall_window_cycles,
            args.heartbeat_cycles,
        )
        errors = validate_record(result)
        if errors:
            raise DecisionError("; ".join(errors))
        args.output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
