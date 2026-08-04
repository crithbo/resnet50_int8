from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v7_four_way_binding_package_v8 as base  # noqa: E402


SOURCE_NAME = "r5_n4_hw_v16_abpe_runnerpc"
INSTALL_NAME = "r5_n4_hw_v17_a_reuse_diag"
SOURCE_ZIP_SHA256 = (
    "e0f6d1effba71e505d22203ec2a43b4a538aaeeb515b806f6953603a342bcec1"
)
BOUND_RETURN_SHA256 = (
    "561e29d888b8970d44ff90405d8709cc6e9aae63393d02261652aa5ff7888d4f"
)
SERVER_RULE_SHA256 = (
    "507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d"
)
PLAN_MUTABLE_SHA256 = (
    "a31d7d6fa17c7a3344f15f6cfc4c227f1ef9baef98d277d090bb1fa79b79da28"
)
SOURCE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / SOURCE_NAME
)
SOURCE_ZIP = SOURCE_ROOT.with_suffix(".zip")
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


A_REUSE_OBSERVER_BLOCK = r'''

    // v17: narrow discriminator for the frozen v16 first-product-to-second-A
    // interval. These qualified counters do not contribute to canonical
    // progress or change DUT behavior.
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
          return_obs_ar_mse0_req_sel_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
          return_obs_ar_mse0_req_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
          [`MSE_BUF_REQ_NUM-1:0] return_obs_ar_buf_req_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
          return_obs_ar_buf_req_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
          return_obs_ar_buf_wvalid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
          [`ARRAY_PORT_TAG-1:0] return_obs_ar_buf_rtag_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
          return_obs_ar_buf_read_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
          [`BUFFER_BANK_NUM-1:0] return_obs_ar_mem_clear_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
          [`BUFFER_BANK_NUM-1:0] return_obs_ar_array_clear_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_ar_sa_src_sel_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_ar_pipeline0_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_ar_alu2ob_write_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_ar_psum_ready_mon;

    generate
        for (genvar return_obs_ar_group = 0;
             return_obs_ar_group < `SLICE_GROUP_SIZE;
             return_obs_ar_group++) begin : RETURN_OBS_AR_GROUP_GEN
            for (genvar return_obs_ar_slice = 0;
                 return_obs_ar_slice < `SLICE_GROUP_NUM;
                 return_obs_ar_slice++) begin : RETURN_OBS_AR_SLICE_GEN
                assign return_obs_ar_mse0_req_sel_mon
                    [return_obs_ar_group][return_obs_ar_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_ar_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_ar_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .se2buf_mem_wreq_buf_sel[0];
                assign return_obs_ar_mse0_req_ready_mon
                    [return_obs_ar_group][return_obs_ar_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_ar_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_ar_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .buf2se_mem_wreq_ready[0];
                for (genvar return_obs_ar_buf = 0;
                     return_obs_ar_buf < 2;
                     return_obs_ar_buf++) begin : RETURN_OBS_AR_BUF_GEN
                    assign return_obs_ar_buf_req_valid_mon
                        [return_obs_ar_group][return_obs_ar_slice]
                        [return_obs_ar_buf] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_ar_group]
                            .u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_ar_slice]
                            .u_slice_wrapper.u_Slice.u_LSU
                            .u_Buffer_Manager_Cluster
                            .se2mrm_req_valid[return_obs_ar_buf];
                    assign return_obs_ar_buf_req_ready_mon
                        [return_obs_ar_group][return_obs_ar_slice]
                        [return_obs_ar_buf] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_ar_group]
                            .u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_ar_slice]
                            .u_slice_wrapper.u_Slice.u_LSU
                            .u_Buffer_Manager_Cluster
                            .mrm2se_req_ready[return_obs_ar_buf];
                    assign return_obs_ar_buf_wvalid_mon
                        [return_obs_ar_group][return_obs_ar_slice]
                        [return_obs_ar_buf] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_ar_group]
                            .u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_ar_slice]
                            .u_slice_wrapper.u_Slice.u_LSU
                            .u_Buffer_Manager_Cluster
                            .se2mrm_wvalid[return_obs_ar_buf];
                    assign return_obs_ar_buf_rtag_mon
                        [return_obs_ar_group][return_obs_ar_slice]
                        [return_obs_ar_buf] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_ar_group]
                            .u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_ar_slice]
                            .u_slice_wrapper.u_Slice.u_LSU
                            .u_Buffer_Manager_Cluster
                            .arm2array_rtag[return_obs_ar_buf];
                    assign return_obs_ar_buf_read_ready_mon
                        [return_obs_ar_group][return_obs_ar_slice]
                        [return_obs_ar_buf] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_ar_group]
                            .u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_ar_slice]
                            .u_slice_wrapper.u_Slice.u_LSU
                            .u_Buffer_Manager_Cluster
                            .array2arm_bp_post[return_obs_ar_buf];
                    assign return_obs_ar_mem_clear_mon
                        [return_obs_ar_group][return_obs_ar_slice]
                        [return_obs_ar_buf] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_ar_group]
                            .u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_ar_slice]
                            .u_slice_wrapper.u_Slice.u_LSU
                            .u_Buffer_Manager_Cluster
                            .BUFFER_MANAGER[return_obs_ar_buf]
                            .u_Buffer_Manager.mrm2buf_clear;
                    assign return_obs_ar_array_clear_mon
                        [return_obs_ar_group][return_obs_ar_slice]
                        [return_obs_ar_buf] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_ar_group]
                            .u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_ar_slice]
                            .u_slice_wrapper.u_Slice.u_LSU
                            .u_Buffer_Manager_Cluster
                            .BUFFER_MANAGER[return_obs_ar_buf]
                            .u_Buffer_Manager.arm2buf_clear;
                end
                assign return_obs_ar_sa_src_sel_mon
                    [return_obs_ar_group][return_obs_ar_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_ar_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_obs_ar_slice]
                        .u_slice_wrapper.u_Slice
                        .u_Specialized_Array.SA_INPORT_GROUP[0]
                        .u_SA_Inport_Group.u_SA_Inport_Connect
                        .sa_inport_src_sel;
                for (genvar return_obs_ar_row = 0;
                     return_obs_ar_row < `SA_ROW_PE_NUM;
                     return_obs_ar_row++) begin : RETURN_OBS_AR_ROW_GEN
                    for (genvar return_obs_ar_col = 0;
                         return_obs_ar_col < `SA_COL_PE_NUM;
                         return_obs_ar_col++) begin : RETURN_OBS_AR_COL_GEN
                        assign return_obs_ar_pipeline0_valid_mon
                            [return_obs_ar_group][return_obs_ar_slice]
                            [return_obs_ar_row][return_obs_ar_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_ar_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_ar_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_ar_row]
                                .SA_COL_PE[return_obs_ar_col]
                                .u_SA_PE.u_SA_PE_Control_Block
                                .alu_pipeline0_valid_bit;
                        assign return_obs_ar_alu2ob_write_mon
                            [return_obs_ar_group][return_obs_ar_slice]
                            [return_obs_ar_row][return_obs_ar_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_ar_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_ar_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_ar_row]
                                .SA_COL_PE[return_obs_ar_col]
                                .u_SA_PE.u_SA_PE_Outbuffer
                                .alu2ob_wr_handshake;
                        assign return_obs_ar_psum_ready_mon
                            [return_obs_ar_group][return_obs_ar_slice]
                            [return_obs_ar_row][return_obs_ar_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_ar_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_ar_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_ar_row]
                                .SA_COL_PE[return_obs_ar_col]
                                .u_SA_PE.u_SA_PE_Outbuffer
                                .sa_pe_ob2alu_port_psum_bit;
                    end
                end
            end
        end
    endgenerate

    longint unsigned return_obs_ar_req_accept [0:1];
    longint unsigned return_obs_ar_data_accept [0:1];
    longint unsigned return_obs_ar_buf_read_accept [0:1];
    longint unsigned return_obs_ar_mem_clear_count [0:1];
    longint unsigned return_obs_ar_array_clear_count [0:1];
    longint unsigned return_obs_ar_sa_src_accept [0:1];
    longint unsigned return_obs_ar_alu2ob_cycles;

    initial begin
        for (int return_obs_ar_i = 0; return_obs_ar_i < 2;
             return_obs_ar_i++) begin
            return_obs_ar_req_accept[return_obs_ar_i] = 0;
            return_obs_ar_data_accept[return_obs_ar_i] = 0;
            return_obs_ar_buf_read_accept[return_obs_ar_i] = 0;
            return_obs_ar_mem_clear_count[return_obs_ar_i] = 0;
            return_obs_ar_array_clear_count[return_obs_ar_i] = 0;
            return_obs_ar_sa_src_accept[return_obs_ar_i] = 0;
        end
        return_obs_ar_alu2ob_cycles = 0;
    end

    always @(posedge u_NDP_Top_new.clk_db or
             negedge u_NDP_Top_new.rst_n_db) begin
        if (!u_NDP_Top_new.rst_n_db) begin
            for (int return_obs_ar_i = 0; return_obs_ar_i < 2;
                 return_obs_ar_i++) begin
                return_obs_ar_req_accept[return_obs_ar_i] = 0;
                return_obs_ar_data_accept[return_obs_ar_i] = 0;
                return_obs_ar_buf_read_accept[return_obs_ar_i] = 0;
                return_obs_ar_mem_clear_count[return_obs_ar_i] = 0;
                return_obs_ar_array_clear_count[return_obs_ar_i] = 0;
                return_obs_ar_sa_src_accept[return_obs_ar_i] = 0;
            end
            return_obs_ar_alu2ob_cycles = 0;
        end
        else if (return_obs_enabled && return_obs_active) begin
            for (int return_obs_ar_i = 0; return_obs_ar_i < 2;
                 return_obs_ar_i++) begin
                if (
                    (|return_obs_ar_buf_req_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [return_obs_ar_i]) &&
                    return_obs_ar_buf_req_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [return_obs_ar_i]
                )
                    return_obs_ar_req_accept[return_obs_ar_i]++;
                if (
                    return_obs_ar_buf_wvalid_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [return_obs_ar_i] &&
                    return_obs_ar_buf_req_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [return_obs_ar_i]
                )
                    return_obs_ar_data_accept[return_obs_ar_i]++;
                if (
                    return_obs_ar_buf_rtag_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [return_obs_ar_i][`ARRAY_PORT_TAG-1] &&
                    return_obs_ar_buf_read_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [return_obs_ar_i]
                )
                    return_obs_ar_buf_read_accept[return_obs_ar_i]++;
                if (|return_obs_ar_mem_clear_mon
                    [return_obs_group_id][return_obs_local_slice_id]
                    [return_obs_ar_i])
                    return_obs_ar_mem_clear_count[return_obs_ar_i]++;
                if (|return_obs_ar_array_clear_mon
                    [return_obs_group_id][return_obs_local_slice_id]
                    [return_obs_ar_i])
                    return_obs_ar_array_clear_count[return_obs_ar_i]++;
                if (
                    (|return_obs_sa_in_tag_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [0][return_obs_ar_i]
                        [`SA_INPORT_GROUP_TAG-1 -: `SA_INPORT_NUM]) &&
                    return_obs_sa_in_buf_bp_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [0][return_obs_ar_i]
                )
                    return_obs_ar_sa_src_accept[return_obs_ar_i]++;
            end
            if (|return_obs_ar_alu2ob_write_mon
                [return_obs_group_id][return_obs_local_slice_id])
                return_obs_ar_alu2ob_cycles++;
        end
    end

    task automatic return_obs_write_a_reuse_state(input string event_name);
        begin
            if (return_obs_fd != 0) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | A_REUSE_BOUNDARY_V1 | event=%s req_accept0=%0d req_accept1=%0d data_accept0=%0d data_accept1=%0d buf_read0=%0d buf_read1=%0d mem_clear0=%0d mem_clear1=%0d array_clear0=%0d array_clear1=%0d sa_src_accept0=%0d sa_src_accept1=%0d alu2ob_cycles=%0d mse0_req_sel=0x%0h mse0_req_ready=0x%0h sa_src_sel=%0b buf0_rtag=0x%0h buf1_rtag=0x%0h pipeline0_valid=0x%0h alu2ob_write=0x%0h psum_ready=0x%0h",
                    $time,
                    event_name,
                    return_obs_ar_req_accept[0],
                    return_obs_ar_req_accept[1],
                    return_obs_ar_data_accept[0],
                    return_obs_ar_data_accept[1],
                    return_obs_ar_buf_read_accept[0],
                    return_obs_ar_buf_read_accept[1],
                    return_obs_ar_mem_clear_count[0],
                    return_obs_ar_mem_clear_count[1],
                    return_obs_ar_array_clear_count[0],
                    return_obs_ar_array_clear_count[1],
                    return_obs_ar_sa_src_accept[0],
                    return_obs_ar_sa_src_accept[1],
                    return_obs_ar_alu2ob_cycles,
                    return_obs_ar_mse0_req_sel_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_ar_mse0_req_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_ar_sa_src_sel_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_ar_buf_rtag_mon
                        [return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_ar_buf_rtag_mon
                        [return_obs_group_id][return_obs_local_slice_id][1],
                    return_obs_ar_pipeline0_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_ar_alu2ob_write_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_ar_psum_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                );
                $fflush(return_obs_fd);
            end
        end
    endtask
'''


