#!/usr/bin/env python3
"""Finalize the fresh serialized-Conv FSDB process-quiescence smoke s4."""

from __future__ import annotations

import json

import finalize_node0004_fsdb_smoke_s1_release as base


base.PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s4"
base.SCHEMA_TAG = "s4"
base.OUT = base.ROOT / "outputs/conv_node0004_fsdb_smoke_s4_quiescence_release1"
base.ZIP = base.OUT / f"{base.PACKAGE_ID}.zip"
base.GATES = {
    "fsdb_v3_final_zip": base.OUT / "gates/fsdb_v3_final_zip.json",
    "post_sim_final_zip": base.OUT / "gates/post_sim_final_zip.json",
    "runner_resilience": base.OUT / "gates/runner_resilience.json",
    "probe_sv_lexical": base.OUT / "gates/probe_sv_lexical.json",
    "probe_full_hdl": base.OUT / "gates/probe_full_hdl.json",
    "operator_command": base.OUT / "gates/operator_command.json",
    "frozen_surface": base.OUT / "gates/frozen_surface.json",
    "runtime_harness": base.OUT / "gates/runtime_harness_family.json",
    "runtime_layout": base.OUT / "gates/runtime_layout_validation.json",
    "quiescence_final_zip": base.OUT / "gates/quiescence_final_zip.json",
    "first_fresh": base.OUT / "gates/first_fresh_validation.json",
    "active_rule_audit": base.OUT / "gates/active_rule_audit.json",
}


def enrich() -> None:
    rule_paths = [
        base.ROOT / ".agents/agent.md",
        base.ROOT / ".agents/plan.md",
        base.ROOT / ".agents/rules/生成前必读索引.md",
        base.ROOT / ".agents/rules/会话转接与所有权规则.md",
        base.ROOT / ".agents/rules/服务器测试包生成规则.md",
        base.ROOT / ".agents/rules/INT8_SA点积专项规则.md",
        base.ROOT / "contracts/current_session_owner_registry_v1.json",
        base.ROOT / "contracts/active_rule_registry_v1.json",
        base.ROOT / "contracts/server_fsdb_process_tree_quiescence_dispatch_v1.json",
        base.ROOT / "contracts/server_waveform_incremental_review_retention_dispatch_v1.json",
        base.ROOT / "contracts/server_package_build_gate_registry_v1.json",
        base.ROOT / "schemas/server_fsdb_runtime_quiescence_v1.schema.json",
        base.ROOT / "tools/server_fsdb_runtime_quiescence.py",
        base.ROOT / ".agents/task_records/20260813_waveform_retention_and_fsdb_quiescence_activation.md",
    ]
    rule_receipt_path = base.OUT / f"{base.PACKAGE_ID}.current_disk_rule_read_receipt.json"
    base.write_json(
        rule_receipt_path,
        {
            "schema": "serialized-conv-current-disk-rule-read-receipt-v1",
            "package_id": base.PACKAGE_ID,
            "role_id": "family.conv.serialized",
            "owner_epoch": 2,
            "registry_epoch": 6,
            "activation_epoch": "waveform-retention-fsdb-quiescence-v1-967ef4e72e6c",
            "identities": [base.identity(path) for path in rule_paths],
            "conflicts": [],
            "pass": all(path.is_file() for path in rule_paths),
        },
    )

    release_path = base.OUT / f"{base.PACKAGE_ID}.release_receipt.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    release.update(
        {
            "activation_epoch": "waveform-retention-fsdb-quiescence-v1-967ef4e72e6c",
            "previous_version_progress": "s2 production compile passed, FSDB writer started and simulation reached 2.446091 ms; it then plateaued for at least 42 minutes, and the INT return captured a non-quiescent changing FSDB set. s3 is unrun and runtime-equivalent.",
            "current_version_purpose": "Fresh diagnostic smoke s4 production-proves child-subreaper process-tree termination/reaping, periodic source-bound simulation-time heartbeat and two stable FSDB exact-set snapshots before archival.",
            "formal_serialized_successor": False,
            "storage_family": "conv_serialized_node0004",
            "server_actions_performed": [],
            "current_disk_rule_read_receipt": base.identity(rule_receipt_path),
        }
    )
    base.write_json(release_path, release)

    task_path = base.OUT / f"{base.PACKAGE_ID}.task_record.md"
    task_path.write_text(
        f"""# Serialized Conv FSDB process-tree quiescence smoke s4

## 上一版本进度

`r5_n4_hw_fsdbsmoke_s2` 已在 production VCS 完成 compile，FSDB writer 启动并把仿真推进到 2.446091 ms；随后至少 42 分钟 host 高 CPU、无新的 simulation-time/log。用户 INT 后的正式 return 证明 simulator/writer 未静止，FSDB exact-set/identity 仍漂移且出现瞬态空 lock。`r5_n4_hw_fsdbsmoke_s3` 的运行面与 s2 等价，保持 `DO_NOT_RUN` 并由本包取代。

## 本版本目的

`{base.PACKAGE_ID}` 只验证 activated FSDB runtime lifecycle，不是 formal serialized Conv successor。它冻结 s2/s3 workload、probe、config、numeric、golden、functional RTL 和原诊断目标，只增加 fresh identity、Linux child-subreaper + fresh session/PGID、内部 timeout、TERM→wait→KILL/reap、source-bound simulation-time heartbeat、process-tree quiescence、两次稳定 FSDB exact-set/path/bytes/SHA snapshot 和 PARTIAL/raw/core failure isolation。

## Result

- State: `PACKAGE_READY_NOT_RUN`; no upload, lease, connection or server run occurred.
- Actual profile remains `DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0` with one package-owned writer.
- Full hierarchy depth-0 `wave.fsdb` and every shard remain unbounded formal-return members.
- The runner waits for supervisor cleanup before finalization and runs stable-snapshot quiescence before waveform discovery/archive.
- Query or quiescence failure preserves raw/core evidence and marks diagnostic evidence incomplete.
- Lexical, focused HDL, FSDB-v3/query, post-sim, runner, runtime, quiescence, first-fresh and final-ZIP gates pass locally.

## Pickup and future command

- Package: `{base.ZIP.relative_to(base.ROOT).as_posix()}`
- Release receipt: `{release_path.relative_to(base.ROOT).as_posix()}`
- Future operator command: `bash {base.PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

## Claim boundary

`PACKAGE_READY_NOT_RUN` only. The first Linux/VCS execution remains the production proof for child-subreaper coverage, real simulator/writer reaping, periodic sim-time observation and stable FSDB snapshots. This local release does not prove DUT natural terminal, formal D, E3/E4/E5 or the plateau's RTL/config root cause.
""",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    status = base.main()
    if status == 0:
        enrich()
    raise SystemExit(status)
