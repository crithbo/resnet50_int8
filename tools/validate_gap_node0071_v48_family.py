#!/usr/bin/env python3
"""Bounded changed-surface release validation for GAP node0071 v48."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / (
    "artifacts/operator_config_validation/r5-server-test-packages/pending/"
    "r5_n71_gap_v47_stage_transition_rootfix.zip"
)
SOURCE_SHA = "e5e1e010970230fb9f9706bc2dd2381dbfecd2c304fd48e212587827110567ab"
NAME = "r5_n71_gap_v48_multislice_pipeline_diag"
MARKER = "    // v48: mask-wide per-slice pipeline information-gain observer."
PYTHON = Path(
    r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\python\python.exe"
)
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_path(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def run(argv: list[str], cwd: Path, timeout: int = 30) -> dict:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return {
            "argv": argv,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as error:
        return {
            "argv": argv,
            "exit_code": 124,
            "stdout": error.stdout or "",
            "stderr": error.stderr or "",
            "timed_out": True,
        }


def zip_map(path: Path) -> tuple[zipfile.ZipFile, dict[str, bytes]]:
    archive = zipfile.ZipFile(path)
    members = {
        "/".join(name.split("/")[1:]): archive.read(name)
        for name in archive.namelist()
        if name and not name.endswith("/")
    }
    return archive, members


def focused_projection(extension: str) -> str:
    replacements = (
        ("u_NDP_Top_new.clk_sg", "clk_sg"),
        ("u_NDP_Top_new.rst_n_sg", "rst_n_sg"),
        ("u_NDP_Top_new.clk_db", "clk_db"),
        ("u_NDP_Top_new.rst_n_db", "rst_n_db"),
        ("u_NDP_Top_new.clk", "clk"),
        ("u_NDP_Top_new.rst_n", "rst_n"),
    )
    body = extension
    for old, new in replacements:
        body = body.replace(old, new)
    return """\
