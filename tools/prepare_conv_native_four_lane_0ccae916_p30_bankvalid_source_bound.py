#!/usr/bin/env python3
"""Prepare p30 generated Buffer5 row2 bank-valid/ready observer."""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p30_bankvalid"
RTL_ROOT = ROOT / "NDP_copy01/rtl"
RTL_TREE_SHA256 = "c6902de6fabfce81ee10af02cec238e5b11d2fdece9454041415c455556e1093"
SOURCES = (
    "includes/NDP_Parameters.svh",
    "Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "Slice/LSU/Buffer_Manager_Cluster/Memory_Req_Manager.sv",
)
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p30_bankvalid_source_bound_v2"
GENERATOR = ROOT / "tools/generate_server_source_bound_observer.py"


class PrepareError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def pred(op: str, symbol_id: str, value: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"op": op, "symbol_id": symbol_id}
    if value is not None:
        result["value"] = value
    return result


def conjunction(*args: dict[str, Any]) -> dict[str, Any]:
    return {"op": "AND", "args": list(args)}


def main() -> int:
    if OUTPUT.exists():
        existing = {path.name for path in OUTPUT.iterdir()}
        if existing != {"source_bound_probe_catalog.json"}:
            raise PrepareError(f"refusing to overwrite source-bound output: {OUTPUT}")
    else:
        OUTPUT.mkdir(parents=True)
    catalog = OUTPUT / "source_bound_probe_catalog.json"
    if not catalog.exists():
        command = [
            sys.executable,
            str(GENERATOR),
            "catalog",
            "--rtl-root",
            str(RTL_ROOT),
            "--rtl-tree-sha256",
            RTL_TREE_SHA256,
        ]
        for source in SOURCES:
            command.extend(["--source", str(RTL_ROOT / source)])
        command.extend(["--output", str(catalog)])
        subprocess.run(command, cwd=ROOT, check=True)
    catalog_value = json.loads(catalog.read_text(encoding="utf-8"))
    if catalog_value.get("valid") is not True or catalog_value.get("errors"):
        raise PrepareError("catalog generation failed")
    symbols = {
        (item["module"], item["name"]): item["symbol_id"]
        for item in catalog_value["symbols"]
    }

    def sid(name: str) -> str:
        try:
            return symbols[("Buffer", name)]
        except KeyError as error:
            raise PrepareError(f"required catalog symbol is absent: Buffer.{name}") from error

    clk = sid("clk")
    rst = sid("rst_n")
    slice_rst = sid("slice_rst")
    arm_rw = sid("arm2buf_req_rw")
    arm_valid = sid("arm2buf_req_valid")
    arm_addr = sid("arm2buf_req_addr")
    arm_wvalid = sid("arm2buf_wvalid")
    arm_ready = sid("buf2arm_req_ready")
    arm_bank_ready = sid("buf2arm_wreq_bank_ready")
    buffer_mask = sid("buffer_mask")
    mrm_valid = sid("mrm2buf_req_valid")
    mrm_rw = sid("mrm2buf_req_rw")
    mrm_addr = sid("mrm2buf_req_addr")
    mrm_ready = sid("buf2mrm_req_ready")
    mrm_clear = sid("mrm2buf_clear")
    valid_buf_clear = sid("valid_buf_clear")
    valid_buf_wr_en = sid("valid_buf_wr_en")
    arm2buf_wr_en = sid("arm2buf_wr_en")
    buf_wr_en = sid("buf_wr_en")
    buf_wr_addr = sid("buf_wr_addr")
    tag_buf_row_empty = sid("tag_buf_row_empty")

    active = {"op": "NOT", "arg": pred("SIGNAL", slice_rst)}
    row2_arm = conjunction(
        active,
        pred("SIGNAL", arm_rw),
        pred("NE", arm_valid, 0),
        pred("EQ", arm_addr, 2),
        pred("SIGNAL", arm_wvalid),
    )
    row2_mrm = conjunction(
        active,
        {"op": "NOT", "arg": pred("SIGNAL", mrm_rw)},
        pred("NE", mrm_valid, 0),
        pred("EQ", mrm_addr, 2),
    )
    ready_other = conjunction(
        pred("NE", arm_bank_ready, 0x00),
        pred("NE", arm_bank_ready, 0x0F),
        pred("NE", arm_bank_ready, 0xF0),
        pred("NE", arm_bank_ready, 0xFF),
    )
    clear_other = conjunction(
        pred("NE", mrm_clear, 0x00),
        pred("NE", mrm_clear, 0x0F),
        pred("NE", mrm_clear, 0xF0),
        pred("NE", mrm_clear, 0xFF),
    )
    payload = [
        arm_bank_ready,
        buffer_mask,
        mrm_clear,
        valid_buf_clear,
        valid_buf_wr_en,
        arm2buf_wr_en,
        buf_wr_en,
        buf_wr_addr,
        tag_buf_row_empty,
    ]
    boundaries = [
        {
            "boundary_id": "row2_arm_bank_valid_timeline",
            "target_module": "Buffer",
            "role": "consumer_accept",
            "clock_symbol_id": clk,
            "reset": {"symbol_id": rst, "active_low": True},
            "stage_gate": row2_arm,
            "classes": [
                {"class_id": "ROW2_ARM_ACCEPT", "bit": 0, "predicate": pred("SIGNAL", arm_ready), "progress": True, "trigger": False},
                {"class_id": "ROW2_ARM_BLOCKED", "bit": 1, "predicate": {"op": "NOT", "arg": pred("SIGNAL", arm_ready)}, "progress": False, "trigger": True},
                {"class_id": "ROW2_BANK_READY_00", "bit": 2, "predicate": pred("EQ", arm_bank_ready, 0x00), "progress": False, "trigger": True},
                {"class_id": "ROW2_BANK_READY_0F", "bit": 3, "predicate": pred("EQ", arm_bank_ready, 0x0F), "progress": False, "trigger": True},
                {"class_id": "ROW2_BANK_READY_F0", "bit": 4, "predicate": pred("EQ", arm_bank_ready, 0xF0), "progress": False, "trigger": True},
                {"class_id": "ROW2_BANK_READY_FF", "bit": 5, "predicate": pred("EQ", arm_bank_ready, 0xFF), "progress": True, "trigger": False},
                {"class_id": "ROW2_BANK_READY_OTHER", "bit": 6, "predicate": ready_other, "progress": False, "trigger": True},
            ],
            "payload_symbol_ids": payload,
        },
        {
            "boundary_id": "row2_mrm_clear_valid_timeline",
            "target_module": "Buffer",
            "role": "internal_match_compute",
            "clock_symbol_id": clk,
            "reset": {"symbol_id": rst, "active_low": True},
            "stage_gate": row2_mrm,
            "classes": [
                {"class_id": "ROW2_MRM_ACCEPT", "bit": 0, "predicate": pred("SIGNAL", mrm_ready), "progress": True, "trigger": False},
                {"class_id": "ROW2_CLEAR_F0", "bit": 1, "predicate": pred("EQ", mrm_clear, 0xF0), "progress": True, "trigger": False},
                {"class_id": "ROW2_CLEAR_0F", "bit": 2, "predicate": pred("EQ", mrm_clear, 0x0F), "progress": True, "trigger": False},
                {"class_id": "ROW2_CLEAR_FF", "bit": 3, "predicate": pred("EQ", mrm_clear, 0xFF), "progress": True, "trigger": False},
                {"class_id": "ROW2_CLEAR_OTHER_NONZERO", "bit": 4, "predicate": clear_other, "progress": True, "trigger": False},
                {"class_id": "ROW2_CLEAR_ZERO", "bit": 5, "predicate": pred("EQ", mrm_clear, 0), "progress": False, "trigger": True},
            ],
            "payload_symbol_ids": payload,
        },
    ]
    observations = [
        ("arm_accept_seen", "row2_arm_bank_valid_timeline", "ROW2_ARM_ACCEPT"),
        ("arm_blocked_seen", "row2_arm_bank_valid_timeline", "ROW2_ARM_BLOCKED"),
        ("bank_ready_00_seen", "row2_arm_bank_valid_timeline", "ROW2_BANK_READY_00"),
        ("bank_ready_0f_seen", "row2_arm_bank_valid_timeline", "ROW2_BANK_READY_0F"),
        ("bank_ready_f0_seen", "row2_arm_bank_valid_timeline", "ROW2_BANK_READY_F0"),
        ("bank_ready_ff_seen", "row2_arm_bank_valid_timeline", "ROW2_BANK_READY_FF"),
        ("bank_ready_other_seen", "row2_arm_bank_valid_timeline", "ROW2_BANK_READY_OTHER"),
        ("clear_f0_seen", "row2_mrm_clear_valid_timeline", "ROW2_CLEAR_F0"),
        ("clear_0f_seen", "row2_mrm_clear_valid_timeline", "ROW2_CLEAR_0F"),
        ("clear_other_seen", "row2_mrm_clear_valid_timeline", "ROW2_CLEAR_OTHER_NONZERO"),
    ]
    decision_observations = [
        {"observation_id": observation, "boundary_id": boundary, "metric": "class_seen", "class_id": class_id}
        for observation, boundary, class_id in observations
    ]
    observation_ids = [row[0] for row in observations]
    candidates = []
    for values in itertools.product((False, True), repeat=len(observation_ids)):
        bits = "".join("1" if value else "0" for value in values)
        candidates.append(
            {
                "candidate_id": f"row2_bankvalid_signature_{bits}",
                "root_cause_class": f"BUFFER5_ROW2_BANKVALID_SIGNATURE_{bits}",
                "signature": dict(zip(observation_ids, values)),
            }
        )
    catalog_semantic = __import__("generate_server_source_bound_observer").semantic_sha256(catalog_value)
    plan = {
        "schema": "server-source-bound-probe-plan-v1",
        "profile": "HIGH_INFORMATION_CAUSAL_V1",
        "package_id": PACKAGE_ID,
        "family": "conv_native_four_lane_node0004",
        "catalog_identity": {"rtl_tree_sha256": RTL_TREE_SHA256, "catalog_semantic_sha256": catalog_semantic},
        "boundaries": boundaries,
        "decision_observations": decision_observations,
        "candidates": candidates,
        "role_coverage": [
            {"role": "source_produce", "disposition": "not_applicable", "boundary_ids": [], "reason": "p26 already proves upstream source13 and actual Memory_AG delivery."},
            {"role": "queue_enqueue", "disposition": "not_applicable", "boundary_ids": [], "reason": "p29 closes competing row2 writers."},
            {"role": "queue_dequeue", "disposition": "not_applicable", "boundary_ids": [], "reason": "p28 already proves the row2 MRM read/clear dequeue; p30 observes the clear outcome inside Buffer5."},
            {"role": "consumer_accept", "disposition": "covered", "boundary_ids": ["row2_arm_bank_valid_timeline"]},
            {"role": "internal_match_compute", "disposition": "covered", "boundary_ids": ["row2_mrm_clear_valid_timeline"]},
            {"role": "output_accept", "disposition": "not_applicable", "boundary_ids": [], "reason": "p30 targets Buffer5 row ownership before downstream output acceptance."},
            {"role": "terminal_propagation", "disposition": "not_applicable", "boundary_ids": [], "reason": "p30 remains a bounded c0 diagnostic."},
            {"role": "formal_d_collection", "disposition": "not_applicable", "boundary_ids": [], "reason": "The frozen diagnostic source has formal_readback_count=0."},
        ],
        "runtime_budget": {
            "qualified_ring_depth": 16,
            "non_progress_ring_depth": 16,
            "first_payload_samples": 8,
            "post_trigger_samples": 8,
            "no_progress_cycles": 1_048_576,
            "max_log_bytes": 16_777_216,
            "text_io_policy": "FIRST_SAMPLES_TRIGGER_AND_FINAL_ONLY",
            "multiclass_encoding": "BITMAP_ALL_TRUE_CLASSES",
            "state_activity_consumes_qualified_budget": False,
            "slowdown_limit_hard": False,
        },
        "claim_boundary": "Diagnostic-only exact Buffer5 row2 clear-to-block bank-ready and per-bank clear/write state. The 62-bit generated payload carries bank-ready, buffer-mask, clear/write bank enables, write row address and tag-row-empty state; no natural-terminal, formal-D, E3-E5, numeric or performance claim.",
    }
    plan_path = OUTPUT / "source_bound_probe_plan.json"
    write_json(plan_path, plan)
    generated = OUTPUT / "generated"
    subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "materialize",
            "--catalog",
            str(catalog),
            "--plan",
            str(plan_path),
            "--output-dir",
            str(generated),
            "--report",
            str(OUTPUT / "source_bound_generation_report.json"),
            "--cheap-check-output",
            str(OUTPUT / "source_bound_observer_generation.json"),
        ],
        cwd=ROOT,
        check=True,
    )
    report = json.loads((OUTPUT / "source_bound_generation_report.json").read_text(encoding="utf-8"))
    if report.get("pass") is not True or report.get("errors"):
        raise PrepareError("source-bound materialization failed")
    print(json.dumps({"status": "PASS", "output": str(OUTPUT), "candidate_count": len(candidates)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
