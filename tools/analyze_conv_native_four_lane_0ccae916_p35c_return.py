#!/usr/bin/env python3
"""Validate the formal p35c return and adjudicate its fail-closed ARM payload."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import analyze_conv_native_four_lane_0ccae916_p33b_return as prior


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p35c_armknown"
EXECUTION_ID = "r1786384633990059082_756950"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p35c_armknown_"
    r"r1786384633990059082_756950_return.zip"
)
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PACKAGE_ID}.zip"
RETURN_BYTES = 152_068
RETURN_SHA256 = "be5b38243a1ea156f6661bcbfbd8a7532951868d412d3f7c3b7025d94100f39f"
SOURCE_BYTES = 5_938_804
SOURCE_SHA256 = "b755592dbd01f05a63f0471ed76ede7673ab987b57a2cf579a8566a3d26f59fc"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p35c_return_analysis/report_v2.json"
RTL = ROOT / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Array_Request_Manager.sv"
RULE_PATHS = (
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md",
    ".agents/rules/INT8_SA点积专项规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md",
    ".agents/rules/整网测试收敛优化专项规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
    "tools/server_post_sim_return.py",
)


class AnalysisError(RuntimeError):
    pass


def target_arm_rows(raw: bytes, target_parent: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.decode(errors="replace").splitlines(), 1):
        row, error = prior.prior_row(line)
        if error or row is None:
            continue
        if (
            row.get("kind") == "EVENT"
            and row.get("boundary") == "arm_row2_accept_token_state"
            and prior.prior.normalize_parent(row["instance"]) == target_parent
        ):
            payload = row.get("payload", "")
            rows.append(
                {
                    "line": line_number,
                    "time": prior.number(row, "time"),
                    "mask": row.get("mask"),
                    "payload": payload,
                    "payload_binary_known": bool(payload)
                    and all(char in "0123456789abcdefABCDEF" for char in payload),
                }
            )
    return {
        "rows": rows,
        "row_count": len(rows),
        "all_payloads_binary_known": bool(rows) and all(row["payload_binary_known"] for row in rows),
        "unknown_payload_count": sum(not row["payload_binary_known"] for row in rows),
        "times": [row["time"] for row in rows],
    }


def live_assignment(text: str, name: str) -> bool:
    return any(line.strip().startswith(f"assign {name}") for line in text.splitlines())


def main() -> int:
    for path in (RETURN_ZIP, SOURCE_ZIP, RTL):
        if not path.is_file():
            raise AnalysisError(f"required identity is absent: {path}")
    return_root, records, payloads, return_errors = prior.prior.base.safe_zip(RETURN_ZIP)
    source_root, source_records, source_payloads, source_errors = prior.prior.base.safe_zip(SOURCE_ZIP)
    core = json.loads(payloads["RETURN_CORE_MANIFEST.json"])
    core_status = json.loads(payloads["return_core/RETURN_CORE_STATUS.json"])
    sim_exit = json.loads(payloads["return_core/SIM_EXIT_RECEIPT.json"])
    plugins = json.loads(payloads["return_core/RETURN_PLUGIN_STATUS.json"])
    gate = json.loads(payloads["evidence/SERVER_RESULT_GATE.json"])
    identity = json.loads(payloads["evidence/production_rtl_identity.json"])
    package_status = json.loads(payloads["evidence/package_local_preflight_status.json"])
    arm_decision = json.loads(payloads["evidence/arm_known_decision.json"])
    source_bound_decision = json.loads(payloads["evidence/source_bound_causal_decision.json"])
    source_manifest = json.loads(source_payloads["package_manifest.json"])
    request = json.loads(source_payloads["contracts/server_post_sim_return_request.json"])
    arm_contract = json.loads(source_payloads["diagnostics/arm_known_contract.json"])
    receipts = {row["path"]: {"bytes": row["bytes"], "sha256": row["sha256"]} for row in core["core_entry_receipts"]}
    expected = {
        "RETURN_CORE_MANIFEST.json",
        "return_core/RETURN_CORE_STATUS.json",
        "return_core/RETURN_PLUGIN_STATUS.json",
        "return_core/SIM_EXIT_RECEIPT.json",
        *receipts,
    }
    for plugin in request["plugins"]:
        plugin_id = plugin["plugin_id"]
        expected |= {
            f"return_core/plugins/{plugin_id}.status.json",
            f"return_core/plugins/{plugin_id}.stdout.log",
            f"return_core/plugins/{plugin_id}.stderr.log",
        }
    receipt_mismatches = {
        path: {"expected": row, "observed": records.get(path)}
        for path, row in receipts.items()
        if records.get(path) != row
    }
    plugin_mismatches = {}
    plugin_by_id = {row["plugin_id"]: row for row in plugins}
    for row in plugins:
        member = json.loads(payloads[f"return_core/plugins/{row['plugin_id']}.status.json"])
        if member != row:
            plugin_mismatches[row["plugin_id"]] = {"aggregate": row, "member": member}
    compile_status = int(payloads["evidence/compile_exit_status.txt"].decode().strip())
    run_status = int(payloads["evidence/run_exit_status.txt"].decode().strip())
    signal_status = payloads["evidence/signal_status.txt"].decode().strip()
    compile_log = payloads["runs/compile/compile_driver.log"].decode(errors="replace")
    simulator_argv = payloads["runs/c0/simulator_argv.txt"].decode(errors="replace")
    compile_pass = compile_status == 0 and "Compilation completed!" in compile_log and "Error-[XMRE]" not in compile_log
    simulation_started = (
        package_status.get("dut_simulation_started") is True
        and sim_exit.get("sim_started") is True
        and "+CODEX_CAUSAL_OBSERVER" in simulator_argv
    )
    interrupted = signal_status == "INT" and sim_exit.get("signal") == "INT" and sim_exit.get("sim_exit_code") == 130
    target = target_arm_rows(payloads["runs/c0/source_bound_causal.log"], arm_contract["target_parent"])
    rtl_text = RTL.read_text(encoding="utf-8")
    low_nibble_fields = [
        "arm_addr_update",
        "add_array_counter_0",
        "add_array_counter_1",
        "add_array_life_cnt",
    ]
    assignment_receipt = {name: live_assignment(rtl_text, name) for name in low_nibble_fields}
    source_files = {
        path: {"size_bytes": row["bytes"], "sha256": row["sha256"]}
        for path, row in source_records.items()
        if path != "package_manifest.json"
    }
    arm_plugin = plugin_by_id.get("arm_known_parser", {})
    fail_closed = (
        arm_decision.get("decision") == "EVIDENCE_INCOMPLETE"
        and arm_decision.get("arm_accept_payloads_decoded") == []
        and arm_decision.get("unknown_payload_rows")
        and arm_plugin.get("exit_code") == 1
        and arm_plugin.get("pass") is False
        and core.get("required_plugin_failures") == ["arm_known_parser"]
    )
    checks = {
        "transport_identity_exact": RETURN_ZIP.stat().st_size == RETURN_BYTES
        and prior.prior.base.sha_file(RETURN_ZIP) == RETURN_SHA256,
        "source_identity_exact": SOURCE_ZIP.stat().st_size == SOURCE_BYTES
        and prior.prior.base.sha_file(SOURCE_ZIP) == SOURCE_SHA256,
        "return_crc_single_root_path_safe": not return_errors and return_root == f"{PACKAGE_ID}_return",
        "source_crc_single_root_path_safe": not source_errors and source_root == PACKAGE_ID,
        "return_exact_set": set(records) == expected,
        "return_core_per_file_receipts_exact": not receipt_mismatches,
        "source_manifest_files_exact": source_manifest["files"] == source_files,
        "returned_source_manifest_exact": payloads["source_package/package_manifest.json"]
        == source_payloads["package_manifest.json"],
        "execution_and_unique_basename_exact": core["execution_id"] == EXECUTION_ID
        and core["return_basename"] == RETURN_ZIP.name
        and sim_exit["execution_id"] == EXECUTION_ID,
        "preflight_compile_and_simulation_started": compile_pass and simulation_started,
        "external_int_partial_return_exact": interrupted
        and core_status.get("disposition") == "PARTIAL_EXECUTION_RETURN",
        "plugin_status_receipts_exact": not plugin_mismatches,
        "unknown_arm_payload_reproduced": target["row_count"] == 3
        and target["unknown_payload_count"] == 3
        and target["times"] == [2_446_432_000, 2_446_438_000, 2_446_448_000]
        and len(arm_decision.get("unknown_payload_rows", [])) == 2,
        "unknown_payload_fails_closed": bool(fail_closed),
        "p34_undriven_leaf_excluded": arm_contract.get("excluded_unknown_source", {}).get("name")
        == "add_array_req_addr"
        and all(row.get("name") != "add_array_req_addr" for row in arm_contract["arm_payload_layout_msb_to_lsb"]),
        "second_undriven_leaf_bound": "wire                        add_array_life_cnt;" in rtl_text
        and assignment_receipt == {
            "arm_addr_update": True,
            "add_array_counter_0": True,
            "add_array_counter_1": True,
            "add_array_life_cnt": False,
        }
        and arm_contract["arm_payload_layout_msb_to_lsb"][-1]["name"] == "add_array_life_cnt",
        "diagnostic_has_no_formal_320d": source_manifest.get("formal_readback_count") == 0
        and gate["execution_gate"].get("formal_D_claimed") is False
        and not any(path.startswith("formal_D/") for path in records),
        "source_bound_generic_decision_not_promoted": source_bound_decision.get("decision") == "EVIDENCE_INCOMPLETE"
        and source_bound_decision.get("matching_candidate_ids") == [],
    }
    valid = all(checks.values())
    status = (
        "P35C_PARTIAL_RETURN_VALID_SECOND_UNDRIVEN_PAYLOAD_FAIL_CLOSED_SUCCESSOR_REQUIRED"
        if valid
        else "RETURN_VALIDATION_FAILED"
    )
    report = {
        "schema": "conv-native-four-lane-0ccae916-p35c-return-analysis-v1",
        "status": status,
        "valid": valid,
        "classification": (
            "PARTIAL_INTERRUPTED_PACKAGE_LOCAL_SOURCE_BOUND_PAYLOAD_COMPLETENESS_ESCAPE_NO_NEW_DUT_CONCLUSION"
            if valid
            else "RETURN_VALIDATION_FAILED"
        ),
        "return_identity": {
            "path": str(RETURN_ZIP),
            "bytes": RETURN_ZIP.stat().st_size,
            "sha256": prior.prior.base.sha_file(RETURN_ZIP),
            "execution_id": EXECUTION_ID,
            "adjacent_sidecar_present": Path(str(RETURN_ZIP) + ".sha256").is_file(),
            "transport_policy": "USER_ATTESTED_EXTERNAL_SIDECAR_WAIVER",
        },
        "source_identity": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": prior.prior.base.sha_file(SOURCE_ZIP),
            "source_manifest_sha256": prior.prior.base.sha_bytes(source_payloads["package_manifest.json"]),
        },
        "internal_receipt": {
            "return_root": return_root,
            "return_file_count": len(records),
            "source_root": source_root,
            "source_file_count": len(source_records),
            "return_errors": return_errors,
            "source_errors": source_errors,
            "missing": sorted(expected - set(records)),
            "extra": sorted(set(records) - expected),
            "core_receipt_mismatches": receipt_mismatches,
            "plugin_status_mismatches": plugin_mismatches,
            "required_plugin_failures": core.get("required_plugin_failures"),
            "checks": checks,
        },
        "execution": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "sim_exit_code": sim_exit.get("sim_exit_code"),
            "compile_succeeded": compile_pass,
            "dut_simulation_started": simulation_started,
            "natural_terminal": False,
            "c0_slice_finish": False,
            "formal_D_payload_present": False,
            "interruption_adjudication": "INT after qualified c0 activity; absent terminal/D is not a DUT, config, RTL or numeric failure.",
        },
        "production_rtl_identity": {
            "collection_valid": identity.get("collection_valid"),
            "actual_differs_cloud_authority": identity.get("actual_differs_cloud_authority"),
            "identity_difference_blocks_simulator": False,
            "array_request_manager_leaf": identity.get("leaves", {}).get("Array_Request_Manager.sv"),
            "causal_cone_adjudication": "Actual/cloud differences remain nonblocking provenance because production compile and c0 simulation passed.",
        },
        "observer_adjudication": {
            "target_arm_rows": target,
            "p34_unknown_leaf_excluded": "add_array_req_addr",
            "new_undriven_payload_leaf": "Array_Request_Manager.add_array_life_cnt",
            "low_nibble_assignment_receipt": assignment_receipt,
            "required_plugin_fail_closed": fail_closed,
            "arm_decision": arm_decision.get("decision"),
            "generic_source_bound_decision": source_bound_decision.get("decision"),
            "why_no_functional_decision": "The two accepted ARM rows remain X/Z-bearing. p35c correctly fails closed, but its generated payload still contains declaration-only add_array_life_cnt.",
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": "p35c closes the p34b fail-open decoder and preserves two live exact-target Buffer/ARM accepted-write time anchors at 2446438000 and 2446448000",
            "FIRST_DIVERGENCE": "the p35c source-bound payload includes undriven add_array_life_cnt as its least-significant field, producing Z in both accepted ARM payloads",
            "HANG_ROOT_CAUSE": {
                "status": "PACKAGE_LOCAL_SOURCE_BOUND_SEMANTIC_COMPLETENESS_ESCAPE",
                "functional_rtl_root_cause_proven": False,
                "authorized_config_fix": None,
                "remaining_observational_equivalents": [
                    "two legitimate advancing ARM tokens",
                    "stable ARM token replay",
                    "address/counter reset or wrap",
                ],
            },
        },
        "result_conjunction": {
            "compile": compile_pass,
            "simulator_started": simulation_started,
            "c0_slice_finish": False,
            "natural_terminal_27_of_27": False,
            "formal_D_320_of_320": False,
            "mismatch_zero_claim": False,
            "E3": False,
            "E4": False,
            "E5": False,
            "performance_claimed": False,
            "passed": False,
        },
        "round_progress": {
            "compared_to_p34b_closed": [
                "B_CONV_NATIVE_P34B_UNKNOWN_ARM_PAYLOAD_PARSER_FAIL_OPEN",
                "p34b undriven add_array_req_addr is excluded from the payload",
            ],
            "first_proven": [
                "p35c required parser really fails closed on live X/Z instead of fabricating token state",
                "a second declaration-only leaf add_array_life_cnt remains in the generated payload",
            ],
            "functional_progress": "ZERO",
            "remaining_candidates": ["legitimate token advance", "stable-token replay", "reset/wrap"],
            "next_package_discrimination": "remove every source-bound declaration-only payload leaf, bind exact instance and declared known width, fingerprint driver semantics, and re-run the same two accepted-write live-event interval",
        },
        "blocker_delta": {
            "closed": ["B_CONV_NATIVE_P34B_UNKNOWN_ARM_PAYLOAD_PARSER_FAIL_OPEN"],
            "added": {
                "B_CONV_NATIVE_P35C_SECOND_UNDRIVEN_PAYLOAD_LEAF": "add_array_life_cnt is declaration-only but was emitted as a required ARM payload field; p35c correctly returned EVIDENCE_INCOMPLETE."
            },
            "preserved": [
                "B_CONV_NATIVE_POSTCLEAR_ARM_TOKEN_ADVANCE_OR_REPLAY_UNRESOLVED",
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN",
                "B_CONV_NATIVE4_E4_E5_UNPROVEN",
            ],
        },
        "successor": {
            "required": valid,
            "fresh_identity": True,
            "tentative_package_id": "r5_n4_0cc_p36_semfp",
            "highest_information_scope": "same exact target and live interval with driver-proven binary-known-width fields only",
            "partial_exit_first_fresh_migration_reused": True,
            "new_next_fresh_gates_required": [
                "exact-instance binding",
                "payload-known-width",
                "semantic fingerprint",
            ],
            "frozen": "87 payload/config/numeric/W3/workload/mapping/bitstream/execplan/SCA/golden/timeout/functional RTL",
            "server_action": False,
        },
        "current_rule_receipts": {
            path: {"bytes": (ROOT / path).stat().st_size, "sha256": prior.prior.base.sha_file(ROOT / path)}
            for path in RULE_PATHS
        },
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed_rule_ids": [
                "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001",
                "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
            ],
            "evidence": "p35c kept a valid core return and failed its required live parser closed on X/Z, preventing a second fabricated functional conclusion.",
            "claim_boundary": "package-local diagnostic completeness only; no DUT/RTL/config/numeric conclusion",
            "public_rule_modified": False,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise AnalysisError(f"refusing to overwrite formal analysis: {OUTPUT}")
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": status, "valid": valid, "output": str(OUTPUT)}, ensure_ascii=False, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
