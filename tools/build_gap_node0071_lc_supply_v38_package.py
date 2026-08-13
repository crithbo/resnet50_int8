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

from tools.build_gap_node0071_complete_server_package import (
    deterministic_zip,
    write_json,
)
from tools.gap_node0071_complete_server_runtime import file_records
from tools import build_gap_node0071_v37_dbclk_rdready_compilefix as source_builder


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v37_dbclk_rdready_compilefix"
INSTALL_NAME = "r5_n71_gap_v40_lc_supply_conservation_diag"
TEST_ID = "r5-gap-node0071-v40-lc-supply-conservation-information-gain"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = (
    "796312c5c4c5ed941a78fd4a0cf245bb580edac9b1b7ff5960b8e78c3eb8fa7b"
)
TRIGGER_RETURN_SHA256 = (
    "dd9f4551f4fd324f100fcb01ff50ec4a7a123df0e0bdc4a8705f02f52ce15f87"
)
TRIGGER_ANALYSIS = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-gap-node0071-v37-return-analysis/report.json"
)
OBSERVER = "tb_probe/native_return_observer.svh"
FEATURE = "RETURN_OBS_LC_SUPPLY_CONSERVATION"
FEATURE_LIMIT = 512
CLOUD_RTL_REPOSITORY = "xlsjdjdk/Trassic2.0_RTL"
CLOUD_RTL_BRANCH = "master"
CLOUD_RTL_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
LOCAL_RTL_HINT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
CLOUD_BUFFER_AG_TEXT_SHA256 = (
    "e47c77d8aec2eb350d81ef2a43b72923869dd4b39a41ebc91e23a508e7ab58aa"
)
CLOUD_RD_CHANNEL_TEXT_SHA256 = (
    "20cafa837ad80f8f01a33b4ae2323b3c515a13b0a2e66b5f2104c4065547824c"
)
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
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise BuildError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def configure_source() -> Any:
    source_builder.SOURCE_NAME = SOURCE_NAME
    source_builder.INSTALL_NAME = INSTALL_NAME
    source_builder.TEST_ID = TEST_ID
    source_builder.SOURCE_ZIP = SOURCE_ZIP
    source_builder.SOURCE_SHA256 = SOURCE_SHA256
    source_builder.TRIGGER_RETURN_SHA256 = TRIGGER_RETURN_SHA256
    source_builder.TRIGGER_ANALYSIS = TRIGGER_ANALYSIS
    root = source_builder.configure_source()
    root.SOURCE_NAME = SOURCE_NAME
    root.INSTALL_NAME = INSTALL_NAME
    root.SOURCE_ZIP = SOURCE_ZIP
    root.SOURCE_SHA256 = SOURCE_SHA256
    return root


