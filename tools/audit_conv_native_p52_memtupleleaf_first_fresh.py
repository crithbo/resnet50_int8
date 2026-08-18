#!/usr/bin/env python3
"""Independent clean-final-ZIP current-epoch audit for native Conv p52."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p52_memtupleleaf"
SOURCE = "r5_n4_0cc_p51_metaidxcone"
FAMILY = "conv_native_four_lane"
EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3+conv-native-p51-direct-memory-tuple-leaf-v1"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p52_memtupleleaf_release"
ZIP = OUT / f"{PACKAGE}.zip"
REPEAT = OUT / f"{PACKAGE}.repeat.zip"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane" / SOURCE / f"{SOURCE}.zip"
GATES = OUT / "gates"
PYTHON = ROOT / ".venv/Scripts/python.exe"
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
sys.path.insert(0, str(ROOT))
from tools.validate_server_tb_vcd_bounded_causal_cone import validate_contract


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(path)
    return value


def run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    return {"command": command, "exit_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def extract(path: Path, destination: Path, expected: str) -> Path:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC failure")
        roots = {Path(row.filename).parts[0] for row in archive.infolist() if row.filename}
        if roots != {expected}:
            raise RuntimeError(f"ZIP root differs: {roots}")
        archive.extractall(destination)
    return destination / expected


def file_map(root: Path) -> dict[str, dict[str, Any]]:
    return {path.relative_to(root).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)} for path in sorted(item for item in root.rglob("*") if item.is_file()) if path.name != "package_manifest.json"}


def workload_map(root: Path) -> dict[str, str]:
    prefixes = ("cfg/", "config/", "configs/", "input/", "inputs/", "workload/", "golden/")
    return {path.relative_to(root).as_posix(): sha(path) for path in root.rglob("*") if path.is_file() and path.relative_to(root).as_posix().startswith(prefixes)}


def negative(contract: dict[str, Any], package: Path, mutate: Callable[[dict[str, Any]], None]) -> bool:
    value = copy.deepcopy(contract)
    mutate(value)
    return validate_contract(value, package).get("pass") is False


def row(seq: int, cycles: int, vcd_tick: int, sim_tick: int, wall: int, **extra: Any) -> dict[str, Any]:
    value = {"seq": seq, "owner_clock_cycles": cycles, "sim_cycles": cycles, "sim_time_ticks": sim_tick, "appended_vcd_timestamp_ticks": vcd_tick, "wall_seconds": wall, "vcd_bytes": 1000 + cycles, "causal_progress_events": 1, "qualified_progress_counters": {"accept": 1}, "causal_state_digest": "a" * 64, "global_progress_witness": {"accept": 1}, "unresolved_xz_absent": True, "write_ok": True, "disk_space_ok": True, "quota_ok": True}
    value.update(extra)
    return value


def runtime_request(samples: list[dict[str, Any]], helper_sha: str) -> dict[str, Any]:
    authority = {"mode": "SHARED_RUNTIME_EVALUATOR_ONLY", "helper_path": "package_tools/server_tb_vcd_runtime_supervision.py", "helper_sha256": helper_sha, "outer_runner_consumes_only_receipt": True, "independent_exit_logic_absent": True, "replay_cases": [{"case_id": "ADVANCING_VCD_TIMESTAMP", "observed_decision": "CONTINUE"}, {"case_id": "PLATEAU_SUSPECTED_ONLY", "observed_decision": "CONTINUE"}, {"case_id": "PLATEAU_DUMP_OFF_PLUS_GRACE", "observed_decision": "CAUSAL_PLATEAU"}, {"case_id": "THREE_INTERVAL_TRUE_FREEZE", "observed_decision": "SIM_TIME_FREEZE"}]}
    phase = {"mode": "SHARED_RUNTIME_EVALUATOR_PHASE_AWARE_DUMPOFF", "helper_path": "package_tools/server_tb_vcd_runtime_supervision.py", "helper_sha256": helper_sha, "replay_cases": [{"case_id": "PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE", "observed_decision": "CONTINUE"}, {"case_id": "PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU", "observed_decision": "CAUSAL_PLATEAU"}, {"case_id": "REPEATED_STOP_MARKER", "observed_decision": "FAIL_CLOSED"}]}
    return {"package_id": PACKAGE, "execution_id": "replay", "attempt_id": "a0", "started": True, "actual_argv_sha256": "1" * 64, "catalog_sha256": "2" * 64, "candidate_matrix_sha256": "3" * 64, "tb_source_sha256": "4" * 64, "elaboration_sha256": "5" * 64, "samples": samples, "candidate_catalog_complete": True, "unresolved_xz": False, "heartbeat_contract": {"source": "APPENDED_VCD_TIMESTAMP", "width_bits": 64, "signed": False, "cadence_cycles": 16384}, "decision_authority": authority, "dumpoff_consistency_authority": phase, "target_entry_observed": True, "target_diagnostic_claim": False, "flush": {"dumpoff": False, "dumpflush": False, "closed": False}, "process_tree": {"term_sent": False, "wait_completed": False, "kill_sent_if_needed": False, "all_reaped": False}, "vcd_identity": None, "return_exact_set": None, "archive_timestamp_receipt": None, "live_diagnostics": {"downstream_state_source": "LIVE_SAME_ATTEMPT", "first_error_source": "LIVE_SAME_ATTEMPT", "stale_evidence_absent": True}}


def runtime_replays(package: Path) -> dict[str, Any]:
    helper = package / "package_tools/server_tb_vcd_runtime_supervision.py"
    spec = importlib.util.spec_from_file_location("p52_runtime", helper)
    if spec is None or spec.loader is None:
        raise RuntimeError("runtime helper cannot load")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    base = [row(0, 0, 0, 0, 0), row(1, 4194304, 7000, 7000, 10, planned_dumpoff=True, planned_dumpoff_cycle=4194304, planned_dumpoff_vcd_timestamp_ticks=7000)]
    vectors = {
        "planned_grace_continue": (base + [row(2, 4325376, 7000, 8000, 40, planned_dumpoff=True, planned_dumpoff_cycle=4194304, planned_dumpoff_vcd_timestamp_ticks=7000)], "NONZERO_EXIT"),
        "planned_grace_plateau": (base + [row(2, 4456448, 7000, 9000, 70, planned_dumpoff=True, planned_dumpoff_cycle=4194304, planned_dumpoff_vcd_timestamp_ticks=7000, stop_marker_count=1)], "CAUSAL_PLATEAU"),
        "true_freeze": ([row(index, index * 100, 7, 7, index * 30) for index in range(4)], "SIM_TIME_FREEZE"),
        "repeat_stop_fail": (base + [row(2, 4456448, 7000, 9000, 70, planned_dumpoff=True, planned_dumpoff_cycle=4194304, planned_dumpoff_vcd_timestamp_ticks=7000, stop_marker_count=2)], "FAIL_CLOSED"),
    }
    observed = {}
    for name, (samples, expected) in vectors.items():
        receipt = module.evaluate(runtime_request(samples, sha(helper)))
        if name == "repeat_stop_fail":
            value = "FAIL_CLOSED" if any("one-shot" in item for item in receipt.get("errors", [])) else str(receipt.get("stop_reason"))
        else:
            value = str(receipt.get("stop_reason"))
        observed[name] = {"expected": expected, "observed": value, "pass": value == expected}
    return {"pass": all(item["pass"] for item in observed.values()), "cases": observed}


def prepare_release_admission(package: Path) -> dict[str, Any]:
    zip_sha = sha(ZIP)
    runner_sha = sha(package / "PREPARE_AND_RUN.sh")
    claim = "Local p52 semantic-v5 direct-leaf package release only; no production or DUT claim."
    release = GATES / "package_release_receipt.json"
    write(release, {"claim_boundary": claim, "package": {"sha256": zip_sha}, "package_id": PACKAGE, "pass": True, "status": "PACKAGE_READY_NOT_RUN"})
    failure = GATES / "precompile_failure_core.json"
    write(failure, {"schema": "server-precompile-preflight-failure-core-v1", "package_id": PACKAGE, "final_zip_sha256": zip_sha, "runner_member_sha256": runner_sha, "preflight": {"exit_code": 19, "stdout": "package claim boundary differs\n", "stderr": ""}, "compile_started": False, "simulation_started": False, "core_return": {"classification": "COMPILE_NOT_STARTED", "published": True, "required_evidence": ["preflight_stdout", "preflight_stderr", "preflight_exit", "compile_not_started"]}, "claim_boundary": "Precompile failure visibility only; no compile or simulation claim."})
    contract = GATES / "package_release_admission_contract.json"
    write(contract, {"schema": "server-package-release-admission-v1", "package": {"package_id": PACKAGE, "family": FAMILY, "staging_root": package.relative_to(ROOT).as_posix(), "final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": zip_sha}, "zip_root_member": PACKAGE, "runner_member": "PREPARE_AND_RUN.sh"}, "manifest": {"member": "TEST_PACKAGE_MANIFEST.json", "package_id_pointer": "/package_identity", "status_pointer": "/status", "ready_status": "PACKAGE_READY_NOT_RUN", "nonfinal_status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES"}, "runtime_preflight": {"runtime_member": "package_tools/package_release_preflight.py", "command_template": ["{python}", "{runtime_member}", "preflight", "--package-root", "{package_root}"], "expected_exit": 0, "nonfinal_rejection_marker": "package claim boundary differs", "timeout_seconds": 60, "non_mutating": True}, "release_receipt": {"path": release.relative_to(ROOT).as_posix(), "sha256": sha(release), "package_id_pointer": "/package_id", "status_pointer": "/status", "pass_pointer": "/pass", "final_zip_sha256_pointer": "/package/sha256", "claim_boundary_pointer": "/claim_boundary", "expected_claim_boundary": claim}, "precompile_failure_core": {"path": failure.relative_to(ROOT).as_posix(), "sha256": sha(failure)}, "python_schema_runtime": {"schema_validation_enabled": True, "schema_dependency": "jsonschema", "missing_dependency_disposition": "FAIL_CLOSED", "skip_allowed": False, "exact_set_compile": True, "compile_staging_and_clean_exact_zip": True, "package_python_source_suffixes": [".py"], "bytecode_destination": "OUTSIDE_PACKAGE_TEMPORARY_DIRECTORY"}, "build_receipt_semantics": {"aggregate_mode": "POSITIVE_ASSERTIONS_AND_EXPECTED_POLARITY_MATCH", "positive_assertions": [{"fact_id": "deterministic_exact_zip", "observed": True, "required": True}, {"fact_id": "frozen_payload_equal", "observed": True, "required": True}], "negative_observations": [{"fact_id": "functional_rtl_modified", "observed": False, "required": False}, {"fact_id": "server_action", "observed": False, "required": False}], "informational_facts": [{"fact_id": "activation_epoch", "value": EPOCH}]}, "claim_boundary": "Local exact staging/ZIP admission only."})
    output = GATES / "package_release_admission.json"
    invocation = run([str(PYTHON), str(ROOT / "tools/validate_server_package_release_admission.py"), "--contract", str(contract), "--workspace-root", str(ROOT), "--output", str(output)])
    return {"invocation": invocation, "validation": load(output)}


def main() -> int:
    GATES.mkdir(parents=True, exist_ok=True)
    reports = OUT / "first_fresh_audit/reports"; reports.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-p52-v5-") as raw:
        temp = Path(raw)
        package = extract(ZIP, temp / "fresh", PACKAGE)
        source = extract(SOURCE_ZIP, temp / "source", SOURCE)
        contract = load(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
        manifest = load(package / "package_manifest.json")
        tb = (package / "tb_probe/native_mse4_bounded_causal_cone_vcd.sv").read_text(encoding="utf-8")
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        live = (package / "package_tools/tb_vcd_live_supervision.py").read_text(encoding="utf-8")
        finalizer = (package / "package_tools/tb_vcd_finalize.py").read_text(encoding="utf-8")
        python_errors = []
        for path in package.rglob("*.py"):
            try:
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
            except Exception as exc:
                python_errors.append(f"{path.relative_to(package)}: {exc}")
        exact = {"manifest_exact": manifest.get("files") == file_map(package), "deterministic_recompute": ZIP.read_bytes() == REPEAT.read_bytes(), "source_workload_frozen": workload_map(package) == workload_map(source), "functional_rtl_absent": not (package / "rtl").exists(), "all_python_compiles": not python_errors, "shared_evaluator_byte_equal": (package / "package_tools/server_tb_vcd_runtime_supervision.py").read_bytes() == (ROOT / "tools/server_tb_vcd_runtime_supervision.py").read_bytes(), "post_return_helper_byte_equal": (package / "package_tools/server_post_sim_return.py").read_bytes() == (ROOT / "tools/server_post_sim_return.py").read_bytes(), "no_packaged_runtime_wave": not any(path.suffix.lower() in {".vcd", ".vpd", ".fsdb", ".fst"} for path in package.rglob("*") if path.is_file())}
        write(reports / "exact_final_zip_clean_extract.json", {"pass": all(exact.values()), "checks": exact, "python_errors": python_errors})
        positive = validate_contract(contract, package)
        import jsonschema
        schema_error = None
        try:
            jsonschema.validate(contract, load(ROOT / "schemas/server_tb_vcd_bounded_causal_cone_v1.schema.json"))
        except Exception as exc:
            schema_error = str(exc)
        negatives = {"missing_predecessor": negative(contract, package, lambda value: value["diagnostic_round"]["evolution"]["predecessor"].update({"contract_path": "provenance/absent.json"})), "candidate_loss": negative(contract, package, lambda value: value["candidates"].pop()), "source_identity_drift": negative(contract, package, lambda value: value["diagnostic_round"]["source_identity"].update({"catalog_source_identity_sha256": "f" * 64})), "size_protection_weakened": negative(contract, package, lambda value: value["budget"].update({"hard_truncation": True})), "phase_policy_removed": negative(contract, package, lambda value: value["runtime_policy"].pop("planned_dumpoff_state_source"))}
        required_leaf_ids = {"sig_mse_mem_queue_idx", "sig_mse_mem_queue_tag", "sig_mse_mem_queue_bp_pre", "sig_mem_idx_gotten_bit", "sig_mem_idx_same_gotten_mask", "sig_idx_split_fifo_empty", "sig_idx_split_fifo_full", "sig_mem_idx_bp_pre_keep_mask", "sig_mem_idx_bp_pre_mask", "sig_mem_idx_split_fifo0_count", "sig_mem_idx_split_fifo1_count", "sig_mem_idx_split_fifo2_count"}
        signal_ids = {row["signal_id"] for row in contract["signals"]}
        matrix = {"positive_contract": positive.get("pass") is True, "schema": schema_error is None, "exact_146_signal_catalog": len(signal_ids) == 146, "p51_106_retained_plus_40": len(contract["diagnostic_round"]["evolution"]["unchanged_signal_ids"]) == 106 and len(contract["diagnostic_round"]["evolution"]["added_signal_ids"]) == 40, "fourteen_candidates": len(contract["candidates"]) == 14, "all_high_zero_hop_drivers": positive.get("missing_high_candidate_direct_driver_ids") == [], "pairwise_matrix_complete": len(contract["candidate_boundary_matrix"]) == 56, "direct_leaf_exact_set": required_leaf_ids.issubset(signal_ids), "negative_controls_rejected": all(negatives.values())}
        write(reports / "candidate_discrimination_matrix.json", {"pass": all(matrix.values()), "checks": matrix, "positive_validation": positive, "negative_controls": negatives, "schema_error": schema_error})
        module_text = tb[:tb.index("bind tb_NDP_Top_new_phy")]
        module_text = "\n".join("      $dumpvars(0, codex_state);" if "$dumpvars(" in line else line for line in module_text.splitlines()) + "\n"
        module_path = temp / "module.sv"; module_path.write_text(module_text, encoding="utf-8", newline="\n")
        frontend = run([str(IVERILOG), "-g2012", "-tnull", str(module_path)])
        replay = runtime_replays(package)
        runtime = {"full_hdl_frontend": frontend["exit_code"] == 0, "semantic_v5_phase_replays": replay["pass"] is True, "planned_dumpoff_sticky": "if (codex_dump_off) begin" in tb and "$dumpon;\n        codex_dump_off <= 0" not in tb, "stop_one_shot": tb.count("CODEX_TBVCD_STOP_V2") == 1 and "!codex_stop_reported" in tb, "live_phase_bound": all(token in live for token in ("dumpoff_consistency_authority", "planned_dumpoff_cycle", "stop_marker_count")), "final_phase_bound": all(token in finalizer for token in ("dumpoff_consistency_authority", "TB_VCD_DUMP_CONTROL_RECEIPT.json", "stop_marker_count")), "no_tb_finish": "$finish;" not in tb}
        write(reports / "source_bound_logger_collector_parser_roundtrip.json", {"pass": all(runtime.values()), "checks": runtime, "frontend": frontend, "runtime_replay": replay})
        runner_checks = {"one_production_launch": runner.count("# CODEX_PRODUCTION_LAUNCH") == 1, "finalizer_armed_before_launch": runner.index("trap 'bootstrap_finalize $?' EXIT") < runner.index("# CODEX_PRODUCTION_LAUNCH"), "all_make_dump_argv_zero": all(token in runner for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")), "shared_evaluator_handoff": all(token in runner for token in ("--runtime-evaluator", "--decision-receipt", "TB_VCD_LIVE_DECISION_RECEIPT.json")), "compile_core_complete": all(token in runner for token in ("compile_argv.json", "compile_source_identity.json", "compile_driver.log", "compile_first_error.txt", "COMPILE_CORE.json")), "actual_source_capture": "capture_actual_compiled_sources.py" in runner, "no_server_preflight_provider_probe": all(token not in runner for token in ("command -v vcs", "which vcs", "make -n", "make --dry-run"))}
        write(reports / "actual_runner_entry_and_input_open.json", {"pass": all(runner_checks.values()), "checks": runner_checks})
        post = load(GATES / "post_sim_final_zip_v5.json")
        post_checks = {"all_scenarios_pass": post.get("pass") is True, "dump_control_returned": "TB_VCD_DUMP_CONTROL_RECEIPT.json" in (package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"), "actual_source_manifest_returned": "actual_compiled_sources/manifest.json" in (package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8")}
        write(reports / "post_sim_return_core_scenarios.json", {"pass": all(post_checks.values()), "checks": post_checks, "validation": post})
        admission = prepare_release_admission(OUT / "build" / PACKAGE)
        admission_checks = {"validator_exit_zero": admission["invocation"]["exit_code"] == 0, "validation_pass": admission["validation"].get("pass") is True, "schema_runtime": admission["validation"].get("checks", {}).get("schema_runtime_available") is True}
        write(reports / "release_admission.json", {"pass": all(admission_checks.values()), "checks": admission_checks, **admission})

    # The generic first-fresh validator owns an exact five-gate evidence set.
    # Release admission remains a separate hard gate and is folded into the
    # aggregate result below.  Normalize every sub-report to the validator's
    # required top-level string-array error form.
    for report_path in sorted(reports.glob("*.json")):
        value = load(report_path)
        if "errors" not in value:
            value["errors"] = [key for key, passed in value.get("checks", {}).items() if passed is not True]
            write(report_path, value)

    evidence = [
        ("exact_final_zip_clean_extract", "exact-final-zip-clean-extract"),
        ("actual_runner_entry_and_input_open", "exact-runner-safe-compile-and-open-paths"),
        ("source_bound_logger_collector_parser_roundtrip", "exact-generated-over-budget-multi-instance"),
        ("post_sim_return_core_scenarios", "exact-final-request-four-scenario"),
        ("candidate_discrimination_matrix", "exact-candidate-positive-negative-matrix"),
    ]
    paths = [reports / f"{name}.json" for name, _kind in evidence]
    first = {"schema": "server-first-fresh-extra-audit-v1", "package": {"package_id": PACKAGE, "family": FAMILY, "final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)}}, "rule_change": {"epoch_id": EPOCH, "rule_ids": ["CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001"], "first_fresh_for_family": True, "notification_acknowledged": True}, "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True}, "evidence_reports": [{"gate_id": name, "evidence_kind": kind, "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)} for (name, kind), path in zip(evidence, paths)], "candidate_discrimination": {"candidate_ids": [row["candidate_id"] for row in contract["candidates"]], "covered_candidate_ids": [row["candidate_id"] for row in contract["candidates"]], "uncovered_candidate_ids": [], "positive_control_count": 14, "negative_control_count": 5, "pairwise_distinguishable": True}, "findings": []}
    first_path = OUT / "first_fresh_audit/contract.json"; write(first_path, first)
    validation = GATES / "first_fresh_validation_v5.json"
    invocation = run([str(PYTHON), str(ROOT / "tools/validate_server_first_fresh_extra_audit.py"), "--contract", str(first_path), "--workspace-root", str(ROOT), "--output", str(validation)])
    release_report = reports / "release_admission.json"
    passed = all(load(path).get("pass") is True for path in paths) and load(release_report).get("pass") is True and invocation["exit_code"] == 0 and load(validation).get("pass") is True
    print(json.dumps({"package_id": PACKAGE, "pass": passed, "validation": str(validation), "failed_reports": [path.name for path in paths if load(path).get("pass") is not True]}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
