from __future__ import annotations

import argparse
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
from tools import build_gap_node0071_col_ag_mrm_lane_v31_package as base


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v32_col_ag_mrm_lane_rulebind"
INSTALL_NAME = "r5_n71_gap_v33_buffer_ag_idx_pair_diag"
TEST_ID = "r5-gap-node0071-v33-buffer-ag-index-pairing-diagnostic"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = "c974125f0b3e913f733ad4c2341b922ea3551a62144b1062c6dd433d82e369a1"
TRIGGER_RETURN_SHA256 = "6bf8f931104739d3f658959958d378fa97081ce7457b0098acff3b1ac3a07a6b"
TRIGGER_ANALYSIS = (
    ROOT / "artifacts/operator_config_validation/r5-gap-node0071-v32-return-analysis/report.json"
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


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"marker differs: {label} ({text.count(old)})")
    return text.replace(old, new, 1)


def configure_source() -> None:
    base.SOURCE_NAME = SOURCE_NAME
    base.INSTALL_NAME = INSTALL_NAME
    base.TEST_ID = TEST_ID
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256
    base.TRIGGER_RETURN_SHA256 = TRIGGER_RETURN_SHA256
    base.TRIGGER_ANALYSIS = TRIGGER_ANALYSIS
    root = base.root_builder()
    root.SOURCE_NAME = SOURCE_NAME
    root.INSTALL_NAME = INSTALL_NAME
    root.SOURCE_ZIP = SOURCE_ZIP
    root.SOURCE_SHA256 = SOURCE_SHA256


