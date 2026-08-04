from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_node0071_complete_server_package import deterministic_zip, write_json
from tools.gap_node0071_complete_server_runtime import file_records
from tools import build_gap_node0071_arm_ready_factor_v30_package as base


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v30_arm_ready_factor_diag"
INSTALL_NAME = "r5_n71_gap_v31_col_ag_mrm_lane_diag"
TEST_ID = "r5-gap-node0071-v31-col-ag-mrm-byte-lane-diagnostic"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = "f0606ebeab52391856a7fb939b6f8c6d02984ae8384117d53d906ba1a9c4a931"
TRIGGER_RETURN_SHA256 = "b72a3baa7468aa6a09254c90a7d488aa949b37045b1dad83670cc8a9dc2239f6"
TRIGGER_ANALYSIS = (
    ROOT / "artifacts/operator_config_validation/r5-gap-node0071-v30-return-analysis/report.json"
)
OBSERVER = "tb_probe/native_return_observer.svh"
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    OBSERVER,
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"marker differs: {label} ({text.count(old)})")
    return text.replace(old, new, 1)


def root_builder():
    return base.base.base.base.base.base


def configure_source() -> None:
    root = root_builder()
    root.SOURCE_NAME = SOURCE_NAME
    root.INSTALL_NAME = INSTALL_NAME
    root.SOURCE_ZIP = SOURCE_ZIP
    root.SOURCE_SHA256 = SOURCE_SHA256


