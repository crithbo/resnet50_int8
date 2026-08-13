#!/usr/bin/env python3
"""Validate p34b and fail closed on its unknown ARM payload escape."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import analyze_conv_native_four_lane_0ccae916_p33b_return as prior


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p34b_armtoken"
EXECUTION_ID = "r1786378914397059149_731119"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p34b_armtoken_"
    r"r1786378914397059149_731119_return.zip"
)
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PACKAGE_ID}.zip"
RETURN_BYTES = 150_589
RETURN_SHA256 = "e9f01d27a84b7dc6b912cff66f6895db95c2bab2cac1b7ef0814bd75178b129b"
SOURCE_BYTES = 5_934_761
SOURCE_SHA256 = "98d9f8b23824d2b5ec9e90f87fdfa1a3ee6bc61df5c9edca81ff19cf5f5b5fd1"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p34b_return_analysis/report.json"
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


def unknown_payload_receipt(raw: bytes) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.decode(errors="replace").splitlines(), 1):
        row, error = prior.prior_row(line)
        if error or row is None:
            continue
        if (
            row.get("kind") == "EVENT"
            and row.get("boundary") == "arm_row2_accept_token_state"
            and prior.prior.normalize_parent(row["instance"]) == prior.TARGET_PARENT
        ):
            payload = row.get("payload", "")
            rows.append(
                {
                    "line": line_number,
                    "time": prior.number(row, "time"),
                    "mask": row.get("mask"),
                    "payload": payload,
                    "payload_binary_known": bool(payload) and all(char in "0123456789abcdefABCDEF" for char in payload),
                }
            )
    return {
        "rows": rows,
        "row_count": len(rows),
        "all_payloads_binary_known": bool(rows) and all(row["payload_binary_known"] for row in rows),
        "unknown_payload_count": sum(not row["payload_binary_known"] for row in rows),
        "times": [row["time"] for row in rows],
    }


def main() -> int:
    for path in (RETURN_ZIP, SOURCE_ZIP):
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
    arm_decision = json.loads(payloads["evidence/arm_token_decision.json"])
    source_manifest = json.loads(source_payloads["package_manifest.json"])
    request = json.loads(source_payloads["contracts/server_post_sim_return_request.json"])
    receipts = {row["path"]: {"bytes": row["bytes"], "sha256": row["sha256"]} for row in core["core_entry_receipts"]}
    expected = {
        "RETURN_CORE_MANIFEST.json", "return_core/RETURN_CORE_STATUS.json",
        "return_core/RETURN_PLUGIN_STATUS.json", "return_core/SIM_EXIT_RECEIPT.json", *receipts,
    }
    for plugin in request["plugins"]:
        plugin_id = plugin["plugin_id"]
        expected |= {
            f"return_core/plugins/{plugin_id}.status.json",
            f"return_core/plugins/{plugin_id}.stdout.log",
            f"return_core/plugins/{plugin_id}.stderr.log",
        }
    receipt_mismatches = {path: {"expected": row, "observed": records.get(path)} for path, row in receipts.items() if records.get(path) != row}
    plugin_mismatches = {}
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
    simulation_started = package_status.get("dut_simulation_started") is True and sim_exit.get("sim_started") is True and "+CODEX_CAUSAL_OBSERVER" in simulator_argv
    interrupted = signal_status == "INT" and sim_exit.get("signal") == "INT" and sim_exit.get("sim_exit_code") == 130
    unknown = unknown_payload_receipt(payloads["runs/c0/source_bound_causal.log"])
    source_text = (ROOT / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Array_Request_Manager.sv").read_text(encoding="utf-8")
    assignment_live = any(
        line.strip().startswith("assign add_array_req_addr")
        for line in source_text.splitlines()
    )
    parser_source = source_payloads["package_tools/arm_token_parser.py"].decode(errors="replace")
    fail_open_parser = (
        'return int(row[key], 16)' in parser_source
        and 'return -1' in parser_source
        and 'value = hexadecimal(row, "payload")' in parser_source
        and 'decoded[field["name"]] = value &' in parser_source
        and "value < 0" not in parser_source
    )
    source_files = {
        path: {"size_bytes": row["bytes"], "sha256": row["sha256"]}
        for path, row in source_records.items() if path != "package_manifest.json"
    }
    checks = {
        "transport_identity_exact": RETURN_ZIP.stat().st_size == RETURN_BYTES and prior.prior.base.sha_file(RETURN_ZIP) == RETURN_SHA256,
        "source_identity_exact": SOURCE_ZIP.stat().st_size == SOURCE_BYTES and prior.prior.base.sha_file(SOURCE_ZIP) == SOURCE_SHA256,
        "return_crc_single_root_path_safe": not return_errors and return_root == f"{PACKAGE_ID}_return",
        "source_crc_single_root_path_safe": not source_errors and source_root == PACKAGE_ID,
        "return_exact_set": set(records) == expected,
        "return_core_per_file_receipts_exact": not receipt_mismatches,
        "source_manifest_files_exact": source_manifest["files"] == source_files,
        "returned_source_manifest_exact": payloads["source_package/package_manifest.json"] == source_payloads["package_manifest.json"],
        "execution_and_unique_basename_exact": core["execution_id"] == EXECUTION_ID and core["return_basename"] == RETURN_ZIP.name and sim_exit["execution_id"] == EXECUTION_ID,
        "preflight_compile_and_simulation_started": compile_pass and simulation_started,
        "external_int_partial_return_exact": interrupted and core_status.get("disposition") == "PARTIAL_EXECUTION_RETURN",
        "post_sim_core_and_required_plugin_completed": not core.get("required_plugin_failures") and not plugin_mismatches,
        "unknown_arm_payload_reproduced": unknown["row_count"] == 3 and unknown["unknown_payload_count"] == 3 and unknown["times"] == [2_446_432_000, 2_446_438_000, 2_446_448_000],
        "undriven_observed_leaf_bound": not assignment_live and "wire                        add_array_req_addr;" in source_text,
        "parser_fail_open_reproduced": fail_open_parser and arm_decision.get("decision") == "TARGET_ARM_ROW2_STABLE_TOKEN_REACCEPT",
        "diagnostic_has_no_formal_320d": source_manifest.get("formal_readback_count") == 0 and gate["execution_gate"].get("formal_D_claimed") is False and not any(path.startswith("formal_D/") for path in records),
    }
    valid = all(checks.values())
    status = "P34B_PARTIAL_RETURN_VALID_PACKAGE_PARSER_FAIL_OPEN_SUCCESSOR_REQUIRED" if valid else "RETURN_VALIDATION_FAILED"
    report = {
        "schema": "conv-native-four-lane-0ccae916-p34b-return-analysis-v1",
        "status": status,
        "valid": valid,
        "classification": "PARTIAL_INTERRUPTED_PACKAGE_LOCAL_UNKNOWN_PAYLOAD_FAIL_OPEN_NO_NEW_DUT_CONCLUSION" if valid else "RETURN_VALIDATION_FAILED",
        "return_identity": {"path": str(RETURN_ZIP), "bytes": RETURN_ZIP.stat().st_size, "sha256": prior.prior.base.sha_file(RETURN_ZIP), "execution_id": EXECUTION_ID, "adjacent_sidecar_present": Path(str(RETURN_ZIP) + ".sha256").is_file(), "transport_policy": "USER_ATTESTED_EXTERNAL_SIDECAR_WAIVER"},
        "source_identity": {"path": SOURCE_ZIP.relative_to(ROOT).as_posix(), "bytes": SOURCE_ZIP.stat().st_size, "sha256": prior.prior.base.sha_file(SOURCE_ZIP), "source_manifest_sha256": prior.prior.base.sha_bytes(source_payloads["package_manifest.json"])},
        "internal_receipt": {"return_root": return_root, "return_file_count": len(records), "source_root": source_root, "source_file_count": len(source_records), "return_errors": return_errors, "source_errors": source_errors, "missing": sorted(expected - set(records)), "extra": sorted(set(records) - expected), "core_receipt_mismatches": receipt_mismatches, "plugin_status_mismatches": plugin_mismatches, "checks": checks},
        "execution": {"compile_exit_status": compile_status, "run_exit_status": run_status, "signal_status": signal_status, "sim_exit_code": sim_exit.get("sim_exit_code"), "compile_succeeded": compile_pass, "dut_simulation_started": simulation_started, "natural_terminal": False, "c0_slice_finish": False, "formal_D_payload_present": False, "interruption_adjudication": "INT after qualified c0 activity; absent terminal/D is not a DUT, config, RTL or numeric failure."},
        "production_rtl_identity": {"collection_valid": identity.get("collection_valid"), "actual_differs_cloud_authority": identity.get("actual_differs_cloud_authority"), "identity_difference_blocks_simulator": False, "array_request_manager_leaf": identity.get("leaves", {}).get("Array_Request_Manager.sv"), "causal_cone_adjudication": "Actual/cloud differences are nonblocking provenance because production compile and c0 simulation passed."},
        "observer_escape": {
            "unknown_payload_receipt": unknown,
            "observed_undriven_leaf": "Array_Request_Manager.add_array_req_addr",
            "current_source_assignment_live": assignment_live,
            "parser_fail_open": fail_open_parser,
            "reported_decision_rejected": arm_decision.get("decision"),
            "why_rejected": "payload contains Z; hexadecimal() returns -1 and decode_payload bit-slices -1 into all-one fields instead of failing closed",
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": "p33b exact target clear followed by two ARM-owned accepted writes at 2446438000 and 2446448000",
            "FIRST_DIVERGENCE": "p34b token payload is not binary-known; package parser fabricated all-one decoded fields from -1",
            "HANG_ROOT_CAUSE": {"status": "PACKAGE_LOCAL_DIAGNOSTIC_PAYLOAD_UNKNOWN_FAIL_OPEN", "functional_rtl_root_cause_proven": False, "authorized_config_fix": None, "remaining_observational_equivalents": ["two legitimate advancing ARM tokens", "stable ARM token replay", "address/counter reset or wrap"]},
        },
        "result_conjunction": {"compile": compile_pass, "simulator_started": simulation_started, "c0_slice_finish": False, "natural_terminal_27_of_27": False, "formal_D_320_of_320": False, "mismatch_zero_claim": False, "E3": False, "E4": False, "E5": False, "performance_claimed": False, "passed": False},
        "round_progress": {"compared_to_p33b_closed": [], "first_proven": ["p34b observer payload contains unknown Z", "package parser maps the unknown payload to a false all-one token decision"], "functional_progress": "ZERO", "remaining_candidates": ["legitimate token advance", "stable-token replay", "reset/wrap"], "next_package_discrimination": "emit only binary-known assigned ARM state/handshake fields, reject X/Z before decode, and adjudicate the same two accepted writes from live EVENT records"},
        "blocker_delta": {"closed": [], "added": {"B_CONV_NATIVE_P34B_UNKNOWN_ARM_PAYLOAD_PARSER_FAIL_OPEN": "Required token decision is invalid because two payloads end in Z and parser decodes -1."}, "preserved": ["B_CONV_NATIVE_POSTCLEAR_ARM_TOKEN_ADVANCE_OR_REPLAY_UNRESOLVED", "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN", "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN", "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN", "B_CONV_NATIVE4_E4_E5_UNPROVEN"]},
        "successor": {"required": valid, "fresh_identity": True, "package_id": "r5_n4_0cc_p35_armknown", "highest_information_scope": "same exact-target clear-to-final ARM accept window with binary-known assigned fields only and X/Z fail-closed parser", "first_fresh_after_rule_change": True, "new_rule_id": "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001", "frozen": "87 payload/config/numeric/W3/workload/mapping/bitstream/execplan/SCA/golden/functional RTL", "server_action": False},
        "current_rule_receipts": {path: {"bytes": (ROOT / path).stat().st_size, "sha256": prior.prior.base.sha_file(ROOT / path)} for path in RULE_PATHS},
        "rule_feedback": {"type": "RULE_CONFIRMATION", "confirmed_rule_ids": ["CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001", "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001", "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001"], "evidence": "p34b independent core preserved live rows, but the required parser accepted an X/Z payload and emitted a false decision; next fresh must use live EVENT fixtures and fail closed on non-binary payload.", "claim_boundary": "package-local diagnostic evidence completeness only; no DUT/RTL/config/numeric conclusion", "public_rule_modified": False},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise AnalysisError(f"refusing to overwrite formal analysis: {OUTPUT}")
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": status, "valid": valid, "output": str(OUTPUT)}, ensure_ascii=False, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
