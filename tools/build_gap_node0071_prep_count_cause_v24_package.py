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
from tools import build_gap_node0071_rd_data_vld_diag_v21_package as base


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v23_rd_data_vld_path_rulefix"
INSTALL_NAME = "r5_n71_gap_v24_prep_count_cause_diag"
TEST_ID = "r5-gap-node0071-v24-prep-count-cause-diagnostic"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = (
    "07ea69a9b647542751c3e47b192d5d1ddb497dad97801e75c9fe002331244c19"
)
TRIGGER_RETURN_SHA256 = (
    "b00dd10f4710509a5a7701182a6fdd09309e5e50a3a9debbadd44a688612b0a6"
)
TRIGGER_ANALYSIS = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-gap-node0071-v23-return-analysis/report.json"
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


def xmr_prefix(mse: int) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_pc_group]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[return_obs_pc_slice]"
        ".u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine"
        f".MSE_INST[{mse}].RD_MSE.u_Memory_RD_Stream_Engine"
        ".u_RD_Data_Channel"
    )


def declarations() -> str:
    lines = [
        "    // v24: read-only prepared-data counter update-cause diagnostic.",
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]",
        "          return_obs_pc_rst_n_mon, return_obs_pc_slice_rst_mon,",
        "          return_obs_pc_wr_mon, return_obs_pc_rd_mon,",
        "          return_obs_pc_data_vld_mon, return_obs_pc_lt_req_mon,",
        "          return_obs_pc_bp_pre_mon, return_obs_pc_ob_bp_pre_mon;",
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]",
        "          [1:0][7:0] return_obs_pc_count_mon,",
        "                      return_obs_pc_tsf_mon,",
        "                      return_obs_pc_spatial_mon;",
        "",
        "    generate",
        "        for (genvar return_obs_pc_group = 0;",
        "             return_obs_pc_group < `SLICE_GROUP_SIZE;",
        "             return_obs_pc_group++) begin : RETURN_OBS_PC_GROUP_GEN",
        "            for (genvar return_obs_pc_slice = 0;",
        "                 return_obs_pc_slice < `SLICE_GROUP_NUM;",
        "                 return_obs_pc_slice++) begin : RETURN_OBS_PC_SLICE_GEN",
    ]
    for slot, mse in enumerate((0, 3)):
        prefix = xmr_prefix(mse)
        fields = {
            "return_obs_pc_rst_n_mon": f"{prefix}.rst_n",
            "return_obs_pc_slice_rst_mon": f"{prefix}.slice_rst",
            "return_obs_pc_wr_mon":
                f"{prefix}.rd_data_chl_prepared_data_wr_hs",
            "return_obs_pc_rd_mon":
                f"{prefix}.rd_data_chl_prepared_data_rd_hs",
            "return_obs_pc_data_vld_mon":
                f"{prefix}.rd_data_chl_data_vld",
            "return_obs_pc_lt_req_mon": f"{prefix}.prepared_data_lt_req",
            "return_obs_pc_bp_pre_mon":
                f"{prefix}.rd_data_chl_prepared_data_bp_pre",
            "return_obs_pc_ob_bp_pre_mon":
                f"{prefix}.rd_data_chl_ob_bp_pre",
            "return_obs_pc_count_mon":
                f"{prefix}.rd_data_chl_prepared_data_cnt",
            "return_obs_pc_tsf_mon":
                f"{prefix}.rd_chl_queue_rd_tsf_size",
            "return_obs_pc_spatial_mon":
                f"{prefix}.mse_buf_spatial_size",
        }
        for target, expression in fields.items():
            lines.extend(
                [
                    f"                assign {target}[return_obs_pc_group]"
                    f"[return_obs_pc_slice][{slot}] =",
                    f"                    {expression};",
                ]
            )
    lines.extend(
        [
            "            end",
            "        end",
            "    endgenerate",
            "",
            "    bit return_obs_pc_enabled;",
            "    int return_obs_pc_limit;",
            "    int return_obs_pc_emit_count;",
            "    bit return_obs_pc_started [0:1];",
            "    bit return_obs_pc_prev_rst_n [0:1];",
            "    bit return_obs_pc_prev_slice_rst [0:1];",
            "    bit return_obs_pc_prev_wr [0:1];",
            "    bit return_obs_pc_prev_rd [0:1];",
            "    logic [7:0] return_obs_pc_prev_count [0:1];",
            "    logic [7:0] return_obs_pc_prev_tsf [0:1];",
            "    logic [7:0] return_obs_pc_prev_spatial [0:1];",
            "    longint unsigned return_obs_pc_wr_count [0:1];",
            "    longint unsigned return_obs_pc_rd_count [0:1];",
            "    longint unsigned return_obs_pc_count_change [0:1];",
            "    longint unsigned return_obs_pc_slice_rst_edge [0:1];",
            "    longint unsigned return_obs_pc_rst_n_edge [0:1];",
            "    longint unsigned return_obs_pc_no_effect_count [0:1];",
            "    longint unsigned return_obs_pc_first_no_effect [0:1];",
            "    longint unsigned return_obs_pc_last_no_effect [0:1];",
            "    longint unsigned return_obs_pc_first_local_reset [0:1];",
            "    longint unsigned return_obs_pc_last_local_reset [0:1];",
            "    bit return_obs_pc_no_effect_seen [0:1];",
            "    bit return_obs_pc_local_reset_seen [0:1];",
            "",
            "    task automatic return_obs_pc_reset;",
            "        begin",
            "            return_obs_pc_emit_count = 0;",
            "            for (int pc_flow = 0; pc_flow < 2; pc_flow++) begin",
            "                return_obs_pc_started[pc_flow] = 1'b0;",
            "                return_obs_pc_prev_rst_n[pc_flow] = 1'b0;",
            "                return_obs_pc_prev_slice_rst[pc_flow] = 1'b0;",
            "                return_obs_pc_prev_wr[pc_flow] = 1'b0;",
            "                return_obs_pc_prev_rd[pc_flow] = 1'b0;",
            "                return_obs_pc_prev_count[pc_flow] = 0;",
            "                return_obs_pc_prev_tsf[pc_flow] = 0;",
            "                return_obs_pc_prev_spatial[pc_flow] = 0;",
            "                return_obs_pc_wr_count[pc_flow] = 0;",
            "                return_obs_pc_rd_count[pc_flow] = 0;",
            "                return_obs_pc_count_change[pc_flow] = 0;",
            "                return_obs_pc_slice_rst_edge[pc_flow] = 0;",
            "                return_obs_pc_rst_n_edge[pc_flow] = 0;",
            "                return_obs_pc_no_effect_count[pc_flow] = 0;",
            "                return_obs_pc_first_no_effect[pc_flow] = 0;",
            "                return_obs_pc_last_no_effect[pc_flow] = 0;",
            "                return_obs_pc_first_local_reset[pc_flow] = 0;",
            "                return_obs_pc_last_local_reset[pc_flow] = 0;",
            "                return_obs_pc_no_effect_seen[pc_flow] = 1'b0;",
            "                return_obs_pc_local_reset_seen[pc_flow] = 1'b0;",
            "            end",
            "        end",
            "    endtask",
            "",
        ]
    )
    return "\n".join(lines)


