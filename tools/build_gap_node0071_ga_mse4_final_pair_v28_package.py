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
from tools import build_gap_node0071_prep_count_cause_v24_package as base


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v24_prep_count_cause_diag"
INSTALL_NAME = "r5_n71_gap_v28_ga_mse4_final_pair_diag"
TEST_ID = "r5-gap-node0071-v28-ga-mse4-final-pair-diagnostic"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = (
    "ad71f6d6ab75f0992505d9d4656c058aa4011776bfc9b7c1c14bd78ec9b428ab"
)
TRIGGER_RETURN_SHA256 = (
    "1ef3b3d7d091004784e46eb72c405fb25d010632d80a423ca99028089fcd43f4"
)
TRIGGER_ANALYSIS = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-gap-node0071-v24-return-analysis/report.json"
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


def configure_source() -> None:
    base.SOURCE_NAME = SOURCE_NAME
    base.INSTALL_NAME = INSTALL_NAME
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256
    base.configure_source()


def ga_prefix(slot: int) -> str:
    col = 0 if slot == 0 else 2
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_pair_group]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[return_obs_pair_slice]"
        ".u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group"
        f".GA_ROW_PE[return_obs_pair_row].GA_COL_PE[{col}].GA_PE"
        ".u_GA_PE"
    )


def mse4_prefix() -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_pair_group]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[return_obs_pair_slice]"
        ".u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine"
        ".MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel"
    )


