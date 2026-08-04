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
from tools import build_gap_node0071_v13_buffer_to_ga_diag_package as base


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix"
INSTALL_NAME = "r5_n71_gap_v23_rd_data_vld_path_rulefix"
TEST_ID = "r5-gap-node0071-v23-rd-data-vld-path-rulefix"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = (
    "a82ac187b46dac4f26a8545bf14bebf5bc5481308791be062ce581a30429bbe3"
)
TRIGGER_RETURN_SHA256 = (
    "59cef2d1051f9f4d38f65c473b8ed2e421d4f603fcdee7faef9844a2b6e603e5"
)
TRIGGER_ANALYSIS = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-gap-node0071-v20-return-analysis/report.json"
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
        raise BuildError(f"marker differs: {label}")
    return text.replace(old, new, 1)


def configure_source() -> None:
    base.SOURCE_NAME = SOURCE_NAME
    base.INSTALL_NAME = INSTALL_NAME
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256


def xmr_prefix(mse: int) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_rd_group]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[return_obs_rd_slice]"
        ".u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine"
        f".MSE_INST[{mse}].RD_MSE.u_Memory_RD_Stream_Engine"
    )


def rd_path_declarations_and_assignments() -> str:
    lines = [
        "    // v21: read-only MSE0/MSE3 RD_Data_Channel data-vld path.",
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]",
        "          return_obs_rd_req_valid_mon, return_obs_rd_req_ready_mon,",
        "          return_obs_rd_queue_wr_mon, return_obs_rd_queue_rd_mon,",
        "          return_obs_rd_queue_full_mon, return_obs_rd_queue_empty_mon,",
        "          return_obs_rd_ib_sel_mon, return_obs_rd_prep_wr_mon,",
        "          return_obs_rd_prep_rd_mon, return_obs_rd_data_vld_path_mon;",
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]",
        "          [1:0][1:0] return_obs_rd_mem_vld_mon,",
        "                      return_obs_rd_mem_ready_mon,",
        "                      return_obs_rd_ib_wr_hs_mon,",
        "                      return_obs_rd_ib_rd_hs_mon,",
        "                      return_obs_rd_ib_vld_mon;",
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]",
        "          [1:0][7:0] return_obs_rd_prep_count_mon,",
        "                      return_obs_rd_queue_tsf_size_mon,",
        "                      return_obs_rd_spatial_size_mon;",
        "",
        "    generate",
        "        for (genvar return_obs_rd_group = 0;",
        "             return_obs_rd_group < `SLICE_GROUP_SIZE;",
        "             return_obs_rd_group++) begin : RETURN_OBS_RD_GROUP_GEN",
        "            for (genvar return_obs_rd_slice = 0;",
        "                 return_obs_rd_slice < `SLICE_GROUP_NUM;",
        "                 return_obs_rd_slice++) begin : RETURN_OBS_RD_SLICE_GEN",
    ]
    for slot, mse in enumerate((0, 3)):
        prefix = xmr_prefix(mse)
        single = {
            "return_obs_rd_req_valid_mon":
                f"{prefix}.u_RD_Data_Channel.rd_data_chl_req_valid",
            "return_obs_rd_req_ready_mon":
                f"{prefix}.u_RD_Data_Channel.rd_data_chl_req_ready",
            "return_obs_rd_queue_wr_mon":
                f"{prefix}.u_RD_Data_Channel.rd_chl_queue_wr_en",
            "return_obs_rd_queue_rd_mon":
                f"{prefix}.u_RD_Data_Channel.rd_chl_queue_rd_en",
            "return_obs_rd_queue_full_mon":
                f"{prefix}.u_RD_Data_Channel.rd_chl_queue_full",
            "return_obs_rd_queue_empty_mon":
                f"{prefix}.u_RD_Data_Channel.rd_chl_queue_empty",
            "return_obs_rd_ib_sel_mon":
                f"{prefix}.u_RD_Data_Channel.rd_chl_ib_sel",
            "return_obs_rd_prep_wr_mon":
                f"{prefix}.u_RD_Data_Channel.rd_data_chl_prepared_data_wr_hs",
            "return_obs_rd_prep_rd_mon":
                f"{prefix}.u_RD_Data_Channel.rd_data_chl_prepared_data_rd_hs",
            "return_obs_rd_data_vld_path_mon":
                f"{prefix}.u_RD_Data_Channel.rd_data_chl_data_vld",
            "return_obs_rd_prep_count_mon":
                f"{prefix}.u_RD_Data_Channel.rd_data_chl_prepared_data_cnt",
            "return_obs_rd_queue_tsf_size_mon":
                f"{prefix}.u_RD_Data_Channel.rd_chl_queue_rd_tsf_size",
            "return_obs_rd_spatial_size_mon":
                f"{prefix}.mse_buf_spatial_size",
        }
        vector = {
            "return_obs_rd_mem_vld_mon":
                f"{prefix}.u_RD_Data_Channel.mem2mse_rdata_valid",
            "return_obs_rd_mem_ready_mon":
                f"{prefix}.u_RD_Data_Channel.mse2mem_rdata_ready",
            "return_obs_rd_ib_wr_hs_mon":
                f"{prefix}.u_RD_Data_Channel.rd_chl_ib_wr_hs",
            "return_obs_rd_ib_rd_hs_mon":
                f"{prefix}.u_RD_Data_Channel.rd_chl_ib_rd_hs",
            "return_obs_rd_ib_vld_mon":
                f"{prefix}.u_RD_Data_Channel.rd_chl_ib_vld",
        }
        for signal, expression in {**single, **vector}.items():
            lines.extend(
                [
                    f"                assign {signal}[return_obs_rd_group]"
                    f"[return_obs_rd_slice][{slot}] =",
                    f"                    {expression};",
                ]
            )
    lines.extend(
        [
            "            end",
            "        end",
            "    endgenerate",
            "",
            "    bit return_obs_rd_path_enabled;",
            "    int return_obs_rd_path_limit;",
            "    int return_obs_rd_path_emit_count;",
            "    longint unsigned return_obs_rd_req_hs_count [0:1];",
            "    longint unsigned return_obs_rd_rdata_hs_count [0:1][0:1];",
            "    longint unsigned return_obs_rd_ib_wr_count [0:1][0:1];",
            "    longint unsigned return_obs_rd_ib_rd_count [0:1][0:1];",
            "    longint unsigned return_obs_rd_prep_wr_count [0:1];",
            "    longint unsigned return_obs_rd_prep_rd_count [0:1];",
            "    longint unsigned return_obs_rd_first_no_rdata [0:1];",
            "    longint unsigned return_obs_rd_last_no_rdata [0:1];",
            "    longint unsigned return_obs_rd_first_no_prep [0:1];",
            "    longint unsigned return_obs_rd_last_no_prep [0:1];",
            "    bit return_obs_rd_no_rdata_seen [0:1];",
            "    bit return_obs_rd_no_prep_seen [0:1];",
            "",
            "    task automatic return_obs_rd_path_reset;",
            "        begin",
            "            return_obs_rd_path_emit_count = 0;",
            "            for (int rd_flow = 0; rd_flow < 2; rd_flow++) begin",
            "                return_obs_rd_req_hs_count[rd_flow] = 0;",
            "                return_obs_rd_prep_wr_count[rd_flow] = 0;",
            "                return_obs_rd_prep_rd_count[rd_flow] = 0;",
            "                return_obs_rd_first_no_rdata[rd_flow] = 0;",
            "                return_obs_rd_last_no_rdata[rd_flow] = 0;",
            "                return_obs_rd_first_no_prep[rd_flow] = 0;",
            "                return_obs_rd_last_no_prep[rd_flow] = 0;",
            "                return_obs_rd_no_rdata_seen[rd_flow] = 1'b0;",
            "                return_obs_rd_no_prep_seen[rd_flow] = 1'b0;",
            "                for (int rd_ch = 0; rd_ch < 2; rd_ch++) begin",
            "                    return_obs_rd_rdata_hs_count[rd_flow][rd_ch] = 0;",
            "                    return_obs_rd_ib_wr_count[rd_flow][rd_ch] = 0;",
            "                    return_obs_rd_ib_rd_count[rd_flow][rd_ch] = 0;",
            "                end",
            "            end",
            "        end",
            "    endtask",
            "",
        ]
    )
    return "\n".join(lines)


