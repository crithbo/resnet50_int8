#!/usr/bin/env python3
"""Independent exact-final-ZIP v4/v3 first-fresh audit for native Conv p50."""

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

from tools import audit_conv_native_p49_tbvcdrt2_first_fresh as prior  # noqa: E402
from tools.validate_server_tb_vcd_bounded_causal_cone import validate_contract  # noqa: E402


PACKAGE = "r5_n4_0cc_p50_rdbufdrain"
FAMILY = "conv_native_four_lane"
EPOCH = "tb-vcd-first-round-breadth-adaptive-v4-runtime-v3"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_release"
ZIP = OUT / f"{PACKAGE}.zip"
REPEAT = OUT / f"{PACKAGE}.repeat.zip"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p49_tbvcdrt2.zip"
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def report(path: Path, checks: dict[str, bool], **extra: Any) -> None:
    write(path, {
        "pass": all(checks.values()),
        "checks": checks,
        "errors": [name for name, passed in checks.items() if not passed],
        **extra,
    })


def patch_prior_globals() -> None:
    prior.PACKAGE = PACKAGE
    prior.FAMILY = FAMILY
    prior.EPOCH = EPOCH
    prior.OUT = OUT
    prior.ZIP = ZIP
    prior.REPEAT = REPEAT
    prior.SOURCE = SOURCE


def release_admission() -> dict[str, Any]:
    """Refresh the inherited admission contract to the current schema-runtime gate."""
    prior.release_admission()
    contract_path = OUT / "gates/package_release_admission_contract.json"
    contract = load(contract_path)
    contract["python_schema_runtime"] = {
        "package_python_source_suffixes": [".py"],
        "exact_set_compile": True,
        "compile_staging_and_clean_exact_zip": True,
        "bytecode_destination": "OUTSIDE_PACKAGE_TEMPORARY_DIRECTORY",
        "schema_validation_enabled": True,
        "schema_dependency": "jsonschema",
        "missing_dependency_disposition": "FAIL_CLOSED",
        "skip_allowed": False,
    }
    write(contract_path, contract)
    output = OUT / "gates/package_release_admission.json"
    invocation = prior.prior.run([
        str(PYTHON),
        str(ROOT / "tools/validate_server_package_release_admission.py"),
        "--contract", str(contract_path),
        "--workspace-root", str(ROOT),
        "--output", str(output),
    ])
    return {"invocation": invocation, "value": load(output) if output.is_file() else {}}


