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

import tools.build_node0004_v64_branch_catchup_successor_v65 as previous  # noqa: E402


SOURCE = "r5_n4_hw_v65_branchcatch_diag"
INSTALL = "r5_n4_hw_v66_epoch_owner_diag"
SOURCE_SHA = "b78e3c7257a34e23fab6cf046922a488c8e1f17356d6dfa6df11234e882a3816"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
ANALYSIS = ROOT / "outputs/conv_node0004_v65_return_analysis/report.json"
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v65_return_v66_successor/build"
base = previous.base


class BuildError(RuntimeError):
    pass


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"replacement count differs for {old!r}")
    return text.replace(old, new, 1)


EPOCH_BLOCK = r'''

    // v66 EPOCH_OWNER_ACTUAL_CONSUMER_BEGIN
    // Per-input address epoch ownership around the third descriptor terminal.
    // Only changing tuples are emitted; held levels are snapshots, not progress.
    bit return_obs_eo_enabled;
    integer return_obs_eo_limit;
    integer return_obs_eo_plusarg_status;
    integer return_obs_eo_records;
    logic [2:0] return_obs_eo_prev_valid;
    logic [2:0] return_obs_eo_prev_same;
    logic [2:0] return_obs_eo_prev_gotten;
    logic [2:0] return_obs_eo_prev_masked;
    logic [17:0] return_obs_eo_prev_tag0;
    logic [17:0] return_obs_eo_prev_tag1;
    logic [17:0] return_obs_eo_prev_tag2;
    logic [20:0] return_obs_eo_prev_lc6;
    logic [20:0] return_obs_eo_prev_lc8;
    logic [20:0] return_obs_eo_prev_lc17;
    longint unsigned return_obs_eo_prev_desc;
    longint unsigned return_obs_eo_prev_prepared;
    longint unsigned return_obs_eo_prev_buf;

    initial begin
        return_obs_eo_enabled = $test$plusargs("RETURN_OBS_EPOCH_OWNER");
        return_obs_eo_limit = 128;
        return_obs_eo_plusarg_status = $value$plusargs(
            "RETURN_OBS_EPOCH_OWNER_LIMIT=%d", return_obs_eo_limit
        );
        return_obs_eo_records = 0;
        return_obs_eo_prev_valid = 0;
        return_obs_eo_prev_same = 0;
        return_obs_eo_prev_gotten = 0;
        return_obs_eo_prev_masked = 0;
        return_obs_eo_prev_tag0 = 0;
        return_obs_eo_prev_tag1 = 0;
        return_obs_eo_prev_tag2 = 0;
        return_obs_eo_prev_lc6 = 0;
        return_obs_eo_prev_lc8 = 0;
        return_obs_eo_prev_lc17 = 0;
        return_obs_eo_prev_desc = 0;
        return_obs_eo_prev_prepared = 0;
        return_obs_eo_prev_buf = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_EPOCH_OWNER enabled=%0d limit_name=RETURN_OBS_EPOCH_OWNER_LIMIT limit=%0d schema=EPOCH_OWNER",
                return_obs_eo_enabled, return_obs_eo_limit
            );
            $fflush(return_obs_fd);
        end
    end

    task automatic return_obs_write_epoch_owner(input string event_name);
        if (return_obs_eo_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "%0t | EPOCH_OWNER_V1 | event=%s desc_terminal=%0d desc=%0d prepared=%0d delta=%0d buf_push=%0d buf_pop=%0d valid=%h same=%h gotten=%h masked=%h bp=%h match=%0d qempty=%0d mode0=%h mode1=%h mode2=%h keep0=%0d keep1=%0d keep2=%0d idx0=%h idx1=%h idx2=%h tag0=%h tag1=%h tag2=%h lc6=%h bp6=%h lc8=%h bp8=%h lc17=%h bp17=%h lc18=%h bp18=%h row_full=%0d col_full=%0d bufq_full=%0d prepared_count=%0d prepared_bp=%0d",
                $time, event_name,
                return_obs_wt_desc_terminal,
                return_obs_md_desc_hs,
                return_obs_md_prepared_wr,
                return_obs_md_prepared_wr - return_obs_md_desc_hs,
                return_obs_rb_buf_push, return_obs_rb_buf_pop,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_valid_bit_unmasked,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_same_bit_unmasked,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_gotten_bit,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_valid_bit_masked,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_queue_bp_pre,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_all_idx_matched,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_empty,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_idx_mode[0],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_idx_mode[1],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_idx_mode[2],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_idx_keep_last_index[0],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_idx_keep_last_index[1],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_idx_keep_last_index[2],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_queue_idx[0],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_queue_idx[1],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_queue_idx[2],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_queue_tag[0],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_queue_tag[1],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_queue_tag[2],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[6],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[6],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[8],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[8],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[17],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[17],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[18],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[18],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_ROW_LC[4].u_IGA_ROW_LC.u_IGA_ROW_LC_Counter.iga_row_lc_outbuf_full,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_COL_LC[4].u_IGA_COL_LC.u_IGA_COL_LC_Counter.iga_col_lc_outbuf_full,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_data_chl_prepared_data_cnt,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_chl_prepared_data_bp_pre
            );
            $fflush(return_obs_fd);
        end
    endtask

    always @(negedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit eo_changed;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_eo_records = 0;
            return_obs_eo_prev_valid = 0;
            return_obs_eo_prev_same = 0;
            return_obs_eo_prev_gotten = 0;
            return_obs_eo_prev_masked = 0;
            return_obs_eo_prev_tag0 = 0;
            return_obs_eo_prev_tag1 = 0;
            return_obs_eo_prev_tag2 = 0;
            return_obs_eo_prev_lc6 = 0;
            return_obs_eo_prev_lc8 = 0;
            return_obs_eo_prev_lc17 = 0;
            return_obs_eo_prev_desc = 0;
            return_obs_eo_prev_prepared = 0;
            return_obs_eo_prev_buf = 0;
        end else if (return_obs_eo_enabled && return_obs_active) begin
            eo_changed =
                return_obs_eo_prev_valid != u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_valid_bit_unmasked ||
                return_obs_eo_prev_same != u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_same_bit_unmasked ||
                return_obs_eo_prev_gotten != u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_gotten_bit ||
                return_obs_eo_prev_masked != u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_valid_bit_masked ||
                return_obs_eo_prev_tag0 != u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_queue_tag[0] ||
                return_obs_eo_prev_tag1 != u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_queue_tag[1] ||
                return_obs_eo_prev_tag2 != u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_queue_tag[2] ||
                return_obs_eo_prev_lc6 != u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[6] ||
                return_obs_eo_prev_lc8 != u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[8] ||
                return_obs_eo_prev_lc17 != u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[17] ||
                return_obs_eo_prev_desc != return_obs_md_desc_hs ||
                return_obs_eo_prev_prepared != return_obs_md_prepared_wr ||
                return_obs_eo_prev_buf != return_obs_rb_buf_push;
            if (return_obs_wt_desc_terminal >= 2 && eo_changed &&
                return_obs_eo_records < return_obs_eo_limit) begin
                return_obs_eo_records++;
                return_obs_write_epoch_owner("QUALIFIED_CHANGE");
            end
            return_obs_eo_prev_valid = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_valid_bit_unmasked;
            return_obs_eo_prev_same = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_same_bit_unmasked;
            return_obs_eo_prev_gotten = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_gotten_bit;
            return_obs_eo_prev_masked = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_valid_bit_masked;
            return_obs_eo_prev_tag0 = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_queue_tag[0];
            return_obs_eo_prev_tag1 = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_queue_tag[1];
            return_obs_eo_prev_tag2 = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_queue_tag[2];
            return_obs_eo_prev_lc6 = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[6];
            return_obs_eo_prev_lc8 = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[8];
            return_obs_eo_prev_lc17 = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[17];
            return_obs_eo_prev_desc = return_obs_md_desc_hs;
            return_obs_eo_prev_prepared = return_obs_md_prepared_wr;
            return_obs_eo_prev_buf = return_obs_rb_buf_push;
        end
    end
    // v66 EPOCH_OWNER_ACTUAL_CONSUMER_END
'''


