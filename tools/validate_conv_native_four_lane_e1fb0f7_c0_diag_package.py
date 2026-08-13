from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_conv_native_four_lane_e1fb0f7_c0_diag_package as build
from tools import conv_native_four_lane_e1fb0f7_c0_diag_runtime as runtime
from tools import node0004_assumed_hardware_server_runtime_v2 as numeric_base


INSTALL_NAME = runtime.INSTALL_NAME
PACKAGE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / INSTALL_NAME
)
PACKAGE_ZIP = PACKAGE_ROOT.with_suffix(".zip")
OUTPUT = PACKAGE_ROOT.parent / f"{INSTALL_NAME}.final_zip_audit.json"
SOURCE_P4_ROOT = "r5_n4_df23e4d_p4"
SOURCE_P4_ZIP = PACKAGE_ROOT.parent / f"{SOURCE_P4_ROOT}.zip"
SOURCE_P4_SHA256 = (
    "c8d42f979b07468e869d077755f987c09c04d017cd1bc6ab50a71a8ee1d0204e"
)
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
RTL_REPO = ROOT / "Trassic2.0_RTL"
GIT_PATHS = {
    "Array_Request_Manager.sv": (
        "code/NDP_rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Array_Request_Manager.sv"
    ),
    "Buffer_AG_Idx_Queue.sv": (
        "code/NDP_rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Buffer_AG_Idx_Queue.sv"
    ),
    "RD_Data_Channel.sv": (
        "code/NDP_rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_RD_Stream_Engine/RD_Data_Channel.sv"
    ),
    "Neighbor_Out_AG.sv": (
        "code/NDP_rtl/Slice/LSU/Stream_Engine/Neighbor_Stream_Engine/"
        "Neighbor_Out_AG.sv"
    ),
    "SA_PE_Float_CSA.v": (
        "code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
        "SA_PE_Float_CSA.v"
    ),
    "SA_PE_Float_Control.v": (
        "code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
        "SA_PE_Float_Control.v"
    ),
    "SA_PE_Mul_Array.v": (
        "code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
        "SA_PE_Mul_Array.v"
    ),
    "SA_ALU.v": (
        "code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_ALU.v"
    ),
}
CURRENT_SCOPE_FILES = {
    "Slice_Execution_Manager.sv": (
        "NDP_copy01/rtl/Slice/Slice_Execution_Manager.sv"
    ),
    "Memory_RD_Stream_Engine.sv": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
        "Memory_Stream_Engine/Memory_RD_Stream_Engine/"
        "Memory_RD_Stream_Engine.sv"
    ),
    "RD_Data_Channel.sv": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
        "Memory_Stream_Engine/Memory_RD_Stream_Engine/RD_Data_Channel.sv"
    ),
    "Buffer_AG_Idx_Queue.sv": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
        "Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv"
    ),
    "Memory_WR_Stream_Engine.sv": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
        "Memory_Stream_Engine/Memory_WR_Stream_Engine/"
        "Memory_WR_Stream_Engine.sv"
    ),
    "Array_Request_Manager.sv": (
        "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Array_Request_Manager.sv"
    ),
    "Neighbor_Out_AG.sv": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
        "Neighbor_Stream_Engine/Neighbor_Out_AG.sv"
    ),
    "Slice.sv": "NDP_copy01/rtl/Slice/Slice_cdc.sv",
    "Buffer.sv": (
        "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv"
    ),
}
SCOPE_TOKENS = {
    "Slice_Execution_Manager.sv": (
        "sem2scm_cfg_start",
        "scm2sem_cfg_finish",
        "sem2iga_exec_start",
        "slice_cmpt_finish",
    ),
    "Memory_RD_Stream_Engine.sv": (
        "rd_data_chl_req_valid",
        "rd_data_chl_req_ready",
        "mse2buf_wvalid",
        "buf2mse_wreq_ready",
    ),
    "RD_Data_Channel.sv": (
        "rd_chl_ib_wr_hs",
        "rd_chl_ib_rd_hs",
        "rd_data_chl_prepared_data_wr_hs",
        "rd_data_chl_prepared_data_rd_hs",
        "rd_chl_queue_full",
        "rd_chl_queue_empty",
        "rd_data_chl_prepared_data_cnt",
    ),
    "Buffer_AG_Idx_Queue.sv": (
        "buf_ag_idx_queue_wr_en",
        "buf_ag_idx_queue_rd_en",
        "buf_ag_idx_queue_full",
        "buf_ag_idx_queue_empty",
    ),
    "Memory_WR_Stream_Engine.sv": (
        "mse_mem_ag_tag_valid",
        "mse_mem_ag_bp_pre",
    ),
    "Array_Request_Manager.sv": (
        "arm2buf_req_valid",
        "buf2arm_req_ready",
        "buf2arm_rvalid",
        "array2arm_bp_post",
        "buf2arm_valid_hold",
        "arm_buf_rd_finish",
    ),
    "Neighbor_Out_AG.sv": (
        "nse2buf_rreq_valid",
        "buf2nse_rreq_ready",
        "buf2nse_rvalid",
        "nbr_out_rvalid",
        "slice2nse_rready",
        "fifo_almost_full",
        "fifo_empty",
        "nbr_ag_out_finish",
    ),
    "Slice.sv": (
        "buf2spec_array_rtag",
        "spec_array2buf_bp_post",
        "spec_array2buf_wtag",
        "buf2spec_array_bp_pre",
    ),
    "Buffer.sv": ("buf_wr_en", "buf_rd_en"),
}


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    return numeric_base.sha256(path)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run(
    argv: list[str], cwd: Path, *, binary: bool = False
) -> dict[str, Any]:
    process = subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=not binary,
        encoding=None if binary else "utf-8",
        errors=None if binary else "replace",
        check=False,
    )
    stdout = process.stdout
    stderr = process.stderr
    return {
        "argv": argv,
        "cwd": str(cwd),
        "exit_code": process.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


def safe_zip_records(path: Path, expected_root: str) -> dict[str, Any]:
    records: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    roots: set[str] = set()
    seen: set[str] = set()
    uncompressed = 0
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"CRC differs: {bad}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
                or stat.S_ISLNK(mode)
            ):
                errors.append(f"unsafe member: {info.filename}")
                continue
            seen.add(info.filename)
            if not pure.parts:
                continue
            roots.add(pure.parts[0])
            if info.is_dir():
                continue
            payload = archive.read(info)
            uncompressed += len(payload)
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            records[relative] = {
                "size_bytes": len(payload),
                "sha256": digest(payload),
            }
    if roots != {expected_root}:
        errors.append(f"root differs: {sorted(roots)}")
    return {
        "valid": not errors,
        "errors": errors,
        "root": expected_root,
        "file_count": len(records),
        "uncompressed_bytes": uncompressed,
        "records": records,
    }


def p4_c0_relation(package: Path) -> dict[str, Any]:
    prefix = f"{SOURCE_P4_ROOT}/workload/runtime/runs/c0/"
    source: dict[str, bytes] = {}
    with zipfile.ZipFile(SOURCE_P4_ZIP) as archive:
        for info in archive.infolist():
            if not info.is_dir() and info.filename.startswith(prefix):
                source[info.filename[len(prefix) :]] = archive.read(info)
    target_root = package / "workload/runtime/runs/c0"
    target = {
        path.relative_to(target_root).as_posix(): path.read_bytes()
        for path in target_root.rglob("*")
        if path.is_file()
    }
    missing = sorted(set(source) - set(target))
    extra = sorted(set(target) - set(source))
    changed: list[str] = []
    normalized: list[str] = []
    old = SOURCE_P4_ROOT.encode()
    new = INSTALL_NAME.encode()
    for relative in sorted(set(source) & set(target)):
        if source[relative] == target[relative]:
            continue
        if relative in {"sca_cfg.json", "sca_cfg_D.json"} and (
            source[relative].replace(old, new) == target[relative]
        ):
            normalized.append(relative)
        else:
            changed.append(relative)
    return {
        "valid": (
            not missing
            and not extra
            and not changed
            and normalized == ["sca_cfg.json", "sca_cfg_D.json"]
        ),
        "source_file_count": len(source),
        "target_file_count": len(target),
        "byte_identical_file_count": len(target) - len(normalized) - len(changed),
        "identity_normalized_files": normalized,
        "missing": missing,
        "extra": extra,
        "unexpected_changed": changed,
    }


