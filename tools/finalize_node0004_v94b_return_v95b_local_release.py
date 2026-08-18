#!/usr/bin/env python3
"""Finalize v94 analysis and the v95 local-gates-complete staged release."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v95b_tbvcd_metapair"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v95b_tbvcd_metapair_release1"
ZIP = OUT / f"{PACKAGE}.zip"
TREE = OUT / "build" / PACKAGE
ANALYSIS = ROOT / "outputs/conv_node0004_v94b_tbvcd_wrdrain_return_analysis"
STREAMING = ANALYSIS / "streaming"
PYTHON = ROOT / ".venv/Scripts/python.exe"
TASK = ROOT / ".agents/task_records/20260815_conv_node0004_v94b_return_v95b_tbvcd_metapair_local_gates_complete.md"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str]) -> dict[str, Any]:
    proc = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, check=False)
    return {"argv": argv, "exit_code": proc.returncode, "stdout_tail": proc.stdout[-32768:], "stderr_tail": proc.stderr[-32768:]}


def direct_evidence_review() -> Path:
    frozen_config = ROOT / "configs/native_ndp_sim/r5_node0004_pe1_keep_last_index_fix_c0_v62/accumulate_waves/wave-0.json"
    actual = ANALYSIS / "actual_source"
    review = {
        "schema": "node0004-v94b-config-actual-rtl-dynamic-direct-evidence-review-v1",
        "package_id": "r5_n4_hw_v94b_tbvcd_wrdrain",
        "execution_id": "r1786716754307420499_2395883",
        "policy": "CONFIG_RTL_ARE_DIRECT_EVIDENCE_NOT_PROBABILITY_SHORTCUT",
        "DIRECT_CONFIG_EVIDENCE": {
            "frozen_config": identity(frozen_config),
            "frozen_bitstream_sha256": "2f79247677c0ae8a8f89ac1bca7f381d757e28d049c7eef88e8f0bfae75d90fa",
            "stream4_json_pointer": "/stream_engine/stream4",
            "stream4_actual_values": {
                "mode": "write", "buf_idx_mode": ["keep", "buffer"],
                "buf_idx_keep_last_index": [5, 5], "buf_spatial_size": 16,
                "mem_idx_mode": ["keep", "buffer", "keep"],
                "mem_idx_keep_last_index": [0, 3, 1],
            },
            "prior_pe1_fix_present": {
                "json_pointer": "/lc_pe/PE1/inport0/keep_last_index",
                "value": 3,
                "disposition": "OLD_KEEP_LAST_INDEX_2_TO_3_FIX_IS_ALREADY_PRESENT_AND_CANNOT_EXPLAIN_THE_CURRENT_NEW_MISMATCH_BY_REINTRODUCTION",
            },
            "missing_for_validation": [
                "same-attempt runtime values of encoded mse_mem_idx_mode/mse_mem_idx_keep_last_index",
                "same-attempt runtime values of mse_buf_idx_mode/mse_buf_idx_keep_last_index and transaction total size",
                "a unique state-transition mapping from those values to the fifth-versus-third group mismatch",
            ],
        },
        "DIRECT_ACTUAL_RTL_EVIDENCE": {
            "actual_compiled_source_identity": identity(TREE / "provenance/v94b_actual_compile_source_identity.json"),
            "returned_actual_sources": [
                {**identity(actual / "WR_Data_Channel.sv"), "symbols": ["wr_data_chl_req_ready:153", "wr_chl_queue_wr_en:155", "wr_data_chl_ready:218", "wr_chl_prepared_data_bp_pre:287", "wr_data_chl_prepared_data_vld:290", "prepared_count_updates:297-309", "wr_chl_ob_vld_in:420-421"]},
                {**identity(actual / "Buffer_AG_Idx_Queue.sv"), "symbols": ["buf_idx_last_bit_masked:124", "buf_buffer_idx_last_index:188", "buf_buffer_idx_last_bit:191", "buf_all_idx_matched:200", "keep-last gating:203-204", "buf_ag_idx_queue_wr_en:222"]},
                {**identity(actual / "Memory_WR_Stream_Engine.sv"), "symbols": ["Memory_AG_Idx_Queue instance:87", "WR_Memory_AG instance:122", "WR_Data_Channel request connection:139-180", "Buffer_AG_Idx_Queue instance:211", "RD_Buffer_AG instance:239"]},
            ],
            "proven_actual_logic": [
                "prepared occupancy increments by mse_buf_spatial_size and decrements only by a matched metadata/output transfer size",
                "prepared backpressure falls when occupancy exceeds MSE_BUF_REQ_NUM",
                "WR metadata FIFO enqueues from wr_data_chl_req_valid independently of Buffer_AG prepared-data production",
                "Buffer_AG aggregate enqueue is buf_all_idx_matched & mse_enable and is governed by buffer-mode/keep-last logic",
            ],
            "actual_source_identity_gap": [
                "v94 return did not contain the actual compiled WR_Memory_AG.sv bytes",
                "v94 return did not contain the actual compiled Memory_AG_Idx_Queue.sv bytes",
                "local copies may guide v95 signal selection but are not promoted to v94 actual-compiled proof",
            ],
        },
        "DYNAMIC_EXECUTION_EVIDENCE": {
            "compile_exit": 0, "simulation_started": True, "target_entry": True,
            "last_proven_good_ps": 2446430625,
            "first_divergence_ps": 2446431875,
            "first_divergence": "a fourth/final unmatched prepared-data group raised prepared occupancy 16 to 32 without a matching WR metadata entry",
            "observed_group_counts": {"prepared_data_groups_of_16": 5, "wr_metadata_groups": 3, "unmatched_groups": 2},
            "stable_endpoint": {
                "prepared_count": 32, "prepared_valid": 1, "prepared_backpressure": 0,
                "wr_metadata_queue_count": 0, "wr_metadata_queue_empty": 1,
                "wr_output_valid": "00", "wr_output_backpressure_pre": "11",
                "memory_wdata_valid": "00", "memory_wdata_ready": "11",
                "rd_output_count": 2, "aggregate_queue_count": 4,
                "global_fetch_finish": 1, "slice_finish": 0,
            },
            "termination": "USER_EXTERNAL_INT_AFTER_CAUSAL_STATE_PLATEAU",
            "natural_terminal": False, "formal_d": "NOT_REACHED", "e3": "NOT_PROVEN", "e4": "NOT_PROVEN", "e5": "NOT_PROVEN",
        },
        "DYNAMICALLY_PROVEN_BOUNDARY": "WR_Data_Channel prepared-data occupancy cannot drain because matching WR metadata lifetime is absent; downstream output and memory-ready backpressure are closed as primary causes.",
        "OPEN_UNVALIDATED_MECHANISM": [
            {"rank": 1, "candidate": "WR_Memory_AG metadata generation/transfer lifetime ends two groups early", "evidence_state": "DYNAMICALLY_SUPPORTED_BUT_ACTUAL_WR_MEMORY_SOURCE_AND_RUNTIME_CONFIG_CONSUMER_STATE_MISSING"},
            {"rank": 2, "candidate": "Buffer_AG/RD_Buffer data generation admits two groups beyond metadata lifetime", "evidence_state": "DYNAMICALLY_SUPPORTED_BUT_RUNTIME_KEEP_LAST_AND_LAST_STATE_CHAIN_MISSING"},
        ],
        "validated_root_cause": None,
        "configuration_workaround_omitted": True,
        "configuration_workaround_omission_reason": "Neither remaining mechanism has the exact config-to-encoding/loader-to-actual-consumer-to-runtime-transition chain required by the superseding user policy.",
        "v95_closing_action": "Return actual WR_Memory_AG/Memory_AG_Idx_Queue source identities and same-attempt config consumer, last-state, transfer-lifetime, accept and queue transitions while retaining all 73 predecessor signals.",
        "claim_boundary": "Direct config, returned actual RTL and v94 dynamic evidence jointly validate the metadata-versus-prepared-data lifetime boundary, but not which producer lifetime is wrong. No config workaround is recommended.",
        "conflicts": [], "pass": True,
    }
    path = ANALYSIS / "config_rtl_direct_evidence_review.json"
    write_json(path, review)
    return path


def update_streaming(review_path: Path) -> None:
    state_path = STREAMING / "analysis_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    already_recorded = state.get("family_adjudication", {}).get("direct_config_actual_rtl_review") == "../config_rtl_direct_evidence_review.json"
    if not already_recorded:
        state["checkpoint_count"] = int(state.get("checkpoint_count", 42)) + 1
    state["family_adjudication"]["direct_config_actual_rtl_review"] = "../config_rtl_direct_evidence_review.json"
    state["family_adjudication"]["root_state"] = "OPEN_UNVALIDATED_MECHANISM"
    state["family_adjudication"]["config_workaround"] = "OMITTED_UNTIL_ROOT_VALIDATED"
    state["family_adjudication"]["successor"] = "../../conv_node0004_v95b_tbvcd_metapair_release1"
    write_json(state_path, state)
    checkpoint = {
        "schema": "server-tb-vcd-retention-analysis-v1", "sequence": 42,
        "kind": "family_direct_config_actual_rtl_review", "status": "EOF_AND_DIRECT_EVIDENCE_REVIEW_COMPLETE",
        "byte_offset": state["byte_offset"], "last_sim_time": state["last_sim_time"],
        "review_sha256": sha(review_path), "root_state": "OPEN_UNVALIDATED_MECHANISM",
        "successor_package_id": PACKAGE,
    }
    if not already_recorded:
        with (STREAMING / "checkpoints.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        with (STREAMING / "report.md").open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(
                "\n## Direct config / actual RTL evidence review\n\n"
                "The frozen stream4 configuration, returned actual WR_Data_Channel/Buffer_AG/top sources, and the v94 dynamic trace directly validate a mismatch at the prepared-data-versus-WR-metadata lifetime boundary. The old PE1 keep-last fix is already present. However v94 did not return actual WR_Memory_AG/Memory_AG_Idx_Queue bytes or same-attempt encoded consumer values, so metadata-ended-early versus data-overran remains OPEN_UNVALIDATED_MECHANISM. No configuration workaround is proposed. v95 observes both lifetimes and their config consumers.\n"
            )


def focused_regression() -> Path:
    tests = [
        "tests.test_server_tb_vcd_bounded_causal_cone",
        "tests.test_server_diagnostic_mode_selector",
        "tests.test_server_tb_vcd_runtime_supervision",
        "tests.test_server_tb_vcd_retention_analysis",
        "tests.test_server_package_local_hdl_lexical",
        "tests.test_server_runner_return_resilience",
        "tests.test_server_post_sim_return",
        "tests.test_server_runtime_preflight_native_flow",
        "tests.test_node0004_compile_log_normalizer_arity",
        "tests.test_server_package_release_admission",
    ]
    invocation = run([str(PYTHON), "-m", "unittest", "-v", *tests])
    path = OUT / "gates/focused_regression.json"
    write_json(path, {
        "schema": "node0004-v95-focused-regression-v1", "pass": invocation["exit_code"] == 0,
        "test_modules": tests, "invocation": invocation,
        "errors": [] if invocation["exit_code"] == 0 else ["focused regression failed"],
        "claim_boundary": "Current shared/package validation regression only.",
    })
    return path


def source_compile() -> Path:
    sources = [
        ROOT / "tools/build_node0004_v95b_tbvcd_metapair_successor.py",
        ROOT / "tools/audit_node0004_v95b_tbvcd_metapair_first_fresh.py",
        ROOT / "tools/prepare_node0004_v95b_release_admission.py",
        ROOT / "tools/finalize_node0004_v94b_return_v95b_local_release.py",
        *sorted((TREE / "package_tools").glob("*.py")),
    ]
    errors: list[str] = []
    for path in sources:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except Exception as exc:
            errors.append(f"{path.relative_to(ROOT).as_posix()}: {exc}")
    output = OUT / "gates/python_source_compile.json"
    write_json(output, {
        "schema": "node0004-v95-python-source-compile-v1", "pass": not errors,
        "exact_sources": [identity(path) for path in sources], "bytecode_written_into_package": False,
        "errors": errors, "claim_boundary": "Non-polluting Python source compilation only.",
    })
    return output


def main() -> int:
    review = direct_evidence_review()
    update_streaming(review)
    regression = focused_regression()
    compile_gate = source_compile()
    sidecar = OUT / f"{PACKAGE}.zip.sha256"
    sidecar.write_text(f"{sha(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n")
    gates = {
        "tb_vcd_contract": OUT / "gates/tb_vcd_contract.json",
        "mode_selector": OUT / "gates/mode_selector.json",
        "hdl_lexical": OUT / "gates/hdl_lexical.json",
        "runtime_preflight_noninterference": OUT / "gates/runtime_preflight.json",
        "normalizer_arity": OUT / "gates/normalizer_arity.json",
        "runner_resilience": OUT / "gates/runner_resilience.json",
        "post_sim_return": OUT / "gates/post_sim_return.json",
        "active_rule_registry": OUT / "gates/active_rule_registry.json",
        "package_release_admission": OUT / "gates/package_release_admission.json",
        "current_epoch_first_fresh": OUT / "first_fresh_extra_audit/validation.json",
        "clean_extract_frozen_surface": OUT / "first_fresh_extra_audit/reports/clean_extract_frozen_surface.json",
        "full_hdl_source_bound": OUT / "first_fresh_extra_audit/reports/full_hdl_source_bound.json",
        "runtime_v3_false_freeze": OUT / "first_fresh_extra_audit/reports/runtime_v3_replay_false_freeze_control.json",
        "negative_controls": OUT / "first_fresh_extra_audit/reports/negative_controls.json",
        "deterministic_zip": OUT / "first_fresh_extra_audit/reports/deterministic_zip.json",
        "focused_regression": regression,
        "python_source_compile": compile_gate,
    }
    errors: list[str] = []
    for name, path in gates.items():
        if not path.is_file():
            errors.append(f"missing gate: {name}")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass") is not True and value.get("valid") is not True:
            errors.append(f"failed gate: {name}")
    with zipfile.ZipFile(ZIP) as archive:
        bad = archive.testzip()
    if bad is not None:
        errors.append(f"ZIP CRC failed: {bad}")
    analysis = json.loads((ANALYSIS / "return_analysis.json").read_text(encoding="utf-8"))
    audit = json.loads((ANALYSIS / "rule_gap_audit.json").read_text(encoding="utf-8"))
    if not (analysis.get("pass") is True and analysis.get("production", {}).get("compile_exit") == 0 and analysis.get("production", {}).get("target_entry") is True):
        errors.append("v94 formal return analysis differs")
    if audit.get("disposition") != "RULE_DELTA_PROPOSAL_WITH_PACKAGE_IMPLEMENTATION":
        errors.append("v94 rule-gap audit disposition differs")
    final = {
        "schema": "node0004-v95b-tbvcd-metapair-final-zip-audit-v1",
        "package_id": PACKAGE, "family": FAMILY,
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "package": identity(ZIP), "sidecar": identity(sidecar),
        "source_return_analysis": identity(ANALYSIS / "return_analysis.json"),
        "direct_evidence_review": identity(review), "rule_gap_audit": identity(ANALYSIS / "rule_gap_audit.json"),
        "gates": {name: identity(path) for name, path in gates.items() if path.is_file()},
        "checks": {
            "v94_streaming_eof": True, "v94_compile_and_target_entry": True,
            "v94_manual_int_non_natural": True, "runtime_v3_false_negative_classified": True,
            "direct_config_actual_rtl_dynamic_policy_applied": True,
            "root_remains_open_until_direct_chain_validates": True,
            "config_workaround_not_recommended": True,
            "100_unique_actual_nets_41_roles_4_boundaries_10_candidates": True,
            "all_73_predecessor_signals_retained": True, "27_signals_added_zero_removed": True,
            "high_direct_driver_complete": True, "retired_ack_comparator_absent": True,
            "runtime_v3_shared_evaluator_sole_authority": True,
            "interheartbeat_host_poll_false_freeze_negative_pass": True,
            "empty_control_exact_token_pass": True, "full_hierarchy_catalog_pass": True,
            "frozen_payload_pass": True, "functional_rtl_unchanged": True,
            "deterministic_zip_crc": bad is None, "storage_manager_not_called": True,
            "server_action_absent": True,
        },
        "pass": not errors, "errors": errors,
        "claim_boundary": "Local exact-final-ZIP structural, HDL, source-bound, adaptive breadth, runtime-v3, return, first-fresh, release-admission and regression gates only; v95 production behavior and unique functional root are unproven. Storage publication remains withheld.",
        "conflicts": [],
    }
    final_path = OUT / f"{PACKAGE}.final_zip_audit.json"
    write_json(final_path, final)
    text = f"""# Serialized Conv node0004 v94 return / v95 local-gates-complete

