#!/usr/bin/env python3
"""Materialize the p37 exact SA accepted-data-beat observer."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p37_saepoch"
PREVIOUS = ROOT / "outputs/conv_native_four_lane_0ccae916_p36b_semfp_source_bound"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p37_saepoch_source_bound_v4"
CATALOG = OUTPUT / "source_bound_probe_catalog.json"
PLAN = OUTPUT / "source_bound_probe_plan.json"
ARM_CONTRACT = OUTPUT / "arm_known_contract.json"
SA_CONTRACT = OUTPUT / "sa_epoch_contract.json"
IDENTITY = OUTPUT / "exact_instance_identity.json"
GENERATOR = ROOT / "tools/generate_server_source_bound_observer.py"
ARM_PARSER = ROOT / "tools/conv_native_four_lane_p35_arm_known_parser.py"
SA_PARSER = ROOT / "tools/conv_native_four_lane_p37_sa_epoch_parser.py"
RTL = ROOT / "NDP_copy01/rtl"
RTL_TREE_SHA256 = "c6902de6fabfce81ee10af02cec238e5b11d2fdece9454041415c455556e1093"
EPOCH = "20260811-exact-instance-payload-semantic-fingerprint-v2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str]) -> None:
    value = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)
    if value.returncode:
        raise RuntimeError(f"command failed ({value.returncode}): {' '.join(argv)}\n{value.stdout}\n{value.stderr}")


def load_generator():
    spec = importlib.util.spec_from_file_location("source_bound_generator_p37", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load source-bound generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p37 source-bound output")
    OUTPUT.mkdir(parents=True)
    sources = [
        RTL / "Slice/LSU/Buffer_Manager_Cluster/Array_Request_Manager.sv",
        RTL / "Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
        RTL / "Slice/Specialized_Array/SA_Outport/SA_Outport.sv",
        RTL / "includes/NDP_Parameters.svh",
    ]
    argv = [sys.executable, str(GENERATOR), "catalog", "--rtl-root", str(RTL), "--rtl-tree-sha256", RTL_TREE_SHA256]
    for source in sources:
        argv.extend(["--source", str(source)])
    argv.extend(["--output", str(CATALOG)])
    run(argv)

    generator = load_generator()
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    symbols = {(row["module"], row["name"]): row for row in catalog["symbols"]}
    plan = json.loads((PREVIOUS / "source_bound_probe_plan.json").read_text(encoding="utf-8"))
    plan["package_id"] = PACKAGE_ID
    plan["catalog_identity"] = {
        "rtl_tree_sha256": RTL_TREE_SHA256,
        "catalog_semantic_sha256": generator.semantic_sha256(catalog),
    }
    plan["runtime_budget"]["first_payload_samples"] = 8

    buffer_parent = (
        "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
        "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice."
        "u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager"
    )
    buffer_near = buffer_parent.replace("BUFFER_MANAGER[5]", "BUFFER_MANAGER[4]")
    sa_group_parent = (
        "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
        "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice."
        "u_Specialized_Array.u_SA_Outport_Group"
    )
    sa_near_group = sa_group_parent.replace("slice_group_gen[0]", "slice_group_gen[1]")
    sa_parents = [f"{sa_group_parent}.SA_OUTPORT[{index}].u_SA_Outport" for index in range(8)]
    sa_near_parents = [f"{sa_near_group}.SA_OUTPORT[{index}].u_SA_Outport" for index in range(8)]
    suffixes = {
        "row2_clear_window_write_owner": ".u_Buffer.codex_probe_row2_clear_window_write_owner_inst",
        "arm_row2_accept_token_state": ".u_Array_Request_Manager.codex_probe_arm_row2_accept_token_state_inst",
        "final_same_row2_block": ".u_Array_Request_Manager.codex_probe_final_same_row2_block_inst",
    }
    sa_suffixes = [f".codex_probe_sa_lane{index}_output_accepted_data_inst" for index in range(8)]
    identity = {
        "schema": "conv-native-four-lane-p37-exact-instance-identity-v1",
        "source_return": {
            "path": "C:/Users/15383/Downloads/r5_n4_0cc_p36b_semfp_r1786417577426033642_868940_return.zip",
            "bytes": 157471,
            "sha256": "d95a8c69b9fb0b44016880d9427146c5b4d1d1980fecbc760419aa5d9e21f9ed",
            "execution_id": "r1786417577426033642_868940",
        },
        "buffer_target_parent": buffer_parent,
        "sa_target_parents": sa_parents,
        "boundaries": {
            **{
                key: {"expected_instance": buffer_parent + suffix, "near_miss_instance": buffer_near + suffix}
                for key, suffix in suffixes.items()
            },
            "sa_output_accepted_data": {
                "expected_instances": [sa_parents[index] + sa_suffixes[index] for index in range(8)],
                "near_miss_instances": [sa_near_parents[index] + sa_suffixes[index] for index in range(8)],
            },
        },
        "selection": "exact slice-group0 Buffer5 plus exact slice-group0 SA_Outport_Group; neighboring manager/group are permanent wrong-instance negatives",
    }
    write(IDENTITY, identity)

    for boundary in plan["boundaries"]:
        boundary_id = boundary["boundary_id"]
        boundary["instance_scope"] = {
            "mode": "EXACT_CANONICAL_INSTANCE",
            "expected_instances": [buffer_parent + suffixes[boundary_id]],
            "near_miss_instances": [buffer_near + suffixes[boundary_id]],
            "identity_provenance": {
                "path": "diagnostics/exact_instance_identity.json",
                "sha256": sha(IDENTITY),
                "selector": f"boundaries.{boundary_id}",
            },
        }

    def sid(name: str) -> str:
        return symbols[("SA_Outport", name)]["symbol_id"]

    sa_payload = [
        sid("sa_outport_out_valid"), sid("sa_outport_out_last"), sid("sa_outport_out_same"),
        sid("sa_outport_out_last_index"), sid("sa_outport_out_data"), sid("sa_outport_bp_post"),
    ]
    lane_boundaries: list[str] = []
    for lane in range(8):
        boundary_id = f"sa_lane{lane}_output_accepted_data"
        lane_boundaries.append(boundary_id)
        plan["boundaries"].append({
            "boundary_id": boundary_id,
            "target_module": "SA_Outport",
            "clock_symbol_id": sid("clk"),
            "reset": {"symbol_id": sid("rst_n"), "active_low": True},
            "stage_gate": {"op": "NOT", "arg": {"op": "SIGNAL", "symbol_id": sid("slice_rst")}},
            "role": "output_accept",
            "classes": [{
                "bit": 0,
                "class_id": f"SA_LANE{lane}_OUTPUT_VALID_ACCEPT",
                "predicate": {"op": "AND", "args": [
                    {"op": "SIGNAL", "symbol_id": sid("sa_outport_out_valid")},
                    {"op": "SIGNAL", "symbol_id": sid("sa_outport_bp_post")},
                ]},
                "progress": True,
                "trigger": True,
            }],
            "payload_symbol_ids": sa_payload,
            "payload_contract": {
                "width_bits": 40,
                "required_binary_known": True,
                "unknown_disposition": "EVIDENCE_INCOMPLETE",
            },
            "instance_scope": {
                "mode": "EXACT_CANONICAL_INSTANCE",
                "expected_instances": [sa_parents[lane] + sa_suffixes[lane]],
                "near_miss_instances": [sa_near_parents[lane] + sa_suffixes[lane]],
                "identity_provenance": {
                    "path": "diagnostics/exact_instance_identity.json",
                    "sha256": sha(IDENTITY),
                    "selector": "boundaries.sa_output_accepted_data",
                },
            },
        })
    plan["decision_observations"] = [
        {
            "observation_id": f"sa_lane{lane}_accept_count",
            "boundary_id": boundary_id,
            "metric": "count_nonzero",
        }
        for lane, boundary_id in enumerate(lane_boundaries)
    ]
    plan["candidates"] = [{
        "candidate_id": "sa_accepted_data_identity_pending_custom_correlator",
        "root_cause_class": "SA_ACCEPTED_DATA_IDENTITY",
        "signature": {f"sa_lane{lane}_accept_count": True for lane in range(8)},
    }]
    for row in plan["role_coverage"]:
        if row["role"] == "output_accept":
            row.update({
                "boundary_ids": lane_boundaries,
                "disposition": "covered",
                "reason": "Eight exact public SA_Outport lane tag/data acceptance boundaries, grouped by timestamp.",
            })
    plan["claim_boundary"] = (
        "Exact group0 Buffer5 ARM state plus eight exact group0 public SA_Outport accepted 40-bit lane tag/data/ready payloads. "
        "Wrong instance, X/Z, width or semantic drift fail closed; equal SA data remains ambiguous."
    )
    write(PLAN, plan)

    arm_contract = json.loads((PREVIOUS / "arm_known_contract.json").read_text(encoding="utf-8"))
    arm_contract.update({
        "schema": "conv-native-four-lane-p37-arm-known-contract-v1",
        "package_id": PACKAGE_ID,
        "source_bound_plan_sha256": sha(PLAN),
        "claim_boundary": "p36-proven exact 45-bit ARM token state retained only as the Buffer-side correlation anchor.",
    })
    write(ARM_CONTRACT, arm_contract)
    write(SA_CONTRACT, {
        "schema": "conv-native-four-lane-p37-sa-epoch-contract-v1",
        "package_id": PACKAGE_ID,
        "boundary_ids": lane_boundaries,
        "expected_instances": [sa_parents[index] + sa_suffixes[index] for index in range(8)],
        "near_miss_instances": [sa_near_parents[index] + sa_suffixes[index] for index in range(8)],
        "payload_width_bits": 40,
        "lane_count": 8,
        "tag_width_bits": 7,
        "lane_data_width_bits": 32,
        "ready_width_bits": 1,
        "payload_layout_msb_to_lsb": [
            "sa_outport_out_valid", "sa_outport_out_last", "sa_outport_out_same",
            "sa_outport_out_last_index[3:0]", "sa_outport_out_data[31:0]", "sa_outport_bp_post"
        ],
        "lane_valid_mask": "0x40",
        "target_group_tag": "0x3fdf",
        "group_tag_formula": "{lane_valid[7:0], OR(lane_last), OR(lane_same), lane0_last_index[3:0]}",
        "minimum_exact_accepted_rows": 2,
        "source_bound_plan_sha256": sha(PLAN),
        "parser_source_sha256": sha(SA_PARSER),
        "source_p36b_arm_decision": "TARGET_ARM_ROW2_STABLE_TOKEN_REACCEPT",
        "remaining_candidates": ["legitimate_distinct_sa_beats_same_tag", "held_sa_beat_reaccepted", "distinct_equal_value_sa_beats"],
        "claim_boundary": "Exact public output acceptance only; equal data is not sufficient to call replay and remains fail-closed ambiguous.",
    })
    shutil.copyfile(ARM_PARSER, OUTPUT / "generated_arm_known_parser.py")
    shutil.copyfile(SA_PARSER, OUTPUT / "generated_sa_epoch_parser.py")
    write(OUTPUT / "rule_change_ack.json", {
        "schema": "conv-native-exact-instance-payload-semfp-fresh-ack-v1",
        "epoch_id": EPOCH,
        "family": "conv_native_four_lane",
        "package_id": PACKAGE_ID,
        "first_fresh_after_change": False,
        "notification_acknowledged": True,
        "prior_first_fresh_pass": {
            "package_id": "r5_n4_0cc_p36b_semfp",
            "path": "artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p36b_semfp/r5_n4_0cc_p36b_semfp.first_fresh_validation.json",
            "sha256": "7e7cd5ea7e0ce3fbf0dcd6073dff27dbe0bd0b5abd619ccd67adfbacf02cfc3c",
        },
        "rule_ids": [
            "CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001",
            "CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001",
            "CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001",
        ],
        "server_rule_sha256": sha(ROOT / ".agents/rules/服务器测试包生成规则.md"),
        "generation_index_sha256": sha(ROOT / ".agents/rules/生成前必读索引.md"),
        "generator_sha256": sha(GENERATOR),
        "upload_hold_until": "ALL_EXACT_FINAL_ZIP_GATES_PASS",
    })
    run([
        sys.executable, str(GENERATOR), "materialize", "--catalog", str(CATALOG), "--plan", str(PLAN),
        "--output-dir", str(OUTPUT / "generated"), "--report", str(OUTPUT / "source_bound_generation_report.json"),
        "--cheap-check-output", str(OUTPUT / "source_bound_observer_generation.json"),
    ])
    print(json.dumps({
        "package_id": PACKAGE_ID,
        "catalog_sha256": sha(CATALOG),
        "plan_sha256": sha(PLAN),
        "arm_contract_sha256": sha(ARM_CONTRACT),
        "sa_contract_sha256": sha(SA_CONTRACT),
        "identity_sha256": sha(IDENTITY),
        "generation_report_sha256": sha(OUTPUT / "source_bound_generation_report.json"),
        "cheap_report_sha256": sha(OUTPUT / "source_bound_observer_generation.json"),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
