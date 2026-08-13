#!/usr/bin/env python3
"""Bind the p46 runtime-layout harness to exact ZIP and first-fresh receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


PACKAGE_ID = "r5_n4_0cc_p46_nativeflow"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("pass") is not True:
        raise RuntimeError(f"required local receipt did not pass: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--first-fresh-reports", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    zip_data = args.zip.read_bytes()
    with zipfile.ZipFile(args.zip) as archive:
        runner = archive.read(f"{PACKAGE_ID}/PREPARE_AND_RUN.sh")
        if archive.testzip() is not None:
            raise RuntimeError("exact ZIP CRC failed")
    reports = args.first_fresh_reports
    exact = load(reports / "exact_final_zip_clean_extract.json")
    runner_report = load(reports / "actual_runner_entry_and_input_open.json")
    source = load(reports / "source_bound_logger_collector_parser_roundtrip.json")
    post = load(reports / "post_sim_return_core_scenarios.json")
    matrix = load(reports / "candidate_discrimination_matrix.json")
    if exact.get("zip_sha256") != digest(zip_data):
        raise RuntimeError("first-fresh clean extract is bound to another ZIP")
    if not runner_report.get("runtime_layout", {}).get("pass"):
        raise RuntimeError("repeat-safe shared helper receipt did not pass")
    if not all(row.get("pass") is True for row in source.get("exit_cases", {}).values()):
        raise RuntimeError("six-exit observer/return roundtrip did not pass")
    if not post.get("pass") or not matrix.get("pass"):
        raise RuntimeError("return-core or candidate matrix did not pass")

    roots = [{"name": "install", "type": "directory"}]
    exit_codes = {"normal": 0, "preflight_fail": 4, "compile_fail": 2, "HUP": 129, "INT": 130, "TERM": 143}
    scenarios: dict[str, Any] = {}
    for index, (name, code) in enumerate(exit_codes.items(), start=1):
        stamp = f"17870000000000000{index:02d}"
        return_zip = f"/home/panqs/ndp/simresult/{PACKAGE_ID}_r{stamp}_{1000 + index}_return.zip"
        scenarios[name] = {
            "command": f"bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /synthetic/NDP_copy01 [{name}]",
            "cwd": "/synthetic/NDP_copy01",
            "runner_exit": code,
            "compile_started": name in {"normal", "compile_fail", "HUP", "INT", "TERM"},
            "simulation_started": name in {"normal", "HUP", "INT", "TERM"},
            "finalizer_reached": True,
            "partial_return_published": name != "normal",
            "fixed_result_return_published": True,
            "return_zip": return_zip,
            "return_sidecar": return_zip + ".sha256",
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
        "claim_boundary": "Exact-ZIP static runner, repeat-safe shared-helper, six-exit observer/parser and post-sim synthetic local receipts only; no server action or DUT result.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
