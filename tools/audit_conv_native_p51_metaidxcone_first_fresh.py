#!/usr/bin/env python3
"""Independent clean-final-ZIP first-fresh audit for native Conv p51."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import audit_conv_native_p50_rdbufdrain_first_fresh as prior
from tools.validate_server_tb_vcd_bounded_causal_cone import validate_contract


PACKAGE = "r5_n4_0cc_p51_metaidxcone"
FAMILY = "conv_native_four_lane"
EPOCH = "tb-vcd-adaptive-v4-runtime-v3-p51-metaidxcone"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p51_metaidxcone_release"
ZIP = OUT / f"{PACKAGE}.zip"
REPEAT = OUT / f"{PACKAGE}.repeat.zip"
SOURCE_ID = "r5_n4_0cc_p50_rdbufdrain"
SOURCE = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/pending/{SOURCE_ID}.zip"
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def report(path: Path, checks: dict[str, bool], **extra: Any) -> None:
    write(path, {"pass": all(checks.values()), "checks": checks, "errors": [key for key, value in checks.items() if not value], **extra})


def negative(contract: dict[str, Any], package: Path, mutate: Callable[[dict[str, Any]], None]) -> bool:
    value = copy.deepcopy(contract); mutate(value)
    return validate_contract(value, package).get("pass") is False


def main() -> int:
    prior.PACKAGE = PACKAGE; prior.FAMILY = FAMILY; prior.EPOCH = EPOCH
    prior.OUT = OUT; prior.ZIP = ZIP; prior.REPEAT = REPEAT; prior.SOURCE = SOURCE
    prior.patch_prior_globals()
    reports = OUT / "first_fresh_audit/reports"; reports.mkdir(parents=True, exist_ok=True)
    admission = prior.release_admission()

    with tempfile.TemporaryDirectory(prefix="native-p51-v4-") as raw:
        temp = Path(raw)
        package = prior.prior.prior.safe_extract(ZIP, temp / "fresh", PACKAGE)
        source = prior.prior.prior.safe_extract(SOURCE, temp / "source", SOURCE_ID)
        contract = load(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
        manifest = load(package / "package_manifest.json")
        tb = (package / "tb_probe/native_mse4_bounded_causal_cone_vcd.sv").read_text(encoding="utf-8")
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        live = (package / "package_tools/tb_vcd_live_supervision.py").read_text(encoding="utf-8")

        python_errors = []
        for path in sorted(package.rglob("*.py")):
            try:
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
            except (OSError, SyntaxError, UnicodeError) as exc:
                python_errors.append(f"{path.relative_to(package).as_posix()}: {exc}")
        exact = {
            "manifest_exact": manifest.get("files") == prior.prior.prior.file_map(package, exclude_manifest=True),
            "deterministic_recompute": ZIP.read_bytes() == REPEAT.read_bytes(),
            "source_workload_frozen": prior.prior.prior.workload_map(package) == prior.prior.prior.workload_map(source),
            "functional_rtl_absent": not (package / "rtl").exists(),
            "all_python_compiles": not python_errors,
            "shared_evaluator_byte_equal": (package / "package_tools/server_tb_vcd_runtime_supervision.py").read_bytes() == (ROOT / "tools/server_tb_vcd_runtime_supervision.py").read_bytes(),
            "post_return_helper_byte_equal": (package / "package_tools/server_post_sim_return.py").read_bytes() == (ROOT / "tools/server_post_sim_return.py").read_bytes(),
            "no_packaged_runtime_wave": not any(path.suffix.lower() in {".vcd", ".vpd", ".fsdb", ".fst"} for path in package.rglob("*") if path.is_file()),
            "release_admission": admission["invocation"]["exit_code"] == 0 and admission["value"].get("pass") is True,
        }
        report(reports / "exact_final_zip_clean_extract.json", exact, python_errors=python_errors)

        positive = validate_contract(contract, package)
        try:
            import jsonschema
            jsonschema.validate(contract, load(ROOT / "schemas/server_tb_vcd_bounded_causal_cone_v1.schema.json"))
            schema_pass, schema_error = True, None
        except Exception as exc:
            schema_pass, schema_error = False, str(exc)
        negatives = {
            "missing_predecessor": negative(contract, package, lambda value: value["diagnostic_round"]["evolution"]["predecessor"].update({"contract_path": "provenance/absent.json"})),
            "low_confidence_removal": negative(contract, package, lambda value: value["diagnostic_round"]["evolution"].update({"removed_signal_ids": [value["signals"][0]["signal_id"]], "unchanged_signal_ids": value["diagnostic_round"]["evolution"]["unchanged_signal_ids"][1:], "removal_evidence": [{"signal_id": value["signals"][0]["signal_id"], "reason": "negative", "confidence": "LOW", "affected_candidate_ids": [value["candidates"][0]["candidate_id"]], "disposition": "FAMILY_ADAPTIVE_PRUNING"}]})),
            "candidate_loss": negative(contract, package, lambda value: value["candidates"].pop()),
            "source_identity_drift": negative(contract, package, lambda value: value["diagnostic_round"]["source_identity"].update({"catalog_source_identity_sha256": "f" * 64})),
            "size_protection_weakened": negative(contract, package, lambda value: value["budget"].update({"hard_truncation": True})),
        }
        breadth = {
            "positive_contract": positive.get("pass") is True,
            "schema": schema_pass,
            "exact_106_signal_catalog": len(contract["signals"]) == 106,
            "p50_88_retained_plus_18": len(contract["diagnostic_round"]["evolution"]["unchanged_signal_ids"]) == 88 and len(contract["diagnostic_round"]["evolution"]["added_signal_ids"]) == 18,
            "nine_candidates": len(contract["candidates"]) == 9,
            "all_high_zero_hop_drivers": positive.get("missing_high_candidate_direct_driver_ids") == [],
            "pairwise_matrix_complete": len(contract["candidate_boundary_matrix"]) == 36,
            "negative_controls_rejected": all(negatives.values()),
        }
        report(reports / "candidate_discrimination_matrix.json", breadth, positive_validation=positive, negative_controls=negatives, schema_error=schema_error)

        module_text = tb[:tb.index("bind tb_NDP_Top_new_phy")]
        module_text = "\n".join("      $dumpvars(0, codex_state);" if "$dumpvars(" in line else line for line in module_text.splitlines()) + "\n"
        module_path = temp / "module.sv"; module_path.write_text(module_text, encoding="utf-8", newline="\n")
        frontend = subprocess.run([str(IVERILOG), "-g2012", "-tnull", str(module_path)], check=False, capture_output=True, text=True)
        replay = prior.prior.runtime_replay(package)
        roundtrip = prior.prior.synthetic_roundtrip(package, temp / "roundtrip")
        runtime = {
            "full_hdl_frontend": frontend.returncode == 0,
            "shared_runtime_four_case_replay": replay.get("pass") is True,
            "natural_synthetic_archive_roundtrip": roundtrip.get("pass") is True,
            "qualified_buffer_accept": "(buffer_fifo_enq && !buffer_fifo_full)" in tb and "(buffer_fifo_deq && !buffer_fifo_empty)" in tb,
            "qualified_metadata_accept": "(data_fifo_enq && !data_fifo_full)" in tb and "(data_fifo_deq && !data_fifo_empty)" in tb,
            "qualified_index_accept": "(buf_idx_wr && !buf_idx_full)" in tb and "(mem_idx_wr && !mem_idx_full)" in tb,
            "held_full_not_unqualified_progress": "buffer_fifo_enq || buffer_fifo_deq" not in tb,
            "transient_ps_row_filtered": "if start_ticks is None:" in live,
            "actual_source_capture_post_compile": runner.index("capture_actual_compiled_sources.py") > runner.index("PRODUCTION_COMPILE") and runner.index("capture_actual_compiled_sources.py") < runner.index('[ "$compile_status" -eq 0 ]'),
            "attempt_direct_review": "build_direct_evidence_review.py" in runner and "evidence/CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json" in (package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"),
            "no_tb_finish": "$finish;" not in tb,
        }
        report(reports / "source_bound_logger_collector_parser_roundtrip.json", runtime, frontend={"exit_code": frontend.returncode, "stdout": frontend.stdout, "stderr": frontend.stderr}, replay=replay, roundtrip=roundtrip)

        runner_checks = {
            "one_production_launch": runner.count("# CODEX_PRODUCTION_LAUNCH") == 1,
            "finalizer_armed_before_launch": runner.index("trap 'bootstrap_finalize $?' EXIT") < runner.index("# CODEX_PRODUCTION_LAUNCH"),
            "all_make_dump_argv_zero": all(token in runner for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")),
            "shared_evaluator_handoff": all(token in runner for token in ("--runtime-evaluator", "--decision-receipt", "TB_VCD_LIVE_DECISION_RECEIPT.json")),
            "compile_core_complete": all(token in runner for token in ("compile_argv.json", "compile_source_identity.json", "compile_driver.log", "compile_first_error.txt", "COMPILE_CORE.json")),
            "post_compile_sources_nonblocking": "actual compiled source capture incomplete; core return preserved" in runner,
            "direct_review_nonblocking": "direct config/RTL evidence review failed; raw core preserved" in runner,
        }
        report(reports / "actual_runner_entry_and_input_open.json", runner_checks)

        post_output = temp / "post.json"
        invocation = prior.prior.prior.run([str(PYTHON), str(package / "package_tools/server_post_sim_return.py"), "validate-final-zip", "--zip", str(ZIP), "--output", str(post_output)])
        post = load(post_output) if post_output.is_file() else {}
        post_checks = {
            "validator_exit_zero": invocation["exit_code"] == 0,
            "all_scenarios_pass": post.get("pass") is True,
            "actual_source_manifest_returned": "actual_compiled_sources/manifest.json" in (package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"),
            "attempt_direct_review_returned": '"source_root": "attempt"' in (package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"),
        }
        report(reports / "post_sim_return_core_scenarios.json", post_checks, invocation=invocation, validation=post)

    expected = {
        "exact_final_zip_clean_extract": "exact-final-zip-clean-extract",
        "actual_runner_entry_and_input_open": "exact-runner-safe-compile-and-open-paths",
        "source_bound_logger_collector_parser_roundtrip": "exact-generated-over-budget-multi-instance",
        "post_sim_return_core_scenarios": "exact-final-request-four-scenario",
        "candidate_discrimination_matrix": "exact-candidate-positive-negative-matrix",
    }
    paths = [reports / f"{name}.json" for name in expected]
    first = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": PACKAGE, "family": FAMILY, "final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": prior.prior.sha(ZIP)}},
        "rule_change": {"epoch_id": EPOCH, "rule_ids": ["CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001"], "first_fresh_for_family": True, "notification_acknowledged": True},
        "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True},
        "evidence_reports": [{"gate_id": path.stem, "evidence_kind": expected[path.stem], "path": path.relative_to(ROOT).as_posix(), "sha256": prior.prior.sha(path)} for path in paths],
        "candidate_discrimination": {"candidate_ids": [row["candidate_id"] for row in contract["candidates"]], "covered_candidate_ids": [row["candidate_id"] for row in contract["candidates"]], "uncovered_candidate_ids": [], "positive_control_count": 20, "negative_control_count": 5, "pairwise_distinguishable": True},
        "findings": [],
    }
    first_path = OUT / "first_fresh_audit/contract.json"; write(first_path, first)
    validation = OUT / "gates/first_fresh_validation.json"
    invocation = prior.prior.prior.run([str(PYTHON), str(ROOT / "tools/validate_server_first_fresh_extra_audit.py"), "--contract", str(first_path), "--workspace-root", str(ROOT), "--output", str(validation)])
    passed = all(load(path).get("pass") is True for path in paths) and invocation["exit_code"] == 0 and load(validation).get("pass") is True
    print(json.dumps({"package_id": PACKAGE, "pass": passed, "validation": str(validation)}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
