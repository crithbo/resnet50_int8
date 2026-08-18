#!/usr/bin/env python3
"""Bind v69 formal analysis to the locally gated v70 successor."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
V69 = "r5_qadd_n7_tailround_lanephase_v69_pfc"
V70 = "r5_qadd_n7_tailround_lanephase_v70_pmapfix"
RETURN = Path(r"C:\Users\15383\Downloads\r5_qadd_n7_tailround_lanephase_v69_pfc_r1786886207604661595_3464688_return.zip")
SIDECAR = Path(str(RETURN) + ".sha256")
V69_OUT = ROOT / "outputs/qlinearadd_node0007_v69_pfc_release"
ANALYSIS_OUT = ROOT / "outputs/qlinearadd_node0007_v69_return_r1786886207604661595_3464688"
V70_OUT = ROOT / "outputs/qlinearadd_node0007_v70_pmapfix_release"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    try:
        label = path.relative_to(ROOT).as_posix()
    except ValueError:
        label = str(path)
    return {"path": label, "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    analysis_path = ANALYSIS_OUT / "formal_return_analysis.json"
    audit_path = ANALYSIS_OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"
    consumption_path = ANALYSIS_OUT / "formal_return_consumption_receipt.json"
    final_gate = V70_OUT / "gates/final_zip_release_audit.json"
    conjunction = V70_OUT / "gates/final_release_conjunction_v70.json"
    exact_gate = V70_OUT / "gates/target_capture_exact.json"
    release = V70_OUT / f"{V70}.release_receipt.json"
    package = V70_OUT / f"{V70}.zip"
    repeat = V70_OUT / f"{V70}.repeat.zip"
    prior = V69_OUT / f"{V69}.zip"
    state = ANALYSIS_OUT / "streaming_analysis/analysis_state.json"
    checkpoints = ANALYSIS_OUT / "streaming_analysis/checkpoints.jsonl"
    report = ANALYSIS_OUT / "streaming_analysis/report.md"
    values = {name: load(path) for name, path in {"analysis": analysis_path, "audit": audit_path, "consumption": consumption_path, "final_gate": final_gate, "conjunction": conjunction, "exact_gate": exact_gate, "release": release}.items()}
    errors = []
    for name in ("analysis", "audit", "consumption", "final_gate", "conjunction", "exact_gate", "release"):
        if values[name].get("pass") is not True:
            errors.append(name)
    if sha(RETURN) != "ee300f555f596400ff756a4f446154cdf1fd4ca203d6e7f8ded9fd7f4c076ae4":
        errors.append("return_identity")
    if SIDECAR.read_text(encoding="utf-8-sig").strip().split() != [sha(RETURN), RETURN.name]:
        errors.append("sidecar_identity")
    if sha(prior) != "2f4196597f12e424df97a94af2e614e413dea8032a04752c0c97fc57ec1d8597":
        errors.append("v69_source_drift")
    if package.read_bytes() != repeat.read_bytes():
        errors.append("deterministic_recompute")
    receipt = {
        "schema": "qadd-v69-return-v70-local-gates-mainline-receipt-v1",
        "role_id": "family.qlinearadd", "owner_epoch": 2, "registry_epoch": 6,
        "current_mainline_role_id": "mainline.control",
        "current_mainline_thread": "019ff027-e7db-72a3-b282-cfad8708da05",
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE_STORAGE_WAIT_MAINLINE_SERIAL_RELEASE" if not errors else "LOCAL_TERMINAL_GATE_FAILURE",
        "return_analysis": {
            "package_id": V69, "execution_id": "r1786886207604661595_3464688", "attempt_id": "a3464688",
            "return_zip": identity(RETURN), "sidecar": identity(SIDECAR), "analysis": identity(analysis_path), "consumption_receipt": identity(consumption_path),
            "streaming_state": identity(state), "append_only_checkpoints": identity(checkpoints), "incremental_report": identity(report),
            "last_proven_good": values["analysis"].get("last_proven_good"), "first_divergence": values["analysis"].get("first_divergence"),
            "validated_root_cause": values["analysis"].get("validated_root_cause"), "return_completeness": values["analysis"].get("return_completeness"),
            "process_ownership": values["analysis"].get("process_ownership"), "dynamic_4_2_repair": "OPEN_NOT_EXECUTED",
        },
        "rule_audit_disposition": {
            "package_build_failure_rule_audit": identity(audit_path),
            "disposition": "RULE_CONFIRMATION_NO_CHANGE / PACKAGE_LOCAL_NEGATIVE_CONTROL_HARDENING",
            "rule_gap_audit": "NOT_TRIGGERED_TARGET_CAUSAL_INTERVAL_NOT_EXECUTED",
        },
        "previous_version_progress": "v69 passed package runtime preflight and production compile, then uniquely failed immediately after simv Popen because the package-local supervisor initialized its PID/start-time map as a set. No target time progress or VCD was produced.",
        "current_version_purpose": "v70 preserves exact authorized 4/2 lineage, workload, numeric/golden, functional RTL absence, tail-round target, 64-signal cone and candidate matrix while fixing the PID/start-time map and returning supervisor stdout/stderr/exit.",
        "successor": {
            "package_id": V70, "package": identity(package), "repeat": identity(repeat),
            "release_receipt": identity(release), "full_gate": identity(final_gate), "exact_gate": identity(exact_gate), "conjunction": identity(conjunction),
            "unique_future_command": f"bash {V70}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy04",
        },
        "frozen_surfaces": ["validated 4/2 config lineage", "numeric", "workload", "golden", "functional RTL", "tail-round target", "64-signal causal cone", "candidate matrix", "TB observation semantics"],
        "managed_storage": {"status": "WAIT_MAINLINE_SOLE_WRITER_RELEASE", "storage_manager_called": False},
        "server_actions_performed": [], "conflicts": [], "pass": not errors, "errors": errors,
        "claim_boundary": "v69 proves package preflight, production compile and a unique package-supervisor post-Popen escape only. v70 proves local package readiness only. Neither proves target execution, ordered 0x33333333->0xcccccccc, two accept/clear events, output, dynamic 4/2 repair, natural terminal, Formal-D or E3-E5.",
    }
    target = V70_OUT / "formal_mainline_receipt.json"
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"receipt": str(target), "status": receipt["status"], "pass": receipt["pass"], "errors": errors}, sort_keys=True))
    return 0 if receipt["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