SUMMARY = r'''                    if (return_obs_pc_enabled) begin
                        $fdisplay(
                            return_obs_fd,
                            "%0t | PREP_COUNT_CAUSE_COUNTS_V1 | event=%s wr=%0d/%0d rd=%0d/%0d count_change=%0d/%0d slice_rst_edge=%0d/%0d rst_n_edge=%0d/%0d no_effect=%0d/%0d records=%0d limit=%0d",
                            $time, event_name,
                            return_obs_pc_wr_count[0], return_obs_pc_wr_count[1],
                            return_obs_pc_rd_count[0], return_obs_pc_rd_count[1],
                            return_obs_pc_count_change[0], return_obs_pc_count_change[1],
                            return_obs_pc_slice_rst_edge[0], return_obs_pc_slice_rst_edge[1],
                            return_obs_pc_rst_n_edge[0], return_obs_pc_rst_n_edge[1],
                            return_obs_pc_no_effect_count[0], return_obs_pc_no_effect_count[1],
                            return_obs_pc_emit_count, return_obs_pc_limit
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | PREP_COUNT_CAUSE_STATE_V1 | event=%s rst_n=0x%0h slice_rst=0x%0h wr=0x%0h rd=0x%0h count=0x%0h tsf=0x%0h spatial=0x%0h lt_req=0x%0h bp_pre=0x%0h ob_bp_pre=0x%0h data_vld=0x%0h",
                            $time, event_name,
                            return_obs_pc_rst_n_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pc_slice_rst_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pc_wr_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pc_rd_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pc_count_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pc_tsf_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pc_spatial_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pc_lt_req_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pc_bp_pre_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pc_ob_bp_pre_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_pc_data_vld_mon[return_obs_group_id][return_obs_local_slice_id]
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | PREP_COUNT_CAUSE_WITNESS_V1 | event=%s mse0_no_effect=%0d:%0d mse3_no_effect=%0d:%0d mse0_local_reset=%0d:%0d mse3_local_reset=%0d:%0d seen_no_effect=0x%0h seen_local_reset=0x%0h",
                            $time, event_name,
                            return_obs_pc_first_no_effect[0], return_obs_pc_last_no_effect[0],
                            return_obs_pc_first_no_effect[1], return_obs_pc_last_no_effect[1],
                            return_obs_pc_first_local_reset[0], return_obs_pc_last_local_reset[0],
                            return_obs_pc_first_local_reset[1], return_obs_pc_last_local_reset[1],
                            {return_obs_pc_no_effect_seen[1], return_obs_pc_no_effect_seen[0]},
                            {return_obs_pc_local_reset_seen[1], return_obs_pc_local_reset_seen[0]}
                        );
                    end
'''


