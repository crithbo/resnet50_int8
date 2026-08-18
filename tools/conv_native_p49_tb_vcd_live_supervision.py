#!/usr/bin/env python3
"""Direct native-Conv TB-VCD runtime-v3 shared-decision process supervisor."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
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
INTERVAL_SECONDS = 30.0
FREEZE_INTERVALS = 3
WALL_SECONDS = 3600.0
VCD_BUDGET = 8_000_000_000
RETURN_BUDGET = 10_000_000_000
SOFT_WARNING = 100_000_000
HEARTBEAT = re.compile(
    r"CODEX_TBVCD_HEARTBEAT_V2\s+sim_time=(?P<time>\d+)\s+"
    r"owner_cycles=(?P<cycles>\d+)\s+progress=(?P<progress>\d+)\s+"
    r"state=(?P<state>[0-9a-fA-FxXzZ]+)\s+global=(?P<global>\d+)\s+"
    r"unresolved_xz=(?P<xz>[01])\s+target_entry=(?P<entry>[01])"
)
REPLAY_CASES = [
    {"case_id": "ADVANCING_VCD_TIMESTAMP", "observed_decision": "CONTINUE"},
    {"case_id": "PLATEAU_SUSPECTED_ONLY", "observed_decision": "CONTINUE"},
    {"case_id": "PLATEAU_DUMP_OFF_PLUS_GRACE", "observed_decision": "CAUSAL_PLATEAU"},
    {"case_id": "THREE_INTERVAL_TRUE_FREEZE", "observed_decision": "SIM_TIME_FREEZE"},
]


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def inside(path: Path, root: Path, label: str) -> Path:
    candidate = path.resolve(strict=False)
    try:
        candidate.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise ValueError(f"{label} escapes attempt root") from exc
    return candidate


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
        capture_output=True,
        text=True,
        check=False,
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
        start_ticks = process_start_ticks(pid)
        # `ps` observes itself while it is producing this snapshot.  That
        # short-lived helper can disappear before /proc/<pid>/stat is read;
        # retaining such a row makes a completely reaped simulator tree look
        # live.  A row without an immutable start-time identity cannot be
        # owned safely and is therefore excluded from the snapshot.
        if start_ticks is None:
            continue
        rows.append(
            {
                "pid": pid,
                "ppid": ppid,
                "pgid": pgid,
                "sid": sid,
                "stat": fields[4],
                "comm": fields[5],
                "start_ticks": start_ticks,
            }
        )
    return rows


def process_start_ticks(pid: int) -> int | None:
    try:
        # /proc/<pid>/stat field 22 is process start time in clock ticks.  The
        # comm field may contain spaces, so split only after the final ')'.
        payload = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
        tail = payload[payload.rfind(")") + 2 :].split()
        return int(tail[19])
    except (OSError, ValueError, IndexError):
        return None


def owned(root_pid: int, pgid: int, known: dict[int, int | None]) -> list[dict[str, Any]]:
    rows = process_rows()
    by_pid = {row["pid"]: row for row in rows}
    children: dict[int, list[int]] = {}
    for row in rows:
        children.setdefault(row["ppid"], []).append(row["pid"])
    closure = {root_pid, *known.keys()}
    pending = list(closure)
    while pending:
        parent = pending.pop()
        for child in children.get(parent, []):
            if child not in closure:
                closure.add(child)
                pending.append(child)
    closure.update(row["pid"] for row in rows if row["pgid"] == pgid)
    closure.update(row["pid"] for row in rows if row["ppid"] == os.getpid())
    result: list[dict[str, Any]] = []
    for pid in sorted(closure):
        if pid not in by_pid or pid == os.getpid():
            continue
        row = by_pid[pid]
        remembered = known.get(pid)
        if remembered is not None and row.get("start_ticks") != remembered:
            # PID reuse is not ownership.
            continue
        known.setdefault(pid, row.get("start_ticks"))
        result.append(row)
    return result


def signal_owned(
    root_pid: int, pgid: int, known: dict[int, int | None], number: int
) -> dict[str, Any]:
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
        known.setdefault(row["pid"], row.get("start_ticks"))
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


def reap(deadline: float, known: dict[int, int | None]) -> list[int]:
    result: list[int] = []
    while time.monotonic() < deadline:
        changed = False
        while True:
            try:
                pid, _status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return result
            if pid <= 0:
                break
            result.append(pid)
            known.pop(pid, None)
            changed = True
        if not changed:
            time.sleep(0.05)
    return result


def scan_log(
    path: Path, offset: int
) -> tuple[int, dict[str, Any] | None, bool, bool]:
    if not path.is_file():
        return offset, None, False, False
    if path.stat().st_size < offset:
        return 0, None, True, False
    latest: dict[str, Any] | None = None
    target_entry = False
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        stream.seek(offset)
        for line in stream:
            match = HEARTBEAT.search(line)
            if match:
                latest = {
                    "display_sim_time_ticks": int(match.group("time")),
                    "owner_clock_cycles": int(match.group("cycles")),
                    "causal_progress_events": int(match.group("progress")),
                    "qualified_progress_counters": {
                        "total": int(match.group("progress"))
                    },
                    "causal_state_digest": match.group("state").lower(),
                    "global_progress_witness": {"count": int(match.group("global"))},
                    "unresolved_xz": match.group("xz") == "1",
                    "target_entry_observed": match.group("entry") == "1",
                }
            if "CODEX_TBVCD_TARGET_ENTRY_V2" in line:
                target_entry = True
        return stream.tell(), latest, False, target_entry


def scan_vcd_timestamp(
    path: Path, offset: int, carry: bytes
) -> tuple[int, bytes, int | None, bool]:
    """Read only newly appended bytes and return the last complete #timestamp."""
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


