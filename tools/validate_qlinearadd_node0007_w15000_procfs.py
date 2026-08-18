#!/usr/bin/env python3
"""Validate one exact post-v73 QAdd 15000s/procfs successor."""

from __future__ import annotations

import argparse
import ast
import ast
import copy
import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PRIOR = "r5_qadd_n7_tailround_lanephase_v73_w8400v7"
PRIOR_SHA = "0cd165a36014e878e507dfc3e810d0271c1e41e1484ca7d5d8e248f8330be18f"
RETURN_SHA = "a65425c43962ee172bf4583b4a114b0a5123d0a19eb20a80860c19ac52e2f23c"
ANALYSIS_SHA = "f0e7d0298d80c233041be6dd26fda8c6aaaabcca6353586f31cd94cc063bc432"
PASS_SHA = "17c0aa3e4d62e45c3cb196700c968d1a3648ed0a6d4ef752ac8cbfa9e9066a04"
ACTIVATION_SHA = "fbe6416d667def0dbf46976e0d7310f0d6dee1004c05c481c9cf2c043b243abf"
GUARD_SHA = "e77e4bd32005f7621f0ece3be7e2c8c2d6d6f07162f72c740f15b0b49839703c"


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


def file_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def zip_tree_exact(package: str, tree: Path, package_zip: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    with zipfile.ZipFile(package_zip) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"ZIP CRC failure: {bad}")
        names = [name for name in archive.namelist() if not name.endswith("/")]
        expected = {f"{package}/{path.relative_to(tree).as_posix()}" for path in tree.rglob("*") if path.is_file()}
        if set(names) != expected or len(names) != len(set(names)):
            errors.append("ZIP/tree exact member set mismatch")
        for name in names:
            relative = Path(*Path(name).parts[1:])
            if archive.read(name) != (tree / relative).read_bytes():
                errors.append(f"ZIP/tree bytes differ: {name}")
                break
    return not errors, errors


