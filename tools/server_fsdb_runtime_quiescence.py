#!/usr/bin/env python3
"""Supervise simulator process trees and prove an FSDB snapshot is quiescent.

Production runners use ``supervise`` on POSIX to start the simulator in a fresh
session/process group, record simulation-time heartbeats from an exact log
pattern, terminate TERM->KILL on signals/timeouts, wait for the direct child,
and require every observed descendant/group member to disappear.  ``quiesce``
then binds two complete FSDB/shard snapshots separated by a settle interval.

Failure never authorizes dropping the raw/core return; callers publish the
partial evidence with DIAGNOSTIC_EVIDENCE_INCOMPLETE.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, BinaryIO


SCHEMA = "server-fsdb-runtime-quiescence-v1"
RULE_ID = "CDA-SERVER-FSDB-PROCESS-TREE-WRITER-QUIESCENCE-001"
SAFE_EXECUTION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
TRANSIENT_SUFFIXES = (".slock", ".lock", ".lck", ".tmp", "~")
PR_SET_CHILD_SUBREAPER = 36


class QuiescenceError(ValueError):
    pass


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    temporary.write_bytes(json_bytes(value))
    os.replace(temporary, path)


def hash_stream(stream: BinaryIO) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    while True:
        block = stream.read(1024 * 1024)
        if not block:
            break
        total += len(block)
        digest.update(block)
    return total, digest.hexdigest()


def hash_file(path: Path) -> tuple[int, str]:
    with path.open("rb") as stream:
        return hash_stream(stream)


def file_identity(path: Path) -> dict[str, Any] | None:
    if path.is_symlink() or not path.is_file():
        return None
    size, digest = hash_file(path)
    return {"path": str(path.resolve()), "bytes": size, "sha256": digest}


def validate_execution_identity(package_id: str, execution_id: str, attempt_id: str) -> None:
    for label, value in (
        ("package_id", package_id),
        ("execution_id", execution_id),
        ("attempt_id", attempt_id),
    ):
        if not SAFE_EXECUTION.fullmatch(value):
            raise QuiescenceError(f"invalid {label}: {value!r}")


def require_inside(path: Path, root: Path, label: str) -> Path:
    resolved_root = root.resolve(strict=True)
    if resolved_root.is_symlink() or not resolved_root.is_dir():
        raise QuiescenceError("attempt root must be a real directory")
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as error:
        raise QuiescenceError(f"{label} escapes attempt root") from error
    return resolved


def process_tree(processes: list[dict[str, Any]], root_pid: int, expected_pgid: int) -> dict[str, Any]:
    by_pid = {int(item["pid"]): item for item in processes}
    group = {pid for pid, row in by_pid.items() if int(row["pgid"]) == expected_pgid}
    if root_pid not in by_pid:
        return {
            "root_present": False,
            "owned_pids": [],
            "escaped_pids": [],
            "group_pids": sorted(group),
        }
    owned = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, row in by_pid.items():
            if int(row["ppid"]) in owned and pid not in owned:
                owned.add(pid)
                changed = True
    escaped = {pid for pid in owned if int(by_pid[pid]["pgid"]) != expected_pgid}
    return {
        "root_present": True,
        "owned_pids": sorted(owned),
        "escaped_pids": sorted(escaped),
        "group_pids": sorted(group),
    }


def enable_child_subreaper() -> dict[str, Any]:
    """Make escaped/double-fork descendants observable and reapable on Linux."""
    if not sys.platform.startswith("linux"):
        raise QuiescenceError("production process-tree supervision requires Linux child-subreaper support")
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0)
    if result != 0:
        error_number = ctypes.get_errno()
        raise QuiescenceError(f"prctl(PR_SET_CHILD_SUBREAPER) failed: errno={error_number}")
    return {"enabled": True, "prctl": "PR_SET_CHILD_SUBREAPER", "value": 1}


def _ps_table() -> list[dict[str, Any]]:
    completed = subprocess.run(
        ["ps", "-eo", "pid=,ppid=,pgid=,sid=,stat=,comm="],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise QuiescenceError(f"ps failed: {completed.stderr.strip()}")
    rows: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        parts = line.split(None, 5)
        if len(parts) != 6:
            continue
        pid, ppid, pgid, sid, state, command = parts
        rows.append(
            {
                "pid": int(pid),
                "ppid": int(ppid),
                "pgid": int(pgid),
                "sid": int(sid),
                "state": state,
                "command": command,
            }
        )
    return rows


def _refresh_owned(root_pid: int, pgid: int, known_owned: set[int]) -> list[dict[str, Any]]:
    """Refresh group, descendant and subreaper-adopted ownership from one ps snapshot."""
    rows = _ps_table()
    by_pid = {int(item["pid"]): item for item in rows}
    tree = process_tree(rows, root_pid, pgid)
    known_owned.update(tree["owned_pids"])
    known_owned.update(tree["group_pids"])
    # A descendant that calls setsid()/double-forks is reparented to this
    # supervisor because PR_SET_CHILD_SUBREAPER is active.  Include it and all
    # descendants even after the original simulator root exits.
    known_owned.update(
        pid
        for pid, row in by_pid.items()
        if int(row["ppid"]) == os.getpid() and pid != root_pid
    )
    changed = True
    while changed:
        changed = False
        for pid, row in by_pid.items():
            if int(row["ppid"]) in known_owned and pid not in known_owned:
                known_owned.add(pid)
                changed = True
    return rows


def _signal_tree(root_pid: int, pgid: int, signum: int, known_owned: set[int]) -> dict[str, Any]:
    rows = _refresh_owned(root_pid, pgid, known_owned)
    signaled: list[int] = []
    errors: list[str] = []
    try:
        os.killpg(pgid, signum)
    except ProcessLookupError:
        pass
    except OSError as error:
        errors.append(f"killpg({pgid},{signum}) failed: {error}")
    table = {item["pid"]: item for item in rows}
    for pid in sorted(known_owned):
        if pid not in table or table[pid]["pgid"] == pgid:
            continue
        try:
            os.kill(pid, signum)
            signaled.append(pid)
        except ProcessLookupError:
            pass
        except OSError as error:
            errors.append(f"kill({pid},{signum}) failed: {error}")
    return {"signal": signum, "escaped_signaled": signaled, "errors": errors}


def _read_sim_time_incremental(
    path: Path,
    pattern: re.Pattern[str],
    offset: int,
    prior_maximum: int | None,
) -> tuple[int, int | None, bool]:
    """Tail only new log bytes; report truncation/rotation rather than hiding it."""
    if not path.is_file():
        return offset, prior_maximum, False
    size = path.stat().st_size
    truncated = size < offset
    if truncated:
        offset = 0
    maximum = prior_maximum
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        stream.seek(offset)
        for line in stream:
            match = pattern.search(line)
            if match:
                value = int(match.group(1))
                maximum = value if maximum is None else max(maximum, value)
        offset = stream.tell()
    return offset, maximum, truncated


def validate_heartbeat(path: Path, plateau_seconds: float) -> dict[str, Any]:
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            required = {"sequence", "host_monotonic_ns", "sim_time", "timescale"}
            if not required <= set(row):
                errors.append(f"heartbeat line {number} misses required fields")
                continue
            if not isinstance(row["sequence"], int) or row["sequence"] < 0:
                errors.append(f"heartbeat line {number} has invalid sequence")
                continue
            if not isinstance(row["host_monotonic_ns"], int) or row["host_monotonic_ns"] < 0:
                errors.append(f"heartbeat line {number} has invalid host monotonic time")
                continue
            if row["sim_time"] is not None and (
                not isinstance(row["sim_time"], int) or row["sim_time"] < 0
            ):
                errors.append(f"heartbeat line {number} has invalid simulation time")
                continue
            if not isinstance(row["timescale"], str) or not row["timescale"]:
                errors.append(f"heartbeat line {number} has invalid timescale")
                continue
            rows.append(row)
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{type(error).__name__}: {error}")
    for index, row in enumerate(rows):
        if row["sequence"] != index:
            errors.append("heartbeat sequence is not contiguous from zero")
        if index and row["host_monotonic_ns"] <= rows[index - 1]["host_monotonic_ns"]:
            errors.append("heartbeat host monotonic time did not increase")
        if index and row["sim_time"] is not None and rows[index - 1]["sim_time"] is not None:
            if row["sim_time"] < rows[index - 1]["sim_time"]:
                errors.append("simulation time regressed")
    last_progress_index: int | None = None
    for index in range(1, len(rows)):
        prior, current = rows[index - 1], rows[index]
        if prior["sim_time"] is not None and current["sim_time"] is not None and current["sim_time"] > prior["sim_time"]:
            last_progress_index = index
    positive_time_observed = any(
        isinstance(row["sim_time"], int) and row["sim_time"] > 0 for row in rows
    )
    plateau = False
    plateau_duration = 0.0
    if len(rows) >= 2:
        anchor = last_progress_index if last_progress_index is not None else 0
        plateau_duration = (rows[-1]["host_monotonic_ns"] - rows[anchor]["host_monotonic_ns"]) / 1e9
        plateau = plateau_duration >= plateau_seconds
    classification = (
        "INVALID"
        if errors
        else "HIGH_CPU_OR_HOST_LIVE_ZERO_SIM_TIME_PROGRESS"
        if plateau
        else "SIM_TIME_PROGRESS_OBSERVED"
        if last_progress_index is not None or positive_time_observed
        else "INSUFFICIENT_HEARTBEAT_WINDOW"
    )
    timescales = sorted({row["timescale"] for row in rows})
    if len(timescales) > 1:
        errors.append("heartbeat timescale changed within one attempt")
        classification = "INVALID"
    return {
        "rows": len(rows),
        "first_sim_time": rows[0]["sim_time"] if rows else None,
        "last_sim_time": rows[-1]["sim_time"] if rows else None,
        "timescales": timescales,
        "plateau_seconds": plateau_duration,
        "plateau": plateau,
        "sim_time_progress_observed": last_progress_index is not None or positive_time_observed,
        "classification": classification,
        "errors": errors,
    }


def supervise(
    package_id: str,
    execution_id: str,
    attempt_id: str,
    attempt_root: Path,
    cwd: Path,
    command: list[str],
    receipt_path: Path,
    heartbeat_source: Path,
    heartbeat_path: Path,
    heartbeat_regex: str,
    timescale: str,
    interval: float,
    term_grace: float,
    kill_grace: float,
    runtime_timeout_seconds: float,
) -> int:
    if os.name != "posix":
        raise QuiescenceError("production process-tree supervision requires POSIX")
    validate_execution_identity(package_id, execution_id, attempt_id)
    if not command:
        raise QuiescenceError("simulator command is empty")
    pattern = re.compile(heartbeat_regex)
    if pattern.groups != 1:
        raise QuiescenceError("heartbeat regex must contain exactly one integer capture group")
    if interval <= 0 or term_grace < 0 or kill_grace < 0 or runtime_timeout_seconds < 0:
        raise QuiescenceError("heartbeat/grace/timeout values are outside the accepted range")
    attempt_root = attempt_root.resolve(strict=True)
    cwd = require_inside(cwd, attempt_root, "simulator cwd")
    if not cwd.is_dir() or cwd.is_symlink():
        raise QuiescenceError("simulator cwd must be a real directory")
    receipt_path = require_inside(receipt_path, attempt_root, "process receipt")
    heartbeat_source = require_inside(heartbeat_source, attempt_root, "heartbeat source")
    heartbeat_path = require_inside(heartbeat_path, attempt_root, "heartbeat output")
    if heartbeat_path.exists():
        raise QuiescenceError("heartbeat output already exists; exact attempt reset is required")
    subreaper = enable_child_subreaper()
    stop_signal: list[int] = []
    timed_out = False

    def handler(signum: int, _frame: Any) -> None:
        if not stop_signal:
            stop_signal.append(signum)

    prior = {item: signal.getsignal(item) for item in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)}
    for item in prior:
        signal.signal(item, handler)
    started_monotonic = time.monotonic()
    started = time.monotonic_ns()
    process = subprocess.Popen(command, cwd=cwd, start_new_session=True)
    pgid = os.getpgid(process.pid)
    known_owned: set[int] = {process.pid}
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    sequence = 0
    next_heartbeat = time.monotonic()
    heartbeat_offset = 0
    last_sim_time: int | None = None
    heartbeat_log_truncated = False
    actions: list[dict[str, Any]] = []
    exit_code: int | None = None
    try:
        while exit_code is None and not stop_signal:
            exit_code = process.poll()
            _refresh_owned(process.pid, pgid, known_owned)
            now = time.monotonic()
            if runtime_timeout_seconds and now - started_monotonic >= runtime_timeout_seconds:
                timed_out = True
                break
            if now >= next_heartbeat:
                heartbeat_offset, last_sim_time, truncated = _read_sim_time_incremental(
                    heartbeat_source, pattern, heartbeat_offset, last_sim_time
                )
                heartbeat_log_truncated = heartbeat_log_truncated or truncated
                row = {
                    "sequence": sequence,
                    "host_monotonic_ns": time.monotonic_ns(),
                    "sim_time": last_sim_time,
                    "timescale": timescale,
                }
                with heartbeat_path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(json.dumps(row, sort_keys=True) + "\n")
                sequence += 1
                next_heartbeat = now + interval
            time.sleep(min(0.1, interval))
        termination_reason = (
            "TIMEOUT"
            if timed_out
            else "NATURAL"
            if not stop_signal
            else signal.Signals(stop_signal[0]).name
        )
        if stop_signal or timed_out or process.poll() is not None:
            # A natural root exit can still leave writer children.  TERM is sent
            # to the owned group only when members remain.
            rows = _refresh_owned(process.pid, pgid, known_owned)
            remaining_group = [row["pid"] for row in rows if row["pgid"] == pgid]
            if stop_signal or timed_out or remaining_group:
                actions.append(_signal_tree(process.pid, pgid, signal.SIGTERM, known_owned))
                deadline = time.monotonic() + term_grace
                while time.monotonic() < deadline:
                    table = {item["pid"] for item in _ps_table()}
                    if not (known_owned & table):
                        break
                    time.sleep(0.1)
                table = {item["pid"] for item in _ps_table()}
                if known_owned & table:
                    actions.append(_signal_tree(process.pid, pgid, signal.SIGKILL, known_owned))
                    deadline = time.monotonic() + kill_grace
                    while time.monotonic() < deadline:
                        table = {item["pid"] for item in _ps_table()}
                        if not (known_owned & table):
                            break
                        time.sleep(0.1)
        try:
            exit_code = process.wait(timeout=max(term_grace + kill_grace, 0.1))
            root_reaped = True
        except subprocess.TimeoutExpired:
            exit_code = process.poll()
            root_reaped = False
        reaped_adopted: list[int] = []
        reap_deadline = time.monotonic() + max(kill_grace, 0.1)
        while True:
            _refresh_owned(process.pid, pgid, known_owned)
            for pid in sorted(known_owned - {process.pid}):
                try:
                    waited, _status = os.waitpid(pid, os.WNOHANG)
                    if waited == pid and pid not in reaped_adopted:
                        reaped_adopted.append(pid)
                except (ChildProcessError, ProcessLookupError):
                    pass
            live = known_owned & {item["pid"] for item in _ps_table()}
            if not live or time.monotonic() >= reap_deadline:
                break
            time.sleep(0.05)
        final_table = {item["pid"] for item in _ps_table()}
        remaining = sorted(known_owned & final_table)
        source_identity = file_identity(heartbeat_source)
        output_identity = file_identity(heartbeat_path)
        receipt_errors = [error for action in actions for error in action["errors"]]
        if source_identity is None:
            receipt_errors.append("same-attempt simulation-time source log is absent")
        if output_identity is None:
            receipt_errors.append("simulation-time heartbeat output is absent")
        if heartbeat_log_truncated:
            receipt_errors.append("heartbeat source log truncated or rotated")
        if not root_reaped:
            receipt_errors.append("simulator root was not reaped")
        if remaining:
            receipt_errors.append(f"owned process tree remains: {remaining}")
        receipt = {
            "schema": SCHEMA,
            "kind": "process_tree_receipt",
            "rule_id": RULE_ID,
            "package_id": package_id,
            "execution_id": execution_id,
            "attempt_id": attempt_id,
            "attempt_root": str(attempt_root),
            "cwd": str(cwd),
            "command": command,
            "start_new_session": True,
            "child_subreaper": subreaper,
            "root_pid": process.pid,
            "pgid": pgid,
            "known_owned_pids": sorted(known_owned),
            "termination_reason": termination_reason,
            "actions": actions,
            "runtime_timeout_seconds": runtime_timeout_seconds,
            "heartbeat_log_truncated": heartbeat_log_truncated,
            "heartbeat_source": source_identity,
            "heartbeat_output": output_identity,
            "reaped_adopted_pids": reaped_adopted,
            "root_exit_code": exit_code,
            "root_reaped": root_reaped,
            "remaining_owned_pids": remaining,
            "process_tree_quiescent": root_reaped and not remaining,
            "started_monotonic_ns": started,
            "ended_monotonic_ns": time.monotonic_ns(),
            "pass": not receipt_errors,
            "errors": receipt_errors,
            "claim_boundary": "Package-owned simulator process-tree lifecycle only; no DUT or waveform semantic claim.",
        }
        atomic_write(receipt_path, receipt)
        return int(exit_code if exit_code is not None else 125)
    finally:
        for item, value in prior.items():
            signal.signal(item, value)


def waveform_snapshot(attempt_root: Path) -> dict[str, Any]:
    wave_root = attempt_root / "run/sim_results"
    members: list[dict[str, Any]] = []
    transient: list[str] = []
    if wave_root.is_dir() and not wave_root.is_symlink():
        for path in sorted(wave_root.glob("wave.fsdb*"), key=lambda item: item.name):
            if path.is_symlink() or not path.is_file():
                transient.append(path.name)
                continue
            size, digest = hash_file(path)
            item = {
                "path": path.relative_to(attempt_root).as_posix(),
                "bytes": size,
                "sha256": digest,
            }
            members.append(item)
            if size == 0 or path.name.lower().endswith(TRANSIENT_SUFFIXES):
                transient.append(path.name)
    return {"members": members, "transient_members": sorted(set(transient))}


def evaluate_quiescence(
    process_receipt: dict[str, Any],
    heartbeat: dict[str, Any],
    pre: dict[str, Any],
    post: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if process_receipt.get("start_new_session") is not True:
        errors.append("simulator was not launched in a fresh session/process group")
    if process_receipt.get("root_reaped") is not True:
        errors.append("simulator root was not reaped")
    if process_receipt.get("process_tree_quiescent") is not True or process_receipt.get("remaining_owned_pids"):
        errors.append("simulator/FSDB process tree is not quiescent")
    if heartbeat.get("errors"):
        errors.extend(f"heartbeat: {item}" for item in heartbeat["errors"])
    if heartbeat.get("sim_time_progress_observed") is not True:
        errors.append("no same-attempt simulation-time advance was observed")
    if pre["transient_members"] or post["transient_members"]:
        errors.append(
            f"transient FSDB members remain: {sorted(set(pre['transient_members'] + post['transient_members']))}"
        )
    if not pre["members"] or not post["members"]:
        errors.append("stable snapshot lacks wave.fsdb or shards")
    if pre["members"] != post["members"]:
        errors.append("FSDB exact set or member identities changed between quiescence snapshots")
    pass_gate = not errors
    return {
        "schema": SCHEMA,
        "kind": "quiescence_receipt",
        "rule_id": RULE_ID,
        "process_tree": process_receipt,
        "simulation_time_heartbeat": heartbeat,
        "pre_snapshot": pre,
        "post_snapshot": post,
        "stable_exact_set": pre["members"] == post["members"] and bool(pre["members"]),
        "diagnostic_status": "COMPLETE" if pass_gate else "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "pass": pass_gate,
        "errors": errors,
        "failure_isolation": "Raw FSDB and compile/sim/signal/core return remain publishable as PARTIAL evidence even when this gate fails.",
        "claim_boundary": "Process-tree, simulation-time heartbeat and stable FSDB snapshot only; no DUT, root-cause, natural-terminal, formal-D, E4 or E5 claim.",
    }


def quiesce(
    attempt_root: Path,
    process_receipt_path: Path,
    heartbeat_path: Path,
    plateau_seconds: float,
    settle_seconds: float,
) -> dict[str, Any]:
    process_receipt = json.loads(process_receipt_path.read_text(encoding="utf-8"))
    heartbeat = validate_heartbeat(heartbeat_path, plateau_seconds)
    pre = waveform_snapshot(attempt_root)
    time.sleep(settle_seconds)
    post = waveform_snapshot(attempt_root)
    return evaluate_quiescence(process_receipt, heartbeat, pre, post)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    supervisor = subparsers.add_parser("supervise")
    supervisor.add_argument("--package-id", required=True)
    supervisor.add_argument("--execution-id", required=True)
    supervisor.add_argument("--attempt-id", required=True)
    supervisor.add_argument("--attempt-root", type=Path, required=True)
    supervisor.add_argument("--cwd", type=Path, required=True)
    supervisor.add_argument("--receipt", type=Path, required=True)
    supervisor.add_argument("--heartbeat-source", type=Path, required=True)
    supervisor.add_argument("--heartbeat-output", type=Path, required=True)
    supervisor.add_argument("--heartbeat-regex", required=True)
    supervisor.add_argument("--timescale", required=True)
    supervisor.add_argument("--heartbeat-interval", type=float, default=30.0)
    supervisor.add_argument("--term-grace", type=float, default=30.0)
    supervisor.add_argument("--kill-grace", type=float, default=10.0)
    supervisor.add_argument("--runtime-timeout-seconds", type=float, required=True)
    supervisor.add_argument("simulator_command", nargs=argparse.REMAINDER)

    gate = subparsers.add_parser("quiesce")
    gate.add_argument("--attempt-root", type=Path, required=True)
    gate.add_argument("--process-receipt", type=Path, required=True)
    gate.add_argument("--heartbeat", type=Path, required=True)
    gate.add_argument("--plateau-seconds", type=float, default=300.0)
    gate.add_argument("--settle-seconds", type=float, default=2.0)
    gate.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "supervise":
            command = args.simulator_command
            if command and command[0] == "--":
                command = command[1:]
            return supervise(
                args.package_id,
                args.execution_id,
                args.attempt_id,
                args.attempt_root,
                args.cwd,
                command,
                args.receipt,
                args.heartbeat_source,
                args.heartbeat_output,
                args.heartbeat_regex,
                args.timescale,
                args.heartbeat_interval,
                args.term_grace,
                args.kill_grace,
                args.runtime_timeout_seconds,
            )
        report = quiesce(
            args.attempt_root,
            args.process_receipt,
            args.heartbeat,
            args.plateau_seconds,
            args.settle_seconds,
        )
        atomic_write(args.output, report)
        print(json.dumps(report, sort_keys=True))
        return 0 if report["pass"] else 1
    except (OSError, json.JSONDecodeError, QuiescenceError) as error:
        print(f"{type(error).__name__}: {error}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