DECLARATIONS = r'''    // v33: MSE0 Buffer_AG_Idx_Queue input/match/FIFO diagnostic.
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SE_BUF_ROW_INPORT_IDX_WIDTH-1:0] return_obs_bq_row_idx_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SE_BUF_COL_INPORT_IDX_WIDTH-1:0] return_obs_bq_col_idx_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SE_BUF_INPORT_TAG_WIDTH-1:0] return_obs_bq_row_tag_mon,
                                           return_obs_bq_col_tag_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
          return_obs_bq_bp_pre_mon,
          return_obs_bq_valid_raw_mon,
          return_obs_bq_same_raw_mon,
          return_obs_bq_gotten_mon,
          return_obs_bq_same_keep_mon,
          return_obs_bq_same_masked_mon,
          return_obs_bq_same_gotten_mon,
          return_obs_bq_valid_masked_mon,
          return_obs_bq_bp_keep_mon,
          return_obs_bq_bp_mask_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_bq_all_matched_mon,
          return_obs_bq_mse_enable_mon,
          return_obs_bq_wr_en_mon,
          return_obs_bq_full_mon,
          return_obs_bq_rd_en_mon,
          return_obs_bq_empty_mon,
          return_obs_bq_out_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][4:0]
          return_obs_bq_count_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_BUF_AG_INPORT_TAG_WIDTH-1:0] return_obs_bq_out_tag_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_BUF_AG_INPORT_IDX_WIDTH-1:0] return_obs_bq_out_idx_mon;

    generate
        for (genvar return_obs_bq_group = 0;
             return_obs_bq_group < `SLICE_GROUP_SIZE;
             return_obs_bq_group++) begin : RETURN_OBS_BQ_GROUP_GEN
            for (genvar return_obs_bq_slice = 0;
                 return_obs_bq_slice < `SLICE_GROUP_NUM;
                 return_obs_bq_slice++) begin : RETURN_OBS_BQ_SLICE_GEN
                `define RETURN_OBS_BQ_XMR u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_bq_group].u_slice_with_datahub_mc_group.slice_group_gen[return_obs_bq_slice].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine.u_Buffer_AG_Idx_Queue
                assign return_obs_bq_row_idx_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.mse_buf_queue_row_idx;
                assign return_obs_bq_col_idx_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.mse_buf_queue_col_idx;
                assign return_obs_bq_row_tag_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.mse_buf_queue_row_tag;
                assign return_obs_bq_col_tag_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.mse_buf_queue_col_tag;
                assign return_obs_bq_bp_pre_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.mse_buf_queue_bp_pre;
                assign return_obs_bq_valid_raw_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.buf_idx_valid_bit_unmasked;
                assign return_obs_bq_same_raw_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.buf_idx_same_bit_unmasked;
                assign return_obs_bq_gotten_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.buf_idx_gotten_bit;
                assign return_obs_bq_same_keep_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.buf_idx_same_bit_keep_mask;
                assign return_obs_bq_same_masked_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.buf_idx_same_bit_masked;
                assign return_obs_bq_same_gotten_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.buf_idx_same_gotten_mask;
                assign return_obs_bq_valid_masked_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.buf_idx_valid_bit_masked;
                assign return_obs_bq_bp_keep_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.buf_idx_bp_pre_keep_mask;
                assign return_obs_bq_bp_mask_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.buf_idx_bp_pre_mask;
                assign return_obs_bq_all_matched_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.buf_all_idx_matched;
                assign return_obs_bq_mse_enable_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.mse_enable;
                assign return_obs_bq_wr_en_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.buf_ag_idx_queue_wr_en;
                assign return_obs_bq_full_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.buf_ag_idx_queue_full;
                assign return_obs_bq_rd_en_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.buf_ag_idx_queue_rd_en;
                assign return_obs_bq_empty_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.buf_ag_idx_queue_empty;
                assign return_obs_bq_count_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.u_buf_ag_idx_queue.fifo_counter;
                assign return_obs_bq_out_valid_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.mse_buf_ag_tag_valid;
                assign return_obs_bq_out_tag_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.mse_buf_ag_tag;
                assign return_obs_bq_out_idx_mon[return_obs_bq_group][return_obs_bq_slice] = `RETURN_OBS_BQ_XMR.mse_buf_ag_idx;
                `undef RETURN_OBS_BQ_XMR
            end
        end
    endgenerate

    bit return_obs_bq_enabled;
    int return_obs_bq_limit;
    int return_obs_bq_emit_count;
    longint unsigned return_obs_bq_col_accept_count;
    longint unsigned return_obs_bq_row_accept_count;
    longint unsigned return_obs_bq_enqueue_count;
    longint unsigned return_obs_bq_dequeue_count;
    longint unsigned return_obs_bq_first_col_accept;
    longint unsigned return_obs_bq_last_col_accept;
    longint unsigned return_obs_bq_last_row_accept;
    longint unsigned return_obs_bq_last_enqueue;
    longint unsigned return_obs_bq_last_dequeue;

    task automatic return_obs_bq_reset;
        begin
            return_obs_bq_emit_count = 0;
            return_obs_bq_col_accept_count = 0;
            return_obs_bq_row_accept_count = 0;
            return_obs_bq_enqueue_count = 0;
            return_obs_bq_dequeue_count = 0;
            return_obs_bq_first_col_accept = 0;
            return_obs_bq_last_col_accept = 0;
            return_obs_bq_last_row_accept = 0;
            return_obs_bq_last_enqueue = 0;
            return_obs_bq_last_dequeue = 0;
        end
    endtask

'''


