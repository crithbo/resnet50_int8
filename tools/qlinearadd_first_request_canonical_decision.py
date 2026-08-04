from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "qlinearadd-first-request-canonical-decision-v1"
MARKER = "# Native NDP return observer v4"
BASE_EVENTS = {"EXEC_START", "HEARTBEAT", "COMP_FINISH"}
BASE_COUNTERS = ("gexec", "req", "rdata", "wdata")
CHAIN_COUNTERS = (
    "slice_start",
    "lc2_hs",
    "lc4_hs",
    "lc6_hs",
    "lc13_hs",
    "lc18_hs",
    "mse0_in0_hs",
    "mse0_in1_hs",
    "mse0_in2_hs",
    "mse0_queue_wr",
    "mse0_ag_hs",
    "mse0_req_enq",
    "mse4_in0_hs",
    "mse4_in1_hs",
    "mse4_in2_hs",
    "mse4_queue_wr",
)
CHAIN_LEVEL_FIELDS = (
    "lc_enable",
    "lc_valid",
    "lc_ready",
    "mse0_in_valid",
    "mse0_in_ready",
    "mse0_match",
    "mse0_empty",
    "mse0_full",
    "mse0_ag_valid",
    "mse0_ag_ready",
    "mse0_req_enq_valid",
    "mse0_req_enq_ready",
    "mse4_in_valid",
    "mse4_in_ready",
    "mse4_match",
    "mse4_empty",
    "mse4_full",
)
BASE_RE = re.compile(
    r"^(?P<time>\d+)\s+\|\s+"
    r"(?P<event>EXEC_START|HEARTBEAT|COMP_FINISH)\s+\|\s+"
    r"(?P<body>.+)$"
)
CHAIN_RE = re.compile(
    r"^(?P<time>\d+)\s+\|\s+FIRST_REQUEST_CHAIN\s+\|\s+(?P<body>.+)$"
)


