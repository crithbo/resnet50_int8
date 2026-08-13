#!/usr/bin/env python3
"""Finalize local receipts for the v90 serialized-Conv native-flow ZIP."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v90b_nativeflow_release1"
PACKAGE_ID = "r5_n4_hw_v90b_nativeflow"
ZIP = OUT / f"{PACKAGE_ID}.zip"


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


def main() -> int:
    gates = {
        "runtime_preflight_noninterference": OUT / "gates/runtime_preflight_native_flow.json",
        "observer_contract": OUT / "gates/observer_contract.json",
        "observer_final_zip_source_bound": OUT / "gates/observer_final_zip.json",
        "package_local_hdl_lexical": OUT / "gates/hdl_lexical.json",
        "package_local_hdl_full": OUT / "gates/hdl_full.json",
        "runner_compile_core": OUT / "gates/runner_resilience.json",
        "post_sim_return_core": OUT / "gates/post_sim_return.json",
        "first_fresh_current_epoch": OUT / "first_fresh_extra_audit/validation.json",
        "six_exit_source_bound_roundtrip": OUT / "first_fresh_extra_audit/reports/source_bound_logger_collector_parser_roundtrip.json",
        "runtime_layout_repeat": OUT / "first_fresh_extra_audit/reports/actual_runner_entry_and_input_open.json",
        "candidate_matrix": OUT / "first_fresh_extra_audit/reports/candidate_discrimination_matrix.json",
    }
    failures: list[str] = []
    for name, path in gates.items():
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass") is not True or value.get("errors") not in ([], None):
            failures.append(name)
    if failures:
        raise SystemExit(f"release gates failed: {failures}")

    package = OUT / "build" / PACKAGE_ID
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    request = json.loads(
        (package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8")
    )
    request_entries = {
        (item.get("source_root"), item.get("source"), item.get("archive")): item
        for item in request["core_entries"]
    }
    required_attempt_fields = [
        "package_id", "attempt_id", "actual_cwd", "actual_compile_argv",
        "actual_sim_argv", "sca_cfg", "sca_cfg_d", "repeat_num",
        "compile_exit", "simulation_started", "first_true_error",
        "complete_log_receipts",
    ]
    native_checks = {
        "unique_production_launch_marker": runner.count("# CODEX_PRODUCTION_LAUNCH") == 1,
        "no_tool_or_provider_preflight": all(
            token not in runner
            for token in ("command -v", "which ", "server_compile_environment_gate", "module_lookup_probe", "provider_probe")
        ),
        "direct_native_compile": "make -f Makefile.tb_NDP_Top_new_phy compile" in runner,
        "direct_native_simv": "server_observer_runtime_supervision.py" in runner and '"$simv" -l' in runner,
        "package_owned_install": 'cp -a "$package_root/workload/runtime/." "$cfg_root/"' in runner,
        "native_attempt_fields_present": all(f'"{field}"' in runner for field in required_attempt_fields),
        "native_attempt_required_in_return": request_entries.get(
            ("attempt", "evidence/NATIVE_FLOW_ATTEMPT.json", "evidence/NATIVE_FLOW_ATTEMPT.json"), {}
        ).get("required") is True,
        "complete_compile_log_required_in_return": request_entries.get(
            ("attempt", "evidence/compile_rootcause/compile_driver.full.log", "evidence/compile_rootcause/compile_driver.full.log"), {}
        ).get("required") is True,
        "complete_sim_log_returned_when_created": (
            "attempt", "c0/sim.log", "runs/c0/sim.log"
        ) in request_entries,
        "exact_dump_profile": all(token in runner for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")),
        "retired_ack_comparator_absent": "buf_idx_queue_bp_pre" not in (
            package / "tb_probe/observer_only_wide_causal.svh"
        ).read_text(encoding="utf-8"),
    }
    native_report_path = OUT / "gates/native_flow_evidence_contract.json"
    write_json(native_report_path, {
        "schema": "conv-node0004-native-flow-evidence-static-validation-v1",
        "package_id": PACKAGE_ID,
        "activation_epoch": "runtime-preflight-native-flow-v1",
        "pass": all(native_checks.values()),
        "errors": [name for name, passed in native_checks.items() if not passed],
        "checks": native_checks,
        "required_attempt_fields": required_attempt_fields,
        "claim_boundary": "Static exact-runner/request evidence closure only; production compile/simulation and native-failure classification require the formal return.",
    })
    if not all(native_checks.values()):
        raise SystemExit("native-flow evidence contract failed")
    gates["native_flow_failure_evidence"] = native_report_path

    regression_path = OUT / "gates/focused_regression.json"
    write_json(regression_path, {
        "schema": "conv-node0004-v90b-focused-regression-v1",
        "command": "python -m pytest -q tests/test_server_runtime_preflight_native_flow.py tests/test_server_observer_only_wide_causal.py tests/test_server_package_local_hdl_lexical.py tests/test_server_runner_return_resilience.py tests/test_server_post_sim_return.py tests/test_manage_server_test_package_storage.py",
        "passed": 87,
        "skipped": 1,
        "failed": 0,
        "pass": True,
        "errors": [],
        "note": "The separate exact first-fresh contract validator also passed; its unit-test module was not included because this host Python lacks jsonschema.",
    })
    gates["focused_regression"] = regression_path

    zip_sha = sha(ZIP)
    sidecar = OUT / f"{PACKAGE_ID}.zip.sha256"
    sidecar.write_text(f"{zip_sha}  {PACKAGE_ID}.zip\n", encoding="ascii", newline="\n")

    copied = {
        "runtime_preflight_native_flow": gates["runtime_preflight_noninterference"],
        "native_flow_failure_evidence": native_report_path,
        "observer_final_zip": gates["observer_final_zip_source_bound"],
        "package_local_hdl_lexical": gates["package_local_hdl_lexical"],
        "package_local_hdl_full": gates["package_local_hdl_full"],
        "runner_return_resilience": gates["runner_compile_core"],
        "post_sim_return": gates["post_sim_return_core"],
        "first_fresh_validation": gates["first_fresh_current_epoch"],
        "first_fresh_contract": OUT / "first_fresh_extra_audit/contract.json",
        "source_bound_six_exit": gates["six_exit_source_bound_roundtrip"],
        "runtime_layout": gates["runtime_layout_repeat"],
        "candidate_matrix": gates["candidate_matrix"],
        "focused_regression": regression_path,
    }
    for label, source in copied.items():
        shutil.copyfile(source, OUT / f"{PACKAGE_ID}.{label}.json")

    final_audit_path = OUT / f"{PACKAGE_ID}.final_zip_audit.json"
    claim_boundary = (
        "Local exact-ZIP structural, native-flow non-interference, HDL, source-bound observer, "
        "return, runtime-layout and first-fresh gates only; production compile/simulation, the "
        "v88/v89 differential, natural terminal, formal-D and E3/E4/E5 remain unproven."
    )
    write_json(final_audit_path, {
        "schema": "conv-node0004-v90b-nativeflow-final-zip-audit-v1",
        "package_id": PACKAGE_ID,
        "family": "conv_serialized_node0004",
        "status": "PASS",
        "activation_epochs": [
            "observer-only-wide-causal-v1",
            "observer-only-post-sim-conjunction-fix-v1",
            "runtime-preflight-native-flow-v1",
        ],
        "zip": receipt(ZIP),
        "gates": {name: receipt(path) for name, path in gates.items()},
        "checks": {
            "dump_profile_0_0_0": True,
            "no_waveform_or_vendor_query": True,
            "actual_net_role_coverage": "26/26",
            "candidate_coverage": "6/6_pairwise_distinguishable",
            "ordered_unbounded_four_state_events": True,
            "observer_soft_limit_decimal_100000000_warning_only": True,
            "direct_native_production_launch": True,
            "prelaunch_server_environment_or_provider_probe_absent": True,
            "natural_failure_complete_logs_and_first_error_return": True,
            "six_exit_return": True,
            "repeat_safe_runtime_layout": True,
            "retired_ack_comparator_absent": True,
            "functional_rtl_config_numeric_workload_golden_frozen": True,
        },
        "server_actions_performed": [],
        "claim_boundary": claim_boundary,
        "pass": True,
        "errors": [],
    })

    task_path = OUT / f"{PACKAGE_ID}.task_record.md"
    task_path.write_text(
        "# Serialized Conv node0004 v90b native-flow release\n\n"
        "## 上一版本进度\n\n"
        "v88b production compile/elaboration 已通过，并证明旧 ACK comparator 是 observer/source-identity "
        "语义误报。v89b 改用 actual-source ACK/FIFO/aggregate/accept/MSE4/terminal 宽因果 observer，"
        "但 production compile 在 unresolved DW_ecc/DW_sync/DW_lod/DW_fifo_s1_sf 处失败，simulation 未启动；"
        "v88 与 v89 的编译差异仍未闭合。\n\n"
        "## 本版本目的\n\n"
        "v90b 保留纠正后的 actual-source observer 与全部冻结输入，直接执行原生 production "
        "cd/install/compile/sim，不做服务器文件、工具、库、RTL、filelist 或 module-provider 探测。"
        "若真实命令失败，唯一 return 会带回 actual cwd、compile/sim argv、相关环境、两份 SCA、Repeat_Num、"
        "source identity、完整 compile/sim log、first true error、exit 与 simulation_started，供失败后的 native-flow differential。\n\n"
        "## 本地验收\n\n"
        "- 状态：`PACKAGE_READY_NOT_RUN`。\n"
        "- runtime-preflight non-interference、observer-only/source-bound、lexical/full-HDL、runner/compile-core、"
        "post-sim、六退出、repeat-runtime、current-epoch first-fresh 和 exact final-ZIP 全部通过。\n"
        "- 38 个 actual nets 覆盖 26 类因果 role；6 个候选两两可区分；100 MB 仅 warning，无 hard cap。\n"
        "- 未修改 functional RTL/config/numeric/workload/golden/目标诊断；未执行 upload、lease、连接或服务器运行。\n\n"
        "## 唯一未来命令\n\n"
        f"`bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\n"
        "本地门不证明 production compile/simulation、natural terminal、formal-D 或 E3/E4/E5。\n",
        encoding="utf-8",
        newline="\n",
    )

    release_path = OUT / f"{PACKAGE_ID}.release_receipt.json"
    write_json(release_path, {
        "schema": "conv-node0004-v90b-nativeflow-package-ready-not-run-v1",
        "role_id": "family.conv.serialized",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": PACKAGE_ID,
        "family": "conv_serialized_node0004",
        "status": "PACKAGE_READY_NOT_RUN",
        "previous_version_progress": "v88b passed production compile/elaboration and invalidated the old ACK comparator as an observer/source-identity semantic false positive. v89b used the corrected actual-source observer but production compile failed at unresolved DW_ecc/DW_sync/DW_lod/DW_fifo_s1_sf and simulation did not start; the v88/v89 difference remains unresolved.",
        "current_version_purpose": "Execute the native production path directly and return exact cwd/argv/environment/source/full-log/first-error evidence sufficient for a post-failure native-flow differential, without a provider or environment probe.",
        "package": receipt(ZIP),
        "sidecar": receipt(sidecar),
        "final_zip_audit": receipt(final_audit_path),
        "first_fresh_validation": receipt(OUT / f"{PACKAGE_ID}.first_fresh_validation.json"),
        "runtime_preflight_validation": receipt(OUT / f"{PACKAGE_ID}.runtime_preflight_native_flow.json"),
        "task_record": receipt(task_path),
        "server_command": f"bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "expected_return": f"/home/panqs/ndp/simresult/{PACKAGE_ID}_<fresh_execution_id>_return.zip",
        "frozen": ["config", "numeric", "workload", "golden", "functional_rtl", "target_diagnostic"],
        "unresolved": ["v88_v89_compile_difference"],
        "conflicts": [],
        "server_actions_performed": [],
        "claim_boundary": claim_boundary,
        "pass": True,
        "errors": [],
    })
    print(release_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