SUMMARY = r'''                    if (return_obs_bq_enabled) begin
                        $fdisplay(
                            return_obs_fd,
                            "%0t | BUFFER_AG_IDX_QUEUE_COUNTS_V1 | event=%s col_accept=%0d row_accept=%0d enqueue=%0d dequeue=%0d records=%0d limit=%0d",
                            $time, event_name,
                            return_obs_bq_col_accept_count,
                            return_obs_bq_row_accept_count,
                            return_obs_bq_enqueue_count,
                            return_obs_bq_dequeue_count,
                            return_obs_bq_emit_count,
                            return_obs_bq_limit
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | BUFFER_AG_IDX_QUEUE_STATE_V1 | event=%s col_idx=0x%0h col_tag=0x%0h row_idx=0x%0h row_tag=0x%0h bp_pre=0x%0h valid_raw=0x%0h same_raw=0x%0h gotten=0x%0h same_keep=0x%0h same_masked=0x%0h same_gotten=0x%0h valid_masked=0x%0h bp_keep=0x%0h bp_mask=0x%0h all_matched=%0b mse_enable=%0b wr_en=%0b full=%0b rd_en=%0b empty=%0b count=%0d out_valid=%0b out_tag=0x%0h out_idx=0x%0h",
                            $time, event_name,
                            return_obs_bq_col_idx_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_col_tag_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_row_idx_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_row_tag_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_bp_pre_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_valid_raw_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_same_raw_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_gotten_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_same_keep_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_same_masked_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_same_gotten_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_valid_masked_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_bp_keep_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_bp_mask_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_all_matched_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_mse_enable_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_wr_en_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_full_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_rd_en_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_empty_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_count_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_out_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_out_tag_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_out_idx_mon[return_obs_group_id][return_obs_local_slice_id]
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | BUFFER_AG_IDX_QUEUE_WITNESS_V1 | event=%s first_col=%0d last_col=%0d last_row=%0d last_enqueue=%0d last_dequeue=%0d",
                            $time, event_name,
                            return_obs_bq_first_col_accept,
                            return_obs_bq_last_col_accept,
                            return_obs_bq_last_row_accept,
                            return_obs_bq_last_enqueue,
                            return_obs_bq_last_dequeue
                        );
                    end
'''


