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
from tools.gap_node0071_package_observer_guard import (
    observer_precompile_receipt,
)
from tools import build_gap_node0071_v13_buffer_to_ga_diag_package as base


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v17_stage1_flow_diag"
INSTALL_NAME = "r5_n71_gap_v18_bp_pre_factor_diag"
TEST_ID = "r5-gap-node0071-v18-bp-pre-factor-observability"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = (
    "d4ff6ba01f96626de2977bbf3ba5216644255b948b872b800c6976ddf3d227d6"
)
TRIGGER_RETURN_SHA256 = (
    "9c8f25bd7f889d047487e7f5687808fefe4525fce401dbc408a70484713c66dd"
)
TRIGGER_ANALYSIS_SHA256 = (
    "79380595960c61cf6610d5ebd5968a51a49c1ac688a1b780af5c75a16d67faca"
)
TRIGGER_TASK_RECORD_SHA256 = (
    "85ee8dd46441affe423571a09572f37954177ab59e8b6e8eecf0b5169cdb08e0"
)
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
NEW_RULE_ID = "CDA-GAP-HANDSHAKE-CONJUNCTION-FACTOR-OBSERVABILITY-001"
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    OBSERVER_RELATIVE,
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
        raise BuildError(f"observer/runner marker differs: {label}")
    return text.replace(old, new, 1)


def configure_source() -> None:
    base.SOURCE_NAME = SOURCE_NAME
    base.INSTALL_NAME = INSTALL_NAME
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256


def _xmr_prefix(mse: int) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_bp_group]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[return_obs_bp_slice]"
        ".u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine"
        f".MSE_INST[{mse}].RD_MSE.u_Memory_RD_Stream_Engine"
    )


def _factor_assignments() -> str:
    lines = [
        "    generate",
        "        for (genvar return_obs_bp_group = 0;",
        "             return_obs_bp_group < `SLICE_GROUP_SIZE;",
        "             return_obs_bp_group++) begin : RETURN_OBS_BP_GROUP_GEN",
        "            for (genvar return_obs_bp_slice = 0;",
        "                 return_obs_bp_slice < `SLICE_GROUP_NUM;",
        "                 return_obs_bp_slice++) begin : RETURN_OBS_BP_SLICE_GEN",
    ]
    for slot, mse in enumerate((0, 3)):
        prefix = _xmr_prefix(mse)
        assignments = {
            "return_obs_bp_pre_mon":
                f"{prefix}.u_WR_Buffer_AG.buf_ag_bp_pre",
            "return_obs_bp_ob_full_mon":
                f"{prefix}.u_WR_Buffer_AG.buf_ag_ob_full",
            "return_obs_bp_data_ready_mon":
                f"{prefix}.u_RD_Data_Channel.rd_data_chl_data_ready",
            "return_obs_bp_data_vld_mon":
                f"{prefix}.u_RD_Data_Channel.rd_data_chl_data_vld",
            "return_obs_bp_prepared_count_mon":
                f"{prefix}.u_RD_Data_Channel.rd_data_chl_prepared_data_cnt",
            "return_obs_bp_rd_ob_full_mon":
                f"{prefix}.u_RD_Data_Channel.rd_data_chl_ob_full",
            "return_obs_bp_barrier_mon":
                f"{prefix}.nse2mse_req_barrier",
            "return_obs_bp_q_rd_mon":
                f"{prefix}.u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_rd_en",
            "return_obs_bp_ob_wr_mon":
                f"{prefix}.u_WR_Buffer_AG.buf_ag_ob_wr_en",
            "return_obs_bp_queue_occupancy_mon":
                f"{prefix}.u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.fifo_counter",
        }
        for signal, expression in assignments.items():
            lines.extend(
                [
                    f"                assign {signal}[return_obs_bp_group]"
                    f"[return_obs_bp_slice][{slot}] =",
                    f"                    {expression};",
                ]
            )
    lines.extend(["            end", "        end", "    endgenerate", ""])
    return "\n".join(lines)


def _factor_declarations() -> str:
    return (
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]\n"
        "          return_obs_bp_pre_mon, return_obs_bp_ob_full_mon,\n"
        "          return_obs_bp_data_ready_mon, return_obs_bp_data_vld_mon,\n"
        "          return_obs_bp_rd_ob_full_mon, return_obs_bp_barrier_mon,\n"
        "          return_obs_bp_q_rd_mon, return_obs_bp_ob_wr_mon;\n"
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [1:0][7:0] return_obs_bp_prepared_count_mon;\n"
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [1:0][7:0] return_obs_bp_queue_occupancy_mon;\n\n"
    )


def _factor_counter_declarations() -> str:
    return (
        "    bit return_obs_bp_factor_enabled;\n"
        "    int return_obs_bp_factor_limit;\n"
        "    int return_obs_bp_factor_emit_count;\n"
        "    bit return_obs_bp_started [0:1];\n"
        "    bit return_obs_bp_prev [0:1][0:5];\n"
        "    logic [7:0] return_obs_bp_prev_prepared_count [0:1];\n"
        "    longint unsigned return_obs_bp_edge_count [0:1][0:5];\n"
        "    longint unsigned return_obs_bp_prepared_change_count [0:1];\n"
        "    longint unsigned return_obs_bp_first_block [0:1][0:4];\n"
        "    longint unsigned return_obs_bp_last_block [0:1][0:4];\n"
        "    bit return_obs_bp_block_seen [0:1][0:4];\n"
        "    longint unsigned return_obs_bp_window_start_edge;\n"
        "    longint unsigned return_obs_bp_window_last_edge;\n"
    )


