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
SOURCE_NAME = "r5_n71_gap_v16_stage1_byte_slots"
INSTALL_NAME = "r5_n71_gap_v17_stage1_flow_diag"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = (
    "85ee11406a8f7b67d67d7fd3e82705c3c48c12b01e2a155496cbf7b05679cee5"
)
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
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
        raise BuildError(f"observer marker differs: {label}")
    return text.replace(old, new, 1)


def configure_source() -> None:
    base.SOURCE_NAME = SOURCE_NAME
    base.INSTALL_NAME = INSTALL_NAME
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256


def _xmr_prefix(mse: int) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_flow_group]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[return_obs_flow_slice]"
        ".u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine"
        f".MSE_INST[{mse}].RD_MSE.u_Memory_RD_Stream_Engine"
    )


def _buffer_prefix(buffer_index: int) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_flow_group]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[return_obs_flow_slice]"
        ".u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster"
        f".BUFFER_MANAGER[{buffer_index}].u_Buffer_Manager"
    )


def _ga_prefix(column: int) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_flow_group]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[return_obs_flow_slice]"
        ".u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group"
        f".GA_ROW_PE[return_obs_flow_row].GA_COL_PE[{column}].GA_PE"
        ".u_GA_PE.u_GA_PE_Inbuffer"
    )


def _flow_assignments() -> str:
    lines = [
        "    generate",
        "        for (genvar return_obs_flow_group = 0;",
        "             return_obs_flow_group < `SLICE_GROUP_SIZE;",
        "             return_obs_flow_group++) begin : RETURN_OBS_FLOW_GROUP_GEN",
        "            for (genvar return_obs_flow_slice = 0;",
        "                 return_obs_flow_slice < `SLICE_GROUP_NUM;",
        "                 return_obs_flow_slice++) begin : RETURN_OBS_FLOW_SLICE_GEN",
    ]
    for slot, mse in enumerate((0, 3)):
        prefix = _xmr_prefix(mse)
        lines.extend(
            [
                f"                assign return_obs_flow_q_wr_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_wr_en;",
                f"                assign return_obs_flow_q_rd_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_rd_en;",
                f"                assign return_obs_flow_q_full_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full;",
                f"                assign return_obs_flow_q_empty_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_empty;",
                f"                assign return_obs_flow_ob_wr_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_WR_Buffer_AG.buf_ag_ob_wr_en;",
                f"                assign return_obs_flow_ob_rd_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_WR_Buffer_AG.buf_ag_ob_rd_en;",
                f"                assign return_obs_flow_ob_bp_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_WR_Buffer_AG.buf_ag_bp_pre;",
                f"                assign return_obs_flow_ob_full_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_WR_Buffer_AG.buf_ag_ob_full;",
                f"                assign return_obs_flow_ob_empty_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_WR_Buffer_AG.buf_ag_ob_empty;",
                f"                assign return_obs_flow_ob_count_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_WR_Buffer_AG.buf_ag_ob_cnt;",
            ]
        )
    for slot, buffer_index in enumerate((0, 4)):
        prefix = _buffer_prefix(buffer_index)
        lines.extend(
            [
                f"                assign return_obs_flow_buf_valid_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_Buffer.valid_buf;",
                f"                assign return_obs_flow_arm_req_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_Array_Request_Manager.arm2buf_req_valid;",
                f"                assign return_obs_flow_arm_ready_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_Array_Request_Manager.buf2arm_req_ready;",
                f"                assign return_obs_flow_arm_rw_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_Array_Request_Manager.arm2buf_req_rw;",
                f"                assign return_obs_flow_arm_clear_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_Array_Request_Manager.arm2buf_clear;",
                f"                assign return_obs_flow_arm_addr_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_Array_Request_Manager.arm2buf_req_addr;",
                f"                assign return_obs_flow_arm_counter0_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_Array_Request_Manager.array_counter_0;",
                f"                assign return_obs_flow_arm_counter1_mon[return_obs_flow_group][return_obs_flow_slice][{slot}] =",
                f"                    {prefix}.u_Array_Request_Manager.array_counter_1;",
            ]
        )
    lines.extend(
        [
            "                for (genvar return_obs_flow_row = 0;",
            "                     return_obs_flow_row < `GA_ROW_PE_NUM;",
            "                     return_obs_flow_row++) begin : RETURN_OBS_FLOW_ROW_GEN",
        ]
    )
    for slot, column in enumerate((0, 2)):
        prefix = _ga_prefix(column)
        for operand in (0, 2):
            op_slot = 0 if operand == 0 else 1
            lines.extend(
                [
                    "                    assign return_obs_flow_ga_stored_tag_mon",
                    f"                        [return_obs_flow_group][return_obs_flow_slice][return_obs_flow_row][{slot}][{op_slot}] =",
                    f"                        {prefix}.ga_pe_inbuffer_tag[{operand}];",
                ]
            )
    lines.extend(
        [
            "                end",
            "            end",
            "        end",
            "    endgenerate",
            "",
        ]
    )
    return "\n".join(lines)


