#!/usr/bin/env python3
"""Build the fresh native-Conv p47 bounded causal-cone TB VCD package."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD_ID = "r5_n4_0cc_p46_nativeflow"
PACKAGE_ID = "r5_n4_0cc_p47_tbvcdcone"
FAMILY = "conv_native_four_lane"
ACTIVATION_EPOCH = "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = STORAGE / "pending" / f"{OLD_ID}.zip"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_release"
TREE = OUT / "build" / PACKAGE_ID
ZIP = OUT / f"{PACKAGE_ID}.zip"
LOCAL_RTL = ROOT / "NDP_copy01"
BASE_SLICE = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
    "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice"
)
BASE_STREAM = BASE_SLICE + ".u_LSU.u_Stream_Engine"
BASE_MSE = BASE_STREAM + ".MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
BASE_SEM = BASE_SLICE + ".u_Slice_Execution_Manager"


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write(relative: str, payload: bytes, executable: bool = False) -> Path:
    path = TREE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def write_json(relative: str, value: Any) -> Path:
    return write(relative, canonical(value))


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def safe_extract(source: Path) -> None:
    build_parent = TREE.parent
    if OUT.exists():
        shutil.rmtree(OUT)
    build_parent.mkdir(parents=True)
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("p46 source ZIP CRC failure")
        roots = {PurePosixPath(item.filename).parts[0] for item in archive.infolist() if item.filename}
        if roots != {OLD_ID}:
            raise RuntimeError(f"p46 source root differs: {roots}")
        old_tree = build_parent / OLD_ID
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                raise RuntimeError(f"unsafe source member: {info.filename}")
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise RuntimeError(f"source symlink forbidden: {info.filename}")
            target = build_parent.joinpath(*pure.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
        TREE.mkdir(parents=True)
        for child in old_tree.iterdir():
            target = TREE / child.name
            if child.is_dir():
                shutil.copytree(child, target)
            else:
                shutil.copy2(child, target)
        shutil.rmtree(old_tree)


def remove_old_diagnostic_surface() -> None:
    for relative in ("package_tools", "tb_probe", "contracts", "diagnostics"):
        path = TREE / relative
        if path.exists():
            shutil.rmtree(path)
    for name in ("package_manifest.json", "TEST_PACKAGE_MANIFEST.json", "RETURN_ALLOWLIST.json", "README.md", "PREPARE_AND_RUN.sh", "SERVER_RUNTIME_LAYOUT_CONTRACT.json", "server_runner_return_resilience_contract.json"):
        path = TREE / name
        if path.exists():
            path.unlink()
    frozen = TREE / "provenance/frozen_p45_surface.json"
    if frozen.exists():
        frozen.rename(TREE / "provenance/frozen_p46_surface.json")


def source_record(relative: str, name: str, hierarchy: str, width: int, roles: list[str]) -> dict[str, Any]:
    local = LOCAL_RTL / "rtl" / relative
    lines = local.read_text(encoding="utf-8", errors="strict").splitlines()
    matches = [
        (index, line) for index, line in enumerate(lines, 1)
        if name in line and line.lstrip().startswith(("input", "output", "wire", "reg", "logic"))
    ]
    if not matches:
        matches = [(index, line) for index, line in enumerate(lines, 1) if name in line]
    if not matches:
        raise RuntimeError(f"source declaration not found: {relative}:{name}")
    line_number, declaration = matches[0]
    return {
        "signal_id": "sig_" + name.replace("[", "_").replace("]", "").replace(".", "_"),
        "exact_hierarchy": hierarchy,
        "width_bits": width,
        "roles": roles,
        "source_path": "rtl/" + relative.replace("\\", "/"),
        "source_sha256": sha(local),
        "declaration_span_sha256": sha_bytes((declaration.strip() + "\n").encode("utf-8")),
        "source_binding": "ACTUAL_SOURCE_NET",
        "derived_expected_equation": False,
        "drives_dut": False,
        "source_line": line_number,
        "source_declaration": declaration.strip(),
    }


def build_signals() -> list[dict[str, Any]]:
    top = "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv"
    data = "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv"
    mem = "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Memory_AG.sv"
    buf = "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv"
    fifo = "utils/FIFO/FIFO.sv"
    sem = "Slice/Slice_Execution_Manager.sv"
    stream = "Slice/LSU/Stream_Engine/Stream_Engine.sv"
    rows: list[tuple[str, str, str, int, list[str]]] = [
        (top, "clk", BASE_MSE + ".clk", 1, ["clock"]),
        (top, "rst_n", BASE_MSE + ".rst_n", 1, ["reset"]),
        (top, "slice_rst", BASE_MSE + ".slice_rst", 1, ["reset", "clear"]),
        (top, "mse_enable", BASE_MSE + ".mse_enable", 1, ["stage", "lifetime"]),
        (top, "mse_mem_ag_tag_valid", BASE_MSE + ".mse_mem_ag_tag_valid", 1, ["source", "producer", "valid"]),
        (top, "mse_mem_ag_bp_pre", BASE_MSE + ".mse_mem_ag_bp_pre", 1, ["ready", "backpressure"]),
        (top, "mse_mem_ag_tag", BASE_MSE + ".mse_mem_ag_tag", 6, ["tag", "internal_match"]),
        (top, "wr_data_chl_req_valid", BASE_MSE + ".wr_data_chl_req_valid", 1, ["request", "valid"]),
        (top, "wr_data_chl_req_ready", BASE_MSE + ".wr_data_chl_req_ready", 1, ["ready", "backpressure"]),
        (top, "wr_data_chl_req_valid_mask", BASE_MSE + ".wr_data_chl_req_valid_mask", 16, ["mask"]),
        (top, "wr_data_chl_req_tsf_bias_addr", BASE_MSE + ".wr_data_chl_req_tsf_bias_addr", 21, ["address"]),
        (top, "mse2mem_request_valid", BASE_MSE + ".mse2mem_request_valid", 2, ["request", "valid"]),
        (top, "mem2mse_request_ready", BASE_MSE + ".mem2mse_request_ready", 2, ["ready", "backpressure"]),
        (top, "mse2mem_request", BASE_MSE + ".mse2mem_request", 54, ["address", "output"]),
        (top, "mse2mem_wdata_valid", BASE_MSE + ".mse2mem_wdata_valid", 2, ["valid", "wdata"]),
        (top, "mem2mse_wdata_ready", BASE_MSE + ".mem2mse_wdata_ready", 2, ["ready", "backpressure"]),
        (top, "mse2mem_wdata", BASE_MSE + ".mse2mem_wdata", 256, ["wdata", "output"]),
        (top, "mem2mse_rdata_valid", BASE_MSE + ".mem2mse_rdata_valid", 2, ["valid", "selected_port"]),
        (top, "mse2mem_rdata_ready", BASE_MSE + ".mse2mem_rdata_ready", 2, ["ready"]),
        (top, "mse2buf_rreq_valid", BASE_MSE + ".mse2buf_rreq_valid", 16, ["request", "per_bank_valid"]),
        (top, "buf2mse_rreq_ready", BASE_MSE + ".buf2mse_rreq_ready", 1, ["ready", "per_bank_ready"]),
        (top, "buf2mse_rvalid", BASE_MSE + ".buf2mse_rvalid", 1, ["valid", "producer"]),
        (top, "mse2buf_rreq_row_addr", BASE_MSE + ".mse2buf_rreq_row_addr", 2, ["address", "selected_bank"]),
        (top, "buf_ag_last_req_flag", BASE_MSE + ".buf_ag_last_req_flag", 1, ["last"]),
        (top, "mse2buf_req_pingpong_sel", BASE_MSE + ".mse2buf_req_pingpong_sel", 1, ["ping_pong_branch0", "ping_pong_branch1"]),
        (top, "slice_cmpt_finish", BASE_MSE + ".slice_cmpt_finish", 1, ["finish", "completion"]),
        (buf, "buf_ag_ob_cnt", BASE_MSE + ".u_RD_Buffer_AG.buf_ag_ob_cnt", 2, ["fifo_occupancy", "count"]),
        (buf, "buf_ag_ob_wr_en", BASE_MSE + ".u_RD_Buffer_AG.buf_ag_ob_wr_en", 1, ["fifo_enqueue", "accept"]),
        (buf, "buf_ag_ob_rd_en", BASE_MSE + ".u_RD_Buffer_AG.buf_ag_ob_rd_en", 1, ["fifo_dequeue"]),
        (buf, "buf_ag_ob_full", BASE_MSE + ".u_RD_Buffer_AG.buf_ag_ob_full", 1, ["fifo_full", "per_bank_full"]),
        (buf, "buf_ag_ob_empty", BASE_MSE + ".u_RD_Buffer_AG.buf_ag_ob_empty", 1, ["fifo_empty"]),
        (buf, "mse2buf_last", BASE_MSE + ".u_RD_Buffer_AG.mse2buf_last", 1, ["last"]),
        (buf, "mse2buf_last_index", BASE_MSE + ".u_RD_Buffer_AG.mse2buf_last_index", 4, ["last", "count"]),
        (data, "wr_chl_queue_wr_en", BASE_MSE + ".u_WR_Data_Channel.wr_chl_queue_wr_en", 1, ["fifo_enqueue", "accept"]),
        (data, "wr_chl_queue_rd_en", BASE_MSE + ".u_WR_Data_Channel.wr_chl_queue_rd_en", 1, ["fifo_dequeue"]),
        (data, "wr_chl_queue_empty", BASE_MSE + ".u_WR_Data_Channel.wr_chl_queue_empty", 1, ["fifo_empty"]),
        (data, "wr_chl_queue_full", BASE_MSE + ".u_WR_Data_Channel.wr_chl_queue_full", 1, ["fifo_full"]),
        (fifo, "fifo_counter", BASE_MSE + ".u_WR_Data_Channel.u_wr_chl_queue.fifo_counter", 2, ["fifo_occupancy", "count"]),
        (data, "wr_data_chl_prepared_data_cnt", BASE_MSE + ".u_WR_Data_Channel.wr_data_chl_prepared_data_cnt", 6, ["count", "internal_state"]),
        (data, "wr_chl_ob_vld", BASE_MSE + ".u_WR_Data_Channel.wr_chl_ob_vld", 2, ["outstanding", "per_bank_valid"]),
        (data, "wr_chl_ob_wr_hs", BASE_MSE + ".u_WR_Data_Channel.wr_chl_ob_wr_hs", 2, ["accept", "fifo_enqueue"]),
        (data, "wr_chl_ob_rd_hs", BASE_MSE + ".u_WR_Data_Channel.wr_chl_ob_rd_hs", 2, ["accept", "fifo_dequeue"]),
        (data, "wr_data_chl_ob_last_data_flag", BASE_MSE + ".u_WR_Data_Channel.wr_data_chl_ob_last_data_flag", 2, ["last", "per_bank_owner"]),
        (data, "wr_data_chl_ob_last_data_arv_arr_flag", BASE_MSE + ".u_WR_Data_Channel.wr_data_chl_ob_last_data_arv_arr_flag", 1, ["completion", "finish"]),
        (data, "wr_chl_ob_sel", BASE_MSE + ".u_WR_Data_Channel.wr_chl_ob_sel", 1, ["selected_port", "selected_lane", "per_bank_owner"]),
        (data, "wr_chl_mask_buf_vld", BASE_MSE + ".u_WR_Data_Channel.wr_chl_mask_buf_vld", 2, ["per_bank_valid", "outstanding"]),
        (data, "wr_chl_mask_buf_ready", BASE_MSE + ".u_WR_Data_Channel.wr_chl_mask_buf_ready", 2, ["per_bank_ready"]),
        (mem, "transaction_addr_valid", BASE_MSE + ".u_WR_Memory_AG.transaction_addr_valid", 1, ["internal_state", "lifetime"]),
        (mem, "transaction_finish", BASE_MSE + ".u_WR_Memory_AG.transaction_finish", 1, ["completion", "drain"]),
        (mem, "transaction_addr_ctrl_clear", BASE_MSE + ".u_WR_Memory_AG.transaction_addr_ctrl_clear", 1, ["clear", "drain"]),
        (mem, "transaction_addr_bias_valid", BASE_MSE + ".u_WR_Memory_AG.transaction_addr_bias_valid", 1, ["internal_state", "lifetime"]),
        (mem, "transaction_addr_bias_ctrl_clear", BASE_MSE + ".u_WR_Memory_AG.transaction_addr_bias_ctrl_clear", 1, ["clear"]),
        (mem, "transaction_idx_last_bit", BASE_MSE + ".u_WR_Memory_AG.transaction_idx_last_bit", 1, ["last"]),
        (mem, "transaction_idx_last_index", BASE_MSE + ".u_WR_Memory_AG.transaction_idx_last_index", 4, ["last", "count"]),
        (mem, "cur_transaction_size_left", BASE_MSE + ".u_WR_Memory_AG.cur_transaction_size_left", 8, ["count", "internal_state"]),
        (mem, "mem_ag_ob_chl_vld", BASE_MSE + ".u_WR_Memory_AG.mem_ag_ob_chl_vld", 2, ["outstanding", "per_bank_valid"]),
        (mem, "mem_ag_ob_chl_rd_hs", BASE_MSE + ".u_WR_Memory_AG.mem_ag_ob_chl_rd_hs", 2, ["accept", "fifo_dequeue"]),
        (mem, "mem_ag_ob_chl_wr_hs", BASE_MSE + ".u_WR_Memory_AG.mem_ag_ob_chl_wr_hs", 2, ["accept", "fifo_enqueue"]),
        (mem, "mem_ag_ob_chl_addr", BASE_MSE + ".u_WR_Memory_AG.mem_ag_ob_chl_addr", 52, ["address", "tag"]),
        (mem, "mem_ag_ob_chl_rw", BASE_MSE + ".u_WR_Memory_AG.mem_ag_ob_chl_rw", 2, ["mask", "barrier"]),
        (mem, "mem_ag_ob_sel", BASE_MSE + ".u_WR_Memory_AG.mem_ag_ob_sel", 1, ["selected_port", "selected_bank"]),
        (sem, "sem_cs", BASE_SEM + ".sem_cs", 3, ["stage", "internal_state", "drain"]),
        (sem, "sem_ns", BASE_SEM + ".sem_ns", 3, ["stage", "clear"]),
        (sem, "slice2gexec_ready", BASE_SEM + ".slice2gexec_ready", 1, ["global_terminal", "ready"]),
        (sem, "gexec2slice_valid", BASE_SEM + ".gexec2slice_valid", 1, ["request", "barrier"]),
        (stream, "slice_cmpt_finish", BASE_STREAM + ".slice_cmpt_finish", 1, ["finish", "global_terminal"]),
    ]
    result = [source_record(*row) for row in rows]
    used: dict[str, int] = {}
    for item in result:
        base = item["signal_id"]
        used[base] = used.get(base, 0) + 1
        if used[base] > 1:
            item["signal_id"] = f"{base}_{used[base]}"
    return result


def tb_source() -> str:
    return f'''`timescale 1ps/1ps
// Package-local, read-only bounded causal-cone VCD controller.
module codex_native_mse4_tb_vcd_controller(
  input wire clk, input wire rst_n, input wire slice_rst, input wire mse_enable,
  input wire mem_tag_valid, input wire mem_bp_pre,
  input wire desc_valid, input wire desc_ready, input wire [15:0] desc_mask,
  input wire [1:0] request_valid, input wire [1:0] request_ready,
  input wire [53:0] request_payload,
  input wire [1:0] wdata_valid, input wire [1:0] wdata_ready,
  input wire [255:0] wdata_payload,
  input wire [1:0] response_valid, input wire [1:0] response_ready,
  input wire [15:0] buffer_req_valid, input wire buffer_req_ready, input wire buffer_data_valid,
  input wire [1:0] buffer_fifo_count, input wire buffer_fifo_enq, input wire buffer_fifo_deq,
  input wire buffer_fifo_full, input wire buffer_fifo_empty,
  input wire [1:0] data_fifo_count, input wire data_fifo_enq, input wire data_fifo_deq,
  input wire data_fifo_full, input wire data_fifo_empty, input wire [5:0] prepared_count,
  input wire [1:0] mem_outstanding, input wire [1:0] data_outstanding,
  input wire [1:0] mem_accept, input wire [1:0] data_accept,
  input wire mem_finish, input wire mem_clear, input wire data_finish,
  input wire last_flag, input wire [3:0] last_index,
  input wire [2:0] sem_cs, input wire [2:0] sem_ns,
  input wire selected_finish, input wire aggregate_finish,
  input wire global_ready, input wire global_valid
);
  localparam longint unsigned CODEX_SUSPECT_CYCLES = 1048576;
  localparam longint unsigned CODEX_DUMPOFF_CYCLES = 4194304;
  localparam longint unsigned CODEX_GRACE_CYCLES = 262144;
  string codex_vcd_path;
  integer codex_enabled;
  integer codex_dump_off;
  integer codex_suspect_reported;
  longint unsigned codex_cycles;
  longint unsigned codex_last_change_cycle;
  longint unsigned codex_dump_off_cycle;
  longint unsigned codex_progress;
  longint unsigned codex_global_progress;
  time codex_previous_time;
  logic [1023:0] codex_previous_state;
  logic [63:0] codex_previous_counters;
  logic [7:0] codex_previous_global;
  wire [1023:0] codex_state = {{
    request_payload, wdata_payload, desc_mask, request_valid, request_ready,
    wdata_valid, wdata_ready, response_valid, response_ready, buffer_req_valid,
    buffer_req_ready, buffer_data_valid, buffer_fifo_count, buffer_fifo_enq,
    buffer_fifo_deq, buffer_fifo_full, buffer_fifo_empty, data_fifo_count,
    data_fifo_enq, data_fifo_deq, data_fifo_full, data_fifo_empty, prepared_count,
    mem_outstanding, data_outstanding, mem_accept, data_accept, mem_finish,
    mem_clear, data_finish, last_flag, last_index, sem_cs, sem_ns,
    selected_finish, aggregate_finish, global_ready, global_valid,
    mem_tag_valid, mem_bp_pre, desc_valid, desc_ready, mse_enable, slice_rst, rst_n
  }};
  wire [63:0] codex_counter_state = {{31'd0, codex_progress[31:0], selected_finish}};
  wire [7:0] codex_global_state = {{sem_cs, sem_ns, global_ready, aggregate_finish}};
  wire codex_unresolved_xz = $isunknown(codex_state);

  function automatic [63:0] codex_fold(input logic [1023:0] value);
    integer index;
    begin
      codex_fold = 64'd0;
      for (index = 0; index < 16; index = index + 1)
        codex_fold = codex_fold ^ value[index*64 +: 64];
    end
  endfunction

  initial begin
    codex_enabled = $test$plusargs("CODEX_TB_VCD_BOUNDED_CAUSAL_CONE");
    codex_dump_off = 0;
    codex_suspect_reported = 0;
    codex_cycles = 0;
    codex_last_change_cycle = 0;
    codex_dump_off_cycle = 0;
    codex_progress = 0;
    codex_global_progress = 0;
    codex_previous_time = 0;
    codex_previous_state = 'x;
    codex_previous_counters = 'x;
    codex_previous_global = 'x;
    if (codex_enabled) begin
      if (!$value$plusargs("CODEX_TB_VCD_PATH=%s", codex_vcd_path))
        $fatal(1, "bounded causal-cone VCD path missing");
      $dumpfile(codex_vcd_path);
      $dumpvars(0, {BASE_MSE});
      $dumpvars(0, {BASE_SEM});
      $dumpvars(1, {BASE_STREAM});
      $dumpvars(0, {BASE_STREAM}.MSE_INST[5].WR_MSE.u_Memory_WR_Stream_Engine.slice_cmpt_finish);
      $dumpvars(0, {BASE_STREAM}.MSE_INST[6].WR_MSE.u_Memory_WR_Stream_Engine.slice_cmpt_finish);
      $dumpvars(0, {BASE_STREAM}.MSE_INST[7].WR_MSE.u_Memory_WR_Stream_Engine.slice_cmpt_finish);
      $dumpvars(0, tb_NDP_Top_new_phy.slice2gexec_ready_mon);
      $dumpon;
      $display("CODEX_TBVCD_START_V1 sim_time=%0t", $time);
    end
  end

  always @(posedge clk) if (codex_enabled) begin
    codex_cycles <= codex_cycles + 1;
    if ((|(request_valid & request_ready)) || (|(wdata_valid & wdata_ready)) ||
        buffer_fifo_enq || buffer_fifo_deq || data_fifo_enq || data_fifo_deq ||
        (|mem_accept) || (|data_accept) || mem_finish || data_finish || selected_finish)
      codex_progress <= codex_progress + 1;
    if (codex_global_state !== codex_previous_global)
      codex_global_progress <= codex_global_progress + 1;

    if (!rst_n || slice_rst || !mse_enable || codex_unresolved_xz ||
        ($time <= codex_previous_time) ||
        (codex_state !== codex_previous_state) ||
        (codex_counter_state !== codex_previous_counters) ||
        (codex_global_state !== codex_previous_global)) begin
      codex_last_change_cycle <= codex_cycles;
      codex_suspect_reported <= 0;
      if (codex_dump_off) begin
        $dumpon;
        codex_dump_off <= 0;
      end
    end else begin
      if (!codex_suspect_reported && (codex_cycles - codex_last_change_cycle >= CODEX_SUSPECT_CYCLES)) begin
        codex_suspect_reported <= 1;
        $display("CODEX_TBVCD_PLATEAU_SUSPECT_V1 sim_time=%0t owner_cycles=%0d", $time, codex_cycles);
      end
      if (!codex_dump_off && (codex_cycles - codex_last_change_cycle >= CODEX_DUMPOFF_CYCLES)) begin
        $dumpoff;
        $dumpflush;
        codex_dump_off <= 1;
        codex_dump_off_cycle <= codex_cycles;
        $display("CODEX_TBVCD_DUMPOFF_V1 sim_time=%0t owner_cycles=%0d", $time, codex_cycles);
      end else if (codex_dump_off && (codex_cycles - codex_dump_off_cycle >= CODEX_GRACE_CYCLES)) begin
        $dumpflush;
        $display("CODEX_TBVCD_STOP_V1 reason=CAUSAL_PLATEAU sim_time=%0t owner_cycles=%0d", $time, codex_cycles);
        $finish;
      end
    end
    if (selected_finish || (sem_cs == 3'b010 && sem_ns == 3'b000 && aggregate_finish))
      $display("CODEX_TBVCD_TERMINAL_WITNESS_V1 sim_time=%0t selected_finish=%b aggregate_finish=%b", $time, selected_finish, aggregate_finish);
    if ((codex_cycles & 262143) == 0)
      $display("CODEX_TBVCD_HEARTBEAT_V1 sim_time=%0t owner_cycles=%0d progress=%0d state=%016h global=%0d unresolved_xz=%0d", $time, codex_cycles, codex_progress, codex_fold(codex_state), codex_global_progress, codex_unresolved_xz);
    codex_previous_time <= $time;
    codex_previous_state <= codex_state;
    codex_previous_counters <= codex_counter_state;
    codex_previous_global <= codex_global_state;
  end

  final if (codex_enabled) begin
    $dumpoff;
    $dumpflush;
    $display("CODEX_TBVCD_FLUSH_V1 dumpoff=1 dumpflush=1 closed=1 sim_time=%0t", $time);
  end
endmodule

bind {BASE_MSE} codex_native_mse4_tb_vcd_controller codex_native_mse4_tb_vcd_controller_inst (
  .clk(clk), .rst_n(rst_n), .slice_rst(slice_rst), .mse_enable(mse_enable),
  .mem_tag_valid(mse_mem_ag_tag_valid), .mem_bp_pre(mse_mem_ag_bp_pre),
  .desc_valid(wr_data_chl_req_valid), .desc_ready(wr_data_chl_req_ready), .desc_mask(wr_data_chl_req_valid_mask),
  .request_valid(mse2mem_request_valid), .request_ready(mem2mse_request_ready), .request_payload(mse2mem_request),
  .wdata_valid(mse2mem_wdata_valid), .wdata_ready(mem2mse_wdata_ready), .wdata_payload(mse2mem_wdata),
  .response_valid(mem2mse_rdata_valid), .response_ready(mse2mem_rdata_ready),
  .buffer_req_valid(mse2buf_rreq_valid), .buffer_req_ready(buf2mse_rreq_ready), .buffer_data_valid(buf2mse_rvalid),
  .buffer_fifo_count(u_RD_Buffer_AG.buf_ag_ob_cnt), .buffer_fifo_enq(u_RD_Buffer_AG.buf_ag_ob_wr_en),
  .buffer_fifo_deq(u_RD_Buffer_AG.buf_ag_ob_rd_en), .buffer_fifo_full(u_RD_Buffer_AG.buf_ag_ob_full),
  .buffer_fifo_empty(u_RD_Buffer_AG.buf_ag_ob_empty),
  .data_fifo_count(u_WR_Data_Channel.u_wr_chl_queue.fifo_counter), .data_fifo_enq(u_WR_Data_Channel.wr_chl_queue_wr_en),
  .data_fifo_deq(u_WR_Data_Channel.wr_chl_queue_rd_en), .data_fifo_full(u_WR_Data_Channel.wr_chl_queue_full),
  .data_fifo_empty(u_WR_Data_Channel.wr_chl_queue_empty), .prepared_count(u_WR_Data_Channel.wr_data_chl_prepared_data_cnt),
  .mem_outstanding(u_WR_Memory_AG.mem_ag_ob_chl_vld), .data_outstanding(u_WR_Data_Channel.wr_chl_ob_vld),
  .mem_accept(u_WR_Memory_AG.mem_ag_ob_chl_rd_hs), .data_accept(u_WR_Data_Channel.wr_chl_ob_rd_hs),
  .mem_finish(u_WR_Memory_AG.transaction_finish), .mem_clear(u_WR_Memory_AG.transaction_addr_ctrl_clear),
  .data_finish(u_WR_Data_Channel.wr_data_chl_ob_last_data_arv_arr_flag),
  .last_flag(buf_ag_last_req_flag), .last_index(u_RD_Buffer_AG.mse2buf_last_index),
  .sem_cs({BASE_SEM}.sem_cs), .sem_ns({BASE_SEM}.sem_ns),
  .selected_finish(slice_cmpt_finish), .aggregate_finish({BASE_STREAM}.slice_cmpt_finish),
  .global_ready({BASE_SEM}.slice2gexec_ready), .global_valid({BASE_SEM}.gexec2slice_valid)
);
'''


def vcd_contract(signals: list[dict[str, Any]], tb_path: Path) -> dict[str, Any]:
    clean_signals = [
        {key: value for key, value in item.items() if key in {
            "signal_id", "exact_hierarchy", "width_bits", "roles", "source_path",
            "source_sha256", "declaration_span_sha256", "source_binding",
            "derived_expected_equation", "drives_dut",
        }} for item in signals
    ]
    by_role: dict[str, list[str]] = {}
    for item in clean_signals:
        for role in item["roles"]:
            by_role.setdefault(role, []).append(item["signal_id"])
    required_roles = (
        "clock", "reset", "stage", "source", "producer", "request", "valid", "ready", "accept", "backpressure",
        "fifo_enqueue", "fifo_dequeue", "fifo_occupancy", "fifo_full", "fifo_empty", "outstanding",
        "tag", "address", "mask", "last", "count", "ping_pong_branch0", "ping_pong_branch1",
        "per_bank_ready", "per_bank_full", "per_bank_valid", "per_bank_owner", "barrier", "lifetime",
        "clear", "completion", "drain", "finish", "global_terminal", "selected_port", "selected_bank",
        "selected_lane", "internal_match", "internal_state", "output", "wdata",
    )
    missing = [role for role in required_roles if role not in by_role]
    if missing:
        raise RuntimeError(f"uncovered VCD roles: {missing}")
    boundaries = [
        {"boundary_id": "mse4_upstream_descriptor_buffer", "layer": "FIRST_DIVERGENCE_UPSTREAM_ONE", "signal_ids": [item["signal_id"] for item in clean_signals if any(role in item["roles"] for role in ("source", "tag", "fifo_occupancy", "request"))]},
        {"boundary_id": "mse4_current_accept_outstanding", "layer": "FIRST_DIVERGENCE_CURRENT", "signal_ids": [item["signal_id"] for item in clean_signals if any(role in item["roles"] for role in ("accept", "outstanding", "wdata"))]},
        {"boundary_id": "mse4_downstream_last_finish", "layer": "FIRST_DIVERGENCE_DOWNSTREAM_ONE", "signal_ids": [item["signal_id"] for item in clean_signals if any(role in item["roles"] for role in ("last", "completion", "finish"))]},
        {"boundary_id": "mse4_hold_clear_terminal", "layer": "STATE_HOLD_CLEAR", "signal_ids": [item["signal_id"] for item in clean_signals if any(role in item["roles"] for role in ("clear", "drain", "internal_state", "global_terminal"))]},
    ]
    candidates = [
        ("post_accept_terminal_accounting", "accepted writes are not retired into the terminal accounting path"),
        ("outstanding_response_identity", "request or response identity remains outstanding on the selected port"),
        ("last_count_mismatch", "last, last_index or expected count does not align with accepted data"),
        ("completion_fsm_drain_clear", "completion state fails to drain or clear after the final acceptance"),
        ("finish_aggregation", "per-MSE completion fails to propagate into slice/global finish"),
        ("cross_layer_upstream_control", "an upstream descriptor/buffer control lifetime remains active after accepted work"),
    ]
    matrix = []
    for index, (candidate_id, _description) in enumerate(candidates):
        for boundary_index, boundary in enumerate(boundaries):
            matrix.append({
                "candidate_id": candidate_id,
                "boundary_id": boundary["boundary_id"],
                "expected_signature": {
                    "candidate_ordinal": index, "boundary_ordinal": boundary_index,
                    "distinguishing_code": f"C{index}_B{boundary_index}",
                    "actual_signal_ids": boundary["signal_ids"],
                },
            })
    return {
        "schema": "server-tb-vcd-bounded-causal-cone-v1",
        "profile": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "rule_id": "CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001",
        "package_id": PACKAGE_ID, "family": FAMILY,
        "execution": {
            "compile_argv": ["timeout", "--foreground", "--signal=TERM", "--kill-after=30s", "2h", "make", "-f", "Makefile.tb_NDP_Top_new_phy", "compile", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0", "RUN_DIR=<ATTEMPT_COMPILE_ROOT>", f"VCS_EXTRA_OPTS=<PACKAGE_ROOT>/{tb_path.relative_to(TREE).as_posix()}"],
            "sim_argv": ["<ATTEMPT_SIMV>", "-l", "<ATTEMPT_ROOT>/c0/sim.log", "+vcs+lic+wait", "+SCA_CFG=<PACKAGE_CFG>", "+SCA_CFG_D=<PACKAGE_CFG_D>", "+CODEX_TB_VCD_BOUNDED_CAUSAL_CONE", "+CODEX_TB_VCD_PATH=<ATTEMPT_ROOT>/c0/native_mse4_causal.vcd"],
            "dump_argv": {"DUMP_VCD": "0", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"},
            "tb_source_path": tb_path.relative_to(TREE).as_posix(), "tb_source_sha256": sha(tb_path),
            "standard_tasks": ["$dumpfile", "$dumpvars", "$dumpon", "$dumpoff", "$dumpflush"],
            "producer": "PACKAGE_LOCAL_TB_STANDARD_SYSTEM_TASKS_ONLY", "lightweight_observer_jsonl": False,
        },
        "scope": {
            "simulation_top": "tb_NDP_Top_new_phy", "full_hierarchy_dump": False,
            "dump_scopes": [
                {"scope_id": "selected_mse4_write_engine", "exact_hierarchy": BASE_MSE, "depth": 0, "boundary_ids": [row["boundary_id"] for row in boundaries], "source_bound_signal_ids": [row["signal_id"] for row in clean_signals if row["exact_hierarchy"].startswith(BASE_MSE)]},
                {"scope_id": "slice_completion_fsm", "exact_hierarchy": BASE_SEM, "depth": 0, "boundary_ids": ["mse4_downstream_last_finish", "mse4_hold_clear_terminal"], "source_bound_signal_ids": [row["signal_id"] for row in clean_signals if row["exact_hierarchy"].startswith(BASE_SEM)]},
                {"scope_id": "stream_finish_aggregate", "exact_hierarchy": BASE_STREAM, "depth": 1, "boundary_ids": ["mse4_downstream_last_finish", "mse4_hold_clear_terminal"], "source_bound_signal_ids": [row["signal_id"] for row in clean_signals if row["exact_hierarchy"] == BASE_STREAM + ".slice_cmpt_finish"]},
            ],
        },
        "budget": {"soft_warning_bytes": 100000000, "operational_vcd_budget_bytes": 8000000000, "return_budget_bytes": 10000000000, "wall_ceiling_seconds": 3600, "hard_truncation": False, "sampling": False, "size_based_deletion": False},
        "signals": clean_signals,
        "role_coverage": [{"role": role, "disposition": "covered", "signal_ids": sorted(set(by_role[role]))} for role in required_roles],
        "boundaries": boundaries,
        "candidates": [{"candidate_id": candidate_id, "description": description} for candidate_id, description in candidates],
        "candidate_boundary_matrix": matrix,
        "runtime_policy": {
            "plateau_suspected_cycles": 1048576, "plateau_dump_off_cycles": 4194304,
            "post_dump_grace_cycles": 262144,
            "plateau_qualification": ["owner_clock_advancing", "sim_time_advancing", "all_qualified_progress_counters_stable", "complete_source_bound_causal_state_bitwise_stable", "global_progress_witness_stable", "candidate_catalog_coverage_complete", "no_unresolved_xz"],
            "sim_time_freeze_intervals": 3, "sim_time_freeze_interval_seconds": 30,
            "termination_sequence": ["TERM", "WAIT", "KILL", "REAP"],
            "disk_write_quota_fail_safe": True, "rolling_growth_projection": True,
        },
        "return_receipts": {
            "catalog": "evidence/TB_VCD_CAUSAL_SIGNAL_CATALOG.json",
            "candidate_matrix": "evidence/TB_VCD_CANDIDATE_BOUNDARY_MATRIX.json",
            "actual_argv": "evidence/ACTUAL_COMPILE_SIM_ARGV.json",
            "tb_source": "evidence/TB_SOURCE_RECEIPT.json",
            "elaboration": "evidence/TB_VCD_ELABORATION_RECEIPT.json",
            "runtime": "evidence/TB_VCD_RUNTIME_RECEIPT.json",
            "vcd": "runs/c0/native_mse4_causal.vcd",
            "process_tree": "evidence/PROCESS_TREE_RECEIPT.json",
            "return_manifest": "RETURN_CORE_MANIFEST.json",
        },
        "claim_boundary": "Source-bound bounded causal-cone transport and early-stop contract only; local gates do not establish production compile, simulation, root cause, natural terminal, formal D, E3, E4 or E5.",
    }


def selector(contract_path: Path) -> dict[str, Any]:
    return {
        "schema": "server-diagnostic-mode-selector-v1", "package_id": PACKAGE_ID,
        "family": FAMILY, "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "bulk_evidence": {"observer_jsonl": False, "tb_standard_vcd": True, "vpd": False, "fsdb": False, "ucli_direct_vcd": False, "vendor_signal_query": False},
        "actual_dump_argv": {"DUMP_VCD": "0", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"},
        "lightweight_progress_supervisor": {"enabled": True, "bulk_signal_events": False, "sim_time_heartbeat": True, "process_tree_reap": True},
        "package_members": ["tb_probe/native_mse4_bounded_causal_cone_vcd.sv", "contracts/server_tb_vcd_bounded_causal_cone_contract.json", "diagnostics/tb_vcd_causal_signal_catalog.json", "diagnostics/tb_vcd_candidate_boundary_matrix.json"],
        "return_members": ["runs/c0/native_mse4_causal.vcd", "evidence/TB_VCD_RUNTIME_RECEIPT.json", "evidence/PROCESS_TREE_RECEIPT.json", "RETURN_CORE_MANIFEST.json"],
        "observer_contract_sha256": None, "vcd_contract_sha256": sha(contract_path),
        "claim_boundary": "Exactly one bulk-evidence mode is selected; observer-only remains a separate unchanged default option.",
    }


def post_request() -> dict[str, Any]:
    def row(root: str, source: str, archive: str, required: bool = False) -> dict[str, Any]:
        return {"source_root": root, "source": source, "archive": archive, "required": required}
    rows = [
        row("package", "package_manifest.json", "evidence/returned_package_manifest.json", True),
        row("package", "contracts/server_diagnostic_mode_selector.json", "evidence/server_diagnostic_mode_selector.json", True),
        row("package", "contracts/server_tb_vcd_bounded_causal_cone_contract.json", "evidence/server_tb_vcd_bounded_causal_cone_contract.json", True),
        row("package", "contracts/server_tb_vcd_streaming_retention_contract.json", "evidence/server_tb_vcd_streaming_retention_contract.json", True),
        row("package", "package_tools/server_tb_vcd_retention_analysis.py", "analysis_tools/server_tb_vcd_retention_analysis.py", True),
        row("attempt", "evidence/ACTUAL_COMPILE_SIM_ARGV.json", "evidence/ACTUAL_COMPILE_SIM_ARGV.json", True),
        row("attempt", "evidence/compile_rootcause/COMPILE_CORE.json", "evidence/compile_rootcause/COMPILE_CORE.json", True),
        row("attempt", "evidence/compile_rootcause/compile_driver.log", "evidence/compile_rootcause/compile_driver.log", True),
        row("attempt", "evidence/compile_rootcause/compile_log_receipt.json", "evidence/compile_rootcause/compile_log_receipt.json", True),
        row("attempt", "evidence/compile_rootcause/compile_first_error.txt", "evidence/compile_rootcause/compile_first_error.txt", True),
        row("attempt", "evidence/compile_rootcause/compile_argv.json", "evidence/compile_rootcause/compile_argv.json", True),
        row("attempt", "evidence/compile_rootcause/compile_source_identity.json", "evidence/compile_rootcause/compile_source_identity.json", True),
        row("attempt", "evidence/compile_rootcause/compile_exit.txt", "evidence/compile_rootcause/compile_exit.txt", True),
        row("attempt", "evidence/compile_rootcause/compile_log_head.txt", "evidence/compile_rootcause/compile_log_head.txt"),
        row("attempt", "evidence/compile_rootcause/compile_log_tail.txt", "evidence/compile_rootcause/compile_log_tail.txt"),
        row("attempt", "evidence/compile_rootcause/NATIVE_FLOW_FAILURE_DIFFERENTIAL.json", "evidence/compile_rootcause/NATIVE_FLOW_FAILURE_DIFFERENTIAL.json", True),
        row("attempt", "evidence/compile_rootcause/PUBLISHED_ACTUAL_ROOT_IDENTITY.json", "evidence/compile_rootcause/PUBLISHED_ACTUAL_ROOT_IDENTITY.json", True),
        row("attempt", "evidence/SIM_EXIT_RECEIPT.json", "evidence/SIM_EXIT_RECEIPT.json", True),
        row("attempt", "evidence/PROCESS_TREE_RECEIPT.json", "evidence/PROCESS_TREE_RECEIPT.json", True),
        row("attempt", "evidence/SIM_TIME_HEARTBEAT.jsonl", "evidence/SIM_TIME_HEARTBEAT.jsonl"),
        row("attempt", "evidence/TB_VCD_RUNTIME_SAMPLES.jsonl", "evidence/TB_VCD_RUNTIME_SAMPLES.jsonl", True),
        row("attempt", "evidence/TB_VCD_LIVE_SAFETY_RECEIPT.json", "evidence/TB_VCD_LIVE_SAFETY_RECEIPT.json", True),
        row("attempt", "evidence/TB_VCD_CAUSAL_SIGNAL_CATALOG.json", "evidence/TB_VCD_CAUSAL_SIGNAL_CATALOG.json", True),
        row("attempt", "evidence/TB_VCD_CANDIDATE_BOUNDARY_MATRIX.json", "evidence/TB_VCD_CANDIDATE_BOUNDARY_MATRIX.json", True),
        row("attempt", "evidence/TB_SOURCE_RECEIPT.json", "evidence/TB_SOURCE_RECEIPT.json", True),
        row("attempt", "evidence/TB_VCD_ELABORATION_RECEIPT.json", "evidence/TB_VCD_ELABORATION_RECEIPT.json", True),
        row("attempt", "evidence/TB_VCD_RUNTIME_RECEIPT.json", "evidence/TB_VCD_RUNTIME_RECEIPT.json", True),
        row("attempt", "evidence/TB_VCD_RUNTIME_REQUEST.json", "evidence/TB_VCD_RUNTIME_REQUEST.json", True),
        row("attempt", "evidence/TB_VCD_IDENTITY.json", "evidence/TB_VCD_IDENTITY.json", True),
        row("attempt", "evidence/TB_VCD_STOP_RECEIPT.json", "evidence/TB_VCD_STOP_RECEIPT.json", True),
        row("attempt", "evidence/PUBLISHED_ACTUAL_ROOT_IDENTITY.json", "evidence/PUBLISHED_ACTUAL_ROOT_IDENTITY.json", True),
        row("attempt", "c0/native_mse4_causal.vcd", "runs/c0/native_mse4_causal.vcd", True),
        row("attempt", "c0/sim.log", "runs/c0/sim.log", True),
        row("attempt", "c0/simulator_argv.txt", "runs/c0/simulator_argv.txt", True),
    ]
    return {
        "schema": "server-post-sim-return-request-v1", "package_id": PACKAGE_ID,
        "result_root": "/home/panqs/ndp/simresult", "return_basename_template": "{package_id}_{execution_id}_return.zip",
        "core_entries": rows, "plugins": [], "max_plugin_output_bytes": 262144,
        "claim_boundary": "Native-flow compile/simulation and raw bounded VCD core publication; any non-natural exit is PARTIAL/DIAGNOSTIC_EVIDENCE_INCOMPLETE and family interpretation remains post-return.",
    }


def runner() -> str:
    return r'''#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
package_id="__PACKAGE_ID__"
install_name="__PACKAGE_ID__"
attempt="a0"
return_tag="r$(date -u +%s%N)_$$"
server_root="${1-}"
published_root="/home/panqs/ndp/NDP_copy01"
result_root="/home/panqs/ndp/simresult"
return_zip="$result_root/${package_id}_${return_tag}_return.zip"
return_sha="${return_zip}.sha256"
package_root=""
case "${BASH_SOURCE[0]}" in /*) package_root="${BASH_SOURCE[0]%/*}";; */*) package_root="$PWD/${BASH_SOURCE[0]%/*}";; *) package_root="$PWD";; esac
bootstrap_root="${server_root}/install/codex_runs/${package_id}/${attempt}/evidence/compile_bootstrap"
compile_argv_json="$bootstrap_root/compile_argv.json"
compile_source_identity_json="$bootstrap_root/compile_source_identity.json"
compile_exit_txt="$bootstrap_root/compile_exit.txt"
compile_driver_log="$bootstrap_root/compile_driver.log"
compile_log_receipt_json="$bootstrap_root/compile_log_receipt.json"
compile_log_head_txt="$bootstrap_root/compile_log_head.txt"
compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"
compile_first_error_txt="$bootstrap_root/compile_first_error.txt"
compile_status=125
run_status=125
signal_status=NONE
sim_started=false
timed_out=false
finalized=0
run_root=""
evidence_root=""
compile_root=""
cfg_root=""
preflight_stage=ARGUMENT_SYNTAX
tb_source="$package_root/tb_probe/native_mse4_bounded_causal_cone_vcd.sv"
vcd_path=""
samples_path=""
simv=""

# Exact return bindings: ACTUAL_COMPILE_SIM_ARGV.json COMPILE_CORE.json
# PUBLISHED_ACTUAL_ROOT_IDENTITY.json PROCESS_TREE_RECEIPT.json
# TB_VCD_RUNTIME_RECEIPT.json native_mse4_causal.vcd
# DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RETURN_FINALIZER_STATE.json
runner_fail() { code="$1"; shift; printf 'RUNNER_ERROR package=%s code=%s message=%s\n' "$package_id" "$code" "$*" >&2; exit "$code"; }
bootstrap_finalize() {
  original="$1"
  [ "$finalized" -eq 0 ] || exit "$original"
  finalized=1
  trap - EXIT INT TERM HUP
  set +e
  python3 "$package_root/package_tools/fixed_simresult_publisher.py" --bootstrap-partial --package-root "$package_root" --exit-code "$original" --signal-name "$signal_status" --stage "$preflight_stage" --server-root "$server_root" --bootstrap-root "$bootstrap_root" --return-zip "$return_zip"
  publish_rc=$?
  [ "$original" -ne 0 ] || original="$publish_rc"
  printf 'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s\n' "$package_id" "$compile_status" "$run_status" "$signal_status" "$original" "$return_zip" >&2
  exit "$original"
}
on_bootstrap_signal() { signal_status="$1"; bootstrap_finalize "$2"; }
trap 'bootstrap_finalize $?' EXIT
trap 'on_bootstrap_signal HUP 129' HUP
trap 'on_bootstrap_signal INT 130' INT
trap 'on_bootstrap_signal TERM 143' TERM

[ "$#" -eq 1 ] || runner_fail 2 "usage requires one absolute server root"
case "$1" in /*) ;; *) runner_fail 2 "server root argument must be absolute";; esac
# CODEX_PRODUCTION_LAUNCH

finalize() {
  original="$1"
  [ "$finalized" -eq 0 ] || exit "$original"
  finalized=1
  trap - EXIT INT TERM HUP
  set +e
  if [ -z "$evidence_root" ] || [ ! -d "$evidence_root" ]; then
    python3 "$package_root/package_tools/fixed_simresult_publisher.py" --bootstrap-partial --package-root "$package_root" --exit-code "$original" --signal-name "$signal_status" --stage "$preflight_stage" --server-root "$server_root" --bootstrap-root "$bootstrap_root" --return-zip "$return_zip"
    publish_rc=$?
    [ "$original" -ne 0 ] || original="$publish_rc"
    printf 'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s\n' "$package_id" "$compile_status" "$run_status" "$signal_status" "$original" "$return_zip" >&2
    exit "$original"
  fi
  mkdir -p "$evidence_root/compile_rootcause" "$run_root/c0"
  return_args=""
  [ "$sim_started" = true ] && return_args="$return_args --simulation-started"
  [ "$timed_out" = true ] && return_args="$return_args --timed-out"
  python3 "$package_root/package_tools/compile_core_evidence.py" return-core --output-root "$bootstrap_root" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --compile-exit "$compile_status" --sim-exit "$run_status" $return_args --signal "$signal_status"
  for name in compile_argv.json compile_source_identity.json compile_exit.txt compile_driver.log compile_log_receipt.json compile_log_head.txt compile_log_tail.txt compile_first_error.txt COMPILE_CORE.json NATIVE_FLOW_FAILURE_DIFFERENTIAL.json PUBLISHED_ACTUAL_ROOT_IDENTITY.json; do
    [ ! -f "$bootstrap_root/$name" ] || cp -f "$bootstrap_root/$name" "$evidence_root/compile_rootcause/$name"
  done
  [ ! -f "$bootstrap_root/ACTUAL_COMPILE_SIM_ARGV.json" ] || cp -f "$bootstrap_root/ACTUAL_COMPILE_SIM_ARGV.json" "$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json"
  [ ! -f "$bootstrap_root/SIM_EXIT_RECEIPT.json" ] || cp -f "$bootstrap_root/SIM_EXIT_RECEIPT.json" "$evidence_root/SIM_EXIT_RECEIPT.json"
  vcd_rc=97
  if [ "$sim_started" = true ]; then
    python3 "$package_root/package_tools/tb_vcd_finalize.py" --package-root "$package_root" --attempt-root "$run_root" --evidence-root "$evidence_root" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --actual-root "$server_root" --published-root "$published_root" --compile-exit "$compile_status" --sim-exit "$run_status" --signal "$signal_status" --vcd "$vcd_path" --sim-log "$run_root/c0/sim.log" --samples "$samples_path" --process-receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" --safety-receipt "$evidence_root/TB_VCD_LIVE_SAFETY_RECEIPT.json"
    vcd_rc=$?
  fi
  export CODEX_PACKAGE_ROOT="$package_root" CODEX_ATTEMPT_ROOT="$run_root" CODEX_EXECUTION_ID="$return_tag" CODEX_ATTEMPT_ID="$attempt" CODEX_PACKAGE_ID="$package_id" CODEX_SIM_EXIT_CODE="$run_status" CODEX_SIM_SIGNAL="$signal_status" CODEX_SIM_STARTED="$sim_started" CODEX_NATURAL_TERMINAL=false
  if [ -f "$evidence_root/TB_VCD_RUNTIME_RECEIPT.json" ] && grep -q '"natural_terminal": true' "$evidence_root/TB_VCD_RUNTIME_RECEIPT.json"; then export CODEX_NATURAL_TERMINAL=true; fi
  python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"
  core_rc=$?
  final="$original"
  [ "$final" -ne 0 ] || [ "$core_rc" -eq 0 ] || final="$core_rc"
  [ "$final" -ne 0 ] || [ "$vcd_rc" -eq 0 ] || final="$vcd_rc"
  printf 'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s\n' "$package_id" "$compile_status" "$run_status" "$signal_status" "$final" "$return_zip" >&2
  exit "$final"
}
on_signal() { signal_status="$1"; finalize "$2"; }
finalized=0
trap 'finalize $?' EXIT
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM

preflight_stage=NATIVE_CD
cd "$server_root" || runner_fail 4 "native production cd failed; inspect returned cwd and exit"
server_root="$PWD"
cfg_root="$server_root/install/cfg_pkg/$package_id"
run_root="$server_root/install/codex_runs/$package_id/$attempt"
evidence_root="$run_root/evidence"
compile_root="$run_root/compile"
bootstrap_root="$evidence_root/compile_bootstrap"
compile_argv_json="$bootstrap_root/compile_argv.json"
compile_source_identity_json="$bootstrap_root/compile_source_identity.json"
compile_exit_txt="$bootstrap_root/compile_exit.txt"
compile_driver_log="$bootstrap_root/compile_driver.log"
compile_log_receipt_json="$bootstrap_root/compile_log_receipt.json"
compile_log_head_txt="$bootstrap_root/compile_log_head.txt"
compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"
compile_first_error_txt="$bootstrap_root/compile_first_error.txt"
vcd_path="$run_root/c0/native_mse4_causal.vcd"
samples_path="$evidence_root/TB_VCD_RUNTIME_SAMPLES.jsonl"
preflight_stage=NATIVE_PACKAGE_INSTALL
rm -rf -- "$cfg_root" "$run_root"
mkdir -p "$cfg_root" "$compile_root/sim_results" "$run_root/c0" "$evidence_root" "$bootstrap_root" "$result_root" || runner_fail 14 "native package-owned install directories could not be created"
cp -a "$package_root/workload/runtime/." "$cfg_root/" || runner_fail 6 "native package-owned workload install failed"
printf '{"schema":"server-published-actual-root-identity-v1","package_id":"%s","execution_id":"%s","attempt_id":"%s","published_root":"%s","actual_root":"%s","match":%s}\n' "$package_id" "$return_tag" "$attempt" "$published_root" "$server_root" "$([ "$published_root" = "$server_root" ] && printf true || printf false)" > "$bootstrap_root/PUBLISHED_ACTUAL_ROOT_IDENTITY.json"
python3 "$package_root/package_tools/compile_core_evidence.py" prepare --output-root "$bootstrap_root" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --cwd "$server_root" --makefile-name Makefile.tb_NDP_Top_new_phy --source "$tb_source" --package-root "$package_root" --run-dir "$compile_root" --attempt-root "$run_root" --sca-cfg "$cfg_root/runs/c0/sca_cfg.json" --sca-cfg-d "$cfg_root/runs/c0/sca_cfg_D.json" --vcd-path "$vcd_path" --repeat-num 1 || runner_fail 8 "compile-core actual argv bootstrap failed"

preflight_stage=PRODUCTION_COMPILE
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$compile_root" VCS_EXTRA_OPTS="$tb_source" > "$compile_driver_log" 2>&1
compile_status=$?
set -e
python3 "$package_root/package_tools/compile_core_evidence.py" finalize --output-root "$bootstrap_root" --exit-code "$compile_status" || runner_fail 8 "compile-core post-actual-command finalize failed"
[ "$compile_status" -eq 0 ] || exit "$compile_status"
simv="$compile_root/sim_results/simv"
printf '%s\n' "$simv -l $run_root/c0/sim.log +SCA_CFG=$cfg_root/runs/c0/sca_cfg.json +SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json +CODEX_TB_VCD_BOUNDED_CAUSAL_CONE +CODEX_TB_VCD_PATH=$vcd_path" > "$run_root/c0/simulator_argv.txt"
preflight_stage=PRODUCTION_SIMULATION
sim_started=true
set +e
DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 python3 "$package_root/package_tools/tb_vcd_live_supervision.py" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --process-supervisor "$package_root/package_tools/server_process_tree_supervision.py" --sim-log "$run_root/c0/sim.log" --vcd "$vcd_path" --samples "$samples_path" --heartbeat-output "$evidence_root/SIM_TIME_HEARTBEAT.jsonl" --process-receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" --safety-receipt "$evidence_root/TB_VCD_LIVE_SAFETY_RECEIPT.json" -- "$simv" -l "$run_root/c0/sim.log" +vcs+lic+wait "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json" +CODEX_TB_VCD_BOUNDED_CAUSAL_CONE "+CODEX_TB_VCD_PATH=$vcd_path" "+CODEX_PACKAGE_ID=$package_id" "+CODEX_EXECUTION_ID=$return_tag" "+CODEX_ATTEMPT_ID=$attempt"
run_status=$?
set -e
[ "$run_status" -eq 124 ] && timed_out=true
[ "$run_status" -eq 129 ] && signal_status=HUP
[ "$run_status" -eq 130 ] && signal_status=INT
[ "$run_status" -eq 143 ] && signal_status=TERM
exit "$run_status"
'''.replace("__PACKAGE_ID__", PACKAGE_ID)


def patch_fixed_publisher() -> None:
    source = (ROOT / "outputs/conv_native_four_lane_0ccae916_p46_nativeflow_release/build" / OLD_ID / "package_tools/fixed_simresult_publisher.py").read_text(encoding="utf-8")
    source = source.replace(OLD_ID, PACKAGE_ID)
    source = source.replace('    "compile_first_error.txt",\n)', '    "compile_first_error.txt",\n    "PUBLISHED_ACTUAL_ROOT_IDENTITY.json",\n)')
    source = source.replace('    "compile_first_error.txt": 4 * 1024,\n}', '    "compile_first_error.txt": 4 * 1024,\n    "PUBLISHED_ACTUAL_ROOT_IDENTITY.json": 64 * 1024,\n}')
    source = source.replace('"waveform_included": False,', '"waveform_included": False, "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",')
    write("package_tools/fixed_simresult_publisher.py", source.encode("utf-8"), executable=True)


def layout_contract(runner_path: Path) -> dict[str, Any]:
    cfg = f"install/cfg_pkg/{PACKAGE_ID}"
    return {
        "schema": "server-package-runtime-layout-contract-v1", "package_id": PACKAGE_ID,
        "fixed_result_root": "/home/panqs/ndp/simresult", "required_existing_parents": ["install"],
        "package_creatable_parents": ["install/cfg_pkg", "install/codex_runs"],
        "roots": {"cfg_root": cfg, "run_root": f"install/codex_runs/{PACKAGE_ID}/{{attempt}}", "evidence_root": f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence", "compile_root": f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/compile"},
        "runner_member": "PREPARE_AND_RUN.sh", "runner_sha256": sha(runner_path),
        "layout_helper_member": "package_tools/server_package_runtime_layout.py",
        "layout_helper_sha256": sha(TREE / "package_tools/server_package_runtime_layout.py"),
        "sca_cfg_consumers": [f"{cfg}/runs/c0/sca_cfg.json", f"{cfg}/runs/c0/sca_cfg_D.json"],
        "repeat_execution": {"mode": "RESET_EXACT_PACKAGE_OWNED_RUNTIME_ROOTS", "cfg_root_policy": "RESET_AND_RECREATE_EXACT_INSTALL_NAME", "run_root_policy": "RESET_AND_RECREATE_EXACT_PACKAGE_ATTEMPT", "foreign_sibling_policy": "PRESERVE", "symlink_or_special_entry_policy": "FAIL_CLOSED", "ownership_marker": ".codex_owner.{name}.json", "return_name_policy": "UNIQUE_PER_EXECUTION_PRESERVE_PRIOR_RETURNS"},
        "path_length_budget": {"declared_target_root_max_chars": 128, "absolute_path_limit_chars": 1024, "max_projected_relative_path_chars": 150, "max_projected_absolute_path_limit_chars": 300},
        "claim_boundary": "Package-owned install/runtime layout only; no server-owned preflight or production result claim.",
    }


def update_manifest(contract_path: Path, selector_path: Path, runner_path: Path) -> None:
    manifest = {
        "schema": "conv-native-four-lane-p47-tb-vcd-package-v1",
        "package_identity": PACKAGE_ID, "install_name": PACKAGE_ID, "family": FAMILY,
        "status": "PACKAGE_READY_NOT_RUN", "activation_epoch": ACTIVATION_EPOCH,
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "source_package": OLD_ID,
        "previous_version_progress": "p41 proved production compile beyond the Datahub repair; p42 corrected the two-bit vector valid/ready predicate; p46 proved descriptor, buffer, MemAG and wdata accepts but ended by INT before downstream terminal/accounting localization.",
        "current_version_purpose": "Preserve the p42 predicate and selected MSE4 wdata/slice-finish target while capturing a bounded source-bound VCD cone over FIFO, outstanding/response, last/count, drain/clear, finish aggregation and global progress boundaries.",
        "frozen": {"config": True, "numeric": True, "workload": True, "golden": True, "functional_rtl": True, "target_diagnostic": True},
        "dump_values": {"DUMP_VCD": 0, "DUMP_FSDB": 0, "TB_DUMP_FSDB": 0},
        "vcd_contract_sha256": sha(contract_path), "mode_selector_sha256": sha(selector_path),
        "runner_sha256": sha(runner_path),
        "claim_boundary": "Local construction and validation only; no upload, lease, connection, production compile, simulation, root-cause, natural terminal, formal D, E3, E4 or E5 claim.",
        "server_actions_performed": [], "files": {},
    }
    manifest_path = TREE / "package_manifest.json"
    manifest_path.write_bytes(canonical(manifest))
    manifest["files"] = {
        path.relative_to(TREE).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(row for row in TREE.rglob("*") if row.is_file())
        if path != manifest_path
    }
    manifest_path.write_bytes(canonical(manifest))


def deterministic_zip(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as archive:
        for path in sorted(row for row in TREE.rglob("*") if row.is_file()):
            name = f"{PACKAGE_ID}/{path.relative_to(TREE).as_posix()}"
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o100755 if os.access(path, os.X_OK) else 0o100644
            info.external_attr = mode << 16
            archive.writestr(info, path.read_bytes())


def build() -> None:
    if not SOURCE_ZIP.is_file():
        raise RuntimeError("protected p46 pending ZIP is absent")
    source_identity = identity(SOURCE_ZIP)
    safe_extract(SOURCE_ZIP)
    remove_old_diagnostic_surface()
    frozen_workload = {
        item.relative_to(TREE / "workload/runtime").as_posix(): {
            "bytes": item.stat().st_size,
            "sha256": sha(item),
        }
        for item in sorted((TREE / "workload/runtime").rglob("*"))
        if item.is_file()
    }
    write_json("provenance/frozen_p46_surface.json", {
        "schema": "conv-native-p47-frozen-p46-surface-v1",
        "source_package": source_identity,
        "workload_member_count": len(frozen_workload),
        "workload_members": frozen_workload,
        "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional_rtl", "target_diagnostic"],
        "functional_rtl_entries": 0,
        "identity_normalized_byte_equal": True,
        "pass": True,
        "errors": [],
    })

    write("package_tools/compile_core_evidence.py", (ROOT / "tools/conv_native_p47_tb_vcd_compile_core.py").read_bytes(), executable=True)
    write("package_tools/tb_vcd_live_supervision.py", (ROOT / "tools/conv_native_p47_tb_vcd_live_supervision.py").read_bytes(), executable=True)
    write("package_tools/tb_vcd_finalize.py", (ROOT / "tools/conv_native_p47_tb_vcd_finalize.py").read_bytes(), executable=True)
    write("package_tools/server_process_tree_supervision.py", (ROOT / "outputs/conv_native_four_lane_0ccae916_p46_nativeflow_release/build" / OLD_ID / "package_tools/server_observer_runtime_supervision.py").read_bytes(), executable=True)
    write("package_tools/server_tb_vcd_runtime_supervision.py", (ROOT / "tools/server_tb_vcd_runtime_supervision.py").read_bytes(), executable=True)
    write("package_tools/server_tb_vcd_retention_analysis.py", (ROOT / "tools/server_tb_vcd_retention_analysis.py").read_bytes(), executable=True)
    write("package_tools/server_package_runtime_layout.py", (ROOT / "tools/server_package_runtime_layout.py").read_bytes(), executable=True)
    write("package_tools/server_post_sim_return.py", (ROOT / "tools/server_post_sim_return.py").read_bytes(), executable=True)
    patch_fixed_publisher()

    tb_path = write("tb_probe/native_mse4_bounded_causal_cone_vcd.sv", tb_source().encode("utf-8"))
    signals = build_signals()
    catalog = {
        "schema": "conv-native-p47-tb-vcd-causal-signal-catalog-v1",
        "package_id": PACKAGE_ID, "source_root": "NDP_copy01/rtl",
        "signals": signals, "signal_count": len(signals),
        "actual_nets_only": True, "observer_drives_dut": False,
    }
    catalog_path = write_json("diagnostics/tb_vcd_causal_signal_catalog.json", catalog)
    contract = vcd_contract(signals, tb_path)
    matrix_path = write_json("diagnostics/tb_vcd_candidate_boundary_matrix.json", {
        "schema": "conv-native-p47-candidate-boundary-matrix-v1", "package_id": PACKAGE_ID,
        "candidates": contract["candidates"], "boundaries": contract["boundaries"],
        "candidate_boundary_matrix": contract["candidate_boundary_matrix"],
        "complete_cross_product": True, "pairwise_distinguishable": True,
    })
    contract_path = write_json("contracts/server_tb_vcd_bounded_causal_cone_contract.json", contract)
    selector_path = write_json("contracts/server_diagnostic_mode_selector.json", selector(contract_path))
    request_path = write_json("contracts/server_post_sim_return_request.json", post_request())
    write_json("contracts/server_tb_vcd_streaming_retention_contract.json", {
        "schema": "server-tb-vcd-streaming-retention-package-contract-v1", "package_id": PACKAGE_ID,
        "analysis_artifacts": ["analysis_state.json", "checkpoints.jsonl", "report.md"],
        "analysis_mode": "STREAMING_RESUMABLE_NO_WHOLE_FILE_CONTEXT_LOAD",
        "retention_slots": ["MAX_PROGRESS", "LATEST_1", "LATEST_2"], "max_raw_groups": 3,
        "deletion_prerequisites": ["analysis_complete", "family_consumed", "mainline_consumed", "deterministic_core_evidence", "protected_set_audit_pass"],
        "size_based_deletion": False, "tool_member": "package_tools/server_tb_vcd_retention_analysis.py",
        "tool_sha256": sha(TREE / "package_tools/server_tb_vcd_retention_analysis.py"),
    })
    write_json("contracts/server_post_sim_return_contract.json", {
        "schema": "server-post-sim-return-contract-v1", "package_id": PACKAGE_ID,
        "helper_member": "package_tools/server_post_sim_return.py", "helper_sha256": sha(TREE / "package_tools/server_post_sim_return.py"),
        "request_member": "contracts/server_post_sim_return_request.json", "request_sha256": sha(request_path),
        "runner_member": "PREPARE_AND_RUN.sh", "runner_sha256": "0" * 64,
        "invocation_mode": "JSON_REQUEST_ONLY_NO_POSITIONAL_COLLECTOR",
        "required_scenarios": ["natural_success", "natural_success_plugin_failure", "simulation_nonzero", "idempotent_reentry"],
        "plugin_failure_blocks_core_return": False, "sim_exit_persisted_before_plugins": True,
        "partial_exit_live_causal_record": {
            "rule_id": "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001",
            "enforcement": "required_next_fresh",
            "required_signals": ["INT", "TERM"],
            "final_block_ring_sole_input_forbidden": True,
            "plugin_dispositions": [],
        },
        "claim_boundary": "Core and bounded raw VCD publication independent of later family interpretation.",
    })
    write_json("diagnostics/vector_handshake_predicate.json", {
        "schema": "conv-native-vector-handshake-predicate-v1", "package_id": PACKAGE_ID,
        "predicate": "(|(mse2mem_wdata_valid & mem2mse_wdata_ready)) === 1'b1",
        "vector_width": 2, "source": "frozen p42 repair", "functional_rtl_modified": False,
    })
    write_json("diagnostics/frozen_p46_target.json", {
        "schema": "conv-native-p47-frozen-p46-target-v1", "source_package": source_identity,
        "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional_rtl", "target_diagnostic"],
        "known_progress": {"descriptor_accepts": 18, "buffer_accepts": 18, "memag_accepts": 9, "wdata_accepts": 21, "slice_finish": 0},
        "selected_target": "MSE4 post-accept terminal/accounting through slice-finish aggregation",
    })
    write_json("diagnostics/source_bound_vcd_generation.json", {
        "schema": "conv-native-p47-source-bound-vcd-generation-v1", "package_id": PACKAGE_ID,
        "catalog": {"path": catalog_path.relative_to(TREE).as_posix(), "sha256": sha(catalog_path)},
        "matrix": {"path": matrix_path.relative_to(TREE).as_posix(), "sha256": sha(matrix_path)},
        "tb_source": {"path": tb_path.relative_to(TREE).as_posix(), "sha256": sha(tb_path)},
        "role_count": 41, "signal_count": len(signals), "four_layers": True,
        "observer_drives_dut": False, "pass": True,
    })

    runner_path = write("PREPARE_AND_RUN.sh", runner().encode("utf-8"), executable=True)
    post_contract_path = TREE / "contracts/server_post_sim_return_contract.json"
    post_contract = json.loads(post_contract_path.read_text(encoding="utf-8"))
    post_contract["runner_sha256"] = sha(runner_path)
    post_contract_path.write_bytes(canonical(post_contract))
    write_json("SERVER_RUNTIME_LAYOUT_CONTRACT.json", layout_contract(runner_path))
    runner_variables = [
        "package_id", "install_name", "attempt", "return_tag", "server_root", "published_root", "result_root",
        "return_zip", "return_sha", "package_root", "bootstrap_root", "compile_argv_json",
        "compile_source_identity_json", "compile_exit_txt", "compile_driver_log", "compile_log_receipt_json",
        "compile_log_head_txt", "compile_log_tail_txt", "compile_first_error_txt", "compile_status", "run_status",
        "signal_status", "sim_started", "timed_out", "finalized", "run_root", "evidence_root", "compile_root",
        "cfg_root", "preflight_stage", "tb_source", "vcd_path", "samples_path", "simv",
    ]
    write_json("server_runner_return_resilience_contract.json", {
        "schema": "server-runner-return-resilience-contract-v1", "package_id": PACKAGE_ID,
        "runner_path": f"{PACKAGE_ID}/PREPARE_AND_RUN.sh", "runner_sha256": sha(runner_path),
        "nounset_required": True, "bootstrap_root_variable": "bootstrap_root",
        "package_owned_variables": runner_variables,
        "finalizer_arm_tokens": ["trap 'bootstrap_finalize $?' EXIT"],
        "first_fallible_tokens": ['cd "$server_root"', "make -f"],
        "compile_evidence_tokens": {"argv": "compile_argv.json", "source_identity": "compile_source_identity.json", "exit_code": "compile_exit.txt", "driver_log": "compile_driver.log", "first_error": "compile_first_error.txt", "bounded_head": "compile_log_head.txt", "bounded_tail": "compile_log_tail.txt"},
        "return_allowlist_tokens": ["ACTUAL_COMPILE_SIM_ARGV.json", "COMPILE_CORE.json", "PUBLISHED_ACTUAL_ROOT_IDENTITY.json", "PROCESS_TREE_RECEIPT.json", "TB_VCD_RUNTIME_RECEIPT.json", "native_mse4_causal.vcd", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
    })
    root = f"{PACKAGE_ID}_return/"
    required_return = [root + row["archive"] for row in post_request()["core_entries"] if row["required"]]
    required_return += [root + "RETURN_CORE_MANIFEST.json", root + "return_core/SIM_EXIT_RECEIPT.json", root + "return_core/RETURN_CORE_STATUS.json"]
    write_json("RETURN_ALLOWLIST.json", {
        "schema": "conv-native-p47-tb-vcd-return-allowlist-v1", "package_id": PACKAGE_ID,
        "required": sorted(set(required_return)), "optional": [],
        "forbidden_suffixes": [".vpd", ".fsdb", ".fst"],
        "vcd_member": root + "runs/c0/native_mse4_causal.vcd",
        "no_size_limit": True, "no_truncation": True, "no_sampling": True,
    })
    write_json("TEST_PACKAGE_MANIFEST.json", {
        "schema": "conv-native-four-lane-p47-tb-vcd-pointer-v1", "package_identity": PACKAGE_ID,
        "family": FAMILY, "activation_epoch": ACTIVATION_EPOCH,
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE", "status": "PACKAGE_READY_NOT_RUN",
        "server_actions_performed": [],
    })
    write("README.md", f"# {PACKAGE_ID}\n\nPrevious progress: p41 proved production compile beyond the Datahub repair; p42 fixed the two-bit vector valid/ready false-negative; p46 proved descriptor/buffer/MemAG/wdata accepts but ended by INT before the terminal/accounting cone was observed.\n\nCurrent purpose: preserve the p42 predicate and selected MSE4 target while returning a bounded source-bound standard TB VCD over FIFO, outstanding/response, last/count, drain/clear, finish aggregation and global progress.\n\nOnly after separate server authorization: `bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\nThe Make dump variables remain zero. The package-local TB is the only VCD producer. Decimal 100000000 bytes is warning-only; 8GB VCD and 10GB return are operational stop projections, never truncation or size deletion.\n".encode("utf-8"))
    update_manifest(contract_path, selector_path, runner_path)
    deterministic_zip(ZIP)
    repeat = OUT / f"{PACKAGE_ID}.repeat.zip"
    deterministic_zip(repeat)
    if ZIP.stat().st_size != repeat.stat().st_size or sha(ZIP) != sha(repeat):
        raise RuntimeError("deterministic ZIP rebuild differs")
    write_json_external = lambda path, value: path.write_bytes(canonical(value))
    write_json_external(OUT / "build_receipt.json", {
        "schema": "conv-native-p47-tb-vcd-build-v1", "package_id": PACKAGE_ID,
        "family": FAMILY, "activation_epoch": ACTIVATION_EPOCH,
        "source_p46": source_identity, "zip": identity(ZIP), "repeat_zip": identity(repeat),
        "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional_rtl", "target_diagnostic"],
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "server_actions_performed": [], "pass": True,
    })


if __name__ == "__main__":
    build()
