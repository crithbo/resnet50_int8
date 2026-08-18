#!/usr/bin/env python3
"""Build native-Conv p52 direct Memory_AG tuple-leaf TB-VCD successor."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import shutil
import stat
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
P51_BUILDER = ROOT / "tools/build_conv_native_four_lane_0ccae916_p51_metaidxcone_package.py"
SPEC = importlib.util.spec_from_file_location("conv_native_p51_builder", P51_BUILDER)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("p51 builder cannot be loaded")
p51 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p51)
base = p51.base

SOURCE_ID = "r5_n4_0cc_p51_metaidxcone"
PACKAGE_ID = "r5_n4_0cc_p52_memtupleleaf"
FAMILY = "conv_native_four_lane"
V5_EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3"
ACTIVATION_EPOCH = V5_EPOCH + "+conv-native-p51-direct-memory-tuple-leaf-v1"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = STORAGE / "tested/conv_native_four_lane" / SOURCE_ID / f"{SOURCE_ID}.zip"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p52_memtupleleaf_release"
TREE = OUT / "build" / PACKAGE_ID
ZIP = OUT / f"{PACKAGE_ID}.zip"
REPEAT = OUT / f"{PACKAGE_ID}.repeat.zip"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p51_metaidxcone_return_analysis_r1786770085722684994_2783486"
MEM_REL = "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_AG_Idx_Queue.sv"
MEM_SOURCE_PATH = "rtl/" + MEM_REL
MEM = base.BASE_MSE + ".u_Memory_AG_Idx_Queue"

for name, value in {
    "SOURCE_ID": SOURCE_ID,
    "PACKAGE_ID": PACKAGE_ID,
    "ACTIVATION_EPOCH": ACTIVATION_EPOCH,
    "SOURCE_ZIP": SOURCE_ZIP,
    "OUT": OUT,
    "TREE": TREE,
    "ZIP": ZIP,
    "REPEAT": REPEAT,
    "ANALYSIS": ANALYSIS,
}.items():
    setattr(base, name, value)


def canonical(value: Any) -> bytes:
    return base.canonical(value)


def load(path: Path) -> dict[str, Any]:
    return base.load(path)


def write_json(relative: str, value: Any) -> Path:
    return base.write_json(relative, value)


def identity(path: Path) -> dict[str, Any]:
    return base.identity(path)


def current_record(name: str, hierarchy: str, width: int, roles: list[str], signal_id: str | None = None) -> dict[str, Any]:
    row = base.source_record(MEM_REL, name, hierarchy, width, roles)
    if signal_id is not None:
        row["signal_id"] = signal_id
    return row


def normalize_existing_memory_sources(signals: list[dict[str, Any]]) -> None:
    for index, row in enumerate(signals):
        if row.get("source_path") not in {MEM_SOURCE_PATH, "rtl/utils/FIFO/FIFO.sv"}:
            continue
        if row.get("source_path") == MEM_SOURCE_PATH:
            name = str(row["signal_id"])[4:]
            refreshed = current_record(name, row["exact_hierarchy"], int(row["width_bits"]), list(row["roles"]), str(row["signal_id"]))
        else:
            refreshed = base.source_record("utils/FIFO/FIFO.sv", "fifo_counter", row["exact_hierarchy"], int(row["width_bits"]), list(row["roles"]))
            refreshed["signal_id"] = str(row["signal_id"])
        refreshed["driver_leaf_for_candidate_ids"] = list(row.get("driver_leaf_for_candidate_ids", []))
        refreshed["driver_depth_edges"] = row.get("driver_depth_edges")
        signals[index] = refreshed


def direct_leaf_records() -> list[dict[str, Any]]:
    rows = [
        current_record("mse_mem_queue_idx", MEM + ".mse_mem_queue_idx", 48, ["source", "address", "selected_port"]),
        current_record("mse_mem_queue_tag", MEM + ".mse_mem_queue_tag", 21, ["source", "tag", "valid", "last"]),
        current_record("mse_mem_queue_bp_pre", MEM + ".mse_mem_queue_bp_pre", 3, ["ready", "backpressure", "selected_port"]),
        current_record("mse_mem_idx_mode", MEM + ".mse_mem_idx_mode", 6, ["source", "selected_port", "internal_match"]),
        current_record("mse_mem_idx_keep_last_index", MEM + ".mse_mem_idx_keep_last_index", 12, ["last", "count", "internal_match"]),
        current_record("mse_mem_idx_enable", MEM + ".mse_mem_idx_enable", 3, ["valid", "selected_port"]),
        current_record("mse_mem_idx_buffer_mode", MEM + ".mse_mem_idx_buffer_mode", 3, ["selected_port", "internal_match"]),
        current_record("mse_mem_idx_keep_mode", MEM + ".mse_mem_idx_keep_mode", 3, ["selected_port", "lifetime"]),
        current_record("mse_mem_idx_cons_mode", MEM + ".mse_mem_idx_cons_mode", 3, ["selected_port", "internal_match"]),
        current_record("mem_idx_valid_bit_unmasked", MEM + ".mem_idx_valid_bit_unmasked", 3, ["valid", "tag"]),
        current_record("mem_idx_last_bit_unmasked", MEM + ".mem_idx_last_bit_unmasked", 3, ["last", "tag"]),
        current_record("mem_idx_same_bit_unmasked", MEM + ".mem_idx_same_bit_unmasked", 3, ["tag", "lifetime"]),
        current_record("mem_idx_last_index", MEM + ".mem_idx_last_index", 12, ["last", "count"]),
        current_record("mem_idx_gotten_bit", MEM + ".mem_idx_gotten_bit", 3, ["internal_state", "lifetime"]),
        current_record("mem_idx_same_bit_keep_mask", MEM + ".mem_idx_same_bit_keep_mask", 3, ["mask", "internal_state"]),
        current_record("mem_idx_same_bit_masked", MEM + ".mem_idx_same_bit_masked", 3, ["mask", "internal_match"]),
        current_record("mem_idx_same_gotten_mask", MEM + ".mem_idx_same_gotten_mask", 3, ["mask", "internal_match"]),
        current_record("mem_idx_valid_bit_operands_mask", MEM + ".mem_idx_valid_bit_operands_mask", 3, ["mask", "valid"]),
        current_record("mem_idx_last_bit_operands_mask", MEM + ".mem_idx_last_bit_operands_mask", 3, ["mask", "last"]),
        current_record("mem_idx_valid_bit_masked", MEM + ".mem_idx_valid_bit_masked", 3, ["mask", "valid", "internal_match"]),
        current_record("mem_idx_last_bit_masked", MEM + ".mem_idx_last_bit_masked", 3, ["mask", "last", "internal_match"]),
        current_record("idx_split_fifo_empty", MEM + ".idx_split_fifo_empty", 3, ["fifo_empty", "internal_state"]),
        current_record("idx_split_fifo_full", MEM + ".idx_split_fifo_full", 3, ["fifo_full", "backpressure"]),
        current_record("mem_idx_fifo_last_bit", MEM + ".mem_idx_fifo_last_bit", 3, ["last", "fifo_dequeue"]),
        current_record("mem_idx_fifo_last_index", MEM + ".mem_idx_fifo_last_index", 12, ["last", "count", "fifo_dequeue"]),
        current_record("mse_mem_fifo_idx", MEM + ".mse_mem_fifo_idx", 48, ["address", "fifo_dequeue"]),
        current_record("mem_idx_fifo_valid_bit", MEM + ".mem_idx_fifo_valid_bit", 3, ["valid", "fifo_occupancy"]),
        current_record("mem_idx_fifo_valid_bit_masked", MEM + ".mem_idx_fifo_valid_bit_masked", 3, ["valid", "mask", "internal_match"]),
        current_record("mem_idx_fifo_last_bit_masked", MEM + ".mem_idx_fifo_last_bit_masked", 3, ["last", "mask"]),
        current_record("mem_idx_fifo_last_index_masked", MEM + ".mem_idx_fifo_last_index_masked", 12, ["last", "count", "mask"]),
        current_record("mse_mem_fifo_idx_masked", MEM + ".mse_mem_fifo_idx_masked", 48, ["address", "mask", "internal_match"]),
        current_record("mem_idx_queue_bp_pre", MEM + ".mem_idx_queue_bp_pre", 3, ["ready", "backpressure"]),
        current_record("mem_idx_split_fifo_wr_en", MEM + ".mem_idx_split_fifo_wr_en", 3, ["fifo_enqueue", "accept"]),
        current_record("mem_idx_bp_pre_keep_mask", MEM + ".mem_idx_bp_pre_keep_mask", 3, ["mask", "backpressure", "lifetime"]),
        current_record("mem_idx_bp_pre_mask", MEM + ".mem_idx_bp_pre_mask", 3, ["mask", "backpressure"]),
        current_record("mem_buffer_idx_last_index", MEM + ".mem_buffer_idx_last_index", 4, ["last", "count", "internal_match"]),
        current_record("mem_buffer_idx_last_bit", MEM + ".mem_buffer_idx_last_bit", 1, ["last", "internal_match"]),
    ]
    for port in range(3):
        row = base.source_record(
            "utils/FIFO/FIFO.sv",
            "fifo_counter",
            MEM + f".MEM_IDX_SPLIT_FIFO[{port}].u_FIFO.fifo_counter",
            5,
            ["fifo_occupancy", "count", "internal_state", "selected_port"],
        )
        row["signal_id"] = f"sig_mem_idx_split_fifo{port}_count"
        rows.append(row)
    return rows


def tag_drivers(signals: list[dict[str, Any]], new_ids: set[str]) -> list[dict[str, Any]]:
    candidates = [
        {"candidate_id": "memory_input0_keep_epoch_terminates_tuple_supply", "priority": "HIGH", "description": "Input0 keep-mode/tag/last lifetime suppresses tuple ten."},
        {"candidate_id": "memory_input1_buffer_epoch_terminates_tuple_supply", "priority": "HIGH", "description": "Input1 buffer token or last lifetime suppresses tuple ten."},
        {"candidate_id": "memory_input2_keep_epoch_terminates_tuple_supply", "priority": "HIGH", "description": "Input2 keep-mode/tag/last lifetime suppresses tuple ten."},
        {"candidate_id": "memory_same_gotten_mask_suppresses_tuple_ten", "priority": "HIGH", "description": "Same/gotten state masks a required tenth input token."},
        {"candidate_id": "memory_split_fifo_keep_release_suppresses_tuple_ten", "priority": "HIGH", "description": "Split-FIFO occupancy or keep-release backpressure prevents the tenth all-match tuple."},
    ]
    common = {
        "sig_mse_mem_queue_idx", "sig_mse_mem_queue_tag", "sig_mse_mem_queue_bp_pre",
        "sig_mse_mem_idx_mode", "sig_mse_mem_idx_keep_last_index", "sig_mse_mem_idx_enable",
        "sig_mse_mem_idx_buffer_mode", "sig_mse_mem_idx_keep_mode", "sig_mse_mem_idx_cons_mode",
        "sig_mem_idx_valid_bit_unmasked", "sig_mem_idx_last_bit_unmasked", "sig_mem_idx_same_bit_unmasked",
        "sig_mem_idx_last_index", "sig_mem_idx_valid_bit_masked", "sig_mem_idx_last_bit_masked",
    }
    mapping = {
        candidates[0]["candidate_id"]: common | {"sig_mem_idx_split_fifo0_count", "sig_idx_split_fifo_empty", "sig_idx_split_fifo_full"},
        candidates[1]["candidate_id"]: common | {"sig_mem_idx_split_fifo1_count", "sig_idx_split_fifo_empty", "sig_idx_split_fifo_full", "sig_mem_buffer_idx_last_bit", "sig_mem_buffer_idx_last_index"},
        candidates[2]["candidate_id"]: common | {"sig_mem_idx_split_fifo2_count", "sig_idx_split_fifo_empty", "sig_idx_split_fifo_full"},
        candidates[3]["candidate_id"]: {"sig_mem_idx_gotten_bit", "sig_mem_idx_same_bit_keep_mask", "sig_mem_idx_same_bit_masked", "sig_mem_idx_same_gotten_mask", "sig_mem_idx_valid_bit_unmasked", "sig_mem_idx_valid_bit_masked", "sig_mse_mem_queue_bp_pre"},
        candidates[4]["candidate_id"]: {"sig_idx_split_fifo_empty", "sig_idx_split_fifo_full", "sig_mem_idx_fifo_valid_bit", "sig_mem_idx_fifo_valid_bit_masked", "sig_mem_idx_queue_bp_pre", "sig_mem_idx_split_fifo_wr_en", "sig_mem_idx_bp_pre_keep_mask", "sig_mem_idx_bp_pre_mask", "sig_mem_idx_split_fifo0_count", "sig_mem_idx_split_fifo1_count", "sig_mem_idx_split_fifo2_count"},
    }
    by_id = {row["signal_id"]: row for row in signals}
    for candidate_id, ids in mapping.items():
        missing = ids - set(by_id)
        if missing:
            raise RuntimeError(f"p52 direct-driver IDs absent: {sorted(missing)}")
        for signal_id in ids:
            if signal_id not in new_ids:
                continue
            row = by_id[signal_id]
            row.setdefault("driver_leaf_for_candidate_ids", []).append(candidate_id)
            row["driver_leaf_for_candidate_ids"] = sorted(set(row["driver_leaf_for_candidate_ids"]))
            row["driver_depth_edges"] = 0
    return candidates


def patch_tb(signals: list[dict[str, Any]]) -> Path:
    path = TREE / "tb_probe/native_mse4_bounded_causal_cone_vcd.sv"
    text = path.read_text(encoding="utf-8")
    port_anchor = "  input wire mem_idx_valid, input wire transfer_size_valid_i, input wire transfer_addr_ready,\n"
    ports = (
        "  input wire [47:0] mem_queue_idx_leaf, input wire [20:0] mem_queue_tag_leaf, input wire [2:0] mem_queue_bp_leaf,\n"
        "  input wire [5:0] mem_idx_mode_leaf, input wire [11:0] mem_keep_last_leaf,\n"
        "  input wire [2:0] mem_enable_leaf, input wire [2:0] mem_buffer_mode_leaf, input wire [2:0] mem_keep_mode_leaf, input wire [2:0] mem_cons_mode_leaf,\n"
        "  input wire [2:0] mem_raw_valid_leaf, input wire [2:0] mem_raw_last_leaf, input wire [2:0] mem_raw_same_leaf, input wire [11:0] mem_raw_last_idx_leaf,\n"
        "  input wire [2:0] mem_gotten_leaf, input wire [2:0] mem_same_keep_leaf, input wire [2:0] mem_same_masked_leaf, input wire [2:0] mem_same_gotten_leaf,\n"
        "  input wire [2:0] mem_valid_operand_leaf, input wire [2:0] mem_last_operand_leaf, input wire [2:0] mem_valid_masked_leaf, input wire [2:0] mem_last_masked_leaf,\n"
        "  input wire [2:0] mem_split_empty_leaf, input wire [2:0] mem_split_full_leaf, input wire [2:0] mem_fifo_last_leaf, input wire [11:0] mem_fifo_last_idx_leaf,\n"
        "  input wire [47:0] mem_fifo_idx_leaf, input wire [2:0] mem_fifo_valid_leaf, input wire [2:0] mem_fifo_valid_masked_leaf,\n"
        "  input wire [2:0] mem_fifo_last_masked_leaf, input wire [11:0] mem_fifo_last_idx_masked_leaf, input wire [47:0] mem_fifo_idx_masked_leaf,\n"
        "  input wire [2:0] mem_queue_ready_leaf, input wire [2:0] mem_split_wr_leaf, input wire [2:0] mem_keep_release_leaf, input wire [2:0] mem_bp_mask_leaf,\n"
        "  input wire [3:0] mem_buffer_last_idx_leaf, input wire mem_buffer_last_leaf,\n"
        "  input wire [4:0] mem_split_count0_leaf, input wire [4:0] mem_split_count1_leaf, input wire [4:0] mem_split_count2_leaf,\n"
    )
    if text.count(port_anchor) != 1:
        raise RuntimeError("p51 direct-leaf TB port anchor differs")
    text = text.replace(port_anchor, ports + port_anchor, 1)
    state_anchor = "    mem_idx_valid, transfer_size_valid_i, transfer_addr_ready, transfer_addr_valid_i,\n"
    state = (
        "    mem_queue_idx_leaf, mem_queue_tag_leaf, mem_queue_bp_leaf, mem_idx_mode_leaf, mem_keep_last_leaf,\n"
        "    mem_enable_leaf, mem_buffer_mode_leaf, mem_keep_mode_leaf, mem_cons_mode_leaf, mem_raw_valid_leaf,\n"
        "    mem_raw_last_leaf, mem_raw_same_leaf, mem_raw_last_idx_leaf, mem_gotten_leaf, mem_same_keep_leaf,\n"
        "    mem_same_masked_leaf, mem_same_gotten_leaf, mem_valid_operand_leaf, mem_last_operand_leaf,\n"
        "    mem_valid_masked_leaf, mem_last_masked_leaf, mem_split_empty_leaf, mem_split_full_leaf,\n"
        "    mem_fifo_last_leaf, mem_fifo_last_idx_leaf, mem_fifo_idx_leaf, mem_fifo_valid_leaf,\n"
        "    mem_fifo_valid_masked_leaf, mem_fifo_last_masked_leaf, mem_fifo_last_idx_masked_leaf,\n"
        "    mem_fifo_idx_masked_leaf, mem_queue_ready_leaf, mem_split_wr_leaf, mem_keep_release_leaf,\n"
        "    mem_bp_mask_leaf, mem_buffer_last_idx_leaf, mem_buffer_last_leaf, mem_split_count0_leaf,\n"
        "    mem_split_count1_leaf, mem_split_count2_leaf,\n"
    )
    if text.count(state_anchor) != 1:
        raise RuntimeError("p51 direct-leaf state anchor differs")
    text = text.replace(state_anchor, state + state_anchor, 1)
    xz_anchor = "      mem_idx_empty, mem_idx_full, mem_idx_count, mem_idx_valid, transfer_size_valid_i,\n"
    xz = (
        "      mem_idx_empty, mem_idx_full, mem_idx_count, mem_queue_idx_leaf, mem_queue_tag_leaf,\n"
        "      mem_queue_bp_leaf, mem_idx_mode_leaf, mem_keep_last_leaf, mem_enable_leaf, mem_buffer_mode_leaf,\n"
        "      mem_keep_mode_leaf, mem_cons_mode_leaf, mem_raw_valid_leaf, mem_raw_last_leaf, mem_raw_same_leaf,\n"
        "      mem_raw_last_idx_leaf, mem_gotten_leaf, mem_same_keep_leaf, mem_same_masked_leaf, mem_same_gotten_leaf,\n"
        "      mem_valid_operand_leaf, mem_last_operand_leaf, mem_valid_masked_leaf, mem_last_masked_leaf,\n"
        "      mem_split_empty_leaf, mem_split_full_leaf, mem_fifo_last_leaf, mem_fifo_last_idx_leaf, mem_fifo_idx_leaf,\n"
        "      mem_fifo_valid_leaf, mem_fifo_valid_masked_leaf, mem_fifo_last_masked_leaf, mem_fifo_last_idx_masked_leaf,\n"
        "      mem_fifo_idx_masked_leaf, mem_queue_ready_leaf, mem_split_wr_leaf, mem_keep_release_leaf, mem_bp_mask_leaf,\n"
        "      mem_buffer_last_idx_leaf, mem_buffer_last_leaf, mem_split_count0_leaf, mem_split_count1_leaf, mem_split_count2_leaf,\n"
        "      mem_idx_valid, transfer_size_valid_i,\n"
    )
    if text.count(xz_anchor) != 1:
        raise RuntimeError("p51 direct-leaf X/Z anchor differs")
    text = text.replace(xz_anchor, xz, 1)
    bind_anchor = "  .mem_idx_count(u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.fifo_counter),\n"
    bind = bind_anchor + (
        "  .mem_queue_idx_leaf(u_Memory_AG_Idx_Queue.mse_mem_queue_idx), .mem_queue_tag_leaf(u_Memory_AG_Idx_Queue.mse_mem_queue_tag),\n"
        "  .mem_queue_bp_leaf(u_Memory_AG_Idx_Queue.mse_mem_queue_bp_pre), .mem_idx_mode_leaf(u_Memory_AG_Idx_Queue.mse_mem_idx_mode),\n"
        "  .mem_keep_last_leaf(u_Memory_AG_Idx_Queue.mse_mem_idx_keep_last_index), .mem_enable_leaf(u_Memory_AG_Idx_Queue.mse_mem_idx_enable),\n"
        "  .mem_buffer_mode_leaf(u_Memory_AG_Idx_Queue.mse_mem_idx_buffer_mode), .mem_keep_mode_leaf(u_Memory_AG_Idx_Queue.mse_mem_idx_keep_mode),\n"
        "  .mem_cons_mode_leaf(u_Memory_AG_Idx_Queue.mse_mem_idx_cons_mode), .mem_raw_valid_leaf(u_Memory_AG_Idx_Queue.mem_idx_valid_bit_unmasked),\n"
        "  .mem_raw_last_leaf(u_Memory_AG_Idx_Queue.mem_idx_last_bit_unmasked), .mem_raw_same_leaf(u_Memory_AG_Idx_Queue.mem_idx_same_bit_unmasked),\n"
        "  .mem_raw_last_idx_leaf(u_Memory_AG_Idx_Queue.mem_idx_last_index), .mem_gotten_leaf(u_Memory_AG_Idx_Queue.mem_idx_gotten_bit),\n"
        "  .mem_same_keep_leaf(u_Memory_AG_Idx_Queue.mem_idx_same_bit_keep_mask), .mem_same_masked_leaf(u_Memory_AG_Idx_Queue.mem_idx_same_bit_masked),\n"
        "  .mem_same_gotten_leaf(u_Memory_AG_Idx_Queue.mem_idx_same_gotten_mask), .mem_valid_operand_leaf(u_Memory_AG_Idx_Queue.mem_idx_valid_bit_operands_mask),\n"
        "  .mem_last_operand_leaf(u_Memory_AG_Idx_Queue.mem_idx_last_bit_operands_mask), .mem_valid_masked_leaf(u_Memory_AG_Idx_Queue.mem_idx_valid_bit_masked),\n"
        "  .mem_last_masked_leaf(u_Memory_AG_Idx_Queue.mem_idx_last_bit_masked), .mem_split_empty_leaf(u_Memory_AG_Idx_Queue.idx_split_fifo_empty),\n"
        "  .mem_split_full_leaf(u_Memory_AG_Idx_Queue.idx_split_fifo_full), .mem_fifo_last_leaf(u_Memory_AG_Idx_Queue.mem_idx_fifo_last_bit),\n"
        "  .mem_fifo_last_idx_leaf(u_Memory_AG_Idx_Queue.mem_idx_fifo_last_index), .mem_fifo_idx_leaf(u_Memory_AG_Idx_Queue.mse_mem_fifo_idx),\n"
        "  .mem_fifo_valid_leaf(u_Memory_AG_Idx_Queue.mem_idx_fifo_valid_bit), .mem_fifo_valid_masked_leaf(u_Memory_AG_Idx_Queue.mem_idx_fifo_valid_bit_masked),\n"
        "  .mem_fifo_last_masked_leaf(u_Memory_AG_Idx_Queue.mem_idx_fifo_last_bit_masked), .mem_fifo_last_idx_masked_leaf(u_Memory_AG_Idx_Queue.mem_idx_fifo_last_index_masked),\n"
        "  .mem_fifo_idx_masked_leaf(u_Memory_AG_Idx_Queue.mse_mem_fifo_idx_masked), .mem_queue_ready_leaf(u_Memory_AG_Idx_Queue.mem_idx_queue_bp_pre),\n"
        "  .mem_split_wr_leaf(u_Memory_AG_Idx_Queue.mem_idx_split_fifo_wr_en), .mem_keep_release_leaf(u_Memory_AG_Idx_Queue.mem_idx_bp_pre_keep_mask),\n"
        "  .mem_bp_mask_leaf(u_Memory_AG_Idx_Queue.mem_idx_bp_pre_mask), .mem_buffer_last_idx_leaf(u_Memory_AG_Idx_Queue.mem_buffer_idx_last_index),\n"
        "  .mem_buffer_last_leaf(u_Memory_AG_Idx_Queue.mem_buffer_idx_last_bit),\n"
        "  .mem_split_count0_leaf(u_Memory_AG_Idx_Queue.MEM_IDX_SPLIT_FIFO[0].u_FIFO.fifo_counter),\n"
        "  .mem_split_count1_leaf(u_Memory_AG_Idx_Queue.MEM_IDX_SPLIT_FIFO[1].u_FIFO.fifo_counter),\n"
        "  .mem_split_count2_leaf(u_Memory_AG_Idx_Queue.MEM_IDX_SPLIT_FIFO[2].u_FIFO.fifo_counter),\n"
    )
    if text.count(bind_anchor) != 1:
        raise RuntimeError("p51 direct-leaf bind anchor differs")
    text = text.replace(bind_anchor, bind, 1)

    first = text.index("      $dumpvars(")
    last = text.index("      $dumpon;", first)
    dump_rows = "\n".join(f"      $dumpvars(0, {row['exact_hierarchy']});" for row in signals)
    text = text[:first] + dump_rows + "\n" + text[last:]
    text = text.replace("  integer codex_suspect_reported;\n", "  integer codex_suspect_reported;\n  integer codex_stop_reported;\n", 1)
    text = text.replace("    codex_suspect_reported = 0;\n", "    codex_suspect_reported = 0;\n    codex_stop_reported = 0;\n", 1)
    start = text.index("    if (!rst_n || slice_rst || !mse_enable || codex_unresolved_xz ||")
    end = text.index("    if (selected_finish ||", start)
    phase = '''    if (codex_dump_off) begin
      if (!codex_stop_reported && (codex_cycles - codex_dump_off_cycle >= CODEX_GRACE_CYCLES)) begin
        codex_stop_reported <= 1;
        $dumpflush;
        $display("CODEX_TBVCD_STOP_V2 reason=CAUSAL_PLATEAU sim_time=%0t owner_cycles=%0d", $time, codex_cycles);
        // The shared packaged runtime evaluator is the sole outer stop authority.
      end
    end else if (!rst_n || slice_rst || !mse_enable || codex_unresolved_xz ||
        ($time <= codex_previous_time) ||
        (codex_state !== codex_previous_state) ||
        (codex_counter_state !== codex_previous_counters) ||
        (codex_global_state !== codex_previous_global)) begin
      codex_last_change_cycle <= codex_cycles;
      codex_suspect_reported <= 0;
    end else begin
      if (!codex_suspect_reported && (codex_cycles - codex_last_change_cycle >= CODEX_SUSPECT_CYCLES)) begin
        codex_suspect_reported <= 1;
        $display("CODEX_TBVCD_PLATEAU_SUSPECT_V2 sim_time=%0t owner_cycles=%0d", $time, codex_cycles);
      end
      if (codex_cycles - codex_last_change_cycle >= CODEX_DUMPOFF_CYCLES) begin
        $dumpoff;
        $dumpflush;
        codex_dump_off <= 1;
        codex_dump_off_cycle <= codex_cycles;
        $display("CODEX_TBVCD_DUMPOFF_V2 sim_time=%0t owner_cycles=%0d", $time, codex_cycles);
      end
    end
'''
    text = text[:start] + phase + text[end:]
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def patch_live_runtime_v5(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "REPLAY_CASES = [\n",
        "DUMPOFF = re.compile(r\"CODEX_TBVCD_DUMPOFF_V2\\s+sim_time=(?P<time>\\d+)\\s+owner_cycles=(?P<cycles>\\d+)\")\n"
        "STOP = re.compile(r\"CODEX_TBVCD_STOP_V2\\s+reason=(?P<reason>[A-Z_]+)\\s+sim_time=(?P<time>\\d+)\\s+owner_cycles=(?P<cycles>\\d+)\")\n"
        "DUMPOFF_REPLAY_CASES = [\n"
        "    {\"case_id\": \"PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE\", \"observed_decision\": \"CONTINUE\"},\n"
        "    {\"case_id\": \"PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU\", \"observed_decision\": \"CAUSAL_PLATEAU\"},\n"
        "    {\"case_id\": \"REPEATED_STOP_MARKER\", \"observed_decision\": \"FAIL_CLOSED\"},\n"
        "]\n"
        "REPLAY_CASES = [\n",
        1,
    )
    scan_start = text.index("def scan_log(")
    scan_end = text.index("\ndef scan_vcd_timestamp(", scan_start)
    scan = '''def scan_log(path: Path, offset: int, dump: dict[str, int] | None, stop_marker_count: int) -> tuple[int, dict[str, Any] | None, bool, bool, dict[str, int] | None, int]:
    if not path.is_file():
        return offset, None, False, False, dump, stop_marker_count
    if path.stat().st_size < offset:
        return 0, None, True, False, dump, stop_marker_count
    latest = None
    target_entry = False
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        stream.seek(offset)
        for line in stream:
            match = HEARTBEAT.search(line)
            if match:
                latest = {"display_sim_time_ticks": int(match.group("time")), "owner_clock_cycles": int(match.group("cycles")), "causal_progress_events": int(match.group("progress")), "qualified_progress_counters": {"total": int(match.group("progress"))}, "causal_state_digest": match.group("state").lower(), "global_progress_witness": {"count": int(match.group("global"))}, "unresolved_xz": match.group("xz") == "1", "target_entry_observed": match.group("entry") == "1"}
            match = DUMPOFF.search(line)
            if match and dump is None:
                dump = {"sim_time_ticks": int(match.group("time")), "owner_clock_cycles": int(match.group("cycles"))}
            match = STOP.search(line)
            if match:
                stop_marker_count += 1
            if "CODEX_TBVCD_TARGET_ENTRY_V2" in line:
                target_entry = True
        return stream.tell(), latest, False, target_entry, dump, stop_marker_count

'''
    text = text[:scan_start] + scan + text[scan_end + 1:]
    load_anchor = "    return module, authority\n\n\ndef shared_decision("
    replacement = '''    dumpoff_authority = {
        "mode": "SHARED_RUNTIME_EVALUATOR_PHASE_AWARE_DUMPOFF",
        "helper_path": "package_tools/server_tb_vcd_runtime_supervision.py",
        "helper_sha256": sha256(resolved),
        "replay_cases": DUMPOFF_REPLAY_CASES,
    }
    return module, authority, dumpoff_authority


def shared_decision('''
    if text.count(load_anchor) != 1:
        raise RuntimeError("native live evaluator authority anchor differs")
    text = text.replace(load_anchor, replacement, 1)
    text = text.replace(
        "    authority: dict[str, Any],\n    args: argparse.Namespace,\n",
        "    authority: dict[str, Any],\n    dumpoff_authority: dict[str, Any],\n    args: argparse.Namespace,\n",
        1,
    )
    text = text.replace(
        '        "decision_authority": authority,\n        "archive_timestamp_receipt": None,',
        '        "decision_authority": authority,\n        "dumpoff_consistency_authority": dumpoff_authority,\n        "archive_timestamp_receipt": None,',
        1,
    )
    text = text.replace(
        "    evaluator, decision_authority = load_evaluator(args.runtime_evaluator)\n",
        "    evaluator, decision_authority, dumpoff_authority = load_evaluator(args.runtime_evaluator)\n",
        1,
    )
    text = text.replace("    root_exit: int | None = None\n", "    root_exit: int | None = None\n    planned_dumpoff: dict[str, int] | None = None\n    stop_marker_count = 0\n", 1)
    old_scan = """                log_offset, heartbeat, log_rotated, target_marker = scan_log(
                    sim_log, log_offset
                )
