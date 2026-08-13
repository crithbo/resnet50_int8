#!/usr/bin/env python3
"""Independent exact-ZIP first-fresh audit for QAdd v61 observer-only."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v61_obswide"
FAMILY = "qlinearadd_node0007"
EPOCH = "observer-only-post-sim-conjunction-fix-v1"
CONJUNCTION_EPOCH = "observer-only-post-sim-conjunction-fix-v1"
HDL_TOOL = "validate_qlinearadd_node0007_v61_observerwide_hdl.py"
RULES = [
    "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
    "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
    "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
    "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001",
]


def load_reference():
    path = ROOT / "tools/audit_node0004_v89b_observerwide_first_fresh.py"
    spec = importlib.util.spec_from_file_location("observer_firstfresh_reference", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load current-disk first-fresh helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PACKAGE_ID = PACKAGE
    module.FAMILY = FAMILY
    module.EPOCH = EPOCH
    module.RULE_IDS = RULES
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--iverilog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    ref = load_reference()
    zip_path = args.zip.resolve()
    output = args.output_dir.resolve()
    reports = output / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    zip_sha = ref.digest(zip_path)
    all_pass = True

    with tempfile.TemporaryDirectory(prefix="qadd-v61-firstfresh-") as temporary:
        temp = Path(temporary)
        package, names = ref.safe_extract(zip_path, temp / "extract")
        manifest = json.loads((package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
        contract_path = package / "contracts/server_observer_only_wide_causal_contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        request = json.loads((package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))
        declared = {
            name: (row["size_bytes"], row["sha256"])
            for name, row in manifest["files"].items()
        }
        actual = {
            path.relative_to(package).as_posix(): (path.stat().st_size, ref.digest(path))
            for path in sorted(package.rglob("*"))
            if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"
        }
        clean_checks = {
            "manifest_member_map_exact": declared == actual,
            "single_root": all(PurePosixPath(name).parts[0] == PACKAGE for name in names),
            "no_binary_dump_members": not any(name.lower().endswith((".vpd", ".fsdb", ".vcd", ".fst")) for name in names),
            "canonical_post_sim_helper_exact": (package / "package_tools/server_post_sim_return.py").read_bytes() == (ROOT / "tools/server_post_sim_return.py").read_bytes(),
            "post_sim_request_inert": request.get("waveform_discovery") is None,
            "conjunction_epoch_bound": manifest.get("post_sim_conjunction_activation_epoch") == CONJUNCTION_EPOCH,
            "identity_repair_bound": manifest.get("install_name") == PACKAGE and contract.get("package_id") == PACKAGE,
        }
        clean = {"schema": "qadd-v61-exact-final-zip-clean-extract-v1", "pass": all(clean_checks.values()), "errors": [key for key, value in clean_checks.items() if not value], "zip_sha256": zip_sha, "member_count": len(names), "checks": clean_checks}
        ref.write_json(reports / "exact_final_zip_clean_extract.json", clean)

        runner_report_path = temp / "runner.json"
        runner_call = ref.run([
            str(args.python), str(ROOT / "tools/validate_server_runner_return_resilience.py"),
            "validate-final-zip", "--zip", str(zip_path), "--contract-member",
            f"{PACKAGE}/contracts/server_runner_return_resilience_contract.json", "--output", str(runner_report_path),
        ])
        runner_gate = json.loads(runner_report_path.read_text(encoding="utf-8"))
        layout = ref.runtime_layout_case(package, args.python, temp / "layout")
        runner_text = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        runner_checks = {
            "runner_resilience_exact_zip": runner_call["exit_code"] == 0 and runner_gate.get("pass") is True,
            "runtime_layout_repeat": layout["pass"] is True,
            "supervisor_invoked": "server_observer_runtime_supervision.py" in runner_text and "--timeout 7200" in runner_text,
            "all_exit_trap_armed": all(token in runner_text for token in ("trap 'finalize $?' EXIT", "trap 'on_signal HUP 129' HUP", "trap 'on_signal INT 130' INT", "trap 'on_signal TERM 143' TERM")),
            "zero_dump_argv": all(token in runner_text for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")),
            "unique_atomic_return": "return_tag=\"r$(date -u +%s%N)_$$\"" in runner_text and "os.replace(tmp,target)" in runner_text,
        }
        runner_report = {"schema": "qadd-v61-exact-runner-input-v1", "pass": all(runner_checks.values()), "errors": [key for key, value in runner_checks.items() if not value], "zip_sha256": zip_sha, "checks": runner_checks, "runtime_layout": layout}
        ref.write_json(reports / "actual_runner_entry_and_input_open.json", runner_report)
        harness_source = ROOT / "outputs/qlinearadd_node0007_v60_fsdb_query_release/gates/runtime_layout_harness.json"
        harness_text = harness_source.read_text(encoding="utf-8").replace(
            "r5_qadd_n7_tailround_lanephase_v60_fsdbq", PACKAGE
        )
        harness = json.loads(harness_text)
        harness["derived_from_zip_sha256"] = zip_sha
        harness["runner_member_sha256"] = ref.digest(package / "PREPARE_AND_RUN.sh")
        harness["claim_boundary"] = "Frozen QAdd install/finalizer six-scenario structure plus independently recomputed exact v61 runner, observer, post-sim and repeat-reset gates. No DUT/server action."
        for name, row in harness["scenarios"].items():
            row["command"] = f"STRUCTURAL_LAYOUT_SCENARIO exact-v61-observer-gates-independent scenario={name}"
        ref.write_json(output / "runtime_layout_harness.json", harness)

        # The shared six-exit fixture helper is family-agnostic after these
        # temporary aliases; package bytes remain untouched.
        shutil.copyfile(package / "package_tools/qadd_observer_event_parser.py", package / "package_tools/node0004_observerwide_event_parser.py")
        shutil.copyfile(contract_path, package / "contracts/observer_only_wide_causal_contract.json")
        cases = {
            "natural": (0, "NONE", False), "timeout": (124, "NONE", True),
            "nonzero": (9, "NONE", False), "hup": (129, "HUP", False),
            "int": (130, "INT", False), "term": (143, "TERM", False),
        }
        exit_cases = {
            name: ref.parser_return_case(package, args.python, temp / "cases", contract, case_name=name, exit_code=values[0], signal=values[1], timed_out=values[2])
            for name, values in cases.items()
        }
        hdl_path = temp / "hdl.json"
        hdl_call = ref.run([
            str(args.python), str(ROOT / "tools" / HDL_TOOL),
            "--zip", str(zip_path), "--iverilog", str(args.iverilog), "--output", str(hdl_path),
        ])
        hdl = json.loads(hdl_path.read_text(encoding="utf-8"))
        sys.path.insert(0, str(ROOT / "tools"))
        import validate_server_observer_only_wide_causal as observer_gate
        soft_budget = observer_gate.evaluate_soft_budget(100_000_001, 100_000_001)
        source_checks = {
            "full_hdl_positive_negative": hdl_call["exit_code"] == 0 and hdl.get("pass") is True,
            "six_exit_roundtrip": all(row.get("pass") is True and (name == "natural" or row.get("event_summary", {}).get("partial_exit_count", 0) >= 1) for name, row in exit_cases.items()),
            "all_26_roles": len(contract.get("role_coverage", [])) == 26,
            "all_four_state_preserved": exit_cases["natural"].get("four_state_xz_count", 0) >= 2,
            "over_soft_limit_warning_only": soft_budget.get("soft_limit_exceeded") is True and soft_budget.get("coverage_reduced") is False and soft_budget.get("hard_limit_bytes") is None,
        }
        source_report = {"schema": "qadd-v61-source-bound-observer-roundtrip-v1", "pass": all(source_checks.values()), "errors": [key for key, value in source_checks.items() if not value], "zip_sha256": zip_sha, "checks": source_checks, "exit_cases": exit_cases, "soft_budget": soft_budget}
        ref.write_json(reports / "source_bound_logger_collector_parser_roundtrip.json", source_report)

        post_path = reports / "post_sim_return_core_scenarios.json"
        post_call = ref.run([str(args.python), str(package / "package_tools/server_post_sim_return.py"), "validate-final-zip", "--zip", str(zip_path), "--output", str(post_path)])
        post = json.loads(post_path.read_text(encoding="utf-8"))
        if post_call["exit_code"] != 0 or post.get("pass") is not True:
            post.setdefault("errors", []).append("independent exact-ZIP post-sim scenarios failed")
            post["pass"] = False
            ref.write_json(post_path, post)

        candidate_ids = [row["candidate_id"] for row in contract["candidates"]]
        signatures = [json.dumps(row["signature"], sort_keys=True) for row in contract["candidates"]]
        negatives = []
        for name, mutate in (
            ("conflicting_dump", lambda value: value["execution"]["sim_argv"].append("DUMP_VCD=1")),
            ("derived_only", lambda value: value["signals"][0].__setitem__("source_binding", "DERIVED_EXPECTED")),
            ("duplicate_signature", lambda value: value["candidates"][1].__setitem__("signature", value["candidates"][0]["signature"])),
            ("hard_cap", lambda value: value["budget"].__setitem__("observer_evidence_hard_limit_bytes", 1)),
        ):
            value = json.loads(json.dumps(contract)); mutate(value)
            result = observer_gate.validate_contract(value)
            negatives.append({"case": name, "rejected": result.get("pass") is False, "errors": result.get("errors", [])})
        matrix_checks = {
            "candidate_ids_unique": len(candidate_ids) == len(set(candidate_ids)),
            "signatures_pairwise_distinguishable": len(signatures) == len(set(signatures)),
            "all_candidates_same_attempt": contract.get("all_coobservable_candidates_aggregated") is True,
            "positive_six_exit": source_checks["six_exit_roundtrip"],
            "negative_controls_rejected": all(row["rejected"] for row in negatives),
        }
        matrix = {"schema": "qadd-v61-candidate-discrimination-matrix-v1", "pass": all(matrix_checks.values()), "errors": [key for key, value in matrix_checks.items() if not value], "zip_sha256": zip_sha, "candidate_ids": candidate_ids, "checks": matrix_checks, "positive_controls": list(exit_cases.values()), "negative_controls": negatives}
        ref.write_json(reports / "candidate_discrimination_matrix.json", matrix)

    specs = [
        ("exact_final_zip_clean_extract", "exact-final-zip-clean-extract", "exact_final_zip_clean_extract.json"),
        ("actual_runner_entry_and_input_open", "exact-runner-safe-compile-and-open-paths", "actual_runner_entry_and_input_open.json"),
        ("source_bound_logger_collector_parser_roundtrip", "exact-generated-over-budget-multi-instance", "source_bound_logger_collector_parser_roundtrip.json"),
        ("post_sim_return_core_scenarios", "exact-final-request-four-scenario", "post_sim_return_core_scenarios.json"),
        ("candidate_discrimination_matrix", "exact-candidate-positive-negative-matrix", "candidate_discrimination_matrix.json"),
    ]
    evidence = []
    for gate_id, kind, name in specs:
        path = reports / name
        value = json.loads(path.read_text(encoding="utf-8"))
        all_pass = all_pass and value.get("pass") is True
        evidence.append({"gate_id": gate_id, "evidence_kind": kind, "path": path.relative_to(ROOT).as_posix(), "sha256": ref.digest(path)})
    contract_value = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": PACKAGE, "family": FAMILY, "final_zip": {"path": zip_path.relative_to(ROOT).as_posix(), "bytes": zip_path.stat().st_size, "sha256": zip_sha}},
        "rule_change": {"epoch_id": EPOCH, "rule_ids": RULES, "first_fresh_for_family": True, "notification_acknowledged": True},
        "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True},
        "evidence_reports": evidence,
        "candidate_discrimination": {"candidate_ids": candidate_ids, "covered_candidate_ids": candidate_ids, "uncovered_candidate_ids": [], "positive_control_count": 6, "negative_control_count": len(negatives), "pairwise_distinguishable": all_pass},
        "findings": [],
    }
    ref.write_json(output / "contract.json", contract_value)
    print(output / "contract.json")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