DECLARATIONS = r'''
    // v38: owner-clock LC/memory/buffer conservation information-gain slice.
    bit return_obs_lcsc_enabled;
    int return_obs_lcsc_limit;
    int return_obs_lcsc_emit_count;
    longint unsigned return_obs_lcsc_edge;
    longint unsigned return_obs_lcsc_bq_wr [0:1];
    longint unsigned return_obs_lcsc_bq_rd [0:1];
    longint unsigned return_obs_lcsc_mq_wr [0:1];
    longint unsigned return_obs_lcsc_mq_rd [0:1];
    longint unsigned return_obs_lcsc_req [0:1];
    longint unsigned return_obs_lcsc_first_bq_full [0:1];
    longint unsigned return_obs_lcsc_last_bq_full [0:1];
    longint unsigned return_obs_lcsc_first_mem_empty [0:1];
    longint unsigned return_obs_lcsc_last_mem_empty [0:1];
    logic [1:0] return_obs_lcsc_bq_add_wr_mon;
    logic [1:0] return_obs_lcsc_bq_add_rd_mon;
    logic [1:0][5:0] return_obs_lcsc_bq_count_mon;
    logic [1:0] return_obs_lcsc_bq_full_mon;
    logic [1:0] return_obs_lcsc_bq_empty_mon;
    logic [1:0] return_obs_lcsc_mq_add_wr_mon;
    logic [1:0] return_obs_lcsc_mq_add_rd_mon;
    logic [1:0][3:0] return_obs_lcsc_mq_count_mon;
    logic [1:0] return_obs_lcsc_mq_full_mon;
    logic [1:0] return_obs_lcsc_mq_empty_mon;
    logic [1:0][`MSE_MQ_INPORT_NUM-1:0]
          [`SE_MEM_INPORT_TAG_WIDTH-1:0] return_obs_lcsc_mem_tag_mon;
    logic [1:0][`MSE_MQ_INPORT_NUM-1:0]
          return_obs_lcsc_mem_bp_mon;
    logic [1:0] return_obs_lcsc_mem_out_valid_mon;
    logic [1:0] return_obs_lcsc_mem_out_bp_mon;
    logic [1:0] return_obs_lcsc_req_valid_mon;
    logic [1:0] return_obs_lcsc_req_ready_mon;
    logic [1:0] return_obs_lcsc_buf_out_valid_mon;
    logic [1:0] return_obs_lcsc_buf_out_bp_mon;
    logic [1:0][31:0] return_obs_lcsc_prev_surface;

    `define RETURN_OBS_LCSC_M0 u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
    `define RETURN_OBS_LCSC_M3 u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].RD_MSE.u_Memory_RD_Stream_Engine
    assign return_obs_lcsc_bq_add_wr_mon[0] = `RETURN_OBS_LCSC_M0.u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.add_wr_ptr;
    assign return_obs_lcsc_bq_add_rd_mon[0] = `RETURN_OBS_LCSC_M0.u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.add_rd_ptr;
    assign return_obs_lcsc_bq_count_mon[0] = `RETURN_OBS_LCSC_M0.u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.fifo_counter;
    assign return_obs_lcsc_bq_full_mon[0] = `RETURN_OBS_LCSC_M0.u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.fifo_full;
    assign return_obs_lcsc_bq_empty_mon[0] = `RETURN_OBS_LCSC_M0.u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.fifo_empty;
    assign return_obs_lcsc_mq_add_wr_mon[0] = `RETURN_OBS_LCSC_M0.u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.add_wr_ptr;
    assign return_obs_lcsc_mq_add_rd_mon[0] = `RETURN_OBS_LCSC_M0.u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.add_rd_ptr;
    assign return_obs_lcsc_mq_count_mon[0] = `RETURN_OBS_LCSC_M0.u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.fifo_counter;
    assign return_obs_lcsc_mq_full_mon[0] = `RETURN_OBS_LCSC_M0.u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.fifo_full;
    assign return_obs_lcsc_mq_empty_mon[0] = `RETURN_OBS_LCSC_M0.u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.fifo_empty;
    assign return_obs_lcsc_mem_tag_mon[0] = `RETURN_OBS_LCSC_M0.u_Memory_AG_Idx_Queue.mse_mem_queue_tag;
    assign return_obs_lcsc_mem_bp_mon[0] = `RETURN_OBS_LCSC_M0.u_Memory_AG_Idx_Queue.mse_mem_queue_bp_pre;
    assign return_obs_lcsc_mem_out_valid_mon[0] = `RETURN_OBS_LCSC_M0.u_Memory_AG_Idx_Queue.mse_mem_ag_tag_valid;
    assign return_obs_lcsc_mem_out_bp_mon[0] = `RETURN_OBS_LCSC_M0.u_Memory_AG_Idx_Queue.mse_mem_ag_bp_post;
    assign return_obs_lcsc_req_valid_mon[0] = `RETURN_OBS_LCSC_M0.u_RD_Memory_AG.rd_data_chl_req_valid;
    assign return_obs_lcsc_req_ready_mon[0] = `RETURN_OBS_LCSC_M0.u_RD_Memory_AG.rd_data_chl_req_ready;
    assign return_obs_lcsc_buf_out_valid_mon[0] = `RETURN_OBS_LCSC_M0.u_Buffer_AG_Idx_Queue.mse_buf_ag_tag_valid;
    assign return_obs_lcsc_buf_out_bp_mon[0] = `RETURN_OBS_LCSC_M0.u_Buffer_AG_Idx_Queue.mse_buf_ag_bp_post;

    assign return_obs_lcsc_bq_add_wr_mon[1] = `RETURN_OBS_LCSC_M3.u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.add_wr_ptr;
    assign return_obs_lcsc_bq_add_rd_mon[1] = `RETURN_OBS_LCSC_M3.u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.add_rd_ptr;
    assign return_obs_lcsc_bq_count_mon[1] = `RETURN_OBS_LCSC_M3.u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.fifo_counter;
    assign return_obs_lcsc_bq_full_mon[1] = `RETURN_OBS_LCSC_M3.u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.fifo_full;
    assign return_obs_lcsc_bq_empty_mon[1] = `RETURN_OBS_LCSC_M3.u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.fifo_empty;
    assign return_obs_lcsc_mq_add_wr_mon[1] = `RETURN_OBS_LCSC_M3.u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.add_wr_ptr;
    assign return_obs_lcsc_mq_add_rd_mon[1] = `RETURN_OBS_LCSC_M3.u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.add_rd_ptr;
    assign return_obs_lcsc_mq_count_mon[1] = `RETURN_OBS_LCSC_M3.u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.fifo_counter;
    assign return_obs_lcsc_mq_full_mon[1] = `RETURN_OBS_LCSC_M3.u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.fifo_full;
    assign return_obs_lcsc_mq_empty_mon[1] = `RETURN_OBS_LCSC_M3.u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.fifo_empty;
    assign return_obs_lcsc_mem_tag_mon[1] = `RETURN_OBS_LCSC_M3.u_Memory_AG_Idx_Queue.mse_mem_queue_tag;
    assign return_obs_lcsc_mem_bp_mon[1] = `RETURN_OBS_LCSC_M3.u_Memory_AG_Idx_Queue.mse_mem_queue_bp_pre;
    assign return_obs_lcsc_mem_out_valid_mon[1] = `RETURN_OBS_LCSC_M3.u_Memory_AG_Idx_Queue.mse_mem_ag_tag_valid;
    assign return_obs_lcsc_mem_out_bp_mon[1] = `RETURN_OBS_LCSC_M3.u_Memory_AG_Idx_Queue.mse_mem_ag_bp_post;
    assign return_obs_lcsc_req_valid_mon[1] = `RETURN_OBS_LCSC_M3.u_RD_Memory_AG.rd_data_chl_req_valid;
    assign return_obs_lcsc_req_ready_mon[1] = `RETURN_OBS_LCSC_M3.u_RD_Memory_AG.rd_data_chl_req_ready;
    assign return_obs_lcsc_buf_out_valid_mon[1] = `RETURN_OBS_LCSC_M3.u_Buffer_AG_Idx_Queue.mse_buf_ag_tag_valid;
    assign return_obs_lcsc_buf_out_bp_mon[1] = `RETURN_OBS_LCSC_M3.u_Buffer_AG_Idx_Queue.mse_buf_ag_bp_post;
    `undef RETURN_OBS_LCSC_M0
    `undef RETURN_OBS_LCSC_M3

'''