DECLARATIONS = r'''    // v31: COL-LC -> MSE0 WR_Buffer_AG -> Buffer0 MRM byte-lane diagnostic.
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`IGA_COL_LC_PORT_WIDTH-1:0] return_obs_lane_col_out_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`IGA_COL_LC_DST_NUM-1:0] return_obs_lane_col_bp_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_lane_bag_wr_mon,
          return_obs_lane_bag_bp_mon,
          return_obs_lane_bag_rd_mon,
          return_obs_lane_bag_empty_mon,
          return_obs_lane_mse_wvalid_mon,
          return_obs_lane_mse_ready_mon,
          return_obs_lane_mrm_wvalid_mon,
          return_obs_lane_mrm_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_BUF_AG_INPORT_TAG_WIDTH-1:0] return_obs_lane_bag_tag_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_BUF_AG_INPORT_IDX_WIDTH-1:0] return_obs_lane_bag_idx_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_BUF_REQ_NUM-1:0] return_obs_lane_mse_req_mon,
                                 return_obs_lane_mrm_req_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`BUFFER_ROW_ADDR_WIDTH-1:0] return_obs_lane_mse_row_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_BUF_REQ_NUM-1:0][`BUFFER_COL_ADDR_WIDTH-1:0]
          return_obs_lane_mse_col_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`BUFFER_BANK_ADDR_WIDTH-1:0] return_obs_lane_mrm_row_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`BUFFER_BANK_NUM-1:0][`BUFFER_STRB_WIDTH-1:0]
          return_obs_lane_mrm_strb_mon;

    generate
        for (genvar return_obs_lane_group = 0;
             return_obs_lane_group < `SLICE_GROUP_SIZE;
             return_obs_lane_group++) begin : RETURN_OBS_LANE_GROUP_GEN
            for (genvar return_obs_lane_slice = 0;
                 return_obs_lane_slice < `SLICE_GROUP_NUM;
                 return_obs_lane_slice++) begin : RETURN_OBS_LANE_SLICE_GEN
                assign return_obs_lane_col_out_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_Index_Generation_Array
                        .iga_col_lc_outport[0];
                assign return_obs_lane_col_bp_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_Index_Generation_Array
                        .iga_col_lc_outport_bp_post[0];
                assign return_obs_lane_bag_wr_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0]
                        .RD_MSE.u_Memory_RD_Stream_Engine.u_WR_Buffer_AG.buf_ag_ob_wr_en;
                assign return_obs_lane_bag_bp_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0]
                        .RD_MSE.u_Memory_RD_Stream_Engine.u_WR_Buffer_AG.buf_ag_bp_pre;
                assign return_obs_lane_bag_rd_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0]
                        .RD_MSE.u_Memory_RD_Stream_Engine.u_WR_Buffer_AG.buf_ag_ob_rd_en;
                assign return_obs_lane_bag_empty_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0]
                        .RD_MSE.u_Memory_RD_Stream_Engine.u_WR_Buffer_AG.buf_ag_ob_empty;
                assign return_obs_lane_bag_tag_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0]
                        .RD_MSE.u_Memory_RD_Stream_Engine.u_WR_Buffer_AG.mse_buf_ag_tag;
                assign return_obs_lane_bag_idx_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0]
                        .RD_MSE.u_Memory_RD_Stream_Engine.u_WR_Buffer_AG.mse_buf_ag_idx;
                assign return_obs_lane_mse_req_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0]
                        .RD_MSE.u_Memory_RD_Stream_Engine.mse2buf_wreq_valid;
                assign return_obs_lane_mse_row_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0]
                        .RD_MSE.u_Memory_RD_Stream_Engine.mse2buf_wreq_row_addr;
                assign return_obs_lane_mse_col_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0]
                        .RD_MSE.u_Memory_RD_Stream_Engine.mse2buf_wreq_col_addr;
                assign return_obs_lane_mse_wvalid_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0]
                        .RD_MSE.u_Memory_RD_Stream_Engine.mse2buf_wvalid;
                assign return_obs_lane_mse_ready_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0]
                        .RD_MSE.u_Memory_RD_Stream_Engine.buf2mse_wreq_ready;
                assign return_obs_lane_mrm_req_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[0].u_Buffer_Manager.mrm2buf_req_valid;
                assign return_obs_lane_mrm_row_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[0].u_Buffer_Manager.mrm2buf_req_addr;
                assign return_obs_lane_mrm_strb_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[0].u_Buffer_Manager.mrm2buf_req_strb;
                assign return_obs_lane_mrm_wvalid_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[0].u_Buffer_Manager.mrm2buf_wvalid;
                assign return_obs_lane_mrm_ready_mon
                    [return_obs_lane_group][return_obs_lane_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_lane_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_lane_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[0].u_Buffer_Manager.buf2mrm_req_ready;
            end
        end
    endgenerate

    bit return_obs_lane_enabled;
    int return_obs_lane_limit;
    int return_obs_lane_emit_count;
    longint unsigned return_obs_lane_col_accept_count;
    longint unsigned return_obs_lane_bag_accept_count;
    longint unsigned return_obs_lane_mse_write_accept_count;
    longint unsigned return_obs_lane_mrm_write_accept_count;
    longint unsigned return_obs_lane_first_col_accept;
    longint unsigned return_obs_lane_last_col_accept;
    longint unsigned return_obs_lane_last_bag_accept;
    longint unsigned return_obs_lane_last_mse_write_accept;
    longint unsigned return_obs_lane_last_mrm_write_accept;

    task automatic return_obs_lane_reset;
        begin
            return_obs_lane_emit_count = 0;
            return_obs_lane_col_accept_count = 0;
            return_obs_lane_bag_accept_count = 0;
            return_obs_lane_mse_write_accept_count = 0;
            return_obs_lane_mrm_write_accept_count = 0;
            return_obs_lane_first_col_accept = 0;
            return_obs_lane_last_col_accept = 0;
            return_obs_lane_last_bag_accept = 0;
            return_obs_lane_last_mse_write_accept = 0;
            return_obs_lane_last_mrm_write_accept = 0;
        end
    endtask

'''


