from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v67_pe7_pair_successor_v68 as previous  # noqa: E402

SOURCE = "r5_n4_hw_v68_pe7_pair_diag"
INSTALL = "r5_n4_hw_v69_branch_drain_diag"
SOURCE_SHA = "372c6135f064dfb5847bedfea3741b8724113eb8e3b0c7f644e87f4fa877fdee"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v68_return_analysis/report.json"
MAPPING_REVIEW = ROOT / "artifacts/operator_config_validation/r5-node0004-pe1-keep-last-index-fix-c0-v62/mapping/conv/op_w0/mapping_review.json"
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v68_return_v69_successor/build"
base = previous.base


class BuildError(RuntimeError):
    pass


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"replacement count differs: {old[:100]!r} count={text.count(old)}")
    return text.replace(old, new, 1)


def configure() -> None:
    previous.SOURCE = SOURCE
    previous.INSTALL = INSTALL
    previous.SOURCE_SHA = SOURCE_SHA
    previous.SOURCE_ZIP = SOURCE_ZIP
    previous.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    previous.configure()


BRANCH_DRAIN_BLOCK = r'''

    // v69 BRANCH_DRAIN_ACTUAL_CONSUMER_BEGIN
    // Qualified causal chain for the LC18 fanout cycle.  Levels are state only.
    bit return_obs_bd_enabled;
    integer return_obs_bd_limit;
    integer return_obs_bd_plusarg_status;
    integer return_obs_bd_records;
    longint unsigned return_obs_bd_lc18_accept;
    longint unsigned return_obs_bd_buf_push;
    longint unsigned return_obs_bd_buf_pop;
    longint unsigned return_obs_bd_rd_write;
    longint unsigned return_obs_bd_rd_read;
    longint unsigned return_obs_bd_buf_req;
    longint unsigned return_obs_bd_buf_return;
    longint unsigned return_obs_bd_prepared_write;
    longint unsigned return_obs_bd_mem_match;
    longint unsigned return_obs_bd_memq_push;
    longint unsigned return_obs_bd_memq_pop;
    longint unsigned return_obs_bd_desc;
    longint unsigned return_obs_bd_request;
    longint unsigned return_obs_bd_prepared_read;
    longint unsigned return_obs_bd_wdata;

    initial begin
        return_obs_bd_enabled = $test$plusargs("RETURN_OBS_BRANCH_DRAIN");
        return_obs_bd_limit = 128;
        return_obs_bd_plusarg_status = $value$plusargs(
            "RETURN_OBS_BRANCH_DRAIN_LIMIT=%d", return_obs_bd_limit
        );
        return_obs_bd_records = 0;
        return_obs_bd_lc18_accept = 0;
        return_obs_bd_buf_push = 0;
        return_obs_bd_buf_pop = 0;
        return_obs_bd_rd_write = 0;
        return_obs_bd_rd_read = 0;
        return_obs_bd_buf_req = 0;
        return_obs_bd_buf_return = 0;
        return_obs_bd_prepared_write = 0;
        return_obs_bd_mem_match = 0;
        return_obs_bd_memq_push = 0;
        return_obs_bd_memq_pop = 0;
        return_obs_bd_desc = 0;
        return_obs_bd_request = 0;
        return_obs_bd_prepared_read = 0;
        return_obs_bd_wdata = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_BRANCH_DRAIN enabled=%0d limit_name=RETURN_OBS_BRANCH_DRAIN_LIMIT limit=%0d schema=BRANCH_DRAIN",
                return_obs_bd_enabled, return_obs_bd_limit);
            $fflush(return_obs_fd);
        end
    end

    task automatic return_obs_write_branch_drain(input string event_name);
        if (return_obs_bd_enabled && return_obs_fd != 0) begin
            $fdisplay(return_obs_fd,
                "%0t | BRANCH_DRAIN_V1 | event=%s lc18=%0d buf_push=%0d buf_pop=%0d rd_wr=%0d rd_rd=%0d buf_req=%0d buf_ret=%0d prep_wr=%0d mem_match=%0d memq_push=%0d memq_pop=%0d desc=%0d req=%0d prep_rd=%0d wdata=%0d lc18_port=%h lc18_bp=%h bufq_full=%0d bufq_empty=%0d rd_count=%0d rd_full=%0d rd_empty=%0d rreq_valid=%h rreq_ready=%0d rvalid=%0d wr_ready=%0d prep_count=%0d prep_bp=%0d prep_valid=%0d hold=%0d mem_valid=%h mem_masked=%h mem_gotten=%h mem_match_state=%0d memq_full=%0d memq_empty=%0d mem_tag_valid=%0d desc_valid=%0d desc_ready=%0d reqq_full=%0d reqq_empty=%0d req_v=%h req_r=%h prep_rd_state=%0d ob_wr=%h wdata_v=%h wdata_r=%h",
                $time, event_name,
                return_obs_bd_lc18_accept, return_obs_bd_buf_push,
                return_obs_bd_buf_pop, return_obs_bd_rd_write,
                return_obs_bd_rd_read, return_obs_bd_buf_req,
                return_obs_bd_buf_return, return_obs_bd_prepared_write,
                return_obs_bd_mem_match, return_obs_bd_memq_push,
                return_obs_bd_memq_pop, return_obs_bd_desc,
                return_obs_bd_request, return_obs_bd_prepared_read,
                return_obs_bd_wdata,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[18],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[18],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_empty,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_RD_Buffer_AG.buf_ag_ob_cnt,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_RD_Buffer_AG.buf_ag_ob_full,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_RD_Buffer_AG.buf_ag_ob_empty,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse2buf_rreq_valid,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.buf2mse_rreq_ready,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.buf2mse_rvalid,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.wr_data_chl_ready,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_data_chl_prepared_data_cnt,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_chl_prepared_data_bp_pre,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_data_chl_prepared_data_vld,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_data_chl_hold_data_vld,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_valid_bit_unmasked,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_valid_bit_masked,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_gotten_bit,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_all_idx_matched,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_full,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_empty,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse_mem_ag_tag_valid,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.wr_data_chl_req_valid,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.wr_data_chl_req_ready,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_chl_queue_full,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_chl_queue_empty,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse2mem_request_valid,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mem2mse_request_ready,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_data_chl_prepared_data_rd_hs,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_chl_ob_wr_hs,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse2mem_wdata_valid,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mem2mse_wdata_ready
            );
            $fflush(return_obs_fd);
        end
    endtask

    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit bd_lc18, bd_buf_push, bd_buf_pop, bd_rd_write, bd_rd_read;
        bit bd_buf_req, bd_buf_return, bd_prep_wr, bd_mem_match;
        bit bd_memq_push, bd_memq_pop, bd_desc, bd_request, bd_prep_rd, bd_wdata;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_bd_records = 0;
            return_obs_bd_lc18_accept = 0; return_obs_bd_buf_push = 0;
            return_obs_bd_buf_pop = 0; return_obs_bd_rd_write = 0;
            return_obs_bd_rd_read = 0; return_obs_bd_buf_req = 0;
            return_obs_bd_buf_return = 0; return_obs_bd_prepared_write = 0;
            return_obs_bd_mem_match = 0; return_obs_bd_memq_push = 0;
            return_obs_bd_memq_pop = 0; return_obs_bd_desc = 0;
            return_obs_bd_request = 0; return_obs_bd_prepared_read = 0;
            return_obs_bd_wdata = 0;
        end else if (return_obs_bd_enabled && return_obs_active) begin
            bd_lc18 = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[18][22] && &u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[18];
            bd_buf_push = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_wr_en && !u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full;
            bd_buf_pop = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_rd_en && !u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_empty;
            bd_rd_write = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_RD_Buffer_AG.buf_ag_ob_wr_en && !u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_RD_Buffer_AG.buf_ag_ob_full;
            bd_rd_read = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_RD_Buffer_AG.buf_ag_ob_rd_en && !u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_RD_Buffer_AG.buf_ag_ob_empty;
            bd_buf_req = (|u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse2buf_rreq_valid) && u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.buf2mse_rreq_ready;
            bd_buf_return = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.buf2mse_rvalid && u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.wr_data_chl_ready;
            bd_prep_wr = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_data_chl_prepared_data_wr_hs;
            bd_mem_match = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_all_idx_matched;
            bd_memq_push = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_wr_en && !u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_full;
            bd_memq_pop = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_rd_en && !u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_empty;
            bd_desc = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.wr_data_chl_req_valid && u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.wr_data_chl_req_ready;
            bd_request = |(u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse2mem_request_valid & u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mem2mse_request_ready);
            bd_prep_rd = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_data_chl_prepared_data_rd_hs;
            bd_wdata = |(u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse2mem_wdata_valid & u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mem2mse_wdata_ready);
            if (bd_lc18) return_obs_bd_lc18_accept++;
            if (bd_buf_push) return_obs_bd_buf_push++;
            if (bd_buf_pop) return_obs_bd_buf_pop++;
            if (bd_rd_write) return_obs_bd_rd_write++;
            if (bd_rd_read) return_obs_bd_rd_read++;
            if (bd_buf_req) return_obs_bd_buf_req++;
            if (bd_buf_return) return_obs_bd_buf_return++;
            if (bd_prep_wr) return_obs_bd_prepared_write++;
            if (bd_mem_match) return_obs_bd_mem_match++;
            if (bd_memq_push) return_obs_bd_memq_push++;
            if (bd_memq_pop) return_obs_bd_memq_pop++;
            if (bd_desc) return_obs_bd_desc++;
            if (bd_request) return_obs_bd_request++;
            if (bd_prep_rd) return_obs_bd_prepared_read++;
            if (bd_wdata) return_obs_bd_wdata++;
            if ((bd_lc18 || bd_buf_push || bd_buf_pop || bd_rd_write || bd_rd_read || bd_buf_req || bd_buf_return || bd_prep_wr || bd_mem_match || bd_memq_push || bd_memq_pop || bd_desc || bd_request || bd_prep_rd || bd_wdata) && return_obs_bd_records < return_obs_bd_limit) begin
                return_obs_bd_records++;
                return_obs_write_branch_drain("QUALIFIED_EDGE");
            end
        end
    end
    // v69 BRANCH_DRAIN_ACTUAL_CONSUMER_END
'''


