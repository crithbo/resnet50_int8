"""Emit one low-overhead Linux process/log liveness snapshot as JSON."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path


def proc_stat(pid: int) -> dict[str, int | str] | None:
    path = Path("/proc") / str(pid) / "stat"
    try:
        text = path.read_text(encoding="ascii")
    except (FileNotFoundError, PermissionError, OSError):
        return None
    close = text.rfind(")")
    if close < 0:
        return None
    fields = text[close + 2 :].split()
    if len(fields) < 20:
        return None
    return {
        "pid": pid,
        "state": fields[0],
        "ppid": int(fields[1]),
        "utime_ticks": int(fields[11]),
        "stime_ticks": int(fields[12]),
        "start_ticks": int(fields[19]),
    }


def descendants(parent: int) -> list[dict[str, int | str]]:
    rows: dict[int, dict[str, int | str]] = {}
    try:
        candidates = [item for item in Path("/proc").iterdir() if item.name.isdigit()]
    except OSError:
        candidates = []
    for item in candidates:
        row = proc_stat(int(item.name))
        if row is not None:
            rows[int(row["pid"])] = row
    selected: set[int] = {parent}
    changed = True
    while changed:
        changed = False
        for pid, row in rows.items():
            if pid not in selected and int(row["ppid"]) in selected:
                selected.add(pid)
                changed = True
    return [rows[pid] for pid in sorted(selected) if pid in rows]


def file_state(path: Path) -> dict[str, int | str | bool | None]:
    try:
        value = path.stat()
    except OSError:
        return {"path": str(path), "exists": False, "bytes": None, "mtime_ns": None}
    return {
        "path": str(path),
        "exists": path.is_file(),
        "bytes": value.st_size,
        "mtime_ns": value.st_mtime_ns,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-pid", type=int, required=True)
    parser.add_argument("--sim-log", type=Path, required=True)
    parser.add_argument("--observer-log", type=Path, required=True)
    args = parser.parse_args()
    record = {
        "schema": "qadd-process-liveness-snapshot-v1",
        "host_time_ns": time.time_ns(),
        "monotonic_ns": time.monotonic_ns(),
        "root_pid": args.root_pid,
        "root_alive": proc_stat(args.root_pid) is not None,
        "process_tree": descendants(args.root_pid),
        "sim_log": file_state(args.sim_log),
        "observer_log": file_state(args.observer_log),
    }
    print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