def declarations() -> str:
    lines = [
        "    // v28: bounded GA-final-pipeline to MSE4 write-pair diagnostic.",
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]",
        "          [`GA_ROW_PE_NUM-1:0][1:0]",
        "          return_obs_pair_ga_ob_full_mon,",
        "          return_obs_pair_ga_normal_wr_req_mon,",
        "          return_obs_pair_ga_normal_wr_hs_mon,",
        "          return_obs_pair_ga_normal_rd_hs_mon;",
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]",
        "          return_obs_pair_m4_req_valid_mon,",
        "          return_obs_pair_m4_req_ready_mon,",
        "          return_obs_pair_m4_q_wr_mon,",
        "          return_obs_pair_m4_q_rd_mon,",
        "          return_obs_pair_m4_q_full_mon,",
        "          return_obs_pair_m4_q_empty_mon,",
        "          return_obs_pair_m4_buf_vld_mon,",
        "          return_obs_pair_m4_buf_ready_mon,",
        "          return_obs_pair_m4_buf_accept_mon,",
        "          return_obs_pair_m4_buf_last_mon,",
        "          return_obs_pair_m4_hold_vld_mon,",
        "          return_obs_pair_m4_prep_wr_mon,",
        "          return_obs_pair_m4_prep_rd_mon,",
        "          return_obs_pair_m4_prep_vld_mon,",
        "          return_obs_pair_m4_finish_mon;",
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]",
        "          [`MSE_REQ_CHL_NUM-1:0]",
        "          return_obs_pair_m4_ob_vld_in_mon,",
        "          return_obs_pair_m4_ob_wr_mon,",
        "          return_obs_pair_m4_ob_rd_mon,",
        "          return_obs_pair_m4_ob_vld_mon,",
        "          return_obs_pair_m4_ob_vld_o_mon,",
        "          return_obs_pair_m4_mem_ready_mon,",
        "          return_obs_pair_m4_last_mon;",
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]",
        "          [5:0] return_obs_pair_m4_prep_count_mon;",
        "",
        "    generate",
        "        for (genvar return_obs_pair_group = 0;",
        "             return_obs_pair_group < `SLICE_GROUP_SIZE;",
        "             return_obs_pair_group++) begin : RETURN_OBS_PAIR_GROUP_GEN",
        "            for (genvar return_obs_pair_slice = 0;",
        "                 return_obs_pair_slice < `SLICE_GROUP_NUM;",
        "                 return_obs_pair_slice++) begin : RETURN_OBS_PAIR_SLICE_GEN",
        "                for (genvar return_obs_pair_row = 0;",
        "                     return_obs_pair_row < `GA_ROW_PE_NUM;",
        "                     return_obs_pair_row++) begin : RETURN_OBS_PAIR_ROW_GEN",
    ]
    for slot in (0, 1):
        prefix = ga_prefix(slot)
        fields = {
            "return_obs_pair_ga_ob_full_mon":
                f"{prefix}.u_GA_PE_Outbuffer.ga_pe_outbuffer_full",
            "return_obs_pair_ga_normal_wr_req_mon":
                f"{prefix}.u_GA_PE_Outbuffer.normal_mode_wr_req",
            "return_obs_pair_ga_normal_wr_hs_mon":
                f"{prefix}.u_GA_PE_Outbuffer.normal_mode_wr_handshake",
            "return_obs_pair_ga_normal_rd_hs_mon":
                f"{prefix}.u_GA_PE_Outbuffer.normal_mode_rd_handshake",
        }
        for target, expression in fields.items():
            lines.extend(
                [
                    f"                    assign {target}",
                    "                        [return_obs_pair_group]"
                    "[return_obs_pair_slice]",
                    f"                        [return_obs_pair_row][{slot}] =",
                    f"                        {expression};",
                ]
            )
    lines.extend(
        [
            "                end",
        ]
    )
    prefix = mse4_prefix()
    scalar_fields = {
        "return_obs_pair_m4_req_valid_mon": f"{prefix}.wr_data_chl_req_valid",
        "return_obs_pair_m4_req_ready_mon": f"{prefix}.wr_data_chl_req_ready",
        "return_obs_pair_m4_q_wr_mon": f"{prefix}.wr_chl_queue_wr_en",
        "return_obs_pair_m4_q_rd_mon": f"{prefix}.wr_chl_queue_rd_en",
        "return_obs_pair_m4_q_full_mon": f"{prefix}.wr_chl_queue_full",
        "return_obs_pair_m4_q_empty_mon": f"{prefix}.wr_chl_queue_empty",
        "return_obs_pair_m4_buf_vld_mon": f"{prefix}.buf2mse_rvalid",
        "return_obs_pair_m4_buf_ready_mon": f"{prefix}.wr_data_chl_ready",
        "return_obs_pair_m4_buf_accept_mon":
            f"{prefix}.buf2mse_rvalid & {prefix}.wr_data_chl_ready",
        "return_obs_pair_m4_buf_last_mon": f"{prefix}.buf_ag_last_req_flag",
        "return_obs_pair_m4_hold_vld_mon":
            f"{prefix}.wr_data_chl_hold_data_vld",
        "return_obs_pair_m4_prep_wr_mon":
            f"{prefix}.wr_data_chl_prepared_data_wr_hs",
        "return_obs_pair_m4_prep_rd_mon":
            f"{prefix}.wr_data_chl_prepared_data_rd_hs",
        "return_obs_pair_m4_prep_vld_mon":
            f"{prefix}.wr_data_chl_prepared_data_vld",
        "return_obs_pair_m4_finish_mon":
            f"{prefix}.wr_data_chl_ob_last_data_arv_arr_flag",
        "return_obs_pair_m4_prep_count_mon":
            f"{prefix}.wr_data_chl_prepared_data_cnt",
    }
    for target, expression in scalar_fields.items():
        lines.extend(
            [
                f"                assign {target}",
                "                    [return_obs_pair_group]"
                "[return_obs_pair_slice] =",
                f"                    {expression};",
            ]
        )
    vector_fields = {
        "return_obs_pair_m4_ob_vld_in_mon": f"{prefix}.wr_chl_ob_vld_in",
        "return_obs_pair_m4_ob_wr_mon": f"{prefix}.wr_chl_ob_wr_hs",
        "return_obs_pair_m4_ob_rd_mon": f"{prefix}.wr_chl_ob_rd_hs",
        "return_obs_pair_m4_ob_vld_mon": f"{prefix}.wr_chl_ob_vld",
        "return_obs_pair_m4_ob_vld_o_mon": f"{prefix}.wr_chl_ob_vld_o",
        "return_obs_pair_m4_mem_ready_mon": f"{prefix}.mem2mse_wdata_ready",
        "return_obs_pair_m4_last_mon":
            f"{prefix}.wr_data_chl_ob_last_data_flag",
    }
    for target, expression in vector_fields.items():
        lines.extend(
            [
                f"                assign {target}",
                "                    [return_obs_pair_group]"
                "[return_obs_pair_slice] =",
                f"                    {expression};",
            ]
        )
    lines.extend(
        [
            "            end",
            "        end",
            "    endgenerate",
            "",
            "    bit return_obs_pair_enabled;",
            "    int return_obs_pair_limit;",
            "    int return_obs_pair_emit_count;",
            "    longint unsigned return_obs_pair_ga_accept_count;",
            "    longint unsigned return_obs_pair_ga_p0_retire_count;",
            "    longint unsigned return_obs_pair_ga_wr_req_count;",
            "    longint unsigned return_obs_pair_ga_wr_hs_count;",
            "    longint unsigned return_obs_pair_ga_rd_hs_count;",
            "    longint unsigned return_obs_pair_m4_req_accept_count;",
            "    longint unsigned return_obs_pair_m4_q_wr_count;",
            "    longint unsigned return_obs_pair_m4_q_rd_count;",
            "    longint unsigned return_obs_pair_m4_buf_accept_count;",
            "    longint unsigned return_obs_pair_m4_prep_wr_count;",
            "    longint unsigned return_obs_pair_m4_prep_rd_count;",
            "    longint unsigned return_obs_pair_m4_ob_wr_count [0:1];",
            "    longint unsigned return_obs_pair_m4_ob_rd_count [0:1];",
            "    longint unsigned return_obs_pair_last_ga_accept;",
            "    longint unsigned return_obs_pair_last_ga_retire;",
            "    longint unsigned return_obs_pair_last_ga_wr;",
            "    longint unsigned return_obs_pair_last_m4_req;",
            "    longint unsigned return_obs_pair_last_m4_buf;",
            "    longint unsigned return_obs_pair_last_m4_ob_wr;",
            "    longint unsigned return_obs_pair_last_m4_ob_rd;",
            "",
            "    task automatic return_obs_pair_reset;",
            "        begin",
            "            return_obs_pair_emit_count = 0;",
            "            return_obs_pair_ga_accept_count = 0;",
            "            return_obs_pair_ga_p0_retire_count = 0;",
            "            return_obs_pair_ga_wr_req_count = 0;",
            "            return_obs_pair_ga_wr_hs_count = 0;",
            "            return_obs_pair_ga_rd_hs_count = 0;",
            "            return_obs_pair_m4_req_accept_count = 0;",
            "            return_obs_pair_m4_q_wr_count = 0;",
            "            return_obs_pair_m4_q_rd_count = 0;",
            "            return_obs_pair_m4_buf_accept_count = 0;",
            "            return_obs_pair_m4_prep_wr_count = 0;",
            "            return_obs_pair_m4_prep_rd_count = 0;",
            "            return_obs_pair_last_ga_accept = 0;",
            "            return_obs_pair_last_ga_retire = 0;",
            "            return_obs_pair_last_ga_wr = 0;",
            "            return_obs_pair_last_m4_req = 0;",
            "            return_obs_pair_last_m4_buf = 0;",
            "            return_obs_pair_last_m4_ob_wr = 0;",
            "            return_obs_pair_last_m4_ob_rd = 0;",
            "            for (int pair_ch = 0; pair_ch < 2; pair_ch++) begin",
            "                return_obs_pair_m4_ob_wr_count[pair_ch] = 0;",
            "                return_obs_pair_m4_ob_rd_count[pair_ch] = 0;",
            "            end",
            "        end",
            "    endtask",
            "",
        ]
    )
    return "\n".join(lines)


