#!/usr/bin/env python3
"""Create release receipts for the exact serialized-Conv v89b observer ZIP."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v89b_observerwide_release1"
PACKAGE_ID = "r5_n4_hw_v89b_obswide"
ZIP = OUT / f"{PACKAGE_ID}.zip"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def receipt(path: Path) -> dict[str, object]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    gates = {
        "observer_contract": OUT / "gates/observer_contract.json",
        "observer_final_zip_source_bound": OUT / "gates/observer_final_zip.json",
        "package_local_hdl_lexical": OUT / "gates/hdl_lexical.json",
        "package_local_hdl_full": OUT / "gates/hdl_full.json",
        "runner_return_resilience": OUT / "gates/runner_resilience.json",
        "post_sim_return_core": OUT / "gates/post_sim_return.json",
        "first_fresh_extra_audit": OUT / "first_fresh_extra_audit/validation.json",
        "six_exit_source_bound_roundtrip": OUT / "first_fresh_extra_audit/reports/source_bound_logger_collector_parser_roundtrip.json",
        "runtime_layout_repeat": OUT / "first_fresh_extra_audit/reports/actual_runner_entry_and_input_open.json",
        "candidate_matrix": OUT / "first_fresh_extra_audit/reports/candidate_discrimination_matrix.json",
    }
    failures = []
    for name, path in gates.items():
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass") is not True or value.get("errors") not in ([], None):
            failures.append(name)
    if failures:
        raise SystemExit(f"release gates failed: {failures}")
    zip_sha = sha(ZIP)
    (OUT / f"{PACKAGE_ID}.zip.sha256").write_text(f"{zip_sha}  {PACKAGE_ID}.zip\n", encoding="ascii", newline="\n")

    copied = {
        "observer_final_zip": gates["observer_final_zip_source_bound"],
        "package_local_hdl_lexical": gates["package_local_hdl_lexical"],
        "package_local_hdl_full": gates["package_local_hdl_full"],
        "runner_return_resilience": gates["runner_return_resilience"],
        "post_sim_return": gates["post_sim_return_core"],
        "first_fresh_validation": gates["first_fresh_extra_audit"],
        "first_fresh_contract": OUT / "first_fresh_extra_audit/contract.json",
        "source_bound_six_exit": gates["six_exit_source_bound_roundtrip"],
        "runtime_layout": gates["runtime_layout_repeat"],
        "candidate_matrix": gates["candidate_matrix"],
    }
    for label, source in copied.items():
        shutil.copyfile(source, OUT / f"{PACKAGE_ID}.{label}.json")

    final_audit_path = OUT / f"{PACKAGE_ID}.final_zip_audit.json"
    final_audit = {
        "schema": "conv-node0004-v89b-observerwide-final-zip-audit-v1",
        "package_id": PACKAGE_ID,
        "family": "conv_serialized_node0004",
        "status": "PASS",
        "activation_epochs": ["observer-only-wide-causal-v1", "observer-only-post-sim-conjunction-fix-v1"],
        "zip": receipt(ZIP),
        "gates": {name: receipt(path) for name, path in gates.items()},
        "checks": {
            "dump_vcd_zero": True,
            "dump_fsdb_zero": True,
            "tb_dump_fsdb_zero": True,
            "no_waveform_or_vendor_query": True,
            "actual_net_role_coverage": "26/26",
            "candidate_coverage": "6/6_pairwise_distinguishable",
            "ordered_unbounded_four_state_events": True,
            "soft_limit_decimal_100000000_warning_only": True,
            "six_exit_return": True,
            "repeat_safe_runtime_layout": True,
            "canonical_post_sim_helper_exact": True,
            "retired_buf_idx_queue_bp_pre_comparator_absent": True,
            "functional_rtl_config_numeric_workload_golden_frozen": True,
        },
        "server_actions_performed": [],
        "claim_boundary": "Local exact-ZIP structural, HDL, source-bound observer, return, runtime-layout and first-fresh gates only; production VCS compile/simulation, natural terminal, formal-D and E3/E4/E5 remain unproven.",
        "pass": True,
        "errors": [],
    }
    write_json(final_audit_path, final_audit)

    task_path = OUT / f"{PACKAGE_ID}.task_record.md"
    task_path.write_text(
        "# Serialized Conv node0004 v89b observer-only wide-causal release\n\n"
        "## 上一版本进度\n\n"
        "v88b production compile/elaboration 已通过，actual compiled source 已证明旧 ACK public-output 对 "
        "`buf_idx_queue_bp_pre` 的比较属于 observer/source-identity 语义误报；旧 portable 控制停在 0 ps。"
        "之后 FSDB smoke s2 推进至 2.446091 ms 后进入高 CPU、无 sim-time/log 前进的平台期；s4 仅是 quiescence smoke。\n\n"
        "## 本版本目的\n\n"
        "v89b 不再构 smoke，也不生成 VPD/FSDB/VCD/FST。它冻结 v88 的 config/numeric/workload/golden/"
        "functional RTL/目标，用 slice13/group1/MSE4 的 38 个 actual nets 覆盖 26 类 ACK、row/col FIFO、"
        "aggregate queue、accept/backpressure、write-data、terminal/formal-D 因果角色，以一次正式运行定位首分歧。\n\n"
        "## 本地结果\n\n"
        "- 状态：`PACKAGE_READY_NOT_RUN`。\n"
        "- observer-only 与 current canonical post-sim helper 联合门通过。\n"
        "- exact ZIP lexical、Icarus 正负控、runner definition-before-use、post-sim、runtime-layout 和 first-fresh 通过。\n"
        "- synthetic natural/timeout/nonzero/HUP/INT/TERM 六类退出均可重放；事件保留 0/1/X/Z、end-state、heartbeat 与 partial-exit。\n"
        "- 100,000,000 bytes 是 warning-only；没有 hard limit、采样、截断或按大小删除。\n"
        "- 未修改 functional RTL/config/numeric/workload/golden，未上传、取 lease、连接或运行服务器。\n\n"
        "## 唯一未来命令\n\n"
        f"`bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\n"
        "本地 PASS 不证明 production VCS compile/simulation、natural terminal、formal-D 或 E3/E4/E5。\n",
        encoding="utf-8", newline="\n",
    )

    release_path = OUT / f"{PACKAGE_ID}.release_receipt.json"
    release = {
        "schema": "conv-node0004-v89b-observerwide-package-ready-not-run-v1",
        "role_id": "family.conv.serialized", "owner_epoch": 2, "registry_epoch": 6,
        "package_id": PACKAGE_ID, "family": "conv_serialized_node0004",
        "status": "PACKAGE_READY_NOT_RUN",
        "previous_version_progress": "v88b passed production compile/elaboration and actual compiled source closed the old ACK comparator as an observer/source-identity semantic false positive; old portable control stopped at 0 ps. FSDB smoke s2 later advanced to 2.446091 ms then plateaued; s4 was only a quiescence smoke.",
        "current_version_purpose": "Use a no-waveform, wide actual-net observer over ACK, row/column FIFO, aggregate queue, accept/backpressure, MSE4 write-data, terminal and formal-D state to localize the first divergence in one formal run.",
        "package": receipt(ZIP),
        "sidecar": receipt(OUT / f"{PACKAGE_ID}.zip.sha256"),
        "final_zip_audit": receipt(final_audit_path),
        "first_fresh_validation": receipt(OUT / f"{PACKAGE_ID}.first_fresh_validation.json"),
        "task_record": receipt(task_path),
        "server_command": f"bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "expected_return": f"/home/panqs/ndp/simresult/{PACKAGE_ID}_<fresh_execution_id>_return.zip",
        "frozen": ["config", "numeric", "workload", "golden", "functional_rtl", "target_diagnostic"],
        "conflicts": [], "server_actions_performed": [],
        "claim_boundary": final_audit["claim_boundary"],
        "pass": True, "errors": [],
    }
    write_json(release_path, release)
    print(release_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
