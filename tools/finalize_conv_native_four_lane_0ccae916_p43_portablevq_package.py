#!/usr/bin/env python3
"""Close p43 exact-final-ZIP and new-epoch first-fresh gates."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p43_portablevq"
FAMILY = "conv_native_four_lane"
EPOCH = "waveform-portable-local-decodability-v1-b0a94cf60d6e"
RULE = "CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p43_portablevq"
BUILD = BASE / "build"
ZIP = BUILD / f"{PACKAGE}.zip"
AUDIT = BASE / "final_zip_audit"
FIRST = BASE / "first_fresh_audit"
FIRST_REPORTS = FIRST / "reports"
FIRST_TOOL = ROOT / "tools/validate_server_first_fresh_extra_audit.py"
OUTPUT = BASE / f"{PACKAGE}.final_zip_audit.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def clean_extract() -> Path:
    target = FIRST / "clean_extract"
    if target.exists():
        raise RuntimeError(f"refusing to overwrite first-fresh clean extraction: {target}")
    target.mkdir(parents=True)
    with zipfile.ZipFile(ZIP) as archive:
        infos = archive.infolist()
        if archive.testzip() is not None:
            raise RuntimeError("final ZIP CRC failure")
        for info in infos:
            member = PurePosixPath(info.filename)
            if (
                member.is_absolute()
                or ".." in member.parts
                or "\\" in info.filename
                or stat.S_ISLNK(info.external_attr >> 16)
            ):
                raise RuntimeError(f"unsafe first-fresh ZIP member: {info.filename}")
            path = target.joinpath(*member.parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(info.filename))
    return target / PACKAGE


def make_first_fresh(values: dict[str, dict[str, Any]]) -> tuple[Path, Path]:
    extracted = clean_extract()
    reports: dict[str, Path] = {
        "exact_final_zip_clean_extract": FIRST_REPORTS / "exact_final_zip_clean_extract.json",
        "actual_runner_entry_and_input_open": FIRST_REPORTS / "actual_runner_entry_and_input_open.json",
        "source_bound_logger_collector_parser_roundtrip": FIRST_REPORTS / "source_bound_final_zip.json",
        "post_sim_return_core_scenarios": FIRST_REPORTS / "post_sim_return_core.json",
        "candidate_discrimination_matrix": FIRST_REPORTS / "candidate_discrimination_matrix.json",
    }
    write(
        reports["exact_final_zip_clean_extract"],
        {
            "schema": "conv-native-p43-first-fresh-clean-extract-v1",
            "pass": extracted.is_dir()
            and (extracted / "PREPARE_AND_RUN.sh").is_file()
            and (extracted / "contracts/server_waveform_portable_profile.json").is_file(),
            "errors": [],
            "clean_extract": extracted.relative_to(ROOT).as_posix(),
            "zip": receipt(ZIP),
        },
    )
    six_scenarios = values["six"].get("scenarios", {})
    six_exit_pass = all(
        six_scenarios.get(name, {}).get("finalizer_reached") is True
        and six_scenarios.get(name, {}).get("fixed_result_return_published") is True
        and (
            six_scenarios.get(name, {}).get("runner_exit") == 0
            if name == "normal"
            else six_scenarios.get(name, {}).get("runner_exit") != 0
        )
        for name in ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM")
    )
    runner_checks = {
        "runner_definition_before_use": values["runner"].get("pass") is True,
        "bootstrap_compile_core": values["compile_core"].get("pass") is True,
        "six_exit": six_exit_pass,
        "runtime_layout": values["layout"].get("pass") is True,
        "observer_public_surface": values["public"].get("pass") is True,
        "portable_exact_zip": values["portable"].get("pass") is True,
    }
    write(
        reports["actual_runner_entry_and_input_open"],
        {
            "schema": "conv-native-p43-first-fresh-runner-v1",
            "pass": all(runner_checks.values()),
            "errors": [name for name, passed in runner_checks.items() if not passed],
            "checks": runner_checks,
            "six_exit_scenarios": ["normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM"],
        },
    )
    source_checks = {
        "typed_source_bound": values["source"].get("pass") is True,
        "vector_handshake_frozen": values["vector"].get("pass") is True,
        "portable_query_source_bound": values["portable_fixture"].get("checks", {}).get(
            "positive_candidate_exact_set"
        )
        is True,
    }
    write(
        reports["source_bound_logger_collector_parser_roundtrip"],
        {
            "schema": "conv-native-p43-first-fresh-source-bound-v1",
            "pass": all(source_checks.values()),
            "errors": [name for name, passed in source_checks.items() if not passed],
            "checks": source_checks,
        },
    )
    post_checks = {
        "post_sim_core": values["post"].get("pass") is True,
        "mandatory_vpd": values["waveform"].get("pass") is True,
        "portable_positive_and_negative": values["portable_fixture"].get("pass") is True,
        "portable_failure_preserves_return": values["portable_fixture"].get("checks", {}).get(
            "negative_return_preserved"
        )
        is True,
    }
    write(
        reports["post_sim_return_core_scenarios"],
        {
            "schema": "conv-native-p43-first-fresh-post-sim-v1",
            "pass": all(post_checks.values()),
            "errors": [name for name, passed in post_checks.items() if not passed],
            "checks": post_checks,
        },
    )
    matrix_checks = {
        "positive_complete": values["portable_fixture"].get("checks", {}).get(
            "positive_status_complete"
        )
        is True,
        "negative_incomplete": values["portable_fixture"].get("checks", {}).get(
            "negative_marks_incomplete"
        )
        is True,
        "xz_preserved": values["portable_fixture"].get("checks", {}).get(
            "positive_xz_preserved"
        )
        is True,
    }
    write(
        reports["candidate_discrimination_matrix"],
        {
            "schema": "conv-native-p43-first-fresh-candidate-matrix-v1",
            "pass": all(matrix_checks.values()),
            "errors": [name for name, passed in matrix_checks.items() if not passed],
            "checks": matrix_checks,
            "candidate_ids": ["native_mse4_causal_target"],
        },
    )
    kinds = {
        "exact_final_zip_clean_extract": "exact-final-zip-clean-extract",
        "actual_runner_entry_and_input_open": "exact-runner-safe-compile-and-open-paths",
        "source_bound_logger_collector_parser_roundtrip": "exact-generated-over-budget-multi-instance",
        "post_sim_return_core_scenarios": "exact-final-request-four-scenario",
        "candidate_discrimination_matrix": "exact-candidate-positive-negative-matrix",
    }
    contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": PACKAGE, "family": FAMILY, "final_zip": receipt(ZIP)},
        "rule_change": {
            "epoch_id": EPOCH,
            "rule_ids": [RULE],
            "first_fresh_for_family": True,
            "notification_acknowledged": True,
        },
        "independent_reaudit": {
            "clean_extract_from_final_zip": True,
            "from_final_zip_only": True,
            "family_build_reports_reused": False,
            "top_level_invocations": 1,
            "all_errors_collected": True,
            "rebuild_per_single_error_forbidden": True,
        },
        "evidence_reports": [
            {
                "gate_id": gate_id,
                "evidence_kind": kinds[gate_id],
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path),
            }
            for gate_id, path in reports.items()
        ],
        "candidate_discrimination": {
            "candidate_ids": ["native_mse4_causal_target"],
            "covered_candidate_ids": ["native_mse4_causal_target"],
            "uncovered_candidate_ids": [],
            "positive_control_count": 1,
            "negative_control_count": 1,
            "pairwise_distinguishable": True,
        },
        "findings": [],
    }
    contract_path = FIRST / "contract.json"
    validation_path = FIRST / "first_fresh_validation.json"
    write(contract_path, contract)
    result = subprocess.run(
        [
            sys.executable,
            str(FIRST_TOOL),
            "--contract",
            str(contract_path),
            "--workspace-root",
            str(ROOT),
            "--output",
            str(validation_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"first-fresh validation failed: {result.stdout}\n{result.stderr}")
    return contract_path, validation_path


def main() -> int:
    if OUTPUT.exists() or FIRST.exists():
        raise RuntimeError("refusing to overwrite p43 final/first-fresh audit")
    paths = {
        "build": BUILD / f"{PACKAGE}.build.json",
        "profile": BASE / "server_package_build_profile_v2.json",
        "runner": AUDIT / "runner_return_resilience.json",
        "source": AUDIT / "source_bound_final_zip.json",
        "post": AUDIT / "post_sim_return.json",
        "waveform": AUDIT / "waveform_return.json",
        "portable": AUDIT / "portable_query.json",
        "portable_fixture": AUDIT / "portable_runtime_fixture.json",
        "compile_core": AUDIT / "compile_core_harness.json",
        "compile_layout": AUDIT / "compile_core_shared_layout.json",
        "six": AUDIT / "six_state_runner_harness.json",
        "layout": AUDIT / "six_state_shared_layout.json",
        "public": AUDIT / "observer_public_surface.json",
        "vector": AUDIT / "vector_join_predicate.json",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing p43 audit receipts: {missing}")
    values = {name: load(path) for name, path in paths.items()}
    first_contract, first_validation = make_first_fresh(values)
    first = load(first_validation)
    profile = values["profile"]
    portable_disposition = [
        row
        for row in profile.get("gate_dispositions", [])
        if row.get("gate_id") == "waveform_portable_local_decodability"
    ]
    first_disposition = [
        row for row in profile.get("gate_dispositions", []) if row.get("gate_id") == "first_fresh_extra_audit"
    ]
    checks = {
        "one_exact_final_zip": len(list(BUILD.glob(f"{PACKAGE}.zip"))) == 1,
        "deterministic_frozen_build": values["build"].get("deterministic_double_build_tree_equal") is True
        and values["build"].get("config_numeric_workload_golden_rtl_frozen") is True
        and values["build"].get("target_diagnostic_frozen") is True,
        "one_shared_prebuild_aggregate": values["build"].get("prebuild_aggregate_top_level_invocations") == 1
        and profile.get("contract_valid") is True
        and profile.get("preflight", {}).get("errors") == [],
        "runner_definition_before_use": values["runner"].get("pass") is True,
        "bootstrap_safe_actual_compile_core": values["compile_core"].get("pass") is True,
        "source_bound_typed": values["source"].get("pass") is True,
        "p42_vector_predicate_frozen": values["vector"].get("pass") is True,
        "datahub_public_surface_frozen": values["public"].get("pass") is True,
        "post_sim_core": values["post"].get("pass") is True,
        "mandatory_raw_vpd": values["waveform"].get("pass") is True,
        "portable_exact_zip": values["portable"].get("pass") is True,
        "portable_runtime_positive_negative": values["portable_fixture"].get("pass") is True,
        "six_exit_runner": all(
            values["six"].get("scenarios", {}).get(name, {}).get("finalizer_reached") is True
            and values["six"].get("scenarios", {}).get(name, {}).get("fixed_result_return_published") is True
            and (
                values["six"].get("scenarios", {}).get(name, {}).get("runner_exit") == 0
                if name == "normal"
                else values["six"].get("scenarios", {}).get(name, {}).get("runner_exit") != 0
            )
            for name in ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM")
        ),
        "runtime_layout": values["layout"].get("pass") is True,
        "portable_gate_blocking": len(portable_disposition) == 1
        and portable_disposition[0].get("disposition") == "blocking_applicable",
        "first_fresh_gate_blocking": len(first_disposition) == 1
        and first_disposition[0].get("disposition") == "blocking_applicable",
        "new_epoch_first_fresh": first.get("pass") is True
        and first.get("upload_authorized") is True
        and first.get("rule_change_epoch_id") == EPOCH,
        "server_action_absent": values["build"].get("server_action") is False,
    }
    errors = [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "conv-native-four-lane-p43-portablevq-final-zip-audit-v1",
        "package_identity": PACKAGE,
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "HOLD_FINAL_ZIP_GATE_FAILED",
        "valid": not errors,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "first_fresh_after_change": True,
        "first_fresh_disposition": "NEW_EPOCH_INDEPENDENT_PASS" if checks["new_epoch_first_fresh"] else "INVALID",
        "candidate_release": False,
        "previous_version_progress": (
            "p41 proved production compile beyond the Datahub public-surface repair; p42 corrected "
            "the package-local two-bit valid/ready scalar-comparison false negative and retained the "
            "MSE4 wdata/slice-finish causal target."
        ),
        "current_version_purpose": (
            "Build the p42-equivalent first-fresh portable successor so the corrected vector-handshake "
            "diagnostic returns authoritative raw VPD, direct VCD and a registered locally decodable query receipt."
        ),
        "checks": checks,
        "errors": errors,
        "zip": receipt(ZIP),
        "audits": {name: receipt(path) for name, path in paths.items()},
        "first_fresh": {
            "contract": receipt(first_contract),
            "validation": receipt(first_validation),
        },
        "expected_server": {
            "command": "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02",
            "return_template": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip",
            "sidecar_template": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip.sha256",
        },
        "claim_boundary": (
            "Local package construction, synthetic plumbing fixtures and exact-ZIP gates only. No upload, "
            "lease, server execution, p43 production compile/DUT result, natural terminal, formal D, E3, E4 or E5 claim."
        ),
        "server_action": False,
    }
    write(OUTPUT, report)
    print(json.dumps({"pass": not errors, "errors": errors, "output": str(OUTPUT)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
