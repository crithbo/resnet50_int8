#!/usr/bin/env python3
"""Capture bootstrap-safe, bounded production-compile evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


HEAD_BYTES = 64 * 1024
TAIL_BYTES = 64 * 1024
FIRST_ERROR_BYTES = 4 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def file_identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    result: dict[str, Any] = {"path": str(resolved), "exists": resolved.is_file()}
    if resolved.is_file():
        result.update({"bytes": resolved.stat().st_size, "sha256": sha256(resolved)})
    return result


def prepare(args: argparse.Namespace) -> int:
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    argv = [
        "timeout", "--foreground", "--signal=TERM", "--kill-after=30s", "2h",
        "make", "-f", args.makefile.name, "compile", "DUMP_VCD=0", "DUMP_FSDB=0",
        "TB_DUMP_FSDB=0", f"RUN_DIR={args.run_dir}",
        f"VCS_EXTRA_OPTS=+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+{args.package_root / 'tb_probe'} {args.source}",
    ]
    write_json(output / "compile_argv.json", {
        "schema": "server-production-compile-argv-v1",
        "cwd": str(args.cwd.resolve()),
        "argv": argv,
        "shell_pipeline": False,
        "waveforms_explicitly_disabled": ["DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
    })
    write_json(output / "compile_source_identity.json", {
        "schema": "server-production-compile-source-identity-v1",
        "cwd": str(args.cwd.resolve()),
        "makefile": file_identity(args.makefile),
        "package_source": file_identity(args.source),
        "package_root": str(args.package_root.resolve()),
        "source_binding": "ACTUAL_PACKAGE_LOCAL_SOURCE_PASSED_TO_PRODUCTION_COMPILE_ARGV",
    })
    (output / "compile_exit.txt").write_text("125\n", encoding="ascii", newline="\n")
    for name in ("compile_driver.log", "compile_log_head.txt", "compile_log_tail.txt", "compile_first_error.txt"):
        (output / name).write_bytes(b"")
    return 0


def first_error(data: bytes) -> bytes:
    text = data.decode("utf-8", errors="replace")
    patterns = (
        re.compile(r"(?i)(^|\s)(error|fatal|failed|failure|undefined|not found|no rule to make target|syntax error)(\s|:|$)"),
        re.compile(r"(?i)(^|\s)(xmre|undeclared identifier|cannot open|permission denied)(\s|:|$)"),
    )
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if any(pattern.search(line) for pattern in patterns):
            # Put the actual first-error line first so an unusually long
            # preceding compiler line cannot consume the bounded excerpt.
            context = [line, *lines[index + 1: index + 3], *lines[max(0, index - 2): index]]
            excerpt = "\n".join(context) + "\n"
            return excerpt.encode("utf-8")[:FIRST_ERROR_BYTES]
    fallback = "\n".join(lines[-5:]) + ("\n" if lines else "")
    return fallback.encode("utf-8")[:FIRST_ERROR_BYTES]


def finalize(args: argparse.Namespace) -> int:
    output = args.output_root.resolve()
    log = output / "compile_driver.log"
    data = log.read_bytes() if log.is_file() else b""
    (output / "compile_exit.txt").write_text(f"{args.exit_code}\n", encoding="ascii", newline="\n")
    (output / "compile_log_head.txt").write_bytes(data[:HEAD_BYTES])
    (output / "compile_log_tail.txt").write_bytes(data[-TAIL_BYTES:] if data else b"")
    (output / "compile_first_error.txt").write_bytes(first_error(data))
    write_json(output / "compile_log_receipt.json", {
        "schema": "server-production-compile-driver-log-receipt-v1",
        "path": str(log),
        "exists": log.is_file(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "head_limit_bytes": HEAD_BYTES,
        "tail_limit_bytes": TAIL_BYTES,
        "first_error_limit_bytes": FIRST_ERROR_BYTES,
    })
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("prepare")
    start.add_argument("--output-root", type=Path, required=True)
    start.add_argument("--cwd", type=Path, required=True)
    start.add_argument("--makefile", type=Path, required=True)
    start.add_argument("--source", type=Path, required=True)
    start.add_argument("--package-root", type=Path, required=True)
    start.add_argument("--run-dir", type=Path, required=True)
    finish = sub.add_parser("finalize")
    finish.add_argument("--output-root", type=Path, required=True)
    finish.add_argument("--exit-code", type=int, required=True)
    args = parser.parse_args()
    return prepare(args) if args.command == "prepare" else finalize(args)


if __name__ == "__main__":
    raise SystemExit(main())
