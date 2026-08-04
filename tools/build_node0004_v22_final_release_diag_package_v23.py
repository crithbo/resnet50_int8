from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v7_four_way_binding_package_v8 as base  # noqa: E402


SOURCE_NAME = "r5_n4_hw_v22_featurebind"
INSTALL_NAME = "r5_n4_hw_v23_final_release_diag"
SOURCE_ZIP_SHA256 = (
    "caf96850ceb5dcf66233dd736757bb2e0b3fbb3b63b066dc9c0194022f1ac68b"
)
SERVER_RULE_SHA256 = (
    "7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141"
)
INDEX_SHA256 = (
    "f768a870d19699c87b66b735a759d3212db6ad51aace30e3a6305b2521a708c8"
)
PLAN_MUTABLE_SHA256 = (
    "2000e85af23d0fe2a3f2c8e4f6eed2920182e1115f37ac9a62a26974131b3ee3"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{SOURCE_NAME}.zip"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
FEATURE = "RETURN_OBS_FINAL_RELEASE"
FEATURE_LIMIT = 256


class BuildError(RuntimeError):
    pass


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise BuildError(
            f"patch anchor count differs for {path.name}: {text.count(old)}"
        )
    path.write_text(
        text.replace(old, new, 1),
        encoding="utf-8",
        newline="\n",
    )


def safe_extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise BuildError("v22 source ZIP SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v22 source ZIP CRC failed")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or not pure.parts
                or info.filename in seen
            ):
                raise BuildError(f"unsafe v22 member: {info.filename}")
            seen.add(info.filename)
            roots.add(pure.parts[0])
        if roots != {SOURCE_NAME}:
            raise BuildError(f"v22 root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE_NAME


def replace_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".bin":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_NAME in text:
            path.write_text(
                text.replace(SOURCE_NAME, INSTALL_NAME),
                encoding="utf-8",
                newline="\n",
            )


FINAL_RELEASE_OBSERVER = r"""

    // v23: corrected-successor discriminator.  ALU writes replace existing
    // live slots and therefore are deliberately not occupancy increments.
    // Qualified handshakes and state-change edges are the only monotonic
    // evidence below; count/empty are snapshots only.
    bit return_obs_fr_enabled;
    integer return_obs_fr_limit;
    integer return_obs_fr_plusarg_status;
    integer return_obs_fr_edge_records;

    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_fr_input_last_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`PORT_LAST_INDEX-1:0] return_obs_fr_input_last_index_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_fr_input_last_matched_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_fr_input_last_out_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_fr_alu_last_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_fr_alu_last_matched_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_fr_alu_write_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_OB_GROUP_SIZE-1:0] return_obs_fr_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0][3:0]
          return_obs_fr_select_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_OB_PTR_WIDTH-1:0] return_obs_fr_initial_ptr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_OB_PTR_WIDTH-1:0] return_obs_fr_ob2alu_ptr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_OB_PTR_WIDTH-1:0] return_obs_fr_alu2ob_ptr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_OB_PTR_WIDTH-1:0] return_obs_fr_output_ptr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [2*(`SA_PE_OB_PTR_WIDTH+1)-1:0] return_obs_fr_count_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0][1:0]
          return_obs_fr_empty_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_fr_pe_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_fr_pe_accept_mon;

    generate
        for (genvar return_obs_fr_group = 0;
             return_obs_fr_group < `SLICE_GROUP_SIZE;
             return_obs_fr_group++) begin : RETURN_OBS_FR_GROUP_GEN
            for (genvar return_obs_fr_slice = 0;
                 return_obs_fr_slice < `SLICE_GROUP_NUM;
                 return_obs_fr_slice++) begin : RETURN_OBS_FR_SLICE_GEN
                for (genvar return_obs_fr_row = 0;
                     return_obs_fr_row < `SA_ROW_PE_NUM;
                     return_obs_fr_row++) begin : RETURN_OBS_FR_ROW_GEN
                    for (genvar return_obs_fr_col = 0;
                         return_obs_fr_col < `SA_COL_PE_NUM;
                         return_obs_fr_col++) begin : RETURN_OBS_FR_COL_GEN
                        assign return_obs_fr_input_last_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Control_Block
                                .sa_pe_buffer_port_last_bit;
                        assign return_obs_fr_input_last_index_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Control_Block
                                .sa_pe_buffer_port_last_index;
                        assign return_obs_fr_input_last_matched_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.sa_pe_inport_last_matched;
                        assign return_obs_fr_input_last_out_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.sa_pe_inport_last_out;
                        assign return_obs_fr_alu_last_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer
                                .alu_result_last_bit;
                        assign return_obs_fr_alu_last_matched_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.sa_pe_alu_result_last_matched;
                        assign return_obs_fr_alu_write_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer
                                .alu2ob_wr_handshake;
                        assign return_obs_fr_ready_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer.ob_out_rd_ready;
                        assign return_obs_fr_select_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] = {
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer
                                .ob_outport_pingpong_buffer_select,
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer
                                .alu2ob_pingpong_buffer_select,
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer
                                .ob2alu_pingpong_buffer_select,
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer
                                .initial_port_pingpong_buffer_select
                        };
                        assign return_obs_fr_initial_ptr_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer.initial_port_wr_ptr;
                        assign return_obs_fr_ob2alu_ptr_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer.ob2alu_rd_ptr;
                        assign return_obs_fr_alu2ob_ptr_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer.alu2ob_wr_ptr;
                        assign return_obs_fr_output_ptr_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer.ob_out_rd_ptr;
                        assign return_obs_fr_count_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] = {
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer
                                .outbuffer_group_count[1],
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer
                                .outbuffer_group_count[0]
                        };
                        assign return_obs_fr_empty_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] = {
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer
                                .outbuffer_group_empty[1],
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer
                                .outbuffer_group_empty[0]
                        };
                        assign return_obs_fr_pe_valid_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_fr_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_fr_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_fr_row]
                                .SA_COL_PE[return_obs_fr_col]
                                .u_SA_PE.u_SA_PE_Outbuffer
                                .sa_pe_outbuffer_port_valid_bit;
                        assign return_obs_fr_pe_accept_mon
                            [return_obs_fr_group][return_obs_fr_slice]
                            [return_obs_fr_row][return_obs_fr_col] =
                            return_obs_abpe_out_accept_mon
                                [return_obs_fr_group][return_obs_fr_slice]
                                [return_obs_fr_row][return_obs_fr_col];
                    end
                end
            end
        end
    endgenerate

    logic [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_fr_prev_input_last;
    logic [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_fr_prev_ready_any;
    logic [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0][3:0]
          return_obs_fr_prev_select;
    logic [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_OB_PTR_WIDTH-1:0] return_obs_fr_prev_initial_ptr;
    logic [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_OB_PTR_WIDTH-1:0] return_obs_fr_prev_ob2alu_ptr;
    logic [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_OB_PTR_WIDTH-1:0] return_obs_fr_prev_alu2ob_ptr;
    logic [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_OB_PTR_WIDTH-1:0] return_obs_fr_prev_output_ptr;
    logic [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_fr_prev_pe_valid;
    longint unsigned return_obs_fr_input_terminal_edges;
    longint unsigned return_obs_fr_input_matched_edges;
    longint unsigned return_obs_fr_input_out_edges;
    longint unsigned return_obs_fr_alu_terminal_writes;
    longint unsigned return_obs_fr_ready_set_edges;
    longint unsigned return_obs_fr_ready_clear_edges;
    longint unsigned return_obs_fr_select_change_edges;
    longint unsigned return_obs_fr_initial_ptr_changes;
    longint unsigned return_obs_fr_ob2alu_ptr_changes;
    longint unsigned return_obs_fr_alu2ob_ptr_changes;
    longint unsigned return_obs_fr_output_ptr_changes;
    longint unsigned return_obs_fr_pe_valid_edges;
    longint unsigned return_obs_fr_pe_accepts;

    initial begin
        return_obs_fr_enabled = $test$plusargs("RETURN_OBS_FINAL_RELEASE");
        return_obs_fr_limit = 256;
        return_obs_fr_plusarg_status = $value$plusargs(
            "RETURN_OBS_FINAL_RELEASE_LIMIT=%d", return_obs_fr_limit
        );
        return_obs_fr_edge_records = 0;
        return_obs_fr_input_terminal_edges = 0;
        return_obs_fr_input_matched_edges = 0;
        return_obs_fr_input_out_edges = 0;
        return_obs_fr_alu_terminal_writes = 0;
        return_obs_fr_ready_set_edges = 0;
        return_obs_fr_ready_clear_edges = 0;
        return_obs_fr_select_change_edges = 0;
        return_obs_fr_initial_ptr_changes = 0;
        return_obs_fr_ob2alu_ptr_changes = 0;
        return_obs_fr_alu2ob_ptr_changes = 0;
        return_obs_fr_output_ptr_changes = 0;
        return_obs_fr_pe_valid_edges = 0;
        return_obs_fr_pe_accepts = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_FINAL_RELEASE enabled=%0d limit_name=RETURN_OBS_FINAL_RELEASE_LIMIT limit=%0d",
                return_obs_fr_enabled,
                return_obs_fr_limit
            );
            $fflush(return_obs_fd);
            $display(
                "[0] [DIAGNOSTIC_FEATURE_ENABLE_V1] feature=RETURN_OBS_FINAL_RELEASE enabled=%0d limit=%0d",
                return_obs_fr_enabled,
                return_obs_fr_limit
            );
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or
             negedge u_NDP_Top_new.rst_n_db) begin
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_fr_prev_input_last = 0;
            return_obs_fr_prev_ready_any = 0;
            return_obs_fr_prev_select = 0;
            return_obs_fr_prev_initial_ptr = 0;
            return_obs_fr_prev_ob2alu_ptr = 0;
            return_obs_fr_prev_alu2ob_ptr = 0;
            return_obs_fr_prev_output_ptr = 0;
            return_obs_fr_prev_pe_valid = 0;
        end
        else if (return_obs_fr_enabled && return_obs_active) begin
            for (int return_obs_fr_r = 0;
                 return_obs_fr_r < `SA_ROW_PE_NUM;
                 return_obs_fr_r++) begin
                for (int return_obs_fr_c = 0;
                     return_obs_fr_c < `SA_COL_PE_NUM;
                     return_obs_fr_c++) begin
                    if (
                        return_obs_fr_input_last_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_fr_r][return_obs_fr_c] &&
                        !return_obs_fr_prev_input_last
                            [return_obs_fr_r][return_obs_fr_c]
                    )
                        return_obs_fr_input_terminal_edges++;
                    if (
                        return_obs_fr_input_last_matched_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_fr_r][return_obs_fr_c]
                    )
                        return_obs_fr_input_matched_edges++;
                    if (
                        return_obs_fr_input_last_out_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_fr_r][return_obs_fr_c]
                    )
                        return_obs_fr_input_out_edges++;
                    if (
                        return_obs_fr_alu_write_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_fr_r][return_obs_fr_c] &&
                        (
                            return_obs_fr_alu_last_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_fr_r][return_obs_fr_c] ||
                            return_obs_fr_alu_last_matched_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_fr_r][return_obs_fr_c]
                        )
                    )
                        return_obs_fr_alu_terminal_writes++;
                    if (
                        (|return_obs_fr_ready_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_fr_r][return_obs_fr_c]) &&
                        !return_obs_fr_prev_ready_any
                            [return_obs_fr_r][return_obs_fr_c]
                    )
                        return_obs_fr_ready_set_edges++;
                    if (
                        !(|return_obs_fr_ready_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_fr_r][return_obs_fr_c]) &&
                        return_obs_fr_prev_ready_any
                            [return_obs_fr_r][return_obs_fr_c]
                    )
                        return_obs_fr_ready_clear_edges++;
                    if (
                        return_obs_fr_select_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_fr_r][return_obs_fr_c] !=
                        return_obs_fr_prev_select
                            [return_obs_fr_r][return_obs_fr_c]
                    )
                        return_obs_fr_select_change_edges++;
                    if (
                        return_obs_fr_initial_ptr_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_fr_r][return_obs_fr_c] !=
                        return_obs_fr_prev_initial_ptr
                            [return_obs_fr_r][return_obs_fr_c]
                    )
                        return_obs_fr_initial_ptr_changes++;
                    if (
                        return_obs_fr_ob2alu_ptr_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_fr_r][return_obs_fr_c] !=
                        return_obs_fr_prev_ob2alu_ptr
                            [return_obs_fr_r][return_obs_fr_c]
                    )
                        return_obs_fr_ob2alu_ptr_changes++;
                    if (
                        return_obs_fr_alu2ob_ptr_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_fr_r][return_obs_fr_c] !=
                        return_obs_fr_prev_alu2ob_ptr
                            [return_obs_fr_r][return_obs_fr_c]
                    )
                        return_obs_fr_alu2ob_ptr_changes++;
                    if (
                        return_obs_fr_output_ptr_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_fr_r][return_obs_fr_c] !=
                        return_obs_fr_prev_output_ptr
                            [return_obs_fr_r][return_obs_fr_c]
                    )
                        return_obs_fr_output_ptr_changes++;
                    if (
                        return_obs_fr_pe_valid_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_fr_r][return_obs_fr_c] &&
                        !return_obs_fr_prev_pe_valid
                            [return_obs_fr_r][return_obs_fr_c]
                    )
                        return_obs_fr_pe_valid_edges++;
                    if (
                        return_obs_fr_pe_accept_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_fr_r][return_obs_fr_c]
                    )
                        return_obs_fr_pe_accepts++;
                end
            end
            if (
                return_obs_fd != 0 &&
                return_obs_fr_edge_records < return_obs_fr_limit &&
                (
                    (|return_obs_fr_input_last_matched_mon
                        [return_obs_group_id][return_obs_local_slice_id]) ||
                    (|return_obs_fr_input_last_out_mon
                        [return_obs_group_id][return_obs_local_slice_id]) ||
                    (|return_obs_fr_alu_last_mon
                        [return_obs_group_id][return_obs_local_slice_id]) ||
                    (|return_obs_fr_alu_last_matched_mon
                        [return_obs_group_id][return_obs_local_slice_id]) ||
                    (return_obs_fr_select_mon
                        [return_obs_group_id][return_obs_local_slice_id] !=
                     return_obs_fr_prev_select) ||
                    (return_obs_fr_pe_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id] &
                     ~return_obs_fr_prev_pe_valid)
                )
            ) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | FINAL_RELEASE_EDGE_V1 | n=%0d input_last=0x%0h input_last_index=0x%0h input_matched=0x%0h input_out=0x%0h alu_last=0x%0h alu_last_matched=0x%0h alu_write=0x%0h ready=0x%0h selects=0x%0h initial_ptr=0x%0h ob2alu_ptr=0x%0h alu2ob_ptr=0x%0h output_ptr=0x%0h count_state=0x%0h empty_state=0x%0h pe_valid=0x%0h pe_accept=0x%0h",
                    $time,
                    return_obs_fr_edge_records + 1,
                    return_obs_fr_input_last_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_input_last_index_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_input_last_matched_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_input_last_out_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_alu_last_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_alu_last_matched_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_alu_write_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_select_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_initial_ptr_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_ob2alu_ptr_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_alu2ob_ptr_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_output_ptr_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_count_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_empty_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_pe_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_pe_accept_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                );
                $fflush(return_obs_fd);
                return_obs_fr_edge_records++;
            end
            return_obs_fr_prev_input_last =
                return_obs_fr_input_last_mon
                    [return_obs_group_id][return_obs_local_slice_id];
            for (int return_obs_fr_r = 0;
                 return_obs_fr_r < `SA_ROW_PE_NUM;
                 return_obs_fr_r++)
                for (int return_obs_fr_c = 0;
                     return_obs_fr_c < `SA_COL_PE_NUM;
                     return_obs_fr_c++)
                    return_obs_fr_prev_ready_any
                        [return_obs_fr_r][return_obs_fr_c] =
                        |return_obs_fr_ready_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_fr_r][return_obs_fr_c];
            return_obs_fr_prev_select =
                return_obs_fr_select_mon
                    [return_obs_group_id][return_obs_local_slice_id];
            return_obs_fr_prev_initial_ptr =
                return_obs_fr_initial_ptr_mon
                    [return_obs_group_id][return_obs_local_slice_id];
            return_obs_fr_prev_ob2alu_ptr =
                return_obs_fr_ob2alu_ptr_mon
                    [return_obs_group_id][return_obs_local_slice_id];
            return_obs_fr_prev_alu2ob_ptr =
                return_obs_fr_alu2ob_ptr_mon
                    [return_obs_group_id][return_obs_local_slice_id];
            return_obs_fr_prev_output_ptr =
                return_obs_fr_output_ptr_mon
                    [return_obs_group_id][return_obs_local_slice_id];
            return_obs_fr_prev_pe_valid =
                return_obs_fr_pe_valid_mon
                    [return_obs_group_id][return_obs_local_slice_id];
        end
    end

    task automatic return_obs_write_final_release_state(
        input string event_name
    );
        begin
            if (return_obs_fr_enabled && return_obs_fd != 0) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | FINAL_RELEASE_BOUNDARY_V1 | event=%s input_terminal_edges=%0d input_matched_edges=%0d input_out_edges=%0d alu_terminal_writes=%0d ready_set_edges=%0d ready_clear_edges=%0d select_change_edges=%0d initial_ptr_changes=%0d ob2alu_ptr_changes=%0d alu2ob_ptr_changes=%0d output_ptr_changes=%0d pe_valid_edges=%0d pe_accepts=%0d sa_group_out_accept=%0d buffer5_write_edge=%0d input_last=0x%0h input_last_index=0x%0h input_matched=0x%0h input_out=0x%0h alu_last=0x%0h alu_last_matched=0x%0h ready=0x%0h selects=0x%0h initial_ptr=0x%0h ob2alu_ptr=0x%0h alu2ob_ptr=0x%0h output_ptr=0x%0h count_state=0x%0h empty_state=0x%0h pe_valid=0x%0h",
                    $time,
                    event_name,
                    return_obs_fr_input_terminal_edges,
                    return_obs_fr_input_matched_edges,
                    return_obs_fr_input_out_edges,
                    return_obs_fr_alu_terminal_writes,
                    return_obs_fr_ready_set_edges,
                    return_obs_fr_ready_clear_edges,
                    return_obs_fr_select_change_edges,
                    return_obs_fr_initial_ptr_changes,
                    return_obs_fr_ob2alu_ptr_changes,
                    return_obs_fr_alu2ob_ptr_changes,
                    return_obs_fr_output_ptr_changes,
                    return_obs_fr_pe_valid_edges,
                    return_obs_fr_pe_accepts,
                    return_obs_abpe_group_out_accept_count,
                    return_obs_buf45_wr_edge_count[1],
                    return_obs_fr_input_last_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_input_last_index_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_input_last_matched_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_input_last_out_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_alu_last_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_alu_last_matched_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_select_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_initial_ptr_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_ob2alu_ptr_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_alu2ob_ptr_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_output_ptr_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_count_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_empty_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_fr_pe_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                );
                $fflush(return_obs_fd);
            end
        end
    endtask
"""


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "FINAL_RELEASE_BOUNDARY_V1" in text:
        raise BuildError("source observer already contains final-release probe")
    path.write_text(
        text.rstrip() + FINAL_RELEASE_OBSERVER + "\n",
        encoding="utf-8",
        newline="\n",
    )
    replace_once(
        path,
        '                return_obs_write_buffer0_flow_state("DIAG_DECISION");',
        '                return_obs_write_buffer0_flow_state("DIAG_DECISION");\n'
        '                return_obs_write_final_release_state("DIAG_DECISION");',
    )
    return base.sha256(path)


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    old = "+RETURN_OBS_ABPE +RETURN_OBS_SLICE=0"
    new = (
        "+RETURN_OBS_ABPE +RETURN_OBS_FINAL_RELEASE "
        "+RETURN_OBS_FINAL_RELEASE_LIMIT=256 +RETURN_OBS_SLICE=0"
    )
    if text.count(old) != 2:
        raise BuildError(f"runner argv anchor count differs: {text.count(old)}")
    path.write_text(
        text.replace(old, new),
        encoding="utf-8",
        newline="\n",
    )


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime.py"
    anchor = """    },
)


def diagnostic_feature_binding("""
    feature_contract = """    },
    {
        "feature": "RETURN_OBS_FINAL_RELEASE",
        "enable": "+RETURN_OBS_FINAL_RELEASE",
        "limits": ("+RETURN_OBS_FINAL_RELEASE_LIMIT=256",),
        "marker_tokens": (
            "feature=RETURN_OBS_FINAL_RELEASE",
            "enabled=1",
            "limit=256",
        ),
    },
)


def diagnostic_feature_binding("""
    replace_once(path, anchor, feature_contract)


def readme() -> str:
    return f"""# node0004 v23 final-result release diagnostic

Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.

This package preserves the v22 numeric payload, W3, qparams, tail, workload,
configuration, bitstream, execplan, SCA, golden, functional RTL binding,
timeout, and backpressure.  It does not implement an RTL or configuration
repair.

The earlier claim that every ALU write must increment
`SA_PE_Outbuffer.outbuffer_group_count` is invalidated.  Initial writes create
the live psum/output slots; `alu2ob_wr_ptr` replaces those slots; final output
reads retire them.

The corrected last proven good boundary is
`SA_ALU_RESULT_ACCEPT_AND_OUTBUFFER_WRITE`.  The first unobserved interval is
`SA_ALU_RESULT_WRITE_TO_FINAL_RESULT_RELEASE_AND_PE_OUTPUT_VALID`.

The added runtime-gated feature is `{FEATURE}` with limit
`RETURN_OBS_FINAL_RELEASE_LIMIT={FEATURE_LIMIT}`.  It records only qualified
handshakes and bounded state-change edges across input terminal/index,
matched/out propagation, ALU terminal tag/write, output-ready set/clear, four
ping-pong selectors, four pointers, first PE/SA/Buffer5 output acceptance.
Outbuffer count/empty are returned only as corroborating state and never count
as qualified progress or prove a defect.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `{INSTALL_NAME}_return.zip`.
"""


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v23-source-") as temp:
        source = safe_extract(Path(temp))
        shutil.copytree(source, package)
    replace_identity(package)
    observer_sha = patch_observer(package)
    patch_runner(package)
    patch_runtime(package)
    (package / "README.md").write_text(
        readme(), encoding="utf-8", newline="\n"
    )

    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-final-release-diagnostic-package-v23",
            "install_name": INSTALL_NAME,
            "status": "PACKAGE_READY_NOT_RUN",
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt_in_this_successor": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
        }
    )
    receipts = manifest["active_receipts"]
    receipts["plan_mutable_provenance_sha256"] = PLAN_MUTABLE_SHA256
    receipts["server_package_rule_sha256"] = SERVER_RULE_SHA256
    for item in receipts["generation_read_receipt"]:
        if item.get("reason") == "common server package gates":
            item["path"] = ".agents/rules/服务器测试包生成规则.md"
            item["sha256"] = SERVER_RULE_SHA256
        elif item.get("reason") == "server package routing":
            item["path"] = ".agents/rules/生成前必读索引.md"
            item["sha256"] = INDEX_SHA256
        elif item.get("reason") == "Conv INT8 SA accumulate release gate":
            item["path"] = ".agents/rules/INT8_SA点积专项规则.md"
    receipts["rules"] = [
        "CDA-SCA-D-TB-READBACK-LENGTH-001",
        "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
        "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
        "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001",
        "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
        "CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001",
        "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
        "CDA-SERVER-NO-DYNAMIC-BASELINE-001",
        "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
        "CDA-SERVER-OBSERVER-CAPTURE-EDGE-WITNESS-001",
        "CDA-SERVER-OBSERVER-DECOUPLED-HANDSHAKE-001",
        "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
        "CDA-SERVER-OBSERVER-EVIDENCE-DOMINANCE-001",
        "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
        "CDA-SERVER-ONE-COMMAND-001",
        "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
        "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
        "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
        "CDA-SERVER-RETURN-RECEIPT-001",
        "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
        "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
        "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
        "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001",
        "CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001",
        "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
        "CDA-SERVER-TB-TARGET-DIRECTORY-ISOLATION-001",
        "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
        "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
        "CDA-SERVER-WORKLOAD-PROVENANCE-001",
        "CDA-SA-NODE0004-ASSUMED-FIXED-HARDWARE-001",
    ]
    manifest["observer_sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"]["sha256"] = observer_sha
    manifest["return_reanalysis"] = {
        "bound_source_package": {
            "path": (
                "artifacts/operator_config_validation/"
                f"r5-server-test-packages/{SOURCE_NAME}.zip"
            ),
            "sha256": SOURCE_ZIP_SHA256,
        },
        "invalidation_receipt": {
            "task_record": (
                ".agents/task_records/"
                "20260803_conv_node0004_v22_outbuffer_occupancy_"
                "adjudication_correction.md"
            ),
            "task_record_sha256": (
                "0eaa10c0e7f97daf3c0765fdea83489733f9061a2749b548654bd65b3a781cb2"
            ),
            "machine_report": (
                "outputs/conv_node0004_v22_return_analysis/"
                "outbuffer_occupancy_adjudication_correction.json"
            ),
            "machine_report_sha256": (
                "2369d9eb4976b67d54a34b5eacfb1e24877b3a2a7000d29967ab082a3d960b8c"
            ),
            "invalidated_blocker": (
                "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            ),
            "invalidated_status": "WAIT_RTL_FIX",
            "invalidated_equation": (
                "delta=4*initial_accept+1*alu_accept-1*output_read_accept"
            ),
        },
        "last_proven_good": "SA_ALU_RESULT_ACCEPT_AND_OUTBUFFER_WRITE",
        "first_divergence": (
            "SA_ALU_RESULT_WRITE_TO_FINAL_RESULT_RELEASE_AND_PE_OUTPUT_VALID"
        ),
        "open_blocker": (
            "B_CONV_NODE0004_SA_FINAL_RESULT_RELEASE_PATH_UNOBSERVED"
        ),
        "rtl_defect_classification": "NOT_YET_PROVEN",
    }
    manifest["narrow_final_release_diagnostic"] = {
        "feature": FEATURE,
        "runtime_enable_parameter": f"+{FEATURE}",
        "limit_parameter": f"+RETURN_OBS_FINAL_RELEASE_LIMIT={FEATURE_LIMIT}",
        "time_zero_marker": (
            "DIAGNOSTIC_FEATURE_ENABLE_V1 "
            f"feature={FEATURE} enabled=1 limit={FEATURE_LIMIT}"
        ),
        "edge_record": "FINAL_RELEASE_EDGE_V1",
        "decision_record": "FINAL_RELEASE_BOUNDARY_V1",
        "returned_record_target": "runs/c0/return_observer.log",
        "feature_receipt_target": "evidence/diagnostic_feature_binding.json",
        "qualified_evidence": [
            "input terminal matched/out edge",
            "ALU terminal-tag write handshake",
            "ob_out_rd_ready set/clear edge",
            "four ping-pong selector changes",
            "four pointer changes and wraps",
            "first PE output valid/accept",
            "first SA group output accept",
            "first Buffer5 write edge",
        ],
        "corroborating_state_only": [
            "outbuffer_group_count",
            "outbuffer_group_empty",
        ],
        "result_partition": [
            (
                "input terminal never matched/out => config/input tag-terminal "
                "mismatch interval"
            ),
            (
                "ALU terminal write but no matching ready set => final-release "
                "RTL leaf interval"
            ),
            (
                "ready set on non-output-selected group or pointer divergence "
                "=> ping-pong/pointer misalignment interval"
            ),
            (
                "ready selected and PE valid but no accept => downstream "
                "backpressure/SA serialization interval"
            ),
        ],
        "timeout_changed": False,
        "backpressure_changed": False,
        "functional_fix": False,
    }
    binding = manifest["diagnostic_feature_runtime_binding"]
    binding["features"].append(
        {
            "feature": FEATURE,
            "runtime_enable_parameter": f"+{FEATURE}",
            "limit_or_budget_parameters": [
                f"+RETURN_OBS_FINAL_RELEASE_LIMIT={FEATURE_LIMIT}"
            ],
            "time_zero_marker": (
                "DIAGNOSTIC_FEATURE_ENABLE_V1 "
                f"feature={FEATURE} enabled=1 limit={FEATURE_LIMIT}"
            ),
            "expected_record_schema": "FINAL_RELEASE_BOUNDARY_V1",
        }
    )
    manifest["superseded_v22_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_ZIP_SHA256,
        "status": "SUPERSEDED_BY_CORRECTED_NARROW_DIAGNOSTIC",
    }
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    observer_receipt = base.observer_precompile_receipt(package, observer_sha)
    if not observer_receipt["valid"]:
        raise BuildError(
            f"observer XMR gate failed: {observer_receipt['errors']}"
        )
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    package = output / INSTALL_NAME
    zip_path = output / f"{INSTALL_NAME}.zip"
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    validation = output / f"{INSTALL_NAME}.validation.json"
    for target in (package, zip_path, sidecar, validation):
        if target.exists():
            raise BuildError(f"refusing to overwrite: {target}")
    package = build_directory(output)
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v23-repeat-") as temp:
        repeat = Path(temp)
        repeat_package = build_directory(repeat)
        repeat_zip = repeat / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v23 deterministic repeat differs")
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    report: dict[str, Any] = {
        "schema": "node0004-final-release-diagnostic-build-v23",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "source_v22_sha256": SOURCE_ZIP_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "deterministic_rebuild_equal": deterministic,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt_in_this_successor": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    base.write_json(validation, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
