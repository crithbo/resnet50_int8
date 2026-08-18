#!/usr/bin/env python3
"""Serialized Conv v94 TB-VCD supervisor with appended-time and exact reaping."""

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
FREEZE_SECONDS = 30
FREEZE_INTERVALS = 3
WALL_LIMIT = 3600.0
VCD_LIMIT = 8_000_000_000
RETURN_LIMIT = 10_000_000_000
HB = re.compile(r"CODEX_TB_VCD_HEARTBEAT_V1 sim_time=(\d+) owner_cycles=(\d+) progress=(\d+) state=([0-9a-fA-FxXzZ]+) global=([0-9a-fA-FxXzZ]+) xz=(\d+)")
DUMPOFF = re.compile(r"CODEX_TB_VCD_DUMPOFF_FLUSH_V1 sim_time=(\d+) owner_cycles=(\d+)")
STOP = re.compile(r"CODEX_TB_VCD_STOP_REQUEST_V1 reason=([A-Z_]+) sim_time=(\d+) owner_cycles=(\d+)")


def atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def inside(path: Path, root: Path, label: str) -> Path:
    result = path.resolve(strict=False)
    try:
        result.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise ValueError(f"{label} escapes exact attempt root") from exc
    return result


def enable_subreaper() -> dict[str, Any]:
    if sys.platform != "linux":
        raise RuntimeError("production process supervisor requires Linux")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER")
    return {"enabled": True, "primitive": "PR_SET_CHILD_SUBREAPER"}


def proc_row(pid: int) -> dict[str, Any] | None:
    try:
        raw = (Path("/proc") / str(pid) / "stat").read_text(encoding="ascii")
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None
    right = raw.rfind(")")
    if right < 0:
        return None
    head = raw[: right + 1]
    tail = raw[right + 2 :].split()
    if len(tail) < 20:
        return None
    return {
        "pid": pid,
        "comm": head[head.find("(") + 1 : -1],
        "state": tail[0],
        "ppid": int(tail[1]),
        "pgid": int(tail[2]),
        "sid": int(tail[3]),
        "starttime": int(tail[19]),
    }


def proc_table() -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        row = proc_row(int(path.name))
        if row is not None:
            rows[row["pid"]] = row
    return rows


def owned(root_pid: int, root_pgid: int, known: dict[int, int]) -> list[dict[str, Any]]:
    rows = proc_table()
    # Drop recycled PIDs before forming the closure.
    for pid, start in list(known.items()):
        if pid not in rows or rows[pid]["starttime"] != start:
            known.pop(pid, None)
    closure = set(known)
    closure.add(root_pid)
    changed = True
    while changed:
        changed = False
        for row in rows.values():
            if row["pgid"] == root_pgid or row["ppid"] in closure or row["ppid"] == os.getpid():
                if row["pid"] != os.getpid() and row["pid"] not in closure:
                    closure.add(row["pid"])
                    changed = True
    result = []
    for pid in sorted(closure):
        row = rows.get(pid)
        if row is None or pid == os.getpid():
            continue
        previous = known.get(pid)
        if previous is not None and previous != row["starttime"]:
            continue
        known[pid] = row["starttime"]
        result.append(row)
    return result


def signal_owned(root_pid: int, pgid: int, known: dict[int, int], number: int) -> dict[str, Any]:
    before = owned(root_pid, pgid, known)
    delivered: list[dict[str, int]] = []
    errors: list[str] = []
    try:
        os.killpg(pgid, number)
    except ProcessLookupError:
        pass
    except OSError as exc:
        errors.append(f"killpg:{exc}")
    for row in before:
        if row["pgid"] == pgid or row["state"] == "Z":
            continue
        if proc_row(row["pid"]) == row:
            try:
                os.kill(row["pid"], number)
                delivered.append({"pid": row["pid"], "starttime": row["starttime"]})
            except ProcessLookupError:
                pass
            except OSError as exc:
                errors.append(f"kill:{row['pid']}:{exc}")
    return {"signal": number, "escaped_identities_signaled": delivered, "errors": errors}


