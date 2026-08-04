from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


INSTALL_NAME = "r5_n4_hw_v30_mse4_descriptor_diag"
MARKER = "    // v30: qualified WR_Memory_AG descriptor -> WR_Data_Channel FIFO/data release."
ACTIVE_FILES = {
    "RD_Buffer_AG": "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv",
    "WR_Data_Channel": "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv",
    "WR_Memory_AG": "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Memory_AG.sv",
    "FIFO": "NDP_copy01/rtl/utils/FIFO/FIFO.sv",
}
LEAVES = {
    "RD_Buffer_AG": ("buf_ag_last_req_flag", "wr_data_chl_ready"),
    "WR_Data_Channel": ("wr_chl_queue_wr_en", "wr_chl_queue_rd_en", "wr_chl_queue_full", "wr_chl_queue_empty", "wr_chl_queue_rd_tsf_size", "wr_data_chl_prepared_data_wr_hs", "wr_data_chl_prepared_data_rd_hs", "wr_data_chl_prepared_data_cnt", "wr_data_chl_prepared_data_vld", "wr_chl_prepared_data_bp_pre", "wr_chl_ob_wr_hs", "wr_chl_ob_rd_hs", "wr_chl_ob_sel", "wr_chl_ob_vld", "wr_chl_ob_bp_pre", "u_wr_chl_queue"),
    "WR_Memory_AG": ("wr_data_chl_req_valid", "wr_data_chl_req_ready", "mse2mem_request_valid", "mem2mse_request_ready", "transaction_addr_valid", "transfer_final_size", "cur_transaction_size_left", "mem_ag_ob_vld", "mem_ag_ob_sel"),
    "FIFO": ("fifo_counter",),
}


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def compile_case(iverilog: Path, root: Path, name: str, source: str) -> dict[str, Any]:
    source_path = root / f"{name}.sv"
    output_path = root / f"{name}.out"
    source_path.write_text(source, encoding="utf-8", newline="\n")
    result = subprocess.run([str(iverilog), "-g2012", "-s", "mse4_focus_top", "-o", str(output_path), str(source_path)], text=True, capture_output=True, encoding="utf-8", errors="replace", check=False)
    return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def prefix() -> str:
    return r'''
`timescale 1ns/1ps
module fifo_stub; logic [2:0] fifo_counter; endmodule
module wr_memory_ag_stub;
  logic wr_data_chl_req_valid, wr_data_chl_req_ready;
  logic [1:0] mse2mem_request_valid, mem2mse_request_ready, mem_ag_ob_vld;
  logic transaction_addr_valid, mem_ag_ob_sel;
  logic [4:0] transfer_final_size; logic [8:0] cur_transaction_size_left;
endmodule
module wr_data_channel_stub;
  logic wr_chl_queue_wr_en, wr_chl_queue_rd_en, wr_chl_queue_full, wr_chl_queue_empty;
  logic [4:0] wr_chl_queue_rd_tsf_size;
  logic wr_data_chl_prepared_data_wr_hs, wr_data_chl_prepared_data_rd_hs;
  logic [6:0] wr_data_chl_prepared_data_cnt;
  logic wr_data_chl_prepared_data_vld, wr_chl_prepared_data_bp_pre, wr_chl_ob_sel;
  logic [1:0] wr_chl_ob_wr_hs, wr_chl_ob_rd_hs, wr_chl_ob_vld, wr_chl_ob_bp_pre;
  fifo_stub u_wr_chl_queue();
endmodule
module rd_buffer_ag_stub; logic buf_ag_last_req_flag, wr_data_chl_ready; endmodule
module memory_wr_stream_engine_stub;
  wr_memory_ag_stub u_WR_Memory_AG();
  wr_data_channel_stub u_WR_Data_Channel();
  rd_buffer_ag_stub u_RD_Buffer_AG();
endmodule
module wr_mse_stub; memory_wr_stream_engine_stub u_Memory_WR_Stream_Engine(); endmodule
module stream_engine_stub;
  generate for (genvar i=0;i<5;i++) begin : MSE_INST wr_mse_stub WR_MSE(); end endgenerate
endmodule
module lsu_stub; stream_engine_stub u_Stream_Engine(); endmodule
module slice_stub; lsu_stub u_LSU(); endmodule
module slice_wrapper_stub; slice_stub u_Slice(); endmodule
module group_stub;
  generate for (genvar s=0;s<1;s++) begin : slice_group_gen slice_wrapper_stub u_slice_wrapper(); end endgenerate
endmodule
module ndp_stub;
  logic clk_db, rst_n_db;
  generate for (genvar g=0;g<1;g++) begin : slice_with_datahub_mc_group_gen group_stub u_slice_with_datahub_mc_group(); end endgenerate
endmodule
module mse4_focus_top;
  ndp_stub u_NDP_Top_new();
  bit return_obs_enabled, return_obs_active;
  integer return_obs_fd;
'''


