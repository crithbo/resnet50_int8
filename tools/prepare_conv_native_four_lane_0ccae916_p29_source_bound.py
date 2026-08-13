#!/usr/bin/env python3
"""Prepare the generated p29 Buffer5 row2 ownership observer."""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p29_row2own"
RTL_ROOT = ROOT / "NDP_copy01/rtl"
RTL_TREE_SHA256 = "c6902de6fabfce81ee10af02cec238e5b11d2fdece9454041415c455556e1093"
SOURCES = (
    "includes/NDP_Parameters.svh",
    "Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "Slice/LSU/Buffer_Manager_Cluster/Memory_Req_Manager.sv",
)
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p29_row2own_source_bound"
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
        retry_sets = (
            {"source_bound_probe_catalog.json"},
            {
                "generated",
                "source_bound_probe_catalog.json",
                "source_bound_probe_plan.json",
            },
        )
        if existing not in retry_sets:
            raise PrepareError(f"refusing to overwrite source-bound output: {OUTPUT}")
        if "generated" in existing and any((OUTPUT / "generated").iterdir()):
            raise PrepareError(f"refusing to overwrite nonempty generated output: {OUTPUT}")
        if "generated" not in existing:
            failed = json.loads(
                (OUTPUT / "source_bound_probe_catalog.json").read_text(encoding="utf-8")
            )
            if failed.get("valid") is not False or not failed.get("errors"):
                raise PrepareError(f"refusing to overwrite non-failed catalog: {OUTPUT}")
    else:
        OUTPUT.mkdir(parents=True)
    catalog = OUTPUT / "source_bound_probe_catalog.json"
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

    def sid(module: str, name: str) -> str:
        try:
            return symbols[(module, name)]
        except KeyError as error:
            raise PrepareError(f"required catalog symbol is absent: {module}.{name}") from error

    clk = sid("Buffer", "clk")
    rst = sid("Buffer", "rst_n")
    slice_rst = sid("Buffer", "slice_rst")
    arm_rw = sid("Buffer", "arm2buf_req_rw")
    arm_valid = sid("Buffer", "arm2buf_req_valid")
    arm_addr = sid("Buffer", "arm2buf_req_addr")
    arm_wvalid = sid("Buffer", "arm2buf_wvalid")
    arm_ready = sid("Buffer", "buf2arm_req_ready")
    arm_bank_ready = sid("Buffer", "buf2arm_wreq_bank_ready")
    mrm_valid = sid("Buffer", "mrm2buf_req_valid")
    mrm_rw = sid("Buffer", "mrm2buf_req_rw")
    mrm_addr = sid("Buffer", "mrm2buf_req_addr")
    mrm_ready = sid("Buffer", "buf2mrm_req_ready")
    mrm_clear = sid("Buffer", "mrm2buf_clear")
    nrm_write_valid = sid("Buffer", "nrm2buf_wreq_valid")
    nrm_write_addr = sid("Buffer", "nrm2buf_wreq_addr")

    active = {"op": "NOT", "arg": pred("SIGNAL", slice_rst)}
    row2_arm = conjunction(
        active,
        pred("SIGNAL", arm_rw),
        pred("NE", arm_valid, 0),
        pred("EQ", arm_addr, 2),
        pred("SIGNAL", arm_wvalid),
    )
    row2_mrm_read = conjunction(
        active,
        {"op": "NOT", "arg": pred("SIGNAL", mrm_rw)},
        pred("NE", mrm_valid, 0),
        pred("EQ", mrm_addr, 2),
    )
    final_row2_block = conjunction(row2_arm, {"op": "NOT", "arg": pred("SIGNAL", arm_ready)})
    competing_row2_writer = {
        "op": "OR",
        "args": [
            conjunction(pred("SIGNAL", mrm_rw), pred("NE", mrm_valid, 0), pred("EQ", mrm_addr, 2)),
            conjunction(pred("NE", nrm_write_valid, 0), pred("EQ", nrm_write_addr, 2)),
        ],
    }

    boundaries = [
        {
            "boundary_id": "row2_arm_write_state",
            "target_module": "Buffer",
            "role": "consumer_accept",
            "clock_symbol_id": clk,
            "reset": {"symbol_id": rst, "active_low": True},
            "stage_gate": row2_arm,
            "classes": [
                {"class_id": "ROW2_WRITE_ACCEPT", "bit": 0, "predicate": pred("SIGNAL", arm_ready), "progress": True, "trigger": False},
                {"class_id": "ROW2_WRITE_BLOCKED", "bit": 1, "predicate": {"op": "NOT", "arg": pred("SIGNAL", arm_ready)}, "progress": False, "trigger": True},
                {"class_id": "ROW2_BANK_READY_ALL", "bit": 2, "predicate": pred("EQ", arm_bank_ready, 255), "progress": True, "trigger": False},
                {"class_id": "ROW2_BANK_READY_NOT_ALL", "bit": 3, "predicate": pred("NE", arm_bank_ready, 255), "progress": False, "trigger": True},
            ],
            "payload_symbol_ids": [],
        },
        {
            "boundary_id": "row2_mrm_read_clear",
            "target_module": "Buffer",
            "role": "internal_match_compute",
            "clock_symbol_id": clk,
            "reset": {"symbol_id": rst, "active_low": True},
            "stage_gate": row2_mrm_read,
            "classes": [
                {"class_id": "ROW2_MRM_READ_ACCEPT", "bit": 0, "predicate": pred("SIGNAL", mrm_ready), "progress": True, "trigger": False},
                {"class_id": "ROW2_MRM_READ_BLOCKED", "bit": 1, "predicate": {"op": "NOT", "arg": pred("SIGNAL", mrm_ready)}, "progress": False, "trigger": True},
                {"class_id": "ROW2_MRM_CLEAR_NONZERO", "bit": 2, "predicate": pred("NE", mrm_clear, 0), "progress": True, "trigger": False},
                {"class_id": "ROW2_MRM_CLEAR_ZERO", "bit": 3, "predicate": pred("EQ", mrm_clear, 0), "progress": False, "trigger": True},
            ],
            "payload_symbol_ids": [],
        },
        {
            "boundary_id": "row2_final_block_competing_writer",
            "target_module": "Buffer",
            "role": "queue_enqueue",
            "clock_symbol_id": clk,
            "reset": {"symbol_id": rst, "active_low": True},
            "stage_gate": final_row2_block,
            "classes": [
                {"class_id": "COMPETING_ROW2_WRITER", "bit": 0, "predicate": competing_row2_writer, "progress": False, "trigger": True},
                {"class_id": "NO_COMPETING_ROW2_WRITER", "bit": 1, "predicate": {"op": "NOT", "arg": competing_row2_writer}, "progress": False, "trigger": True},
            ],
            "payload_symbol_ids": [],
        },
    ]
    observations = [
        ("row2_clear_seen", "row2_mrm_read_clear", "ROW2_MRM_CLEAR_NONZERO"),
        ("row2_write_accept_seen", "row2_arm_write_state", "ROW2_WRITE_ACCEPT"),
        ("row2_write_blocked_seen", "row2_arm_write_state", "ROW2_WRITE_BLOCKED"),
        ("row2_bank_not_all_seen", "row2_arm_write_state", "ROW2_BANK_READY_NOT_ALL"),
        ("competing_row2_writer_seen", "row2_final_block_competing_writer", "COMPETING_ROW2_WRITER"),
    ]
    decision_observations = [
        {
            "observation_id": observation_id,
            "boundary_id": boundary_id,
            "metric": "class_seen",
            "class_id": class_id,
        }
        for observation_id, boundary_id, class_id in observations
    ]
    candidates = []
    observation_ids = [item[0] for item in observations]
    for values in itertools.product((False, True), repeat=len(observation_ids)):
        bits = "".join("1" if value else "0" for value in values)
        candidates.append(
            {
                "candidate_id": f"row2_signature_{bits}",
                "root_cause_class": f"BUFFER5_ROW2_OWNERSHIP_SIGNATURE_{bits}",
                "signature": dict(zip(observation_ids, values)),
            }
        )
    catalog_semantic = __import__(
        "generate_server_source_bound_observer"
    ).semantic_sha256(catalog_value)
    plan = {
        "schema": "server-source-bound-probe-plan-v1",
        "profile": "HIGH_INFORMATION_CAUSAL_V1",
        "package_id": PACKAGE_ID,
        "family": "conv_native_four_lane_node0004",
        "catalog_identity": {
            "rtl_tree_sha256": RTL_TREE_SHA256,
            "catalog_semantic_sha256": catalog_semantic,
        },
        "boundaries": boundaries,
        "decision_observations": decision_observations,
        "candidates": candidates,
        "role_coverage": [
            {"role": "source_produce", "disposition": "not_applicable", "boundary_ids": [], "reason": "p26 already proved the upstream source and actual Memory_AG delivery."},
            {"role": "queue_enqueue", "disposition": "covered", "boundary_ids": ["row2_final_block_competing_writer"]},
            {"role": "queue_dequeue", "disposition": "not_applicable", "boundary_ids": [], "reason": "p28 public evidence already proves qualified Buffer5 row2 MRM read acceptance."},
            {"role": "consumer_accept", "disposition": "covered", "boundary_ids": ["row2_arm_write_state"]},
            {"role": "internal_match_compute", "disposition": "covered", "boundary_ids": ["row2_mrm_read_clear"]},
            {"role": "output_accept", "disposition": "not_applicable", "boundary_ids": [], "reason": "The bounded target is Buffer5 input row ownership and ready release, not downstream output data."},
            {"role": "terminal_propagation", "disposition": "not_applicable", "boundary_ids": [], "reason": "p29 remains a c0 row-release diagnostic; natural terminal remains an independent return gate."},
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
        "claim_boundary": "Diagnostic-only c0 Buffer5 row2 ownership/clear/ready cone. Raw per-instance timestamps are combined with the frozen focused Buffer5 public timeline; no natural-terminal, formal-D, E3, E4, E5, numeric, RTL-correctness or performance claim.",
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
    report = json.loads(
        (OUTPUT / "source_bound_generation_report.json").read_text(encoding="utf-8")
    )
    if report.get("pass") is not True or report.get("errors"):
        raise PrepareError("source-bound materialization failed")
    print(json.dumps({"status": "PASS", "output": str(OUTPUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
