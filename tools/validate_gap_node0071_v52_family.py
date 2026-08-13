#!/usr/bin/env python3
"""Changed-surface validation for the exact GAP node0071 v52 ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
import stat


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_n71_gap_v52_ga_read_mse4_direct_diag"
SOURCE_NAME = "r5_n71_gap_v51_ga_ob_mode_factor_diag"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_NAME}.zip"
SOURCE_SHA = "76336937dd52822e948dcc81c6f35054c73d0066dfad5f964b6753a04a78f7b4"
MARKER = "    // v52: qualified-only all-slice GA selected-read to MSE4 direct consumer."
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
INDEX_SHA = "b3c5d7dcfb5a6417d38448f98e0cecac716ec05568aa454c4a99f447b1e69378"
SERVER_SHA = "1fa6d9be4894d914e1f7b1889b0f62c7ed43f661e77de2afd1b97472b2be019c"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def zip_map(path: Path, expected_root: str) -> tuple[dict[str, bytes], dict[str, bool]]:
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos]
        roots = {PurePosixPath(name).parts[0] for name in names if name}
        checks = {
            "crc": archive.testzip() is None,
            "single_root": roots == {expected_root},
            "path_safe": all(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts and "\\" not in name for name in names),
            "duplicate_free": len(names) == len(set(names)),
            "symlink_free": all(not stat.S_ISLNK((row.external_attr >> 16) & 0xFFFF) for row in infos),
        }
        members = {PurePosixPath(*PurePosixPath(row.filename).parts[1:]).as_posix(): archive.read(row) for row in infos if not row.is_dir()}
    return members, checks


def run(argv: list[str], cwd: Path) -> dict[str, object]:
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, check=False)
    return {"argv": argv, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def focused_wrapper(extension: str) -> str:
    body = extension.replace("u_NDP_Top_new.clk_sg", "clk_sg").replace("u_NDP_Top_new.rst_n_sg", "rst_n_sg").replace("u_NDP_Top_new.clk_db", "clk_db").replace("u_NDP_Top_new.rst_n_db", "rst_n_db")
    declarations = """