SAMPLER = r'''
    // v24 qualified counter-cause checks. A stable level is state only.
    always @(posedge u_NDP_Top_new.clk_sg) begin
        if (
            u_NDP_Top_new.rst_n_sg &&
            return_obs_enabled &&
            return_obs_pc_enabled &&
            return_obs_active &&
            return_obs_fd != 0
        ) begin
            for (int pc_flow = 0; pc_flow < 2; pc_flow++) begin
                bit pc_event;
                bit pc_no_effect;
                pc_event = 1'b0;
                pc_no_effect = 1'b0;
                if (return_obs_pc_started[pc_flow]) begin
                    if (return_obs_pc_wr_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow])
                        return_obs_pc_wr_count[pc_flow]++;
                    if (return_obs_pc_rd_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow])
                        return_obs_pc_rd_count[pc_flow]++;
                    if (return_obs_pc_count_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow] != return_obs_pc_prev_count[pc_flow])
                        return_obs_pc_count_change[pc_flow]++;
                    if (return_obs_pc_slice_rst_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow] != return_obs_pc_prev_slice_rst[pc_flow])
                        return_obs_pc_slice_rst_edge[pc_flow]++;
                    if (return_obs_pc_rst_n_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow] != return_obs_pc_prev_rst_n[pc_flow])
                        return_obs_pc_rst_n_edge[pc_flow]++;
                    if (
                        return_obs_pc_prev_rst_n[pc_flow] &&
                        !return_obs_pc_prev_slice_rst[pc_flow] &&
                        return_obs_pc_prev_wr[pc_flow] &&
                        !return_obs_pc_prev_rd[pc_flow] &&
                        return_obs_pc_count_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow] == return_obs_pc_prev_count[pc_flow]
                    ) begin
                        pc_no_effect = 1'b1;
                        return_obs_pc_no_effect_count[pc_flow]++;
                        if (!return_obs_pc_no_effect_seen[pc_flow])
                            return_obs_pc_first_no_effect[pc_flow] = return_obs_sg_clock_edge_count;
                        return_obs_pc_no_effect_seen[pc_flow] = 1'b1;
                        return_obs_pc_last_no_effect[pc_flow] = return_obs_sg_clock_edge_count;
                    end
                    if (
                        !return_obs_pc_rst_n_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow] ||
                        return_obs_pc_slice_rst_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow]
                    ) begin
                        if (!return_obs_pc_local_reset_seen[pc_flow])
                            return_obs_pc_first_local_reset[pc_flow] = return_obs_sg_clock_edge_count;
                        return_obs_pc_local_reset_seen[pc_flow] = 1'b1;
                        return_obs_pc_last_local_reset[pc_flow] = return_obs_sg_clock_edge_count;
                    end
                    pc_event =
                        return_obs_pc_wr_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow] ||
                        return_obs_pc_rd_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow] ||
                        (return_obs_pc_count_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow] != return_obs_pc_prev_count[pc_flow]) ||
                        (return_obs_pc_slice_rst_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow] != return_obs_pc_prev_slice_rst[pc_flow]) ||
                        (return_obs_pc_rst_n_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow] != return_obs_pc_prev_rst_n[pc_flow]) ||
                        pc_no_effect;
                    if (pc_event && return_obs_pc_emit_count < return_obs_pc_limit) begin
                        return_obs_pc_emit_count++;
                        $fdisplay(
                            return_obs_fd,
                            "%0t | PREP_COUNT_CAUSE_EVENT_V1 | n=%0d mse=%0d sg_edge=%0d prev_rst_n=%0b prev_slice_rst=%0b prev_wr=%0b prev_rd=%0b prev_count=%0d prev_tsf=%0d prev_spatial=%0d rst_n=%0b slice_rst=%0b wr=%0b rd=%0b count=%0d tsf=%0d spatial=%0d no_effect=%0b lt_req=%0b bp_pre=%0b ob_bp_pre=%0b data_vld=%0b",
                            $time, return_obs_pc_emit_count, (pc_flow == 0 ? 0 : 3),
                            return_obs_sg_clock_edge_count,
                            return_obs_pc_prev_rst_n[pc_flow],
                            return_obs_pc_prev_slice_rst[pc_flow],
                            return_obs_pc_prev_wr[pc_flow],
                            return_obs_pc_prev_rd[pc_flow],
                            return_obs_pc_prev_count[pc_flow],
                            return_obs_pc_prev_tsf[pc_flow],
                            return_obs_pc_prev_spatial[pc_flow],
                            return_obs_pc_rst_n_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow],
                            return_obs_pc_slice_rst_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow],
                            return_obs_pc_wr_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow],
                            return_obs_pc_rd_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow],
                            return_obs_pc_count_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow],
                            return_obs_pc_tsf_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow],
                            return_obs_pc_spatial_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow],
                            pc_no_effect,
                            return_obs_pc_lt_req_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow],
                            return_obs_pc_bp_pre_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow],
                            return_obs_pc_ob_bp_pre_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow],
                            return_obs_pc_data_vld_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow]
                        );
                    end
                end
                else begin
                    return_obs_pc_started[pc_flow] = 1'b1;
                end
                return_obs_pc_prev_rst_n[pc_flow] =
                    return_obs_pc_rst_n_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow];
                return_obs_pc_prev_slice_rst[pc_flow] =
                    return_obs_pc_slice_rst_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow];
                return_obs_pc_prev_wr[pc_flow] =
                    return_obs_pc_wr_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow];
                return_obs_pc_prev_rd[pc_flow] =
                    return_obs_pc_rd_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow];
                return_obs_pc_prev_count[pc_flow] =
                    return_obs_pc_count_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow];
                return_obs_pc_prev_tsf[pc_flow] =
                    return_obs_pc_tsf_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow];
                return_obs_pc_prev_spatial[pc_flow] =
                    return_obs_pc_spatial_mon[return_obs_group_id][return_obs_local_slice_id][pc_flow];
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
        "prepared count declarations",
    )
    text = replace_once(
        text,
        '        return_obs_rd_path_enabled =\n'
        '            $test$plusargs("RETURN_OBS_RD_DATA_PATH");\n',
        '        return_obs_rd_path_enabled =\n'
        '            $test$plusargs("RETURN_OBS_RD_DATA_PATH");\n'
        '        return_obs_pc_enabled =\n'
        '            $test$plusargs("RETURN_OBS_PREP_COUNT_CAUSE");\n',
        "prepared count feature plusarg",
    )
    text = replace_once(
        text,
        "        return_obs_rd_path_limit = 512;\n",
        "        return_obs_rd_path_limit = 512;\n"
        "        return_obs_pc_limit = 512;\n",
        "prepared count default limit",
    )
    text = replace_once(
        text,
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_FILE=%s",\n',
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=%d",\n'
        '                return_obs_pc_limit\n'
        '            );\n'
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_FILE=%s",\n',
        "prepared count limit plusarg",
    )
    text = text.replace(
        "        return_obs_rd_path_reset();\n",
        "        return_obs_rd_path_reset();\n"
        "        return_obs_pc_reset();\n",
    )
    if text.count("return_obs_pc_reset();") != 2:
        raise BuildError("prepared count reset call count differs")
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
        "prepared count summary",
    )
    text = replace_once(
        text,
        "bp_factor_limit=%0d rd_data_path=%0d rd_data_path_limit=%0d",
        "bp_factor_limit=%0d rd_data_path=%0d rd_data_path_limit=%0d "
        "prep_count_cause=%0d prep_count_cause_limit=%0d",
        "prepared count time0 format",
    )
    text = replace_once(
        text,
        "                        return_obs_rd_path_enabled,\n"
        "                        return_obs_rd_path_limit\n",
        "                        return_obs_rd_path_enabled,\n"
        "                        return_obs_rd_path_limit,\n"
        "                        return_obs_pc_enabled,\n"
        "                        return_obs_pc_limit\n",
        "prepared count time0 args",
    )
    text = replace_once(
        text,
        "    final begin\n",
        SAMPLER + "    final begin\n",
        "prepared count sampler",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def upgrade_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "  +RETURN_OBS_RD_DATA_PATH_LIMIT=512\n",
        "  +RETURN_OBS_RD_DATA_PATH_LIMIT=512\n"
        "  +RETURN_OBS_PREP_COUNT_CAUSE\n"
        "  +RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512\n",
        "runner simulator plusargs",
    )
    text = replace_once(
        text,
        "+RETURN_OBS_RD_DATA_PATH_LIMIT=512 +RETURN_OBS_FILE=",
        "+RETURN_OBS_RD_DATA_PATH_LIMIT=512 "
        "+RETURN_OBS_PREP_COUNT_CAUSE "
        "+RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512 +RETURN_OBS_FILE=",
        "runner command receipt",
    )
    marker = (
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
    addition = marker + (
        "  if [ \"$observer_ok\" = true ] && "
        "grep -Fq 'prep_count_cause=1' \"$observer_log\" && "
        "grep -Fq 'prep_count_cause_limit=512' \"$observer_log\" && "
        "grep -Fq 'PREP_COUNT_CAUSE_COUNTS_V1' \"$observer_log\" && "
        "grep -Fq 'PREP_COUNT_CAUSE_STATE_V1' \"$observer_log\" && "
        "grep -Fq 'PREP_COUNT_CAUSE_WITNESS_V1' \"$observer_log\"; then\n"
        "    prep_count_cause_ok=true\n"
        "  else\n"
        "    prep_count_cause_ok=false\n"
        "  fi\n"
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
    manifest = base.base.replace_identity(source_manifest)
    receipts = current_receipts(source_manifest)
    receipt_by_path = {item["path"]: item["sha256"] for item in receipts}
    manifest.update(
        {
            "schema":
                "gap-node0071-prepared-count-cause-diagnostic-package-v24",
            "test_id": TEST_ID,
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "read-only MSE0/MSE3 prepared-data counter local reset and "
                "update-priority localization"
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
    rules = manifest["rule_receipts"]
    for path, digest in receipt_by_path.items():
        if "服务器测试包生成规则" in path:
            rules["server_rule_sha256"] = digest
        elif path.endswith("GAP_probe_v7_validator_rules.md"):
            rules["gap_probe_rule_sha256"] = digest
        elif path.endswith("GAP_int32_mac_bypass_rules.md"):
            rules["gap_int32_rule_sha256"] = digest
    rules["current_match"] = True
    rules["plan_sha256_mutable_provenance_only"] = sha256(
        ROOT / ".agents/plan.md"
    )
    manifest["prepared_count_cause_diagnostic_contract"] = {
        "trigger_return_sha256": TRIGGER_RETURN_SHA256,
        "trigger_analysis_sha256": sha256(TRIGGER_ANALYSIS),
        "last_proven_good": (
            "MSE0/MSE3 memory-return 5,5/5,5 and prepared writes 6/10"
        ),
        "first_divergence": (
            "MSE3_PREPARED_DATA_COUNT_NOT_RETAINED_AFTER_QUALIFIED_WRITES"
        ),
        "runtime_enable": "+RETURN_OBS_PREP_COUNT_CAUSE",
        "runtime_limit": "+RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512",
        "time0_marker":
            "prep_count_cause=1 prep_count_cause_limit=512",
        "records": [
            "PREP_COUNT_CAUSE_EVENT_V1",
            "PREP_COUNT_CAUSE_COUNTS_V1",
            "PREP_COUNT_CAUSE_STATE_V1",
            "PREP_COUNT_CAUSE_WITNESS_V1",
        ],
        "observed_mse": [0, 3],
        "counter_equation": (
            "if !rst_n or slice_rst: count'=0; else if wr&&rd: "
            "count'=count+tsf-spatial; else if wr: count'=count+tsf; "
            "else if rd: count'=count-spatial"
        ),
        "qualified_events": [
            "prepared_data_wr_hs",
            "prepared_data_rd_hs",
            "prepared_data_cnt change",
            "slice_rst edge",
            "rst_n edge",
        ],
        "state_only": [
            "stable rst_n/slice_rst level",
            "prepared_data_cnt level",
            "tsf/spatial level",
            "data_vld/lt_req/bp_pre level",
            "no_effect diagnostic count",
        ],
        "clock": "clk_sg",
        "stable_level_counts_as_progress": False,
        "read_only": True,
        "drives_dut": False,
        "changes_timeout": False,
    }
    feature = manifest["diagnostic_feature_runtime_enable_contract"]
    feature["features"] = list(feature.get("features", [])) + [
        {
            "name": "prepared_count_cause",
            "runtime_enable": "+RETURN_OBS_PREP_COUNT_CAUSE",
            "runtime_limit": "+RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512",
            "time0_marker":
                "prep_count_cause=1 prep_count_cause_limit=512",
            "returned_binding_receipt":
                "evidence/observer_binding.txt",
            "return_target": "runs/return_observer.log",
            "zero_when_disabled":
                "DISABLED_INSTRUMENTATION_ZERO",
        }
    ]
    manifest["generation_provenance"].update(
        {
            "tool":
                "tools/build_gap_node0071_prep_count_cause_v24_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "trigger_return_sha256": TRIGGER_RETURN_SHA256,
            "numeric_payload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change": (
                "fresh identity plus bounded read-only MSE0/MSE3 prepared "
                "counter update-cause observer"
            ),
        }
    )
    manifest["files"] = file_records(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_source()
    package = base.base.extract_source(destination)
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
    base.base.rewrite_identity(package)
    upgrade_observer(package / OBSERVER)
    upgrade_runner(package / "PREPARE_AND_RUN.sh")
    (package / "README.md").write_text(
        "# GAP node0071 v24 prepared-count cause diagnostic\n\n"
        f"Test ID: `{TEST_ID}`.\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It keeps all "
        "73 frozen numeric/workload files, config, golden, execplan and "
        "functional RTL semantics unchanged. It adds only bounded read-only "
        "MSE0/MSE3 prepared counter reset/update-cause evidence.\n\n"
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
        "source_v23_zip_sha256": SOURCE_SHA256,
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
        prefix="gap-node0071-v24-repeat-"
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
                "gap-node0071-prepared-count-cause-v24-build-v1",
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
        print(f"GAP v24 build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
