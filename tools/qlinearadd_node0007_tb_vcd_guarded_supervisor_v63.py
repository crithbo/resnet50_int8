#!/usr/bin/env python3
"""Guard and reap the QAdd bounded causal-cone VCD simulator attempt.

This package-local process wrapper deliberately performs no server inventory or
provider preflight.  It starts the exact simulator command immediately, owns the
new process group as a Linux child subreaper, samples only attempt-owned logs and
the attempt-owned VCD, and enforces the independent runtime safeguards required
by the bounded causal-cone mode.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PR_SET_CHILD_SUBREAPER = 36
VCD_LIMIT = 8_000_000_000
RETURN_LIMIT = 10_000_000_000
WALL_LIMIT = 3600.0
FREEZE_INTERVALS = 3
FREEZE_SECONDS = 30.0


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def identity(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return {"path": str(path), "bytes": size, "sha256": digest.hexdigest()}


def inside(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise ValueError(f"{label} escapes attempt root") from exc
    return resolved


def enable_subreaper() -> dict[str, Any]:
    if sys.platform != "linux":
        raise ValueError("production process supervision requires Linux")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER failed")
    return {"enabled": True, "primitive": "PR_SET_CHILD_SUBREAPER", "value": 1}


def process_rows() -> list[dict[str, Any]]:
    completed = subprocess.run(
        ["ps", "-eo", "pid=,ppid=,pgid=,sid=,stat=,comm="],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        return []
    rows: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        fields = line.strip().split(None, 5)
        if len(fields) != 6:
            continue
        try:
            pid, ppid, pgid, sid = (int(fields[index]) for index in range(4))
        except ValueError:
            continue
        rows.append(
            {
                "pid": pid,
                "ppid": ppid,
                "pgid": pgid,
                "sid": sid,
                "stat": fields[4],
                "comm": fields[5],
            }
        )
    return rows


def owned(root_pid: int, pgid: int, known: set[int]) -> list[dict[str, Any]]:
    rows = process_rows()
    by_pid = {row["pid"]: row for row in rows}
    children: dict[int, list[int]] = {}
    for row in rows:
        children.setdefault(row["ppid"], []).append(row["pid"])
    closure = {root_pid, *known}
    pending = list(closure)
    while pending:
        parent = pending.pop()
        for child in children.get(parent, []):
            if child not in closure:
                closure.add(child)
                pending.append(child)
    closure.update(row["pid"] for row in rows if row["pgid"] == pgid)
    closure.update(row["pid"] for row in rows if row["ppid"] == os.getpid())
    return [by_pid[pid] for pid in sorted(closure) if pid in by_pid and pid != os.getpid()]


def signal_owned(root_pid: int, pgid: int, known: set[int], number: int) -> dict[str, Any]:
    rows = owned(root_pid, pgid, known)
    delivered: list[int] = []
    errors: list[str] = []
    try:
        os.killpg(pgid, number)
    except ProcessLookupError:
        pass
    except OSError as exc:
        errors.append(str(exc))
    for row in rows:
        known.add(row["pid"])
        if row["pgid"] == pgid:
            continue
        try:
            os.kill(row["pid"], number)
            delivered.append(row["pid"])
        except ProcessLookupError:
            pass
        except OSError as exc:
            errors.append(str(exc))
    return {"signal": number, "escaped_pids_signaled": delivered, "errors": errors}


def reap(deadline: float, known: set[int]) -> list[int]:
    result: list[int] = []
    while time.monotonic() < deadline:
        changed = False
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return result
            if pid <= 0:
                break
            result.append(pid)
            known.discard(pid)
            changed = True
        if not changed:
            time.sleep(0.05)
    return result


def scan_progress(path: Path, offset: int, pattern: re.Pattern[str]) -> tuple[int, dict[str, int] | None, bool]:
    if not path.is_file():
        return offset, None, False
    if path.stat().st_size < offset:
        return 0, None, True
    latest: dict[str, int] | None = None
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        stream.seek(offset)
        for line in stream:
            match = pattern.search(line)
            if match:
                latest = {
                    "sim_time": int(match.group(1)),
                    "owner_cycles": int(match.group(2)),
                    "progress": int(match.group(3)),
                    "global_progress": int(match.group(4)),
                }
        return stream.tell(), latest, False


def scan_vcd_time(path: Path, offset: int, carry: bytes) -> tuple[int, bytes, int | None, bool]:
    """Read only newly appended VCD bytes and return the latest real #timestamp."""
    if not path.is_file():
        return offset, carry, None, False
    size = path.stat().st_size
    if size < offset:
        return 0, b"", None, True
    latest: int | None = None
    with path.open("rb") as stream:
        stream.seek(offset)
        payload = carry + stream.read()
        new_offset = stream.tell()
    rows = payload.split(b"\n")
    trailing = rows.pop() if rows else b""
    for raw in rows:
        row = raw.strip()
        if len(row) > 1 and row.startswith(b"#") and row[1:].isdigit():
            latest = int(row[1:])
    return new_offset, trailing[-128:], latest, False


