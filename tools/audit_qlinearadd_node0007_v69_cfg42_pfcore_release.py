#!/usr/bin/env python3
"""Run the full current QAdd release audit for v69 and bind v68 analysis."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v69_pfc"
OUT = ROOT / "outputs/qlinearadd_node0007_v69_pfc_release"
ANALYSIS_OUT = ROOT / "outputs/qlinearadd_node0007_v68_return_r1786853531805017272_3183291"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    path = ROOT / "tools/audit_qlinearadd_node0007_v68_cfg42_tick_release.py"
    source = path.read_text(encoding="utf-8")
    replacements = [
        ('r5_qadd_n7_tailround_lanephase_v68_cfg42_t2', PACKAGE),
        ('PRIOR = "r5_qadd_n7_tailround_lanephase_v67_cfg42_tg"', 'PRIOR = "r5_qadd_n7_tailround_lanephase_v68_cfg42_t2"'),
        ('PRIOR_SHA = "dbd18a58144321cdb252a9edf17b3fdc7d4087a00d6458d49bdb5d1a75443740"', 'PRIOR_SHA = "449e07e917bca6ff406bd94804903375e24d51b74b5c20762dc53e110ff228f4"'),
        ('EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3+qadd-pretarget-safety-pulse-v1+runtime-v3-pid-identity"', 'EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3+qadd-precompile-core-capture-v1"'),
        ('OUT = ROOT / "outputs/qlinearadd_node0007_v68_cfg42_tick_release"', 'OUT = ROOT / "outputs/qlinearadd_node0007_v69_pfc_release"'),
        ('tools/validate_qlinearadd_node0007_v68_cfg42_tick.py', 'tools/validate_qlinearadd_node0007_v69_cfg42_pfcore.py'),
        ('qlinearadd_node0007_tb_vcd_causal_cone_v68.svh', 'qlinearadd_node0007_tb_vcd_causal_cone_v69.svh'),
        ('qlinearadd_node0007_tb_vcd_live_supervision_v68.py', 'qlinearadd_node0007_tb_vcd_live_supervision_v69.py'),
        ('qlinearadd_node0007_tb_vcd_finalize_v68.py', 'qlinearadd_node0007_tb_vcd_finalize_v69.py'),
        ('codex_qadd_tb_vcd_causal_cone_v68', 'codex_qadd_tb_vcd_causal_cone_v69'),
        ('qadd-v68', 'qadd-v69'),
        ('QAdd v68', 'QAdd v69'),
        ('round_index\\"] == 2', 'round_index\\"] == 3'),
        ('v67 proved exact 4/2 materialization, production compile and fast pretarget execution, but same-time safety snapshots left appended VCD time static and caused a package-local semantic-v5 freeze before target entry.', 'v68 preserved exact 4/2 and reached package runtime preflight, but the third attempt stopped before production compile and omitted preflight stdout/stderr/exit and the true first error.'),
        ('Preserve exact 4/2 and the full 64-signal causal target; make each transport-only pretarget pulse span a real owner edge, retain continuous unbounded target capture, and bind process ownership to PID plus start time.', 'Preserve the exact v68 functional/diagnostic package and capture package-preflight stdout, stderr, exit, runner stage and first error before retrying the unchanged target.'),
    ]
    for old, new in replacements:
        if old not in source:
            raise RuntimeError(f"v68 release-audit adapter anchor drifted: {old}")
        source = source.replace(old, new)
    namespace: dict[str, Any] = {"__name__": "qadd_v69_full_release_audit", "__file__": str(path)}
    exec(compile(source, str(path), "exec"), namespace)
    base_exit = int(namespace["main"]())

    base_report = OUT / "gates/final_zip_release_audit.json"
    exact_report = OUT / "gates/v69_exact.json"
    base_value = json.loads(base_report.read_text(encoding="utf-8")) if base_report.is_file() else {}
    exact_value = json.loads(exact_report.read_text(encoding="utf-8")) if exact_report.is_file() else {}
    analysis = ANALYSIS_OUT / "formal_return_analysis.json"
    audit = ANALYSIS_OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_RECURRING_ESCAPE.json"
    escalation = ANALYSIS_OUT / "SHARED_RULE_AUDIT_ESCALATION.json"
    package = OUT / f"{PACKAGE}.zip"
    errors = []
    if base_exit != 0 or base_value.get("pass") is not True:
        errors.append("full_current_release_audit")
    if exact_value.get("pass") is not True:
        errors.append("v69_precompile_core_exact_gate")
    report = {
        "schema": "qadd-v69-final-release-conjunction-v1",
        "role_id": "family.qlinearadd",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": PACKAGE,
        "full_current_release_audit": identity(base_report),
        "precompile_core_exact_gate": identity(exact_report),
        "source_return_analysis": identity(analysis),
        "recurring_package_build_failure_rule_audit": identity(audit),
        "shared_rule_audit_escalation": identity(escalation),
        "package": identity(package),
        "storage_manager_called": False,
        "server_actions_performed": [],
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE_STORAGE_WAIT_MAINLINE_SERIAL_RELEASE" if not errors else "LOCAL_GATE_FAILURE",
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "All current local exact-package gates only; no production compile/simulation, dynamic 4/2 validation, natural terminal, Formal-D or E3-E5 claim.",
    }
    target = OUT / "gates/final_release_conjunction_v69.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"package_id": PACKAGE, "pass": report["pass"], "errors": errors}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