SUMMARY = r'''                    if (return_obs_lane_enabled) begin
                        $fdisplay(
                            return_obs_fd,
                            "%0t | COL_AG_MRM_LANE_COUNTS_V1 | event=%s col_accept=%0d bag_accept=%0d mse_write_accept=%0d mrm_write_accept=%0d records=%0d limit=%0d",
                            $time, event_name,
                            return_obs_lane_col_accept_count,
                            return_obs_lane_bag_accept_count,
                            return_obs_lane_mse_write_accept_count,
                            return_obs_lane_mrm_write_accept_count,
                            return_obs_lane_emit_count,
                            return_obs_lane_limit
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | COL_AG_MRM_LANE_STATE_V1 | event=%s col_out=0x%0h col_bp=0x%0h bag_wr=%0b bag_bp=%0b bag_rd=%0b bag_empty=%0b bag_tag=0x%0h bag_idx=0x%0h mse_req=0x%0h mse_row=0x%0h mse_col=0x%0h mse_wvalid=%0b mse_ready=%0b mrm_req=0x%0h mrm_row=0x%0h mrm_strb=0x%0h mrm_wvalid=%0b mrm_ready=%0b valid_at_arm_addr=0x%0h",
                            $time, event_name,
                            return_obs_lane_col_out_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_col_bp_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_bag_wr_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_bag_bp_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_bag_rd_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_bag_empty_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_bag_tag_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_bag_idx_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_mse_req_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_mse_row_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_mse_col_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_mse_wvalid_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_mse_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_mrm_req_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_mrm_row_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_mrm_strb_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_mrm_wvalid_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_lane_mrm_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                            {return_obs_flow_buf_valid_mon[return_obs_group_id][return_obs_local_slice_id][0][7]
                                [return_obs_flow_arm_addr_mon[return_obs_group_id][return_obs_local_slice_id][0]],
                             return_obs_flow_buf_valid_mon[return_obs_group_id][return_obs_local_slice_id][0][6]
                                [return_obs_flow_arm_addr_mon[return_obs_group_id][return_obs_local_slice_id][0]],
                             return_obs_flow_buf_valid_mon[return_obs_group_id][return_obs_local_slice_id][0][5]
                                [return_obs_flow_arm_addr_mon[return_obs_group_id][return_obs_local_slice_id][0]],
                             return_obs_flow_buf_valid_mon[return_obs_group_id][return_obs_local_slice_id][0][4]
                                [return_obs_flow_arm_addr_mon[return_obs_group_id][return_obs_local_slice_id][0]],
                             return_obs_flow_buf_valid_mon[return_obs_group_id][return_obs_local_slice_id][0][3]
                                [return_obs_flow_arm_addr_mon[return_obs_group_id][return_obs_local_slice_id][0]],
                             return_obs_flow_buf_valid_mon[return_obs_group_id][return_obs_local_slice_id][0][2]
                                [return_obs_flow_arm_addr_mon[return_obs_group_id][return_obs_local_slice_id][0]],
                             return_obs_flow_buf_valid_mon[return_obs_group_id][return_obs_local_slice_id][0][1]
                                [return_obs_flow_arm_addr_mon[return_obs_group_id][return_obs_local_slice_id][0]],
                             return_obs_flow_buf_valid_mon[return_obs_group_id][return_obs_local_slice_id][0][0]
                                [return_obs_flow_arm_addr_mon[return_obs_group_id][return_obs_local_slice_id][0]]}
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | COL_AG_MRM_LANE_WITNESS_V1 | event=%s first_col=%0d last_col=%0d last_bag=%0d last_mse_write=%0d last_mrm_write=%0d",
                            $time, event_name,
                            return_obs_lane_first_col_accept,
                            return_obs_lane_last_col_accept,
                            return_obs_lane_last_bag_accept,
                            return_obs_lane_last_mse_write_accept,
                            return_obs_lane_last_mrm_write_accept
                        );
                    end
'''


