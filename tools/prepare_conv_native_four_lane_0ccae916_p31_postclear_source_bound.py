#!/usr/bin/env python3
"""Prepare p31 generated final-row2 bank-state discriminator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p31_postclear"
RTL_ROOT = ROOT / "NDP_copy01/rtl"
RTL_TREE_SHA256 = "c6902de6fabfce81ee10af02cec238e5b11d2fdece9454041415c455556e1093"
SOURCES = (
    "includes/NDP_Parameters.svh",
    "Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "Slice/LSU/Buffer_Manager_Cluster/Array_Request_Manager.sv",
)
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p31_postclear_source_bound_v2"
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


def negated(arg: dict[str, Any]) -> dict[str, Any]:
    return {"op": "NOT", "arg": arg}


def main() -> int:
    if OUTPUT.exists():
        raise PrepareError(f"refusing to overwrite source-bound output: {OUTPUT}")
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

    b_clk = sid("Buffer", "clk")
    b_rst = sid("Buffer", "rst_n")
    b_slice_rst = sid("Buffer", "slice_rst")
    b_arm_rw = sid("Buffer", "arm2buf_req_rw")
    b_arm_valid = sid("Buffer", "arm2buf_req_valid")
    b_arm_addr = sid("Buffer", "arm2buf_req_addr")
    b_arm_wvalid = sid("Buffer", "arm2buf_wvalid")
    b_arm_ready = sid("Buffer", "buf2arm_req_ready")
    b_bank_ready = sid("Buffer", "buf2arm_wreq_bank_ready")
    b_buffer_mask = sid("Buffer", "buffer_mask")
    b_mrm_clear = sid("Buffer", "mrm2buf_clear")
    b_valid_clear = sid("Buffer", "valid_buf_clear")
    b_valid_wr = sid("Buffer", "valid_buf_wr_en")
    b_arm_wr = sid("Buffer", "arm2buf_wr_en")
    b_buf_wr = sid("Buffer", "buf_wr_en")
    b_buf_addr = sid("Buffer", "buf_wr_addr")
    b_row_empty = sid("Buffer", "tag_buf_row_empty")

    a_clk = sid("Array_Request_Manager", "clk")
    a_rst = sid("Array_Request_Manager", "rst_n")
    a_slice_rst = sid("Array_Request_Manager", "slice_rst")
    a_buffer_rw = sid("Array_Request_Manager", "buffer_rw")
    a_arm_valid = sid("Array_Request_Manager", "arm2buf_req_valid")
    a_arm_addr = sid("Array_Request_Manager", "arm2buf_req_addr")
    a_arm_wvalid = sid("Array_Request_Manager", "arm2buf_wvalid")
    a_arm_ready = sid("Array_Request_Manager", "buf2arm_req_ready")
    a_same = sid("Array_Request_Manager", "array2buf_same_bit")
    a_array_addr = sid("Array_Request_Manager", "array_req_addr")
    a_addr_update = sid("Array_Request_Manager", "arm_addr_update")

    buffer_common = conjunction(
        negated(pred("SIGNAL", b_slice_rst)),
        pred("SIGNAL", b_arm_rw),
        pred("NE", b_arm_valid, 0),
        pred("EQ", b_arm_addr, 2),
        pred("SIGNAL", b_arm_wvalid),
        negated(pred("SIGNAL", b_arm_ready)),
    )
    buffer_payload = [
        b_bank_ready,
        b_buffer_mask,
        b_mrm_clear,
        b_valid_clear,
        b_valid_wr,
        b_arm_wr,
        b_buf_wr,
        b_buf_addr,
        b_row_empty,
    ]

    bank_specs: list[tuple[str, dict[str, Any]]] = [
        ("00", pred("EQ", b_bank_ready, 0x00)),
        ("0f", pred("EQ", b_bank_ready, 0x0F)),
        ("f0", pred("EQ", b_bank_ready, 0xF0)),
        ("ff", pred("EQ", b_bank_ready, 0xFF)),
        (
            "other",
            conjunction(
                pred("NE", b_bank_ready, 0x00),
                pred("NE", b_bank_ready, 0x0F),
                pred("NE", b_bank_ready, 0xF0),
                pred("NE", b_bank_ready, 0xFF),
            ),
        ),
    ]
    boundaries: list[dict[str, Any]] = []
    observations: list[tuple[str, str, str]] = []
    for label, bank_predicate in bank_specs:
        boundary_id = f"row2_block_bank_ready_{label}"
        class_id = f"ROW2_BLOCK_BANK_READY_{label.upper()}"
        boundaries.append(
            {
                "boundary_id": boundary_id,
                "target_module": "Buffer",
                "role": "consumer_accept",
                "clock_symbol_id": b_clk,
                "reset": {"symbol_id": b_rst, "active_low": True},
                "stage_gate": conjunction(buffer_common, bank_predicate),
                "classes": [
                    {
                        "class_id": class_id,
                        "bit": 0,
                        "predicate": {"op": "CONST", "value": True},
                        "progress": False,
                        "trigger": True,
                    }
                ],
                "payload_symbol_ids": buffer_payload,
            }
        )
        observations.append((f"block_bank_{label}_seen", boundary_id, class_id))

    final_boundary = "final_same_row2_block"
    final_class = "FINAL_SAME_ROW2_BLOCK"
    boundaries.append(
        {
            "boundary_id": final_boundary,
            "target_module": "Array_Request_Manager",
            "role": "internal_match_compute",
            "clock_symbol_id": a_clk,
            "reset": {"symbol_id": a_rst, "active_low": True},
            "stage_gate": conjunction(
                negated(pred("SIGNAL", a_slice_rst)),
                pred("SIGNAL", a_buffer_rw),
                pred("NE", a_arm_valid, 0),
                pred("EQ", a_arm_addr, 2),
                pred("SIGNAL", a_arm_wvalid),
                negated(pred("SIGNAL", a_arm_ready)),
                pred("SIGNAL", a_same),
            ),
            "classes": [
                {
                    "class_id": final_class,
                    "bit": 0,
                    "predicate": {"op": "CONST", "value": True},
                    "progress": False,
                    "trigger": True,
                }
            ],
            "payload_symbol_ids": [
                a_arm_valid,
                a_buffer_rw,
                a_arm_addr,
                a_arm_ready,
                a_same,
                a_array_addr,
                a_addr_update,
                a_arm_wvalid,
            ],
        }
    )
    observations.insert(0, ("final_same_row2_block_seen", final_boundary, final_class))
    decision_observations = [
        {
            "observation_id": observation_id,
            "boundary_id": boundary_id,
            "metric": "class_seen",
            "class_id": class_id,
        }
        for observation_id, boundary_id, class_id in observations
    ]
    observation_ids = [row[0] for row in observations]

    def signature(final_seen: bool, bank: str | None) -> dict[str, bool]:
        value = {observation_id: False for observation_id in observation_ids}
        value["final_same_row2_block_seen"] = final_seen
        # p30 proves the earlier short blocked row2 epoch is 0x0f.
        value["block_bank_0f_seen"] = True
        if bank is not None:
            value[f"block_bank_{bank}_seen"] = True
        return value

    candidates = [
        {
            "candidate_id": "target_final_same_row2_block_not_reached",
            "root_cause_class": "TARGET_FINAL_SAME_ROW2_BLOCK_NOT_REACHED",
            "signature": signature(False, None),
        },
        *[
            {
                "candidate_id": f"final_postclear_bank_ready_{bank}",
                "root_cause_class": f"FINAL_POSTCLEAR_BANK_READY_{bank.upper()}",
                "signature": signature(True, bank),
            }
            for bank in ("0f", "00", "f0", "ff", "other")
        ],
    ]
    catalog_semantic = __import__("generate_server_source_bound_observer").semantic_sha256(catalog_value)
    plan = {
        "schema": "server-source-bound-probe-plan-v1",
        "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
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
            {"role": "source_produce", "disposition": "not_applicable", "boundary_ids": [], "reason": "p26 already proves source13 and actual Memory_AG delivery."},
            {"role": "queue_enqueue", "disposition": "not_applicable", "boundary_ids": [], "reason": "p29 closes competing row2 writers."},
            {"role": "queue_dequeue", "disposition": "not_applicable", "boundary_ids": [], "reason": "p28 proves row2 MRM clear/dequeue."},
            {"role": "consumer_accept", "disposition": "covered", "boundary_ids": [row["boundary_id"] for row in boundaries if row["target_module"] == "Buffer"], "reason": "Immediate blocked-row2 bank-state candidates."},
            {"role": "internal_match_compute", "disposition": "covered", "boundary_ids": [final_boundary], "reason": "Same-bit final-row2 epoch marker in Array_Request_Manager."},
            {"role": "output_accept", "disposition": "not_applicable", "boundary_ids": [], "reason": "p31 stops at the Buffer5 acceptance boundary."},
            {"role": "terminal_propagation", "disposition": "not_applicable", "boundary_ids": [], "reason": "p31 is bounded c0 diagnostic only."},
            {"role": "formal_d_collection", "disposition": "not_applicable", "boundary_ids": [], "reason": "Frozen diagnostic source has formal_readback_count=0."},
        ],
        "runtime_budget": {
            "qualified_ring_depth": 8,
            "non_progress_ring_depth": 8,
            "first_payload_samples": 4,
            "post_trigger_samples": 4,
            "no_progress_cycles": 1_048_576,
            "max_log_bytes": 16_777_216,
            "text_io_policy": "FIRST_SAMPLES_TRIGGER_AND_FINAL_ONLY",
            "multiclass_encoding": "BITMAP_ALL_TRUE_CLASSES",
            "state_activity_consumes_qualified_budget": False,
            "slowdown_limit_hard": False,
        },
        "claim_boundary": (
            "Diagnostic-only immediate candidate triggers. A prior 0x0f blocked epoch is frozen from p30; "
            "the same-bit Array_Request_Manager marker proves the final row2 epoch is active, while separate "
            "Buffer triggers distinguish final bank-ready 00/0f/f0/ff/other without relying on SystemVerilog final."
        ),
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
    write_json(
        OUTPUT / "first_fresh_epoch_ack.json",
        {
            "schema": "conv-native-first-fresh-epoch-ack-v1",
            "epoch_id": "20260810-first-fresh-extra-audit-v1",
            "family": "conv_native_four_lane_node0004",
            "package_id": PACKAGE_ID,
            "first_fresh_after_change": True,
            "notification_acknowledged": True,
            "cheap_prebuild_aggregate_invocations": 1,
            "final_zip_target_count": 1,
        },
    )
    print(json.dumps({"status": "PASS", "output": str(OUTPUT), "candidate_count": len(candidates)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