RD_SUMMARY = r'''                    if (return_obs_rd_path_enabled) begin
                        $fdisplay(
                            return_obs_fd,
                            "%0t | RD_DATA_VLD_PATH_COUNTS_V1 | event=%s req_hs=%0d/%0d rdata_hs=%0d,%0d/%0d,%0d ib_wr=%0d,%0d/%0d,%0d ib_rd=%0d,%0d/%0d,%0d prep_wr=%0d/%0d prep_rd=%0d/%0d records=%0d limit=%0d",
                            $time, event_name,
                            return_obs_rd_req_hs_count[0], return_obs_rd_req_hs_count[1],
                            return_obs_rd_rdata_hs_count[0][0], return_obs_rd_rdata_hs_count[0][1],
                            return_obs_rd_rdata_hs_count[1][0], return_obs_rd_rdata_hs_count[1][1],
                            return_obs_rd_ib_wr_count[0][0], return_obs_rd_ib_wr_count[0][1],
                            return_obs_rd_ib_wr_count[1][0], return_obs_rd_ib_wr_count[1][1],
                            return_obs_rd_ib_rd_count[0][0], return_obs_rd_ib_rd_count[0][1],
                            return_obs_rd_ib_rd_count[1][0], return_obs_rd_ib_rd_count[1][1],
                            return_obs_rd_prep_wr_count[0], return_obs_rd_prep_wr_count[1],
                            return_obs_rd_prep_rd_count[0], return_obs_rd_prep_rd_count[1],
                            return_obs_rd_path_emit_count, return_obs_rd_path_limit
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | RD_DATA_VLD_PATH_STATE_V1 | event=%s req_vld=0x%0h req_ready=0x%0h q_wr=0x%0h q_rd=0x%0h q_full=0x%0h q_empty=0x%0h mem_vld=0x%0h mem_ready=0x%0h ib_vld=0x%0h ib_sel=0x%0h prep_count=0x%0h queue_tsf=0x%0h spatial=0x%0h prep_wr=0x%0h prep_rd=0x%0h data_vld=0x%0h",
                            $time, event_name,
                            return_obs_rd_req_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_req_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_queue_wr_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_queue_rd_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_queue_full_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_queue_empty_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_mem_vld_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_mem_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_ib_vld_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_ib_sel_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_prep_count_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_queue_tsf_size_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_spatial_size_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_prep_wr_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_prep_rd_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_data_vld_path_mon[return_obs_group_id][return_obs_local_slice_id]
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | RD_DATA_VLD_PATH_WITNESS_V1 | event=%s mse0_no_rdata=%0d:%0d mse3_no_rdata=%0d:%0d mse0_no_prep=%0d:%0d mse3_no_prep=%0d:%0d seen_rdata=0x%0h seen_prep=0x%0h",
                            $time, event_name,
                            return_obs_rd_first_no_rdata[0], return_obs_rd_last_no_rdata[0],
                            return_obs_rd_first_no_rdata[1], return_obs_rd_last_no_rdata[1],
                            return_obs_rd_first_no_prep[0], return_obs_rd_last_no_prep[0],
                            return_obs_rd_first_no_prep[1], return_obs_rd_last_no_prep[1],
                            {return_obs_rd_no_rdata_seen[1], return_obs_rd_no_rdata_seen[0]},
                            {return_obs_rd_no_prep_seen[1], return_obs_rd_no_prep_seen[0]}
                        );
                    end
'''