SAMPLER = r'''    // v31 sampler: accepted transactions only; stable levels are state.
    always @(posedge u_NDP_Top_new.clk_sg) begin
        if (
            u_NDP_Top_new.rst_n_sg &&
            return_obs_enabled &&
            return_obs_lane_enabled &&
            return_obs_active &&
            return_obs_fd != 0
        ) begin
            bit lane_col_accept;
            bit lane_bag_accept;
            bit lane_mse_write_accept;
            bit lane_mrm_write_accept;
            bit lane_any_event;
            lane_col_accept =
                return_obs_lane_col_out_mon[return_obs_group_id][return_obs_local_slice_id]
                    [`IGA_COL_LC_PORT_WIDTH-1] &&
                (&return_obs_lane_col_bp_mon[return_obs_group_id][return_obs_local_slice_id]);
            lane_bag_accept =
                return_obs_lane_bag_wr_mon[return_obs_group_id][return_obs_local_slice_id] &&
                return_obs_lane_bag_bp_mon[return_obs_group_id][return_obs_local_slice_id];
            lane_mse_write_accept =
                (|return_obs_lane_mse_req_mon[return_obs_group_id][return_obs_local_slice_id]) &&
                return_obs_lane_mse_wvalid_mon[return_obs_group_id][return_obs_local_slice_id] &&
                return_obs_lane_mse_ready_mon[return_obs_group_id][return_obs_local_slice_id];
            lane_mrm_write_accept =
                (|return_obs_lane_mrm_req_mon[return_obs_group_id][return_obs_local_slice_id]) &&
                return_obs_lane_mrm_wvalid_mon[return_obs_group_id][return_obs_local_slice_id] &&
                return_obs_lane_mrm_ready_mon[return_obs_group_id][return_obs_local_slice_id];
            lane_any_event = lane_col_accept || lane_bag_accept ||
                lane_mse_write_accept || lane_mrm_write_accept;
            if (lane_col_accept) begin
                return_obs_lane_col_accept_count++;
                if (return_obs_lane_first_col_accept == 0)
                    return_obs_lane_first_col_accept = return_obs_sg_clock_edge_count;
                return_obs_lane_last_col_accept = return_obs_sg_clock_edge_count;
            end
            if (lane_bag_accept) begin
                return_obs_lane_bag_accept_count++;
                return_obs_lane_last_bag_accept = return_obs_sg_clock_edge_count;
            end
            if (lane_mse_write_accept) begin
                return_obs_lane_mse_write_accept_count++;
                return_obs_lane_last_mse_write_accept = return_obs_sg_clock_edge_count;
            end
            if (lane_mrm_write_accept) begin
                return_obs_lane_mrm_write_accept_count++;
                return_obs_lane_last_mrm_write_accept = return_obs_sg_clock_edge_count;
            end
            if (lane_any_event && return_obs_lane_emit_count < return_obs_lane_limit) begin
                return_obs_lane_emit_count++;
                $fdisplay(
                    return_obs_fd,
                    "%0t | COL_AG_MRM_LANE_EVENT_V1 | edge=%0d col_accept=%0b col_out=0x%0h col_bp=0x%0h bag_accept=%0b bag_tag=0x%0h bag_idx=0x%0h mse_write_accept=%0b mse_req=0x%0h mse_row=0x%0h mse_col=0x%0h mrm_write_accept=%0b mrm_req=0x%0h mrm_row=0x%0h mrm_strb=0x%0h",
                    $time, return_obs_sg_clock_edge_count,
                    lane_col_accept,
                    return_obs_lane_col_out_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_lane_col_bp_mon[return_obs_group_id][return_obs_local_slice_id],
                    lane_bag_accept,
                    return_obs_lane_bag_tag_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_lane_bag_idx_mon[return_obs_group_id][return_obs_local_slice_id],
                    lane_mse_write_accept,
                    return_obs_lane_mse_req_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_lane_mse_row_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_lane_mse_col_mon[return_obs_group_id][return_obs_local_slice_id],
                    lane_mrm_write_accept,
                    return_obs_lane_mrm_req_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_lane_mrm_row_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_lane_mrm_strb_mon[return_obs_group_id][return_obs_local_slice_id]
                );
                $fflush(return_obs_fd);
            end
        end
    end

'''


