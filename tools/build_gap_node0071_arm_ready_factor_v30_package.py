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
from tools import build_gap_node0071_mse0_buffer_prep_group0_v29_package as base


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v29_mse0_buffer_prep_group0_diag"
INSTALL_NAME = "r5_n71_gap_v30_arm_ready_factor_diag"
TEST_ID = "r5-gap-node0071-v30-buffer0-arm-read-ready-factor-diagnostic"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = "15833d826872e118a9be834b082351ae2b31862da0b138a2a4f271269108e164"
TRIGGER_RETURN_SHA256 = "2b990565c41da4984bb1293ccbaf135a0f92ccee955e11653f25c60fd0c1a0bd"
TRIGGER_ANALYSIS = (
    ROOT / "artifacts/operator_config_validation/r5-gap-node0071-v29-return-analysis/report.json"
)
RTL_SYNC_REPORT = ROOT / "artifacts/rtl_sync/trassic_master_d0aa87f_20260803/report.json"
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


DECLARATIONS = r'''    // v30: Buffer0 ARM read-ready conjunction factor diagnostic.
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`BUFFER_BANK_NUM-1:0] return_obs_armf_mask_mon,
          return_obs_armf_bank_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`VALID_BUFFER_BANK_WIDTH-1:0] return_obs_armf_clear_reg_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_armf_nrm_barrier_mon;

    generate
        for (genvar return_obs_armf_group = 0;
             return_obs_armf_group < `SLICE_GROUP_SIZE;
             return_obs_armf_group++) begin : RETURN_OBS_ARMF_GROUP_GEN
            for (genvar return_obs_armf_slice = 0;
                 return_obs_armf_slice < `SLICE_GROUP_NUM;
                 return_obs_armf_slice++) begin : RETURN_OBS_ARMF_SLICE_GEN
                assign return_obs_armf_mask_mon
                    [return_obs_armf_group][return_obs_armf_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_armf_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_armf_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[0].u_Buffer_Manager.u_Buffer.buffer_mask;
                assign return_obs_armf_bank_ready_mon
                    [return_obs_armf_group][return_obs_armf_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_armf_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_armf_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[0].u_Buffer_Manager.u_Buffer.buf2arm_rreq_bank_ready;
                assign return_obs_armf_clear_reg_mon
                    [return_obs_armf_group][return_obs_armf_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_armf_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_armf_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[0].u_Buffer_Manager.u_Buffer.arm_clear_reg;
                assign return_obs_armf_nrm_barrier_mon
                    [return_obs_armf_group][return_obs_armf_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_armf_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_armf_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[0].u_Buffer_Manager.u_Buffer.nrm2buf_rd_barrier;
            end
        end
    endgenerate

    bit return_obs_armf_enabled;
    int return_obs_armf_limit;
    int return_obs_armf_emit_count;
    bit return_obs_armf_started;
    logic [`BUFFER_BANK_NUM-1:0] return_obs_armf_prev_bank_ready;
    bit return_obs_armf_prev_barrier;
    bit return_obs_armf_prev_ready;
    bit return_obs_armf_prev_blocked;
    longint unsigned return_obs_armf_accept_count;
    longint unsigned return_obs_armf_bank_edge_count;
    longint unsigned return_obs_armf_barrier_edge_count;
    longint unsigned return_obs_armf_ready_edge_count;
    longint unsigned return_obs_armf_block_entry_count;
    longint unsigned return_obs_armf_first_block;
    longint unsigned return_obs_armf_last_factor_edge;
    longint unsigned return_obs_armf_last_accept;

    task automatic return_obs_armf_reset;
        begin
            return_obs_armf_emit_count = 0;
            return_obs_armf_started = 1'b0;
            return_obs_armf_prev_bank_ready = 0;
            return_obs_armf_prev_barrier = 1'b0;
            return_obs_armf_prev_ready = 1'b0;
            return_obs_armf_prev_blocked = 1'b0;
            return_obs_armf_accept_count = 0;
            return_obs_armf_bank_edge_count = 0;
            return_obs_armf_barrier_edge_count = 0;
            return_obs_armf_ready_edge_count = 0;
            return_obs_armf_block_entry_count = 0;
            return_obs_armf_first_block = 0;
            return_obs_armf_last_factor_edge = 0;
            return_obs_armf_last_accept = 0;
        end
    endtask

'''