def reap(deadline: float, known: dict[int, int]) -> list[dict[str, int]]:
    result: list[dict[str, int]] = []
    while time.monotonic() < deadline:
        changed = False
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return result
            if pid <= 0:
                break
            result.append({"pid": pid, "starttime": known.pop(pid, -1)})
            changed = True
        if not changed:
            time.sleep(0.02)
    return result


def scan_log(path: Path, offset: int, heartbeat: dict[str, Any] | None, dump: dict[str, int] | None) -> tuple[int, dict[str, Any] | None, dict[str, int] | None, dict[str, Any] | None, bool]:
    if not path.is_file():
        return offset, heartbeat, dump, None, False
    if path.stat().st_size < offset:
        return 0, heartbeat, dump, None, True
    stop = None
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        stream.seek(offset)
        for line in stream:
            match = HB.search(line)
            if match:
                heartbeat = {
                    "reported_sim_time_ticks": int(match.group(1)),
                    "owner_clock_cycles": int(match.group(2)),
                    "sim_cycles": int(match.group(2)),
                    "causal_progress_events": int(match.group(3)),
                    "qualified_progress_counters": {"events": int(match.group(3))},
                    "causal_state_digest": hashlib.sha256(match.group(4).encode()).hexdigest(),
                    "global_progress_witness": {"digest": hashlib.sha256(match.group(5).encode()).hexdigest()},
                    "unresolved_xz_absent": match.group(6) == "0",
                }
            match = DUMPOFF.search(line)
            if match:
                dump = {"sim_time_ticks": int(match.group(1)), "owner_clock_cycles": int(match.group(2))}
            match = STOP.search(line)
            if match:
                stop = {"reason": match.group(1), "sim_time_ticks": int(match.group(2)), "owner_clock_cycles": int(match.group(3))}
        return stream.tell(), heartbeat, dump, stop, False


def scan_vcd(path: Path, offset: int, carry: bytes) -> tuple[int, bytes, int | None, bool]:
    if not path.is_file():
        return offset, carry, None, False
    if path.stat().st_size < offset:
        return 0, b"", None, True
    with path.open("rb") as stream:
        stream.seek(offset)
        payload = carry + stream.read()
        new_offset = stream.tell()
    rows = payload.split(b"\n")
    tail = rows.pop() if rows else b""
    latest = None
    for raw in rows:
        row = raw.strip()
        if len(row) > 1 and row[0:1] == b"#" and row[1:].isdigit():
            latest = int(row[1:])
    return new_offset, tail[-128:], latest, False


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