SUMMARY = r'''
                    if (return_obs_lcsc_enabled) begin
                        $fdisplay(
                            return_obs_fd,
                            "%0t | LC_SUPPLY_CONSERVATION_COUNTS_V1 | event=%s edge=%0d bq_wr=%0d/%0d bq_rd=%0d/%0d mq_wr=%0d/%0d mq_rd=%0d/%0d req=%0d/%0d records=%0d limit=%0d",
                            $time, event_name, return_obs_lcsc_edge,
                            return_obs_lcsc_bq_wr[0], return_obs_lcsc_bq_wr[1],
                            return_obs_lcsc_bq_rd[0], return_obs_lcsc_bq_rd[1],
                            return_obs_lcsc_mq_wr[0], return_obs_lcsc_mq_wr[1],
                            return_obs_lcsc_mq_rd[0], return_obs_lcsc_mq_rd[1],
                            return_obs_lcsc_req[0], return_obs_lcsc_req[1],
                            return_obs_lcsc_emit_count, return_obs_lcsc_limit
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | LC_SUPPLY_CONSERVATION_STATE_V1 | event=%s bq_count=%0d/%0d bq_full=0x%0h bq_empty=0x%0h mq_count=%0d/%0d mq_full=0x%0h mq_empty=0x%0h mem_tag0=0x%0h mem_tag3=0x%0h mem_bp0=0x%0h mem_bp3=0x%0h mem_out_vld=0x%0h mem_out_bp=0x%0h req_vld=0x%0h req_ready=0x%0h buf_out_vld=0x%0h buf_out_bp=0x%0h",
                            $time, event_name,
                            return_obs_lcsc_bq_count_mon[0], return_obs_lcsc_bq_count_mon[1],
                            return_obs_lcsc_bq_full_mon, return_obs_lcsc_bq_empty_mon,
                            return_obs_lcsc_mq_count_mon[0], return_obs_lcsc_mq_count_mon[1],
                            return_obs_lcsc_mq_full_mon, return_obs_lcsc_mq_empty_mon,
                            return_obs_lcsc_mem_tag_mon[0], return_obs_lcsc_mem_tag_mon[1],
                            return_obs_lcsc_mem_bp_mon[0], return_obs_lcsc_mem_bp_mon[1],
                            return_obs_lcsc_mem_out_valid_mon, return_obs_lcsc_mem_out_bp_mon,
                            return_obs_lcsc_req_valid_mon, return_obs_lcsc_req_ready_mon,
                            return_obs_lcsc_buf_out_valid_mon, return_obs_lcsc_buf_out_bp_mon
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | LC_SUPPLY_CONSERVATION_WITNESS_V1 | event=%s bq_full=%0d:%0d/%0d:%0d mem_empty=%0d:%0d/%0d:%0d",
                            $time, event_name,
                            return_obs_lcsc_first_bq_full[0], return_obs_lcsc_last_bq_full[0],
                            return_obs_lcsc_first_bq_full[1], return_obs_lcsc_last_bq_full[1],
                            return_obs_lcsc_first_mem_empty[0], return_obs_lcsc_last_mem_empty[0],
                            return_obs_lcsc_first_mem_empty[1], return_obs_lcsc_last_mem_empty[1]
                        );
                    end
'''


