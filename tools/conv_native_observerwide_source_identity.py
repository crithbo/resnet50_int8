#!/usr/bin/env python3
"""Bind native-Conv observer symbols to the production source/compile closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def actual_source(root: Path, relative: str) -> Path:
    candidates = [root / relative]
    if relative.startswith("rtl/"):
        candidates.append(root / relative[4:])
    else:
        candidates.append(root / "rtl" / relative)
    return next((path for path in candidates if path.is_file()), candidates[0])


def vcs_argv(text: str) -> list[str]:
    rows = [line.strip() for line in text.splitlines() if re.match(r"^(?:\S*/)?vcs(?:\s|$)", line.strip())]
    if not rows:
        return []
    try:
        return shlex.split(rows[-1], posix=True)
    except ValueError:
        return rows[-1].split()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-root", type=Path, required=True)
    parser.add_argument("--compile-log", type=Path, required=True)
    parser.add_argument("--compile-exit", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.server_root.resolve()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    compile_exit = int(args.compile_exit.read_text(encoding="utf-8").strip()) if args.compile_exit.is_file() else 125
    compile_text = args.compile_log.read_text(encoding="utf-8", errors="replace") if args.compile_log.is_file() else ""
    argv = vcs_argv(compile_text)
    expected_by_path: dict[str, str] = {}
    names_by_path: dict[str, set[str]] = {}
    for signal in contract["signals"]:
        relative = str(signal["source_path"])
        expected_by_path[relative] = str(signal["source_sha256"])
        names_by_path.setdefault(relative, set()).add(str(signal["exact_hierarchy"]).rsplit(".", 1)[-1].split("[")[0])

    rows: list[dict[str, object]] = []
    errors: list[str] = []
    for relative in sorted(expected_by_path):
        source = actual_source(root, relative)
        row: dict[str, object] = {"relative_path": relative, "resolved_path": str(source), "exists": source.is_file()}
        if source.is_file():
            data = source.read_bytes()
            text = data.decode("utf-8", errors="replace")
            row.update(bytes=len(data), sha256=digest(data), expected_sha256=expected_by_path[relative])
            row["identity_match"] = row["sha256"] == row["expected_sha256"]
            missing = sorted(name for name in names_by_path[relative] if name not in text)
            row["required_names"] = sorted(names_by_path[relative])
            row["missing_names"] = missing
            if not row["identity_match"]:
                errors.append(f"source identity mismatch: {relative}")
            if missing:
                errors.append(f"catalog symbols absent from source {relative}: {missing}")
            destination = args.output_dir / "actual_sources" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        else:
            row.update(expected_sha256=expected_by_path[relative], identity_match=False, required_names=sorted(names_by_path[relative]), missing_names=sorted(names_by_path[relative]))
            errors.append(f"source absent: {relative}")
        rows.append(row)

    status = "COMPLETE" if compile_exit == 0 and argv and not errors else "DIAGNOSTIC_EVIDENCE_INCOMPLETE"
    result = {
        "schema": "conv-native-observer-actual-source-identity-v1",
        "status": status,
        "compile_exit": compile_exit,
        "compile_cwd": str(root),
        "actual_vcs_argv": argv,
        "sources": rows,
        "errors": errors,
        "claim_boundary": "Actual production compile argv and exact source/catalog identity only; no DUT result or functional RTL claim.",
    }
    write(args.output, result)
    return 0 if status == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
