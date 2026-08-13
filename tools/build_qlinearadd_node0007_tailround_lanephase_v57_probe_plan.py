"""Build the v57 low-overhead generated Buffer lane-phase probe plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from generate_server_source_bound_observer import semantic_sha256


PACKAGE_ID = "r5_qadd_n7_tailround_lanephase_qual_v57"
TARGET = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
    "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice."
    "u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer"
)
NEAR_MISS = TARGET.replace("BUFFER_MANAGER[5]", "BUFFER_MANAGER[4]")


def sig(symbol: str) -> dict[str, object]:
    return {"op": "SIGNAL", "symbol_id": symbol}


def neg(symbol: str) -> dict[str, object]:
    return {"op": "NOT", "arg": sig(symbol)}


def and_(*items: dict[str, object]) -> dict[str, object]:
    return {"op": "AND", "args": list(items)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-id", default=PACKAGE_ID)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--identity-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    symbols = {(item["module"], item["name"]): item for item in catalog["symbols"]}

    def sym(name: str) -> str:
        return symbols[("Buffer", name)]["symbol_id"]

    clk, rst = sym("clk"), sym("rst_n")
    arm_wvalid = sym("arm2buf_wvalid")
    write_ready = sym("buf_wreq_ready")
    read_ready = sym("buf2mrm_rreq_ready")
    read_valid = sym("buf2mrm_rvalid")
    payload = [write_ready, read_ready, arm_wvalid, read_valid]
    provenance = {
        "path": args.identity_source.as_posix(),
        "sha256": hashlib.sha256(args.identity_source.read_bytes()).hexdigest(),
        "selector": "v54 exact Buffer5 group0/local-slice0 target retained; v56 proved all-instance probe fanout and pre-stage contamination",
    }
    def common(boundary_id: str, role: str) -> dict[str, object]:
        monitor = f".codex_probe_{boundary_id}_inst"
        return {
            "boundary_id": boundary_id,
            "role": role,
            "target_module": "Buffer",
            "clock_symbol_id": clk,
            "reset": {"symbol_id": rst, "active_low": True},
            "stage_gate": {"op": "CONST", "value": True},
            "instance_scope": {
                "mode": "EXACT_CANONICAL_INSTANCE",
                "expected_instances": [TARGET + monitor],
                "near_miss_instances": [NEAR_MISS + monitor],
                "identity_provenance": provenance,
            },
            "payload_symbol_ids": payload,
            "payload_contract": {
                "width_bits": 4,
                "required_binary_known": True,
                "unknown_disposition": "EVIDENCE_INCOMPLETE",
            },
        }
    boundaries = [
        {
            **common("buffer5_lanephase_write", "source_produce"),
            "classes": [
                {"class_id": "arm_write_accept", "bit": 0, "progress": True, "trigger": False, "predicate": and_(sig(arm_wvalid), sig(write_ready))},
                {"class_id": "arm_write_blocked", "bit": 1, "progress": False, "trigger": True, "predicate": and_(sig(arm_wvalid), neg(write_ready))},
            ],
        },
        {
            **common("buffer5_lanephase_ready", "internal_match_compute"),
            "classes": [
                {"class_id": "selected_read_ready_true", "bit": 0, "progress": False, "trigger": False, "predicate": sig(read_ready)},
                {"class_id": "selected_read_ready_false", "bit": 1, "progress": False, "trigger": True, "predicate": neg(read_ready)},
            ],
        },
        {
            **common("buffer5_lanephase_result", "queue_dequeue"),
            "classes": [
                {"class_id": "mrm_read_result", "bit": 0, "progress": True, "trigger": False, "predicate": sig(read_valid)},
                {"class_id": "no_mrm_read_result", "bit": 1, "progress": False, "trigger": True, "predicate": neg(read_valid)},
            ],
        },
    ]
    observations = [
        {"observation_id": "arm_accept", "boundary_id": "buffer5_lanephase_write", "metric": "count_nonzero", "class_id": "arm_write_accept"},
        {"observation_id": "arm_blocked", "boundary_id": "buffer5_lanephase_write", "metric": "class_seen", "class_id": "arm_write_blocked"},
        {"observation_id": "read_result", "boundary_id": "buffer5_lanephase_result", "metric": "class_seen", "class_id": "mrm_read_result"},
        {"observation_id": "read_ready_false", "boundary_id": "buffer5_lanephase_ready", "metric": "class_seen", "class_id": "selected_read_ready_false"},
    ]
    candidates = [
        {"candidate_id": "residual_lane_blocks_next_arm_write", "root_cause_class": "TEMPORAL_LANE_PHASE_PRODUCER_BLOCKED", "signature": {"arm_accept": True, "arm_blocked": True, "read_result": True, "read_ready_false": True}},
        {"candidate_id": "first_read_never_produces_result", "root_cause_class": "CONSUMER_FIRST_READ_NO_RESULT", "signature": {"arm_accept": True, "arm_blocked": False, "read_result": False, "read_ready_false": True}},
        {"candidate_id": "producer_never_attempts_second_write", "root_cause_class": "UPSTREAM_SECOND_OUTPUT_ABSENT", "signature": {"arm_accept": True, "arm_blocked": False, "read_result": True, "read_ready_false": True}},
        {"candidate_id": "legacy_selected_ready_mismatch", "root_cause_class": "LEGACY_OBSERVER_SELECTED_READY_MISMATCH", "signature": {"arm_accept": True, "arm_blocked": False, "read_result": True, "read_ready_false": False}},
    ]
    role_coverage = [
        {"role": "source_produce", "disposition": "covered", "boundary_ids": ["buffer5_lanephase_write"], "reason": "Generated write accept/block boundary."},
        {"role": "queue_dequeue", "disposition": "covered", "boundary_ids": ["buffer5_lanephase_result"], "reason": "Generated MRM read-result boundary."},
        {"role": "internal_match_compute", "disposition": "covered", "boundary_ids": ["buffer5_lanephase_ready"], "reason": "Generated selected read-ready boundary."},
        {"role": "queue_enqueue", "disposition": "not_applicable", "boundary_ids": [], "reason": "v54 already proved the first accepted Buffer5 write; v57 does not re-probe that byte-equal edge."},
        {"role": "consumer_accept", "disposition": "not_applicable", "boundary_ids": [], "reason": "The byte-equal Q53 observer supplies request-valid and selected-ready state; v57 only adds source-bound result chronology."},
        {"role": "output_accept", "disposition": "not_applicable", "boundary_ids": [], "reason": "MRM read result is the decisive downstream boundary; duplicate output-valid probe was removed."},
        {"role": "terminal_propagation", "disposition": "not_applicable", "boundary_ids": [], "reason": "Byte-equal ordered-stage observer remains authoritative."},
        {"role": "formal_d_collection", "disposition": "not_applicable", "boundary_ids": [], "reason": "Byte-equal 28D result gate remains authoritative."},
    ]
    plan = {
        "schema": "server-source-bound-probe-plan-v2",
        "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "profile": "HIGH_INFORMATION_CAUSAL_V1",
        "package_id": args.package_id,
        "family": "qlinearadd_node0007",
        "catalog_identity": {
            "rtl_tree_sha256": catalog["rtl_identity"]["rtl_tree_sha256"],
            "catalog_semantic_sha256": semantic_sha256(catalog),
        },
        "diagnostic_semantics": {
            "instance_match": "EXACT_CANONICAL_EQUALITY",
            "record_grouping_key": ["boundary_id", "canonical_instance", "seq"],
            "unknown_payload": "EVIDENCE_INCOMPLETE",
            "numeric_parse_failure": "EVIDENCE_INCOMPLETE",
            "candidate_match_cardinality": "EXACTLY_ONE",
            "stage_qualification": "PACKAGE_LOCAL_EXEC_START_FILTER_BEFORE_GENERATED_PARSER",
        },
        "boundaries": boundaries,
        "role_coverage": role_coverage,
        "decision_observations": observations,
        "candidates": candidates,
        "runtime_budget": {
            "qualified_ring_depth": 32,
            "non_progress_ring_depth": 16,
            "first_payload_samples": 8,
            "post_trigger_samples": 16,
            "no_progress_cycles": 1048576,
            "max_log_bytes": 8388608,
            "state_activity_consumes_qualified_budget": False,
            "multiclass_encoding": "BITMAP_ALL_TRUE_CLASSES",
            "text_io_policy": "FIRST_SAMPLES_TRIGGER_AND_FINAL_ONLY",
            "slowdown_limit_hard": False,
        },
        "claim_boundary": "Read-only exact Buffer5 lane-phase chronology after ordered EXEC_START; old observer, workload, config, numeric, golden, timeout and functional RTL remain byte-equal.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(args.output), "plan_semantic_sha256": semantic_sha256(plan), "boundaries": len(boundaries), "candidates": len(candidates)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