SUMMARY = r'''                    if (return_obs_pair_enabled) begin
                        $fdisplay(
                            return_obs_fd,
                            "%0t | GA_MSE4_FINAL_PAIR_COUNTS_V1 | event=%s ga_accept=%0d ga_p0_retire=%0d ga_wr_req=%0d ga_wr_hs=%0d ga_rd_hs=%0d m4_req_accept=%0d m4_q_wr=%0d m4_q_rd=%0d m4_buf_accept=%0d m4_prep_wr=%0d m4_prep_rd=%0d m4_ob_wr=%0d/%0d m4_ob_rd=%0d/%0d records=%0d limit=%0d",
                            $time, event_name,
                            return_obs_pair_ga_accept_count,
                            return_obs_pair_ga_p0_retire_count,
                            return_obs_pair_ga_wr_req_count,
                            return_obs_pair_ga_wr_hs_count,
                            return_obs_pair_ga_rd_hs_count,
                            return_obs_pair_m4_req_accept_count,
                            return_obs_pair_m4_q_wr_count,
                            return_obs_pair_m4_q_rd_count,
                            return_obs_pair_m4_buf_accept_count,
                            return_obs_pair_m4_prep_wr_count,
                            return_obs_pair_m4_prep_rd_count,
                            return_obs_pair_m4_ob_wr_count[0],
                            return_obs_pair_m4_ob_wr_count[1],
                            return_obs_pair_m4_ob_rd_count[0],
                            return_obs_pair_m4_ob_rd_count[1],
                            return_obs_pair_emit_count,
                            return_obs_pair_limit
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | GA_MSE4_FINAL_PAIR_STATE_V1 | event=%s ga_p0_valid=0x%0h ga_p0_bp=0x%0h ga_result_tag=0x%0h ga_ob_full=0x%0h ga_ob_count=0x%0h m4_req_vld=%0b m4_req_ready=%0b m4_q_full=%0b m4_q_empty=%0b m4_buf_vld=%0b m4_buf_ready=%0b m4_buf_last=%0b m4_hold=%0b m4_prep_vld=%0b m4_prep_count=%0d m4_ob_vld=0x%0h m4_ob_vld_o=0x%0h m4_mem_ready=0x%0h m4_last=0x%0h finish=%0b",
                            $time, event_name,
                            return_obs_ga_p0_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_ga_p0_bp_post_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_ga_result_tag_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_ga_ob_full_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_ga_ob_count_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_m4_req_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_m4_req_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_m4_q_full_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_m4_q_empty_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_m4_buf_vld_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_m4_buf_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_m4_buf_last_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_m4_hold_vld_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_m4_prep_vld_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_m4_prep_count_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_m4_ob_vld_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_m4_ob_vld_o_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_m4_mem_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_m4_last_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pair_m4_finish_mon[return_obs_group_id][return_obs_local_slice_id]
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | GA_MSE4_FINAL_PAIR_WITNESS_V1 | event=%s last_ga_accept=%0d last_ga_retire=%0d last_ga_wr=%0d last_m4_req=%0d last_m4_buf=%0d last_m4_ob_wr=%0d last_m4_ob_rd=%0d",
                            $time, event_name,
                            return_obs_pair_last_ga_accept,
                            return_obs_pair_last_ga_retire,
                            return_obs_pair_last_ga_wr,
                            return_obs_pair_last_m4_req,
                            return_obs_pair_last_m4_buf,
                            return_obs_pair_last_m4_ob_wr,
                            return_obs_pair_last_m4_ob_rd
                        );
                    end
'''