SUMMARY = r'''                    if (return_obs_armf_enabled) begin
                        $fdisplay(
                            return_obs_fd,
                            "%0t | BUFFER0_ARM_READY_FACTOR_COUNTS_V1 | event=%s accept=%0d bank_edge=%0d barrier_edge=%0d ready_edge=%0d block_entry=%0d records=%0d limit=%0d",
                            $time, event_name,
                            return_obs_armf_accept_count,
                            return_obs_armf_bank_edge_count,
                            return_obs_armf_barrier_edge_count,
                            return_obs_armf_ready_edge_count,
                            return_obs_armf_block_entry_count,
                            return_obs_armf_emit_count,
                            return_obs_armf_limit
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | BUFFER0_ARM_READY_FACTOR_STATE_V1 | event=%s req=0x%0h rw=%0b addr=0x%0h mask=0x%0h bank_ready=0x%0h selected_ready=0x%0h barrier=%0b composite_ready=%0b clear_at_addr=%0b valid_at_addr=0x%0h",
                            $time, event_name,
                            return_obs_flow_arm_req_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_flow_arm_rw_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_flow_arm_addr_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_armf_mask_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_armf_bank_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                            (return_obs_armf_mask_mon[return_obs_group_id][return_obs_local_slice_id] &
                             return_obs_armf_bank_ready_mon[return_obs_group_id][return_obs_local_slice_id]),
                            return_obs_armf_nrm_barrier_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_flow_arm_ready_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_armf_clear_reg_mon[return_obs_group_id][return_obs_local_slice_id]
                                [return_obs_flow_arm_addr_mon[return_obs_group_id][return_obs_local_slice_id][0]],
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
                            "%0t | BUFFER0_ARM_READY_FACTOR_WITNESS_V1 | event=%s first_block=%0d last_factor_edge=%0d last_accept=%0d",
                            $time, event_name,
                            return_obs_armf_first_block,
                            return_obs_armf_last_factor_edge,
                            return_obs_armf_last_accept
                        );
                    end
'''


