#!/usr/bin/env python3
"""Prepare p34 live ARM token/counter source-bound observation."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p34_armtoken"
P33 = ROOT / "outputs/conv_native_four_lane_0ccae916_p33b_wrowner_source_bound"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p34_armtoken_source_bound"
CATALOG = OUTPUT / "source_bound_probe_catalog.json"
PLAN = OUTPUT / "source_bound_probe_plan.json"
CONTRACT = OUTPUT / "arm_token_contract.json"
EPOCH = OUTPUT / "epoch_reuse_receipt.json"
PARSER = ROOT / "tools/conv_native_four_lane_p34_arm_token_parser.py"
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
        raise RuntimeError("refusing to overwrite p34 source-bound inputs")
    if sha(PRIOR_PASS) != PRIOR_PASS_SHA:
        raise RuntimeError("p31 first-fresh PASS identity differs")
    OUTPUT.mkdir(parents=True)
    shutil.copyfile(P33 / "source_bound_probe_catalog.json", CATALOG)
    old = json.loads((P33 / "source_bound_probe_plan.json").read_text(encoding="utf-8"))
    by_id = {row["boundary_id"]: row for row in old["boundaries"]}
    window = copy.deepcopy(by_id["row2_clear_window_write_owner"])
    final = copy.deepcopy(by_id["final_same_row2_block"])
    accept = both(
        signal("sym_d01e809dba33e9f8804c2134"),
        ne("sym_2a5b34ebdcc84c7e8874046a", 0),
        eq("sym_40752e6209bff9636a0bd42b", 2),
        signal("sym_35f6830e300bb301d8ffb218"),
        signal("sym_7f6e8d81d4bbb466298f0546"),
    )
    class_signals = (
        (1, "ARM_ADD_ARRAY_REQ_ADDR", "sym_e8d98d6f89e1060097f7a266"),
        (2, "ARM_ADD_ARRAY_COUNTER0", "sym_62a6e8c1035cc527a58fb2de"),
        (3, "ARM_ADD_ARRAY_COUNTER1", "sym_7680e276016a1ed1563b4bf7"),
        (4, "ARM_ADD_ARRAY_LIFE", "sym_dfcfd3066f84c568106c0317"),
        (5, "ARM_ARRAY_WREQ_ADDR_RESET", "sym_fc1cc140bff2f03bfad36cac"),
        (6, "ARM_SAME_TOKEN", "sym_457c23a5cafd636e04aaa064"),
        (7, "ARM_LAST_TOKEN", "sym_0c3cbc46043128a6dc4e1dac"),
    )
    arm = {
        "boundary_id": "arm_row2_accept_token_state",
        "target_module": "Array_Request_Manager",
        "clock_symbol_id": "sym_eee02fb40622d4c13ff96a82",
        "reset": {"symbol_id": "sym_d33e799edf0951a0d826b190", "active_low": True},
        "stage_gate": {"op": "NOT", "arg": signal("sym_c52acf39d6a236fe4034826d")},
        "role": "source_produce",
        "payload_symbol_ids": [
            "sym_40752e6209bff9636a0bd42b", "sym_2a5b34ebdcc84c7e8874046a",
            "sym_4777160a2b61a2ef921052e0", "sym_35f6830e300bb301d8ffb218",
            "sym_7f6e8d81d4bbb466298f0546", "sym_bb63525882c666e7aa7283c4",
            "sym_51dc1a5235ac0708a5764ae7", "sym_784ffb556338b0ad19a894c1",
            "sym_39d479221c317e013a1b5e11", "sym_d7698da265ea5f7e76475170",
            "sym_0c3cbc46043128a6dc4e1dac", "sym_a44d51a2f896a471527a8eec",
            "sym_457c23a5cafd636e04aaa064", "sym_fc1cc140bff2f03bfad36cac",
            "sym_839345a108a1d69fed1ceb4b", "sym_e8d98d6f89e1060097f7a266",
            "sym_62a6e8c1035cc527a58fb2de", "sym_7680e276016a1ed1563b4bf7",
            "sym_dfcfd3066f84c568106c0317",
        ],
        "classes": [
            {"bit": 0, "class_id": "ARM_ROW2_WRITE_ACCEPT", "predicate": accept, "progress": True, "trigger": True},
            *[
                {"bit": bit, "class_id": class_id, "predicate": both(copy.deepcopy(accept), signal(symbol)), "progress": False, "trigger": False}
                for bit, class_id, symbol in class_signals
            ],
        ],
    }
    observations = [
        {"observation_id": "accept", "boundary_id": arm["boundary_id"], "class_id": "ARM_ROW2_WRITE_ACCEPT", "metric": "class_seen"},
        *[
            {"observation_id": f"class_{bit}", "boundary_id": arm["boundary_id"], "class_id": class_id, "metric": "class_seen"}
            for bit, class_id, _ in class_signals
        ],
    ]
    candidates = [
        {"candidate_id": "arm_accept_no_aux", "root_cause_class": "ARM_ACCEPT_NO_AUX", "signature": {"accept": True, **{f"class_{bit}": False for bit, _, _ in class_signals}}},
        *[
            {"candidate_id": f"arm_class_{bit}", "root_cause_class": class_id, "signature": {"accept": True, **{f"class_{other}": other == bit for other, _, _ in class_signals}}}
            for bit, class_id, _ in class_signals
        ],
    ]
    plan = {
        "schema": "server-source-bound-probe-plan-v1", "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "package_id": PACKAGE_ID, "family": "conv_native_four_lane_node0004", "profile": "HIGH_INFORMATION_CAUSAL_V1",
        "catalog_identity": copy.deepcopy(old["catalog_identity"]), "boundaries": [window, arm, final],
        "decision_observations": observations, "candidates": candidates,
        "runtime_budget": {**old["runtime_budget"], "post_trigger_samples": 8},
        "role_coverage": [
            {"role": "source_produce", "boundary_ids": [arm["boundary_id"]], "disposition": "covered", "reason": "Every accepted ARM row2 token emits live state."},
            {"role": "queue_enqueue", "boundary_ids": [], "disposition": "not_applicable", "reason": "The Buffer boundary is typed queue_dequeue; its live event remains the exact accepted-write anchor."},
            {"role": "queue_dequeue", "boundary_ids": [window["boundary_id"]], "disposition": "covered", "reason": "Exact f0 clear anchor."},
            {"role": "consumer_accept", "boundary_ids": [], "disposition": "not_applicable", "reason": "The source_produce boundary includes the ready handshake without changing its role type."},
            {"role": "internal_match_compute", "boundary_ids": [final["boundary_id"]], "disposition": "covered", "reason": "Same-parent final row2 marker."},
            {"role": "output_accept", "boundary_ids": [], "disposition": "not_applicable", "reason": "Bounded Buffer5 diagnostic."},
            {"role": "terminal_propagation", "boundary_ids": [], "disposition": "not_applicable", "reason": "Bounded c0 diagnostic."},
            {"role": "formal_d_collection", "boundary_ids": [], "disposition": "not_applicable", "reason": "Frozen formal_readback_count=0."},
        ],
        "claim_boundary": "Live exact-target Buffer clear/write anchors plus ARM token/counter/reset state; no final-block ring dependency.",
    }
    write(PLAN, plan)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    symbols = {row["symbol_id"]: row for row in catalog["symbols"]}
    layout = [{"name": symbols[symbol]["name"], "symbol_id": symbol, "width_bits": symbols[symbol]["width_bits"]} for symbol in arm["payload_symbol_ids"]]
    contract = {
        "schema": "conv-native-four-lane-p34-arm-token-contract-v1", "package_id": PACKAGE_ID,
        "target_parent": (
            "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
            "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU."
            "u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager"
        ),
        "buffer_boundary": window["boundary_id"], "arm_boundary": arm["boundary_id"], "final_boundary": final["boundary_id"],
        "required_boundaries": [window["boundary_id"], arm["boundary_id"], final["boundary_id"]],
        "buffer_arm_accept_bit": 1, "reset_class_bit": 5,
        "arm_payload_layout_msb_to_lsb": layout,
        "token_state_fields": ["array_req_addr", "array_counter_0", "array_counter_1", "array_life_cnt", "array2buf_valid_bit", "array2buf_last_bit", "array2buf_last_index", "array2buf_same_bit"],
        "source_bound_plan_sha256": sha(PLAN), "target_parser_source_sha256": sha(PARSER),
        "claim_boundary": "Live exact-target records only; Buffer and ARM accepted-write times must match and remain inside one clear/final epoch.",
    }
    write(CONTRACT, contract)
    shutil.copyfile(PARSER, OUTPUT / "generated_arm_token_parser.py")
    write(EPOCH, {"schema": "conv-native-first-fresh-epoch-reuse-v1", "epoch_id": "20260810-first-fresh-extra-audit-v1", "family": "conv_native_four_lane", "package_id": PACKAGE_ID, "first_fresh_after_change": False, "prior_pass_path": PRIOR_PASS.relative_to(ROOT).as_posix(), "prior_pass_sha256": PRIOR_PASS_SHA})
    print(json.dumps({"catalog_sha256": sha(CATALOG), "plan_sha256": sha(PLAN), "contract_sha256": sha(CONTRACT), "epoch_sha256": sha(EPOCH)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
