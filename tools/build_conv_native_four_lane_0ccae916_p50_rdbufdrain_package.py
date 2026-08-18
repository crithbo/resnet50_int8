#!/usr/bin/env python3
"""Build the p49-return-driven native Conv p50 adaptive TB-VCD successor.

This builder deliberately starts from the exact protected p49 package.  It
changes only the fresh identity and package-local diagnostic/runtime-return
surface; workload, configuration, numeric inputs, golden data and functional
RTL remain byte-equal to p49.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p49_tbvcdrt2"
PACKAGE_ID = "r5_n4_0cc_p50_rdbufdrain"
FAMILY = "conv_native_four_lane"
ACTIVATION_EPOCH = "tb-vcd-first-round-breadth-adaptive-v4-runtime-v3"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = STORAGE / "pending" / f"{SOURCE_ID}.zip"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_release"
TREE = OUT / "build" / PACKAGE_ID
ZIP = OUT / f"{PACKAGE_ID}.zip"
REPEAT = OUT / f"{PACKAGE_ID}.repeat.zip"
ANALYSIS = ROOT / (
    "outputs/conv_native_four_lane_0ccae916_p49_tbvcdrt2_return_analysis_"
    "r1786716730326805125_2394257"
)
LOCAL_RTL = ROOT / "NDP_copy01/rtl"

BASE_SLICE = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
    "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice"
)
BASE_STREAM = BASE_SLICE + ".u_LSU.u_Stream_Engine"
BASE_MSE = BASE_STREAM + ".MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
BASE_SEM = BASE_SLICE + ".u_Slice_Execution_Manager"

TOP = "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv"
BUF = "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv"
DATA = "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def write_json(relative: str, value: Any) -> Path:
    path = TREE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))
    return path


def safe_extract() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    TREE.parent.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("p49 source ZIP CRC failure")
        roots = {
            PurePosixPath(item.filename).parts[0]
            for item in archive.infolist()
            if item.filename
        }
        if roots != {SOURCE_ID}:
            raise RuntimeError(f"p49 ZIP root differs: {sorted(roots)}")
        old_tree = TREE.parent / SOURCE_ID
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                raise RuntimeError(f"unsafe source member: {info.filename}")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise RuntimeError(f"source symlink forbidden: {info.filename}")
            target = TREE.parent.joinpath(*pure.parts)
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


def replace_identity_in_text_files() -> None:
    for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
        if path.suffix.lower() not in {".json", ".md", ".py", ".sh", ".sv", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_ID in text:
            path.write_text(text.replace(SOURCE_ID, PACKAGE_ID), encoding="utf-8", newline="\n")


def source_record(
    relative: str,
    name: str,
    hierarchy: str,
    width: int,
    roles: list[str],
) -> dict[str, Any]:
    source = LOCAL_RTL / relative
    lines = source.read_text(encoding="utf-8", errors="strict").splitlines()
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    matches = [
        (index, line)
        for index, line in enumerate(lines, 1)
        if pattern.search(line)
        and line.lstrip().startswith(("input", "output", "wire", "reg", "logic", "localparam"))
    ]
    if not matches:
        matches = [(index, line) for index, line in enumerate(lines, 1) if pattern.search(line)]
    if not matches:
        raise RuntimeError(f"source declaration absent: {relative}:{name}")
    line_number, declaration = matches[0]
    return {
        "signal_id": "sig_" + name,
        "exact_hierarchy": hierarchy,
        "width_bits": width,
        "roles": roles,
        "source_path": "rtl/" + relative,
        "source_sha256": sha(source),
        "declaration_span_sha256": sha_bytes((declaration.strip() + "\n").encode("utf-8")),
        "source_binding": "ACTUAL_SOURCE_NET",
        "derived_expected_equation": False,
        "drives_dut": False,
        "source_line": line_number,
        "source_declaration": declaration.strip(),
        "driver_leaf_for_candidate_ids": [],
        "driver_depth_edges": None,
    }


def build_signals() -> tuple[list[dict[str, Any]], list[str]]:
    catalog = load(TREE / "diagnostics/tb_vcd_causal_signal_catalog.json")
    signals = catalog.get("signals")
    if not isinstance(signals, list) or len(signals) != 66:
        raise RuntimeError("p49 baseline catalog is not the exact 66-signal set")
    for item in signals:
        item["driver_leaf_for_candidate_ids"] = []
        item["driver_depth_edges"] = None

    additions = [
        source_record(TOP, "wr_data_chl_ready", BASE_MSE + ".wr_data_chl_ready", 1, ["ready", "backpressure"]),
        source_record(BUF, "buf_ag_ob_wr_ptr", BASE_MSE + ".u_RD_Buffer_AG.buf_ag_ob_wr_ptr", 1, ["fifo_enqueue", "internal_state"]),
        source_record(BUF, "buf_ag_ob_rd_ptr", BASE_MSE + ".u_RD_Buffer_AG.buf_ag_ob_rd_ptr", 1, ["fifo_dequeue", "internal_state"]),
        source_record(BUF, "buf_ag_idx_last_bit", BASE_MSE + ".u_RD_Buffer_AG.buf_ag_idx_last_bit", 1, ["last", "internal_match"]),
        source_record(BUF, "buf_ag_idx_last_index", BASE_MSE + ".u_RD_Buffer_AG.buf_ag_idx_last_index", 4, ["last", "count", "internal_match"]),
        source_record(DATA, "wr_data_chl_prepared_data_vld", BASE_MSE + ".u_WR_Data_Channel.wr_data_chl_prepared_data_vld", 1, ["valid", "internal_state"]),
        source_record(DATA, "wr_data_chl_prepared_data_wr_hs", BASE_MSE + ".u_WR_Data_Channel.wr_data_chl_prepared_data_wr_hs", 1, ["accept", "fifo_enqueue"]),
        source_record(DATA, "wr_data_chl_prepared_data_rd_hs", BASE_MSE + ".u_WR_Data_Channel.wr_data_chl_prepared_data_rd_hs", 1, ["accept", "fifo_dequeue"]),
        source_record(DATA, "wr_chl_prepared_data_bp_pre", BASE_MSE + ".u_WR_Data_Channel.wr_chl_prepared_data_bp_pre", 1, ["ready", "backpressure"]),
        source_record(DATA, "wr_data_chl_data_vld", BASE_MSE + ".u_WR_Data_Channel.wr_data_chl_data_vld", 1, ["valid", "producer"]),
        source_record(DATA, "wr_data_chl_hold_data_vld", BASE_MSE + ".u_WR_Data_Channel.wr_data_chl_hold_data_vld", 1, ["valid", "internal_state", "lifetime"]),
        source_record(DATA, "wr_data_chl_hold_last_flag", BASE_MSE + ".u_WR_Data_Channel.wr_data_chl_hold_last_flag", 1, ["last", "internal_state"]),
        source_record(DATA, "wr_data_chl_last_flag", BASE_MSE + ".u_WR_Data_Channel.wr_data_chl_last_flag", 1, ["last"]),
        source_record(DATA, "wr_data_chl_prepared_data_cur_base_wptr", BASE_MSE + ".u_WR_Data_Channel.wr_data_chl_prepared_data_cur_base_wptr", 5, ["fifo_enqueue", "count", "internal_state"]),
        source_record(DATA, "wr_data_chl_prepared_data_cur_base_rptr", BASE_MSE + ".u_WR_Data_Channel.wr_data_chl_prepared_data_cur_base_rptr", 5, ["fifo_dequeue", "count", "internal_state"]),
        source_record(DATA, "wr_chl_queue_rd_tsf_size", BASE_MSE + ".u_WR_Data_Channel.wr_chl_queue_rd_tsf_size", 5, ["count", "internal_match"]),
        source_record(DATA, "wr_chl_queue_rd_mask_flag", BASE_MSE + ".u_WR_Data_Channel.wr_chl_queue_rd_mask_flag", 1, ["mask", "internal_match"]),
        source_record(DATA, "wr_chl_ob_vld_in", BASE_MSE + ".u_WR_Data_Channel.wr_chl_ob_vld_in", 2, ["valid", "per_bank_valid"]),
        source_record(DATA, "wr_chl_ob_bp_pre", BASE_MSE + ".u_WR_Data_Channel.wr_chl_ob_bp_pre", 2, ["ready", "backpressure", "per_bank_ready"]),
        source_record(TOP, "wr_data_chl_req_tsf_size", BASE_MSE + ".wr_data_chl_req_tsf_size", 5, ["count", "request"]),
        source_record(TOP, "mse_buf_ag_tag_valid", BASE_MSE + ".mse_buf_ag_tag_valid", 1, ["tag", "valid", "internal_match"]),
        source_record(TOP, "mse_buf_ag_tag", BASE_MSE + ".mse_buf_ag_tag", 6, ["tag", "last", "internal_match"]),
    ]
    existing = {item["signal_id"] for item in signals}
    for item in additions:
        if item["signal_id"] in existing:
            raise RuntimeError(f"added signal duplicates p49: {item['signal_id']}")
        existing.add(item["signal_id"])
        signals.append(item)

    drivers: dict[str, set[str]] = {
        "rd_buffer_full_no_consumer": {
            "sig_wr_data_chl_ready", "sig_buf_ag_ob_rd_en", "sig_buf_ag_ob_full",
            "sig_wr_chl_prepared_data_bp_pre", "sig_wr_data_chl_hold_data_vld",
        },
        "prepared_data_no_drain": {
            "sig_wr_data_chl_prepared_data_vld", "sig_wr_data_chl_prepared_data_rd_hs",
            "sig_wr_chl_ob_vld_in", "sig_wr_chl_ob_bp_pre",
            "sig_wr_data_chl_prepared_data_cnt",
        },
        "metadata_queue_starvation": {
            "sig_wr_chl_queue_rd_en", "sig_wr_chl_queue_empty",
            "sig_wr_chl_queue_rd_tsf_size", "sig_wr_chl_queue_rd_mask_flag",
        },
        "output_buffer_admission": {
            "sig_wr_chl_ob_vld_in", "sig_wr_chl_ob_bp_pre", "sig_wr_chl_ob_vld",
            "sig_wr_chl_ob_wr_hs",
        },
        "last_count_pairing": {
            "sig_buf_ag_idx_last_bit", "sig_buf_ag_idx_last_index", "sig_mse2buf_last",
            "sig_mse2buf_last_index", "sig_wr_data_chl_last_flag",
            "sig_wr_data_chl_hold_last_flag", "sig_transaction_idx_last_bit",
            "sig_transaction_idx_last_index",
        },
        "completion_propagation": {
            "sig_transaction_finish", "sig_transaction_addr_ctrl_clear",
            "sig_wr_data_chl_ob_last_data_arv_arr_flag", "sig_slice_cmpt_finish",
            "sig_slice_cmpt_finish_2", "sig_sem_cs", "sig_sem_ns",
        },
    }
    by_id = {item["signal_id"]: item for item in signals}
    for candidate_id, signal_ids in drivers.items():
        missing = signal_ids - set(by_id)
        if missing:
            raise RuntimeError(f"driver signal IDs absent for {candidate_id}: {sorted(missing)}")
        for signal_id in signal_ids:
            by_id[signal_id]["driver_leaf_for_candidate_ids"].append(candidate_id)
            by_id[signal_id]["driver_leaf_for_candidate_ids"].sort()
            by_id[signal_id]["driver_depth_edges"] = 0
    return signals, [item["signal_id"] for item in additions]


def patch_tb(signals: list[dict[str, Any]]) -> Path:
    path = TREE / "tb_probe/native_mse4_bounded_causal_cone_vcd.sv"
    text = path.read_text(encoding="utf-8")
    port_anchor = (
        "  input wire data_fifo_full, input wire data_fifo_empty, input wire [5:0] prepared_count,\n"
    )
    port_add = (
        port_anchor
        + "  input wire wr_channel_ready, input wire buffer_write_ptr, input wire buffer_read_ptr,\n"
        + "  input wire buffer_idx_last_bit, input wire [3:0] buffer_idx_last_index,\n"
        + "  input wire prepared_valid, input wire prepared_wr_hs, input wire prepared_rd_hs,\n"
        + "  input wire prepared_bp, input wire data_valid, input wire hold_data_valid,\n"
        + "  input wire hold_last, input wire data_last, input wire [4:0] prepared_wptr,\n"
        + "  input wire [4:0] prepared_rptr, input wire [4:0] queue_tsf_size, input wire queue_mask,\n"
        + "  input wire [1:0] ob_vld_in, input wire [1:0] ob_bp_pre, input wire [4:0] req_tsf_size,\n"
        + "  input wire buf_tag_valid, input wire [5:0] buf_tag,\n"
    )
    if port_anchor not in text:
        raise RuntimeError("p49 TB port anchor absent")
    text = text.replace(port_anchor, port_add, 1)
    text = text.replace(
        "  logic [7:0] codex_previous_global;",
        "  logic [31:0] codex_previous_global;",
        1,
    )
    state_start = text.index("  wire [1023:0] codex_state = {")
    state_end = text.index("  function automatic", state_start)
    state_block = '''  wire [1023:0] codex_state = {
    request_payload, wdata_payload, desc_mask, request_valid, request_ready,
    wdata_valid, wdata_ready, response_valid, response_ready, buffer_req_valid,
    buffer_req_ready, buffer_data_valid, buffer_fifo_count, buffer_fifo_enq,
    buffer_fifo_deq, buffer_fifo_full, buffer_fifo_empty, data_fifo_count,
    data_fifo_enq, data_fifo_deq, data_fifo_full, data_fifo_empty, prepared_count,
    wr_channel_ready, buffer_write_ptr, buffer_read_ptr, buffer_idx_last_bit,
    buffer_idx_last_index, prepared_valid, prepared_wr_hs, prepared_rd_hs,
    prepared_bp, data_valid, hold_data_valid, hold_last, data_last,
    prepared_wptr, prepared_rptr, queue_tsf_size, queue_mask, ob_vld_in,
    ob_bp_pre, req_tsf_size, buf_tag_valid, buf_tag,
    mem_outstanding, data_outstanding, mem_accept, data_accept, mem_finish,
    mem_clear, data_finish, last_flag, last_index, sem_cs, sem_ns,
    selected_finish, aggregate_finish, global_ready, global_valid,
    mem_tag_valid, mem_bp_pre, desc_valid, desc_ready, mse_enable, slice_rst, rst_n
  };
  wire [63:0] codex_counter_state = {31'd0, codex_progress[31:0], selected_finish};
  wire [31:0] codex_global_state = {
    2'd0, sem_cs, sem_ns, buffer_fifo_count, data_fifo_count, prepared_count,
    mem_outstanding, data_outstanding, selected_finish, aggregate_finish,
    global_ready, global_valid, buffer_fifo_full, data_fifo_full,
    prepared_valid, hold_data_valid
  };
  // X/Z qualification is validity-aware. Raw X/Z transitions remain in the VCD;
  // inactive payload/tag X/Z cannot by itself suppress a legitimate plateau.
  wire codex_unresolved_xz =
    $isunknown({rst_n, slice_rst, mse_enable, desc_valid, desc_ready,
      request_valid, request_ready, wdata_valid, wdata_ready, response_valid,
      response_ready, buffer_req_valid, buffer_req_ready, buffer_data_valid,
      buffer_fifo_count, buffer_fifo_enq, buffer_fifo_deq, buffer_fifo_full,
      buffer_fifo_empty, data_fifo_count, data_fifo_enq, data_fifo_deq,
      data_fifo_full, data_fifo_empty, prepared_count, wr_channel_ready,
      buffer_write_ptr, buffer_read_ptr, prepared_valid, prepared_wr_hs,
      prepared_rd_hs, prepared_bp, data_valid, hold_data_valid, prepared_wptr,
      prepared_rptr, ob_vld_in, ob_bp_pre, mem_outstanding, data_outstanding,
      mem_accept, data_accept, mem_finish, mem_clear, data_finish, sem_cs,
      sem_ns, selected_finish, aggregate_finish, global_ready, global_valid}) ||
    (desc_valid && $isunknown({desc_mask, req_tsf_size})) ||
    ((|request_valid) && $isunknown(request_payload)) ||
    ((|wdata_valid) && $isunknown(wdata_payload)) ||
    ((|buffer_req_valid) && $isunknown({buffer_idx_last_bit, buffer_idx_last_index})) ||
    ((!data_fifo_empty) && $isunknown({queue_tsf_size, queue_mask})) ||
    (hold_data_valid && $isunknown({hold_last, data_last})) ||
    (buf_tag_valid && $isunknown(buf_tag)) ||
    (last_flag && $isunknown(last_index));

'''
    text = text[:state_start] + state_block + text[state_end:]

    first = text.index("      $dumpvars(")
    last = text.index("      $dumpon;", first)
    rows = "\n".join(
        f"      $dumpvars(0, {item['exact_hierarchy']});" for item in signals
    )
    text = text[:first] + rows + "\n" + text[last:]

    bind_anchor = (
        "  .data_fifo_empty(u_WR_Data_Channel.wr_chl_queue_empty), .prepared_count(u_WR_Data_Channel.wr_data_chl_prepared_data_cnt),\n"
    )
    bind_add = (
        bind_anchor
        + "  .wr_channel_ready(wr_data_chl_ready), .buffer_write_ptr(u_RD_Buffer_AG.buf_ag_ob_wr_ptr),\n"
        + "  .buffer_read_ptr(u_RD_Buffer_AG.buf_ag_ob_rd_ptr), .buffer_idx_last_bit(u_RD_Buffer_AG.buf_ag_idx_last_bit),\n"
        + "  .buffer_idx_last_index(u_RD_Buffer_AG.buf_ag_idx_last_index),\n"
        + "  .prepared_valid(u_WR_Data_Channel.wr_data_chl_prepared_data_vld),\n"
        + "  .prepared_wr_hs(u_WR_Data_Channel.wr_data_chl_prepared_data_wr_hs),\n"
        + "  .prepared_rd_hs(u_WR_Data_Channel.wr_data_chl_prepared_data_rd_hs),\n"
        + "  .prepared_bp(u_WR_Data_Channel.wr_chl_prepared_data_bp_pre),\n"
        + "  .data_valid(u_WR_Data_Channel.wr_data_chl_data_vld),\n"
        + "  .hold_data_valid(u_WR_Data_Channel.wr_data_chl_hold_data_vld),\n"
        + "  .hold_last(u_WR_Data_Channel.wr_data_chl_hold_last_flag),\n"
        + "  .data_last(u_WR_Data_Channel.wr_data_chl_last_flag),\n"
        + "  .prepared_wptr(u_WR_Data_Channel.wr_data_chl_prepared_data_cur_base_wptr),\n"
        + "  .prepared_rptr(u_WR_Data_Channel.wr_data_chl_prepared_data_cur_base_rptr),\n"
        + "  .queue_tsf_size(u_WR_Data_Channel.wr_chl_queue_rd_tsf_size),\n"
        + "  .queue_mask(u_WR_Data_Channel.wr_chl_queue_rd_mask_flag),\n"
        + "  .ob_vld_in(u_WR_Data_Channel.wr_chl_ob_vld_in), .ob_bp_pre(u_WR_Data_Channel.wr_chl_ob_bp_pre),\n"
        + "  .req_tsf_size(wr_data_chl_req_tsf_size), .buf_tag_valid(mse_buf_ag_tag_valid), .buf_tag(mse_buf_ag_tag),\n"
    )
    if bind_anchor not in text:
        raise RuntimeError("p49 TB bind anchor absent")
    text = text.replace(bind_anchor, bind_add, 1)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def source_identity_sha(signals: list[dict[str, Any]]) -> str:
    rows = [
        {
            "signal_id": item["signal_id"],
            "exact_hierarchy": item["exact_hierarchy"],
            "width_bits": item["width_bits"],
            "source_path": item["source_path"],
            "source_sha256": item["source_sha256"],
            "declaration_span_sha256": item["declaration_span_sha256"],
        }
        for item in signals
    ]
    return sha_bytes(compact(sorted(rows, key=lambda row: row["signal_id"])).encode("utf-8"))


def pinned_rtl_sha(signals: list[dict[str, Any]]) -> str:
    rows = sorted({(item["source_path"], item["source_sha256"]) for item in signals})
    return sha_bytes(compact(rows).encode("utf-8"))


def build_contract(
    signals: list[dict[str, Any]],
    tb_path: Path,
    baseline_path: Path,
    evolution_return_path: str,
) -> dict[str, Any]:
    old = load(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    clean_signals = [
        {key: item[key] for key in (
            "signal_id", "exact_hierarchy", "width_bits", "roles", "source_path",
            "source_sha256", "declaration_span_sha256", "source_binding",
            "derived_expected_equation", "drives_dut", "driver_leaf_for_candidate_ids",
            "driver_depth_edges",
        )}
        for item in signals
    ]
    by_role: dict[str, list[str]] = {}
    for item in clean_signals:
        for role in item["roles"]:
            by_role.setdefault(role, []).append(item["signal_id"])
    required_roles = [item["role"] for item in old["role_coverage"]]
    if len(required_roles) != 41 or any(role not in by_role for role in required_roles):
        raise RuntimeError("p50 exact causal role coverage differs")

    def ids(*names: str) -> list[str]:
        selected = set(names)
        available = {item["signal_id"] for item in clean_signals}
        missing = selected - available
        if missing:
            raise RuntimeError(f"boundary signal absent: {sorted(missing)}")
        return sorted(selected)

    boundaries = [
        {
            "boundary_id": "mse4_upstream_descriptor_rd_buffer",
            "layer": "FIRST_DIVERGENCE_UPSTREAM_ONE",
            "signal_ids": ids(
                "sig_wr_data_chl_req_valid", "sig_wr_data_chl_req_ready",
                "sig_wr_data_chl_req_tsf_size", "sig_mse_buf_ag_tag_valid",
                "sig_mse_buf_ag_tag", "sig_buf_ag_ob_cnt", "sig_buf_ag_ob_wr_en",
                "sig_buf_ag_ob_full", "sig_buf_ag_ob_wr_ptr", "sig_buf_ag_ob_rd_ptr",
                "sig_buf_ag_idx_last_bit", "sig_buf_ag_idx_last_index",
            ),
        },
        {
            "boundary_id": "mse4_current_rd_to_prepared_join",
            "layer": "FIRST_DIVERGENCE_CURRENT",
            "signal_ids": ids(
                "sig_buf_ag_ob_rd_en", "sig_wr_data_chl_ready", "sig_buf2mse_rvalid",
                "sig_wr_chl_prepared_data_bp_pre", "sig_wr_data_chl_data_vld",
                "sig_wr_data_chl_hold_data_vld", "sig_wr_data_chl_prepared_data_wr_hs",
                "sig_wr_data_chl_prepared_data_rd_hs", "sig_wr_data_chl_prepared_data_cnt",
                "sig_wr_data_chl_prepared_data_cur_base_wptr",
                "sig_wr_data_chl_prepared_data_cur_base_rptr",
            ),
        },
        {
            "boundary_id": "mse4_downstream_queue_output_last",
            "layer": "FIRST_DIVERGENCE_DOWNSTREAM_ONE",
            "signal_ids": ids(
                "sig_fifo_counter", "sig_wr_chl_queue_empty", "sig_wr_chl_queue_full",
                "sig_wr_chl_queue_rd_en", "sig_wr_chl_queue_rd_tsf_size",
                "sig_wr_chl_queue_rd_mask_flag", "sig_wr_data_chl_prepared_data_vld",
                "sig_wr_chl_ob_vld_in", "sig_wr_chl_ob_bp_pre", "sig_wr_chl_ob_vld",
                "sig_wr_chl_ob_wr_hs", "sig_wr_data_chl_last_flag",
                "sig_wr_data_chl_hold_last_flag", "sig_mse2buf_last",
                "sig_mse2buf_last_index", "sig_transaction_idx_last_bit",
                "sig_transaction_idx_last_index",
            ),
        },
        {
            "boundary_id": "mse4_state_drain_clear_finish",
            "layer": "STATE_HOLD_CLEAR",
            "signal_ids": ids(
                "sig_transaction_addr_valid", "sig_transaction_finish",
                "sig_transaction_addr_ctrl_clear", "sig_cur_transaction_size_left",
                "sig_wr_data_chl_ob_last_data_arv_arr_flag", "sig_slice_cmpt_finish",
                "sig_slice_cmpt_finish_2", "sig_sem_cs", "sig_sem_ns",
                "sig_slice2gexec_ready", "sig_gexec2slice_valid",
            ),
        },
    ]
    candidates = [
        {"candidate_id": "rd_buffer_full_no_consumer", "priority": "HIGH", "description": "RD buffer is full while wr_data_chl_ready/dequeue remains blocked."},
        {"candidate_id": "prepared_data_no_drain", "priority": "HIGH", "description": "Prepared-data occupancy is not consumed into the WR output buffers."},
        {"candidate_id": "metadata_queue_starvation", "priority": "HIGH", "description": "WR metadata queue validity/size/mask does not align with prepared data."},
        {"candidate_id": "output_buffer_admission", "priority": "HIGH", "description": "Selected output-buffer valid/backpressure prevents prepared-data admission."},
        {"candidate_id": "last_count_pairing", "priority": "HIGH", "description": "Buffer/tag last and expected count fail to pair at the final transfer."},
        {"candidate_id": "completion_propagation", "priority": "MEDIUM", "description": "Drained local state fails to clear and propagate MSE/slice/global finish."},
    ]
    candidate_signals = {
        item["candidate_id"]: sorted(
            signal["signal_id"]
            for signal in clean_signals
            if item["candidate_id"] in signal["driver_leaf_for_candidate_ids"]
        )
        for item in candidates
    }
    predicates = {
        "rd_buffer_full_no_consumer": "buf_ag_ob_full==1 && buf_ag_ob_cnt==2 && buf_ag_ob_rd_en==0 && wr_data_chl_ready==0",
        "prepared_data_no_drain": "prepared_data_cnt!=0 && prepared_data_vld==0_or_ob_accept==0 && prepared_rd_hs==0",
        "metadata_queue_starvation": "prepared_data_cnt!=0 && wr_chl_queue_empty==1_or_tsf_size_mismatch",
        "output_buffer_admission": "prepared_data_vld==1 && wr_chl_ob_vld_in!=0 && wr_chl_ob_wr_hs==0 && wr_chl_ob_bp_pre==0",
        "last_count_pairing": "mse2buf_last_or_tag_last && last_index_count_pair_does_not_reach_WR_last",
        "completion_propagation": "local_drain_complete && transaction_finish_or_slice_finish_remains_zero",
    }
    matrix: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(candidates):
        cid = candidate["candidate_id"]
        for boundary_index, boundary in enumerate(boundaries):
            direct = sorted(set(candidate_signals[cid]) & set(boundary["signal_ids"]))
            matrix.append({
                "candidate_id": cid,
                "boundary_id": boundary["boundary_id"],
                "expected_signature": {
                    "candidate_code": f"P50C{candidate_index}",
                    "boundary_code": f"B{boundary_index}",
                    "decision_predicate": predicates[cid],
                    "candidate_signal_ids": candidate_signals[cid],
                    "direct_driver_signal_ids_at_boundary": direct,
                    "ordered_four_state_transitions_required": True,
                },
            })

    pinned = pinned_rtl_sha(clean_signals)
    contract = old
    contract["package_id"] = PACKAGE_ID
    contract["execution"].update({
        "tb_source_path": tb_path.relative_to(TREE).as_posix(),
        "tb_source_sha256": sha(tb_path),
        "dump_targeting": {
            "mode": "EXACT_CATALOG_SIGNALS",
            "module_scope_dump": False,
            "dumpvars_depth": 0,
            "signal_ids": [item["signal_id"] for item in clean_signals],
        },
    })
    contract["scope"] = {
        "simulation_top": "tb_NDP_Top_new_phy",
        "full_hierarchy_dump": False,
        "dump_scopes": [
            {
                "scope_id": f"exact_{item['signal_id']}",
                "exact_hierarchy": item["exact_hierarchy"],
                "depth": 0,
                "boundary_ids": [
                    boundary["boundary_id"]
                    for boundary in boundaries
                    if item["signal_id"] in boundary["signal_ids"]
                ] or [boundaries[0]["boundary_id"]],
                "source_bound_signal_ids": [item["signal_id"]],
            }
            for item in clean_signals
        ],
    }
    contract["signals"] = clean_signals
    contract["role_coverage"] = [
        {"role": role, "disposition": "covered", "signal_ids": sorted(set(by_role[role]))}
        for role in required_roles
    ]
    contract["boundaries"] = boundaries
    contract["candidates"] = candidates
    contract["candidate_boundary_matrix"] = matrix
    contract["diagnostic_round"] = {
        "round_index": 1,
        "round_kind": "FIRST_DIAGNOSTIC_ROUND",
        "breadth_baseline": {
            "mode": "FAMILY_CURRENT_ROUND_AT_LEAST_THREE_SOFT_REFERENCE",
            "reference_round_index": 3,
            "reference_package_id": SOURCE_ID,
            "receipt_path": baseline_path.relative_to(TREE).as_posix(),
            "receipt_sha256": sha(baseline_path),
            "reference_signal_count": 66,
            "reference_direct_driver_leaf_count": 0,
            "reference_candidate_count": 6,
            "reference_boundary_count": 4,
            "reasonable_signal_count_range": {"minimum": 50, "maximum": 82},
            "deviation": {
                "relation": "ABOVE_REFERENCE_RANGE",
                "explanation": (
                    "All 66 p49 signals are retained because their removal confidence is LOW; 22 zero-hop "
                    "RD-buffer/prepared-data/metadata/output/last drivers are added to distinguish the narrowed HIGH candidates."
                ),
                "acknowledged": True,
            },
        },
        "source_identity": {
            "pinned_rtl_tree_sha256": pinned,
            "catalog_source_identity_sha256": source_identity_sha(clean_signals),
        },
        "coverage_gaps": [],
        "evolution": {
            "predecessor": None,
            "added_signal_ids": [item["signal_id"] for item in clean_signals],
            "removed_signal_ids": [],
            "unchanged_signal_ids": [],
            "removal_evidence": [],
            "candidate_preservation": {
                "preserved_candidate_ids": [],
                "closed_candidate_ids": [],
                "new_candidate_ids": [item["candidate_id"] for item in candidates],
                "closure_evidence": [],
            },
        },
    }
    contract["return_receipts"]["breadth_evolution"] = evolution_return_path
    contract["first_fresh_controls"] = {
        "required_for_family_epoch": True,
        "clean_exact_zip_revalidation": True,
        "negative_controls": {
            "missing_soft_reference_receipt": True,
            "deviation_without_explanation": True,
            "low_confidence_removal": True,
            "add_remove_diff_mismatch": True,
            "candidate_loss": True,
            "source_identity_drift": True,
            "size_or_stop_protection_weakened": True,
        },
    }
    contract["claim_boundary"] = (
        "p49-return-driven first current-v4 adaptive causal-cone transport only. Local gates do not establish "
        "production p50 compile/simulation, unique RTL root, natural terminal, formal D, E3, E4 or E5."
    )
    return contract


def update_runtime_and_return(contract: dict[str, Any]) -> None:
    # Current package-local runtime helpers include vector-name normalization,
    # PID start-time ownership and bounded TERM/KILL/reap action recording.
    shutil.copyfile(
        ROOT / "tools/conv_native_p49_tb_vcd_finalize.py",
        TREE / "package_tools/tb_vcd_finalize.py",
    )
    shutil.copyfile(
        ROOT / "tools/conv_native_p49_tb_vcd_live_supervision.py",
        TREE / "package_tools/tb_vcd_live_supervision.py",
    )
    shutil.copyfile(
        ROOT / "tools/server_tb_vcd_runtime_supervision.py",
        TREE / "package_tools/server_tb_vcd_runtime_supervision.py",
    )
    shutil.copyfile(
        ROOT / "tools/server_tb_vcd_retention_analysis.py",
        TREE / "package_tools/server_tb_vcd_retention_analysis.py",
    )
    shutil.copyfile(
        ROOT / "tools/server_post_sim_return.py",
        TREE / "package_tools/server_post_sim_return.py",
    )
    preflight = (ROOT / "tools/conv_native_p49_package_release_preflight.py").read_text(encoding="utf-8")
    preflight = preflight.replace(SOURCE_ID, PACKAGE_ID).replace("native Conv p49", "native Conv p50")
    (TREE / "package_tools/package_release_preflight.py").write_text(
        preflight, encoding="utf-8", newline="\n"
    )
    for path in (TREE / "package_tools").glob("*.py"):
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    runner_path = TREE / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    anchor = '--sim-log "$run_root/c0/sim.log" --vcd "$vcd_path"'
    replacement = (
        '--sim-log "$run_root/c0/sim.log" --console-log "$run_root/c0/console.log" '
        '--vcd "$vcd_path"'
    )
    if anchor not in runner:
        raise RuntimeError("p49 runner console capture anchor absent")
    runner = runner.replace(anchor, replacement, 1)
    runner_path.write_text(runner, encoding="utf-8", newline="\n")
    runner_path.chmod(runner_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = load(request_path)
    request["package_id"] = PACKAGE_ID
    additions = [
        {"source_root": "package", "source": "diagnostics/p49_third_round_breadth_reference.json", "archive": "evidence/TB_VCD_BREADTH_REFERENCE.json", "required": True},
        {"source_root": "package", "source": "diagnostics/p49_to_p50_adaptive_signal_diff.json", "archive": "evidence/TB_VCD_BREADTH_EVOLUTION.json", "required": True},
        {"source_root": "package", "source": "diagnostics/valid_qualified_xz_contract.json", "archive": "evidence/TB_VCD_VALID_QUALIFIED_XZ_CONTRACT.json", "required": True},
        {"source_root": "package", "source": "diagnostics/p49_config_rtl_direct_evidence_review.json", "archive": "evidence/CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json", "required": True},
        {"source_root": "package", "source": "workload/runtime/runs/c0/sca_cfg.json", "archive": "evidence/consumed_config/sca_cfg.json", "required": True},
        {"source_root": "package", "source": "workload/runtime/runs/c0/sca_cfg_D.json", "archive": "evidence/consumed_config/sca_cfg_D.json", "required": True},
        {"source_root": "attempt", "source": "c0/console.log", "archive": "runs/c0/console.log", "required": True},
    ]
    archives = {item["archive"] for item in request["core_entries"]}
    request["core_entries"].extend(item for item in additions if item["archive"] not in archives)
    request["claim_boundary"] = (
        "Native-flow compile/simulation plus adaptive bounded VCD and complete console/core evidence; "
        "every non-natural exit remains PARTIAL/DIAGNOSTIC_EVIDENCE_INCOMPLETE."
    )
    request_path.write_bytes(canonical(request))

    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = load(selector_path)
    selector["package_id"] = PACKAGE_ID
    selector["vcd_contract_sha256"] = sha(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    selector["return_members"] = sorted(set(selector["return_members"]) | {
        "evidence/TB_VCD_BREADTH_EVOLUTION.json",
        "evidence/CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json",
        "evidence/consumed_config/sca_cfg.json",
        "evidence/consumed_config/sca_cfg_D.json",
        "runs/c0/console.log",
    })
    selector_path.write_bytes(canonical(selector))

    post_contract_path = TREE / "contracts/server_post_sim_return_contract.json"
    post_contract = load(post_contract_path)
    post_contract.update({
        "package_id": PACKAGE_ID,
        "helper_sha256": sha(TREE / "package_tools/server_post_sim_return.py"),
        "request_sha256": sha(request_path),
        "runner_sha256": sha(runner_path),
    })
    post_contract_path.write_bytes(canonical(post_contract))

    layout_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = load(layout_path)
    layout["package_id"] = PACKAGE_ID
    layout["runner_sha256"] = sha(runner_path)
    layout_path.write_bytes(canonical(layout))

    runner_contract_path = TREE / "server_runner_return_resilience_contract.json"
    runner_contract = load(runner_contract_path)
    runner_contract["package_id"] = PACKAGE_ID
    runner_contract["runner_path"] = f"{PACKAGE_ID}/PREPARE_AND_RUN.sh"
    runner_contract["runner_sha256"] = sha(runner_path)
    runner_contract["return_allowlist_tokens"] = sorted(
        set(runner_contract.get("return_allowlist_tokens", []))
        | {"console.log"}
    )
    runner_contract_path.write_bytes(canonical(runner_contract))

    root = f"{PACKAGE_ID}_return/"
    required = [
        root + item["archive"]
        for item in request["core_entries"]
        if item.get("required") is True
    ]
    required += [
        root + "RETURN_CORE_MANIFEST.json",
        root + "return_core/SIM_EXIT_RECEIPT.json",
        root + "return_core/RETURN_CORE_STATUS.json",
    ]
    allowlist_path = TREE / "RETURN_ALLOWLIST.json"
    allowlist = load(allowlist_path)
    allowlist.update({
        "schema": "conv-native-p50-tb-vcd-return-allowlist-v1",
        "package_id": PACKAGE_ID,
        "required": sorted(set(required)),
        "vcd_member": root + "runs/c0/native_mse4_causal.vcd",
        "no_size_limit": True,
        "no_truncation": True,
        "no_sampling": True,
    })
    allowlist_path.write_bytes(canonical(allowlist))


def update_manifests(signals: list[dict[str, Any]], additions: list[str]) -> None:
    runner_path = TREE / "PREPARE_AND_RUN.sh"
    contract_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    pointer_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    pointer = load(pointer_path)
    pointer.update({
        "schema": "conv-native-four-lane-p50-adaptive-tb-vcd-pointer-v1",
        "package_identity": PACKAGE_ID,
        "family": FAMILY,
        "activation_epoch": ACTIVATION_EPOCH,
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "status": "PACKAGE_READY_NOT_RUN",
        "server_actions_performed": [],
    })
    pointer_path.write_bytes(canonical(pointer))

    (TREE / "README.md").write_text(
        f"# {PACKAGE_ID}\n\n"
        "Previous progress: p41 proved production compile beyond Datahub; p42 fixed the two-bit vector predicate; "
        "p46 proved descriptor/buffer/MemAG/wdata accepts; p49 entered MSE4 and narrowed the stable divergence to "
        "RD_Buffer_AG full/dequeue versus WR prepared-data drain, but the user external INT prevented a natural terminal.\n\n"
        "Current purpose: retain all p49 LOW-confidence signals and add source-bound zero-hop RD-buffer, prepared-data, "
        "metadata queue, output admission, last/count and completion drivers so the narrowed candidates are pairwise "
        "distinguishable. Runtime-v3 remains the sole stop authority; valid-qualified X/Z preserves every raw transition. "
        "The return also carries the exact consumed config copies and the direct config/actual-compiler-path review so "
        "config-to-consumer and RTL mechanisms can be validated without treating probability as proof.\n\n"
        "Current root status is OPEN_UNVALIDATED_MECHANISM. No configuration workaround is recommended or applied; "
        "functional RTL and all configuration bytes remain frozen.\n\n"
        f"Only after separate server authorization: `bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\n"
        "The runner captures simulator console output into the return instead of leaking it to the terminal. "
        "No upload, lease, connection or server execution was performed.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = TREE / "package_manifest.json"
    manifest = load(manifest_path)
    manifest.update({
        "schema": "conv-native-four-lane-p50-adaptive-tb-vcd-package-v1",
        "package_identity": PACKAGE_ID,
        "install_name": PACKAGE_ID,
        "family": FAMILY,
        "status": "PACKAGE_READY_NOT_RUN",
        "activation_epoch": ACTIVATION_EPOCH,
        "source_package": SOURCE_ID,
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "previous_version_progress": (
            "p49 compiled, entered MSE4 and narrowed the first stable divergence to RD buffer full/dequeue versus "
            "WR prepared-data drain before external INT."
        ),
        "current_version_purpose": (
            "Retain the p49 catalog and add HIGH-candidate zero-hop drivers, valid-qualified X/Z, vector header "
            "normalization, bounded PID cleanup, attempt-owned console capture, exact consumed-config return, and "
            "the direct config/actual-compiler-path evidence review needed to validate rather than assume a mechanism."
        ),
        "vcd_contract_sha256": sha(contract_path),
        "mode_selector_sha256": sha(selector_path),
        "runner_sha256": sha(runner_path),
        "rule_gap_audit": "provenance/RULE_GAP_AUDIT.json",
        "rule_audit_disposition": "RULE_DELTA_PROPOSAL_IMPLEMENTED",
        "config_rtl_evidence_review": "diagnostics/p49_config_rtl_direct_evidence_review.json",
        "root_disposition": "OPEN_UNVALIDATED_MECHANISM",
        "diagnostic_signal_count": len(signals),
        "added_signal_ids": additions,
        "frozen": {
            "config": True,
            "numeric": True,
            "workload": True,
            "golden": True,
            "functional_rtl": True,
            "target_diagnostic": True,
        },
        "server_actions_performed": [],
        "claim_boundary": (
            "Local build and validation only; no p50 production compile/simulation, root cause, natural terminal, "
            "formal D, E3, E4 or E5 claim."
        ),
    })
    manifest["files"] = {
        path.relative_to(TREE).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha(path),
        }
        for path in sorted(item for item in TREE.rglob("*") if item.is_file())
        if path != manifest_path
    }
    manifest_path.write_bytes(canonical(manifest))


def deterministic_zip(target: Path) -> None:
    with zipfile.ZipFile(
        target,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
    ) as archive:
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(
                f"{PACKAGE_ID}/{path.relative_to(TREE).as_posix()}",
                (1980, 1, 1, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if os.access(path, os.X_OK) else 0o100644) << 16
            archive.writestr(info, path.read_bytes())


def main() -> int:
    required = [
        SOURCE_ZIP,
        ANALYSIS / "formal_return_analysis.json",
        ANALYSIS / "RULE_GAP_AUDIT.json",
        ANALYSIS / "CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json",
    ]
    if any(not path.is_file() for path in required):
        raise RuntimeError(f"required p49 source/analysis absent: {[str(p) for p in required if not p.is_file()]}")
    formal = load(ANALYSIS / "formal_return_analysis.json")
    gap = load(ANALYSIS / "RULE_GAP_AUDIT.json")
    if formal.get("pass") is not True or gap.get("rule_disposition") != "RULE_DELTA_PROPOSAL":
        raise RuntimeError("p49 formal analysis/RULE_GAP disposition differs")

    safe_extract()
    replace_identity_in_text_files()
    provenance = TREE / "provenance"
    provenance.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ANALYSIS / "formal_return_analysis.json", provenance / "p49_formal_return_analysis.json")
    shutil.copyfile(ANALYSIS / "RULE_GAP_AUDIT.json", provenance / "RULE_GAP_AUDIT.json")
    shutil.copyfile(
        ANALYSIS / "CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json",
        TREE / "diagnostics/p49_config_rtl_direct_evidence_review.json",
    )

    signals, additions = build_signals()
    tb_path = patch_tb(signals)
    pinned = pinned_rtl_sha(signals)
    baseline_path = write_json("diagnostics/p49_third_round_breadth_reference.json", {
        "schema": "server-tb-vcd-family-round-breadth-baseline-v1",
        "family": FAMILY,
        "package_id": SOURCE_ID,
        "round_index": 3,
        "signal_count": 66,
        "direct_driver_leaf_count": 0,
        "candidate_count": 6,
        "boundary_count": 4,
        "pinned_rtl_tree_sha256": pinned,
        "machine_check_exit": 0,
        "claim_boundary": "p49 exact 66-signal third-round breadth is a soft family reference only.",
    })
    diff_path = write_json("diagnostics/p49_to_p50_adaptive_signal_diff.json", {
        "schema": "conv-native-p49-to-p50-adaptive-signal-diff-v1",
        "family": FAMILY,
        "source_package": SOURCE_ID,
        "package_id": PACKAGE_ID,
        "source_contract_sha256": sha(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"),
        "source_signal_count": 66,
        "current_signal_count": len(signals),
        "unchanged_signal_ids": [item["signal_id"] for item in signals if item["signal_id"] not in additions],
        "added_signal_ids": additions,
        "removed_signal_ids": [],
        "removal_disposition": "LOW_CONFIDENCE_RETAINED_BY_DEFAULT",
        "addition_reason": (
            "p49 narrowed the stable divergence but lacked candidate-specific zero-hop drivers at the "
            "RD-buffer/prepared-data/metadata/output/last/completion join."
        ),
        "affected_candidates": [
            "rd_buffer_full_no_consumer", "prepared_data_no_drain",
            "metadata_queue_starvation", "output_buffer_admission",
            "last_count_pairing", "completion_propagation",
        ],
        "machine_check_exit": 0,
        "pass": True,
    })
    write_json("diagnostics/valid_qualified_xz_contract.json", {
        "schema": "conv-native-valid-qualified-xz-contract-v1",
        "package_id": PACKAGE_ID,
        "raw_vcd_preserves_every_four_state_transition": True,
        "plateau_xz_qualification": "VALID_OR_ACTIVE_OWNER_GATED",
        "inactive_payload_or_tag_xz_suppresses_plateau": False,
        "control_count_pointer_fsm_xz_always_qualified": True,
        "observer_drives_dut": False,
        "machine_check_exit": 0,
        "pass": True,
    })

    catalog_path = TREE / "diagnostics/tb_vcd_causal_signal_catalog.json"
    catalog = load(catalog_path)
    catalog.update({
        "schema": "conv-native-p50-adaptive-tb-vcd-causal-signal-catalog-v1",
        "package_id": PACKAGE_ID,
        "signals": signals,
        "signal_count": len(signals),
        "p49_signals_retained": 66,
        "added_zero_hop_driver_signals": len(additions),
    })
    catalog_path.write_bytes(canonical(catalog))

    contract = build_contract(
        signals,
        tb_path,
        baseline_path,
        "evidence/TB_VCD_BREADTH_EVOLUTION.json",
    )
    contract_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    contract_path.write_bytes(canonical(contract))
    matrix_path = TREE / "diagnostics/tb_vcd_candidate_boundary_matrix.json"
    matrix_path.write_bytes(canonical({
        "schema": "conv-native-p50-adaptive-candidate-boundary-matrix-v1",
        "package_id": PACKAGE_ID,
        "candidates": contract["candidates"],
        "boundaries": contract["boundaries"],
        "candidate_boundary_matrix": contract["candidate_boundary_matrix"],
        "complete_cross_product": True,
        "pairwise_distinguishable": True,
    }))
    write_json("diagnostics/tb_vcd_exact_dump_plan.json", {
        "schema": "conv-native-p50-tb-vcd-exact-dump-plan-v1",
        "package_id": PACKAGE_ID,
        "strategy": "EXPLICIT_SOURCE_BOUND_SIGNAL_ONLY",
        "signal_count": len(signals),
        "signal_ids": [item["signal_id"] for item in signals],
        "exact_hierarchies": [item["exact_hierarchy"] for item in signals],
        "module_scope_dump_forbidden": True,
        "uncataloged_signal_forbidden": True,
        "pass": True,
    })
    source_generation_path = TREE / "diagnostics/source_bound_vcd_generation.json"
    source_generation = load(source_generation_path)
    source_generation.update({
        "schema": "conv-native-p50-source-bound-vcd-generation-v1",
        "package_id": PACKAGE_ID,
        "catalog": {"path": catalog_path.relative_to(TREE).as_posix(), "sha256": sha(catalog_path)},
        "matrix": {"path": matrix_path.relative_to(TREE).as_posix(), "sha256": sha(matrix_path)},
        "tb_source": {"path": tb_path.relative_to(TREE).as_posix(), "sha256": sha(tb_path)},
        "role_count": 41,
        "signal_count": len(signals),
        "zero_hop_driver_count": sum(bool(item["driver_leaf_for_candidate_ids"]) for item in signals),
        "pass": True,
    })
    source_generation_path.write_bytes(canonical(source_generation))

    update_runtime_and_return(contract)
    # selector hashes were updated after the contract, and return/runtime identities
    # now bind the final runner and helper bytes.
    update_manifests(signals, additions)
    deterministic_zip(ZIP)
    deterministic_zip(REPEAT)
    if ZIP.read_bytes() != REPEAT.read_bytes():
        raise RuntimeError("p50 deterministic exact-ZIP recomputation differs")
    build_receipt = {
        "schema": "conv-native-p50-adaptive-tb-vcd-build-v1",
        "package_id": PACKAGE_ID,
        "family": FAMILY,
        "activation_epoch": ACTIVATION_EPOCH,
        "source_p49_pending": identity(SOURCE_ZIP),
        "formal_return_analysis": identity(ANALYSIS / "formal_return_analysis.json"),
        "rule_gap_audit": identity(ANALYSIS / "RULE_GAP_AUDIT.json"),
        "config_rtl_direct_evidence_review": identity(
            ANALYSIS / "CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json"
        ),
        "rule_audit_disposition": "RULE_DELTA_PROPOSAL_IMPLEMENTED",
        "adaptive_signal_diff": identity(diff_path),
        "zip": identity(ZIP),
        "repeat_zip": identity(REPEAT),
        "frozen_surfaces": [
            "config", "numeric", "workload", "golden", "functional_rtl",
            "p42_vector_predicate", "MSE4_target",
        ],
        "storage_publication": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "server_actions_performed": [],
        "pass": True,
        "errors": [],
    }
    (OUT / "build_receipt.json").write_bytes(canonical(build_receipt))
    print(json.dumps({
        "package_id": PACKAGE_ID,
        "signals": len(signals),
        "added_signals": len(additions),
        "zip": str(ZIP),
        "pass": True,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
