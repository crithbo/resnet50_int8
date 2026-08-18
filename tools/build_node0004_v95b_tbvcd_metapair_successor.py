#!/usr/bin/env python3
"""Build the v94-return-driven serialized Conv metadata/data lifetime successor.

This is deliberately a local staging builder.  It never invokes the package
storage manager and never performs a server action.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v95b_tbvcd_metapair"
PREVIOUS = "r5_n4_hw_v94b_tbvcd_wrdrain"
OUT = ROOT / "outputs/conv_node0004_v95b_tbvcd_metapair_release1"
TREE = OUT / "build" / PACKAGE
FINAL_ZIP = OUT / f"{PACKAGE}.zip"
SOURCE_TREE = (
    ROOT
    / "outputs/conv_node0004_v94b_tbvcd_wrdrain_release1/build"
    / PREVIOUS
)
RETURN_ZIP = Path(
    "C:/Users/15383/Downloads/"
    "r5_n4_hw_v94b_tbvcd_wrdrain_r1786716754307420499_2395883_return.zip"
)
V94_BUILDER = ROOT / "tools/build_node0004_v94b_tbvcd_wrdrain_successor.py"
ANALYSIS = ROOT / "outputs/conv_node0004_v94b_tbvcd_wrdrain_return_analysis/return_analysis.json"
RULE_AUDIT = ROOT / "outputs/conv_node0004_v94b_tbvcd_wrdrain_return_analysis/rule_gap_audit.json"

TARGET = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
    "u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
)
WR_MEM = (
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Memory_WR_Stream_Engine/WR_Memory_AG.sv"
)
BUFFER = "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv"
MEM_IDX = "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_AG_Idx_Queue.sv"
WR_TOP = (
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv"
)
FROZEN_CONFIG = ROOT / "configs/native_ndp_sim/r5_node0004_pe1_keep_last_index_fix_c0_v62/accumulate_waves/wave-0.json"
CONFIG_EVIDENCE = ROOT / "artifacts/operator_config_validation/r5-node0004-pe1-keep-last-index-fix-c0-v62"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def semantic_sha(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def declaration_span(path: Path, symbol: str) -> str:
    rows = [
        row.strip()
        for row in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if re.search(r"\b" + re.escape(symbol) + r"\b", row)
    ]
    if not rows:
        raise RuntimeError(f"source declaration is absent: {path}:{symbol}")
    return hashlib.sha256(rows[0].encode("utf-8")).hexdigest()


def local_signal(
    signal_id: str,
    suffix: str,
    width: int,
    roles: list[str],
    relative: str,
    symbol: str,
) -> dict[str, Any]:
    source = ROOT / "NDP_copy01" / relative
    return {
        "signal_id": signal_id,
        "exact_hierarchy": f"{TARGET}.{suffix}",
        "width_bits": width,
        "roles": roles,
        "source_path": relative,
        "source_sha256": sha(source),
        "declaration_span_sha256": declaration_span(source, symbol),
        "source_binding": "ACTUAL_SOURCE_NET",
        "derived_expected_equation": False,
        "drives_dut": False,
        "driver_leaf_for_candidate_ids": [],
        "driver_depth_edges": None,
    }


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
    return semantic_sha(sorted(rows, key=lambda row: row["signal_id"]))


def load_v94() -> Any:
    spec = importlib.util.spec_from_file_location("node0004_v94_builder_for_v95", V94_BUILDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def actual_compile_identity() -> dict[str, Any]:
    with zipfile.ZipFile(RETURN_ZIP) as archive:
        member = next(
            name
            for name in archive.namelist()
            if name.endswith("evidence/compiled_source/source_identity.json")
        )
        value = json.loads(archive.read(member))
    return value


def pinned_rtl_identity(actual: dict[str, Any]) -> str:
    value = {
        "filelists": [
            {"sha256": row.get("sha256"), "exists": row.get("exists")}
            for row in actual.get("filelists", [])
        ],
        "defines": actual.get("define_tokens", []),
        "parameters": actual.get("parameter_tokens", []),
        "sources": sorted(
            {
                row.get("relative_path"): row.get("sha256")
                for row in actual.get("sources", [])
                if isinstance(row, dict)
            }.items()
        ),
    }
    return semantic_sha(value)


def assign_driver(signal: dict[str, Any], *candidate_ids: str) -> None:
    signal["driver_leaf_for_candidate_ids"] = sorted(set(candidate_ids))
    signal["driver_depth_edges"] = 0 if candidate_ids else None


def normalize_signals(signals: list[dict[str, Any]]) -> None:
    for signal in signals:
        signal.setdefault("driver_leaf_for_candidate_ids", [])
        signal.setdefault("driver_depth_edges", None)
    by_id = {row["signal_id"]: row for row in signals}
    assignments = {
        "sig_wr_queue_full": ["metadata_queue_starvation_or_block"],
        "sig_wr_queue_empty": ["metadata_queue_starvation_or_block"],
        "sig_wr_queue_tsf_size": ["prepared_valid_size_gate"],
        "sig_wr_queue_mask_flag": ["output_buffer_selection_gate"],
        "sig_wr_ob_bp_pre": ["output_buffer_backpressure"],
        "sig_wdata_ready": ["memory_wdata_drain_block"],
        "sig_prepared_wr_hs": ["prepared_count_accounting", "prepared_write_without_drain"],
        "sig_prepared_rd_hs": ["prepared_count_accounting", "prepared_write_without_drain"],
        "sig_global_fetch_finish": ["terminal_lifetime_hold"],
    }
    for signal_id, candidates in assignments.items():
        assign_driver(by_id[signal_id], *candidates)


def additions() -> list[dict[str, Any]]:
    add = local_signal
    return [
        add("sig_meta_input_valid", "u_WR_Memory_AG.mse_mem_ag_tag_valid", 1, ["valid", "producer", "metadata_queue"], WR_MEM, "mse_mem_ag_tag_valid"),
        add("sig_meta_input_ready", "u_WR_Memory_AG.mse_mem_ag_bp_pre", 1, ["ready", "accept", "backpressure", "metadata_queue"], WR_MEM, "mse_mem_ag_bp_pre"),
        add("sig_meta_transaction_bias_valid", "u_WR_Memory_AG.transaction_addr_bias_valid", 1, ["valid", "metadata_queue", "lifetime"], WR_MEM, "transaction_addr_bias_valid"),
        add("sig_meta_transaction_valid", "u_WR_Memory_AG.transaction_addr_valid", 1, ["valid", "metadata_queue", "lifetime"], WR_MEM, "transaction_addr_valid"),
        add("sig_meta_transaction_finish", "u_WR_Memory_AG.transaction_finish", 1, ["completion", "metadata_queue", "lifetime"], WR_MEM, "transaction_finish"),
        add("sig_meta_size_left", "u_WR_Memory_AG.cur_transaction_size_left", 8, ["count", "outstanding", "metadata_queue"], WR_MEM, "cur_transaction_size_left"),
        add("sig_meta_final_size", "u_WR_Memory_AG.transfer_final_size", 5, ["count", "metadata_queue", "prepared_data"], WR_MEM, "transfer_final_size"),
        add("sig_meta_transfer_valid", "u_WR_Memory_AG.transfer_size_valid", 1, ["valid", "metadata_queue", "producer"], WR_MEM, "transfer_size_valid"),
        add("sig_meta_transfer_accept", "u_WR_Memory_AG.transfer_addr_bp_post", 1, ["accept", "ready", "metadata_queue"], WR_MEM, "transfer_addr_bp_post"),
        add("sig_meta_output_ready", "u_WR_Memory_AG.mem_ag_ob_bp_pre", 1, ["ready", "backpressure", "output_buffer"], WR_MEM, "mem_ag_ob_bp_pre"),
        add("sig_meta_output_valid", "u_WR_Memory_AG.mem_ag_ob_vld", 2, ["valid", "output_buffer", "metadata_queue"], WR_MEM, "mem_ag_ob_vld"),
        add("sig_meta_output_wr", "u_WR_Memory_AG.mem_ag_ob_chl_wr_hs", 2, ["fifo_enqueue", "accept", "output_buffer"], WR_MEM, "mem_ag_ob_chl_wr_hs"),
        add("sig_meta_output_rd", "u_WR_Memory_AG.mem_ag_ob_chl_rd_hs", 2, ["fifo_dequeue", "drain", "output_buffer"], WR_MEM, "mem_ag_ob_chl_rd_hs"),
        add("sig_buf_last_masked", "u_Buffer_AG_Idx_Queue.buf_idx_last_bit_masked", 2, ["mask", "last", "producer"], BUFFER, "buf_idx_last_bit_masked"),
        add("sig_buf_selected_last", "u_Buffer_AG_Idx_Queue.buf_buffer_idx_last_bit", 1, ["last", "producer", "lifetime"], BUFFER, "buf_buffer_idx_last_bit"),
        add("sig_buf_selected_last_index", "u_Buffer_AG_Idx_Queue.buf_buffer_idx_last_index", 4, ["index", "producer", "lifetime"], BUFFER, "buf_buffer_idx_last_index"),
        add("sig_cfg_mem_idx_mode", "mse_mem_idx_mode", 6, ["configuration", "mode", "metadata_queue"], WR_TOP, "mse_mem_idx_mode"),
        add("sig_cfg_mem_keep_last", "mse_mem_idx_keep_last_index", 12, ["configuration", "last", "metadata_queue"], WR_TOP, "mse_mem_idx_keep_last_index"),
        add("sig_cfg_buf_keep_last", "mse_buf_idx_keep_last_index", 8, ["configuration", "last", "prepared_data"], WR_TOP, "mse_buf_idx_keep_last_index"),
        add("sig_cfg_transaction_total_size", "mse_transaciton_total_size", 8, ["configuration", "count", "metadata_queue"], WR_TOP, "mse_transaciton_total_size"),
        add("sig_memidx_all_matched", "u_Memory_AG_Idx_Queue.mem_all_idx_matched", 1, ["accept", "metadata_queue", "producer"], MEM_IDX, "mem_all_idx_matched"),
        add("sig_memidx_buffer_last", "u_Memory_AG_Idx_Queue.mem_buffer_idx_last_bit", 1, ["last", "metadata_queue", "lifetime"], MEM_IDX, "mem_buffer_idx_last_bit"),
        add("sig_memidx_buffer_last_index", "u_Memory_AG_Idx_Queue.mem_buffer_idx_last_index", 4, ["index", "metadata_queue", "lifetime"], MEM_IDX, "mem_buffer_idx_last_index"),
        add("sig_memidx_queue_wr", "u_Memory_AG_Idx_Queue.mem_ag_idx_queue_wr_en", 1, ["fifo_enqueue", "accept", "metadata_queue"], MEM_IDX, "mem_ag_idx_queue_wr_en"),
        add("sig_memidx_queue_rd", "u_Memory_AG_Idx_Queue.mem_ag_idx_queue_rd_en", 1, ["fifo_dequeue", "drain", "metadata_queue"], MEM_IDX, "mem_ag_idx_queue_rd_en"),
        add("sig_memidx_queue_empty", "u_Memory_AG_Idx_Queue.mem_ag_idx_queue_empty", 1, ["fifo_empty", "metadata_queue", "lifetime"], MEM_IDX, "mem_ag_idx_queue_empty"),
        add("sig_memidx_queue_full", "u_Memory_AG_Idx_Queue.mem_ag_idx_queue_full", 1, ["fifo_full", "backpressure", "metadata_queue"], MEM_IDX, "mem_ag_idx_queue_full"),
    ]


PRIORITY = {
    "prepared_write_without_drain": "MEDIUM",
    "metadata_queue_starvation_or_block": "HIGH",
    "prepared_valid_size_gate": "LOW",
    "output_buffer_selection_gate": "LOW",
    "output_buffer_backpressure": "LOW",
    "memory_wdata_drain_block": "LOW",
    "prepared_count_accounting": "MEDIUM",
    "terminal_lifetime_hold": "MEDIUM",
    "metadata_generation_lifetime_ends_early": "HIGH",
    "buffer_data_generation_lifetime_overruns": "HIGH",
}


def current_candidates(old: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = [
        {**row, "priority": PRIORITY[row["candidate_id"]]}
        for row in old
    ]
    result.extend(
        [
            {
                "candidate_id": "metadata_generation_lifetime_ends_early",
                "description": "WR_Memory_AG transaction/transfer lifetime ends before the final two prepared-data groups receive matching metadata.",
                "priority": "HIGH",
            },
            {
                "candidate_id": "buffer_data_generation_lifetime_overruns",
                "description": "Buffer_AG index/last lifetime admits two prepared-data groups beyond the matching WR_Memory_AG transaction lifetime.",
                "priority": "HIGH",
            },
        ]
    )
    return result


def candidate_sets() -> dict[str, list[str]]:
    return {
        "prepared_write_without_drain": ["sig_prepared_wr_hs", "sig_prepared_rd_hs", "sig_prepared_count", "sig_mse_buf_spatial_size", "sig_wr_queue_tsf_size"],
        "metadata_queue_starvation_or_block": ["sig_wr_req_valid", "sig_wr_req_ready", "sig_wr_queue_wr", "sig_wr_queue_rd", "sig_wr_queue_count", "sig_wr_queue_empty", "sig_wr_queue_full"],
        "prepared_valid_size_gate": ["sig_prepared_count", "sig_wr_queue_tsf_size", "sig_prepared_valid", "sig_mse_enable"],
        "output_buffer_selection_gate": ["sig_wr_ob_sel", "sig_wr_queue_mask_flag", "sig_wr_ob_vld_in", "sig_wr_ob_wr_hs"],
        "output_buffer_backpressure": ["sig_wr_ob_vld", "sig_wr_ob_bp_pre", "sig_wr_ob_vld_in", "sig_wr_ob_wr_hs"],
        "memory_wdata_drain_block": ["sig_wr_ob_vld", "sig_wdata_valid", "sig_wdata_ready", "sig_wr_ob_rd_hs"],
        "prepared_count_accounting": ["sig_prepared_wr_hs", "sig_prepared_rd_hs", "sig_mse_buf_spatial_size", "sig_wr_queue_tsf_size", "sig_prepared_count"],
        "terminal_lifetime_hold": ["sig_prepared_count", "sig_wr_queue_count", "sig_wr_ob_vld", "sig_hold_data_valid", "sig_mse_enable", "sig_slice_finish", "sig_global_fetch_finish", "sig_global_slice_finish"],
        "metadata_generation_lifetime_ends_early": ["sig_cfg_mem_idx_mode", "sig_cfg_mem_keep_last", "sig_cfg_transaction_total_size", "sig_memidx_all_matched", "sig_memidx_buffer_last", "sig_memidx_buffer_last_index", "sig_memidx_queue_wr", "sig_memidx_queue_rd", "sig_memidx_queue_empty", "sig_memidx_queue_full", "sig_meta_input_valid", "sig_meta_input_ready", "sig_meta_transaction_bias_valid", "sig_meta_transaction_valid", "sig_meta_transaction_finish", "sig_meta_size_left", "sig_meta_final_size", "sig_meta_transfer_valid", "sig_meta_transfer_accept", "sig_meta_output_ready", "sig_wr_req_valid"],
        "buffer_data_generation_lifetime_overruns": ["sig_idx_mode", "sig_cfg_buf_keep_last", "sig_all_match", "sig_gotten", "sig_valid_mask", "sig_buf_last_masked", "sig_buf_selected_last", "sig_buf_selected_last_index", "sig_queue_wr", "sig_rd_ob_wr", "sig_prepared_wr_hs"],
    }


def build_matrix(candidates: list[dict[str, Any]], boundaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sets = candidate_sets()
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        for boundary in boundaries:
            boundary_ids = set(boundary["signal_ids"])
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "boundary_id": boundary["boundary_id"],
                    "expected_signature": {
                        "decision_predicate": f"v95_{candidate_id}_distinguishing_predicate",
                        "candidate_signal_ids": sets[candidate_id],
                        "direct_boundary_signal_ids": [
                            signal_id for signal_id in sets[candidate_id] if signal_id in boundary_ids
                        ],
                        "requires_complete_ordered_transitions": True,
                    },
                }
            )
    return rows


def baseline_receipt(pinned: str, prior_signals: list[dict[str, Any]], prior_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "server-tb-vcd-family-round-breadth-baseline-v1",
        "family": "conv_serialized_node0004",
        "package_id": PREVIOUS,
        "round_index": 3,
        "signal_count": len(prior_signals),
        "direct_driver_leaf_count": sum(bool(row["driver_leaf_for_candidate_ids"]) for row in prior_signals),
        "candidate_count": len(prior_candidates),
        "boundary_count": 4,
        "pinned_rtl_tree_sha256": pinned,
        "machine_check_exit": 0,
        "normalization_note": "v94b is the same-family third TB-VCD diagnostic and is normalized to the activated breadth schema solely for v95 exact evolution checking.",
    }


def baseline_block(receipt_path: str, receipt_sha: str, pinned: str, signal_count: int, driver_count: int, candidate_count: int, current_count: int) -> dict[str, Any]:
    minimum, maximum = 60, 104
    relation = "WITHIN_REFERENCE_RANGE"
    if current_count < minimum:
        relation = "BELOW_REFERENCE_RANGE"
    elif current_count > maximum:
        relation = "ABOVE_REFERENCE_RANGE"
    return {
        "mode": "FAMILY_CURRENT_ROUND_AT_LEAST_THREE_SOFT_REFERENCE",
        "reference_round_index": 3,
        "reference_package_id": PREVIOUS,
        "receipt_path": receipt_path,
        "receipt_sha256": receipt_sha,
        "reference_signal_count": signal_count,
        "reference_direct_driver_leaf_count": driver_count,
        "reference_candidate_count": candidate_count,
        "reference_boundary_count": 4,
        "reasonable_signal_count_range": {"minimum": minimum, "maximum": maximum},
        "deviation": {
            "relation": relation,
            "explanation": None if relation == "WITHIN_REFERENCE_RANGE" else "HIGH-priority zero-hop driver coverage controls the breadth; raw signal count is only a soft reference.",
            "acknowledged": relation != "WITHIN_REFERENCE_RANGE",
        },
    }


def first_fresh_controls() -> dict[str, Any]:
    return {
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


def patch_contract(v94: Any, signals: list[dict[str, Any]], probe_sha: str, pinned: str) -> tuple[dict[str, Any], dict[str, Any]]:
    prior_signals = v94.make_signals()
    normalize_signals(prior_signals)
    old = v94.build_contract(prior_signals, "0" * 64)
    prior_candidates = [
        {**row, "priority": PRIORITY[row["candidate_id"]]}
        for row in old["candidates"]
    ]
    baseline_path = "provenance/v94b_round3_breadth_baseline.json"
    baseline_sha = sha(TREE / baseline_path)
    prior = old
    prior["execution"]["tb_source_path"] = "provenance/v94b_tb_vcd_bounded_causal_cone.svh"
    prior["execution"]["tb_source_sha256"] = sha(TREE / prior["execution"]["tb_source_path"])
    prior["candidates"] = prior_candidates
    prior["first_fresh_controls"] = first_fresh_controls()
    prior["return_receipts"]["breadth_evolution"] = "evidence/vcd/VCD_BREADTH_EVOLUTION.json"
    prior["diagnostic_round"] = {
        "round_index": 1,
        "round_kind": "FIRST_DIAGNOSTIC_ROUND",
        "breadth_baseline": baseline_block(
            baseline_path,
            baseline_sha,
            pinned,
            len(prior_signals),
            sum(bool(row["driver_leaf_for_candidate_ids"]) for row in prior_signals),
            len(prior_candidates),
            len(prior_signals),
        ),
        "source_identity": {
            "pinned_rtl_tree_sha256": pinned,
            "catalog_source_identity_sha256": source_identity_sha(prior_signals),
        },
        "coverage_gaps": [],
        "evolution": {
            "predecessor": None,
            "added_signal_ids": sorted(row["signal_id"] for row in prior_signals),
            "removed_signal_ids": [],
            "unchanged_signal_ids": [],
            "removal_evidence": [],
            "candidate_preservation": {
                "preserved_candidate_ids": [],
                "closed_candidate_ids": [],
                "new_candidate_ids": sorted(row["candidate_id"] for row in prior_candidates),
                "closure_evidence": [],
            },
        },
    }
    prior["claim_boundary"] = "Current-schema normalization of tested v94b for exact v95 evolution checking; no new dynamic claim."

    contract = v94.build_contract(signals, probe_sha)
    contract["package_id"] = PACKAGE
    contract["execution"]["tb_source_sha256"] = probe_sha
    contract["execution"]["dump_targeting"]["signal_ids"] = [row["signal_id"] for row in signals]
    contract["candidates"] = current_candidates(prior_candidates)
    contract["boundaries"] = [
        {
            "boundary_id": "upstream",
            "layer": "FIRST_DIVERGENCE_UPSTREAM_ONE",
            "signal_ids": [
                "sig_all_match", "sig_gotten", "sig_valid_mask", "sig_buf_last_masked",
                "sig_buf_selected_last", "sig_buf_selected_last_index", "sig_queue_wr",
                "sig_rd_ob_wr", "sig_prepared_wr_hs",
            ],
        },
        {
            "boundary_id": "current",
            "layer": "FIRST_DIVERGENCE_CURRENT",
            "signal_ids": [
                "sig_meta_input_valid", "sig_meta_input_ready", "sig_meta_transaction_bias_valid",
                "sig_meta_transaction_valid", "sig_meta_transaction_finish", "sig_meta_size_left",
                "sig_meta_final_size", "sig_meta_transfer_valid", "sig_meta_transfer_accept",
                "sig_memidx_all_matched", "sig_memidx_buffer_last", "sig_memidx_buffer_last_index",
                "sig_memidx_queue_wr", "sig_memidx_queue_rd", "sig_memidx_queue_empty",
                "sig_memidx_queue_full", "sig_wr_req_valid", "sig_wr_req_ready",
                "sig_prepared_count", "sig_prepared_valid", "sig_prepared_rd_hs",
            ],
        },
        {
            "boundary_id": "downstream",
            "layer": "FIRST_DIVERGENCE_DOWNSTREAM_ONE",
            "signal_ids": [
                "sig_meta_output_ready", "sig_meta_output_valid", "sig_meta_output_wr",
                "sig_meta_output_rd", "sig_wr_queue_wr", "sig_wr_queue_rd", "sig_wr_queue_count",
                "sig_wr_queue_empty", "sig_wr_queue_full", "sig_wr_queue_tsf_size",
                "sig_wr_queue_mask_flag", "sig_wr_ob_vld_in", "sig_wr_ob_bp_pre",
                "sig_wr_ob_wr_hs", "sig_wr_ob_vld", "sig_wr_ob_rd_hs", "sig_wr_ob_sel",
                "sig_wdata_valid", "sig_wdata_ready",
            ],
        },
        {
            "boundary_id": "state_hold_clear",
            "layer": "STATE_HOLD_CLEAR",
            "signal_ids": [
                "sig_rst_n", "sig_slice_rst", "sig_hold_data_valid", "sig_mse_enable",
                "sig_slice_finish", "sig_global_fetch_finish", "sig_global_slice_finish",
                "sig_prepared_bp", "sig_rd_ob_count", "sig_queue_count", "sig_cfg_mem_idx_mode",
                "sig_cfg_mem_keep_last", "sig_idx_mode", "sig_cfg_buf_keep_last",
                "sig_cfg_transaction_total_size",
            ],
        },
    ]
    contract["candidate_boundary_matrix"] = build_matrix(contract["candidates"], contract["boundaries"])
    contract["return_receipts"]["breadth_evolution"] = "evidence/vcd/VCD_BREADTH_EVOLUTION.json"
    contract["first_fresh_controls"] = first_fresh_controls()
    prior_path = "provenance/v94b_current_schema_round1_contract.json"
    prior_ids = {row["signal_id"] for row in prior_signals}
    current_ids = {row["signal_id"] for row in signals}
    prior_candidate_ids = {row["candidate_id"] for row in prior_candidates}
    current_candidate_ids = {row["candidate_id"] for row in contract["candidates"]}
    contract["diagnostic_round"] = {
        "round_index": 2,
        "round_kind": "EVIDENCE_REFINED_SUCCESSOR",
        "breadth_baseline": baseline_block(
            baseline_path,
            baseline_sha,
            pinned,
            len(prior_signals),
            sum(bool(row["driver_leaf_for_candidate_ids"]) for row in prior_signals),
            len(prior_candidates),
            len(signals),
        ),
        "source_identity": {
            "pinned_rtl_tree_sha256": pinned,
            "catalog_source_identity_sha256": source_identity_sha(signals),
        },
        "coverage_gaps": [],
        "evolution": {
            "predecessor": {
                "package_id": PREVIOUS,
                "round_index": 1,
                "contract_path": prior_path,
                "contract_sha256": "PENDING",
                "pinned_rtl_tree_sha256": pinned,
            },
            "added_signal_ids": sorted(current_ids - prior_ids),
            "removed_signal_ids": sorted(prior_ids - current_ids),
            "unchanged_signal_ids": sorted(prior_ids & current_ids),
            "removal_evidence": [],
            "candidate_preservation": {
                "preserved_candidate_ids": sorted(prior_candidate_ids & current_candidate_ids),
                "closed_candidate_ids": sorted(prior_candidate_ids - current_candidate_ids),
                "new_candidate_ids": sorted(current_candidate_ids - prior_candidate_ids),
                "closure_evidence": [],
            },
        },
    }
    contract["claim_boundary"] = "v94-return-driven metadata-versus-data lifetime discriminator; no production result, functional root, natural terminal, formal-D, E3, E4 or E5 claim."
    return prior, contract


def patch_supervisor(text: str) -> str:
    text = text.replace(
        'parser.add_argument("--stop-control", type=Path, required=True)',
        'parser.add_argument("--stop-control", type=Path, required=True)\n    parser.add_argument("--console-log", type=Path, required=True)',
        1,
    )
    text = text.replace(
        'control = inside(args.stop_control, root, "stop control")',
        'control = inside(args.stop_control, root, "stop control")\n    console = inside(args.console_log, root, "console log")',
        1,
    )
    text = text.replace(
        'if receipt.exists() or control.exists() or not command:\n        raise ValueError("stale receipt/control or absent simulator command")',
        'if receipt.exists() or control.exists() or console.exists() or not command:\n        raise ValueError("stale receipt/control/console or absent simulator command")\n    control.parent.mkdir(parents=True, exist_ok=True)\n    control.write_text("", encoding="ascii")',
        1,
    )
    text = text.replace(
        'process = subprocess.Popen(command, cwd=args.cwd, start_new_session=True)',
        'console_stream = console.open("xb")\n    process = subprocess.Popen(command, cwd=args.cwd, start_new_session=True, stdout=console_stream, stderr=subprocess.STDOUT)',
        1,
    )
    text = text.replace(
        'decision, shared_receipt = shared_decision(evaluator.evaluate, samples, authority)',
        'evaluation_samples = select_evaluation_samples(samples)\n                decision, shared_receipt = shared_decision(evaluator.evaluate, evaluation_samples, authority)',
        1,
    )
    text = text.replace(
        'finally:\n        for number, old in old_handlers.items():\n            signal.signal(number, old)',
        'finally:\n        for number, old in old_handlers.items():\n            signal.signal(number, old)\n        console_stream.flush(); os.fsync(console_stream.fileno()); console_stream.close()',
        1,
    )
    text = text.replace(
        '"samples": samples, "heartbeat_contract":',
        '"samples": samples, "evaluation_samples": select_evaluation_samples(samples), "sample_selection": {"schema":"node0004-v95-evaluator-sample-selection-v1","raw_count":len(samples),"evaluation_count":len(select_evaluation_samples(samples)),"policy":"STRICT_OWNER_HEARTBEAT_OR_30S_FIXED_TIMESTAMP_OR_TERMINAL"}, "console_log": identity(console), "heartbeat_contract":',
        1,
    )
    anchor = "def main() -> int:\n"
    helper = '''def select_evaluation_samples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove host polls between source-bound owner-heartbeat updates.

    Fixed-timestamp rows are retained at 30-second cadence so a real three-
    interval simulation-time freeze remains observable.  Terminal rows are
    always retained.  The shared evaluator remains the sole decision authority.
    """
    selected: list[dict[str, Any]] = []
    for raw in samples:
        row = dict(raw)
        if not selected:
            selected.append(row); continue
        previous = selected[-1]
        cycles = int(row.get("owner_clock_cycles", row.get("sim_cycles", 0)))
        old_cycles = int(previous.get("owner_clock_cycles", previous.get("sim_cycles", 0)))
        tick = int(row.get("appended_vcd_timestamp_ticks", row.get("sim_time_ticks", 0)))
        old_tick = int(previous.get("appended_vcd_timestamp_ticks", previous.get("sim_time_ticks", 0)))
        terminal = row.get("signal") in {"HUP", "INT", "TERM"} or row.get("natural_terminal") is True or row.get("exit_code") not in (None, 0) or row.get("write_ok") is False or row.get("disk_space_ok") is False or row.get("quota_ok") is False
        freeze_sample = tick == old_tick and float(row.get("wall_seconds", 0)) - float(previous.get("wall_seconds", 0)) >= 30.0
        if cycles > old_cycles or freeze_sample or terminal:
            row["seq"] = len(selected); selected.append(row)
    return selected

