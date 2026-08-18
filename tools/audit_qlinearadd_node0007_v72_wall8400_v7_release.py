#!/usr/bin/env python3
"""Run every current exact/release/first-fresh gate for QAdd v72."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v72_wall8400_v7"
OUT = ROOT / "outputs/qlinearadd_node0007_v72_release"
ANALYSIS_OUT = ROOT / "outputs/qlinearadd_node0007_v70_return_r1786935559104408108_3677225"
EPOCH = "qadd-source-bound-wall-8400-v1+tb-vcd-predecessor-semantic-compatibility-v7"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    source_path = ROOT / "tools/audit_qlinearadd_node0007_v70_pidmapfix_release.py"
    source = source_path.read_text(encoding="utf-8")
    replacements = [
        ('PACKAGE = "r5_qadd_n7_tailround_lanephase_v70_pmapfix"', f'PACKAGE = "{PACKAGE}"'),
        ('OUT = ROOT / "outputs/qlinearadd_node0007_v70_pmapfix_release"', 'OUT = ROOT / "outputs/qlinearadd_node0007_v72_release"'),
        ('ANALYSIS_OUT = ROOT / "outputs/qlinearadd_node0007_v69_return_r1786886207604661595_3464688"', 'ANALYSIS_OUT = ROOT / "outputs/qlinearadd_node0007_v70_return_r1786935559104408108_3677225"'),
        ('PRIOR = "r5_qadd_n7_tailround_lanephase_v69_pfc"', 'PRIOR = "r5_qadd_n7_tailround_lanephase_v70_pmapfix"'),
        ('PRIOR_SHA = "2f4196597f12e424df97a94af2e614e413dea8032a04752c0c97fc57ec1d8597"', 'PRIOR_SHA = "7df37603b1d6ccab664301f8e998d8eacf1e114c434c56eb17b8904b210eaac8"'),
        ('EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3+qadd-supervisor-pidmap-v1"', f'EPOCH = "{EPOCH}"'),
        ('tools/validate_qlinearadd_node0007_v70_pidmapfix.py', 'tools/validate_qlinearadd_node0007_v72_wall8400_v7.py'),
        ('tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v70.svh', 'tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v72.svh'),
        ('package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v70.py', 'package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v72.py'),
        ('package_tools/qlinearadd_node0007_tb_vcd_finalize_v70.py', 'package_tools/qlinearadd_node0007_tb_vcd_finalize_v72.py'),
        ('codex_qadd_tb_vcd_causal_cone_v70', 'codex_qadd_tb_vcd_causal_cone_v72'),
        ('qadd-v70', 'qadd-v72'),
        ('qadd_v70', 'qadd_v72'),
        ('QAdd v70', 'QAdd v72'),
        ('outputs/qlinearadd_node0007_v69_return_r1786886207604661595_3464688/formal_return_analysis.json', 'outputs/qlinearadd_node0007_v70_return_r1786935559104408108_3677225/formal_return_analysis.json'),
        ('outputs/qlinearadd_node0007_v69_return_r1786886207604661595_3464688/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json', 'outputs/qlinearadd_node0007_v70_return_r1786935559104408108_3677225/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json'),
        ('ROOT / "outputs/qlinearadd_node0007_v69_pfc_release/r5_qadd_n7_tailround_lanephase_v69_pfc.zip"', 'ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tailround_lanephase_v70_pmapfix.zip"'),
        ('outputs/qlinearadd_node0007_v70_pmapfix_release/gate_runtime/python', 'outputs/qlinearadd_node0007_v70_pmapfix_release/gate_runtime/python'),
        ('RULE_CONFIRMATION_NO_CHANGE', 'RULE_DELTA_PROPOSAL_CONSUMED_BY_QADD_SOURCE_BOUND_WALL_8400_AND_SEMANTIC_V7'),
        ('contract["diagnostic_round"]["round_index"] == 4', 'contract["diagnostic_round"]["round_index"] == 5'),
        ('v69 passed package preflight and production compile, then uniquely failed in the package-local supervisor after simv Popen because its PID/start-time map was initialized as a set; target and VCD were not reached.', 'v70 reached production simulation and 19/30 advancing pretarget transfers; v71 exposed only local semantic-compatibility/finalizer/gate-runtime defects and remains nonpublishable.'),
        ('Preserve exact v69 4/2/config/workload/TB causal semantics while repairing the PID/start-time map and returning supervisor stdout/stderr/exit for the unchanged target.', 'Preserve exact v70 validated 4/2/config/workload/TB causal semantics while applying current semantic-v7 predecessor compatibility, complete finalizer propagation and the existing schema-enabled repository gate runtime.'),
        ('final_release_conjunction_v70.json', 'final_release_conjunction_v72.json'),
    ]
    for old, new in replacements:
        if old not in source:
            raise RuntimeError(f"v70 release adapter anchor drifted: {old}")
        source = source.replace(old, new)
    namespace: dict[str, Any] = {"__name__": "qadd_v72_full_release_audit", "__file__": str(source_path)}
    exec(compile(source, str(source_path), "exec"), namespace)
    base_exit = int(namespace["main"]())
    reports = {
        "full_current_release_audit": OUT / "gates/final_zip_release_audit.json",
        "wall8400_semantic_v7_exact_gate": OUT / "gates/target_capture_exact.json",
        "current_epoch_first_fresh": OUT / "gates/first_fresh_validation.json",
        "runtime_budget_admission": OUT / "build" / PACKAGE / "diagnostics/runtime_budget_admission.json",
    }
    errors = []
    for name, path in reports.items():
        if not path.is_file() or load(path).get("pass") is not True:
            errors.append(name)
    if base_exit != 0:
        errors.append("full_current_release_audit_exit")
    package = OUT / f"{PACKAGE}.zip"
    report = {
        "schema": "qadd-v72-final-release-conjunction-v1", "role_id": "family.qlinearadd",
        "owner_epoch": 2, "registry_epoch": 6, "package_id": PACKAGE, "activation_epoch": EPOCH,
        **{name: identity(path) for name, path in reports.items()},
        "source_return_analysis": identity(ANALYSIS_OUT / "formal_return_analysis.json"),
        "package_build_failure_rule_audit": identity(ANALYSIS_OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"),
        "package": identity(package), "gate_schema_runtime": "outputs/qlinearadd_node0007_v70_pmapfix_release/gate_runtime/python",
        "storage_manager_called": False, "server_actions_performed": [],
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE_STORAGE_WAIT_MAINLINE_SERIAL_RELEASE" if not errors else "LOCAL_GATE_FAILURE",
        "pass": not errors, "errors": sorted(set(errors)),
        "claim_boundary": "All current local exact-package gates only; no production target, dynamic 4/2 validation, natural terminal, Formal-D or E3-E5 claim.",
    }
    write(OUT / "gates/final_release_conjunction_v72.json", report)
    print(json.dumps({"package_id": PACKAGE, "pass": report["pass"], "errors": report["errors"]}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
