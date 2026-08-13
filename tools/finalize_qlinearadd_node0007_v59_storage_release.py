#!/usr/bin/env python3
"""Stage the exact QAdd v59 portable-waveform package for manager rotation.

This is a local release/staging operation only.  It never uploads, leases,
compiles with VCS, or runs a DUT simulation.
"""

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
PACKAGE = "r5_qadd_n7_tailround_lanephase_qual_v59_portable_vcd_query"
FAMILY = "qlinearadd_node0007"
OUT = ROOT / "outputs/qlinearadd_node0007_v59_portable_vcd_query_release"
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
EXPECTED_ZIP_BYTES = 70752607
EXPECTED_ZIP_SHA256 = "b9bee4ac932fbb5b198ca2c6da5cdacb7598356a59a8e55c909b9694255164a0"


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
        "tests.test_server_waveform_portable_query",
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
    passed = process.returncode == 0 and "Ran 72 tests" in combined and "OK" in combined
    return {
        "schema": "qlinearadd-node0007-v59-local-regression-v1",
        "pass": passed,
        "errors": [] if passed else ["focused regression did not pass 72/72"],
        "command": command,
        "exit_code": process.returncode,
        "expected_test_count": 72,
        "observed_summary": "72/72 PASS" if passed else combined[-8192:],
        "server_action": False,
    }


def inspect_runner() -> dict[str, Any]:
    with zipfile.ZipFile(ZIP) as archive:
        root = archive.namelist()[0].split("/", 1)[0]
        runner = archive.read(f"{root}/PREPARE_AND_RUN.sh").decode(
            "utf-8", errors="replace"
        )
        raw_plan = json.loads(
            archive.read(f"{root}/contracts/server_waveform_mandatory_plan.json")
        )
        profile = json.loads(
            archive.read(f"{root}/contracts/server_waveform_portable_profile.json")
        )
        request = json.loads(
            archive.read(f"{root}/contracts/server_post_sim_return_request.json")
        )
        portable_runtime = archive.read(
            f"{root}/package_tools/qlinearadd_node0007_portable_query_runtime_v59.py"
        ).decode("utf-8", errors="replace")
    actual_argv = (
        'argv=["DUMP_VCD=1","DUMP_PORTABLE_VCD=1","DUMP_FSDB=0",'
        '"TB_DUMP_FSDB=0"'
    )
    core_archives = {entry["archive"] for entry in request["core_entries"]}
    checks = {
        "root_identity": root == PACKAGE,
        "compile_dual_dump_args": (
            "compile DUMP_VCD=1 DUMP_PORTABLE_VCD=1 DUMP_FSDB=0" in runner
            and 'TB_DUMP_FSDB=0 "RUN_DIR=$compile_root"' in runner
        ),
        "simulation_dual_dump_args": (
            "DUMP_VCD=1 DUMP_PORTABLE_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 "
            "timeout --foreground" in runner
        ),
        "actual_simulator_argv_json_bound": (
            "actual_simulator_argv.json" in runner and actual_argv in runner
        ),
        "raw_vpd_preserved": "raw_wave_name=wave.vpd" in runner,
        "portable_vcd_bound": "portable_wave_name=wave.vcd" in runner,
        "no_dump_vcd_0": "DUMP_VCD=0" not in runner,
        "full_hierarchy_depth_zero_no_exclusions": (
            raw_plan["dump"]["scope_mode"] == "FULL_HIERARCHY"
            and raw_plan["dump"]["included_scopes"] == ["tb_NDP_Top_new_phy"]
            and raw_plan["dump"]["hierarchy_depth"] == 0
            and raw_plan["dump"]["excluded_scopes"] == []
            and profile["portable_vcd"]["source_bound_scope"]["top"]
            == "tb_NDP_Top_new_phy"
            and profile["portable_vcd"]["source_bound_scope"]["depth"] == 0
            and "excluded_scopes" not in profile["portable_vcd"]["source_bound_scope"]
        ),
        "direct_vcd_and_query": (
            profile["portable_vcd"]["first_fresh_required"] is True
            and profile["portable_vcd"]["format"] == "VCD"
            and profile["signal_query"]["format"] == "REGISTERED_EVENT_ROWS"
            and profile["signal_query"]["ordered_every_transition"] is True
        ),
        "unbounded_unsampled_untruncated": (
            profile["raw_vpd"]["hard_limit_bytes"] is None
            and profile["raw_vpd"]["sampling"] is False
            and profile["raw_vpd"]["truncation"] is False
            and profile["raw_vpd"]["size_based_deletion"] is False
            and profile["portable_vcd"]["hard_limit_bytes"] is None
            and profile["portable_vcd"]["sampling"] is False
            and profile["portable_vcd"]["truncation"] is False
            and profile["portable_vcd"]["size_based_deletion"] is False
            and profile["signal_query"]["hard_limit_bytes"] is None
            and profile["signal_query"]["hard_limit_events"] is None
            and profile["signal_query"]["sampling"] is False
            and profile["signal_query"]["truncation"] is False
        ),
        "registered_catalog_complete": (
            profile["signal_query"]["ordered_every_transition"] is True
            and len(profile["probe_catalog"]) == 8
        ),
        "portable_failure_fail_closed": (
            "DIAGNOSTIC_EVIDENCE_INCOMPLETE" in runner
            and "raw_core_return_preserved" in runner
            and "return_must_publish" in runner
        ),
        "portable_return_allowlist": all(
            archive_name in core_archives
            for archive_name in (
                "waveforms/run/sim_results/wave.vcd",
                "waveforms/SIGNAL_QUERY_RECEIPT.json",
                "waveforms/PORTABLE_WAVEFORM_RUNTIME_RECEIPT.json",
                "waveforms/PORTABLE_WAVEFORM_VALIDATION.json",
                "waveforms/PORTABLE_WAVEFORM_STATUS.json",
                "waveforms/PORTABLE_RETURN_ALLOWLIST.json",
            )
        ),
        "runtime_exact_tcl_and_four_state_parser": all(
            token in portable_runtime
            for token in (
                "dump -file",
                "wave.vpd",
                "wave.vcd",
                'char not in "01xz"',
                "sequence",
                "candidate_end_states",
            )
        ),
        "partial_exit_collection": all(
            token in runner
            for token in ("TIMEOUT", "HUP", "INT", "TERM", "SIMULATION_NONZERO")
        ),
    }
    return {
        "schema": "qlinearadd-node0007-v59-exact-runner-portable-waveform-v1",
        "pass": all(checks.values()),
        "errors": [name for name, value in checks.items() if value is not True],
        "checks": checks,
        "zip": receipt(ZIP),
        "claim_boundary": "Exact runner/profile/request plumbing only; no server or DUT claim.",
    }


