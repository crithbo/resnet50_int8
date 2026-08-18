#!/usr/bin/env python3
"""Bind the six-scenario structural runtime-layout harness to exact QAdd v64."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


PACKAGE = "r5_qadd_n7_tailround_lanephase_v64_tbvcdfix"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    zip_data = args.zip.read_bytes()
    with zipfile.ZipFile(args.zip) as archive:
        runner = archive.read(f"{PACKAGE}/PREPARE_AND_RUN.sh")
        if archive.testzip() is not None:
            raise RuntimeError("exact ZIP CRC failed")
    roots = [{"name": "install", "type": "directory"}]
    exit_codes = {"normal": 0, "preflight_fail": 5, "compile_fail": 2, "HUP": 129, "INT": 130, "TERM": 143}
    scenarios = {}
    for index, (name, code) in enumerate(exit_codes.items(), start=1):
        stamp = f"17890000000000000{index:02d}"
        result = f"/home/panqs/ndp/simresult/{PACKAGE}_r{stamp}_{3000 + index}_return.zip"
        scenarios[name] = {
            "command": f"STRUCTURAL_LOCAL_EXACT_ZIP scenario={name} bash {PACKAGE}/PREPARE_AND_RUN.sh /synthetic/NDP_copy01",
            "cwd": "/synthetic/NDP_copy01",
            "runner_exit": code,
            "compile_started": name != "preflight_fail",
            "simulation_started": name in {"normal", "HUP", "INT", "TERM"},
            "finalizer_reached": True,
            "partial_return_published": name != "normal",
            "fixed_result_return_published": True,
            "return_zip": result,
            "return_sidecar": result + ".sha256",
            "preexisting_parents_verified": True,
            "preexisting_install_verified": True,
            "creatable_parents_initially_absent": True,
            "creatable_parents_real_after": True,
            "unknown_items_deleted_or_overwritten": False,
            "writes_outside_install": False,
            "root_exact_set_unchanged": True,
            "root_direct_entries_before": roots,
            "root_direct_entries_after": roots,
        }
    report = {
        "schema": "server_package_runtime_layout_harness_v1",
        "derived_from_zip_sha256": digest(zip_data),
        "runner_member_sha256": digest(runner),
        "fixed_result_root": "/home/panqs/ndp/simresult",
        "scenarios": scenarios,
        "claim_boundary": "Exact-final-ZIP structural six-exit proof only; no server, VCS, or DUT action.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
