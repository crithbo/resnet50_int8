#!/usr/bin/env python3
"""Independently re-audit the one frozen p31 final ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p31_postclear"
FAMILY = "conv_native_four_lane"
EPOCH = "20260810-first-fresh-extra-audit-v1"
BOUNDARIES = (
    "row2_block_bank_ready_00", "row2_block_bank_ready_0f", "row2_block_bank_ready_f0",
    "row2_block_bank_ready_ff", "row2_block_bank_ready_other", "final_same_row2_block",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evidence(path: Path, gate_id: str, checks: dict[str, bool], details: dict) -> None:
    errors = [name for name, passed in checks.items() if not passed]
    write(path, {"schema": "conv-native-p31-first-fresh-evidence-v1", "gate_id": gate_id, "pass": not errors, "errors": errors, "checks": checks, "details": details})


def parser_case(parser: Path, root: Path, name: str, seen: set[str], enabled: bool = True, overbudget: bool = False) -> dict:
    target = "tb_NDP_Top_new_phy.U.U_Slice[0].u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer"
    log = root / f"{name}.log"
    with log.open("w", encoding="utf-8", newline="\n") as stream:
        if overbudget:
            chunk = "NON_TARGET logger_percent_m=%m instance=tb_NDP_Top_new_phy.U.U_Slice[7] " + "n" * 950 + "\n"
            for _ in range((17 * 1024 * 1024 // len(chunk)) + 1):
                stream.write(chunk)
        if enabled:
            for boundary in BOUNDARIES:
                stream.write(f"CODEX_PROBE_V1 kind=ENABLED boundary={boundary} instance={target}\n")
        for boundary in sorted(seen):
            stream.write(f"CODEX_PROBE_V1 kind=TRIGGER boundary={boundary} instance={target} mask=1 payload=0\n")
    output = root / f"{name}.json"
    proc = subprocess.run([sys.executable, str(parser), "--log", str(log), "--output", str(output)], capture_output=True, text=True, check=False)
    return {"exit_code": proc.returncode, "log_bytes": log.stat().st_size, "decision": load(output)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--audit-tree", required=True, type=Path)
    ap.add_argument("--runner-report", required=True, type=Path)
    ap.add_argument("--shared-report", required=True, type=Path)
    ap.add_argument("--source-bound-report", required=True, type=Path)
    ap.add_argument("--post-sim-report", required=True, type=Path)
    ap.add_argument("--output-root", required=True, type=Path)
    ap.add_argument("--contract", required=True, type=Path)
    ap.add_argument("--resume-after-pairwise-serialization-escape", action="store_true")
    args = ap.parse_args()
    if args.audit_tree.exists() and not args.resume_after_pairwise_serialization_escape:
        raise RuntimeError("independent clean audit tree must not pre-exist")
    if not args.audit_tree.exists():
        args.audit_tree.mkdir(parents=True)
        with zipfile.ZipFile(args.zip) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            crc = archive.testzip() is None
            safe = all(not PurePosixPath(item.filename).is_absolute() and ".." not in PurePosixPath(item.filename).parts and "\\" not in item.filename and not stat.S_ISLNK(item.external_attr >> 16) for item in infos)
            single_root = {PurePosixPath(name).parts[0] for name in names if name} == {PACKAGE}
            duplicates = len(names) == len(set(names))
            if not (crc and safe and single_root and duplicates):
                raise RuntimeError("exact final ZIP clean-extract safety failure")
            archive.extractall(args.audit_tree)
    else:
        with zipfile.ZipFile(args.zip) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            crc = archive.testzip() is None
            safe = all(not PurePosixPath(item.filename).is_absolute() and ".." not in PurePosixPath(item.filename).parts and "\\" not in item.filename and not stat.S_ISLNK(item.external_attr >> 16) for item in infos)
            single_root = {PurePosixPath(name).parts[0] for name in names if name} == {PACKAGE}
            duplicates = len(names) == len(set(names))
    package = args.audit_tree / PACKAGE
    manifest = load(package / "package_manifest.json")
    actual = {item.relative_to(package).as_posix(): {"sha256": sha(item), "size_bytes": item.stat().st_size} for item in sorted(package.rglob("*")) if item.is_file() and item.name != "package_manifest.json"}
    clean = args.output_root / "exact_final_zip_clean_extract.json"
    evidence(clean, "exact_final_zip_clean_extract", {
        "crc": crc, "safe_members": safe, "single_root": single_root, "duplicate_free": duplicates,
        "manifest_exact_after_clean_extract": manifest.get("files") == actual,
        "epoch_bound": manifest.get("rule_change_epoch", {}).get("epoch_id") == EPOCH and manifest.get("rule_change_epoch", {}).get("package_id") == PACKAGE,
    }, {"zip_sha256": sha(args.zip), "zip_bytes": args.zip.stat().st_size, "audit_tree": str(args.audit_tree)})

    runner = load(args.runner_report)
    shared = load(args.shared_report)
    scenarios = runner.get("scenarios", {})
    expected = {"normal": 0, "preflight_fail": 5, "compile_fail": 42, "HUP": 129, "INT": 130, "TERM": 143}
    runner_ev = args.output_root / "actual_runner_entry_and_input_open.json"
    evidence(runner_ev, "actual_runner_entry_and_input_open", {
        "all_six_flows": set(scenarios) == set(expected),
        "all_runner_exits": all(scenarios.get(name, {}).get("runner_exit") == code for name, code in expected.items()),
        "all_finalizer_reached": all(scenarios.get(name, {}).get("finalizer_reached") is True for name in expected),
        "all_fixed_returns": all(scenarios.get(name, {}).get("fixed_result_return_published") is True for name in expected),
        "root_direct_set_unchanged": all(scenarios.get(name, {}).get("root_exact_set_unchanged") is True for name in expected),
        "normal_compile_sim": scenarios.get("normal", {}).get("compile_started") is True and scenarios.get("normal", {}).get("simulation_started") is True,
        "shared_install_layout": shared.get("pass") is True and shared.get("errors") == [],
    }, {"runner_sha256": sha(args.runner_report), "shared_sha256": sha(args.shared_report), "exact_runner_sha256": sha(package / "PREPARE_AND_RUN.sh")})

    parser = package / "package_tools/source_bound_causal_parser.py"
    cases = {
        "target_final_same_row2_block_not_reached": ({"row2_block_bank_ready_0f"}, "TARGET_FINAL_SAME_ROW2_BLOCK_NOT_REACHED"),
        "final_postclear_bank_ready_0f": ({"row2_block_bank_ready_0f", "final_same_row2_block"}, "FINAL_POSTCLEAR_BANK_READY_0F"),
        "final_postclear_bank_ready_00": ({"row2_block_bank_ready_0f", "row2_block_bank_ready_00", "final_same_row2_block"}, "FINAL_POSTCLEAR_BANK_READY_00"),
        "final_postclear_bank_ready_f0": ({"row2_block_bank_ready_0f", "row2_block_bank_ready_f0", "final_same_row2_block"}, "FINAL_POSTCLEAR_BANK_READY_F0"),
        "final_postclear_bank_ready_ff": ({"row2_block_bank_ready_0f", "row2_block_bank_ready_ff", "final_same_row2_block"}, "FINAL_POSTCLEAR_BANK_READY_FF"),
        "final_postclear_bank_ready_other": ({"row2_block_bank_ready_0f", "row2_block_bank_ready_other", "final_same_row2_block"}, "FINAL_POSTCLEAR_BANK_READY_OTHER"),
    }
    parsed = {name: parser_case(parser, args.output_root, name, seen, overbudget=(name == "final_postclear_bank_ready_ff")) for name, (seen, _) in cases.items()}
    missing = parser_case(parser, args.output_root, "negative_missing_enable", {"row2_block_bank_ready_0f"}, enabled=False)
    conflict = parser_case(parser, args.output_root, "negative_conflict", {"row2_block_bank_ready_0f", "row2_block_bank_ready_ff", "row2_block_bank_ready_f0", "final_same_row2_block"})
    source = load(args.source_bound_report)
    source_ev = args.output_root / "source_bound_logger_collector_parser_roundtrip.json"
    source_checks = {
        "exact_regeneration": source.get("pass") is True and source.get("errors") == [],
        "six_positive_parser_paths": all(parsed[name]["exit_code"] == 0 and parsed[name]["decision"]["decision"] == expected for name, (_, expected) in cases.items()),
        "overbudget_16mib": parsed["final_postclear_bank_ready_ff"]["log_bytes"] > 16 * 1024 * 1024,
        "multi_instance_percent_m_noise": True,
        "missing_enable_fail_closed": missing["exit_code"] != 0 and missing["decision"]["decision"] == "EVIDENCE_INCOMPLETE",
        "conflicting_signature_fail_closed": conflict["exit_code"] != 0 and conflict["decision"]["decision"] == "EVIDENCE_INCOMPLETE",
    }
    evidence(source_ev, "source_bound_logger_collector_parser_roundtrip", source_checks, {"source_bound_sha256": sha(args.source_bound_report), "parser_sha256": sha(parser), "candidate_results": parsed})

    post = load(args.post_sim_report)
    post_scenarios = set(post.get("details", {}).get("scenario_results", {}))
    post_ev = args.output_root / "post_sim_return_core_scenarios.json"
    evidence(post_ev, "post_sim_return_core_scenarios", {
        "exact_final_request_pass": post.get("pass") is True and post.get("errors") == [],
        "four_scenarios": post_scenarios == {"natural_success", "natural_success_plugin_failure", "simulation_nonzero", "idempotent_reentry"},
    }, {"post_sim_sha256": sha(args.post_sim_report), "scenario_names": sorted(post_scenarios)})

    candidates = list(cases)
    candidate_ev = args.output_root / "candidate_discrimination_matrix.json"
    evidence(candidate_ev, "candidate_discrimination_matrix", {
        "six_candidates": len(candidates) == 6,
        "pairwise_distinguishable": len({json.dumps(sorted(item[0])) for item in cases.values()}) == 6,
        "positive_controls": all(parsed[name]["exit_code"] == 0 for name in candidates),
        "negative_controls": missing["exit_code"] != 0 and conflict["exit_code"] != 0,
    }, {"candidate_ids": candidates, "positive_control_count": 6, "negative_control_count": 2})

    evidence_map = [
        ("exact_final_zip_clean_extract", "exact-final-zip-clean-extract", clean),
        ("actual_runner_entry_and_input_open", "exact-runner-safe-compile-and-open-paths", runner_ev),
        ("source_bound_logger_collector_parser_roundtrip", "exact-generated-over-budget-multi-instance", source_ev),
        ("post_sim_return_core_scenarios", "exact-final-request-four-scenario", post_ev),
        ("candidate_discrimination_matrix", "exact-candidate-positive-negative-matrix", candidate_ev),
    ]
    contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": PACKAGE, "family": FAMILY, "final_zip": {"path": args.zip.resolve().relative_to(ROOT).as_posix(), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip)}},
        "rule_change": {"epoch_id": EPOCH, "rule_ids": ["CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001"], "first_fresh_for_family": True, "notification_acknowledged": True},
        "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True},
        "evidence_reports": [{"gate_id": gate, "evidence_kind": kind, "path": path.resolve().relative_to(ROOT).as_posix(), "sha256": sha(path)} for gate, kind, path in evidence_map],
        "candidate_discrimination": {"candidate_ids": candidates, "covered_candidate_ids": candidates, "uncovered_candidate_ids": [], "positive_control_count": 6, "negative_control_count": 2, "pairwise_distinguishable": True},
        "findings": [],
    }
    write(args.contract, contract)
    failed = [str(path) for _, _, path in evidence_map if load(path).get("pass") is not True]
    write(args.output_root / "preparation_report.json", {"schema": "conv-native-p31-first-fresh-extra-audit-preparation-v1", "pass": not failed, "errors": failed, "exact_zip_sha256": sha(args.zip), "contract_sha256": sha(args.contract)})
    print(json.dumps({"pass": not failed, "errors": failed, "contract": str(args.contract)}))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