SAMPLER = r'''    // v30 factor sampler: only qualified accepts and factor edges advance.
    always @(posedge u_NDP_Top_new.clk_sg) begin
        if (
            u_NDP_Top_new.rst_n_sg &&
            return_obs_enabled &&
            return_obs_armf_enabled &&
            return_obs_active &&
            return_obs_fd != 0
        ) begin
            bit armf_accept;
            bit armf_blocked;
            bit armf_bank_edge;
            bit armf_barrier_edge;
            bit armf_ready_edge;
            bit armf_block_entry;
            bit armf_any_event;
            armf_accept =
                (|return_obs_flow_arm_req_mon[return_obs_group_id][return_obs_local_slice_id][0]) &&
                !return_obs_flow_arm_rw_mon[return_obs_group_id][return_obs_local_slice_id][0] &&
                return_obs_flow_arm_ready_mon[return_obs_group_id][return_obs_local_slice_id][0];
            armf_blocked =
                (|return_obs_flow_arm_req_mon[return_obs_group_id][return_obs_local_slice_id][0]) &&
                !return_obs_flow_arm_rw_mon[return_obs_group_id][return_obs_local_slice_id][0] &&
                !return_obs_flow_arm_ready_mon[return_obs_group_id][return_obs_local_slice_id][0];
            armf_bank_edge = return_obs_armf_started &&
                return_obs_armf_bank_ready_mon[return_obs_group_id][return_obs_local_slice_id] !=
                return_obs_armf_prev_bank_ready;
            armf_barrier_edge = return_obs_armf_started &&
                return_obs_armf_nrm_barrier_mon[return_obs_group_id][return_obs_local_slice_id] !=
                return_obs_armf_prev_barrier;
            armf_ready_edge = return_obs_armf_started &&
                return_obs_flow_arm_ready_mon[return_obs_group_id][return_obs_local_slice_id][0] !=
                return_obs_armf_prev_ready;
            armf_block_entry = return_obs_armf_started &&
                armf_blocked && !return_obs_armf_prev_blocked;
            armf_any_event = armf_accept || armf_bank_edge ||
                armf_barrier_edge || armf_ready_edge || armf_block_entry;
            if (armf_accept) begin
                return_obs_armf_accept_count++;
                return_obs_armf_last_accept = return_obs_sg_clock_edge_count;
            end
            if (armf_bank_edge) begin
                return_obs_armf_bank_edge_count++;
                return_obs_armf_last_factor_edge = return_obs_sg_clock_edge_count;
            end
            if (armf_barrier_edge) begin
                return_obs_armf_barrier_edge_count++;
                return_obs_armf_last_factor_edge = return_obs_sg_clock_edge_count;
            end
            if (armf_ready_edge) begin
                return_obs_armf_ready_edge_count++;
                return_obs_armf_last_factor_edge = return_obs_sg_clock_edge_count;
            end
            if (armf_block_entry) begin
                return_obs_armf_block_entry_count++;
                if (return_obs_armf_first_block == 0)
                    return_obs_armf_first_block = return_obs_sg_clock_edge_count;
            end
            if (armf_any_event && return_obs_armf_emit_count < return_obs_armf_limit) begin
                return_obs_armf_emit_count++;
                $fdisplay(
                    return_obs_fd,
                    "%0t | BUFFER0_ARM_READY_FACTOR_EVENT_V1 | n=%0d sg_edge=%0d accept=%0b block_entry=%0b req=0x%0h rw=%0b addr=0x%0h mask=0x%0h bank_ready=0x%0h selected_ready=0x%0h barrier=%0b composite_ready=%0b clear_at_addr=%0b valid_at_addr=0x%0h",
                    $time, return_obs_armf_emit_count,
                    return_obs_sg_clock_edge_count,
                    armf_accept, armf_block_entry,
                    return_obs_flow_arm_req_mon[return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_flow_arm_rw_mon[return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_flow_arm_addr_mon[return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_armf_mask_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_armf_bank_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                    (return_obs_armf_mask_mon[return_obs_group_id][return_obs_local_slice_id] &
                     return_obs_armf_bank_ready_mon[return_obs_group_id][return_obs_local_slice_id]),
                    return_obs_armf_nrm_barrier_mon[return_obs_group_id][return_obs_local_slice_id],
                    return_obs_flow_arm_ready_mon[return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_armf_clear_reg_mon[return_obs_group_id][return_obs_local_slice_id]
                        [return_obs_flow_arm_addr_mon[return_obs_group_id][return_obs_local_slice_id][0]],
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
            end
            return_obs_armf_started = 1'b1;
            return_obs_armf_prev_bank_ready =
                return_obs_armf_bank_ready_mon[return_obs_group_id][return_obs_local_slice_id];
            return_obs_armf_prev_barrier =
                return_obs_armf_nrm_barrier_mon[return_obs_group_id][return_obs_local_slice_id];
            return_obs_armf_prev_ready =
                return_obs_flow_arm_ready_mon[return_obs_group_id][return_obs_local_slice_id][0];
            return_obs_armf_prev_blocked = armf_blocked;
            $fflush(return_obs_fd);
        end
    end

'''


def correct_v29_group0(text: str) -> str:
    old = (
        "            m0_group0_accept =\n"
        "                (|return_obs_ga_group_out_tag_mon[return_obs_group_id][return_obs_local_slice_id][0][0]) &&\n"
        "                return_obs_ga_group_bp_post_mon[return_obs_group_id][return_obs_local_slice_id][0];\n"
    )
    new = (
        "            m0_group0_accept = 1'b0;\n"
        "            for (int m0_group_row = 0; m0_group_row < `GA_ROW_PE_NUM; m0_group_row++) begin\n"
        "                m0_group0_accept |= return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][0]\n"
        "                    [m0_group_row][`GA_INPORT_TAG-1];\n"
        "            end\n"
        "            m0_group0_accept &=\n"
        "                return_obs_ga_group_bp_post_mon[return_obs_group_id][return_obs_local_slice_id][0];\n"
    )
    return replace_once(text, old, new, "v29 group0 qualified fix")


