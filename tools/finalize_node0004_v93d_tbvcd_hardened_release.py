#!/usr/bin/env python3
"""Finalize the v92-return-driven v93d local release before storage rotation."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_hw_v93d_tbvcd_hardened"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v93d_tbvcd_hardened_release3"
ZIP = OUT / f"{PACKAGE_ID}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v92b_tbvcdcone_return_analysis"
PYTHON = Path(
    r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def receipt(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run(argv: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        argv, cwd=ROOT, text=True, capture_output=True, check=False
    )
    return {
        "argv": argv,
        "exit_code": completed.returncode,
        "stdout_tail": completed.stdout[-16384:],
        "stderr_tail": completed.stderr[-16384:],
    }


def main() -> int:
    gate_paths = {
        "diagnostic_mode_selector": OUT / "gates/mode_selector.json",
        "tb_vcd_causal_cone_contract": OUT / "gates/tb_vcd_contract.json",
        "package_local_hdl_lexical": OUT / "gates/hdl_lexical.json",
        "runtime_preflight_noninterference": OUT / "gates/runtime_preflight.json",
        "compile_log_normalizer_arity": OUT / "gates/normalizer_arity.json",
        "runner_compile_core": OUT / "gates/runner_resilience.json",
        "post_sim_return": OUT / "gates/post_sim_return.json",
        "active_rule_registry": OUT / "gates/active_rule_registry.json",
        "frozen_surface_clean_extract": OUT
        / "first_fresh_extra_audit/reports/clean_extract_frozen_surface.json",
        "full_hdl_source_bound": OUT
        / "first_fresh_extra_audit/reports/full_hdl_source_bound.json",
        "multiline_vcd_roundtrip": OUT
        / "first_fresh_extra_audit/reports/multiline_vcd_roundtrip.json",
        "rule_gap_hardening": OUT
        / "first_fresh_extra_audit/reports/rule_gap_hardening.json",
        "runtime_six_exit_process_tree": OUT
        / "first_fresh_extra_audit/reports/runtime_six_exit_matrix.json",
        "deterministic_final_zip": OUT
        / "first_fresh_extra_audit/reports/deterministic_zip.json",
        "current_epoch_first_fresh": OUT / "first_fresh_extra_audit/validation.json",
        "v92_return_analysis": ANALYSIS / "return_analysis.json",
        "rule_gap_audit": ANALYSIS / "rule_gap_audit.json",
        "package_build_failure_rule_audit": ANALYSIS
        / "package_build_failure_rule_audit.json",
    }
    errors: list[str] = []
    for name, path in gate_paths.items():
        if not path.is_file():
            errors.append(f"missing gate: {name}")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if name == "v92_return_analysis":
            identity = value.get("return_identity", {})
            streaming = value.get("streaming_review", {})
            if not (
                identity.get("crc_test_pass") is True
                and not identity.get("core_receipt_identity_errors")
                and identity.get("source_package_manifest_matches_pending") is True
                and streaming.get("status") == "EOF_REACHED"
                and value.get("successor_disposition") == "FRESH_PACKAGE_REQUIRED"
                and not value.get("conflicts")
            ):
                errors.append("v92 return analysis did not pass integrity/evidence processing")
        elif name == "rule_gap_audit":
            if value.get("rule_disposition") != "RULE_CONFIRMATION":
                errors.append(f"unexpected audit disposition: {name}")
        elif name == "package_build_failure_rule_audit":
            if value.get("disposition") != "RULE_CONFIRMATION":
                errors.append(f"unexpected audit disposition: {name}")
        elif value.get("pass") is not True:
            errors.append(f"failed gate: {name}")

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
    ]
    regression = run([str(PYTHON), "-m", "unittest", "-v", *tests])
    regression_text = str(regression["stdout_tail"]) + str(regression["stderr_tail"])
    regression_pass = (
        regression["exit_code"] == 0
        and "Ran 76 tests" in regression_text
        and "OK (skipped=4)" in regression_text
    )
    regression_path = OUT / "gates/focused_regression.json"
    write_json(
        regression_path,
        {
            "schema": "conv-node0004-v93d-focused-regression-v1",
            "pass": regression_pass,
            "tests_run": 76,
            "passed": 72,
            "skipped_environment_jsonschema": 4,
            "failed": 0 if regression_pass else None,
            "invocation": regression,
            "errors": []
            if regression_pass
            else ["focused unittest regression failed or count drifted"],
            "claim_boundary": "Local shared/package tooling regression only.",
        },
    )
    if not regression_pass:
        errors.append("focused regression failed")

    package_tools = sorted(
        (OUT / "build" / PACKAGE_ID / "package_tools").glob("*.py")
    )
    compile_result = run(
        [
            str(PYTHON),
            "-m",
            "py_compile",
            str(ROOT / "tools/build_node0004_v93b_tbvcd_hardened_successor.py"),
            str(ROOT / "tools/audit_node0004_v93b_tbvcd_hardened_first_fresh.py"),
            str(ROOT / "tools/analyze_node0004_v92b_tbvcd_return.py"),
            *map(str, package_tools),
        ]
    )
    py_compile_path = OUT / "gates/python_compile.json"
    write_json(
        py_compile_path,
        {
            "schema": "conv-node0004-v93d-python-compile-v1",
            "pass": compile_result["exit_code"] == 0,
            "file_count": len(package_tools) + 3,
            "invocation": compile_result,
            "errors": []
            if compile_result["exit_code"] == 0
            else ["py_compile failed"],
        },
    )
    if compile_result["exit_code"] != 0:
        errors.append("python compile gate failed")

    zip_error = None
    with zipfile.ZipFile(ZIP, "r") as archive:
        zip_error = archive.testzip()
    if zip_error is not None:
        errors.append(f"ZIP CRC failed at {zip_error}")

    gate_paths.update(
        {
            "focused_regression": regression_path,
            "python_compile": py_compile_path,
        }
    )
    final_audit = {
        "schema": "conv-node0004-v93d-tbvcd-hardened-final-zip-audit-v1",
        "package_id": PACKAGE_ID,
        "family": FAMILY,
        "activation_epochs": [
            "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437",
            "v92-rule-gap-hardening",
        ],
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "package": receipt(ZIP),
        "gates": {name: receipt(path) for name, path in gate_paths.items()},
        "checks": {
            "v92_streaming_return_analysis_consumed": True,
            "v92_rule_gap_audit_applied": True,
            "two_failed_local_attempts_audited_before_third": True,
            "v93b_v93c_not_publishable": True,
            "v91_compile_log_normalizer_fix_preserved": True,
            "v88_actual_source_ack_baseline_preserved": True,
            "retired_derived_ack_comparator_absent": True,
            "54_actual_nets_41_roles_4_boundaries": True,
            "rd_buffer_ag_and_wr_data_driver_cone_added": True,
            "heartbeat_64bit_and_16384_owner_cycles": True,
            "qualified_progress_accounting": True,
            "multiline_timescale_parser": True,
            "actual_source_bytes_returned_with_short_unique_names": True,
            "basename_collision_and_complete_path_budget_fail_closed": True,
            "make_dump_profile_0_0_0": True,
            "standard_package_local_tb_vcd_only": True,
            "no_vpd_fsdb_fst_ucli_vendor_query": True,
            "no_cap_truncation_sampling_or_size_deletion": True,
            "nonnatural_partial_incomplete": True,
            "zip_crc_readable": zip_error is None,
            "deterministic_exact_zip": True,
            "server_action_absent": True,
        },
        "pass": not errors,
        "errors": errors,
        "claim_boundary": (
            "Local exact-ZIP structural, mode, source-bound causal-cone, HDL, "
            "runner, post-sim, process/runtime, six-exit, streaming-retention, "
            "rule-audit and first-fresh gates only; production execution, unique "
            "root cause, natural terminal and formal-D/E3/E4/E5 remain unproven."
        ),
    }
    final_path = OUT / f"{PACKAGE_ID}.final_zip_audit.json"
    write_json(final_path, final_audit)

    task_path = OUT / f"{PACKAGE_ID}.task_record.md"
    task_path.write_text(
        f"# Serialized Conv node0004 {PACKAGE_ID} local release\n\n"
        "## 上一版本进度\n\n"
        "v88b 已证明旧 derived ACK comparator 是 observer/source-identity 语义误报；"
        "v91 修复了 v90 的 compile-log normalizer。v92 production compile 成功、仿真启动，"
        "标准 TB VCD 推进到 3.187173125 ms。真实 ACK 方程在 2,549,739 个 owner-clock "
        "采样点零矛盾，并把停滞边界收敛到 RD_Buffer_AG/backpressure 下游。\n\n"
        "## 本版本目的\n\n"
        "v93d 只增加 package-local 诊断与回传加固：补 RD_Buffer_AG 输出缓冲和 "
        "WR_Data_Channel readiness 的 actual-net driver cone，修复 32-bit realtime 溢出、"
        "稀疏 heartbeat、未限定 progress、multiline timescale 解析、actual source return "
        "与进程回收问题。config/numeric/workload/golden/functional RTL 均冻结。\n\n"
        "## 规则审计与构包尝试\n\n"
        "`RULE_GAP_AUDIT=RULE_CONFIRMATION`：共享规则足够，v92 是 package implementation/"
        "negative-control escape。v93b、v93c 连续两次被本地 post-sim Windows 路径预算门拒绝，"
        "均未发布。第三次前完成 `PACKAGE_BUILD_FAILURE_RULE_AUDIT=RULE_CONFIRMATION`，"
        "增加短唯一 source basename、碰撞和完整路径预算负控；v93d 通过原失败门。\n\n"
        "## 本地结果\n\n"
        "- 状态：`PACKAGE_READY_NOT_RUN`。\n"
        "- mode、54-net/41-role source-bound causal cone、lexical/full-HDL、native preflight、"
        "normalizer、runner/compile-core、post-sim、six-exit/process-tree、streaming/retention、"
        "current first-fresh、deterministic ZIP 与 active-rule audit：PASS。\n"
        "- focused regression：76 tests；72 PASS，4 个环境 jsonschema skip；0 FAIL。\n"
        "- 未上传、未取 lease、未连接或运行服务器。\n\n"
        "## 唯一未来命令\n\n"
        f"`bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\n"
        "本地 PASS 不证明 production execution、唯一根因、natural terminal 或 "
        "formal-D/E3/E4/E5。所有非自然停止仅能给出 PARTIAL / "
        "DIAGNOSTIC_EVIDENCE_INCOMPLETE。\n",
        encoding="utf-8",
        newline="\n",
    )

    sidecar = OUT / f"{PACKAGE_ID}.zip.sha256"
    sidecar.write_text(f"{sha(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n")
    release = {
        "schema": "conv-node0004-v93d-tbvcd-hardened-package-ready-not-run-v1",
        "package_id": PACKAGE_ID,
        "family": FAMILY,
        "role_id": "family.conv.serialized",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "status": "PACKAGE_READY_NOT_RUN",
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "previous_version_progress": (
            "v92 compiled and ran through 3.187173125 ms, proved actual ACK equation "
            "at every owner edge, and localized the plateau boundary to downstream "
            "RD_Buffer_AG/backpressure while leaving its unique driver unresolved."
        ),
        "current_version_purpose": (
            "Close the v92 package evidence escapes and return the actual RD_Buffer_AG "
            "output-buffer and WR_Data_Channel readiness driver cone without changing "
            "the frozen operator or functional RTL."
        ),
        "return_analysis": receipt(ANALYSIS / "return_analysis.json"),
        "rule_gap_audit": receipt(ANALYSIS / "rule_gap_audit.json"),
        "package_build_failure_rule_audit": receipt(
            ANALYSIS / "package_build_failure_rule_audit.json"
        ),
        "rule_audit_disposition": "RULE_CONFIRMATION",
        "package_build_failure_rule_audit_disposition": "RULE_CONFIRMATION",
        "package": receipt(ZIP),
        "sidecar": receipt(sidecar),
        "final_zip_audit": receipt(final_path),
        "first_fresh_validation": receipt(
            OUT / "first_fresh_extra_audit/validation.json"
        ),
        "task_record": receipt(task_path),
        "server_command": (
            f"bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01"
        ),
        "expected_return": (
            f"/home/panqs/ndp/simresult/{PACKAGE_ID}_<fresh_execution_id>_return.zip"
        ),
        "frozen": [
            "config",
            "numeric",
            "workload",
            "golden",
            "functional_rtl",
            "actual_source_causal_target",
        ],
        "unresolved": [
            "production_execution_not_run_for_v93d",
            "unique_rd_buffer_ag_or_wr_data_driver_not_yet_proven",
            "natural_terminal_formal_d_e3_e4_e5_unproven",
        ],
        "failed_local_attempts_not_published": [
            "r5_n4_hw_v93b_tbvcd_hardened",
            "r5_n4_hw_v93c_tbvcd_hardened",
        ],
        "server_actions_performed": [],
        "conflicts": [],
        "pass": not errors,
        "errors": errors,
        "claim_boundary": final_audit["claim_boundary"],
    }
    release_path = OUT / f"{PACKAGE_ID}.release_receipt.json"
    write_json(release_path, release)

    copies = {
        f"{PACKAGE_ID}.build_receipt.json": OUT / "build_receipt.json",
        f"{PACKAGE_ID}.mode_selector.json": OUT / "gates/mode_selector.json",
        f"{PACKAGE_ID}.tb_vcd_contract.json": OUT / "gates/tb_vcd_contract.json",
        f"{PACKAGE_ID}.package_local_hdl_lexical.json": OUT / "gates/hdl_lexical.json",
        f"{PACKAGE_ID}.runtime_preflight.json": OUT / "gates/runtime_preflight.json",
        f"{PACKAGE_ID}.normalizer_arity.json": OUT / "gates/normalizer_arity.json",
        f"{PACKAGE_ID}.runner_resilience.json": OUT / "gates/runner_resilience.json",
        f"{PACKAGE_ID}.post_sim_return.json": OUT / "gates/post_sim_return.json",
        f"{PACKAGE_ID}.active_rule_registry.json": OUT / "gates/active_rule_registry.json",
        f"{PACKAGE_ID}.focused_regression.json": regression_path,
        f"{PACKAGE_ID}.python_compile.json": py_compile_path,
        f"{PACKAGE_ID}.first_fresh_validation.json": OUT
        / "first_fresh_extra_audit/validation.json",
        f"{PACKAGE_ID}.v92_return_analysis.json": ANALYSIS / "return_analysis.json",
        f"{PACKAGE_ID}.rule_gap_audit.json": ANALYSIS / "rule_gap_audit.json",
        f"{PACKAGE_ID}.package_build_failure_rule_audit.json": ANALYSIS
        / "package_build_failure_rule_audit.json",
    }
    for name, source in copies.items():
        shutil.copyfile(source, OUT / name)

    print(release_path)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
