#!/usr/bin/env python3
"""Validate the formal p37b return and adjudicate the SA beat identity split."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import analyze_conv_native_four_lane_0ccae916_p36b_return as prior


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p37b_saepoch"
EXECUTION_ID = "r1786424725008449561_945345"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p37b_saepoch_"
    r"r1786424725008449561_945345_return.zip"
)
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PACKAGE_ID}.zip"
RETURN_BYTES = 464_129
RETURN_SHA256 = "30438196b8c577eba2c711d54dc6ebb5dc6d8a8e3defbd0a86b1887c461ea484"
SOURCE_BYTES = 5_957_133
SOURCE_SHA256 = "d2f0bd8dd532975cebb12dab89fac8a4dbe0aa87e2a0ac6e38323ad7fedc2c80"
SEMANTIC_FINGERPRINT = "454d569a675d9a97eef177ff3e49f21e55c62bd0f49a2fe337e0478859f23f33"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p37b_return_analysis/report.json"
FAMILY_AUDIT = ROOT / "outputs/conv_native_four_lane_0ccae916_p37b_saepoch/p37b_family_audit.json"
FINAL_AUDIT = ROOT / "outputs/conv_native_four_lane_0ccae916_p37b_saepoch/r5_n4_0cc_p37b_saepoch.final_zip_audit.json"
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


def matching_lines(raw: bytes, marker: str) -> list[str]:
    return [line for line in raw.decode(errors="replace").splitlines() if marker in line]


def main() -> int:
    required_paths = (RETURN_ZIP, SOURCE_ZIP, FAMILY_AUDIT, FINAL_AUDIT)
    for path in required_paths:
        if not path.is_file():
            raise AnalysisError(f"required identity is absent: {path}")

    base = prior.prior.prior.prior.base
    return_root, records, payloads, return_errors = base.safe_zip(RETURN_ZIP)
    source_root, source_records, source_payloads, source_errors = base.safe_zip(SOURCE_ZIP)
    core = json.loads(payloads["RETURN_CORE_MANIFEST.json"])
    core_status = json.loads(payloads["return_core/RETURN_CORE_STATUS.json"])
    sim_exit = json.loads(payloads["return_core/SIM_EXIT_RECEIPT.json"])
    plugins = json.loads(payloads["return_core/RETURN_PLUGIN_STATUS.json"])
    gate = json.loads(payloads["evidence/SERVER_RESULT_GATE.json"])
    identity = json.loads(payloads["evidence/production_rtl_identity.json"])
    package_status = json.loads(payloads["evidence/package_local_preflight_status.json"])
    sa_decision = json.loads(payloads["evidence/sa_epoch_decision.json"])
    arm_decision = json.loads(payloads["evidence/arm_known_decision.json"])
    source_bound_decision = json.loads(payloads["evidence/source_bound_causal_decision.json"])
    buffer5 = json.loads(payloads["evidence/buffer5_public_summary.json"])
    returned_generation = json.loads(payloads["source_package/source_bound_generation_report.json"])
    returned_binding = json.loads(payloads["source_package/source_bound_probe_binding.json"])
    source_manifest = json.loads(source_payloads["package_manifest.json"])
    request = json.loads(source_payloads["contracts/server_post_sim_return_request.json"])
    sa_contract = json.loads(source_payloads["diagnostics/sa_epoch_contract.json"])
    source_generation = json.loads(source_payloads["diagnostics/source_bound_generation_report.json"])
    source_binding = json.loads(source_payloads["diagnostics/source_bound_probe_binding.json"])
    family_audit = json.loads(FAMILY_AUDIT.read_text(encoding="utf-8"))
    final_audit = json.loads(FINAL_AUDIT.read_text(encoding="utf-8"))

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

    beats = sa_decision.get("accepted_complete_beats", [])
    expected_data = [
        "000004790000288700001fac00001feaffee36a4fffffe73000010af00006eaa",
        "fffffb0b00001f310000163400001674ffee2d3afffff4a5000006330000661e",
    ]
    exact_beats = (
        len(beats) == 2
        and [row.get("time") for row in beats] == [2_446_438_000, 2_446_441_000]
        and [row.get("group_tag") for row in beats] == ["0x3fdf", "0x3fdf"]
        and [row.get("data_hex") for row in beats] == expected_data
        and all(len(row.get("lanes", [])) == 8 for row in beats)
        and all(
            lane.get("lane") == index and lane.get("instance") == sa_contract["expected_instances"][index]
            for beat in beats for index, lane in enumerate(beat["lanes"])
        )
    )
    exact_sa_decision = (
        sa_decision.get("decision") == "DISTINCT_SA_DATA_BEATS_SHARE_ARM_TAG"
        and sa_decision.get("matching_candidate_ids") == ["legitimate_distinct_sa_beats_same_tag"]
        and sa_decision.get("selected_data_distinct") is True
        and sa_decision.get("selected_data_identical") is False
        and sa_decision.get("errors") == []
        and sa_decision.get("payload_width_bits") == 40
        and sa_decision.get("wrong_instance_rows_ignored") == 21_408
    )
    generated_semantics = (
        returned_generation == source_generation
        and returned_binding == source_binding
        and returned_generation.get("diagnostic_semantics_sha256") == SEMANTIC_FINGERPRINT
        and returned_binding.get("diagnostic_semantics_sha256") == SEMANTIC_FINGERPRINT
        and returned_binding.get("schema") == "server-source-bound-probe-binding-v2"
        and returned_binding.get("private_hierarchical_xmr_generated") is False
        and len(returned_binding.get("boundaries", [])) == 11
        and all(
            boundary.get("instance_scope", {}).get("mode") == "EXACT_CANONICAL_INSTANCE"
            and boundary.get("payload_contract", {}).get("required_binary_known") is True
            for boundary in returned_binding.get("boundaries", [])
        )
    )
    local_fixture_pass = (
        family_audit.get("valid") is True
        and family_audit.get("pass") is True
        and family_audit.get("positive_control_count") == 3
        and family_audit.get("negative_control_count") == 4
        and family_audit.get("checks", {}).get("four_negatives_fail_closed") is True
        and family_audit.get("checks", {}).get("two_positive_decisions") is True
        and family_audit.get("case_results", {}).get("mixed_lane_same", {}).get("exit_code") == 0
        and family_audit.get("case_results", {}).get("mixed_lane_same", {}).get("decision", {}).get("decision")
        == "DISTINCT_SA_DATA_BEATS_SHARE_ARM_TAG"
    )

    observer_log = payloads["runs/c0/return_observer.log"]
    dwrite = matching_lines(observer_log, "DWRITE_PATH_EDGE_V1")
    wrterm = matching_lines(observer_log, "WRTERM2_EDGE_V1")
    datahub = matching_lines(observer_log, "DATAHUB_DRAIN_EDGE_V1")
    dskew = matching_lines(observer_log, "DSKEW_EDGE_V1")
    downstream_narrowing = (
        len(dwrite) == 30
        and len(wrterm) == 16
        and len(datahub) == 29
        and len(dskew) == 44
        and "prepared_count=32" in dwrite[-1]
        and "wdata_hs=0" in dwrite[-1]
        and "desc_count=0" in wrterm[-1]
        and "src_count=3" in wrterm[-1]
        and "tag_count=2" in wrterm[-1]
        and "hold=1" in wrterm[-1]
        and "head8=1" in datahub[-1]
        and "accept8=1" in datahub[-1]
        and "desc=18" in dskew[-1]
        and "prepared=20" in dskew[-1]
        and "delta=2" in dskew[-1]
    )

    sa_plugin = plugin_by_id.get("sa_epoch_parser", {})
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
        "real_per_lane_accept_and_full_256bit_identity": exact_beats and exact_sa_decision,
        "sa_epoch_required_plugin_pass": sa_plugin.get("pass") is True
        and sa_plugin.get("exit_code") == 0
        and sa_plugin.get("required_for_adjudication") is True,
        "nonuniform_lane_positive_and_negatives_effective": local_fixture_pass,
        "downstream_write_path_narrowing_receipt": downstream_narrowing,
        "stable_arm_tag_receipt_preserved": arm_decision.get("decision") == "TARGET_ARM_ROW2_STABLE_TOKEN_REACCEPT",
        "generic_candidate_not_overpromoted": source_bound_decision.get("decision") == "SA_ACCEPTED_DATA_IDENTITY",
        "final_public_buffer5_stall_exact": buffer5.get("valid") is True
        and buffer5.get("last", {}).get("mrm_valid") == "0x0"
        and buffer5.get("last", {}).get("sa_raw_valid") == "1"
        and buffer5.get("last", {}).get("sa_ready") == "0"
        and buffer5.get("last", {}).get("blocked_cycles") == "786432",
        "diagnostic_has_no_formal_320d": source_manifest.get("formal_readback_count") == 0
        and gate["execution_gate"].get("formal_D_claimed") is False
        and not any(path.startswith("formal_D/") for path in records),
        "release_audits_frozen_pass": final_audit.get("valid") is True
        and final_audit.get("status") == "PACKAGE_READY_NOT_RUN",
    }
    valid = all(checks.values())
    status = "P37B_PARTIAL_RETURN_VALID_DISTINCT_SA_BEATS_PROVEN_WRITE_DESCRIPTOR_BOUNDARY_SUCCESSOR_REQUIRED" if valid else "RETURN_VALIDATION_FAILED"
    report = {
        "schema": "conv-native-four-lane-0ccae916-p37b-return-analysis-v1",
        "status": status,
        "valid": valid,
        "classification": "PARTIAL_INTERRUPTED_DISTINCT_SA_BEATS_SAME_TAG_PROVEN_MSE4_WRITE_DESCRIPTOR_DATA_SKEW_UNRESOLVED" if valid else "RETURN_VALIDATION_FAILED",
        "return_identity": {
            "path": str(RETURN_ZIP), "bytes": RETURN_ZIP.stat().st_size, "sha256": base.sha_file(RETURN_ZIP),
            "execution_id": EXECUTION_ID, "adjacent_sidecar_present": Path(str(RETURN_ZIP) + ".sha256").is_file(),
            "transport_policy": "USER_ATTESTED_EXTERNAL_SIDECAR_WAIVER",
        },
        "source_identity": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(), "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": base.sha_file(SOURCE_ZIP), "source_manifest_sha256": base.sha_bytes(source_payloads["package_manifest.json"]),
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
            "natural_terminal_27_of_27": False, "formal_D_payload_present": False,
            "interruption_adjudication": "INT after a long qualified c0 run. The stable 786432-cycle blocked interval exposes a real hang boundary; absent terminal/D is not itself a numeric, config or RTL verdict.",
        },
        "production_rtl_identity": {
            "collection_valid": identity.get("collection_valid"),
            "actual_differs_local_provenance": identity.get("actual_differs_local_provenance"),
            "actual_differs_cloud_authority": identity.get("actual_differs_cloud_authority"),
            "identity_difference_blocks_simulator": False,
            "causal_cone_adjudication": "Actual/local/cloud differences are nonblocking provenance after production compile and simulation; dynamic exact-instance receipts bind this diagnostic result.",
        },
        "observer_adjudication": {
            "group_tag_formula": sa_contract.get("group_tag_formula"), "target_group_tag": "0x3fdf",
            "accepted_complete_beats": beats, "complete_beat_count": len(beats),
            "full_data_distinct": True, "full_data_identical": False,
            "decision": sa_decision.get("decision"), "matching_candidate_ids": sa_decision.get("matching_candidate_ids"),
            "wrong_instance_rows_ignored": sa_decision.get("wrong_instance_rows_ignored"),
            "nonuniform_lane_positive_control": "mixed_lane_same PASS; OR(same) semantics are not overconstrained per lane",
            "claim_boundary": "Exact c0 SA acceptance identity only; it closes replay/equal-value ambiguity but does not prove terminal, D, E gates or a functional fix.",
        },
        "downstream_causal_ledger": {
            "dwrite_event_count": len(dwrite), "dwrite_last": dwrite[-1] if dwrite else None,
            "wrterm_event_count": len(wrterm), "wrterm_last": wrterm[-1] if wrterm else None,
            "datahub_event_count": len(datahub), "datahub_last": datahub[-1] if datahub else None,
            "dskew_event_count": len(dskew), "dskew_last": dskew[-1] if dskew else None,
            "adjudication": "DataHub channel8 accepts the final offered head. Thereafter no new head is offered while MSE4 retains prepared data and source/tag entries but its descriptor queue is empty. The next split belongs at MSE4 address/descriptor production versus write-data preparation, not at SA replay or downstream DataHub ready.",
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": "two complete, exact-instance eight-lane SA beats at 2446438000 and 2446441000 are distinct in all-256-bit identity while sharing group tag 0x3fdf; downstream DWRITE and DataHub continue qualified accepts",
            "FIRST_DIVERGENCE": "after MSE4 descriptor count reaches 18 and drains to zero, prepared write-data count reaches 20 (delta=2) and no further DataHub channel8 head is produced; source/tag entries remain",
            "HANG_ROOT_CAUSE": {
                "status": "DUT_CAUSAL_LEAF_NARROWED_TO_MSE4_ADDRESS_DESCRIPTOR_END_VERSUS_WRITE_DATA_PREPARATION_SKEW_UNRESOLVED",
                "functional_rtl_root_cause_proven": False, "authorized_config_fix": None,
                "closed_observational_equivalents": [
                    "one held SA beat accepted twice", "two distinct equal-value SA beats", "DataHub channel8 refusing the final offered write head",
                ],
                "remaining_observational_equivalents": [
                    "address/index terminal legitimately ends before write-data preparation because descriptor and data units differ",
                    "address/index terminal ends two write units early due to transaction/connect/config occurrence mismatch",
                    "MSE4 descriptor/tag/source join ownership suppresses an otherwise required descriptor",
                ],
            },
        },
        "result_conjunction": {
            "compile": compile_pass, "simulator_started": simulation_started, "c0_slice_finish": False,
            "natural_terminal_27_of_27": False, "formal_D_320_of_320": False, "mismatch_zero_claim": False,
            "E3": False, "E4": False, "E5": False, "performance_claimed": False, "passed": False,
        },
        "round_progress": {
            "compared_to_p36b_closed": [
                "B_CONV_NATIVE_STABLE_ARM_TAG_DISTINCT_DATA_BEAT_OR_REPLAY_UNRESOLVED",
                "held-beat reaccept candidate", "distinct equal-value beat candidate",
            ],
            "first_proven": [
                "two complete accepted SA beats share the p36b ARM tag but carry different 256-bit data",
                "nonuniform lane same-bit input reconstructs the public OR-based group tag correctly",
                "the final offered DataHub channel8 head is accepted before the local writer stops offering heads",
                "the final local ledger has 18 descriptors versus 20 prepared write-data units",
            ],
            "functional_progress": "NONZERO_CAUSAL_NARROWING",
            "remaining_candidates": ["legal descriptor/data unit ratio", "two-unit early address/index terminal", "descriptor/tag/source join suppression"],
            "next_package_discrimination": "source-bind MSE4 address/index terminal production and WR_Data_Channel preparation/output join with exact transaction unit/last/tag counters through the final two-unit skew",
        },
        "blocker_delta": {
            "closed": ["B_CONV_NATIVE_STABLE_ARM_TAG_DISTINCT_DATA_BEAT_OR_REPLAY_UNRESOLVED"],
            "added": {
                "B_CONV_NATIVE_MSE4_DESCRIPTOR_18_VS_PREPARED_20_UNIT_SEMANTICS_UNRESOLVED": "p37b proves real distinct SA data, while the downstream exact ledger ends with two more prepared write-data units than produced descriptors."
            },
            "preserved": [
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN", "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN", "B_CONV_NATIVE4_E3_E4_E5_UNPROVEN",
            ],
        },
        "successor": {
            "required": valid, "fresh_identity": True, "tentative_package_id": "r5_n4_0cc_p38_mse4join",
            "highest_information_scope": "same c0 interval with exact MSE4 address/index terminal versus write-data prepare/output transaction-unit ledger",
            "first_fresh_after_change": False, "prior_first_fresh_pass_receipt": "p36b typed-v2 first-fresh PASS",
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
                "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
            ],
            "evidence": "p37b accepted only exact-instance, binary-known per-lane valid-and-ready events, reconstructed the public OR tag semantics, and closed replay without overclaiming natural/D/E gates.",
            "claim_boundary": "c0 diagnostic causality only; no numeric, RTL-fix, config-fix, natural-terminal, formal-D or performance conclusion",
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