RD_SAMPLE_ALWAYS = r'''
    // v21 qualified read-return/prepared-data path. Stable levels are state
    // only; only request, rdata, inbuffer and prepared-data handshakes count.
    always @(posedge u_NDP_Top_new.clk_sg) begin
        if (
            u_NDP_Top_new.rst_n_sg &&
            return_obs_enabled &&
            return_obs_rd_path_enabled &&
            return_obs_active &&
            return_obs_fd != 0
        ) begin
            for (int rd_flow = 0; rd_flow < 2; rd_flow++) begin
                bit rd_any_event;
                rd_any_event = 1'b0;
                if (
                    return_obs_rd_req_valid_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow] &&
                    return_obs_rd_req_ready_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow]
                ) begin
                    return_obs_rd_req_hs_count[rd_flow]++;
                    rd_any_event = 1'b1;
                end
                for (int rd_ch = 0; rd_ch < 2; rd_ch++) begin
                    if (
                        return_obs_rd_mem_vld_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow][rd_ch] &&
                        return_obs_rd_mem_ready_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow][rd_ch]
                    ) begin
                        return_obs_rd_rdata_hs_count[rd_flow][rd_ch]++;
                        rd_any_event = 1'b1;
                    end
                    if (return_obs_rd_ib_wr_hs_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow][rd_ch]) begin
                        return_obs_rd_ib_wr_count[rd_flow][rd_ch]++;
                        rd_any_event = 1'b1;
                    end
                    if (return_obs_rd_ib_rd_hs_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow][rd_ch]) begin
                        return_obs_rd_ib_rd_count[rd_flow][rd_ch]++;
                        rd_any_event = 1'b1;
                    end
                end
                if (return_obs_rd_prep_wr_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow]) begin
                    return_obs_rd_prep_wr_count[rd_flow]++;
                    rd_any_event = 1'b1;
                end
                if (return_obs_rd_prep_rd_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow]) begin
                    return_obs_rd_prep_rd_count[rd_flow]++;
                    rd_any_event = 1'b1;
                end
                if (
                    !return_obs_rd_queue_empty_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow] &&
                    !(|(
                        return_obs_rd_mem_vld_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow] &
                        return_obs_rd_mem_ready_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow]
                    ))
                ) begin
                    if (!return_obs_rd_no_rdata_seen[rd_flow])
                        return_obs_rd_first_no_rdata[rd_flow] = return_obs_sg_clock_edge_count;
                    return_obs_rd_no_rdata_seen[rd_flow] = 1'b1;
                    return_obs_rd_last_no_rdata[rd_flow] = return_obs_sg_clock_edge_count;
                end
                if (
                    !return_obs_rd_queue_empty_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow] &&
                    return_obs_rd_prep_count_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow] == 0
                ) begin
                    if (!return_obs_rd_no_prep_seen[rd_flow])
                        return_obs_rd_first_no_prep[rd_flow] = return_obs_sg_clock_edge_count;
                    return_obs_rd_no_prep_seen[rd_flow] = 1'b1;
                    return_obs_rd_last_no_prep[rd_flow] = return_obs_sg_clock_edge_count;
                end
                if (rd_any_event && return_obs_rd_path_emit_count < return_obs_rd_path_limit) begin
                    return_obs_rd_path_emit_count++;
                    $fdisplay(
                        return_obs_fd,
                        "%0t | RD_DATA_VLD_PATH_EVENT_V1 | n=%0d mse=%0d sg_edge=%0d req_hs=%0b mem_vld=0x%0h mem_ready=0x%0h ib_wr=0x%0h ib_rd=0x%0h ib_vld=0x%0h ib_sel=%0b prep_wr=%0b prep_rd=%0b prep_count=%0d queue_tsf=%0d spatial=%0d data_vld=%0b",
                        $time, return_obs_rd_path_emit_count, (rd_flow == 0 ? 0 : 3), return_obs_sg_clock_edge_count,
                        return_obs_rd_req_valid_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow] &&
                            return_obs_rd_req_ready_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow],
                        return_obs_rd_mem_vld_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow],
                        return_obs_rd_mem_ready_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow],
                        return_obs_rd_ib_wr_hs_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow],
                        return_obs_rd_ib_rd_hs_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow],
                        return_obs_rd_ib_vld_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow],
                        return_obs_rd_ib_sel_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow],
                        return_obs_rd_prep_wr_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow],
                        return_obs_rd_prep_rd_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow],
                        return_obs_rd_prep_count_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow],
                        return_obs_rd_queue_tsf_size_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow],
                        return_obs_rd_spatial_size_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow],
                        return_obs_rd_data_vld_path_mon[return_obs_group_id][return_obs_local_slice_id][rd_flow]
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
        rd_path_declarations_and_assignments()
        + "    bit return_obs_enabled;\n",
        "RD path declarations",
    )
    text = replace_once(
        text,
        '        return_obs_bp_factor_enabled =\n'
        '            $test$plusargs("RETURN_OBS_BP_FACTORS");\n',
        '        return_obs_bp_factor_enabled =\n'
        '            $test$plusargs("RETURN_OBS_BP_FACTORS");\n'
        '        return_obs_rd_path_enabled =\n'
        '            $test$plusargs("RETURN_OBS_RD_DATA_PATH");\n',
        "RD path feature plusarg",
    )
    text = replace_once(
        text,
        "        return_obs_bp_factor_limit = 512;\n",
        "        return_obs_bp_factor_limit = 512;\n"
        "        return_obs_rd_path_limit = 512;\n",
        "RD path default limit",
    )
    text = replace_once(
        text,
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_FILE=%s",\n',
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_RD_DATA_PATH_LIMIT=%d",\n'
        '                return_obs_rd_path_limit\n'
        '            );\n'
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_FILE=%s",\n',
        "RD path limit plusarg",
    )
    text = text.replace(
        "        return_obs_bp_factor_emit_count = 0;\n",
        "        return_obs_bp_factor_emit_count = 0;\n"
        "        return_obs_rd_path_reset();\n",
    )
    if text.count("return_obs_rd_path_reset();") != 2:
        raise BuildError("RD path reset call count differs")
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
        + RD_SUMMARY
        + "                end\n"
        "                $fflush(return_obs_fd);\n"
        "            end\n"
        "        end\n"
        "    endtask\n\n"
        "    task automatic return_obs_write_internal_state",
        "RD path summary",
    )
    text = replace_once(
        text,
        '"# slice=%0d stall_cycles=%0d heartbeat_cycles=%0d deep=%0d '
        'deep_limit=%0d accum_state=%0d accum_limit=%0d bp_factor=%0d '
        'bp_factor_limit=%0d",\n',
        '"# slice=%0d stall_cycles=%0d heartbeat_cycles=%0d deep=%0d '
        'deep_limit=%0d accum_state=%0d accum_limit=%0d bp_factor=%0d '
        'bp_factor_limit=%0d rd_data_path=%0d rd_data_path_limit=%0d",\n',
        "RD path time0 header format",
    )
    text = replace_once(
        text,
        "                        return_obs_bp_factor_enabled,\n"
        "                        return_obs_bp_factor_limit\n",
        "                        return_obs_bp_factor_enabled,\n"
        "                        return_obs_bp_factor_limit,\n"
        "                        return_obs_rd_path_enabled,\n"
        "                        return_obs_rd_path_limit\n",
        "RD path time0 header args",
    )
    text = replace_once(
        text,
        "    final begin\n",
        RD_SAMPLE_ALWAYS + "    final begin\n",
        "RD path sampling always",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def upgrade_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "  +RETURN_OBS_BP_FACTOR_LIMIT=512\n",
        "  +RETURN_OBS_BP_FACTOR_LIMIT=512\n"
        "  +RETURN_OBS_RD_DATA_PATH\n"
        "  +RETURN_OBS_RD_DATA_PATH_LIMIT=512\n",
        "runner simulator args",
    )
    text = replace_once(
        text,
        "+RETURN_OBS_BP_FACTOR_LIMIT=512 +RETURN_OBS_FILE=",
        "+RETURN_OBS_BP_FACTOR_LIMIT=512 +RETURN_OBS_RD_DATA_PATH "
        "+RETURN_OBS_RD_DATA_PATH_LIMIT=512 +RETURN_OBS_FILE=",
        "runner command receipt",
    )
    if text.count("+RETURN_OBS_RD_DATA_PATH") < 2:
        raise BuildError("runner RD path plusarg binding count differs")
    text = replace_once(
        text,
        "  if [ \"$observer_ok\" = true ] && grep -Fq 'bp_factor=1' "
        "\"$observer_log\" && grep -Fq 'bp_factor_limit=512' "
        "\"$observer_log\" && grep -Fq 'BP_PRE_FACTOR_COUNTS_V1' "
        "\"$observer_log\" && grep -Fq 'BP_PRE_FACTOR_STATE_V1' "
        "\"$observer_log\" && grep -Fq 'BP_PRE_FACTOR_WITNESS_V1' "
        "\"$observer_log\"; then\n",
        "  if [ \"$observer_ok\" = true ] && grep -Fq 'bp_factor=1' "
        "\"$observer_log\" && grep -Fq 'bp_factor_limit=512' "
        "\"$observer_log\" && grep -Fq 'BP_PRE_FACTOR_COUNTS_V1' "
        "\"$observer_log\" && grep -Fq 'BP_PRE_FACTOR_STATE_V1' "
        "\"$observer_log\" && grep -Fq 'BP_PRE_FACTOR_WITNESS_V1' "
        "\"$observer_log\"; then\n",
        "existing factor binding remains",
    )
    marker = (
        "  if [ \"$bp_factor_ok\" = true ]; then\n"
        "    printf 'bp_pre_factor_observability_enabled=true\\n"
        "bp_pre_factor_limit=512\\nbp_pre_factor_records_returned=true\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  else\n"
        "    printf 'bp_pre_factor_observability_enabled=false\\n"
        "bp_pre_factor_limit=UNKNOWN\\nbp_pre_factor_records_returned=false\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  fi\n"
    )
    addition = marker + (
        "  if [ \"$observer_ok\" = true ] && "
        "grep -Fq 'rd_data_path=1' \"$observer_log\" && "
        "grep -Fq 'rd_data_path_limit=512' \"$observer_log\" && "
        "grep -Fq 'RD_DATA_VLD_PATH_COUNTS_V1' \"$observer_log\" && "
        "grep -Fq 'RD_DATA_VLD_PATH_STATE_V1' \"$observer_log\" && "
        "grep -Fq 'RD_DATA_VLD_PATH_WITNESS_V1' \"$observer_log\"; then\n"
        "    rd_data_path_ok=true\n"
        "  else\n"
        "    rd_data_path_ok=false\n"
        "  fi\n"
        "  if [ \"$rd_data_path_ok\" = true ]; then\n"
        "    printf 'rd_data_vld_path_enabled=true\\n"
        "rd_data_vld_path_limit=512\\n"
        "rd_data_vld_path_records_returned=true\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  else\n"
        "    printf 'rd_data_vld_path_enabled=false\\n"
        "rd_data_vld_path_limit=UNKNOWN\\n"
        "rd_data_vld_path_records_returned=false\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  fi\n"
    )
    text = replace_once(text, marker, addition, "runner feature receipt")
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
    manifest = base.replace_identity(source_manifest)
    receipts = current_receipts(source_manifest)
    receipt_by_path = {item["path"]: item["sha256"] for item in receipts}
    manifest.update(
        {
            "schema":
                "gap-node0071-rd-data-vld-path-rulefix-package-v23",
            "test_id": TEST_ID,
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "read-only MSE0/MSE3 memory-return, RD inbuffer, queue and "
                "prepared-data path localization below rd_data_chl_data_vld"
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
    audit.update(
        {
            "read_receipt": receipts,
            "all_current_match": True,
            "plan_sha256_mutable_provenance_only":
                sha256(ROOT / ".agents/plan.md"),
            "final_zip_rule_self_audit_pass":
                "PENDING_EXTERNAL_RELEASE_REPORT",
        }
    )
    closure_rule = (
        "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001"
    )
    if closure_rule not in audit["applicable_rule_ids"]:
        audit["applicable_rule_ids"].append(closure_rule)
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
    rules["plan_sha256_mutable_provenance_only"] = sha256(
        ROOT / ".agents/plan.md"
    )
    manifest["rd_data_vld_path_diagnostic_contract"] = {
        "trigger_return_sha256": TRIGGER_RETURN_SHA256,
        "trigger_analysis_sha256": sha256(TRIGGER_ANALYSIS),
        "last_proven_good": (
            "sum_s1 GA input/output 32 and MSE4 write-data 8/8"
        ),
        "first_divergence": (
            "RD_DATA_CHANNEL_DATA_VLD_ABSENT_AFTER_INITIAL_SUM_S1_PROGRESS"
        ),
        "rtl_equations": [
            "buf_ag_bp_pre = !buf_ag_ob_full && "
            "rd_data_chl_data_ready && !nse2mse_req_barrier",
            "rd_data_chl_data_ready = "
            "rd_data_chl_data_vld && !rd_data_chl_ob_full",
        ],
        "runtime_enable": "+RETURN_OBS_RD_DATA_PATH",
        "runtime_limit": "+RETURN_OBS_RD_DATA_PATH_LIMIT=512",
        "time0_marker": "rd_data_path=1 rd_data_path_limit=512",
        "records": [
            "RD_DATA_VLD_PATH_EVENT_V1",
            "RD_DATA_VLD_PATH_COUNTS_V1",
            "RD_DATA_VLD_PATH_STATE_V1",
            "RD_DATA_VLD_PATH_WITNESS_V1",
        ],
        "observed_mse": [0, 3],
        "qualified_events": [
            "rd_data_chl_req_valid && rd_data_chl_req_ready",
            "mem2mse_rdata_valid[ch] && mse2mem_rdata_ready[ch]",
            "rd_chl_ib_wr_hs[ch]",
            "rd_chl_ib_rd_hs[ch]",
            "rd_data_chl_prepared_data_wr_hs",
            "rd_data_chl_prepared_data_rd_hs",
        ],
        "state_only": [
            "queue_full/empty",
            "inbuffer_valid/selector",
            "prepared_data_cnt",
            "queue_tsf_size",
            "mse_buf_spatial_size",
            "rd_data_chl_data_vld",
        ],
        "clock": "clk_sg",
        "stable_level_counts_as_progress": False,
        "read_only": True,
        "drives_dut": False,
        "changes_timeout": False,
    }
    manifest["post_generation_rule_drift"] = {
        "source_package": SOURCE_NAME,
        "source_package_sha256": SOURCE_SHA256,
        "old_server_rule_sha256":
            source_manifest["rule_receipts"]["server_rule_sha256"],
        "current_server_rule_sha256":
            receipt_by_path[".agents/rules/服务器测试包生成规则.md"],
        "content_neutral": False,
        "reason": (
            "v20 formal return requires continuous successor closure and a "
            "new RD data-valid path diagnostic; v23 retains the v22 "
            "feature-finalizer fix and adds the missing continuous-closure "
            "applicable-rule receipt found by the v22 final-ZIP audit"
        ),
    }
    manifest["v21_quarantine"] = {
        "zip_sha256":
            "898fc7ab72a062722c13fefa60a232e1bf361b6b799cd9cb1f8c248709b4bde2",
        "first_divergence":
            "EXIT_FINALIZER_RD_DATA_PATH_OK_UNBOUND_VARIABLE",
        "released": False,
    }
    manifest["v22_quarantine"] = {
        "zip_sha256":
            "5e9bf8ae98833a967ae5c9c8a41fb06ac91b691afa34dc1cf795f86857d2e821",
        "first_divergence":
            "FINAL_ZIP_MANIFEST_CONTINUOUS_CLOSURE_RULE_ID_ABSENT",
        "released": False,
    }
    feature = manifest["diagnostic_feature_runtime_enable_contract"]
    features = list(feature.get("features", []))
    features.append(
        {
            "name": "rd_data_vld_path",
            "runtime_enable": "+RETURN_OBS_RD_DATA_PATH",
            "runtime_limit": "+RETURN_OBS_RD_DATA_PATH_LIMIT=512",
            "time0_marker": "rd_data_path=1 rd_data_path_limit=512",
            "returned_binding_receipt":
                "evidence/observer_binding.txt",
            "return_target": "runs/return_observer.log",
            "zero_when_disabled":
                "DISABLED_INSTRUMENTATION_ZERO",
        }
    )
    feature["features"] = features
    manifest["generation_provenance"].update(
        {
            "tool":
                "tools/build_gap_node0071_rd_data_vld_diag_v21_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "numeric_payload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change": (
                "fresh identity plus read-only RD data-valid path observer"
            ),
        }
    )
    manifest["files"] = file_records(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_source()
    package = base.extract_source(destination)
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
    base.rewrite_identity(package)
    upgrade_observer(package / OBSERVER)
    upgrade_runner(package / "PREPARE_AND_RUN.sh")
    (package / "README.md").write_text(
        "# GAP node0071 v23 RD data-valid path diagnostic\n\n"
        f"Test ID: `{TEST_ID}`.\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It keeps the "
        "v20 workload/config/golden/execplan and existing qualified "
        "checkpoints byte-identical, then adds a bounded read-only MSE0/MSE3 "
        "RD_Data_Channel path observer below the v20 data-valid divergence.\n\n"
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
        path
        for path in source_records
        if source_records[path] != final_records[path]
    }
    if changed != ALLOWED_CHANGED:
        raise BuildError(f"changed path set differs: {sorted(changed)}")
    frozen = sorted(set(source_records) - ALLOWED_CHANGED)
    return package, {
        "source_v20_zip_sha256": SOURCE_SHA256,
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
        prefix="gap-node0071-v21-repeat-"
    ) as temp:
        repeated, _ = build_directory(Path(temp))
        repeated_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        deterministic_zip(
            repeated, repeated_zip, archive_root=INSTALL_NAME
        )
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
            "schema":
                "gap-node0071-rd-data-vld-path-rulefix-v23-build-v1",
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
        print(f"GAP v21 build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
