#!/usr/bin/env python3
"""Build the native-four-lane p16 public Buffer5 causal successor."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
import tempfile
import types
from pathlib import Path, PurePosixPath
from typing import Any

# Only a few deterministic ZIP/extraction helpers are reused from the p15
# builder.  Its optional schema dependency is not required for those helpers.
if "jsonschema" not in sys.modules:
    sys.modules["jsonschema"] = types.SimpleNamespace(validate=lambda *_a, **_k: None)

import build_conv_native_four_lane_0ccae916_p15_install_only_package as base


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p15_installonly"
PACKAGE_ID = "r5_n4_0cc_p16_b5port"
WORKLOAD_INSTALL_NAME = "r5_n4_0cc_p11f_pubord"
ATTEMPT = "a0"
SOURCE_SHA256 = (
    "e323e3394124c9b8b655037ac916cc3e3510360cb0097f1f91f60bfb9508c9b8"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_ID}.zip"
)
DEFAULT_OUTPUT = (
    ROOT / "outputs/conv_native_four_lane_0ccae916_p16_buffer5_public"
)
SOURCE_ANALYSIS = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p15_return_analysis/report.json"
)
CURRENT_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
OLD_OUTPUT_PREFIX = (
    f"install/codex_runs/{SOURCE_ID}/{ATTEMPT}/c0/d/"
)
OUTPUT_PREFIX = f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}/c0/d/"
OBSERVER = "tb_probe/native_return_observer.svh"
FINALIZER = "package_tools/node0004_buffer5_public_finalizer.py"
RUNTIME = "package_tools/node0004_assumed_hardware_server_runtime.py"
ALLOWED_CHANGED_PATHS = {
    "PREPARE_AND_RUN.sh",
    "README.md",
    "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
    "TEST_PACKAGE_MANIFEST.json",
    "package_manifest.json",
    RUNTIME,
    "package_tools/fixed_simresult_publisher.py",
    FINALIZER,
    OBSERVER,
    "workload/runtime/runs/c0/sca_cfg_D.json",
}
CURRENT_CLOUD_LEAVES = {
    "Array_Request_Manager.sv": (
        "6f56815097da9b9fccde1ba2a435037ff9743ca48281f5fd25b2106ca2e51dfc"
    ),
    "Buffer_AG_Idx_Queue.sv": (
        "7bbf229f60fb91fe89fd78d8e2df8716cd4de2be3fc578c5270c570ea33c7bca"
    ),
    "RD_Data_Channel.sv": (
        "08b35e80c234c6567099c4da5e18ff0a18955e259b7c12bedff72325f744038c"
    ),
    "Neighbor_Out_AG.sv": (
        "05a6b1eadd2d5fb125a6a9e6b01b03dbbf9cd1bddc32423c01b5b6651cced41e"
    ),
    "SA_PE_Float_CSA.v": (
        "72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3"
    ),
    "SA_PE_Float_Control.v": (
        "b7ba64b0b6f5c399b00d43245b979b53755fce15c975bedb7dc3722fa1ef530e"
    ),
    "SA_PE_Mul_Array.v": (
        "32ce57705851f0febbc57abecd736010890374d7c11e4ba656dfd1b84d71032d"
    ),
    "SA_ALU.v": (
        "c986ea2de79381afb220ccef83f28466ec3bdda39cd4d80255419bfa214fee06"
    ),
    "Buffer.sv": (
        "41ae28b741931bb53effdce6482e68110983f2d57f43cd4c87dfd50b6a34acc0"
    ),
    "Buffer_Manager.sv": (
        "7c31e9bfa82cf0dab4109fe9656bb6bb380c0525742d358f67b3ffab56ce7735"
    ),
    "Memory_Req_Manager.sv": (
        "c2b4db840e6812d2c235d84143f7f8267ebd6aac9fc96371d06490d86608198c"
    ),
}


class BuildError(RuntimeError):
    pass


OBSERVER_APPEND = r"""

