#!/usr/bin/env python3
"""Close one serialized-Conv observer-only event stream without reducing it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    identity = (args.package_id, args.execution_id, args.attempt_id)
    signals = contract["signals"]
    widths = {item["signal_id"]: item["width_bits"] for item in signals}
    errors: list[str] = []
    rows: list[dict[str, object]] = []
    last_time = 0
    last_values: dict[str, str] = {}
    if args.chunk.is_file():
        for line_number, line in enumerate(args.chunk.read_text(encoding="utf-8", errors="strict").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: {exc}")
                continue
            if not isinstance(row, dict):
                errors.append(f"line {line_number}: row is not an object")
                continue
            if tuple(row.get(key) for key in ("package_id", "execution_id", "attempt_id")) != identity:
                errors.append(f"line {line_number}: identity drift")
            if row.get("seq") != len(rows):
                errors.append(f"line {line_number}: sequence gap")
            sim_time = row.get("sim_time")
            if not isinstance(sim_time, int) or sim_time < last_time:
                errors.append(f"line {line_number}: nonordered simulation time")
            else:
                last_time = sim_time
            if row.get("record_type") == "EVENT":
                signal_id = row.get("signal_id")
                value = row.get("value_4state")
                if signal_id not in widths or not isinstance(value, str) or len(value) != widths.get(signal_id):
                    errors.append(f"line {line_number}: signal/value width mismatch")
                else:
                    last_values[str(signal_id)] = value.upper()
            rows.append(row)
    else:
        errors.append("observer chunk is absent")

    if args.simulation_started == "true":
        # Persist an explicit live-exit record for every disposition.  Timeout,
        # signal and nonzero exits therefore never depend on a simulator final block.
        rows.append({
            "record_type": "PARTIAL_EXIT", "package_id": args.package_id,
            "execution_id": args.execution_id, "attempt_id": args.attempt_id,
            "seq": len(rows), "sim_time": last_time, "timescale": "1ps",
            "signal_id": "__exit__", "width_bits": 1,
            "value_4state": "0" if args.exit_code == 0 else "1",
        })
        # Duplicate the last known actual value of every catalog signal as the
        # exact end-state ledger.  This does not invent a value or discard the
        # prior transition stream.
        for signal in signals:
            signal_id = signal["signal_id"]
            value = last_values.get(signal_id)
            if value is None:
                errors.append(f"missing first/end value for {signal_id}")
                continue
            rows.append({
                "record_type": "EVENT", "package_id": args.package_id,
                "execution_id": args.execution_id, "attempt_id": args.attempt_id,
                "seq": len(rows), "sim_time": last_time, "timescale": "1ps",
                "signal_id": signal_id, "width_bits": signal["width_bits"],
                "value_4state": value,
            })

    chunk_data = ("\n".join(compact(row) for row in rows) + ("\n" if rows else "")).encode("utf-8")
    atomic(args.chunk, chunk_data)
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    catalog = {
        "schema": "server-observer-signal-catalog-v1", "package_id": args.package_id,
        "execution_id": args.execution_id, "attempt_id": args.attempt_id,
        "source_bound": True, "derived_expected_equation": False,
        "signals": signals,
    }
    matrix = {
        "boundary_observations": contract["boundary_observations"],
        "candidates": contract["candidates"],
    }
    matrix_sha = digest(canonical(matrix))
    candidate_ids = sorted(item["candidate_id"] for item in contract["candidates"])
    index = {
        "schema": "server-observer-event-index-v1", "package_id": args.package_id,
        "execution_id": args.execution_id, "attempt_id": args.attempt_id,
        "chunks": [{"path": contract["return_members"]["chunk_prefix"] + args.chunk.name,
                    "bytes": len(chunk_data), "sha256": digest(chunk_data),
                    "sampling": False, "truncated": False}],
        "candidate_ids": candidate_ids, "candidate_boundary_matrix_sha256": matrix_sha,
        "event_count_cap": None, "byte_cap": None, "sampling": False, "truncated": False,
        "end_state": last_values,
    }
    process = json.loads(args.process_receipt.read_text(encoding="utf-8")) if args.process_receipt.is_file() else {}
    heartbeat_rows = []
    if args.heartbeat_log.is_file():
        for line in args.heartbeat_log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                heartbeat_rows.append(json.loads(line))
    observed = [row.get("simulation_time") for row in heartbeat_rows if isinstance(row.get("simulation_time"), int)]
    heartbeat = {
        "schema": "server-observer-sim-time-heartbeat-v1", "package_id": args.package_id,
        "execution_id": args.execution_id, "attempt_id": args.attempt_id,
        "rows": heartbeat_rows, "simulation_time_progress_observed": bool(observed and max(observed) > min(observed)),
        "last_simulation_time": max(observed) if observed else None, "timescale": "1ps",
    }
    actual_argv = json.loads(args.actual_argv.read_text(encoding="utf-8"))
    sim_exit = {
        "schema": "server-observer-sim-exit-v1", "package_id": args.package_id,
        "execution_id": args.execution_id, "attempt_id": args.attempt_id,
        "simulation_started": args.simulation_started == "true", "exit_code": args.exit_code,
        "signal": args.signal, "timed_out": args.timed_out == "true",
        "natural_terminal": args.exit_code == 0 and args.signal == "NONE",
        "last_simulation_time": last_time,
    }
    complete = (
        args.simulation_started == "true" and not errors
        and process.get("process_tree_reaped") is True
        and heartbeat["simulation_time_progress_observed"] is True
        and actual_argv.get("source_identity_status") == "COMPLETE"
    )
    decision = {
        "schema": "server-observer-wide-causal-decision-v1", "package_id": args.package_id,
        "execution_id": args.execution_id, "attempt_id": args.attempt_id,
        "candidate_ids_covered": candidate_ids, "candidate_boundary_matrix_sha256": matrix_sha,
        "diagnostic_evidence_complete": complete,
        "classification": "RETURN_REQUIRES_FAMILY_SIGNAL_INTERPRETATION" if complete else "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "errors": errors,
        "claim_boundary": "Transport/integrity decision only; no DUT verdict or derived expected equation.",
    }
    for name, value in (
        ("OBSERVER_SIGNAL_CATALOG.json", catalog), ("OBSERVER_EVENT_INDEX.json", index),
        ("SIM_TIME_HEARTBEAT.json", heartbeat), ("SIM_EXIT_RECEIPT.json", sim_exit),
        ("OBSERVER_DECISION.json", decision),
    ):
        atomic(output / name, canonical(value))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