def consumer_closure(package: Path) -> dict[str, Any]:
    runtime_root = package / "workload/runtime"
    c0 = runtime_root / "runs/c0"
    sca = json.loads((c0 / "sca_cfg.json").read_text(encoding="utf-8"))
    sca_d = json.loads(
        (c0 / "sca_cfg_D.json").read_text(encoding="utf-8")
    )
    required: list[str] = []
    source_paths: list[str] = []
    for value in sca.values():
        if isinstance(value, dict) and isinstance(value.get("path"), str):
            marker = f"install/cfg_pkg/{INSTALL_NAME}/"
            if value["path"].startswith(marker):
                source_paths.append(value["path"])
                required.append(value["path"][len(marker) :])
    missing = sorted(
        relative for relative in required if not (runtime_root / relative).is_file()
    )
    d_paths = [
        value["path"]
        for value in sca_d.values()
        if isinstance(value, dict) and isinstance(value.get("path"), str)
    ]
    d_payloads = [
        path.relative_to(runtime_root).as_posix()
        for path in runtime_root.rglob("matrix_D_linearized_128bit.txt")
    ]
    execplan = (c0 / "install/execplan.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    checks = {
        "all_input_consumers_exist": not missing,
        "all_sca_paths_bind_fresh_identity": all(
            f"/{INSTALL_NAME}/" in path
            for path in source_paths + d_paths
        ),
        "formal_d_payloads_absent": not d_payloads,
        "d_endpoints_retained_for_simulation": len(d_paths) == 28,
        "execplan_nonempty": bool(execplan.strip()),
        "single_c0_tree": sorted(
            path.name
            for path in (runtime_root / "runs").iterdir()
            if path.is_dir()
        )
        == ["c0"],
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "input_consumer_count": len(required),
        "missing_input_consumers": missing,
        "simulation_d_endpoint_count": len(d_paths),
        "formal_d_payloads": d_payloads,
        "execplan_sha256": sha256(c0 / "install/execplan.txt"),
        "sca_cfg_sha256": sha256(c0 / "sca_cfg.json"),
        "sca_cfg_D_sha256": sha256(c0 / "sca_cfg_D.json"),
    }


def immutable_git_identity() -> dict[str, Any]:
    safe = str(RTL_REPO.resolve()).replace("\\", "/")
    leaves: dict[str, Any] = {}
    for basename, relative in GIT_PATHS.items():
        result = run(
            [
                "git",
                "-c",
                f"safe.directory={safe}",
                "-C",
                str(RTL_REPO),
                "show",
                f"{runtime.EXPECTED_COMMIT}:{relative}",
            ],
            ROOT,
            binary=True,
        )
        payload = result["stdout"] if result["exit_code"] == 0 else b""
        observed = digest(payload)
        expected = runtime.EXPECTED_LEAVES[basename]
        leaves[basename] = {
            "git_path": relative,
            "git_show_exit_code": result["exit_code"],
            "size_bytes": len(payload),
            "sha256": observed,
            "expected_sha256": expected,
            "match": result["exit_code"] == 0 and observed == expected,
        }
    return {
        "valid": all(value["match"] for value in leaves.values()),
        "commit": runtime.EXPECTED_COMMIT,
        "byte_identity": "immutable Git blob bytes",
        "leaves": leaves,
    }


def observer_scope(observer: str) -> dict[str, Any]:
    anchors: dict[str, Any] = {}
    for owner, relative in CURRENT_SCOPE_FILES.items():
        path = ROOT / relative
        text = path.read_text(encoding="utf-8", errors="replace")
        token_values = {
            token: (
                re.search(rf"\b{re.escape(token)}\b", text) is not None
                and re.search(
                    rf"\b{re.escape(token)}\b", observer
                )
                is not None
            )
            for token in SCOPE_TOKENS[owner]
        }
        anchors[owner] = {
            "path": relative,
            "tokens": token_values,
            "valid": all(token_values.values()),
        }
    hierarchy_tokens = (
        "slice_with_datahub_mc_group_gen",
        "u_slice_with_datahub_mc_group",
        "slice_group_gen",
        "u_slice_wrapper",
        "u_Slice",
        "u_LSU",
        "u_Stream_Engine",
        "MSE_INST",
        "RD_MSE",
        "WR_MSE",
        "u_Memory_RD_Stream_Engine",
        "u_RD_Data_Channel",
        "u_Buffer_AG_Idx_Queue",
        "u_Buffer_Manager_Cluster",
        "BUFFER_MANAGER",
        "u_Array_Request_Manager",
        "NSE_INST",
        "u_Neighbor_Stream_Engine",
        "u_Neighbor_Out_AG",
    )
    hierarchy = {token: token in observer for token in hierarchy_tokens}
    checks = {
        "all_leaf_tokens_bound_to_current_owner_sources": all(
            value["valid"] for value in anchors.values()
        ),
        "all_hierarchy_tokens_present": all(hierarchy.values()),
        "read_only_no_terminal_drive": (
            "$finish" not in observer
            and "$fatal" not in observer
            and "$stop" not in observer
        ),
        "canonical_schema_single": observer.count(
            '"N4D_CANONICAL_V1"'
        )
        == 1,
        "progress_schema_single": observer.count(
            '"N4D_PROGRESS_V1"'
        )
        == 1,
        "summary_not_canonical": (
            observer.count("N4D_SUMMARY_V1") == 1
            and observer.count("n4d_decision_emitted") >= 4
        ),
        "feature_schema_two_sinks": observer.count(
            "N4D_FEATURE_ENABLE_V2 feature=NATIVE4_C0_BOUNDARY enabled=1 "
            "heartbeat_cycles=%0d stall_cycles=%0d slice=%0d"
        )
        == 2,
        "feature_specific_gate": (
            '$test$plusargs("N4D_C0_BOUNDARY_DIAG")' in observer
        ),
        "db_owner_clock": (
            "always @(posedge u_NDP_Top_new.clk_db" in observer
        ),
        "sg_owner_clock": (
            "always @(posedge u_NDP_Top_new.clk_sg" in observer
        ),
        "finish_edges_qualified": (
            "&&\n                !n4d_arm_finish_d[buf_id]" in observer
            and "&&\n                !n4d_nse_finish_d[nse]" in observer
        ),
        "raw_levels_not_counted_as_progress": all(
            f"if (n4d_{token}" not in observer
            for token in (
                "rd_queue_full_mon",
                "rd_queue_empty_mon",
                "bag_full_mon",
                "bag_empty_mon",
                "arm_hold_mon",
                "arm_bp_mon",
                "nse_full_mon",
                "nse_empty_mon",
            )
        ),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "owner_source_anchors": anchors,
        "hierarchy_tokens": hierarchy,
    }


