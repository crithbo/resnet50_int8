#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v65_tbvcdrt3"
OUT = ROOT / "outputs/qlinearadd_node0007_v65_tbvcdrt3_release"
TARGET = OUT / "storage_staging"
TEMP = OUT / "storage_staging.tmp"
ANALYSIS = ROOT / "outputs/qlinearadd_node0007_v64_return_r1786704798234127277_2300842"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root is not an object: {path}")
    return value


def main() -> int:
    package_zip = OUT / f"{PACKAGE}.zip"
    repeat_zip = OUT / f"{PACKAGE}.repeat.zip"
    release = OUT / f"{PACKAGE}.release_receipt.json"
    final_audit = OUT / "gates/final_zip_release_audit.json"
    first_fresh = OUT / "gates/first_fresh_validation.json"
    admission = OUT / "gates/package_release_admission.json"
    formal_analysis = ANALYSIS / "formal_return_analysis.json"
    build_failure_audit = ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_APPLICABILITY.json"

    required_pass = (release, final_audit, first_fresh, admission, formal_analysis)
    missing = [str(path) for path in required_pass if not path.is_file()]
    if missing:
        raise RuntimeError(f"required storage evidence is absent: {missing}")
    failed = [str(path) for path in required_pass if load(path).get("pass") is not True]
    if failed:
        raise RuntimeError(f"required storage evidence did not pass: {failed}")
    if not package_zip.is_file() or not repeat_zip.is_file():
        raise RuntimeError("package/repeat ZIP is absent")
    if package_zip.read_bytes() != repeat_zip.read_bytes():
        raise RuntimeError("deterministic repeat ZIP differs")
    if TARGET.exists() or TEMP.exists():
        raise RuntimeError("storage staging already exists; refusing overwrite")

    copies = {
        package_zip: f"{PACKAGE}.zip",
        release: f"{PACKAGE}.release.json",
        OUT / "build_receipt.json": f"{PACKAGE}.build.json",
        OUT / "frozen_surface_receipt.json": f"{PACKAGE}.frozen_surface.json",
        final_audit: f"{PACKAGE}.final_zip_release_audit.json",
        first_fresh: f"{PACKAGE}.first_fresh_validation.json",
        OUT / "gates/focused_regressions.json": f"{PACKAGE}.focused_regressions.json",
        admission: f"{PACKAGE}.package_release_admission.json",
        OUT / "gates/package_release_admission_contract.json": f"{PACKAGE}.package_release_admission_contract.json",
        OUT / "gates/precompile_failure_core.json": f"{PACKAGE}.precompile_failure_core.json",
        OUT / "gates/mode_selector_tree.json": f"{PACKAGE}.mode_selector_tree.json",
        OUT / "gates/mode_selector_zip.json": f"{PACKAGE}.mode_selector_zip.json",
        OUT / "gates/tb_vcd_tree.json": f"{PACKAGE}.tb_vcd_tree.json",
        OUT / "gates/tb_vcd_zip.json": f"{PACKAGE}.tb_vcd_exact_zip.json",
        OUT / "gates/hdl_lexical_tree.json": f"{PACKAGE}.hdl_lexical_tree.json",
        OUT / "gates/hdl_lexical_zip.json": f"{PACKAGE}.hdl_lexical_exact_zip.json",
        OUT / "gates/runner_tree.json": f"{PACKAGE}.runner_tree.json",
        OUT / "gates/runner_zip.json": f"{PACKAGE}.runner_exact_zip.json",
        OUT / "gates/runtime_preflight.json": f"{PACKAGE}.runtime_preflight_native_flow.json",
        OUT / "gates/runtime_layout.json": f"{PACKAGE}.runtime_layout.json",
        OUT / "gates/runtime_layout_harness.json": f"{PACKAGE}.runtime_layout_harness.json",
        OUT / "gates/post_sim.json": f"{PACKAGE}.post_sim_return.json",
        formal_analysis: f"{PACKAGE}.predecessor_v64_formal_return_analysis.json",
        build_failure_audit: f"{PACKAGE}.predecessor_v64_package_build_failure_rule_audit.json",
        ANALYSIS / "streaming_analysis/analysis_state.json": f"{PACKAGE}.predecessor_v64_analysis_state.json",
        ANALYSIS / "streaming_analysis/checkpoints.jsonl": f"{PACKAGE}.predecessor_v64_analysis_checkpoints.jsonl",
        ANALYSIS / "streaming_analysis/report.md": f"{PACKAGE}.predecessor_v64_incremental_report.md",
    }
    absent = [str(path) for path in copies if not path.is_file()]
    if absent:
        raise RuntimeError(f"publication receipt source is absent: {absent}")

    TEMP.mkdir(parents=False)
    try:
        rows = []
        for source, name in sorted(copies.items(), key=lambda item: item[1]):
            target = TEMP / name
            shutil.copy2(source, target)
            rows.append(
                {
                    "name": name,
                    "source": source.relative_to(ROOT).as_posix(),
                    "bytes": target.stat().st_size,
                    "sha256": sha(target),
                }
            )
        zip_sha = sha(TEMP / f"{PACKAGE}.zip")
        sidecar = TEMP / f"{PACKAGE}.zip.sha256"
        sidecar.write_text(f"{zip_sha}  {PACKAGE}.zip\n", encoding="utf-8", newline="\n")
        manifest = {
            "schema": "qadd-v65-storage-publication-staging-v1",
            "package_id": PACKAGE,
            "family": "qlinearadd_node0007",
            "pass": True,
            "package": {
                "name": f"{PACKAGE}.zip",
                "bytes": (TEMP / f"{PACKAGE}.zip").stat().st_size,
                "sha256": zip_sha,
            },
            "deterministic_repeat_byte_equal": True,
            "formal_analysis_bound": {
                "name": f"{PACKAGE}.predecessor_v64_formal_return_analysis.json",
                "sha256": sha(TEMP / f"{PACKAGE}.predecessor_v64_formal_return_analysis.json"),
            },
            "receipts": rows,
            "server_actions_performed": [],
            "claim_boundary": "QAdd-only local storage staging; no server, RTL, config, numeric, workload, rule, plan or registry action.",
        }
        manifest_path = TEMP / f"{PACKAGE}.storage_publication_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(TEMP, TARGET)
    except BaseException:
        if TEMP.exists():
            shutil.rmtree(TEMP)
        raise

    print(
        json.dumps(
            {
                "pass": True,
                "package_id": PACKAGE,
                "source_dir": str(TARGET),
                "member_count": len(list(TARGET.iterdir())),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
