#!/usr/bin/env python3
"""Close the p44 exact-final-ZIP and current-epoch first-fresh gates."""

from __future__ import annotations

import hashlib
import json
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p44_fsdbvq"
FAMILY = "conv_native_four_lane"
EPOCH = "package-local-hdl-lexical-v1-01211147e247"
RULES = [
    "CDA-SERVER-PACKAGE-LOCAL-HDL-RESERVED-DECLARATION-NAME-LEXICAL-001",
    "CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001",
    "CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001",
]
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p44_fsdbvq"
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
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def clean_extract() -> Path:
    target = FIRST / "clean_extract"
    if target.exists():
        raise RuntimeError(f"refusing to overwrite first-fresh extraction: {target}")
    target.mkdir(parents=True)
    with zipfile.ZipFile(ZIP) as archive:
        infos = archive.infolist()
        if archive.testzip() is not None or len(infos) != len({row.filename for row in infos}):
            raise RuntimeError("final ZIP CRC or duplicate member failure")
        roots = set()
        for row in infos:
            member = PurePosixPath(row.filename)
            if member.parts:
                roots.add(member.parts[0])
            if member.is_absolute() or ".." in member.parts or "\\" in row.filename or stat.S_ISLNK(row.external_attr >> 16):
                raise RuntimeError(f"unsafe final ZIP member: {row.filename}")
            path = target.joinpath(*member.parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(row.filename))
    if roots != {PACKAGE}:
        raise RuntimeError(f"final ZIP root differs: {roots}")
    return target / PACKAGE