class CanonicalDecisionError(ValueError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _tokens(body: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in body.split():
        if "=" not in token:
            raise CanonicalDecisionError(f"malformed observer token: {token}")
        key, value = token.split("=", 1)
        if key in result:
            raise CanonicalDecisionError(f"duplicate observer field: {key}")
        result[key] = value
    return result


def _integer(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise CanonicalDecisionError(
            f"observer integer is malformed: {value}"
        ) from exc


def _integer_list(value: str, length: int) -> list[int]:
    parts = value.split(",")
    if len(parts) != length:
        raise CanonicalDecisionError(
            f"observer list length differs: expected {length}, got {len(parts)}"
        )
    return [_integer(part) for part in parts]


def parse_base_samples(observer_text: str) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    required = {
        "slice",
        "active_cycles",
        "gexec",
        "gconfig",
        "req",
        "rdata",
        "wdata",
        "buf4_wr",
        "buf4_rd",
        "buf5_wr",
        "buf5_rd",
    }
    for line_number, line in enumerate(observer_text.splitlines(), start=1):
        match = BASE_RE.fullmatch(line)
        if match is None:
            continue
        fields = _tokens(match.group("body"))
        if set(fields) != required:
            raise CanonicalDecisionError(
                "base observer summary field exact-set differs"
            )
        samples.append(
            {
                "line_number": line_number,
                "time": int(match.group("time")),
                "event": match.group("event"),
                "slice": _integer(fields["slice"]),
                "active_cycles": _integer(fields["active_cycles"]),
                "counters": {
                    name: _integer(fields[name]) for name in BASE_COUNTERS
                },
            }
        )
    return samples


def parse_chain_samples(observer_text: str) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    required = {
        "slice",
        "active_cycles",
        "slice_start",
        "lc_enable",
        "lc_valid",
        "lc_ready",
        "lc_hs",
        "mse0_in_valid",
        "mse0_in_ready",
        "mse0_in_hs",
        "mse0_match",
        "mse0_empty",
        "mse0_full",
        "mse0_queue_wr",
        "mse0_ag_valid",
        "mse0_ag_ready",
        "mse0_ag_hs",
        "mse0_req_enq_valid",
        "mse0_req_enq_ready",
        "mse0_req_enq",
        "mse4_in_valid",
        "mse4_in_ready",
        "mse4_in_hs",
        "mse4_match",
        "mse4_empty",
        "mse4_full",
        "mse4_queue_wr",
    }
    for line_number, line in enumerate(observer_text.splitlines(), start=1):
        match = CHAIN_RE.fullmatch(line)
        if match is None:
            continue
        fields = _tokens(match.group("body"))
        if set(fields) != required:
            raise CanonicalDecisionError(
                "first-request observer field exact-set differs"
            )
        lc_hs = _integer_list(fields["lc_hs"], 5)
        mse0_hs = _integer_list(fields["mse0_in_hs"], 3)
        mse4_hs = _integer_list(fields["mse4_in_hs"], 3)
        counters = {
            "slice_start": _integer(fields["slice_start"]),
            "lc2_hs": lc_hs[0],
            "lc4_hs": lc_hs[1],
            "lc6_hs": lc_hs[2],
            "lc13_hs": lc_hs[3],
            "lc18_hs": lc_hs[4],
            "mse0_in0_hs": mse0_hs[0],
            "mse0_in1_hs": mse0_hs[1],
            "mse0_in2_hs": mse0_hs[2],
            "mse0_queue_wr": _integer(fields["mse0_queue_wr"]),
            "mse0_ag_hs": _integer(fields["mse0_ag_hs"]),
            "mse0_req_enq": _integer(fields["mse0_req_enq"]),
            "mse4_in0_hs": mse4_hs[0],
            "mse4_in1_hs": mse4_hs[1],
            "mse4_in2_hs": mse4_hs[2],
            "mse4_queue_wr": _integer(fields["mse4_queue_wr"]),
        }
        levels = {
            name: _integer(fields[name]) for name in CHAIN_LEVEL_FIELDS
        }
        samples.append(
            {
                "line_number": line_number,
                "time": int(match.group("time")),
                "slice": _integer(fields["slice"]),
                "active_cycles": _integer(fields["active_cycles"]),
                "counters": counters,
                "levels": levels,
            }
        )
    return samples


def _first_request_boundary(
    counters: dict[str, int],
) -> tuple[str, str]:
    if counters["slice_start"] == 0:
        return (
            "SEM_EXEC_START_TO_SLICE_START_RUN",
            "execution command was observed but actual slice_start_run never fired",
        )
    if counters["lc4_hs"] == 0:
        return (
            "SLICE_START_RUN_TO_PHYSICAL_LC4_OUTER_HANDSHAKE",
            "actual slice start fired but mapped outer physical LC4 never handshook",
        )
    if counters["lc2_hs"] == 0 or counters["lc6_hs"] == 0:
        missing = ",".join(
            name
            for name in ("lc2_hs", "lc6_hs")
            if counters[name] == 0
        )
        return (
            "PHYSICAL_LC4_TO_INNER_LC2_LC6_HANDSHAKE",
            f"outer LC4 advanced but mapped inner handshake is absent: {missing}",
        )
    if counters["lc13_hs"] == 0 or counters["lc18_hs"] == 0:
        missing = ",".join(
            name
            for name in ("lc13_hs", "lc18_hs")
            if counters[name] == 0
        )
        return (
            "INNER_LC2_LC6_TO_LEAF_LC13_LC18_HANDSHAKE",
            f"upstream LCs advanced but mapped leaf handshake is absent: {missing}",
        )
    missing_mse0 = [
        name
        for name in ("mse0_in0_hs", "mse0_in1_hs", "mse0_in2_hs")
        if counters[name] == 0
    ]
    if missing_mse0:
        return (
            "LEAF_LC_LCPE_TO_SELECTED_MSE0_INDEX_INPUT_HANDSHAKE",
            "selected MSE0 index input handshake is absent: "
            + ",".join(missing_mse0),
        )
    if counters["mse0_queue_wr"] == 0:
        return (
            "MSE0_INDEX_INPUT_TO_MATCH_QUEUE_WRITE",
            "all selected MSE0 index inputs advanced but no matched queue write occurred",
        )
    if counters["mse0_ag_hs"] == 0:
        return (
            "MSE0_MATCH_QUEUE_TO_ADDRESS_GENERATOR_HANDSHAKE",
            "MSE0 matched queue wrote but address generator never accepted an entry",
        )
    if counters["mse0_req_enq"] == 0:
        return (
            "MSE0_ADDRESS_GENERATOR_TO_FIRST_REQUEST_ENQUEUE",
            "MSE0 address generator advanced but no qualified request enqueue occurred",
        )
    return (
        "FIRST_REQUEST_ENQUEUE_TO_BASE_REQUEST_ACCEPTANCE",
        "a local first-request enqueue occurred but the base accepted-request counter did not advance",
    )


def decide(
    observer_payload: bytes,
    *,
    stall_window_cycles: int,
    minimum_monotonic_windows: int,
) -> dict[str, Any]:
    text = observer_payload.decode("utf-8", errors="replace")
    marker_present = MARKER in text
    base = parse_base_samples(text)
    chain = parse_chain_samples(text)
    heartbeats = [sample for sample in base if sample["event"] == "HEARTBEAT"]
    finish = [sample for sample in base if sample["event"] == "COMP_FINISH"]

    monotonic = True
    window_records: list[dict[str, Any]] = []
    consecutive_advancing = 0
    max_consecutive_advancing = 0
    flat_start: int | None = None
    for index, (before, after) in enumerate(zip(chain, chain[1:]), start=1):
        delta = {
            name: after["counters"][name] - before["counters"][name]
            for name in CHAIN_COUNTERS
        }
        if (
            after["active_cycles"] < before["active_cycles"]
            or any(value < 0 for value in delta.values())
        ):
            monotonic = False
        advanced = any(value > 0 for value in delta.values())
        if advanced:
            consecutive_advancing += 1
            max_consecutive_advancing = max(
                max_consecutive_advancing, consecutive_advancing
            )
            flat_start = after["active_cycles"]
        else:
            consecutive_advancing = 0
            if flat_start is None:
                flat_start = before["active_cycles"]
        window_records.append(
            {
                "index": index,
                "start_line": before["line_number"],
                "end_line": after["line_number"],
                "start_active_cycles": before["active_cycles"],
                "end_active_cycles": after["active_cycles"],
                "qualified_delta": delta,
                "qualified_advanced": advanced,
            }
        )

    last_chain = chain[-1] if chain else None
    last_base = heartbeats[-1] if heartbeats else None
    flat_cycles = (
        0
        if last_chain is None or flat_start is None
        else last_chain["active_cycles"] - flat_start
    )
    if not marker_present:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "OBSERVER_TIME0_BINDING"
        reason = "observer time-0 enabled marker is absent"
    elif not base:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "BASE_OBSERVER_SAMPLE_STREAM"
        reason = "base observer summaries are absent"
    elif not chain:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "FIRST_REQUEST_CHAIN_RETURN_BINDING"
        reason = "first-request chain samples are absent"
    elif not monotonic:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "FIRST_REQUEST_QUALIFIED_COUNTER_MONOTONICITY"
        reason = "a qualified first-request counter or active cycle decreased"
    elif finish:
        decision = "NATURAL_TERMINAL_OBSERVED"
        boundary = "SLICE_CMPT_FINISH"
        reason = "a unique edge-qualified COMP_FINISH summary was observed"
    elif last_base is not None and last_base["counters"]["req"] > 0:
        decision = "FIRST_REQUEST_ACCEPTED_CONTINUE_STANDARD_PROGRESS"
        boundary = "MSE_REQUEST_ACCEPTED"
        reason = "the base qualified accepted-request counter advanced"
    elif max_consecutive_advancing >= minimum_monotonic_windows:
        decision = "STILL_PROGRESSING_NOT_FINISHED"
        boundary, detail = _first_request_boundary(last_chain["counters"])
        reason = (
            f"{max_consecutive_advancing} consecutive windows advanced a "
            f"qualified internal counter; current frontier: {detail}"
        )
    elif flat_cycles >= stall_window_cycles:
        boundary, detail = _first_request_boundary(last_chain["counters"])
        decision = f"LONG_RUNNING_HANG_AT_{boundary}"
        reason = (
            f"{detail}; all qualified internal counters were flat for "
            f"{flat_cycles} cycles, meeting stall_window={stall_window_cycles}"
        )
    else:
        boundary, detail = _first_request_boundary(last_chain["counters"])
        decision = "INSUFFICIENT_FIRST_REQUEST_EVIDENCE"
        reason = (
            f"{detail}; neither the monotonic-progress nor stall-window gate "
            "has been met"
        )

    record = {
        "schema": SCHEMA,
        "version": 1,
        "decision": decision,
        "reason": reason,
        "boundary": boundary,
        "sample_range": {
            "base_sample_count": len(base),
            "heartbeat_count": len(heartbeats),
            "chain_sample_count": len(chain),
            "chain_window_count": len(window_records),
            "first_chain_line": chain[0]["line_number"] if chain else None,
            "last_chain_line": chain[-1]["line_number"] if chain else None,
        },
        "qualified_counter_names": {
            "base": list(BASE_COUNTERS),
            "first_request_chain": list(CHAIN_COUNTERS),
        },
        "counter_snapshot": {
            "base": (
                {name: 0 for name in BASE_COUNTERS}
                if last_base is None
                else dict(last_base["counters"])
            ),
            "first_request_chain": (
                {name: 0 for name in CHAIN_COUNTERS}
                if last_chain is None
                else dict(last_chain["counters"])
            ),
            "last_level_snapshot_not_used_as_progress": (
                {name: None for name in CHAIN_LEVEL_FIELDS}
                if last_chain is None
                else dict(last_chain["levels"])
            ),
            "max_consecutive_advancing_windows": max_consecutive_advancing,
            "flat_qualified_cycles": flat_cycles,
        },
        "windows": window_records,
        "content_summary": {
            "observer_sha256": _sha256(observer_payload),
            "marker_present": marker_present,
            "qualified_monotonic": monotonic,
            "stall_window_cycles": stall_window_cycles,
            "minimum_monotonic_windows": minimum_monotonic_windows,
            "summary_only_lines_ignored": sum(
                1 for line in text.splitlines() if "| SUMMARY_ONLY |" in line
            ),
        },
    }
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
    if record["qualified_counter_names"] != {
        "base": list(BASE_COUNTERS),
        "first_request_chain": list(CHAIN_COUNTERS),
    }:
        raise CanonicalDecisionError("qualified counter set differs")
    snapshot = record["counter_snapshot"]
    if set(snapshot["base"]) != set(BASE_COUNTERS):
        raise CanonicalDecisionError("base counter snapshot differs")
    if set(snapshot["first_request_chain"]) != set(CHAIN_COUNTERS):
        raise CanonicalDecisionError("chain counter snapshot differs")
    if set(snapshot["last_level_snapshot_not_used_as_progress"]) != set(
        CHAIN_LEVEL_FIELDS
    ):
        raise CanonicalDecisionError("level snapshot differs")
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
    expected = _sha256(
        json.dumps(
            digest_source, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )
    if digest["value"] != expected:
        raise CanonicalDecisionError("canonical content digest mismatch")
    for window in record["windows"]:
        if set(window["qualified_delta"]) != set(CHAIN_COUNTERS):
            raise CanonicalDecisionError("window counter delta differs")


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


def _failure_record(
    reason: str,
    boundary: str,
    observer_payload: bytes,
    stall_window_cycles: int,
    minimum_monotonic_windows: int,
) -> dict[str, Any]:
    empty = (
        f"{MARKER} enabled\n"
        "0 | EXEC_START | slice=0 active_cycles=0 gexec=0 gconfig=0 "
        "req=0 rdata=0 wdata=0 buf4_wr=0 buf4_rd=0 buf5_wr=0 buf5_rd=0\n"
    ).encode()
    record = decide(
        empty,
        stall_window_cycles=stall_window_cycles,
        minimum_monotonic_windows=minimum_monotonic_windows,
    )
    record["decision"] = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
    record["reason"] = reason
    record["boundary"] = boundary
    record["content_summary"]["observer_sha256"] = _sha256(observer_payload)
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
    payload = args.observer_log.read_bytes() if args.observer_log.is_file() else b""
    try:
        record = decide(
            payload,
            stall_window_cycles=stall_window,
            minimum_monotonic_windows=minimum_windows,
        )
    except CanonicalDecisionError as exc:
        record = _failure_record(
            str(exc),
            "FIRST_REQUEST_CHAIN_CANONICAL_PARSER",
            payload,
            stall_window,
            minimum_windows,
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