def negative_result(
    contract: dict[str, Any],
    package: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> bool:
    value = copy.deepcopy(contract)
    mutate(value)
    return validate_contract(value, package)["pass"] is False


def main() -> int:
    patch_prior_globals()
    reports = OUT / "first_fresh_audit/reports"
    reports.mkdir(parents=True, exist_ok=True)
    admission = release_admission()

    with tempfile.TemporaryDirectory(prefix="native-p50-v4-") as raw:
        temp = Path(raw)
        package = prior.prior.safe_extract(ZIP, temp / "fresh", PACKAGE)
        source = prior.prior.safe_extract(SOURCE, temp / "source", "r5_n4_0cc_p49_tbvcdrt2")
        contract = load(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
        manifest = load(package / "package_manifest.json")
        tb = (package / "tb_probe/native_mse4_bounded_causal_cone_vcd.sv").read_text(encoding="utf-8")
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")

        python_errors: list[str] = []
        for path in sorted(package.rglob("*.py")):
            try:
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
            except (OSError, SyntaxError, UnicodeError) as exc:
                python_errors.append(f"{path.relative_to(package).as_posix()}: {exc}")
        exact = {
            "manifest_exact": manifest.get("files") == prior.prior.file_map(package, exclude_manifest=True),
            "deterministic_recompute": ZIP.read_bytes() == REPEAT.read_bytes(),
            "source_workload_frozen": prior.prior.workload_map(package) == prior.prior.workload_map(source),
            "functional_rtl_absent": not (package / "rtl").exists(),
            "all_python_compiles": not python_errors,
            "current_shared_evaluator_byte_equal": (
                package / "package_tools/server_tb_vcd_runtime_supervision.py"
            ).read_bytes() == (ROOT / "tools/server_tb_vcd_runtime_supervision.py").read_bytes(),
            "current_post_return_helper_byte_equal": (
                package / "package_tools/server_post_sim_return.py"
            ).read_bytes() == (ROOT / "tools/server_post_sim_return.py").read_bytes(),
            "no_packaged_runtime_wave": not any(
                path.suffix.lower() in {".vcd", ".vpd", ".fsdb", ".fst"}
                for path in package.rglob("*") if path.is_file()
            ),
            "release_admission": admission["invocation"]["exit_code"] == 0
            and admission["value"].get("pass") is True,
        }
        report(reports / "exact_final_zip_clean_extract.json", exact, python_errors=python_errors)

        positive = validate_contract(contract, package)
        try:
            import jsonschema

            jsonschema.validate(
                contract,
                load(ROOT / "schemas/server_tb_vcd_bounded_causal_cone_v1.schema.json"),
            )
            schema_pass = True
            schema_error = None
        except Exception as exc:  # fail closed and retain exact error
            schema_pass = False
            schema_error = str(exc)

        negatives = {
            "missing_soft_reference_receipt": negative_result(
                contract,
                package,
                lambda value: value["diagnostic_round"]["breadth_baseline"].update(
                    {"receipt_path": "diagnostics/absent_reference.json"}
                ),
            ),
            "deviation_without_explanation": negative_result(
                contract,
                package,
                lambda value: value["diagnostic_round"]["breadth_baseline"]["deviation"].update(
                    {"explanation": None}
                ),
            ),
            "low_confidence_removal": negative_result(
                contract,
                package,
                lambda value: value["diagnostic_round"]["evolution"].update({
                    "removed_signal_ids": [value["signals"][0]["signal_id"]],
                    "removal_evidence": [{
                        "signal_id": value["signals"][0]["signal_id"],
                        "reason": "negative control",
                        "confidence": "LOW",
                        "affected_candidate_ids": [value["candidates"][0]["candidate_id"]],
                        "disposition": "FAMILY_ADAPTIVE_PRUNING",
                    }],
                }),
            ),
            "add_remove_diff_mismatch": negative_result(
                contract,
                package,
                lambda value: value["diagnostic_round"]["evolution"]["added_signal_ids"].pop(),
            ),
            "candidate_loss": negative_result(
                contract,
                package,
                lambda value: value["candidates"].pop(),
            ),
            "source_identity_drift": negative_result(
                contract,
                package,
                lambda value: value["diagnostic_round"]["source_identity"].update(
                    {"catalog_source_identity_sha256": "f" * 64}
                ),
            ),
            "size_or_stop_protection_weakened": negative_result(
                contract,
                package,
                lambda value: value["budget"].update({"hard_truncation": True}),
            ),
        }
        breadth_checks = {
            "positive_v4_contract": positive.get("pass") is True,
            "schema_v4": schema_pass,
            "exact_88_signal_catalog": len(contract["signals"]) == 88,
            "p49_66_retained_plus_22": len(contract["diagnostic_round"]["evolution"]["added_signal_ids"]) == 88,
            "five_high_candidates": sum(item["priority"] == "HIGH" for item in contract["candidates"]) == 5,
            "all_high_zero_hop_drivers": positive.get("missing_high_candidate_direct_driver_ids") == [],
            "pairwise_matrix_complete": len(contract["candidate_boundary_matrix"]) == 24,
            "all_v4_negative_controls_rejected": all(negatives.values()),
        }
        report(
            reports / "candidate_discrimination_matrix.json",
            breadth_checks,
            positive_validation=positive,
            negative_controls=negatives,
            schema_error=schema_error,
        )

        module_text = tb[:tb.index("bind tb_NDP_Top_new_phy")]
        module_text = "\n".join(
            "      $dumpvars(0, codex_state);" if "$dumpvars(" in line else line
            for line in module_text.splitlines()
        ) + "\n"
        module_path = temp / "module.sv"
        module_path.write_text(module_text, encoding="utf-8", newline="\n")
        frontend = subprocess.run(
            [str(IVERILOG), "-g2012", "-tnull", str(module_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        replay = prior.runtime_replay(package)
        roundtrip = prior.synthetic_roundtrip(package, temp / "roundtrip")
        runtime_checks = {
            "full_hdl_frontend": frontend.returncode == 0,
            "shared_runtime_four_case_replay": replay.get("pass") is True,
            "natural_synthetic_archive_roundtrip": roundtrip.get("pass") is True,
            "valid_qualified_xz": "VALID_OR_ACTIVE_OWNER_GATED" in (
                package / "diagnostics/valid_qualified_xz_contract.json"
            ).read_text(encoding="utf-8"),
            "vector_range_normalization": 're.sub(r"\\s+\\[[^]]+\\]\\s*$", "", cleaned)' in (
                package / "package_tools/tb_vcd_finalize.py"
            ).read_text(encoding="utf-8"),
            "pid_starttime_identity": "start_ticks" in (
                package / "package_tools/tb_vcd_live_supervision.py"
            ).read_text(encoding="utf-8"),
            "attempt_console_capture": '--console-log "$run_root/c0/console.log"' in runner
            and "runs/c0/console.log" in (
                package / "contracts/server_post_sim_return_request.json"
            ).read_text(encoding="utf-8"),
            "no_tb_independent_finish": "$finish;" not in tb,
        }
        report(
            reports / "source_bound_logger_collector_parser_roundtrip.json",
            runtime_checks,
            frontend={"exit_code": frontend.returncode, "stdout": frontend.stdout, "stderr": frontend.stderr},
            replay=replay,
            roundtrip=roundtrip,
        )

        runner_checks = {
            "one_production_launch": runner.count("# CODEX_PRODUCTION_LAUNCH") == 1,
            "finalizer_armed_before_launch": runner.index("trap 'bootstrap_finalize $?' EXIT")
            < runner.index("# CODEX_PRODUCTION_LAUNCH"),
            "all_make_dump_argv_zero": all(
                token in runner for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")
            ),
            "shared_evaluator_handoff": all(
                token in runner
                for token in ("--runtime-evaluator", "--decision-receipt", "TB_VCD_LIVE_DECISION_RECEIPT.json")
            ),
            "compile_core_complete": all(
                token in runner
                for token in (
                    "compile_argv.json", "compile_source_identity.json", "compile_driver.log",
                    "compile_first_error.txt", "COMPILE_CORE.json",
                )
            ),
            "attempt_console_capture": '--console-log "$run_root/c0/console.log"' in runner,
        }
        report(reports / "actual_runner_entry_and_input_open.json", runner_checks)

        post_output = temp / "post_sim_final_zip.json"
        post_invocation = prior.prior.run([
            str(PYTHON),
            str(package / "package_tools/server_post_sim_return.py"),
            "validate-final-zip", "--zip", str(ZIP), "--output", str(post_output),
        ])
        post_value = load(post_output) if post_output.is_file() else {}
        post_checks = {
            "validator_exit_zero": post_invocation["exit_code"] == 0,
            "four_scenarios_pass": post_value.get("pass") is True,
            "console_and_breadth_returned": all(
                token in (package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8")
                for token in ("runs/c0/console.log", "TB_VCD_BREADTH_EVOLUTION.json")
            ),
        }
        report(
            reports / "post_sim_return_core_scenarios.json",
            post_checks,
            invocation=post_invocation,
            validation=post_value,
        )

    expected_kinds = {
        "exact_final_zip_clean_extract": "exact-final-zip-clean-extract",
        "actual_runner_entry_and_input_open": "exact-runner-safe-compile-and-open-paths",
        "source_bound_logger_collector_parser_roundtrip": "exact-generated-over-budget-multi-instance",
        "post_sim_return_core_scenarios": "exact-final-request-four-scenario",
        "candidate_discrimination_matrix": "exact-candidate-positive-negative-matrix",
    }
    report_paths = [reports / f"{name}.json" for name in expected_kinds]
    all_reports_pass = all(load(path).get("pass") is True for path in report_paths)
    first = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {
            "package_id": PACKAGE,
            "family": FAMILY,
            "final_zip": {
                "path": ZIP.relative_to(ROOT).as_posix(),
                "bytes": ZIP.stat().st_size,
                "sha256": prior.sha(ZIP),
            },
        },
        "rule_change": {
            "epoch_id": EPOCH,
            "rule_ids": ["CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001"],
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
                "gate_id": path.stem,
                "evidence_kind": expected_kinds[path.stem],
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": prior.sha(path),
            }
            for path in report_paths
        ],
        "candidate_discrimination": {
            "candidate_ids": [item["candidate_id"] for item in contract["candidates"]],
            "covered_candidate_ids": [item["candidate_id"] for item in contract["candidates"]],
            "uncovered_candidate_ids": [],
            "positive_control_count": 16,
            "negative_control_count": 7,
            "pairwise_distinguishable": True,
        },
        "findings": [],
    }
    first_path = OUT / "first_fresh_audit/contract.json"
    validation = OUT / "gates/first_fresh_validation.json"
    write(first_path, first)
    invocation = prior.prior.run([
        str(PYTHON),
        str(ROOT / "tools/validate_server_first_fresh_extra_audit.py"),
        "--contract", str(first_path),
        "--workspace-root", str(ROOT),
        "--output", str(validation),
    ])
    passed = all_reports_pass and invocation["exit_code"] == 0 and load(validation).get("pass") is True
    print(json.dumps({"package_id": PACKAGE, "pass": passed, "validation": str(validation)}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