SAMPLER = r'''
    // v28 qualified events only; stable levels are snapshots, not progress.
    always @(posedge u_NDP_Top_new.clk_sg) begin
        if (
            u_NDP_Top_new.rst_n_sg &&
            return_obs_enabled &&
            return_obs_pair_enabled &&
            return_obs_active &&
            return_obs_fd != 0
        ) begin
            for (int pair_row = 0; pair_row < `GA_ROW_PE_NUM; pair_row++) begin
                for (int pair_slot = 0; pair_slot < 2; pair_slot++) begin
                    bit pair_ga_accept;
                    bit pair_ga_retire;
                    bit pair_ga_wr_req;
                    bit pair_ga_wr_hs;
                    bit pair_ga_rd_hs;
                    pair_ga_accept =
                        return_obs_ga_p0_enable_mon[return_obs_group_id][return_obs_local_slice_id][pair_row][pair_slot] &&
                        return_obs_ga_input_valid_mon[return_obs_group_id][return_obs_local_slice_id][pair_row][pair_slot];
                    pair_ga_retire =
                        return_obs_ga_p0_valid_mon[return_obs_group_id][return_obs_local_slice_id][pair_row][pair_slot] &&
                        return_obs_ga_p0_bp_post_mon[return_obs_group_id][return_obs_local_slice_id][pair_row][pair_slot];
                    pair_ga_wr_req =
                        return_obs_pair_ga_normal_wr_req_mon[return_obs_group_id][return_obs_local_slice_id][pair_row][pair_slot];
                    pair_ga_wr_hs =
                        return_obs_pair_ga_normal_wr_hs_mon[return_obs_group_id][return_obs_local_slice_id][pair_row][pair_slot];
                    pair_ga_rd_hs =
                        return_obs_pair_ga_normal_rd_hs_mon[return_obs_group_id][return_obs_local_slice_id][pair_row][pair_slot];
                    if (pair_ga_accept) begin
                        return_obs_pair_ga_accept_count++;
                        return_obs_pair_last_ga_accept = return_obs_sg_clock_edge_count;
                    end
                    if (pair_ga_retire) begin
                        return_obs_pair_ga_p0_retire_count++;
                        return_obs_pair_last_ga_retire = return_obs_sg_clock_edge_count;
                    end
                    if (pair_ga_wr_req)
                        return_obs_pair_ga_wr_req_count++;
                    if (pair_ga_wr_hs) begin
                        return_obs_pair_ga_wr_hs_count++;
                        return_obs_pair_last_ga_wr = return_obs_sg_clock_edge_count;
                    end
                    if (pair_ga_rd_hs)
                        return_obs_pair_ga_rd_hs_count++;
                    if (
                        (pair_ga_accept || pair_ga_retire || pair_ga_wr_hs ||
                         pair_ga_rd_hs) &&
                        return_obs_pair_emit_count < return_obs_pair_limit
                    ) begin
                        return_obs_pair_emit_count++;
                        $fdisplay(
                            return_obs_fd,
                            "%0t | GA_MSE4_FINAL_PAIR_GA_EVENT_V1 | n=%0d sg_edge=%0d pe=%0d%0d accept=%0b p0_retire=%0b p0_valid=%0b p0_bp=%0b result_tag=0x%0h wr_req=%0b wr_hs=%0b rd_hs=%0b ob_full=%0b ob_count=%0d",
                            $time, return_obs_pair_emit_count,
                            return_obs_sg_clock_edge_count,
                            pair_row, (pair_slot == 0 ? 0 : 2),
                            pair_ga_accept, pair_ga_retire,
                            return_obs_ga_p0_valid_mon[return_obs_group_id][return_obs_local_slice_id][pair_row][pair_slot],
                            return_obs_ga_p0_bp_post_mon[return_obs_group_id][return_obs_local_slice_id][pair_row][pair_slot],
                            return_obs_ga_result_tag_mon[return_obs_group_id][return_obs_local_slice_id][pair_row][pair_slot],
                            pair_ga_wr_req, pair_ga_wr_hs, pair_ga_rd_hs,
                            return_obs_pair_ga_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][pair_row][pair_slot],
                            return_obs_ga_ob_count_mon[return_obs_group_id][return_obs_local_slice_id][pair_row][pair_slot]
                        );
                    end
                end
            end
            begin
                bit pair_m4_req_accept;
                bit pair_m4_event;
                pair_m4_req_accept =
                    return_obs_pair_m4_req_valid_mon[return_obs_group_id][return_obs_local_slice_id] &&
                    return_obs_pair_m4_req_ready_mon[return_obs_group_id][return_obs_local_slice_id];
                pair_m4_event =
                    pair_m4_req_accept ||
                    return_obs_pair_m4_q_wr_mon[return_obs_group_id][return_obs_local_slice_id] ||
                    return_obs_pair_m4_q_rd_mon[return_obs_group_id][return_obs_local_slice_id] ||
                    return_obs_pair_m4_buf_accept_mon[return_obs_group_id][return_obs_local_slice_id] ||
                    return_obs_pair_m4_prep_wr_mon[return_obs_group_id][return_obs_local_slice_id] ||
                    return_obs_pair_m4_prep_rd_mon[return_obs_group_id][return_obs_local_slice_id] ||
                    (|return_obs_pair_m4_ob_wr_mon[return_obs_group_id][return_obs_local_slice_id]) ||
                    (|return_obs_pair_m4_ob_rd_mon[return_obs_group_id][return_obs_local_slice_id]) ||
                    return_obs_pair_m4_finish_mon[return_obs_group_id][return_obs_local_slice_id];
                if (pair_m4_req_accept) begin
                    return_obs_pair_m4_req_accept_count++;
                    return_obs_pair_last_m4_req = return_obs_sg_clock_edge_count;
                end
                if (return_obs_pair_m4_q_wr_mon[return_obs_group_id][return_obs_local_slice_id])
                    return_obs_pair_m4_q_wr_count++;
                if (return_obs_pair_m4_q_rd_mon[return_obs_group_id][return_obs_local_slice_id])
                    return_obs_pair_m4_q_rd_count++;
                if (return_obs_pair_m4_buf_accept_mon[return_obs_group_id][return_obs_local_slice_id]) begin
                    return_obs_pair_m4_buf_accept_count++;
                    return_obs_pair_last_m4_buf = return_obs_sg_clock_edge_count;
                end
                if (return_obs_pair_m4_prep_wr_mon[return_obs_group_id][return_obs_local_slice_id])
                    return_obs_pair_m4_prep_wr_count++;
                if (return_obs_pair_m4_prep_rd_mon[return_obs_group_id][return_obs_local_slice_id])
                    return_obs_pair_m4_prep_rd_count++;
                for (int pair_ch = 0; pair_ch < 2; pair_ch++) begin
                    if (return_obs_pair_m4_ob_wr_mon[return_obs_group_id][return_obs_local_slice_id][pair_ch]) begin
                        return_obs_pair_m4_ob_wr_count[pair_ch]++;
                        return_obs_pair_last_m4_ob_wr = return_obs_sg_clock_edge_count;
                    end
                    if (return_obs_pair_m4_ob_rd_mon[return_obs_group_id][return_obs_local_slice_id][pair_ch]) begin
                        return_obs_pair_m4_ob_rd_count[pair_ch]++;
                        return_obs_pair_last_m4_ob_rd = return_obs_sg_clock_edge_count;
                    end
                end
                if (
                    pair_m4_event &&
                    return_obs_pair_emit_count < return_obs_pair_limit
                ) begin
                    return_obs_pair_emit_count++;
                    $fdisplay(
                        return_obs_fd,
                        "%0t | GA_MSE4_FINAL_PAIR_M4_EVENT_V1 | n=%0d sg_edge=%0d req_accept=%0b req_vld=%0b req_ready=%0b q_wr=%0b q_rd=%0b q_full=%0b q_empty=%0b buf_accept=%0b buf_vld=%0b buf_ready=%0b buf_last=%0b hold=%0b prep_wr=%0b prep_rd=%0b prep_vld=%0b prep_count=%0d ob_vld_in=0x%0h ob_wr=0x%0h ob_rd=0x%0h ob_vld=0x%0h ob_vld_o=0x%0h mem_ready=0x%0h last=0x%0h finish=%0b",
                        $time, return_obs_pair_emit_count,
                        return_obs_sg_clock_edge_count,
                        pair_m4_req_accept,
                        return_obs_pair_m4_req_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_req_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_q_wr_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_q_rd_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_q_full_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_q_empty_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_buf_accept_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_buf_vld_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_buf_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_buf_last_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_hold_vld_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_prep_wr_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_prep_rd_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_prep_vld_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_prep_count_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_ob_vld_in_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_ob_wr_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_ob_rd_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_ob_vld_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_ob_vld_o_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_mem_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_last_mon[return_obs_group_id][return_obs_local_slice_id],
                        return_obs_pair_m4_finish_mon[return_obs_group_id][return_obs_local_slice_id]
                    );
                end
            end
            $fflush(return_obs_fd);
        end
    end

'''