def supervisor_checks(source: str) -> dict[str, bool]:
    tree = ast.parse(source)
    known = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "known"
    ]
    return {
        "wall_exact_15000": source.count("WALL_SECONDS = 15000.0") == 1 and "WALL_SECONDS = 8400.0" not in source,
        "pid_start_time_map": len(known) == 1 and isinstance(known[0].value, ast.Dict),
        "childless_procfs_helper": "PROCFS_NO_CHILD_ENUMERATOR" in source and "_PROCFS.ps_table()" in source,
        "subprocess_ps_forbidden": 'subprocess.run(["ps"' not in source and "command=[\"ps\"" not in source,
        "pid_reuse_protected": '"pid_reuse_protection": True' in source,
        "identity_receipt": all(token in source for token in ("child_process_identity", "owned_process_identities_remaining", "start_time_ticks")),
        "fresh_reap_deadlines": source.count("reap_deadline = time.monotonic() + 60.0") >= 2,
        "kill_timestamp_bound": source.count("last_kill_host_monotonic_ns = time.monotonic_ns()") >= 3,
        "fresh_deadline_origin": '"post_kill_reap_deadline_origin": "FRESH_AFTER_LAST_KILL"' in source,
        "stubborn_descendant_fail_closed": 'errors.append("owned simulator descendants remain after TERM/WAIT/KILL/reap")' in source,
        "runtime_admission_returned": '"runtime_budget_admission": json.loads(' in source,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--repeat-zip", type=Path, required=True)
    parser.add_argument("--prior-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = args.package_id
    tree = args.tree.resolve()
    package_zip = args.zip.resolve()
    repeat_zip = args.repeat_zip.resolve()
    prior_zip = args.prior_zip.resolve()
    manifest = load(tree / "TEST_PACKAGE_MANIFEST.json")
    selector = load(tree / "contracts/server_diagnostic_mode_selector.json")
    binding = load(tree / "contracts/server_family_dispatch_mode_binding.json")
    contract_path = tree / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    contract = load(contract_path)
    admission_path = tree / "diagnostics/runtime_budget_admission.json"
    admission = load(admission_path)
    request = load(tree / "contracts/server_post_sim_return_request.json")
    allow = load(tree / "RETURN_ALLOWLIST.json")
    live_rel = next(path.relative_to(tree).as_posix() for path in tree.glob("package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v*.py") if "v69" not in path.name)
    source = (tree / live_rel).read_text(encoding="utf-8")
    admission_tool = import_module(ROOT / "tools/server_runtime_budget_admission.py", "qadd_w15k_admission")
    causal_tool = import_module(ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py", "qadd_w15k_causal")
    zip_ok, zip_errors = zip_tree_exact(package, tree, package_zip)
    source_checks = supervisor_checks(source)
    finalizer_path = tree / "package_tools/qlinearadd_node0007_tb_vcd_finalize_v80.py"
    finalizer_source = finalizer_path.read_text(encoding="utf-8")

    def alias_names(text: str) -> list[str]:
        parsed = ast.parse(text)
        for node in parsed.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "CANONICAL_VCD_ALIASES"
                for target in node.targets
            ):
                if isinstance(node.value, (ast.Tuple, ast.List)):
                    return [
                        item.value for item in node.value.elts
                        if isinstance(item, ast.Constant) and isinstance(item.value, str)
                    ]
        return []

    canonical_aliases = [
        "catalog.json", "candidate_matrix.json", "tb_source.json", "elaboration.json",
        "runtime.json", "return_manifest.json", "finalization_receipt.json",
    ]
    producer_tokens = [
        "shutil.copyfile(catalog_path, vcd_evidence / CANONICAL_VCD_ALIASES[0])",
        "shutil.copyfile(matrix_path, vcd_evidence / CANONICAL_VCD_ALIASES[1])",
        "atomic_json(vcd_evidence / CANONICAL_VCD_ALIASES[2]",
        "atomic_json(vcd_evidence / CANONICAL_VCD_ALIASES[3]",
        "atomic_json(vcd_evidence / CANONICAL_VCD_ALIASES[4]",
        "atomic_json(vcd_evidence / CANONICAL_VCD_ALIASES[5]",
        "vcd_evidence / CANONICAL_VCD_ALIASES[6]",
    ]
    aliases_exact = alias_names(finalizer_source) == canonical_aliases
    producer_tokens_exact = all(finalizer_source.count(token) == 1 for token in producer_tokens)
    deleted_alias_negatives = {}
    for alias in canonical_aliases:
        mutated = finalizer_source.replace(f'    "{alias}",\n', "", 1)
        deleted_alias_negatives[alias] = alias_names(mutated) != canonical_aliases

    wrong_source = copy.deepcopy(admission)
    wrong_source["source_measurement"]["source_return_sha256"] = "0" * 64
    wrong_wall = copy.deepcopy(admission)
    wrong_wall["selected_wall_ceiling_seconds"] = 14999
    wrong_admission_absolute = copy.deepcopy(admission)
    wrong_admission_absolute["absolute_maximum_wall_seconds"] = 15000
    wrong_absolute = copy.deepcopy(contract)
    wrong_absolute["budget"]["absolute_maximum_wall_seconds"] = 15000
    wrong_predecessor = copy.deepcopy(contract)
    wrong_predecessor["diagnostic_round"]["evolution"]["predecessor"]["contract_sha256"] = "0" * 64
    required_return = [
        "source_package/runtime_budget_admission.json",
        "source_package/procfs_process_identity_reap_contract.json",
        "source_package/v73_formal_return_analysis.json",
        "source_package/v73_formal_mainline_receipt.json",
        "source_package/v73_RULE_GAP_AUDIT.json",
        "source_package/qadd_source_bound_wall_15000_activation_receipt.json",
        "source_package/family_dispatch_mode_binding_activation_receipt.json",
        "source_package/qadd_tbvcd_semantic8_validator_coherence_receipt.json",
        "source_package/server_family_dispatch_mode_binding.json",
        "source_package/v74_local_build_failed_path_budget.json",
        "source_package/v75_dispatch_identity_mismatch.json",
        "source_package/v76_staging_dispatch_family_failure.json",
        "source_package/v77_tbvcd_semantic8_gate_failure.json",
        "source_package/PACKAGE_BUILD_FAILURE_RULE_AUDIT_V74_V75.json",
        "source_package/qualified_progress_contract.json",
        "source_package/final_zip_rule_self_audit.json",
        "source_package/qadd_runtime_budget_selected_absolute_coherence_receipt.json",
        "source_package/v78_independent_audit_failure.json",
    ]
    request_map = {row["archive"]: row for row in request["core_entries"]}
    predecessor = contract["diagnostic_round"]["evolution"]["predecessor"]
    guards = admission.get("independent_operational_guards", {})
    checks = {
        "prior_v73_byte_frozen": prior_zip.stat().st_size == 108_809_782 and sha(prior_zip) == PRIOR_SHA,
        "deterministic_exact_zip": package_zip.read_bytes() == repeat_zip.read_bytes(),
        "zip_tree_exact": zip_ok,
        "manifest_exact_set": manifest.get("files") == file_map(tree),
        "package_identity": all(manifest.get(key) == package for key in ("package_id", "package_identity", "install_name")),
        "manifest_semantics_8_6_5_1": manifest.get("gate_semantic_versions") == {"tb_vcd_bounded_causal_cone_final_zip": 8, "first_fresh_extra_audit": 6, "runtime_layout": 5, "family_dispatch_mode_binding_final_zip": 1},
        "mode_selector": selector.get("package_id") == package and selector.get("family") == "qlinearadd" and selector.get("selected_mode") == "TB_VCD_BOUNDED_CAUSAL_CONE",
        "dispatch_binding": binding.get("package_id") == package and binding.get("family_role_id") == "family.qlinearadd" and binding.get("diagnostic_mode") == selector.get("selected_mode"),
        "admission_pass": admission_tool.validate(admission).get("pass") is True,
        "admission_source_return": admission.get("source_measurement", {}).get("source_return_sha256") == RETURN_SHA,
        "admission_source_analysis": admission.get("source_measurement", {}).get("source_formal_analysis_sha256") == ANALYSIS_SHA,
        "projection_and_selected": admission.get("projection", {}).get("recommended_wall_ceiling_seconds") == 11862 and admission.get("selected_wall_ceiling_seconds") == 15000,
        "admission_absolute_maximum_86400": admission.get("absolute_maximum_wall_seconds") == 86400,
        "budget_end_to_end": contract.get("budget", {}).get("wall_ceiling_seconds") == 15000 and contract.get("budget", {}).get("absolute_maximum_wall_seconds") == 86400 and contract.get("budget", {}).get("runtime_budget_admission_sha256") == sha(admission_path),
        "nested_final_self_audit_closed": manifest.get("final_zip_rule_self_audit", {}).get("status") == "FINAL_EXACT_ZIP_AND_FIRST_FRESH_AUDIT_PASS",
        "nested_final_self_audit_receipt_exact": (
            isinstance(manifest.get("final_zip_rule_self_audit", {}).get("receipt_path"), str)
            and (tree / manifest["final_zip_rule_self_audit"]["receipt_path"]).is_file()
            and sha(tree / manifest["final_zip_rule_self_audit"]["receipt_path"]) == manifest["final_zip_rule_self_audit"].get("receipt_sha256")
        ),
        "qualified_progress_contract": load(tree / "diagnostics/qualified_progress_contract.json").get("pass") is True,
        "held_level_progress_removed": all(token not in (tree / contract["execution"]["tb_source_path"]).read_text(encoding="utf-8") for token in ("wire tbvcd_progress_event = (|sig_buf_wr_en) || (|sig_buf_rd_en) || sig_mrm_rvalid || sig_arm_rvalid || sig_slice_finish", "wire tbvcd_output_event = sig_mrm_rvalid || sig_arm_rvalid")),
        "guards_unchanged": guards.get("vcd_operational_budget_bytes") == 8_000_000_000 and guards.get("return_budget_bytes") == 10_000_000_000 and all(guards.get(key) is True for key in ("disk_space_guard_enabled", "growth_projection_enabled", "write_failure_guard_enabled", "quota_guard_enabled", "signal_guard_enabled", "plateau_protection_unchanged", "return_integrity_fail_closed")),
        "predecessor_exact": predecessor.get("package_id") == PRIOR and predecessor.get("round_index") == 5 and predecessor.get("published_gate_semantic_version") == "7" and predecessor.get("published_pass_receipt_sha256") == PASS_SHA,
        "source_bound_shape": len(contract.get("signals", [])) == 64 and len(contract.get("role_coverage", [])) == 41 and len(contract.get("boundaries", [])) == 4 and len(contract.get("candidates", [])) == 7,
        "canonical_runtime_helper": (tree / "package_tools/server_tb_vcd_runtime_supervision.py").read_bytes() == (ROOT / "tools/server_tb_vcd_runtime_supervision.py").read_bytes(),
        "canonical_layout_helper": (tree / "package_tools/server_package_runtime_layout.py").read_bytes() == (ROOT / "tools/server_package_runtime_layout.py").read_bytes(),
        "canonical_post_sim_helper": (tree / "package_tools/server_post_sim_return.py").read_bytes() == (ROOT / "tools/server_post_sim_return.py").read_bytes(),
        "canonical_procfs_helper": sha(tree / "package_tools/server_observer_operational_guard_v2.py") == GUARD_SHA,
        "supervisor_controls": all(source_checks.values()),
        "wrong_source_rejected": admission_tool.validate(wrong_source).get("pass") is False,
        "wrong_wall_rejected": admission_tool.validate(wrong_wall).get("pass") is False,
        "wrong_admission_absolute_rejected": admission_tool.validate(wrong_admission_absolute).get("pass") is False,
        "wrong_absolute_max_rejected": causal_tool.validate_contract(wrong_absolute, tree).get("pass") is False,
        "wrong_predecessor_sha_rejected": causal_tool.validate_contract(wrong_predecessor, tree).get("pass") is False,
        "return_core_entries": all(path in request_map and request_map[path].get("required") is True for path in required_return),
        "return_allowlist_entries": all(path in allow.get("required", []) and f"{package}_return/{path}" in allow.get("required", []) for path in required_return),
        "canonical_vcd_alias_set_exact": aliases_exact,
        "canonical_vcd_alias_producer_tokens_exact": producer_tokens_exact,
        "deleted_alias_producer_negatives_fail_closed": all(deleted_alias_negatives.values()),
        "runner_validates_finalization_alias_identities": all(
            token in (tree / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
            for token in (
                "qadd-tb-vcd-finalization-guard-receipt-v1",
                "set(mapped)!=expected",
                "hashlib.sha256(data).hexdigest()",
                "set(manifest_rows)!=expected-{'return_manifest.json'}",
            )
        ),
        "functional_rtl_absent": not (tree / "rtl").exists(),
    }
    errors = [name for name, passed in checks.items() if not passed] + zip_errors
    result = {
        "schema": "qadd-w15000-procfs-exact-validation-v1",
        "package_id": package,
        "checks": checks,
        "supervisor_source_checks": source_checks,
        "canonical_alias_producer_negative_controls": deleted_alias_negatives,
        "package": {"path": package_zip.as_posix(), "bytes": package_zip.stat().st_size, "sha256": sha(package_zip)},
        "prior_v73": {"path": prior_zip.as_posix(), "bytes": prior_zip.stat().st_size, "sha256": sha(prior_zip)},
        "schema_enabled_python": str(Path(__import__("sys").executable).resolve()),
        "storage_manager_called": False,
        "server_actions_performed": [],
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "Local exact package/budget/procfs/return gates only; no production target, natural terminal, Formal-D or E3-E5 claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"package_id": package, "pass": result["pass"], "errors": errors}, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
