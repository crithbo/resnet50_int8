from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


INSTALL_NAME = "r5_n4_hw_v27_dwrite_path_diag"
MARKER = "    // v27: narrow MSE4 Buffer5-read/tag -> last-index0 -> slice-finish path."
ACTIVE_FILES = {
    "RD_Buffer_AG": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_WR_Stream_Engine/RD_Buffer_AG.sv"
    ),
    "WR_Data_Channel": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_WR_Stream_Engine/WR_Data_Channel.sv"
    ),
}
LEAVES = {
    "RD_Buffer_AG": (
        "buf_ag_ob_wr_en",
        "buf_ag_ob_full",
        "mse2buf_rreq_valid",
        "buf2mse_rreq_ready",
        "mse2buf_last",
        "mse2buf_last_index",
        "buf_ag_idx_last_bit",
        "buf_ag_idx_last_index",
        "buf_ag_ob_cnt",
        "buf_ag_ob_empty",
        "wr_data_chl_ready",
    ),
    "WR_Data_Channel": (
        "wr_data_chl_prepared_data_wr_hs",
        "wr_chl_ob_wr_hs",
        "mse2mem_wdata_valid",
        "mem2mse_wdata_ready",
        "wr_data_chl_last_flag",
        "wr_data_chl_last_bitmap_reg",
        "wr_data_chl_last_bitmap_rptr",
        "wr_data_chl_prepared_data_cnt",
        "wr_data_chl_ob_last_data_flag",
        "slice_cmpt_finish",
    ),
}


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def compile_case(
    iverilog: Path, root: Path, name: str, source: str
) -> dict[str, Any]:
    source_path = root / f"{name}.sv"
    output_path = root / f"{name}.out"
    source_path.write_text(source, encoding="utf-8", newline="\n")
    result = subprocess.run(
        [
            str(iverilog),
            "-g2012",
            "-s",
            "dwrite_focus_top",
            "-o",
            str(output_path),
            str(source_path),
        ],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def prefix() -> str:
    return r"""
`timescale 1ns/1ps
module rd_buffer_stub;
  logic buf_ag_ob_wr_en, buf_ag_ob_full, buf2mse_rreq_ready;
  logic [15:0] mse2buf_rreq_valid;
  logic mse2buf_last, buf_ag_idx_last_bit, buf_ag_ob_empty;
  logic [3:0] mse2buf_last_index, buf_ag_idx_last_index;
  logic [1:0] buf_ag_ob_cnt;
  logic wr_data_chl_ready;
endmodule
module wr_data_stub;
  logic wr_data_chl_prepared_data_wr_hs, wr_data_chl_last_flag;
  logic [1:0] wr_chl_ob_wr_hs, mse2mem_wdata_valid;
  logic [1:0] mem2mse_wdata_ready, wr_data_chl_ob_last_data_flag;
  logic [31:0] wr_data_chl_last_bitmap_reg;
  logic [4:0] wr_data_chl_last_bitmap_rptr;
  logic [5:0] wr_data_chl_prepared_data_cnt;
  logic slice_cmpt_finish;
endmodule
module memory_wr_stub;
  rd_buffer_stub u_RD_Buffer_AG();
  wr_data_stub u_WR_Data_Channel();
endmodule
module stream_stub;
  generate
    for (genvar m = 0; m < 5; m++) begin : MSE_INST
      if (m == 4) begin : WR_MSE
        memory_wr_stub u_Memory_WR_Stream_Engine();
      end else begin : WR_MSE
        memory_wr_stub u_Memory_WR_Stream_Engine();
      end
    end
  endgenerate
endmodule
module lsu_stub;
  stream_stub u_Stream_Engine();
endmodule
module slice_stub;
  lsu_stub u_LSU();
endmodule
module wrapper_stub;
  slice_stub u_Slice();
endmodule
module group_stub;
  generate
    for (genvar s = 0; s < 1; s++) begin : slice_group_gen
      wrapper_stub u_slice_wrapper();
    end
  endgenerate
endmodule
module ndp_stub;
  logic clk_db, rst_n_db;
  generate
    for (genvar g = 0; g < 1; g++) begin : slice_with_datahub_mc_group_gen
      group_stub u_slice_with_datahub_mc_group();
    end
  endgenerate
endmodule
module dwrite_focus_top;
  ndp_stub u_NDP_Top_new();
  bit return_obs_enabled;
  bit return_obs_active;
  integer return_obs_fd;
"""


def main() -> int:
    global INSTALL_NAME
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--iverilog", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--install-name", default=INSTALL_NAME)
    args = parser.parse_args()
    INSTALL_NAME = args.install_name
    project = args.project_root.resolve()
    zip_path = args.zip.resolve()
    errors: list[str] = []
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            errors.append("ZIP CRC failed")
        member = f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
        observer = archive.read(member).decode("utf-8")
    if observer.count(MARKER) != 1:
        errors.append("v27 marker count differs")
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
            "sha256": sha256(path.read_bytes()),
            "leaf_checks": checks,
        }
        if not all(checks.values()):
            errors.append(f"{module} active leaf closure failed")
    focused = prefix() + block + "\nendmodule\n"
    with tempfile.TemporaryDirectory(prefix="v27-dwrite-scope-") as temp:
        root = Path(temp)
        positive = compile_case(args.iverilog.resolve(), root, "positive", focused)
        typo = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_typo_leaf",
            focused.replace(".buf_ag_ob_full", ".buf_ag_ob_fulx", 1),
        )
        deleted = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_deleted_declaration",
            focused.replace(
                "logic buf_ag_ob_wr_en, buf_ag_ob_full, buf2mse_rreq_ready;",
                "logic buf_ag_ob_wr_en, buf2mse_rreq_ready;",
                1,
            ),
        )
        missing_task = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_missing_task_end",
            focused.replace("    endtask", "    end", 1),
        )
    if positive["exit_code"] != 0:
        errors.append("focused positive compile failed")
    if any(case["exit_code"] == 0 for case in (typo, deleted, missing_task)):
        errors.append("one or more focused negative controls did not fail")
    report = {
        "schema": "node0004-v27-dwrite-observer-scope-v1",
        "valid": not errors,
        "errors": errors,
        "zip": {
            "path": str(zip_path),
            "sha256": sha256(zip_path.read_bytes()),
        },
        "observer_sha256": sha256(observer.encode()),
        "active_rtl": active,
        "focused_compatible_frontend": {
            "tool": str(args.iverilog.resolve()),
            "positive": positive,
            "negative_typo_leaf": typo,
            "negative_deleted_declaration": deleted,
            "negative_missing_task_end": missing_task,
        },
        "all_negative_controls_fail_closed": all(
            case["exit_code"] != 0 for case in (typo, deleted, missing_task)
        ),
        "scope": (
            "only v27-added D-write path observer HDL and its directly "
            "referenced active RTL leaves"
        ),
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