SAMPLER = r'''
    // v38 sampler: exact owner-clock qualified FIFO accepts and surface edges.
    always @(posedge u_NDP_Top_new.clk) begin
        if (!u_NDP_Top_new.rst_n) begin
            return_obs_lcsc_edge = 0;
            return_obs_lcsc_emit_count = 0;
            return_obs_lcsc_prev_surface = '0;
            for (int lcsc_reset_flow = 0; lcsc_reset_flow < 2; lcsc_reset_flow++) begin
                return_obs_lcsc_bq_wr[lcsc_reset_flow] = 0;
                return_obs_lcsc_bq_rd[lcsc_reset_flow] = 0;
                return_obs_lcsc_mq_wr[lcsc_reset_flow] = 0;
                return_obs_lcsc_mq_rd[lcsc_reset_flow] = 0;
                return_obs_lcsc_req[lcsc_reset_flow] = 0;
                return_obs_lcsc_first_bq_full[lcsc_reset_flow] = 0;
                return_obs_lcsc_last_bq_full[lcsc_reset_flow] = 0;
                return_obs_lcsc_first_mem_empty[lcsc_reset_flow] = 0;
                return_obs_lcsc_last_mem_empty[lcsc_reset_flow] = 0;
            end
        end
        else if (
            return_obs_enabled &&
            return_obs_lcsc_enabled &&
            return_obs_active &&
            return_obs_fd != 0
        ) begin
            return_obs_lcsc_edge++;
            for (int lcsc_flow = 0; lcsc_flow < 2; lcsc_flow++) begin
                bit lcsc_req;
                bit lcsc_surface_edge;
                bit lcsc_event;
                logic [31:0] lcsc_surface;
                lcsc_req = return_obs_lcsc_req_valid_mon[lcsc_flow] &&
                           return_obs_lcsc_req_ready_mon[lcsc_flow];
                lcsc_surface = {
                    8'b0,
                    return_obs_lcsc_mem_tag_mon[lcsc_flow],
                    return_obs_lcsc_mem_bp_mon[lcsc_flow],
                    return_obs_lcsc_mem_out_valid_mon[lcsc_flow],
                    return_obs_lcsc_mem_out_bp_mon[lcsc_flow],
                    return_obs_lcsc_req_valid_mon[lcsc_flow],
                    return_obs_lcsc_req_ready_mon[lcsc_flow],
                    return_obs_lcsc_buf_out_valid_mon[lcsc_flow],
                    return_obs_lcsc_buf_out_bp_mon[lcsc_flow],
                    return_obs_lcsc_bq_full_mon[lcsc_flow],
                    return_obs_lcsc_bq_empty_mon[lcsc_flow],
                    return_obs_lcsc_mq_full_mon[lcsc_flow],
                    return_obs_lcsc_mq_empty_mon[lcsc_flow]
                };
                lcsc_surface_edge =
                    lcsc_surface != return_obs_lcsc_prev_surface[lcsc_flow];
                lcsc_event =
                    return_obs_lcsc_bq_add_wr_mon[lcsc_flow] ||
                    return_obs_lcsc_bq_add_rd_mon[lcsc_flow] ||
                    return_obs_lcsc_mq_add_wr_mon[lcsc_flow] ||
                    return_obs_lcsc_mq_add_rd_mon[lcsc_flow] ||
                    lcsc_req || lcsc_surface_edge;
                if (return_obs_lcsc_bq_add_wr_mon[lcsc_flow])
                    return_obs_lcsc_bq_wr[lcsc_flow]++;
                if (return_obs_lcsc_bq_add_rd_mon[lcsc_flow])
                    return_obs_lcsc_bq_rd[lcsc_flow]++;
                if (return_obs_lcsc_mq_add_wr_mon[lcsc_flow])
                    return_obs_lcsc_mq_wr[lcsc_flow]++;
                if (return_obs_lcsc_mq_add_rd_mon[lcsc_flow])
                    return_obs_lcsc_mq_rd[lcsc_flow]++;
                if (lcsc_req) return_obs_lcsc_req[lcsc_flow]++;
                if (return_obs_lcsc_bq_full_mon[lcsc_flow]) begin
                    if (return_obs_lcsc_first_bq_full[lcsc_flow] == 0)
                        return_obs_lcsc_first_bq_full[lcsc_flow] =
                            return_obs_lcsc_edge;
                    return_obs_lcsc_last_bq_full[lcsc_flow] =
                        return_obs_lcsc_edge;
                end
                if (return_obs_lcsc_mq_empty_mon[lcsc_flow]) begin
                    if (return_obs_lcsc_first_mem_empty[lcsc_flow] == 0)
                        return_obs_lcsc_first_mem_empty[lcsc_flow] =
                            return_obs_lcsc_edge;
                    return_obs_lcsc_last_mem_empty[lcsc_flow] =
                        return_obs_lcsc_edge;
                end
                if (
                    lcsc_event &&
                    return_obs_lcsc_emit_count < return_obs_lcsc_limit
                ) begin
                    return_obs_lcsc_emit_count++;
                    $fdisplay(
                        return_obs_fd,
                        "%0t | LC_SUPPLY_CONSERVATION_EVENT_V1 | n=%0d edge=%0d mse=%0d bq_wr=%0b bq_rd=%0b bq_count=%0d bq_full=%0b bq_empty=%0b mq_wr=%0b mq_rd=%0b mq_count=%0d mq_full=%0b mq_empty=%0b mem_tag=0x%0h mem_bp=0x%0h mem_out_vld=%0b mem_out_bp=%0b req=%0b req_vld=%0b req_ready=%0b buf_out_vld=%0b buf_out_bp=%0b surface_edge=%0b",
                        $time, return_obs_lcsc_emit_count,
                        return_obs_lcsc_edge, (lcsc_flow == 0 ? 0 : 3),
                        return_obs_lcsc_bq_add_wr_mon[lcsc_flow],
                        return_obs_lcsc_bq_add_rd_mon[lcsc_flow],
                        return_obs_lcsc_bq_count_mon[lcsc_flow],
                        return_obs_lcsc_bq_full_mon[lcsc_flow],
                        return_obs_lcsc_bq_empty_mon[lcsc_flow],
                        return_obs_lcsc_mq_add_wr_mon[lcsc_flow],
                        return_obs_lcsc_mq_add_rd_mon[lcsc_flow],
                        return_obs_lcsc_mq_count_mon[lcsc_flow],
                        return_obs_lcsc_mq_full_mon[lcsc_flow],
                        return_obs_lcsc_mq_empty_mon[lcsc_flow],
                        return_obs_lcsc_mem_tag_mon[lcsc_flow],
                        return_obs_lcsc_mem_bp_mon[lcsc_flow],
                        return_obs_lcsc_mem_out_valid_mon[lcsc_flow],
                        return_obs_lcsc_mem_out_bp_mon[lcsc_flow],
                        lcsc_req,
                        return_obs_lcsc_req_valid_mon[lcsc_flow],
                        return_obs_lcsc_req_ready_mon[lcsc_flow],
                        return_obs_lcsc_buf_out_valid_mon[lcsc_flow],
                        return_obs_lcsc_buf_out_bp_mon[lcsc_flow],
                        lcsc_surface_edge
                    );
                end
                return_obs_lcsc_prev_surface[lcsc_flow] = lcsc_surface;
            end
            if (return_obs_lcsc_emit_count != 0) $fflush(return_obs_fd);
        end
    end

'''