// Native Conv p16: public-module-port-only Buffer5 causal observer.
// This append reads ports of Buffer u_Buffer and never reads private state.
integer n4b5_fd;
integer n4b5_enabled;
integer n4b5_event_limit;
integer n4b5_event_count;
integer n4b5_cycle;
integer n4b5_blocked_cycles;
integer n4b5_arm_accept_count;
integer n4b5_mrm_accept_count;
integer n4b5_mrm_clear_count;
integer n4b5_sa_accept_count;
reg [1023:0] n4b5_output_path;
reg [`BUFFER_BANK_NUM-1:0] n4b5_arm_valid_d;
reg n4b5_arm_rw_d;
reg [`BUFFER_BANK_ADDR_WIDTH-1:0] n4b5_arm_addr_d;
reg n4b5_arm_ready_d;
reg n4b5_arm_wvalid_d;
reg [`BUFFER_BANK_NUM-1:0] n4b5_mrm_valid_d;
reg n4b5_mrm_rw_d;
reg [`BUFFER_BANK_ADDR_WIDTH-1:0] n4b5_mrm_addr_d;
reg n4b5_mrm_ready_d;
reg [`BUFFER_BANK_NUM-1:0] n4b5_mrm_clear_d;

task automatic n4b5_emit(input [127:0] reason);
begin
    if (n4b5_fd != 0 && n4b5_event_count < n4b5_event_limit) begin
        $fdisplay(
            n4b5_fd,
            "N4B5_EVENT_V1 reason=%0s cycle=%0d arm_valid=0x%0h arm_rw=%0d arm_addr=0x%0h arm_ready=%0d arm_wvalid=%0d arm_clear=0x%0h mrm_valid=0x%0h mrm_rw=%0d mrm_addr=0x%0h mrm_strb=0x%0h mrm_ready=%0d mrm_clear=0x%0h sa_raw_valid=%0d sa_ready=%0d sa_tag=0x%0h arm_accept=%0d mrm_accept=%0d mrm_clear_count=%0d sa_accept=%0d blocked_cycles=%0d",
            reason,
            n4b5_cycle,
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.arm2buf_req_valid,
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.arm2buf_req_rw,
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.arm2buf_req_addr,
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.buf2arm_req_ready,
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.arm2buf_wvalid,
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.arm2buf_clear,
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_req_valid,
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_req_rw,
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_req_addr,
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_req_strb,
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.buf2mrm_req_ready,
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_clear,
            n4p_sa_out_raw_valid_now,
            n4p_sa_out_ready_now,
            n4p_sa_out_raw_tag_now,
            n4b5_arm_accept_count,
            n4b5_mrm_accept_count,
            n4b5_mrm_clear_count,
            n4b5_sa_accept_count,
            n4b5_blocked_cycles
        );
        n4b5_event_count = n4b5_event_count + 1;
        $fflush(n4b5_fd);
    end
end
endtask

initial begin
    n4b5_enabled = $test$plusargs("N4B5_PUBLIC_CAUSAL");
    n4b5_event_limit = 128;
    $value$plusargs("N4B5_EVENT_LIMIT=%d", n4b5_event_limit);
    n4b5_fd = 0;
    n4b5_event_count = 0;
    n4b5_cycle = 0;
    n4b5_blocked_cycles = 0;
    n4b5_arm_accept_count = 0;
    n4b5_mrm_accept_count = 0;
    n4b5_mrm_clear_count = 0;
    n4b5_sa_accept_count = 0;
    n4b5_arm_valid_d = 0;
    n4b5_arm_rw_d = 0;
    n4b5_arm_addr_d = 0;
    n4b5_arm_ready_d = 0;
    n4b5_arm_wvalid_d = 0;
    n4b5_mrm_valid_d = 0;
    n4b5_mrm_rw_d = 0;
    n4b5_mrm_addr_d = 0;
    n4b5_mrm_ready_d = 0;
    n4b5_mrm_clear_d = 0;
    if (n4b5_enabled) begin
        if (!$value$plusargs("N4B5_FILE=%s", n4b5_output_path)) begin
            $error("N4B5_FILE is required");
            n4b5_enabled = 0;
        end
        else begin
            n4b5_fd = $fopen(n4b5_output_path, "w");
            if (n4b5_fd == 0) begin
                $error("N4B5 public causal output cannot be created");
                n4b5_enabled = 0;
            end
            else begin
                $fdisplay(
                    n4b5_fd,
                    "N4B5_FEATURE_ENABLE_V1 feature=BUFFER5_PUBLIC_CAUSAL enabled=1 stage=c0 slice=0 event_limit=%0d drives_dut=0 changes_timeout=0 private_xmr=0",
                    n4b5_event_limit
                );
                $fflush(n4b5_fd);
            end
        end
    end
end

always @(posedge u_NDP_Top_new.clk_sg or
         negedge u_NDP_Top_new.rst_n_sg) begin
    if (!u_NDP_Top_new.rst_n_sg) begin
        n4b5_cycle = 0;
        n4b5_blocked_cycles = 0;
    end
    else if (n4b5_enabled && n4d_active) begin
        n4b5_cycle = n4b5_cycle + 1;
        if (
            (|u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.arm2buf_req_valid)
            &&
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.buf2arm_req_ready
        ) n4b5_arm_accept_count = n4b5_arm_accept_count + 1;
        if (
            (|u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_req_valid)
            &&
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.buf2mrm_req_ready
        ) n4b5_mrm_accept_count = n4b5_mrm_accept_count + 1;
        if (
            |u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_clear
        ) n4b5_mrm_clear_count = n4b5_mrm_clear_count + 1;
        if (n4p_sa_out_raw_valid_now && n4p_sa_out_ready_now)
            n4b5_sa_accept_count = n4b5_sa_accept_count + 1;
        if (n4p_sa_out_raw_valid_now && !n4p_sa_out_ready_now)
            n4b5_blocked_cycles = n4b5_blocked_cycles + 1;
        else
            n4b5_blocked_cycles = 0;

        if (
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.arm2buf_req_valid
                != n4b5_arm_valid_d
            ||
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.arm2buf_req_addr
                != n4b5_arm_addr_d
            ||
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.buf2arm_req_ready
                != n4b5_arm_ready_d
            ||
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_req_valid
                != n4b5_mrm_valid_d
            ||
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_req_addr
                != n4b5_mrm_addr_d
            ||
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.buf2mrm_req_ready
                != n4b5_mrm_ready_d
            ||
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_clear
                != n4b5_mrm_clear_d
        ) n4b5_emit("interface_change");
        if (n4b5_blocked_cycles == 1)
            n4b5_emit("sa_blocked_begin");
        if (
            n4b5_blocked_cycles != 0
            && (n4b5_blocked_cycles % 262144) == 0
        ) n4b5_emit("sa_blocked_stable");

        n4b5_arm_valid_d =
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.arm2buf_req_valid;
        n4b5_arm_rw_d =
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.arm2buf_req_rw;
        n4b5_arm_addr_d =
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.arm2buf_req_addr;
        n4b5_arm_ready_d =
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.buf2arm_req_ready;
        n4b5_arm_wvalid_d =
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.arm2buf_wvalid;
        n4b5_mrm_valid_d =
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_req_valid;
        n4b5_mrm_rw_d =
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_req_rw;
        n4b5_mrm_addr_d =
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_req_addr;
        n4b5_mrm_ready_d =
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.buf2mrm_req_ready;
        n4b5_mrm_clear_d =
            u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group_id]
                .u_slice_with_datahub_mc_group
                .slice_group_gen[n4d_local_slice_id]
                .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_clear;
    end
end

final begin
    if (n4b5_fd != 0) begin
        n4b5_emit("final");
        $fclose(n4b5_fd);
    end
end
"""


FINALIZER_SOURCE = r'''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def fields(line: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"(?:^| )([A-Za-z0-9_]+)=([^ ]+)", line)
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observer-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    text = (
        args.observer_log.read_text(encoding="utf-8", errors="replace")
        if args.observer_log.is_file()
        else ""
    )
    markers = [
        fields(line) for line in text.splitlines()
        if line.startswith("N4B5_FEATURE_ENABLE_V1 ")
    ]
    events = [
        fields(line) for line in text.splitlines()
        if line.startswith("N4B5_EVENT_V1 ")
    ]
    last = events[-1] if events else {}
    required = {
        "arm_valid", "arm_rw", "arm_addr", "arm_ready", "arm_wvalid",
        "arm_clear", "mrm_valid", "mrm_rw", "mrm_addr", "mrm_strb",
        "mrm_ready", "mrm_clear", "sa_raw_valid", "sa_ready", "sa_tag",
        "arm_accept", "mrm_accept", "mrm_clear_count", "sa_accept",
        "blocked_cycles",
    }
    valid = (
        len(markers) == 1
        and bool(events)
        and all(required <= set(row) for row in events)
    )
    result = {
        "schema": "conv-native-four-lane-buffer5-public-summary-v1",
        "valid": valid,
        "feature_marker_count": len(markers),
        "event_count": len(events),
        "reason_counts": {
            reason: sum(row.get("reason") == reason for row in events)
            for reason in sorted({row.get("reason", "") for row in events})
        },
        "last": last or None,
        "observer_log": {
            "present": args.observer_log.is_file(),
            "size_bytes": (
                args.observer_log.stat().st_size
                if args.observer_log.is_file() else 0
            ),
            "sha256": (
                sha256(args.observer_log)
                if args.observer_log.is_file() else None
            ),
        },
        "candidate_matrix": {
            "producer_repeated_occupied_row": (
                "arm_valid!=0, arm_rw=1, arm_ready=0 and repeated arm_addr"
            ),
            "consumer_not_issued": (
                "sa_raw_valid=1, sa_ready=0 and mrm_valid=0"
            ),
            "consumer_request_blocked": (
                "mrm_valid!=0, mrm_rw=0 and mrm_ready=0"
            ),
            "clear_visibility_failure": (
                "mrm_clear!=0 followed by unchanged arm_addr/arm_ready=0"
            ),
        },
        "claim_boundary": (
            "c0 public module-port flow-control diagnostic only; held "
            "levels are state and accepted counters are transactions"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def sha256(path: Path) -> str:
    return base.sha256(path)


def write_json(path: Path, value: Any) -> None:
    base.write_json(path, value)


def configure_base() -> None:
    values = {
        "SOURCE_ID": SOURCE_ID,
        "PACKAGE_ID": PACKAGE_ID,
        "SOURCE_SHA256": SOURCE_SHA256,
        "SOURCE_ZIP": SOURCE_ZIP,
        "DEFAULT_OUTPUT": DEFAULT_OUTPUT,
        "OLD_OUTPUT_PREFIX": OLD_OUTPUT_PREFIX,
        "OUTPUT_PREFIX": OUTPUT_PREFIX,
        "ALLOWED_CHANGED_PATHS": ALLOWED_CHANGED_PATHS,
    }
    for name, value in values.items():
        setattr(base, name, value)


def replace_identity(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if SOURCE_ID not in text:
        raise BuildError(f"source identity anchor absent: {path}")
    path.write_text(
        text.replace(SOURCE_ID, PACKAGE_ID),
        encoding="utf-8",
        newline="\n",
    )


def patch_observer(package: Path) -> dict[str, Any]:
    path = package / OBSERVER
    baseline = path.read_bytes()
    if hashlib.sha256(baseline).hexdigest() != (
        "9c9c11f51f495b7b4b0a3ea453bf607dd1a74a0727cac091a2b7c626cc83e500"
    ):
        raise BuildError("p15 observer bytes differ")
    path.write_text(
        baseline.decode("utf-8").rstrip() + "\n" + OBSERVER_APPEND.lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    text = path.read_text(encoding="utf-8")
    private_tokens = (
        ".valid_buf",
        ".buf_wr_en",
        ".buf_rd_en",
        ".arm_addr_reg",
    )
    append = text[len(baseline.decode("utf-8").rstrip() + "\n") :]
    if any(token in append for token in private_tokens):
        raise BuildError("p16 append contains a private Buffer XMR")
    required_ports = (
        ".u_Buffer.arm2buf_req_valid",
        ".u_Buffer.arm2buf_req_addr",
        ".u_Buffer.buf2arm_req_ready",
        ".u_Buffer.mrm2buf_req_valid",
        ".u_Buffer.mrm2buf_req_addr",
        ".u_Buffer.buf2mrm_req_ready",
        ".u_Buffer.mrm2buf_clear",
    )
    if not all(token in append for token in required_ports):
        raise BuildError("p16 public Buffer port matrix is incomplete")
    return {
        "baseline_sha256": hashlib.sha256(baseline).hexdigest(),
        "append_sha256": hashlib.sha256(
            OBSERVER_APPEND.lstrip().encode()
        ).hexdigest(),
        "final_sha256": sha256(path),
        "final_size_bytes": path.stat().st_size,
        "public_port_matrix_complete": True,
        "private_xmr_added": False,
    }


def patch_runtime(package: Path) -> None:
    path = package / RUNTIME
    text = path.read_text(encoding="utf-8").replace(SOURCE_ID, PACKAGE_ID)
    for name, value in CURRENT_CLOUD_LEAVES.items():
        pattern = re_cloud = f'"{name}": "'
        if name in {
            "Buffer.sv",
            "Buffer_Manager.sv",
            "Memory_Req_Manager.sv",
        }:
            continue
        start = text.find(pattern, text.find("CLOUD_AUTHORITY_LEAVES"))
        if start < 0:
            raise BuildError(f"cloud leaf anchor absent: {name}")
        value_start = start + len(pattern)
        value_end = text.find('"', value_start)
        text = text[:value_start] + value + text[value_end:]
    expected_close = "\n}\nCLOUD_AUTHORITY_COMMIT"
    extra_expected = "".join(
        f'    "{name}": "{CURRENT_CLOUD_LEAVES[name]}",\n'
        for name in (
            "Buffer.sv",
            "Buffer_Manager.sv",
            "Memory_Req_Manager.sv",
        )
    )
    if expected_close not in text:
        raise BuildError("EXPECTED_LEAVES close anchor absent")
    text = text.replace(
        expected_close,
        "\n" + extra_expected + "}\nCLOUD_AUTHORITY_COMMIT",
        1,
    )
    cloud_close = "\n}\nPARSING_RE"
    extra_cloud = "".join(
        f'    "{name}": "{CURRENT_CLOUD_LEAVES[name]}",\n'
        for name in (
            "Buffer.sv",
            "Buffer_Manager.sv",
            "Memory_Req_Manager.sv",
        )
    )
    if cloud_close not in text:
        raise BuildError("CLOUD_AUTHORITY_LEAVES close anchor absent")
    text = text.replace(
        cloud_close,
        ",\n" + extra_cloud + "}\nPARSING_RE",
        1,
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8").replace(SOURCE_ID, PACKAGE_ID)
    text = text.replace(
        'public_finalizer="$package_root/package_tools/'
        'node0004_public_order_finalizer.py"\n',
        'public_finalizer="$package_root/package_tools/'
        'node0004_public_order_finalizer.py"\n'
        'b5_finalizer="$package_root/package_tools/'
        'node0004_buffer5_public_finalizer.py"\n',
        1,
    )
    text = text.replace(
        'python3 "$public_finalizer" --observer-log '
        '"$run_root/c0/public_order_observer.log" --compile-status',
        'python3 "$b5_finalizer" --observer-log '
        '"$run_root/c0/buffer5_public_observer.log" --output '
        '"$evidence_root/buffer5_public_summary.json" >/dev/null 2>&1 '
        '|| true\n'
        '  python3 "$public_finalizer" --observer-log '
        '"$run_root/c0/public_order_observer.log" --compile-status',
        1,
    )
    text = text.replace(
        'public_log="$run_root/c0/public_order_observer.log"\n',
        'public_log="$run_root/c0/public_order_observer.log"\n'
        'b5_log="$run_root/c0/buffer5_public_observer.log"\n',
        1,
    )
    text = text.replace(
        '+N4P_EVENT_LIMIT=64 +N4P_FILE=$public_log',
        '+N4P_EVENT_LIMIT=64 +N4P_FILE=$public_log '
        '+N4B5_PUBLIC_CAUSAL +N4B5_EVENT_LIMIT=128 +N4B5_FILE=$b5_log',
        1,
    )
    text = text.replace(
        '"+N4P_FILE=$public_log"',
        '"+N4P_FILE=$public_log" +N4B5_PUBLIC_CAUSAL '
        '+N4B5_EVENT_LIMIT=128 "+N4B5_FILE=$b5_log"',
        1,
    )
    if text.count("+N4B5_PUBLIC_CAUSAL") != 2:
        raise BuildError("p16 runner plusarg insertion count differs")
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_contract(package: Path) -> dict[str, Any]:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    contract = json.loads(
        path.read_text(encoding="utf-8").replace(SOURCE_ID, PACKAGE_ID)
    )
    additions = contract["path_budget"]["additional_projected_paths"]
    for item in (
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/c0/"
        "buffer5_public_observer.log",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence/"
        "buffer5_public_summary.json",
    ):
        if item not in additions:
            additions.append(item)
    contract["package_id"] = PACKAGE_ID
    contract["claim_boundary"] = (
        "p16 package-local public-port Buffer5 c0 causal observer, exact "
        "source binding, actual causal-leaf identity and fixed return only; "
        "no numeric, terminal, formal-D, E3, E4 or E5 claim."
    )
    paths = base.projected_paths(package, contract)
    longest = max(paths, key=lambda value: (len(value), value))
    contract["path_budget"]["max_projected_absolute_path_chars"] = (
        base.SERVER_ROOT_BUDGET_CHARS + 1 + len(longest)
    )
    write_json(path, contract)
    return contract


def patch_manifest(
    package: Path, contract: dict[str, Any], observer_receipt: dict[str, Any]
) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(
        path.read_text(encoding="utf-8").replace(SOURCE_ID, PACKAGE_ID)
    )
    manifest["schema"] = (
        "conv-native-four-lane-0ccae916-p16-buffer5-public-package-v1"
    )
    manifest["package_identity"] = PACKAGE_ID
    manifest["run_namespace"] = (
        f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}"
    )
    manifest["return_name"] = f"{PACKAGE_ID}_return.zip"
    manifest["status"] = "PACKAGE_READY_NOT_RUN"
    manifest["candidate_release"] = False
    manifest["package_release"] = "PERFORMANCE_DIAGNOSTIC_CANDIDATE"
    manifest["source_p15_return_analysis"] = {
        "path": SOURCE_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": sha256(SOURCE_ANALYSIS),
        "classification": (
            "LONG_RUNNING_C0_BACKPRESSURE_STALL_CONFIRMED_BEFORE_EXTERNAL_INT"
        ),
        "exact_p15_source_consumable": False,
        "p15_plus_one_leaf_hotfix_diagnostic_consumable": True,
    }
    manifest["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": (
            "fix exact observer manifest binding and disambiguate Buffer5 "
            "producer/request-ready from MRM consumer/read-clear behavior"
        ),
    }
    manifest["observer_binding"].update(
        {
            "source": OBSERVER,
            "source_sha256": observer_receipt["final_sha256"],
            "sha256": observer_receipt["final_sha256"],
            "size_bytes": observer_receipt["final_size_bytes"],
            "p15_baseline_sha256": observer_receipt["baseline_sha256"],
            "p16_append_sha256": observer_receipt["append_sha256"],
            "new_dut_hierarchy_references": 0,
            "public_module_port_references_added": [
                "Buffer.arm2buf_req_valid/rw/addr",
                "Buffer.buf2arm_req_ready",
                "Buffer.arm2buf_wvalid/clear",
                "Buffer.mrm2buf_req_valid/rw/addr/strb",
                "Buffer.buf2mrm_req_ready",
                "Buffer.mrm2buf_clear",
            ],
            "private_state_xmr": False,
            "private_state_xmr_added_by_p16": False,
            "runtime_enable_p16": "+N4B5_PUBLIC_CAUSAL",
            "p16_feature_marker": "N4B5_FEATURE_ENABLE_V1",
        }
    )
    manifest["buffer5_public_causal_matrix"] = {
        "observer_log": (
            f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}/c0/"
            "buffer5_public_observer.log"
        ),
        "summary": (
            f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}/evidence/"
            "buffer5_public_summary.json"
        ),
        "event_limit": 128,
        "stable_snapshot_period_cycles": 262144,
        "accepted_events_only_are_transactions": True,
        "held_levels_are_state_only": True,
        "candidate_matrix": [
            "producer repeated occupied row",
            "consumer request absent",
            "consumer request blocked",
            "clear visibility failure",
        ],
    }
    manifest["expected_production_rtl_identity"][
        "cloud_authority_commit"
    ] = CURRENT_COMMIT
    manifest["expected_production_rtl_identity"][
        "cloud_authority_leaves"
    ] = CURRENT_CLOUD_LEAVES
    manifest["expected_production_rtl_identity"]["leaves"].update(
        {
            name: CURRENT_CLOUD_LEAVES[name]
            for name in (
                "Buffer.sv",
                "Buffer_Manager.sv",
                "Memory_Req_Manager.sv",
            )
        }
    )
    manifest["cloud_rtl_authority"]["approved_commit"] = CURRENT_COMMIT
    manifest["cloud_rtl_authority"]["leaves"] = CURRENT_CLOUD_LEAVES
    allow = manifest["return_allowlist"]
    allow.extend(
        [
            {
                "max_bytes": 2_097_152,
                "missing_semantics": (
                    "Buffer5 public-port finalizer did not emit a summary"
                ),
                "required": True,
                "source_path": "buffer5_public_summary.json",
                "source_root": "evidence",
                "target_path": "evidence/buffer5_public_summary.json",
            },
            {
                "max_bytes": 8_388_608,
                "missing_semantics": (
                    "Buffer5 public-port observer did not reach time zero"
                ),
                "required": False,
                "source_path": "c0/buffer5_public_observer.log",
                "source_root": "run",
                "target_path": "runs/c0/buffer5_public_observer.log",
            },
        ]
    )
    manifest["release_gate_applicability"].update(
        {
            "package_local_hdl": "blocking_applicable_observer_append",
            "diagnostic_predicate_trace": (
                "blocking_applicable_public_buffer5_event_trace"
            ),
        }
    )
    manifest["release_gate_matrix"]["package_local_hdl"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "pass": True,
        "scope": "package-local observer append; functional RTL absent",
    }
    manifest["release_gate_matrix"]["diagnostic_semantics"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "pass": True,
        "scope": (
            "public-port event/change/stable-level trace and qualified "
            "transaction counters"
        ),
    }
    paths = base.projected_paths(package, contract)
    longest = max(paths, key=lambda value: (len(value), value))
    inner = [
        item.relative_to(package).as_posix()
        for item in package.rglob("*")
        if item.is_file() and item != path
    ] + ["package_manifest.json"]
    manifest["path_length_budget"].update(
        {
            "longest_projected_relative_path": longest,
            "longest_projected_relative_path_chars": len(longest),
            "max_projected_relative_path_chars": len(longest),
            "max_projected_absolute_path_chars": (
                base.SERVER_ROOT_BUDGET_CHARS + 1 + len(longest)
            ),
            "max_zip_member_chars": max(
                len(f"{WORKLOAD_INSTALL_NAME}/{relative}")
                for relative in inner
            ),
            "max_inner_suffix_chars": max(map(len, inner)),
            "max_inner_depth": max(
                len(PurePosixPath(relative).parts) for relative in inner
            ),
            "max_inner_component_chars": max(
                len(component)
                for relative in inner
                for component in PurePosixPath(relative).parts
            ),
        }
    )
    manifest["files"] = base.file_records(package)
    write_json(path, manifest)


def patch_readme_and_pointer(package: Path) -> None:
    pointer_path = package / "TEST_PACKAGE_MANIFEST.json"
    pointer = json.loads(
        pointer_path.read_text(encoding="utf-8").replace(SOURCE_ID, PACKAGE_ID)
    )
    pointer["schema"] = "conv-native-four-lane-p16-buffer5-public-pointer-v1"
    pointer["package_identity"] = PACKAGE_ID
    pointer["status"] = "PACKAGE_READY_NOT_RUN"
    write_json(pointer_path, pointer)
    (package / "README.md").write_text(
        "# Native four-lane Conv p16 Buffer5 public causal successor\n\n"
        "This diagnostic successor preserves the p15 workload/config/numeric "
        "payload and install-only V2 runtime layout. It fixes the exact "
        "observer manifest binding and records only public Buffer module "
        "ports at the c0 Buffer5 backpressure boundary.\n\n"
        "Run after extraction:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n"
        "```\n\n"
        f"Expected return: `/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip` "
        "and its `.sha256` sidecar. The package is diagnostic-only and does "
        "not claim natural terminal, formal 320D, performance, E3, E4 or E5.\n",
        encoding="utf-8",
        newline="\n",
    )