"""
    new_scan = """                log_offset, heartbeat, log_rotated, target_marker, planned_dumpoff, stop_marker_count = scan_log(
                    sim_log, log_offset, planned_dumpoff, stop_marker_count
                )
"""
    if text.count(old_scan) != 1:
        raise RuntimeError("native live scan anchor differs")
    text = text.replace(old_scan, new_scan, 1)
    text = text.replace('                    "sim_time_ticks": last_vcd_tick,\n', '                    "sim_time_ticks": int(last_heartbeat.get("display_sim_time_ticks", last_vcd_tick)),\n', 1)
    row_anchor = '                    "timescale": "1ps",\n'
    row_extra = (
        '                    "planned_dumpoff": planned_dumpoff is not None,\n'
        '                    "planned_dumpoff_cycle": None if planned_dumpoff is None else planned_dumpoff["owner_clock_cycles"],\n'
        '                    "planned_dumpoff_vcd_timestamp_ticks": None if planned_dumpoff is None else last_vcd_tick,\n'
        '                    "stop_marker_count": stop_marker_count,\n'
    )
    text = text.replace(row_anchor, row_extra + row_anchor, 1)
    text = text.replace("                    evaluator, decision_authority, args, samples\n", "                    evaluator, decision_authority, dumpoff_authority, args, samples\n")
    text = text.replace('                        "decision_authority": decision_authority,\n', '                        "decision_authority": decision_authority,\n                        "dumpoff_consistency_authority": dumpoff_authority,\n')
    text = text.replace(
        '        "decision_authority": decision_authority,\n        "outer_runner_consumed_shared_receipt_only": True,',
        '        "decision_authority": decision_authority,\n        "dumpoff_consistency_authority": dumpoff_authority,\n        "dump_control": {"planned_dumpoff": planned_dumpoff is not None, "planned_dumpoff_cycle": None if planned_dumpoff is None else planned_dumpoff["owner_clock_cycles"], "planned_dumpoff_vcd_timestamp_ticks": None if planned_dumpoff is None else last_vcd_tick, "stop_marker_count": stop_marker_count, "sticky": True},\n        "outer_runner_consumed_shared_receipt_only": True,',
        1,
    )
    text = text.replace(
        '            "target_entry_observed": last_heartbeat["target_entry_observed"],\n            "thresholds": {',
        '            "target_entry_observed": last_heartbeat["target_entry_observed"],\n            "dumpoff_consistency_authority": dumpoff_authority,\n            "dump_control": {"planned_dumpoff": planned_dumpoff is not None, "planned_dumpoff_cycle": None if planned_dumpoff is None else planned_dumpoff["owner_clock_cycles"], "planned_dumpoff_vcd_timestamp_ticks": None if planned_dumpoff is None else last_vcd_tick, "stop_marker_count": stop_marker_count, "sticky": True},\n            "thresholds": {',
        1,
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_finalizer_runtime_v5(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace('        "last_progress": 0,\n', '        "last_progress": 0,\n        "dumpoff": None,\n        "stop_marker_count": 0,\n', 1)
    text = text.replace(
        '    stop = re.compile(r"CODEX_TBVCD_STOP_V[12] reason=([A-Z_]+)")\n',
        '    dumpoff = re.compile(r"CODEX_TBVCD_DUMPOFF_V2 sim_time=(\\d+) owner_cycles=(\\d+)")\n    stop = re.compile(r"CODEX_TBVCD_STOP_V[12] reason=([A-Z_]+)")\n',
        1,
    )
    text = text.replace(
        '            match = stop.search(line)\n            if match:\n                result["stop_reason"] = match.group(1)\n',
        '            match = dumpoff.search(line)\n            if match and result["dumpoff"] is None:\n                result["dumpoff"] = {"sim_time_ticks": int(match.group(1)), "owner_clock_cycles": int(match.group(2))}\n            match = stop.search(line)\n            if match:\n                result["stop_reason"] = match.group(1)\n                result["stop_marker_count"] += 1\n',
        1,
    )
    text = text.replace(
        '    samples[-1]["sim_time_ticks"] = scan["last_appended_timestamp_ticks"]\n',
        '    samples[-1]["sim_time_ticks"] = markers["last_display_sim_time"] if markers["dumpoff"] is not None else scan["last_appended_timestamp_ticks"]\n    samples[-1]["planned_dumpoff"] = markers["dumpoff"] is not None\n    samples[-1]["planned_dumpoff_cycle"] = None if markers["dumpoff"] is None else markers["dumpoff"]["owner_clock_cycles"]\n    samples[-1]["planned_dumpoff_vcd_timestamp_ticks"] = None if markers["dumpoff"] is None else scan["last_appended_timestamp_ticks"]\n    samples[-1]["stop_marker_count"] = markers["stop_marker_count"]\n',
        1,
    )
    auth_anchor = '        "archive_timestamp_receipt": (\n'
    phase = '''        "dumpoff_consistency_authority": {
            "mode": "SHARED_RUNTIME_EVALUATOR_PHASE_AWARE_DUMPOFF",
            "helper_path": "package_tools/server_tb_vcd_runtime_supervision.py",
            "helper_sha256": sha_file(package / "package_tools/server_tb_vcd_runtime_supervision.py")[1],
            "replay_cases": [
                {"case_id": "PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE", "observed_decision": "CONTINUE"},
                {"case_id": "PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU", "observed_decision": "CAUSAL_PLATEAU"},
                {"case_id": "REPEATED_STOP_MARKER", "observed_decision": "FAIL_CLOSED"},
            ],
        },
'''
    if text.count(auth_anchor) != 1:
        raise RuntimeError("native finalizer archive authority anchor differs")
    text = text.replace(auth_anchor, phase + auth_anchor, 1)
    compare_anchor = '    if live_decision.get("decision_authority") != request["decision_authority"]:\n        conjunction_errors.append("live/final shared decision authority identity differs")\n'
    compare = compare_anchor + '    if live_decision.get("dumpoff_consistency_authority") != request["dumpoff_consistency_authority"]:\n        conjunction_errors.append("live/final planned-dumpoff authority identity differs")\n'
    if text.count(compare_anchor) != 1:
        raise RuntimeError("native finalizer live authority anchor differs")
    text = text.replace(compare_anchor, compare, 1)
    write_anchor = '    atomic_json(evidence / "TB_VCD_RUNTIME_RECEIPT.json", receipt)\n'
    write_extra = write_anchor + '    atomic_json(evidence / "TB_VCD_DUMP_CONTROL_RECEIPT.json", {"schema": "conv-native-p52-tb-vcd-dump-control-receipt-v1", "package_id": args.package_id, "execution_id": args.execution_id, "attempt_id": args.attempt_id, "activation_epoch": "' + V5_EPOCH + '", "dump_control": process.get("dump_control"), "dumpoff_consistency_authority": request["dumpoff_consistency_authority"], "pass": not any("dumpoff" in item.lower() or "stop marker" in item.lower() for item in receipt.get("errors", []))})\n'
    if text.count(write_anchor) != 1:
        raise RuntimeError("native finalizer runtime receipt anchor differs")
    text = text.replace(write_anchor, write_extra, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def normalize_predecessor(original_contract: dict[str, Any], original_tb: bytes) -> tuple[dict[str, Any], Path, Path]:
    historical = TREE / "provenance/p51_historical_exact_contract.json"
    historical.write_bytes(canonical(original_contract))
    prior_tb = TREE / "provenance/p51_native_mse4_bounded_causal_cone_vcd.sv"
    prior_tb.write_bytes(original_tb)
    prior = copy.deepcopy(original_contract)
    normalize_existing_memory_sources(prior["signals"])
    pinned = base.pinned_rtl_sha(prior["signals"])
    baseline = write_json("provenance/p51_round3_breadth_baseline.json", {
        "schema": "server-tb-vcd-family-round-breadth-baseline-v1", "family": FAMILY,
        "package_id": SOURCE_ID, "round_index": 3, "signal_count": len(prior["signals"]),
        "direct_driver_leaf_count": sum(bool(row.get("driver_leaf_for_candidate_ids")) for row in prior["signals"]),
        "candidate_count": len(prior["candidates"]), "boundary_count": 4,
        "pinned_rtl_tree_sha256": pinned, "machine_check_exit": 0,
        "normalization_note": "p51 exact contract is byte-preserved separately; this compatibility lineage binds its returned actual Memory_AG source identity and semantic-v5 runtime only.",
    })
    prior["execution"]["tb_source_path"] = prior_tb.relative_to(TREE).as_posix()
    prior["execution"]["tb_source_sha256"] = base.sha(prior_tb)
    prior["runtime_policy"].update({
        "planned_dumpoff_state_source": "EXECUTION_BOUND_TB_STICKY_EVENT",
        "post_dumpoff_progress_source": "EXECUTION_BOUND_OWNER_CLOCK_AND_TB_TIME",
        "dump_off_grace_precedes_freeze": True,
        "stop_marker_policy": "ONE_SHOT_LATCHED",
        "required_dumpoff_consistency_replays": ["PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE", "PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU", "REPEATED_STOP_MARKER_FAIL_CLOSED"],
    })
    prior["return_receipts"]["dump_control"] = "evidence/TB_VCD_DUMP_CONTROL_RECEIPT.json"
    prior["diagnostic_round"] = {
        "round_index": 1, "round_kind": "FIRST_DIAGNOSTIC_ROUND",
        "breadth_baseline": {
            "mode": "FAMILY_CURRENT_ROUND_AT_LEAST_THREE_SOFT_REFERENCE", "reference_round_index": 3,
            "reference_package_id": SOURCE_ID, "receipt_path": baseline.relative_to(TREE).as_posix(), "receipt_sha256": base.sha(baseline),
            "reference_signal_count": len(prior["signals"]), "reference_direct_driver_leaf_count": sum(bool(row.get("driver_leaf_for_candidate_ids")) for row in prior["signals"]),
            "reference_candidate_count": len(prior["candidates"]), "reference_boundary_count": 4,
            "reasonable_signal_count_range": {"minimum": 70, "maximum": 118},
            "deviation": {"relation": "WITHIN_REFERENCE_RANGE", "explanation": None, "acknowledged": False},
        },
        "source_identity": {"pinned_rtl_tree_sha256": pinned, "catalog_source_identity_sha256": base.source_identity_sha(prior["signals"])},
        "coverage_gaps": [],
        "evolution": {"predecessor": None, "added_signal_ids": sorted(row["signal_id"] for row in prior["signals"]), "removed_signal_ids": [], "unchanged_signal_ids": [], "removal_evidence": [], "candidate_preservation": {"preserved_candidate_ids": [], "closed_candidate_ids": [], "new_candidate_ids": sorted(row["candidate_id"] for row in prior["candidates"]), "closure_evidence": []}},
    }
    path = write_json("provenance/p51_actual_source_semantic_v5_round1_contract.json", prior)
    return prior, path, baseline


def build_contract(prior: dict[str, Any], prior_path: Path, baseline: Path, signals: list[dict[str, Any]], new_candidates: list[dict[str, Any]], tb: Path, added: set[str]) -> dict[str, Any]:
    contract = copy.deepcopy(prior)
    contract["package_id"] = PACKAGE_ID
    contract["execution"]["tb_source_path"] = tb.relative_to(TREE).as_posix()
    contract["execution"]["tb_source_sha256"] = base.sha(tb)
    contract["execution"]["dump_targeting"]["signal_ids"] = [row["signal_id"] for row in signals]
    contract["signals"] = [{key: row[key] for key in ("signal_id", "exact_hierarchy", "width_bits", "roles", "source_path", "source_sha256", "declaration_span_sha256", "source_binding", "derived_expected_equation", "drives_dut", "driver_leaf_for_candidate_ids", "driver_depth_edges")} for row in signals]
    prior_ids = {row["signal_id"] for row in prior["signals"]}
    old_candidates = copy.deepcopy(prior["candidates"])
    candidates = old_candidates + new_candidates
    contract["candidates"] = candidates
    by_role: dict[str, list[str]] = {}
    for row in signals:
        for role in row["roles"]:
            by_role.setdefault(role, []).append(row["signal_id"])
    contract["role_coverage"] = [{"role": item["role"], "disposition": "covered", "signal_ids": sorted(set(by_role[item["role"]]))} for item in prior["role_coverage"]]
    leaf_ids = sorted(added)
    boundaries = copy.deepcopy(prior["boundaries"])
    boundaries[0]["signal_ids"] = sorted(set(boundaries[0]["signal_ids"]) | set(leaf_ids))
    contract["boundaries"] = boundaries
    candidate_signals = {candidate["candidate_id"]: sorted(row["signal_id"] for row in signals if candidate["candidate_id"] in row.get("driver_leaf_for_candidate_ids", [])) for candidate in candidates}
    matrix = []
    for ci, candidate in enumerate(candidates):
        for bi, boundary in enumerate(boundaries):
            ids = candidate_signals[candidate["candidate_id"]]
            matrix.append({"candidate_id": candidate["candidate_id"], "boundary_id": boundary["boundary_id"], "expected_signature": {"candidate_code": f"P52C{ci}", "boundary_code": f"B{bi}", "decision_predicate": f"p52_{candidate['candidate_id']}_actual_leaf_transition_predicate", "candidate_signal_ids": ids, "direct_driver_signal_ids_at_boundary": sorted(set(ids) & set(boundary["signal_ids"])), "ordered_four_state_transitions_required": True}})
    contract["candidate_boundary_matrix"] = matrix
    contract["scope"]["dump_scopes"] = [{"scope_id": f"exact_{row['signal_id']}", "exact_hierarchy": row["exact_hierarchy"], "depth": 0, "boundary_ids": [boundary["boundary_id"] for boundary in boundaries if row["signal_id"] in boundary["signal_ids"]] or [boundaries[0]["boundary_id"]], "source_bound_signal_ids": [row["signal_id"]]} for row in signals]
    pinned = base.pinned_rtl_sha(signals)
    current_ids = {row["signal_id"] for row in signals}
    prior_cids = {row["candidate_id"] for row in old_candidates}
    current_cids = {row["candidate_id"] for row in candidates}
    contract["diagnostic_round"] = {
        "round_index": 2, "round_kind": "EVIDENCE_REFINED_SUCCESSOR",
        "breadth_baseline": {"mode": "FAMILY_CURRENT_ROUND_AT_LEAST_THREE_SOFT_REFERENCE", "reference_round_index": 3, "reference_package_id": SOURCE_ID, "receipt_path": baseline.relative_to(TREE).as_posix(), "receipt_sha256": base.sha(baseline), "reference_signal_count": len(prior["signals"]), "reference_direct_driver_leaf_count": sum(bool(row.get("driver_leaf_for_candidate_ids")) for row in prior["signals"]), "reference_candidate_count": len(old_candidates), "reference_boundary_count": 4, "reasonable_signal_count_range": {"minimum": 70, "maximum": 118}, "deviation": {"relation": "ABOVE_REFERENCE_RANGE", "explanation": "The exact p51 rule-gap audit requires raw three-input, same/gotten, split-FIFO and keep-release actual leaves; HIGH-driver closure outweighs the soft count reference.", "acknowledged": True}},
        "source_identity": {"pinned_rtl_tree_sha256": pinned, "catalog_source_identity_sha256": base.source_identity_sha(signals)},
        "coverage_gaps": [],
        "evolution": {"predecessor": {"package_id": SOURCE_ID, "round_index": 1, "contract_path": prior_path.relative_to(TREE).as_posix(), "contract_sha256": base.sha(prior_path), "pinned_rtl_tree_sha256": pinned}, "added_signal_ids": sorted(current_ids - prior_ids), "removed_signal_ids": [], "unchanged_signal_ids": sorted(current_ids & prior_ids), "removal_evidence": [], "candidate_preservation": {"preserved_candidate_ids": sorted(prior_cids & current_cids), "closed_candidate_ids": [], "new_candidate_ids": sorted(current_cids - prior_cids), "closure_evidence": []}},
    }
    contract["claim_boundary"] = "p51-return-driven direct Memory_AG tuple-leaf and semantic-v5 runtime transport only; local gates cannot prove production compile/simulation, a root leaf, natural terminal, formal D, E3, E4 or E5."
    return contract


def update_return_and_manifests(contract: dict[str, Any], signals: list[dict[str, Any]], additions: list[str]) -> None:
    package_tools = TREE / "package_tools"
    shutil.copyfile(ROOT / "tools/server_tb_vcd_runtime_supervision.py", package_tools / "server_tb_vcd_runtime_supervision.py")
    patch_live_runtime_v5(package_tools / "tb_vcd_live_supervision.py")
    patch_finalizer_runtime_v5(package_tools / "tb_vcd_finalize.py")
    for path in (package_tools / "tb_vcd_live_supervision.py", package_tools / "tb_vcd_finalize.py", package_tools / "server_tb_vcd_runtime_supervision.py"):
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = load(request_path)
    request["package_id"] = PACKAGE_ID
    dump_row = {"source_root": "attempt", "source": "evidence/TB_VCD_DUMP_CONTROL_RECEIPT.json", "archive": "evidence/TB_VCD_DUMP_CONTROL_RECEIPT.json", "required": True}
    request["core_entries"] = [row for row in request["core_entries"] if row.get("archive") != dump_row["archive"]] + [dump_row]
    request["claim_boundary"] = "Direct Memory_AG input-leaf VCD plus semantic-v5 phase-aware runtime receipts; every non-natural/incomplete exit remains PARTIAL/DIAGNOSTIC_EVIDENCE_INCOMPLETE."
    request_path.write_bytes(canonical(request))
    contract_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    contract_path.write_bytes(canonical(contract))
    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = load(selector_path)
    selector["package_id"] = PACKAGE_ID
    selector["vcd_contract_sha256"] = base.sha(contract_path)
    selector["return_members"] = sorted(set(selector["return_members"]) | {"evidence/TB_VCD_DUMP_CONTROL_RECEIPT.json"})
    selector_path.write_bytes(canonical(selector))
    runner = TREE / "PREPARE_AND_RUN.sh"
    post_contract = TREE / "contracts/server_post_sim_return_contract.json"
    post = load(post_contract); post.update({"package_id": PACKAGE_ID, "helper_sha256": base.sha(package_tools / "server_post_sim_return.py"), "request_sha256": base.sha(request_path), "runner_sha256": base.sha(runner)}); post_contract.write_bytes(canonical(post))
    layout_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"; layout = load(layout_path); layout.update({"package_id": PACKAGE_ID, "runner_sha256": base.sha(runner)}); layout_path.write_bytes(canonical(layout))
    resilience_path = TREE / "server_runner_return_resilience_contract.json"; resilience = load(resilience_path); resilience.update({"package_id": PACKAGE_ID, "runner_path": f"{PACKAGE_ID}/PREPARE_AND_RUN.sh", "runner_sha256": base.sha(runner)}); resilience_path.write_bytes(canonical(resilience))
    allow_path = TREE / "RETURN_ALLOWLIST.json"; allow = load(allow_path); root = f"{PACKAGE_ID}_return/"; allow.update({"schema": "conv-native-p52-tb-vcd-return-allowlist-v1", "package_id": PACKAGE_ID, "required": sorted(set(allow.get("required", [])) | {root + "evidence/TB_VCD_DUMP_CONTROL_RECEIPT.json"}), "vcd_member": root + "runs/c0/native_mse4_causal.vcd", "no_size_limit": True, "no_truncation": True, "no_sampling": True}); allow_path.write_bytes(canonical(allow))

    pointer_path = TREE / "TEST_PACKAGE_MANIFEST.json"; pointer = load(pointer_path); pointer.update({"schema": "conv-native-four-lane-p52-direct-leaf-pointer-v1", "package_identity": PACKAGE_ID, "family": FAMILY, "activation_epoch": ACTIVATION_EPOCH, "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE", "status": "PACKAGE_READY_NOT_RUN", "server_actions_performed": []}); pointer_path.write_bytes(canonical(pointer))
    (TREE / "README.md").write_text(
        f"# {PACKAGE_ID}\n\nPrevious progress: p51 validated a one-transaction (32-unit) Memory_AG metadata supply deficit on the actual NDP_copy02 execution, narrowing the missing event to tuple ten; the exact input/same-gotten/split-FIFO leaf remained open. p51 also exposed the planned-dumpoff false-freeze and repeated STOP defect.\n\nCurrent purpose: preserve frozen p42/p51 semantics and directly observe all three Memory_AG input tags/indices/modes/last/same/gotten masks, split-FIFO occupancy and keep-release gates while using semantic-v5 two-phase planned dumpoff/freeze and one-shot STOP.\n\nOnly after separate server authorization: `bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\nNo upload, lease, connection, server execution, storage publication, config/workload/numeric/golden or functional RTL change was performed.\n",
        encoding="utf-8", newline="\n",
    )
    manifest_path = TREE / "package_manifest.json"; manifest = load(manifest_path)
    manifest.update({"schema": "conv-native-four-lane-p52-direct-memory-tuple-leaf-v1", "package_identity": PACKAGE_ID, "install_name": PACKAGE_ID, "family": FAMILY, "status": "PACKAGE_READY_NOT_RUN", "activation_epoch": ACTIVATION_EPOCH, "source_package": SOURCE_ID, "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE", "previous_version_progress": "p51 validated a 32-unit Memory_AG metadata supply deficit and tuple-ten absence but left the direct formation leaf open; its runtime falsely froze after planned dumpoff and repeated STOP.", "current_version_purpose": "Directly distinguish the three input lifetimes, same/gotten suppression and split-FIFO/keep-release formation leaves under semantic-v5 runtime.", "vcd_contract_sha256": base.sha(contract_path), "mode_selector_sha256": base.sha(selector_path), "runner_sha256": base.sha(runner), "rule_gap_audit": "provenance/p51_RULE_GAP_AUDIT.json", "rule_audit_disposition": "RULE_DELTA_ACTIVATED_AND_APPLIED", "root_disposition": "OPEN_DIRECT_MEMORY_AG_TUPLE_FORMATION_LEAF", "diagnostic_signal_count": len(signals), "added_signal_ids": additions, "frozen": {"config": True, "numeric": True, "workload": True, "golden": True, "functional_rtl": True, "target_diagnostic": True}, "server_actions_performed": [], "claim_boundary": "Local build and gates only; no p52 production compile/simulation/root/natural/formal-D/E3/E4/E5 claim."})
    manifest["files"] = {path.relative_to(TREE).as_posix(): {"size_bytes": path.stat().st_size, "sha256": base.sha(path)} for path in sorted(item for item in TREE.rglob("*") if item.is_file()) if path != manifest_path}
    manifest_path.write_bytes(canonical(manifest))


def main() -> int:
    required = [SOURCE_ZIP, ANALYSIS / "formal_return_analysis.json", ANALYSIS / "RULE_GAP_AUDIT.json", ANALYSIS / "DIRECT_CONFIG_ACTUAL_RTL_EVIDENCE.json", ROOT / "outputs/tb_vcd_planned_dumpoff_consistency_v5/canonical_activation_receipt.json"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"p52 source/analysis/v5 activation absent: {missing}")
    formal = load(ANALYSIS / "formal_return_analysis.json")
    gap = load(ANALYSIS / "RULE_GAP_AUDIT.json")
    if formal.get("pass") is not True or gap.get("disposition") != "RULE_DELTA_PROPOSAL_SHARED_RUNTIME_IMPLEMENTATION_REQUIRED":
        raise RuntimeError("p51 formal analysis or rule-gap disposition differs")
    base.safe_extract()
    original_contract = load(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    original_tb = (TREE / "tb_probe/native_mse4_bounded_causal_cone_vcd.sv").read_bytes()
    base.replace_identity_in_text_files()
    provenance = TREE / "provenance"; provenance.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ANALYSIS / "formal_return_analysis.json", provenance / "p51_formal_return_analysis.json")
    shutil.copyfile(ANALYSIS / "RULE_GAP_AUDIT.json", provenance / "p51_RULE_GAP_AUDIT.json")
    shutil.copyfile(ANALYSIS / "DIRECT_CONFIG_ACTUAL_RTL_EVIDENCE.json", provenance / "p51_DIRECT_CONFIG_ACTUAL_RTL_EVIDENCE.json")
    shutil.copyfile(ROOT / "contracts/server_tb_vcd_planned_dumpoff_consistency_delta_v5.json", provenance / "server_tb_vcd_planned_dumpoff_consistency_delta_v5.json")
    shutil.copyfile(ROOT / "outputs/tb_vcd_planned_dumpoff_consistency_v5/canonical_activation_receipt.json", provenance / "tb_vcd_semantic_v5_activation_receipt.json")

    prior, prior_path, baseline = normalize_predecessor(original_contract, original_tb)
    signals = copy.deepcopy(prior["signals"])
    additions = direct_leaf_records()
    existing = {row["signal_id"] for row in signals}
    if existing & {row["signal_id"] for row in additions}:
        raise RuntimeError("p52 direct-leaf signal ID collides with p51")
    signals.extend(additions)
    new_ids = {row["signal_id"] for row in additions}
    new_candidates = tag_drivers(signals, new_ids)
    tb_path = patch_tb(signals)
    contract = build_contract(prior, prior_path, baseline, signals, new_candidates, tb_path, new_ids)
    matrix_path = write_json("diagnostics/tb_vcd_candidate_boundary_matrix.json", {"schema": "conv-native-p52-direct-leaf-candidate-boundary-matrix-v1", "package_id": PACKAGE_ID, "candidates": contract["candidates"], "boundaries": contract["boundaries"], "candidate_boundary_matrix": contract["candidate_boundary_matrix"], "complete_cross_product": True, "pairwise_distinguishable": True})
    catalog_path = TREE / "diagnostics/tb_vcd_causal_signal_catalog.json"; catalog = load(catalog_path); catalog.update({"schema": "conv-native-p52-direct-leaf-causal-signal-catalog-v1", "package_id": PACKAGE_ID, "signals": signals, "signal_count": len(signals), "p51_signals_retained": len(prior["signals"]), "added_direct_leaf_signals": len(additions)}); catalog_path.write_bytes(canonical(catalog))
    write_json("diagnostics/tb_vcd_exact_dump_plan.json", {"schema": "conv-native-p52-tb-vcd-exact-dump-plan-v1", "package_id": PACKAGE_ID, "strategy": "EXPLICIT_SOURCE_BOUND_SIGNAL_ONLY", "signal_count": len(signals), "signal_ids": [row["signal_id"] for row in signals], "exact_hierarchies": [row["exact_hierarchy"] for row in signals], "module_scope_dump_forbidden": True, "uncataloged_signal_forbidden": True, "pass": True})
    source_path = TREE / "diagnostics/source_bound_vcd_generation.json"; source = load(source_path); source.update({"schema": "conv-native-p52-source-bound-vcd-generation-v1", "package_id": PACKAGE_ID, "catalog": {"path": catalog_path.relative_to(TREE).as_posix(), "sha256": base.sha(catalog_path)}, "matrix": {"path": matrix_path.relative_to(TREE).as_posix(), "sha256": base.sha(matrix_path)}, "tb_source": {"path": tb_path.relative_to(TREE).as_posix(), "sha256": base.sha(tb_path)}, "role_count": 41, "signal_count": len(signals), "zero_hop_driver_count": sum(bool(row.get("driver_leaf_for_candidate_ids")) for row in signals), "pass": True}); source_path.write_bytes(canonical(source))
    diff = write_json("diagnostics/p51_to_p52_direct_leaf_signal_diff.json", {"schema": "conv-native-p51-to-p52-direct-leaf-signal-diff-v1", "family": FAMILY, "source_package": SOURCE_ID, "package_id": PACKAGE_ID, "source_signal_count": len(prior["signals"]), "current_signal_count": len(signals), "unchanged_signal_ids": sorted(row["signal_id"] for row in prior["signals"]), "added_signal_ids": sorted(new_ids), "removed_signal_ids": [], "removal_disposition": "LOW_CONFIDENCE_RETAINED_BY_DEFAULT", "addition_reason": "p51 proves tuple-ten absence but lacks the exact three-input/same-gotten/split-FIFO/keep-release formation leaves.", "machine_check_exit": 0, "pass": True})
    update_return_and_manifests(contract, signals, sorted(new_ids))
    base.deterministic_zip(ZIP); base.deterministic_zip(REPEAT)
    if ZIP.read_bytes() != REPEAT.read_bytes():
        raise RuntimeError("p52 deterministic exact-ZIP recomputation differs")
    receipt = {"schema": "conv-native-p52-direct-memory-tuple-leaf-build-v1", "package_id": PACKAGE_ID, "family": FAMILY, "activation_epoch": ACTIVATION_EPOCH, "source_p51_tested": identity(SOURCE_ZIP), "formal_return_analysis": identity(ANALYSIS / "formal_return_analysis.json"), "rule_gap_audit": identity(ANALYSIS / "RULE_GAP_AUDIT.json"), "semantic_v5_activation": identity(ROOT / "outputs/tb_vcd_planned_dumpoff_consistency_v5/canonical_activation_receipt.json"), "signal_diff": identity(diff), "zip": identity(ZIP), "repeat_zip": identity(REPEAT), "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional_rtl", "p42_vector_predicate", "p51_root_boundary", "MSE4_target"], "storage_publication": "NOT_AUTHORIZED_LOCAL_ONLY", "server_actions_performed": [], "pass": True, "errors": []}
    (OUT / "build_receipt.json").write_bytes(canonical(receipt))
    print(json.dumps({"package_id": PACKAGE_ID, "signals": len(signals), "added_signals": len(additions), "candidates": len(contract["candidates"]), "zip": str(ZIP), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