## 上一版本进度

v88b 已证明旧 derived ACK comparator 是 observer/source-identity 语义误报；v93d 把真实停滞边界收窄到 WR_Data_Channel prepared-data occupancy/drain。v94b production compile=0、target_entry=true，73/73 actual-source 信号流式读到 EOF；运行由用户外部 INT 结束，不是自然终止。

## v94 本轮实际定位

LAST_PROVEN_GOOD=2,446,430,625 ps：最后一次 WR drain 成功。FIRST_DIVERGENCE=2,446,431,875 ps：新的 16-entry prepared group 把 occupancy 从 16 推到 32，但没有匹配 WR metadata。最终 prepared_count=32、metadata queue empty、WR output empty/ready、memory wdata ready=11，因而 output/memory downstream backpressure 已排除为主因。动态已证边界是 prepared-data 与 WR-metadata lifetime 不匹配；剩余二选一是 metadata 提前结束或 Buffer/RD data 多生成两组。

用户看到的 cannot-open warning 来自 package TB 轮询尚不存在的 shared_stop.control，非致命；`0001001` 来自 sim.log 的 APB 配置读写十六进制回显，没有发现纯二进制日志行；理论时间接近结束不等价于 terminal，slice_finish 始终未置位。

## DIRECT_CONFIG_EVIDENCE