def upgrade_observer(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = correct_v29_group0(text)
    text = replace_once(
        text, "    bit return_obs_enabled;\n",
        DECLARATIONS + "    bit return_obs_enabled;\n", "v30 declarations",
    )
    text = replace_once(
        text,
        '        return_obs_m0path_enabled =\n'
        '            $test$plusargs("RETURN_OBS_MSE0_BUFFER_PREP_GROUP0");\n',
        '        return_obs_m0path_enabled =\n'
        '            $test$plusargs("RETURN_OBS_MSE0_BUFFER_PREP_GROUP0");\n'
        '        return_obs_armf_enabled =\n'
        '            $test$plusargs("RETURN_OBS_BUFFER0_ARM_READY_FACTORS");\n',
        "v30 plusarg",
    )
    text = replace_once(
        text, "        return_obs_m0path_limit = 512;\n",
        "        return_obs_m0path_limit = 512;\n"
        "        return_obs_armf_limit = 256;\n", "v30 default limit",
    )
    text = replace_once(
        text,
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_FILE=%s",\n',
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=%d",\n'
        '                return_obs_armf_limit\n'
        '            );\n'
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_FILE=%s",\n',
        "v30 limit plusarg",
    )
    text = text.replace(
        "        return_obs_m0path_reset();\n",
        "        return_obs_m0path_reset();\n"
        "        return_obs_armf_reset();\n",
    )
    if text.count("return_obs_armf_reset();") != 2:
        raise BuildError("v30 reset call count differs")
    text = replace_once(
        text,
        "                    if (return_obs_m0path_enabled) begin\n",
        SUMMARY + "                    if (return_obs_m0path_enabled) begin\n",
        "v30 summary",
    )
    text = replace_once(
        text,
        "mse0_buffer_prep_group0=%0d mse0_buffer_prep_group0_limit=%0d",
        "mse0_buffer_prep_group0=%0d mse0_buffer_prep_group0_limit=%0d "
        "buffer0_arm_ready_factors=%0d buffer0_arm_ready_factors_limit=%0d",
        "v30 time0 format",
    )
    text = replace_once(
        text,
        "                        return_obs_m0path_enabled,\n"
        "                        return_obs_m0path_limit\n",
        "                        return_obs_m0path_enabled,\n"
        "                        return_obs_m0path_limit,\n"
        "                        return_obs_armf_enabled,\n"
        "                        return_obs_armf_limit\n",
        "v30 time0 args",
    )
    text = replace_once(
        text, "    final begin\n", SAMPLER + "    final begin\n", "v30 sampler",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def upgrade_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "  +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512\n",
        "  +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512\n"
        "  +RETURN_OBS_BUFFER0_ARM_READY_FACTORS\n"
        "  +RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256\n",
        "runner v30 plusargs",
    )
    text = replace_once(
        text,
        "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512 +RETURN_OBS_FILE=",
        "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512 "
        "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS "
        "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256 +RETURN_OBS_FILE=",
        "runner v30 argv receipt",
    )
    marker = (
        "  if [ \"$mse0_path_ok\" = true ]; then\n"
        "    printf 'mse0_buffer_prep_group0_enabled=true\\n"
        "mse0_buffer_prep_group0_limit=512\\n"
        "mse0_buffer_prep_group0_records_returned=true\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  else\n"
        "    printf 'mse0_buffer_prep_group0_enabled=false\\n"
        "mse0_buffer_prep_group0_limit=UNKNOWN\\n"
        "mse0_buffer_prep_group0_records_returned=false\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  fi\n"
    )
    addition = marker + (
        "  if [ \"$observer_ok\" = true ] && "
        "grep -Fq 'buffer0_arm_ready_factors=1' \"$observer_log\" && "
        "grep -Fq 'buffer0_arm_ready_factors_limit=256' \"$observer_log\" && "
        "grep -Fq 'BUFFER0_ARM_READY_FACTOR_COUNTS_V1' \"$observer_log\" && "
        "grep -Fq 'BUFFER0_ARM_READY_FACTOR_STATE_V1' \"$observer_log\" && "
        "grep -Fq 'BUFFER0_ARM_READY_FACTOR_WITNESS_V1' \"$observer_log\"; then\n"
        "    arm_ready_factor_ok=true\n"
        "  else\n"
        "    arm_ready_factor_ok=false\n"
        "  fi\n"
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
    text = replace_once(text, marker, addition, "runner v30 receipt")
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
    manifest = base.base.base.base.base.replace_identity(source_manifest)
    receipts = current_receipts(source_manifest)
    manifest.update(
        {
            "schema": "gap-node0071-buffer0-arm-ready-factor-diagnostic-package-v30",
            "test_id": TEST_ID,
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "read-only Buffer0 ARM read request to selected-bank "
                "readiness and NRM read-barrier conjunction"
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
        "resolution": "fresh v30 exact final bytes bind current rules",
    }
    manifest["buffer0_arm_ready_factor_diagnostic_contract"] = {
        "trigger_return_sha256": TRIGGER_RETURN_SHA256,
        "trigger_analysis_sha256": sha256(TRIGGER_ANALYSIS),
        "last_proven_good": (
            "8 active-window MSE0 buffer accepts reach prepared writes; "
            "2 ARM accepts clear and 5 prepared reads produce data_vld"
        ),
        "first_divergence": (
            "BUFFER0_ARM_READ_REQUEST_0xFF_HELD_WITH_"
            "BUF2ARM_REQ_READY_0_AFTER_TWO_ACCEPTS"
        ),
        "runtime_enable": "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS",
        "runtime_limit": "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256",
        "time0_marker": (
            "buffer0_arm_ready_factors=1 "
            "buffer0_arm_ready_factors_limit=256"
        ),
        "records": [
            "BUFFER0_ARM_READY_FACTOR_EVENT_V1",
            "BUFFER0_ARM_READY_FACTOR_COUNTS_V1",
            "BUFFER0_ARM_READY_FACTOR_STATE_V1",
            "BUFFER0_ARM_READY_FACTOR_WITNESS_V1",
        ],
        "clock": "clk_sg",
        "ready_equation": (
            "buf2arm_rreq_ready=&(~buffer_mask|"
            "buf2arm_rreq_bank_ready)&~nrm2buf_rd_barrier"
        ),
        "bank_ready_equation": (
            "bank_ready[bank]=&valid_buf[bank][arm_addr]&"
            "~arm_clear_reg[arm_addr]"
        ),
        "qualified_events": [
            "ARM read request and composite-ready accept",
            "bank-ready vector edge",
            "NRM read-barrier edge",
            "composite-ready edge",
            "first transition into blocked read request",
        ],
        "state_only": [
            "stable request/ready/barrier level",
            "stable mask/address/valid/clear level",
        ],
        "stable_level_counts_as_progress": False,
        "read_only": True,
        "drives_dut": False,
        "changes_timeout": False,
        "v29_observer_correction": (
            "group0 counter now uses the GA valid tag bit across rows; "
            "nonzero stable tag level is not counted"
        ),
        "hdl_positive_control_scope": (
            "v30 XMR declarations/assignments/reset/update/use and corrected "
            "v29 group0 qualified expression"
        ),
    }
    feature = manifest["diagnostic_feature_runtime_enable_contract"]
    feature["features"] = list(feature.get("features", [])) + [
        {
            "name": "buffer0_arm_ready_factors",
            "runtime_enable": "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS",
            "runtime_limit": "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256",
            "time0_marker": (
                "buffer0_arm_ready_factors=1 "
                "buffer0_arm_ready_factors_limit=256"
            ),
            "returned_binding_receipt": "evidence/observer_binding.txt",
            "return_target": "runs/return_observer.log",
            "zero_when_disabled": "DISABLED_INSTRUMENTATION_ZERO",
        }
    ]
    manifest["active_rtl_identity"] = {
        "commit": "d0aa87f682880a260fb792aaac88f70a23aba414",
        "sync_report": str(RTL_SYNC_REPORT.relative_to(ROOT)).replace("\\", "/"),
        "sync_report_sha256": sha256(RTL_SYNC_REPORT),
        "gap_fix_assumed": False,
    }
    manifest["generation_provenance"].update(
        {
            "tool": "tools/build_gap_node0071_arm_ready_factor_v30_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "trigger_return_sha256": TRIGGER_RETURN_SHA256,
            "numeric_payload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change": (
                "correct v29 stable-level group0 counter and add bounded "
                "Buffer0 ARM ready conjunction factor observer"
            ),
        }
    )
    manifest["files"] = file_records(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_source()
    package = base.base.base.base.base.extract_source(destination)
    source_manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    source_records = file_records(package, exclude_manifest=False)
    numeric_before = {
        path: record
        for path, record in file_records(package / "workload", exclude_manifest=False).items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    base.base.base.base.base.rewrite_identity(package)
    upgrade_observer(package / OBSERVER)
    upgrade_runner(package / "PREPARE_AND_RUN.sh")
    (package / "README.md").write_text(
        "# GAP node0071 v30 Buffer0 ARM-ready factor diagnostic\n\n"
        f"Test ID: `{TEST_ID}`.\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It preserves "
        "the frozen numeric/config/golden/execplan/functional-RTL payload and "
        "adds bounded read-only selected-bank-ready versus NRM-barrier factor "
        "evidence. It also corrects the v29 package-local group0 stable-level "
        "counter; no DUT behavior changes.\n\n"
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
        "source_v29_zip_sha256": SOURCE_SHA256,
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
    with tempfile.TemporaryDirectory(prefix="gap-node0071-v30-repeat-") as temp:
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
            "schema": "gap-node0071-buffer0-arm-ready-factor-v30-build-v1",
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
