from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v7_four_way_binding_package_v8 as base  # noqa: E402


SOURCE_NAME = "r5_n4_hw_v18_a_reuse_diag"
INSTALL_NAME = "r5_n4_hw_v19_buffer0_flow_diag"
SOURCE_ZIP_SHA256 = (
    "aa12edc55f10e28133e843e3ddeff832831a8d8c71cef47c5bc69e7c48f73fc1"
)
BOUND_RETURN_SHA256 = (
    "c064ea3a88bbba648f2d9fedb4cf8c1f833680711820014d62a2013bb3fa69c0"
)
SERVER_RULE_SHA256 = (
    "507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d"
)
PLAN_MUTABLE_SHA256 = (
    "523afbf1f98258940a7333754ea684b519fe51f6c3ac08c6a7ad985461c77f75"
)
SOURCE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / SOURCE_NAME
)
SOURCE_ZIP = SOURCE_ROOT.with_suffix(".zip")
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


FLOW_OBSERVER_BLOCK = r'''

    // v19: the v18 return proved selector alignment and one successful
    // Buffer0-to-SA product. This record is the single remaining diagnostic
    // interval: WR_Buffer_AG -> Buffer0 row-valid/full -> ARM address/life.
    // Counters below are qualified handshakes; level vectors are snapshots.
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
          return_obs_b0_ag_ob_cnt_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_b0_ag_full_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_b0_ag_empty_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_b0_ag_wr_en_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_b0_ag_bp_pre_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_b0_ag_rd_en_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_b0_mse_req_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_BUF_REQ_NUM-1:0] return_obs_b0_mse_req_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`BUFFER_ROW_ADDR_WIDTH-1:0] return_obs_b0_mse_req_row_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_b0_mse_last_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`PORT_LAST_INDEX-1:0] return_obs_b0_mse_last_index_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_b0_mse_pingpong_mon;

    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_b0_mrm_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_b0_arm_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`BUFFER_BANK_NUM-1:0] return_obs_b0_arm_bank_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`BUFFER_BANK_NUM-1:0][`VALID_BUFFER_BANK_WIDTH-1:0]
          return_obs_b0_row0_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`BUFFER_BANK_NUM-1:0][`VALID_BUFFER_BANK_WIDTH-1:0]
          return_obs_b0_row1_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`BUFFER_LIFE_TIME_WIDTH-1:0] return_obs_b0_counter0_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`BUFFER_LIFE_TIME_WIDTH-1:0] return_obs_b0_counter1_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`BUFFER_ROW_ADDR_WIDTH-1:0] return_obs_b0_arm_addr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`BUFFER_LIFE_TIME_WIDTH-1:0] return_obs_b0_life_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`BUFFER_BANK_NUM-1:0] return_obs_b0_arm_req_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_b0_arm_addr_update_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_b0_arm_data_valid_mon;

    generate
        for (genvar return_obs_b0_group = 0;
             return_obs_b0_group < `SLICE_GROUP_SIZE;
             return_obs_b0_group++) begin : RETURN_OBS_B0_GROUP_GEN
            for (genvar return_obs_b0_slice = 0;
                 return_obs_b0_slice < `SLICE_GROUP_NUM;
                 return_obs_b0_slice++) begin : RETURN_OBS_B0_SLICE_GEN
                assign return_obs_b0_ag_ob_cnt_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_WR_Buffer_AG.buf_ag_ob_cnt;
                assign return_obs_b0_ag_full_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_WR_Buffer_AG.buf_ag_ob_full;
                assign return_obs_b0_ag_empty_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_WR_Buffer_AG.buf_ag_ob_empty;
                assign return_obs_b0_ag_wr_en_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_WR_Buffer_AG.buf_ag_ob_wr_en;
                assign return_obs_b0_ag_bp_pre_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_WR_Buffer_AG.buf_ag_bp_pre;
                assign return_obs_b0_ag_rd_en_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_WR_Buffer_AG.buf_ag_ob_rd_en;
                assign return_obs_b0_mse_req_ready_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .buf2mse_wreq_ready[0];
                assign return_obs_b0_mse_req_valid_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .mse2buf_wreq_valid[0];
                assign return_obs_b0_mse_req_row_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .mse2buf_wreq_row_addr[0];
                assign return_obs_b0_mse_last_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_WR_Buffer_AG.mse2buf_last;
                assign return_obs_b0_mse_last_index_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_WR_Buffer_AG.mse2buf_last_index;
                assign return_obs_b0_mse_pingpong_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_WR_Buffer_AG.buf_ag_req_pingpong;

                assign return_obs_b0_mrm_ready_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[0]
                        .u_Buffer_Manager.u_Buffer.buf2mrm_req_ready;
                assign return_obs_b0_arm_ready_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[0]
                        .u_Buffer_Manager.u_Buffer.buf2arm_req_ready;
                assign return_obs_b0_arm_bank_ready_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[0]
                        .u_Buffer_Manager.u_Buffer.buf2arm_rreq_bank_ready;
                for (genvar return_obs_b0_bank = 0;
                     return_obs_b0_bank < `BUFFER_BANK_NUM;
                     return_obs_b0_bank++) begin : RETURN_OBS_B0_BANK_GEN
                    assign return_obs_b0_row0_valid_mon
                        [return_obs_b0_group][return_obs_b0_slice]
                        [return_obs_b0_bank] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_b0_group]
                            .u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_b0_slice]
                            .u_slice_wrapper.u_Slice.u_LSU
                            .u_Buffer_Manager_Cluster.BUFFER_MANAGER[0]
                            .u_Buffer_Manager.u_Buffer.valid_buf
                            [return_obs_b0_bank][0];
                    assign return_obs_b0_row1_valid_mon
                        [return_obs_b0_group][return_obs_b0_slice]
                        [return_obs_b0_bank] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_b0_group]
                            .u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_b0_slice]
                            .u_slice_wrapper.u_Slice.u_LSU
                            .u_Buffer_Manager_Cluster.BUFFER_MANAGER[0]
                            .u_Buffer_Manager.u_Buffer.valid_buf
                            [return_obs_b0_bank][1];
                end
                assign return_obs_b0_counter0_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[0]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .array_counter_0;
                assign return_obs_b0_counter1_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[0]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .array_counter_1;
                assign return_obs_b0_arm_addr_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[0]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .array_req_addr;
                assign return_obs_b0_life_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[0]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .array_life_cnt;
                assign return_obs_b0_arm_req_valid_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[0]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .arm2buf_req_valid;
                assign return_obs_b0_arm_addr_update_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[0]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .arm_addr_update;
                assign return_obs_b0_arm_data_valid_mon
                    [return_obs_b0_group][return_obs_b0_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_b0_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_b0_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[0]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .buf2arm_valid_bit;
            end
        end
    endgenerate

    longint unsigned return_obs_b0_ag_enqueue_count;
    longint unsigned return_obs_b0_ag_dequeue_count;
    longint unsigned return_obs_b0_mse_req_accept_count;
    longint unsigned return_obs_b0_arm_req_accept_count;
    logic [`BUFFER_ROW_ADDR_WIDTH-1:0] return_obs_b0_last_mse_row;
    logic [`BUFFER_ROW_ADDR_WIDTH-1:0] return_obs_b0_last_arm_addr;

    initial begin
        return_obs_b0_ag_enqueue_count = 0;
        return_obs_b0_ag_dequeue_count = 0;
        return_obs_b0_mse_req_accept_count = 0;
        return_obs_b0_arm_req_accept_count = 0;
        return_obs_b0_last_mse_row = 0;
        return_obs_b0_last_arm_addr = 0;
    end

    always @(posedge u_NDP_Top_new.clk_db or
             negedge u_NDP_Top_new.rst_n_db) begin
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_b0_ag_enqueue_count = 0;
            return_obs_b0_ag_dequeue_count = 0;
            return_obs_b0_mse_req_accept_count = 0;
            return_obs_b0_arm_req_accept_count = 0;
            return_obs_b0_last_mse_row = 0;
            return_obs_b0_last_arm_addr = 0;
        end
        else if (return_obs_enabled && return_obs_active) begin
            if (
                return_obs_b0_ag_wr_en_mon
                    [return_obs_group_id][return_obs_local_slice_id] &&
                return_obs_b0_ag_bp_pre_mon
                    [return_obs_group_id][return_obs_local_slice_id]
            )
                return_obs_b0_ag_enqueue_count++;
            if (
                return_obs_b0_ag_rd_en_mon
                    [return_obs_group_id][return_obs_local_slice_id] &&
                !return_obs_b0_ag_empty_mon
                    [return_obs_group_id][return_obs_local_slice_id]
            )
                return_obs_b0_ag_dequeue_count++;
            if (
                (|return_obs_b0_mse_req_valid_mon
                    [return_obs_group_id][return_obs_local_slice_id]) &&
                return_obs_b0_mse_req_ready_mon
                    [return_obs_group_id][return_obs_local_slice_id]
            ) begin
                return_obs_b0_mse_req_accept_count++;
                return_obs_b0_last_mse_row =
                    return_obs_b0_mse_req_row_mon
                        [return_obs_group_id][return_obs_local_slice_id];
            end
            if (
                (|return_obs_b0_arm_req_valid_mon
                    [return_obs_group_id][return_obs_local_slice_id]) &&
                return_obs_b0_arm_ready_mon
                    [return_obs_group_id][return_obs_local_slice_id]
            ) begin
                return_obs_b0_arm_req_accept_count++;
                return_obs_b0_last_arm_addr =
                    return_obs_b0_arm_addr_mon
                        [return_obs_group_id][return_obs_local_slice_id];
            end
        end
    end

    task automatic return_obs_write_buffer0_flow_state(
        input string event_name
    );
        begin
            if (return_obs_fd != 0) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | BUFFER0_FLOW_BOUNDARY_V1 | event=%s ag_enq=%0d ag_deq=%0d mse_req_accept=%0d arm_req_accept=%0d last_mse_row=%0d last_arm_addr=%0d ag_count=%0d ag_full=%0b ag_empty=%0b ag_wr_en=%0b ag_bp_pre=%0b ag_rd_en=%0b mse_ready=%0b mse_req_valid=0x%0h mse_row=%0d mse_last=%0b mse_last_index=%0d mse_pingpong=%0b mrm_ready=%0b arm_ready=%0b arm_bank_ready=0x%0h row0_valid=0x%0h row1_valid=0x%0h arm_counter0=%0d arm_counter1=%0d arm_addr=%0d arm_life=%0d arm_req_valid=0x%0h arm_addr_update=%0b arm_data_valid=%0b",
                    $time,
                    event_name,
                    return_obs_b0_ag_enqueue_count,
                    return_obs_b0_ag_dequeue_count,
                    return_obs_b0_mse_req_accept_count,
                    return_obs_b0_arm_req_accept_count,
                    return_obs_b0_last_mse_row,
                    return_obs_b0_last_arm_addr,
                    return_obs_b0_ag_ob_cnt_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_ag_full_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_ag_empty_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_ag_wr_en_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_ag_bp_pre_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_ag_rd_en_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_mse_req_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_mse_req_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_mse_req_row_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_mse_last_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_mse_last_index_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_mse_pingpong_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_mrm_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_arm_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_arm_bank_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_row0_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_row1_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_counter0_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_counter1_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_arm_addr_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_life_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_arm_req_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_arm_addr_update_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_b0_arm_data_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                );
                $fflush(return_obs_fd);
            end
        end
    endtask
'''