def semantic_closure(source: str) -> dict[str, Any]:
    checks = {
        "declaration": source.count("longint unsigned return_obs_md_desc_hs;") == 1,
        "initialization": source.count("return_obs_md_desc_hs = 0;") >= 2,
        "qualified_update": source.count("if (md_desc_hs) return_obs_md_desc_hs++;") == 1,
        "consumer_use": source.count("return_obs_md_desc_hs,") >= 1,
        "state_not_progress": "FIFO occupancy and combinational ready/valid levels are corroborating state only" in source,
    }
    return {"valid": all(checks.values()), "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--iverilog", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    project = args.project_root.resolve()
    errors: list[str] = []
    with zipfile.ZipFile(args.zip.resolve()) as archive:
        if archive.testzip() is not None:
            errors.append("ZIP CRC failed")
        observer = archive.read(f"{INSTALL_NAME}/tb_probe/native_return_observer.svh").decode("utf-8")
    if observer.count(MARKER) != 1:
        errors.append("v30 marker count differs")
        block = ""
    else:
        block = observer[observer.index(MARKER):]
    active: dict[str, Any] = {}
    for module, relative in ACTIVE_FILES.items():
        path = project / relative
        text = path.read_text(encoding="utf-8")
        checks = {leaf: leaf in text for leaf in LEAVES[module]}
        active[module] = {"path": relative, "bytes": path.stat().st_size, "sha256": digest(path.read_bytes()), "leaf_checks": checks}
        if not all(checks.values()):
            errors.append(f"{module} active leaf closure failed")
    focused = prefix() + block + "\nendmodule\n"
    positive_closure = semantic_closure(focused)
    with tempfile.TemporaryDirectory(prefix="v30-mse4-scope-") as temp:
        root = Path(temp)
        positive = compile_case(args.iverilog.resolve(), root, "positive", focused)
        typo = compile_case(args.iverilog.resolve(), root, "negative_typo_leaf", focused.replace(".wr_chl_queue_rd_en", ".wr_chl_queue_rd_ex", 1))
        deleted = compile_case(args.iverilog.resolve(), root, "negative_deleted_declaration", focused.replace("logic wr_chl_queue_wr_en, wr_chl_queue_rd_en, wr_chl_queue_full, wr_chl_queue_empty;", "logic wr_chl_queue_wr_en, wr_chl_queue_full, wr_chl_queue_empty;", 1))
        missing_task = compile_case(args.iverilog.resolve(), root, "negative_missing_task_end", focused.replace("    endtask", "    end", 1))
        update_mutant_source = focused.replace("if (md_desc_hs) return_obs_md_desc_hs++;", "", 1)
        update_mutant = compile_case(args.iverilog.resolve(), root, "negative_deleted_qualified_update", update_mutant_source)
        update_mutant_closure = semantic_closure(update_mutant_source)
    if positive["exit_code"] != 0:
        errors.append("focused positive compile failed")
    if not positive_closure["valid"]:
        errors.append("positive semantic closure failed")
    if any(case["exit_code"] == 0 for case in (typo, deleted, missing_task)):
        errors.append("one or more syntax/scope negatives did not fail")
    if update_mutant_closure["valid"]:
        errors.append("deleted qualified update did not fail semantic closure")
    frontend = subprocess.run([str(args.iverilog.resolve()), "-V"], text=True, capture_output=True, encoding="utf-8", errors="replace", check=False)
    report = {
        "schema": "node0004-v30-mse4-descriptor-observer-scope-v1",
        "valid": not errors,
        "errors": errors,
        "package_local_gate": {"applicable": True, "rule_id": "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001", "observer_sha256": digest(observer.encode())},
        "active_local_rtl": active,
        "frontend": {"path": str(args.iverilog.resolve()), "version_exit": frontend.returncode, "version_stdout": frontend.stdout, "version_stderr": frontend.stderr},
        "positive": positive,
        "positive_semantic_closure": positive_closure,
        "negative_typo_leaf": typo,
        "negative_deleted_declaration": deleted,
        "negative_missing_task_end": missing_task,
        "negative_deleted_qualified_update": update_mutant,
        "negative_deleted_qualified_update_semantic_closure": update_mutant_closure,
        "all_negative_controls_fail_closed": all(case["exit_code"] != 0 for case in (typo, deleted, missing_task)) and not update_mutant_closure["valid"],
        "claim_boundary": "focused package-local v30 observer syntax/scope and direct active-leaf existence; not full-design VCS elaboration or server RTL identity",
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
