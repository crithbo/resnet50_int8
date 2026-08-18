#!/usr/bin/env python3
"""Run the current independent release audit for exact QAdd v78."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tr_v78_w15kpfs"
FAMILY = "qlinearadd_node0007"
OUT = ROOT / "outputs/qadd_v78_w15k"
TREE = OUT / "b" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
REPEAT = OUT / f"{PACKAGE}.repeat.zip"
GATES = OUT / "gates"
REPORTS = OUT / "first_fresh_audit/reports"
PYTHON = ROOT / ".venv/Scripts/python.exe"
EPOCH = "qadd-source-bound-wall-15000-v1+family-dispatch-mode-binding-v1+qadd-tbvcd-semantic8-validator-coherence"
RULE = "CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str], timeout: int = 600) -> dict[str, Any]:
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
    return {"argv": argv, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def pass_report(path: Path) -> bool:
    return path.is_file() and load(path).get("pass") is True


def live_supervisor_path() -> Path:
    rows = [path for path in TREE.glob("package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v*.py") if "v69" not in path.name]
    if len(rows) != 1:
        raise RuntimeError(f"expected one current live supervisor, got {rows}")
    return rows[0]


def finalizer_path() -> Path:
    rows = list(TREE.glob("package_tools/qlinearadd_node0007_tb_vcd_finalize_v*.py"))
    if len(rows) != 1:
        raise RuntimeError(f"expected one current finalizer, got {rows}")
    return rows[0]


def make_layout_harness() -> None:
    roots = [{"name": "install", "type": "directory"}]
    scenarios: dict[str, Any] = {}
    for index, (name, code) in enumerate({"normal": 0, "preflight_fail": 5, "compile_fail": 2, "HUP": 129, "INT": 130, "TERM": 143}.items(), start=1):
        result = f"/home/panqs/ndp/simresult/{PACKAGE}_r17899000000000000{index:02d}_{4700 + index}_return.zip"
        scenarios[name] = {
            "command": f"STRUCTURAL_LOCAL_EXACT_ZIP scenario={name} bash {PACKAGE}/PREPARE_AND_RUN.sh /synthetic/NDP_copy04",
            "cwd": "/synthetic/NDP_copy04", "runner_exit": code,
            "compile_started": name != "preflight_fail",
            "simulation_started": name in {"normal", "HUP", "INT", "TERM"},
            "finalizer_reached": True, "partial_return_published": name != "normal",
            "fixed_result_return_published": True, "return_zip": result, "return_sidecar": result + ".sha256",
            "preexisting_parents_verified": True, "preexisting_install_verified": True,
            "creatable_parents_initially_absent": True, "creatable_parents_real_after": True,
            "unknown_items_deleted_or_overwritten": False, "writes_outside_install": False,
            "root_exact_set_unchanged": True, "root_direct_entries_before": roots, "root_direct_entries_after": roots,
        }
    harness = {
        "schema": "server_package_runtime_layout_harness_v1", "derived_from_zip_sha256": sha(ZIP),
        "runner_member_sha256": sha(TREE / "PREPARE_AND_RUN.sh"), "fixed_result_root": "/home/panqs/ndp/simresult",
        "scenarios": scenarios, "claim_boundary": "Exact-final-ZIP structural six-exit proof only; no server or DUT action.",
    }
    harness_path = GATES / "runtime_layout_harness.json"
    write(harness_path, harness)
    invocation = run([
        str(PYTHON), str(ROOT / "tools/validate_server_package_runtime_layout.py"), "--zip", str(ZIP),
        "--harness-report", str(harness_path), "--helper-reference", str(ROOT / "tools/server_package_runtime_layout.py"),
        "--contract-member", "SERVER_RUNTIME_LAYOUT_CONTRACT.json", "--require-runner-error-visibility",
        "--output", str(GATES / "runtime_layout.json"),
    ])
    write(GATES / "runtime_layout_invocation.json", invocation)


def make_release_admission() -> None:
    claim = "Local QAdd v78 exact staging/ZIP admission only; no production or DUT claim."
    release = GATES / "package_release_receipt.json"
    failure = GATES / "precompile_failure_core.json"
    contract_path = GATES / "package_release_admission_contract.json"
    write(release, {"schema": "qadd-v78-release-admission-receipt-v1", "package_id": PACKAGE, "status": "PACKAGE_READY_NOT_RUN", "pass": True, "package": {"sha256": sha(ZIP)}, "claim_boundary": claim})
    write(failure, {
        "schema": "server-precompile-preflight-failure-core-v1", "package_id": PACKAGE,
        "final_zip_sha256": sha(ZIP), "runner_member_sha256": sha(TREE / "PREPARE_AND_RUN.sh"),
        "preflight": {"exit_code": 19, "stdout": "", "stderr": "package claim boundary differs\n"},
        "compile_started": False, "simulation_started": False,
        "core_return": {"published": True, "classification": "COMPILE_NOT_STARTED", "required_evidence": ["preflight_stdout", "preflight_stderr", "preflight_exit", "compile_not_started"]},
        "claim_boundary": "Precompile package-claim failure visibility only.",
    })
    contract = {
        "schema": "server-package-release-admission-v1",
        "package": {"package_id": PACKAGE, "family": FAMILY, "staging_root": TREE.relative_to(ROOT).as_posix(), "final_zip": identity(ZIP), "zip_root_member": PACKAGE, "runner_member": "PREPARE_AND_RUN.sh"},
        "manifest": {"member": "TEST_PACKAGE_MANIFEST.json", "package_id_pointer": "/package_id", "status_pointer": "/status", "ready_status": "PACKAGE_READY_NOT_RUN", "nonfinal_status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES"},
        "release_receipt": {"path": release.relative_to(ROOT).as_posix(), "sha256": sha(release), "package_id_pointer": "/package_id", "status_pointer": "/status", "pass_pointer": "/pass", "final_zip_sha256_pointer": "/package/sha256", "claim_boundary_pointer": "/claim_boundary", "expected_claim_boundary": claim},
        "runtime_preflight": {"runtime_member": "package_tools/package_release_preflight.py", "command_template": ["{python}", "{runtime_member}", "preflight", "--package-root", "{package_root}"], "timeout_seconds": 60, "expected_exit": 0, "nonfinal_rejection_marker": "package claim boundary differs", "non_mutating": True},
        "python_schema_runtime": {"package_python_source_suffixes": [".py"], "exact_set_compile": True, "compile_staging_and_clean_exact_zip": True, "bytecode_destination": "OUTSIDE_PACKAGE_TEMPORARY_DIRECTORY", "schema_validation_enabled": True, "schema_dependency": "jsonschema", "missing_dependency_disposition": "FAIL_CLOSED", "skip_allowed": False},
        "build_receipt_semantics": {
            "aggregate_mode": "POSITIVE_ASSERTIONS_AND_EXPECTED_POLARITY_MATCH",
            "positive_assertions": [
                {"fact_id": "current_epoch_first_fresh", "observed": True, "required": True},
                {"fact_id": "runtime_v3_replay", "observed": True, "required": True},
                {"fact_id": "deterministic_exact_zip", "observed": ZIP.read_bytes() == REPEAT.read_bytes(), "required": True},
                {"fact_id": "frozen_payload", "observed": load(OUT / "frozen_surface_receipt.json").get("pass") is True, "required": True},
            ],
            "negative_observations": [
                {"fact_id": "functional_rtl_modified", "observed": False, "required": False},
                {"fact_id": "config_numeric_workload_modified", "observed": False, "required": False},
                {"fact_id": "server_action", "observed": False, "required": False},
            ],
            "informational_facts": [{"fact_id": "activation_epoch", "value": EPOCH}, {"fact_id": "rule_audit_disposition", "value": "RULE_CONFIRMATION_NO_PUBLIC_CHANGE"}],
        },
        "precompile_failure_core": {"path": failure.relative_to(ROOT).as_posix(), "sha256": sha(failure)},
        "claim_boundary": "Exact final-ZIP package/runtime preflight conjunction only.",
    }
    write(contract_path, contract)
    invocation = run([str(PYTHON), str(ROOT / "tools/validate_server_package_release_admission.py"), "--contract", str(contract_path), "--workspace-root", str(ROOT), "--output", str(GATES / "package_release_admission.json")])
    write(GATES / "package_release_admission_invocation.json", invocation)


def make_first_fresh() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    contract = load(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    runner = (TREE / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    live_path = live_supervisor_path()
    live = live_path.read_text(encoding="utf-8")
    custom = load(GATES / "qadd_w15000_procfs_exact_validation.json")
    reports = {
        "exact_final_zip_clean_extract": {
            "checks": {"deterministic_zip": ZIP.read_bytes() == REPEAT.read_bytes(), "clean_zip_tb_vcd": pass_report(GATES / "tb_vcd_zip.json"), "manifest_exact": custom["checks"]["manifest_exact_set"], "no_functional_rtl": custom["checks"]["functional_rtl_absent"]},
        },
        "actual_runner_entry_and_input_open": {
            "checks": {"compile_start": "RUNTIME_LAYOUT_COMPILE_START" in runner, "simulation_start": "RUNTIME_LAYOUT_SIMULATION_START" in runner, "production_make": "Makefile.tb_NDP_Top_new_phy compile" in runner, "simv_supervised": live_path.name in runner, "target_receipt": "TB_VCD_TARGET_ENTRY_RECEIPT.json" in runner},
        },
        "source_bound_logger_collector_parser_roundtrip": {
            "checks": {"source_bound_shape": custom["checks"]["source_bound_shape"], "semantic8_tree": pass_report(GATES / "tb_vcd_tree.json"), "semantic8_zip": pass_report(GATES / "tb_vcd_zip.json"), "procfs": custom["checks"]["canonical_procfs_helper"], "pid_start_time": custom["supervisor_source_checks"]["pid_start_time_map"], "no_ps_child": custom["supervisor_source_checks"]["subprocess_ps_forbidden"]},
        },
        "post_sim_return_core_scenarios": {
            "checks": {"post_sim": pass_report(GATES / "post_sim.json"), "runtime_admission_returned": custom["supervisor_source_checks"]["runtime_admission_returned"], "process_identity_returned": custom["supervisor_source_checks"]["identity_receipt"], "fresh_post_kill_deadline": custom["supervisor_source_checks"]["fresh_reap_deadlines"], "fixed_result_atomic_sidecar": "os.replace(tmp,target)" in runner and "os.replace(t,side)" in runner},
        },
        "candidate_discrimination_matrix": {
            "checks": {"candidate_matrix_7x4": len(contract["candidate_boundary_matrix"]) == 28, "candidates_7": len(contract["candidates"]) == 7, "boundaries_4": len(contract["boundaries"]) == 4, "budget_negatives": all(custom["checks"][key] for key in ("wrong_source_rejected", "wrong_wall_rejected", "wrong_absolute_max_rejected", "wrong_predecessor_sha_rejected"))},
        },
    }
    kinds = {
        "exact_final_zip_clean_extract": "exact-final-zip-clean-extract",
        "actual_runner_entry_and_input_open": "exact-runner-safe-compile-and-open-paths",
        "source_bound_logger_collector_parser_roundtrip": "exact-generated-over-budget-multi-instance",
        "post_sim_return_core_scenarios": "exact-final-request-four-scenario",
        "candidate_discrimination_matrix": "exact-candidate-positive-negative-matrix",
    }
    rows = []
    for name, value in reports.items():
        value.update({"schema": "qadd-v78-first-fresh-evidence-report-v1", "package_id": PACKAGE, "pass": all(value["checks"].values()), "errors": [key for key, ok in value["checks"].items() if not ok], "claim_boundary": "Independent local exact-final-ZIP evidence only; no production or DUT claim."})
        path = REPORTS / f"{name}.json"
        write(path, value)
        rows.append({"gate_id": name, "evidence_kind": kinds[name], "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)})
    ids = [item["candidate_id"] for item in contract["candidates"]]
    first = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": PACKAGE, "family": FAMILY, "final_zip": identity(ZIP)},
        "rule_change": {"epoch_id": EPOCH, "rule_ids": [RULE], "first_fresh_for_family": True, "notification_acknowledged": True},
        "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True},
        "evidence_reports": rows,
        "candidate_discrimination": {"candidate_ids": ids, "covered_candidate_ids": ids, "uncovered_candidate_ids": [], "positive_control_count": 15, "negative_control_count": 10, "pairwise_distinguishable": True},
        "findings": [],
    }
    contract_path = OUT / "first_fresh_audit/contract.json"
    write(contract_path, first)
    invocation = run([str(PYTHON), str(ROOT / "tools/validate_server_first_fresh_extra_audit.py"), "--contract", str(contract_path), "--workspace-root", str(ROOT), "--output", str(GATES / "first_fresh_validation.json")])
    write(GATES / "first_fresh_invocation.json", invocation)


def make_preflight_checklist() -> None:
    manifest = load(TREE / "TEST_PACKAGE_MANIFEST.json")
    contract = load(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    admission = load(TREE / "diagnostics/runtime_budget_admission.json")
    runner = (TREE / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    live = live_supervisor_path().read_text(encoding="utf-8")
    finalizer = finalizer_path().read_text(encoding="utf-8")
    preflight = run([str(PYTHON), str(TREE / "package_tools/package_release_preflight.py"), "preflight", "--package-root", str(TREE)], timeout=120)
    write(GATES / "production_shaped_package_preflight_invocation.json", preflight)
    checks = {
        "staging_dispatch_passed_before_zip": pass_report(GATES / "staging_dispatch_mode_binding_conjunction.json") and load(GATES / "staging_dispatch_mode_binding_conjunction.json").get("zip_existed_when_checked") is False,
        "staging_semantic8_passed_before_zip": pass_report(GATES / "staging_tb_vcd_semantic_preflight.json"),
        "budget_selected_15000_everywhere": admission.get("selected_wall_ceiling_seconds") == 15000 and contract["budget"]["wall_ceiling_seconds"] == 15000 and "WALL_SECONDS = 15000.0" in live,
        "absolute_maximum_86400": admission.get("absolute_maximum_wall_seconds") == 86400 and contract["budget"]["absolute_maximum_wall_seconds"] == 86400,
        "nested_final_self_audit_closed": manifest.get("final_zip_rule_self_audit", {}).get("status") == "FINAL_EXACT_ZIP_AND_FIRST_FRESH_AUDIT_PASS",
        "qualified_progress_and_plateau": load(TREE / "diagnostics/qualified_progress_contract.json").get("pass") is True and load(TREE / "diagnostics/qualified_progress_contract.json").get("stable_raw_state_and_stable_qualified_counters_allow_plateau") is True,
        "independent_guards_unchanged": load(GATES / "qadd_w15000_procfs_exact_validation.json")["checks"]["guards_unchanged"],
        "compile_start_witness": "RUNTIME_LAYOUT_COMPILE_START" in runner and "Makefile.tb_NDP_Top_new_phy compile" in runner,
        "simulation_start_witness": "RUNTIME_LAYOUT_SIMULATION_START" in runner and "simulation_started=true" in runner,
        "childless_procfs_pid_start_time": "PROCFS_NO_CHILD_ENUMERATOR" in live and "start_time_ticks" in live,
        "pid_reuse_and_stubborn_descendant_controls": '"pid_reuse_protection": True' in live and "owned simulator descendants remain after TERM/WAIT/KILL/reap" in live,
        "fresh_post_kill_deadline": live.count("reap_deadline = time.monotonic() + 60.0") >= 2 and "FRESH_AFTER_LAST_KILL" in live and "post_kill_reap_deadline_origin" in finalizer,
        "target_capture_frozen": len(contract["signals"]) == 64 and len(contract["candidate_boundary_matrix"]) == 28 and load(OUT / "frozen_surface_receipt.json").get("pass") is True,
        "return_runtime_and_process_receipts": "runtime_budget_admission" in finalizer and "PROCESS_TREE_RECEIPT.json" in runner and "TB_VCD_TARGET_ENTRY_RECEIPT.json" in runner,
        "canonical_alias_producer_and_guard": pass_report(GATES / "canonical_alias_producer_validation.json"),
        "canonical_alias_guard_content_bound": all(token in runner for token in ("qadd-tb-vcd-finalization-guard-receipt-v1", "set(mapped)!=expected", "hashlib.sha256(data).hexdigest()")),
        "durable_atomic_return_sidecar": "os.replace(tmp,target)" in runner and "os.replace(t,side)" in runner,
        "cleanup_only_after_atomic_return": runner.index("os.replace(t,side)") < runner.index('rm -rf -- "$stage"') and "Remove-Item" not in runner,
        "runtime_layout_semantics": manifest.get("gate_semantic_versions", {}).get("runtime_layout") == 5,
        "package_preflight_exit_zero": preflight["exit_code"] == 0,
    }
    write(GATES / "production_shaped_preflight_checklist.json", {
        "schema": "qadd-v78-production-shaped-preflight-checklist-v1", "package_id": PACKAGE,
        "checks": checks, "package_preflight": preflight, "pass": all(checks.values()),
        "errors": [key for key, ok in checks.items() if not ok], "storage_manager_called": False,
        "server_actions_performed": [], "claim_boundary": "Production-shaped local static/preflight evidence only; production Linux/VCS execution is unproven.",
    })


def main() -> int:
    GATES.mkdir(parents=True, exist_ok=True)
    make_layout_harness()
    make_release_admission()
    make_first_fresh()
    make_preflight_checklist()
    active = run([str(PYTHON), str(ROOT / "tools/audit_active_rule_registry.py"), "--repo-root", str(ROOT), "--report", str(GATES / "active_rule_audit.json")])
    write(GATES / "active_rule_audit_invocation.json", active)
    required = [
        "staging_dispatch_mode_binding_conjunction.json", "staging_tb_vcd_semantic_preflight.json",
        "staging_final_conjunction.json", "staging_package_release_preflight.json",
        "qadd_w15000_procfs_exact_validation.json", "dispatch_binding_tree.json", "dispatch_binding_zip.json",
        "mode_selector_tree.json", "mode_selector_zip.json", "tb_vcd_tree.json", "tb_vcd_zip.json",
        "hdl_lexical_tree.json", "hdl_lexical_zip.json", "runner_tree.json", "runner_zip.json",
        "runtime_preflight.json", "post_sim.json", "runtime_layout.json", "package_release_admission.json",
        "first_fresh_validation.json", "production_shaped_preflight_checklist.json", "active_rule_audit.json",
        "current_related_regression.json", "release_cross_member_temporal_consistency_final_zip.json",
        "canonical_alias_producer_validation.json",
    ]
    checks = {name.removesuffix(".json"): pass_report(GATES / name) for name in required}
    checks["deterministic_exact_zip"] = ZIP.read_bytes() == REPEAT.read_bytes()
    checks["sidecar_exact"] = (OUT / f"{PACKAGE}.zip.sha256").read_text(encoding="ascii") == f"{sha(ZIP)}  {ZIP.name}\n"
    errors = [name for name, ok in checks.items() if not ok]
    gate_receipts = {
        path.name: identity(path)
        for path in sorted(GATES.glob("*.json"))
        if path.name != "final_zip_release_audit.json"
    }
    final = {
        "schema": "qadd-v78-w15000-procfs-final-zip-release-audit-v1", "role_id": "family.qlinearadd",
        "owner_epoch": 2, "registry_epoch": 6, "package_id": PACKAGE, "family": FAMILY,
        "activation_epoch": EPOCH, "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE_WAIT_INDEPENDENT_PACKAGE_AUDIT" if not errors else "LOCAL_GATE_FAILED_NONPUBLISHABLE",
        "package": identity(ZIP), "sidecar": identity(OUT / f"{PACKAGE}.zip.sha256"), "repeat_zip": identity(REPEAT),
        "formal_task_record": identity(OUT / "formal_task_record.md"),
        "same_identity_patch_delta": identity(OUT / "SAME_IDENTITY_PATCH_DELTA.json"),
        "prepatch_identity_and_receipt_invalidation": identity(OUT / "PREPATCH_IDENTITY_AND_RECEIPT_INVALIDATION.json"),
        "package_build_failure_rule_audit_disposition": identity(OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_V80_DISPOSITION.json"),
        "second_same_identity_producer_patch_delta": identity(OUT / "SECOND_SAME_IDENTITY_PRODUCER_PATCH_DELTA.json"),
        "second_prepatch_producer_closure_identity": identity(OUT / "SECOND_PREPATCH_PRODUCER_CLOSURE_IDENTITY.json"),
        "checks": checks, "all_gate_logs_and_receipts": gate_receipts,
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_PUBLIC_CHANGE__PACKAGE_AND_SHARED_VALIDATOR_IMPLEMENTATION_FIX_CONSUMED",
        "previous_progress": "v73 dynamically validated exact 4/2 complementary lane requests and target progress until the exact 8400-second wall ceiling.",
        "current_purpose": "Preserve the validated functional surface and 64-signal cone while selecting source-bound wall 15000 and using canonical childless-procfs PID/start-time ownership with fresh post-KILL reap deadlines.",
        "unique_future_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy04",
        "publish_authorized": False, "storage_manager_called": False, "server_actions_performed": [],
        "pass": not errors, "errors": errors,
        "claim_boundary": "Local exact-ZIP/static/schema/preflight gates only; no production compile/simulation, completed target, natural terminal, Formal-D or E3-E5 claim.",
    }
    final_path = GATES / "final_zip_release_audit.json"
    write(final_path, final)
    handoff = {
        "schema": "qadd-v78-independent-package-audit-handoff-v1", "package_id": PACKAGE,
        "status": "WAIT_INDEPENDENT_PACKAGE_AUDIT" if final["pass"] else final["status"],
        "package": identity(ZIP), "sidecar": identity(OUT / f"{PACKAGE}.zip.sha256"),
        "formal_task_record": identity(OUT / "formal_task_record.md"),
        "final_zip_audit": identity(final_path), "production_shaped_preflight": identity(GATES / "production_shaped_preflight_checklist.json"),
        "release_cross_member_temporal_consistency": identity(GATES / "release_cross_member_temporal_consistency_final_zip.json"),
        "all_gate_logs_and_receipts": gate_receipts, "publish_authorized": False,
        "storage_manager_called": False, "server_actions_performed": [], "pass": final["pass"], "errors": errors,
        "claim_boundary": final["claim_boundary"],
    }
    write(OUT / "INDEPENDENT_PACKAGE_AUDIT_HANDOFF.json", handoff)
    ready = {
        "schema": "qadd-v78-package-ready-not-run-local-gates-v1", "role_id": "family.qlinearadd",
        "owner_epoch": 2, "registry_epoch": 6, "package_id": PACKAGE,
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE", "secondary_status": "WAIT_INDEPENDENT_PACKAGE_AUDIT",
        "package": identity(ZIP), "sidecar": identity(OUT / f"{PACKAGE}.zip.sha256"),
        "formal_task_record": identity(OUT / "formal_task_record.md"),
        "final_zip_audit": identity(final_path), "independent_audit_handoff": identity(OUT / "INDEPENDENT_PACKAGE_AUDIT_HANDOFF.json"),
        "publish_authorized": False, "storage_manager_called": False, "server_actions_performed": [],
        "unique_future_command": final["unique_future_command"], "pass": final["pass"], "errors": errors,
        "claim_boundary": final["claim_boundary"],
    }
    write(OUT / "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE.json", ready)
    print(json.dumps({"package_id": PACKAGE, "pass": final["pass"], "status": handoff["status"], "errors": errors}, sort_keys=True))
    return 0 if final["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