def _factor_summary_records() -> str:
    return (
        "                    if (return_obs_bp_factor_enabled) begin\n"
        "                        $fdisplay(\n"
        "                            return_obs_fd,\n"
        "                            \"%0t | BP_PRE_FACTOR_COUNTS_V1 | event=%s bp_edge=%0d/%0d ob_full_edge=%0d/%0d ready_edge=%0d/%0d vld_edge=%0d/%0d prep_change=%0d/%0d rd_ob_full_edge=%0d/%0d barrier_edge=%0d/%0d q_rd=%0d/%0d ob_wr=%0d/%0d edge_records=%0d limit=%0d\",\n"
        "                            $time, event_name,\n"
        "                            return_obs_bp_edge_count[0][0], return_obs_bp_edge_count[1][0],\n"
        "                            return_obs_bp_edge_count[0][1], return_obs_bp_edge_count[1][1],\n"
        "                            return_obs_bp_edge_count[0][2], return_obs_bp_edge_count[1][2],\n"
        "                            return_obs_bp_edge_count[0][3], return_obs_bp_edge_count[1][3],\n"
        "                            return_obs_bp_prepared_change_count[0], return_obs_bp_prepared_change_count[1],\n"
        "                            return_obs_bp_edge_count[0][4], return_obs_bp_edge_count[1][4],\n"
        "                            return_obs_bp_edge_count[0][5], return_obs_bp_edge_count[1][5],\n"
        "                            return_obs_flow_q_rd_count[0], return_obs_flow_q_rd_count[1],\n"
        "                            return_obs_flow_ob_wr_count[0], return_obs_flow_ob_wr_count[1],\n"
        "                            return_obs_bp_factor_emit_count, return_obs_bp_factor_limit\n"
        "                        );\n"
        "                        $fdisplay(\n"
        "                            return_obs_fd,\n"
        "                            \"%0t | BP_PRE_FACTOR_STATE_V1 | event=%s bp_pre=0x%0h ob_full=0x%0h data_ready=0x%0h data_vld=0x%0h prepared_count=0x%0h rd_ob_full=0x%0h barrier=0x%0h q_rd=0x%0h ob_wr=0x%0h queue_occupancy=0x%0h window_edges=%0d:%0d\",\n"
        "                            $time, event_name,\n"
        "                            return_obs_bp_pre_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                            return_obs_bp_ob_full_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                            return_obs_bp_data_ready_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                            return_obs_bp_data_vld_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                            return_obs_bp_prepared_count_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                            return_obs_bp_rd_ob_full_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                            return_obs_bp_barrier_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                            return_obs_bp_q_rd_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                            return_obs_bp_ob_wr_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                            return_obs_bp_queue_occupancy_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                            return_obs_bp_window_start_edge, return_obs_bp_window_last_edge\n"
        "                        );\n"
        "                        $fdisplay(\n"
        "                            return_obs_fd,\n"
        "                            \"%0t | BP_PRE_FACTOR_WITNESS_V1 | event=%s mse0_ob_full=%0d:%0d mse3_ob_full=%0d:%0d mse0_not_ready=%0d:%0d mse3_not_ready=%0d:%0d mse0_not_vld=%0d:%0d mse3_not_vld=%0d:%0d mse0_rd_ob_full=%0d:%0d mse3_rd_ob_full=%0d:%0d mse0_barrier=%0d:%0d mse3_barrier=%0d:%0d seen0=0x%0h seen3=0x%0h\",\n"
        "                            $time, event_name,\n"
        "                            return_obs_bp_first_block[0][0], return_obs_bp_last_block[0][0],\n"
        "                            return_obs_bp_first_block[1][0], return_obs_bp_last_block[1][0],\n"
        "                            return_obs_bp_first_block[0][1], return_obs_bp_last_block[0][1],\n"
        "                            return_obs_bp_first_block[1][1], return_obs_bp_last_block[1][1],\n"
        "                            return_obs_bp_first_block[0][2], return_obs_bp_last_block[0][2],\n"
        "                            return_obs_bp_first_block[1][2], return_obs_bp_last_block[1][2],\n"
        "                            return_obs_bp_first_block[0][3], return_obs_bp_last_block[0][3],\n"
        "                            return_obs_bp_first_block[1][3], return_obs_bp_last_block[1][3],\n"
        "                            return_obs_bp_first_block[0][4], return_obs_bp_last_block[0][4],\n"
        "                            return_obs_bp_first_block[1][4], return_obs_bp_last_block[1][4],\n"
        "                            {return_obs_bp_block_seen[0][4], return_obs_bp_block_seen[0][3], return_obs_bp_block_seen[0][2], return_obs_bp_block_seen[0][1], return_obs_bp_block_seen[0][0]},\n"
        "                            {return_obs_bp_block_seen[1][4], return_obs_bp_block_seen[1][3], return_obs_bp_block_seen[1][2], return_obs_bp_block_seen[1][1], return_obs_bp_block_seen[1][0]}\n"
        "                        );\n"
        "                    end\n"
    )


