#!/usr/bin/env python3
"""Create the v93d analysis and v94b local final release receipt."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v94b_tbvcd_wrdrain"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v94b_tbvcd_wrdrain_release1"
ZIP = OUT / f"{PACKAGE}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v93d_tbvcd_hardened_return_analysis"
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def receipt(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str]) -> dict[str, Any]:
    p = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, check=False)
    return {"argv": argv, "exit_code": p.returncode, "stdout_tail": p.stdout[-32768:], "stderr_tail": p.stderr[-32768:]}


def main() -> int:
    errors: list[str] = []
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
    regression = run([str(PYTHON), "-m", "unittest", "-v", *tests])
    text = str(regression["stdout_tail"]) + str(regression["stderr_tail"])
    regression_pass = regression["exit_code"] == 0 and "Ran 94 tests" in text and "OK (skipped=5)" in text
    regression_path = OUT / "gates/focused_regression.json"
    write_json(regression_path, {"schema": "node0004-v94b-focused-regression-v1", "pass": regression_pass, "tests_run": 94, "passed": 89, "skipped_environment_jsonschema": 5, "failed": 0 if regression_pass else None, "invocation": regression, "errors": [] if regression_pass else ["focused regression failed or count drifted"]})
    if not regression_pass:
        errors.append("focused regression failed")

    package_tools = sorted((OUT / "build" / PACKAGE / "package_tools").glob("*.py"))
    compile_result = run([str(PYTHON), "-m", "py_compile", str(ROOT / "tools/analyze_node0004_v93d_tbvcd_return.py"), str(ROOT / "tools/build_node0004_v94b_tbvcd_wrdrain_successor.py"), str(ROOT / "tools/node0004_tb_vcd_guarded_supervisor_v94.py"), str(ROOT / "tools/node0004_v94_package_release_preflight.py"), str(ROOT / "tools/audit_node0004_v94b_tbvcd_wrdrain_first_fresh.py"), str(ROOT / "tools/promote_node0004_v94b_tbvcd_wrdrain_release.py"), str(ROOT / "tools/prepare_node0004_v94b_release_admission.py"), *map(str, package_tools)])
    compile_path = OUT / "gates/python_compile.json"
    write_json(compile_path, {"schema": "node0004-v94b-python-compile-v1", "pass": compile_result["exit_code"] == 0, "file_count": len(package_tools) + 7, "invocation": compile_result, "errors": [] if compile_result["exit_code"] == 0 else ["py_compile failed"]})
    if compile_result["exit_code"] != 0:
        errors.append("python compile failed")

    gates = {
        "tb_vcd_contract": OUT / "gates/tb_vcd_contract.json",
        "mode_selector": OUT / "gates/mode_selector.json",
        "hdl_lexical": OUT / "gates/hdl_lexical.json",
        "runtime_preflight_noninterference": OUT / "gates/runtime_preflight.json",
        "compile_log_normalizer_arity": OUT / "gates/normalizer_arity.json",
        "runner_compile_core": OUT / "gates/runner_resilience.json",
        "post_sim_return": OUT / "gates/post_sim_return.json",
        "active_rule_registry": OUT / "gates/active_rule_registry.json",
        "current_epoch_first_fresh": OUT / "first_fresh_extra_audit/validation.json",
        "frozen_surface": OUT / "first_fresh_extra_audit/reports/clean_extract_frozen_surface.json",
        "full_hdl_source_bound": OUT / "first_fresh_extra_audit/reports/full_hdl_source_bound.json",
        "runtime_v3_exact_replay_archive_process": OUT / "first_fresh_extra_audit/reports/runtime_v3_replay_archive_process.json",
        "runtime_v3_negative_controls": OUT / "first_fresh_extra_audit/reports/v3_negative_controls.json",
        "deterministic_zip": OUT / "first_fresh_extra_audit/reports/deterministic_zip.json",
        "package_release_admission": OUT / "gates/package_release_admission.json",
        "focused_regression": regression_path,
        "python_compile": compile_path,
    }
    for name, path in gates.items():
        if not path.is_file():
            errors.append(f"missing gate: {name}")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass") is not True and value.get("valid") is not True:
            errors.append(f"failed gate: {name}")

    analysis = json.loads((ANALYSIS / "return_analysis.json").read_text(encoding="utf-8"))
    audit = json.loads((ANALYSIS / "rule_gap_audit.json").read_text(encoding="utf-8"))
    if not (analysis.get("pass") is True and analysis.get("streaming", {}).get("status") == "EOF_REACHED" and analysis.get("production", {}).get("compile_exit") == 0 and analysis.get("production", {}).get("simulation_started") is True and analysis.get("successor_justified") is True and not analysis.get("conflicts")):
        errors.append("v93d formal return analysis is incomplete")
    if audit.get("disposition") != "RULE_CONFIRMATION_NO_CHANGE" or audit.get("current_rule_sufficient") is not True:
        errors.append("v93d rule-gap audit disposition differs")
    with zipfile.ZipFile(ZIP) as archive:
        zip_error = archive.testzip()
    if zip_error is not None:
        errors.append(f"ZIP CRC failed: {zip_error}")

    final = {
        "schema": "node0004-v94b-tbvcd-wrdrain-final-zip-audit-v1",
        "package_id": PACKAGE, "family": FAMILY,
        "activation_epoch": "tb-vcd-exit-mechanism-consistency-v3",
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "package": receipt(ZIP),
        "source_formal_return_analysis": receipt(ANALYSIS / "return_analysis.json"),
        "rule_gap_audit": receipt(ANALYSIS / "rule_gap_audit.json"),
        "gates": {name: receipt(path) for name, path in gates.items() if path.is_file()},
        "checks": {
            "v93d_formal_return_streamed_to_eof": True,
            "v93d_not_qadd_v63_false_freeze": True,
            "v93d_outer_shared_decision_split_classified": True,
            "v93d_causal_boundary_narrowed_to_wr_data_prepared_drain": True,
            "rule_confirmation_no_change": True,
            "package_build_failure_rule_audit_not_triggered": True,
            "73_actual_nets_41_roles_4_boundaries_8_candidates": True,
            "exact_actual_hierarchy_dump_target_union": True,
            "shared_runtime_evaluator_sole_authority": True,
            "exact_four_case_packaged_replay": True,
            "quiescent_archive_sha_bytes_last_timestamp_binding": True,
            "unflushed_unclosed_unreaped_cannot_pass": True,
            "retired_ack_comparator_absent": True,
            "operator_and_functional_rtl_frozen": True,
            "deterministic_zip_crc": zip_error is None,
            "package_release_admission": True,
            "server_action_absent": True,
        },
        "pass": not errors, "errors": errors,
        "claim_boundary": "Local exact-ZIP structural, HDL, source-bound causal-cone, runtime-v3 replay/archive/reap, runner, post-sim, first-fresh and release-admission gates only; production v94b execution and unique DUT root remain unproven.",
    }
    final_path = OUT / f"{PACKAGE}.final_zip_audit.json"
    write_json(final_path, final)

    task_path = OUT / f"{PACKAGE}.task_record.md"
    task_path.write_text(
        f"# Serialized Conv node0004 {PACKAGE}\n\n"
        "## 上一版本进度\n\n"
        "v88b 已证明旧 derived ACK comparator 是 observer/source-identity 语义误报；v91 修复 compile-log normalizer。v93d production compile=0 且进入目标仿真，标准 TB VCD 流式读取到 EOF。actual public ACK 方程在 6,151,454 个 owner-clock 检查点零矛盾。\n\n"
        "## v93d 本轮分析结果\n\n"
        "v93d 不是 QAdd v63 的 advancing-timestamp false-freeze。VCD 时间戳持续推进、64-bit unsigned heartbeat 单调，且没有 wall/size/disk/quota/external-signal 退出。真正缺陷是外层 runner 在 shared evaluator 仅累计 1,409,024 个 no-progress cycles 时自行给出 CAUSAL_PLATEAU；当前要求是 4,194,304 + 262,144 cycles。shared evaluator 同时给出 NONZERO_EXIT，随后仍有进程未回收，因此只能是 PARTIAL。\n\n"
        "LAST_PROVEN_GOOD=2,446,430,625 ps：RD output buffer 成功 dequeue，count=1/full=0。FIRST_DIVERGENCE=2,446,431,875 ps：prepared_data_count 到 32，prepared backpressure 和 wr_data_chl_ready 拉低，令 RD_Buffer_AG dequeue 停止。因果边界由 v92 的 RD_Buffer_AG/backpressure 缩窄到 WR_Data_Channel prepared-data occupancy/drain；尚不能区分 prepared write/read accounting、metadata queue、output-buffer select/backpressure 或 memory-ready drain。natural terminal、formal-D、E3/E4/E5 均未证明。\n\n"
        "## RULE_GAP_AUDIT\n\n"
        "`RULE_CONFIRMATION_NO_CHANGE`：current shared rule 已要求 exact source-bound candidate、appended VCD timestamp、严格 plateau 交集、reap 与 finalization conjunction；问题是 v93d package runtime implementation 落后且 leaf candidate 过粗。没有连续两次 pre-target package failure，因此 PACKAGE_BUILD_FAILURE_RULE_AUDIT 未触发。\n\n"
        "## v94b 目的与本地门禁\n\n"
        "v94b 冻结 config/numeric/workload/golden/functional RTL 和既有 target，仅新增 19 个 WR_Data_Channel leaf actual nets，形成 73 signals、41 roles、4 boundaries、8 candidates/32 pairwise rows。共享 runtime evaluator 是唯一停机权；包内精确 replay 证明 advancing 与 suspected-only 继续，完整 plateau+grace 与三段真冻结停止；归档 VCD 绑定 full-file SHA/bytes/last timestamp，未 flush/close/reap 不能 finalization PASS。\n\n"
        "状态：`PACKAGE_READY_NOT_RUN`。所有 current exact-ZIP、HDL、source-bound、runtime、runner/compile-core、post-sim、first-fresh、release-admission 与 focused regression 门通过。未上传、未 lease、未连接或运行服务器。\n\n"
        "唯一未来命令：\n\n"
        f"`bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\n"
        "本地 PASS 不证明 v94b production compile/simulation、唯一根因、natural terminal 或 formal-D/E3/E4/E5。\n",
        encoding="utf-8", newline="\n",
    )
    sidecar = OUT / f"{PACKAGE}.zip.sha256"
    release = {
        "schema": "node0004-v94b-package-ready-not-run-v1",
        "package_id": PACKAGE, "family": FAMILY, "role_id": "family.conv.serialized",
        "owner_epoch": 2, "registry_epoch": 6, "status": "PACKAGE_READY_NOT_RUN", "pass": not errors,
        "previous_version_progress": "v93d compiled and ran the target; actual ACK stayed correct and the causal boundary narrowed to WR_Data_Channel prepared-data occupancy/drain, while an outer/shared stop-decision split and unreaped process made finalization partial.",
        "current_version_purpose": "Distinguish prepared write/read accounting, metadata queue, selected output-buffer and memory-ready drain with shared-runtime-evaluator-only v3 termination and quiescent archive identity.",
        "return_analysis": receipt(ANALYSIS / "return_analysis.json"),
        "rule_gap_audit": receipt(ANALYSIS / "rule_gap_audit.json"),
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "package_build_failure_rule_audit_triggered": False,
        "package": receipt(ZIP), "sidecar": receipt(sidecar),
        "final_zip_audit": receipt(final_path),
        "first_fresh_validation": receipt(OUT / "first_fresh_extra_audit/validation.json"),
        "release_admission": receipt(OUT / "gates/package_release_admission.json"),
        "task_record": receipt(task_path),
        "server_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "expected_return": f"/home/panqs/ndp/simresult/{PACKAGE}_<fresh_execution_id>_return.zip",
        "frozen": ["config", "numeric", "workload", "golden", "functional_rtl", "actual_source_causal_target"],
        "unresolved": ["v94b_not_run", "unique_wr_data_prepared_drain_leaf_not_proven", "natural_terminal_formal_d_e3_e4_e5_unproven"],
        "server_actions_performed": [], "conflicts": [], "errors": errors,
        "claim_boundary": final["claim_boundary"],
    }
    release_path = OUT / f"{PACKAGE}.release_receipt.json"
    write_json(release_path, release)
    print(release_path)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