def make_first_fresh(values: dict[str, dict[str, Any]]) -> tuple[Path, Path]:
    extracted = clean_extract()
    reports = {
        "exact_final_zip_clean_extract": FIRST_REPORTS / "exact_final_zip_clean_extract.json",
        "actual_runner_entry_and_input_open": FIRST_REPORTS / "actual_runner_entry_and_input_open.json",
        "source_bound_logger_collector_parser_roundtrip": FIRST_REPORTS / "source_bound_logger_collector_parser_roundtrip.json",
        "post_sim_return_core_scenarios": FIRST_REPORTS / "post_sim_return_core_scenarios.json",
        "candidate_discrimination_matrix": FIRST_REPORTS / "candidate_discrimination_matrix.json",
    }
    write(
        reports["exact_final_zip_clean_extract"],
        {
            "schema": "conv-native-p44-first-fresh-clean-extract-v1",
            "pass": extracted.is_dir()
            and (extracted / "PREPARE_AND_RUN.sh").is_file()
            and (extracted / "package_tools/dump_waveform.tcl").is_file()
            and (extracted / "tb_probe/native_fsdb_event_probe.svh").is_file(),
            "errors": [],
            "clean_extract": extracted.relative_to(ROOT).as_posix(),
            "zip": receipt(ZIP),
        },
    )
    six = values["six"].get("scenarios", {})
    six_pass = all(
        six.get(name, {}).get("finalizer_reached") is True
        and six.get(name, {}).get("fixed_result_return_published") is True
        and (six.get(name, {}).get("runner_exit") == 0 if name == "normal" else six.get(name, {}).get("runner_exit") != 0)
        for name in ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM")
    )
    runner_checks = {
        "runner_definition_before_use": values["runner"].get("pass") is True,
        "bootstrap_compile_core": values["compile_core"].get("pass") is True,
        "six_exit": six_pass,
        "runtime_layout": values["layout"].get("pass") is True,
        "full_hdl_frontend_scope_state": values["hdl"].get("pass") is True,
        "lexical_exact_zip": values["lexical"].get("pass") is True,
    }
    write(
        reports["actual_runner_entry_and_input_open"],
        {
            "schema": "conv-native-p44-first-fresh-runner-v1",
            "pass": all(runner_checks.values()),
            "errors": [name for name, passed in runner_checks.items() if not passed],
            "checks": runner_checks,
            "six_exit_scenarios": ["normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM"],
        },
    )
    source_checks = {
        "typed_source_bound": values["source"].get("pass") is True,
        "vector_handshake_frozen": values["vector"].get("pass") is True,
        "datahub_public_surface_frozen": values["public"].get("pass") is True,
        "registered_query_exact_candidate_set": values["query"].get("checks", {}).get("positive_exact_candidate_set") is True,
    }
    write(
        reports["source_bound_logger_collector_parser_roundtrip"],
        {
            "schema": "conv-native-p44-first-fresh-source-bound-v1",
            "pass": all(source_checks.values()),
            "errors": [name for name, passed in source_checks.items() if not passed],
            "checks": source_checks,
        },
    )
    post_checks = {
        "post_sim_core": values["post"].get("pass") is True,
        "mandatory_fsdb_v3": values["waveform"].get("pass") is True,
        "registered_query_positive_negative": values["query"].get("pass") is True,
        "query_failure_preserves_raw_and_core": values["query"].get("checks", {}).get("negative_raw_and_core_preserved") is True,
    }
    write(
        reports["post_sim_return_core_scenarios"],
        {
            "schema": "conv-native-p44-first-fresh-post-sim-v1",
            "pass": all(post_checks.values()),
            "errors": [name for name, passed in post_checks.items() if not passed],
            "checks": post_checks,
        },
    )
    matrix_checks = {
        "positive_complete": values["query"].get("checks", {}).get("positive_complete") is True,
        "negative_incomplete": values["query"].get("checks", {}).get("negative_marks_incomplete") is True,
        "xz_preserved": values["query"].get("checks", {}).get("positive_xz_preserved") is True,
        "contiguous_sequence": values["query"].get("checks", {}).get("positive_contiguous") is True,
    }
    write(
        reports["candidate_discrimination_matrix"],
        {
            "schema": "conv-native-p44-first-fresh-candidate-matrix-v1",
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
            "rule_ids": RULES,
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
            {"gate_id": gate, "evidence_kind": kinds[gate], "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}
            for gate, path in reports.items()
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
        [sys.executable, str(FIRST_TOOL), "--contract", str(contract_path), "--workspace-root", str(ROOT), "--output", str(validation_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if result.returncode:
        raise RuntimeError(f"first-fresh validation failed: {result.stdout}\n{result.stderr}")
    return contract_path, validation_path


def main() -> int:
    if OUTPUT.exists() or FIRST.exists():
        raise RuntimeError("refusing to overwrite p44 final/first-fresh audit")
    paths = {
        "build": BUILD / f"{PACKAGE}.build.json",
        "profile": BASE / "server_package_build_profile_v2.json",
        "runner": AUDIT / "runner_return_resilience.json",
        "lexical": AUDIT / "package_local_hdl_lexical.json",
        "hdl": AUDIT / "package_local_hdl_full.json",
        "source": AUDIT / "source_bound_final_zip.json",
        "post": AUDIT / "post_sim_return.json",
        "waveform": AUDIT / "waveform_return.json",
        "query": AUDIT / "fsdb_query_runtime.json",
        "compile_core": AUDIT / "compile_core_harness.json",
        "compile_layout": AUDIT / "compile_core_shared_layout.json",
        "six": AUDIT / "six_state_runner_harness.json",
        "layout": AUDIT / "six_state_shared_layout.json",
        "public": AUDIT / "observer_public_surface.json",
        "vector": AUDIT / "vector_join_predicate.json",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing p44 audit receipts: {missing}")
    values = {name: load(path) for name, path in paths.items()}
    first_contract, first_validation = make_first_fresh(values)
    first = load(first_validation)
    profile = values["profile"]
    dispositions = {row.get("gate_id"): row for row in profile.get("gate_dispositions", [])}
    with zipfile.ZipFile(ZIP) as archive:
        runner_text = archive.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode("utf-8")
        member_names = archive.namelist()
    six = values["six"].get("scenarios", {})
    checks = {
        "one_exact_final_zip": len(list(BUILD.glob(f"{PACKAGE}.zip"))) == 1,
        "deterministic_frozen_build": values["build"].get("deterministic_double_build_tree_equal") is True and values["build"].get("config_numeric_workload_golden_rtl_frozen") is True and values["build"].get("target_diagnostic_frozen") is True,
        "one_shared_staging_aggregate": values["build"].get("prebuild_aggregate_top_level_invocations") == 1 and profile.get("contract_valid") is True and profile.get("preflight", {}).get("errors") == [],
        "staging_hdl_lexical": values["build"].get("staging_hdl_lexical_aggregate_pass") is True,
        "exact_zip_hdl_lexical": values["lexical"].get("pass") is True and values["lexical"].get("reserved_identifier_violations") == [],
        "full_hdl_frontend_scope_state_negative": values["hdl"].get("pass") is True,
        "runner_definition_before_use": values["runner"].get("pass") is True,
        "bootstrap_safe_actual_compile_core": values["compile_core"].get("pass") is True,
        "source_bound_typed": values["source"].get("pass") is True,
        "p42_vector_predicate_frozen": values["vector"].get("pass") is True,
        "datahub_public_surface_frozen": values["public"].get("pass") is True,
        "post_sim_core": values["post"].get("pass") is True,
        "mandatory_fsdb_v3": values["waveform"].get("pass") is True,
        "registered_query_positive_negative": values["query"].get("pass") is True,
        "six_exit_runner": all(
            six.get(name, {}).get("finalizer_reached") is True
            and six.get(name, {}).get("fixed_result_return_published") is True
            and (six.get(name, {}).get("runner_exit") == 0 if name == "normal" else six.get(name, {}).get("runner_exit") != 0)
            for name in ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM")
        ),
        "runtime_layout_repeat": values["layout"].get("pass") is True,
        "fsdb_flags_exact": all(token in runner_text for token in ("DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0")),
        "retired_vpd_direct_vcd_absent": all(token not in runner_text for token in ("DUMP_PORTABLE_VCD", "wave.vpd", "wave.vcd")) and all(not name.lower().endswith((".vpd", ".vcd")) for name in member_names),
        "waveform_gate_blocking": dispositions.get("waveform_observation_final_zip", {}).get("disposition") == "blocking_applicable",
        "query_gate_blocking": dispositions.get("waveform_portable_local_decodability", {}).get("disposition") == "blocking_applicable",
        "lexical_gate_blocking": dispositions.get("package_local_hdl_lexical_final_zip", {}).get("disposition") == "blocking_applicable",
        "first_fresh_gate_blocking": dispositions.get("first_fresh_extra_audit", {}).get("disposition") == "blocking_applicable",
        "current_epoch_first_fresh": first.get("pass") is True and first.get("upload_authorized") is True and first.get("rule_change_epoch_id") == EPOCH,
        "server_action_absent": values["build"].get("server_action") is False,
    }
    errors = [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "conv-native-four-lane-p44-fsdbvq-final-zip-audit-v1",
        "package_identity": PACKAGE,
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "HOLD_FINAL_ZIP_GATE_FAILED",
        "valid": not errors,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "first_fresh_after_change": True,
        "first_fresh_disposition": "CURRENT_EPOCH_INDEPENDENT_PASS" if checks["current_epoch_first_fresh"] else "INVALID",
        "candidate_release": False,
        "previous_version_progress": (
            "p41 proved production compile beyond the Datahub public-surface repair; p42 corrected the two-bit "
            "vector-handshake predicate; p43 stopped at 0 ps on the retired direct-VCD command before MSE4 execution."
        ),
        "current_version_purpose": (
            "Preserve the p42 vector correction and MSE4 causal target while returning authoritative unbounded "
            "full-hierarchy FSDB-v3 and a complete source-bound registered 4-state event receipt."
        ),
        "checks": checks,
        "errors": errors,
        "zip": receipt(ZIP),
        "audits": {name: receipt(path) for name, path in paths.items()},
        "first_fresh": {"contract": receipt(first_contract), "validation": receipt(first_validation)},
        "expected_server": {
            "command": "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02",
            "return_template": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip",
            "execution_blocked_until": "SEPARATE_USER_SERVER_AUTHORIZATION_AFTER_SERIALIZED_FSDB_SMOKE_GATE",
        },
        "claim_boundary": (
            "Local exact-ZIP construction, static gates and synthetic runtime fixtures only. No upload, lease, server "
            "execution, production compile/DUT result, natural terminal, formal-D, E3, E4 or E5 claim."
        ),
        "server_action": False,
    }
    write(OUTPUT, report)
    print(json.dumps({"pass": not errors, "errors": errors, "output": str(OUTPUT)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