'''
    if anchor not in text:
        raise RuntimeError("supervisor main anchor absent")
    return text.replace(anchor, helper + anchor, 1)


def patch_probe_stop_token(text: str) -> str:
    """Require the exact supervisor token; an empty pre-created file is inert."""
    text = text.replace(
        "          integer codex_control_fd;",
        "          integer codex_control_fd;\n"
        "          integer codex_control_scan;\n"
        "          string codex_control_token;",
        1,
    )
    old = '''              if (codex_control_fd != 0) begin
                $fclose(codex_control_fd);
                $dumpoff; $dumpflush; codex_dump_active = 0; codex_stop_reported = 1;
                $display("CODEX_TB_VCD_DUMPOFF_FLUSH_V1 sim_time=%0d owner_cycles=%0d", codex_time_ps, codex_owner_cycles);
                $display("CODEX_TB_VCD_STOP_REQUEST_V1 reason=CAUSAL_PLATEAU sim_time=%0d owner_cycles=%0d", codex_time_ps, codex_owner_cycles);
              end'''
    new = '''              if (codex_control_fd != 0) begin
                codex_control_scan = $fscanf(codex_control_fd, "%s", codex_control_token);
                $fclose(codex_control_fd);
                if (codex_control_scan == 1 && codex_control_token == "CAUSAL_PLATEAU") begin
                  $dumpoff; $dumpflush; codex_dump_active = 0; codex_stop_reported = 1;
                  $display("CODEX_TB_VCD_DUMPOFF_FLUSH_V1 sim_time=%0d owner_cycles=%0d", codex_time_ps, codex_owner_cycles);
                  $display("CODEX_TB_VCD_STOP_REQUEST_V1 reason=CAUSAL_PLATEAU sim_time=%0d owner_cycles=%0d", codex_time_ps, codex_owner_cycles);
                end
              end'''
    if old not in text:
        raise RuntimeError("probe stop-control anchor absent")
    return text.replace(old, new, 1)


def patch_finalizer(text: str) -> str:
    start = text.index("def vcd_header(path):")
    end = text.index("\ndef runtime_signals", start)
    header = '''def vcd_header(path):
    refs=[]; timescale=None; end=False; scopes=[]; in_timescale=False; body=[]
    if path.is_file():
        with path.open('r',encoding='utf-8',errors='replace') as f:
            for line in f:
                s=line.strip()
                if in_timescale:
                    if s=='$end': timescale=' '.join(body).strip(); in_timescale=False
                    else: body.append(s)
                    continue
                if s=='$timescale': in_timescale=True; body=[]; continue
                if s.startswith('$timescale'): timescale=s.replace('$timescale','').replace('$end','').strip()
                if s.startswith('$scope'):
                    parts=s.split()
                    if len(parts)>=3: scopes.append(parts[2])
                elif s.startswith('$upscope'):
                    if scopes: scopes.pop()
                elif s.startswith('$var'):
                    parts=s.split()
                    if len(parts)>=5: refs.append('.'.join([*scopes,parts[4].split('[')[0]]))
                if '$enddefinitions' in s: end=True; break
    return timescale,end,sorted(set(refs))
