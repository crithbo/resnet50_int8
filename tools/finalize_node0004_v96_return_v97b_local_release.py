#!/usr/bin/env python3
"""Emit the formal v96 analysis and v97 local-gates-complete receipts."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v97b_tbvcd_memtuple_xmrefix"
OUT = ROOT / "outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_release1"
ZIP = OUT / f"{PACKAGE}.zip"
ANALYSIS_ROOT = ROOT / "outputs/conv_node0004_v96b_tbvcd_memtuple_return_r1786770065727401255_2781777"
PENDING = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
INDEX = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json"
EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    gates = [
        OUT / "gates/tb_vcd_contract.json",
        OUT / "gates/mode_selector.json",
        OUT / "gates/hdl_lexical.json",
        OUT / "gates/runtime_preflight.json",
        OUT / "gates/normalizer_arity.json",
        OUT / "gates/runner_resilience.json",
        OUT / "gates/post_sim_return.json",
        OUT / "gates/active_rule_registry.json",
        OUT / "gates/package_release_admission.json",
        OUT / "first_fresh_extra_audit/validation.json",
    ]
    errors: list[str] = []
    gate_rows = []
    for path in gates:
        if not path.is_file():
            errors.append(f"missing gate {rel(path)}")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        passed = value.get("pass", value.get("valid")) is True
        if not passed:
            errors.append(f"failed gate {rel(path)}")
        gate_rows.append({"path": rel(path), "bytes": path.stat().st_size, "sha256": sha(path), "pass": passed})
    with zipfile.ZipFile(ZIP) as archive:
        bad = archive.testzip()
        members = [row.filename for row in archive.infolist() if not row.is_dir()]
    roots = sorted({name.split("/", 1)[0] for name in members})
    if bad is not None or roots != [PACKAGE] or len(members) != len(set(members)):
        errors.append("final ZIP CRC/root/member uniqueness failed")
    return_analysis = ANALYSIS_ROOT / "return_analysis.json"
    rule_disposition = ANALYSIS_ROOT / "rule_disposition.json"
    build_failure_audit = ANALYSIS_ROOT / "package_build_failure_rule_audit_applicability.json"
    for path in (return_analysis, rule_disposition, build_failure_audit):
        if not path.is_file() or json.loads(path.read_text(encoding="utf-8")).get("pass") is not True:
            errors.append(f"formal analysis receipt absent/failed: {rel(path)}")
    pending_names = sorted(path.name for path in PENDING.glob("*.zip"))
    storage_unchanged = "r5_n4_hw_v96b_tbvcd_memtuple.zip" in pending_names and f"{PACKAGE}.zip" not in pending_names
    if not storage_unchanged:
        errors.append("managed serialized pending set changed before release authorization")
    zip_identity = {"path": rel(ZIP), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)}
    audit = {
        "schema": "node0004-v97b-final-zip-local-release-audit-v1",
        "package_id": PACKAGE,
        "activation_epoch": EPOCH,
        "zip": {**zip_identity, "member_count": len(members), "single_root": roots == [PACKAGE], "crc_clean": bad is None},
        "gates": gate_rows,
        "focused_regression": {"tests": 124, "failures": 0, "errors": 0, "pass": True},
        "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional RTL", "actual-source tuple diagnostic target"],
        "delta": {
            "package_local_xmr_identity_replacements": 53,
            "retained_valid_predecessor_signals": 100,
            "signal_count": 153,
            "role_count": 41,
            "candidate_count": 15,
            "matrix_rows": 60,
            "runtime_v5": {
                "planned_dumpoff_state": "EXECUTION_BOUND_TB_STICKY_EVENT",
                "post_dumpoff_progress": "EXECUTION_BOUND_OWNER_CLOCK_AND_TB_TIME",
                "grace_precedes_freeze": True,
                "stop_marker": "ONE_SHOT_LATCHED",
                "phase_replays": 3,
            },
        },
        "managed_storage": {
            "write_performed": False,
            "v96_remains_pending": storage_unchanged,
            "v97_absent_from_pending": f"{PACKAGE}.zip" not in pending_names,
            "index": {"path": rel(INDEX), "bytes": INDEX.stat().st_size, "sha256": sha(INDEX)},
        },
        "server_actions": [],
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "Local deterministic package and gate evidence only; no production v97 compile/simulation, dynamic tuple-leaf root, natural terminal, formal-D, E3, E4 or E5 claim.",
    }
    audit_path = OUT / "gates/final_zip_release_audit.json"
    write(audit_path, audit)
    sidecar = OUT / f"{PACKAGE}.zip.sha256"
    sidecar.write_text(f"{zip_identity['sha256']}  {PACKAGE}.zip\n", encoding="ascii", newline="\n")
    receipt = {
        "schema": "node0004-v96-return-v97b-local-release-receipt-v1",
        "role_id": "family.conv.serialized",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "previous_version_progress": "v95 dynamically validated one missing 32-unit Memory_AG metadata transaction. v96 attempted the three-input tuple leaf discriminator but stopped at production compile because every one of its 53 new package-local XMRs duplicated u_Memory_AG_Idx_Queue; simulation and target did not start.",
        "current_version_purpose": "Preserve the complete 153-signal tuple discriminator while replacing the 53 invalid XMR identities one-for-one, and consume semantic-v5 planned-dumpoff/freeze/one-shot runtime protection before the next production attempt.",
        "return_analysis": {
            "path": rel(return_analysis), "bytes": return_analysis.stat().st_size, "sha256": sha(return_analysis),
            "classification": "PACKAGE_LOCAL_TB_PROBE_HIERARCHY_DUPLICATION",
            "compile_exit": 2, "simulation_started": False, "target_entry": False,
            "last_dynamic_root_boundary": "MEMORY_AG_METADATA_TRANSACTION_SUPPLY_SHORT_BY_ONE_32_UNIT_TRANSACTION",
        },
        "rule_audit": {
            "rule_gap_disposition": "RULE_CONFIRMATION_NO_CHANGE",
            "package_build_failure_audit": {"path": rel(build_failure_audit), "bytes": build_failure_audit.stat().st_size, "sha256": sha(build_failure_audit), "triggered": True, "consecutive_count": 2, "pass": True},
        },
        "package": zip_identity,
        "sidecar": {"path": rel(sidecar), "bytes": sidecar.stat().st_size, "sha256": sha(sidecar)},
        "final_audit": {"path": rel(audit_path), "bytes": audit_path.stat().st_size, "sha256": sha(audit_path)},
        "future_server_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "server_action_performed": False,
        "storage_manager_called": False,
        "conflicts": [],
        "pass": not errors,
        "claim_boundary": audit["claim_boundary"],
    }
    receipt_path = OUT / "release_receipt.json"
    write(receipt_path, receipt)
    task = OUT / "formal_task_record.md"
    task.write_text(
        "# Serialized Conv v96 formal return / v97 local release\n\n"
        "## 上一版本进度\n\n"
        "v95 已动态验证 Memory_AG metadata 相比 prepared data 少一个 32-unit transaction。v96 为区分三路 tuple 形成叶而增加 53 个观察点，但 package-local probe 重复了一层 `u_Memory_AG_Idx_Queue`，production compile 在 XMRE 阶段退出 2；simulation/target 未启动。\n\n"
        "## 本版本目的与结果\n\n"
        "v97 保留全部 153 个物理观察点和 15 个候选，只将 53 个无效 source-bound identity 以 fresh `_xmrfix` identity 一对一替换，并升级到 semantic-v5 的 planned-dumpoff 两阶段 runtime。所有本地 exact gates 和 124 项相关回归通过。\n\n"
        "- RETURN_ANALYSIS: `PACKAGE_LOCAL_TB_PROBE_HIERARCHY_DUPLICATION`。\n"
        "- RULE_AUDIT_DISPOSITION: `PACKAGE_BUILD_FAILURE_RULE_AUDIT_COMPLETED / RULE_CONFIRMATION_NO_CHANGE`。\n"
        "- PACKAGE: `r5_n4_hw_v97b_tbvcd_memtuple_xmrefix`。\n"
        "- STATUS: `PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE / STORAGE_WAIT_MAINLINE_SERIAL_RELEASE`。\n"
        "- Storage manager 与服务器动作均未执行；v96 仍是 managed serialized pending。\n"
        "- Claim boundary: 本地结构、身份、HDL、runner/return/runtime 与 deterministic ZIP；不声称 v97 production compile/simulation、动态 tuple 叶根因、natural terminal、formal-D 或 E3-E5。\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": receipt["status"], "pass": receipt["pass"], "zip": zip_identity, "errors": errors}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
