#!/usr/bin/env python3
"""Supervise a simulator process tree and persist simulation-time heartbeats.

The helper is deliberately independent of any waveform writer.  It launches the
simulator as a direct child in a fresh session, enables Linux child-subreaper
semantics, terminates/reaps the owned tree on timeout or signal, and records
same-attempt simulation-time progress from an exact source log.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


SCHEMA = "server-observer-runtime-supervision-v1"
SIGKILL_NUMBER = int(getattr(signal, "SIGKILL", 9))
PR_SET_CHILD_SUBREAPER = 36


class SupervisionError(ValueError):
    pass


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_bytes(json_bytes(value))
    os.replace(temporary, path)


def file_identity(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return {"path": str(path), "bytes": size, "sha256": digest.hexdigest()}


def require_inside(path: Path, root: Path, label: str) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise SupervisionError(f"{label} escapes attempt root") from exc
    return resolved


def enable_child_subreaper() -> dict[str, Any]:
    if sys.platform != "linux":
        raise SupervisionError("production process-tree supervision requires Linux")
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0)
    if result != 0:
        number = ctypes.get_errno()
        raise SupervisionError(f"PR_SET_CHILD_SUBREAPER failed: errno={number}")
    return {"enabled": True, "primitive": "PR_SET_CHILD_SUBREAPER", "value": 1}


def ps_table() -> list[dict[str, Any]]:
    completed = subprocess.run(
        ["ps", "-eo", "pid=,ppid=,pgid=,sid=,stat=,comm="],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SupervisionError(f"ps failed: {completed.stderr.strip()}")
    rows: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        fields = line.strip().split(None, 5)
        if len(fields) != 6:
            continue
        try:
            pid, ppid, pgid, sid = (int(fields[index]) for index in range(4))
        except ValueError:
            continue
        rows.append({
            "pid": pid, "ppid": ppid, "pgid": pgid, "sid": sid,
            "stat": fields[4], "comm": fields[5],
        })
    return rows


def owned_processes(root_pid: int, pgid: int, known: set[int]) -> list[dict[str, Any]]:
    rows = ps_table()
    by_parent: dict[int, list[int]] = {}
    by_pid = {row["pid"]: row for row in rows}
    for row in rows:
        by_parent.setdefault(row["ppid"], []).append(row["pid"])
    pending = [root_pid, *known]
    closure = set(known)
    closure.add(root_pid)
    while pending:
        parent = pending.pop()
        for child in by_parent.get(parent, []):
            if child not in closure:
                closure.add(child)
                pending.append(child)
    closure.update(row["pid"] for row in rows if row["pgid"] == pgid)
    # A double-forked child adopted by this subreaper has our PID as parent.
    closure.update(row["pid"] for row in rows if row["ppid"] == os.getpid())
    return [by_pid[pid] for pid in sorted(closure) if pid in by_pid and pid != os.getpid()]


def signal_owned(root_pid: int, pgid: int, known: set[int], signum: int) -> dict[str, Any]:
    rows = owned_processes(root_pid, pgid, known)
    delivered: list[int] = []
    errors: list[str] = []
    try:
        os.killpg(pgid, signum)
    except ProcessLookupError:
        pass
    except OSError as exc:
        errors.append(f"killpg({pgid},{signum}) failed: {exc}")
    for row in rows:
        pid = row["pid"]
        known.add(pid)
        if row["pgid"] == pgid:
            continue
        try:
            os.kill(pid, signum)
            delivered.append(pid)
        except ProcessLookupError:
            pass
        except OSError as exc:
            errors.append(f"kill({pid},{signum}) failed: {exc}")
    return {"signal": signum, "escaped_pids_signaled": delivered, "errors": errors}


def read_sim_time_incremental(
    source: Path,
    pattern: re.Pattern[str],
    offset: int,
    previous: int | None,
) -> tuple[int, int | None, bool]:
    if not source.exists():
        return offset, previous, False
    size = source.stat().st_size
    if size < offset:
        return 0, previous, True
    last = previous
    with source.open("r", encoding="utf-8", errors="replace") as stream:
        stream.seek(offset)
        for line in stream:
            match = pattern.search(line)
            if match:
                last = int(match.group(1))
        return stream.tell(), last, False


def validate_heartbeat_rows(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    if not path.exists() or not path.is_file() or path.is_symlink():
        errors.append("heartbeat output is absent or unsafe")
    else:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"heartbeat line {number} is invalid JSON: {exc}")
                continue
            rows.append(row)
    for index, row in enumerate(rows):
        if row.get("seq") != index:
            errors.append("heartbeat sequence is not contiguous from zero")
            break
        if not isinstance(row.get("host_monotonic_ns"), int):
            errors.append(f"heartbeat row {index} lacks host monotonic time")
        if row.get("simulation_time") is not None and not isinstance(row.get("simulation_time"), int):
            errors.append(f"heartbeat row {index} has invalid simulation time")
        if not isinstance(row.get("timescale"), str) or not row.get("timescale"):
            errors.append(f"heartbeat row {index} lacks timescale")
    host_times = [row.get("host_monotonic_ns") for row in rows if isinstance(row.get("host_monotonic_ns"), int)]
    if any(right <= left for left, right in zip(host_times, host_times[1:])):
        errors.append("heartbeat host monotonic time did not increase")
    sim_times = [row["simulation_time"] for row in rows if isinstance(row.get("simulation_time"), int)]
    progress = any(value > 0 for value in sim_times) or any(right > left for left, right in zip(sim_times, sim_times[1:]))
    return {
        "rows": len(rows),
        "simulation_time_progress_observed": progress,
        "last_simulation_time": sim_times[-1] if sim_times else None,
        "errors": errors,
        "pass": not errors,
    }


def reap_adopted(known: set[int], deadline: float) -> list[int]:
    reaped: list[int] = []
    while time.monotonic() < deadline:
        changed = False
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return reaped
            if pid <= 0:
                break
            reaped.append(pid)
            known.discard(pid)
            changed = True
        if not changed:
            time.sleep(0.05)
    return reaped


def supervise(args: argparse.Namespace) -> dict[str, Any]:
    attempt_root = args.attempt_root.resolve(strict=True)
    heartbeat_source = require_inside(args.heartbeat_source, attempt_root, "heartbeat source")
    heartbeat_output = require_inside(args.heartbeat_output, attempt_root, "heartbeat output")
    receipt_path = require_inside(args.receipt, attempt_root, "process receipt")
    if heartbeat_output.exists() or receipt_path.exists():
        raise SupervisionError("attempt-local heartbeat/receipt already exists; exact-owned reset is required")
    if not args.simulator_command or args.simulator_command[0] == "--":
        args.simulator_command = args.simulator_command[1:]
    if not args.simulator_command:
        raise SupervisionError("simulator command is required")
    pattern = re.compile(args.heartbeat_regex)
    if pattern.groups != 1:
        raise SupervisionError("heartbeat regex must contain exactly one integer capture group")
    if args.timeout <= 0 or args.interval <= 0 or args.grace < 0:
        raise SupervisionError("timeout/interval/grace values are invalid")

    subreaper = enable_child_subreaper()
    heartbeat_output.parent.mkdir(parents=True, exist_ok=True)
    started_ns = time.monotonic_ns()
    process = subprocess.Popen(
        args.simulator_command,
        cwd=args.cwd,
        start_new_session=True,
    )
    pgid = os.getpgid(process.pid)
    known: set[int] = {process.pid}
    received_signal: int | None = None
    timed_out = False
    old_handlers: dict[int, Any] = {}

    def handle(signum: int, _frame: Any) -> None:
        nonlocal received_signal
        received_signal = signum

    for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        old_handlers[signum] = signal.signal(signum, handle)

    offset = 0
    last_sim_time: int | None = None
    log_truncated = False
    next_heartbeat = time.monotonic()
    heartbeat_seq = 0
    deadline = time.monotonic() + args.timeout
    terminate_receipts: list[dict[str, Any]] = []
    last_kill_host_monotonic_ns: int | None = None
    post_kill_reap_deadline_host_monotonic_ns: int | None = None
    try:
        while process.poll() is None:
            now = time.monotonic()
            if now >= next_heartbeat:
                offset, last_sim_time, truncated = read_sim_time_incremental(
                    heartbeat_source, pattern, offset, last_sim_time
                )
                log_truncated = log_truncated or truncated
                row = {
                    "seq": heartbeat_seq,
                    "host_monotonic_ns": time.monotonic_ns(),
                    "simulation_time": last_sim_time,
                    "timescale": args.timescale,
                }
                with heartbeat_output.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(json.dumps(row, sort_keys=True) + "\n")
                heartbeat_seq += 1
                next_heartbeat = now + args.interval
            if received_signal is not None or now >= deadline:
                timed_out = received_signal is None
                terminate_receipts.append(signal_owned(process.pid, pgid, known, signal.SIGTERM))
                break
            for row in owned_processes(process.pid, pgid, known):
                known.add(row["pid"])
            time.sleep(min(0.1, args.interval))

        # A clean root exit does not imply its process tree exited.  Always
        # drain descendants/adopted grandchildren before producing evidence.
        remaining = owned_processes(process.pid, pgid, known)
        if process.poll() is None or remaining:
            if process.poll() is not None and remaining:
                terminate_receipts.append(signal_owned(process.pid, pgid, known, signal.SIGTERM))
            term_deadline = time.monotonic() + args.grace
            while time.monotonic() < term_deadline and owned_processes(process.pid, pgid, known):
                reap_adopted(known, time.monotonic() + 0.05)
                time.sleep(0.05)
            remaining = owned_processes(process.pid, pgid, known)
            if remaining:
                terminate_receipts.append(signal_owned(process.pid, pgid, known, SIGKILL_NUMBER))
                last_kill_host_monotonic_ns = time.monotonic_ns()
        try:
            root_exit = process.wait(timeout=max(args.grace, 0.1))
        except subprocess.TimeoutExpired:
            root_exit = None
        reap_deadline = time.monotonic() + max(args.grace, 0.1)
        if last_kill_host_monotonic_ns is not None:
            post_kill_reap_deadline_host_monotonic_ns = int(reap_deadline * 1_000_000_000)
        reaped = reap_adopted(known, reap_deadline)
        remaining_rows = owned_processes(process.pid, pgid, known)
        # Capture a final same-attempt simulation-time receipt after the tree is
        # quiescent.  Short successful simulations may finish before the first
        # periodic interval, so relying only on in-loop heartbeats is unsafe.
        offset, last_sim_time, truncated = read_sim_time_incremental(
            heartbeat_source, pattern, offset, last_sim_time
        )
        log_truncated = log_truncated or truncated
        final_row = {
            "seq": heartbeat_seq,
            "host_monotonic_ns": time.monotonic_ns(),
            "simulation_time": last_sim_time,
            "timescale": args.timescale,
        }
        with heartbeat_output.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(final_row, sort_keys=True) + "\n")
        heartbeat_seq += 1
    finally:
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)

    heartbeat = validate_heartbeat_rows(heartbeat_output)
    errors = list(heartbeat["errors"])
    if log_truncated:
        errors.append("simulation-time source log truncated or rotated")
    if remaining_rows:
        errors.append("owned simulator descendants remain after TERM/KILL/reap")
    receipt = {
        "schema": SCHEMA,
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "attempt_root": str(attempt_root),
        "cwd": str(Path(args.cwd).resolve()),
        "actual_argv": args.simulator_command,
        "root_pid": process.pid,
        "pgid": pgid,
        "child_subreaper": subreaper,
        "started_host_monotonic_ns": started_ns,
        "root_exit": root_exit,
        "received_signal": received_signal,
        "timed_out": timed_out,
        "termination": terminate_receipts,
        "post_kill_reap": {
            "deadline_origin": "FRESH_AFTER_LAST_KILL" if last_kill_host_monotonic_ns is not None else "NOT_APPLICABLE",
            "last_kill_host_monotonic_ns": last_kill_host_monotonic_ns,
            "deadline_host_monotonic_ns": post_kill_reap_deadline_host_monotonic_ns,
            "completed": not remaining_rows,
        },
        "reaped_pids": reaped,
        "owned_pids_remaining": [row["pid"] for row in remaining_rows],
        "process_tree_reaped": not remaining_rows,
        "heartbeat_source": file_identity(heartbeat_source),
        "heartbeat_output": file_identity(heartbeat_output),
        "simulation_time_progress_observed": heartbeat["simulation_time_progress_observed"],
        "last_simulation_time": heartbeat["last_simulation_time"],
        "heartbeat_rows": heartbeat["rows"],
        "errors": errors,
        "diagnostic_status": "COMPLETE" if not errors else "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "pass": not errors,
        "claim_boundary": "Owned process-tree termination/reap and simulation-time heartbeat only; no DUT result claim.",
    }
    atomic_write(receipt_path, receipt)
    return receipt


def validate_receipt(path: Path) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if receipt.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if receipt.get("child_subreaper", {}).get("enabled") is not True:
        errors.append("child subreaper was not enabled")
    if receipt.get("process_tree_reaped") is not True:
        errors.append("process tree was not reaped")
    if receipt.get("owned_pids_remaining") not in ([], None):
        errors.append("owned PIDs remain")
    post_kill = receipt.get("post_kill_reap")
    kill_sent = any(
        isinstance(item, dict) and item.get("signal") in {SIGKILL_NUMBER, "SIGKILL"}
        for item in receipt.get("termination", [])
    )
    if kill_sent and not (
        isinstance(post_kill, dict)
        and post_kill.get("deadline_origin") == "FRESH_AFTER_LAST_KILL"
        and isinstance(post_kill.get("last_kill_host_monotonic_ns"), int)
        and isinstance(post_kill.get("deadline_host_monotonic_ns"), int)
        and post_kill["deadline_host_monotonic_ns"] > post_kill["last_kill_host_monotonic_ns"]
        and post_kill.get("completed") is True
    ):
        errors.append("KILL lacks a fresh completed post-KILL reap deadline")
    if receipt.get("simulation_time_progress_observed") is not True:
        errors.append("same-attempt simulation-time progress is absent")
    if receipt.get("errors"):
        errors.extend(f"receipt: {item}" for item in receipt["errors"])
    return {"schema": SCHEMA, "errors": errors, "pass": not errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("supervise")
    run.add_argument("--package-id", required=True)
    run.add_argument("--execution-id", required=True)
    run.add_argument("--attempt-id", required=True)
    run.add_argument("--attempt-root", type=Path, required=True)
    run.add_argument("--cwd", type=Path, required=True)
    run.add_argument("--heartbeat-source", type=Path, required=True)
    run.add_argument("--heartbeat-output", type=Path, required=True)
    run.add_argument("--heartbeat-regex", required=True)
    run.add_argument("--timescale", required=True)
    run.add_argument("--timeout", type=float, required=True)
    run.add_argument("--interval", type=float, default=30.0)
    run.add_argument("--grace", type=float, default=10.0)
    run.add_argument("--receipt", type=Path, required=True)
    run.add_argument("simulator_command", nargs=argparse.REMAINDER)
    check = sub.add_parser("validate-receipt")
    check.add_argument("--receipt", type=Path, required=True)
    check.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "supervise":
        report = supervise(args)
        return_code = report.get("root_exit")
        if report.get("timed_out"):
            return_code = 124
        elif report.get("received_signal"):
            return_code = 128 + int(report["received_signal"])
        if return_code is None:
            return_code = 1
    else:
        report = validate_receipt(args.receipt)
        return_code = 0 if report["pass"] else 1
    payload = json_bytes(report)
    if getattr(args, "output", None):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
    else:
        sys.stdout.buffer.write(payload)
    return int(return_code)


if __name__ == "__main__":
    raise SystemExit(main())