def main() -> int:
    if STAGE.exists():
        raise RuntimeError(f"fresh storage staging directory required: {STAGE}")
    if (
        not ZIP.is_file()
        or ZIP.stat().st_size != EXPECTED_ZIP_BYTES
        or sha256_file(ZIP) != EXPECTED_ZIP_SHA256
    ):
        raise RuntimeError("exact v59 ZIP identity differs")
    sidecar = SIDECAR.read_text(encoding="ascii").split()
    if not sidecar or sidecar[0] != EXPECTED_ZIP_SHA256:
        raise RuntimeError("v59 sidecar differs")

    reports = {
        "formal_return_analysis": FORMAL_ANALYSIS,
        "build": BUILD / f"{PACKAGE}.build.json",
        "frozen_surface": OUT / f"{PACKAGE}.frozen_surface.json",
        "final_zip": OUT / f"{PACKAGE}.final_zip_audit.json",
        "runner": AUDIT / "runner_return_resilience_validation.json",
        "source_bound": AUDIT / "source_bound_final_zip_validation.json",
        "post_sim": AUDIT / "post_sim_return_validation.json",
        "waveform": AUDIT / "waveform_mandatory_validation.json",
        "portable_profile": AUDIT / "portable_profile_validation.json",
        "portable_query": AUDIT / "portable_query_validation.json",
        "first_fresh_contract": AUDIT / "first_fresh_extra_audit_contract.json",
        "first_fresh": AUDIT / "first_fresh_extra_audit_validation.json",
        "clean_extract": AUDIT / "reports/exact_final_zip_clean_extract.json",
        "actual_runner": AUDIT / "reports/actual_runner_entry_and_input_open.json",
        "source_roundtrip": AUDIT / "reports/source_bound_logger_collector_parser_roundtrip.json",
        "post_scenarios": AUDIT / "reports/post_sim_return_core_scenarios.json",
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
    runner_path = STAGE / f"{PACKAGE}.runner_portable_waveform.json"
    write(tests_path, tests)
    write(runner_path, runner)

    release_path = STAGE / f"{PACKAGE}.release.json"
    release = {
        "schema": "qlinearadd-node0007-v59-release-v1",
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
            "v57h passed production compile and entered tail-round stage1; formal "
            "return localized the first divergence to required lanes on the selected "
            "ping-pong port not becoming ready. v58 preserved that read-accept "
            "diagnostic under mandatory authoritative raw VPD."
        ),
        "LAST_PROVEN_GOOD": "C_BUFFER5_MRM_REQUEST_DECODE",
        "FIRST_DIVERGENCE": (
            "C_BUFFER5_ROW_BANK_LANE_VALIDITY_TO_C_BUFFER5_READ_ACCEPT"
        ),
        "current_purpose": (
            "Preserve the v58 tail-round/lane-phase read-accept diagnostic while "
            "adding same-attempt direct unbounded VCD and a source-bound complete "
            "event/query receipt for producer, clear and selected-port-ready timing."
        ),
        "gate_matrix": {
            "final_zip": "PASS",
            "first_fresh_new_epoch": "PASS",
            "source_bound": "PASS_4_POSITIVE_8_NEGATIVE",
            "post_sim": "PASS",
            "runner_resilience_six_exit": "PASS",
            "mandatory_raw_vpd": "PASS",
            "portable_vcd_query": "PASS_POSITIVE_AND_FAIL_CLOSED_NEGATIVE",
            "focused_regression": "PASS_72",
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
        "waveform": {
            "authoritative_raw_vpd_preserved": True,
            "same_attempt_direct_vcd": True,
            "registered_complete_query_receipt": True,
            "full_hierarchy_depth_zero": True,
            "scope_exclusions": [],
            "unbounded": True,
            "sampling": False,
            "truncation": False,
            "portable_failure_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "portable_failure_preserves_raw_core_return": True,
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
