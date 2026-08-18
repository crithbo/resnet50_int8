#!/usr/bin/env python3
"""Repack the exact v99 member stream and require byte-identical ZIP output."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_n4_hw_v99b_lcdup_guarded"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    with zipfile.ZipFile(args.zip) as source:
        names = source.namelist()
        roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
        if roots != {PACKAGE} or len(names) != len(set(names)) or source.testzip() is not None:
            errors.append("source ZIP root/duplicate-set/CRC differs")
        rows = [(info, source.read(info.filename)) for info in source.infolist()]
    with tempfile.TemporaryDirectory(prefix="node0004-v99-repack-") as temporary:
        repeat = Path(temporary) / args.zip.name
        with zipfile.ZipFile(repeat, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for original, data in rows:
                info = zipfile.ZipInfo(original.filename, (2026, 8, 16, 0, 0, 0))
                mode = (original.external_attr >> 16) & 0o777
                info.external_attr = (stat.S_IFREG | mode) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
        same = args.zip.read_bytes() == repeat.read_bytes()
        repeat_identity = {"bytes": repeat.stat().st_size, "sha256": sha(repeat)}
    if not same:
        errors.append("deterministic repack bytes differ")
    report = {
        "schema": "node0004-v99b-deterministic-zip-repack-v1", "package_id": PACKAGE,
        "pass": not errors, "errors": errors,
        "source": {"path": str(args.zip), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip)},
        "repeat": repeat_identity, "byte_equal": same,
        "claim_boundary": "Deterministic exact-ZIP reproduction only; no production execution claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
