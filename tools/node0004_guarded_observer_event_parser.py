#!/usr/bin/env python3
"""Stream-close node0004 observer evidence without a whole-file rewrite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def compact(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def hash_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return size, digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--chunk", type=Path, required=True)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--signal", required=True)
    parser.add_argument("--timed-out", choices=("true", "false"), required=True)
    parser.add_argument("--simulation-started", choices=("true", "false"), required=True)
    parser.add_argument("--process-receipt", type=Path, required=True)
    parser.add_argument("--heartbeat-log", type=Path, required=True)
    parser.add_argument("--actual-argv", type=Path, required=True)
    parser.add_argument("--guard-receipt", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    contract = load_json(args.contract)
    signals = contract["signals"]
    widths = {item["signal_id"]: item["width_bits"] for item in signals}
    identity = (args.package_id, args.execution_id, args.attempt_id)
    errors: list[str] = []
    last_time = 0
    last_values: dict[str, str] = {}
    count = 0
    ended_with_newline = False
    if args.chunk.is_file():
        with args.chunk.open("rb") as stream:
            for number, raw in enumerate(stream, 1):
                ended_with_newline = raw.endswith(b"\n")
                try:
                    row = json.loads(raw.decode("utf-8", errors="strict"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    errors.append(f"line {number}: {error}")
                    continue
                if tuple(row.get(key) for key in ("package_id", "execution_id", "attempt_id")) != identity:
                    errors.append(f"line {number}: identity drift")
                if row.get("seq") != count:
                    errors.append(f"line {number}: sequence gap")
                sim_time = row.get("sim_time")
                if not isinstance(sim_time, int) or sim_time < last_time:
                    errors.append(f"line {number}: nonordered simulation time")
                else:
                    last_time = sim_time
                if row.get("record_type") == "EVENT":
                    sid = row.get("signal_id")
                    value = row.get("value_4state")
                    if sid not in widths or not isinstance(value, str) or len(value) != widths.get(sid):
                        errors.append(f"line {number}: signal/value width mismatch")
                    else:
                        last_values[str(sid)] = value.upper()
                count += 1
    else:
        errors.append("observer chunk is absent")

    guard = load_json(args.guard_receipt) if args.guard_receipt else {}
    if guard.get("guard_triggered") is True:
        errors.append(f"operational guard stop: {guard.get('stop_reason')}")
    append_allowed = args.chunk.is_file() and ended_with_newline
    if args.simulation_started == "true" and append_allowed:
        with args.chunk.open("ab") as stream:
            stream.write(compact({
                "record_type": "PARTIAL_EXIT", "package_id": args.package_id,
                "execution_id": args.execution_id, "attempt_id": args.attempt_id,
                "seq": count, "sim_time": last_time, "timescale": "1ps",
                "signal_id": "__exit__", "width_bits": 1,
                "value_4state": "0" if args.exit_code == 0 else "1",
            }))
            count += 1
            for signal in signals:
                sid = signal["signal_id"]
                value = last_values.get(sid)
                if value is None:
                    errors.append(f"missing first/end value for {sid}")
                    continue
                stream.write(compact({
                    "record_type": "EVENT", "package_id": args.package_id,
                    "execution_id": args.execution_id, "attempt_id": args.attempt_id,
                    "seq": count, "sim_time": last_time, "timescale": "1ps",
                    "signal_id": sid, "width_bits": signal["width_bits"], "value_4state": value,
                }))
                count += 1
            stream.flush()
            os.fsync(stream.fileno())
    elif args.simulation_started == "true":
        errors.append("observer chunk lacks a complete final newline; no silent repair performed")

    chunk_bytes, chunk_sha = hash_file(args.chunk) if args.chunk.is_file() else (0, hashlib.sha256(b"").hexdigest())
    matrix = {"boundary_observations": contract["boundary_observations"], "candidates": contract["candidates"]}
    matrix_sha = hashlib.sha256(canonical(matrix)).hexdigest()
    candidate_ids = sorted(item["candidate_id"] for item in contract["candidates"])
    process = load_json(args.process_receipt)
    heartbeat_rows = []
    if args.heartbeat_log.is_file():
        with args.heartbeat_log.open("r", encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    heartbeat_rows.append(json.loads(line))
    observed = [row.get("simulation_time") for row in heartbeat_rows if isinstance(row.get("simulation_time"), int)]
    actual_argv = load_json(args.actual_argv)
    complete = (
        args.simulation_started == "true" and not errors
        and process.get("process_tree_reaped") is True
        and bool(observed and max(observed) > min(observed))
        and actual_argv.get("source_identity_status") == "COMPLETE"
        and guard.get("guard_triggered") is not True
    )
    output = args.output_dir
    values = {
        "OBSERVER_SIGNAL_CATALOG.json": {
            "schema": "server-observer-signal-catalog-v1", "package_id": args.package_id,
            "execution_id": args.execution_id, "attempt_id": args.attempt_id,
            "source_bound": True, "derived_expected_equation": False, "signals": signals,
        },
        "OBSERVER_EVENT_INDEX.json": {
            "schema": "server-observer-event-index-v1", "package_id": args.package_id,
            "execution_id": args.execution_id, "attempt_id": args.attempt_id,
            "chunks": [{"path": contract["return_members"]["chunk_prefix"] + args.chunk.name,
                        "bytes": chunk_bytes, "sha256": chunk_sha, "sampling": False, "truncated": False}],
            "candidate_ids": candidate_ids, "candidate_boundary_matrix_sha256": matrix_sha,
            "event_count_cap": None, "byte_cap": None, "sampling": False, "truncated": False,
            "end_state": last_values, "operational_guard_receipt": guard,
        },
        "SIM_TIME_HEARTBEAT.json": {
            "schema": "server-observer-sim-time-heartbeat-v1", "package_id": args.package_id,
            "execution_id": args.execution_id, "attempt_id": args.attempt_id,
            "rows": heartbeat_rows, "simulation_time_progress_observed": bool(observed and max(observed) > min(observed)),
            "last_simulation_time": max(observed) if observed else None, "timescale": "1ps",
        },
        "SIM_EXIT_RECEIPT.json": {
            "schema": "server-observer-sim-exit-v1", "package_id": args.package_id,
            "execution_id": args.execution_id, "attempt_id": args.attempt_id,
            "simulation_started": args.simulation_started == "true", "exit_code": args.exit_code,
            "signal": args.signal, "timed_out": args.timed_out == "true",
            "natural_terminal": args.exit_code == 0 and args.signal == "NONE" and guard.get("guard_triggered") is not True,
            "last_simulation_time": last_time, "operational_guard_stop": guard.get("stop_reason"),
        },
        "OBSERVER_DECISION.json": {
            "schema": "server-observer-wide-causal-decision-v1", "package_id": args.package_id,
            "execution_id": args.execution_id, "attempt_id": args.attempt_id,
            "candidate_ids_covered": candidate_ids, "candidate_boundary_matrix_sha256": matrix_sha,
            "diagnostic_evidence_complete": complete,
            "classification": "RETURN_REQUIRES_FAMILY_SIGNAL_INTERPRETATION" if complete else "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "errors": errors,
            "claim_boundary": "Streaming transport/integrity decision only; no DUT verdict.",
        },
    }
    for name, value in values.items():
        atomic(output / name, canonical(value))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