'''
    text = text[:start] + header + text[end:]
    text = text.replace(
        "timescale,enddefs,refs=vcd_header(a.vcd); required={x['signal_id'] for x in signals}; complete=required.issubset(set(refs)); vid,last_archive_tick=vcd_ident(a.vcd)",
        "timescale,enddefs,refs=vcd_header(a.vcd); required={x['exact_hierarchy'] for x in signals}; complete=required.issubset(set(refs)); vid,last_archive_tick=vcd_ident(a.vcd)",
        1,
    )
    text = text.replace("'missing_signal_ids':sorted(required-set(refs))", "'missing_exact_hierarchies':sorted(required-set(refs))", 1)
    text = text.replace("samples=proc.get('samples',[])", "samples=proc.get('evaluation_samples',proc.get('samples',[]))", 1)
    # A duplicate final row with unchanged owner-heartbeat is exactly the v94
    # false-plateau escape.  Archive identity is bound separately.
    duplicate = """    if samples and last_archive_tick>=samples[-1].get('appended_vcd_timestamp_ticks',0):
        final=dict(samples[-1]); final['seq']=len(samples); final['wall_seconds']=float(final.get('wall_seconds',0))+0.001; final['appended_vcd_timestamp_ticks']=last_archive_tick; final['sim_time_ticks']=last_archive_tick
        if proc.get('stop_marker'): final['owner_clock_cycles']=proc['stop_marker'].get('owner_clock_cycles',final.get('owner_clock_cycles',0)); final['sim_cycles']=final['owner_clock_cycles']
        samples=[*samples,final]
"""
    if duplicate not in text:
        raise RuntimeError("finalizer duplicate sample anchor absent")
    text = text.replace(duplicate, "", 1)
    text = text.replace(
        "write(out/'VCD_CANDIDATE_MATRIX.json',{'schema':'node0004-tb-vcd-candidate-matrix-v1','package_id':a.package_id,'candidates':c['candidates'],'candidate_boundary_matrix':c['candidate_boundary_matrix']})",
        "write(out/'VCD_CANDIDATE_MATRIX.json',{'schema':'node0004-tb-vcd-candidate-matrix-v1','package_id':a.package_id,'candidates':c['candidates'],'candidate_boundary_matrix':c['candidate_boundary_matrix']})\n    write(out/'VCD_BREADTH_EVOLUTION.json',{'schema':'server-tb-vcd-breadth-evolution-runtime-v1','package_id':a.package_id,'diagnostic_round':c['diagnostic_round'],'catalog_signal_count':len(signals)})",
        1,
    )
    text = text.replace(
        "'signal':'NONE'",
        "'signal':('NONE' if proc.get('received_signal') is None else {1:'HUP',2:'INT',15:'TERM'}.get(proc.get('received_signal'),str(proc.get('received_signal'))))",
        1,
    )
    return text


def patch_runner(text: str) -> str:
    old = '--stop-control "$run_root/c0/shared_stop.control" -- "$simv"'
    new = '--stop-control "$run_root/c0/shared_stop.control" --console-log "$run_root/c0/sim_console.log" -- "$simv"'
    if old not in text:
        raise RuntimeError("runner supervisor console anchor absent")
    text = text.replace(old, new, 1)
    text = text.replace(
        "# V94: appended-VCD-time supervision, exact post-dumpoff marker/grace, PID-starttime reaping.",
        "# V95: source-heartbeat-filtered shared evaluation, tokenized stop control, full hierarchy catalog and console capture.",
        1,
    )
    return text


def update_post_request(signals: list[dict[str, Any]]) -> None:
    path = TREE / "contracts/server_post_sim_return_request.json"
    request = json.loads(path.read_text(encoding="utf-8"))
    existing = {row["archive"] for row in request["core_entries"]}
    additions = [
        {
            "archive": "evidence/vcd/VCD_BREADTH_EVOLUTION.json",
            "required": False,
            "source": "evidence/vcd/VCD_BREADTH_EVOLUTION.json",
            "source_root": "attempt",
        },
        {
            "archive": "runs/c0/sim_console.log",
            "required": False,
            "source": "c0/sim_console.log",
            "source_root": "attempt",
        },
    ]
    for relative in sorted({row["source_path"] for row in signals}):
        archive = f"evidence/compiled_source/actual_source_files/{Path(relative).name}"
        additions.append(
            {
                "archive": archive,
                "required": False,
                "source": f"evidence/compiled_source/actual_sources/{relative}",
                "source_root": "attempt",
            }
        )
    for row in additions:
        if row["archive"] not in existing:
            request["core_entries"].append(row)
            existing.add(row["archive"])
    request["package_id"] = PACKAGE
    request["claim_boundary"] = "Unbounded bounded-cone VCD, exact breadth/runtime/source/core receipts and console log; no sampling, truncation or size deletion."
    write_json(path, request)


def update_allowlist() -> None:
    request = json.loads((TREE / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))
    members = [f"{PACKAGE}_return/{row['archive']}" for row in request["core_entries"]]
    members.append(f"{PACKAGE}_return/RETURN_CORE_MANIFEST.json")
    allowlist = {
        "schema": "server-tb-vcd-return-allowlist-v1",
        "package_id": PACKAGE,
        "required_or_conditional_exact_members": sorted(set(members)),
        "prefixes": [],
        "no_size_limit": True,
        "hard_truncation": False,
        "sampling": False,
        "size_based_deletion": False,
    }
    write_json(TREE / "RETURN_ALLOWLIST.json", allowlist)


def update_mode_selector_members() -> None:
    path = TREE / "contracts/diagnostic_mode_selector.json"
    selector = json.loads(path.read_text(encoding="utf-8"))
    selector["package_id"] = PACKAGE
    selector["package_members"] = sorted(
        f"{PACKAGE}/{member.relative_to(TREE).as_posix()}"
        for member in TREE.rglob("*")
        if member.is_file()
    )
    write_json(path, selector)


def refresh_bound_contract_identities() -> None:
    runner_contract_path = TREE / "contracts/server_runner_return_resilience.json"
    runner_contract = json.loads(runner_contract_path.read_text(encoding="utf-8"))
    runner_contract["package_id"] = PACKAGE
    runner_contract["runner_sha256"] = sha(TREE / "PREPARE_AND_RUN.sh")
    write_json(runner_contract_path, runner_contract)

    post_contract_path = TREE / "contracts/server_post_sim_return_contract.json"
    post_contract = json.loads(post_contract_path.read_text(encoding="utf-8"))
    post_contract["package_id"] = PACKAGE
    post_contract["request_sha256"] = sha(TREE / "contracts/server_post_sim_return_request.json")
    post_contract["helper_sha256"] = sha(TREE / "package_tools/server_post_sim_return.py")
    write_json(post_contract_path, post_contract)


def file_rows() -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(TREE).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha(path),
        }
        for path in sorted(item for item in TREE.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    ]


def deterministic_zip() -> None:
    manifest_path = TREE / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "node0004-v95b-tbvcd-metapair-package-manifest-v1",
            "package_id": PACKAGE,
            "status": "PACKAGE_READY_NOT_RUN",
            "previous_version_progress": "v94b compiled, entered the target and narrowed the stable hold to a mismatch between five prepared-data groups and three WR metadata groups; user INT ended the non-natural run.",
            "current_purpose": "Distinguish WR_Memory_AG metadata lifetime ending early from Buffer_AG/RD_Buffer data lifetime overrunning, while fixing v94 runtime-v3 sample, stop-control, catalog and console-return defects.",
            "source_return_analysis": "provenance/v94b_return_analysis.json",
            "rule_gap_audit": "provenance/v94b_rule_gap_audit.json",
            "rule_audit_disposition": "RULE_DELTA_PROPOSAL_WITH_PACKAGE_IMPLEMENTATION",
            "retired_ack_comparator_present": False,
            "storage_status": "STAGED_AWAITING_MAINLINE_SERIAL_RELEASE",
        }
    )
    manifest["files"] = file_rows()
    write_json(manifest_path, manifest)
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(FINAL_ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(TREE.rglob("*"), key=lambda item: item.relative_to(TREE).as_posix()):
            if not path.is_file():
                continue
            relative = f"{PACKAGE}/{path.relative_to(TREE).as_posix()}"
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.suffix in {".sh", ".py"} else 0o644) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def replace_package_identity() -> None:
    textual = {".py", ".sh", ".json", ".md", ".txt"}
    for path in TREE.rglob("*"):
        if path.is_file() and path.suffix.lower() in textual:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if PREVIOUS in text:
                path.write_text(text.replace(PREVIOUS, PACKAGE), encoding="utf-8", newline="\n")


def main() -> int:
    if not SOURCE_TREE.is_dir() or not RETURN_ZIP.is_file() or not ANALYSIS.is_file() or not RULE_AUDIT.is_file():
        raise RuntimeError("v94 source tree, formal return, analysis or rule audit is absent")
    OUT.mkdir(parents=True, exist_ok=True)
    if TREE.exists():
        shutil.rmtree(TREE)
    shutil.copytree(SOURCE_TREE, TREE)
    for cache in sorted(TREE.rglob("__pycache__"), reverse=True):
        if cache.is_dir():
            shutil.rmtree(cache)
    for bytecode in TREE.rglob("*.pyc"):
        bytecode.unlink()
    replace_package_identity()
    v94 = load_v94()
    signals = v94.make_signals()
    normalize_signals(signals)
    signals.extend(additions())
    by_id = {row["signal_id"]: row for row in signals}
    for signal_id in ("sig_cfg_mem_idx_mode", "sig_cfg_mem_keep_last", "sig_cfg_transaction_total_size", "sig_memidx_all_matched", "sig_memidx_buffer_last", "sig_memidx_buffer_last_index", "sig_memidx_queue_wr", "sig_memidx_queue_empty", "sig_meta_transfer_valid", "sig_meta_output_ready", "sig_meta_transaction_valid", "sig_meta_transaction_finish", "sig_meta_size_left"):
        assign_driver(by_id[signal_id], "metadata_generation_lifetime_ends_early")
    for signal_id in ("sig_idx_mode", "sig_cfg_buf_keep_last", "sig_all_match", "sig_buf_last_masked", "sig_buf_selected_last", "sig_buf_selected_last_index"):
        assign_driver(by_id[signal_id], "buffer_data_generation_lifetime_overruns")

    probe = patch_probe_stop_token(v94.make_probe(signals))
    probe_path = TREE / "tb_probe/tb_vcd_bounded_causal_cone.svh"
    probe_path.write_text(probe, encoding="utf-8", newline="\n")

    provenance = TREE / "provenance"
    shutil.copyfile(SOURCE_TREE / "tb_probe/tb_vcd_bounded_causal_cone.svh", provenance / "v94b_tb_vcd_bounded_causal_cone.svh")
    shutil.copyfile(ANALYSIS, provenance / "v94b_return_analysis.json")
    shutil.copyfile(RULE_AUDIT, provenance / "v94b_rule_gap_audit.json")
    actual = actual_compile_identity()
    write_json(provenance / "v94b_actual_compile_source_identity.json", actual)
    shutil.copyfile(FROZEN_CONFIG, provenance / "frozen_node0004_wave0_config.json")
    shutil.copyfile(CONFIG_EVIDENCE / "local_rebuild_report.json", provenance / "v62_config_consumer_rebuild_report.json")
    shutil.copyfile(CONFIG_EVIDENCE / "causal_transaction_ledger.json", provenance / "v62_config_causal_transaction_ledger.json")
    shutil.copyfile(CONFIG_EVIDENCE / "boundary_microtrace.json", provenance / "v62_config_boundary_microtrace.json")
    write_json(
        provenance / "v95_config_actual_consumer_validation_plan.json",
        {
            "schema": "node0004-v95-config-actual-consumer-validation-plan-v1",
            "package_id": PACKAGE,
            "frozen_config": "provenance/frozen_node0004_wave0_config.json",
            "frozen_bitstream_sha256": "2f79247677c0ae8a8f89ac1bca7f381d757e28d049c7eef88e8f0bfae75d90fa",
            "stream4_expected": {
                "mode": "write",
                "buf_idx_mode": ["keep", "buffer"],
                "buf_idx_keep_last_index": [5, 5],
                "buf_spatial_size": 16,
                "mem_idx_mode": ["keep", "buffer", "keep"],
                "mem_idx_keep_last_index": [0, 3, 1],
            },
            "lc_pe_expected": {
                "PE1.inport0.mode": "keep",
                "PE1.inport0.keep_last_index": 3,
                "PE1.inport0.src_id": "DRAM_LC.LC15",
                "PE1.inport2.mode": "buffer",
                "PE1.inport2.src_id": "DRAM_LC.LC9",
            },
            "runtime_signal_ids": [
                "sig_cfg_mem_idx_mode", "sig_cfg_mem_keep_last", "sig_idx_mode",
                "sig_cfg_buf_keep_last", "sig_cfg_transaction_total_size",
                "sig_memidx_all_matched", "sig_memidx_buffer_last",
                "sig_memidx_buffer_last_index", "sig_memidx_queue_wr",
                "sig_memidx_queue_rd", "sig_memidx_queue_empty", "sig_memidx_queue_full",
            ],
            "required_actual_sources": [WR_TOP, MEM_IDX, WR_MEM, BUFFER],
            "root_policy": "VALIDATED_ROOT_CAUSE only if config-to-runtime-consumer values, actual compiled source logic and dynamic state transitions form one unique causal chain; otherwise OPEN_UNVALIDATED_MECHANISM and no config workaround.",
        },
    )
    pinned = pinned_rtl_identity(actual)

    baseline_signals = v94.make_signals()
    normalize_signals(baseline_signals)
    baseline = baseline_receipt(
        pinned,
        baseline_signals,
        [{**row, "priority": PRIORITY[row["candidate_id"]]} for row in v94.build_contract(v94.make_signals(), "0" * 64)["candidates"]],
    )
    baseline_path = provenance / "v94b_round3_breadth_baseline.json"
    write_json(baseline_path, baseline)
    prior, contract = patch_contract(v94, signals, sha(probe_path), pinned)
    prior_path = provenance / "v94b_current_schema_round1_contract.json"
    write_json(prior_path, prior)
    contract["diagnostic_round"]["evolution"]["predecessor"]["contract_sha256"] = sha(prior_path)
    write_json(TREE / "contracts/tb_vcd_bounded_causal_cone_contract.json", contract)

    supervisor_path = TREE / "package_tools/node0004_tb_vcd_process_supervisor.py"
    supervisor_path.write_text(patch_supervisor(supervisor_path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    finalizer_path = TREE / "package_tools/node0004_tb_vcd_finalize.py"
    finalizer_path.write_text(patch_finalizer(finalizer_path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    runner_path = TREE / "PREPARE_AND_RUN.sh"
    runner_path.write_text(patch_runner(runner_path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    update_post_request(signals)
    update_allowlist()

    readme = (
        f"# {PACKAGE}\n\n"
        "Previous progress: v94b compiled and entered the target. Streaming VCD analysis found five 16-entry prepared-data writes but only three matching WR metadata groups; the final prepared count was 32. The run did not finish naturally and was ended by user INT.\n\n"
        "Current purpose: distinguish WR_Memory_AG metadata lifetime ending early from Buffer_AG/RD_Buffer data lifetime overrunning. The 73 prior signals are retained and the actual zero-hop metadata/last-state drivers are added. Runtime-v3 now evaluates only source-heartbeat rows (plus 30-second fixed-time and terminal rows), uses a tokenized pre-created stop control, reconstructs full VCD hierarchy, and returns simulator console output separately.\n\n"
        "Evidence policy: frozen config and its runtime consumer nets, actual compiled RTL sources/drivers, and dynamic state transitions are independent direct-evidence layers. A root is VALIDATED only when those layers form one contradiction or unique causal chain. Until then the classification remains OPEN_UNVALIDATED_MECHANISM and this package makes no configuration-workaround recommendation.\n\n"
        "Run only after separate authorization:\n\n"
        f"    bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01\n\n"
        "No upload, lease or server run has occurred. The package is staged and intentionally not published to pending storage.\n"
    )
    (TREE / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    refresh_bound_contract_identities()
    update_mode_selector_members()
    deterministic_zip()
    write_json(
        OUT / "build_receipt.json",
        {
            "schema": "node0004-v95b-tbvcd-metapair-build-v1",
            "package_id": PACKAGE,
            "source_formal_return": str(RETURN_ZIP),
            "source_return_analysis": ANALYSIS.relative_to(ROOT).as_posix(),
            "rule_gap_audit": RULE_AUDIT.relative_to(ROOT).as_posix(),
            "authorized_changes": [
                "fresh identity",
                "WR_Memory_AG and Buffer_AG zero-hop causal leaves",
                "source-heartbeat-filtered shared runtime evaluation",
                "tokenized package-owned stop control",
                "full-hierarchy VCD catalog validation",
                "separate simulator console capture",
                "signal-consistent exit receipt",
            ],
            "signal_count": len(signals),
            "retained_predecessor_signal_count": len(v94.make_signals()),
            "removed_signal_count": 0,
            "status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES",
            "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
            "zip": {"path": FINAL_ZIP.relative_to(ROOT).as_posix(), "bytes": FINAL_ZIP.stat().st_size, "sha256": sha(FINAL_ZIP)},
            "pass": True,
            "errors": [],
        },
    )
    print(FINAL_ZIP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