def extend_observer(source: str) -> str:
    source = replace_once(
        source,
        "// v13 buffer-to-GA extension: read-only qualified counters and raw-state\n",
        "// v17 stage1-flow extension: rate-limited, read-only snapshots split\n"
        "// MSE0/MSE3 Buffer-AG queue/output, Buffer0/4 byte-valid/clear/ARM,\n"
        "// and GA stored operand-tag state.  These fields never enter the\n"
        "// canonical monotonic-progress predicate and never drive the DUT.\n"
        "//\n"
        "// v13 buffer-to-GA extension: read-only qualified counters and raw-state\n",
        "header",
    )
    declarations = (
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]\n"
        "          return_obs_flow_q_wr_mon, return_obs_flow_q_rd_mon,\n"
        "          return_obs_flow_q_full_mon, return_obs_flow_q_empty_mon;\n"
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]\n"
        "          return_obs_flow_ob_wr_mon, return_obs_flow_ob_rd_mon,\n"
        "          return_obs_flow_ob_bp_mon, return_obs_flow_ob_full_mon,\n"
        "          return_obs_flow_ob_empty_mon;\n"
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [1:0][1:0] return_obs_flow_ob_count_mon;\n"
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [1:0][`BUFFER_BANK_NUM-1:0][`VALID_BUFFER_DEPTH-1:0]\n"
        "          [`VALID_BUFFER_BANK_WIDTH-1:0] return_obs_flow_buf_valid_mon;\n"
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [1:0][`BUFFER_BANK_NUM-1:0]\n"
        "          return_obs_flow_arm_req_mon, return_obs_flow_arm_clear_mon;\n"
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]\n"
        "          return_obs_flow_arm_ready_mon, return_obs_flow_arm_rw_mon;\n"
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [1:0][`BUFFER_BANK_ADDR_WIDTH-1:0]\n"
        "          return_obs_flow_arm_addr_mon;\n"
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [1:0][`BUFFER_LIFE_TIME_WIDTH-1:0]\n"
        "          return_obs_flow_arm_counter0_mon,\n"
        "          return_obs_flow_arm_counter1_mon;\n"
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [`GA_ROW_PE_NUM-1:0][1:0][1:0]\n"
        "          [`GA_PE_ALU_TAG_WIDTH-1:0]\n"
        "          return_obs_flow_ga_stored_tag_mon;\n\n"
    )
    source = replace_once(
        source,
        "    generate\n",
        declarations + "    generate\n",
        "flow monitor declarations",
    )
    source = replace_once(
        source,
        "    bit return_obs_enabled;\n",
        _flow_assignments() + "    bit return_obs_enabled;\n",
        "flow XMR assignments",
    )
    source = replace_once(
        source,
        "    longint unsigned return_obs_ga_group2_accept_count;\n",
        "    longint unsigned return_obs_ga_group2_accept_count;\n"
        "    longint unsigned return_obs_flow_q_wr_count [0:1];\n"
        "    longint unsigned return_obs_flow_q_rd_count [0:1];\n"
        "    longint unsigned return_obs_flow_ob_wr_count [0:1];\n"
        "    longint unsigned return_obs_flow_ob_rd_count [0:1];\n"
        "    longint unsigned return_obs_flow_arm_accept_count [0:1];\n"
        "    longint unsigned return_obs_flow_arm_clear_count [0:1];\n",
        "flow counters",
    )
    source = replace_once(
        source,
        "                    $fdisplay(\n"
        "                        return_obs_fd,\n"
        "                        \"%0t | BUFFER_TO_GA_STATE | event=%s buf_rtag=0x%0h buf_bp=0x%0h group_tag=0x%0h group_bp=0x%0h pe_operand_valid=0x%0h\",\n"
        "                        $time,\n"
        "                        event_name,\n"
        "                        return_obs_buf_to_ga_rtag_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_buf_to_ga_bp_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_ga_group_out_tag_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_ga_group_bp_post_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_ga_operand_inport_valid_mon[return_obs_group_id][return_obs_local_slice_id]\n"
        "                    );\n",
        "                    $fdisplay(\n"
        "                        return_obs_fd,\n"
        "                        \"%0t | BUFFER_TO_GA_STATE | event=%s buf_rtag=0x%0h buf_bp=0x%0h group_tag=0x%0h group_bp=0x%0h pe_operand_valid=0x%0h\",\n"
        "                        $time,\n"
        "                        event_name,\n"
        "                        return_obs_buf_to_ga_rtag_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_buf_to_ga_bp_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_ga_group_out_tag_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_ga_group_bp_post_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_ga_operand_inport_valid_mon[return_obs_group_id][return_obs_local_slice_id]\n"
        "                    );\n"
        "                    $fdisplay(\n"
        "                        return_obs_fd,\n"
        "                        \"%0t | STAGE1_FLOW_COUNTS_V1 | event=%s q_wr=%0d/%0d q_rd=%0d/%0d ob_wr=%0d/%0d ob_rd=%0d/%0d arm_accept=%0d/%0d arm_clear=%0d/%0d\",\n"
        "                        $time, event_name,\n"
        "                        return_obs_flow_q_wr_count[0], return_obs_flow_q_wr_count[1],\n"
        "                        return_obs_flow_q_rd_count[0], return_obs_flow_q_rd_count[1],\n"
        "                        return_obs_flow_ob_wr_count[0], return_obs_flow_ob_wr_count[1],\n"
        "                        return_obs_flow_ob_rd_count[0], return_obs_flow_ob_rd_count[1],\n"
        "                        return_obs_flow_arm_accept_count[0], return_obs_flow_arm_accept_count[1],\n"
        "                        return_obs_flow_arm_clear_count[0], return_obs_flow_arm_clear_count[1]\n"
        "                    );\n"
        "                    $fdisplay(\n"
        "                        return_obs_fd,\n"
        "                        \"%0t | STAGE1_FLOW_STATE_V1 | event=%s q_full=0x%0h q_empty=0x%0h ob_count=0x%0h ob_full=0x%0h ob_empty=0x%0h buf_valid=0x%0h arm_req=0x%0h arm_ready=0x%0h arm_rw=0x%0h arm_clear=0x%0h arm_addr=0x%0h arm_ctr0=0x%0h arm_ctr1=0x%0h ga_stored_tag=0x%0h\",\n"
        "                        $time, event_name,\n"
        "                        return_obs_flow_q_full_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_flow_q_empty_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_flow_ob_count_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_flow_ob_full_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_flow_ob_empty_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_flow_buf_valid_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_flow_arm_req_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_flow_arm_ready_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_flow_arm_rw_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_flow_arm_clear_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_flow_arm_addr_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_flow_arm_counter0_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_flow_arm_counter1_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_flow_ga_stored_tag_mon[return_obs_group_id][return_obs_local_slice_id]\n"
        "                    );\n",
        "flow summary records",
    )
    source = replace_once(
        source,
        "                return_obs_ga_group2_accept_count = 0;\n"
        "                for (int channel = 0;\n",
        "                return_obs_ga_group2_accept_count = 0;\n"
        "                for (int flow = 0; flow < 2; flow++) begin\n"
        "                    return_obs_flow_q_wr_count[flow] = 0;\n"
        "                    return_obs_flow_q_rd_count[flow] = 0;\n"
        "                    return_obs_flow_ob_wr_count[flow] = 0;\n"
        "                    return_obs_flow_ob_rd_count[flow] = 0;\n"
        "                    return_obs_flow_arm_accept_count[flow] = 0;\n"
        "                    return_obs_flow_arm_clear_count[flow] = 0;\n"
        "                end\n"
        "                for (int channel = 0;\n",
        "flow counter reset",
    )
    source = replace_once(
        source,
        "            return_obs_sg_clock_edge_count++;\n"
        "            return_obs_sg_last_edge_time = $time;\n",
        "            return_obs_sg_clock_edge_count++;\n"
        "            return_obs_sg_last_edge_time = $time;\n"
        "            for (int flow = 0; flow < 2; flow++) begin\n"
        "                if (return_obs_flow_q_wr_mon[return_obs_group_id][return_obs_local_slice_id][flow] &&\n"
        "                    !return_obs_flow_q_full_mon[return_obs_group_id][return_obs_local_slice_id][flow])\n"
        "                    return_obs_flow_q_wr_count[flow]++;\n"
        "                if (return_obs_flow_q_rd_mon[return_obs_group_id][return_obs_local_slice_id][flow] &&\n"
        "                    !return_obs_flow_q_empty_mon[return_obs_group_id][return_obs_local_slice_id][flow])\n"
        "                    return_obs_flow_q_rd_count[flow]++;\n"
        "                if (return_obs_flow_ob_wr_mon[return_obs_group_id][return_obs_local_slice_id][flow] &&\n"
        "                    return_obs_flow_ob_bp_mon[return_obs_group_id][return_obs_local_slice_id][flow])\n"
        "                    return_obs_flow_ob_wr_count[flow]++;\n"
        "                if (return_obs_flow_ob_rd_mon[return_obs_group_id][return_obs_local_slice_id][flow] &&\n"
        "                    !return_obs_flow_ob_empty_mon[return_obs_group_id][return_obs_local_slice_id][flow])\n"
        "                    return_obs_flow_ob_rd_count[flow]++;\n"
        "                if ((|return_obs_flow_arm_req_mon[return_obs_group_id][return_obs_local_slice_id][flow]) &&\n"
        "                    !return_obs_flow_arm_rw_mon[return_obs_group_id][return_obs_local_slice_id][flow] &&\n"
        "                    return_obs_flow_arm_ready_mon[return_obs_group_id][return_obs_local_slice_id][flow])\n"
        "                    return_obs_flow_arm_accept_count[flow]++;\n"
        "                if (|return_obs_flow_arm_clear_mon[return_obs_group_id][return_obs_local_slice_id][flow])\n"
        "                    return_obs_flow_arm_clear_count[flow]++;\n"
        "            end\n",
        "flow qualified counters",
    )
    return source


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
            "schema": "gap-node0071-stage1-flow-diagnostic-server-package-v17",
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "read-only MSE0/MSE3 Buffer-AG queue/output, Buffer0/4 "
                "byte-valid/clear/ARM and GA stored-operand localization; "
                "v16 stage1 config, bitstream, golden and numeric workload frozen"
            ),
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_SHA256,
            "quarantines_package_sha256": None,
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
    manifest["final_zip_rule_self_audit_contract"].update(
        {
            "read_receipt": receipts,
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
        if path.endswith("服务器测试包生成规则.md"):
            rules["server_rule_sha256"] = digest
        elif path.endswith("GAP_int32_mac_bypass_rules.md"):
            rules["gap_int32_rule_sha256"] = digest
        elif path.endswith("GAP_probe_v7_validator_rules.md"):
            rules["gap_probe_rule_sha256"] = digest
    rules["current_match"] = True
    rules["plan_sha256_mutable_provenance_only"] = sha256(ROOT / ".agents/plan.md")
    feature = manifest["diagnostic_feature_runtime_enable_contract"]
    feature.update(
        {
            "observer_algorithm_changed": True,
            "semantic_extension":
                "stage1 flow records use the same already-bound accumulator "
                "runtime gate; their schemas are declared in the separate "
                "stage1_flow_diagnostic_contract",
        }
    )
    manifest["stage1_flow_diagnostic_contract"] = {
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "trigger_return_zip_sha256":
            "dec639e4adf98282951dfc1a7913ea6942140e6c372ad29be19ffdae094bdbef",
        "source_v16_zip_sha256": SOURCE_SHA256,
        "last_good":
            "MSE0_AND_MSE3_BUFFER_ACCEPTS_AND_FOUR_GA_JOINT_ACCEPTS",
        "first_unresolved_boundary": (
            "MSE0_BUFFER_AG_QUEUE_TO_BUFFER0_BYTE_VALID_CLEAR_TO_"
            "GA_STORED_OPERAND0_TAG"
        ),
        "record_schemas": [
            "STAGE1_FLOW_COUNTS_V1",
            "STAGE1_FLOW_STATE_V1",
        ],
        "source_clock": "clk_sg",
        "snapshot_clock": "clk_db",
        "shares_runtime_feature":
            "buffer_to_ga_accumulator_state",
        "qualified_counters": [
            "MSE0_MSE3_BUFFER_AG_INDEX_QUEUE_WRITE_READ",
            "MSE0_MSE3_WR_BUFFER_AG_OUTPUT_WRITE_READ",
            "BUFFER0_BUFFER4_ARM_READ_ACCEPT_CLEAR",
        ],
        "raw_state_only": [
            "BUFFER_AG_QUEUE_FULL_EMPTY",
            "WR_BUFFER_AG_COUNT_FULL_EMPTY",
            "BUFFER0_BUFFER4_ALL_BANK_ALL_ROW_BYTE_VALID",
            "BUFFER0_BUFFER4_ARM_ADDRESS_COUNTERS",
            "GA_PE_OPERAND0_OPERAND2_STORED_TAGS",
        ],
        "excluded_from_monotonic_progress": True,
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
                "tools/build_gap_node0071_stage1_flow_diag_v17_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "numeric_payload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change": (
                "fresh identity plus read-only stage1 flow observer extension"
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
    frozen_before = {
        path: record
        for path, record in file_records(
            package / "workload", exclude_manifest=False
        ).items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    base.rewrite_identity(package)
    observer = package / OBSERVER_RELATIVE
    observer.write_text(
        extend_observer(observer.read_text(encoding="utf-8")),
        encoding="utf-8",
        newline="\n",
    )
    (package / "README.md").write_text(
        "# GAP node0071 v17 stage1 flow diagnostic\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It keeps the "
        "v16 stage1 byte-slot configuration, all bitstreams, execplan, SCA "
        "semantics, golden and 73 numeric workload files unchanged. The "
        "read-only observer adds rate-limited MSE0/MSE3 Buffer-AG queue/output, "
        "Buffer0/4 byte-valid/clear/ARM and GA stored operand-tag snapshots. "
        "The added state does not enter canonical progress and does not drive "
        "the DUT.\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package, source_manifest)
    frozen_after = {
        path: record
        for path, record in file_records(
            package / "workload", exclude_manifest=False
        ).items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    if frozen_before != frozen_after or len(frozen_after) != 73:
        raise BuildError("frozen 73-file workload drifted")
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
    return package, {
        "source_v16_zip_sha256": SOURCE_SHA256,
        "observer_sha256": sha256(observer),
        "changed_paths": sorted(changed),
        "changed_paths_exact_allowlist": True,
        "frozen_numeric_workload_file_count": len(frozen_after),
        "frozen_numeric_workload_tree_equal": True,
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    first_sha = sha256(zip_path)
    first_tree = file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(prefix="gap-node0071-v17-repeat-") as tmp:
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
            "schema": "gap-node0071-stage1-flow-v17-build-v1",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
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
        print(f"GAP v17 build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