def _factor_reset() -> str:
    return (
        "                return_obs_bp_factor_emit_count = 0;\n"
        "                return_obs_bp_window_start_edge = 0;\n"
        "                return_obs_bp_window_last_edge = 0;\n"
        "                for (int bp_flow = 0; bp_flow < 2; bp_flow++) begin\n"
        "                    return_obs_bp_started[bp_flow] = 1'b0;\n"
        "                    return_obs_bp_prev_prepared_count[bp_flow] = 0;\n"
        "                    return_obs_bp_prepared_change_count[bp_flow] = 0;\n"
        "                    for (int bp_factor = 0; bp_factor < 6; bp_factor++) begin\n"
        "                        return_obs_bp_prev[bp_flow][bp_factor] = 1'b0;\n"
        "                        return_obs_bp_edge_count[bp_flow][bp_factor] = 0;\n"
        "                    end\n"
        "                    for (int bp_blocker = 0; bp_blocker < 5; bp_blocker++) begin\n"
        "                        return_obs_bp_first_block[bp_flow][bp_blocker] = 0;\n"
        "                        return_obs_bp_last_block[bp_flow][bp_blocker] = 0;\n"
        "                        return_obs_bp_block_seen[bp_flow][bp_blocker] = 1'b0;\n"
        "                    end\n"
        "                end\n"
    )


def _factor_sg_monitor() -> str:
    return (
        "            if (return_obs_bp_factor_enabled) begin\n"
        "                if (return_obs_bp_window_start_edge == 0)\n"
        "                    return_obs_bp_window_start_edge = return_obs_sg_clock_edge_count;\n"
        "                return_obs_bp_window_last_edge = return_obs_sg_clock_edge_count;\n"
        "                for (int bp_flow = 0; bp_flow < 2; bp_flow++) begin\n"
        "                    if (!return_obs_bp_started[bp_flow]) begin\n"
        "                        return_obs_bp_started[bp_flow] = 1'b1;\n"
        "                        return_obs_bp_prev[bp_flow][0] = return_obs_bp_pre_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow];\n"
        "                        return_obs_bp_prev[bp_flow][1] = return_obs_bp_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow];\n"
        "                        return_obs_bp_prev[bp_flow][2] = return_obs_bp_data_ready_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow];\n"
        "                        return_obs_bp_prev[bp_flow][3] = return_obs_bp_data_vld_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow];\n"
        "                        return_obs_bp_prev[bp_flow][4] = return_obs_bp_rd_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow];\n"
        "                        return_obs_bp_prev[bp_flow][5] = return_obs_bp_barrier_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow];\n"
        "                        return_obs_bp_prev_prepared_count[bp_flow] = return_obs_bp_prepared_count_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow];\n"
        "                    end\n"
        "                    else begin\n"
        "                        if (return_obs_bp_prev[bp_flow][0] != return_obs_bp_pre_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow]) return_obs_bp_edge_count[bp_flow][0]++;\n"
        "                        if (return_obs_bp_prev[bp_flow][1] != return_obs_bp_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow]) return_obs_bp_edge_count[bp_flow][1]++;\n"
        "                        if (return_obs_bp_prev[bp_flow][2] != return_obs_bp_data_ready_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow]) return_obs_bp_edge_count[bp_flow][2]++;\n"
        "                        if (return_obs_bp_prev[bp_flow][3] != return_obs_bp_data_vld_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow]) return_obs_bp_edge_count[bp_flow][3]++;\n"
        "                        if (return_obs_bp_prev[bp_flow][4] != return_obs_bp_rd_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow]) return_obs_bp_edge_count[bp_flow][4]++;\n"
        "                        if (return_obs_bp_prev[bp_flow][5] != return_obs_bp_barrier_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow]) return_obs_bp_edge_count[bp_flow][5]++;\n"
        "                        if (return_obs_bp_prev_prepared_count[bp_flow] != return_obs_bp_prepared_count_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow]) return_obs_bp_prepared_change_count[bp_flow]++;\n"
        "                        if ((return_obs_bp_prev[bp_flow][0] != return_obs_bp_pre_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow] ||\n"
        "                             return_obs_bp_prev[bp_flow][1] != return_obs_bp_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow] ||\n"
        "                             return_obs_bp_prev[bp_flow][2] != return_obs_bp_data_ready_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow] ||\n"
        "                             return_obs_bp_prev[bp_flow][3] != return_obs_bp_data_vld_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow] ||\n"
        "                             return_obs_bp_prev[bp_flow][4] != return_obs_bp_rd_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow] ||\n"
        "                             return_obs_bp_prev[bp_flow][5] != return_obs_bp_barrier_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow] ||\n"
        "                             return_obs_bp_prev_prepared_count[bp_flow] != return_obs_bp_prepared_count_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow]) &&\n"
        "                            return_obs_bp_factor_emit_count < return_obs_bp_factor_limit) begin\n"
        "                            return_obs_bp_factor_emit_count++;\n"
        "                            $fdisplay(return_obs_fd,\n"
        "                                \"%0t | BP_PRE_FACTOR_EDGE_V1 | n=%0d mse=%0d sg_edge=%0d bp_pre=%0b ob_full=%0b data_ready=%0b data_vld=%0b prepared_count=%0d rd_ob_full=%0b barrier=%0b q_rd=%0b ob_wr=%0b queue_occupancy=%0d\",\n"
        "                                $time, return_obs_bp_factor_emit_count, (bp_flow == 0 ? 0 : 3), return_obs_sg_clock_edge_count,\n"
        "                                return_obs_bp_pre_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow],\n"
        "                                return_obs_bp_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow],\n"
        "                                return_obs_bp_data_ready_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow],\n"
        "                                return_obs_bp_data_vld_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow],\n"
        "                                return_obs_bp_prepared_count_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow],\n"
        "                                return_obs_bp_rd_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow],\n"
        "                                return_obs_bp_barrier_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow],\n"
        "                                return_obs_bp_q_rd_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow],\n"
        "                                return_obs_bp_ob_wr_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow],\n"
        "                                return_obs_bp_queue_occupancy_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow]);\n"
        "                        end\n"
        "                        return_obs_bp_prev[bp_flow][0] = return_obs_bp_pre_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow];\n"
        "                        return_obs_bp_prev[bp_flow][1] = return_obs_bp_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow];\n"
        "                        return_obs_bp_prev[bp_flow][2] = return_obs_bp_data_ready_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow];\n"
        "                        return_obs_bp_prev[bp_flow][3] = return_obs_bp_data_vld_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow];\n"
        "                        return_obs_bp_prev[bp_flow][4] = return_obs_bp_rd_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow];\n"
        "                        return_obs_bp_prev[bp_flow][5] = return_obs_bp_barrier_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow];\n"
        "                        return_obs_bp_prev_prepared_count[bp_flow] = return_obs_bp_prepared_count_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow];\n"
        "                    end\n"
        "                    if (return_obs_bp_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow]) begin\n"
        "                        if (!return_obs_bp_block_seen[bp_flow][0]) return_obs_bp_first_block[bp_flow][0] = return_obs_sg_clock_edge_count;\n"
        "                        return_obs_bp_block_seen[bp_flow][0] = 1'b1; return_obs_bp_last_block[bp_flow][0] = return_obs_sg_clock_edge_count;\n"
        "                    end\n"
        "                    if (!return_obs_bp_data_ready_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow]) begin\n"
        "                        if (!return_obs_bp_block_seen[bp_flow][1]) return_obs_bp_first_block[bp_flow][1] = return_obs_sg_clock_edge_count;\n"
        "                        return_obs_bp_block_seen[bp_flow][1] = 1'b1; return_obs_bp_last_block[bp_flow][1] = return_obs_sg_clock_edge_count;\n"
        "                    end\n"
        "                    if (!return_obs_bp_data_vld_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow]) begin\n"
        "                        if (!return_obs_bp_block_seen[bp_flow][2]) return_obs_bp_first_block[bp_flow][2] = return_obs_sg_clock_edge_count;\n"
        "                        return_obs_bp_block_seen[bp_flow][2] = 1'b1; return_obs_bp_last_block[bp_flow][2] = return_obs_sg_clock_edge_count;\n"
        "                    end\n"
        "                    if (return_obs_bp_rd_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow]) begin\n"
        "                        if (!return_obs_bp_block_seen[bp_flow][3]) return_obs_bp_first_block[bp_flow][3] = return_obs_sg_clock_edge_count;\n"
        "                        return_obs_bp_block_seen[bp_flow][3] = 1'b1; return_obs_bp_last_block[bp_flow][3] = return_obs_sg_clock_edge_count;\n"
        "                    end\n"
        "                    if (return_obs_bp_barrier_mon[return_obs_group_id][return_obs_local_slice_id][bp_flow]) begin\n"
        "                        if (!return_obs_bp_block_seen[bp_flow][4]) return_obs_bp_first_block[bp_flow][4] = return_obs_sg_clock_edge_count;\n"
        "                        return_obs_bp_block_seen[bp_flow][4] = 1'b1; return_obs_bp_last_block[bp_flow][4] = return_obs_sg_clock_edge_count;\n"
        "                    end\n"
        "                end\n"
        "            end\n"
    )


