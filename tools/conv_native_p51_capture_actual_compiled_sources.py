#!/usr/bin/env python3
"""Post-compile, exact-path capture of native Conv diagnostic RTL sources.

This helper is intentionally invoked only after the production compile command
has returned.  It is not a preflight or provider inventory.  Missing sources
are recorded in the manifest and never prevent compile-core publication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath
from typing import Any


SOURCES = (
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv",
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_AG_Idx_Queue.sv",
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv",
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Memory_AG.sv",
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv",
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv",
    "rtl/utils/FIFO/FIFO.sv",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-root", required=True, type=Path)
    parser.add_argument("--compile-log", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    compile_log = args.compile_log.read_text(encoding="utf-8", errors="replace") if args.compile_log.is_file() else ""
    records: list[dict[str, Any]] = []
    for relative in SOURCES:
        pure = PurePosixPath(relative)
        source = args.server_root.joinpath(*pure.parts)
        record: dict[str, Any] = {
            "relative_path": relative,
            "absolute_path": str(source),
            "compile_log_membership": relative in compile_log or source.as_posix() in compile_log,
            "present": source.is_file(),
        }
        if source.is_file():
            target = args.output_root / "files" / Path(*pure.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            record.update({
                "archive_path": "evidence/actual_rtl/" + pure.name,
                "bytes": target.stat().st_size,
                "sha256": digest(target),
            })
        records.append(record)

    manifest = {
        "schema": "conv-native-post-compile-actual-source-capture-v1",
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "phase": "POST_PRODUCTION_COMPILE",
        "preflight_or_provider_probe": False,
        "server_root": str(args.server_root),
        "compile_log": str(args.compile_log),
        "requested_exact_set": list(SOURCES),
        "records": records,
        "complete": all(item["present"] for item in records),
        "missing": [item["relative_path"] for item in records if not item["present"]],
    }
    (args.output_root / "manifest.json").write_bytes(canonical(manifest))
    return 0 if manifest["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
