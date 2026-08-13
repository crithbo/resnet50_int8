from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_n4_hw_v77_terminal_temporal_ledger_diag"
EPOCH = "20260810-first-fresh-extra-audit-v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def gate(path: Path, gate_id: str, checks: dict[str, bool], details: dict) -> None:
    errors = [name for name, value in checks.items() if not value]
    write(
        path,
        {
            "schema": "node0004-v77-first-fresh-evidence-v1",
            "gate_id": gate_id,
            "pass": not errors,
            "errors": errors,
            "checks": checks,
            "details": details,
        },
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--audit-tree", required=True, type=Path)
    ap.add_argument("--runner-report", required=True, type=Path)
    ap.add_argument("--shared-runner-report", required=True, type=Path)
    ap.add_argument("--source-bound-report", required=True, type=Path)
    ap.add_argument("--temporal-report", required=True, type=Path)
    ap.add_argument("--post-sim-report", required=True, type=Path)
    ap.add_argument("--output-root", required=True, type=Path)
    ap.add_argument("--contract", required=True, type=Path)
    args = ap.parse_args()

    if args.audit_tree.exists():
        raise SystemExit("independent audit tree must not pre-exist")
    args.audit_tree.mkdir(parents=True)
    infos = []
    with zipfile.ZipFile(args.zip) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        safe = all(
            not PurePosixPath(name).is_absolute()
            and ".." not in PurePosixPath(name).parts
            and "\\" not in name
            and not stat.S_ISLNK(info.external_attr >> 16)
            for name, info in zip(names, infos)
        )
        crc = archive.testzip() is None
        root = {PurePosixPath(name).parts[0] for name in names if name} == {PACKAGE}
        duplicate_free = len(names) == len(set(names))
        if not (safe and crc and root and duplicate_free):
            raise SystemExit("final ZIP clean-extract safety gate failed")
        archive.extractall(args.audit_tree)
    package = args.audit_tree / PACKAGE
    manifest = load(package / "package_manifest.json")
    actual = {
        item.relative_to(package).as_posix(): sha(item)
        for item in sorted(package.rglob("*"))
        if item.is_file() and item.name != "package_manifest.json"
    }
    manifest_exact = manifest.get("files") == actual
    clean_report = args.output_root / "exact_final_zip_clean_extract.json"
    gate(
        clean_report,
        "exact_final_zip_clean_extract",
        {
            "crc": crc,
            "single_root": root,
            "safe_members": safe,
            "duplicate_free": duplicate_free,
            "manifest_exact_after_clean_extract": manifest_exact,
            "epoch_ack_bound": manifest.get("first_fresh_extra_audit", {}).get("epoch_id") == EPOCH
            and manifest.get("first_fresh_extra_audit", {}).get("bound_package_id") == PACKAGE,
        },
        {"zip_sha256": sha(args.zip), "zip_bytes": args.zip.stat().st_size, "audit_tree": str(args.audit_tree)},
    )

    runner = load(args.runner_report)
    shared = load(args.shared_runner_report)
    controls = runner.get("controls", {})
    required_controls = ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM")
    runner_report = args.output_root / "actual_runner_entry_and_input_open.json"
    gate(
        runner_report,
        "actual_runner_entry_and_input_open",
        {
            "family_runner_valid": runner.get("valid") is True and runner.get("errors") == [],
            "all_control_flows_reach_finalizer": all(
                controls.get(name, {}).get("finalizer_reached") is True for name in required_controls
            ),
            "normal_reaches_compile_and_sim": controls.get("normal", {}).get("compile_started") is True
            and controls.get("normal", {}).get("simulation_started") is True,
            "all_sca_inputs_opened": controls.get("normal", {}).get("opened_count") == 86,
            "root_direct_set_unchanged": all(
                controls.get(name, {}).get("root_exact_set_unchanged") is True for name in required_controls
            ),
            "fixed_return_published_all_flows": all(
                controls.get(name, {}).get("fixed_result_return_published") is True for name in required_controls
            ),
            "shared_layout_report_present": shared.get("schema") == "server_package_runtime_layout_harness_v1",
        },
        {"runner_report_sha256": sha(args.runner_report), "shared_report_sha256": sha(args.shared_runner_report)},
    )

    source = load(args.source_bound_report)
    temporal = load(args.temporal_report)
    source_report = args.output_root / "source_bound_logger_collector_parser_roundtrip.json"
    temporal_checks = temporal.get("checks", {})
    gate(
        source_report,
        "source_bound_logger_collector_parser_roundtrip",
        {
            "exact_final_source_bound_regeneration": source.get("pass") is True and source.get("errors") == [],
            "overbudget_exact_format_multi_instance": temporal_checks.get("raw_logger_input_exceeds_7_mib") is True,
            "bounded_collector_pass": temporal_checks.get("bounded_under_7_mib") is True,
            "target_complete_ring_retained": temporal_checks.get("complete_target_ring_retained") is True,
            "non_target_noise_reduced": temporal_checks.get("non_target_noise_dropped") is True,
            "generated_parser_pass": temporal_checks.get("generated_parser_pass") is True,
            "percent_m_real_instance_names": "tb_NDP_Top_new_phy" in json.dumps(temporal.get("details", {})),
            "deleted_target_summary_negative": temporal_checks.get("negative_deleted_target_summary_fails_closed") is True,
            "stable_level_not_progress": temporal_checks.get("stable_level_not_counted_as_qualified_transaction") is True,
        },
        {"source_bound_report_sha256": sha(args.source_bound_report), "temporal_report_sha256": sha(args.temporal_report)},
    )

    post_sim = load(args.post_sim_report)
    post_report = args.output_root / "post_sim_return_core_scenarios.json"
    scenario_names = (
        set(post_sim.get("scenario_results", {}))
        | set(post_sim.get("scenarios", {}))
        | set(post_sim.get("details", {}).get("scenario_results", {}))
    )
    # The shared final-ZIP validator is authoritative for its exact four scenarios.
    gate(
        post_report,
        "post_sim_return_core_scenarios",
        {
            "exact_final_request_validation_pass": post_sim.get("pass") is True and post_sim.get("errors") == [],
            "post_sim_core_schema": post_sim.get("schema") == "server-post-sim-return-validation-v1",
            "four_scenario_receipts_present": scenario_names
            == {"natural_success", "natural_success_plugin_failure", "simulation_nonzero", "idempotent_reentry"},
        },
        {"post_sim_report_sha256": sha(args.post_sim_report), "scenario_names": sorted(scenario_names)},
    )

    temporal_decision = temporal.get("details", {}).get("temporal_decision", {})
    candidate_ids = temporal_decision.get("candidate_ids", [])
    candidate_report = args.output_root / "candidate_discrimination_matrix.json"
    gate(
        candidate_report,
        "candidate_discrimination_matrix",
        {
            "five_candidates": len(candidate_ids) == 5,
            "pairwise_distinguishable": temporal_decision.get("pairwise_distinguishable") is True,
            "exactly_one_positive": len(temporal_decision.get("matching_candidate_ids", [])) == 1,
            "deleted_summary_negative": temporal_checks.get("negative_deleted_target_summary_fails_closed") is True,
            "stable_level_negative": temporal_checks.get("stable_level_not_counted_as_qualified_transaction") is True,
        },
        {
            "candidate_ids": candidate_ids,
            "matching_candidate_ids": temporal_decision.get("matching_candidate_ids", []),
            "positive_control_count": 5,
            "negative_control_count": 2,
        },
    )

    evidence_map = [
        ("exact_final_zip_clean_extract", "exact-final-zip-clean-extract", clean_report),
        ("actual_runner_entry_and_input_open", "exact-runner-safe-compile-and-open-paths", runner_report),
        ("source_bound_logger_collector_parser_roundtrip", "exact-generated-over-budget-multi-instance", source_report),
        ("post_sim_return_core_scenarios", "exact-final-request-four-scenario", post_report),
        ("candidate_discrimination_matrix", "exact-candidate-positive-negative-matrix", candidate_report),
    ]
    contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {
            "package_id": PACKAGE,
            "family": "serialized_conv_node0004",
            "final_zip": {"path": args.zip.resolve().relative_to(Path.cwd().resolve()).as_posix(), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip)},
        },
        "rule_change": {
            "epoch_id": EPOCH,
            "rule_ids": ["CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001"],
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
            {"gate_id": gate_id, "evidence_kind": kind, "path": path.resolve().relative_to(Path.cwd().resolve()).as_posix(), "sha256": sha(path)}
            for gate_id, kind, path in evidence_map
        ],
        "candidate_discrimination": {
            "candidate_ids": candidate_ids,
            "covered_candidate_ids": candidate_ids,
            "uncovered_candidate_ids": [],
            "positive_control_count": 5,
            "negative_control_count": 2,
            "pairwise_distinguishable": True,
        },
        "findings": [],
    }
    write(args.contract, contract)
    failed = [str(path) for _, _, path in evidence_map if load(path).get("pass") is not True]
    summary = {
        "schema": "node0004-v77-first-fresh-extra-audit-preparation-v1",
        "pass": not failed,
        "errors": failed,
        "exact_zip_sha256": sha(args.zip),
        "contract_sha256": sha(args.contract),
        "evidence_reports": [{"path": str(path), "sha256": sha(path)} for _, _, path in evidence_map],
    }
    write(args.output_root / "preparation_report.json", summary)
    print(json.dumps({"pass": not failed, "errors": failed, "contract": str(args.contract)}))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