def build_profile(output: Path) -> None:
    value = {
        "schema": "server-package-build-profile-v1",
        "package_id": PACKAGE_ID,
        "family": "conv_native_four_lane",
        "lifecycle": "NEXT_FRESH_SUCCESSOR",
        "mode": "SHADOW_ONLY_NEXT_FRESH",
        "contract_valid": True,
        "current_package_impact": True,
        "changed_surfaces": [
            "package_identity",
            "observer",
            "parser",
            "return_collector",
            "runner",
            "sca",
            "storage",
        ],
        "required_validator_gates": [
            "core_identity_bootstrap",
            "diagnostic_semantics",
            "final_zip_content",
            "materialized_config",
            "package_local_hdl",
            "return_result_contract",
            "runner_control_flow",
            "runtime_layout",
            "storage_rotation",
        ],
        "claim_boundary": {
            "builds_zip": False,
            "runs_family_validator": False,
            "blocking_promotion_authorized": False,
            "changes_family_release": False,
        },
        "preflight": {"pass": True, "errors": [], "warnings": []},
    }
    write_json(output / f"{PACKAGE_ID}.build_profile.json", value)


def build_directory(destination: Path) -> Path:
    configure_base()
    if sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p15 source ZIP differs")
    if not SOURCE_ANALYSIS.is_file():
        raise BuildError("formal p15 return analysis is absent")
    package = base.safe_extract_source(destination)
    patch_runner(package)
    for relative in (
        "package_tools/fixed_simresult_publisher.py",
    ):
        replace_identity(package / relative)
    patch_runtime(package)
    base.patch_sca_d(package)
    (package / FINALIZER).write_text(
        FINALIZER_SOURCE, encoding="utf-8", newline="\n"
    )
    observer_receipt = patch_observer(package)
    contract = patch_contract(package)
    patch_readme_and_pointer(package)
    patch_manifest(package, contract, observer_receipt)
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = [
        output / PACKAGE_ID,
        output / f"{PACKAGE_ID}.zip",
        output / f"{PACKAGE_ID}.zip.sha256",
        output / f"{PACKAGE_ID}.build.json",
        output / f"{PACKAGE_ID}.build_profile.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite a p16 build target")
    build_profile(output)
    package = build_directory(output)
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    digest = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix=".p16_repeat_", dir=ROOT) as temp:
        repeat_root = Path(temp)
        repeat = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{PACKAGE_ID}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("p16 deterministic double build differs")
    sidecar = output / f"{PACKAGE_ID}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    source_payloads = base.zip_payloads(SOURCE_ZIP, SOURCE_ID) if hasattr(
        base, "zip_payloads"
    ) else None
    report = {
        "schema": "conv-native-four-lane-p16-buffer5-public-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID,
        "source_p15_zip_sha256": SOURCE_SHA256,
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "deterministic_double_build": deterministic,
        "changed_paths": sorted(ALLOWED_CHANGED_PATHS),
        "source_payload_probe": source_payloads is not None,
        "functional_rtl_modified": False,
        "config_numeric_w3_golden_timeout_changed": False,
        "observer_changed": True,
        "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


configure_base()


if __name__ == "__main__":
    raise SystemExit(main())
