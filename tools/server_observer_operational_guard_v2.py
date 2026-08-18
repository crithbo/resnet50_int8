#!/usr/bin/env python3
"""Supervise one observer phase with symlink-safe live-tree accounting.

This helper never follows a symlink while measuring a live compiler/simulator
tree.  An exact-owned symlink whose lexical target remains inside the declared
owned roots is recorded as an entry and is not traversed.  Concurrent
create/delete races are resampled a bounded number of times.  Any monitor
exception after the child starts terminates and reaps the complete owned tree,
persists an emergency receipt, and remains an infrastructure failure rather
than masquerading as a production compile error.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable


SCHEMA = "server-observer-operational-guard-receipt-v2"
GUARD_EXIT = 122
PRESTART_GUARD_EXIT = 2
PR_SET_CHILD_SUBREAPER = 36
PROC_ROOT = Path("/proc")
ProcessKey = tuple[int, int]


class GuardError(ValueError):
    pass


class LiveTreeRace(RuntimeError):
    """A live entry disappeared between directory enumeration and lstat."""


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_bytes(canonical_bytes(value))
    os.replace(temporary, path)


def append_stderr(path: Path | None, message: str) -> None:
    rendered = message.rstrip("\n") + "\n"
    if path is None:
        print(rendered, end="", file=sys.stderr, flush=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(rendered)
        stream.flush()
        os.fsync(stream.fileno())


def file_identity(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return {"path": str(path), "status": "ABSENT"}
    if not stat.S_ISREG(info.st_mode):
        return {"path": str(path), "status": "NOT_REGULAR_NOFOLLOW"}
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return {"path": str(path), "bytes": size, "sha256": digest.hexdigest()}


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.path.normpath(os.fspath(path))))


def _inside(path: Path, roots: list[Path]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def require_real_directory(path: Path, label: str) -> Path:
    lexical = _absolute_lexical(path)
    try:
        info = os.lstat(lexical)
    except FileNotFoundError as exc:
        raise GuardError(f"{label} is absent: {lexical}") from exc
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise GuardError(f"{label} must be a real directory: {lexical}")
    resolved = Path(os.path.realpath(lexical))
    if resolved != lexical:
        raise GuardError(f"{label} has a symlinked ancestor: {lexical}")
    return lexical


def _lexical_link_target(link: Path, raw_target: str) -> Path:
    target = Path(raw_target)
    if not target.is_absolute():
        target = link.parent / target
    return _absolute_lexical(target)


def _scan_owned_roots_once(roots: list[Path]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    total = 0
    for root in roots:
        stack = [root]
        while stack:
            directory = stack.pop()
            try:
                with os.scandir(directory) as iterator:
                    children = sorted(iterator, key=lambda item: item.name)
            except FileNotFoundError as exc:
                raise LiveTreeRace(str(directory)) from exc
            for child in children:
                path = Path(child.path)
                try:
                    info = child.stat(follow_symlinks=False)
                except FileNotFoundError as exc:
                    raise LiveTreeRace(str(path)) from exc
                relative_owner = next(root_item for root_item in roots if _inside(path, [root_item]))
                relative = path.relative_to(relative_owner).as_posix()
                if stat.S_ISLNK(info.st_mode):
                    try:
                        raw_target = os.readlink(path)
                    except FileNotFoundError as exc:
                        raise LiveTreeRace(str(path)) from exc
                    lexical_target = _lexical_link_target(path, raw_target)
                    if not _inside(lexical_target, roots):
                        raise GuardError(f"owned live-tree symlink target escapes declared roots: {path} -> {raw_target}")
                    total += info.st_size
                    entries.append({
                        "owner_root": str(relative_owner),
                        "path": str(path),
                        "relative_path": relative,
                        "entry_type": "symlink_no_follow",
                        "bytes": info.st_size,
                        "link_target": raw_target,
                        "lexical_target": str(lexical_target),
                    })
                elif stat.S_ISDIR(info.st_mode):
                    entries.append({
                        "owner_root": str(relative_owner),
                        "path": str(path),
                        "relative_path": relative,
                        "entry_type": "directory",
                        "bytes": 0,
                    })
                    stack.append(path)
                elif stat.S_ISREG(info.st_mode):
                    total += info.st_size
                    entries.append({
                        "owner_root": str(relative_owner),
                        "path": str(path),
                        "relative_path": relative,
                        "entry_type": "regular",
                        "bytes": info.st_size,
                    })
                else:
                    raise GuardError(f"owned live tree contains unsupported special entry: {path}")
    entries.sort(key=lambda item: (item["owner_root"], item["relative_path"], item["entry_type"]))
    return {"bytes": total, "entries": entries}


def snapshot_owned_roots(
    roots: list[Path], *, max_resamples: int = 3, resample_delay_seconds: float = 0.01
) -> dict[str, Any]:
    if max_resamples < 0 or resample_delay_seconds < 0:
        raise GuardError("live-tree resample policy is invalid")
    exact_roots = [require_real_directory(path, "owned root") for path in roots]
    if len(set(exact_roots)) != len(exact_roots):
        raise GuardError("owned roots contain duplicates")
    for left in exact_roots:
        for right in exact_roots:
            if left != right and (left in right.parents or right in left.parents):
                raise GuardError("owned roots overlap")
    last_race: LiveTreeRace | None = None
    for attempt in range(max_resamples + 1):
        try:
            result = _scan_owned_roots_once(exact_roots)
            result.update({
                "owned_roots": [str(path) for path in exact_roots],
                "resample_count": attempt,
                "max_resamples": max_resamples,
                "nofollow_lstat": True,
                "symlink_targets_traversed": False,
            })
            return result
        except LiveTreeRace as exc:
            last_race = exc
            if attempt >= max_resamples:
                break
            time.sleep(resample_delay_seconds)
    raise GuardError(f"live-tree stat race did not stabilize after bounded resampling: {last_race}")


def parse_watch(value: str) -> tuple[str, Path, int]:
    parts = value.split("=", 2)
    if len(parts) != 3 or not parts[0] or not parts[1]:
        raise argparse.ArgumentTypeError("watch must be LABEL=ABSOLUTE_PATH=LIMIT_BYTES")
    path = Path(parts[1])
    try:
        limit = int(parts[2])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("watch limit must be an integer") from exc
    if not path.is_absolute() or limit < 1:
        raise argparse.ArgumentTypeError("watch path must be absolute and limit positive")
    return parts[0], path, limit


def measure_watch(path: Path, roots: list[Path]) -> dict[str, Any]:
    lexical = _absolute_lexical(path)
    if not _inside(lexical, roots):
        raise GuardError(f"watched path is outside exact-owned roots: {path}")
    try:
        info = os.lstat(lexical)
    except FileNotFoundError:
        return {"path": str(lexical), "entry_type": "absent", "bytes": 0}
    if stat.S_ISLNK(info.st_mode):
        raw_target = os.readlink(lexical)
        target = _lexical_link_target(lexical, raw_target)
        if not _inside(target, roots):
            raise GuardError(f"watched symlink target escapes exact-owned roots: {lexical}")
        return {
            "path": str(lexical), "entry_type": "symlink_no_follow", "bytes": info.st_size,
            "link_target": raw_target, "lexical_target": str(target),
        }
    if not stat.S_ISREG(info.st_mode):
        raise GuardError(f"watched path must be absent, regular or an owned no-follow link: {lexical}")
    return {"path": str(lexical), "entry_type": "regular", "bytes": info.st_size}


def unlink_exact_owned_link_entry(path: Path, roots: list[Path]) -> dict[str, Any]:
    """Unlink one declared internal symlink without following its target."""
    exact_roots = [require_real_directory(root, "owned root") for root in roots]
    lexical = _absolute_lexical(path)
    if not _inside(lexical, exact_roots):
        raise GuardError(f"cleanup link path escapes exact-owned roots: {path}")
    try:
        info = os.lstat(lexical)
    except FileNotFoundError as exc:
        raise GuardError(f"cleanup link is absent: {lexical}") from exc
    if not stat.S_ISLNK(info.st_mode):
        raise GuardError(f"cleanup helper only accepts a symlink entry: {lexical}")
    raw_target = os.readlink(lexical)
    target = _lexical_link_target(lexical, raw_target)
    if not _inside(target, exact_roots):
        raise GuardError(f"cleanup symlink target escapes exact-owned roots: {lexical}")
    os.unlink(lexical)
    return {
        "path": str(lexical),
        "entry_type": "symlink_no_follow",
        "link_target": raw_target,
        "lexical_target": str(target),
        "target_traversed": False,
        "unlinked": True,
    }


def evaluate(
    *,
    watches: list[tuple[str, Path, int]],
    roots: list[Path],
    baseline_bytes: int,
    growth_limit_bytes: int,
    disk_path: Path,
    min_free_bytes: int,
    max_resamples: int,
    resample_delay_seconds: float,
) -> dict[str, Any]:
    tree = snapshot_owned_roots(
        roots, max_resamples=max_resamples, resample_delay_seconds=resample_delay_seconds
    )
    exact_roots = [Path(item) for item in tree["owned_roots"]]
    watched: list[dict[str, Any]] = []
    reason = None
    for label, path, limit in watches:
        item = measure_watch(path, exact_roots)
        item.update({"label": label, "limit_bytes": limit})
        watched.append(item)
        if reason is None and item["bytes"] >= limit:
            reason = f"WATCH_FILE_LIMIT:{label}"
    growth = max(0, int(tree["bytes"]) - baseline_bytes)
    free = shutil.disk_usage(disk_path).free
    if reason is None and growth >= growth_limit_bytes:
        reason = "ATTEMPT_GROWTH_LIMIT"
    if reason is None and free < min_free_bytes:
        reason = "DISK_FREE_RESERVE"
    return {
        "reason": reason,
        "watched_files": watched,
        "attempt_tree_bytes": tree["bytes"],
        "attempt_entry_count": len(tree["entries"]),
        "symlink_entry_count": sum(item["entry_type"] == "symlink_no_follow" for item in tree["entries"]),
        "live_tree_snapshot": tree,
        "attempt_baseline_bytes": baseline_bytes,
        "attempt_growth_bytes": growth,
        "attempt_growth_limit_bytes": growth_limit_bytes,
        "disk_path": str(disk_path),
        "disk_free_bytes": free,
        "minimum_disk_free_bytes": min_free_bytes,
    }


def enable_child_subreaper() -> dict[str, Any]:
    if sys.platform != "linux":
        raise GuardError("production operational supervision requires Linux")
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0)
    if result != 0:
        raise GuardError(f"PR_SET_CHILD_SUBREAPER failed: errno={ctypes.get_errno()}")
    return {"enabled": True, "primitive": "PR_SET_CHILD_SUBREAPER"}


def parse_proc_stat(value: str) -> dict[str, Any]:
    """Parse Linux /proc/<pid>/stat without losing spaces or ')' in comm."""
    left = value.find("(")
    right = value.rfind(")")
    if left <= 0 or right <= left:
        raise GuardError("invalid /proc stat record")
    try:
        pid = int(value[:left].strip())
    except ValueError as exc:
        raise GuardError("invalid /proc stat pid") from exc
    fields = value[right + 1 :].strip().split()
    if len(fields) < 20:
        raise GuardError("short /proc stat record")
    try:
        ppid = int(fields[1])
        pgid = int(fields[2])
        sid = int(fields[3])
        start_time_ticks = int(fields[19])
    except ValueError as exc:
        raise GuardError("invalid /proc stat numeric field") from exc
    return {
        "pid": pid,
        "ppid": ppid,
        "pgid": pgid,
        "sid": sid,
        "stat": fields[0],
        "comm": value[left + 1 : right],
        "start_time_ticks": start_time_ticks,
    }


def read_proc_row(pid: int, proc_root: Path = PROC_ROOT) -> dict[str, Any] | None:
    path = proc_root / str(pid) / "stat"
    try:
        value = path.read_text(encoding="utf-8", errors="strict")
    except (FileNotFoundError, ProcessLookupError):
        return None
    except OSError as exc:
        if getattr(exc, "errno", None) in {2, 3}:
            return None
        raise GuardError(f"cannot read process identity for pid {pid}: {exc}") from exc
    row = parse_proc_stat(value)
    if row["pid"] != pid:
        raise GuardError(f"/proc identity mismatch for pid {pid}")
    return row


def process_key(row: dict[str, Any]) -> ProcessKey:
    return int(row["pid"]), int(row["start_time_ticks"])


def ps_table(proc_root: Path = PROC_ROOT) -> list[dict[str, Any]]:
    """Return an exact PID+start-time snapshot without spawning a child enumerator.

    v100 proved that a subprocess-backed ``ps`` scan can enumerate the ``ps``
    child itself and make an already successful command look unreaped.  Procfs
    has no helper child, and start_time_ticks prevents stale PID ownership from
    being transferred to a reused PID.
    """
    try:
        entries = list(proc_root.iterdir())
    except OSError as exc:
        raise GuardError(f"cannot enumerate procfs: {exc}") from exc
    rows: list[dict[str, Any]] = []
    for entry in entries:
        if not entry.name.isdecimal():
            continue
        row = read_proc_row(int(entry.name), proc_root)
        if row is not None:
            rows.append(row)
    rows.sort(key=lambda row: (row["pid"], row["start_time_ticks"]))
    return rows


def identity_matches(row: dict[str, Any], proc_root: Path = PROC_ROOT) -> bool:
    current = read_proc_row(int(row["pid"]), proc_root)
    return current is not None and process_key(current) == process_key(row)


def owned_processes(
    root_identity: ProcessKey | None, root_pgid: int, known: set[ProcessKey]
) -> list[dict[str, Any]]:
    rows = ps_table()
    by_pid = {row["pid"]: row for row in rows}
    by_parent: dict[int, list[int]] = {}
    for row in rows:
        by_parent.setdefault(row["ppid"], []).append(row["pid"])
    seeds = set(known)
    if root_identity is not None:
        seeds.add(root_identity)
    closure: set[ProcessKey] = set()
    pending: list[int] = []
    for key in seeds:
        row = by_pid.get(key[0])
        if row is not None and process_key(row) == key:
            closure.add(key)
            pending.append(key[0])
    while pending:
        parent = pending.pop()
        for child in by_parent.get(parent, []):
            row = by_pid[child]
            key = process_key(row)
            if key not in closure:
                closure.add(key)
                pending.append(child)
    closure.update(process_key(row) for row in rows if row["pgid"] == root_pgid)
    # As a child-subreaper the guard directly adopts escaped descendants.  A
    # procfs snapshot introduces no package-owned enumerator child here.
    closure.update(process_key(row) for row in rows if row["ppid"] == os.getpid())
    return sorted(
        [row for row in rows if process_key(row) in closure and row["pid"] != os.getpid()],
        key=lambda row: (row["pid"], row["start_time_ticks"]),
    )


def signal_owned(
    root_identity: ProcessKey | None, root_pgid: int, known: set[ProcessKey], signum: int
) -> dict[str, Any]:
    rows = owned_processes(root_identity, root_pgid, known)
    delivered: list[int] = []
    identity_drift_skipped: list[dict[str, int]] = []
    errors: list[str] = []
    if any(row["pgid"] == root_pgid for row in rows):
        try:
            os.killpg(root_pgid, signum)
        except ProcessLookupError:
            pass
        except OSError as exc:
            errors.append(f"killpg({root_pgid},{signum}) failed: {exc}")
    for row in rows:
        pid = row["pid"]
        key = process_key(row)
        known.add(key)
        if row["pgid"] == root_pgid:
            continue
        if not identity_matches(row):
            identity_drift_skipped.append({"pid": pid, "start_time_ticks": row["start_time_ticks"]})
            continue
        try:
            os.kill(pid, signum)
            delivered.append(pid)
        except ProcessLookupError:
            pass
        except OSError as exc:
            errors.append(f"kill({pid},{signum}) failed: {exc}")
    return {
        "signal": signal.Signals(signum).name,
        "escaped_pids_signaled": delivered,
        "identity_drift_skipped": identity_drift_skipped,
        "errors": errors,
    }


def reap_adopted(known: set[ProcessKey], deadline: float) -> list[int]:
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
            known.difference_update(key for key in known if key[0] == pid)
            changed = True
        if not changed:
            time.sleep(0.05)
    return reaped


def terminate_owned_tree(
    process: subprocess.Popen[Any], root_identity: ProcessKey | None,
    root_pgid: int, known: set[ProcessKey], grace: float
) -> dict[str, Any]:
    actions = [signal_owned(root_identity, root_pgid, known, signal.SIGTERM)]
    deadline = time.monotonic() + grace
    reaped: list[int] = []
    while time.monotonic() < deadline:
        reaped.extend(reap_adopted(known, time.monotonic() + 0.05))
        if not owned_processes(root_identity, root_pgid, known):
            break
        time.sleep(0.05)
    remaining = owned_processes(root_identity, root_pgid, known)
    if remaining:
        actions.append(signal_owned(root_identity, root_pgid, known, signal.SIGKILL))
    try:
        root_exit = process.wait(timeout=max(grace, 0.1))
    except subprocess.TimeoutExpired:
        root_exit = None
    reaped.extend(reap_adopted(known, time.monotonic() + max(grace, 0.1)))
    final = owned_processes(root_identity, root_pgid, known)
    return {
        "actions": actions,
        "root_exit": root_exit,
        "reaped_pids": sorted(set(reaped)),
        "owned_pids_remaining": [row["pid"] for row in final],
        "owned_process_identities_remaining": [
            {"pid": row["pid"], "start_time_ticks": row["start_time_ticks"]} for row in final
        ],
        "process_tree_reaped": not final,
    }


def emergency_finalize(
    *,
    receipt_path: Path,
    stderr_path: Path | None,
    base_receipt: dict[str, Any],
    error: BaseException,
    terminate: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    message = f"OPERATIONAL_GUARD_MONITOR_EXCEPTION {type(error).__name__}: {error}"
    append_stderr(stderr_path, message)
    try:
        termination = terminate()
    except BaseException as terminate_error:  # emergency path must still publish
        termination = {
            "actions": [],
            "root_exit": None,
            "reaped_pids": [],
            "owned_pids_remaining": [base_receipt.get("child_pid")],
            "owned_process_identities_remaining": [base_receipt.get("child_process_identity")],
            "process_tree_reaped": False,
            "termination_error": f"{type(terminate_error).__name__}: {terminate_error}",
        }
        append_stderr(stderr_path, f"OPERATIONAL_GUARD_TERMINATION_EXCEPTION {type(terminate_error).__name__}: {terminate_error}")
    value = {
        **base_receipt,
        "guard_triggered": True,
        "stop_reason": "MONITOR_EXCEPTION",
        "stop_count": 1,
        "one_shot_stop": True,
        "monitor_exception": {"type": type(error).__name__, "message": str(error)},
        "termination": termination,
        "process_fully_reaped": termination.get("process_tree_reaped") is True,
        "stderr_receipt": file_identity(stderr_path),
        "failure_classification": "SHARED_MONITOR_EXCEPTION",
        "production_compile_error_claim_allowed": False,
        "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "pass": False,
        "claim_boundary": "Emergency operational-guard receipt only; no production compile, DUT, natural-terminal or Formal-D claim.",
    }
    atomic_json(receipt_path, value)
    return value


def supervise(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if sys.platform != "linux":
        raise GuardError("operational supervision requires Linux")
    attempt_root = require_real_directory(args.attempt_root, "attempt root")
    additional = [require_real_directory(path, "additional owned root") for path in args.owned_root]
    roots = [attempt_root, *additional]
    receipt_path = _absolute_lexical(args.receipt)
    if not _inside(receipt_path, [attempt_root]):
        raise GuardError("guard receipt must be inside exact attempt root")
    stderr_path = _absolute_lexical(args.log) if args.log is not None else None
    if stderr_path is not None and not _inside(stderr_path, roots):
        raise GuardError("guard log must be inside exact-owned roots")
    disk_path = require_real_directory(args.disk_path, "disk accounting path")
    if args.timeout <= 0 or args.interval <= 0 or args.grace <= 0:
        raise GuardError("timeout/interval/grace must be positive")
    if args.growth_limit_bytes < 1 or args.min_free_bytes < 1:
        raise GuardError("growth/free-space limits must be positive")
    if not args.command:
        raise GuardError("guarded command is absent")
    if args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        raise GuardError("guarded command is absent")

    baseline_snapshot = snapshot_owned_roots(
        roots, max_resamples=args.max_resamples, resample_delay_seconds=args.resample_delay
    )
    baseline = int(baseline_snapshot["bytes"])
    initial = evaluate(
        watches=args.watch, roots=roots, baseline_bytes=baseline,
        growth_limit_bytes=args.growth_limit_bytes, disk_path=disk_path,
        min_free_bytes=args.min_free_bytes, max_resamples=args.max_resamples,
        resample_delay_seconds=args.resample_delay,
    )
    if initial["reason"] is not None:
        value = {
            "schema": SCHEMA, "package_id": args.package_id,
            "execution_id": args.execution_id, "attempt_id": args.attempt_id,
            "phase": args.mode, "command_started": False, "command": args.command,
            "cwd": str(args.cwd), "child_pid": None, "child_exit": None,
            "guard_triggered": True, "stop_reason": initial["reason"], "stop_count": 1,
            "one_shot_stop": True, "monitor_exception": None,
            "baseline_snapshot": baseline_snapshot, "samples": [initial], "final_snapshot": initial,
            "termination": {
                "actions": [], "root_exit": None, "reaped_pids": [],
                "owned_pids_remaining": [], "owned_process_identities_remaining": [],
                "process_tree_reaped": True,
            },
            "process_fully_reaped": True, "stderr_receipt": file_identity(stderr_path),
            "failure_classification": "PRESTART_OPERATIONAL_BOUNDARY",
            "production_compile_error_claim_allowed": False,
            "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE", "pass": False,
            "claim_boundary": "Pre-start operational guard only; no production compile or DUT claim.",
        }
        atomic_json(receipt_path, value)
        return value, GUARD_EXIT

    subreaper = enable_child_subreaper()
    if stderr_path is not None:
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        log_stream = stderr_path.open("ab", buffering=0)
    else:
        log_stream = None
    try:
        process = subprocess.Popen(
            args.command,
            cwd=args.cwd,
            stdout=log_stream,
            stderr=subprocess.STDOUT if log_stream is not None else None,
            start_new_session=True,
        )
        root_pgid = process.pid
        root_row = read_proc_row(process.pid)
        root_identity = process_key(root_row) if root_row is not None else None
        known: set[ProcessKey] = {root_identity} if root_identity is not None else set()
        base_receipt = {
            "schema": SCHEMA, "package_id": args.package_id,
            "execution_id": args.execution_id, "attempt_id": args.attempt_id,
            "phase": args.mode, "command_started": True, "command": args.command,
            "cwd": str(args.cwd), "child_pid": process.pid, "child_subreaper": subreaper,
            "child_process_identity": (
                {"pid": root_identity[0], "start_time_ticks": root_identity[1]}
                if root_identity is not None else None
            ),
            "process_identity_model": {
                "snapshot_backend": "PROCFS_NO_CHILD_ENUMERATOR",
                "identity_fields": ["pid", "start_time_ticks"],
                "pid_reuse_protection": True,
                "self_enumerator_child_process": False,
            },
            "baseline_snapshot": baseline_snapshot, "samples": [],
        }
        try:
            atomic_json(receipt_path, {
                **base_receipt, "status": "RUNNING", "stop_count": 0,
                "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
                "claim_boundary": "Start receipt only; final guard status is not yet available.",
            })
        except (GuardError, OSError, subprocess.SubprocessError) as error:
            value = emergency_finalize(
                receipt_path=receipt_path,
                stderr_path=stderr_path,
                base_receipt=base_receipt,
                error=error,
                terminate=lambda: terminate_owned_tree(
                    process, root_identity, root_pgid, known, args.grace
                ),
            )
            return value, GUARD_EXIT
        deadline = time.monotonic() + args.timeout
        samples: list[dict[str, Any]] = []
        stop_reason: str | None = None
        termination: dict[str, Any] | None = None
        try:
            while process.poll() is None:
                for row in owned_processes(root_identity, root_pgid, known):
                    known.add(process_key(row))
                snapshot = evaluate(
                    watches=args.watch, roots=roots, baseline_bytes=baseline,
                    growth_limit_bytes=args.growth_limit_bytes, disk_path=disk_path,
                    min_free_bytes=args.min_free_bytes, max_resamples=args.max_resamples,
                    resample_delay_seconds=args.resample_delay,
                )
                snapshot.update({"seq": len(samples), "host_monotonic_ns": time.monotonic_ns()})
                samples.append(snapshot)
                if snapshot["reason"] is not None:
                    stop_reason = snapshot["reason"]
                elif time.monotonic() >= deadline:
                    stop_reason = "WALL_TIMEOUT"
                if stop_reason is not None:
                    termination = terminate_owned_tree(
                        process, root_identity, root_pgid, known, args.grace
                    )
                    break
                time.sleep(args.interval)
        except (GuardError, OSError, subprocess.SubprocessError) as error:
            base_receipt["samples"] = samples
            value = emergency_finalize(
                receipt_path=receipt_path,
                stderr_path=stderr_path,
                base_receipt=base_receipt,
                error=error,
                terminate=lambda: terminate_owned_tree(
                    process, root_identity, root_pgid, known, args.grace
                ),
            )
            return value, GUARD_EXIT

        if termination is None:
            try:
                remaining = owned_processes(root_identity, root_pgid, known)
                if remaining:
                    termination = terminate_owned_tree(
                        process, root_identity, root_pgid, known, args.grace
                    )
                else:
                    try:
                        root_exit = process.wait(timeout=max(args.grace, 0.1))
                    except subprocess.TimeoutExpired:
                        termination = terminate_owned_tree(
                            process, root_identity, root_pgid, known, args.grace
                        )
                    else:
                        termination = {
                            "actions": [], "root_exit": root_exit, "reaped_pids": [],
                            "owned_pids_remaining": [],
                            "owned_process_identities_remaining": [],
                            "process_tree_reaped": True,
                        }
            except (GuardError, OSError, subprocess.SubprocessError) as error:
                base_receipt["samples"] = samples
                value = emergency_finalize(
                    receipt_path=receipt_path,
                    stderr_path=stderr_path,
                    base_receipt=base_receipt,
                    error=error,
                    terminate=lambda: terminate_owned_tree(
                        process, root_identity, root_pgid, known, args.grace
                    ),
                )
                return value, GUARD_EXIT
        child_exit = termination.get("root_exit")
        final_snapshot: dict[str, Any] | None
        final_snapshot_error: dict[str, str] | None = None
        try:
            final_snapshot = evaluate(
                watches=args.watch, roots=roots, baseline_bytes=baseline,
                growth_limit_bytes=args.growth_limit_bytes, disk_path=disk_path,
                min_free_bytes=args.min_free_bytes, max_resamples=args.max_resamples,
                resample_delay_seconds=args.resample_delay,
            )
        except (GuardError, OSError) as error:
            final_snapshot = None
            final_snapshot_error = {"type": type(error).__name__, "message": str(error)}
            append_stderr(stderr_path, f"OPERATIONAL_GUARD_FINAL_SNAPSHOT_EXCEPTION {type(error).__name__}: {error}")
        monitor_ok = final_snapshot_error is None
        process_reaped = termination.get("process_tree_reaped") is True
        operational_stop = stop_reason is not None
        failure_classification = "OPERATIONAL_BOUNDARY_STOP" if operational_stop else "GUARDED_COMMAND_EXIT"
        if not monitor_ok:
            failure_classification = "FINAL_SNAPSHOT_INCOMPLETE"
        production_claim = bool(
            args.mode == "compile" and not operational_stop and monitor_ok and
            process_reaped and isinstance(child_exit, int) and child_exit != 0
        )
        value = {
            **base_receipt, "child_exit": child_exit,
            "guard_triggered": operational_stop, "stop_reason": stop_reason,
            "stop_count": 1 if operational_stop else 0, "one_shot_stop": True,
            "monitor_exception": final_snapshot_error, "samples": samples,
            "final_snapshot": final_snapshot, "termination": termination,
            "process_fully_reaped": process_reaped, "stderr_receipt": file_identity(stderr_path),
            "failure_classification": failure_classification,
            "production_compile_error_claim_allowed": production_claim,
            "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE" if operational_stop or not monitor_ok or not process_reaped else "COMPLETE",
            "pass": monitor_ok and process_reaped and not operational_stop,
            "claim_boundary": "Operational resource/termination guard only; no DUT, natural-terminal or Formal-D claim.",
        }
        atomic_json(receipt_path, value)
        return value, GUARD_EXIT if operational_stop or not monitor_ok or not process_reaped else int(child_exit or 0)
    finally:
        if log_stream is not None:
            log_stream.flush()
            os.fsync(log_stream.fileno())
            log_stream.close()


def validate_receipt(receipt: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        return {"schema": SCHEMA, "pass": False, "errors": ["invalid guard receipt schema"]}
    if receipt.get("stop_count") not in (0, 1):
        errors.append("stop_count must be zero or one")
    if receipt.get("one_shot_stop") is not True:
        errors.append("one_shot_stop must be true")
    classification = receipt.get("failure_classification")
    if classification not in {
        "GUARDED_COMMAND_EXIT", "OPERATIONAL_BOUNDARY_STOP", "PRESTART_OPERATIONAL_BOUNDARY",
        "SHARED_MONITOR_EXCEPTION", "FINAL_SNAPSHOT_INCOMPLETE",
    }:
        errors.append("failure_classification is invalid")
    if classification in {"SHARED_MONITOR_EXCEPTION", "FINAL_SNAPSHOT_INCOMPLETE"}:
        if receipt.get("diagnostic_status") != "DIAGNOSTIC_EVIDENCE_INCOMPLETE":
            errors.append("monitor failure must be diagnostic incomplete")
        if receipt.get("production_compile_error_claim_allowed") is not False:
            errors.append("monitor failure cannot claim production compile error")
    if receipt.get("command_started") is True:
        identity_model = receipt.get("process_identity_model")
        if not isinstance(identity_model, dict):
            errors.append("started child lacks PID plus start-time identity model")
        else:
            expected_model = {
                "snapshot_backend": "PROCFS_NO_CHILD_ENUMERATOR",
                "identity_fields": ["pid", "start_time_ticks"],
                "pid_reuse_protection": True,
                "self_enumerator_child_process": False,
            }
            if identity_model != expected_model:
                errors.append("process identity model is not exact procfs PID plus start-time")
        if receipt.get("process_fully_reaped") is not True:
            errors.append("started child tree was not fully reaped")
        remaining = receipt.get("termination", {}).get("owned_pids_remaining")
        if remaining not in ([], None):
            errors.append("owned child remains after guard finalization")
        identity_remaining = receipt.get("termination", {}).get(
            "owned_process_identities_remaining"
        )
        if identity_remaining not in ([], None):
            errors.append("owned child identity remains after guard finalization")
    stderr_receipt = receipt.get("stderr_receipt")
    if classification == "SHARED_MONITOR_EXCEPTION":
        if not isinstance(stderr_receipt, dict) or stderr_receipt.get("status") == "ABSENT":
            errors.append("monitor exception lacks captured stderr receipt")
        if receipt.get("stop_count") != 1:
            errors.append("monitor exception must consume the one-shot stop")
    return {"schema": SCHEMA, "pass": not errors, "errors": errors}


def classify_phase_exit(exit_code: int, receipt: dict[str, Any] | None) -> dict[str, Any]:
    if receipt is None:
        return {
            "classification": "GUARD_RECEIPT_MISSING_INFRASTRUCTURE_FAILURE",
            "exit_code": exit_code,
            "production_compile_error": False,
            "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        }
    validation = validate_receipt(receipt)
    if not validation["pass"]:
        return {
            "classification": "GUARD_RECEIPT_INVALID_INFRASTRUCTURE_FAILURE",
            "exit_code": exit_code,
            "production_compile_error": False,
            "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "errors": validation["errors"],
        }
    allowed = receipt.get("production_compile_error_claim_allowed") is True
    return {
        "classification": receipt.get("failure_classification"),
        "exit_code": exit_code,
        "production_compile_error": allowed,
        "diagnostic_status": receipt.get("diagnostic_status"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command_name", required=True)
    run = sub.add_parser("supervise")
    run.add_argument("--package-id", required=True)
    run.add_argument("--execution-id", required=True)
    run.add_argument("--attempt-id", required=True)
    run.add_argument("--mode", choices=("compile", "simulation", "finalization"), required=True)
    run.add_argument("--attempt-root", type=Path, required=True)
    run.add_argument("--owned-root", type=Path, action="append", default=[])
    run.add_argument("--cwd", type=Path, required=True)
    run.add_argument("--disk-path", type=Path, required=True)
    run.add_argument("--min-free-bytes", type=int, required=True)
    run.add_argument("--growth-limit-bytes", type=int, required=True)
    run.add_argument("--watch", type=parse_watch, action="append", default=[])
    run.add_argument("--timeout", type=float, required=True)
    run.add_argument("--interval", type=float, required=True)
    run.add_argument("--grace", type=float, required=True)
    run.add_argument("--max-resamples", type=int, default=3)
    run.add_argument("--resample-delay", type=float, default=0.01)
    run.add_argument("--receipt", type=Path, required=True)
    run.add_argument("--log", type=Path)
    run.add_argument("command", nargs=argparse.REMAINDER)
    check = sub.add_parser("validate-receipt")
    check.add_argument("--receipt", type=Path, required=True)
    classify = sub.add_parser("classify-exit")
    classify.add_argument("--exit-code", type=int, required=True)
    classify.add_argument("--receipt", type=Path)
    for command in (check, classify):
        command.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command_name == "supervise":
        try:
            report, code = supervise(args)
        except (GuardError, OSError, subprocess.SubprocessError) as error:
            append_stderr(args.log, f"OPERATIONAL_GUARD_PRESTART_ERROR {type(error).__name__}: {error}")
            return PRESTART_GUARD_EXIT
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return int(code)
    if args.command_name == "validate-receipt":
        report = validate_receipt(json.loads(args.receipt.read_text(encoding="utf-8")))
        code = 0 if report["pass"] else 1
    else:
        receipt = json.loads(args.receipt.read_text(encoding="utf-8")) if args.receipt else None
        report = classify_phase_exit(args.exit_code, receipt)
        code = 0 if report["production_compile_error"] or report["classification"] != "GUARD_RECEIPT_INVALID_INFRASTRUCTURE_FAILURE" else 1
    payload = canonical_bytes(report)
    if args.output:
        atomic_json(args.output, report)
    else:
        sys.stdout.buffer.write(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
