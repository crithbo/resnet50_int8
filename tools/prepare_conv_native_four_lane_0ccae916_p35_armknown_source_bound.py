#!/usr/bin/env python3
"""Prepare p35 generated observation without the undriven p34 payload leaf."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p35_armknown"
SOURCE = ROOT / "outputs/conv_native_four_lane_0ccae916_p34b_armtoken_source_bound"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p35_armknown_source_bound"
CATALOG = OUTPUT / "source_bound_probe_catalog.json"
PLAN = OUTPUT / "source_bound_probe_plan.json"
CONTRACT = OUTPUT / "arm_known_contract.json"
PARSER = ROOT / "tools/conv_native_four_lane_p35_arm_known_parser.py"
REMOVED_SYMBOL = "sym_e8d98d6f89e1060097f7a266"
REMOVED_CLASS = "ARM_ADD_ARRAY_REQ_ADDR"
RULE_EPOCH = "20260811-native-live-causal-partial-exit-v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p35 source-bound inputs")
    OUTPUT.mkdir(parents=True)
    shutil.copyfile(SOURCE / "source_bound_probe_catalog.json", CATALOG)
    plan = json.loads((SOURCE / "source_bound_probe_plan.json").read_text(encoding="utf-8"))
    plan["package_id"] = PACKAGE_ID
    arm = next(row for row in plan["boundaries"] if row["boundary_id"] == "arm_row2_accept_token_state")
    arm["payload_symbol_ids"] = [symbol for symbol in arm["payload_symbol_ids"] if symbol != REMOVED_SYMBOL]
    arm["classes"] = [row for row in arm["classes"] if row["class_id"] != REMOVED_CLASS]
    plan["decision_observations"] = [row for row in plan["decision_observations"] if row.get("class_id") != REMOVED_CLASS]
    plan["candidates"] = [row for row in plan["candidates"] if row["candidate_id"] != "arm_class_1"]
    for candidate in plan["candidates"]:
        candidate["signature"].pop("class_1", None)
    plan["runtime_budget"]["first_payload_samples"] = max(2, int(plan["runtime_budget"].get("first_payload_samples", 0)))
    plan["claim_boundary"] = (
        "Live exact-target Buffer clear/write anchors plus binary-known assigned ARM token/counter/reset state; "
        "the undriven add_array_req_addr p34 leaf is excluded and X/Z must fail closed."
    )
    write(PLAN, plan)
    old_contract = json.loads((SOURCE / "arm_token_contract.json").read_text(encoding="utf-8"))
    old_contract.update(
        {
            "schema": "conv-native-four-lane-p35-arm-known-contract-v1",
            "package_id": PACKAGE_ID,
            "source_bound_plan_sha256": sha(PLAN),
            "target_parser_source_sha256": sha(PARSER),
            "excluded_unknown_source": {
                "symbol_id": REMOVED_SYMBOL,
                "name": "add_array_req_addr",
                "reason": "Declared but undriven in current Array_Request_Manager; p34 emitted Z and the parser failed open.",
            },
            "claim_boundary": "Binary-known live exact-target records only; any X/Z payload is EVIDENCE_INCOMPLETE.",
        }
    )
    old_contract["arm_payload_layout_msb_to_lsb"] = [
        row for row in old_contract["arm_payload_layout_msb_to_lsb"] if row["symbol_id"] != REMOVED_SYMBOL
    ]
    write(CONTRACT, old_contract)
    shutil.copyfile(PARSER, OUTPUT / "generated_arm_known_parser.py")
    write(
        OUTPUT / "rule_change_ack.json",
        {
            "schema": "conv-native-live-causal-first-fresh-ack-v1",
            "epoch_id": RULE_EPOCH,
            "family": "conv_native_four_lane",
            "package_id": PACKAGE_ID,
            "first_fresh_after_change": True,
            "rule_id": "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001",
            "server_rule_sha256": sha(ROOT / ".agents/rules/服务器测试包生成规则.md"),
            "post_sim_helper_sha256": sha(ROOT / "tools/server_post_sim_return.py"),
            "upload_hold_until": "INDEPENDENT_EXTRA_AUDIT_PASS",
        },
    )
    print(json.dumps({"catalog_sha256": sha(CATALOG), "plan_sha256": sha(PLAN), "contract_sha256": sha(CONTRACT), "ack_sha256": sha(OUTPUT / "rule_change_ack.json")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