def replace_text_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".bin"}:
            continue
        payload = path.read_bytes()
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_NAME in text:
            path.write_text(
                text.replace(SOURCE_NAME, INSTALL_NAME),
                encoding="utf-8",
                newline="\n",
            )


def patch_observer(package: Path) -> str:
    observer = package / "tb_probe/native_return_observer.svh"
    text = observer.read_text(encoding="utf-8")
    old = '                return_obs_write_abpe_state("DIAG_DECISION");\n'
    new = old + '                return_obs_write_a_reuse_state("DIAG_DECISION");\n'
    if text.count(old) != 1 or "A_REUSE_BOUNDARY_V1" in text:
        raise base.BuildError("v16 observer decision-call shape differs")
    observer.write_text(
        text.replace(old, new, 1) + A_REUSE_OBSERVER_BLOCK,
        encoding="utf-8",
        newline="\n",
    )
    return base.sha256(observer)


def readme() -> str:
    return f"""# node0004 v17 A reuse narrow diagnostic

Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.

The v16 formal return compiled and ran, then proved a four-window internal
stall after exactly one complete A/B issue to all 64 PEs.  It did not prove a
functional or numeric result.  This successor preserves the byte-identical
frozen workload/configuration/golden and adds one read-only observer interval:

`MSE0 return -> Buffer0/1 write/select/clear -> SA inport0 source -> PE
pipeline0 -> ALU-to-outbuffer write`.

`A_REUSE_BOUNDARY_V1` is emitted with the unique canonical decision.  Its
qualified counters distinguish:

1. producer/consumer selector divergence;
2. Buffer0/1 fill/clear/lifetime failure;
3. SA source delivery failure;
4. PE pipeline/outbuffer backpressure after the first product.

This is not a functional fix and is not evidence of E4/E5.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `{INSTALL_NAME}_return.zip` and adjacent `.sha256`.
"""


