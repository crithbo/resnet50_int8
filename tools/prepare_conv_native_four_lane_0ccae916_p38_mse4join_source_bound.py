#!/usr/bin/env python3
"""Materialize the p38 exact MSE4 descriptor/data join observer."""

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
PACKAGE_ID = "r5_n4_0cc_p38_mse4join"
PREVIOUS = ROOT / "outputs/conv_native_four_lane_0ccae916_p37b_saepoch_source_bound"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p38_mse4join_source_bound"
CATALOG = OUTPUT / "source_bound_probe_catalog.json"
PLAN = OUTPUT / "source_bound_probe_plan.json"
IDENTITY = OUTPUT / "exact_instance_identity.json"
ARM_CONTRACT = OUTPUT / "arm_known_contract.json"
SA_CONTRACT = OUTPUT / "sa_epoch_contract.json"
JOIN_CONTRACT = OUTPUT / "mse4_join_contract.json"
GENERATOR = ROOT / "tools/generate_server_source_bound_observer.py"
JOIN_PARSER = ROOT / "tools/conv_native_four_lane_p38_mse4_join_parser.py"
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
    spec = importlib.util.spec_from_file_location("source_bound_generator_p38", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load source-bound generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p38 source-bound output")
    OUTPUT.mkdir(parents=True)
    sources = [
        RTL / "Slice/LSU/Buffer_Manager_Cluster/Array_Request_Manager.sv",
        RTL / "Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
        RTL / "Slice/Specialized_Array/SA_Outport/SA_Outport.sv",
        RTL / "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv",
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
    plan["runtime_budget"]["first_payload_samples"] = 32
    plan["runtime_budget"]["qualified_ring_depth"] = 32
    plan["runtime_budget"]["post_trigger_samples"] = 32

    identity = json.loads((PREVIOUS / "exact_instance_identity.json").read_text(encoding="utf-8"))
    identity["schema"] = "conv-native-four-lane-p38-exact-instance-identity-v1"
    identity["package_id"] = PACKAGE_ID
    identity["source_return"] = {
        "path": "C:/Users/15383/Downloads/r5_n4_0cc_p37b_saepoch_r1786424725008449561_945345_return.zip",
        "bytes": 464129,
        "sha256": "30438196b8c577eba2c711d54dc6ebb5dc6d8a8e3defbd0a86b1887c461ea484",
        "execution_id": "r1786424725008449561_945345",
    }
    target_parent = (
        "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
        "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice."
        "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
    )
    near_parent = target_parent.replace("slice_group_gen[0]", "slice_group_gen[1]")
    new_ids = (
        "mse4_memag_output_accept",
        "mse4_descriptor_accept",
        "mse4_buffer_data_accept",
        "mse4_wdata_output_accept",
        "mse4_slice_finish",
    )
    identity["mse4_target_parent"] = target_parent
    identity["boundaries"]["mse4_descriptor_data_join"] = {
        "expected_instances": [f"{target_parent}.codex_probe_{boundary}_inst" for boundary in new_ids],
        "near_miss_instances": [f"{near_parent}.codex_probe_{boundary}_inst" for boundary in new_ids],
    }
    identity["selection"] = (
        "exact slice-group0 Buffer5 and SA anchors plus exact slice-group0 MSE4 Memory_WR_Stream_Engine; "
        "slice-group1 MSE4 is the permanent wrong-instance negative"
    )
    write(IDENTITY, identity)
    identity_sha = sha(IDENTITY)
    for boundary in plan["boundaries"]:
        boundary["instance_scope"]["identity_provenance"]["sha256"] = identity_sha

    def row(name: str) -> dict[str, Any]:
        try:
            return symbols[("Memory_WR_Stream_Engine", name)]
        except KeyError as error:
            raise RuntimeError(f"required Memory_WR_Stream_Engine symbol is absent: {name}") from error

    def sid(name: str) -> str:
        return row(name)["symbol_id"]

    clock = sid("clk")
    reset = {"symbol_id": sid("rst_n"), "active_low": True}
    stage = {"op": "NOT", "arg": {"op": "SIGNAL", "symbol_id": sid("slice_rst")}}
    definitions = [
        {
            "boundary_id": "mse4_memag_output_accept",
            "role": "source_produce",
            "predicate": {"op": "AND", "args": [
                {"op": "SIGNAL", "symbol_id": sid("mse_mem_ag_tag_valid")},
                {"op": "SIGNAL", "symbol_id": sid("mse_mem_ag_bp_pre")},
            ]},
            "payload": ["mse_mem_ag_tag_valid"],
        },
        {
            "boundary_id": "mse4_descriptor_accept",
            "role": "queue_enqueue",
            "predicate": {"op": "AND", "args": [
                {"op": "SIGNAL", "symbol_id": sid("wr_data_chl_req_valid")},
                {"op": "SIGNAL", "symbol_id": sid("wr_data_chl_req_ready")},
            ]},
            "payload": ["wr_data_chl_req_valid"],
        },
        {
            "boundary_id": "mse4_buffer_data_accept",
            "role": "consumer_accept",
            "predicate": {"op": "AND", "args": [
                {"op": "SIGNAL", "symbol_id": sid("buf2mse_rvalid")},
                {"op": "SIGNAL", "symbol_id": sid("wr_data_chl_ready")},
            ]},
            "payload": ["wr_data_chl_ready"],
        },
        {
            "boundary_id": "mse4_wdata_output_accept",
            "role": "output_accept",
            "predicate": {"op": "AND", "args": [
                {"op": "SIGNAL", "symbol_id": sid("mse2mem_wdata_valid")},
                {"op": "SIGNAL", "symbol_id": sid("mem2mse_wdata_ready")},
            ]},
            "payload": ["mse2mem_wdata_valid", "mem2mse_wdata_ready"],
        },
        {
            "boundary_id": "mse4_slice_finish",
            "role": "terminal_propagation",
            "predicate": {"op": "SIGNAL", "symbol_id": sid("slice_cmpt_finish")},
            "payload": ["slice_cmpt_finish"],
        },
    ]
    widths: dict[str, int] = {}
    for definition in definitions:
        boundary_id = definition["boundary_id"]
        payload_names = definition["payload"]
        width = sum(int(row(name)["width_bits"]) for name in payload_names)
        widths[boundary_id] = width
        plan["boundaries"].append({
            "boundary_id": boundary_id,
            "target_module": "Memory_WR_Stream_Engine",
            "clock_symbol_id": clock,
            "reset": reset,
            "stage_gate": stage,
            "role": definition["role"],
            "classes": [{
                "bit": 0,
                "class_id": boundary_id.upper(),
                "predicate": definition["predicate"],
                "progress": definition["role"] != "terminal_propagation",
                "trigger": True,
            }],
            "payload_symbol_ids": [sid(name) for name in payload_names],
            "payload_contract": {
                "width_bits": width,
                "required_binary_known": True,
                "unknown_disposition": "EVIDENCE_INCOMPLETE",
            },
            "instance_scope": {
                "mode": "EXACT_CANONICAL_INSTANCE",
                "expected_instances": [f"{target_parent}.codex_probe_{boundary_id}_inst"],
                "near_miss_instances": [f"{near_parent}.codex_probe_{boundary_id}_inst"],
                "identity_provenance": {
                    "path": "diagnostics/exact_instance_identity.json",
                    "sha256": identity_sha,
                    "selector": "boundaries.mse4_descriptor_data_join",
                },
            },
        })

    by_role = {row["role"]: row for row in plan["role_coverage"]}
    for definition in definitions:
        coverage = by_role[definition["role"]]
        coverage["disposition"] = "covered"
        coverage["boundary_ids"] = sorted(set(coverage.get("boundary_ids", [])) | {definition["boundary_id"]})
        coverage["reason"] = "Exact transaction-qualified Buffer5/SA anchors and MSE4 descriptor/data/output/terminal join boundaries."
    plan["decision_observations"] = [
        {"observation_id": f"{boundary}_count", "boundary_id": boundary, "metric": "count_nonzero"}
        for boundary in new_ids
    ]
    plan["candidates"] = [{
        "candidate_id": "mse4_descriptor_data_join_pending_custom_correlator",
        "root_cause_class": "MSE4_DESCRIPTOR_DATA_JOIN",
        "signature": {f"{boundary}_count": True for boundary in new_ids[:-1]} | {"mse4_slice_finish_count": False},
    }]
    plan["claim_boundary"] = (
        "Exact slice-group0 MSE4 Memory_WR_Stream_Engine transaction-qualified memory-index, descriptor, Buffer-data, "
        "write-output and finish events, retaining p37b exact SA/Buffer anchors. Wrong instance, X/Z, width or semantic drift fail closed."
    )
    write(PLAN, plan)

    arm = json.loads((PREVIOUS / "arm_known_contract.json").read_text(encoding="utf-8"))
    arm.update({"package_id": PACKAGE_ID, "source_bound_plan_sha256": sha(PLAN)})
    write(ARM_CONTRACT, arm)
    sa = json.loads((PREVIOUS / "sa_epoch_contract.json").read_text(encoding="utf-8"))
    sa.update({"package_id": PACKAGE_ID, "source_bound_plan_sha256": sha(PLAN)})
    write(SA_CONTRACT, sa)
    write(JOIN_CONTRACT, {
        "schema": "conv-native-four-lane-p38-mse4-join-contract-v1",
        "package_id": PACKAGE_ID,
        "boundaries": [
            {
                "boundary_id": definition["boundary_id"],
                "expected_instance": f"{target_parent}.codex_probe_{definition['boundary_id']}_inst",
                "near_miss_instance": f"{near_parent}.codex_probe_{definition['boundary_id']}_inst",
                "payload_width_bits": widths[definition["boundary_id"]],
                "payload_symbols": definition["payload"],
            }
            for definition in definitions
        ],
        "expected_unit_elements": 16,
        "unit_binding": {
            "descriptor_size_source": "frozen MSE4 wr_data_chl_req_tsf_size=16 receipt in p37b MSE4_DESCRIPTOR_EDGE_V1",
            "buffer_size_source": "frozen MSE4 mse_buf_spatial_size=16 materialized config and p37b ROWLC4_BUFAG_EDGE_V1",
            "dynamic_event_payload_scope": "binary-known qualified handshake identity; unresolved macro-width unit fields are not added to generated payload",
        },
        "source_p37b_decision": "DISTINCT_SA_DATA_BEATS_SHARE_ARM_TAG",
        "source_p37b_descriptor_count": 18,
        "source_p37b_prepared_handshake_count": 20,
        "source_p37b_data_minus_descriptor_delta": 2,
        "source_bound_plan_sha256": sha(PLAN),
        "parser_source_sha256": sha(JOIN_PARSER),
        "claim_boundary": (
            "Exact MSE4 parent-module transaction units in c0 only. A positive delta proves data outruns descriptors; "
            "it does not by itself authorize a config or RTL fix and does not claim natural terminal or formal D."
        ),
    })
    shutil.copyfile(PREVIOUS / "generated_arm_known_parser.py", OUTPUT / "generated_arm_known_parser.py")
    shutil.copyfile(PREVIOUS / "generated_sa_epoch_parser.py", OUTPUT / "generated_sa_epoch_parser.py")
    shutil.copyfile(JOIN_PARSER, OUTPUT / "generated_mse4_join_parser.py")
    write(OUTPUT / "rule_change_ack.json", {
        "schema": "conv-native-exact-instance-payload-semfp-fresh-ack-v1",
        "epoch_id": EPOCH,
        "family": "conv_native_four_lane",
        "package_id": PACKAGE_ID,
        "first_fresh_after_change": False,
        "notification_acknowledged": True,
        "prior_first_fresh_pass": {
            "package_id": "r5_n4_0cc_p36b_semfp",
            "path": "artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p36b_semfp/r5_n4_0cc_p36b_semfp.first_fresh_validation.json",
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
        "join_contract_sha256": sha(JOIN_CONTRACT),
        "identity_sha256": sha(IDENTITY),
        "generation_report_sha256": sha(OUTPUT / "source_bound_generation_report.json"),
        "cheap_report_sha256": sha(OUTPUT / "source_bound_observer_generation.json"),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
