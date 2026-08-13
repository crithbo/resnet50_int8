#!/usr/bin/env python3
"""Publish the fixed bootstrap partial return for native Conv p39."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any


PACKAGE_ID = "r5_n4_0cc_p39_compilecore"
FIXED_RESULT_ROOT = "/home/panqs/ndp/simresult"
CORE_ALLOWLIST = (
    "compile_argv.json",
    "compile_source_identity.json",
    "compile_exit.txt",
    "compile_log_receipt.json",
    "compile_log_head.txt",
    "compile_log_tail.txt",
    "compile_first_error.txt",
)
LIMITS = {
    "compile_argv.json": 64 * 1024,
    "compile_source_identity.json": 64 * 1024,
    "compile_exit.txt": 128,
    "compile_log_receipt.json": 64 * 1024,
    "compile_log_head.txt": 64 * 1024,
    "compile_log_tail.txt": 64 * 1024,
    "compile_first_error.txt": 4 * 1024,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def deterministic_zip(root: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(row for row in root.rglob("*") if row.is_file()):
            info = zipfile.ZipInfo(path.relative_to(root).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def publish(args: argparse.Namespace) -> dict[str, Any]:
    return_zip = args.return_zip
    if not return_zip.is_absolute():
        raise RuntimeError("fixed return target must be absolute")
    if return_zip.parent != Path(FIXED_RESULT_ROOT) or not return_zip.name.startswith(PACKAGE_ID + "_r"):
        raise RuntimeError("fixed return target is outside the package-owned simresult namespace")
    target = return_zip.resolve()
    if target.exists() or Path(str(target) + ".sha256").exists():
        raise RuntimeError("fixed return target already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    bootstrap = args.bootstrap_root.resolve()
    with tempfile.TemporaryDirectory(prefix=f".{PACKAGE_ID}_return_", dir=target.parent) as temporary:
        root = Path(temporary) / PACKAGE_ID
        core = root / "compile_core"
        core.mkdir(parents=True)
        members: list[dict[str, Any]] = []
        missing: list[str] = []
        for name in CORE_ALLOWLIST:
            source = bootstrap / name
            if not source.is_file():
                missing.append(name)
                continue
            if source.stat().st_size > LIMITS[name]:
                raise RuntimeError(f"compile-core member exceeds bound: {name}")
            destination = core / name
            shutil.copyfile(source, destination)
            members.append({"path": f"compile_core/{name}", "bytes": destination.stat().st_size, "sha256": sha256(destination)})
        status = root / "evidence/package_local_preflight_status.json"
        write_json(status, {
            "schema": "conv-native-four-lane-package-local-preflight-status-v1",
            "preflight_stage": args.stage,
            "runner_exit_code": args.exit_code,
            "signal_name": args.signal_name,
            "production_compile_started": args.stage == "PRODUCTION_COMPILE",
            "dut_simulation_started": False,
            "partial": True,
        })
        members.append({"path": "evidence/package_local_preflight_status.json", "bytes": status.stat().st_size, "sha256": sha256(status)})
        write_json(root / "RETURN_MANIFEST.json", {
            "schema": "conv-native-p39-bootstrap-compile-core-return-v1",
            "package_identity": PACKAGE_ID,
            "partial": True,
            "stage": args.stage,
            "runner_exit_code": args.exit_code,
            "signal_name": args.signal_name,
            "server_root": args.server_root,
            "bootstrap_root": str(bootstrap),
            "members": members,
            "missing_optional_before_stage": missing,
            "compile_core_complete": not missing,
            "waveform_included": False,
            "full_compile_driver_log_included": False,
        })
        (root / "RETURN_ALLOWLIST.txt").write_text(
            "RETURN_MANIFEST.json\nRETURN_ALLOWLIST.txt\nevidence/package_local_preflight_status.json\n" + "".join(f"compile_core/{name}\n" for name in CORE_ALLOWLIST),
            encoding="utf-8", newline="\n",
        )
        staged = target.with_name(f".{target.name}.{os.getpid()}.staged")
        if staged.exists():
            raise RuntimeError("fixed return staging target already exists")
        deterministic_zip(root.parent, staged)
        os.replace(staged, target)
    digest = sha256(target)
    Path(str(target) + ".sha256").write_text(f"{digest}  {target.name}\n", encoding="ascii", newline="\n")
    return {"schema": "fixed-simresult-publication-v1", "return_zip": str(target), "bytes": target.stat().st_size, "sha256": digest}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--bootstrap-root", type=Path, required=True)
    parser.add_argument("--bootstrap-partial", action="store_true")
    parser.add_argument("--exit-code", type=int, default=125)
    parser.add_argument("--signal-name", default="NONE")
    parser.add_argument("--stage", default="EARLY_PREFLIGHT")
    parser.add_argument("--server-root", default="")
    parser.add_argument("--return-zip", type=Path, required=True)
    args = parser.parse_args()
    if not args.bootstrap_partial:
        raise RuntimeError("p39 publisher is bootstrap-partial only; post-sim uses the shared core")
    print(json.dumps(publish(args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