def build_directory(output: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise base.BuildError("v16 source ZIP SHA differs")
    package = output / INSTALL_NAME
    if package.exists():
        raise base.BuildError(f"refusing to overwrite: {package}")
    shutil.copytree(SOURCE_ROOT, package)
    replace_text_identity(package)
    observer_sha = patch_observer(package)
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema"] = "resnet50-node0004-a-reuse-diagnostic-package-v17"
    manifest["install_name"] = INSTALL_NAME
    manifest["classification"] = "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
    manifest["status"] = "PACKAGE_READY_NOT_RUN"
    manifest["candidate_release"] = False
    manifest["observer_sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"]["sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"]["size_bytes"] = (
        package / "tb_probe/native_return_observer.svh"
    ).stat().st_size
    receipts = manifest["active_receipts"]
    receipts["plan_mutable_provenance_sha256"] = PLAN_MUTABLE_SHA256
    receipts["server_package_rule_sha256"] = SERVER_RULE_SHA256
    for item in receipts["generation_read_receipt"]:
        if item.get("sha256") in {
            "0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a",
            "507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d",
        }:
            item["sha256"] = SERVER_RULE_SHA256
    for rule_id in (
        "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
        "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
        "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
        "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
        "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
        "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
        "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
        "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
        "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
        "CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001",
    ):
        if rule_id not in receipts["rules"]:
            receipts["rules"].append(rule_id)
    manifest["v16_return_adjudication"] = {
        "bound_return_sha256": BOUND_RETURN_SHA256,
        "status": "LONG_RUNNING_HANG_AFTER_FIRST_SA_OPERAND_ACCEPT",
        "last_good": "one complete A/B issue accepted by all 64 PEs",
        "first_bad": (
            "no second A/B issue; A absent, B retained, no PE/SA output"
        ),
        "root_cause": "UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT",
    }
    manifest["narrow_diagnostic"] = {
        "schema": "node0004-a-reuse-boundary-v1",
        "record": "A_REUSE_BOUNDARY_V1",
        "canonical_record_count": 1,
        "interval": (
            "MSE0_RETURN_TO_BUFFER0_1_TO_SA_INPORT0_SECOND_ACCEPT"
        ),
        "qualified_counters": [
            "accepted Buffer0/1 requests",
            "accepted Buffer0/1 write data",
            "accepted Buffer0/1 SA reads",
            "Buffer0/1 memory/array clears",
            "accepted SA inport0 source0/source1 events",
            "ALU-to-outbuffer write cycles",
        ],
        "snapshots": [
            "MSE0 request selector/ready",
            "SA inport0 source selector",
            "Buffer0/1 read tags",
            "PE pipeline0 valid",
            "ALU-to-outbuffer write mask",
            "outbuffer psum-ready mask",
        ],
        "result_interpretation": {
            "one_target_only_and_sa_other_source": (
                "producer/consumer selector divergence"
            ),
            "balanced_writes_but_no_buffer_read": (
                "Buffer valid/clear/lifetime interval"
            ),
            "buffer_read_but_no_sa_source_accept": (
                "Buffer-to-SA source/ready interval"
            ),
            "sa_source_accept_but_no_alu2ob_write": (
                "PE pipeline/outbuffer backpressure interval"
            ),
            "alu2ob_write_then_no_next_a": (
                "next-A producer/reuse interval"
            ),
        },
        "not_functional_fix": True,
    }
    manifest["numeric_analysis_repeated"] = False
    manifest["node0004_workload_rebuilt"] = False
    manifest["configuration_rebuilt"] = False
    manifest["functional_rtl_modified"] = False
    manifest["server_rtl_entries"] = 0
    (package / "README.md").write_text(
        readme(), encoding="utf-8", newline="\n"
    )
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    package = output / INSTALL_NAME
    zip_path = output / f"{INSTALL_NAME}.zip"
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    validation = output / f"{INSTALL_NAME}.validation.json"
    for target in (package, zip_path, sidecar, validation):
        if target.exists():
            raise base.BuildError(f"refusing to overwrite: {target}")
    package = build_directory(output)
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v17-repeat-") as temp:
        repeat_root = Path(temp)
        repeat_package = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        repeated = base.sha256(repeat_zip) == digest
    if not repeated:
        raise base.BuildError("v17 deterministic rebuild differs")
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-a-reuse-diagnostic-package-validation-v17",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": repeated,
        "source_v16_sha256": SOURCE_ZIP_SHA256,
        "bound_v16_return_sha256": BOUND_RETURN_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_rtl_entries": 0,
        "server_action": False,
        "final_zip_rule_self_audit_pending": True,
    }
    base.write_json(validation, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