def configure() -> None:
    previous.SOURCE = SOURCE
    previous.INSTALL = INSTALL
    previous.SOURCE_SHA = SOURCE_SHA
    previous.SOURCE_ZIP = SOURCE_ZIP
    previous.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    previous.configure_base()


def build_directory(output: Path) -> Path:
    configure()
    with tempfile.TemporaryDirectory(prefix="node0004-v66-source-") as temp:
        source = base.extract_source(Path(temp))
        package = output / INSTALL
        if package.exists():
            raise BuildError(f"refusing to overwrite {package}")
        shutil.copytree(source, package)
    base.replace_identity(package)

    observer_path = package / "tb_probe/native_return_observer.svh"
    observer = observer_path.read_text(encoding="utf-8")
    if "RETURN_OBS_EPOCH_OWNER" in observer:
        raise BuildError("epoch owner feature already present")
    observer = replace_once(
        observer,
        '                return_obs_write_branch_catchup("DIAG_DECISION");\n',
        '                return_obs_write_branch_catchup("DIAG_DECISION");\n'
        '                return_obs_write_epoch_owner("DIAG_DECISION");\n',
    )
    observer += EPOCH_BLOCK
    observer_path.write_text(observer, encoding="utf-8", newline="\n")

    runner_path = package / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    token = "+RETURN_OBS_BRANCH_CATCHUP +RETURN_OBS_BRANCH_CATCHUP_LIMIT=64"
    if runner.count(token) != 2:
        raise BuildError("branch feature argv count differs")
    runner = runner.replace(
        token,
        token + " +RETURN_OBS_EPOCH_OWNER +RETURN_OBS_EPOCH_OWNER_LIMIT=128",
    )
    runner_path.write_text(runner, encoding="utf-8", newline="\n")

    runtime_path = package / "package_tools/node0004_hang_localization_runtime.py"
    runtime = runtime_path.read_text(encoding="utf-8")
    needle = '''    {
        "feature": "RETURN_OBS_BRANCH_CATCHUP",
        "enable": "+RETURN_OBS_BRANCH_CATCHUP",
        "limits": ("+RETURN_OBS_BRANCH_CATCHUP_LIMIT=64",),
        "marker_tokens": (
            "feature=RETURN_OBS_BRANCH_CATCHUP", "enabled=1", "limit=64",
        ),
    },
'''
    addition = needle + '''    {
        "feature": "RETURN_OBS_EPOCH_OWNER",
        "enable": "+RETURN_OBS_EPOCH_OWNER",
        "limits": ("+RETURN_OBS_EPOCH_OWNER_LIMIT=128",),
        "marker_tokens": (
            "feature=RETURN_OBS_EPOCH_OWNER", "enabled=1", "limit=128",
        ),
    },
'''
    runtime = replace_once(runtime, needle, addition)
    runtime_path.write_text(runtime, encoding="utf-8", newline="\n")

    old_manifest = json.loads(
        (package / "package_manifest.json").read_text(encoding="utf-8")
    )
    old_observer_sha = old_manifest["observer_sha256"]
    new_observer_sha = base.sha256(observer_path)
    manifest = base.replace_hash(old_manifest, old_observer_sha, new_observer_sha)
    manifest.update(
        {
            "install_name": INSTALL,
            "source_package_sha256": SOURCE_SHA,
            "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "observer_sha256": new_observer_sha,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "configuration_rebuilt": False,
            "configuration_rebuilt_in_this_successor": False,
            "mapping_rebuilt": False,
            "bitstream_rebuilt": False,
            "execplan_rebuilt": False,
            "sca_semantics_rebuilt": False,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
        }
    )
    manifest.setdefault("diagnostic_features", {})["RETURN_OBS_EPOCH_OWNER"] = {
        "runtime_enable_parameter": "+RETURN_OBS_EPOCH_OWNER",
        "limit_parameter": "+RETURN_OBS_EPOCH_OWNER_LIMIT=128",
        "time_zero_marker": "DIAGNOSTIC_FEATURE_ENABLE_V1",
        "edge_schema": "EPOCH_OWNER_V1",
        "boundary_schema": "EPOCH_OWNER_V1",
        "clock": "u_NDP_Top_new.clk_db",
        "reset": "u_NDP_Top_new.rst_n_db",
        "progress_semantics": "qualified tuple changes only",
    }
    base.write_json(
        package / "provenance/v65_to_v66_epoch_owner.json",
        {
            "schema": "node0004-v65-to-v66-epoch-owner-v1",
            "source_v65_sha256": SOURCE_SHA,
            "v65_return_sha256": (
                "55aa22054535bfe032b62639c36f67cf058b09e84752fe3eeef13a0d186dacd3"
            ),
            "v65_return_analysis": {
                "path": ANALYSIS.relative_to(ROOT).as_posix(),
                "sha256": base.sha256(ANALYSIS),
                "last_proven_good": (
                    "third descriptor terminal reaches desc18/prepared18/delta0"
                ),
                "first_divergence": (
                    "address branch lacks a complete new three-input tuple "
                    "while Buffer accepts two unmatched groups"
                ),
            },
            "changed_surface": [
                "fresh identity",
                "per-input address epoch ownership observer",
                "runtime feature binding",
                "manifest and return identity projection",
            ],
            "candidate_observation_matrix": {
                "shared_source_partial_capture": (
                    "LC6/8/17 data plus complete bp vectors correlated to "
                    "Memory_AG per-input tags"
                ),
                "lc_terminal_or_keep_stop": (
                    "per-input tag/index and physical LC tuple changes"
                ),
                "memory_ag_same_gotten_suppression": (
                    "per-input raw/same/gotten/masked/mode/keep chronology"
                ),
                "buffer_branch_early_epoch_accept": (
                    "Buffer push/pop, descriptor, prepared and epoch tuple "
                    "chronology in the same clocked record"
                ),
            },
            "frozen": [
                "numeric/W3/qparams/tail/workload/config/golden",
                "mapping/bitstream/execplan/SCA semantics",
                "timeout/backpressure",
                "functional RTL/ISA/hardware/active ndp-sim",
            ],
        },
    )
    readme = package / "README.md"
    readme.write_text(
        "# node0004 v66 per-input epoch-owner diagnostic\n\n"
        "This package freezes v65 computation and adds one bounded, qualified "
        "ledger correlating each MSE4 address input with physical LC6/8/17, "
        "same/gotten state, and the Buffer data epoch.\n\n"
        f"Run: `bash {INSTALL}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n",
        encoding="utf-8",
        newline="\n",
    )
    base.refresh_receipts(manifest)
    manifest["files"] = base.package_records(package)
    base.write_json(package / "package_manifest.json", manifest)
    manifest["files"] = base.package_records(package)
    base.write_json(package / "package_manifest.json", manifest)
    base.update_path_budget(package)
    manifest = json.loads(
        (package / "package_manifest.json").read_text(encoding="utf-8")
    )
    manifest["files"] = base.package_records(package)
    base.write_json(package / "package_manifest.json", manifest)
    return package


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()
    out = args.output_root.resolve()
    out.mkdir(parents=True, exist_ok=True)
    for item in (out / INSTALL, out / f"{INSTALL}.zip"):
        if item.exists():
            raise BuildError(f"refusing to overwrite {item}")
    package = build_directory(out)
    archive = out / f"{INSTALL}.zip"
    base.deterministic_zip(package, archive)
    digest = base.sha256(archive)
    with tempfile.TemporaryDirectory(prefix="node0004-v66-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("deterministic rebuild differs")
    sidecar = out / f"{INSTALL}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {archive.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "node0004-v65-to-v66-epoch-owner-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
        "zip": str(archive),
        "zip_bytes": archive.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v65_sha256": SOURCE_SHA,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    base.write_json(out / f"{INSTALL}.build.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