def upgrade_observer(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    bit return_obs_enabled;\n",
        declarations() + "    bit return_obs_enabled;\n",
        "pair declarations",
    )
    text = replace_once(
        text,
        '        return_obs_pc_enabled =\n'
        '            $test$plusargs("RETURN_OBS_PREP_COUNT_CAUSE");\n',
        '        return_obs_pc_enabled =\n'
        '            $test$plusargs("RETURN_OBS_PREP_COUNT_CAUSE");\n'
        '        return_obs_pair_enabled =\n'
        '            $test$plusargs("RETURN_OBS_GA_MSE4_FINAL_PAIR");\n',
        "pair feature plusarg",
    )
    text = replace_once(
        text,
        "        return_obs_pc_limit = 512;\n",
        "        return_obs_pc_limit = 512;\n"
        "        return_obs_pair_limit = 512;\n",
        "pair default limit",
    )
    text = replace_once(
        text,
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_FILE=%s",\n',
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=%d",\n'
        '                return_obs_pair_limit\n'
        '            );\n'
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_FILE=%s",\n',
        "pair limit plusarg",
    )
    text = text.replace(
        "        return_obs_pc_reset();\n",
        "        return_obs_pc_reset();\n"
        "        return_obs_pair_reset();\n",
    )
    if text.count("return_obs_pair_reset();") != 2:
        raise BuildError("pair reset call count differs")
    text = replace_once(
        text,
        "                    end\n"
        "                end\n"
        "                $fflush(return_obs_fd);\n"
        "            end\n"
        "        end\n"
        "    endtask\n\n"
        "    task automatic return_obs_write_internal_state",
        "                    end\n"
        + SUMMARY
        + "                end\n"
        "                $fflush(return_obs_fd);\n"
        "            end\n"
        "        end\n"
        "    endtask\n\n"
        "    task automatic return_obs_write_internal_state",
        "pair summary",
    )
    text = replace_once(
        text,
        "prep_count_cause=%0d prep_count_cause_limit=%0d",
        "prep_count_cause=%0d prep_count_cause_limit=%0d "
        "ga_mse4_final_pair=%0d ga_mse4_final_pair_limit=%0d",
        "pair time0 format",
    )
    text = replace_once(
        text,
        "                        return_obs_pc_enabled,\n"
        "                        return_obs_pc_limit\n",
        "                        return_obs_pc_enabled,\n"
        "                        return_obs_pc_limit,\n"
        "                        return_obs_pair_enabled,\n"
        "                        return_obs_pair_limit\n",
        "pair time0 args",
    )
    text = replace_once(
        text,
        "    final begin\n",
        SAMPLER + "    final begin\n",
        "pair sampler",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def upgrade_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "  +RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512\n",
        "  +RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512\n"
        "  +RETURN_OBS_GA_MSE4_FINAL_PAIR\n"
        "  +RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512\n",
        "runner pair plusargs",
    )
    text = replace_once(
        text,
        "+RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512 +RETURN_OBS_FILE=",
        "+RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512 "
        "+RETURN_OBS_GA_MSE4_FINAL_PAIR "
        "+RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512 +RETURN_OBS_FILE=",
        "runner pair command receipt",
    )
    marker = (
        "  if [ \"$prep_count_cause_ok\" = true ]; then\n"
        "    printf 'prep_count_cause_enabled=true\\n"
        "prep_count_cause_limit=512\\n"
        "prep_count_cause_records_returned=true\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  else\n"
        "    printf 'prep_count_cause_enabled=false\\n"
        "prep_count_cause_limit=UNKNOWN\\n"
        "prep_count_cause_records_returned=false\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  fi\n"
    )
    addition = marker + (
        "  if [ \"$observer_ok\" = true ] && "
        "grep -Fq 'ga_mse4_final_pair=1' \"$observer_log\" && "
        "grep -Fq 'ga_mse4_final_pair_limit=512' \"$observer_log\" && "
        "grep -Fq 'GA_MSE4_FINAL_PAIR_COUNTS_V1' \"$observer_log\" && "
        "grep -Fq 'GA_MSE4_FINAL_PAIR_STATE_V1' \"$observer_log\" && "
        "grep -Fq 'GA_MSE4_FINAL_PAIR_WITNESS_V1' \"$observer_log\"; then\n"
        "    ga_mse4_pair_ok=true\n"
        "  else\n"
        "    ga_mse4_pair_ok=false\n"
        "  fi\n"
        "  if [ \"$ga_mse4_pair_ok\" = true ]; then\n"
        "    printf 'ga_mse4_final_pair_enabled=true\\n"
        "ga_mse4_final_pair_limit=512\\n"
        "ga_mse4_final_pair_records_returned=true\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  else\n"
        "    printf 'ga_mse4_final_pair_enabled=false\\n"
        "ga_mse4_final_pair_limit=UNKNOWN\\n"
        "ga_mse4_final_pair_records_returned=false\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  fi\n"
    )
    text = replace_once(text, marker, addition, "runner pair receipt")
    path.write_text(text, encoding="utf-8", newline="\n")


