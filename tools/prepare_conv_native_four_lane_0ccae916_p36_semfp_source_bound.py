#!/usr/bin/env python3
"""Materialize the p36 exact-instance/binary-known source-bound observer."""

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
PACKAGE_ID = "r5_n4_0cc_p36_semfp"
PREVIOUS = ROOT / "outputs/conv_native_four_lane_0ccae916_p35c_armknown_source_bound"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p36_semfp_source_bound"
CATALOG = OUTPUT / "source_bound_probe_catalog.json"
PLAN = OUTPUT / "source_bound_probe_plan.json"
CONTRACT = OUTPUT / "arm_known_contract.json"
IDENTITY = OUTPUT / "exact_instance_identity.json"
GENERATOR = ROOT / "tools/generate_server_source_bound_observer.py"
PARSER = ROOT / "tools/conv_native_four_lane_p35_arm_known_parser.py"
RTL = ROOT / "NDP_copy01/rtl"
RTL_TREE_SHA256 = "c6902de6fabfce81ee10af02cec238e5b11d2fdece9454041415c455556e1093"
REMOVED_SYMBOL = "sym_dfcfd3066f84c568106c0317"
REMOVED_CLASS = "ARM_ADD_ARRAY_LIFE"
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
    spec = importlib.util.spec_from_file_location("source_bound_generator_p36", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load source-bound generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p36 source-bound output")
    OUTPUT.mkdir(parents=True)
    sources = [
        RTL / "Slice/LSU/Buffer_Manager_Cluster/Array_Request_Manager.sv",
        RTL / "Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
        RTL / "includes/NDP_Parameters.svh",
    ]
    argv = [sys.executable, str(GENERATOR), "catalog", "--rtl-root", str(RTL), "--rtl-tree-sha256", RTL_TREE_SHA256]
    for source in sources:
        argv.extend(["--source", str(source)])
    argv.extend(["--output", str(CATALOG)])
    run(argv)

    generator = load_generator()
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    plan = json.loads((PREVIOUS / "source_bound_probe_plan.json").read_text(encoding="utf-8"))
    plan["schema"] = "server-source-bound-probe-plan-v2"
    plan["package_id"] = PACKAGE_ID
    plan["catalog_identity"] = {
        "rtl_tree_sha256": RTL_TREE_SHA256,
        "catalog_semantic_sha256": generator.semantic_sha256(catalog),
    }
    plan["diagnostic_semantics"] = {
        "instance_match": "EXACT_CANONICAL_EQUALITY",
        "record_grouping_key": ["boundary_id", "canonical_instance", "seq"],
        "unknown_payload": "EVIDENCE_INCOMPLETE",
        "numeric_parse_failure": "EVIDENCE_INCOMPLETE",
        "candidate_match_cardinality": "EXACTLY_ONE",
    }

    parent = (
        "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
        "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice."
        "u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager"
    )
    near_parent = parent.replace("BUFFER_MANAGER[5]", "BUFFER_MANAGER[4]")
    suffixes = {
        "row2_clear_window_write_owner": ".u_Buffer.codex_probe_row2_clear_window_write_owner_inst",
        "arm_row2_accept_token_state": ".u_Array_Request_Manager.codex_probe_arm_row2_accept_token_state_inst",
        "final_same_row2_block": ".u_Array_Request_Manager.codex_probe_final_same_row2_block_inst",
    }
    identity_value = {
        "schema": "conv-native-four-lane-p36-exact-instance-identity-v1",
        "source_return": {
            "path": "C:/Users/15383/Downloads/r5_n4_0cc_p35c_armknown_r1786384633990059082_756950_return.zip",
            "bytes": 152068,
            "sha256": "be5b38243a1ea156f6661bcbfbd8a7532951868d412d3f7c3b7025d94100f39f",
            "execution_id": "r1786384633990059082_756950",
        },
        "target_parent": parent,
        "boundaries": {
            key: {"expected_instance": parent + suffix, "near_miss_instance": near_parent + suffix}
            for key, suffix in suffixes.items()
        },
        "selection": "exact group0 Buffer_Manager[5]; group0 Buffer_Manager[4] is a permanent wrong-instance negative",
    }
    write(IDENTITY, identity_value)

    symbols = {row["symbol_id"]: row for row in catalog["symbols"]}
    arm = next(row for row in plan["boundaries"] if row["boundary_id"] == "arm_row2_accept_token_state")
    arm["payload_symbol_ids"] = [value for value in arm["payload_symbol_ids"] if value != REMOVED_SYMBOL]
    arm["classes"] = [row for row in arm["classes"] if row["class_id"] != REMOVED_CLASS]
    plan["decision_observations"] = [row for row in plan["decision_observations"] if row.get("class_id") != REMOVED_CLASS]
    plan["candidates"] = [row for row in plan["candidates"] if row["candidate_id"] != "arm_class_4"]
    for candidate in plan["candidates"]:
        candidate["signature"].pop("class_4", None)
        candidate["signature"]["arm_event_count"] = True
    plan["decision_observations"].append({
        "observation_id": "arm_event_count",
        "boundary_id": "arm_row2_accept_token_state",
        "metric": "count_nonzero",
    })
    for boundary in plan["boundaries"]:
        boundary_id = boundary["boundary_id"]
        boundary["instance_scope"] = {
            "mode": "EXACT_CANONICAL_INSTANCE",
            "expected_instances": [parent + suffixes[boundary_id]],
            "near_miss_instances": [near_parent + suffixes[boundary_id]],
            "identity_provenance": {
                "path": "diagnostics/exact_instance_identity.json",
                "sha256": sha(IDENTITY),
                "selector": f"boundaries.{boundary_id}",
            },
        }
        width = sum(int(symbols[value]["width_bits"]) for value in boundary["payload_symbol_ids"])
        boundary["payload_contract"] = {
            "width_bits": width,
            "required_binary_known": True,
            "unknown_disposition": "EVIDENCE_INCOMPLETE",
        }
    plan["claim_boundary"] = (
        "Exact canonical group0 Buffer5 instances and binary-known declared-width payloads only; "
        "both undriven ARM add_* leaves are excluded, and wrong-instance/X/Z/width errors fail closed."
    )
    write(PLAN, plan)

    old_contract = json.loads((PREVIOUS / "arm_known_contract.json").read_text(encoding="utf-8"))
    old_contract.update({
        "schema": "conv-native-four-lane-p36-arm-known-contract-v1",
        "package_id": PACKAGE_ID,
        "source_bound_plan_sha256": sha(PLAN),
        "target_parser_source_sha256": sha(PARSER),
        "excluded_unknown_sources": [
            old_contract.pop("excluded_unknown_source"),
            {
                "symbol_id": REMOVED_SYMBOL,
                "name": "add_array_life_cnt",
                "reason": "Declared but undriven in current Array_Request_Manager; p35c emitted Z and correctly failed closed.",
            },
        ],
        "claim_boundary": "Exact target plus binary-known 45-bit live ARM payload; any wrong instance, X/Z, parse failure, or width mismatch is EVIDENCE_INCOMPLETE.",
    })
    old_contract["arm_payload_layout_msb_to_lsb"] = [
        row for row in old_contract["arm_payload_layout_msb_to_lsb"] if row["symbol_id"] != REMOVED_SYMBOL
    ]
    write(CONTRACT, old_contract)
    shutil.copyfile(PARSER, OUTPUT / "generated_arm_known_parser.py")
    write(OUTPUT / "rule_change_ack.json", {
        "schema": "conv-native-exact-instance-payload-semfp-first-fresh-ack-v1",
        "epoch_id": EPOCH,
        "family": "conv_native_four_lane",
        "package_id": PACKAGE_ID,
        "first_fresh_after_change": True,
        "notification_acknowledged": True,
        "rule_ids": [
            "CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001",
            "CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001",
            "CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001",
        ],
        "server_rule_sha256": sha(ROOT / ".agents/rules/服务器测试包生成规则.md"),
        "generation_index_sha256": sha(ROOT / ".agents/rules/生成前必读索引.md"),
        "generator_sha256": sha(GENERATOR),
        "upload_hold_until": "INDEPENDENT_EXTRA_AUDIT_PASS",
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
        "contract_sha256": sha(CONTRACT),
        "identity_sha256": sha(IDENTITY),
        "generation_report_sha256": sha(OUTPUT / "source_bound_generation_report.json"),
        "cheap_report_sha256": sha(OUTPUT / "source_bound_observer_generation.json"),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
