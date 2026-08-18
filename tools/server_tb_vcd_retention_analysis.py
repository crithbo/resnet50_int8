#!/usr/bin/env python3
"""Streaming VCD/JSONL review plus safe three-slot raw-result retention.

Large inputs are read incrementally.  Persistent state is deliberately small:
analysis_state.json is rewritten atomically, checkpoints.jsonl is append-only,
and report.md is updated after every chunk.  Raw deletion is a separate,
explicit command and is allowed only for exact regular files under the bound
storage root after all consumption/core/protected-set gates close.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Iterator


SCHEMA = "server-tb-vcd-retention-analysis-v1"
STATE_NAME = "analysis_state.json"
CHECKPOINTS_NAME = "checkpoints.jsonl"
REPORT_NAME = "report.md"


def sha_file(path: Path) -> tuple[int, str]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            h.update(block)
    return size, h.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(data)
        temp = Path(stream.name)
    os.replace(temp, path)


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(text)
        temp = Path(stream.name)
    os.replace(temp, path)


@contextmanager
def open_source(path: Path, member: str | None) -> Iterator[tuple[BinaryIO, dict[str, Any]]]:
    if member is None:
        size, digest = sha_file(path)
        with path.open("rb") as stream:
            yield stream, {"path": path.as_posix(), "bytes": size, "sha256": digest}
        return
    archive_size, archive_sha = sha_file(path)
    with zipfile.ZipFile(path) as archive:
        if member not in archive.namelist() or member.startswith("/") or ".." in Path(member).parts:
            raise ValueError("unsafe or absent ZIP member")
        info = archive.getinfo(member)
        with archive.open(info) as raw:
            yield raw, {
                "path": f"{path.as_posix()}::{member}", "bytes": info.file_size,
                "sha256": archive_sha, "identity_kind": "CONTAINER_SHA256_PLUS_MEMBER_CRC32_SIZE",
                "container_bytes": archive_size, "container_sha256": archive_sha,
                "member_crc32": f"{info.CRC:08x}", "member_bytes": info.file_size,
            }


def _skip(stream: BinaryIO, count: int) -> None:
    remaining = count
    while remaining:
        block = stream.read(min(1024 * 1024, remaining))
        if not block:
            raise ValueError("saved offset exceeds current source")
        remaining -= len(block)


def _initial_state(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "kind": "analysis_state", "source": source,
        "byte_offset": 0, "line_number": 0, "last_sim_time": 0, "timescale": None,
        "timescale_collecting": False, "timescale_tokens": [],
        "signal_catalog": {}, "signal_summaries": {}, "status": "IN_PROGRESS",
        "checkpoint_count": 0,
        "claim_boundary": "Bounded streaming summary only; family retains diagnosis authority.",
    }


def _update_signal(state: dict[str, Any], code: str, value: str) -> None:
    summary = state["signal_summaries"].setdefault(code, {"transitions": 0, "xz_transitions": 0, "first_value": None, "last_value": None, "last_time": 0})
    if summary["last_value"] != value:
        summary["transitions"] += 1
        if any(ch in "xXzZ" for ch in value):
            summary["xz_transitions"] += 1
        if summary["first_value"] is None:
            summary["first_value"] = value
        summary["last_value"] = value
        summary["last_time"] = state["last_sim_time"]


def _parse_vcd_line(state: dict[str, Any], line: str) -> int:
    stripped = line.strip()
    if not stripped:
        return 0
    if state.get("timescale_collecting"):
        before_end, separator, _ = stripped.partition("$end")
        if before_end:
            state.setdefault("timescale_tokens", []).append(before_end.strip())
        if separator:
            state["timescale"] = " ".join(state.get("timescale_tokens", [])).strip() or None
            state["timescale_collecting"] = False
            state["timescale_tokens"] = []
        return 0
    if stripped.startswith("$timescale"):
        tail = stripped[len("$timescale"):].strip()
        before_end, separator, _ = tail.partition("$end")
        if separator:
            state["timescale"] = before_end.strip() or state["timescale"]
        else:
            state["timescale_collecting"] = True
            state["timescale_tokens"] = [before_end.strip()] if before_end.strip() else []
        return 0
    if stripped.startswith("$var"):
        parts = stripped.split()
        if len(parts) >= 6:
            state["signal_catalog"][parts[3]] = {"width_bits": int(parts[2]), "reference": " ".join(parts[4:-1])}
        return 0
    if stripped.startswith("#") and stripped[1:].isdigit():
        state["last_sim_time"] = int(stripped[1:])
        return 0
    if stripped[0] in "01xXzZ":
        _update_signal(state, stripped[1:], stripped[0])
        return 1
    if stripped[0] in "bBrR":
        parts = stripped.split()
        if len(parts) == 2:
            _update_signal(state, parts[1], parts[0][1:])
            return 1
    return 0


def _parse_jsonl_line(state: dict[str, Any], line: str) -> int:
    row = json.loads(line)
    if not isinstance(row, dict):
        return 0
    state["last_sim_time"] = max(state["last_sim_time"], int(row.get("sim_time", 0)))
    signal = row.get("signal_id")
    value = row.get("value_4state")
    if isinstance(signal, str) and isinstance(value, str):
        _update_signal(state, signal, value)
        return 1
    return 0


def analyze_chunk(
    source_path: Path, state_dir: Path, kind: str, member: str | None = None,
    max_bytes: int = 8 * 1024 * 1024, root_cause_unique: bool = False,
) -> dict[str, Any]:
    state_path = state_dir / STATE_NAME
    with open_source(source_path, member) as (stream, identity):
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state["source"]["sha256"] != identity["sha256"] or state["source"]["bytes"] != identity["bytes"]:
                raise ValueError("source identity drift")
            if state["status"] == "ROOT_CAUSE_UNIQUE_STOP":
                raise ValueError("root cause already unique; further scan is forbidden")
        else:
            state = _initial_state(identity)
        start = int(state["byte_offset"])
        _skip(stream, start)
        lines_read = events_read = bytes_read = 0
        while bytes_read < max_bytes:
            raw = stream.readline()
            if not raw:
                break
            bytes_read += len(raw)
            lines_read += 1
            line = raw.decode("utf-8", errors="strict")
            events_read += _parse_vcd_line(state, line) if kind == "vcd" else _parse_jsonl_line(state, line)
        state["byte_offset"] = start + bytes_read
        state["line_number"] += lines_read
        eof = state["byte_offset"] >= identity["bytes"]
        if eof and kind == "vcd" and state.get("timescale_collecting"):
            raise ValueError("unterminated VCD timescale declaration")
        state["status"] = "ROOT_CAUSE_UNIQUE_STOP" if root_cause_unique else ("EOF_REACHED" if eof else "IN_PROGRESS")
        state["checkpoint_count"] += 1
        checkpoint = {
            "schema": SCHEMA, "kind": "analysis_checkpoint", "sequence": state["checkpoint_count"],
            "source_sha256": identity["sha256"], "start_offset": start, "end_offset": state["byte_offset"],
            "lines_read": lines_read, "events_read": events_read, "last_sim_time": state["last_sim_time"], "status": state["status"],
        }
        atomic_json(state_path, state)
        state_dir.mkdir(parents=True, exist_ok=True)
        with (state_dir / CHECKPOINTS_NAME).open("a", encoding="utf-8", newline="\n") as output:
            output.write(json.dumps(checkpoint, sort_keys=True, ensure_ascii=False) + "\n")
        rows = [
            "# Incremental diagnostic review", "", f"- status: `{state['status']}`",
            f"- source SHA-256: `{identity['sha256']}`", f"- byte offset: `{state['byte_offset']}/{identity['bytes']}`",
            f"- lines: `{state['line_number']}`", f"- last sim time: `{state['last_sim_time']}`",
            f"- catalog entries: `{len(state['signal_catalog'])}`", f"- summarized signals: `{len(state['signal_summaries'])}`",
            "", "This report is incrementally updated; immutable checkpoints remain in checkpoints.jsonl.", "",
        ]
        atomic_text(state_dir / REPORT_NAME, "\n".join(rows))
        return checkpoint


def _file_identity_key(group: dict[str, Any]) -> tuple[Any, ...]:
    raw = tuple(sorted(item["sha256"] for item in group.get("raw_evidence", [])))
    return (group["source_package"]["sha256"], group["return_zip"]["sha256"], group["sidecar"]["sha256"], raw)


def retention_plan(index: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if index.get("schema") != SCHEMA or index.get("kind") != "retention_index" or index.get("max_raw_groups") != 3:
        errors.append("invalid retention index identity or maximum")
    groups = index.get("groups") if isinstance(index.get("groups"), list) else []
    by_identity: dict[tuple[Any, ...], dict[str, Any]] = {}
    duplicates: list[str] = []
    duplicate_groups: list[dict[str, Any]] = []
    for group in sorted(groups, key=lambda item: item.get("sequence", 0), reverse=True):
        key = _file_identity_key(group)
        if key in by_identity:
            duplicates.append(group["group_id"])
            duplicate_groups.append(group)
        else:
            by_identity[key] = group
    unique = list(by_identity.values())
    max_progress = max(unique, key=lambda item: tuple(item.get("progress_metric", [])), default=None)
    latest = sorted((item for item in unique if item is not max_progress), key=lambda item: item.get("sequence", 0), reverse=True)[:2]
    keep = ([max_progress] if max_progress else []) + latest
    keep_ids = {item["group_id"] for item in keep}
    delete = [item for item in unique if item["group_id"] not in keep_ids]
    for group in [*delete, *duplicate_groups]:
        required = ("analysis_complete", "family_consumed", "mainline_consumed", "deterministic_core_evidence", "protected_set_audit_pass")
        missing = [name for name in required if group.get(name) is not True]
        if missing:
            errors.append(f"{group['group_id']}: deletion prerequisites open: {missing}")
    slots = {
        "MAX_PROGRESS": max_progress["group_id"] if max_progress else None,
        "LATEST_1": latest[0]["group_id"] if len(latest) > 0 else None,
        "LATEST_2": latest[1]["group_id"] if len(latest) > 1 else None,
    }
    return {
        "schema": SCHEMA, "kind": "retention_plan", "pass": not errors, "family": index.get("family"), "track": index.get("track"),
        "slots": slots, "deduplicated_groups": duplicates, "keep_group_ids": sorted(keep_ids),
        "delete_group_ids": [item["group_id"] for item in delete] + duplicates, "errors": errors,
        "claim_boundary": "Local raw-group retention only; task records, reports and deterministic core evidence are never deleted.",
    }


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def apply_retention(index: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    if not plan.get("pass"):
        raise ValueError("retention plan is not safe")
    root = Path(index["storage_root"]).resolve()
    by_id = {item["group_id"]: item for item in index["groups"]}
    protected_paths = {
        str(record["path"])
        for group_id in plan.get("keep_group_ids", [])
        for record in [
            by_id[group_id]["source_package"], by_id[group_id]["return_zip"], by_id[group_id]["sidecar"],
            *by_id[group_id]["raw_evidence"],
        ]
    }
    deleted: list[str] = []
    for group_id in plan["delete_group_ids"]:
        group = by_id[group_id]
        records = [group["source_package"], group["return_zip"], group["sidecar"], *group["raw_evidence"]]
        for record in records:
            if str(record["path"]) in protected_paths:
                continue
            path = Path(record["path"])
            if not _inside(path, root) or path.is_symlink() or not path.is_file():
                raise ValueError(f"unsafe deletion target: {path}")
            size, digest = sha_file(path)
            if size != record["bytes"] or digest != record["sha256"]:
                raise ValueError(f"deletion identity drift: {path}")
        for record in records:
            if str(record["path"]) in protected_paths:
                continue
            Path(record["path"]).unlink()
            deleted.append(record["path"])
    return {"schema": SCHEMA, "kind": "retention_apply_receipt", "deleted": deleted, "deleted_group_ids": plan["delete_group_ids"], "pass": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze")
    analyze.add_argument("--source", required=True, type=Path)
    analyze.add_argument("--kind", choices=["vcd", "jsonl"], required=True)
    analyze.add_argument("--zip-member")
    analyze.add_argument("--state-dir", required=True, type=Path)
    analyze.add_argument("--max-bytes", type=int, default=8 * 1024 * 1024)
    analyze.add_argument("--root-cause-unique", action="store_true")
    plan_parser = sub.add_parser("plan-retention")
    plan_parser.add_argument("--index", required=True, type=Path)
    plan_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "analyze":
        checkpoint = analyze_chunk(args.source, args.state_dir, args.kind, args.zip_member, args.max_bytes, args.root_cause_unique)
        print(json.dumps(checkpoint, ensure_ascii=False))
        return 0
    index = json.loads(args.index.read_text(encoding="utf-8"))
    plan = retention_plan(index)
    atomic_json(args.output, plan)
    return 0 if plan["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