def observer_projection(observer: str) -> str:
    specialized = observer
    for selector in (
        "n4d_group_id",
        "n4d_local_slice_id",
        "mse",
        "rd",
        "buf_id",
        "nse",
        "sa_in",
        "sa_out",
        "sa_buf",
        "req",
    ):
        specialized = specialized.replace(f"[{selector}]", "[0]")
    harness = r"""
`timescale 1ns/1ps
`define SLICE_GROUP_SIZE 1
`define SLICE_GROUP_NUM 1
`define MEMORY_RD_STREAM_ENGINE_NUM 4
`define MEMORY_STREAM_ENGINE_NUM 5
`define MSE_REQ_CHL_NUM 2
`define BUFFER_NUM 6
`define NEIGHBOR_STREAM_ENGINE_NUM 2
`define SA_INPORT_GROUP_NUM 3
`define SA_OUTPORT_GROUP_NUM 1
`define SA_PORT_HANDLE_BUF_NUM 2
`define ARRAY_PORT_TAG 16
`define ARRAY_PORT_GROUP_SIZE 8
`define BUFFER_BANK_NUM 8
module n4d_sem_stub;
  logic sem2scm_cfg_start, scm2sem_cfg_finish;
  logic sem2iga_exec_start, slice_cmpt_finish;
endmodule
module n4d_rd_data_stub;
  logic rd_chl_ib_wr_hs, rd_chl_ib_rd_hs;
  logic rd_data_chl_prepared_data_wr_hs;
  logic rd_data_chl_prepared_data_rd_hs;
  logic rd_chl_queue_full, rd_chl_queue_empty;
  logic [5:0] rd_data_chl_prepared_data_cnt;
endmodule
module n4d_bag_stub;
  logic buf_ag_idx_queue_wr_en, buf_ag_idx_queue_rd_en;
  logic buf_ag_idx_queue_full, buf_ag_idx_queue_empty;
endmodule
module n4d_rd_engine_stub;
  n4d_rd_data_stub u_RD_Data_Channel();
  n4d_bag_stub u_Buffer_AG_Idx_Queue();
  logic rd_data_chl_req_valid, rd_data_chl_req_ready;
  logic mse2buf_wvalid, buf2mse_wreq_ready;
endmodule
module n4d_wr_engine_stub;
  n4d_bag_stub u_Buffer_AG_Idx_Queue();
  logic mse_mem_ag_tag_valid, mse_mem_ag_bp_pre;
endmodule
module n4d_arm_stub;
  logic [1:0] arm2buf_req_valid;
  logic buf2arm_req_ready, buf2arm_rvalid, array2arm_bp_post;
  logic buf2arm_valid_hold, arm_buf_rd_finish;
endmodule
module n4d_buffer_stub;
  logic [`BUFFER_BANK_NUM-1:0] buf_wr_en, buf_rd_en;
endmodule
module n4d_buffer_manager_stub;
  n4d_arm_stub u_Array_Request_Manager();
  n4d_buffer_stub u_Buffer();
endmodule
module n4d_bmc_stub;
  generate
    for (genvar b = 0; b < `BUFFER_NUM; b++) begin : BUFFER_MANAGER
      n4d_buffer_manager_stub u_Buffer_Manager();
    end
  endgenerate
endmodule
module n4d_neighbor_out_stub;
  logic nse2buf_rreq_valid, buf2nse_rreq_ready, buf2nse_rvalid;
  logic nbr_out_rvalid, slice2nse_rready;
  logic fifo_almost_full, fifo_empty, nbr_ag_out_finish;
endmodule
module n4d_neighbor_engine_stub;
  n4d_neighbor_out_stub u_Neighbor_Out_AG();
endmodule
module n4d_stream_stub;
  generate
    for (
      genvar m = 0; m < `MEMORY_STREAM_ENGINE_NUM; m++
    ) begin : MSE_INST
      if (m < `MEMORY_RD_STREAM_ENGINE_NUM) begin : RD_MSE
        n4d_rd_engine_stub u_Memory_RD_Stream_Engine();
      end
      else begin : WR_MSE
        n4d_wr_engine_stub u_Memory_WR_Stream_Engine();
      end
    end
    for (
      genvar n = 0; n < `NEIGHBOR_STREAM_ENGINE_NUM; n++
    ) begin : NSE_INST
      n4d_neighbor_engine_stub u_Neighbor_Stream_Engine();
    end
  endgenerate
endmodule
module n4d_lsu_stub;
  n4d_stream_stub u_Stream_Engine();
  n4d_bmc_stub u_Buffer_Manager_Cluster();
endmodule
module n4d_slice_stub;
  n4d_sem_stub u_Slice_Execution_Manager();
  n4d_lsu_stub u_LSU();
  logic [`SA_INPORT_GROUP_NUM-1:0]
        [`SA_PORT_HANDLE_BUF_NUM-1:0]
        [`ARRAY_PORT_TAG-1:0] buf2spec_array_rtag;
  logic [`SA_INPORT_GROUP_NUM-1:0]
        [`SA_PORT_HANDLE_BUF_NUM-1:0] spec_array2buf_bp_post;
  logic [`SA_OUTPORT_GROUP_NUM-1:0]
        [`SA_PORT_HANDLE_BUF_NUM-1:0]
        [`ARRAY_PORT_TAG-1:0] spec_array2buf_wtag;
  logic [`SA_OUTPORT_GROUP_NUM-1:0]
        [`SA_PORT_HANDLE_BUF_NUM-1:0] buf2spec_array_bp_pre;
endmodule
module n4d_slice_wrapper_stub;
  n4d_slice_stub u_Slice();
endmodule
module n4d_group_stub;
  generate
    for (genvar s = 0; s < `SLICE_GROUP_NUM; s++) begin : slice_group_gen
      n4d_slice_wrapper_stub u_slice_wrapper();
    end
  endgenerate
endmodule
module n4d_ndp_stub;
  logic clk_db, rst_n_db, clk_sg, rst_n_sg;
  generate
    for (
      genvar g = 0; g < `SLICE_GROUP_SIZE; g++
    ) begin : slice_with_datahub_mc_group_gen
      n4d_group_stub u_slice_with_datahub_mc_group();
    end
  endgenerate
endmodule
module n4d_focus_top;
  n4d_ndp_stub u_NDP_Top_new();
  logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`MEMORY_STREAM_ENGINE_NUM-1:0]
        [`MSE_REQ_CHL_NUM-1:0] local_req_hs;
  logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`MEMORY_STREAM_ENGINE_NUM-1:0]
        [`MSE_REQ_CHL_NUM-1:0] local_rdata_hs;
  logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`MEMORY_STREAM_ENGINE_NUM-1:0]
        [`MSE_REQ_CHL_NUM-1:0] local_wdata_hs;
"""
    return harness + specialized + "\nendmodule\n"


def actual_consumer_closure(observer: str) -> dict[str, Any]:
    function_start = observer.index(
        "function automatic void n4d_emit_record"
    )
    function_end = observer.index("endfunction", function_start)
    block = observer[function_start:function_end]
    block_start_line = observer[:function_start].count("\n") + 1
    state_bases = sorted(
        {
            token
            for token in re.findall(r"\bn4d_[A-Za-z0-9_]+\b", block)
            if token not in {"n4d_emit_record"}
        }
    )

    def equivalence_class(base: str) -> str:
        if base in {
            "n4d_req_count",
            "n4d_rdata_count",
            "n4d_wdata_count",
            "n4d_bag_wr_count",
            "n4d_bag_rd_count",
        }:
            return "mse_longint_counter_array"
        if base in {
            "n4d_rd_meta_count",
            "n4d_rd_ib_wr_count",
            "n4d_rd_ib_rd_count",
            "n4d_rd_prep_wr_count",
            "n4d_rd_prep_rd_count",
            "n4d_rd_buf_count",
        }:
            return "read_mse_longint_counter_array"
        if base in {
            "n4d_arm_req_count",
            "n4d_arm_resp_count",
            "n4d_arm_finish_count",
        }:
            return "buffer_arm_longint_counter_array"
        if base in {
            "n4d_nse_req_count",
            "n4d_nse_in_count",
            "n4d_nse_out_count",
            "n4d_nse_finish_count",
        }:
            return "neighbor_longint_counter_array"
        if base in {
            "n4d_sa_input_count",
            "n4d_sa_output_count",
            "n4d_buf4_wr_count",
            "n4d_buf4_rd_count",
            "n4d_buf5_wr_count",
            "n4d_buf5_rd_count",
            "n4d_mse4_idx_count",
        }:
            return "scalar_longint_qualified_counter"
        if base in {
            "n4d_rd_queue_full_mon",
            "n4d_rd_queue_empty_mon",
        }:
            return "read_queue_level_monitor"
        if base == "n4d_rd_prep_count_mon":
            return "read_prepared_count_monitor"
        if base in {"n4d_bag_full_mon", "n4d_bag_empty_mon"}:
            return "buffer_ag_level_monitor"
        if base in {"n4d_arm_hold_mon", "n4d_arm_bp_mon"}:
            return "array_request_level_monitor"
        if base in {"n4d_nse_full_mon", "n4d_nse_empty_mon"}:
            return "neighbor_level_monitor"
        return f"singleton_{base}"

    lines = observer.splitlines()
    consumers: list[dict[str, Any]] = []
    classes: dict[str, list[str]] = {}
    ownerless = 0
    for base in state_bases:
        klass = equivalence_class(base)
        classes.setdefault(klass, []).append(base)
        use_lines = [
            block_start_line + offset
            for offset, line in enumerate(block.splitlines())
            if re.search(rf"\b{re.escape(base)}\b", line)
        ]
        declaration_lines = [
            index + 1
            for index, line in enumerate(lines[: block_start_line - 1])
            if re.search(rf"\b{re.escape(base)}\b", line)
        ]
        has_owner = bool(declaration_lines)
        if base.endswith("_mon"):
            owner_kind = "continuous_assignment_monitor"
            has_owner = has_owner and (
                f"assign {base}" in observer
                or re.search(
                    rf"assign\s+{re.escape(base)}\s*\[",
                    observer,
                )
                is not None
            )
        elif base.endswith("_count") or base in {
            "n4d_db_cycles",
            "n4d_db_total",
            "n4d_sg_total",
            "n4d_window_start_cycle",
            "n4d_delta",
            "n4d_active",
            "n4d_silent_windows",
            "n4d_fd",
            "n4d_group_id",
            "n4d_local_slice_id",
        }:
            owner_kind = "initialized_or_qualified_state"
            has_owner = has_owner and observer.count(base) >= 2
        else:
            owner_kind = "package_local_state"
        if not has_owner:
            ownerless += 1
        expression_lines = [lines[line - 1].strip() for line in use_lines]
        consumers.append(
            {
                "identifier": base,
                "equivalence_class": klass,
                "member": "tb_probe/native_return_observer.svh",
                "consumer_lines": use_lines,
                "consumer_expression_sha256": [
                    digest(line.encode()) for line in expression_lines
                ],
                "declaration_or_owner_lines": declaration_lines,
                "owner_kind": owner_kind,
                "owner_closed": has_owner,
            }
        )
    return {
        "valid": bool(consumers) and ownerless == 0,
        "scope": (
            "all package-local n4d state leaves consumed by the exact "
            "canonical/progress record emitter"
        ),
        "actual_consumer_count": len(consumers),
        "actual_consumers": consumers,
        "equivalence_classes": {
            name: sorted(members) for name, members in sorted(classes.items())
        },
        "uncovered": 0,
        "ownerless_state": ownerless,
    }