def extend_observer(source: str) -> str:
    source = replace_once(
        source,
        "// v17 stage1-flow extension: rate-limited, read-only snapshots split\n",
        "// v18 bp-pre factor extension: separately observes every conjunct of\n"
        "// buf_ag_bp_pre for MSE0/MSE3.  All taps are read-only; transition\n"
        "// counts and first/last blocking witnesses are excluded from canonical\n"
        "// monotonic progress and are emitted with a finite runtime budget.\n"
        "//\n"
        "// v17 stage1-flow extension: rate-limited, read-only snapshots split\n",
        "observer header",
    )
    source = replace_once(
        source,
        "    generate\n"
        "        for (genvar return_obs_flow_group = 0;\n",
        _factor_declarations()
        + "    generate\n"
        "        for (genvar return_obs_flow_group = 0;\n",
        "factor declarations",
    )
    source = replace_once(
        source,
        "    bit return_obs_enabled;\n",
        _factor_assignments() + "    bit return_obs_enabled;\n",
        "factor XMR assignments",
    )
    source = replace_once(
        source,
        "    bit return_obs_accum_state_enabled;\n",
        "    bit return_obs_accum_state_enabled;\n"
        + _factor_counter_declarations(),
        "factor runtime and counters",
    )
    summary_marker = (
        "                        return_obs_flow_ga_stored_tag_mon"
        "[return_obs_group_id][return_obs_local_slice_id]\n"
        "                    );\n"
        "                end\n"
    )
    source = replace_once(
        source,
        summary_marker,
        "                        return_obs_flow_ga_stored_tag_mon"
        "[return_obs_group_id][return_obs_local_slice_id]\n"
        "                    );\n"
        + _factor_summary_records()
        + "                end\n",
        "factor summary records",
    )
    source = replace_once(
        source,
        "        return_obs_accum_state_enabled =\n"
        "            $test$plusargs(\"RETURN_OBS_ACCUM_STATE\");\n",
        "        return_obs_accum_state_enabled =\n"
        "            $test$plusargs(\"RETURN_OBS_ACCUM_STATE\");\n"
        "        return_obs_bp_factor_enabled =\n"
        "            $test$plusargs(\"RETURN_OBS_BP_FACTORS\");\n",
        "factor enable plusarg",
    )
    source = replace_once(
        source,
        "        return_obs_accum_limit = 512;\n",
        "        return_obs_accum_limit = 512;\n"
        "        return_obs_bp_factor_limit = 512;\n",
        "factor default limit",
    )
    source = replace_once(
        source,
        "        return_obs_plusarg_status =\n"
        "            $value$plusargs(\n"
        "                \"RETURN_OBS_ACCUM_LIMIT=%d\",\n"
        "                return_obs_accum_limit\n"
        "            );\n",
        "        return_obs_plusarg_status =\n"
        "            $value$plusargs(\n"
        "                \"RETURN_OBS_ACCUM_LIMIT=%d\",\n"
        "                return_obs_accum_limit\n"
        "            );\n"
        "        return_obs_plusarg_status =\n"
        "            $value$plusargs(\n"
        "                \"RETURN_OBS_BP_FACTOR_LIMIT=%d\",\n"
        "                return_obs_bp_factor_limit\n"
        "            );\n",
        "factor limit plusarg",
    )
    source = replace_once(
        source,
        "        return_obs_accum_count = 0;\n",
        "        return_obs_accum_count = 0;\n"
        + _factor_reset().replace("                ", "        "),
        "factor initial reset",
    )
    source = replace_once(
        source,
        "                return_obs_accum_limit <= 0) begin\n",
        "                return_obs_accum_limit <= 0 ||\n"
        "                return_obs_bp_factor_limit <= 0) begin\n",
        "factor limit validation",
    )
    source = replace_once(
        source,
        "RETURN_OBSERVER invalid plusargs: slice=%0d stall=%0d heartbeat=%0d deep_limit=%0d accum_limit=%0d",
        "RETURN_OBSERVER invalid plusargs: slice=%0d stall=%0d heartbeat=%0d deep_limit=%0d accum_limit=%0d bp_factor_limit=%0d",
        "factor error format",
    )
    source = replace_once(
        source,
        "                    return_obs_accum_limit\n"
        "                );\n",
        "                    return_obs_accum_limit,\n"
        "                    return_obs_bp_factor_limit\n"
        "                );\n",
        "factor error argument",
    )
    source = replace_once(
        source,
        "# slice=%0d stall_cycles=%0d heartbeat_cycles=%0d deep=%0d deep_limit=%0d accum_state=%0d accum_limit=%0d",
        "# slice=%0d stall_cycles=%0d heartbeat_cycles=%0d deep=%0d deep_limit=%0d accum_state=%0d accum_limit=%0d bp_factor=%0d bp_factor_limit=%0d",
        "factor time0 marker format",
    )
    source = replace_once(
        source,
        "                        return_obs_accum_state_enabled,\n"
        "                        return_obs_accum_limit\n"
        "                    );\n",
        "                        return_obs_accum_state_enabled,\n"
        "                        return_obs_accum_limit,\n"
        "                        return_obs_bp_factor_enabled,\n"
        "                        return_obs_bp_factor_limit\n"
        "                    );\n",
        "factor time0 marker args",
    )
    source = replace_once(
        source,
        "                return_obs_ga_group2_accept_count = 0;\n"
        "                for (int flow = 0; flow < 2; flow++) begin\n",
        "                return_obs_ga_group2_accept_count = 0;\n"
        + _factor_reset()
        + "                for (int flow = 0; flow < 2; flow++) begin\n",
        "factor EXEC_START reset",
    )
    source = replace_once(
        source,
        "            return_obs_accum_state_enabled &&\n"
        "            return_obs_active &&\n",
        "            (return_obs_accum_state_enabled || return_obs_bp_factor_enabled) &&\n"
        "            return_obs_active &&\n",
        "factor source-clock enable",
    )
    source = replace_once(
        source,
        "            return_obs_sg_last_edge_time = $time;\n"
        "            for (int flow = 0; flow < 2; flow++) begin\n",
        "            return_obs_sg_last_edge_time = $time;\n"
        + _factor_sg_monitor()
        + "            for (int flow = 0; flow < 2; flow++) begin\n",
        "factor source-clock monitor",
    )
    source = replace_once(
        source,
        "                        return_obs_ga_input_valid_mon\n"
        "                            [return_obs_group_id]\n"
        "                            [return_obs_local_slice_id][row][slot] &&\n"
        "                        return_obs_accum_count < return_obs_accum_limit\n",
        "                        return_obs_ga_input_valid_mon\n"
        "                            [return_obs_group_id]\n"
        "                            [return_obs_local_slice_id][row][slot] &&\n"
        "                        return_obs_accum_state_enabled &&\n"
        "                        return_obs_accum_count < return_obs_accum_limit\n",
        "accumulator feature remains separately gated",
    )
    return source


