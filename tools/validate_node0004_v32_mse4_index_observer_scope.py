from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


INSTALL_NAME = "r5_n4_hw_v32_mse4_index_diag"
MARKER = "    // v32: qualified MSE4 memory-index matching/queue -> WR_Memory_AG pipeline."
ACTIVE_FILES = {
    "Memory_AG_Idx_Queue": "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_AG_Idx_Queue.sv",
    "WR_Memory_AG": "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Memory_AG.sv",
    "WR_Data_Channel": "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv",
    "FIFO": "NDP_copy01/rtl/utils/FIFO/FIFO.sv",
}
LEAVES = {
    "Memory_AG_Idx_Queue": (
        "mse_mem_queue_bp_pre",
        "mem_idx_valid_same_gotten_masked",
        "mem_idx_valid_bit_unmasked",
        "mem_idx_same_bit_unmasked",
        "mem_idx_gotten_bit",
        "mem_idx_valid_bit_masked",
        "mem_all_idx_matched",
        "mem_ag_idx_queue_wr_en",
        "mem_ag_idx_queue_rd_en",
        "mem_ag_idx_queue_full",
        "mem_ag_idx_queue_empty",
        "mse_mem_ag_tag_valid",
        "u_mem_ag_idx_queue",
    ),
    "WR_Memory_AG": (
        "mem_ag_idx_valid_bit",
        "mem_ag_idx_last_bit",
        "mem_ag_idx_last_index",
        "mse_mem_ag_bp_pre",
        "transaction_addr_bias_bp_pre",
        "transaction_addr_bias_valid",
        "transaction_addr_bp_pre",
        "transaction_addr_valid",
        "transaction_finish",
        "cur_transaction_size_left",
        "wr_data_chl_req_valid",
        "wr_data_chl_req_ready",
    ),
    "WR_Data_Channel": (
        "wr_data_chl_prepared_data_wr_hs",
        "wr_data_chl_prepared_data_cnt",
        "wr_data_chl_prepared_data_vld",
        "wr_chl_prepared_data_bp_pre",
    ),
    "FIFO": ("fifo_counter",),
}
COUNTERS = (
    "accept0",
    "accept1",
    "accept2",
    "match",
    "push",
    "pop",
    "bias_capture",
    "transaction_capture",
    "transaction_finish",
    "descriptor",
    "prepared",
)


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def compile_case(iverilog: Path, root: Path, name: str, source: str) -> dict[str, Any]:
    source_path = root / f"{name}.sv"
    output_path = root / f"{name}.out"
    source_path.write_text(source, encoding="utf-8", newline="\n")
    command = [str(iverilog), "-g2012", "-s", "mse4_index_focus_top", "-o", str(output_path), str(source_path)]
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {"command": command, "cwd": str(root), "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def prefix() -> str:
    return r'''
`timescale 1ns/1ps
module fifo_stub; logic [3:0] fifo_counter; endmodule
module memory_idx_queue_stub;
  logic [2:0] mse_mem_queue_bp_pre, mem_idx_valid_same_gotten_masked;
  logic [2:0] mem_idx_valid_bit_unmasked, mem_idx_same_bit_unmasked;
  logic [2:0] mem_idx_gotten_bit, mem_idx_valid_bit_masked;
  logic mem_all_idx_matched, mem_ag_idx_queue_wr_en, mem_ag_idx_queue_rd_en;
  logic mem_ag_idx_queue_full, mem_ag_idx_queue_empty, mse_mem_ag_tag_valid;
  fifo_stub u_mem_ag_idx_queue();
endmodule
module wr_memory_ag_stub;
  logic mem_ag_idx_valid_bit, mem_ag_idx_last_bit, mse_mem_ag_bp_pre;
  logic [2:0] mem_ag_idx_last_index;
  logic transaction_addr_bias_bp_pre, transaction_addr_bias_valid;
  logic transaction_addr_bp_pre, transaction_addr_valid, transaction_finish;
  logic [8:0] cur_transaction_size_left;
  logic wr_data_chl_req_valid, wr_data_chl_req_ready;
endmodule
module wr_data_channel_stub;
  logic wr_data_chl_prepared_data_wr_hs;
  logic [6:0] wr_data_chl_prepared_data_cnt;
  logic wr_data_chl_prepared_data_vld, wr_chl_prepared_data_bp_pre;
endmodule
module memory_wr_stream_engine_stub;
  memory_idx_queue_stub u_Memory_AG_Idx_Queue();
  wr_memory_ag_stub u_WR_Memory_AG();
  wr_data_channel_stub u_WR_Data_Channel();
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
module mse4_index_focus_top;
  ndp_stub u_NDP_Top_new();
  bit return_obs_enabled, return_obs_active;
  integer return_obs_fd;
'''


def semantic_closure(source: str) -> dict[str, Any]:
    per_counter: dict[str, dict[str, bool]] = {}
    for name in COUNTERS:
        identifier = f"return_obs_mi_{name}"
        update = (
            f"if (mi_{name}) {identifier}++;"
            if name not in ("transaction_capture", "transaction_finish")
            else f"if (mi_{name}) {identifier}++;"
        )
        per_counter[name] = {
            "declared_once": source.count(f"longint unsigned {identifier};") == 1,
            "initialized": source.count(f"{identifier} = 0;") >= 2,
            "qualified_update_once": source.count(update) == 1,
            "consumer_use": source.count(identifier) >= 5,
        }
    checks = {
        "all_counter_roles_closed": all(all(row.values()) for row in per_counter.values()),
        "edge_record_present": source.count("MSE4_INDEX_EDGE_V1") == 1,
        "boundary_record_present": source.count("MSE4_INDEX_BOUNDARY_V1") == 1,
        "state_not_progress": "Valid/ready/full levels are state only; progress counters require a qualified edge." in source,
    }
    return {"valid": all(checks.values()), "checks": checks, "per_counter": per_counter}


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
        observer_payload = archive.read(f"{INSTALL_NAME}/tb_probe/native_return_observer.svh")
    observer = observer_payload.decode("utf-8")
    if observer.count(MARKER) != 1:
        errors.append("v32 marker count differs")
        block = ""
    else:
        block = observer[observer.index(MARKER) :]
    active: dict[str, Any] = {}
    for module, relative in ACTIVE_FILES.items():
        path = project / relative
        text = path.read_text(encoding="utf-8")
        checks = {leaf: leaf in text for leaf in LEAVES[module]}
        active[module] = {
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": digest(path.read_bytes()),
            "leaf_checks": checks,
        }
        if not all(checks.values()):
            errors.append(f"{module} active leaf closure failed")
    focused = prefix() + block + "\nendmodule\n"
    focused_sha = digest(focused.encode())
    positive_closure = semantic_closure(focused)
    with tempfile.TemporaryDirectory(prefix="v32-mse4-index-scope-") as temp:
        root = Path(temp)
        positive = compile_case(args.iverilog.resolve(), root, "positive", focused)
        typo = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_typo_consumer",
            focused.replace(".mem_ag_idx_queue_wr_en", ".mem_ag_idx_queue_wr_ex", 1),
        )
        deleted = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_deleted_declaration",
            focused.replace("longint unsigned return_obs_mi_match;\n", "", 1),
        )
        syntax = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_missing_task_end",
            focused.replace("    endtask", "    end", 1),
        )
        update_mutant_source = focused.replace("if (mi_match) return_obs_mi_match++;", "", 1)
        update_mutant = compile_case(args.iverilog.resolve(), root, "negative_deleted_qualified_update", update_mutant_source)
        update_mutant_closure = semantic_closure(update_mutant_source)
    if positive["exit_code"] != 0:
        errors.append("focused positive compile failed")
    if not positive_closure["valid"]:
        errors.append("positive semantic closure failed")
    if any(case["exit_code"] == 0 for case in (typo, deleted, syntax)):
        errors.append("one or more syntax/scope negatives did not fail")
    if update_mutant_closure["valid"]:
        errors.append("deleted qualified update did not fail semantic closure")
    frontend = subprocess.run(
        [str(args.iverilog.resolve()), "-V"],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    report = {
        "schema": "node0004-v32-mse4-index-observer-scope-v1",
        "valid": not errors,
        "errors": errors,
        "package_local_hdl_gate": {
            "applicable": True,
            "rule_id": "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
            "exact_members": [
                {
                    "path": f"{INSTALL_NAME}/tb_probe/native_return_observer.svh",
                    "bytes": len(observer_payload),
                    "sha256": digest(observer_payload),
                    "role": "package-local read-only observer",
                }
            ],
            "include_or_concatenation_order_sha256": digest(
                b"+define+NATIVE_RETURN_OBSERVER_ENABLE\n+incdir+<package>/tb_probe\nnative_return_observer.svh\n"
            ),
            "focused_harness_sha256": focused_sha,
            "specializations": [],
            "closure": {
                "scope": "v32 changed MSE4 memory-index counters and required boundary records",
                "declared": len(COUNTERS),
                "used": len(COUNTERS),
                "unresolved": 0 if positive_closure["valid"] else 1,
                "ownerless_state": 0 if positive_closure["valid"] else 1,
            },
            "negative_controls": {
                "delete_declaration_fail_closed": deleted["exit_code"] != 0,
                "misspell_consumer_use_fail_closed": typo["exit_code"] != 0,
                "delete_reset_or_update_fail_closed": not update_mutant_closure["valid"],
            },
            "claim_boundary": "focused exact v32 package-local added observer syntax/scope/state ownership and direct active-leaf existence; not full-design VCS elaboration or server RTL identity",
            "pass": not errors,
        },
        "active_local_rtl": active,
        "frontend": {
            "path": str(args.iverilog.resolve()),
            "version_exit": frontend.returncode,
            "version_stdout": frontend.stdout,
            "version_stderr": frontend.stderr,
        },
        "positive": positive,
        "positive_semantic_closure": positive_closure,
        "negative_typo_consumer": typo,
        "negative_deleted_declaration": deleted,
        "negative_missing_task_end": syntax,
        "negative_deleted_qualified_update": update_mutant,
        "negative_deleted_qualified_update_semantic_closure": update_mutant_closure,
        "all_negative_controls_fail_closed": all(case["exit_code"] != 0 for case in (typo, deleted, syntax))
        and not update_mutant_closure["valid"],
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