def replace_text_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".bin":
            continue
        payload = path.read_bytes()
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_NAME in text:
            path.write_text(
                text.replace(SOURCE_NAME, INSTALL_NAME),
                encoding="utf-8",
                newline="\n",
            )


def patch_observer(package: Path) -> str:
    observer = package / "tb_probe/native_return_observer.svh"
    text = observer.read_text(encoding="utf-8")
    old = '                return_obs_write_a_reuse_state("DIAG_DECISION");\n'
    new = old + (
        '                return_obs_write_buffer0_flow_state'
        '("DIAG_DECISION");\n'
    )
    if text.count(old) != 1 or "BUFFER0_FLOW_BOUNDARY_V1" in text:
        raise base.BuildError("v18 observer decision-call shape differs")
    observer.write_text(
        text.replace(old, new, 1) + FLOW_OBSERVER_BLOCK,
        encoding="utf-8",
        newline="\n",
    )
    return base.sha256(observer)


def readme() -> str:
    return f"""# node0004 v19 Buffer0 flow narrow diagnostic

Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.

The v18 formal return excluded producer/SA selector divergence and proved:
two MSE0 payload writes to Buffer0, one Buffer0-to-SA read, and one
ALU-to-outbuffer write. It then stalled with no Buffer0 valid bank bits.

This package preserves the frozen workload, configuration, mapping,
bitstream, execplan, SCA, inputs, and golden. It adds exactly one diagnostic
record, `BUFFER0_FLOW_BOUNDARY_V1`, at the canonical decision. Qualified
counters cover WR_Buffer_AG enqueue/dequeue, MSE-to-Buffer request acceptance,
and Buffer0 ARM request acceptance. State-only snapshots cover queue
occupancy, current row/tag, Buffer0 row0/row1 valid maps and ready, and
Array_Request_Manager address/lifetime counters.

This is not a functional fix and makes no E4/E5 claim.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `{INSTALL_NAME}_return.zip` and adjacent `.sha256`.
"""


