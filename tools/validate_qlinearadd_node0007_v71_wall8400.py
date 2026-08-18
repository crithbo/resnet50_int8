#!/usr/bin/env python3
"""Validate exact QAdd v71 runtime-budget and fresh post-KILL reap surfaces."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
PACKAGE = "r5_qadd_n7_tailround_lanephase_v71_wall8400"
PRIOR = "r5_qadd_n7_tailround_lanephase_v70_pmapfix"
PRIOR_SHA = "7df37603b1d6ccab664301f8e998d8eacf1e114c434c56eb17b8904b210eaac8"
RETURN_SHA = "ae317f36edd28ecf0b9c3bf7d5c7734612d18755932f9fedb371a1203addb369"
LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v71.py"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def import_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest_files(tree: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(tree).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(tree.rglob("*"))
        if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def exact_zip_tree(tree: Path, package_zip: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    with zipfile.ZipFile(package_zip) as archive:
        if archive.testzip() is not None:
            errors.append("ZIP CRC failure")
        names = [name for name in archive.namelist() if not name.endswith("/")]
        expected = {f"{PACKAGE}/{path.relative_to(tree).as_posix()}" for path in tree.rglob("*") if path.is_file()}
        if set(names) != expected or len(names) != len(set(names)):
            errors.append("ZIP/tree exact member set mismatch")
        for name in names:
            relative = Path(*Path(name).parts[1:])
            if archive.read(name) != (tree / relative).read_bytes():
                errors.append(f"ZIP/tree bytes differ: {name}")
                break
    return not errors, errors


def supervisor_source_checks(source: str) -> dict[str, bool]:
    tree = ast.parse(source)
    known = [node for node in ast.walk(tree) if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "known"]
    return {
        "wall_exact_8400": source.count("WALL_SECONDS = 8400.0") == 1 and "WALL_SECONDS = 3600.0" not in source,
        "pid_map_dict": len(known) == 1 and isinstance(known[0].value, ast.Dict),
        "runtime_admission_loaded": "diagnostics/runtime_budget_admission.json" in source and '"runtime_budget_admission":' in source,
        "term_deadline_distinct": "term_deadline = time.monotonic() + 30.0" in source,
        "fresh_reap_after_last_kill": source.count("reap_deadline = time.monotonic() + 60.0") >= 2 and "post_kill_reap_deadline_host_monotonic_ns = int(reap_deadline * 1_000_000_000)" in source,
        "kill_timestamp_bound": source.count("last_kill_host_monotonic_ns = time.monotonic_ns()") >= 3,
        "receipt_origin_bound": '"post_kill_reap_deadline_origin": "FRESH_AFTER_LAST_KILL" if last_kill_host_monotonic_ns is not None else "NOT_APPLICABLE"' in source,
        "stubborn_survivor_incomplete": "post_kill_reap_completed = not remaining" in source and 'errors.append("owned simulator descendants remain after TERM/WAIT/KILL/reap")' in source,
    }


def process_negative_control(tree: Path, admission: dict[str, Any]) -> dict[str, Any]:
    evaluator = import_module(tree / "package_tools/server_tb_vcd_runtime_supervision.py", "qadd_v71_runtime_evaluator")
    live = import_module(tree / LIVE, "qadd_v71_live_supervisor")
    _module, authority = live.load_evaluator(tree / "package_tools/server_tb_vcd_runtime_supervision.py")
    phase = live.phase_authority(tree / "package_tools/server_tb_vcd_runtime_supervision.py")
    request = {
        "package_id": PACKAGE,
        "execution_id": "negative",
        "attempt_id": "a-negative",
        "started": True,
        "actual_argv_sha256": "0" * 64,
        "catalog_sha256": "0" * 64,
        "candidate_matrix_sha256": "0" * 64,
        "tb_source_sha256": "0" * 64,
        "elaboration_sha256": "0" * 64,
        "samples": [{
            "seq": 0, "wall_seconds": 1, "sim_cycles": 1, "owner_clock_cycles": 1,
            "sim_time_ticks": 1, "appended_vcd_timestamp_ticks": 1, "vcd_bytes": 1,
            "causal_progress_events": 0, "qualified_progress_counters": {},
            "causal_state_digest": "a", "global_progress_witness": {}, "unresolved_xz": False,
            "disk_space_ok": True, "write_ok": True, "quota_ok": True,
        }],
        "runtime_budget_admission": admission,
        "candidate_catalog_complete": True,
        "unresolved_xz": False,
        "flush": {"dumpoff": False, "dumpflush": False, "closed": False},
        "process_tree": {
            "term_sent": True,
            "wait_completed": True,
            "kill_sent_if_needed": True,
            "all_reaped": False,
            "post_kill_reap_deadline_origin": "TERM_DEADLINE_REUSED",
            "last_kill_host_monotonic_ns": 200,
            "post_kill_reap_deadline_host_monotonic_ns": 100,
            "post_kill_reap_completed": False,
        },
        "heartbeat_contract": {"source": "APPENDED_VCD_TIMESTAMP", "width_bits": 64, "signed": False, "cadence_cycles": 16384},
        "decision_authority": authority,
        "dumpoff_consistency_authority": phase,
        "archive_timestamp_receipt": None,
        "target_entry_observed": False,
        "target_diagnostic_claim": False,
        "vcd_identity": None,
        "return_exact_set": None,
        "live_diagnostics": {"downstream_state_source": "LIVE_SAME_ATTEMPT", "first_error_source": "LIVE_SAME_ATTEMPT", "stale_evidence_absent": True},
    }
    receipt = evaluator.evaluate(request)
    errors = receipt.get("errors", [])
    return {
        "stubborn_or_expired_reap_fails_closed": any("post-KILL reap" in item for item in errors),
        "all_reaped_false": receipt.get("process_tree", {}).get("all_reaped") is False,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--repeat-zip", type=Path, required=True)
    parser.add_argument("--prior-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tree = args.tree.resolve()
    package_zip = args.zip.resolve()
    repeat_zip = args.repeat_zip.resolve()
    prior_zip = args.prior_zip.resolve()
    manifest = load(tree / "TEST_PACKAGE_MANIFEST.json")
    contract = load(tree / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    admission_path = tree / "diagnostics/runtime_budget_admission.json"
    admission = load(admission_path)
    admission_tool = import_module(ROOT / "tools/server_runtime_budget_admission.py", "qadd_v71_budget_admission")
    selector = load(tree / "contracts/server_diagnostic_mode_selector.json")
    request = load(tree / "contracts/server_post_sim_return_request.json")
    allow = load(tree / "RETURN_ALLOWLIST.json")
    source = (tree / LIVE).read_text(encoding="utf-8")
    source_checks = supervisor_source_checks(source)
    expired_mutant = source.replace("reap_deadline = time.monotonic() + 60.0", "reap_deadline = term_deadline")
    admission_wrong_source = copy.deepcopy(admission)
    admission_wrong_source["source_measurement"]["source_return_sha256"] = "0" * 64
    admission_wrong_wall = copy.deepcopy(admission)
    admission_wrong_wall["selected_wall_ceiling_seconds"] = 8399
    zip_ok, zip_errors = exact_zip_tree(tree, package_zip)
    required_return = [
        "source_package/runtime_budget_admission.json",
        "source_package/post_kill_fresh_reap_contract.json",
        "source_package/v70_formal_return_analysis.json",
        "source_package/v70_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json",
        "source_package/qadd_source_bound_wall_8400_activation_receipt.json",
    ]
    request_map = {row["archive"]: row for row in request["core_entries"]}
    process_negative = process_negative_control(tree, admission)
    checks = {
        "prior_v70_byte_frozen": prior_zip.stat().st_size == 108_772_022 and sha(prior_zip) == PRIOR_SHA,
        "deterministic_exact_zip": package_zip.read_bytes() == repeat_zip.read_bytes(),
        "zip_tree_exact": zip_ok,
        "manifest_exact_set": manifest.get("files") == manifest_files(tree),
        "package_manifest_identity": all(manifest.get(key) == PACKAGE for key in ("package_id", "package_identity", "install_name")),
        "manifest_gate_semantics_6_5_5": manifest.get("gate_semantic_versions") == {"tb_vcd_bounded_causal_cone_final_zip": 6, "first_fresh_extra_audit": 5, "runtime_layout": 5},
        "mode_selector_exact": selector.get("package_id") == PACKAGE and selector.get("selected_mode") == "TB_VCD_BOUNDED_CAUSAL_CONE",
        "admission_deterministic_pass": admission_tool.validate(admission).get("pass") is True,
        "admission_source_exact": admission.get("source_measurement", {}).get("source_return_sha256") == RETURN_SHA,
        "admission_projection_8022_selected_8400": admission.get("projection", {}).get("recommended_wall_ceiling_seconds") == 8022 and admission.get("selected_wall_ceiling_seconds") == 8400,
        "contract_budget_bound": contract.get("budget", {}).get("runtime_budget_mode") == "MEASURED_PRETARGET_AWARE" and contract.get("budget", {}).get("wall_ceiling_seconds") == 8400 and contract.get("budget", {}).get("runtime_budget_admission_sha256") == sha(admission_path),
        "independent_guards_unchanged": admission.get("independent_operational_guards") == {"vcd_operational_budget_bytes": 8_000_000_000, "return_budget_bytes": 10_000_000_000, "disk_space_guard_enabled": True, "growth_projection_enabled": True, "write_failure_guard_enabled": True, "quota_guard_enabled": True},
        "source_bound_64_signals": len(contract.get("signals", [])) == 64,
        "current_runtime_helper_exact": (tree / "package_tools/server_tb_vcd_runtime_supervision.py").read_bytes() == (ROOT / "tools/server_tb_vcd_runtime_supervision.py").read_bytes(),
        "current_runtime_layout_helper_exact": (tree / "package_tools/server_package_runtime_layout.py").read_bytes() == (ROOT / "tools/server_package_runtime_layout.py").read_bytes(),
        "current_post_sim_helper_exact": (tree / "package_tools/server_post_sim_return.py").read_bytes() == (ROOT / "tools/server_post_sim_return.py").read_bytes(),
        "supervisor_source_controls": all(source_checks.values()),
        "expired_deadline_source_mutant_rejected": not all(supervisor_source_checks(expired_mutant).values()),
        "wrong_source_return_rejected": admission_tool.validate(admission_wrong_source).get("pass") is False,
        "wrong_wall_rejected": admission_tool.validate(admission_wrong_wall).get("pass") is False,
        "stubborn_descendant_receipt_rejected": process_negative["stubborn_or_expired_reap_fails_closed"] and process_negative["all_reaped_false"],
        "return_core_entries": all(path in request_map and request_map[path].get("required") is True for path in required_return),
        "return_allowlist_entries": all(path in allow.get("required", []) and f"{PACKAGE}_return/{path}" in allow.get("required", []) for path in required_return),
        "functional_rtl_absent": not (tree / "rtl").exists(),
    }
    errors = [name for name, passed in checks.items() if not passed] + zip_errors
    result = {
        "schema": "qadd-v71-wall8400-exact-validation-v1",
        "package_id": PACKAGE,
        "checks": checks,
        "supervisor_source_checks": source_checks,
        "process_negative_control": process_negative,
        "package": {"path": package_zip.as_posix(), "bytes": package_zip.stat().st_size, "sha256": sha(package_zip)},
        "prior_v70": {"path": prior_zip.as_posix(), "bytes": prior_zip.stat().st_size, "sha256": sha(prior_zip)},
        "storage_manager_called": False,
        "server_actions_performed": [],
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "Local exact package/runtime-budget/reap controls only; no production target/4-2/terminal claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"package_id": PACKAGE, "pass": result["pass"], "errors": errors}, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
