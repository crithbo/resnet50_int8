from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


INSTALL_NAME = "r5_n4_hw_v35_rowlc4_bufag_diag"
MARKER = "    // v35: information-gain boundary for LC18 fanout bit10 through"
COUNTERS = (
    "row_capture",
    "row_complete",
    "row_out",
    "col_capture",
    "col_complete",
    "col_out",
    "buf_row_accept",
    "buf_col_accept",
    "buf_match",
    "buf_push",
    "buf_pop",
    "rd_write",
    "rd_read",
)
ACTIVE_FILES = (
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_ROW_LC/IGA_ROW_LC.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_ROW_LC/IGA_ROW_LC_Inbuffer.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_ROW_LC/IGA_ROW_LC_Counter.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_COL_LC/IGA_COL_LC.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_COL_LC/IGA_COL_LC_Inbuffer.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_COL_LC/IGA_COL_LC_Counter.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv",
)


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def compile_case(
    iverilog: Path, root: Path, name: str, source: str
) -> dict[str, Any]:
    source_path = root / f"{name}.sv"
    output_path = root / f"{name}.out"
    source_path.write_text(source, encoding="utf-8", newline="\n")
    command = [
        str(iverilog),
        "-g2012",
        "-s",
        "rowlc4_bufag_focus_top",
        "-o",
        str(output_path),
        str(source_path),
    ]
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "command": command,
        "cwd": str(root),
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def prefix() -> str:
    return r'''
`timescale 1ns/1ps
module lc_counter_stub;
  logic iga_row_lc_cnt_outport_valid_bit, iga_col_lc_cnt_outport_valid_bit;
  logic [3:0] iga_row_lc_outbuf_count, iga_col_lc_outbuf_count;
  logic iga_row_lc_outbuf_full, iga_row_lc_outbuf_empty;
  logic iga_col_lc_outbuf_full, iga_col_lc_outbuf_empty;
endmodule
module lc_inbuffer_stub;
  logic iga_row_lc_inport_valid_bit_masked;
  logic iga_col_lc_inport_valid_bit_masked;
endmodule
module row_stub;
  logic iga_row_lc_inbuffer_bp_pre, iga_row_lc_inbuffer_valid_bit;
  logic iga_row_lc_cnt_bp_pre, iga_row_lc_cnt_bp_post;
  logic [31:0] iga_row_lc_inport_tag, iga_row_lc_outport;
  logic [7:0] iga_row_lc_inport_bp_pre, iga_row_lc_outport_bp_post;
  lc_inbuffer_stub u_IGA_ROW_LC_Inbuffer();
  lc_counter_stub u_IGA_ROW_LC_Counter();
endmodule
module col_stub;
  logic iga_col_lc_inbuffer_bp_pre, iga_col_lc_inbuffer_valid_bit;
  logic iga_col_lc_cnt_bp_pre, iga_col_lc_cnt_bp_post;
  logic [31:0] iga_col_lc_inport_tag, iga_col_lc_outport;
  logic [7:0] iga_col_lc_inport_bp_pre, iga_col_lc_outport_bp_post;
  lc_inbuffer_stub u_IGA_COL_LC_Inbuffer();
  lc_counter_stub u_IGA_COL_LC_Counter();
endmodule
module iga_stub;
  generate
    for (genvar i=0;i<8;i++) begin : IGA_ROW_LC
      row_stub u_IGA_ROW_LC();
    end
    for (genvar j=0;j<8;j++) begin : IGA_COL_LC
      col_stub u_IGA_COL_LC();
    end
  endgenerate
endmodule
module buffer_ag_stub;
  logic [2:0] mse_buf_queue_bp_pre, buf_idx_valid_bit_masked;
  logic [2:0] buf_idx_valid_bit_unmasked, buf_idx_same_bit_unmasked;
  logic [2:0] buf_idx_gotten_bit;
  logic buf_all_idx_matched, buf_ag_idx_queue_wr_en;
  logic buf_ag_idx_queue_rd_en, buf_ag_idx_queue_full, buf_ag_idx_queue_empty;
endmodule
module rd_ag_stub;
  logic buf_ag_ob_wr_en, buf_ag_ob_rd_en, buf_ag_ob_full, buf_ag_ob_empty;
  logic [3:0] buf_ag_ob_cnt;
  logic wr_data_chl_ready;
endmodule
module wr_data_stub;
  logic [5:0] wr_data_chl_prepared_data_cnt;
  logic wr_data_chl_prepared_data_vld, wr_chl_prepared_data_bp_pre;
endmodule
module memory_wr_stream_engine_stub;
  buffer_ag_stub u_Buffer_AG_Idx_Queue();
  rd_ag_stub u_RD_Buffer_AG();
  wr_data_stub u_WR_Data_Channel();
endmodule
module wr_mse_stub;
  memory_wr_stream_engine_stub u_Memory_WR_Stream_Engine();
endmodule
module stream_engine_stub;
  generate
    for (genvar i=0;i<5;i++) begin : MSE_INST
      wr_mse_stub WR_MSE();
    end
  endgenerate
endmodule
module lsu_stub; stream_engine_stub u_Stream_Engine(); endmodule
module slice_stub;
  iga_stub u_Index_Generation_Array();
  lsu_stub u_LSU();
endmodule
module slice_wrapper_stub; slice_stub u_Slice(); endmodule
module group_stub;
  generate
    for (genvar s=0;s<1;s++) begin : slice_group_gen
      slice_wrapper_stub u_slice_wrapper();
    end
  endgenerate
endmodule
module ndp_stub;
  logic clk_db, rst_n_db;
  generate
    for (genvar g=0;g<1;g++) begin : slice_with_datahub_mc_group_gen
      group_stub u_slice_with_datahub_mc_group();
    end
  endgenerate
endmodule
module rowlc4_bufag_focus_top;
  ndp_stub u_NDP_Top_new();
  bit return_obs_enabled, return_obs_active;
  integer return_obs_fd;
'''


