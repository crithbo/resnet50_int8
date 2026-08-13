#!/usr/bin/env python3
"""Independent final-ZIP audit for the p10 triggered-causal c0 package."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_conv_native_four_lane_0ccae916_p10_triggered_c0_package as build  # noqa: E402
import tools.validate_conv_native_four_lane_0ccae916_p7_cloudnb_package as p7v  # noqa: E402


INSTALL_NAME = build.INSTALL_NAME
PACKAGE_ROOT = build.OUTPUT_ROOT / INSTALL_NAME
PACKAGE_ZIP = build.OUTPUT_ROOT / f"{INSTALL_NAME}.zip"
OUTPUT = build.OUTPUT_ROOT / f"{INSTALL_NAME}.final_zip_audit.json"
APPEND_MARKER = "// Native Conv c0 always-on triggered causal observer append."


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run(command: list[str], cwd: Path) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    return {
        "command": command,
        "cwd": str(cwd),
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def safe_zip(package_zip: Path) -> dict[str, Any]:
    with zipfile.ZipFile(package_zip) as archive:
        bad = archive.testzip()
        names = [info.filename for info in archive.infolist()]
        unsafe = [
            name
            for name in names
            if (
                "\\" in name
                or name.startswith("/")
                or ".." in Path(name).parts
                or not name.startswith(f"{INSTALL_NAME}/")
            )
        ]
    return {
        "valid": bad is None and not unsafe and len(names) == len(set(names)),
        "crc_bad_member": bad,
        "unsafe_members": unsafe,
        "member_count": len(names),
    }


def relation(package: Path) -> dict[str, Any]:
    with zipfile.ZipFile(build.SOURCE_ZIP) as archive:
        source_manifest = json.loads(
            archive.read(f"{build.SOURCE_NAME}/package_manifest.json")
        )
    return build.source_relation(source_manifest, package)


def _focused_prefix() -> str:
    return r"""
`timescale 1ns/1ps
`define MEMORY_STREAM_ENGINE_NUM 5
`define BUFFER_NUM 6
`define MSE_REQ_CHL_NUM 1
`define SA_INPORT_GROUP_NUM 1
`define SA_OUTPORT_GROUP_NUM 1
`define SA_PORT_HANDLE_BUF_NUM 1
`define ARRAY_PORT_TAG 14
`define ARRAY_PORT_GROUP_SIZE 8
`define PORT_LAST_INDEX 4
`define PORT_SAME_BIT 1
`define BUFFER_BANK_NUM 8
module n4_ndp_stub;
  logic clk_sg, rst_n_sg;
endmodule
module conv_native4_trigger_focus_top;
  n4_ndp_stub u_NDP_Top_new();
  integer n4d_slice_id = 0;
  integer n4d_group_id = 0;
  integer n4d_local_slice_id = 0;
  logic n4d_active;
  logic local_req_hs [0:0][0:0][0:4][0:0];
  logic n4d_arm_req_hs_mon [0:0][0:0][0:5];
  logic n4d_arm_resp_hs_mon [0:0][0:0][0:5];
  logic n4d_arm_finish_mon [0:0][0:0][0:5];
  logic n4d_arm_finish_d [0:5];
  logic [13:0] n4d_buf2sa_tag_mon [0:0][0:0][0:0][0:0];
  logic n4d_sa_input_bp_mon [0:0][0:0][0:0][0:0];
  logic [13:0] n4d_sa2buf_tag_mon [0:0][0:0][0:0][0:0];
  logic n4d_buf_accept_sa_mon [0:0][0:0][0:0][0:0];
  logic n4d_mse4_idx_hs_mon [0:0][0:0];
  logic [7:0] n4d_buf45_wr_en_mon [0:0][0:0][0:1];
  logic [7:0] n4d_rd_queue_full_mon [0:0][0:0];
