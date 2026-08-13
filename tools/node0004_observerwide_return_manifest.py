#!/usr/bin/env python3
"""Atomically bind the shared return-core manifest to its exact ZIP member set."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    manifest_name = contract["return_members"]["return_manifest"]
    argv_name = contract["return_members"]["actual_argv"]
    temporary = args.zip.with_name(f".{args.zip.name}.observer.tmp.{os.getpid()}")
    with zipfile.ZipFile(args.zip, "r") as source:
        names = source.namelist()
        if manifest_name not in names or argv_name not in names:
            raise SystemExit("shared return lacks manifest or actual argv receipt")
        actual = json.loads(source.read(argv_name))
        manifest = json.loads(source.read(manifest_name))
        manifest.update(
            package_id=actual["package_id"], execution_id=actual["execution_id"],
            attempt_id=actual["attempt_id"],
            members=sorted(name for name in names if name != manifest_name),
            observer_only_profile="OBSERVER_ONLY_WIDE_CAUSAL_V1",
        )
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as target:
            for info in source.infolist():
                data = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n" if info.filename == manifest_name else source.read(info.filename)
                target.writestr(info, data)
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise SystemExit("rewritten return CRC failure")
    os.replace(temporary, args.zip)
    digest = hashlib.sha256(args.zip.read_bytes()).hexdigest()
    side_tmp = args.sidecar.with_name(f".{args.sidecar.name}.tmp.{os.getpid()}")
    side_tmp.write_text(f"{digest}  {args.zip.name}\n", encoding="ascii")
    os.replace(side_tmp, args.sidecar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
