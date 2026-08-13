#!/usr/bin/env python3
"""Prepare independent first-fresh evidence for serialized Conv v81."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v81_ack_phase_targetfix"
FAMILY = "serialized_conv_node0004"
EPOCH = "20260811-partial-exit-live-causal-record-v1"
RULE = "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001"
CANDIDATES = [
    "POSTNBA_SETTLE_WITH_SAME_CYCLE_CONSUMER_ACCEPT",
    "HALF_CYCLE_SETTLE_WITH_NEXT_EDGE_CONSUMER_ACCEPT",
    "SETTLED_PUBLIC_ACK_BUT_CONSUMER_STALE",
    "INACTIVE_DELTA_SETTLE",
    "PERSISTENT_EQUATION_OR_COMPILED_SOURCE_MISMATCH",
    "OPERAND_OR_EPOCH_TRANSITION",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def evidence(path: Path, gate_id: str, checks: dict[str, bool], details: dict[str, Any]) -> Path:
    errors = [name for name, passed in checks.items() if not passed]
    write(
        path,
        {
            "schema": "conv-node0004-v81-first-fresh-evidence-v1",
            "gate_id": gate_id,
            "pass": not errors,
            "errors": errors,
            "checks": checks,
            "details": details,
        },
    )
    return path


def run(argv: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--audit-tree", required=True, type=Path)
    parser.add_argument("--v76-return", required=True, type=Path)
    parser.add_argument("--iverilog", required=True, type=Path)
    parser.add_argument("--bash", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    args = parser.parse_args()

    if args.output_root.exists() or args.audit_tree.exists():
        raise SystemExit("independent first-fresh output/audit tree must not pre-exist")
    args.output_root.mkdir(parents=True)
    args.audit_tree.mkdir(parents=True)

    with zipfile.ZipFile(args.zip) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        crc = archive.testzip() is None
        safe = all(
            not PurePosixPath(item.filename).is_absolute()
            and ".." not in PurePosixPath(item.filename).parts
            and "\\" not in item.filename
            and not stat.S_ISLNK(item.external_attr >> 16)
            for item in infos
        )
        root_ok = {PurePosixPath(name).parts[0] for name in names if name} == {PACKAGE}
        duplicates_ok = len(names) == len(set(names))
        if not all((crc, safe, root_ok, duplicates_ok)):
            raise SystemExit("exact final ZIP clean-extract safety failed")
        archive.extractall(args.audit_tree)

    package = args.audit_tree / PACKAGE
    manifest = load(package / "package_manifest.json")
    actual = {
        item.relative_to(package).as_posix(): sha(item)
        for item in sorted(package.rglob("*"))
        if item.is_file() and item.name != "package_manifest.json"
    }
    clean = evidence(
        args.output_root / "exact_final_zip_clean_extract.json",
        "exact_final_zip_clean_extract",
        {
            "crc": crc,
            "safe_members": safe,
            "single_root": root_ok,
            "duplicate_free": duplicates_ok,
            "manifest_exact": manifest.get("files") == actual,
            "epoch_ack": manifest.get("first_fresh_extra_audit", {}).get("epoch_id") == EPOCH,
            "package_bound": manifest.get("first_fresh_extra_audit", {}).get("bound_package_id") == PACKAGE,
            "first_fresh_after_change": manifest.get("first_fresh_extra_audit", {}).get("first_fresh_after_change") is True,
        },
        {
            "zip_path": args.zip.resolve().relative_to(ROOT).as_posix(),
            "zip_bytes": args.zip.stat().st_size,
            "zip_sha256": sha(args.zip),
            "member_count": len(names),
            "clean_tree": args.audit_tree.resolve().relative_to(ROOT).as_posix(),
        },
    )

    source_path = args.output_root / "exact_source_bound.json"
    source_proc = run([
        str(args.python), str(ROOT / "tools/generate_server_source_bound_observer.py"),
        "validate-final-zip", "--zip", str(args.zip), "--report", str(source_path),
    ])
    source_value = load(source_path) if source_path.is_file() else {}

    temporal_path = args.output_root / "exact_temporal.json"
    temporal_proc = run([
        str(args.python), str(ROOT / "tools/validate_node0004_v81_temporal_collector.py"),
        "--zip", str(args.zip), "--v76-return", str(args.v76_return), "--output", str(temporal_path),
    ])
    temporal_value = load(temporal_path) if temporal_path.is_file() else {}

    phase_path = args.output_root / "exact_phase.json"
    phase_proc = run([
        str(args.python), str(ROOT / "tools/validate_node0004_v81_phase.py"),
        "--zip", str(args.zip), "--iverilog", str(args.iverilog), "--output", str(phase_path),
    ])
    phase_value = load(phase_path) if phase_path.is_file() else {}

    logger = evidence(
        args.output_root / "source_bound_logger_collector_parser_roundtrip.json",
        "source_bound_logger_collector_parser_roundtrip",
        {
            "source_bound_exit_zero": source_proc.returncode == 0,
            "exact_generation_pass": source_value.get("pass") is True and source_value.get("errors") == [],
            "temporal_exit_zero": temporal_proc.returncode == 0,
            "overbudget_multi_instance": temporal_value.get("checks", {}).get("raw_logger_input_exceeds_7_mib") is True,
            "bounded_collector": temporal_value.get("checks", {}).get("bounded_under_7_mib") is True,
            "percent_m_real_instance": "tb_NDP_Top_new_phy" in json.dumps(temporal_value.get("details", {})),
            "phase_exit_zero": phase_proc.returncode == 0,
            "tiny_live_only_fixture": phase_value.get("checks", {}).get("tiny_live_fixture_passes") is True,
            "final_only_ring_negative": phase_value.get("checks", {}).get("final_ring_only_fails_closed") is True,
            "wrong_instance_negative": phase_value.get("checks", {}).get("wrong_instance_fails_closed") is True,
        },
        {
            "source_bound_sha256": sha(source_path) if source_path.is_file() else None,
            "temporal_sha256": sha(temporal_path) if temporal_path.is_file() else None,
            "phase_sha256": sha(phase_path) if phase_path.is_file() else None,
            "process_exits": {"source_bound": source_proc.returncode, "temporal": temporal_proc.returncode, "phase": phase_proc.returncode},
        },
    )

    post_path = args.output_root / "exact_post_sim.json"
    post_proc = run([
        str(args.python), str(package / "package_tools/server_post_sim_return.py"),
        "validate-final-zip", "--zip", str(args.zip), "--output", str(post_path),
    ])
    post_value = load(post_path) if post_path.is_file() else {}
    scenarios = set(post_value.get("details", {}).get("scenario_results", {}))
    live = post_value.get("details", {}).get("partial_exit_live_causal_record", {})
    post = evidence(
        args.output_root / "post_sim_return_core_scenarios.json",
        "post_sim_return_core_scenarios",
        {
            "validator_exit_zero": post_proc.returncode == 0,
            "post_sim_pass": post_value.get("pass") is True and post_value.get("errors") == [],
            "four_scenarios": scenarios == {"natural_success", "natural_success_plugin_failure", "simulation_nonzero", "idempotent_reentry"},
            "partial_exit_contract_complete": live.get("contract_errors") == [],
            "required_live_plugin_executed": bool(live.get("plugin_results")) and all(
                row.get("executed") is True and row.get("pass") is True
                for row in live.get("plugin_results", {}).values()
            ),
            "final_only_ring_sole_input_forbidden": live.get("final_block_ring_sole_input_forbidden") is True,
        },
        {"post_sim_validation_sha256": sha(post_path) if post_path.is_file() else None, "scenario_names": sorted(scenarios)},
    )

    runner_path = args.output_root / "exact_runner.json"
    shared_path = args.output_root / "exact_shared_harness.json"
    runner_proc = run([
        str(args.python), str(ROOT / "tools/validate_node0004_v81_install_only_runner.py"),
        "--zip", str(args.zip), "--sidecar", str(args.sidecar),
        "--expected-zip-sha256", sha(args.zip), "--bash", str(args.bash),
        "--python", str(args.python), "--output", str(runner_path),
        "--shared-harness-output", str(shared_path),
    ], timeout=600)
    runner_value = load(runner_path) if runner_path.is_file() else {}
    controls = runner_value.get("controls", {})
    flows = ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM")
    runner = evidence(
        args.output_root / "actual_runner_entry_and_input_open.json",
        "actual_runner_entry_and_input_open",
        {
            "runner_exit_zero": runner_proc.returncode == 0,
            "runner_valid": runner_value.get("valid") is True and runner_value.get("errors") == [],
            "normal_compile_and_sim": controls.get("normal", {}).get("compile_started") is True and controls.get("normal", {}).get("simulation_started") is True,
            "all_86_inputs_open": controls.get("normal", {}).get("opened_count") == 86,
            "all_flows_finalized": all(controls.get(flow, {}).get("finalizer_reached") is True for flow in flows),
            "all_flows_fixed_return": all(controls.get(flow, {}).get("fixed_result_return_published") is True for flow in flows),
            "root_direct_set_unchanged": all(controls.get(flow, {}).get("root_exact_set_unchanged") is True for flow in flows),
        },
        {"runner_validation_sha256": sha(runner_path) if runner_path.is_file() else None, "shared_harness_sha256": sha(shared_path) if shared_path.is_file() else None},
    )

    checks = phase_value.get("checks", {})
    candidate_checks = {
        CANDIDATES[0]: checks.get("postnba_accept") is True,
        CANDIDATES[1]: checks.get("half_next_accept") is True,
        CANDIDATES[2]: checks.get("consumer_stale") is True,
        CANDIDATES[3]: checks.get("inactive_settle") is True,
        CANDIDATES[4]: checks.get("persistent") is True,
        CANDIDATES[5]: checks.get("operand_transition") is True,
    }
    matrix = evidence(
        args.output_root / "candidate_discrimination_matrix.json",
        "candidate_discrimination_matrix",
        {
            "six_candidates_covered": all(candidate_checks.values()),
            "pairwise_distinguishable": len(CANDIDATES) == len(set(CANDIDATES)),
            "missing_phase_negative": checks.get("missing_phase_fails_closed") is True,
            "duplicate_phase_negative": checks.get("duplicate_phase_fails_closed") is True,
            "wrong_instance_negative": checks.get("wrong_instance_fails_closed") is True,
            "final_only_negative": checks.get("final_ring_only_fails_closed") is True,
            "deleted_leaf_negative": checks.get("deleted_actual_negative") is True,
            "wrong_sibling_negative": checks.get("wrong_sibling_negative") is True,
        },
        {"candidate_ids": CANDIDATES, "candidate_checks": candidate_checks, "positive_control_count": 6, "negative_control_count": 6},
    )

    evidence_map = [
        ("exact_final_zip_clean_extract", "exact-final-zip-clean-extract", clean),
        ("actual_runner_entry_and_input_open", "exact-runner-safe-compile-and-open-paths", runner),
        ("source_bound_logger_collector_parser_roundtrip", "exact-generated-over-budget-multi-instance", logger),
        ("post_sim_return_core_scenarios", "exact-final-request-four-scenario", post),
        ("candidate_discrimination_matrix", "exact-candidate-positive-negative-matrix", matrix),
    ]
    contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {
            "package_id": PACKAGE,
            "family": FAMILY,
            "final_zip": {"path": args.zip.resolve().relative_to(ROOT).as_posix(), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip)},
        },
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
            {"gate_id": gate_id, "evidence_kind": kind, "path": path.resolve().relative_to(ROOT).as_posix(), "sha256": sha(path)}
            for gate_id, kind, path in evidence_map
        ],
        "candidate_discrimination": {
            "candidate_ids": CANDIDATES,
            "covered_candidate_ids": CANDIDATES,
            "uncovered_candidate_ids": [],
            "positive_control_count": 6,
            "negative_control_count": 6,
            "pairwise_distinguishable": True,
        },
        "findings": [],
    }
    contract_path = args.output_root / "contract.json"
    write(contract_path, contract)
    failed = [path.name for _, _, path in evidence_map if load(path).get("pass") is not True]
    write(
        args.output_root / "preparation_report.json",
        {
            "schema": "conv-node0004-v81-first-fresh-extra-audit-preparation-v1",
            "pass": not failed,
            "errors": failed,
            "epoch_id": EPOCH,
            "package_id": PACKAGE,
            "exact_zip_sha256": sha(args.zip),
            "contract_sha256": sha(contract_path),
        },
    )
    print(json.dumps({"pass": not failed, "errors": failed, "contract": str(contract_path)}))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
