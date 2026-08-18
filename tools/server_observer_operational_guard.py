#!/usr/bin/env python3
"""Bound one package-owned observer run without truncating captured evidence.

The guard terminates the complete child command when a watched file, aggregate
attempt growth, wall time, or filesystem reserve crosses its declared safety
boundary.  It never edits or deletes evidence.  The caller can therefore
publish every complete record produced before the one-shot stop and mark the
result DIAGNOSTIC_EVIDENCE_INCOMPLETE.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover - Windows validation host
    resource = None  # type: ignore[assignment]


SCHEMA = "server-observer-operational-guard-receipt-v1"
GUARD_EXIT = 122
PR_SET_CHILD_SUBREAPER = 36


class GuardError(ValueError):
    pass


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def file_identity(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        return {"path": str(path), "status": "ABSENT_OR_UNSAFE"}
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return {"path": str(path), "bytes": size, "sha256": digest.hexdigest()}


def tree_bytes(root: Path) -> int:
    total = 0
    if not root.exists():
        return 0
    for directory, names, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in names:
            if (base / name).is_symlink():
                raise GuardError(f"attempt tree contains symlink: {base / name}")
        for name in files:
            path = base / name
            if path.is_symlink() or not path.is_file():
                raise GuardError(f"attempt tree contains unsafe member: {path}")
            total += path.stat().st_size
    return total


def parse_watch(value: str) -> tuple[str, Path, int]:
    parts = value.split("=", 2)
    if len(parts) != 3 or not parts[0] or not parts[1]:
        raise argparse.ArgumentTypeError("watch must be LABEL=ABSOLUTE_PATH=LIMIT_BYTES")
    path = Path(parts[1])
    try:
        limit = int(parts[2])
    except ValueError as error:
        raise argparse.ArgumentTypeError("watch limit must be an integer") from error
    if not path.is_absolute() or limit < 1:
        raise argparse.ArgumentTypeError("watch path must be absolute and limit positive")
    return parts[0], path, limit


def evaluate(
    *,
    watches: list[tuple[str, Path, int]],
    attempt_root: Path,
    baseline_bytes: int,
    growth_limit_bytes: int,
    disk_path: Path,
    min_free_bytes: int,
    additional_roots: list[Path] | None = None,
) -> dict[str, Any]:
    watched = []
    reason = None
    for label, path, limit in watches:
        size = path.stat().st_size if path.is_file() and not path.is_symlink() else 0
        watched.append({"label": label, "path": str(path), "bytes": size, "limit_bytes": limit})
        if reason is None and size >= limit:
            reason = f"WATCH_FILE_LIMIT:{label}"
    roots = [attempt_root, *(additional_roots or [])]
    current = sum(tree_bytes(root) for root in roots)
    growth = max(0, current - baseline_bytes)
    free = shutil.disk_usage(disk_path).free
    if reason is None and growth >= growth_limit_bytes:
        reason = "ATTEMPT_GROWTH_LIMIT"
    if reason is None and free < min_free_bytes:
        reason = "DISK_FREE_RESERVE"
    return {
        "reason": reason,
        "watched_files": watched,
        "attempt_tree_bytes": current,
        "owned_roots": [str(root) for root in roots],
        "attempt_baseline_bytes": baseline_bytes,
        "attempt_growth_bytes": growth,
        "attempt_growth_limit_bytes": growth_limit_bytes,
        "disk_path": str(disk_path),
        "disk_free_bytes": free,
        "minimum_disk_free_bytes": min_free_bytes,
    }


def enable_subreaper() -> bool:
    if sys.platform != "linux":
        return False
    libc = ctypes.CDLL(None, use_errno=True)
    return libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) == 0


def reap_children() -> list[int]:
    reaped: list[int] = []
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            break
        if pid <= 0:
            break
        reaped.append(pid)
    return reaped


def supervise(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if sys.platform != "linux":
        raise GuardError("operational supervision requires Linux")
    attempt_root = args.attempt_root.resolve(strict=True)
    additional_roots = [path.resolve(strict=True) for path in args.owned_root]
    owned_roots = [attempt_root, *additional_roots]
    disk_path = args.disk_path.resolve(strict=True)
    receipt = args.receipt.resolve()
    try:
        receipt.relative_to(attempt_root)
    except ValueError as error:
        raise GuardError("guard receipt must be inside the exact attempt root") from error
    for _, path, _ in args.watch:
        resolved_watch = path.resolve()
        if not any(_inside(resolved_watch, root) for root in owned_roots):
            raise GuardError(f"watched path is outside exact owned roots: {path}")
    if args.timeout <= 0 or args.interval <= 0 or args.grace <= 0:
        raise GuardError("timeout/interval/grace must be positive")
    if args.growth_limit_bytes < 1 or args.min_free_bytes < 1:
        raise GuardError("growth/free-space limits must be positive")
    if not args.command:
        raise GuardError("guarded command is absent")

    baseline = sum(tree_bytes(root) for root in owned_roots)
    initial = evaluate(
        watches=args.watch,
        attempt_root=attempt_root,
        baseline_bytes=baseline,
        growth_limit_bytes=args.growth_limit_bytes,
        disk_path=disk_path,
        min_free_bytes=args.min_free_bytes,
        additional_roots=additional_roots,
    )
    if initial["reason"] is not None:
        value = {
            "schema": SCHEMA,
            "package_id": args.package_id,
            "execution_id": args.execution_id,
            "attempt_id": args.attempt_id,
            "mode": args.mode,
            "command_started": False,
            "guard_triggered": True,
            "stop_reason": initial["reason"],
            "one_shot_stop": True,
            "initial_snapshot": initial,
            "final_snapshot": initial,
            "process_fully_reaped": True,
            "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "claim_boundary": "Operational resource guard only; no DUT result claim.",
        }
        atomic_json(receipt, value)
        return value, GUARD_EXIT

    subreaper = enable_subreaper()

    def preexec() -> None:
        os.setsid()
        if args.file_size_limit_bytes is not None:
            if resource is None:
                raise GuardError("RLIMIT_FSIZE is unavailable")
            resource.setrlimit(
                resource.RLIMIT_FSIZE,
                (args.file_size_limit_bytes, args.file_size_limit_bytes),
            )

    log_stream = None
    if args.log is not None:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        log_stream = args.log.open("wb")
    try:
        process = subprocess.Popen(
            args.command,
            cwd=args.cwd,
            stdout=log_stream,
            stderr=subprocess.STDOUT if log_stream is not None else None,
            preexec_fn=preexec,
        )
        deadline = time.monotonic() + args.timeout
        samples: list[dict[str, Any]] = []
        stop_reason = None
        terminated = False
        while process.poll() is None:
            snapshot = evaluate(
                watches=args.watch,
                attempt_root=attempt_root,
                baseline_bytes=baseline,
                growth_limit_bytes=args.growth_limit_bytes,
                disk_path=disk_path,
                min_free_bytes=args.min_free_bytes,
                additional_roots=additional_roots,
            )
            snapshot["host_monotonic"] = time.monotonic()
            samples.append(snapshot)
            if snapshot["reason"] is not None:
                stop_reason = snapshot["reason"]
            elif time.monotonic() >= deadline:
                stop_reason = "WALL_TIMEOUT"
            if stop_reason is not None:
                terminated = True
                os.killpg(process.pid, signal.SIGTERM)
                break
            time.sleep(args.interval)
        if terminated:
            term_deadline = time.monotonic() + args.grace
            while process.poll() is None and time.monotonic() < term_deadline:
                time.sleep(0.05)
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
        child_exit = process.wait()
    finally:
        if log_stream is not None:
            log_stream.flush()
            os.fsync(log_stream.fileno())
            log_stream.close()

    final_snapshot = evaluate(
        watches=args.watch,
        attempt_root=attempt_root,
        baseline_bytes=baseline,
        growth_limit_bytes=args.growth_limit_bytes,
        disk_path=disk_path,
        min_free_bytes=args.min_free_bytes,
        additional_roots=additional_roots,
    )
    reaped = reap_children()
    value = {
        "schema": SCHEMA,
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "mode": args.mode,
        "command_started": True,
        "command": args.command,
        "cwd": str(args.cwd),
        "child_pid": process.pid,
        "child_exit": child_exit,
        "guard_triggered": stop_reason is not None,
        "stop_reason": stop_reason,
        "one_shot_stop": True,
        "term_then_kill": True,
        "child_subreaper": subreaper,
        "adopted_children_reaped": reaped,
        "process_fully_reaped": process.poll() is not None,
        "wall_timeout_seconds": args.timeout,
        "poll_interval_seconds": args.interval,
        "file_size_rlimit_bytes": args.file_size_limit_bytes,
        "initial_snapshot": initial,
        "sample_count": len(samples),
        "last_sample": samples[-1] if samples else initial,
        "final_snapshot": final_snapshot,
        "watched_identities": [file_identity(path) for _, path, _ in args.watch],
        "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE" if stop_reason else "COMPLETE",
        "claim_boundary": "Operational resource/termination guard only; no DUT, natural-terminal or Formal-D claim.",
    }
    atomic_json(receipt, value)
    return value, GUARD_EXIT if stop_reason is not None else child_exit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
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
    run.add_argument("--file-size-limit-bytes", type=int)
    run.add_argument("--timeout", type=float, required=True)
    run.add_argument("--interval", type=float, required=True)
    run.add_argument("--grace", type=float, required=True)
    run.add_argument("--receipt", type=Path, required=True)
    run.add_argument("--log", type=Path)
    run.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    try:
        report, code = supervise(args)
    except (GuardError, OSError, subprocess.SubprocessError) as error:
        print(f"OPERATIONAL_GUARD_ERROR {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