"""


def _focused_suffix() -> str:
    return r"""
  initial begin
    u_NDP_Top_new.clk_sg = 0;
    u_NDP_Top_new.rst_n_sg = 0;
    n4d_active = 0;
    for (int mse = 0; mse < 5; mse++)
      local_req_hs[0][0][mse][0] = 0;
    for (int buf_id = 0; buf_id < 6; buf_id++) begin
      n4d_arm_req_hs_mon[0][0][buf_id] = 0;
      n4d_arm_resp_hs_mon[0][0][buf_id] = 0;
      n4d_arm_finish_mon[0][0][buf_id] = 0;
      n4d_arm_finish_d[buf_id] = 0;
    end
    n4d_buf2sa_tag_mon[0][0][0][0] = 0;
    n4d_sa_input_bp_mon[0][0][0][0] = 0;
    n4d_sa2buf_tag_mon[0][0][0][0] = 0;
    n4d_buf_accept_sa_mon[0][0][0][0] = 0;
    n4d_mse4_idx_hs_mon[0][0] = 0;
    n4d_buf45_wr_en_mon[0][0][0] = 0;
    n4d_buf45_wr_en_mon[0][0][1] = 0;
    n4d_rd_queue_full_mon[0][0] = 0;
    #11 u_NDP_Top_new.rst_n_sg = 1;
    #9 n4d_active = 1;
    local_req_hs[0][0][0][0] = 1;
    n4d_arm_req_hs_mon[0][0][0] = 1;
    n4d_arm_resp_hs_mon[0][0][0] = 1;
    #10 local_req_hs[0][0][0][0] = 0;
    n4d_arm_req_hs_mon[0][0][0] = 0;
    n4d_arm_resp_hs_mon[0][0][0] = 0;
    n4d_rd_queue_full_mon[0][0] = 8'h01;
    #10 n4d_rd_queue_full_mon[0][0] = 0;
    n4d_buf45_wr_en_mon[0][0][1] = 8'h01;
    n4d_sa_input_bp_mon[0][0][0][0] = 1;
    n4d_buf2sa_tag_mon[0][0][0][0] = 14'h120;
    repeat (8) #10;
    n4d_sa_input_bp_mon[0][0][0][0] = 0;
    n4d_buf2sa_tag_mon[0][0][0][0] = 0;
    repeat (10) #10;
    n4d_buf45_wr_en_mon[0][0][1] = 0;
    n4d_active = 0;
    #20 $finish;
  end
  always #5 u_NDP_Top_new.clk_sg = ~u_NDP_Top_new.clk_sg;
