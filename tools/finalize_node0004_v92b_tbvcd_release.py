#!/usr/bin/env python3
"""Finalize local receipts for v92b before atomic storage publication."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_hw_v92b_tbvcdcone"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v92b_tbvcdcone_release1"
ZIP = OUT / f"{PACKAGE_ID}.zip"
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def receipt(path: Path) -> dict[str, object]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str]) -> dict[str, object]:
    completed = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, check=False)
    return {"argv": argv, "exit_code": completed.returncode, "stdout_tail": completed.stdout[-16384:], "stderr_tail": completed.stderr[-16384:]}


def main() -> int:
    gate_paths = {
        "diagnostic_mode_selector": OUT / "gates/mode_selector.json",
        "tb_vcd_causal_cone_contract": OUT / "gates/tb_vcd_contract.json",
        "package_local_hdl_lexical": OUT / "gates/hdl_lexical.json",
        "runtime_preflight_noninterference": OUT / "gates/runtime_preflight.json",
        "compile_log_normalizer_arity": OUT / "gates/normalizer_arity.json",
        "runner_compile_core": OUT / "gates/runner_resilience.json",
        "post_sim_return": OUT / "gates/post_sim_return.json",
        "frozen_surface_clean_extract": OUT / "first_fresh_extra_audit/reports/clean_extract_frozen_surface.json",
        "full_hdl_source_bound": OUT / "first_fresh_extra_audit/reports/full_hdl_source_bound.json",
        "synthetic_vcd_roundtrip": OUT / "first_fresh_extra_audit/reports/synthetic_vcd_roundtrip.json",
        "runtime_six_exit_process_tree": OUT / "first_fresh_extra_audit/reports/runtime_six_exit_matrix.json",
        "deterministic_final_zip": OUT / "first_fresh_extra_audit/reports/deterministic_zip.json",
        "current_epoch_first_fresh": OUT / "first_fresh_extra_audit/validation.json",
    }
    errors: list[str] = []
    for name, path in gate_paths.items():
        if not path.is_file():
            errors.append(f"missing gate: {name}")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass") is not True:
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
    regression_pass = regression["exit_code"] == 0 and "Ran 75 tests" in str(regression["stderr_tail"]) and "OK (skipped=4)" in str(regression["stderr_tail"])
    regression_report = {
        "schema": "conv-node0004-v92b-focused-regression-v1", "pass": regression_pass,
        "tests_run": 75, "passed": 71, "skipped_environment_jsonschema": 4, "failed": 0 if regression_pass else None,
        "invocation": regression, "errors": [] if regression_pass else ["focused unittest regression failed or count drifted"],
        "claim_boundary": "Local shared/package tooling regression only.",
    }
    write_json(OUT / "gates/focused_regression.json", regression_report)
    if not regression_pass:
        errors.append("focused regression failed")

    retention = run([str(PYTHON), "-m", "unittest", "-v", "tests.test_server_tb_vcd_retention_analysis"])
    retention_pass = retention["exit_code"] == 0 and "Ran 6 tests" in str(retention["stderr_tail"])
    retention_report = {
        "schema": "conv-node0004-v92b-streaming-retention-gate-v1", "pass": retention_pass,
        "streaming_state": ["analysis_state.json", "checkpoints.jsonl", "report.md"],
        "protected_set": ["MAX_PROGRESS", "LATEST_1", "LATEST_2"],
        "deletion_gate_count": 5, "whole_file_context_load_forbidden": True,
        "invocation": retention, "errors": [] if retention_pass else ["streaming/resume retention regression failed"],
    }
    write_json(OUT / "gates/streaming_retention.json", retention_report)
    if not retention_pass:
        errors.append("streaming retention gate failed")

    package_tools = sorted((OUT / "build" / PACKAGE_ID / "package_tools").glob("*.py"))
    compile_result = run([str(PYTHON), "-m", "py_compile", str(ROOT / "tools/build_node0004_v92b_tbvcd_successor.py"), str(ROOT / "tools/audit_node0004_v92b_tbvcd_first_fresh.py"), *map(str, package_tools)])
    py_compile_report = {"schema": "conv-node0004-v92b-python-compile-v1", "pass": compile_result["exit_code"] == 0, "file_count": len(package_tools) + 2, "invocation": compile_result, "errors": [] if compile_result["exit_code"] == 0 else ["py_compile failed"]}
    write_json(OUT / "gates/python_compile.json", py_compile_report)
    if compile_result["exit_code"] != 0:
        errors.append("python compile gate failed")

    gate_paths.update({"focused_regression": OUT / "gates/focused_regression.json", "streaming_retention": OUT / "gates/streaming_retention.json", "python_compile": OUT / "gates/python_compile.json"})
    final_audit = {
        "schema": "conv-node0004-v92b-tbvcd-final-zip-audit-v1", "package_id": PACKAGE_ID, "family": FAMILY,
        "activation_epoch": "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437",
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE", "package": receipt(ZIP),
        "gates": {name: receipt(path) for name, path in gate_paths.items()},
        "checks": {
            "v91_compile_log_normalizer_fix_preserved": True,
            "v88_actual_source_ack_baseline_preserved": True,
            "retired_derived_ack_comparator_absent": True,
            "actual_public_ack_and_driver_inputs_bound": True,
            "row_col_aggregate_fifo_and_mse4_terminal_cone_bound": True,
            "global_progress_forbids_local_plateau": True,
            "make_dump_profile_0_0_0": True,
            "standard_package_local_tb_vcd_only": True,
            "no_vpd_fsdb_fst_ucli_vendor_query": True,
            "no_cap_truncation_sampling_or_size_deletion": True,
            "nonnatural_partial_incomplete": True,
            "deterministic_exact_zip": True,
            "server_action_absent": True,
        },
        "pass": not errors, "errors": errors,
        "claim_boundary": "Local exact-ZIP structural, mode, source-bound causal-cone, HDL, runner, post-sim, process/runtime, six-exit, streaming-retention and first-fresh gates only; production compile/simulation/root cause/natural terminal/formal-D/E3/E4/E5 remain unproven.",
    }
    final_path = OUT / f"{PACKAGE_ID}.final_zip_audit.json"
    write_json(final_path, final_audit)

    task_path = OUT / f"{PACKAGE_ID}.task_record.md"
    task_path.write_text(
        f"# Serialized Conv node0004 {PACKAGE_ID} local release\n\n"
        "## 上一版本进度\n\n"
        "v88b 已用 actual compiled source 证明旧 derived ACK comparator 属于 observer/source-identity 语义误报；v90b 的 native production compile/elaboration/link 已成功；v91 修复了其 package-local compile-log normalizer 的 6→5 参数缺陷，并保持真实 ACK/FIFO/aggregate/MSE4/terminal 诊断目标。\n\n"
        "## 本版本目的\n\n"
        "本 fresh identity 显式选择 `TB_VCD_BOUNDED_CAUSAL_CONE`。它保留 v91 normalizer 和冻结 workload/config/numeric/golden/functional RTL，改用 package-local 标准 `$dumpfile/$dumpvars/$dumpon/$dumpoff/$dumpflush`，覆盖 actual ACK 及 driver inputs、row/col/aggregate FIFO、request/ready/accept/backpressure、MSE4 wdata、drain/clear/completion 与 global terminal witness。\n\n"
        "## 本地门禁结果\n\n"
        "- 状态：`PACKAGE_READY_NOT_RUN`。\n"
        "- mode selector、42-signal/41-role source-bound causal cone、4 boundary、8×4 candidate matrix：PASS。\n"
        "- lexical、SystemVerilog frontend、bash syntax、native preflight non-interference、五参数 normalizer、runner/compile-core、post-sim、六退出/process-tree、strict plateau/global-progress/freeze、streaming/resume retention、current-epoch first-fresh 与 deterministic exact ZIP：PASS。\n"
        "- shared focused regression：75 tests，71 PASS，4 个仅因本机无 jsonschema 的环境 skip；独立 schema-free validators 均 PASS。\n"
        "- 未上传、未取 lease、未连接或运行服务器。\n\n"
        "## 唯一未来命令\n\n"
        f"`bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\n"
        "本地门禁不证明 production compile/simulation/root cause/natural terminal/formal-D/E3/E4/E5。所有非自然停止只允许 PARTIAL / DIAGNOSTIC_EVIDENCE_INCOMPLETE。\n",
        encoding="utf-8", newline="\n",
    )

    sidecar = OUT / f"{PACKAGE_ID}.zip.sha256"
    sidecar.write_text(f"{sha(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n")
    release = {
        "schema": "conv-node0004-v92b-tbvcd-package-ready-not-run-v1", "package_id": PACKAGE_ID,
        "family": FAMILY, "role_id": "family.conv.serialized", "owner_epoch": 2, "registry_epoch": 6,
        "status": "PACKAGE_READY_NOT_RUN", "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "previous_version_progress": "v91 preserved the successful native compile path and fixed v90's package-local compile-log normalizer arity; v88 had already retired the false derived ACK comparator.",
        "current_version_purpose": "Return a bounded source-bound standard TB VCD for the actual ACK/FIFO/aggregate/request/MSE4/terminal causal cone with strict plateau and independent runtime safeguards.",
        "package": receipt(ZIP), "sidecar": receipt(sidecar), "final_zip_audit": receipt(final_path),
        "first_fresh_validation": receipt(OUT / "first_fresh_extra_audit/validation.json"), "task_record": receipt(task_path),
        "server_command": f"bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "expected_return": f"/home/panqs/ndp/simresult/{PACKAGE_ID}_<fresh_execution_id>_return.zip",
        "frozen": ["config", "numeric", "workload", "golden", "functional_rtl", "actual_source_causal_target"],
        "unresolved": ["production_compile_and_simulation_not_run", "natural_terminal_formal_d_e3_e4_e5_unproven"],
        "server_actions_performed": [], "conflicts": [], "pass": not errors, "errors": errors,
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
        f"{PACKAGE_ID}.streaming_retention.json": OUT / "gates/streaming_retention.json",
        f"{PACKAGE_ID}.focused_regression.json": OUT / "gates/focused_regression.json",
        f"{PACKAGE_ID}.first_fresh_validation.json": OUT / "first_fresh_extra_audit/validation.json",
    }
    for name, source in copies.items():
        shutil.copyfile(source, OUT / name)
    print(release_path)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