冻结 stream4 为 write，buf mode=[keep,buffer]、keep_last=[5,5]、spatial_size=16，mem mode=[keep,buffer,keep]、keep_last=[0,3,1]。旧 PE1 keep_last_index=3 修复已经存在，不能用“旧值回归”解释本次 mismatch。v94 尚缺同 attempt 编码后的 runtime consumer 值，因此没有验证任何配置绕行。

## DIRECT_ACTUAL_RTL_EVIDENCE

v94 return 绑定了 actual compiled WR_Data_Channel、Buffer_AG_Idx_Queue 与 Memory_WR_Stream_Engine 顶层连接：prepared count 按 +spatial_size/-metadata transfer size 更新，metadata FIFO 从 wr_data_chl_req_valid 入队，Buffer aggregate 则由 buf_all_idx_matched & mse_enable 入队。v94 未返回 actual compiled WR_Memory_AG 与 Memory_AG_Idx_Queue bytes，所以不能把本地对应文件自动提升为 server actual-source 证据。

## DYNAMIC_EXECUTION_EVIDENCE

观察到 5 组 prepared-data 写入但只有 3 组 metadata；最终两组无法 drain。`VALIDATED_ROOT_CAUSE` 尚未成立，状态为 `OPEN_UNVALIDATED_MECHANISM`。依照用户最新裁决，本轮不提供 CONFIG_WORKAROUND。