def rewrite_runner(runner: Path) -> None:
    text = runner.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "+RETURN_OBS_ACCUM_STATE +RETURN_OBS_ACCUM_LIMIT=512 "
        "+RETURN_OBS_FILE=<run>/sim_results/return_observer/return_observer.log)",
        "+RETURN_OBS_ACCUM_STATE +RETURN_OBS_ACCUM_LIMIT=512 "
        "+RETURN_OBS_BP_FACTORS +RETURN_OBS_BP_FACTOR_LIMIT=512 "
        "+RETURN_OBS_FILE=<run>/sim_results/return_observer/return_observer.log)",
        "server command receipt factor plusargs",
    )
    old_binding = (
        "  if [ -s \"$observer_log\" ] && grep -Fq '[RETURN_OBSERVER] enabled' "
        "\"$run_root/sim_results/sim.log\" && grep -q 'Native NDP return observer' "
        "\"$observer_log\" && grep -Fq 'accum_state=1' \"$observer_log\"; then\n"
        "    printf 'observer_enabled_and_returned=true\\nbuffer_to_ga_accum_state_enabled=true\\nbuffer_to_ga_accum_limit=512\\n'       >\"$evidence_root/observer_binding.txt\"\n"
        "  else\n"
        "    printf 'observer_enabled_and_returned=false\\nbuffer_to_ga_accum_state_enabled=false\\nbuffer_to_ga_accum_limit=UNKNOWN\\n'       >\"$evidence_root/observer_binding.txt\"\n"
        "  fi\n"
    )
    new_binding = (
        "  if [ -s \"$observer_log\" ] && grep -Fq '[RETURN_OBSERVER] enabled' "
        "\"$run_root/sim_results/sim.log\" && grep -q 'Native NDP return observer' "
        "\"$observer_log\" && grep -Fq 'accum_state=1' \"$observer_log\"; then\n"
        "    observer_ok=true\n"
        "  else\n"
        "    observer_ok=false\n"
        "  fi\n"
        "  if [ \"$observer_ok\" = true ] && grep -Fq 'bp_factor=1' \"$observer_log\" "
        "&& grep -Fq 'bp_factor_limit=512' \"$observer_log\" "
        "&& grep -Fq 'BP_PRE_FACTOR_COUNTS_V1' \"$observer_log\" "
        "&& grep -Fq 'BP_PRE_FACTOR_STATE_V1' \"$observer_log\" "
        "&& grep -Fq 'BP_PRE_FACTOR_WITNESS_V1' \"$observer_log\"; then\n"
        "    bp_factor_ok=true\n"
        "  else\n"
        "    bp_factor_ok=false\n"
        "  fi\n"
        "  if [ \"$observer_ok\" = true ]; then\n"
        "    printf 'observer_enabled_and_returned=true\\nbuffer_to_ga_accum_state_enabled=true\\nbuffer_to_ga_accum_limit=512\\n' >\"$evidence_root/observer_binding.txt\"\n"
        "  else\n"
        "    printf 'observer_enabled_and_returned=false\\nbuffer_to_ga_accum_state_enabled=false\\nbuffer_to_ga_accum_limit=UNKNOWN\\n' >\"$evidence_root/observer_binding.txt\"\n"
        "  fi\n"
        "  if [ \"$bp_factor_ok\" = true ]; then\n"
        "    printf 'bp_pre_factor_observability_enabled=true\\nbp_pre_factor_limit=512\\nbp_pre_factor_records_returned=true\\n' >>\"$evidence_root/observer_binding.txt\"\n"
        "  else\n"
        "    printf 'bp_pre_factor_observability_enabled=false\\nbp_pre_factor_limit=UNKNOWN\\nbp_pre_factor_records_returned=false\\n' >>\"$evidence_root/observer_binding.txt\"\n"
        "  fi\n"
    )
    text = replace_once(text, old_binding, new_binding, "factor return binding")
    text = replace_once(
        text,
        "  +RETURN_OBS_ACCUM_LIMIT=512\n"
        "  \"+RETURN_OBS_FILE=$observer_log\"\n",
        "  +RETURN_OBS_ACCUM_LIMIT=512\n"
        "  +RETURN_OBS_BP_FACTORS\n"
        "  +RETURN_OBS_BP_FACTOR_LIMIT=512\n"
        "  \"+RETURN_OBS_FILE=$observer_log\"\n",
        "factor simulator plusargs",
    )
    runner.write_text(text, encoding="utf-8", newline="\n")


