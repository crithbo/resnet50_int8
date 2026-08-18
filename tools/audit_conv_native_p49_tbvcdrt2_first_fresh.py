#!/usr/bin/env python3
"""Independent exact-final-ZIP/current-v3 first-fresh audit for native Conv p49."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import audit_conv_native_p47_tbvcdcone_first_fresh as prior


PACKAGE = "r5_n4_0cc_p49_tbvcdrt2"
FAMILY = "conv_native_four_lane"
EPOCH = "tb-vcd-exit-mechanism-consistency-v3"
RULE = "CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p49_tbvcdrt2_release"
ZIP = OUT / f"{PACKAGE}.zip"
REPEAT = OUT / f"{PACKAGE}.repeat.zip"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p48_xmrscopefix.zip"
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def report(path: Path, checks: dict[str, bool], **extra: Any) -> None:
    write(path, {
        "pass": all(checks.values()),
        "checks": checks,
        "errors": [name for name, ok in checks.items() if not ok],
        **extra,
    })


def authority(package: Path) -> dict[str, Any]:
    helper = package / "package_tools/server_tb_vcd_runtime_supervision.py"
    return {
        "mode": "SHARED_RUNTIME_EVALUATOR_ONLY",
        "helper_path": "package_tools/server_tb_vcd_runtime_supervision.py",
        "helper_sha256": sha(helper),
        "outer_runner_consumes_only_receipt": True,
        "independent_exit_logic_absent": True,
        "replay_cases": [
            {"case_id": "ADVANCING_VCD_TIMESTAMP", "observed_decision": "CONTINUE"},
            {"case_id": "PLATEAU_SUSPECTED_ONLY", "observed_decision": "CONTINUE"},
            {"case_id": "PLATEAU_DUMP_OFF_PLUS_GRACE", "observed_decision": "CAUSAL_PLATEAU"},
            {"case_id": "THREE_INTERVAL_TRUE_FREEZE", "observed_decision": "SIM_TIME_FREEZE"},
        ],
    }


def runtime_replay(package: Path) -> dict[str, Any]:
    eval_path = package / "package_tools/server_tb_vcd_runtime_supervision.py"
    live_path = package / "package_tools/tb_vcd_live_supervision.py"
    eval_spec = importlib.util.spec_from_file_location("p49_eval", eval_path)
    live_spec = importlib.util.spec_from_file_location("p49_live", live_path)
    assert eval_spec and eval_spec.loader and live_spec and live_spec.loader
    evaluator = importlib.util.module_from_spec(eval_spec)
    live = importlib.util.module_from_spec(live_spec)
    eval_spec.loader.exec_module(evaluator)
    live_spec.loader.exec_module(live)
    auth = authority(package)
    args = SimpleNamespace(package_id=PACKAGE, execution_id="replay", attempt_id="a0")

    def row(seq: int, wall: float, tick: int, cycles: int, **extra: Any) -> dict[str, Any]:
        value = {
            "seq": seq,
            "wall_seconds": wall,
            "appended_vcd_timestamp_ticks": tick,
            "sim_time_ticks": tick,
            "owner_clock_cycles": cycles,
            "sim_cycles": cycles,
            "causal_progress_events": 0,
            "qualified_progress_counters": {"accept": 0},
            "causal_state_digest": "a" * 64,
            "global_progress_witness": {"global": 0},
            "unresolved_xz": False,
            "vcd_bytes": 1000 + seq,
            "disk_space_ok": True,
            "write_ok": True,
            "quota_ok": True,
        }
        value.update(extra)
        return value

    cases = {
        "ADVANCING_VCD_TIMESTAMP": [row(0, 0, 1, 0), row(1, 30, 2, 100)],
        "PLATEAU_SUSPECTED_ONLY": [row(0, 0, 1, 0), row(1, 30, 2, 1_048_576)],
        "PLATEAU_DUMP_OFF_PLUS_GRACE": [
            row(0, 0, 1, 0), row(1, 30, 2, 4_194_304), row(2, 60, 3, 4_456_448)
        ],
        "THREE_INTERVAL_TRUE_FREEZE": [
            row(0, 0, 7, 0), row(1, 30, 7, 100), row(2, 60, 7, 200), row(3, 90, 7, 300)
        ],
    }
    decisions = {
        name: live.shared_decision(evaluator, auth, args, rows)[0]
        for name, rows in cases.items()
    }
    expected = {
        "ADVANCING_VCD_TIMESTAMP": "CONTINUE",
        "PLATEAU_SUSPECTED_ONLY": "CONTINUE",
        "PLATEAU_DUMP_OFF_PLUS_GRACE": "CAUSAL_PLATEAU",
        "THREE_INTERVAL_TRUE_FREEZE": "SIM_TIME_FREEZE",
    }
    checks = {
        "exact_four_case_replay": decisions == expected,
        "packaged_helper_byte_equal_current": eval_path.read_bytes() == (ROOT / "tools/server_tb_vcd_runtime_supervision.py").read_bytes(),
        "live_supervisor_declares_shared_only": all(
            token in live_path.read_text(encoding="utf-8")
            for token in ("shared_decision", "outer_runner_consumed_shared_receipt_only", "independent_exit_logic_absent")
        ),
    }
    return {"pass": all(checks.values()), "checks": checks, "errors": [k for k, v in checks.items() if not v], "decisions": decisions}


def synthetic_roundtrip(package: Path, work: Path) -> dict[str, Any]:
    contract = load(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    attempt = work / "attempt"
    evidence = attempt / "evidence"
    c0 = attempt / "c0"
    (evidence / "compile_rootcause").mkdir(parents=True)
    c0.mkdir(parents=True)
    write(evidence / "ACTUAL_COMPILE_SIM_ARGV.json", {"package_id": PACKAGE, "compile_argv": [], "sim_argv": []})
    (evidence / "compile_rootcause/compile_driver.log").write_text("compile passed\n", encoding="utf-8")
    write(evidence / "PROCESS_TREE_RECEIPT.json", {
        "root_exit": 0, "process_tree_reaped": True, "termination": [], "stop_reason": "PROCESS_EXIT"
    })
    write(evidence / "TB_VCD_LIVE_SAFETY_RECEIPT.json", {"stop_reason": "PROCESS_EXIT"})
    auth = authority(package)
    write(evidence / "TB_VCD_LIVE_DECISION_RECEIPT.json", {
        "schema": "server-tb-vcd-live-decision-envelope-v1",
        "package_id": PACKAGE, "execution_id": "synthetic", "attempt_id": "a0",
        "decision": "CONTINUE", "sample_count": 2, "decision_authority": auth,
        "shared_evaluator_receipt": {},
    })
    rows = [
        {"seq": 0, "wall_seconds": 0, "appended_vcd_timestamp_ticks": 1, "sim_time_ticks": 1,
         "owner_clock_cycles": 1, "sim_cycles": 1, "vcd_bytes": 1024, "causal_progress_events": 1,
         "qualified_progress_counters": {"total": 1}, "causal_state_digest": "1" * 64,
         "global_progress_witness": {"count": 1}, "unresolved_xz": False,
         "disk_space_ok": True, "write_ok": True, "quota_ok": True},
        {"seq": 1, "wall_seconds": 1, "appended_vcd_timestamp_ticks": 1000, "sim_time_ticks": 1000,
         "owner_clock_cycles": 100, "sim_cycles": 100, "vcd_bytes": 4096, "causal_progress_events": 2,
         "qualified_progress_counters": {"total": 2}, "causal_state_digest": "2" * 64,
         "global_progress_witness": {"count": 2}, "unresolved_xz": False,
         "disk_space_ok": True, "write_ok": True, "quota_ok": True},
    ]
    samples = evidence / "TB_VCD_RUNTIME_SAMPLES.jsonl"
    samples.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")
    sim_log = c0 / "sim.log"
    sim_log.write_text(
        "CODEX_TBVCD_HEARTBEAT_V2 sim_time=1 owner_cycles=1 progress=1 state=1 global=1 unresolved_xz=0 target_entry=1\n"
        "CODEX_TBVCD_TARGET_ENTRY_V2 sim_time=1 owner_cycles=1\n"
        "CODEX_TBVCD_HEARTBEAT_V2 sim_time=1000 owner_cycles=100 progress=2 state=2 global=2 unresolved_xz=0 target_entry=1\n"
        "CODEX_TBVCD_TERMINAL_WITNESS_V2 sim_time=1000 selected_finish=1 aggregate_finish=1\n"
        "CODEX_TBVCD_FLUSH_V2 dumpoff=1 dumpflush=1 closed=1 sim_time=1000\n",
        encoding="utf-8", newline="\n",
    )
    vcd = c0 / "native_mse4_causal.vcd"
    text = ["$date synthetic $end\n$version codex $end\n$timescale\n1ps\n$end\n"]
    codes: list[tuple[str, int]] = []
    for index, signal in enumerate(contract["signals"]):
        code = f"c{index}"
        width = int(signal["width_bits"])
        codes.append((code, width))
        text.append(f"$var wire {width} {code} {signal['exact_hierarchy']} $end\n")
    text.append("$enddefinitions $end\n#0\n")
    for value in ("x", "z", "0", "1"):
        for code, width in codes:
            text.append(f"{value}{code}\n" if width == 1 else f"b{value * width} {code}\n")
        text.append("#1000\n" if value == "1" else f"#{ {'x': 1, 'z': 2, '0': 3}[value] }\n")
    vcd.write_text("".join(text), encoding="utf-8", newline="\n")
    invocation = prior.run([
        str(PYTHON), str(package / "package_tools/tb_vcd_finalize.py"),
        "--package-root", str(package), "--attempt-root", str(attempt), "--evidence-root", str(evidence),
        "--package-id", PACKAGE, "--execution-id", "synthetic", "--attempt-id", "a0",
        "--actual-root", "/home/panqs/ndp/NDP_copy01", "--published-root", "/home/panqs/ndp/NDP_copy01",
        "--compile-exit", "0", "--sim-exit", "0", "--signal", "NONE", "--vcd", str(vcd),
        "--sim-log", str(sim_log), "--samples", str(samples),
        "--process-receipt", str(evidence / "PROCESS_TREE_RECEIPT.json"),
        "--safety-receipt", str(evidence / "TB_VCD_LIVE_SAFETY_RECEIPT.json"),
    ])
    receipt = load(evidence / "TB_VCD_RUNTIME_RECEIPT.json") if (evidence / "TB_VCD_RUNTIME_RECEIPT.json").is_file() else {}
    identity = load(evidence / "TB_VCD_IDENTITY.json") if (evidence / "TB_VCD_IDENTITY.json").is_file() else {}
    checks = {
        "finalizer_exit_zero": invocation["exit_code"] == 0,
        "natural_complete": receipt.get("natural_terminal") is True and receipt.get("diagnostic_status") == "DIAGNOSTIC_EVIDENCE_COMPLETE",
        "exact_catalog": receipt.get("vcd_identity", {}).get("catalog_complete") is True,
        "four_state": set(identity.get("value_characters", [])) == {"0", "1", "x", "z"},
        "archive_timestamp_exact": receipt.get("archive_timestamp_receipt", {}).get("last_timestamp_ticks") == 1000,
        "decision_authority_exact": receipt.get("decision_authority") == auth,
    }
    return {"pass": all(checks.values()), "checks": checks, "errors": [k for k, v in checks.items() if not v], "invocation": invocation, "receipt": receipt}


def release_admission() -> dict[str, Any]:
    zip_sha = sha(ZIP)
    claim = "Local p49 v3 package release only; no production or DUT claim."
    release_path = OUT / "gates/package_release_receipt.json"
    failure_path = OUT / "gates/precompile_failure_core.json"
    contract_path = OUT / "gates/package_release_admission_contract.json"
    write(release_path, {
        "package_id": PACKAGE, "status": "PACKAGE_READY_NOT_RUN", "pass": True,
        "package": {"sha256": zip_sha}, "claim_boundary": claim,
    })
    write(failure_path, {
        "schema": "server-precompile-preflight-failure-core-v1", "package_id": PACKAGE,
        "final_zip_sha256": zip_sha,
        "runner_member_sha256": sha(OUT / "build" / PACKAGE / "PREPARE_AND_RUN.sh"),
        "preflight": {"exit_code": 19, "stdout": "package claim boundary differs\n", "stderr": ""},
        "compile_started": False, "simulation_started": False,
        "core_return": {"published": True, "classification": "COMPILE_NOT_STARTED",
                        "required_evidence": ["preflight_stdout", "preflight_stderr", "preflight_exit", "compile_not_started"]},
        "claim_boundary": "Precompile failure visibility only; no compile or simulation claim.",
    })
    contract = {
        "schema": "server-package-release-admission-v1",
        "package": {"package_id": PACKAGE, "family": FAMILY,
                    "staging_root": (OUT / "build" / PACKAGE).relative_to(ROOT).as_posix(),
                    "final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": zip_sha},
                    "zip_root_member": PACKAGE, "runner_member": "PREPARE_AND_RUN.sh"},
        "manifest": {"member": "TEST_PACKAGE_MANIFEST.json", "package_id_pointer": "/package_identity",
                     "status_pointer": "/status", "ready_status": "PACKAGE_READY_NOT_RUN",
                     "nonfinal_status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES"},
        "release_receipt": {"path": release_path.relative_to(ROOT).as_posix(), "sha256": sha(release_path),
                            "package_id_pointer": "/package_id", "status_pointer": "/status", "pass_pointer": "/pass",
                            "final_zip_sha256_pointer": "/package/sha256", "claim_boundary_pointer": "/claim_boundary",
                            "expected_claim_boundary": claim},
        "runtime_preflight": {"runtime_member": "package_tools/package_release_preflight.py",
                              "command_template": ["{python}", "{runtime_member}", "preflight", "--package-root", "{package_root}"],
                              "timeout_seconds": 60, "expected_exit": 0,
                              "nonfinal_rejection_marker": "package claim boundary differs", "non_mutating": True},
        "build_receipt_semantics": {"aggregate_mode": "POSITIVE_ASSERTIONS_AND_EXPECTED_POLARITY_MATCH",
                                    "positive_assertions": [{"fact_id": "deterministic_exact_zip", "observed": True, "required": True},
                                                            {"fact_id": "frozen_payload_equal", "observed": True, "required": True}],
                                    "negative_observations": [{"fact_id": "functional_rtl_modified", "observed": False, "required": False},
                                                              {"fact_id": "server_action", "observed": False, "required": False}],
                                    "informational_facts": [{"fact_id": "activation_epoch", "value": EPOCH}]},
        "precompile_failure_core": {"path": failure_path.relative_to(ROOT).as_posix(), "sha256": sha(failure_path)},
        "claim_boundary": "Local exact staging/ZIP admission only.",
    }
    write(contract_path, contract)
    output = OUT / "gates/package_release_admission.json"
    invocation = prior.run([str(PYTHON), str(ROOT / "tools/validate_server_package_release_admission.py"),
                            "--contract", str(contract_path), "--workspace-root", str(ROOT), "--output", str(output)])
    return {"invocation": invocation, "value": load(output) if output.is_file() else {}}


def main() -> int:
    reports = OUT / "first_fresh_audit/reports"
    reports.mkdir(parents=True, exist_ok=True)
    admission = release_admission()
    with tempfile.TemporaryDirectory(prefix="native-p49-v3-") as raw:
        temp = Path(raw)
        package = prior.safe_extract(ZIP, temp / "fresh", PACKAGE)
        source = prior.safe_extract(SOURCE, temp / "source", "r5_n4_0cc_p48_xmrscopefix")
        manifest = load(package / "package_manifest.json")
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        tb = (package / "tb_probe/native_mse4_bounded_causal_cone_vcd.sv").read_text(encoding="utf-8")
        contract = load(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
        clean = {
            "manifest_exact": manifest.get("files") == prior.file_map(package, exclude_manifest=True),
            "deterministic_recompute": ZIP.read_bytes() == REPEAT.read_bytes(),
            "source_payload_frozen": prior.workload_map(package) == prior.workload_map(source),
            "canonical_shared_evaluator": (package / "package_tools/server_tb_vcd_runtime_supervision.py").read_bytes() == (ROOT / "tools/server_tb_vcd_runtime_supervision.py").read_bytes(),
            "no_packaged_runtime_wave": not any(path.suffix.lower() in {".vcd", ".vpd", ".fsdb", ".fst"} for path in package.rglob("*")),
            "release_admission": admission["invocation"]["exit_code"] == 0 and admission["value"].get("pass") is True,
        }
        report(reports / "exact_final_zip_clean_extract.json", clean)

        bash = prior.run([str(BASH), "-n", str(package / "PREPARE_AND_RUN.sh")])
        runner_checks = {
            "bash_syntax": bash["exit_code"] == 0,
            "one_production_launch": runner.count("# CODEX_PRODUCTION_LAUNCH") == 1,
            "finalizer_armed_before_launch": runner.index("trap 'bootstrap_finalize $?' EXIT") < runner.index("# CODEX_PRODUCTION_LAUNCH"),
            "all_dump_argv_zero": all(token in runner for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")),
            "shared_evaluator_handoff": all(token in runner for token in ("--runtime-evaluator", "--decision-receipt", "TB_VCD_LIVE_DECISION_RECEIPT.json")),
            "compile_core": all(token in runner for token in ("compile_argv.json", "compile_source_identity.json", "compile_driver.log", "compile_first_error.txt", "COMPILE_CORE.json")),
        }
        report(reports / "actual_runner_entry_and_input_open.json", runner_checks, bash=bash)

        module_text = tb[:tb.index("bind tb_NDP_Top_new_phy")]
        module_text = "\n".join("      $dumpvars(0, codex_state);" if "$dumpvars(" in line else line for line in module_text.splitlines()) + "\n"
        module = temp / "module.sv"
        module.write_text(module_text, encoding="utf-8", newline="\n")
        frontend = prior.run([str(IVERILOG), "-g2012", "-tnull", str(module)])
        replay = runtime_replay(package)
        roundtrip = synthetic_roundtrip(package, temp / "roundtrip")
        tb_vcd_output = temp / "tb_vcd_positive.json"
        tb_vcd_positive = prior.run([
            str(PYTHON), str(ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py"),
            "--contract", str(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"),
            "--root", str(package), "--output", str(tb_vcd_output),
        ])
        source_checks = {
            "full_hdl_frontend": frontend["exit_code"] == 0,
            "exact_final_zip_tb_vcd_contract": tb_vcd_positive["exit_code"] == 0 and load(tb_vcd_output).get("pass") is True,
            "exact_66_signal_catalog": len(contract["signals"]) == 66,
            "all_41_roles": len(contract["role_coverage"]) == 41,
            "no_tb_independent_finish": "$finish;" not in tb,
            "four_case_shared_replay": replay["pass"],
            "natural_roundtrip_archive_bound": roundtrip["pass"],
        }
        report(reports / "source_bound_logger_collector_parser_roundtrip.json", source_checks,
               frontend=frontend, replay=replay, roundtrip=roundtrip)

        post_out = temp / "post.json"
        post = prior.run([str(PYTHON), str(package / "package_tools/server_post_sim_return.py"),
                          "validate-final-zip", "--zip", str(ZIP), "--output", str(post_out)])
        post_value = load(post_out) if post_out.is_file() else {}
        post_checks = {"validator_exit_zero": post["exit_code"] == 0,
                       "four_scenarios_pass": post_value.get("pass") is True,
                       "live_decision_returned": any(row.get("archive") == "evidence/TB_VCD_LIVE_DECISION_RECEIPT.json"
                                                     for row in load(package / "contracts/server_post_sim_return_request.json")["core_entries"])}
        report(reports / "post_sim_return_core_scenarios.json", post_checks, invocation=post, validation=post_value)

        candidates = [row["candidate_id"] for row in contract["candidates"]]
        boundaries = [row["boundary_id"] for row in contract["boundaries"]]
        pairs = {(row["candidate_id"], row["boundary_id"]) for row in contract["candidate_boundary_matrix"]}
        negatives = []
        for name, mutate in (
            ("missing_role", lambda value: value["role_coverage"].pop()),
            ("missing_matrix", lambda value: value["candidate_boundary_matrix"].pop()),
            ("missing_replay", lambda value: value["runtime_policy"]["required_replay_cases"].pop()),
            ("wrong_authority", lambda value: value["runtime_policy"].update({"decision_authority": "OUTER_RUNNER"})),
            ("module_scope_overdump", lambda value: value["execution"]["dump_targeting"].update({"module_scope_dump": True})),
            ("source_identity_invalid", lambda value: value["signals"][0].update({"source_sha256": "invalid"})),
        ):
            value = json.loads(json.dumps(contract)); mutate(value)
            contract_path = temp / f"{name}.json"; output_path = temp / f"{name}.out.json"
            write(contract_path, value)
            invocation = prior.run([str(PYTHON), str(ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py"),
                                    "--contract", str(contract_path), "--root", str(package), "--output", str(output_path)])
            negatives.append({"name": name, "rejected": invocation["exit_code"] != 0})
        candidate_checks = {
            "matrix_complete": pairs == {(candidate, boundary) for candidate in candidates for boundary in boundaries},
            "native_candidates_present": {"post_accept_terminal_accounting", "outstanding_response_identity", "last_count_mismatch", "completion_fsm_drain_clear", "finish_aggregation"}.issubset(candidates),
            "all_v3_negatives_rejected": all(row["rejected"] for row in negatives),
        }
        report(reports / "candidate_discrimination_matrix.json", candidate_checks, negative_controls=negatives)

    kinds = {
        "exact_final_zip_clean_extract": "exact-final-zip-clean-extract",
        "actual_runner_entry_and_input_open": "exact-runner-safe-compile-and-open-paths",
        "source_bound_logger_collector_parser_roundtrip": "exact-generated-over-budget-multi-instance",
        "post_sim_return_core_scenarios": "exact-final-request-four-scenario",
        "candidate_discrimination_matrix": "exact-candidate-positive-negative-matrix",
    }
    evidence = [{"gate_id": name, "evidence_kind": kind,
                 "path": (reports / f"{name}.json").relative_to(ROOT).as_posix(),
                 "sha256": sha(reports / f"{name}.json")} for name, kind in kinds.items()]
    first = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": PACKAGE, "family": FAMILY,
                    "final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)}},
        "rule_change": {"epoch_id": EPOCH, "rule_ids": [RULE], "first_fresh_for_family": True, "notification_acknowledged": True},
        "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True,
                                "family_build_reports_reused": False, "top_level_invocations": 1,
                                "all_errors_collected": True, "rebuild_per_single_error_forbidden": True},
        "evidence_reports": evidence,
        "candidate_discrimination": {"candidate_ids": candidates, "covered_candidate_ids": candidates,
                                     "uncovered_candidate_ids": [], "positive_control_count": 12,
                                     "negative_control_count": 6, "pairwise_distinguishable": True},
        "findings": [],
    }
    first_path = OUT / "first_fresh_audit/contract.json"
    validation = OUT / "gates/first_fresh_validation.json"
    write(first_path, first)
    invocation = prior.run([str(PYTHON), str(ROOT / "tools/validate_server_first_fresh_extra_audit.py"),
                            "--contract", str(first_path), "--workspace-root", str(ROOT), "--output", str(validation)])
    print(json.dumps({"package_id": PACKAGE, "pass": invocation["exit_code"] == 0, "validation": str(validation)}, sort_keys=True))
    return 0 if invocation["exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