def upgrade_observer(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    // v30: Buffer0 ARM read-ready conjunction factor diagnostic.\n",
        DECLARATIONS + "    // v30: Buffer0 ARM read-ready conjunction factor diagnostic.\n",
        "v31 declarations",
    )
    text = replace_once(
        text,
        '        return_obs_armf_enabled =\n'
        '            $test$plusargs("RETURN_OBS_BUFFER0_ARM_READY_FACTORS");\n',
        '        return_obs_armf_enabled =\n'
        '            $test$plusargs("RETURN_OBS_BUFFER0_ARM_READY_FACTORS");\n'
        '        return_obs_lane_enabled =\n'
        '            $test$plusargs("RETURN_OBS_COL_AG_MRM_LANE");\n',
        "v31 enable",
    )
    text = replace_once(
        text,
        "        return_obs_armf_limit = 256;\n",
        "        return_obs_armf_limit = 256;\n"
        "        return_obs_lane_limit = 256;\n",
        "v31 default limit",
    )
    text = replace_once(
        text,
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_FILE=%s",\n',
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_COL_AG_MRM_LANE_LIMIT=%d",\n'
        '                return_obs_lane_limit\n'
        '            );\n'
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_FILE=%s",\n',
        "v31 limit plusarg",
    )
    text = text.replace(
        "        return_obs_armf_reset();\n",
        "        return_obs_armf_reset();\n"
        "        return_obs_lane_reset();\n",
    )
    if text.count("return_obs_lane_reset();") != 2:
        raise BuildError("v31 reset call count differs")
    text = replace_once(
        text,
        "                    if (return_obs_armf_enabled) begin\n",
        SUMMARY + "                    if (return_obs_armf_enabled) begin\n",
        "v31 summary",
    )
    text = replace_once(
        text,
        "buffer0_arm_ready_factors=%0d buffer0_arm_ready_factors_limit=%0d",
        "buffer0_arm_ready_factors=%0d buffer0_arm_ready_factors_limit=%0d "
        "col_ag_mrm_lane=%0d col_ag_mrm_lane_limit=%0d",
        "v31 time0 format",
    )
    text = replace_once(
        text,
        "                        return_obs_armf_enabled,\n"
        "                        return_obs_armf_limit\n",
        "                        return_obs_armf_enabled,\n"
        "                        return_obs_armf_limit,\n"
        "                        return_obs_lane_enabled,\n"
        "                        return_obs_lane_limit\n",
        "v31 time0 args",
    )
    text = replace_once(
        text,
        "    // v30 factor sampler: only qualified accepts and factor edges advance.\n",
        SAMPLER + "    // v30 factor sampler: only qualified accepts and factor edges advance.\n",
        "v31 sampler",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def upgrade_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "  +RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256\n",
        "  +RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256\n"
        "  +RETURN_OBS_COL_AG_MRM_LANE\n"
        "  +RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256\n",
        "runner v31 plusargs",
    )
    text = replace_once(
        text,
        "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256 +RETURN_OBS_FILE=",
        "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256 "
        "+RETURN_OBS_COL_AG_MRM_LANE "
        "+RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256 +RETURN_OBS_FILE=",
        "runner v31 argv receipt",
    )
    marker = (
        "  if [ \"$arm_ready_factor_ok\" = true ]; then\n"
        "    printf 'buffer0_arm_ready_factors_enabled=true\\n"
        "buffer0_arm_ready_factors_limit=256\\n"
        "buffer0_arm_ready_factors_records_returned=true\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  else\n"
        "    printf 'buffer0_arm_ready_factors_enabled=false\\n"
        "buffer0_arm_ready_factors_limit=UNKNOWN\\n"
        "buffer0_arm_ready_factors_records_returned=false\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  fi\n"
    )
    addition = marker + (
        "  if [ \"$observer_ok\" = true ] && "
        "grep -Fq 'col_ag_mrm_lane=1' \"$observer_log\" && "
        "grep -Fq 'col_ag_mrm_lane_limit=256' \"$observer_log\" && "
        "grep -Fq 'COL_AG_MRM_LANE_COUNTS_V1' \"$observer_log\" && "
        "grep -Fq 'COL_AG_MRM_LANE_STATE_V1' \"$observer_log\" && "
        "grep -Fq 'COL_AG_MRM_LANE_WITNESS_V1' \"$observer_log\"; then\n"
        "    col_ag_mrm_lane_ok=true\n"
        "  else\n"
        "    col_ag_mrm_lane_ok=false\n"
        "  fi\n"
        "  if [ \"$col_ag_mrm_lane_ok\" = true ]; then\n"
        "    printf 'col_ag_mrm_lane_enabled=true\\n"
        "col_ag_mrm_lane_limit=256\\n"
        "col_ag_mrm_lane_records_returned=true\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  else\n"
        "    printf 'col_ag_mrm_lane_enabled=false\\n"
        "col_ag_mrm_lane_limit=UNKNOWN\\n"
        "col_ag_mrm_lane_records_returned=false\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  fi\n"
    )
    text = replace_once(text, marker, addition, "runner v31 receipt")
    path.write_text(text, encoding="utf-8", newline="\n")