def build_directory(output: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise base.BuildError("v18 source ZIP SHA differs")
    package = output / INSTALL_NAME
    if package.exists():
        raise base.BuildError(f"refusing to overwrite: {package}")
    shutil.copytree(SOURCE_ROOT, package)
    replace_text_identity(package)
    observer_sha = patch_observer(package)
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema"] = "resnet50-node0004-buffer0-flow-diagnostic-package-v19"
    manifest["install_name"] = INSTALL_NAME
    manifest["classification"] = "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
    manifest["status"] = "PACKAGE_READY_NOT_RUN"
    manifest["candidate_release"] = False
    manifest["observer_sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"]["sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"]["size_bytes"] = (
        package / "tb_probe/native_return_observer.svh"
    ).stat().st_size
    receipts = manifest["active_receipts"]
    receipts["plan_mutable_provenance_sha256"] = PLAN_MUTABLE_SHA256
    receipts["server_package_rule_sha256"] = SERVER_RULE_SHA256
    manifest["v18_return_adjudication"] = {
        "bound_return_sha256": BOUND_RETURN_SHA256,
        "status": "LONG_RUNNING_HANG_AT_BUFFER0_POST_FIRST_READ",
        "last_good": (
            "two MSE0 Buffer0 transfers, one Buffer0-to-SA read, one "
            "ALU-to-outbuffer write"
        ),
        "first_bad": (
            "no next Buffer0/1 read; Buffer0 rtag has no valid bank bits"
        ),
        "root_cause": "UNRESOLVED_BUFFER0_VALID_LIFETIME_SUBBOUNDARY",
    }
    manifest["buffer0_flow_diagnostic"] = {
        "schema": "node0004-buffer0-flow-boundary-v1",
        "record": "BUFFER0_FLOW_BOUNDARY_V1",
        "canonical_record_count": 1,
        "interval": (
            "MSE0_WR_BUFFER_AG_TO_BUFFER0_ROW_VALID_TO_ARM_NEXT_READ"
        ),
        "qualified_counters": [
            "WR_Buffer_AG enqueue handshake",
            "WR_Buffer_AG dequeue handshake",
            "MSE0-to-Buffer request handshake",
            "Buffer0 ARM request handshake",
        ],
        "state_only_snapshots": [
            "WR_Buffer_AG count/full/empty/current row/tag",
            "Buffer0 MRM/ARM ready and row0/row1 valid maps",
            "Array_Request_Manager address/lifetime counters",
        ],
        "result_interpretation": {
            "ag_no_next_enqueue": "loop/AG producer boundary",
            "ag_queued_mse_not_ready": "Buffer0 full/valid write boundary",
            "row1_valid_arm_not_ready": "Buffer0 ARM ready boundary",
            "row1_invalid_arm_addr1": "MSE0 row production/write boundary",
            "arm_counter_not_advanced": "Array_Request_Manager address/life boundary",
        },
        "not_functional_fix": True,
    }
    manifest["numeric_analysis_repeated"] = False
    manifest["node0004_workload_rebuilt"] = False
    manifest["configuration_rebuilt"] = False
    manifest["functional_rtl_modified"] = False
    manifest["server_rtl_entries"] = 0
    manifest["server_action"] = False
    manifest["superseded_v18_diagnostic"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_ZIP_SHA256,
        "status": "CONSUMED_RETURN_SUPERSEDED_BY_NARROWER_DIAGNOSTIC",
    }
    (package / "README.md").write_text(
        readme(), encoding="utf-8", newline="\n"
    )
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
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
            raise base.BuildError(f"refusing to overwrite: {target}")
    package = build_directory(output)
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v19-repeat-") as temp:
        repeat_root = Path(temp)
        repeat_package = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        repeated = base.sha256(repeat_zip) == digest
    if not repeated:
        raise base.BuildError("v19 deterministic rebuild differs")
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-buffer0-flow-diagnostic-package-validation-v19",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": repeated,
        "source_v18_sha256": SOURCE_ZIP_SHA256,
        "bound_v18_return_sha256": BOUND_RETURN_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_rtl_entries": 0,
        "server_action": False,
        "final_zip_rule_self_audit_pending": True,
    }
    base.write_json(validation, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
