#!/usr/bin/env python3
"""Live safety wrapper for the bounded native-MSE4 TB VCD attempt.

The wrapped generic supervisor owns and reaps the simulator process tree.  This
layer records 30-second runtime samples and independently enforces the three
interval simulation-time freeze, wall, growth, return projection and disk
guards required by the TB-VCD mode.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any


WALL_SECONDS = 3600
INTERVAL_SECONDS = 30
FREEZE_INTERVALS = 3
VCD_BUDGET = 8_000_000_000
RETURN_BUDGET = 10_000_000_000
SOFT_WARNING = 100_000_000
HEARTBEAT = re.compile(
    r"CODEX_TBVCD_HEARTBEAT_V1\s+sim_time=(?P<time>\d+)\s+"
    r"owner_cycles=(?P<cycles>\d+)\s+progress=(?P<progress>\d+)\s+"
    r"state=(?P<state>[0-9a-fA-F]+)\s+global=(?P<global>\d+)\s+"
    r"unresolved_xz=(?P<xz>[01])"
)


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    os.replace(temporary, path)


def latest_heartbeat(log: Path) -> dict[str, Any] | None:
    if not log.is_file():
        return None
    last: dict[str, Any] | None = None
    with log.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            match = HEARTBEAT.search(line)
            if match:
                last = {
                    "sim_time_ticks": int(match.group("time")),
                    "sim_cycles": int(match.group("cycles")),
                    "owner_clock_cycles": int(match.group("cycles")),
                    "causal_progress_events": int(match.group("progress")),
                    "qualified_progress_counters": {"total": int(match.group("progress"))},
                    "causal_state_digest": match.group("state").lower(),
                    "global_progress_witness": {"count": int(match.group("global"))},
                    "unresolved_xz": match.group("xz") == "1",
                }
    return last


def append_sample(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def supervise(args: argparse.Namespace) -> int:
    if not args.simulator_command or args.simulator_command[0] == "--":
        args.simulator_command = args.simulator_command[1:]
    if not args.simulator_command:
        raise ValueError("simulator command is required")
    attempt = args.attempt_root.resolve()
    for candidate in (args.sim_log, args.vcd, args.samples, args.safety_receipt, args.process_receipt):
        candidate.resolve(strict=False).relative_to(attempt)

    command = [
        "python3", str(args.process_supervisor), "supervise",
        "--package-id", args.package_id,
        "--execution-id", args.execution_id,
        "--attempt-id", args.attempt_id,
        "--attempt-root", str(attempt),
        "--cwd", str(args.cwd),
        "--heartbeat-source", str(args.sim_log),
        "--heartbeat-output", str(args.heartbeat_output),
        "--heartbeat-regex", r"CODEX_TBVCD_HEARTBEAT_V1 sim_time=([0-9]+)",
        "--timescale", "1ps",
        "--timeout", str(WALL_SECONDS),
        "--interval", str(INTERVAL_SECONDS),
        "--grace", "30",
        "--receipt", str(args.process_receipt),
        "--", *args.simulator_command,
    ]
    started = time.monotonic()
    child = subprocess.Popen(command, cwd=args.cwd)
    received: int | None = None
    old_handlers: dict[int, Any] = {}

    def handle(signum: int, _frame: Any) -> None:
        nonlocal received
        received = signum

    for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        old_handlers[signum] = signal.signal(signum, handle)

    seq = 0
    previous_time: int | None = None
    freeze_count = 0
    previous_wall = 0.0
    previous_bytes = 0
    stop_reason: str | None = None
    samples: list[dict[str, Any]] = []
    next_sample = started
    try:
        while child.poll() is None:
            now = time.monotonic()
            if received is not None:
                stop_reason = {signal.SIGHUP: "HUP", signal.SIGINT: "INT", signal.SIGTERM: "TERM"}[received]
                child.send_signal(signal.SIGTERM)
                break
            if now >= next_sample:
                wall = now - started
                heartbeat = latest_heartbeat(args.sim_log) or {
                    "sim_time_ticks": 0, "sim_cycles": 0, "owner_clock_cycles": 0,
                    "causal_progress_events": 0, "qualified_progress_counters": {},
                    "causal_state_digest": "absent", "global_progress_witness": {},
                    "unresolved_xz": True,
                }
                size = args.vcd.stat().st_size if args.vcd.is_file() else 0
                delta_wall = max(0.0, wall - previous_wall)
                rate = max(0, size - previous_bytes) / delta_wall if delta_wall else 0.0
                projection = int(size + rate * max(0.0, WALL_SECONDS - wall))
                disk = shutil.disk_usage(args.vcd.parent)
                row = {
                    "seq": seq, "wall_seconds": wall, **heartbeat,
                    "vcd_bytes": size,
                    "vcd_operational_projection_bytes": projection,
                    "return_projection_bytes": projection + 256_000_000,
                    "disk_space_ok": disk.free > max(1_000_000_000, min(RETURN_BUDGET, projection)),
                    "write_ok": args.vcd.parent.is_dir(), "quota_ok": True,
                    "soft_warning_exceeded": size > SOFT_WARNING,
                }
                append_sample(args.samples, row)
                samples.append(row)
                if previous_time is not None and heartbeat["sim_time_ticks"] == previous_time:
                    freeze_count += 1
                elif heartbeat["sim_time_ticks"] != previous_time:
                    freeze_count = 0
                previous_time = heartbeat["sim_time_ticks"]
                previous_wall, previous_bytes = wall, size
                seq += 1
                if freeze_count >= FREEZE_INTERVALS:
                    stop_reason = "SIM_TIME_FREEZE"
                elif wall >= WALL_SECONDS:
                    stop_reason = "WALL_CEILING"
                elif projection >= VCD_BUDGET:
                    stop_reason = "VCD_OPERATIONAL_BUDGET"
                elif projection + 256_000_000 >= RETURN_BUDGET:
                    stop_reason = "RETURN_BUDGET_PROJECTION"
                elif not row["disk_space_ok"]:
                    stop_reason = "DISK_SPACE_FAILURE"
                if stop_reason:
                    child.send_signal(signal.SIGTERM)
                    break
                next_sample = now + INTERVAL_SECONDS
            time.sleep(0.1)

        try:
            child_exit = child.wait(timeout=90)
        except subprocess.TimeoutExpired:
            child.kill()
            child_exit = child.wait(timeout=30)
            stop_reason = stop_reason or "TERM"
    finally:
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)

    if not samples or (time.monotonic() - started) > samples[-1]["wall_seconds"] + 0.1:
        heartbeat = latest_heartbeat(args.sim_log) or {
            "sim_time_ticks": 0, "sim_cycles": 0, "owner_clock_cycles": 0,
            "causal_progress_events": 0, "qualified_progress_counters": {},
            "causal_state_digest": "absent", "global_progress_witness": {},
            "unresolved_xz": True,
        }
        size = args.vcd.stat().st_size if args.vcd.is_file() else 0
        row = {
            "seq": seq, "wall_seconds": time.monotonic() - started, **heartbeat,
            "vcd_bytes": size, "vcd_operational_projection_bytes": size,
            "return_projection_bytes": size + 256_000_000,
            "disk_space_ok": True, "write_ok": args.vcd.parent.is_dir(),
            "quota_ok": True, "exit_code": child_exit,
        }
        append_sample(args.samples, row)
        samples.append(row)

    atomic_json(args.safety_receipt, {
        "schema": "server-tb-vcd-live-safety-receipt-v1",
        "package_id": args.package_id, "execution_id": args.execution_id,
        "attempt_id": args.attempt_id, "stop_reason": stop_reason,
        "wrapped_supervisor_exit": child_exit, "sample_count": len(samples),
        "thresholds": {
            "sim_time_freeze_intervals": FREEZE_INTERVALS,
            "sim_time_freeze_interval_seconds": INTERVAL_SECONDS,
            "wall_ceiling_seconds": WALL_SECONDS,
            "operational_vcd_budget_bytes": VCD_BUDGET,
            "return_budget_bytes": RETURN_BUDGET,
            "soft_warning_bytes": SOFT_WARNING,
        },
        "samples_path": str(args.samples),
        "claim_boundary": "Independent runtime safety and process supervision only; no DUT outcome claim.",
    })
    if stop_reason and stop_reason not in {"HUP", "INT", "TERM"}:
        return 124
    if received is not None:
        return 128 + received
    return int(child_exit)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--attempt-root", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--process-supervisor", type=Path, required=True)
    parser.add_argument("--sim-log", type=Path, required=True)
    parser.add_argument("--vcd", type=Path, required=True)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--heartbeat-output", type=Path, required=True)
    parser.add_argument("--process-receipt", type=Path, required=True)
    parser.add_argument("--safety-receipt", type=Path, required=True)
    parser.add_argument("simulator_command", nargs=argparse.REMAINDER)
    return supervise(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