def append_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def attempt_bytes(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_evaluator(path: Path) -> tuple[Any, dict[str, Any]]:
    resolved = path.resolve(strict=True)
    spec = importlib.util.spec_from_file_location("server_tb_vcd_runtime_supervision", resolved)
    if spec is None or spec.loader is None:
        raise RuntimeError("shared runtime evaluator cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    authority = {
        "mode": "SHARED_RUNTIME_EVALUATOR_ONLY",
        "helper_path": "package_tools/server_tb_vcd_runtime_supervision.py",
        "helper_sha256": sha256(resolved),
        "outer_runner_consumes_only_receipt": True,
        "independent_exit_logic_absent": True,
        "replay_cases": REPLAY_CASES,
    }
    return module, authority


def shared_decision(
    module: Any,
    authority: dict[str, Any],
    args: argparse.Namespace,
    samples: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    request = {
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "started": True,
        "actual_argv_sha256": "0" * 64,
        "catalog_sha256": "0" * 64,
        "candidate_matrix_sha256": "0" * 64,
        "tb_source_sha256": "0" * 64,
        "elaboration_sha256": "0" * 64,
        "samples": samples,
        "candidate_catalog_complete": True,
        "unresolved_xz": bool(samples[-1].get("unresolved_xz", True)),
        "flush": {"dumpoff": False, "dumpflush": False, "closed": False},
        "process_tree": {
            "term_sent": False,
            "wait_completed": False,
            "kill_sent_if_needed": False,
            "all_reaped": False,
        },
        "heartbeat_contract": {
            "source": "APPENDED_VCD_TIMESTAMP",
            "width_bits": 64,
            "signed": False,
            "cadence_cycles": 16_384,
        },
        "decision_authority": authority,
        "archive_timestamp_receipt": None,
        "target_entry_observed": bool(samples[-1].get("target_entry_observed")),
        "target_diagnostic_claim": False,
        "vcd_identity": None,
        "return_exact_set": None,
        "live_diagnostics": {
            "downstream_state_source": "LIVE_SAME_ATTEMPT",
            "first_error_source": "LIVE_SAME_ATTEMPT",
            "stale_evidence_absent": True,
        },
    }
    receipt = module.evaluate(request)
    errors = receipt.get("errors") if isinstance(receipt.get("errors"), list) else []
    pending_only = receipt.get("stop_reason") == "NONZERO_EXIT" and (
        "sample stream ended without a terminal supervisor decision" in errors
    )
    return ("CONTINUE" if pending_only else str(receipt.get("stop_reason"))), receipt


def supervise(args: argparse.Namespace) -> int:
    command = list(args.simulator_command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError("simulator command is required")
    root = args.attempt_root.resolve(strict=True)
    sim_log = inside(args.sim_log, root, "sim log")
    vcd = inside(args.vcd, root, "VCD")
    samples_path = inside(args.samples, root, "samples")
    heartbeat_path = inside(args.heartbeat_output, root, "heartbeat")
    process_receipt = inside(args.process_receipt, root, "process receipt")
    safety_receipt = inside(args.safety_receipt, root, "safety receipt")
    decision_receipt = inside(args.decision_receipt, root, "decision receipt")
    console_log = inside(args.console_log, root, "console log") if args.console_log else None
    for path in (samples_path, heartbeat_path, process_receipt, safety_receipt, decision_receipt, console_log):
        if path is None:
            continue
        if path.exists():
            raise ValueError(f"attempt-owned output already exists: {path}")

    evaluator, decision_authority = load_evaluator(args.runtime_evaluator)

    subreaper = enable_subreaper()
    started = time.monotonic()
    started_ns = time.monotonic_ns()
    console_stream = console_log.open("wb") if console_log is not None else None
    process = subprocess.Popen(
        command,
        cwd=args.cwd,
        start_new_session=True,
        stdout=console_stream,
        stderr=subprocess.STDOUT if console_stream is not None else None,
    )
    pgid = os.getpgid(process.pid)
    known: dict[int, int | None] = {process.pid: process_start_ticks(process.pid)}
    received: int | None = None
    old_handlers: dict[int, Any] = {}

    def handler(number: int, _frame: Any) -> None:
        nonlocal received
        received = number

    for number in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        old_handlers[number] = signal.signal(number, handler)

    log_offset = 0
    vcd_offset = 0
    vcd_carry = b""
    last_heartbeat: dict[str, Any] = {
        "display_sim_time_ticks": 0,
        "owner_clock_cycles": 0,
        "causal_progress_events": 0,
        "qualified_progress_counters": {},
        "causal_state_digest": "absent",
        "global_progress_witness": {},
        "unresolved_xz": True,
        "target_entry_observed": False,
    }
    last_vcd_tick = 0
    previous_size = 0
    previous_wall = 0.0
    next_sample = started
    seq = 0
    samples: list[dict[str, Any]] = []
    stop_reason: str | None = None
    rotations: list[str] = []
    actions: list[dict[str, Any]] = []
    reaped: list[int] = []
    remaining: list[dict[str, Any]] = []
    root_exit: int | None = None
    try:
        while process.poll() is None:
            now = time.monotonic()
            if now >= next_sample:
                log_offset, heartbeat, log_rotated, target_marker = scan_log(
                    sim_log, log_offset
                )
                if log_rotated:
                    rotations.append("sim_log")
                if heartbeat is not None:
                    last_heartbeat.update(heartbeat)
                if target_marker:
                    last_heartbeat["target_entry_observed"] = True
                vcd_offset, vcd_carry, current_tick, vcd_rotated = scan_vcd_timestamp(
                    vcd, vcd_offset, vcd_carry
                )
                if vcd_rotated:
                    rotations.append("vcd")
                timestamp_regression = current_tick is not None and current_tick < last_vcd_tick
                if current_tick is not None:
                    last_vcd_tick = current_tick
                wall = now - started
                try:
                    size = vcd.stat().st_size if vcd.is_file() else 0
                    write_ok = True
                except OSError:
                    size = previous_size
                    write_ok = False
                delta_wall = max(0.001, wall - previous_wall)
                rate = max(0, size - previous_size) / delta_wall
                vcd_projection = int(size + rate * max(0.0, WALL_SECONDS - wall))
                return_projection = int(
                    attempt_bytes(root) + rate * max(0.0, WALL_SECONDS - wall)
                )
                try:
                    free = shutil.disk_usage(root).free
                    disk_ok = free > max(1_073_741_824, int(rate * 120.0))
                except OSError:
                    free = 0
                    disk_ok = False
                row = {
                    "seq": seq,
                    "host_monotonic_ns": time.monotonic_ns(),
                    "wall_seconds": wall,
                    "sim_time_ticks": last_vcd_tick,
                    "appended_vcd_timestamp_ticks": last_vcd_tick,
                    **last_heartbeat,
                    "vcd_bytes": size,
                    "vcd_operational_projection_bytes": vcd_projection,
                    "return_projection_bytes": return_projection,
                    "disk_free_bytes": free,
                    "disk_space_ok": disk_ok,
                    "write_ok": write_ok,
                    "quota_ok": True,
                    "soft_warning_exceeded": size > SOFT_WARNING,
                    "timescale": "1ps",
                }
                append_row(samples_path, row)
                append_row(heartbeat_path, row)
                samples.append(row)
                seq += 1
                previous_size = size
                previous_wall = wall
                next_sample = now + INTERVAL_SECONDS
                decision, evaluator_receipt = shared_decision(
                    evaluator, decision_authority, args, samples
                )
                atomic_json(
                    decision_receipt,
                    {
                        "schema": "server-tb-vcd-live-decision-envelope-v1",
                        "package_id": args.package_id,
                        "execution_id": args.execution_id,
                        "attempt_id": args.attempt_id,
                        "decision": decision,
                        "sample_count": len(samples),
                        "decision_authority": decision_authority,
                        "shared_evaluator_receipt": evaluator_receipt,
                    },
                )
                if decision != "CONTINUE":
                    stop_reason = decision
            if received is not None:
                signal_name = signal.Signals(received).name.removeprefix("SIG")
                if not samples or samples[-1].get("signal") != signal_name:
                    signal_row = dict(samples[-1]) if samples else {
                        "seq": 0,
                        "wall_seconds": time.monotonic() - started,
                        "sim_cycles": 0,
                        "owner_clock_cycles": 0,
                        "causal_progress_events": 0,
                        "qualified_progress_counters": {},
                        "causal_state_digest": "absent",
                        "global_progress_witness": {},
                        "unresolved_xz": True,
                        "appended_vcd_timestamp_ticks": last_vcd_tick,
                        "vcd_bytes": 0,
                    }
                    signal_row.update({"seq": seq, "signal": signal_name})
                    append_row(samples_path, signal_row)
                    samples.append(signal_row)
                decision, evaluator_receipt = shared_decision(
                    evaluator, decision_authority, args, samples
                )
                atomic_json(
                    decision_receipt,
                    {
                        "schema": "server-tb-vcd-live-decision-envelope-v1",
                        "package_id": args.package_id,
                        "execution_id": args.execution_id,
                        "attempt_id": args.attempt_id,
                        "decision": decision,
                        "sample_count": len(samples),
                        "decision_authority": decision_authority,
                        "shared_evaluator_receipt": evaluator_receipt,
                    },
                )
                stop_reason = decision
            if stop_reason is not None:
                actions.append(signal_owned(process.pid, pgid, known, signal.SIGTERM))
                break
            for row in owned(process.pid, pgid, known):
                known.setdefault(row["pid"], row.get("start_ticks"))
            time.sleep(0.1)

        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline and owned(process.pid, pgid, known):
            reaped.extend(reap(min(deadline, time.monotonic() + 0.25), known))
            time.sleep(0.05)
        remaining = owned(process.pid, pgid, known)
        if remaining:
            actions.append(signal_owned(process.pid, pgid, known, signal.SIGKILL))
        try:
            root_exit = process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            actions.append(signal_owned(process.pid, pgid, known, signal.SIGKILL))
            try:
                root_exit = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                root_exit = None
        reap_deadline = time.monotonic() + 60.0
        reaped.extend(reap(min(reap_deadline, time.monotonic() + 1.0), known))
        remaining = owned(process.pid, pgid, known)
        while remaining and time.monotonic() < reap_deadline:
            # KILL was already issued above.  Observe/reap without producing a
            # tight repeated-signal storm when an escaped process is not our
            # waitable child.
            newly_reaped = reap(min(reap_deadline, time.monotonic() + 1.0), known)
            reaped.extend(newly_reaped)
            remaining = owned(process.pid, pgid, known)
            if not newly_reaped and remaining:
                time.sleep(0.1)
    finally:
        if console_stream is not None:
            console_stream.flush()
            os.fsync(console_stream.fileno())
            console_stream.close()
        for number, old in old_handlers.items():
            signal.signal(number, old)

    if stop_reason is None:
        stop_reason = "PROCESS_EXIT"
    errors: list[str] = []
    if rotations:
        errors.append("attempt-owned log or VCD rotated during supervision")
    if remaining:
        errors.append("owned simulator descendants remain after TERM/WAIT/KILL/reap")
    exit_code = (
        int(root_exit)
        if stop_reason == "PROCESS_EXIT" and isinstance(root_exit, int)
        else {
            "HUP": 129,
            "INT": 130,
            "TERM": 143,
            "SIM_TIME_FREEZE": 124,
            "WALL_CEILING": 124,
        }.get(stop_reason, 96)
    )
    process_value = {
        "schema": "conv-native-tb-vcd-direct-process-supervision-v2",
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
        "termination": actions,
        "reaped_pids": sorted(set(reaped)),
        "owned_pids_remaining": [row["pid"] for row in remaining],
        "owned_process_identity": [
            {"pid": row["pid"], "start_ticks": row.get("start_ticks"), "pgid": row.get("pgid")}
            for row in remaining
        ],
        "process_tree_reaped": not remaining,
        "sim_time_progress_observed": last_vcd_tick > 0,
        "last_appended_vcd_timestamp_ticks": last_vcd_tick,
        "target_entry_observed": last_heartbeat["target_entry_observed"],
        "heartbeat_source": "APPENDED_VCD_TIMESTAMP",
        "heartbeat_width_bits": 64,
        "heartbeat_signed": False,
        "heartbeat_cadence_cycles": 16_384,
        "decision_authority": decision_authority,
        "outer_runner_consumed_shared_receipt_only": True,
        "samples": samples,
        "errors": errors,
        "diagnostic_status": (
            "DIAGNOSTIC_EVIDENCE_COMPLETE" if not errors else "DIAGNOSTIC_EVIDENCE_INCOMPLETE"
        ),
        "supervisor_exit": exit_code,
        "claim_boundary": "Process/runtime transport only; no DUT or natural-terminal claim.",
    }
    atomic_json(process_receipt, process_value)
    atomic_json(
        safety_receipt,
        {
            "schema": "server-tb-vcd-live-safety-receipt-v2",
            "package_id": args.package_id,
            "execution_id": args.execution_id,
            "attempt_id": args.attempt_id,
            "stop_reason": stop_reason,
            "wrapped_supervisor_exit": exit_code,
            "sample_count": len(samples),
            "appended_vcd_timestamp_ticks": last_vcd_tick,
            "shared_evaluator_decision": stop_reason,
            "target_entry_observed": last_heartbeat["target_entry_observed"],
            "thresholds": {
                "sim_time_freeze_intervals": FREEZE_INTERVALS,
                "sim_time_freeze_interval_seconds": int(INTERVAL_SECONDS),
                "wall_ceiling_seconds": int(WALL_SECONDS),
                "operational_vcd_budget_bytes": VCD_BUDGET,
                "return_budget_bytes": RETURN_BUDGET,
                "soft_warning_bytes": SOFT_WARNING,
            },
            "errors": errors,
            "claim_boundary": "Independent runtime safety only; no DUT outcome claim.",
        },
    )
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--attempt-root", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--process-supervisor", type=Path, required=False)
    parser.add_argument("--runtime-evaluator", type=Path, required=True)
    parser.add_argument("--decision-receipt", type=Path, required=True)
    parser.add_argument("--console-log", type=Path)
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