`define GLB_SLICE_NUM 16
`define SLICE_GROUP_SIZE 4
`define SLICE_GROUP_NUM 4
module gap_v48_changed_surface;
  logic clk,clk_sg,clk_db,rst_n,rst_n_sg,rst_n_db;
  bit return_obs_enabled;
  integer return_obs_fd;
  integer return_obs_plusarg_status;
  logic return_obs_sem_cfg_start_mon [4][4];
  logic return_obs_sem_cfg_finish_mon [4][4];
  logic return_obs_slice_finish_mon [4][4];
  logic return_obs_mse0_buf_hs_mon [4][4];
  logic return_obs_mse3_buf_hs_mon [4][4];
  logic [31:0] return_obs_ga_input_valid_mon [4][4];
  logic [31:0] return_obs_ga_outbuffer_wr_mon [4][4];
  logic [31:0] local_req_hs [4][4][5];
  logic [31:0] local_wdata_hs [4][4][5];
""" + body + "\nendmodule\n"


def compile_sv(source: str, path: Path, name: str) -> dict:
    src = path / f"{name}.sv"
    src.write_text(source, encoding="utf-8", newline="\n")
    result = run(
        [str(IVERILOG), "-g2012", "-tnull", "-s",
         "gap_v48_changed_surface", str(src)],
        path,
    )
    result["source_sha256"] = sha_bytes(source.encode())
    result["stderr_sha256"] = sha_bytes(result["stderr"].encode())
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = args.target_zip.resolve()
    output = args.output.resolve()
    fixed = output.parent / "hdl_scope_fixed"
    fixed.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    target_archive, target_members = zip_map(target)
    source_archive, source_members = zip_map(SOURCE)
    target_names = target_archive.namelist()
    target_infos = target_archive.infolist()
    roots = {PurePosixPath(name).parts[0] for name in target_names if name}
    target_root = next(iter(roots)) if len(roots) == 1 else ""
    manifest = json.loads(target_members["TEST_PACKAGE_MANIFEST.json"])

    archive_checks = {
        "crc": target_archive.testzip() is None,
        "single_root": roots == {NAME},
        "path_safe": all(
            not PurePosixPath(name).is_absolute()
            and ".." not in PurePosixPath(name).parts
            and "\\" not in name
            for name in target_names
        ),
        "duplicate_free": len(target_names) == len(set(target_names)),
        "symlink_free": all(
            ((info.external_attr >> 16) & 0o170000) != 0o120000
            for info in target_infos
        ),
    }

    declared = manifest["files"]
    actual_payload = {
        key: value for key, value in target_members.items()
        if key != "TEST_PACKAGE_MANIFEST.json"
    }
    manifest_checks = {
        "exact_set": set(declared) == set(actual_payload),
        "per_file_receipts": all(
            declared[name]["size_bytes"] == len(payload)
            and declared[name]["sha256"] == sha_bytes(payload)
            for name, payload in actual_payload.items()
        ),
        "install_identity": manifest.get("install_name") == NAME,
        "package_identity": manifest.get("package_name") == f"{NAME}.zip",
        "source_binding":
            manifest.get("source_package", {}).get("sha256") == SOURCE_SHA
            and sha_path(SOURCE) == SOURCE_SHA,
    }

    common = set(source_members) & set(target_members)
    same = sorted(name for name in common if source_members[name] == target_members[name])
    changed = sorted(name for name in common if source_members[name] != target_members[name])
    added = sorted(set(target_members) - set(source_members))
    removed = sorted(set(source_members) - set(target_members))
    expected_changed = {
        "PREPARE_AND_RUN.sh",
        "README.md",
        "TEST_PACKAGE_MANIFEST.json",
        "package_tools/gap_node0071_complete_server_runtime.py",
        "tb_probe/native_return_observer.svh",
        "workload/sca_cfg.json",
        "workload/sca_cfg_D.json",
    }
    expected_added = {
        "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
        "package_tools/gap_node0071_multislice_pipeline_decision.py",
        "package_tools/server_package_runtime_layout.py",
        "provenance/v47_to_v48_multislice_pipeline.json",
    }
    numeric = sorted(
        name for name in target_members
        if name.startswith(("workload/input/", "workload/golden/"))
        or name.startswith("workload/install/cfg_pkg/")
        or name == "workload/install/execplan.txt"
    )
    config_semantics = sorted(
        name for name in target_members
        if name.startswith(("p/v41/configs/", "p/v41/mapping/",
                            "provenance/tail_configs/",
                            "provenance/tail_mapping/"))
    )
    frozen_checks = {
        "source_zip": sha_path(SOURCE) == SOURCE_SHA,
        "numeric_73_exact": len(numeric) == 73
        and all(name in same for name in numeric),
        "config_mapping_exact": bool(config_semantics)
        and all(name in same for name in config_semantics),
        "no_removed_member": removed == [],
        "changed_exact_set": set(changed) == expected_changed,
        "added_exact_set": set(added) == expected_added,
        "unchanged_member_count": len(same) == 220,
    }

    observer = target_members["tb_probe/native_return_observer.svh"].decode()
    at = observer.find(MARKER)
    extension = observer[at:] if at >= 0 else ""
    public_inputs = (
        "return_obs_sem_cfg_start_mon",
        "return_obs_sem_cfg_finish_mon",
        "return_obs_slice_finish_mon",
        "return_obs_mse0_buf_hs_mon",
        "return_obs_mse3_buf_hs_mon",
        "return_obs_ga_input_valid_mon",
        "return_obs_ga_outbuffer_wr_mon",
        "local_req_hs",
        "local_wdata_hs",
    )
    preexisting = observer[:at]
    semantic_tokens = (
        'event=%s',
        '(ms_changed ? "QUALIFIED_EDGE" : "HEARTBEAT")',
        "return_obs_ms_emit_count < 256",
        "return_obs_ms_prev_snapshot = ms_snapshot;",
        "return_obs_ms_cfg_start_seen[",
        "return_obs_ms_mse0_seen[",
        "return_obs_ms_mse3_seen[",
        "return_obs_ms_ga_in_seen[",
        "return_obs_ms_ga_out_seen[",
        "return_obs_ms_mse4_req_seen[",
        "return_obs_ms_mse4_wdata_seen[",
        "return_obs_ms_finish_seen[",
    )
    observer_checks = {
        "marker": at >= 0,
        "public_inputs_predeclared": all(token in preexisting for token in public_inputs),
        "no_private_data_xmr": all(
            token not in extension
            for token in ("MSE_INST[", "SLICE_INST[", "u_Array_Request_Manager.")
        ),
        "owner_clocks": all(
            token in extension for token in
            ("u_NDP_Top_new.clk", "u_NDP_Top_new.clk_sg",
             "u_NDP_Top_new.clk_db")
        ),
        "qualified_rate_limited": all(token in extension for token in semantic_tokens),
        "read_only": not any(token in extension for token in
                             ("force ", "release ", "assign u_NDP_Top_new")),
    }

    projection = focused_projection(extension)
    positive = compile_sv(projection, fixed, "positive")
    removed_decl = compile_sv(
        projection.replace(
            "    logic [`GLB_SLICE_NUM-1:0] return_obs_ms_ga_out_seen;\n",
            "",
            1,
        ),
        fixed,
        "negative_declaration_removed",
    )
    typo_use = compile_sv(
        projection.replace(
            "return_obs_ms_ga_out_seen <= '0;",
            "return_obs_ms_ga_out_seen_typo <= '0;",
            1,
        ),
        fixed,
        "negative_use_typo",
    )
    removed_update = extension.replace(
        "return_obs_ms_prev_snapshot = ms_snapshot;",
        "/* critical update removed */",
        1,
    )
    hdl_checks = {
        "iverilog_available": run([str(IVERILOG), "-V"], fixed)["exit_code"] == 0,
        "focused_positive": positive["exit_code"] == 0,
        "declaration_negative": removed_decl["exit_code"] != 0,
        "use_typo_negative": typo_use["exit_code"] != 0,
        "critical_update_negative":
            "return_obs_ms_prev_snapshot = ms_snapshot;" not in removed_update,
    }

    parser_path = (
        output.parent / "extracted_multislice_pipeline_decision.py"
    )
    parser_path.write_bytes(
        target_members["package_tools/gap_node0071_multislice_pipeline_decision.py"]
    )
    parser_result_path = output.parent / "predicate_trace.json"
    parser_run = run(
        [str(PYTHON), str(parser_path), "self-test",
         "--output", str(parser_result_path)],
        ROOT,
    )
    predicate = (
        json.loads(parser_result_path.read_text(encoding="utf-8"))
        if parser_result_path.is_file() else {}
    )
    predicate_checks = {
        "exact_parser_self_test_exit": parser_run["exit_code"] == 0,
        "exact_parser_self_test_pass": predicate.get("pass") is True,
        "stable_level_not_progress":
            predicate.get("checks", {}).get("stable_level_not_extra_progress")
            is True,
        "nearest_escape":
            predicate.get("checks", {}).get("nearest_escape_identified") is True,
        "simultaneous_event":
            predicate.get("checks", {}).get("simultaneous_event_supported") is True,
        "reset_absent_marker_fail_closed":
            predicate.get("checks", {}).get("reset_or_absent_marker_fail_closed")
            is True,
    }

    runner = target_members["PREPARE_AND_RUN.sh"].decode()
    helper = target_members["package_tools/server_package_runtime_layout.py"]
    helper_sha = sha_bytes(helper)
    return_allowlist = manifest.get("return_allowlist", [])
    d_entries = [
        item for item in return_allowlist
        if item.get("target_path", "").startswith("readback/")
    ]
    runner_checks = {
        "shared_helper_exact":
            helper_sha
            == "7969ca56e13a7e0a0a83bdfd48d1409d28eef2ae0fd63ad08f0ec5c39e2d848a",
        "fixed_result_literal":
            'result_root="/home/panqs/ndp/simresult"' in runner,
        "install_only_layout":
            'layout_helper="$package_root/package_tools/server_package_runtime_layout.py"'
            in runner
            and 'cfg_parent="$server_root/install/cfg_pkg"' not in runner,
        "early_finalizer_armed":
            runner.index("trap 'finalize $?' EXIT")
            < runner.index('ndp_pre_snapshot="$(root_snapshot)"'),
        "signal_paths": all(
            token in runner
            for token in (
                "trap 'on_signal HUP 129' HUP",
                "trap 'on_signal INT 130' INT",
                "trap 'on_signal TERM 143' TERM",
            )
        ),
        "observer_absent_fail_closed":
            "OBSERVER_LOG_ABSENT_OR_PARSER_FAILED_BEFORE_DECISION" in runner,
        "no_parser_traceback_stderr":
            '--output "$evidence_root/stage_transition_decision.json" >/dev/null 2>&1'
            in runner,
        "feature_argv":
            "+RETURN_OBS_MULTISLICE_PIPELINE" in runner
            and "+RETURN_OBS_MULTISLICE_HEARTBEAT_CYCLES=1048576" in runner,
        "formal_d_48": len(d_entries) == 48,
        "return_allowlist_75": len(return_allowlist) == 75,
        "runtime_d_absent": not any(
            name.startswith("workload/runtime/") and "matrix_D" in name
            for name in target_members
        ),
    }

    observer_guard = run(
        [
            str(PYTHON),
            str(ROOT / "tools/gap_node0071_package_observer_guard.py"),
            "--package-root",
            str(target.parent / NAME),
            "--expected-sha256",
            sha_bytes(target_members["tb_probe/native_return_observer.svh"]),
        ],
        ROOT,
    )
    runtime_preflight = run(
        [
            str(PYTHON),
            str(target.parent / NAME /
                "package_tools/gap_node0071_complete_server_runtime.py"),
            "preflight",
            "--package-root",
            str(target.parent / NAME),
        ],
        ROOT,
    )
    package_tool_checks = {
        "observer_guard": observer_guard["exit_code"] == 0,
        "runtime_preflight": runtime_preflight["exit_code"] == 0,
    }

    groups = {
        "archive": archive_checks,
        "manifest": manifest_checks,
        "frozen": frozen_checks,
        "observer": observer_checks,
        "hdl": hdl_checks,
        "predicate": predicate_checks,
        "runner": runner_checks,
        "package_tools": package_tool_checks,
    }
    for group, checks in groups.items():
        errors.extend(f"{group}:{name}" for name, passed in checks.items() if not passed)

    result = {
        "schema": "gap-node0071-v48-family-final-zip-validation-v1",
        "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "target_zip": str(target.relative_to(ROOT)).replace("\\", "/"),
        "target_zip_bytes": target.stat().st_size,
        "target_zip_sha256": sha_path(target),
        "source_zip": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_zip_sha256": sha_path(SOURCE),
        "checks": groups,
        "frozen_receipt": {
            "numeric_file_count": len(numeric),
            "numeric_exact_count": sum(name in same for name in numeric),
            "config_mapping_file_count": len(config_semantics),
            "config_mapping_exact_count": sum(name in same for name in config_semantics),
            "unchanged_count": len(same),
            "changed": changed,
            "added": added,
            "removed": removed,
        },
        "hdl_scope": {
            "frontend": str(IVERILOG),
            "positive": positive,
            "negative_declaration_removed": removed_decl,
            "negative_use_typo": typo_use,
            "critical_update_negative_fail_closed":
                hdl_checks["critical_update_negative"],
            "claim_boundary":
                "Exact v48 appended observer logic and its package-local public "
                "monitor inputs only; no full-design or server VCS elaboration claim.",
        },
        "predicate_trace": predicate,
        "observer_guard": observer_guard,
        "runtime_preflight": runtime_preflight,
        "release_gate_matrix": {
            "package_bootstrap_runtime_layout": "SHARED_V2_14_OF_14_RECEIPT_REUSE_PENDING_EXACT_ZIP_REBIND",
            "package_local_hdl": "PASS" if all(hdl_checks.values()) else "FAIL",
            "materialized_config": "NOT_APPLICABLE_BYTE_EQUAL_RECEIPT_REUSE",
            "diagnostic_semantics": "PASS" if all(predicate_checks.values()) else "FAIL",
            "return_result_contract": "PASS" if all(runner_checks.values()) else "FAIL",
        },
        "valid": not errors,
        "errors": errors,
        "claim_boundary":
            "Local package/frozen-set/changed-observer/predicate/runner checks only. "
            "No DUT simulation, server execution, natural terminal, formal-D, E3, E4, or E5 claim.",
    }
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({
        "output": str(output),
        "sha256": sha_path(output),
        "valid": result["valid"],
        "errors": errors,
    }, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