def current_receipts(source_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for item in source_manifest[
        "final_zip_rule_self_audit_contract"
    ]["read_receipt"]:
        receipt = dict(item)
        receipt["sha256"] = sha256(ROOT / receipt["path"])
        receipt["current_match"] = True
        receipts.append(receipt)
    return receipts


def update_manifest(package: Path, source_manifest: dict[str, Any]) -> None:
    manifest = base.base.base.replace_identity(source_manifest)
    receipts = current_receipts(source_manifest)
    receipt_by_path = {item["path"]: item["sha256"] for item in receipts}
    manifest.update(
        {
            "schema": "gap-node0071-ga-mse4-final-pair-diagnostic-package-v28",
            "test_id": TEST_ID,
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "read-only final GA int32 pipeline/outbuffer retirement to "
                "MSE4 request, prepared-data, output-buffer and finish pairing"
            ),
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_SHA256,
            "quarantines_package_sha256": SOURCE_SHA256,
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
    applicable = list(audit["applicable_rule_ids"])
    hdl_rule = (
        "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001"
    )
    if hdl_rule not in applicable:
        applicable.append(hdl_rule)
    audit.update(
        {
            "read_receipt": receipts,
            "applicable_rule_ids": applicable,
            "all_current_match": True,
            "plan_sha256_mutable_provenance_only":
                sha256(ROOT / ".agents/plan.md"),
            "final_zip_rule_self_audit_pass":
                "PENDING_EXTERNAL_RELEASE_REPORT",
        }
    )
    rules = manifest["rule_receipts"]
    for path, digest in receipt_by_path.items():
        if path.endswith("GAP_probe_v7_validator_rules.md"):
            rules["gap_probe_rule_sha256"] = digest
        elif path.endswith("GAP_int32_mac_bypass_rules.md"):
            rules["gap_int32_rule_sha256"] = digest
        elif "rules/" in path or "rules\\" in path:
            if digest == sha256(ROOT / ".agents/rules/服务器测试包生成规则.md"):
                rules["server_rule_sha256"] = digest
            elif digest == sha256(ROOT / ".agents/rules/生成前必读索引.md"):
                rules["generation_index_sha256"] = digest
    rules["current_match"] = True
    rules["plan_sha256_mutable_provenance_only"] = sha256(
        ROOT / ".agents/plan.md"
    )
    manifest["post_generation_rule_drift"] = {
        "content_neutral": False,
        "current_server_rule_sha256": sha256(
            ROOT / ".agents/rules/服务器测试包生成规则.md"
        ),
        "resolution": (
            "fresh v28 rebuild binds the narrowed package-local HDL "
            "syntax/scope positive-control rule in exact final bytes"
        ),
    }
    manifest["ga_mse4_final_pair_diagnostic_contract"] = {
        "trigger_return_sha256": TRIGGER_RETURN_SHA256,
        "trigger_analysis_sha256": sha256(TRIGGER_ANALYSIS),
        "last_proven_good": (
            "MSE0/MSE3 prepared paths symmetric; GA outbuffer accepted 32 "
            "outputs and MSE4 retired 8 write-data beats per channel"
        ),
        "first_divergence": (
            "FINAL_GA_PIPELINE_TO_MSE4_NINTH_REQUEST_WRITE_DATA_PAIR_PENDING"
        ),
        "runtime_enable": "+RETURN_OBS_GA_MSE4_FINAL_PAIR",
        "runtime_limit": "+RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512",
        "time0_marker":
            "ga_mse4_final_pair=1 ga_mse4_final_pair_limit=512",
        "records": [
            "GA_MSE4_FINAL_PAIR_GA_EVENT_V1",
            "GA_MSE4_FINAL_PAIR_M4_EVENT_V1",
            "GA_MSE4_FINAL_PAIR_COUNTS_V1",
            "GA_MSE4_FINAL_PAIR_STATE_V1",
            "GA_MSE4_FINAL_PAIR_WITNESS_V1",
        ],
        "clock": "clk_sg",
        "qualified_events": [
            "GA input accepted into int32 pipeline0",
            "GA pipeline0 valid accepted by downstream",
            "GA normal-mode outbuffer write/read handshake",
            "MSE4 request valid and ready",
            "MSE4 metadata queue write/read",
            "MSE4 buffer-data valid and ready",
            "MSE4 prepared-data write/read",
            "MSE4 write outbuffer write/read",
            "MSE4 last-data finish pulse",
        ],
        "state_only": [
            "stable valid/ready/full/empty level",
            "stable tag, count and last level",
            "stable outstanding level",
        ],
        "stable_level_counts_as_progress": False,
        "read_only": True,
        "drives_dut": False,
        "changes_timeout": False,
        "hdl_positive_control_scope": (
            "only v28 declarations/XMR assignments/reset-update/use leaves "
            "that feed GA_MSE4_FINAL_PAIR_* required records"
        ),
    }
    feature = manifest["diagnostic_feature_runtime_enable_contract"]
    feature["features"] = list(feature.get("features", [])) + [
        {
            "name": "ga_mse4_final_pair",
            "runtime_enable": "+RETURN_OBS_GA_MSE4_FINAL_PAIR",
            "runtime_limit": "+RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512",
            "time0_marker":
                "ga_mse4_final_pair=1 ga_mse4_final_pair_limit=512",
            "returned_binding_receipt": "evidence/observer_binding.txt",
            "return_target": "runs/return_observer.log",
            "zero_when_disabled": "DISABLED_INSTRUMENTATION_ZERO",
        }
    ]
    manifest["generation_provenance"].update(
        {
            "tool":
                "tools/build_gap_node0071_ga_mse4_final_pair_v28_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "trigger_return_sha256": TRIGGER_RETURN_SHA256,
            "numeric_payload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change": (
                "fresh identity plus bounded read-only GA final pipeline/"
                "outbuffer to MSE4 request/write-data pairing observer"
            ),
        }
    )
    manifest["files"] = file_records(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_source()
    package = base.base.base.extract_source(destination)
    source_manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    source_records = file_records(package, exclude_manifest=False)
    numeric_before = {
        path: record
        for path, record in file_records(
            package / "workload", exclude_manifest=False
        ).items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    base.base.base.rewrite_identity(package)
    upgrade_observer(package / OBSERVER)
    upgrade_runner(package / "PREPARE_AND_RUN.sh")
    (package / "README.md").write_text(
        "# GAP node0071 v28 GA-to-MSE4 final-pair diagnostic\n\n"
        f"Test ID: `{TEST_ID}`.\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It preserves "
        "the 73 frozen numeric/workload files, config, golden, execplan and "
        "functional RTL semantics. It adds bounded read-only qualified "
        "evidence across the final GA int32 pipeline/outbuffer and MSE4 "
        "request/write-data pairing boundary.\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package, source_manifest)
    numeric_after = {
        path: record
        for path, record in file_records(
            package / "workload", exclude_manifest=False
        ).items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    if numeric_before != numeric_after or len(numeric_after) != 73:
        raise BuildError("frozen 73-file numeric/workload tree drifted")
    final_records = file_records(package, exclude_manifest=False)
    if set(source_records) != set(final_records):
        raise BuildError("package relative file set changed")
    changed = {
        path for path in source_records
        if source_records[path] != final_records[path]
    }
    if changed != ALLOWED_CHANGED:
        raise BuildError(f"changed path set differs: {sorted(changed)}")
    frozen = sorted(set(source_records) - ALLOWED_CHANGED)
    return package, {
        "source_v24_zip_sha256": SOURCE_SHA256,
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
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v28-repeat-"
    ) as temp:
        repeated, _ = build_directory(Path(temp))
        repeated_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        deterministic_zip(repeated, repeated_zip, archive_root=INSTALL_NAME)
        if sha256(repeated_zip) != digest:
            raise BuildError("repeat ZIP differs")
        if file_records(repeated, exclude_manifest=False) != tree:
            raise BuildError("repeat package tree differs")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": digest,
    }


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
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        result = {
            "schema": "gap-node0071-ga-mse4-final-pair-v28-build-v1",
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
