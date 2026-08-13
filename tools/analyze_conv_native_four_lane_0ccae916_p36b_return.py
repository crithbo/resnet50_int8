#!/usr/bin/env python3
"""Validate the formal p36b return and adjudicate the known-width ARM token split."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import analyze_conv_native_four_lane_0ccae916_p35c_return as prior


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p36b_semfp"
EXECUTION_ID = "r1786417577426033642_868940"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p36b_semfp_"
    r"r1786417577426033642_868940_return.zip"
)
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PACKAGE_ID}.zip"
RETURN_BYTES = 157_471
RETURN_SHA256 = "d95a8c69b9fb0b44016880d9427146c5b4d1d1980fecbc760419aa5d9e21f9ed"
SOURCE_BYTES = 5_942_345
SOURCE_SHA256 = "0111176e62fca03a023bbd83098067191113bdc4a91a7bf5c7e0e37c3d288e0e"
SEMANTIC_FINGERPRINT = "127a2a92e6ef3ad9154114aa15ec5c39f69f6f13f1ac311ff9eadec3f34b21a5"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p36b_return_analysis/report.json"
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
    "tools/generate_server_source_bound_observer.py",
)


class AnalysisError(RuntimeError):
    pass


def source_files(records: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        path: {"size_bytes": row["bytes"], "sha256": row["sha256"]}
        for path, row in records.items()
        if path != "package_manifest.json"
    }


def main() -> int:
    for path in (RETURN_ZIP, SOURCE_ZIP):
        if not path.is_file():
            raise AnalysisError(f"required identity is absent: {path}")

    base = prior.prior.prior.base
    return_root, records, payloads, return_errors = base.safe_zip(RETURN_ZIP)
    source_root, source_records, source_payloads, source_errors = base.safe_zip(SOURCE_ZIP)
    core = json.loads(payloads["RETURN_CORE_MANIFEST.json"])
    core_status = json.loads(payloads["return_core/RETURN_CORE_STATUS.json"])
    sim_exit = json.loads(payloads["return_core/SIM_EXIT_RECEIPT.json"])
    plugins = json.loads(payloads["return_core/RETURN_PLUGIN_STATUS.json"])
    gate = json.loads(payloads["evidence/SERVER_RESULT_GATE.json"])
    identity = json.loads(payloads["evidence/production_rtl_identity.json"])
    package_status = json.loads(payloads["evidence/package_local_preflight_status.json"])
    arm_decision = json.loads(payloads["evidence/arm_known_decision.json"])
    source_bound_decision = json.loads(payloads["evidence/source_bound_causal_decision.json"])
    returned_generation = json.loads(payloads["source_package/source_bound_generation_report.json"])
    returned_binding = json.loads(payloads["source_package/source_bound_probe_binding.json"])
    source_manifest = json.loads(source_payloads["package_manifest.json"])
    request = json.loads(source_payloads["contracts/server_post_sim_return_request.json"])
    contract = json.loads(source_payloads["diagnostics/arm_known_contract.json"])
    source_generation = json.loads(source_payloads["diagnostics/source_bound_generation_report.json"])
    source_binding = json.loads(source_payloads["diagnostics/source_bound_probe_binding.json"])

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
    plugin_mismatches: dict[str, Any] = {}
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
    target = prior.target_arm_rows(payloads["runs/c0/source_bound_causal.log"], contract["target_parent"])
    accepted = arm_decision.get("arm_accept_rows", [])
    decoded = arm_decision.get("arm_accept_payloads_decoded", [])
    target_instance = contract["target_parent"] + ".u_Array_Request_Manager.codex_probe_arm_row2_accept_token_state_inst"
    exact_target_known = (
        len(accepted) == 2
        and all(row.get("instance") == target_instance for row in accepted)
        and all(row.get("payload_known") == "1" and row.get("payload_width") == "45" for row in accepted)
        and [int(row["time"]) for row in accepted] == [2_446_438_000, 2_446_448_000]
        and [row["payload"] for row in accepted] == ["17ff8803fdf6", "17ff8803fdf6"]
    )
    stable_decision = (
        arm_decision.get("decision") == "TARGET_ARM_ROW2_STABLE_TOKEN_REACCEPT"
        and arm_decision.get("matching_candidate_ids") == ["arm_stable_token_reaccept"]
        and arm_decision.get("stable_token_reaccept") is True
        and arm_decision.get("token_state_progress") is False
        and arm_decision.get("reset_or_wrap") is False
        and len(decoded) == 2
        and decoded[0] == decoded[1]
        and arm_decision.get("unknown_payload_rows") == []
    )
    arm_plugin = plugin_by_id.get("arm_known_parser", {})
    source_bound_plugin = plugin_by_id.get("source_bound_parser", {})
    generated_semantics = (
        returned_generation == source_generation
        and returned_binding == source_binding
        and returned_generation.get("diagnostic_semantics_sha256") == SEMANTIC_FINGERPRINT
        and returned_binding.get("diagnostic_semantics_sha256") == SEMANTIC_FINGERPRINT
        and returned_binding.get("schema") == "server-source-bound-probe-binding-v2"
        and returned_binding.get("private_hierarchical_xmr_generated") is False
        and all(
            boundary.get("instance_scope", {}).get("mode") == "EXACT_CANONICAL_INSTANCE"
            and boundary.get("payload_contract", {}).get("required_binary_known") is True
            for boundary in returned_binding.get("boundaries", [])
        )
    )

    checks = {
        "transport_identity_exact": RETURN_ZIP.stat().st_size == RETURN_BYTES and base.sha_file(RETURN_ZIP) == RETURN_SHA256,
        "source_identity_exact": SOURCE_ZIP.stat().st_size == SOURCE_BYTES and base.sha_file(SOURCE_ZIP) == SOURCE_SHA256,
        "return_crc_single_root_path_safe": not return_errors and return_root == f"{PACKAGE_ID}_return",
        "source_crc_single_root_path_safe": not source_errors and source_root == PACKAGE_ID,
        "return_exact_set_allowlist": set(records) == expected,
        "return_core_per_file_receipts_exact": not receipt_mismatches,
        "source_manifest_files_exact": source_manifest["files"] == source_files(source_records),
        "returned_source_members_exact": payloads["source_package/package_manifest.json"] == source_payloads["package_manifest.json"]
        and payloads["source_package/source_bound_generation_report.json"] == source_payloads["diagnostics/source_bound_generation_report.json"]
        and payloads["source_package/source_bound_probe_binding.json"] == source_payloads["diagnostics/source_bound_probe_binding.json"],
        "execution_and_unique_basename_exact": core["execution_id"] == EXECUTION_ID
        and core["return_basename"] == RETURN_ZIP.name
        and sim_exit["execution_id"] == EXECUTION_ID,
        "preflight_compile_and_simulation_started": compile_pass and simulation_started,
        "external_int_partial_return_exact": interrupted
        and core_status.get("disposition") == "PARTIAL_EXECUTION_RETURN"
        and core.get("required_plugin_failures") == [],
        "plugin_status_receipts_exact": not plugin_mismatches,
        "typed_v2_generation_semantics_exact": generated_semantics,
        "exact_target_45bit_binary_known": exact_target_known and target["all_payloads_binary_known"] and target["unknown_payload_count"] == 0,
        "stable_token_reaccept_not_reset_wrap": stable_decision and arm_plugin.get("pass") is True and arm_plugin.get("exit_code") == 0,
        "generic_candidate_not_overpromoted": source_bound_decision.get("decision") == "EVIDENCE_INCOMPLETE"
        and source_bound_decision.get("matching_candidate_ids") == []
        and source_bound_plugin.get("required_for_adjudication") is False,
        "diagnostic_has_no_formal_320d": source_manifest.get("formal_readback_count") == 0
        and gate["execution_gate"].get("formal_D_claimed") is False
        and not any(path.startswith("formal_D/") for path in records),
    }
    valid = all(checks.values())
    status = "P36B_PARTIAL_RETURN_VALID_STABLE_ARM_TAG_REACCEPT_PROVEN_SUCCESSOR_REQUIRED" if valid else "RETURN_VALIDATION_FAILED"
    report = {
        "schema": "conv-native-four-lane-0ccae916-p36b-return-analysis-v1",
        "status": status,
        "valid": valid,
        "classification": "PARTIAL_INTERRUPTED_EXACT_TARGET_STABLE_ARM_TAG_REACCEPT_PROVEN_PRODUCER_BEAT_IDENTITY_UNRESOLVED" if valid else "RETURN_VALIDATION_FAILED",
        "return_identity": {
            "path": str(RETURN_ZIP), "bytes": RETURN_ZIP.stat().st_size, "sha256": base.sha_file(RETURN_ZIP),
            "execution_id": EXECUTION_ID, "adjacent_sidecar_present": Path(str(RETURN_ZIP) + ".sha256").is_file(),
            "transport_policy": "USER_ATTESTED_EXTERNAL_SIDECAR_WAIVER",
        },
        "source_identity": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(), "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": base.sha_file(SOURCE_ZIP),
            "source_manifest_sha256": base.sha_bytes(source_payloads["package_manifest.json"]),
            "diagnostic_semantics_sha256": SEMANTIC_FINGERPRINT,
        },
        "internal_receipt": {
            "return_root": return_root, "return_file_count": len(records), "source_root": source_root,
            "source_file_count": len(source_records), "return_errors": return_errors, "source_errors": source_errors,
            "missing": sorted(expected - set(records)), "extra": sorted(set(records) - expected),
            "core_receipt_mismatches": receipt_mismatches, "plugin_status_mismatches": plugin_mismatches,
            "required_plugin_failures": core.get("required_plugin_failures"), "checks": checks,
        },
        "execution": {
            "compile_exit_status": compile_status, "run_exit_status": run_status, "signal_status": signal_status,
            "sim_exit_code": sim_exit.get("sim_exit_code"), "compile_succeeded": compile_pass,
            "dut_simulation_started": simulation_started, "c0_slice_finish": False, "natural_terminal": False,
            "formal_D_payload_present": False,
            "interruption_adjudication": "INT after qualified c0 activity; absent terminal/D is not a DUT, config, RTL or numeric failure.",
        },
        "production_rtl_identity": {
            "collection_valid": identity.get("collection_valid"),
            "actual_differs_cloud_authority": identity.get("actual_differs_cloud_authority"),
            "identity_difference_blocks_simulator": False,
            "array_request_manager_leaf": identity.get("leaves", {}).get("Array_Request_Manager.sv"),
            "causal_cone_adjudication": "Actual/cloud differences remain nonblocking provenance after production compile and c0 simulation; the dynamic exact-target records are authoritative for this diagnostic split.",
        },
        "observer_adjudication": {
            "exact_target_parent": contract["target_parent"], "payload_width_bits": 45,
            "target_arm_rows": target, "accepted_rows": accepted, "decoded_payloads": decoded,
            "decision": arm_decision.get("decision"), "stable_token_reaccept": True,
            "token_state_progress": False, "reset_or_wrap": False,
            "semantic_fingerprint": SEMANTIC_FINGERPRINT,
            "claim_boundary": "The ARM tag/state vector is identical across two qualified accepts. This does not yet distinguish two distinct SA data beats sharing one row tag from replay of one held producer beat.",
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": "two exact-target, 45-bit binary-known ARM row2 accepts at 2446438000 and 2446448000 with complete source-bound semantic identity",
            "FIRST_DIVERGENCE": "the two qualified accepts carry an identical ARM address/counter/tag vector, while the producer data-beat identity and between-accept valid epoch are not recorded",
            "HANG_ROOT_CAUSE": {
                "status": "DUT_CAUSAL_LEAF_NARROWED_TO_STABLE_ARM_TAG_ACCEPTED_TWICE_PRODUCER_BEAT_IDENTITY_UNRESOLVED",
                "functional_rtl_root_cause_proven": False, "authorized_config_fix": None,
                "closed_observational_equivalents": ["advancing ARM tag/counter state", "ARM address/counter reset or wrap"],
                "remaining_observational_equivalents": [
                    "two distinct SA output data beats that intentionally share one same-row tag",
                    "one held SA output beat accepted twice after ready reassertion",
                ],
            },
        },
        "result_conjunction": {
            "compile": compile_pass, "simulator_started": simulation_started, "c0_slice_finish": False,
            "natural_terminal_27_of_27": False, "formal_D_320_of_320": False, "mismatch_zero_claim": False,
            "E3": False, "E4": False, "E5": False, "performance_claimed": False, "passed": False,
        },
        "round_progress": {
            "compared_to_p35c_closed": [
                "B_CONV_NATIVE_P35C_SECOND_UNDRIVEN_PAYLOAD_LEAF",
                "unknown/X/Z payload and wrong-instance ambiguity",
                "ARM address/counter reset-or-wrap candidate",
                "advancing ARM tag/counter-state candidate",
            ],
            "first_proven": [
                "two exact-target post-clear ARM accepts have binary-known 45-bit payloads",
                "the accepted ARM address/counter/tag state is byte-identical on both transactions",
            ],
            "functional_progress": "NONZERO_CAUSAL_NARROWING",
            "remaining_candidates": ["distinct same-tag SA data beats", "same held SA beat replay"],
            "next_package_discrimination": "record exact-target SA output tag, full data beat, valid/ready acceptance, and the intervening producer-valid epoch, then correlate them to both Buffer5 ARM accepts",
        },
        "blocker_delta": {
            "closed": [
                "B_CONV_NATIVE_P35C_SECOND_UNDRIVEN_PAYLOAD_LEAF",
                "B_CONV_NATIVE_POSTCLEAR_ARM_TOKEN_ADVANCE_OR_RESET_WRAP_UNRESOLVED",
            ],
            "added": {
                "B_CONV_NATIVE_STABLE_ARM_TAG_DISTINCT_DATA_BEAT_OR_REPLAY_UNRESOLVED": "p36b proves identical accepted ARM tag state but does not carry producer data/valid-epoch identity."
            },
            "preserved": [
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN", "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN", "B_CONV_NATIVE4_E3_E4_E5_UNPROVEN",
            ],
        },
        "successor": {
            "required": valid, "fresh_identity": True, "tentative_package_id": "r5_n4_0cc_p37_saepoch",
            "highest_information_scope": "same exact c0 interval with transaction-qualified SA output data/valid epoch linked to both Buffer5 ARM accepts",
            "first_fresh_after_change": False,
            "prior_first_fresh_pass_receipt": "p36b typed-v2 first-fresh validation",
            "frozen": "87 payload/config/numeric/W3/workload/mapping/bitstream/execplan/SCA/golden/timeout/functional RTL",
            "server_action": False,
        },
        "current_rule_receipts": {
            path: {"bytes": (ROOT / path).stat().st_size, "sha256": base.sha_file(ROOT / path)} for path in RULE_PATHS
        },
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed_rule_ids": [
                "CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001",
                "CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001",
                "CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
            ],
            "evidence": "p36b excluded both undriven leaves, accepted only exact-target 45-bit known payloads, and reduced the causal split without overclaiming natural/D/E gates.",
            "claim_boundary": "exact-target diagnostic causality only; no numeric, RTL-fix, natural-terminal, formal-D or performance conclusion",
            "public_rule_modified": False,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise AnalysisError(f"refusing to overwrite formal analysis: {OUTPUT}")
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": status, "valid": valid, "output": str(OUTPUT)}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