`define GLB_SLICE_NUM 16
`define SLICE_GROUP_SIZE 4
`define SLICE_GROUP_NUM 4
`define GA_ROW_PE_NUM 4
`define GA_PE_OUTBUFFER_CNT_WIDTH 2
module gap_v52_changed_surface;
  logic clk_sg, clk_db, rst_n_sg, rst_n_db;
  bit return_obs_enabled;
  integer return_obs_fd;
  logic return_obs_ga_outbuffer_wr_mon [4][4][4][2];
  logic return_obs_v51_selected_rd_mon [4][4][4][2];
  logic return_obs_v51_is_transout_mon [4][4][4][2];
  logic [1:0] return_obs_ga_ob_count_mon [4][4][4][2];
  logic return_obs_mse4_idx_hs_mon [4][4];
  logic return_obs_pair_m4_req_valid_mon [4][4];
  logic return_obs_pair_m4_req_ready_mon [4][4];
  logic return_obs_pair_m4_q_wr_mon [4][4];
  logic return_obs_pair_m4_q_rd_mon [4][4];
  logic return_obs_pair_m4_buf_accept_mon [4][4];
  logic return_obs_pair_m4_prep_wr_mon [4][4];
  logic return_obs_pair_m4_prep_rd_mon [4][4];
  logic [1:0] return_obs_pair_m4_ob_wr_mon [4][4];
  logic [1:0] return_obs_pair_m4_ob_rd_mon [4][4];
  logic [1:0] local_req_hs [4][4][5];
  logic [1:0] local_wdata_hs [4][4][5];
  logic return_obs_pair_m4_finish_mon [4][4];
"""
    return declarations + body + "\nendmodule\n"


def compile_sv(source: str, directory: Path, label: str) -> dict[str, object]:
    path = directory / f"{label}.sv"
    path.write_text(source, encoding="utf-8", newline="\n")
    result = run([str(IVERILOG), "-g2012", "-tnull", "-s", "gap_v52_changed_surface", str(path)], directory)
    result["source_sha256"] = sha_bytes(source.encode())
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument("--runner-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = args.target_zip.resolve()
    errors: list[str] = []
    members, archive_checks = zip_map(target, NAME)
    source, source_checks = zip_map(SOURCE, SOURCE_NAME)
    if sha(SOURCE) != SOURCE_SHA:
        errors.append("source_sha")
    errors.extend(f"archive:{key}" for key, value in archive_checks.items() if not value)
    manifest = json.loads(members["TEST_PACKAGE_MANIFEST.json"])
    payload = {key: value for key, value in members.items() if key != "TEST_PACKAGE_MANIFEST.json"}
    declared = manifest.get("files", {})
    manifest_checks = {
        "exact_set": set(payload) == set(declared),
        "per_file_receipts": all(declared[key]["size_bytes"] == len(value) and declared[key]["sha256"] == sha_bytes(value) for key, value in payload.items()),
        "identity": manifest.get("install_name") == NAME and manifest.get("package_name") == NAME + ".zip",
        "source_binding": manifest.get("source_package", {}).get("sha256") == SOURCE_SHA,
        "allowlist_85": len(manifest.get("return_allowlist", [])) == 85,
        "formal_d_48": len(manifest.get("readback_checks", [])) == 48,
        "repeatable_return": manifest.get("repeat_execution_contract", {}).get("return_name_policy") == "UNIQUE_PER_EXECUTION_PRESERVE_PRIOR_RETURNS",
        "current_receipts": manifest.get("rule_receipts", {}).get("server_package_rule_sha256") == SERVER_SHA and manifest.get("rule_receipts", {}).get("generation_index_sha256") == INDEX_SHA,
    }
    errors.extend(f"manifest:{key}" for key, value in manifest_checks.items() if not value)
    normalized = {key: value.replace(NAME.encode(), SOURCE_NAME.encode()) for key, value in members.items()}
    changed = sorted(key for key in set(source) | set(normalized) if source.get(key) != normalized.get(key))
    expected_changed = sorted([
        "PREPARE_AND_RUN.sh", "README.md", "SERVER_RUNTIME_LAYOUT_CONTRACT.json", "TEST_PACKAGE_MANIFEST.json",
        "package_tools/gap_node0071_complete_server_runtime.py", "package_tools/gap_node0071_ga_read_mse4_direct_decision.py",
        "provenance/v51_to_v52_ga_read_mse4_direct.json", "tb_probe/native_return_observer.svh",
    ])
    freeze_checks = {
        "normalized_changed_exact_set": changed == expected_changed,
        "source_archive_safe": all(source_checks.values()),
        "numeric_workload_config_golden_byte_equal": all(source.get(key) == normalized.get(key) for key in source if key.startswith("workload/")),
        "timeout_unchanged": [line for line in normalized["PREPARE_AND_RUN.sh"].splitlines() if b"timeout " in line] == [line for line in source["PREPARE_AND_RUN.sh"].splitlines() if b"timeout " in line],
        "functional_rtl_absent": not any(key.startswith("rtl/") for key in members),
    }
    errors.extend(f"freeze:{key}" for key, value in freeze_checks.items() if not value)
    observer = members["tb_probe/native_return_observer.svh"].decode()
    extension = observer[observer.index(MARKER):]
    semantics = {
        "owner_clk_sg": "always @(posedge u_NDP_Top_new.clk_sg" in extension,
        "reporter_clk_db": "always @(posedge u_NDP_Top_new.clk_db" in extension,
        "qualified_limit_320": "qualified_changed && return_obs_v52_emit_count < 320" in extension,
        "heartbeat_outside_budget": "if (qualified_changed)\n                    return_obs_v52_emit_count++;" in extension,
        "stable_level_not_progress": '(qualified_changed ? "QUALIFIED_EDGE" : "HEARTBEAT")' in extension,
        "all_17_masks_in_snapshot": extension.count("return_obs_v52_") > 100 and "logic [17*`GLB_SLICE_NUM-1:0] qualified_snapshot;" in extension,
        "local_req_existing_surface": "if (|local_req_hs[g][s][4])" in extension,
        "local_wdata_existing_surface": "if (|local_wdata_hs[g][s][4])" in extension,
        "no_undefined_local_alias": "return_obs_mse4_local_req_hs_mon" not in extension and "return_obs_mse4_local_wdata_hs_mon" not in extension,
    }
    errors.extend(f"semantics:{key}" for key, value in semantics.items() if not value)
    focused = focused_wrapper(extension)
    with tempfile.TemporaryDirectory(prefix="gap-v52-hdl-") as tmp:
        directory = Path(tmp)
        positive = compile_sv(focused, directory, "positive")
        delete_decl = compile_sv(focused.replace("  logic [1:0] local_req_hs [4][4][5];\n", "", 1), directory, "delete_declaration")
        typo_use = compile_sv(focused.replace("local_wdata_hs[g][s][4]", "local_wdata_hx[g][s][4]", 1), directory, "typo_use")
    delete_update_text = extension.replace("return_obs_v52_m4_local_req_seen[id] <= 1'b1;", "", 1)
    hdl = {
        "tool": str(IVERILOG), "positive": positive, "delete_declaration": delete_decl, "typo_use": typo_use,
        "checks": {
            "positive_exit_zero": positive["exit_code"] == 0,
            "delete_declaration_exit_nonzero": delete_decl["exit_code"] != 0,
            "typo_use_exit_nonzero": typo_use["exit_code"] != 0,
            "delete_key_update_fail_closed": "return_obs_v52_m4_local_req_seen[id] <= 1'b1;" not in delete_update_text,
        },
        "claim_boundary": "Exact changed observer syntax/name resolution against a focused wrapper containing only reused package-local surfaces; not full-design elaboration or DUT simulation.",
    }
    errors.extend(f"hdl:{key}" for key, value in hdl["checks"].items() if not value)
    with tempfile.TemporaryDirectory(prefix="gap-v52-parser-") as tmp:
        directory = Path(tmp)
        script = directory / "parser.py"
        output = directory / "trace.json"
        script.write_bytes(members["package_tools/gap_node0071_ga_read_mse4_direct_decision.py"])
        predicate = run([sys.executable, str(script), "self-test", "--output", str(output)], directory)
        predicate_payload = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    predicate["payload"] = predicate_payload
    predicate["all_checks_true"] = predicate["exit_code"] == 0 and predicate_payload.get("pass") is True and all(predicate_payload.get("checks", {}).values())
    if not predicate["all_checks_true"]:
        errors.append("predicate_trace")
    runner_report = json.loads(args.runner_report.read_text(encoding="utf-8"))
    runner = members["PREPARE_AND_RUN.sh"].decode()
    runner_checks = {
        "feature_plusarg": "+RETURN_OBS_GA_READ_MSE4_DIRECT" in runner,
        "parser_bound": "gap_node0071_ga_read_mse4_direct_decision.py" in runner,
        "unique_return": 'return_tag="r$(date -u +%s%N)_$$"' in runner,
        "harness_valid": runner_report.get("valid") is True and runner_report.get("errors") == [],
        "parser_exit_zero": runner_report.get("checks", {}).get("normal_all_decision_parsers_exit_zero") is True,
        "parser_stderr_empty": runner_report.get("checks", {}).get("normal_decision_parser_stderr_empty") is True,
    }
    errors.extend(f"runner:{key}" for key, value in runner_checks.items() if not value)
    result = {
        "schema": "gap-node0071-v52-family-validation-v1", "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d", "target_zip": str(target.relative_to(ROOT)).replace("\\", "/"),
        "target_zip_bytes": target.stat().st_size, "target_zip_sha256": sha(target), "archive_checks": archive_checks,
        "manifest_checks": manifest_checks, "freeze_checks": freeze_checks, "normalized_changed_members": changed,
        "observer_semantics": semantics, "hdl_scope": hdl, "predicate_trace": predicate, "runner_checks": runner_checks,
        "errors": errors, "valid": not errors,
        "claim_boundary": "Exact final package-local changed surfaces and frozen-byte receipts only; no server/DUT run, natural terminal, formal D, E3, E4, or E5 claim.",
    }
    write_json(args.output, result)
    print(json.dumps({"output": str(args.output), "sha256": sha(args.output), "valid": not errors, "errors": errors}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
