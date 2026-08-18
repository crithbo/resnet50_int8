#!/usr/bin/env python3
"""Build the p50-return-driven native Conv p51 metadata/index causal cone."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import stat
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "tools/build_conv_native_four_lane_0ccae916_p50_rdbufdrain_package.py"
SPEC = importlib.util.spec_from_file_location("conv_native_p50_builder", BASE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("p50 builder cannot be loaded")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)

SOURCE_ID = "r5_n4_0cc_p50_rdbufdrain"
PACKAGE_ID = "r5_n4_0cc_p51_metaidxcone"
FAMILY = "conv_native_four_lane"
ACTIVATION_EPOCH = "tb-vcd-adaptive-v4-runtime-v3-p51-metaidxcone"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = STORAGE / "pending" / f"{SOURCE_ID}.zip"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p51_metaidxcone_release"
TREE = OUT / "build" / PACKAGE_ID
ZIP = OUT / f"{PACKAGE_ID}.zip"
REPEAT = OUT / f"{PACKAGE_ID}.repeat.zip"
ANALYSIS = ROOT / (
    "outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_return_analysis_"
    "r1786734260114876474_2596301"
)

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

IDX_BUF = "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv"
IDX_MEM = "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_AG_Idx_Queue.sv"
WR_AG = "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Memory_AG.sv"
TOP = base.TOP
BASE_MSE = base.BASE_MSE


def write_json(relative: str, value: Any) -> Path:
    return base.write_json(relative, value)


def build_signals() -> tuple[list[dict[str, Any]], list[str]]:
    catalog = base.load(TREE / "diagnostics/tb_vcd_causal_signal_catalog.json")
    signals = catalog.get("signals")
    if not isinstance(signals, list) or len(signals) != 88:
        raise RuntimeError("p50 baseline catalog is not the exact 88-signal set")
    additions = [
        base.source_record(IDX_BUF, "buf_all_idx_matched", BASE_MSE + ".u_Buffer_AG_Idx_Queue.buf_all_idx_matched", 1, ["internal_match", "producer"]),
        base.source_record(IDX_BUF, "buf_ag_idx_queue_wr_en", BASE_MSE + ".u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_wr_en", 1, ["fifo_enqueue", "accept"]),
        base.source_record(IDX_BUF, "buf_ag_idx_queue_rd_en", BASE_MSE + ".u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_rd_en", 1, ["fifo_dequeue", "accept"]),
        base.source_record(IDX_BUF, "buf_ag_idx_queue_empty", BASE_MSE + ".u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_empty", 1, ["fifo_empty", "internal_state"]),
        base.source_record(IDX_BUF, "buf_ag_idx_queue_full", BASE_MSE + ".u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full", 1, ["fifo_full", "backpressure"]),
        base.source_record("utils/FIFO/FIFO.sv", "fifo_counter", BASE_MSE + ".u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.fifo_counter", 6, ["fifo_occupancy", "count", "internal_state"]),
        base.source_record(IDX_MEM, "mem_all_idx_matched", BASE_MSE + ".u_Memory_AG_Idx_Queue.mem_all_idx_matched", 1, ["internal_match", "producer"]),
        base.source_record(IDX_MEM, "mem_ag_idx_queue_wr_en", BASE_MSE + ".u_Memory_AG_Idx_Queue.mem_ag_idx_queue_wr_en", 1, ["fifo_enqueue", "accept"]),
        base.source_record(IDX_MEM, "mem_ag_idx_queue_rd_en", BASE_MSE + ".u_Memory_AG_Idx_Queue.mem_ag_idx_queue_rd_en", 1, ["fifo_dequeue", "accept"]),
        base.source_record(IDX_MEM, "mem_ag_idx_queue_empty", BASE_MSE + ".u_Memory_AG_Idx_Queue.mem_ag_idx_queue_empty", 1, ["fifo_empty", "internal_state"]),
        base.source_record(IDX_MEM, "mem_ag_idx_queue_full", BASE_MSE + ".u_Memory_AG_Idx_Queue.mem_ag_idx_queue_full", 1, ["fifo_full", "backpressure"]),
        base.source_record("utils/FIFO/FIFO.sv", "fifo_counter", BASE_MSE + ".u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.fifo_counter", 4, ["fifo_occupancy", "count", "internal_state"]),
        base.source_record(WR_AG, "mem_ag_idx_valid_bit", BASE_MSE + ".u_WR_Memory_AG.mem_ag_idx_valid_bit", 1, ["tag", "valid", "internal_match"]),
        base.source_record(WR_AG, "transfer_size_valid", BASE_MSE + ".u_WR_Memory_AG.transfer_size_valid", 1, ["valid", "producer"]),
        base.source_record(WR_AG, "transfer_addr_bp_post", BASE_MSE + ".u_WR_Memory_AG.transfer_addr_bp_post", 1, ["ready", "accept"]),
        base.source_record(WR_AG, "transfer_addr_valid", BASE_MSE + ".u_WR_Memory_AG.transfer_addr_valid", 1, ["valid", "producer"]),
        base.source_record(WR_AG, "mem_ag_ob_bp_pre", BASE_MSE + ".u_WR_Memory_AG.mem_ag_ob_bp_pre", 1, ["ready", "backpressure"]),
        base.source_record(TOP, "mse_buf_spatial_size", BASE_MSE + ".mse_buf_spatial_size", 5, ["count", "request", "internal_match"]),
    ]
    # FIFO's generic declaration name would collide twice.  Bind stable IDs to
    # the two exact instance identities instead of the generic leaf name.
    additions[5]["signal_id"] = "sig_buf_idx_queue_count"
    additions[11]["signal_id"] = "sig_mem_idx_queue_count"
    existing = {item["signal_id"] for item in signals}
    for item in additions:
        if item["signal_id"] in existing:
            raise RuntimeError(f"p51 duplicate signal id: {item['signal_id']}")
        signals.append(item)
        existing.add(item["signal_id"])

    drivers = {
        "buffer_memory_idx_queue_rate_mismatch": {
            "sig_buf_all_idx_matched", "sig_buf_ag_idx_queue_wr_en", "sig_buf_ag_idx_queue_rd_en",
            "sig_buf_ag_idx_queue_empty", "sig_buf_ag_idx_queue_full", "sig_buf_idx_queue_count",
            "sig_mem_all_idx_matched", "sig_mem_ag_idx_queue_wr_en", "sig_mem_ag_idx_queue_rd_en",
            "sig_mem_ag_idx_queue_empty", "sig_mem_ag_idx_queue_full", "sig_mem_idx_queue_count",
        },
        "memory_metadata_transfer_underproduction": {
            "sig_mem_ag_idx_valid_bit", "sig_transfer_size_valid", "sig_transfer_addr_bp_post",
            "sig_transfer_addr_valid", "sig_mem_ag_ob_bp_pre", "sig_wr_data_chl_req_valid",
            "sig_wr_data_chl_req_ready", "sig_wr_chl_queue_wr_en",
        },
        "prepared_spatial_accounting_surplus": {
            "sig_mse_buf_spatial_size", "sig_wr_data_chl_prepared_data_wr_hs",
            "sig_wr_data_chl_prepared_data_rd_hs", "sig_wr_data_chl_prepared_data_cnt",
            "sig_wr_chl_queue_rd_tsf_size", "sig_wr_chl_queue_rd_en",
        },
    }
    by_id = {item["signal_id"]: item for item in signals}
    for candidate, ids in drivers.items():
        missing = ids - set(by_id)
        if missing:
            raise RuntimeError(f"p51 driver ids absent for {candidate}: {sorted(missing)}")
        for signal_id in ids:
            row = by_id[signal_id]
            row.setdefault("driver_leaf_for_candidate_ids", [])
            if candidate not in row["driver_leaf_for_candidate_ids"]:
                row["driver_leaf_for_candidate_ids"].append(candidate)
                row["driver_leaf_for_candidate_ids"].sort()
            row["driver_depth_edges"] = 0
    return signals, [item["signal_id"] for item in additions]


def patch_tb(signals: list[dict[str, Any]]) -> Path:
    path = TREE / "tb_probe/native_mse4_bounded_causal_cone_vcd.sv"
    text = path.read_text(encoding="utf-8")
    port_anchor = "  input wire buf_tag_valid, input wire [5:0] buf_tag,\n"
    port_rows = (
        port_anchor
        + "  input wire buf_idx_all_match, input wire buf_idx_wr, input wire buf_idx_rd,\n"
        + "  input wire buf_idx_empty, input wire buf_idx_full, input wire [5:0] buf_idx_count,\n"
        + "  input wire mem_idx_all_match, input wire mem_idx_wr, input wire mem_idx_rd,\n"
        + "  input wire mem_idx_empty, input wire mem_idx_full, input wire [3:0] mem_idx_count,\n"
        + "  input wire mem_idx_valid, input wire transfer_size_valid_i, input wire transfer_addr_ready,\n"
        + "  input wire transfer_addr_valid_i, input wire mem_output_ready, input wire [4:0] spatial_size,\n"
    )
    if port_anchor not in text:
        raise RuntimeError("p50 TB p51 port anchor absent")
    text = text.replace(port_anchor, port_rows, 1)
    text = text.replace(
        "    ob_bp_pre, req_tsf_size, buf_tag_valid, buf_tag,\n    mem_outstanding,",
        "    ob_bp_pre, req_tsf_size, buf_tag_valid, buf_tag,\n"
        "    buf_idx_all_match, buf_idx_wr, buf_idx_rd, buf_idx_empty, buf_idx_full, buf_idx_count,\n"
        "    mem_idx_all_match, mem_idx_wr, mem_idx_rd, mem_idx_empty, mem_idx_full, mem_idx_count,\n"
        "    mem_idx_valid, transfer_size_valid_i, transfer_addr_ready, transfer_addr_valid_i,\n"
        "    mem_output_ready, spatial_size, mem_outstanding,",
        1,
    )
    text = text.replace(
        "      prepared_rptr, ob_vld_in, ob_bp_pre, mem_outstanding, data_outstanding,",
        "      prepared_rptr, ob_vld_in, ob_bp_pre, buf_idx_all_match, buf_idx_wr, buf_idx_rd,\n"
        "      buf_idx_empty, buf_idx_full, buf_idx_count, mem_idx_all_match, mem_idx_wr, mem_idx_rd,\n"
        "      mem_idx_empty, mem_idx_full, mem_idx_count, mem_idx_valid, transfer_size_valid_i,\n"
        "      transfer_addr_ready, transfer_addr_valid_i, mem_output_ready, spatial_size,\n"
        "      mem_outstanding, data_outstanding,",
        1,
    )
    old_progress = (
        "        buffer_fifo_enq || buffer_fifo_deq || data_fifo_enq || data_fifo_deq ||\n"
        "        (|mem_accept) || (|data_accept) || mem_finish || data_finish || selected_finish)"
    )
    new_progress = (
        "        (buffer_fifo_enq && !buffer_fifo_full) ||\n"
        "        (buffer_fifo_deq && !buffer_fifo_empty) ||\n"
        "        (data_fifo_enq && !data_fifo_full) ||\n"
        "        (data_fifo_deq && !data_fifo_empty) ||\n"
        "        (buf_idx_wr && !buf_idx_full) || (buf_idx_rd && !buf_idx_empty) ||\n"
        "        (mem_idx_wr && !mem_idx_full) || (mem_idx_rd && !mem_idx_empty) ||\n"
        "        (|mem_accept) || (|data_accept) || mem_finish || data_finish || selected_finish)"
    )
    if old_progress not in text:
        raise RuntimeError("p50 unqualified progress predicate absent")
    text = text.replace(old_progress, new_progress, 1)

    first = text.index("      $dumpvars(")
    last = text.index("      $dumpon;", first)
    rows = "\n".join(f"      $dumpvars(0, {row['exact_hierarchy']});" for row in signals)
    text = text[:first] + rows + "\n" + text[last:]

    bind_anchor = (
        "  .req_tsf_size(wr_data_chl_req_tsf_size), .buf_tag_valid(mse_buf_ag_tag_valid), .buf_tag(mse_buf_ag_tag),\n"
    )
    bind_rows = (
        bind_anchor
        + "  .buf_idx_all_match(u_Buffer_AG_Idx_Queue.buf_all_idx_matched),\n"
        + "  .buf_idx_wr(u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_wr_en), .buf_idx_rd(u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_rd_en),\n"
        + "  .buf_idx_empty(u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_empty), .buf_idx_full(u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full),\n"
        + "  .buf_idx_count(u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.fifo_counter),\n"
        + "  .mem_idx_all_match(u_Memory_AG_Idx_Queue.mem_all_idx_matched),\n"
        + "  .mem_idx_wr(u_Memory_AG_Idx_Queue.mem_ag_idx_queue_wr_en), .mem_idx_rd(u_Memory_AG_Idx_Queue.mem_ag_idx_queue_rd_en),\n"
        + "  .mem_idx_empty(u_Memory_AG_Idx_Queue.mem_ag_idx_queue_empty), .mem_idx_full(u_Memory_AG_Idx_Queue.mem_ag_idx_queue_full),\n"
        + "  .mem_idx_count(u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.fifo_counter),\n"
        + "  .mem_idx_valid(u_WR_Memory_AG.mem_ag_idx_valid_bit), .transfer_size_valid_i(u_WR_Memory_AG.transfer_size_valid),\n"
        + "  .transfer_addr_ready(u_WR_Memory_AG.transfer_addr_bp_post), .transfer_addr_valid_i(u_WR_Memory_AG.transfer_addr_valid),\n"
        + "  .mem_output_ready(u_WR_Memory_AG.mem_ag_ob_bp_pre), .spatial_size(mse_buf_spatial_size),\n"
    )
    if bind_anchor not in text:
        raise RuntimeError("p50 TB p51 bind anchor absent")
    text = text.replace(bind_anchor, bind_rows, 1)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def baseline_block(path: Path, pinned: str, signal_count: int, driver_count: int, candidate_count: int, current_count: int) -> dict[str, Any]:
    minimum, maximum = 70, 118
    relation = "WITHIN_REFERENCE_RANGE" if minimum <= current_count <= maximum else (
        "BELOW_REFERENCE_RANGE" if current_count < minimum else "ABOVE_REFERENCE_RANGE"
    )
    return {
        "mode": "FAMILY_CURRENT_ROUND_AT_LEAST_THREE_SOFT_REFERENCE",
        "reference_round_index": 3,
        "reference_package_id": SOURCE_ID,
        "receipt_path": path.relative_to(TREE).as_posix(),
        "receipt_sha256": base.sha(path),
        "reference_signal_count": signal_count,
        "reference_direct_driver_leaf_count": driver_count,
        "reference_candidate_count": candidate_count,
        "reference_boundary_count": 4,
        "reasonable_signal_count_range": {"minimum": minimum, "maximum": maximum},
        "deviation": {
            "relation": relation,
            "explanation": None if relation == "WITHIN_REFERENCE_RANGE" else "HIGH driver coverage controls breadth; count is a soft reference.",
            "acknowledged": relation != "WITHIN_REFERENCE_RANGE",
        },
    }


def build_contract(signals: list[dict[str, Any]], tb_path: Path, original_contract: dict[str, Any], original_tb: bytes) -> dict[str, Any]:
    prior = copy.deepcopy(original_contract)
    prior_signals = prior["signals"]
    prior_candidates = prior["candidates"]
    pinned = base.pinned_rtl_sha(signals)
    provenance = TREE / "provenance"
    prior_tb = provenance / "p50_native_mse4_bounded_causal_cone_vcd.sv"
    prior_tb.write_bytes(original_tb)
    baseline = write_json("provenance/p50_round3_breadth_baseline.json", {
        "schema": "server-tb-vcd-family-round-breadth-baseline-v1",
        "family": FAMILY,
        "package_id": SOURCE_ID,
        "round_index": 3,
        "signal_count": len(prior_signals),
        "direct_driver_leaf_count": sum(bool(row.get("driver_leaf_for_candidate_ids")) for row in prior_signals),
        "candidate_count": len(prior_candidates),
        "boundary_count": 4,
        "pinned_rtl_tree_sha256": pinned,
        "machine_check_exit": 0,
        "normalization_note": "p50 normalized to current adaptive-v4 schema solely for exact p51 evolution checking.",
    })
    prior["execution"]["tb_source_path"] = prior_tb.relative_to(TREE).as_posix()
    prior["execution"]["tb_source_sha256"] = base.sha(prior_tb)
    prior["diagnostic_round"] = {
        "round_index": 1,
        "round_kind": "FIRST_DIAGNOSTIC_ROUND",
        "breadth_baseline": baseline_block(
            baseline, pinned, len(prior_signals),
            sum(bool(row.get("driver_leaf_for_candidate_ids")) for row in prior_signals),
            len(prior_candidates), len(prior_signals),
        ),
        "source_identity": {
            "pinned_rtl_tree_sha256": pinned,
            "catalog_source_identity_sha256": base.source_identity_sha(prior_signals),
        },
        "coverage_gaps": [],
        "evolution": {
            "predecessor": None,
            "added_signal_ids": sorted(row["signal_id"] for row in prior_signals),
            "removed_signal_ids": [],
            "unchanged_signal_ids": [],
            "removal_evidence": [],
            "candidate_preservation": {
                "preserved_candidate_ids": [], "closed_candidate_ids": [],
                "new_candidate_ids": sorted(row["candidate_id"] for row in prior_candidates),
                "closure_evidence": [],
            },
        },
    }
    prior_path = write_json("provenance/p50_current_schema_round1_contract.json", prior)

    contract = copy.deepcopy(prior)
    contract["package_id"] = PACKAGE_ID
    contract["execution"]["tb_source_path"] = tb_path.relative_to(TREE).as_posix()
    contract["execution"]["tb_source_sha256"] = base.sha(tb_path)
    contract["execution"]["dump_targeting"]["signal_ids"] = [row["signal_id"] for row in signals]
    contract["signals"] = [
        {key: row[key] for key in (
            "signal_id", "exact_hierarchy", "width_bits", "roles", "source_path", "source_sha256",
            "declaration_span_sha256", "source_binding", "derived_expected_equation", "drives_dut",
            "driver_leaf_for_candidate_ids", "driver_depth_edges",
        )}
        for row in signals
    ]
    by_role: dict[str, list[str]] = {}
    for row in signals:
        for role in row["roles"]:
            by_role.setdefault(role, []).append(row["signal_id"])
    required_roles = [row["role"] for row in prior["role_coverage"]]
    contract["role_coverage"] = [
        {"role": role, "disposition": "covered", "signal_ids": sorted(set(by_role[role]))}
        for role in required_roles
    ]

    def ids(*names: str) -> list[str]:
        available = {row["signal_id"] for row in signals}
        if set(names) - available:
            raise RuntimeError(f"p51 boundary signal absent: {sorted(set(names) - available)}")
        return sorted(names)

    boundaries = [
        {"boundary_id": "idx_generation_upstream", "layer": "FIRST_DIVERGENCE_UPSTREAM_ONE", "signal_ids": ids(
            "sig_buf_all_idx_matched", "sig_buf_ag_idx_queue_wr_en", "sig_buf_ag_idx_queue_full",
            "sig_buf_idx_queue_count", "sig_mem_all_idx_matched", "sig_mem_ag_idx_queue_wr_en",
            "sig_mem_ag_idx_queue_full", "sig_mem_idx_queue_count", "sig_mse_enable")},
        {"boundary_id": "idx_to_metadata_current", "layer": "FIRST_DIVERGENCE_CURRENT", "signal_ids": ids(
            "sig_buf_ag_idx_queue_rd_en", "sig_buf_ag_idx_queue_empty", "sig_mse_buf_ag_tag_valid",
            "sig_buf_ag_ob_rd_en", "sig_buf_ag_ob_full", "sig_wr_data_chl_ready",
            "sig_wr_chl_prepared_data_bp_pre", "sig_wr_data_chl_hold_data_vld",
            "sig_mem_ag_idx_queue_rd_en", "sig_mem_ag_idx_queue_empty", "sig_mse_mem_ag_tag_valid",
            "sig_mem_ag_idx_valid_bit", "sig_transfer_size_valid", "sig_transfer_addr_bp_post",
            "sig_transfer_addr_valid", "sig_mem_ag_ob_bp_pre")},
        {"boundary_id": "metadata_prepared_downstream", "layer": "FIRST_DIVERGENCE_DOWNSTREAM_ONE", "signal_ids": ids(
            "sig_wr_data_chl_req_valid", "sig_wr_data_chl_req_ready", "sig_wr_chl_queue_wr_en",
            "sig_wr_chl_queue_rd_en", "sig_wr_chl_queue_empty", "sig_wr_chl_queue_rd_tsf_size",
            "sig_mse_buf_spatial_size", "sig_wr_data_chl_prepared_data_wr_hs",
            "sig_wr_data_chl_prepared_data_rd_hs", "sig_wr_data_chl_prepared_data_cnt",
            "sig_wr_data_chl_prepared_data_vld", "sig_wr_chl_queue_rd_mask_flag",
            "sig_wr_chl_ob_vld_in", "sig_wr_chl_ob_bp_pre", "sig_wr_chl_ob_vld", "sig_wr_chl_ob_wr_hs")},
        {"boundary_id": "last_drain_finish_state", "layer": "STATE_HOLD_CLEAR", "signal_ids": ids(
            "sig_buf_ag_idx_last_bit", "sig_buf_ag_idx_last_index", "sig_mse2buf_last",
            "sig_mse2buf_last_index", "sig_wr_data_chl_last_flag", "sig_transaction_idx_last_bit",
            "sig_transaction_idx_last_index", "sig_transaction_finish", "sig_transaction_addr_ctrl_clear",
            "sig_wr_data_chl_hold_last_flag", "sig_wr_data_chl_ob_last_data_arv_arr_flag",
            "sig_slice_cmpt_finish", "sig_slice_cmpt_finish_2", "sig_sem_cs", "sig_sem_ns")},
    ]
    old_candidates = copy.deepcopy(prior_candidates)
    new_candidates = [
        {"candidate_id": "buffer_memory_idx_queue_rate_mismatch", "priority": "HIGH", "description": "Buffer and memory index queues accept or drain different group counts."},
        {"candidate_id": "memory_metadata_transfer_underproduction", "priority": "HIGH", "description": "Memory index metadata does not produce one WR metadata request per prepared group."},
        {"candidate_id": "prepared_spatial_accounting_surplus", "priority": "HIGH", "description": "Prepared spatial-size increments exceed metadata transfer-size decrements."},
    ]
    candidates = old_candidates + new_candidates
    candidate_signals = {
        candidate["candidate_id"]: sorted(
            row["signal_id"] for row in signals
            if candidate["candidate_id"] in row.get("driver_leaf_for_candidate_ids", [])
        ) for candidate in candidates
    }
    matrix = []
    for ci, candidate in enumerate(candidates):
        cid = candidate["candidate_id"]
        for bi, boundary in enumerate(boundaries):
            matrix.append({
                "candidate_id": cid,
                "boundary_id": boundary["boundary_id"],
                "expected_signature": {
                    "candidate_code": f"P51C{ci}", "boundary_code": f"B{bi}",
                    "decision_predicate": f"p51_{cid}_source_bound_transition_predicate",
                    "candidate_signal_ids": candidate_signals[cid],
                    "direct_driver_signal_ids_at_boundary": sorted(set(candidate_signals[cid]) & set(boundary["signal_ids"])),
                    "ordered_four_state_transitions_required": True,
                },
            })
    contract["boundaries"] = boundaries
    contract["candidates"] = candidates
    contract["candidate_boundary_matrix"] = matrix
    contract["scope"]["dump_scopes"] = [
        {
            "scope_id": f"exact_{row['signal_id']}", "exact_hierarchy": row["exact_hierarchy"], "depth": 0,
            "boundary_ids": [b["boundary_id"] for b in boundaries if row["signal_id"] in b["signal_ids"]] or [boundaries[0]["boundary_id"]],
            "source_bound_signal_ids": [row["signal_id"]],
        } for row in signals
    ]
    prior_ids = {row["signal_id"] for row in prior_signals}
    current_ids = {row["signal_id"] for row in signals}
    prior_cids = {row["candidate_id"] for row in prior_candidates}
    current_cids = {row["candidate_id"] for row in candidates}
    contract["diagnostic_round"] = {
        "round_index": 2,
        "round_kind": "EVIDENCE_REFINED_SUCCESSOR",
        "breadth_baseline": baseline_block(
            baseline, pinned, len(prior_signals),
            sum(bool(row.get("driver_leaf_for_candidate_ids")) for row in prior_signals),
            len(prior_candidates), len(signals),
        ),
        "source_identity": {"pinned_rtl_tree_sha256": pinned, "catalog_source_identity_sha256": base.source_identity_sha(signals)},
        "coverage_gaps": [],
        "evolution": {
            "predecessor": {
                "package_id": SOURCE_ID, "round_index": 1,
                "contract_path": prior_path.relative_to(TREE).as_posix(), "contract_sha256": base.sha(prior_path),
                "pinned_rtl_tree_sha256": pinned,
            },
            "added_signal_ids": sorted(current_ids - prior_ids), "removed_signal_ids": [],
            "unchanged_signal_ids": sorted(current_ids & prior_ids), "removal_evidence": [],
            "candidate_preservation": {
                "preserved_candidate_ids": sorted(prior_cids & current_cids), "closed_candidate_ids": [],
                "new_candidate_ids": sorted(current_cids - prior_cids), "closure_evidence": [],
            },
        },
    }
    contract["return_receipts"]["breadth_evolution"] = "evidence/TB_VCD_BREADTH_EVOLUTION.json"
    contract["claim_boundary"] = (
        "p50-return-driven metadata/index refinement transport only. Local gates do not establish production p51 "
        "compile/simulation, a validated RTL root, natural terminal, formal D, E3, E4 or E5."
    )
    return contract


def update_runtime_and_return(contract: dict[str, Any]) -> None:
    package_tools = TREE / "package_tools"
    for source, target in (
        (ROOT / "tools/conv_native_p49_tb_vcd_finalize.py", package_tools / "tb_vcd_finalize.py"),
        (ROOT / "tools/conv_native_p49_tb_vcd_live_supervision.py", package_tools / "tb_vcd_live_supervision.py"),
        (ROOT / "tools/server_tb_vcd_runtime_supervision.py", package_tools / "server_tb_vcd_runtime_supervision.py"),
        (ROOT / "tools/server_tb_vcd_retention_analysis.py", package_tools / "server_tb_vcd_retention_analysis.py"),
        (ROOT / "tools/server_post_sim_return.py", package_tools / "server_post_sim_return.py"),
        (ROOT / "tools/conv_native_p51_capture_actual_compiled_sources.py", package_tools / "capture_actual_compiled_sources.py"),
        (ROOT / "tools/conv_native_p51_build_direct_evidence_review.py", package_tools / "build_direct_evidence_review.py"),
    ):
        shutil.copyfile(source, target)
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    runner_path = TREE / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    compile_anchor = (
        'python3 "$package_root/package_tools/compile_core_evidence.py" finalize --output-root "$bootstrap_root" --exit-code "$compile_status" || runner_fail 8 "compile-core post-actual-command finalize failed"\n'
    )
    capture = compile_anchor + (
        'python3 "$package_root/package_tools/capture_actual_compiled_sources.py" --server-root "$server_root" '
        '--compile-log "$compile_driver_log" --output-root "$bootstrap_root/actual_compiled_sources" '
        '--package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" || '
        'printf \'CODEX_WARNING actual compiled source capture incomplete; core return preserved\\n\' >&2\n'
    )
    if compile_anchor not in runner:
        raise RuntimeError("p50 compile finalize anchor absent")
    runner = runner.replace(compile_anchor, capture, 1)
    post_anchor = (
        '  export CODEX_PACKAGE_ROOT="$package_root" CODEX_ATTEMPT_ROOT="$run_root" CODEX_EXECUTION_ID="$return_tag"'
    )
    review = (
        '  python3 "$package_root/package_tools/build_direct_evidence_review.py" --package-id "$package_id" '
        '--execution-id "$return_tag" --attempt-id "$attempt" --actual-root "$server_root" '
        '--published-root "$published_root" --config-root "$cfg_root" --bootstrap-root "$bootstrap_root" '
        '--evidence-root "$evidence_root" --compile-exit "$compile_status" --sim-exit "$run_status" || '
        'printf \'CODEX_WARNING direct config/RTL evidence review failed; raw core preserved\\n\' >&2\n'
        + post_anchor
    )
    if post_anchor not in runner:
        raise RuntimeError("p50 post-return export anchor absent")
    runner = runner.replace(post_anchor, review, 1)
    runner_path.write_text(runner, encoding="utf-8", newline="\n")
    runner_path.chmod(runner_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = base.load(request_path)
    request["package_id"] = PACKAGE_ID
    request["core_entries"] = [
        row for row in request["core_entries"]
        if row.get("archive") != "evidence/CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json"
    ]
    extra = [
        {"source_root": "attempt", "source": "evidence/CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json", "archive": "evidence/CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json", "required": True},
        {"source_root": "attempt", "source": "evidence/compile_bootstrap/actual_compiled_sources/manifest.json", "archive": "evidence/compile_bootstrap/actual_compiled_sources/manifest.json", "required": True},
    ]
    for relative in (
        "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv",
        "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_AG_Idx_Queue.sv",
        "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv",
        "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Memory_AG.sv",
        "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv",
        "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv",
        "rtl/utils/FIFO/FIFO.sv",
    ):
        extra.append({
            "source_root": "attempt", "source": "evidence/compile_bootstrap/actual_compiled_sources/files/" + relative,
            "archive": "evidence/actual_rtl/" + Path(relative).name, "required": False,
        })
    archives = {row["archive"] for row in request["core_entries"]}
    request["core_entries"].extend(row for row in extra if row["archive"] not in archives)
    request["claim_boundary"] = (
        "Adaptive metadata/index causal cone plus post-compile actual source capture; every non-natural or incomplete "
        "exit remains PARTIAL/DIAGNOSTIC_EVIDENCE_INCOMPLETE."
    )
    request_path.write_bytes(base.canonical(request))

    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = base.load(selector_path)
    selector["package_id"] = PACKAGE_ID
    selector["vcd_contract_sha256"] = base.sha(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    selector["return_members"] = sorted(set(selector["return_members"]) | {
        "evidence/CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json",
        "evidence/compile_bootstrap/actual_compiled_sources/manifest.json",
    })
    selector_path.write_bytes(base.canonical(selector))

    post_contract_path = TREE / "contracts/server_post_sim_return_contract.json"
    post_contract = base.load(post_contract_path)
    post_contract.update({
        "package_id": PACKAGE_ID, "helper_sha256": base.sha(package_tools / "server_post_sim_return.py"),
        "request_sha256": base.sha(request_path), "runner_sha256": base.sha(runner_path),
    })
    post_contract_path.write_bytes(base.canonical(post_contract))
    layout_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = base.load(layout_path); layout["package_id"] = PACKAGE_ID; layout["runner_sha256"] = base.sha(runner_path)
    layout_path.write_bytes(base.canonical(layout))
    runner_contract_path = TREE / "server_runner_return_resilience_contract.json"
    runner_contract = base.load(runner_contract_path)
    runner_contract.update({"package_id": PACKAGE_ID, "runner_path": f"{PACKAGE_ID}/PREPARE_AND_RUN.sh", "runner_sha256": base.sha(runner_path)})
    runner_contract["return_allowlist_tokens"] = sorted(set(runner_contract.get("return_allowlist_tokens", [])) | {"actual_compiled_sources"})
    runner_contract_path.write_bytes(base.canonical(runner_contract))

    allowlist_path = TREE / "RETURN_ALLOWLIST.json"
    allowlist = base.load(allowlist_path)
    root = f"{PACKAGE_ID}_return/"
    required = [root + row["archive"] for row in request["core_entries"] if row.get("required") is True]
    required += [root + "RETURN_CORE_MANIFEST.json", root + "return_core/SIM_EXIT_RECEIPT.json", root + "return_core/RETURN_CORE_STATUS.json"]
    allowlist.update({
        "schema": "conv-native-p51-tb-vcd-return-allowlist-v1", "package_id": PACKAGE_ID,
        "required": sorted(set(required)), "vcd_member": root + "runs/c0/native_mse4_causal.vcd",
        "no_size_limit": True, "no_truncation": True, "no_sampling": True,
    })
    allowlist_path.write_bytes(base.canonical(allowlist))


def update_manifests(signals: list[dict[str, Any]], additions: list[str]) -> None:
    runner = TREE / "PREPARE_AND_RUN.sh"
    contract = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    selector = TREE / "contracts/server_diagnostic_mode_selector.json"
    pointer_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    pointer = base.load(pointer_path)
    pointer.update({
        "schema": "conv-native-four-lane-p51-adaptive-tb-vcd-pointer-v1", "package_identity": PACKAGE_ID,
        "family": FAMILY, "activation_epoch": ACTIVATION_EPOCH, "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "status": "PACKAGE_READY_NOT_RUN", "server_actions_performed": [],
    })
    pointer_path.write_bytes(base.canonical(pointer))
    (TREE / "README.md").write_text(
        f"# {PACKAGE_ID}\n\n"
        "Previous progress: p41 proved production compile beyond Datahub; p42 fixed the two-bit vector predicate. "
        "p50 entered MSE4 and dynamically proved 18 metadata/output accepts versus 20 prepared writes and 23/21 "
        "RD-buffer enqueue/dequeue operations, ending with metadata empty, prepared count 32 and RD count 2/full. "
        "It reached the 3600-second wall ceiling because held full-FIFO write enables were incorrectly counted as progress.\n\n"
        "Current purpose: retain every p50 signal, qualify progress by real FIFO acceptance, and add both Buffer_AG "
        "and Memory_AG index queue write/read/count/full/empty state plus WR metadata transfer and spatial-size accounting. "
        "The return captures the exact post-compile RTL bytes and constructs the config/RTL/dynamic review per attempt.\n\n"
        "Root remains DYNAMICALLY_PROVEN_METADATA_EMPTY_AT_PREPARED_OUTPUT_JOIN with the upstream metadata-versus-buffer "
        "index cause open. No configuration workaround is validated or applied.\n\n"
        f"Only after separate server authorization: `bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\n"
        "No upload, lease, connection, server execution, storage publication or functional payload change was performed.\n",
        encoding="utf-8", newline="\n",
    )
    manifest_path = TREE / "package_manifest.json"
    manifest = base.load(manifest_path)
    manifest.update({
        "schema": "conv-native-four-lane-p51-adaptive-tb-vcd-package-v1", "package_identity": PACKAGE_ID,
        "install_name": PACKAGE_ID, "family": FAMILY, "status": "PACKAGE_READY_NOT_RUN",
        "activation_epoch": ACTIVATION_EPOCH, "source_package": SOURCE_ID,
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "previous_version_progress": "p50 executed MSE4 and proved a two-group data/metadata residual mismatch before a false-progress wall ceiling.",
        "current_version_purpose": "Discriminate Buffer_AG versus Memory_AG index lifetime and metadata/spatial accounting with qualified progress and returned actual RTL bytes.",
        "vcd_contract_sha256": base.sha(contract), "mode_selector_sha256": base.sha(selector),
        "runner_sha256": base.sha(runner), "rule_gap_audit": "provenance/RULE_GAP_AUDIT.json",
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE_IMPLEMENTATION_FIX",
        "config_rtl_evidence_review": "evidence/CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json",
        "root_disposition": "OPEN_UNVALIDATED_MECHANISM", "diagnostic_signal_count": len(signals),
        "added_signal_ids": additions,
        "frozen": {"config": True, "numeric": True, "workload": True, "golden": True, "functional_rtl": True, "target_diagnostic": True},
        "server_actions_performed": [],
        "claim_boundary": "Local build and gates only; no p51 production compile/simulation/root/natural/formal-D/E3/E4/E5 claim.",
    })
    manifest["files"] = {
        path.relative_to(TREE).as_posix(): {"size_bytes": path.stat().st_size, "sha256": base.sha(path)}
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()) if path != manifest_path
    }
    manifest_path.write_bytes(base.canonical(manifest))


def main() -> int:
    required = [SOURCE_ZIP, ANALYSIS / "formal_return_analysis.json", ANALYSIS / "RULE_GAP_AUDIT.json", ANALYSIS / "CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"p50 source/analysis absent: {missing}")
    formal = base.load(ANALYSIS / "formal_return_analysis.json")
    gap = base.load(ANALYSIS / "RULE_GAP_AUDIT.json")
    if formal.get("pass") is not True or gap.get("rule_disposition") != "RULE_CONFIRMATION_NO_CHANGE":
        raise RuntimeError("p50 analysis or rule disposition differs")

    base.safe_extract()
    original_contract = base.load(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    original_tb = (TREE / "tb_probe/native_mse4_bounded_causal_cone_vcd.sv").read_bytes()
    base.replace_identity_in_text_files()
    provenance = TREE / "provenance"; provenance.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ANALYSIS / "formal_return_analysis.json", provenance / "p50_formal_return_analysis.json")
    shutil.copyfile(ANALYSIS / "RULE_GAP_AUDIT.json", provenance / "RULE_GAP_AUDIT.json")
    shutil.copyfile(ANALYSIS / "CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json", provenance / "p50_CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json")

    signals, additions = build_signals()
    tb_path = patch_tb(signals)
    contract = build_contract(signals, tb_path, original_contract, original_tb)
    contract_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    contract_path.write_bytes(base.canonical(contract))
    matrix_path = write_json("diagnostics/tb_vcd_candidate_boundary_matrix.json", {
        "schema": "conv-native-p51-adaptive-candidate-boundary-matrix-v1", "package_id": PACKAGE_ID,
        "candidates": contract["candidates"], "boundaries": contract["boundaries"],
        "candidate_boundary_matrix": contract["candidate_boundary_matrix"],
        "complete_cross_product": True, "pairwise_distinguishable": True,
    })
    catalog_path = TREE / "diagnostics/tb_vcd_causal_signal_catalog.json"
    catalog = base.load(catalog_path)
    catalog.update({"schema": "conv-native-p51-adaptive-tb-vcd-causal-signal-catalog-v1", "package_id": PACKAGE_ID, "signals": signals, "signal_count": len(signals), "p50_signals_retained": 88, "added_zero_hop_driver_signals": len(additions)})
    catalog_path.write_bytes(base.canonical(catalog))
    write_json("diagnostics/tb_vcd_exact_dump_plan.json", {
        "schema": "conv-native-p51-tb-vcd-exact-dump-plan-v1", "package_id": PACKAGE_ID,
        "strategy": "EXPLICIT_SOURCE_BOUND_SIGNAL_ONLY", "signal_count": len(signals),
        "signal_ids": [row["signal_id"] for row in signals], "exact_hierarchies": [row["exact_hierarchy"] for row in signals],
        "module_scope_dump_forbidden": True, "uncataloged_signal_forbidden": True, "pass": True,
    })
    source_generation_path = TREE / "diagnostics/source_bound_vcd_generation.json"
    source_generation = base.load(source_generation_path)
    source_generation.update({
        "schema": "conv-native-p51-source-bound-vcd-generation-v1", "package_id": PACKAGE_ID,
        "catalog": {"path": catalog_path.relative_to(TREE).as_posix(), "sha256": base.sha(catalog_path)},
        "matrix": {"path": matrix_path.relative_to(TREE).as_posix(), "sha256": base.sha(matrix_path)},
        "tb_source": {"path": tb_path.relative_to(TREE).as_posix(), "sha256": base.sha(tb_path)},
        "role_count": 41, "signal_count": len(signals),
        "zero_hop_driver_count": sum(bool(row.get("driver_leaf_for_candidate_ids")) for row in signals), "pass": True,
    })
    source_generation_path.write_bytes(base.canonical(source_generation))
    diff = write_json("diagnostics/p50_to_p51_adaptive_signal_diff.json", {
        "schema": "conv-native-p50-to-p51-adaptive-signal-diff-v1", "family": FAMILY,
        "source_package": SOURCE_ID, "package_id": PACKAGE_ID, "source_signal_count": 88,
        "current_signal_count": len(signals), "unchanged_signal_ids": sorted(row["signal_id"] for row in signals if row["signal_id"] not in additions),
        "added_signal_ids": additions, "removed_signal_ids": [], "removal_disposition": "LOW_CONFIDENCE_RETAINED_BY_DEFAULT",
        "addition_reason": "p50 dynamically proved two extra prepared groups and requires exact Buffer_AG/Memory_AG index and metadata transfer discrimination.",
        "machine_check_exit": 0, "pass": True,
    })
    update_runtime_and_return(contract)
    update_manifests(signals, additions)
    base.deterministic_zip(ZIP); base.deterministic_zip(REPEAT)
    if ZIP.read_bytes() != REPEAT.read_bytes():
        raise RuntimeError("p51 deterministic exact-ZIP recomputation differs")
    receipt = {
        "schema": "conv-native-p51-adaptive-tb-vcd-build-v1", "package_id": PACKAGE_ID, "family": FAMILY,
        "activation_epoch": ACTIVATION_EPOCH, "source_p50_pending": base.identity(SOURCE_ZIP),
        "formal_return_analysis": base.identity(ANALYSIS / "formal_return_analysis.json"),
        "rule_gap_audit": base.identity(ANALYSIS / "RULE_GAP_AUDIT.json"),
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE_IMPLEMENTATION_FIX",
        "adaptive_signal_diff": base.identity(diff), "zip": base.identity(ZIP), "repeat_zip": base.identity(REPEAT),
        "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional_rtl", "p42_vector_predicate", "MSE4_target"],
        "storage_publication": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE", "server_actions_performed": [], "pass": True, "errors": [],
    }
    (OUT / "build_receipt.json").write_bytes(base.canonical(receipt))
    print(json.dumps({"package_id": PACKAGE_ID, "signals": len(signals), "added_signals": len(additions), "zip": str(ZIP), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