def semantic_closure(source: str, full_observer: str) -> dict[str, Any]:
    per_counter: dict[str, dict[str, bool]] = {}
    for name in COUNTERS:
        identifier = f"return_obs_rb_{name}"
        local = f"rb_{name}"
        per_counter[name] = {
            "declared_once": source.count(
                f"longint unsigned {identifier};"
            )
            == 1,
            "initialized": source.count(f"{identifier} = 0;") >= 2,
            "qualified_update_once": source.count(
                f"if ({local}) {identifier}++;"
            )
            == 1,
            "consumer_use": source.count(identifier) >= 5,
        }
    checks = {
        "all_counter_roles_closed": all(
            all(row.values()) for row in per_counter.values()
        ),
        "edge_record_present": source.count("ROWLC4_BUFAG_EDGE_V1") == 1,
        "boundary_record_present": (
            source.count("ROWLC4_BUFAG_BOUNDARY_V1") == 1
        ),
        "decision_hook_exact": full_observer.count(
            "return_obs_write_rowlc4_bufag_state(event_name);"
        )
        == 1,
        "physical_mapping_exact": all(
            token in source
            for token in (
                ".IGA_ROW_LC[4].u_IGA_ROW_LC",
                ".IGA_COL_LC[4].u_IGA_COL_LC",
                ".MSE_INST[4].WR_MSE",
                ".u_Buffer_AG_Idx_Queue",
                ".u_RD_Buffer_AG",
                ".u_WR_Data_Channel",
            )
        ),
        "level_not_qualified_progress": (
            "if (rb_buf_match) return_obs_rb_buf_match++;" in source
            and "bufq_full" in source
            and "prepared_count" in source
        ),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "per_counter": per_counter,
    }


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
        payload = archive.read(
            f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
        )
    observer = payload.decode("utf-8")
    if observer.count(MARKER) != 1:
        errors.append("v35 marker count differs")
        block = ""
    else:
        block = observer[observer.index(MARKER) :]

    active: list[dict[str, Any]] = []
    for relative in ACTIVE_FILES:
        path = project / relative
        if not path.is_file():
            errors.append(f"missing active RTL leaf: {relative}")
            continue
        active.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": digest(path.read_bytes()),
            }
        )

    focused = prefix() + block + "\nendmodule\n"
    closure = semantic_closure(focused, observer)
    with tempfile.TemporaryDirectory(prefix="v35-rowlc4-bufag-scope-") as temp:
        root = Path(temp)
        positive = compile_case(args.iverilog.resolve(), root, "positive", focused)
        typo = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_typo_consumer",
            focused.replace(".IGA_ROW_LC[4]", ".IGA_ROW_LX[4]", 1),
        )
        deleted = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_deleted_declaration",
            focused.replace(
                "longint unsigned return_obs_rb_row_capture;\n", "", 1
            ),
        )
        syntax = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_missing_task_end",
            focused.replace("    endtask", "    end", 1),
        )
        update_source = focused.replace(
            "if (rb_buf_push) return_obs_rb_buf_push++;", "", 1
        )
        update_case = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_deleted_qualified_update",
            update_source,
        )
        update_closure = semantic_closure(update_source, observer)

    if positive["exit_code"] != 0:
        errors.append("focused positive compile failed")
    if not closure["valid"]:
        errors.append("positive semantic closure failed")
    if any(case["exit_code"] == 0 for case in (typo, deleted, syntax)):
        errors.append("syntax/scope negative did not fail closed")
    if update_closure["valid"]:
        errors.append("deleted qualified update did not fail semantic closure")
    report = {
        "schema": "node0004-v35-rowlc4-bufag-observer-scope-v1",
        "valid": not errors,
        "errors": errors,
        "package_local_hdl_gate": {
            "applicable": True,
            "exact_member": {
                "path": f"{INSTALL_NAME}/tb_probe/native_return_observer.svh",
                "bytes": len(payload),
                "sha256": digest(payload),
            },
            "focused_harness_sha256": digest(focused.encode()),
            "claim_boundary": (
                "v35-added ROW_LC4/COL_LC4/Buffer_AG/RD_Buffer_AG observer "
                "syntax, hierarchy scope, counter ownership and direct active "
                "leaf identity; not full-design VCS elaboration"
            ),
            "pass": not errors,
        },
        "active_local_rtl": active,
        "positive": positive,
        "positive_semantic_closure": closure,
        "negative_typo_consumer": typo,
        "negative_deleted_declaration": deleted,
        "negative_missing_task_end": syntax,
        "negative_deleted_qualified_update": update_case,
        "negative_deleted_qualified_update_semantic_closure": update_closure,
        "all_negative_controls_fail_closed": (
            all(case["exit_code"] != 0 for case in (typo, deleted, syntax))
            and not update_closure["valid"]
        ),
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