def current_rule_receipts(source_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    receipts = []
    for item in source_manifest["final_zip_rule_self_audit_contract"]["read_receipt"]:
        receipt = dict(item)
        receipt["sha256"] = sha256(ROOT / receipt["path"])
        receipt["current_match"] = True
        receipts.append(receipt)
    return receipts


def update_manifest(package: Path, source_manifest: dict[str, Any]) -> None:
    manifest = base.replace_identity(source_manifest)
    receipts = current_rule_receipts(source_manifest)
    receipt_by_path = {item["path"]: item["sha256"] for item in receipts}
    manifest.update(
        {
            "schema": "gap-node0071-bp-pre-factor-diagnostic-server-package-v18",
            "test_id": TEST_ID,
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "read-only, rate-limited MSE0/MSE3 buf_ag_bp_pre factor "
                "observability; v17 numeric/config/workload/golden/bitstream/"
                "execplan semantics frozen"
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
    manifest["bound_return_analysis"] = {
        "trigger_source_package_sha256": SOURCE_SHA256,
        "trigger_return_sha256": TRIGGER_RETURN_SHA256,
        "analysis_report_sha256": TRIGGER_ANALYSIS_SHA256,
        "analysis_task_record_sha256": TRIGGER_TASK_RECORD_SHA256,
        "classification":
            "LONG_RUNNING_HANG_AT_MSE3_BUFFER_AG_BP_PRE_CONJUNCTION_PENDING_LEAF",
        "unresolved_leaf_disjunction": [
            "rd_data_chl_data_ready==0",
            "nse2mse_req_barrier==1",
        ],
    }
    audit_contract = manifest["final_zip_rule_self_audit_contract"]
    applicable = list(audit_contract["applicable_rule_ids"])
    if NEW_RULE_ID not in applicable:
        applicable.append(NEW_RULE_ID)
    audit_contract.update(
        {
            "read_receipt": receipts,
            "applicable_rule_ids": applicable,
            "all_current_match": True,
            "plan_sha256_mutable_provenance_only":
                sha256(ROOT / ".agents/plan.md"),
            "final_zip_independent_validator_required": True,
            "final_zip_rule_self_audit_pass":
                "PENDING_EXTERNAL_RELEASE_REPORT",
        }
    )
    rules = manifest["rule_receipts"]
    for path, digest in receipt_by_path.items():
        if path.endswith("生成前必读索引.md"):
            rules["generation_index_sha256"] = digest
        elif path.endswith("算子配置规则.md"):
            rules["common_operator_rule_sha256"] = digest
        elif path.endswith("NDP硬件字段语义.md"):
            rules["ndp_field_rule_sha256"] = digest
        elif path.endswith("服务器测试包生成规则.md"):
            rules["server_rule_sha256"] = digest
        elif path.endswith("GAP_int32_mac_bypass_rules.md"):
            rules["gap_int32_rule_sha256"] = digest
        elif path.endswith("GAP_probe_v7_validator_rules.md"):
            rules["gap_probe_rule_sha256"] = digest
        elif path.endswith("精确UINT8量化尾专项规则.md"):
            rules["exact_uint8_tail_rule_sha256"] = digest
    rules["current_match"] = True
    rules["plan_sha256_mutable_provenance_only"] = sha256(ROOT / ".agents/plan.md")
    manifest["bp_pre_factor_observability_contract"] = {
        "rule_id": NEW_RULE_ID,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "feature_name": "bp_pre_factor_observability",
        "runtime_enable_plusarg": "+RETURN_OBS_BP_FACTORS",
        "runtime_limit_plusarg": "+RETURN_OBS_BP_FACTOR_LIMIT=512",
        "effective_limit": 512,
        "source_clock": "clk_sg",
        "snapshot_clock": "clk_db",
        "coverage_window": (
            "from first active clk_sg edge after EXEC_START through latest "
            "signal-safe summary/terminal"
        ),
        "record_schemas": [
            "BP_PRE_FACTOR_EDGE_V1",
            "BP_PRE_FACTOR_COUNTS_V1",
            "BP_PRE_FACTOR_STATE_V1",
            "BP_PRE_FACTOR_WITNESS_V1",
        ],
        "time0_marker": {
            "return_target": "runs/return_observer.log",
            "required_tokens": ["bp_factor=1", "bp_factor_limit=512"],
        },
        "feature_specific_binding_receipt": {
            "return_target": "evidence/observer_binding.txt",
            "success_exact_lines": [
                "bp_pre_factor_observability_enabled=true",
                "bp_pre_factor_limit=512",
                "bp_pre_factor_records_returned=true",
            ],
            "failure_exact_lines": [
                "bp_pre_factor_observability_enabled=false",
                "bp_pre_factor_limit=UNKNOWN",
                "bp_pre_factor_records_returned=false",
            ],
        },
        "return_allowlist_targets": [
            "evidence/actual_compile_argv.txt",
            "evidence/actual_simulator_argv.txt",
            "evidence/observer_binding.txt",
            "runs/return_observer.log",
        ],
        "conjunction_equation": (
            "buf_ag_bp_pre = !buf_ag_ob_full && "
            "rd_data_chl_data_ready && !nse2mse_req_barrier"
        ),
        "conjuncts": [
            {
                "name": "buf_ag_bp_pre",
                "owner": "MSE0/MSE3 WR_Buffer_AG ready/backpressure conjunction output",
                "sampling": "clk_sg state + transition edge; output zero does not assign a leaf",
            },
            {
                "name": "buf_ag_ob_full",
                "owner": "MSE0/MSE3 WR_Buffer_AG output-buffer occupancy",
                "sampling": "clk_sg state + transition edge + first/last high witness",
            },
            {
                "name": "rd_data_chl_data_ready",
                "owner": "MSE0/MSE3 RD_Data_Channel ready conjunction",
                "sampling": "clk_sg state + transition edge + first/last low witness",
            },
            {
                "name": "rd_data_chl_data_vld",
                "owner": "MSE0/MSE3 RD_Data_Channel prepared-data sufficiency",
                "sampling": "clk_sg state + transition edge + first/last low witness",
            },
            {
                "name": "rd_data_chl_prepared_data_cnt",
                "owner": "MSE0/MSE3 RD_Data_Channel prepared-data FIFO",
                "sampling": "clk_sg state + value-change edge",
            },
            {
                "name": "rd_data_chl_ob_full",
                "owner": "MSE0/MSE3 RD_Data_Channel output buffer",
                "sampling": "clk_sg state + transition edge + first/last high witness",
            },
            {
                "name": "nse2mse_req_barrier",
                "owner": "Stream_Engine neighbor-stream barrier routing",
                "sampling": "clk_sg state + transition edge + first/last high witness",
            },
            {
                "name": "buf_ag_idx_queue_rd_en",
                "owner": "MSE0/MSE3 Buffer_AG_Idx_Queue dequeue",
                "sampling": "qualified accepted count requires !queue_empty",
            },
            {
                "name": "buf_ag_ob_wr_en",
                "owner": "MSE0/MSE3 WR_Buffer_AG accepted address write",
                "sampling": "qualified accepted count requires buf_ag_bp_pre",
            },
            {
                "name": "buf_ag_idx_queue_occupancy",
                "owner": "MSE0/MSE3 Buffer_AG_Idx_Queue FIFO",
                "sampling": "clk_sg state snapshot only",
            },
        ],
        "stable_levels_excluded_from_monotonic_progress": True,
        "factor_edge_counts_excluded_from_canonical_progress": True,
        "output_zero_leaf_attribution_forbidden": True,
        "numeric_workload_changed": False,
        "config_changed": False,
        "functional_rtl_modified": False,
    }
    observer_sha = sha256(package / OBSERVER_RELATIVE)
    observer_gate = observer_precompile_receipt(package, observer_sha)
    if not observer_gate["valid"]:
        raise BuildError(
            f"observer XMR static gate failed: {observer_gate['errors']}"
        )
    manifest["package_local_observer"]["xmr_static_gate"] = (
        observer_gate["xmr_static_gate"]
    )
    manifest["generation_provenance"].update(
        {
            "tool":
                "tools/build_gap_node0071_bp_pre_factor_diag_v18_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "numeric_payload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change": (
                "fresh identity plus package-local read-only MSE0/MSE3 "
                "buf_ag_bp_pre factor observer extension"
            ),
        }
    )
    manifest["files"] = file_records(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_source()
    package = base.extract_source(destination)
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_records = file_records(package, exclude_manifest=False)
    frozen_before = file_records(
        package / "workload", exclude_manifest=False
    )
    frozen_numeric_before = {
        path: record
        for path, record in frozen_before.items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    base.rewrite_identity(package)
    rewrite_runner(package / "PREPARE_AND_RUN.sh")
    observer = package / OBSERVER_RELATIVE
    observer.write_text(
        extend_observer(observer.read_text(encoding="utf-8")),
        encoding="utf-8",
        newline="\n",
    )
    (package / "README.md").write_text(
        "# GAP node0071 v18 bp-pre factor diagnostic\n\n"
        f"Test ID: `{TEST_ID}`.\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It keeps "
        "the v17 numeric/config/workload/golden/bitstream/execplan semantics "
        "frozen and adds only package-local read-only, rate-limited MSE0/MSE3 "
        "`buf_ag_bp_pre` factor observability. Stable levels, transition "
        "counts and first/last blocking witnesses do not enter canonical "
        "monotonic progress and do not drive the DUT.\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package, source_manifest)
    frozen_after = file_records(
        package / "workload", exclude_manifest=False
    )
    frozen_numeric_after = {
        path: record
        for path, record in frozen_after.items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    if (
        frozen_numeric_before != frozen_numeric_after
        or len(frozen_numeric_after) != 73
    ):
        raise BuildError("frozen 73-file numeric/workload tree drifted")
    final_records = file_records(package, exclude_manifest=False)
    if set(source_records) != set(final_records):
        raise BuildError("relative file set changed")
    changed = {
        path
        for path in source_records
        if source_records[path] != final_records[path]
    }
    if changed != ALLOWED_CHANGED:
        raise BuildError(f"changed path set differs: {sorted(changed)}")
    frozen_semantic_paths = sorted(
        set(source_records) - ALLOWED_CHANGED
    )
    return package, {
        "source_v17_zip_sha256": SOURCE_SHA256,
        "observer_sha256": sha256(observer),
        "changed_paths": sorted(changed),
        "changed_paths_exact_allowlist": True,
        "frozen_numeric_workload_file_count": len(frozen_numeric_after),
        "frozen_numeric_workload_tree_equal": True,
        "frozen_semantic_file_count": len(frozen_semantic_paths),
        "frozen_semantic_tree_equal": all(
            source_records[path] == final_records[path]
            for path in frozen_semantic_paths
        ),
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    first_sha = sha256(zip_path)
    first_tree = file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v18-repeat-"
    ) as tmp:
        repeated, _ = build_directory(Path(tmp))
        repeated_zip = Path(tmp) / f"{INSTALL_NAME}.zip"
        deterministic_zip(repeated, repeated_zip, archive_root=INSTALL_NAME)
        if sha256(repeated_zip) != first_sha:
            raise BuildError("repeat ZIP differs")
        if file_records(repeated, exclude_manifest=False) != first_tree:
            raise BuildError("repeat package tree differs")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": first_sha,
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
            "schema": "gap-node0071-bp-pre-factor-v18-build-v1",
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
    except Exception as error:
        print(f"GAP v18 build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
