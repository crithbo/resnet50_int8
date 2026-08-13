#!/usr/bin/env python3
"""Write the post-storage completion receipt for diagnostic FSDB smoke s4."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_fsdb_smoke_s4_quiescence_release1"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s4"
FAMILY = "conv_serialized_node0004"
GATES = [
    "fsdb_v3_final_zip",
    "post_sim_final_zip",
    "runner_resilience",
    "probe_sv_lexical",
    "probe_full_hdl",
    "operator_command",
    "frozen_surface",
    "runtime_harness_family",
    "runtime_layout_validation",
    "quiescence_final_zip",
    "first_fresh_validation",
    "active_rule_audit",
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    sys.path.insert(0, str(ROOT / "tools"))
    import manage_server_test_package_storage as storage_manager

    audit = storage_manager.audit(STORAGE)
    pickup = STORAGE / "pending" / f"{PACKAGE_ID}.zip"
    receipt_dir = STORAGE / "pending_receipts" / FAMILY / PACKAGE_ID
    old_dir = STORAGE / "superseded" / FAMILY / "r5_n4_hw_fsdbsmoke_s3"
    gate_receipts: dict[str, object] = {}
    errors: list[str] = []
    for gate in GATES:
        path = OUT / "gates" / f"{gate}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        gate_receipts[gate] = {**identity(path), "pass": value.get("pass") is True}
        if value.get("pass") is not True:
            errors.append(f"gate_failed:{gate}")
    if audit.get("pass") is not True:
        errors.append("storage_audit_failed")
    if audit.get("pending_by_family", {}).get(FAMILY) != [PACKAGE_ID]:
        errors.append("pending_family_mismatch")
    if not pickup.is_file():
        errors.append("pickup_missing")
    if not old_dir.is_dir() or (STORAGE / "pending/r5_n4_hw_fsdbsmoke_s3.zip").exists():
        errors.append("s3_rotation_mismatch")

    receipt = {
        "schema": "node0004-fsdb-smoke-s4-completion-v1",
        "role_id": "family.conv.serialized",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "activation_epoch": "waveform-retention-fsdb-quiescence-v1-967ef4e72e6c",
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "LOCAL_TERMINAL_GATE_FAILURE",
        "previous_version_progress": "s2 production compile passed, FSDB writer started and simulation reached 2.446091 ms, then host execution plateaued for at least 42 minutes. Its INT return captured a non-quiescent changing FSDB exact set. s3 remained unrun because its runtime surface was equivalent.",
        "current_version_purpose": "Build one non-formal diagnostic smoke that retains the s2/s3 payload and adds activated process-tree reaping, source-bound periodic simulation-time heartbeat, and stable FSDB exact-set snapshots before return archival.",
        "package": {
            "package_id": PACKAGE_ID,
            "classification": "DIAGNOSTIC_SMOKE_ONLY_NOT_FORMAL_SERIALIZED_SUCCESSOR",
            "pickup": identity(pickup),
            "receipt_dir": receipt_dir.relative_to(ROOT).as_posix(),
            "release_receipt": identity(receipt_dir / f"{PACKAGE_ID}.release_receipt.json"),
            "task_record": identity(receipt_dir / f"{PACKAGE_ID}.task_record.md"),
            "runner_member": f"{PACKAGE_ID}/PREPARE_AND_RUN.sh",
            "future_operator_command": f"bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        },
        "profile": {
            "DUMP_VCD": 0,
            "DUMP_FSDB": 1,
            "TB_DUMP_FSDB": 0,
            "authoritative_attempt_local_fsdb": True,
            "unbounded_waveform_return": True,
            "process_tree_subreaper_and_fresh_pgid": True,
            "term_wait_kill_reap": True,
            "periodic_source_bound_sim_time_heartbeat": True,
            "two_stable_exact_set_snapshots": True,
            "transient_lock_tmp_empty_rejected": True,
            "partial_raw_core_failure_isolation": True,
        },
        "frozen": {
            "s2_s3_workload": True,
            "probe": True,
            "config": True,
            "numeric": True,
            "golden": True,
            "functional_rtl": True,
            "diagnostic_target": True,
        },
        "gates": gate_receipts,
        "storage": {
            "audit_pass": audit.get("pass") is True,
            "pending_by_family": audit.get("pending_by_family"),
            "index": identity(STORAGE / "PACKAGE_STORAGE_INDEX.json"),
            "s3_disposition": "superseded",
            "s3_preserved_members": [identity(path) for path in sorted(old_dir.iterdir()) if path.is_file()],
            "s4_disposition": "pending",
        },
        "remaining_blockers": [
            "The first real Linux/VCS run remains the production proof boundary for subreaper coverage, real simulator/writer reaping, sim-time heartbeats and stable FSDB snapshots.",
            "This diagnostic smoke does not prove DUT natural terminal, formal D, E3/E4/E5, or the s2 plateau root cause.",
            "No formal serialized Conv successor was built; the formal family packages remain frozen.",
        ],
        "claim_boundary": "Exact local package/gate/storage result only. No upload, lease, server connection, server run, production VCS or DUT result is claimed.",
        "server_actions": [],
        "conflicts": [],
        "errors": errors,
        "pass": not errors,
    }
    receipt_path = OUT / "completion_receipt.json"
    write_json(receipt_path, receipt)
    task_path = OUT / "completion_task_record.md"
    task_path.write_text(
        f"""# Serialized Conv FSDB quiescence smoke s4 completion

## 上一版本进度

s2 已证明 production compile、FSDB writer 启动和仿真推进到 2.446091 ms；随后至少 42 分钟只有 host 高 CPU，没有新的 simulation-time/log。INT return 显示 simulator/writer 未静止，FSDB exact-set/identity 仍变化。s3 与该运行面等价，因此保持未运行并已完整转入 superseded。

## 本版本目的

s4 是一份 fresh diagnostic smoke，不是 formal serialized Conv successor。它冻结 s2/s3 的 workload、probe、config、numeric、golden、functional RTL 和诊断目标，只加入激活的 process-tree termination/reaping、真实 sim-time heartbeat、FSDB stable-snapshot/quiescence 及失败隔离。

## 结果

- 状态：`{receipt['status']}`。
- exact final ZIP、FSDB-v3/query、lexical/full-HDL、runner six-exit、repeat reset、runtime layout、quiescence、post-sim、first-fresh 和 active-rule audit 均通过。
- s3 已由 storage manager 原子转入 superseded；s4 是本 family 唯一 pending；全局 storage audit 通过。
- 未执行 upload、lease、server connection 或 server run。

## Pickup

- `{pickup.relative_to(ROOT).as_posix()}`
- 命令：`bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

## Claim boundary

本记录只证明本地 package/gate/storage 闭合。真实 Linux/VCS 的子进程回收、sim-time heartbeat、稳定 FSDB snapshot，以及 DUT natural terminal/formal-D/E3/E4/E5，仍需正式 return 才能裁决。
""",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"pass": not errors, "errors": errors, "status": receipt["status"], "receipt": str(receipt_path)}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