SAMPLER = r'''    // v33 sampler: qualified input accepts and FIFO accepts only.
    always @(posedge u_NDP_Top_new.clk_sg) begin
        if (
            u_NDP_Top_new.rst_n_sg &&
            return_obs_enabled &&
            return_obs_bq_enabled &&
            return_obs_active &&
            return_obs_fd != 0
        ) begin
            bit bq_col_accept;
            bit bq_row_accept;
            bit bq_enqueue;
            bit bq_dequeue;
            bit bq_event;
            bq_col_accept =
                return_obs_bq_valid_raw_mon[return_obs_group_id][return_obs_local_slice_id][0] &&
                return_obs_bq_bp_pre_mon[return_obs_group_id][return_obs_local_slice_id][0];
            bq_row_accept =
                return_obs_bq_valid_raw_mon[return_obs_group_id][return_obs_local_slice_id][1] &&
                return_obs_bq_bp_pre_mon[return_obs_group_id][return_obs_local_slice_id][1];
            bq_enqueue =
                return_obs_bq_wr_en_mon[return_obs_group_id][return_obs_local_slice_id] &&
                !return_obs_bq_full_mon[return_obs_group_id][return_obs_local_slice_id];
            bq_dequeue =
                return_obs_bq_rd_en_mon[return_obs_group_id][return_obs_local_slice_id] &&
                !return_obs_bq_empty_mon[return_obs_group_id][return_obs_local_slice_id];
            bq_event = bq_col_accept || bq_row_accept || bq_enqueue || bq_dequeue;
            if (bq_col_accept) begin
                return_obs_bq_col_accept_count++;
                if (return_obs_bq_first_col_accept == 0)
                    return_obs_bq_first_col_accept = return_obs_sg_clock_edge_count;
                return_obs_bq_last_col_accept = return_obs_sg_clock_edge_count;
            end
            if (bq_row_accept) begin
                return_obs_bq_row_accept_count++;
                return_obs_bq_last_row_accept = return_obs_sg_clock_edge_count;
            end
            if (bq_enqueue) begin
                return_obs_bq_enqueue_count++;
                return_obs_bq_last_enqueue = return_obs_sg_clock_edge_count;
            end
            if (bq_dequeue) begin
                return_obs_bq_dequeue_count++;
                return_obs_bq_last_dequeue = return_obs_sg_clock_edge_count;
            end
            if (bq_event && return_obs_bq_emit_count < return_obs_bq_limit) begin
                return_obs_bq_emit_count++;
                $fdisplay(
                    return_obs_fd,
                    "%0t | BUFFER_AG_IDX_QUEUE_EVENT_V1 | edge=%0d col_accept=%0b row_accept=%0b enqueue=%0b dequeue=%0b col_idx=0x%0h col_tag=0x%0h row_idx=0x%0h row_tag=0x%0h bp_pre=0x%0h valid_raw=0x%0h same_raw=0x%0h gotten=0x%0h same_keep=0x%0h same_masked=0x%0h same_gotten=0x%0h valid_masked=0x%0h bp_keep=0x%0h bp_mask=0x%0h all_matched=%0b mse_enable=%0b full=%0b count=%0d out_valid=%0b out_tag=0x%0h out_idx=0x%0h",
                    $time, return_obs_sg_clock_edge_count,
                    bq_col_accept, bq_row_accept, bq_enqueue, bq_dequeue,
                    return_obs_bq_col_idx_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_col_tag_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_row_idx_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_row_tag_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_bp_pre_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_valid_raw_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_same_raw_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_gotten_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_same_keep_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_same_masked_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_same_gotten_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_valid_masked_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_bp_keep_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_bp_mask_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_all_matched_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_mse_enable_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_full_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_count_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_out_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_out_tag_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_bq_out_idx_mon[return_obs_group_id][return_obs_local_slice_id]
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
        "    // v31: COL-LC -> MSE0 WR_Buffer_AG -> Buffer0 MRM byte-lane diagnostic.\n",
        DECLARATIONS
        + "    // v31: COL-LC -> MSE0 WR_Buffer_AG -> Buffer0 MRM byte-lane diagnostic.\n",
        "v33 declarations",
    )
    text = replace_once(
        text,
        '        return_obs_lane_enabled =\n'
        '            $test$plusargs("RETURN_OBS_COL_AG_MRM_LANE");\n',
        '        return_obs_lane_enabled =\n'
        '            $test$plusargs("RETURN_OBS_COL_AG_MRM_LANE");\n'
        '        return_obs_bq_enabled =\n'
        '            $test$plusargs("RETURN_OBS_BUFFER_AG_IDX_QUEUE");\n',
        "v33 enable",
    )
    text = replace_once(
        text,
        "        return_obs_lane_limit = 256;\n",
        "        return_obs_lane_limit = 256;\n"
        "        return_obs_bq_limit = 256;\n",
        "v33 default limit",
    )
    text = replace_once(
        text,
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_COL_AG_MRM_LANE_LIMIT=%d",\n'
        '                return_obs_lane_limit\n'
        '            );\n',
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_COL_AG_MRM_LANE_LIMIT=%d",\n'
        '                return_obs_lane_limit\n'
        '            );\n'
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=%d",\n'
        '                return_obs_bq_limit\n'
        '            );\n',
        "v33 limit plusarg",
    )
    text = text.replace(
        "        return_obs_lane_reset();\n",
        "        return_obs_lane_reset();\n"
        "        return_obs_bq_reset();\n",
    )
    if text.count("return_obs_bq_reset();") != 2:
        raise BuildError("v33 reset call count differs")
    text = replace_once(
        text,
        "                    if (return_obs_lane_enabled) begin\n",
        SUMMARY + "                    if (return_obs_lane_enabled) begin\n",
        "v33 summary",
    )
    text = replace_once(
        text,
        "col_ag_mrm_lane=%0d col_ag_mrm_lane_limit=%0d",
        "col_ag_mrm_lane=%0d col_ag_mrm_lane_limit=%0d "
        "buffer_ag_idx_queue=%0d buffer_ag_idx_queue_limit=%0d",
        "v33 time0 format",
    )
    text = replace_once(
        text,
        "                        return_obs_lane_enabled,\n"
        "                        return_obs_lane_limit\n",
        "                        return_obs_lane_enabled,\n"
        "                        return_obs_lane_limit,\n"
        "                        return_obs_bq_enabled,\n"
        "                        return_obs_bq_limit\n",
        "v33 time0 args",
    )
    text = replace_once(
        text,
        "    // v31 sampler: accepted transactions only; stable levels are state.\n",
        SAMPLER + "    // v31 sampler: accepted transactions only; stable levels are state.\n",
        "v33 sampler",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def upgrade_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "  +RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256\n",
        "  +RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256\n"
        "  +RETURN_OBS_BUFFER_AG_IDX_QUEUE\n"
        "  +RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256\n",
        "runner v33 plusargs",
    )
    text = replace_once(
        text,
        "+RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256 +RETURN_OBS_FILE=",
        "+RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256 "
        "+RETURN_OBS_BUFFER_AG_IDX_QUEUE "
        "+RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256 +RETURN_OBS_FILE=",
        "runner v33 argv receipt",
    )
    marker = (
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
    addition = marker + (
        "  if [ \"$observer_ok\" = true ] && "
        "grep -Fq 'buffer_ag_idx_queue=1' \"$observer_log\" && "
        "grep -Fq 'buffer_ag_idx_queue_limit=256' \"$observer_log\" && "
        "grep -Fq 'BUFFER_AG_IDX_QUEUE_COUNTS_V1' \"$observer_log\" && "
        "grep -Fq 'BUFFER_AG_IDX_QUEUE_STATE_V1' \"$observer_log\" && "
        "grep -Fq 'BUFFER_AG_IDX_QUEUE_WITNESS_V1' \"$observer_log\"; then\n"
        "    buffer_ag_idx_queue_ok=true\n"
        "  else\n"
        "    buffer_ag_idx_queue_ok=false\n"
        "  fi\n"
        "  if [ \"$buffer_ag_idx_queue_ok\" = true ]; then\n"
        "    printf 'buffer_ag_idx_queue_enabled=true\\n"
        "buffer_ag_idx_queue_limit=256\\n"
        "buffer_ag_idx_queue_records_returned=true\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  else\n"
        "    printf 'buffer_ag_idx_queue_enabled=false\\n"
        "buffer_ag_idx_queue_limit=UNKNOWN\\n"
        "buffer_ag_idx_queue_records_returned=false\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  fi\n"
    )
    text = replace_once(text, marker, addition, "runner v33 receipt")
    path.write_text(text, encoding="utf-8", newline="\n")


def update_manifest(package: Path, source_manifest: dict[str, Any]) -> None:
    base.update_manifest(package, source_manifest)
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "gap-node0071-buffer-ag-index-pair-diagnostic-package-v33",
            "test_id": TEST_ID,
            "claim_boundary": (
                "read-only MSE0 Buffer_AG_Idx_Queue direct input accepts, "
                "decoded pairing masks, FIFO accepted enqueue/dequeue and output"
            ),
        }
    )
    manifest["buffer_ag_index_pair_diagnostic_contract"] = {
        "trigger_return_sha256": TRIGGER_RETURN_SHA256,
        "trigger_analysis_sha256": base.sha256(TRIGGER_ANALYSIS),
        "last_proven_good": (
            "COL-LC0 accepted lane1 value exists; all eight downstream "
            "MSE writes are preserved by Buffer0 MRM"
        ),
        "first_divergence": (
            "COL_LC0_ACCEPTED_BYTE_LANE1_VALUE_PRESENT_ONLY_BEFORE_MSE0_"
            "BUFFER_AG_ACTIVITY_AND_NO_BUFFER0_MRM_BYTE_LANE1_WRITE"
        ),
        "runtime_enable": "+RETURN_OBS_BUFFER_AG_IDX_QUEUE",
        "runtime_limit": "+RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256",
        "time0_marker": "buffer_ag_idx_queue=1 buffer_ag_idx_queue_limit=256",
        "records": [
            "BUFFER_AG_IDX_QUEUE_EVENT_V1",
            "BUFFER_AG_IDX_QUEUE_COUNTS_V1",
            "BUFFER_AG_IDX_QUEUE_STATE_V1",
            "BUFFER_AG_IDX_QUEUE_WITNESS_V1",
        ],
        "clock": "clk_sg",
        "qualified_events": [
            "column valid_raw[0] and bp_pre[0]",
            "row valid_raw[1] and bp_pre[1]",
            "queue wr_en and not full",
            "queue rd_en and not empty",
        ],
        "state_only": [
            "stable raw tag/index, valid/same/gotten/mask vectors",
            "stable full/empty/count/output state",
        ],
        "stable_level_counts_as_progress": False,
        "read_only": True,
        "drives_dut": False,
        "changes_timeout": False,
    }
    features = manifest["diagnostic_feature_runtime_enable_contract"]["features"]
    unique = []
    seen = set()
    for feature in features:
        if feature["name"] in seen:
            continue
        seen.add(feature["name"])
        unique.append(feature)
    unique.append(
        {
            "name": "buffer_ag_idx_queue",
            "runtime_enable": "+RETURN_OBS_BUFFER_AG_IDX_QUEUE",
            "runtime_limit": "+RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256",
            "time0_marker": "buffer_ag_idx_queue=1 buffer_ag_idx_queue_limit=256",
            "returned_binding_receipt": "evidence/observer_binding.txt",
            "return_target": "runs/return_observer.log",
            "zero_when_disabled": "DISABLED_INSTRUMENTATION_ZERO",
        }
    )
    manifest["diagnostic_feature_runtime_enable_contract"]["features"] = unique
    manifest["generation_provenance"].update(
        {
            "tool": "tools/build_gap_node0071_buffer_ag_idx_queue_v33_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "trigger_return_sha256": TRIGGER_RETURN_SHA256,
            "package_side_change": (
                "add bounded accepted-event MSE0 Buffer_AG_Idx_Queue "
                "input/match/FIFO observer"
            ),
        }
    )
    manifest["files"] = file_records(package)
    write_json(path, manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_source()
    root = base.root_builder()
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
        "# GAP node0071 v33 Buffer-AG index pairing diagnostic\n\n"
        f"Test ID: `{TEST_ID}`.\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It preserves "
        "the frozen numeric/config/golden/execplan/functional-RTL payload and "
        "adds bounded read-only accepted-event evidence at the MSE0 "
        "Buffer_AG_Idx_Queue input/match/FIFO boundary.\n\n"
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
    return package, {
        "source_v32_zip_sha256": SOURCE_SHA256,
        "changed_paths": sorted(changed),
        "changed_paths_exact_allowlist": True,
        "frozen_numeric_workload_file_count": len(numeric_after),
        "frozen_numeric_workload_tree_equal": True,
        "frozen_other_file_count": len(source_records) - len(ALLOWED_CHANGED),
        "frozen_other_tree_equal": all(
            source_records[path] == final_records[path]
            for path in set(source_records) - ALLOWED_CHANGED
        ),
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    digest = base.sha256(zip_path)
    tree = file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(prefix="gap-node0071-v33-repeat-") as temp:
        repeated, _ = build_directory(Path(temp))
        repeated_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        deterministic_zip(repeated, repeated_zip, archive_root=INSTALL_NAME)
        if base.sha256(repeated_zip) != digest:
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
        digest = base.sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
        )
        result = {
            "schema": "gap-node0071-buffer-ag-index-pair-v33-build-v1",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "test_id": TEST_ID,
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package": str(package),
            "zip": str(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "zip_sha256": digest,
            "sidecar": str(sidecar),
            "sidecar_sha256": base.sha256(sidecar),
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
        import traceback
        traceback.print_exc()
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