def add_runtime_feature(runtime: str) -> str:
    anchor = '''    {
        "feature": "RETURN_OBS_PE7_PAIR",
        "enable": "+RETURN_OBS_PE7_PAIR",
        "limits": ("+RETURN_OBS_PE7_PAIR_LIMIT=128",),
        "marker_tokens": (
            "feature=RETURN_OBS_PE7_PAIR", "enabled=1", "limit=128",
        ),
    },
)'''
    replacement = anchor[:-2] + '''    {
        "feature": "RETURN_OBS_BRANCH_DRAIN",
        "enable": "+RETURN_OBS_BRANCH_DRAIN",
        "limits": ("+RETURN_OBS_BRANCH_DRAIN_LIMIT=128",),
        "marker_tokens": (
            "feature=RETURN_OBS_BRANCH_DRAIN", "enabled=1", "limit=128",
        ),
    },
)'''
    return once(runtime, anchor, replacement)


def build_directory(output: Path) -> Path:
    configure()
    with tempfile.TemporaryDirectory(prefix="node0004-v69-source-") as td:
        source = base.extract_source(Path(td))
        package = output / INSTALL
        if package.exists():
            raise BuildError(f"refusing to overwrite {package}")
        shutil.copytree(source, package)
    base.replace_identity(package)

    op = package / "tb_probe/native_return_observer.svh"
    observer = op.read_text(encoding="utf-8")
    observer = once(observer, '                return_obs_write_pe7_pair("DIAG_DECISION");',
                    '                return_obs_write_pe7_pair("DIAG_DECISION");\n                return_obs_write_branch_drain("DIAG_DECISION");')
    observer = once(observer, '                return_obs_write_rowlc4_bufag_state(event_name);',
                    '                return_obs_write_rowlc4_bufag_state(event_name);\n                return_obs_write_branch_drain(event_name);')
    observer = observer.rstrip() + BRANCH_DRAIN_BLOCK + "\n"
    op.write_text(observer, encoding="utf-8", newline="\n")

    rp = package / "PREPARE_AND_RUN.sh"
    runner = rp.read_text(encoding="utf-8")
    anchor = " +RETURN_OBS_PE7_PAIR +RETURN_OBS_PE7_PAIR_LIMIT=128"
    if runner.count(anchor) != 2:
        raise BuildError("v68 PE7 runner binding count differs")
    runner = runner.replace(anchor, anchor + " +RETURN_OBS_BRANCH_DRAIN +RETURN_OBS_BRANCH_DRAIN_LIMIT=128")
    rp.write_text(runner, encoding="utf-8", newline="\n")

    runtime_path = package / "package_tools/node0004_hang_localization_runtime.py"
    runtime_path.write_text(add_runtime_feature(runtime_path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")

    manifest_path = package / "package_manifest.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_sha, new_sha = old["observer_sha256"], base.sha256(op)
    manifest = base.replace_hash(old, old_sha, new_sha)
    manifest.setdefault("diagnostic_features", {})["RETURN_OBS_BRANCH_DRAIN"] = {
        "runtime_enable_parameter": "+RETURN_OBS_BRANCH_DRAIN",
        "limit_parameter": "+RETURN_OBS_BRANCH_DRAIN_LIMIT=128",
        "edge_schema": "BRANCH_DRAIN_V1",
        "boundary_schema": "BRANCH_DRAIN_V1",
        "owner_clock": "u_NDP_Top_new.clk_db",
        "owner_reset": "u_NDP_Top_new.rst_n_db",
        "causal_scope": [
            "physical LC18 destination bit10 versus PE7 input2",
            "ROW_LC4/Buffer_AG/RD_Buffer_AG request-return",
            "WR prepared-data and Memory_AG descriptor join",
            "memory request and write-data output handshakes",
        ],
        "candidate_matrix": {
            "address_request_queue_empty": "mem match/queue/desc/request counters and state",
            "prepared_data_cannot_join_request": "prepared count/valid/read and WR queue state",
            "memory_channel_backpressure": "request and wdata valid-ready vectors",
            "buffer_read_return_not_accepted": "buffer request/return and WR ready/hold",
        },
    }
    manifest.update({
        "install_name": INSTALL, "source_package_sha256": SOURCE_SHA,
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "observer_sha256": new_sha, "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False, "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False, "configuration_rebuilt": False,
        "configuration_rebuilt_in_this_successor": False, "mapping_rebuilt": False,
        "bitstream_rebuilt": False, "execplan_rebuilt": False,
        "sca_semantics_rebuilt": False, "functional_rtl_modified": False,
        "server_action": False,
    })
    base.write_json(package / "provenance/v68_to_v69_branch_drain.json", {
        "schema": "node0004-v68-to-v69-branch-drain-v1",
        "source_v68_sha256": SOURCE_SHA,
        "v68_return_sha256": "2a39ff084c605e06343fba9b6193d1e5666640f519266a5aa2d1f332b807d97e",
        "analysis_sha256": base.sha256(ANALYSIS),
        "mapping_review_sha256": base.sha256(MAPPING_REVIEW),
        "last_proven_good": "SECOND_EPOCH_LC18_Q0_REACHES_PE7_AND_COMPLETES_NINTH_MATCH_WRITE_READ_OUTPUT",
        "first_divergence": "LC18_NEXT_TOKEN_IS_BLOCKED_ONLY_BY_ROW_LC4_BIT10_WHILE_PE7_INPUT2_REMAINS_READY",
        "changed_surface": ["fresh identity", "BRANCH_DRAIN qualified observer", "runner/runtime feature binding"],
        "frozen": ["numeric/W3/qparams/tail/workload/config/golden", "timeout/backpressure",
                   "functional RTL/ISA/hardware/active ndp-sim"],
    })
    base.refresh_receipts(manifest)
    manifest["files"] = base.package_records(package); base.write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package); base.write_json(manifest_path, manifest)
    base.update_path_budget(package)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.package_records(package); base.write_json(manifest_path, manifest)
    return package


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    a = ap.parse_args()
    out = a.output_root.resolve(); out.mkdir(parents=True, exist_ok=True)
    package = build_directory(out)
    archive = out / f"{INSTALL}.zip"; base.deterministic_zip(package, archive)
    digest = base.sha256(archive)
    with tempfile.TemporaryDirectory(prefix="node0004-v69-repeat-") as td:
        repeat = build_directory(Path(td)); rz = Path(td) / f"{INSTALL}.zip"
        base.deterministic_zip(repeat, rz); deterministic = base.sha256(rz) == digest
    if not deterministic:
        raise BuildError("deterministic rebuild differs")
    sidecar = out / f"{INSTALL}.zip.sha256"
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "node0004-v68-to-v69-branch-drain-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
        "zip": str(archive), "zip_bytes": archive.stat().st_size, "zip_sha256": digest,
        "sidecar": str(sidecar), "deterministic_rebuild_equal": deterministic,
        "source_v68_sha256": SOURCE_SHA, "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "numeric_analysis_repeated": False, "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False, "functional_rtl_modified": False, "server_action": False,
    }
    base.write_json(out / f"{INSTALL}.build.json", report)
    print(json.dumps(report, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