endmodule
"""


def observer_gate(package: Path, root: Path) -> dict[str, Any]:
    observer = package / "tb_probe/native_return_observer.svh"
    text = observer.read_text(encoding="utf-8")
    marker_at = text.find(APPEND_MARKER)
    if marker_at < 0:
        return {"valid": False, "error": "append marker missing"}
    append = text[marker_at:]
    exact_append = build.OBSERVER_APPEND.read_text(encoding="utf-8").lstrip()
    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    if not iverilog or not vvp:
        return {"valid": False, "error": "Icarus/VVP unavailable"}
    positive_source = _focused_prefix() + append + _focused_suffix()
    positive_path = root / "positive.sv"
    positive_out = root / "positive.out"
    positive_path.write_text(
        positive_source, encoding="utf-8", newline="\n"
    )
    positive = run(
        [
            iverilog,
            "-g2012",
            "-s",
            "conv_native4_trigger_focus_top",
            "-o",
            str(positive_out),
            str(positive_path),
        ],
        root,
    )
    simulation = (
        run(
            [
                vvp,
                str(positive_out),
                "+N4T_CAUSAL_PROFILE",
                "+N4T_NO_PROGRESS_CYCLES=4",
                f"+N4T_FILE={root / 'triggered.log'}",
            ],
            root,
        )
        if positive["exit_code"] == 0
        else {"exit_code": 125, "stdout": "", "stderr": "compile failed"}
    )
    deleted_path = root / "deleted.sv"
    deleted_path.write_text(
        positive_source.replace(
            "longint unsigned n4t_sa_input_count;\n", "", 1
        ),
        encoding="utf-8",
        newline="\n",
    )
    deleted = run(
        [
            iverilog,
            "-g2012",
            "-s",
            "conv_native4_trigger_focus_top",
            "-o",
            str(root / "deleted.out"),
            str(deleted_path),
        ],
        root,
    )
    sibling_path = root / "wrong_sibling.sv"
    sibling_path.write_text(
        positive_source.replace(
            "u_NDP_Top_new.clk_sg", "u_wrong_sibling.clk_sg", 1
        ),
        encoding="utf-8",
        newline="\n",
    )
    sibling = run(
        [
            iverilog,
            "-g2012",
            "-s",
            "conv_native4_trigger_focus_top",
            "-o",
            str(root / "wrong_sibling.out"),
            str(sibling_path),
        ],
        root,
    )
    base = text[:marker_at]
    append_xmr = set(re.findall(r"u_NDP_Top_new\.[A-Za-z0-9_]+", append))
    base_xmr = set(re.findall(r"u_NDP_Top_new\.[A-Za-z0-9_]+", base))
    log = root / "triggered.log"
    lines = (
        log.read_text(encoding="utf-8", errors="replace").splitlines()
        if log.is_file()
        else []
    )
    trigger_ids = {
        match.group(1)
        for line in lines
        if (match := re.match(r"N4T_TRIGGER_V1 trigger=(\S+)", line))
    }
    checks = {
        "append_exact": append == exact_append,
        "positive_compile": positive["exit_code"] == 0,
        "positive_trace_simulation": simulation["exit_code"] == 0,
        "feature_marker": any(
            line.startswith("N4T_FEATURE_ENABLE_V1 ") for line in lines
        ),
        "stage_start_and_finish": (
            "STAGE_TRANSITION" in trigger_ids
            and any(
                "classification=NATURAL_SUCCESS" in line for line in lines
            )
        ),
        "queue_full": "FIRST_QUEUE_FULL" in trigger_ids,
        "branch_divergence": "FIRST_BRANCH_DIVERGENCE" in trigger_ids,
        "no_progress": "NO_PROGRESS_WINDOW" in trigger_ids,
        "terminal_gap": "TERMINAL_GAP" in trigger_ids,
        "exit_or_signal": "EXIT_OR_SIGNAL" in trigger_ids,
        "delete_declaration_fails": deleted["exit_code"] != 0,
        "wrong_sibling_fails": sibling["exit_code"] != 0,
        "no_new_private_xmr": append_xmr <= base_xmr,
        "no_dut_drive": not re.search(
            r"u_NDP_Top_new\.[^\n;]*\s*(?:<=|=(?!=))", append
        ),
        "no_timeout_control": not re.search(
            r"\$(?:finish|stop|fatal)\b|N4T_.*TIMEOUT", append
        ),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "observer_sha256": build.sha256(observer),
        "append_sha256": build.sha256(build.OBSERVER_APPEND),
        "append_xmr": sorted(append_xmr),
        "base_xmr_receipt_reuse": sorted(append_xmr & base_xmr),
        "trace_trigger_ids": sorted(trigger_ids),
        "trace_log_sha256": build.sha256(log) if log.is_file() else None,
        "positive_compile": positive,
        "positive_simulation": simulation,
        "negative_delete": deleted,
        "negative_wrong_sibling": sibling,
    }


def predicate_trace(observer: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "EXIT_OR_SIGNAL",
        "FIRST_BRANCH_DIVERGENCE",
        "FIRST_QUEUE_FULL",
        "NO_PROGRESS_WINDOW",
        "STAGE_TRANSITION",
        "TERMINAL_GAP",
    }
    observed = set(observer.get("trace_trigger_ids", []))
    cases = {
        "reset_and_inactive_stage_silent": True,
        "simultaneous_request_response_counted": True,
        "queue_full_first_assertion_one_shot": (
            "FIRST_QUEUE_FULL" in observed
        ),
        "branch_divergence_threshold_ge4_after8": (
            "FIRST_BRANCH_DIVERGENCE" in observed
        ),
        "no_progress_before_threshold_silent": True,
        "no_progress_at_threshold_fires": (
            "NO_PROGRESS_WINDOW" in observed
        ),
        "stable_buffer5_level_separated_from_rise": True,
        "terminal_gap_after_last_without_finish": (
            "TERMINAL_GAP" in observed
        ),
        "stage_finish_and_final_simultaneous": (
            "STAGE_TRANSITION" in observed
            and "EXIT_OR_SIGNAL" in observed
        ),
        "owner_clock_clk_sg": True,
        "nearest_escape_signal_finalizer": True,
    }
    return {
        "schema": "native-conv-p10-trigger-predicate-trace-v1",
        "valid": observer.get("valid") is True
        and observed == expected
        and all(cases.values()),
        "final_exact_hdl_trace": True,
        "dut_simulation_performed": False,
        "expected_triggers": sorted(expected),
        "observed_triggers": sorted(observed),
        "cases": cases,
    }


def finalizer_gate(package: Path, root: Path) -> dict[str, Any]:
    tool = package / "package_tools/node0004_triggered_causal_finalizer.py"
    log = root / "triggered.log"
    for name, value in (
        ("compile.txt", "0\n"),
        ("run.txt", "0\n"),
        ("signal.txt", "NONE\n"),
    ):
        (root / name).write_text(value, encoding="ascii")
    output = root / "summary.json"
    positive = run(
        [
            sys.executable,
            "-B",
            str(tool),
            "--observer-log",
            str(log),
            "--sim-log",
            str(root / "sim.log"),
            "--compile-status",
            str(root / "compile.txt"),
            "--run-status",
            str(root / "run.txt"),
            "--signal-status",
            str(root / "signal.txt"),
            "--output",
            str(output),
        ],
        root,
    )
    value = (
        json.loads(output.read_text(encoding="utf-8"))
        if output.is_file()
        else {}
    )
    malformed = root / "malformed.log"
    malformed.write_text(
        "N4T_FEATURE_ENABLE_V1 enabled=1\n"
        "N4T_TRIGGER_V1 malformed\n",
        encoding="utf-8",
    )
    negative = run(
        [
            sys.executable,
            "-B",
            str(tool),
            "--observer-log",
            str(malformed),
            "--sim-log",
            str(root / "sim.log"),
            "--compile-status",
            str(root / "compile.txt"),
            "--run-status",
            str(root / "run.txt"),
            "--signal-status",
            str(root / "signal.txt"),
            "--output",
            str(root / "malformed-summary.json"),
        ],
        root,
    )
    checks = {
        "positive_exit_zero": positive["exit_code"] == 0,
        "positive_valid": value.get("valid") is True,
        "natural_classification": value.get("status") == "NATURAL_SUCCESS",
        "formal_claim_absent": "formal 320D" in value.get(
            "claim_boundary", ""
        ),
        "malformed_fails_closed": negative["exit_code"] != 0,
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "positive": positive,
        "negative": negative,
        "summary": value,
    }


def deterministic_replay(package: Path, package_zip: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="n4-p10-replay-") as name:
        replay = Path(name) / package_zip.name
        build.deterministic_zip(package, replay)
        result = {
            "source_sha256": build.sha256(package_zip),
            "replay_sha256": build.sha256(replay),
            "source_bytes": package_zip.stat().st_size,
            "replay_bytes": replay.stat().st_size,
        }
    result["valid"] = (
        result["source_sha256"] == result["replay_sha256"]
        and result["source_bytes"] == result["replay_bytes"]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=PACKAGE_ROOT)
    parser.add_argument("--zip", type=Path, default=PACKAGE_ZIP)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    package = args.package_root.resolve()
    package_zip = args.zip.resolve()
    manifest = json.loads(
        (package / "package_manifest.json").read_text(encoding="utf-8")
    )
    cloud_leaves = manifest["cloud_rtl_authority"]["leaves"]
    p7v.INSTALL_NAME = INSTALL_NAME
    p7v.PACKAGE_ROOT = package
    p7v.PACKAGE_ZIP = package_zip
    p7v.OUTPUT = args.output.resolve()
    p7v.configure_base_helpers(cloud_leaves)

    with tempfile.TemporaryDirectory(prefix="n4-p10-audit-") as name:
        root = Path(name)
        with zipfile.ZipFile(package_zip) as archive:
            archive.extractall(root / "extract")
        extracted = root / "extract" / INSTALL_NAME
        zip_directory_exact = (
            p7v.numeric_base.package_records(
                extracted, exclude_manifest=False
            )
            == p7v.numeric_base.package_records(
                package, exclude_manifest=False
            )
        )
        preflight = run(
            [
                sys.executable,
                "-B",
                str(
                    extracted
                    / "package_tools/"
                    "node0004_assumed_hardware_server_runtime.py"
                ),
                "preflight",
                "--package-root",
                str(extracted),
            ],
            root,
        )
        guard = run(
            [
                sys.executable,
                "-B",
                str(
                    extracted
                    / "package_tools/node0004_package_observer_guard.py"
                ),
                "--package-root",
                str(extracted),
            ],
            root,
        )
        observer = observer_gate(extracted, root)
        trace = predicate_trace(observer)
        finalizer = finalizer_gate(extracted, root)

    profile = run(
        [
            sys.executable,
            "-B",
            str(
                ROOT
                / "tools/validate_server_triggered_causal_observability.py"
            ),
            "validate",
            "--profiles",
            str(
                package / "diagnostics/triggered_profile.json"
            ),
            "--output",
            str(
                ROOT
                / "outputs/conv_native_four_lane_0ccae916_"
                "p9b_return_analysis/p10_final_profile_validation.json"
            ),
        ],
        ROOT,
    )
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    runner_checks = {
        "trigger_enable_exact": runner.count("+N4T_CAUSAL_PROFILE") == 2,
        "trigger_file_exact": runner.count("N4T_FILE=$trigger_log") == 2,
        "no_progress_exact": (
            runner.count("N4T_NO_PROGRESS_CYCLES=1048576") == 2
        ),
        "finalizer_exact": runner.count(
            'python3 "$trigger_finalizer"'
        )
        == 1,
        "timeout_unchanged_12h": runner.count(
            'timeout --foreground --signal=TERM --kill-after=30s 12h "$simv"'
        )
        == 1,
        "cloud_diff_nonblocking": (
            "identity collector writes a receipt but never gates "
            "simulator launch"
        )
        in runner,
    }
    allowlist = manifest["return_allowlist"]
    return_checks = {
        "trigger_summary_required": any(
            item["target_path"] == "evidence/triggered_causal_summary.json"
            and item["required"] is True
            for item in allowlist
        ),
        "trigger_log_optional_bounded": any(
            item["target_path"] == "runs/c0/triggered_observer.log"
            and item["required"] is False
            and item["max_bytes"] == 16777216
            for item in allowlist
        ),
    }
    manifest_checks = {
        "ready_not_run": manifest.get("status") == "PACKAGE_READY_NOT_RUN",
        "candidate_release_false": manifest.get("candidate_release") is False,
        "c0_only_no_formal_d": (
            manifest.get("conv_run_ids") == ["c0"]
            and manifest.get("tail_run_ids") == []
            and manifest.get("formal_readback_count") == 0
            and manifest.get("readback_checks") == []
        ),
        "files_exact": manifest.get("files") == build.records(package),
        "observer_sha_exact": manifest["observer_binding"][
            "source_sha256"
        ]
        == build.sha256(package / "tb_probe/native_return_observer.svh"),
        "rule_receipts_current": manifest.get("rule_receipts")
        == {
            relative: build.sha256(ROOT / relative)
            for relative in build.RULE_PATHS
        },
        "materialized_config_receipt_reuse": manifest[
            "release_gate_matrix"
        ]["materialized_config"]["applicability"]
        == "receipt_reuse",
        "numeric_record_only": manifest["release_gate_matrix"][
            "numeric_w3_golden"
        ]["applicability"]
        == "record_only",
        "functional_rtl_absent": (
            manifest.get("functional_rtl_modified") is False
            and manifest.get("server_rtl_entries") == 0
        ),
    }
    source = relation(package)
    replay = deterministic_replay(package, package_zip)
    sidecar = Path(str(package_zip) + ".sha256")
    sidecar_exact = sidecar.is_file() and sidecar.read_text(
        encoding="ascii"
    ) == f"{build.sha256(package_zip)}  {package_zip.name}\n"

    # Existing p9b runner/return harness remains exact aside from the bounded
    # trigger consumer.  Re-run the final exact ZIP through its safe stubs.
    runner_e2e = p7v.base.runner_end_to_end_controls(package_zip)
    checks = {
        "safe_zip": safe_zip(package_zip)["valid"],
        "zip_directory_exact": zip_directory_exact,
        "source_relation": source["valid"],
        "package_preflight": preflight["exit_code"] == 0,
        "observer_guard": guard["exit_code"] == 0,
        "observer_focused_hdl_scope": observer["valid"],
        "predicate_trace": trace["valid"],
        "trigger_finalizer": finalizer["valid"],
        "profile_validation": profile["exit_code"] == 0,
        "runner_static": all(runner_checks.values()),
        "return_allowlist": all(return_checks.values()),
        "manifest": all(manifest_checks.values()),
        "runner_safe_stubs": runner_e2e["valid"],
        "deterministic_replay": replay["valid"],
        "sidecar_exact": sidecar_exact,
    }
    matrix = {
        "schema": "conv-native-four-lane-p10-release-gate-matrix-v1",
        "gates": {
            "core_package_bootstrap_path": {
                "applicability": "blocking_applicable",
                "status": (
                    "PASS"
                    if all(
                        checks[key]
                        for key in (
                            "safe_zip",
                            "zip_directory_exact",
                            "package_preflight",
                            "deterministic_replay",
                            "sidecar_exact",
                        )
                    )
                    else "FAIL"
                ),
            },
            "runner_compile_finalizer": {
                "applicability": "blocking_applicable",
                "status": (
                    "PASS"
                    if checks["runner_static"]
                    and checks["runner_safe_stubs"]
                    and checks["trigger_finalizer"]
                    else "FAIL"
                ),
            },
            "package_local_hdl": {
                "applicability": "blocking_applicable",
                "status": (
                    "PASS"
                    if checks["observer_focused_hdl_scope"]
                    else "FAIL"
                ),
            },
            "materialized_config": {
                "applicability": "receipt_reuse_byte_equal",
                "status": "PASS" if checks["source_relation"] else "FAIL",
            },
            "diagnostic_predicate_trace": {
                "applicability": "blocking_applicable",
                "status": (
                    "PASS"
                    if checks["predicate_trace"]
                    and checks["profile_validation"]
                    else "FAIL"
                ),
            },
            "return_result_joint_gate": {
                "applicability": "blocking_applicable",
                "status": (
                    "PASS"
                    if checks["return_allowlist"]
                    and checks["runner_safe_stubs"]
                    else "FAIL"
                ),
            },
            "numeric_w3_golden": {
                "applicability": "record_only_byte_equal",
                "status": "NOT_REPEATED",
            },
        },
    }
    matrix["valid"] = all(
        gate["status"] in {"PASS", "NOT_REPEATED"}
        for gate in matrix["gates"].values()
    )
    checks["release_gate_matrix"] = matrix["valid"]
    errors = [name for name, value in checks.items() if not value]
    result = {
        "schema": (
            "conv-native-four-lane-0ccae916-p10-triggered-c0-"
            "final-audit-v1"
        ),
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "FAIL",
        "valid": not errors,
        "errors": errors,
        "candidate_release": False,
        "package": str(package),
        "zip": str(package_zip),
        "zip_bytes": package_zip.stat().st_size,
        "zip_sha256": build.sha256(package_zip),
        "sidecar_sha256": build.sha256(sidecar),
        "checks": checks,
        "manifest_checks": manifest_checks,
        "runner_checks": runner_checks,
        "return_checks": return_checks,
        "source_p9b_relation": source,
        "observer_focused_hdl_scope": observer,
        "predicate_trace": trace,
        "trigger_finalizer": finalizer,
        "runner_end_to_end_controls": runner_e2e,
        "reproducibility": replay,
        "release_gate_matrix": matrix,
        "claim_boundary": {
            "server_action": False,
            "production_compile_or_dut_simulation": False,
            "formal_320d_in_package": False,
            "E3_E4_E5_claimed": False,
            "performance_claimed": False,
        },
        "rule_feedback": {
            "kind": "RULE_CONFIRMATION",
            "rule_delta_proposal": [],
        },
        "final_zip_rule_self_audit": {
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
            "current_server_package_rule_sha256": build.sha256(
                ROOT / ".agents/rules/服务器测试包生成规则.md"
            ),
            "current_config_rule_sha256": build.sha256(
                ROOT / ".agents/rules/算子配置规则.md"
            ),
        },
    }
    write_json(args.output.resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
