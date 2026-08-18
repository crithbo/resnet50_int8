#!/usr/bin/env python3
"""Finalize the v68 analysis / v69 local-gates mainline receipt, without storage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
V68 = "r5_qadd_n7_tailround_lanephase_v68_cfg42_t2"
V69 = "r5_qadd_n7_tailround_lanephase_v69_pfc"
V68_SHA = "449e07e917bca6ff406bd94804903375e24d51b74b5c20762dc53e110ff228f4"
ANALYSIS_OUT = ROOT / "outputs/qlinearadd_node0007_v68_return_r1786853531805017272_3183291"
RELEASE_OUT = ROOT / "outputs/qlinearadd_node0007_v69_pfc_release"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    pending = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{V68}.zip"
    package = RELEASE_OUT / f"{V69}.zip"
    repeat = RELEASE_OUT / f"{V69}.repeat.zip"
    analysis_path = ANALYSIS_OUT / "formal_return_analysis.json"
    audit_path = ANALYSIS_OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_RECURRING_ESCAPE.json"
    escalation_path = ANALYSIS_OUT / "SHARED_RULE_AUDIT_ESCALATION.json"
    disposition_path = ANALYSIS_OUT / "RULE_AUDIT_DISPOSITION.json"
    consumption_path = ANALYSIS_OUT / "formal_return_consumption_receipt.json"
    streaming_state = ANALYSIS_OUT / "streaming_analysis/analysis_state.json"
    checkpoints = ANALYSIS_OUT / "streaming_analysis/checkpoints.jsonl"
    report = ANALYSIS_OUT / "streaming_analysis/report.md"
    final_gate = RELEASE_OUT / "gates/final_release_conjunction_v69.json"
    release_receipt = RELEASE_OUT / f"{V69}.release_receipt.json"
    failed_attempt = ROOT / "outputs/qlinearadd_node0007_v69_cfg42_pfcore_release/gates/final_release_conjunction_v69.json"

    analysis = load(analysis_path)
    audit = load(audit_path)
    disposition = load(disposition_path)
    gate = load(final_gate)
    release = load(release_receipt)
    errors: list[str] = []
    if pending.stat().st_size != 108_709_836 or sha(pending) != V68_SHA:
        errors.append("v68_pending_identity_drift")
    if package.read_bytes() != repeat.read_bytes():
        errors.append("deterministic_package_recompute_drift")
    if analysis.get("pass") is not True:
        errors.append("formal_return_analysis")
    if audit.get("pass") is not True:
        errors.append("recurring_package_build_failure_rule_audit")
    if gate.get("pass") is not True:
        errors.append("final_release_conjunction")
    if release.get("pass") is not True or release.get("status") != "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE":
        errors.append("release_receipt")
    checkpoint_rows = [json.loads(row) for row in checkpoints.read_text(encoding="utf-8").splitlines() if row.strip()]
    if [row.get("sequence") for row in checkpoint_rows] != [1, 2, 3, 4, 5]:
        errors.append("streaming_checkpoint_sequence")
    failed_value = load(failed_attempt) if failed_attempt.is_file() else {}
    if failed_value.get("pass") is not False or "full_current_release_audit" not in failed_value.get("errors", []):
        errors.append("preserved_long_identity_gate_failure_receipt")

    receipt = {
        "schema": "qadd-v68-return-v69-local-gates-mainline-receipt-v1",
        "role_id": "family.qlinearadd",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "status": "RETURN_ANALYSIS_COMPLETE_RULE_AUDIT_DISPOSITION_COMPLETE_PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE_STORAGE_WAIT_MAINLINE_SERIAL_RELEASE" if not errors else "LOCAL_TERMINAL_FAILURE",
        "previous_version_progress": "v68 preserved the exact validated 4/2 lineage and unchanged 64-signal causal target, but its formal run stopped inside package runtime preflight before production compile and omitted the true preflight error.",
        "current_version_purpose": "v69 preserves v68 functional/config/diagnostic semantics and adds exact package-preflight stdout, stderr, exit, runner-stage and compile-not-started first-error return so the next formal attempt cannot repeat the opaque precompile escape.",
        "RETURN_ANALYSIS": {
            "source_package": identity(pending),
            "formal_analysis": identity(analysis_path),
            "consumption_receipt": identity(consumption_path),
            "streaming": {
                "analysis_state": identity(streaming_state),
                "checkpoints": identity(checkpoints),
                "incremental_report": identity(report),
                "checkpoint_count": len(checkpoint_rows),
            },
            "last_proven_good": analysis["last_proven_good"],
            "first_divergence": analysis["first_divergence"],
            "DIRECT_CONFIG_EVIDENCE": analysis["DIRECT_CONFIG_EVIDENCE"],
            "DIRECT_ACTUAL_RTL_EVIDENCE": analysis["DIRECT_ACTUAL_RTL_EVIDENCE"],
            "DYNAMIC_EXECUTION_EVIDENCE": analysis["DYNAMIC_EXECUTION_EVIDENCE"],
            "VALIDATED_ROOT_CAUSE": analysis["VALIDATED_ROOT_CAUSE"],
            "OPEN_UNVALIDATED_MECHANISM": analysis["OPEN_UNVALIDATED_MECHANISM"],
            "boundaries": analysis["boundaries"],
        },
        "RULE_AUDIT_DISPOSITION": {
            "disposition": disposition,
            "recurring_package_build_failure_rule_audit": identity(audit_path),
            "shared_rule_audit_escalation": identity(escalation_path),
            "rule_gap_audit": "NOT_TRIGGERED_TARGET_NOT_EXECUTED",
            "classification": "EXISTING_RULE_IMPLEMENTATION_ESCAPE_NO_PUBLIC_RULE_DELTA",
        },
        "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE": {
            "package": identity(package),
            "repeat_package": identity(repeat),
            "release_receipt": identity(release_receipt),
            "final_gate_conjunction": identity(final_gate),
            "unique_future_command": release["unique_future_command"],
            "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        },
        "local_build_attempts": [
            {
                "identity": "r5_qadd_n7_tailround_lanephase_v69_cfg42_pfcore",
                "status": "LOCAL_GATE_FAILED_PRESERVED_NOT_PUBLISHED",
                "failure": "runtime path budget 243 > 240",
                "receipt": identity(failed_attempt),
            },
            {
                "identity": V69,
                "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE",
                "failure": None,
                "receipt": identity(final_gate),
            },
        ],
        "frozen_surfaces": ["exact_4_2_config_lineage", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_causal_cone", "candidate_matrix", "tb_functional_observation_semantics"],
        "storage_manager_called": False,
        "server_actions_performed": [],
        "conflicts": [],
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "The return proves only an exact precompile package-runtime-preflight boundary; v69 proves only local package readiness. No production compile/simulation, same-attempt actual compiled RTL, ordered 0x33333333->0xcccccccc acceptance/clear, dynamic repair closure, natural terminal, Formal-D or E3-E5 is claimed.",
    }
    target = RELEASE_OUT / "formal_mainline_receipt.json"
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"receipt": str(target), "pass": receipt["pass"], "errors": errors}, sort_keys=True))
    return 0 if receipt["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
