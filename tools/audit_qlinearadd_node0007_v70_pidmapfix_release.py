#!/usr/bin/env python3
"""Run current exact-final-ZIP/first-fresh gates for QAdd v70."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v70_pmapfix"
OUT = ROOT / "outputs/qlinearadd_node0007_v70_pmapfix_release"
ANALYSIS_OUT = ROOT / "outputs/qlinearadd_node0007_v69_return_r1786886207604661595_3464688"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    path = ROOT / "tools/audit_qlinearadd_node0007_v67_cfg42_target_capture_release.py"
    source = path.read_text(encoding="utf-8")
    replacements = [
        ('PACKAGE = "r5_qadd_n7_tailround_lanephase_v67_cfg42_tg"', f'PACKAGE = "{PACKAGE}"'),
        ('PRIOR = "r5_qadd_n7_tailround_lanephase_v66_cfg42"', 'PRIOR = "r5_qadd_n7_tailround_lanephase_v69_pfc"'),
        ('PRIOR_SHA = "f9add4a1f54d922fb76fbe7d7b8a72e4965fea0c27546864fb3032bcad8862bc"', 'PRIOR_SHA = "2f4196597f12e424df97a94af2e614e413dea8032a04752c0c97fc57ec1d8597"'),
        ('EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3+qadd-v66-return-target-capture-v1+tb-vcd-adaptive-v4+runtime-v3"', 'EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3+qadd-supervisor-pidmap-v1"'),
        ('OUT = ROOT / "outputs/qlinearadd_node0007_v67_cfg42_tgcap_release"', 'OUT = ROOT / "outputs/qlinearadd_node0007_v70_pmapfix_release"'),
        ('PRIOR_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PRIOR}.zip"', 'PRIOR_ZIP = ROOT / "outputs/qlinearadd_node0007_v69_pfc_release/r5_qadd_n7_tailround_lanephase_v69_pfc.zip"'),
        ('tools/validate_qlinearadd_node0007_v67_cfg42_target_capture.py', 'tools/validate_qlinearadd_node0007_v70_pidmapfix.py'),
        ('tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v67.svh', 'tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v70.svh'),
        ('package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v67.py', 'package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v70.py'),
        ('package_tools/qlinearadd_node0007_tb_vcd_finalize_v67.py', 'package_tools/qlinearadd_node0007_tb_vcd_finalize_v70.py'),
        ('codex_qadd_tb_vcd_causal_cone_v67', 'codex_qadd_tb_vcd_causal_cone_v70'),
        ('qadd-v67', 'qadd-v70'), ('QAdd v67', 'QAdd v70'),
        ('outputs/qlinearadd_node0007_v66_return_r1786770100877714671_2785121/formal_return_analysis.json', 'outputs/qlinearadd_node0007_v69_return_r1786886207604661595_3464688/formal_return_analysis.json'),
        ('outputs/qlinearadd_node0007_v66_return_r1786770100877714671_2785121/RULE_GAP_AUDIT.json', 'outputs/qlinearadd_node0007_v69_return_r1786886207604661595_3464688/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json'),
        ('RULE_CONFIRMATION_NO_PUBLIC_CHANGE', 'RULE_CONFIRMATION_NO_CHANGE'),
        ('Path(r"C:\\Users\\15383\\AppData\\Local\\Temp\\codex_jsonschema_20260809")', 'ROOT / "outputs/qlinearadd_node0007_v70_pmapfix_release/gate_runtime/python"'),
        ('v66 proved exact 4/2 materialization and production compile while pretarget matrix preload advanced; wall ceiling arrived before target entry, so the ordered 0x33333333/0xcccccccc acceptance contract remains dynamically open.', 'v69 passed package preflight and production compile, then uniquely failed in the package-local supervisor after simv Popen because its PID/start-time map was initialized as a set; target and VCD were not reached.'),
        ('Preserve the validated 4/2 lineage and full 64-signal causal target while suppressing full-rate pretarget VCD, retaining periodic safety snapshots, and starting continuous unbounded causal capture before the target-entry marker.', 'Preserve exact v69 4/2/config/workload/TB causal semantics while repairing the PID/start-time map and returning supervisor stdout/stderr/exit for the unchanged target.'),
    ]
    for old, new in replacements:
        if old not in source:
            raise RuntimeError(f"v67 release adapter anchor drifted: {old}")
        source = source.replace(old, new)

    nested_prior_anchor = '''        ('OUT = ROOT / "outputs/qlinearadd_node0007_v65_tbvcdrt3_release"', 'OUT = ROOT / "outputs/qlinearadd_node0007_v70_pmapfix_release"'),\n'''
    nested_prior_replacement = nested_prior_anchor + '''        ('SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PRIOR}.zip"', 'SOURCE = ROOT / "outputs/qlinearadd_node0007_v69_pfc_release/r5_qadd_n7_tailround_lanephase_v69_pfc.zip"'),\n'''
    if nested_prior_anchor not in source:
        raise RuntimeError("nested prior ZIP adapter anchor drifted")
    source = source.replace(nested_prior_anchor, nested_prior_replacement, 1)

    injection_anchor = '''        source = source.replace(old, new)\n    phase_anchor = """def import_module(path: Path, name: str) -> Any:\n'''
    injection = '''        source = source.replace(old, new)\n    refined_negative_replacements = [\n        ('("low_confidence_removal", lambda value: value["diagnostic_round"].update({"round_index": 2, "round_kind": "EVIDENCE_REFINED_SUCCESSOR"}))', '("low_confidence_removal", lambda value: (value["diagnostic_round"]["evolution"]["removed_signal_ids"].append(value["diagnostic_round"]["evolution"]["unchanged_signal_ids"][0]), value["diagnostic_round"]["evolution"]["removal_evidence"].append({"signal_id": value["diagnostic_round"]["evolution"]["unchanged_signal_ids"][0], "reason": "negative control", "confidence": "LOW", "affected_candidate_ids": [], "disposition": "FAMILY_ADAPTIVE_PRUNING"})))'),\n        ('("add_remove_diff_mismatch", lambda value: value["diagnostic_round"]["evolution"]["added_signal_ids"].pop())', '("add_remove_diff_mismatch", lambda value: value["diagnostic_round"]["evolution"]["added_signal_ids"].append("sig_not_in_catalog"))'),\n        ('("candidate_loss", lambda value: value["diagnostic_round"]["evolution"]["candidate_preservation"]["new_candidate_ids"].pop())', '("candidate_loss", lambda value: value["diagnostic_round"]["evolution"]["candidate_preservation"]["preserved_candidate_ids"].pop())'),\n        ('"breadth_v4_round1": contract["diagnostic_round"]["round_index"] == 1 and contract["diagnostic_round"]["round_kind"] == "FIRST_DIAGNOSTIC_ROUND"', '"breadth_v4_round1": contract["diagnostic_round"]["round_index"] == 4 and contract["diagnostic_round"]["round_kind"] == "EVIDENCE_REFINED_SUCCESSOR" and contract["diagnostic_round"]["evolution"]["predecessor"]["package_id"] == PRIOR'),\n    ]\n    for old, new in refined_negative_replacements:\n        if old not in source:\n            raise RuntimeError(f"v70 refined negative-control anchor drifted: {old}")\n        source = source.replace(old, new)\n    phase_anchor = """def import_module(path: Path, name: str) -> Any:\n'''
    if injection_anchor not in source:
        raise RuntimeError("nested release injection anchor drifted")
    source = source.replace(injection_anchor, injection, 1)
    namespace: dict[str, Any] = {"__name__": "qadd_v70_full_release_audit", "__file__": str(path)}
    exec(compile(source, str(path), "exec"), namespace)
    base_exit = int(namespace["main"]())

    base_report = OUT / "gates/final_zip_release_audit.json"
    exact_report = OUT / "gates/target_capture_exact.json"
    base = json.loads(base_report.read_text(encoding="utf-8")) if base_report.is_file() else {}
    exact = json.loads(exact_report.read_text(encoding="utf-8")) if exact_report.is_file() else {}
    analysis = ANALYSIS_OUT / "formal_return_analysis.json"
    audit = ANALYSIS_OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"
    package = OUT / f"{PACKAGE}.zip"
    errors = []
    if base_exit != 0 or base.get("pass") is not True:
        errors.append("full_current_release_audit")
    if exact.get("pass") is not True:
        errors.append("v70_pidmap_exact_gate")
    report = {
        "schema": "qadd-v70-final-release-conjunction-v1", "role_id": "family.qlinearadd", "owner_epoch": 2, "registry_epoch": 6,
        "package_id": PACKAGE, "full_current_release_audit": identity(base_report), "pidmap_exact_gate": identity(exact_report),
        "source_return_analysis": identity(analysis), "package_build_failure_rule_audit": identity(audit), "package": identity(package),
        "storage_manager_called": False, "server_actions_performed": [],
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE_STORAGE_WAIT_MAINLINE_SERIAL_RELEASE" if not errors else "LOCAL_GATE_FAILURE",
        "pass": not errors, "errors": errors,
        "claim_boundary": "All current local exact-package gates only; no production target, dynamic 4/2 validation, natural terminal, Formal-D or E3-E5 claim.",
    }
    target = OUT / "gates/final_release_conjunction_v70.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"package_id": PACKAGE, "pass": report["pass"], "errors": errors}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
