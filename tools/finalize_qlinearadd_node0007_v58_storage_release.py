#!/usr/bin/env python3
"""Stage exact QAdd v58 package/receipts for package-storage rotation."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_qual_v58_mandatory_vpd"
FAMILY = "qlinearadd_node0007"
OUT = ROOT / "outputs/qlinearadd_node0007_v58_mandatory_vpd_release"
BUILD = OUT / "build"
AUDIT = OUT / "exact_zip_audit"
STAGE = OUT / "storage_release"
ZIP = BUILD / f"{PACKAGE}.zip"
SIDECAR = BUILD / f"{PACKAGE}.zip.sha256"
FORMAL_ANALYSIS = (
    ROOT
    / "outputs/qlinearadd_node0007_v57h_formal_return_1113452"
    / "formal_return_analysis.json"
)
EXPECTED_ZIP_BYTES = 46652561
EXPECTED_ZIP_SHA256 = "97c5fce6714e9a53937043fb7626d2b462c52ce362147341b834fa33c2b9582d"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be object: {path}")
    return value


def write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def run_tests() -> dict[str, Any]:
    modules = [
        "tests.test_server_waveform_mandatory_return",
        "tests.test_server_post_sim_return",
        "tests.test_server_runner_return_resilience",
        "tests.test_server_first_fresh_extra_audit",
        "tests.test_qlinearadd_node0007_source_bound_stage_filter_v57",
        "tests.test_manage_server_test_package_storage",
    ]
    command = [sys.executable, "-B", "-m", "unittest", *modules, "-v"]
    process = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    combined = process.stdout + process.stderr
    passed = process.returncode == 0 and "Ran 60 tests" in combined and "OK" in combined
    return {
        "schema": "qlinearadd-node0007-v58-local-regression-v1",
        "pass": passed,
        "errors": [] if passed else ["focused regression did not pass 60/60"],
        "command": command,
        "exit_code": process.returncode,
        "expected_test_count": 60,
        "observed_summary": "60/60 PASS" if passed else combined[-8192:],
        "server_action": False,
    }


def inspect_runner() -> dict[str, Any]:
    with zipfile.ZipFile(ZIP) as archive:
        root = archive.namelist()[0].split("/", 1)[0]
        runner = archive.read(f"{root}/PREPARE_AND_RUN.sh").decode(
            "utf-8", errors="replace"
        )
        plan = json.loads(
            archive.read(f"{root}/contracts/server_waveform_mandatory_plan.json")
        )
        request = json.loads(
            archive.read(f"{root}/contracts/server_post_sim_return_request.json")
        )
    checks = {
        "root_identity": root == PACKAGE,
        "compile_dump_vcd_1": "compile DUMP_VCD=1 DUMP_FSDB=0" in runner,
        "compile_tb_dump_fsdb_0": 'TB_DUMP_FSDB=0 "RUN_DIR=$compile_root"' in runner,
        "sim_dump_arguments": (
            "DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 timeout --foreground" in runner
        ),
        "actual_simulator_argv_records_dump_arguments": (
            "actual_simulator_argv.txt" in runner
            and "DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 timeout" in runner
        ),
        "no_dump_vcd_0": "DUMP_VCD=0" not in runner,
        "full_hierarchy_depth_zero": (
            plan["dump"]["scope_mode"] == "FULL_HIERARCHY"
            and plan["dump"]["included_scopes"] == ["tb_NDP_Top_new_phy"]
            and plan["dump"]["hierarchy_depth"] == 0
            and plan["dump"]["excluded_scopes"] == []
        ),
        "unbounded_return": (
            plan["return_policy"]["hard_limit_bytes"] is None
            and plan["return_policy"]["collect_all_matching"] is True
            and request["waveform_discovery"]["no_size_limit"] is True
        ),
        "started_missing_wave_fail_closed": (
            '[ "$waveform_receipt_rc" -eq 0 ] || final=97' in runner
        ),
        "partial_exit_collection": all(
            token in runner
            for token in ("TIMEOUT", "HUP", "INT", "TERM", "SIMULATION_NONZERO")
        ),
    }
    return {
        "schema": "qlinearadd-node0007-v58-exact-runner-waveform-v1",
        "pass": all(checks.values()),
        "errors": [name for name, value in checks.items() if value is not True],
        "checks": checks,
        "zip": receipt(ZIP),
        "claim_boundary": "Exact runner/plan/request plumbing only; no server or DUT claim.",
    }


def main() -> int:
    if STAGE.exists():
        raise RuntimeError(f"fresh storage staging directory required: {STAGE}")
    if (
        not ZIP.is_file()
        or ZIP.stat().st_size != EXPECTED_ZIP_BYTES
        or sha256_file(ZIP) != EXPECTED_ZIP_SHA256
    ):
        raise RuntimeError("exact v58 ZIP identity differs")
    sidecar = SIDECAR.read_text(encoding="ascii").split()
    if not sidecar or sidecar[0] != EXPECTED_ZIP_SHA256:
        raise RuntimeError("v58 sidecar differs")

    reports = {
        "formal_return_analysis": FORMAL_ANALYSIS,
        "build": BUILD / f"{PACKAGE}.build.json",
        "frozen_surface": OUT / f"{PACKAGE}.frozen_surface.json",
        "final_zip": OUT / f"{PACKAGE}.final_zip_audit.json",
        "runner": AUDIT / "runner_return_resilience_validation.json",
        "source_bound": AUDIT / "source_bound_final_zip_validation.json",
        "post_sim": AUDIT / "post_sim_return_validation.json",
        "waveform": AUDIT / "waveform_mandatory_validation.json",
        "first_fresh_contract": AUDIT / "first_fresh_extra_audit_contract.json",
        "first_fresh": AUDIT / "first_fresh_extra_audit_validation.json",
        "clean_extract": AUDIT / "reports/exact_final_zip_clean_extract.json",
        "candidate_matrix": AUDIT / "reports/candidate_discrimination_matrix.json",
    }
    missing = [str(path) for path in reports.values() if not path.is_file()]
    if missing:
        raise RuntimeError(f"release reports absent: {missing}")
    values = {name: load(path) for name, path in reports.items()}
    required_pass = {
        name: value.get("pass") is True
        for name, value in values.items()
        if name not in {"build", "first_fresh_contract"}
    }
    required_pass["build"] = values["build"].get("final_audit_pass") is True
    required_pass["first_fresh_upload_authorized"] = (
        values["first_fresh"].get("upload_authorized") is True
    )
    failures = [name for name, passed in required_pass.items() if not passed]
    if failures:
        raise RuntimeError(f"release gates failed: {failures}")

    tests = run_tests()
    runner = inspect_runner()
    if tests["pass"] is not True or runner["pass"] is not True:
        raise RuntimeError(
            f"final local checks failed: tests={tests['errors']} runner={runner['errors']}"
        )

    STAGE.mkdir()
    shutil.copy2(ZIP, STAGE / ZIP.name)
    shutil.copy2(SIDECAR, STAGE / SIDECAR.name)
    for name, path in reports.items():
        shutil.copy2(path, STAGE / f"{PACKAGE}.{name}.json")
    tests_path = STAGE / f"{PACKAGE}.local_tests.json"
    runner_path = STAGE / f"{PACKAGE}.runner_waveform.json"
    write(tests_path, tests)
    write(runner_path, runner)

    release_path = STAGE / f"{PACKAGE}.release.json"
    release = {
        "schema": "qlinearadd-node0007-v58-release-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "pass": True,
        "errors": [],
        "package_id": PACKAGE,
        "family": FAMILY,
        "zip": receipt(STAGE / ZIP.name),
        "sidecar": receipt(STAGE / SIDECAR.name),
        "formal_return_analysis": receipt(
            STAGE / f"{PACKAGE}.formal_return_analysis.json"
        ),
        "previous_progress": (
            "v57h passed production compile and started simulation; tail-round "
            "stage1 was entered, but the run timed out without natural terminal "
            "and formal D remained 0/28."
        ),
        "LAST_PROVEN_GOOD": "C_BUFFER5_MRM_REQUEST_DECODE",
        "FIRST_DIVERGENCE": (
            "C_BUFFER5_ROW_BANK_LANE_VALIDITY_TO_C_BUFFER5_READ_ACCEPT"
        ),
        "current_purpose": (
            "Preserve the v57h tail-round/lane-phase diagnostic and return full "
            "tb_NDP_Top_new_phy depth-0 unbounded VPD plus formal evidence for "
            "the current Buffer5 selected-port/bank-lane readiness stall."
        ),
        "gate_matrix": {
            "final_zip": "PASS",
            "first_fresh": "PASS_UPLOAD_AUTHORIZED",
            "source_bound": "PASS_4_POSITIVE_8_NEGATIVE",
            "post_sim": "PASS",
            "runner_resilience": "PASS",
            "mandatory_waveform": "PASS",
            "focused_regression": "PASS_60",
            "storage_exact_set": "PENDING_MANAGER_ROTATION",
        },
        "frozen": {
            "config": True,
            "numeric": True,
            "workload_semantics": True,
            "golden": True,
            "functional_rtl": True,
            "target_diagnostic_exact_bytes": True,
        },
        "server_action": False,
        "lease_acquired": False,
        "claim_boundary": (
            "PACKAGE_READY_NOT_RUN local package/fixture claim only; no production "
            "compile, simulation, natural terminal, formal D, E4 or E5 claim."
        ),
    }
    write(release_path, release)
    print(
        json.dumps(
            {
                "status": release["status"],
                "stage": relative(STAGE),
                "member_count": len(list(STAGE.iterdir())),
                "zip": release["zip"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