def current_receipts(source_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    receipts = []
    for item in source_manifest["final_zip_rule_self_audit_contract"]["read_receipt"]:
        receipt = dict(item)
        receipt["sha256"] = sha256(ROOT / receipt["path"])
        receipt["current_match"] = True
        receipts.append(receipt)
    return receipts


def update_manifest(package: Path, source_manifest: dict[str, Any]) -> None:
    manifest = root_builder().replace_identity(source_manifest)
    receipts = current_receipts(source_manifest)
    manifest.update(
        {
            "schema": "gap-node0071-col-ag-mrm-byte-lane-diagnostic-package-v31",
            "test_id": TEST_ID,
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "read-only accepted-event chain from IGA COL-LC0 through "
                "MSE0 WR_Buffer_AG and Buffer0 MRM byte-lane writes"
            ),
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_SHA256,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "source_numeric_payload_reused_without_rebuild": True,
            "functional_fix": False,
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_run_performed": False,
            "uploaded": False,
            "lease_acquired": False,
        }
    )
    audit = manifest["final_zip_rule_self_audit_contract"]
    audit["read_receipt"] = receipts
    audit["all_current_match"] = True
    audit["plan_sha256_mutable_provenance_only"] = sha256(ROOT / ".agents/plan.md")
    audit["final_zip_rule_self_audit_pass"] = "PENDING_EXTERNAL_RELEASE_REPORT"
    manifest["rule_receipts"]["server_rule_sha256"] = sha256(
        ROOT / ".agents/rules/服务器测试包生成规则.md"
    )
    manifest["rule_receipts"]["generation_index_sha256"] = sha256(
        ROOT / ".agents/rules/生成前必读索引.md"
    )
    manifest["rule_receipts"]["current_match"] = True
    manifest["rule_receipts"]["plan_sha256_mutable_provenance_only"] = sha256(
        ROOT / ".agents/plan.md"
    )
    manifest["post_generation_rule_drift"] = {
        "content_neutral": False,
        "current_server_rule_sha256": sha256(
            ROOT / ".agents/rules/服务器测试包生成规则.md"
        ),
        "resolution": "fresh v31 exact final bytes bind current rules",
    }
    manifest["col_ag_mrm_byte_lane_diagnostic_contract"] = {
        "trigger_return_sha256": TRIGGER_RETURN_SHA256,
        "trigger_analysis_sha256": sha256(TRIGGER_ANALYSIS),
        "last_proven_good": (
            "two Buffer0 ARM full-row reads accepted with all selected banks "
            "ready and NRM read barrier low"
        ),
        "first_divergence": (
            "THIRD_BUFFER0_ARM_ROW_READ_HELD_WITH_ALL_SELECTED_BANK_"
            "READINESS_ZERO_AND_NRM_READ_BARRIER_ZERO"
        ),
        "runtime_enable": "+RETURN_OBS_COL_AG_MRM_LANE",
        "runtime_limit": "+RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256",
        "time0_marker": "col_ag_mrm_lane=1 col_ag_mrm_lane_limit=256",
        "records": [
            "COL_AG_MRM_LANE_EVENT_V1",
            "COL_AG_MRM_LANE_COUNTS_V1",
            "COL_AG_MRM_LANE_STATE_V1",
            "COL_AG_MRM_LANE_WITNESS_V1",
        ],
        "clock": "clk_sg",
        "qualified_events": [
            "COL-LC0 valid and all downstream backpressure accepts",
            "MSE0 WR_Buffer_AG valid write and bp_pre accept",
            "MSE0 address/data paired write request and Buffer-ready accept",
            "Buffer0 MRM request/data and Buffer-ready accept",
        ],
        "state_only": [
            "stable COL/tag/address/request/ready/strobe level",
            "stable Buffer0 valid-byte snapshot",
        ],
        "stable_level_counts_as_progress": False,
        "read_only": True,
        "drives_dut": False,
        "changes_timeout": False,
        "hdl_positive_control_scope": (
            "v31 new XMR declarations, accepted-event conjunctions, counters, "
            "summary records, runtime enable and return binding"
        ),
    }
    feature = manifest["diagnostic_feature_runtime_enable_contract"]
    feature["features"] = list(feature.get("features", [])) + [
        {
            "name": "col_ag_mrm_lane",
            "runtime_enable": "+RETURN_OBS_COL_AG_MRM_LANE",
            "runtime_limit": "+RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256",
            "time0_marker": "col_ag_mrm_lane=1 col_ag_mrm_lane_limit=256",
            "returned_binding_receipt": "evidence/observer_binding.txt",
            "return_target": "runs/return_observer.log",
            "zero_when_disabled": "DISABLED_INSTRUMENTATION_ZERO",
        }
    ]
    manifest["generation_provenance"].update(
        {
            "tool": "tools/build_gap_node0071_col_ag_mrm_lane_v31_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "trigger_return_sha256": TRIGGER_RETURN_SHA256,
            "numeric_payload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change": (
                "add bounded accepted-event COL-LC0 to MSE0 WR_Buffer_AG to "
                "Buffer0 MRM byte-lane observer"
            ),
        }
    )
    manifest["files"] = file_records(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_source()
    root = root_builder()
    package = root.extract_source(destination)
    source_manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    source_records = file_records(package, exclude_manifest=False)
    numeric_before = {
        path: record
        for path, record in file_records(package / "workload", exclude_manifest=False).items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    root.rewrite_identity(package)
    upgrade_observer(package / OBSERVER)
    upgrade_runner(package / "PREPARE_AND_RUN.sh")
    (package / "README.md").write_text(
        "# GAP node0071 v31 COL/AG/MRM byte-lane diagnostic\n\n"
        f"Test ID: `{TEST_ID}`.\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It preserves "
        "the frozen numeric/config/golden/execplan/functional-RTL payload and "
        "adds bounded read-only accepted-event evidence from COL-LC0 through "
        "MSE0 WR_Buffer_AG to Buffer0 MRM byte-lane writes.\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package, source_manifest)
    numeric_after = {
        path: record
        for path, record in file_records(package / "workload", exclude_manifest=False).items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    if numeric_before != numeric_after or len(numeric_after) != 73:
        raise BuildError("frozen 73-file numeric/workload tree drifted")
    final_records = file_records(package, exclude_manifest=False)
    if set(source_records) != set(final_records):
        raise BuildError("package relative file set changed")
    changed = {
        path for path in source_records if source_records[path] != final_records[path]
    }
    if changed != ALLOWED_CHANGED:
        raise BuildError(f"changed path set differs: {sorted(changed)}")
    frozen = sorted(set(source_records) - ALLOWED_CHANGED)
    return package, {
        "source_v30_zip_sha256": SOURCE_SHA256,
        "changed_paths": sorted(changed),
        "changed_paths_exact_allowlist": True,
        "frozen_numeric_workload_file_count": len(numeric_after),
        "frozen_numeric_workload_tree_equal": True,
        "frozen_other_file_count": len(frozen),
        "frozen_other_tree_equal": all(
            source_records[path] == final_records[path] for path in frozen
        ),
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    digest = sha256(zip_path)
    tree = file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(prefix="gap-node0071-v31-repeat-") as temp:
        repeated, _ = build_directory(Path(temp))
        repeated_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        deterministic_zip(repeated, repeated_zip, archive_root=INSTALL_NAME)
        if sha256(repeated_zip) != digest:
            raise BuildError("repeat ZIP differs")
        if file_records(repeated, exclude_manifest=False) != tree:
            raise BuildError("repeat package tree differs")
    return {"package_tree_equal": True, "zip_equal": True, "repeat_zip_sha256": digest}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=PACKAGE_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    package = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package, zip_path, sidecar, validation):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        package, proof = build_directory(output_root)
        repeated = repeat_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
        )
        result = {
            "schema": "gap-node0071-col-ag-mrm-byte-lane-v31-build-v1",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "test_id": TEST_ID,
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package": str(package),
            "zip": str(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "zip_sha256": digest,
            "sidecar": str(sidecar),
            "sidecar_sha256": sha256(sidecar),
            **proof,
            "repeat_build": repeated,
            "numeric_analysis_repeated": False,
            "workload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
        }
        write_json(validation, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