def upgrade_observer(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    // v33: MSE0 Buffer_AG_Idx_Queue input/match/FIFO diagnostic.\n",
        DECLARATIONS
        + "    // v33: MSE0 Buffer_AG_Idx_Queue input/match/FIFO diagnostic.\n",
        "declarations",
    )
    text = replace_once(
        text,
        "                    if (return_obs_bq_enabled) begin\n",
        SUMMARY + "                    if (return_obs_bq_enabled) begin\n",
        "summary",
    )
    text = replace_once(
        text,
        "        return_obs_dbrr_enabled =\n"
        '            $test$plusargs("RETURN_OBS_DBCLK_RD_READY");\n',
        "        return_obs_dbrr_enabled =\n"
        '            $test$plusargs("RETURN_OBS_DBCLK_RD_READY");\n'
        "        return_obs_lcsc_enabled =\n"
        f'            $test$plusargs("{FEATURE}");\n',
        "feature enable",
    )
    text = replace_once(
        text,
        "        return_obs_dbrr_limit = 256;\n",
        "        return_obs_dbrr_limit = 256;\n"
        f"        return_obs_lcsc_limit = {FEATURE_LIMIT};\n",
        "feature limit",
    )
    text = replace_once(
        text,
        "        return_obs_plusarg_status =\n"
        "            $value$plusargs(\n"
        '                "RETURN_OBS_DBCLK_RD_READY_LIMIT=%d",\n'
        "                return_obs_dbrr_limit\n"
        "            );\n",
        "        return_obs_plusarg_status =\n"
        "            $value$plusargs(\n"
        '                "RETURN_OBS_DBCLK_RD_READY_LIMIT=%d",\n'
        "                return_obs_dbrr_limit\n"
        "            );\n"
        "        return_obs_plusarg_status =\n"
        "            $value$plusargs(\n"
        f'                "{FEATURE}_LIMIT=%d",\n'
        "                return_obs_lcsc_limit\n"
        "            );\n",
        "feature limit plusarg",
    )
    text = replace_once(
        text,
        '                    $fdisplay(\n'
        '                        return_obs_fd,\n'
        '                        "# checkpoints: cfg/exec memory buffer SA GA; deep=MSE0 context plus clk_sg GA input/output and MSE4 request/write-data accounting"\n'
        '                    );\n',
        '                    $fdisplay(\n'
        '                        return_obs_fd,\n'
        '                        "# checkpoints: cfg/exec memory buffer SA GA; deep=MSE0 context plus clk_sg GA input/output and MSE4 request/write-data accounting"\n'
        '                    );\n'
        '                    $fdisplay(\n'
        '                        return_obs_fd,\n'
        '                        "# lc_supply_conservation=%0d lc_supply_conservation_limit=%0d owner_clock=clk_db",\n'
        '                        return_obs_lcsc_enabled,\n'
        '                        return_obs_lcsc_limit\n'
        '                    );\n',
        "time0 marker",
    )
    text = replace_once(
        text,
        "    // v33 sampler: qualified input accepts and FIFO accepts only.\n",
        SAMPLER
        + "    // v33 sampler: qualified input accepts and FIFO accepts only.\n",
        "sampler",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def upgrade_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "  if [ \"$dbclk_rd_ready_ok\" = true ]; then\n"
        "    printf 'dbclk_rd_ready_enabled=true\\ndbclk_rd_ready_limit=256\\ndbclk_rd_ready_records_returned=true\\n' >>\"$evidence_root/observer_binding.txt\"\n"
        "  else\n"
        "    printf 'dbclk_rd_ready_enabled=false\\ndbclk_rd_ready_limit=UNKNOWN\\ndbclk_rd_ready_records_returned=false\\n' >>\"$evidence_root/observer_binding.txt\"\n"
        "  fi\n",
        "  if [ \"$dbclk_rd_ready_ok\" = true ]; then\n"
        "    printf 'dbclk_rd_ready_enabled=true\\ndbclk_rd_ready_limit=256\\ndbclk_rd_ready_records_returned=true\\n' >>\"$evidence_root/observer_binding.txt\"\n"
        "  else\n"
        "    printf 'dbclk_rd_ready_enabled=false\\ndbclk_rd_ready_limit=UNKNOWN\\ndbclk_rd_ready_records_returned=false\\n' >>\"$evidence_root/observer_binding.txt\"\n"
        "  fi\n"
        "  if [ \"$observer_ok\" = true ] && "
        "grep -Fq 'lc_supply_conservation=1' \"$observer_log\" && "
        "grep -Fq 'lc_supply_conservation_limit=512' \"$observer_log\" && "
        "grep -Fq 'LC_SUPPLY_CONSERVATION_COUNTS_V1' \"$observer_log\" && "
        "grep -Fq 'LC_SUPPLY_CONSERVATION_STATE_V1' \"$observer_log\" && "
        "grep -Fq 'LC_SUPPLY_CONSERVATION_WITNESS_V1' \"$observer_log\"; then\n"
        "    lc_supply_conservation_ok=true\n"
        "  else\n"
        "    lc_supply_conservation_ok=false\n"
        "  fi\n"
        "  if [ \"$lc_supply_conservation_ok\" = true ]; then\n"
        "    printf 'lc_supply_conservation_enabled=true\\nlc_supply_conservation_limit=512\\nlc_supply_conservation_records_returned=true\\n' >>\"$evidence_root/observer_binding.txt\"\n"
        "  else\n"
        "    printf 'lc_supply_conservation_enabled=false\\nlc_supply_conservation_limit=UNKNOWN\\nlc_supply_conservation_records_returned=false\\n' >>\"$evidence_root/observer_binding.txt\"\n"
        "  fi\n",
        "runner return binding",
    )
    text = replace_once(
        text,
        "  +RETURN_OBS_DBCLK_RD_READY\n"
        "  +RETURN_OBS_DBCLK_RD_READY_LIMIT=256\n",
        "  +RETURN_OBS_DBCLK_RD_READY\n"
        "  +RETURN_OBS_DBCLK_RD_READY_LIMIT=256\n"
        f"  +{FEATURE}\n"
        f"  +{FEATURE}_LIMIT={FEATURE_LIMIT}\n",
        "simulator feature argv",
    )
    text = replace_once(
        text,
        " +RETURN_OBS_DBCLK_RD_READY +RETURN_OBS_DBCLK_RD_READY_LIMIT=256 +RETURN_OBS_FILE=<run>/sim_results/return_observer/return_observer.log)",
        " +RETURN_OBS_DBCLK_RD_READY +RETURN_OBS_DBCLK_RD_READY_LIMIT=256"
        f" +{FEATURE} +{FEATURE}_LIMIT={FEATURE_LIMIT}"
        " +RETURN_OBS_FILE=<run>/sim_results/return_observer/return_observer.log)",
        "documented command",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def path_budget(package: Path) -> dict[str, Any]:
    relative = [
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
    ]
    max_inner = max(map(len, relative))
    max_depth = max(path.count("/") + 1 for path in relative)
    max_component = max(
        len(component)
        for path in relative
        for component in path.split("/")
    )
    max_zip_member = len(INSTALL_NAME) + 1 + max_inner
    return {
        "declared_target_root_max_chars": 96,
        "max_projected_absolute_path_chars": 240,
        "max_zip_member_chars": 224,
        "max_inner_suffix_chars": 128,
        "max_inner_depth": 8,
        "max_component_chars": 48,
        "measured_max_inner_suffix_chars": max_inner,
        "measured_max_inner_depth": max_depth,
        "measured_max_component_chars": max_component,
        "measured_max_zip_member_chars": max_zip_member,
        "projected_max_absolute_path_chars": 96 + 1 + max_inner,
        "identity_repeated_in_inner_path": any(
            INSTALL_NAME in path for path in relative
        ),
    }


def update_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "gap-node0071-lc-supply-conservation-package-v40",
            "test_id": TEST_ID,
            "package_name": INSTALL_NAME,
            "install_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "evidence_ceiling": "E2_LOCAL_ONLY",
            "supersedes_package_sha256": SOURCE_SHA256,
            "trigger_return_sha256": TRIGGER_RETURN_SHA256,
        }
    )
    manifest["rule_receipts"] = {
        **manifest.get("rule_receipts", {}),
        "agent_sha256": sha256(ROOT / ".agents/agent.md"),
        "plan_sha256_mutable_provenance_only":
            sha256(ROOT / ".agents/plan.md"),
        "generation_index_sha256": sha256(
            ROOT / ".agents/rules/生成前必读索引.md"
        ),
        "server_rule_sha256": sha256(
            ROOT / ".agents/rules/服务器测试包生成规则.md"
        ),
        "common_operator_rule_sha256": sha256(
            ROOT / ".agents/rules/算子配置规则.md"
        ),
        "ndp_field_rule_sha256": sha256(
            ROOT / ".agents/rules/NDP硬件字段语义.md"
        ),
        "gap_int32_rule_sha256": sha256(
            ROOT / ".agents/rules/GAP_int32_mac_bypass_rules.md"
        ),
        "gap_probe_rule_sha256": sha256(
            ROOT / ".agents/rules/GAP_probe_v7_validator_rules.md"
        ),
        "exact_uint8_tail_rule_sha256": sha256(
            ROOT / ".agents/rules/精确UINT8量化尾专项规则.md"
        ),
        "current_match": True,
    }
    manifest["lc_supply_conservation_information_gain_contract"] = {
        "feature": FEATURE,
        "limit": FEATURE_LIMIT,
        "owner_clock": "clk_db / u_NDP_Top_new.clk",
        "flows": ["MSE0", "MSE3"],
        "qualified_events": [
            "Buffer_AG FIFO actual add_wr_ptr/add_rd_ptr",
            "Memory_AG FIFO actual add_wr_ptr/add_rd_ptr",
            "RD_Memory_AG request valid&&ready",
            "public-surface state edge",
        ],
        "stable_level_policy": "state/witness only; never monotonic progress",
        "public_surfaces": [
            "Memory_AG_Idx_Queue.mse_mem_queue_tag",
            "Memory_AG_Idx_Queue.mse_mem_queue_bp_pre",
            "Memory_AG_Idx_Queue.mse_mem_ag_tag_valid",
            "Memory_AG_Idx_Queue.mse_mem_ag_bp_post",
            "RD_Memory_AG.rd_data_chl_req_valid",
            "RD_Memory_AG.rd_data_chl_req_ready",
            "Buffer_AG_Idx_Queue.mse_buf_ag_tag_valid",
            "Buffer_AG_Idx_Queue.mse_buf_ag_bp_post",
        ],
        "necessary_private_xmr": {
            "reason": (
                "v37 accepted-count balance equals the cloud-current 32-entry "
                "Buffer_AG FIFO depth; exact FIFO add pointers and the full "
                "6-bit counter are required to distinguish queue conservation "
                "from upstream LC/Memory_AG supply loss"
            ),
            "module": "FIFO",
            "module_path": "NDP_copy01/rtl/utils/FIFO/FIFO.sv",
            "module_sha256": sha256(
                ROOT / "NDP_copy01/rtl/utils/FIFO/FIFO.sv"
            ),
            "cloud_inheritance_proof": (
                "FIFO.sv is absent from the 11-file e1fb0f7..0ccae91 "
                "GitHub compare changed set, so the exact local FIFO module "
                "bytes are inherited unchanged by the approved cloud commit"
            ),
            "buffer_ag_fifo_depth": 32,
            "buffer_ag_fifo_counter_width": 6,
            "memory_ag_fifo_depth": 8,
            "memory_ag_fifo_counter_width": 4,
            "leaves": [
                "add_wr_ptr",
                "add_rd_ptr",
                "fifo_counter",
                "fifo_full",
                "fifo_empty",
            ],
            "clock": "clk_db",
            "instance_paths": [
                "MSE_INST[0|3].RD_MSE.u_Memory_RD_Stream_Engine.u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue",
                "MSE_INST[0|3].RD_MSE.u_Memory_RD_Stream_Engine.u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue",
            ],
        },
        "candidate_observation_matrix": {
            "materialized_occurrence_or_terminal_stop": [
                "public memory input tags/bp stop before Memory_AG FIFO add",
                "Memory_AG and request counters stop with empty FIFOs",
            ],
            "shared_lc_or_backpressure_cycle": [
                "public input tag/bp surface remains blocked",
                "Buffer FIFO pending/full while memory FIFO/request empty",
            ],
            "memory_ag_queue_loss_or_block": [
                "Memory_AG FIFO add/read/count conservation",
                "memory output valid/bp and RD request valid/ready",
            ],
            "v37_observer_conservation_epoch_error": [
                "closed before successor: the old 5-bit monitor truncated "
                "cloud-current FIFO count 32 to zero",
            ],
        },
        "cloud_rtl_authority_contract": {
            "rule_id":
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
            "repository": CLOUD_RTL_REPOSITORY,
            "branch": CLOUD_RTL_BRANCH,
            "approved_commit": CLOUD_RTL_COMMIT,
            "local_expected_provenance_hint": LOCAL_RTL_HINT,
            "runtime_success_predicate": False,
            "identity_collection_after_compile": "nonblocking",
            "actual_sha_mismatch_must_not_prevent_simulator_start": True,
            "gap_causal_cone_receipts": {
                "Buffer_AG_Idx_Queue.sv": {
                    "github_dom_lf_text_sha256":
                        CLOUD_BUFFER_AG_TEXT_SHA256,
                    "github_dom_lf_text_bytes": 9781,
                    "depth": 32,
                    "instance": "u_buf_ag_idx_queue",
                    "public_ports": [
                        "mse_buf_ag_tag_valid",
                        "mse_buf_ag_bp_post",
                    ],
                },
                "RD_Data_Channel.sv": {
                    "github_dom_lf_text_sha256":
                        CLOUD_RD_CHANNEL_TEXT_SHA256,
                    "github_dom_lf_text_bytes": 27590,
                    "rd_channel_queue_depth": 128,
                    "public_ports": [
                        "rd_data_chl_req_ready",
                        "rd_data_chl_data_ready",
                    ],
                },
                "FIFO.sv": {
                    "changed_in_cloud_compare": False,
                    "inherited_module_sha256": sha256(
                        ROOT / "NDP_copy01/rtl/utils/FIFO/FIFO.sv"
                    ),
                },
            },
            "claim_boundary": (
                "These receipts bind successor field widths and XMR scope. "
                "The real server compile return must still report actual "
                "identity; a mismatch is evidence, not a pre-simulation gate."
            ),
        },
        "causal_slice": {
            "kept": "full sum_s1 prefix needed to reproduce first divergence",
            "dropped": [],
            "reason": (
                "the first divergence occurs inside the first legal stage; no "
                "typed hardware checkpoint permits a shorter internal replay"
            ),
        },
        "config_changed": False,
        "timeout_changed": False,
        "backpressure_changed": False,
        "functional_rtl_modified": False,
    }
    manifest["release_gate_matrix"] = {
        "schema": "server-local-release-gate-impact-applicability-v1",
        "single_matrix": True,
        "core_always": {
            "gate_id": "package_identity_bootstrap_path_runtime_d",
            "applicable": True,
            "reason": "fresh diagnostic identity",
            "changed_surface": "package namespace and final ZIP",
            "evidence": [
                "final ZIP CRC/root/path/exact-set/per-file receipts",
                "sidecar and runtime-D-absent safe-runner positive",
            ],
            "blocking": True,
        },
        "runner": {
            "gate_id": "real_runner_compile_and_shared_finalizer",
            "applicable": True,
            "reason": "fresh runner adds one feature argv and return receipt",
            "changed_surface": "PREPARE_AND_RUN.sh",
            "evidence": [
                "safe compile/simulator positive",
                "EXIT and TERM shared-finalizer positives",
                "cloud/local RTL identity mismatch still reaches safe simulator",
            ],
            "blocking": True,
        },
        "package_local_hdl": {
            "gate_id": "actual_referenced_package_local_hdl",
            "applicable": True,
            "reason": "observer changed",
            "changed_surface": OBSERVER,
            "evidence": [
                "focused exact-section syntax/scope",
                "actual FIFO module/private-leaf and public-surface proof",
            ],
            "blocking": True,
        },
        "materialized_config": {
            "gate_id": "materialized_config_consumer_contract",
            "applicable": False,
            "reason": (
                "only fresh install namespace changes; identity-normalized "
                "SCA/SCA_D and all transaction/config bytes are reused"
            ),
            "changed_surface": "namespace strings only",
            "evidence": [
                "73-file byte equality",
                "identity-normalized SCA/SCA_D semantic equality",
            ],
            "blocking": False,
        },
        "diagnostic_semantics": {
            "gate_id": "observer_canonical_result_trust",
            "applicable": True,
            "reason": "new qualified observer predicate",
            "changed_surface": "LC supply conservation event predicate",
            "evidence": [
                "exact predicate trace",
                "feature four-way binding and actual-consumer negatives",
            ],
            "blocking": True,
        },
        "return_result": {
            "gate_id": "return_allowlist_and_result_conjunction",
            "applicable": True,
            "reason": "fresh feature must survive EXIT/TERM partial return",
            "changed_surface": "feature-specific observer binding receipt",
            "evidence": [
                "safe runner EXIT/TERM return",
                "manifest allowlist and result-gate validation",
            ],
            "blocking": True,
        },
        "record_only_warnings": [
            "frozen numeric/W3/golden are byte-equality receipts only",
            "unrelated RTL and report formatting are not rerun",
        ],
        "materialized_config_rules": {
            "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001":
                "not_applicable_exact_byte_equal",
            "CDA-CONFIG-BOUNDARY-MICROTRACE-001":
                "not_applicable_exact_byte_equal",
        },
    }
    manifest["predicate_trace_contract"] = {
        "rule_id": "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
        "exact_event_predicate": (
            "bq_add_wr || bq_add_rd || mq_add_wr || mq_add_rd || "
            "(req_valid && req_ready) || (surface != prev_surface)"
        ),
        "required_cases": [
            "each conjunct isolated",
            "boundary before/during/after",
            "simultaneous events",
            "stable level",
            "stage inactive/reset",
            "owner clock",
            "recent escaping edge",
        ],
        "execution": "local metadata/event trace only; no DUT",
    }
    manifest["applicable_rule_ids"] = sorted(
        set(manifest.get("applicable_rule_ids") or [])
        | {
            "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
            "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
            "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
            "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
            "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
            "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
            "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
            "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
        }
    )
    manifest["generation_provenance"].update(
        {
            "tool": "tools/build_gap_node0071_lc_supply_v38_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "trigger_return_sha256": TRIGGER_RETURN_SHA256,
            "trigger_analysis_sha256": sha256(TRIGGER_ANALYSIS),
            "numeric_payload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "functional_rtl_modified": False,
        }
    )
    manifest["path_length_budget"] = path_budget(package)
    manifest["files"] = file_records(package)
    write_json(path, manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    root = configure_source()
    package = root.extract_source(destination)
    source_records = file_records(package, exclude_manifest=False)
    frozen_before = file_records(package / "workload", exclude_manifest=False)
    root.rewrite_identity(package)
    upgrade_observer(package / OBSERVER)
    upgrade_runner(package / "PREPARE_AND_RUN.sh")
    (package / "README.md").write_text(
        "# GAP node0071 v40 LC/memory supply conservation diagnostic\n\n"
        f"Test ID: `{TEST_ID}`.\n\n"
        "This is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It preserves the "
        "frozen 73-file numeric/workload/config/golden payload, timeout, "
        "backpressure and functional RTL. It adds one clk_db-owned, "
        "qualified/rate-limited information-gain feature covering both MSE0 "
        "and MSE3 Buffer_AG/Memory_AG FIFO conservation and public request "
        "surfaces. Its widths are bound to cloud-authoritative RTL commit "
        f"`{CLOUD_RTL_COMMIT}` (Buffer_AG depth 32, RD queue depth 128); "
        "server-side identity collection is nonblocking after compile.\n\n"
        "Run exactly:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package)
    frozen_after = file_records(package / "workload", exclude_manifest=False)
    final_records = file_records(package, exclude_manifest=False)
    changed = {
        name for name in source_records
        if source_records[name] != final_records[name]
    }
    if set(source_records) != set(final_records):
        raise BuildError("package member exact-set changed")
    if changed != ALLOWED_CHANGED:
        raise BuildError(f"changed path allowlist differs: {sorted(changed)}")
    numeric_before = {
        name: value for name, value in frozen_before.items()
        if name not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    numeric_after = {
        name: value for name, value in frozen_after.items()
        if name not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    if len(numeric_after) != 73 or numeric_before != numeric_after:
        raise BuildError("frozen 73-file numeric/workload tree drifted")
    budget = path_budget(package)
    if (
        budget["measured_max_inner_suffix_chars"]
        > budget["max_inner_suffix_chars"]
        or budget["measured_max_inner_depth"] > budget["max_inner_depth"]
        or budget["measured_max_component_chars"]
        > budget["max_component_chars"]
        or budget["identity_repeated_in_inner_path"]
    ):
        raise BuildError(f"path budget failed: {budget}")
    return package, {
        "source_zip_sha256": SOURCE_SHA256,
        "changed_paths": sorted(changed),
        "frozen_numeric_workload_file_count": 73,
        "frozen_numeric_workload_tree_equal": True,
        "config_sca_semantics_byte_equal": (
            frozen_before["sca_cfg.json"]["sha256"]
            == frozen_after["sca_cfg.json"]["sha256"]
        ),
        "config_sca_d_semantics_byte_equal": (
            frozen_before["sca_cfg_D.json"]["sha256"]
            == frozen_after["sca_cfg_D.json"]["sha256"]
        ),
        "path_length_budget": budget,
    }


def build_zip(output_root: Path) -> dict[str, Any]:
    package, proof = build_directory(output_root)
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    digest = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="gap-v40-repeat-") as temporary:
        repeated, _ = build_directory(Path(temporary))
        repeated_zip = Path(temporary) / f"{INSTALL_NAME}.zip"
        deterministic_zip(repeated, repeated_zip, archive_root=INSTALL_NAME)
        if sha256(repeated_zip) != digest:
            raise BuildError("deterministic second ZIP differs")
        if file_records(repeated, exclude_manifest=False) != file_records(
            package, exclude_manifest=False
        ):
            raise BuildError("deterministic second tree differs")
    sidecar = Path(str(zip_path) + ".sha256")
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    return {
        "schema": "gap-node0071-lc-supply-conservation-v40-build-v1",
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
        "repeat_build": {
            "package_tree_equal": True,
            "zip_equal": True,
            "repeat_zip_sha256": digest,
        },
        "numeric_analysis_repeated": False,
        "workload_rebuilt": False,
        "config_semantics_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=PACKAGE_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    targets = (
        output_root / INSTALL_NAME,
        output_root / f"{INSTALL_NAME}.zip",
        output_root / f"{INSTALL_NAME}.zip.sha256",
        output_root / f"{INSTALL_NAME}.validation.json",
    )
    for path in targets:
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        result = build_zip(output_root)
        write_json(targets[-1], result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as error:
        import traceback

        traceback.print_exc()
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