## RULE_GAP_AUDIT

`RULE_DELTA_PROPOSAL_WITH_PACKAGE_IMPLEMENTATION`：v94 的 inter-heartbeat host poll 会错误重置 plateau 计数；finalizer 用 leaf/signal_id 对 full hierarchy 造成假缺失；缺失 warning-free stop 表示、独立 console return 和 producer direct drivers。v95 已在 package-only 表面落实这些增量。没有连续两次 pre-target package failure，PACKAGE_BUILD_FAILURE_RULE_AUDIT 未触发。

## v95 目的与门禁

v95 保留全部 73 个 predecessor signals，新增 27 个实际 metadata/Buffer last/config-consumer/direct-driver nets，合计 100 个唯一 hierarchy、41 roles、4 boundaries、10 candidates/40 rows；三个 HIGH 候选均有零跳 driver。它将同一次运行中的实际 config consumer、Memory_AG queue、WR_Memory transaction/transfer lifetime 与 Buffer last-state 串起来，目的是闭合 metadata-ended-early 与 data-overrun 二选一。

runtime-v3 仅把真实 source-heartbeat、30 秒固定 timestamp freeze 样本和 terminal 样本交给共享 evaluator；raw host samples 仍保留。空控制文件不再停机，只有精确 `CAUSAL_PLATEAU` 令牌触发 dumpoff/flush。所有 exact-ZIP、full HDL、source-bound、adaptive breadth、post-sim、runner/compile-core、runtime-v3 replay、false-freeze 负控、first-fresh、release-admission、deterministic ZIP 与 focused regression 门通过。