def attempt_bytes(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def supervise(args: argparse.Namespace) -> dict[str, Any]:
    root = args.attempt_root.resolve(strict=True)
    log = inside(args.sim_log, root, "sim log")
    vcd = inside(args.vcd, root, "VCD")
    heartbeat = inside(args.heartbeat, root, "heartbeat")
    receipt = inside(args.receipt, root, "receipt")
    if heartbeat.exists() or receipt.exists():
        raise ValueError("attempt-owned heartbeat or receipt already exists")
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError("simulator command is absent")

    subreaper = enable_subreaper()
    started_ns = time.monotonic_ns()
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=args.cwd, start_new_session=True)
    pgid = os.getpgid(process.pid)
    known: set[int] = {process.pid}
    received: int | None = None
    stop_reason: str | None = None
    old_handlers: dict[int, Any] = {}

    def handler(number: int, _frame: Any) -> None:
        nonlocal received
        received = number

    for number in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        old_handlers[number] = signal.signal(number, handler)

    progress_pattern = re.compile(
        r"CODEX_TB_VCD_HEARTBEAT sim_time=([0-9]+) cycles=([0-9]+) progress=([0-9]+) global=([0-9]+)"
    )
    offset = 0
    last_progress: dict[str, int] | None = None
    vcd_offset = 0
    vcd_carry = b""
    last_vcd_time: int | None = None
    last_sim_change = started
    next_sample = started
    previous_size = 0
    previous_time = started
    rolling_rate = 0.0
    seq = 0
    log_rotated = False
    samples: list[dict[str, Any]] = []
    term_receipts: list[dict[str, Any]] = []
    try:
        while process.poll() is None:
            now = time.monotonic()
            if now >= next_sample:
                offset, current, rotated = scan_progress(log, offset, progress_pattern)
                log_rotated = log_rotated or rotated
                if current is not None:
                    last_progress = current
                vcd_offset, vcd_carry, current_vcd_time, vcd_rotated = scan_vcd_time(
                    vcd, vcd_offset, vcd_carry
                )
                log_rotated = log_rotated or vcd_rotated
                if current_vcd_time is not None:
                    if last_vcd_time is None or current_vcd_time > last_vcd_time:
                        last_sim_change = now
                    last_vcd_time = current_vcd_time
                try:
                    current_size = vcd.stat().st_size if vcd.is_file() else 0
                    write_ok = True
                except OSError:
                    current_size = previous_size
                    write_ok = False
                dt = max(0.001, now - previous_time)
                rolling_rate = max(0.0, (current_size - previous_size) / dt)
                projected_vcd = int(current_size + rolling_rate * max(0.0, WALL_LIMIT - (now - started)))
                try:
                    free = shutil.disk_usage(root).free
                    disk_ok = free > max(1_073_741_824, int(rolling_rate * 120.0))
                except OSError:
                    free = 0
                    disk_ok = False
                total_bytes = attempt_bytes(root)
                projected_return = int(total_bytes + rolling_rate * max(0.0, WALL_LIMIT - (now - started)))
                row = {
                    "seq": seq,
                    "host_monotonic_ns": time.monotonic_ns(),
                    "wall_seconds": now - started,
                    "simulation_time": last_vcd_time,
                    "reported_heartbeat_sim_time": None if last_progress is None else last_progress["sim_time"],
                    "owner_clock_cycles": 0 if last_progress is None else last_progress["owner_cycles"],
                    "causal_progress_events": 0 if last_progress is None else last_progress["progress"],
                    "global_progress_witness": 0 if last_progress is None else last_progress["global_progress"],
                    "vcd_bytes": current_size,
                    "vcd_operational_projection_bytes": projected_vcd,
                    "return_projection_bytes": projected_return,
                    "disk_free_bytes": free,
                    "write_ok": write_ok,
                    "disk_space_ok": disk_ok,
                    "quota_ok": True,
                    "timescale": "1ps",
                }
                with heartbeat.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(json.dumps(row, sort_keys=True) + "\n")
                samples.append(row)
                seq += 1
                previous_size = current_size
                previous_time = now
                next_sample = now + args.interval
                if not write_ok:
                    stop_reason = "WRITE_FAILURE"
                elif not disk_ok:
                    stop_reason = "DISK_SPACE_FAILURE"
                elif current_size >= VCD_LIMIT or projected_vcd >= VCD_LIMIT:
                    stop_reason = "VCD_OPERATIONAL_BUDGET"
                elif projected_return >= RETURN_LIMIT:
                    stop_reason = "RETURN_BUDGET_PROJECTION"
                elif now - last_sim_change >= FREEZE_INTERVALS * FREEZE_SECONDS:
                    stop_reason = "SIM_TIME_FREEZE"
                elif now - started >= WALL_LIMIT:
                    stop_reason = "WALL_CEILING"
            if received is not None:
                stop_reason = signal.Signals(received).name.removeprefix("SIG")
            if stop_reason is not None:
                term_receipts.append(signal_owned(process.pid, pgid, known, signal.SIGTERM))
                break
            for row in owned(process.pid, pgid, known):
                known.add(row["pid"])
            time.sleep(0.1)

        if process.poll() is None or owned(process.pid, pgid, known):
            deadline = time.monotonic() + args.grace
            while time.monotonic() < deadline and owned(process.pid, pgid, known):
                reap(time.monotonic() + 0.05, known)
                time.sleep(0.05)
            if owned(process.pid, pgid, known):
                term_receipts.append(signal_owned(process.pid, pgid, known, signal.SIGKILL))
        try:
            root_exit = process.wait(timeout=max(args.grace, 0.1))
        except subprocess.TimeoutExpired:
            root_exit = None
        final_deadline = time.monotonic() + max(args.grace, 0.1)
        reaped = reap(final_deadline, known)
        remaining = owned(process.pid, pgid, known)
        while remaining and time.monotonic() < final_deadline:
            term_receipts.append(signal_owned(process.pid, pgid, known, signal.SIGKILL))
            reaped.extend(reap(min(final_deadline, time.monotonic() + 0.25), known))
            remaining = owned(process.pid, pgid, known)
    finally:
        for number, old in old_handlers.items():
            signal.signal(number, old)

    if stop_reason is None:
        stop_reason = "PROCESS_EXIT"
    errors: list[str] = []
    if remaining:
        errors.append("owned simulator descendants remain after TERM/WAIT/KILL/reap")
    if log_rotated:
        errors.append("attempt-owned sim log rotated during supervision")
    value = {
        "schema": "qadd-tb-vcd-guarded-process-supervision-v1",
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "attempt_root": str(root),
        "cwd": str(Path(args.cwd).resolve()),
        "actual_argv": command,
        "root_pid": process.pid,
        "pgid": pgid,
        "child_subreaper": subreaper,
        "started_host_monotonic_ns": started_ns,
        "root_exit": root_exit,
        "received_signal": received,
        "stop_reason": stop_reason,
        "termination": term_receipts,
        "reaped_pids": reaped,
        "owned_pids_remaining": [row["pid"] for row in remaining],
        "process_tree_reaped": not remaining,
        "heartbeat": identity(heartbeat),
        "vcd": identity(vcd),
        "samples": samples,
        "thresholds": {
            "sim_time_freeze_intervals": FREEZE_INTERVALS,
            "sim_time_freeze_interval_seconds": FREEZE_SECONDS,
            "wall_ceiling_seconds": int(WALL_LIMIT),
            "operational_vcd_budget_bytes": VCD_LIMIT,
            "return_budget_bytes": RETURN_LIMIT,
        },
        "errors": errors,
        "diagnostic_status": "DIAGNOSTIC_EVIDENCE_COMPLETE" if not errors else "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "pass": not errors,
        "claim_boundary": "Process-tree and independent runtime safeguards only; no DUT or natural-terminal claim.",
    }
    atomic_json(receipt, value)
    if stop_reason != "PROCESS_EXIT":
        return_code = {
            "HUP": 129,
            "INT": 130,
            "TERM": 143,
            "SIM_TIME_FREEZE": 124,
            "WALL_CEILING": 124,
        }.get(stop_reason, 96)
    else:
        return_code = root_exit if isinstance(root_exit, int) else 97
    value["supervisor_exit"] = return_code
    atomic_json(receipt, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--attempt-root", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--sim-log", type=Path, required=True)
    parser.add_argument("--vcd", type=Path, required=True)
    parser.add_argument("--heartbeat", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=30.0)
    parser.add_argument("--grace", type=float, default=30.0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    report = supervise(args)
    return int(report["supervisor_exit"])


if __name__ == "__main__":
    raise SystemExit(main())