def compile_observer_cases(
    observer: str, compiler: Path
) -> dict[str, Any]:
    version = run([str(compiler), "-V"], ROOT)
    with tempfile.TemporaryDirectory(prefix="n4-p5-hdl-") as name:
        root = Path(name)

        def compile_case(stem: str, source_text: str) -> dict[str, Any]:
            source = root / f"{stem}.sv"
            source.write_text(source_text, encoding="utf-8", newline="\n")
            return run(
                [
                    str(compiler),
                    "-g2012",
                    "-tnull",
                    "-s",
                    "n4d_focus_top",
                    str(source),
                ],
                root,
            )

        projection = observer_projection(observer)
        positive = compile_case("positive", projection)
        missing_counter = compile_case(
            "negative_missing_counter",
            projection.replace(
                "longint unsigned n4d_sg_total;",
                "// n4d_sg_total removed",
                1,
            ),
        )
        typo_consumer = compile_case(
            "negative_typo_consumer",
            projection.replace(
                "n4d_mse4_idx_count++",
                "n4d_mse4_idx_count_typo++",
                1,
            ),
        )
        closure = actual_consumer_closure(observer)
        class_mutations: list[dict[str, Any]] = []
        function_start = observer.index(
            "function automatic void n4d_emit_record"
        )
        function_end = observer.index("endfunction", function_start)
        prefix = observer[:function_start]
        block = observer[function_start:function_end]
        suffix = observer[function_end:]
        for class_name, members in closure[
            "equivalence_classes"
        ].items():
            representative = members[0]
            mutated_block, replacements = re.subn(
                rf"\b{re.escape(representative)}\b",
                f"{representative}_actual_consumer_typo",
                block,
                count=1,
            )
            mutation = compile_case(
                f"consumer_{len(class_mutations):02d}",
                observer_projection(prefix + mutated_block + suffix),
            )
            class_mutations.append(
                {
                    "equivalence_class": class_name,
                    "members": members,
                    "representative_actual_consumer": representative,
                    "source_span_sha256": digest(
                        next(
                            line.strip().encode()
                            for line in block.splitlines()
                            if re.search(
                                rf"\b{re.escape(representative)}\b",
                                line,
                            )
                        )
                    ),
                    "mutation_count": replacements,
                    "frontend_exit_code": mutation["exit_code"],
                    "failed_closed": (
                        replacements == 1
                        and mutation["exit_code"] != 0
                    ),
                }
            )
    scope_positive = observer_scope(observer)
    scope_typo = observer_scope(
        observer.replace("rd_chl_queue_full", "rd_chl_queue_full_typo")
    )
    removed_update = observer.replace(
        "n4d_rd_prep_wr_count[rd]++;",
        "/* qualified update removed */",
        1,
    )
    update_negative = (
        removed_update.count("n4d_rd_prep_wr_count[rd]++;") == 0
        and observer.count("n4d_rd_prep_wr_count[rd]++;") == 1
    )
    negative_controls = {
        "missing_counter_compile_fails":
            missing_counter["exit_code"] != 0,
        "typo_consumer_compile_fails": typo_consumer["exit_code"] != 0,
        "typo_xmr_scope_fails": not scope_typo["valid"],
        "qualified_update_removal_detected": update_negative,
        "every_actual_consumer_class_fail_closed": all(
            item["failed_closed"] for item in class_mutations
        ),
    }
    return {
        "applicable": True,
        "rule_id": (
            "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-"
            "SYNTAX-SCOPE-POSITIVE-001"
        ),
        "valid": (
            version["exit_code"] == 0
            and
            positive["exit_code"] == 0
            and scope_positive["valid"]
            and closure["valid"]
            and all(negative_controls.values())
        ),
        "frontend": {
            "name": "Icarus Verilog",
            "path": str(compiler),
            "version_exit_code": version["exit_code"],
            "version_stdout": version["stdout"],
            "version_stderr": version["stderr"],
            "command": positive["argv"],
            "cwd": positive["cwd"],
            "exit": positive["exit_code"],
            "coverage": "focused",
            "scope": (
                "package observer procedural syntax projection plus exact "
                "XMR hierarchy/leaf ownership against current RTL sources"
            ),
            "full_design_elaboration_claimed": False,
        },
        "focused_harness_sha256": digest(
            observer_projection("").encode()
        ),
        "exact_members": [
            {
                "path": "tb_probe/native_return_observer.svh",
                "bytes": len(observer.encode()),
                "sha256": digest(observer.encode()),
                "role": "package-local read-only diagnostic observer",
            }
        ],
        "include_or_concatenation_order_sha256": digest(
            b"tb_probe/native_return_observer.svh\n"
        ),
        "specializations": [
            {
                "original_selectors": [
                    "[n4d_group_id]",
                    "[n4d_local_slice_id]",
                    "[mse]",
                    "[rd]",
                    "[buf_id]",
                    "[nse]",
                    "[sa_in]",
                    "[sa_out]",
                    "[sa_buf]",
                    "[req]",
                ],
                "specialization": "[0]",
                "reason": (
                    "Icarus rejects runtime selectors on multidimensional "
                    "packed arrays; package macros specialize the focused "
                    "harness to the retained c0 slice only"
                ),
                "impact_boundary": (
                    "selector values only; exact package-local declarations, "
                    "assignments, resets, qualified updates and consumer "
                    "identifiers remain in the parsed source"
                ),
            }
        ],
        "closure": closure,
        "closure_summary": {
            "scope": closure["scope"],
            "declared": closure["actual_consumer_count"],
            "used": closure["actual_consumer_count"],
            "unresolved": 0 if closure["valid"] else 1,
            "ownerless_state": closure["ownerless_state"],
        },
        "positive_compile": positive,
        "scope_positive": scope_positive,
        "negative_compile_missing_counter": missing_counter,
        "negative_compile_typo_consumer": typo_consumer,
        "actual_consumer_class_negative_controls": class_mutations,
        "negative_controls": negative_controls,
        "claim_boundary": (
            "focused Icarus elaboration of exact package-local observer "
            "bytes with external DUT hierarchy/type/macro stubs; production "
            "VCS full-design compile remains pending server return"
        ),
        "pass": (
            version["exit_code"] == 0
            and positive["exit_code"] == 0
            and scope_positive["valid"]
            and closure["valid"]
            and all(negative_controls.values())
        ),
    }


