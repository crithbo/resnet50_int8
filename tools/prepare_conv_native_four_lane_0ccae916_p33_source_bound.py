#!/usr/bin/env python3
"""Prepare the generated p33 clear-window write-owner observer inputs."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p33b_wrowner"
P32 = ROOT / "outputs/conv_native_four_lane_0ccae916_p32b_validowner_source_bound"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p33b_wrowner_source_bound"
CATALOG = OUTPUT / "source_bound_probe_catalog.json"
PLAN = OUTPUT / "source_bound_probe_plan.json"
CONTRACT = OUTPUT / "target_epoch_write_owner_contract.json"
EPOCH = OUTPUT / "epoch_reuse_receipt.json"
PARSER = ROOT / "tools/conv_native_four_lane_p33_target_epoch_write_owner_parser.py"
PRIOR_PASS = ROOT / "outputs/conv_native_four_lane_0ccae916_p31_postclear/first_fresh_extra_audit/validation.json"
PRIOR_PASS_SHA = "48c58b614af0ba1fe311d454e5229d4f000a5b944d711e52a8c43ecc85ab0ec1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def signal(symbol: str) -> dict[str, Any]:
    return {"op": "SIGNAL", "symbol_id": symbol}


def eq(symbol: str, value: int) -> dict[str, Any]:
    return {"op": "EQ", "symbol_id": symbol, "value": value}


def ne(symbol: str, value: int) -> dict[str, Any]:
    return {"op": "NE", "symbol_id": symbol, "value": value}


def both(*args: dict[str, Any]) -> dict[str, Any]:
    return {"op": "AND", "args": list(args)}


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p33 source-bound inputs")
    if sha(PRIOR_PASS) != PRIOR_PASS_SHA:
        raise RuntimeError("p31 first-fresh PASS identity differs")
    OUTPUT.mkdir(parents=True)
    shutil.copyfile(P32 / "source_bound_probe_catalog.json", CATALOG)
    old = json.loads((P32 / "source_bound_probe_plan.json").read_text(encoding="utf-8"))
    by_id = {row["boundary_id"]: row for row in old["boundaries"]}
    old_clear = by_id["row2_clear_f0_at_0f"]
    old_post = by_id["row2_postclear_bank_0f_no_write_accept"]
    final = copy.deepcopy(by_id["final_same_row2_block"])

    # One broad-stage, exact-clear-triggered boundary is intentional: generated
    # RING_POST samples then remain active after mrm_clear deasserts and cover the
    # full clear-to-post interval.  Owner bits describe the effective Buffer mux
    # priority, not merely simultaneous request levels.
    window = {
        "boundary_id": "row2_clear_window_write_owner",
        "target_module": "Buffer",
        "clock_symbol_id": old_clear["clock_symbol_id"],
        "reset": copy.deepcopy(old_clear["reset"]),
        "stage_gate": {
            "op": "NOT",
            "arg": signal("sym_3d436453f9e6305dc4d6dbe0"),
        },
        "payload_symbol_ids": copy.deepcopy(old_clear["payload_symbol_ids"]),
        "role": "queue_dequeue",
        "classes": [
            {
                "bit": 0, "class_id": "ROW2_CLEAR_F0_AT_0F",
                "predicate": copy.deepcopy(old_clear["stage_gate"]),
                "progress": False, "trigger": True,
            },
            {
                "bit": 1, "class_id": "ROW2_EFFECTIVE_ARM_WRITE_ACCEPT",
                "predicate": both(
                    signal("sym_50a1e2b0cddc9fab137545b7"),
                    eq("sym_c572af4ecaef9e2b953e4c4e", 2),
                    eq("sym_bb8d3aebf9d6d097f2d710f5", 0),
                    ne("sym_1d55190d21ef83a4ff06ea5a", 0),
                ),
                "progress": True, "trigger": False,
            },
            {
                "bit": 2, "class_id": "ROW2_EFFECTIVE_MRM_WRITE_ACCEPT",
                "predicate": both(
                    signal("sym_50a1e2b0cddc9fab137545b7"),
                    eq("sym_c572af4ecaef9e2b953e4c4e", 2),
                    ne("sym_bb8d3aebf9d6d097f2d710f5", 0),
                ),
                "progress": True, "trigger": False,
            },
            {
                "bit": 3, "class_id": "ROW2_EFFECTIVE_NRM_WRITE_ACCEPT",
                "predicate": both(
                    signal("sym_50a1e2b0cddc9fab137545b7"),
                    eq("sym_c572af4ecaef9e2b953e4c4e", 2),
                    eq("sym_bb8d3aebf9d6d097f2d710f5", 0),
                    eq("sym_1d55190d21ef83a4ff06ea5a", 0),
                    ne("sym_cee6ab4989ac278d485f77dc", 0),
                ),
                "progress": True, "trigger": False,
            },
            {
                "bit": 4, "class_id": "ROW2_POSTCLEAR_BANK_0F_BLOCKED",
                "predicate": copy.deepcopy(old_post["stage_gate"]),
                "progress": False, "trigger": False,
            },
        ],
    }
    boundaries = [window, final]
    observations = [
        {"observation_id": "clear_seen", "boundary_id": window["boundary_id"], "class_id": "ROW2_CLEAR_F0_AT_0F", "metric": "class_seen"},
        {"observation_id": "arm_accept_seen", "boundary_id": window["boundary_id"], "class_id": "ROW2_EFFECTIVE_ARM_WRITE_ACCEPT", "metric": "class_seen"},
        {"observation_id": "mrm_accept_seen", "boundary_id": window["boundary_id"], "class_id": "ROW2_EFFECTIVE_MRM_WRITE_ACCEPT", "metric": "class_seen"},
        {"observation_id": "nrm_accept_seen", "boundary_id": window["boundary_id"], "class_id": "ROW2_EFFECTIVE_NRM_WRITE_ACCEPT", "metric": "class_seen"},
        {"observation_id": "post_0f_seen", "boundary_id": window["boundary_id"], "class_id": "ROW2_POSTCLEAR_BANK_0F_BLOCKED", "metric": "class_seen"},
        {"observation_id": "final_seen", "boundary_id": final["boundary_id"], "class_id": "FINAL_SAME_ROW2_BLOCK", "metric": "class_seen"},
    ]
    candidates = [
        {
            "candidate_id": "target_final_not_reached",
            "root_cause_class": "TARGET_FINAL_NOT_REACHED",
            "signature": {"clear_seen": True, "arm_accept_seen": False, "mrm_accept_seen": False, "nrm_accept_seen": False, "post_0f_seen": False, "final_seen": False},
        },
        {
            "candidate_id": "target_post_state_not_reached",
            "root_cause_class": "TARGET_POST_STATE_NOT_REACHED",
            "signature": {"clear_seen": True, "arm_accept_seen": False, "mrm_accept_seen": False, "nrm_accept_seen": False, "post_0f_seen": False, "final_seen": True},
        },
    ]
    owner_names = ("ARM", "MRM", "NRM")
    for bitmap in range(8):
        owners = [name for index, name in enumerate(owner_names) if bitmap & (1 << index)]
        suffix = "NO_ACCEPT" if not owners else "_".join(owners) + "_ACCEPT"
        candidates.append({
            "candidate_id": f"global_owner_bitmap_{bitmap}",
            "root_cause_class": f"GLOBAL_CLEAR_WINDOW_{suffix}",
            "signature": {
                "clear_seen": True,
                "arm_accept_seen": bool(bitmap & 1),
                "mrm_accept_seen": bool(bitmap & 2),
                "nrm_accept_seen": bool(bitmap & 4),
                "post_0f_seen": True,
                "final_seen": True,
            },
        })
    plan = {
        "schema": "server-source-bound-probe-plan-v1",
        "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "package_id": PACKAGE_ID,
        "family": "conv_native_four_lane_node0004",
        "profile": "HIGH_INFORMATION_CAUSAL_V1",
        "catalog_identity": copy.deepcopy(old["catalog_identity"]),
        "boundaries": boundaries,
        "decision_observations": observations,
        "candidates": candidates,
        "runtime_budget": {
            **old["runtime_budget"],
            "post_trigger_samples": 8,
        },
        "role_coverage": [
            {"role": "source_produce", "boundary_ids": [], "disposition": "not_applicable", "reason": "p26 freezes source13 delivery."},
            {"role": "queue_enqueue", "boundary_ids": [], "disposition": "not_applicable", "reason": "The exact-clear window is classified as queue_dequeue; its payload bitmap still records effective accepted-write ownership."},
            {"role": "queue_dequeue", "boundary_ids": [window["boundary_id"]], "disposition": "covered", "reason": "Exact f0 clear is the window trigger."},
            {"role": "consumer_accept", "boundary_ids": [], "disposition": "not_applicable", "reason": "The post-clear class is state evidence inside the queue_dequeue window, not a distinct consumer boundary."},
            {"role": "internal_match_compute", "boundary_ids": [final["boundary_id"]], "disposition": "covered", "reason": "Same-parent final row2 marker."},
            {"role": "output_accept", "boundary_ids": [], "disposition": "not_applicable", "reason": "Bounded Buffer5 diagnostic."},
            {"role": "terminal_propagation", "boundary_ids": [], "disposition": "not_applicable", "reason": "Bounded c0 diagnostic."},
            {"role": "formal_d_collection", "boundary_ids": [], "disposition": "not_applicable", "reason": "Frozen formal_readback_count=0."},
        ],
        "claim_boundary": "Generated exact-clear-triggered RING_POST window with effective write-owner bitmap; family parser separately correlates exact target and epoch.",
    }
    write(PLAN, plan)
    shutil.copyfile(PARSER, OUTPUT / "generated_target_epoch_write_owner_parser.py")
    owner_candidates = []
    for bitmap in range(8):
        owners = [name for index, name in enumerate(owner_names) if bitmap & (1 << index)]
        label = "NO_ACCEPTED_WRITE" if not owners else "_AND_".join(owners) + "_ACCEPTED_WRITE"
        owner_candidates.append({
            "candidate_id": f"target_owner_bitmap_{bitmap}",
            "owner_bitmap": bitmap,
            "root_cause_class": f"TARGET_INTERVAL_{label}",
        })
    target_parent = (
        "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
        "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU."
        "u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager"
    )
    contract = {
        "schema": "conv-native-four-lane-p33-target-epoch-write-owner-contract-v1",
        "package_id": PACKAGE_ID,
        "target_parent": target_parent,
        "clear_window_boundary": window["boundary_id"],
        "final_boundary": final["boundary_id"],
        "required_boundaries": [window["boundary_id"], final["boundary_id"]],
        "post_state_class_bit": 4,
        "accepted_write_owner_bits": {"ARM": 1, "MRM": 2, "NRM": 3},
        "owner_order": list(owner_names),
        "candidates": owner_candidates,
        "source_bound_plan_sha256": sha(PLAN),
        "target_parser_source_sha256": sha(PARSER),
        "claim_boundary": "Exact target and one clear-to-post RING_POST window; other instances and pre-clear class history cannot satisfy an owner candidate.",
    }
    write(CONTRACT, contract)
    write(EPOCH, {
        "schema": "conv-native-first-fresh-epoch-reuse-v1",
        "epoch_id": "20260810-first-fresh-extra-audit-v1",
        "family": "conv_native_four_lane", "package_id": PACKAGE_ID,
        "first_fresh_after_change": False,
        "prior_pass_path": PRIOR_PASS.relative_to(ROOT).as_posix(),
        "prior_pass_sha256": PRIOR_PASS_SHA,
    })
    print(json.dumps({
        "catalog_sha256": sha(CATALOG), "plan_sha256": sha(PLAN),
        "contract_sha256": sha(CONTRACT), "epoch_sha256": sha(EPOCH),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
