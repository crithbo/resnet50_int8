#!/usr/bin/env python3
"""Generate p32 source-bound clear/post-state probes and target correlator contract."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p32b_validowner"
RTL_ROOT = ROOT / "NDP_copy01/rtl"
RTL_TREE_SHA256 = "c6902de6fabfce81ee10af02cec238e5b11d2fdece9454041415c455556e1093"
SOURCES = (
    "includes/NDP_Parameters.svh",
    "Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "Slice/LSU/Buffer_Manager_Cluster/Array_Request_Manager.sv",
)
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p32b_validowner_source_bound"
GENERATOR = ROOT / "tools/generate_server_source_bound_observer.py"
TARGET_PARSER = ROOT / "tools/conv_native_four_lane_p32_target_epoch_parser.py"


class PrepareError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def pred(op: str, symbol_id: str, value: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"op": op, "symbol_id": symbol_id}
    if value is not None:
        result["value"] = value
    return result


def conjunction(*args: dict[str, Any]) -> dict[str, Any]:
    return {"op": "AND", "args": list(args)}


def negated(arg: dict[str, Any]) -> dict[str, Any]:
    return {"op": "NOT", "arg": arg}


def main() -> int:
    if OUTPUT.exists():
        raise PrepareError(f"refusing to overwrite source-bound output: {OUTPUT}")
    OUTPUT.mkdir(parents=True)
    catalog_path = OUTPUT / "source_bound_probe_catalog.json"
    command = [
        sys.executable, str(GENERATOR), "catalog", "--rtl-root", str(RTL_ROOT),
        "--rtl-tree-sha256", RTL_TREE_SHA256,
    ]
    for source in SOURCES:
        command.extend(["--source", str(RTL_ROOT / source)])
    command.extend(["--output", str(catalog_path)])
    subprocess.run(command, cwd=ROOT, check=True)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if catalog.get("valid") is not True or catalog.get("errors"):
        raise PrepareError("catalog generation failed")
    symbols = {(item["module"], item["name"]): item["symbol_id"] for item in catalog["symbols"]}

    def sid(module: str, name: str) -> str:
        try:
            return symbols[(module, name)]
        except KeyError as error:
            raise PrepareError(f"required symbol is absent: {module}.{name}") from error

    b = {name: sid("Buffer", name) for name in (
        "clk", "rst_n", "slice_rst", "buffer_mask", "mrm2buf_req_valid", "mrm2buf_req_rw",
        "mrm2buf_req_addr", "mrm2buf_clear", "mrm2buf_wvalid", "arm2buf_req_valid",
        "arm2buf_req_rw", "arm2buf_req_addr", "buf2arm_req_ready", "arm2buf_wvalid",
        "arm2buf_last_bit", "arm2buf_last_index", "mrm2buf_wr_en", "nrm2buf_wr_en",
        "arm2buf_wr_en", "buf_wr_en", "buf_wr_addr", "valid_buf_wr_en", "valid_buf_clear",
        "buf2arm_wreq_bank_ready", "buf_wreq_ready", "tag_buf_row_empty",
    )}
    a = {name: sid("Array_Request_Manager", name) for name in (
        "clk", "rst_n", "slice_rst", "buffer_rw", "arm2buf_req_valid", "arm2buf_req_addr",
        "arm2buf_wvalid", "buf2arm_req_ready", "array2buf_same_bit", "array_req_addr", "arm_addr_update",
    )}
    buffer_common = conjunction(
        negated(pred("SIGNAL", b["slice_rst"])), pred("SIGNAL", b["arm2buf_req_rw"]),
        pred("NE", b["arm2buf_req_valid"], 0), pred("EQ", b["arm2buf_req_addr"], 2),
        pred("SIGNAL", b["arm2buf_wvalid"]), negated(pred("SIGNAL", b["buf2arm_req_ready"])),
    )
    payload = [
        b["buf2arm_wreq_bank_ready"], b["buffer_mask"], b["mrm2buf_clear"], b["valid_buf_clear"],
        b["mrm2buf_req_valid"], b["mrm2buf_req_rw"], b["mrm2buf_req_addr"], b["mrm2buf_wvalid"],
        b["mrm2buf_wr_en"], b["nrm2buf_wr_en"], b["arm2buf_wr_en"], b["buf_wr_en"],
        b["valid_buf_wr_en"], b["buf_wr_addr"], b["buf_wreq_ready"], b["arm2buf_req_addr"],
        b["arm2buf_last_bit"], b["arm2buf_last_index"], b["tag_buf_row_empty"],
    ]
    specs: list[tuple[str, dict[str, Any]]] = [
        ("row2_clear_f0_at_0f", conjunction(buffer_common, pred("EQ", b["buf2arm_wreq_bank_ready"], 0x0F), pred("EQ", b["mrm2buf_clear"], 0xF0), pred("EQ", b["mrm2buf_req_addr"], 2))),
        ("row2_postclear_bank_0f_no_write_accept", conjunction(buffer_common, pred("EQ", b["buf2arm_wreq_bank_ready"], 0x0F), pred("EQ", b["mrm2buf_clear"], 0), negated(pred("SIGNAL", b["buf_wreq_ready"])))),
        ("row2_postclear_bank_0f_write_accept", conjunction(buffer_common, pred("EQ", b["buf2arm_wreq_bank_ready"], 0x0F), pred("EQ", b["mrm2buf_clear"], 0), pred("SIGNAL", b["buf_wreq_ready"]))),
        ("row2_postclear_bank_00", conjunction(buffer_common, pred("EQ", b["mrm2buf_clear"], 0), pred("EQ", b["buf2arm_wreq_bank_ready"], 0x00))),
        ("row2_postclear_bank_f0", conjunction(buffer_common, pred("EQ", b["mrm2buf_clear"], 0), pred("EQ", b["buf2arm_wreq_bank_ready"], 0xF0))),
        ("row2_postclear_bank_ff", conjunction(buffer_common, pred("EQ", b["mrm2buf_clear"], 0), pred("EQ", b["buf2arm_wreq_bank_ready"], 0xFF))),
        ("row2_postclear_bank_other", conjunction(
            buffer_common, pred("EQ", b["mrm2buf_clear"], 0),
            pred("NE", b["buf2arm_wreq_bank_ready"], 0x00), pred("NE", b["buf2arm_wreq_bank_ready"], 0x0F),
            pred("NE", b["buf2arm_wreq_bank_ready"], 0xF0), pred("NE", b["buf2arm_wreq_bank_ready"], 0xFF),
        )),
    ]
    boundaries: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    for boundary_id, gate in specs:
        class_id = boundary_id.upper()
        boundaries.append({
            "boundary_id": boundary_id, "target_module": "Buffer",
            "role": "queue_dequeue" if boundary_id == "row2_clear_f0_at_0f" else "consumer_accept",
            "clock_symbol_id": b["clk"], "reset": {"symbol_id": b["rst_n"], "active_low": True},
            "stage_gate": gate,
            "classes": [{"class_id": class_id, "bit": 0, "predicate": {"op": "CONST", "value": True}, "progress": False, "trigger": True}],
            "payload_symbol_ids": payload,
        })
        observations.append({"observation_id": f"{boundary_id}_seen", "boundary_id": boundary_id, "metric": "class_seen", "class_id": class_id})
    final_boundary = "final_same_row2_block"
    final_class = final_boundary.upper()
    boundaries.append({
        "boundary_id": final_boundary, "target_module": "Array_Request_Manager", "role": "internal_match_compute",
        "clock_symbol_id": a["clk"], "reset": {"symbol_id": a["rst_n"], "active_low": True},
        "stage_gate": conjunction(
            negated(pred("SIGNAL", a["slice_rst"])), pred("SIGNAL", a["buffer_rw"]),
            pred("NE", a["arm2buf_req_valid"], 0), pred("EQ", a["arm2buf_req_addr"], 2),
            pred("SIGNAL", a["arm2buf_wvalid"]), negated(pred("SIGNAL", a["buf2arm_req_ready"])),
            pred("SIGNAL", a["array2buf_same_bit"]),
        ),
        "classes": [{"class_id": final_class, "bit": 0, "predicate": {"op": "CONST", "value": True}, "progress": False, "trigger": True}],
        "payload_symbol_ids": [a["arm2buf_req_valid"], a["buffer_rw"], a["arm2buf_req_addr"], a["buf2arm_req_ready"], a["array2buf_same_bit"], a["array_req_addr"], a["arm_addr_update"], a["arm2buf_wvalid"]],
    })
    observations.append({"observation_id": "final_same_row2_block_seen", "boundary_id": final_boundary, "metric": "class_seen", "class_id": final_class})
    observation_ids = [row["observation_id"] for row in observations]

    def signature(state: str | None, final: bool = True) -> dict[str, bool]:
        value = {name: False for name in observation_ids}
        value["row2_clear_f0_at_0f_seen"] = True
        value["final_same_row2_block_seen"] = final
        if state:
            value[f"{state}_seen"] = True
        return value

    state_boundaries = [name for name, _ in specs if name != "row2_clear_f0_at_0f"]
    candidates = [
        {"candidate_id": "target_final_not_reached", "root_cause_class": "TARGET_FINAL_NOT_REACHED", "signature": signature(None, False)},
        {"candidate_id": "target_post_state_not_reached", "root_cause_class": "TARGET_POST_STATE_NOT_REACHED", "signature": signature(None, True)},
        *[
            {"candidate_id": name, "root_cause_class": name.upper(), "signature": signature(name, True)}
            for name in state_boundaries
        ],
    ]
    semantic = __import__("generate_server_source_bound_observer").semantic_sha256(catalog)
    plan = {
        "schema": "server-source-bound-probe-plan-v1", "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "profile": "HIGH_INFORMATION_CAUSAL_V1", "package_id": PACKAGE_ID, "family": "conv_native_four_lane_node0004",
        "catalog_identity": {"rtl_tree_sha256": RTL_TREE_SHA256, "catalog_semantic_sha256": semantic},
        "boundaries": boundaries, "decision_observations": observations, "candidates": candidates,
        "role_coverage": [
            {"role": "source_produce", "disposition": "not_applicable", "boundary_ids": [], "reason": "p26 freezes source13 delivery."},
            {"role": "queue_enqueue", "disposition": "not_applicable", "boundary_ids": [], "reason": "p29 freezes competing external writer closure."},
            {"role": "queue_dequeue", "disposition": "covered", "boundary_ids": ["row2_clear_f0_at_0f"], "reason": "Exact f0 clear epoch anchor."},
            {"role": "consumer_accept", "disposition": "covered", "boundary_ids": [name for name, _ in specs if name != "row2_clear_f0_at_0f"], "reason": "Immediate mutually exclusive post-clear bank/write-accept classes."},
            {"role": "internal_match_compute", "disposition": "covered", "boundary_ids": [final_boundary], "reason": "Same-parent final row2 marker."},
            {"role": "output_accept", "disposition": "not_applicable", "boundary_ids": [], "reason": "Bounded Buffer5 diagnostic."},
            {"role": "terminal_propagation", "disposition": "not_applicable", "boundary_ids": [], "reason": "Bounded c0 diagnostic."},
            {"role": "formal_d_collection", "disposition": "not_applicable", "boundary_ids": [], "reason": "Frozen formal_readback_count=0."},
        ],
        "runtime_budget": {"qualified_ring_depth": 8, "non_progress_ring_depth": 8, "first_payload_samples": 4, "post_trigger_samples": 4, "no_progress_cycles": 1_048_576, "max_log_bytes": 16_777_216, "text_io_policy": "FIRST_SAMPLES_TRIGGER_AND_FINAL_ONLY", "multiclass_encoding": "BITMAP_ALL_TRUE_CLASSES", "state_activity_consumes_qualified_budget": False, "slowdown_limit_hard": False},
        "claim_boundary": "Generated immediate Buffer5 clear/post-state classes plus final same-row2 marker; family target parser separately correlates exact parent and epoch.",
    }
    plan_path = OUTPUT / "source_bound_probe_plan.json"
    write_json(plan_path, plan)
    generated = OUTPUT / "generated"
    subprocess.run([
        sys.executable, str(GENERATOR), "materialize", "--catalog", str(catalog_path), "--plan", str(plan_path),
        "--output-dir", str(generated), "--report", str(OUTPUT / "source_bound_generation_report.json"),
        "--cheap-check-output", str(OUTPUT / "source_bound_observer_generation.json"),
    ], cwd=ROOT, check=True)
    generation = json.loads((OUTPUT / "source_bound_generation_report.json").read_text(encoding="utf-8"))
    if generation.get("pass") is not True or generation.get("errors"):
        raise PrepareError("source-bound materialization failed")
    contract = {
        "schema": "conv-native-four-lane-p32b-target-epoch-contract-v1", "package_id": PACKAGE_ID,
        "target_parent": "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager",
        "clear_boundary": "row2_clear_f0_at_0f", "final_boundary": final_boundary,
        "post_state_boundaries": state_boundaries,
        "required_boundaries": [name for name, _ in specs] + [final_boundary],
        "candidates": [
            {"candidate_id": "postclear_0f_no_write_accept", "root_cause_class": "TARGET_POSTCLEAR_0F_NO_WRITE_ACCEPT", "observed_boundary": "row2_postclear_bank_0f_no_write_accept"},
            {"candidate_id": "postclear_0f_write_accept", "root_cause_class": "TARGET_POSTCLEAR_0F_WRITE_ACCEPT", "observed_boundary": "row2_postclear_bank_0f_write_accept"},
            {"candidate_id": "postclear_00", "root_cause_class": "TARGET_POSTCLEAR_BANK_READY_00", "observed_boundary": "row2_postclear_bank_00"},
            {"candidate_id": "postclear_f0", "root_cause_class": "TARGET_POSTCLEAR_BANK_READY_F0", "observed_boundary": "row2_postclear_bank_f0"},
            {"candidate_id": "postclear_ff", "root_cause_class": "TARGET_POSTCLEAR_BANK_READY_FF", "observed_boundary": "row2_postclear_bank_ff"},
            {"candidate_id": "postclear_other", "root_cause_class": "TARGET_POSTCLEAR_BANK_READY_OTHER", "observed_boundary": "row2_postclear_bank_other"},
            {"candidate_id": "post_state_not_reached", "root_cause_class": "TARGET_POST_STATE_NOT_REACHED", "observed_boundary": None},
        ],
        "source_bound_plan_sha256": sha(plan_path), "target_parser_source_sha256": sha(TARGET_PARSER),
        "claim_boundary": "Exact target parent and one clear-to-final epoch; raw records from other instances and epochs cannot satisfy a target candidate.",
    }
    write_json(OUTPUT / "target_epoch_correlator_contract.json", contract)
    shutil.copyfile(TARGET_PARSER, generated / "target_epoch_valid_owner_parser.py")
    write_json(OUTPUT / "epoch_reuse_receipt.json", {
        "schema": "conv-native-first-fresh-epoch-reuse-v1", "epoch_id": "20260810-first-fresh-extra-audit-v1",
        "family": "conv_native_four_lane", "package_id": PACKAGE_ID, "first_fresh_after_change": False,
        "prior_pass_path": "outputs/conv_native_four_lane_0ccae916_p31_postclear/first_fresh_extra_audit/validation.json",
        "prior_pass_sha256": "48c58b614af0ba1fe311d454e5229d4f000a5b944d711e52a8c43ecc85ab0ec1",
    })
    print(json.dumps({"status": "PASS", "output": str(OUTPUT), "candidate_count": len(candidates)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