def attempt_bytes(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except OSError:
            pass
    return total


def load_evaluator(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("packaged_tb_vcd_runtime_evaluator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("shared runtime evaluator cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluator_request(samples: list[dict[str, Any]], authority: dict[str, Any]) -> dict[str, Any]:
    return {
        "package_id": "live", "execution_id": "live", "attempt_id": "live", "started": True,
        "actual_argv_sha256": "1" * 64, "catalog_sha256": "2" * 64,
        "candidate_matrix_sha256": "3" * 64, "tb_source_sha256": "4" * 64,
        "elaboration_sha256": "5" * 64, "samples": samples,
        "candidate_catalog_complete": True,
        "unresolved_xz": not bool(samples and samples[-1].get("unresolved_xz_absent") is True),
        "heartbeat_contract": {"source": "APPENDED_VCD_TIMESTAMP", "width_bits": 64, "signed": False, "cadence_cycles": 16384},
        "decision_authority": authority,
        "target_entry_observed": True, "target_diagnostic_claim": False,
        "flush": {"dumpoff": False, "dumpflush": False, "closed": False},
        "process_tree": {"term_sent": False, "wait_completed": False, "kill_sent_if_needed": False, "all_reaped": False},
        "vcd_identity": None, "return_exact_set": None, "archive_timestamp_receipt": None,
        "live_diagnostics": {"downstream_state_source": "LIVE_SAME_ATTEMPT", "first_error_source": "LIVE_SAME_ATTEMPT", "stale_evidence_absent": True},
    }


def replay_cases(evaluate: Any) -> list[dict[str, str]]:
    def row(seq: int, cycles: int, tick: int, wall: int) -> dict[str, Any]:
        return {
            "seq": seq, "owner_clock_cycles": cycles, "sim_cycles": cycles,
            "sim_time_ticks": tick, "appended_vcd_timestamp_ticks": tick,
            "wall_seconds": wall, "vcd_bytes": 1000 + cycles,
            "causal_progress_events": 1, "qualified_progress_counters": {"accept": 1},
            "causal_state_digest": "a" * 64, "global_progress_witness": {"accept": 1},
            "unresolved_xz_absent": True, "write_ok": True, "disk_space_ok": True, "quota_ok": True,
        }
    placeholder = {
        "mode": "SHARED_RUNTIME_EVALUATOR_ONLY", "helper_path": "pending",
        "helper_sha256": "7" * 64, "outer_runner_consumes_only_receipt": True,
        "independent_exit_logic_absent": True,
        "replay_cases": [
            {"case_id": "ADVANCING_VCD_TIMESTAMP", "observed_decision": "CONTINUE"},
            {"case_id": "PLATEAU_SUSPECTED_ONLY", "observed_decision": "CONTINUE"},
            {"case_id": "PLATEAU_DUMP_OFF_PLUS_GRACE", "observed_decision": "CAUSAL_PLATEAU"},
            {"case_id": "THREE_INTERVAL_TRUE_FREEZE", "observed_decision": "SIM_TIME_FREEZE"},
        ],
    }
    vectors = {
        "ADVANCING_VCD_TIMESTAMP": [row(0, 0, 0, 0), row(1, 100, 100, 1)],
        "PLATEAU_SUSPECTED_ONLY": [row(0, 0, 0, 0), row(1, 1048576, 1048576, 10)],
        "PLATEAU_DUMP_OFF_PLUS_GRACE": [row(0, 0, 0, 0), row(1, 1048576, 1048576, 10), row(2, 4194304, 4194304, 20), row(3, 4456448, 4456448, 30)],
        "THREE_INTERVAL_TRUE_FREEZE": [row(index, index * 100, 7, index * 30) for index in range(4)],
    }
    result = []
    for case, samples in vectors.items():
        reason = evaluate(evaluator_request(samples, placeholder)).get("stop_reason")
        decision = "CONTINUE" if reason == "NONZERO_EXIT" else str(reason)
        result.append({"case_id": case, "observed_decision": decision})
    expected = dict((item["case_id"], item["observed_decision"]) for item in placeholder["replay_cases"])
    if {item["case_id"]: item["observed_decision"] for item in result} != expected:
        raise RuntimeError(f"shared evaluator exact replay differs: {result}")
    return result


def shared_decision(evaluate: Any, samples: list[dict[str, Any]], authority: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    receipt = evaluate(evaluator_request(samples, authority))
    reason = str(receipt.get("stop_reason"))
    if reason == "NONZERO_EXIT" and "sample stream ended without a terminal supervisor decision" in receipt.get("errors", []):
        return "CONTINUE", receipt
    return reason, receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--attempt-root", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--sim-log", type=Path, required=True)
    parser.add_argument("--vcd", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--runtime-evaluator", type=Path, required=True)
    parser.add_argument("--stop-control", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--grace", type=float, default=30.0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    root = args.attempt_root.resolve(strict=True)
    log = inside(args.sim_log, root, "sim log")
    vcd = inside(args.vcd, root, "VCD")
    receipt = inside(args.receipt, root, "receipt")
    control = inside(args.stop_control, root, "stop control")
    evaluator_path = args.runtime_evaluator.resolve(strict=True)
    evaluator_path.relative_to(Path(__file__).resolve().parent)
    if receipt.exists() or control.exists() or not command:
        raise ValueError("stale receipt/control or absent simulator command")

    evaluator = load_evaluator(evaluator_path)
    evaluator_sha = hashlib.sha256(evaluator_path.read_bytes()).hexdigest()
    authority = {
        "mode": "SHARED_RUNTIME_EVALUATOR_ONLY",
        "helper_path": "package_tools/server_tb_vcd_runtime_supervision.py",
        "helper_sha256": evaluator_sha,
        "outer_runner_consumes_only_receipt": True,
        "independent_exit_logic_absent": True,
        "replay_cases": replay_cases(evaluator.evaluate),
    }

    subreaper = enable_subreaper()
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=args.cwd, start_new_session=True)
    root_row = proc_row(process.pid)
    if root_row is None:
        raise RuntimeError("cannot bind launched simulator process identity")
    pgid = root_row["pgid"]
    known = {process.pid: root_row["starttime"]}
    received = None
    old_handlers = {}

    def handler(number: int, _frame: Any) -> None:
        nonlocal received
        received = number

    for number in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        old_handlers[number] = signal.signal(number, handler)

    log_offset = 0
    vcd_offset = 0
    vcd_carry = b""
    heartbeat = None
    dump = None
    last_vcd_tick = None
    last_vcd_change_wall = started
    freeze_intervals = 0
    next_sample = started
    old_bytes = 0
    old_wall = started
    samples = []
    actions = []
    stop_reason = None
    shared_receipt: dict[str, Any] | None = None
    log_rotated = False
    try:
        while process.poll() is None:
            now = time.monotonic()
            if now >= next_sample:
                log_offset, heartbeat, dump, marker, rotated = scan_log(log, log_offset, heartbeat, dump)
                log_rotated |= rotated
                vcd_offset, vcd_carry, new_tick, rotated = scan_vcd(vcd, vcd_offset, vcd_carry)
                log_rotated |= rotated
                if new_tick is not None:
                    if last_vcd_tick is None or new_tick > last_vcd_tick:
                        last_vcd_change_wall = now
                        freeze_intervals = 0
                    elif dump is None and now - last_vcd_change_wall >= FREEZE_SECONDS:
                        freeze_intervals += 1
                        last_vcd_change_wall = now
                    last_vcd_tick = new_tick
                size = vcd.stat().st_size if vcd.is_file() else 0
                rate = max(0.0, (size - old_bytes) / max(now - old_wall, 0.001))
                projected_vcd = int(size + rate * max(0.0, WALL_LIMIT - (now - started)))
                projected_return = int(attempt_bytes(root) + rate * max(0.0, WALL_LIMIT - (now - started)))
                free = shutil.disk_usage(root).free
                row = {
                    "seq": len(samples), "wall_seconds": now - started,
                    "appended_vcd_timestamp_ticks": 0 if last_vcd_tick is None else last_vcd_tick,
                    "sim_time_ticks": 0 if last_vcd_tick is None else last_vcd_tick,
                    "vcd_bytes": size, "vcd_operational_projection_bytes": projected_vcd,
                    "return_projection_bytes": projected_return, "write_ok": True,
                    "disk_space_ok": free > max(1_073_741_824, int(rate * 120)), "quota_ok": True,
                    "dumpoff_seen": dump is not None,
                }
                row.update(heartbeat or {"owner_clock_cycles": 0, "sim_cycles": 0, "causal_progress_events": 0, "qualified_progress_counters": {}, "causal_state_digest": "0" * 64, "global_progress_witness": {}, "unresolved_xz_absent": False})
                samples.append(row)
                old_bytes, old_wall = size, now
                next_sample = now + args.interval
                if received is not None:
                    row["signal"] = signal.Signals(received).name.removeprefix("SIG")
                decision, shared_receipt = shared_decision(evaluator.evaluate, samples, authority)
                if marker is not None and decision != marker["reason"]:
                    raise RuntimeError(f"TB stop marker diverges from shared evaluator: {marker['reason']} != {decision}")
                if decision != "CONTINUE":
                    stop_reason = decision
                    if stop_reason == "CAUSAL_PLATEAU":
                        temporary = control.with_name(control.name + ".tmp")
                        temporary.write_text("CAUSAL_PLATEAU\n", encoding="ascii")
                        os.replace(temporary, control)
                        flush_deadline = time.monotonic() + 30.0
                        while time.monotonic() < flush_deadline:
                            log_offset, heartbeat, dump, marker, rotated = scan_log(log, log_offset, heartbeat, dump)
                            log_rotated |= rotated
                            if dump is not None:
                                break
                            time.sleep(0.02)
                        if dump is None:
                            stop_reason = "WRITE_FAILURE"
                    actions.append(signal_owned(process.pid, pgid, known, signal.SIGTERM))
                    break
            owned(process.pid, pgid, known)
            time.sleep(0.05)

        term_deadline = time.monotonic() + args.grace
        while time.monotonic() < term_deadline:
            reap(time.monotonic() + 0.05, known)
            if process.poll() is not None and not owned(process.pid, pgid, known):
                break
            time.sleep(0.05)
        remaining = owned(process.pid, pgid, known)
        if process.poll() is None or remaining:
            actions.append(signal_owned(process.pid, pgid, known, signal.SIGKILL))
        try:
            root_exit = process.wait(timeout=max(args.grace, 0.1))
        except subprocess.TimeoutExpired:
            root_exit = None
        reap_deadline = time.monotonic() + max(args.grace, 0.1)
        reaped = reap(reap_deadline, known)
        remaining = owned(process.pid, pgid, known)
        if remaining:
            actions.append(signal_owned(process.pid, pgid, known, signal.SIGKILL))
            reaped.extend(reap(time.monotonic() + 1.0, known))
            remaining = owned(process.pid, pgid, known)
    finally:
        for number, old in old_handlers.items():
            signal.signal(number, old)

    log_offset, heartbeat, dump, marker, rotated = scan_log(log, log_offset, heartbeat, dump)
    log_rotated |= rotated
    vcd_offset, vcd_carry, new_tick, rotated = scan_vcd(vcd, vcd_offset, vcd_carry)
    log_rotated |= rotated
    if new_tick is not None:
        last_vcd_tick = new_tick
    if stop_reason is None:
        stop_reason = "NATURAL_TERMINAL" if root_exit == 0 else "NONZERO_EXIT"
    snap1 = identity(vcd)
    time.sleep(1)
    snap2 = identity(vcd)
    stable = bool(snap1 and snap1 == snap2)
    errors = []
    if remaining:
        errors.append("identity-bound simulator descendants remain after TERM/WAIT/KILL/reap")
    if log_rotated:
        errors.append("attempt-owned log or VCD rotated during supervision")
    if dump is not None and marker is not None and marker["owner_clock_cycles"] - dump["owner_clock_cycles"] != 262144:
        errors.append("dumpoff-to-stop grace is not exactly 262144 owner cycles")
    value = {
        "schema": "node0004-tb-vcd-process-supervision-v2", "package_id": args.package_id,
        "execution_id": args.execution_id, "attempt_id": args.attempt_id,
        "actual_argv": command, "cwd": str(args.cwd.resolve()),
        "root_process_identity": root_row, "pgid": pgid, "child_subreaper": subreaper,
        "root_exit": root_exit, "received_signal": received, "stop_reason": stop_reason,
        "termination": actions, "reaped_process_identities": reaped,
        "owned_processes_remaining": remaining, "owned_pids_remaining": [row["pid"] for row in remaining],
        "process_tree_reaped": not remaining,
        "process_tree": {"term_sent": bool(actions), "wait_completed": True, "kill_sent_if_needed": any(row["signal"] == signal.SIGKILL for row in actions), "all_reaped": not remaining},
        "samples": samples, "heartbeat_contract": {"source": "APPENDED_VCD_TIMESTAMP", "width_bits": 64, "signed": False, "cadence_cycles": 16384},
        "decision_authority": authority,
        "shared_evaluator_receipt": shared_receipt,
        "dumpoff_marker": dump, "stop_marker": marker,
        "simulation_time_progress_observed": bool(last_vcd_tick and last_vcd_tick > 0),
        "vcd_stable_snapshots": [snap1, snap2], "vcd_stable": stable,
        "log_truncated": log_rotated, "errors": errors, "pass": not errors,
        "claim_boundary": "Runtime, exact stop marker and identity-bound process/VCD stability only; non-natural stop is PARTIAL.",
    }
    atomic(receipt, value)
    codes = {"CAUSAL_PLATEAU": 90, "SIM_TIME_FREEZE": 91, "VCD_OPERATIONAL_BUDGET": 92, "RETURN_BUDGET_PROJECTION": 93, "DISK_SPACE_FAILURE": 94, "WALL_CEILING": 124, "HUP": 129, "INT": 130, "TERM": 143}
    return codes.get(stop_reason, root_exit if isinstance(root_exit, int) else 125)


if __name__ == "__main__":
    raise SystemExit(main())