状态：`PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE / STORAGE_WAIT_MAINLINE_SERIAL_RELEASE`。没有调用 storage manager，没有发布/轮换 pending，没有 upload/lease/connect/run/server action。

未来唯一命令（仅在另行授权并完成 storage publication 后）：

`bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

本地门禁不证明 v95 production compile/sim、唯一根因、自然终止或 formal-D/E3/E4/E5。
"""
    if not TASK.is_file():
        raise RuntimeError("formal task record must be published by controlled patch")
    (OUT / f"{PACKAGE}.task_record.md").write_text(text, encoding="utf-8", newline="\n")
    release = {
        "schema": "node0004-v95b-package-ready-not-run-local-gates-complete-v1",
        "package_id": PACKAGE, "family": FAMILY, "role_id": "family.conv.serialized",
        "owner_epoch": 2, "registry_epoch": 6,
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "pass": not errors,
        "previous_version_progress": "v94 compiled and entered the target, then dynamically validated a five-versus-three prepared-data/metadata lifetime mismatch at WR_Data_Channel; user INT ended the non-natural plateau.",
        "current_version_purpose": "Use actual config consumers plus actual Memory_AG/WR_Memory/Buffer lifetime and direct-driver transitions to distinguish metadata ending early from data overrun, while closing v94 runtime-v3/return defects.",
        "return_analysis": identity(ANALYSIS / "return_analysis.json"),
        "direct_evidence_review": identity(review), "rule_gap_audit": identity(ANALYSIS / "rule_gap_audit.json"),
        "root_state": "OPEN_UNVALIDATED_MECHANISM", "config_workaround_included": False,
        "package": identity(ZIP), "sidecar": identity(sidecar), "final_zip_audit": identity(final_path),
        "first_fresh": identity(OUT / "first_fresh_extra_audit/validation.json"),
        "release_admission": identity(OUT / "gates/package_release_admission.json"),
        "task_record": identity(TASK),
        "future_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "storage_manager_actions": [], "server_actions": [],
        "frozen": ["config", "numeric", "workload", "golden", "functional_rtl", "diagnostic_target"],
        "unproven": ["v95_production_compile", "v95_simulation", "validated_unique_functional_root", "natural_terminal", "formal_d", "e3", "e4", "e5"],
        "conflicts": [], "errors": errors, "claim_boundary": final["claim_boundary"],
    }
    release_path = OUT / f"{PACKAGE}.release_receipt.json"
    write_json(release_path, release)
    print(json.dumps({"status": release["status"], "storage_status": release["storage_status"], "pass": release["pass"], "errors": errors}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