def runtime_controls(package: Path) -> dict[str, Any]:
    positive_preflight = runtime.preflight(package)
    with tempfile.TemporaryDirectory(prefix="n4-p5-runtime-") as name:
        temporary = Path(name)
        mutation = temporary / INSTALL_NAME
        shutil.copytree(package, mutation)
        removed = (
            mutation
            / "workload/runtime/runs/c0/install/execplan_op_w0.txt"
        )
        removed.unlink()
        missing_member_failed = False
        try:
            runtime.preflight(mutation)
        except runtime.RuntimeErrorContract:
            missing_member_failed = True

        fake_leaf_root = temporary / "leaves"
        fake_leaf_root.mkdir()
        compile_lines: list[str] = []
        for basename in runtime.EXPECTED_LEAVES:
            leaf = fake_leaf_root / basename
            leaf.write_bytes(b"wrong identity\n")
            compile_lines.append(f"Parsing design file '{leaf}'")
        compile_log = temporary / "compile.log"
        compile_log.write_text(
            "\n".join(compile_lines) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        identity_mismatch_failed = False
        identity_output = temporary / "identity.json"
        try:
            runtime.collect_compile_identity(compile_log, identity_output)
        except runtime.RuntimeErrorContract:
            identity_mismatch_failed = True

        sim_log = temporary / "sim.log"
        observer_log = temporary / "observer.log"
        natural_output = temporary / "natural.json"
        sim_log.write_text(
            f"{runtime.FEATURE_MARKER}\n{runtime.NATURAL_MARKER}\n",
            encoding="utf-8",
            newline="\n",
        )
        observer_log.write_text(
            f"{runtime.FEATURE_MARKER}\n"
            f"{runtime.CANONICAL_MARKER} "
            "schema=n4d-canonical-v1 decision=SLICE_FINISH "
            "reason=qualified_slice_finish "
            "boundary=c0_exec_to_slice_finish "
            "sample_start=0 sample_end=1 delta=1 total=1\n",
            encoding="utf-8",
            newline="\n",
        )
        natural_positive = runtime.qualify_run(
            sim_log, observer_log, natural_output
        )
        observer_log.write_text(
            f"{runtime.FEATURE_MARKER}\n"
            f"{runtime.CANONICAL_MARKER} "
            "schema=n4d-canonical-v1 decision=HEARTBEAT "
            "reason=qualified_snapshot "
            "boundary=c0_exec_to_slice_finish "
            "sample_start=0 sample_end=1 delta=1 total=1\n",
            encoding="utf-8",
            newline="\n",
        )
        missing_finish_failed = False
        try:
            runtime.qualify_run(sim_log, observer_log, natural_output)
        except runtime.RuntimeErrorContract:
            missing_finish_failed = True

        long_server = Path("C:/" + "x" * 241)
        path_budget_failed = False
        try:
            runtime.path_budget(package, long_server)
        except runtime.RuntimeErrorContract:
            path_budget_failed = True

        def refresh_exact_set(root: Path) -> None:
            manifest_path = root / "package_manifest.json"
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            manifest["files"] = numeric_base.package_records(root)
            write_json(manifest_path, manifest)

        deep = temporary / "deep_path"
        shutil.copytree(package, deep)
        deep_member = deep / (("d" * 140) + ".txt")
        deep_member.parent.mkdir(parents=True, exist_ok=True)
        deep_member.write_text("negative\n", encoding="utf-8")
        refresh_exact_set(deep)
        deep_path_failed = False
        try:
            runtime.preflight(deep)
        except runtime.RuntimeErrorContract:
            deep_path_failed = True

        repeated = temporary / "repeated_identity"
        shutil.copytree(package, repeated)
        repeated_member = (
            repeated / "workload/runtime" / INSTALL_NAME / "member.txt"
        )
        repeated_member.parent.mkdir(parents=True)
        repeated_member.write_text("negative\n", encoding="utf-8")
        refresh_exact_set(repeated)
        repeated_identity_failed = False
        try:
            runtime.preflight(repeated)
        except runtime.RuntimeErrorContract:
            repeated_identity_failed = True

        stale_consumer = temporary / "stale_consumer"
        shutil.copytree(package, stale_consumer)
        source = (
            stale_consumer
            / "workload/runtime/runs/c0/install/op_w0/slice00/"
            "matrix_A_linearized_128bit.txt"
        )
        source.rename(source.with_name("matrix_A_short.txt"))
        refresh_exact_set(stale_consumer)
        stale_consumer_failed = False
        try:
            runtime.preflight(stale_consumer)
        except runtime.RuntimeErrorContract:
            stale_consumer_failed = True
    controls = {
        "missing_exact_member_fails_preflight": missing_member_failed,
        "wrong_actual_compile_bytes_fail_identity": identity_mismatch_failed,
        "missing_slice_finish_fails_natural": missing_finish_failed,
        "overlong_server_root_fails_path_budget": path_budget_failed,
        "added_overbudget_deep_member_fails": deep_path_failed,
        "inner_repeated_full_identity_fails":
            repeated_identity_failed,
        "renamed_member_with_stale_consumer_fails":
            stale_consumer_failed,
    }
    return {
        "valid": (
            positive_preflight.get("valid") is True
            and natural_positive.get("valid") is True
            and all(controls.values())
        ),
        "positive_preflight": positive_preflight,
        "positive_natural_control": natural_positive,
        "negative_controls": controls,
    }


def runner_controls(package: Path) -> dict[str, Any]:
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    checks = {
        "preflight_before_namespace_creation": (
            runner.index("package_preflight_json=")
            < runner.index('mkdir -p "$cfg_root"')
        ),
        "one_actual_compile": runner.count(
            "make -f Makefile.tb_NDP_Top_new_phy compile"
        )
        == 2,
        "observer_macro_and_incdir_bound": (
            runner.count("+define+NATIVE_RETURN_OBSERVER_ENABLE") == 2
            and runner.count("+incdir+$package_root/tb_probe") == 2
        ),
        "post_compile_identity_before_sim": (
            runner.index('python3 "$runtime" compile-identity')
            < runner.index('simv="$run_root/compile/sim_results/simv"')
        ),
        "c0_only": (
            '"$run_root/c0"' in runner
            and "/c1" not in runner
            and "/c2" not in runner
        ),
        "one_hour_run_timeout": (
            "timeout --foreground --signal=TERM --kill-after=30s 1h" in runner
        ),
        "analysis_and_collection_in_exit_trap": (
            'python3 "$runtime" analyze' in runner
            and 'python3 "$runtime" collect' in runner
            and "trap 'finalize $?' EXIT" in runner
        ),
        "no_server_source_preflight": (
            "git " not in runner
            and "sha256sum" not in runner
            and "NDP_rtl" not in runner
        ),
        "no_functional_rtl_write": all(
            token not in runner
            for token in ("sed -i", "patch ", "git checkout", "cp *rtl")
        ),
    }
    return {"valid": all(checks.values()), "checks": checks}


def observer_binding_and_feature_controls(
    package: Path,
) -> dict[str, Any]:
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    observer_path = package / "tb_probe/native_return_observer.svh"
    observer = observer_path.read_text(encoding="utf-8")
    manifest = json.loads(
        (package / "package_manifest.json").read_text(encoding="utf-8")
    )

    def binding_contract(
        runner_text: str,
        observer_present: bool,
        manifest_value: dict[str, Any],
    ) -> bool:
        binding = manifest_value.get("observer_binding", {})
        allowlist = manifest_value.get("return_allowlist", [])
        targets = {
            item.get("target_path")
            for item in allowlist
            if isinstance(item, dict)
        }
        return all(
            (
                observer_present,
                binding.get("source")
                == "tb_probe/native_return_observer.svh",
                binding.get("source_sha256") == sha256(observer_path),
                runner_text.count(
                    "+incdir+$package_root/tb_probe"
                )
                == 2,
                runner_text.count(
                    "+define+NATIVE_RETURN_OBSERVER_ENABLE"
                )
                == 2,
                runner_text.count("+RETURN_OBSERVER") == 2,
                "runs/c0/return_observer.log" in targets,
                "evidence/compile_argv.txt" in targets,
                "runs/c0/simulator_argv.txt" in targets,
                "trap 'finalize $?' EXIT" in runner_text,
                "trap 'on_signal HUP 129' HUP" in runner_text,
                "trap 'on_signal INT 130' INT" in runner_text,
                "trap 'on_signal TERM 143' TERM" in runner_text,
            )
        )

    binding_positive = binding_contract(runner, True, manifest)
    missing_return = json.loads(json.dumps(manifest))
    missing_return["return_allowlist"] = [
        item
        for item in missing_return["return_allowlist"]
        if item["target_path"] != "runs/c0/return_observer.log"
    ]
    binding_negatives = {
        "source_removed_fails": not binding_contract(
            runner, False, manifest
        ),
        "incdir_removed_fails": not binding_contract(
            runner.replace("+incdir+$package_root/tb_probe", ""),
            True,
            manifest,
        ),
        "compile_enable_removed_fails": not binding_contract(
            runner.replace(
                "+define+NATIVE_RETURN_OBSERVER_ENABLE", ""
            ),
            True,
            manifest,
        ),
        "runtime_return_binding_removed_fails": not binding_contract(
            runner, True, missing_return
        ),
    }

    def feature_contract(
        runner_text: str,
        observer_text: str,
        manifest_value: dict[str, Any],
    ) -> bool:
        features = manifest_value.get("diagnostic_features")
        if not isinstance(features, list) or len(features) != 1:
            return False
        feature = features[0]
        targets = {
            item.get("target_path")
            for item in manifest_value.get("return_allowlist", [])
            if isinstance(item, dict)
        }
        marker = runtime.FEATURE_MARKER
        return all(
            (
                feature.get("feature") == "NATIVE4_C0_BOUNDARY",
                feature.get("runtime_enable")
                == "+N4D_C0_BOUNDARY_DIAG",
                feature.get("limit_parameters")
                == {
                    "heartbeat_cycles": 262144,
                    "stall_cycles": 1048576,
                    "slice": 0,
                },
                feature.get("time0_marker") == marker,
                runner_text.count("+N4D_C0_BOUNDARY_DIAG") == 2,
                runner_text.count(
                    "+RETURN_OBS_HEARTBEAT_CYCLES=262144"
                )
                == 2,
                runner_text.count(
                    "+RETURN_OBS_STALL_CYCLES=1048576"
                )
                == 2,
                "N4D_FEATURE_ENABLE_V2 "
                "feature=NATIVE4_C0_BOUNDARY enabled=1 "
                "heartbeat_cycles=%0d stall_cycles=%0d slice=%0d"
                in observer_text,
                "evidence/feature_binding/c0.json" in targets,
                'python3 "$runtime" feature-binding' in runner_text,
            )
        )

    feature_positive = feature_contract(runner, observer, manifest)
    feature_missing_return = json.loads(json.dumps(manifest))
    feature_missing_return["return_allowlist"] = [
        item
        for item in feature_missing_return["return_allowlist"]
        if item["target_path"] != "evidence/feature_binding/c0.json"
    ]
    feature_negatives = {
        "feature_enable_removed_fails": not feature_contract(
            runner.replace("+N4D_C0_BOUNDARY_DIAG", ""),
            observer,
            manifest,
        ),
        "feature_limit_removed_fails": not feature_contract(
            runner.replace(
                "+RETURN_OBS_STALL_CYCLES=1048576", ""
            ),
            observer,
            manifest,
        ),
        "time0_marker_removed_fails": not feature_contract(
            runner,
            observer.replace("N4D_FEATURE_ENABLE_V2", "N4D_MARKER_REMOVED"),
            manifest,
        ),
        "feature_return_removed_fails": not feature_contract(
            runner, observer, feature_missing_return
        ),
    }
    return {
        "valid": (
            binding_positive
            and all(binding_negatives.values())
            and feature_positive
            and all(feature_negatives.values())
        ),
        "observer_binding_four_way": {
            "valid": binding_positive,
            "negative_controls": binding_negatives,
        },
        "diagnostic_feature_end_to_end": {
            "valid": feature_positive,
            "negative_controls": feature_negatives,
        },
    }


def canonical_decision_controls(package: Path) -> dict[str, Any]:
    observer = (
        package / "tb_probe/native_return_observer.svh"
    ).read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="n4-p5-canonical-") as name:
        root = Path(name)
        sim = root / "sim.log"
        obs = root / "observer.log"
        output = root / "receipt.json"
        sim.write_text(
            f"{runtime.FEATURE_MARKER}\n{runtime.NATURAL_MARKER}\n",
            encoding="utf-8",
            newline="\n",
        )
        canonical = (
            f"{runtime.CANONICAL_MARKER} "
            "schema=n4d-canonical-v1 decision=SLICE_FINISH "
            "reason=qualified_slice_finish "
            "boundary=c0_exec_to_slice_finish "
            "sample_start=0 sample_end=10 delta=1 total=1"
        )

        def rejected(lines: list[str]) -> bool:
            obs.write_text(
                runtime.FEATURE_MARKER
                + "\n"
                + "\n".join(lines)
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            try:
                runtime.qualify_run(sim, obs, output)
            except runtime.RuntimeErrorContract:
                return True
            return False

        positive_obs = (
            runtime.FEATURE_MARKER
            + "\nN4D_PROGRESS_V1 schema=n4d-canonical-v1 "
            "decision=HEARTBEAT reason=qualified_snapshot "
            "boundary=c0_exec_to_slice_finish sample_start=0 "
            "sample_end=5 delta=1 total=1\n"
            + canonical
            + "\nN4D_SUMMARY_V1 decision_already_emitted=1 total=1\n"
        )
        obs.write_text(
            positive_obs, encoding="utf-8", newline="\n"
        )
        positive = runtime.qualify_run(sim, obs, output)
        high_level_mutation = observer.replace(
            "else if (n4d_enabled && n4d_active) begin",
            "else if (n4d_enabled && n4d_active) begin\n"
            "        if (n4d_rd_queue_full_mon[0][0][0]) "
            "n4d_sg_total++;",
            1,
        )
        negatives = {
            "sustained_raw_level_as_progress_fails": not observer_scope(
                high_level_mutation
            )["valid"],
            "summary_reusing_canonical_prefix_fails": rejected(
                [
                    canonical,
                    f"{runtime.CANONICAL_MARKER} "
                    "schema=n4d-canonical-v1 decision=SUMMARY "
                    "reason=summary boundary=c0_exec_to_slice_finish "
                    "sample_start=10 sample_end=10 delta=0 total=1",
                ]
            ),
            "two_conflicting_canonical_records_fail": rejected(
                [
                    canonical,
                    canonical.replace(
                        "decision=SLICE_FINISH",
                        "decision=INCOMPLETE_AT_SIMULATOR_END",
                    ),
                ]
            ),
            "missing_reason_fails": rejected(
                [canonical.replace("reason=qualified_slice_finish ", "")]
            ),
            "missing_boundary_fails": rejected(
                [
                    canonical.replace(
                        "boundary=c0_exec_to_slice_finish ", ""
                    )
                ]
            ),
        }
    return {
        "valid": positive.get("valid") is True and all(negatives.values()),
        "positive": positive,
        "negative_controls": negatives,
        "observer_prefixes": {
            "canonical": "N4D_CANONICAL_V1",
            "progress": "N4D_PROGRESS_V1",
            "summary": "N4D_SUMMARY_V1",
        },
    }


def return_allowlist_controls(package: Path) -> dict[str, Any]:
    manifest = json.loads(
        (package / "package_manifest.json").read_text(encoding="utf-8")
    )
    declarations = manifest.get("return_allowlist", [])
    targets = [
        item.get("target_path")
        for item in declarations
        if isinstance(item, dict)
    ]
    forbidden = (
        "simv.daidir",
        "csrc",
        "wave",
        ".vcd",
        ".fsdb",
        ".zip",
        "simv",
    )
    checks = {
        "manifest_declares_nonempty_allowlist": bool(declarations),
        "targets_unique": len(targets) == len(set(targets)),
        "every_entry_has_source_target_required_budget_semantics": all(
            isinstance(item, dict)
            and item.get("source_root") in {"evidence", "run", "package"}
            and isinstance(item.get("source_path"), str)
            and isinstance(item.get("target_path"), str)
            and isinstance(item.get("required"), bool)
            and isinstance(item.get("max_bytes"), int)
            and item["max_bytes"] > 0
            and isinstance(item.get("missing_semantics"), str)
            and bool(item["missing_semantics"])
            for item in declarations
        ),
        "forbidden_targets_absent": all(
            not any(token in str(target) for token in forbidden)
            for target in targets
        ),
        "collector_consumes_manifest_allowlist": (
            'manifest.get("return_allowlist")'
            in (
                package
                / "package_tools/node0004_assumed_hardware_server_runtime.py"
            ).read_text(encoding="utf-8")
        ),
        "diagnostic_budget_16mib_32mib": manifest.get(
            "return_budget"
        )
        == {
            "zip_max_bytes": 16 * 1024 * 1024,
            "uncompressed_max_bytes": 32 * 1024 * 1024,
            "single_text_max_bytes": 8 * 1024 * 1024,
        },
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "declaration_count": len(declarations),
        "targets": targets,
    }


def runner_end_to_end_controls(
    package_zip: Path,
) -> dict[str, Any]:
    git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    python_exe = ROOT / ".venv/Scripts/python.exe"

    def posix(path: Path) -> str:
        value = path.resolve().as_posix()
        if len(value) >= 3 and value[1:3] == ":/":
            return f"/{value[0].lower()}{value[2:]}"
        return value

    with tempfile.TemporaryDirectory(
        prefix="n4-p5-runner-", dir=ROOT / "outputs"
    ) as name:
        root = Path(name)
        extract = root / "extract"
        extract.mkdir()
        with zipfile.ZipFile(package_zip) as archive:
            archive.extractall(extract)
        package = extract / INSTALL_NAME
        package_before = numeric_base.package_records(
            package, exclude_manifest=False
        )
        stub_bin = root / "stub_bin"
        stub_bin.mkdir()
        leaf_root = root / "leaves"
        leaf_root.mkdir()
        safe = str(RTL_REPO.resolve()).replace("\\", "/")
        for basename, relative in GIT_PATHS.items():
            result = run(
                [
                    "git",
                    "-c",
                    f"safe.directory={safe}",
                    "-C",
                    str(RTL_REPO),
                    "show",
                    f"{runtime.EXPECTED_COMMIT}:{relative}",
                ],
                ROOT,
                binary=True,
            )
            if result["exit_code"] != 0:
                raise RuntimeError(
                    f"cannot materialize runner stub leaf: {basename}"
                )
            (leaf_root / basename).write_bytes(result["stdout"])
        python_wrapper = stub_bin / "python3"
        python_wrapper.write_text(
            "#!/usr/bin/env bash\n"
            f'exec "{posix(python_exe)}" "$@"\n',
            encoding="utf-8",
            newline="\n",
        )
        make_stub = stub_bin / "make"
        make_stub.write_text(
            r"""#!/usr/bin/env bash
set -u
run_dir=
for arg in "$@"; do
  case "$arg" in RUN_DIR=*) run_dir="${arg#RUN_DIR=}";; esac
done
[ -n "$run_dir" ] || exit 91
mkdir -p "$run_dir/sim_results"
printf 'compile_reached\n' > "$N4D_STUB_STATE/compile_reached"
for leaf in "$N4D_STUB_LEAF_ROOT"/*; do
  printf "Parsing design file '%s'\n" "$(cygpath -m "$leaf")"
done
simv="$run_dir/sim_results/simv"
cat > "$simv" <<'SIMV'
#!/usr/bin/env bash
set -u
sim_log=
observer_log=
previous=
for arg in "$@"; do
  if [ "$previous" = "-l" ]; then sim_log="$arg"; fi
  case "$arg" in +RETURN_OBS_FILE=*) observer_log="${arg#*=}";; esac
  previous="$arg"
done
[ -n "$sim_log" ] || exit 92
[ -n "$observer_log" ] || exit 93
mkdir -p "$(dirname "$sim_log")" "$(dirname "$observer_log")"
marker='N4D_FEATURE_ENABLE_V2 feature=NATIVE4_C0_BOUNDARY enabled=1 heartbeat_cycles=262144 stall_cycles=1048576 slice=0'
printf '%s\n' "$marker" > "$observer_log"
printf '%s\n' 'N4D_PROGRESS_V1 schema=n4d-canonical-v1 decision=HEARTBEAT reason=qualified_snapshot boundary=c0_exec_to_slice_finish sample_start=0 sample_end=5 delta=1 total=1' >> "$observer_log"
printf '%s\n' 'N4D_CANONICAL_V1 schema=n4d-canonical-v1 decision=SLICE_FINISH reason=qualified_slice_finish boundary=c0_exec_to_slice_finish sample_start=0 sample_end=10 delta=1 total=1' >> "$observer_log"
printf '%s\n' 'N4D_SUMMARY_V1 decision_already_emitted=1 total=1' >> "$observer_log"
printf '%s\n' "$marker" > "$sim_log"
printf '%s\n' '$finish at simulation time' >> "$sim_log"
printf 'sim_reached\n' > "$N4D_STUB_STATE/sim_reached"
if [ "${N4D_STUB_MODE:-natural}" = "signal" ]; then
  while :; do sleep 1; done
fi
exit 0
SIMV
chmod +x "$simv"
exit 0
""",
            encoding="utf-8",
            newline="\n",
        )
        os.chmod(python_wrapper, 0o755)
        os.chmod(make_stub, 0o755)
        state = root / "state"
        state.mkdir()
        environment = os.environ.copy()
        environment.update(
            {
                "PATH": (
                    str(stub_bin)
                    + os.pathsep
                    + r"C:\Program Files\Git\usr\bin"
                    + os.pathsep
                    + r"C:\Program Files\Git\bin"
                    + os.pathsep
                    + environment.get("PATH", "")
                ),
                "N4D_STUB_LEAF_ROOT": posix(leaf_root),
                "N4D_STUB_STATE": posix(state),
                "N4D_STUB_MODE": "natural",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        natural_server = root / "server_natural"
        natural_server.mkdir()
        natural = subprocess.run(
            [
                str(git_bash),
                posix(package / "PREPARE_AND_RUN.sh"),
                posix(natural_server),
            ],
            cwd=package,
            env=environment,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=60,
            check=False,
        )
        natural_return = (
            natural_server / f"{INSTALL_NAME}_return.zip"
        )
        natural_sidecar = Path(str(natural_return) + ".sha256")
        natural_return_valid = False
        natural_return_records: dict[str, Any] = {}
        if natural_return.is_file():
            audit = safe_zip_records(
                natural_return, f"{INSTALL_NAME}_return"
            )
            natural_return_valid = audit["valid"]
            natural_return_records = audit["records"]
        package_after = numeric_base.package_records(
            package, exclude_manifest=False
        )

        signal_state = root / "signal_state"
        signal_state.mkdir()
        signal_server = root / "server_signal"
        signal_server.mkdir()
        signal_environment = environment.copy()
        signal_environment["N4D_STUB_STATE"] = posix(signal_state)
        signal_environment["N4D_STUB_MODE"] = "signal"
        signal_stdout = root / "signal_stdout.txt"
        signal_stderr = root / "signal_stderr.txt"
        signal_status = root / "signal_wrapper_status.txt"
        signal_wrapper = root / "run_signal.sh"
        signal_wrapper.write_text(
            "#!/usr/bin/env bash\n"
            "set +e\n"
            f'( source "{posix(package / "PREPARE_AND_RUN.sh")}" '
            f'"{posix(signal_server)}" ) '
            f'>"{posix(signal_stdout)}" '
            f'2>"{posix(signal_stderr)}" &\n'
            "runner_pid=$!\n"
            "for attempt in $(seq 1 100); do\n"
            f'  [ ! -f "{posix(signal_state / "sim_reached")}" ] '
            "|| break\n"
            "  sleep 0.1\n"
            "done\n"
            "sleep 1\n"
            'kill -TERM "$runner_pid"\n'
            'wait "$runner_pid"\n'
            "status=$?\n"
            f'printf "%s\\n" "$status" > "{posix(signal_status)}"\n'
            "exit 0\n",
            encoding="utf-8",
            newline="\n",
        )
        signal_run = subprocess.run(
            [str(git_bash), posix(signal_wrapper)],
            cwd=root,
            env=signal_environment,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=60,
            check=False,
        )
        signal_return = signal_server / f"{INSTALL_NAME}_return.zip"
        signal_stderr_text = (
            signal_stderr.read_text(
                encoding="utf-8", errors="replace"
            )
            if signal_stderr.is_file()
            else ""
        )
        signal_return_valid = False
        signal_status_value = None
        if signal_return.is_file():
            signal_return_valid = safe_zip_records(
                signal_return, f"{INSTALL_NAME}_return"
            )["valid"]
        if signal_status.is_file():
            signal_status_value = signal_status.read_text(
                encoding="ascii"
            ).strip()

        negative_extract = root / "negative_extract"
        negative_extract.mkdir()
        with zipfile.ZipFile(package_zip) as archive:
            archive.extractall(negative_extract)
        negative_package = negative_extract / INSTALL_NAME
        negative_manifest_path = (
            negative_package / "package_manifest.json"
        )
        negative_manifest = json.loads(
            negative_manifest_path.read_text(encoding="utf-8")
        )
        negative_manifest["observer_binding"]["source_sha256"] = "0" * 64
        write_json(negative_manifest_path, negative_manifest)
        negative_state = root / "negative_state"
        negative_state.mkdir()
        negative_server = root / "server_negative"
        negative_server.mkdir()
        negative_environment = environment.copy()
        negative_environment["N4D_STUB_STATE"] = posix(negative_state)
        wrong_identity = subprocess.run(
            [
                str(git_bash),
                posix(negative_package / "PREPARE_AND_RUN.sh"),
                posix(negative_server),
            ],
            cwd=negative_package,
            env=negative_environment,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=60,
            check=False,
        )
        natural_compile_reached = (
            state / "compile_reached"
        ).is_file()
        natural_sim_reached = (state / "sim_reached").is_file()
        bootstrap_artifacts_absent = not any(
            path.name == "__pycache__" or path.suffix == ".pyc"
            for path in package.rglob("*")
        )
        negative_compile_reached = (
            negative_state / "compile_reached"
        ).exists()
        natural_return_sha = (
            sha256(natural_return)
            if natural_return.is_file()
            else None
        )
        natural_sidecar_valid = (
            natural_sidecar.is_file()
            and natural_return_sha is not None
            and natural_sidecar.read_text(encoding="ascii")
            == f"{natural_return_sha}  {natural_return.name}\n"
        )
        signal_return_sha = (
            sha256(signal_return)
            if signal_return.is_file()
            else None
        )

    checks = {
        "natural_runner_exit_zero": natural.returncode == 0,
        "natural_reaches_compile_once": natural_compile_reached,
        "natural_reaches_simulator": natural_sim_reached,
        "natural_finalizer_return_exact": natural_return_valid,
        "natural_return_sidecar_exact": natural_sidecar_valid,
        "natural_return_has_all_finalizer_receipts": all(
            target in natural_return_records
            for target in (
                "evidence/compile_exit_status.txt",
                "evidence/run_exit_status.txt",
                "evidence/signal_status.txt",
                "evidence/SERVER_RESULT_GATE.json",
                "evidence/feature_binding/c0.json",
                "evidence/natural_terminal/c0.json",
                "source_package/package_manifest.json",
                "RETURN_MANIFEST.json",
                "RETURN_ALLOWLIST.json",
            )
        ),
        "bootstrap_package_tree_immutable": package_before == package_after,
        "no_python_bootstrap_artifacts": bootstrap_artifacts_absent,
        "natural_stderr_has_no_shell_diagnostic": not any(
            token in natural.stderr
            for token in ("unbound variable", "command not found")
        ),
        "signal_wrapper_completed": signal_run.returncode == 0,
        "signal_runner_exit_143": signal_status_value == "143",
        "signal_finalizer_return_exact": signal_return_valid,
        "signal_stderr_has_no_shell_diagnostic": not any(
            token in signal_stderr_text
            for token in ("unbound variable", "command not found")
        ),
        "wrong_observer_sha_fails_before_compile": (
            wrong_identity.returncode != 0
            and not negative_compile_reached
        ),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "natural": {
            "exit_code": natural.returncode,
            "stdout_sha256": digest(natural.stdout.encode()),
            "stderr": natural.stderr,
            "return_zip_sha256": (
                natural_return_sha
            ),
        },
        "signal": {
            "wrapper_exit_code": signal_run.returncode,
            "runner_exit_code": signal_status_value,
            "stderr": signal_stderr_text,
            "return_zip_sha256": (
                signal_return_sha
            ),
        },
        "negative_wrong_observer_sha": {
            "exit_code": wrong_identity.returncode,
            "compile_reached": (
                negative_compile_reached
            ),
            "stderr": wrong_identity.stderr,
        },
        "claim_boundary": (
            "safe local make/simv stubs prove the exact final runner reaches "
            "compile/simulation/finalizer/allowlist return without invoking "
            "production VCS or DUT simulation"
        ),
    }


def deterministic_zip_replay(package: Path, package_zip: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="n4-p5-rezip-") as name:
        replay = Path(name) / package_zip.name
        build.deterministic_zip(package, replay)
        replay_sha = sha256(replay)
        replay_bytes = replay.stat().st_size
    return {
        "valid": (
            replay_sha == sha256(package_zip)
            and replay_bytes == package_zip.stat().st_size
        ),
        "replay_sha256": replay_sha,
        "source_sha256": sha256(package_zip),
        "replay_bytes": replay_bytes,
        "source_bytes": package_zip.stat().st_size,
    }


def main() -> int:
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=PACKAGE_ROOT)
    parser.add_argument("--zip", type=Path, default=PACKAGE_ZIP)
    parser.add_argument("--iverilog", type=Path, default=IVERILOG)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    package = args.package_root.resolve()
    package_zip = args.zip.resolve()
    errors: list[str] = []

    zip_audit = safe_zip_records(package_zip, INSTALL_NAME)
    package_records = numeric_base.package_records(
        package, exclude_manifest=False
    )
    zip_matches_directory = zip_audit["records"] == package_records
    audit_temp = tempfile.TemporaryDirectory(prefix="n4-p5-final-extract-")
    audit_extract = Path(audit_temp.name)
    with zipfile.ZipFile(package_zip) as archive:
        archive.extractall(audit_extract)
    audited_package = audit_extract / INSTALL_NAME
    manifest = json.loads(
        (audited_package / "package_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    manifest_checks = {
        "status_ready_not_run": (
            manifest.get("status") == "PACKAGE_READY_NOT_RUN"
        ),
        "diagnostic_class": (
            manifest.get("candidate_class")
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
        ),
        "candidate_release_false": (
            manifest.get("candidate_release") is False
        ),
        "one_c0_run": manifest.get("conv_run_ids") == ["c0"],
        "no_tail_runs": manifest.get("tail_run_ids") == [],
        "no_formal_readbacks": (
            manifest.get("formal_readback_count") == 0
            and manifest.get("readback_checks") == []
        ),
        "no_functional_rtl": (
            manifest.get("functional_rtl_file_count") == 0
            and manifest.get("functional_rtl_modified") is False
        ),
        "historical_return_analysis_bound": (
            manifest.get("source_return_analysis", {}).get("sha256")
            == build.RETURN_ANALYSIS_SHA256
        ),
        "source_p4_and_v1_bound": (
            manifest.get("delivery_and_workload_provenance", {}).get(
                "source_p4_zip_sha256"
            )
            == build.SOURCE_P4_SHA256
            and manifest.get("delivery_and_workload_provenance", {}).get(
                "source_v1_zip_sha256"
            )
            == build.SOURCE_V1_SHA256
        ),
    }
    checks: dict[str, Any] = {
        "source_p4_sha256_exact": (
            sha256(SOURCE_P4_ZIP) == SOURCE_P4_SHA256
        ),
        "safe_final_zip": zip_audit["valid"],
        "zip_matches_persisted_package_directory": zip_matches_directory,
        "manifest_files_exact": (
            manifest.get("files")
            == numeric_base.package_records(audited_package)
        ),
        "manifest_gate": all(manifest_checks.values()),
    }
    p4_relation = p4_c0_relation(audited_package)
    closure = consumer_closure(audited_package)
    git_identity = immutable_git_identity()
    observer_path = (
        audited_package / "tb_probe/native_return_observer.svh"
    )
    observer = observer_path.read_text(encoding="utf-8")
    observer_hdl = compile_observer_cases(
        observer, args.iverilog.resolve()
    )
    runtime_gate = runtime_controls(audited_package)
    runner_gate = runner_controls(audited_package)
    binding_feature = observer_binding_and_feature_controls(
        audited_package
    )
    canonical_gate = canonical_decision_controls(audited_package)
    allowlist_gate = return_allowlist_controls(audited_package)
    runner_end_to_end = runner_end_to_end_controls(package_zip)
    reproducibility = deterministic_zip_replay(package, package_zip)
    checks.update(
        {
            "p4_c0_content_neutral_relation": p4_relation["valid"],
            "consumer_closure": closure["valid"],
            "immutable_e1fb0f7_git_leaf_identity": git_identity["valid"],
            "focused_observer_hdl_syntax_scope": observer_hdl["valid"],
            "runtime_positive_and_negative_controls": runtime_gate["valid"],
            "runner_chain_controls": runner_gate["valid"],
            "observer_binding_and_feature_controls":
                binding_feature["valid"],
            "canonical_decision_controls": canonical_gate["valid"],
            "manifest_bound_return_allowlist":
                allowlist_gate["valid"],
            "runner_end_to_end_safe_stub_controls":
                runner_end_to_end["valid"],
            "deterministic_zip_replay": reproducibility["valid"],
        }
    )
    errors = [name for name, value in checks.items() if not value]
    sidecar = Path(str(package_zip) + ".sha256")
    sidecar_expected = f"{sha256(package_zip)}  {package_zip.name}\n"
    sidecar_valid = (
        sidecar.is_file()
        and sidecar.read_text(encoding="ascii") == sidecar_expected
    )
    checks["sidecar_exact"] = sidecar_valid
    if not sidecar_valid:
        errors.append("sidecar_exact")
    valid = not errors
    result = {
        "schema": (
            "conv-native-four-lane-e1fb0f7-c0diag-final-zip-audit-v1"
        ),
        "status": "PACKAGE_READY_NOT_RUN" if valid else "FAIL",
        "valid": valid,
        "errors": errors,
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "package": str(package),
        "zip": str(package_zip),
        "zip_bytes": package_zip.stat().st_size,
        "zip_sha256": sha256(package_zip),
        "sidecar": str(sidecar),
        "sidecar_sha256": sha256(sidecar) if sidecar.is_file() else None,
        "checks": checks,
        "manifest_checks": manifest_checks,
        "zip_audit": {
            key: value
            for key, value in zip_audit.items()
            if key != "records"
        },
        "p4_c0_relation": p4_relation,
        "consumer_closure": closure,
        "immutable_git_identity": git_identity,
        "observer_hdl": observer_hdl,
        "runtime_controls": runtime_gate,
        "runner_controls": runner_gate,
        "observer_binding_and_feature_controls": binding_feature,
        "canonical_decision_controls": canonical_gate,
        "return_allowlist_controls": allowlist_gate,
        "runner_end_to_end_controls": runner_end_to_end,
        "reproducibility": reproducibility,
        "final_zip_rule_self_audit": {
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
            "current_match": True,
            "rule_receipts": manifest.get("rule_receipts"),
            "current_server_package_rule_sha256": (
                "5f1369c4af431baaf74044a004a3383860a9d279561712616"
                "fb19e745465c7f9"
            ),
            "current_plan_mutable_provenance_sha256": sha256(
                ROOT / ".agents/plan.md"
            ),
            "fresh_extract_root": str(audited_package),
            "independent_validator": str(Path(__file__).resolve()),
            "independent_validator_sha256": sha256(Path(__file__)),
        },
        "claim_boundary": {
            "server_action": False,
            "actual_production_compile_receipt": "PENDING_SERVER_RETURN",
            "natural_terminal": "PENDING_SERVER_RETURN",
            "formal_D": "NOT_INCLUDED_DIAGNOSTIC_ONLY",
            "E3_claimed": False,
            "E4_claimed": False,
            "E5_claimed": False,
        },
    }
    write_json(args.output.resolve(), result)
    audit_temp.cleanup()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
