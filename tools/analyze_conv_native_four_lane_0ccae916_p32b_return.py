#!/usr/bin/env python3
"""Validate and adjudicate the formal native-four-lane p32b return."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import analyze_conv_native_four_lane_0ccae916_p30_return as base


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p32b_validowner"
EXECUTION_ID = "r1786370009009142729_655330"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p32b_validowner_"
    r"r1786370009009142729_655330_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE_ID}.zip"
)
RETURN_BYTES = 148_722
RETURN_SHA256 = "6bfd9e6eda9b0ae6ceb0ebbc066f1035b0bc791766b7ea851dedd168f5e9be7e"
SOURCE_BYTES = 5_934_940
SOURCE_SHA256 = "fc21dc0fccb4fbf612e55418964f78ba482678ec232a4bb438b50f97e03a2d47"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p32b_return_analysis/report.json"
FIRST_FRESH = ROOT / "outputs/conv_native_four_lane_0ccae916_p31_postclear/first_fresh_extra_audit/validation.json"
FIRST_FRESH_SHA256 = "48c58b614af0ba1fe311d454e5229d4f000a5b944d711e52a8c43ecc85ab0ec1"
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
    "contracts/server_first_fresh_extra_audit_dispatch_v1.json",
    "tools/validate_server_first_fresh_extra_audit.py",
    "tools/generate_server_source_bound_observer.py",
    "tools/server_post_sim_return.py",
)


class AnalysisError(RuntimeError):
    pass


def normalize_parent(instance: str) -> str:
    for marker in (".u_Buffer.", ".u_Array_Request_Manager."):
        if marker in instance:
            return instance.split(marker, 1)[0]
    return instance


def main() -> int:
    for path in (RETURN_ZIP, SOURCE_ZIP, FIRST_FRESH):
        if not path.is_file():
            raise AnalysisError(f"required identity is absent: {path}")
    return_root, records, payloads, return_errors = base.safe_zip(RETURN_ZIP)
    source_root, source_records, source_payloads, source_errors = base.safe_zip(SOURCE_ZIP)

    core = json.loads(payloads["RETURN_CORE_MANIFEST.json"])
    core_status = json.loads(payloads["return_core/RETURN_CORE_STATUS.json"])
    sim_exit = json.loads(payloads["return_core/SIM_EXIT_RECEIPT.json"])
    plugins = json.loads(payloads["return_core/RETURN_PLUGIN_STATUS.json"])
    gate = json.loads(payloads["evidence/SERVER_RESULT_GATE.json"])
    identity = json.loads(payloads["evidence/production_rtl_identity.json"])
    package_status = json.loads(payloads["evidence/package_local_preflight_status.json"])
    package_preflight = json.loads(payloads["evidence/package_preflight.json"])
    install_preflight = json.loads(payloads["evidence/install_preflight.json"])
    observer_preflight = json.loads(payloads["evidence/observer_precompile.json"])
    root_gate = json.loads(payloads["evidence/ndp_root_toplevel_gate.json"])
    generated_decision = json.loads(payloads["evidence/source_bound_causal_decision.json"])
    target_decision = json.loads(payloads["evidence/target_epoch_valid_owner_decision.json"])
    public_summary = json.loads(payloads["evidence/buffer5_public_summary.json"])
    public_order = json.loads(payloads["evidence/public_order_summary.json"])
    triggered = json.loads(payloads["evidence/triggered_causal_summary.json"])
    feature = json.loads(payloads["evidence/feature_binding/c0.json"])
    source_manifest = json.loads(source_payloads["package_manifest.json"])
    request = json.loads(source_payloads["contracts/server_post_sim_return_request.json"])
    generation = json.loads(payloads["source_package/source_bound_generation_report.json"])
    binding = json.loads(payloads["source_package/source_bound_probe_binding.json"])

    receipts = {
        row["path"]: {"bytes": row["bytes"], "sha256": row["sha256"]}
        for row in core["core_entry_receipts"]
    }
    plugin_ids = [row["plugin_id"] for row in request["plugins"]]
    expected = {
        "RETURN_CORE_MANIFEST.json",
        "return_core/RETURN_CORE_STATUS.json",
        "return_core/RETURN_PLUGIN_STATUS.json",
        "return_core/SIM_EXIT_RECEIPT.json",
        *receipts,
    }
    for plugin_id in plugin_ids:
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
    for row in plugins:
        member = json.loads(payloads[f"return_core/plugins/{row['plugin_id']}.status.json"])
        if member != row:
            plugin_mismatches[row["plugin_id"]] = {"aggregate": row, "member": member}
    source_files = {
        path: {"size_bytes": row["bytes"], "sha256": row["sha256"]}
        for path, row in source_records.items()
        if path != "package_manifest.json"
    }

    compile_status = int(payloads["evidence/compile_exit_status.txt"].decode().strip())
    run_status = int(payloads["evidence/run_exit_status.txt"].decode().strip())
    signal_status = payloads["evidence/signal_status.txt"].decode().strip()
    compile_log = payloads["runs/compile/compile_driver.log"].decode(errors="replace")
    simulator_argv = payloads["runs/c0/simulator_argv.txt"].decode(errors="replace")
    compile_pass = (
        compile_status == 0
        and "Verdi KDB elaboration finished with 0 error(s)" in compile_log
        and "Compilation completed!" in compile_log
        and "Error-[XMRE]" not in compile_log
    )
    simulation_started = (
        package_status.get("dut_simulation_started") is True
        and sim_exit.get("sim_started") is True
        and "+CODEX_CAUSAL_OBSERVER" in simulator_argv
        and feature.get("valid") is True
    )
    interrupted = (
        signal_status == "INT"
        and sim_exit.get("signal") == "INT"
        and sim_exit.get("sim_exit_code") == 130
        and core.get("disposition") == "PARTIAL_EXECUTION_RETURN"
        and core_status.get("disposition") == "PARTIAL_EXECUTION_RETURN"
    )
    plugins_pass = (
        [row["plugin_id"] for row in plugins] == plugin_ids
        and all(row["pass"] and row["exit_code"] == 0 and not row["timed_out"] for row in plugins)
        and not plugin_mismatches
        and not core.get("required_plugin_failures")
    )
    generated_exact = (
        payloads["source_package/source_bound_generation_report.json"]
        == source_payloads["diagnostics/source_bound_generation_report.json"]
        and payloads["source_package/source_bound_probe_binding.json"]
        == source_payloads["diagnostics/source_bound_probe_binding.json"]
        and generation.get("pass") is True
        and not generation.get("errors")
        and binding.get("private_hierarchical_xmr_generated") is False
    )
    first_fresh = json.loads(FIRST_FRESH.read_text(encoding="utf-8"))
    first_fresh_pass = (
        base.sha_file(FIRST_FRESH) == FIRST_FRESH_SHA256
        and first_fresh.get("pass") is True
        and first_fresh.get("upload_authorized") is True
    )
    no_formal = (
        source_manifest.get("formal_readback_count") == 0
        and gate["execution_gate"].get("formal_D_claimed") is False
        and not any(path.startswith("formal_D/") for path in records)
    )

    target_parent = (
        "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
        "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU."
        "u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager"
    )
    target_rows = target_decision.get("target_trigger_rows", [])
    clear_rows = [row for row in target_rows if row.get("boundary") == "row2_clear_f0_at_0f"]
    post_rows = [row for row in target_rows if row.get("boundary") == "row2_postclear_bank_0f_no_write_accept"]
    final_rows = [row for row in target_rows if row.get("boundary") == "final_same_row2_block"]
    exact_target_epoch = (
        target_decision.get("decision") == "TARGET_POSTCLEAR_0F_NO_WRITE_ACCEPT"
        and target_decision.get("matching_candidate_ids") == ["postclear_0f_no_write_accept"]
        and target_decision.get("target_parent") == target_parent
        and target_decision.get("errors") == []
        and target_decision.get("missing_enabled_boundaries") == []
        and target_decision.get("out_of_epoch_target_state_rows") == []
        and len(clear_rows) == len(post_rows) == len(final_rows) == 1
        and clear_rows[0]["payload"] == "3fffc3c3c100003fffffe4f0"
        and post_rows[0]["payload"] == "3ffc00000100003fffffe4f0"
        and base.number(clear_rows[0]["time"]) == 2_446_437_000
        and base.number(post_rows[0]["time"]) == 2_446_468_000
        and base.number(final_rows[0]["time"]) == 2_446_469_000
    )
    generated_decision_pass = (
        generated_decision.get("decision") == "ROW2_POSTCLEAR_BANK_0F_NO_WRITE_ACCEPT"
        and generated_decision.get("matching_candidate_ids") == ["row2_postclear_bank_0f_no_write_accept"]
        and generated_decision.get("errors") == []
        and generated_decision.get("missing_enabled_boundaries") == []
    )
    # The boundary predicate only proves ready=0 at the post-state sample.  It
    # deliberately does not claim that no accepted write occurred in the 31 ns
    # clear-to-post interval; that temporal gap is the next diagnostic target.
    sampled_no_write_only = exact_target_epoch and post_rows[0]["payload"] == "3ffc00000100003fffffe4f0"

    checks = {
        "transport_identity_exact": RETURN_ZIP.stat().st_size == RETURN_BYTES and base.sha_file(RETURN_ZIP) == RETURN_SHA256,
        "source_identity_exact": SOURCE_ZIP.stat().st_size == SOURCE_BYTES and base.sha_file(SOURCE_ZIP) == SOURCE_SHA256,
        "return_crc_single_root_path_safe": not return_errors and return_root == f"{PACKAGE_ID}_return",
        "source_crc_single_root_path_safe": not source_errors and source_root == PACKAGE_ID,
        "return_exact_set": set(records) == expected,
        "return_core_per_file_receipts_exact": not receipt_mismatches,
        "source_manifest_files_exact": source_manifest["files"] == source_files,
        "returned_source_manifest_exact": payloads["source_package/package_manifest.json"] == source_payloads["package_manifest.json"],
        "execution_and_unique_basename_exact": core["execution_id"] == EXECUTION_ID and core["return_basename"] == RETURN_ZIP.name and sim_exit["execution_id"] == EXECUTION_ID,
        "install_root_package_observer_preflights_pass": package_preflight["valid"] and install_preflight["valid"] and observer_preflight["valid"] and root_gate["valid"] and root_gate["ndp_root_toplevel_unchanged"],
        "generated_source_bound_identity_exact": generated_exact,
        "p31_first_fresh_extra_audit_receipt_pass": first_fresh_pass,
        "production_compile_pass": compile_pass,
        "simulation_started_then_external_int": simulation_started and interrupted,
        "post_sim_core_and_plugins_pass": core_status["return_publication_independent_of_plugin_success"] and plugins_pass,
        "generated_decision_pass": generated_decision_pass,
        "exact_target_parent_epoch_correlation": exact_target_epoch,
        "sampled_post_state_no_write_accept_only": sampled_no_write_only,
        "formal_320d_absent_by_diagnostic_design": no_formal,
    }
    valid = all(checks.values())
    status = "P32B_PARTIAL_INTERRUPTED_CLEAR_TO_POST_WRITE_OWNER_SUCCESSOR_REQUIRED" if valid else "RETURN_VALIDATION_FAILED"
    report = {
        "schema": "conv-native-four-lane-0ccae916-p32b-return-analysis-v1",
        "status": status,
        "valid": valid,
        "classification": "PARTIAL_INTERRUPTED_TARGET_CORRELATED_POSTCLEAR_0F_SAMPLE_WITH_INTERVAL_OWNER_UNRESOLVED" if valid else "RETURN_VALIDATION_FAILED",
        "return_identity": {
            "path": str(RETURN_ZIP), "bytes": RETURN_ZIP.stat().st_size,
            "sha256": base.sha_file(RETURN_ZIP), "execution_id": EXECUTION_ID,
            "adjacent_sidecar_present": Path(str(RETURN_ZIP) + ".sha256").is_file(),
            "transport_policy": "USER_ATTESTED_EXTERNAL_SIDECAR_WAIVER",
        },
        "source_identity": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(), "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": base.sha_file(SOURCE_ZIP),
            "source_manifest_sha256": base.sha_bytes(source_payloads["package_manifest.json"]),
        },
        "internal_receipt": {
            "return_root": return_root, "return_file_count": len(records),
            "source_root": source_root, "source_file_count": len(source_records),
            "return_errors": return_errors, "source_errors": source_errors,
            "missing": sorted(expected - set(records)), "extra": sorted(set(records) - expected),
            "core_receipt_mismatches": receipt_mismatches,
            "plugin_status_mismatches": plugin_mismatches, "checks": checks,
        },
        "execution": {
            "compile_exit_status": compile_status, "run_exit_status": run_status,
            "signal_status": signal_status, "sim_exit_code": sim_exit["sim_exit_code"],
            "compile_succeeded": compile_pass, "dut_simulation_started": simulation_started,
            "natural_terminal": False, "c0_slice_finish": False,
            "formal_D_payload_present": False, "post_sim_core_disposition": core["disposition"],
            "all_plugins_pass": plugins_pass,
            "interruption_adjudication": "INT after qualified c0 progress; absent terminal/D is not a DUT, config, RTL or numeric failure.",
        },
        "production_rtl_identity": {
            "collection_valid": identity.get("collection_valid"),
            "actual_differs_cloud_authority": identity.get("actual_differs_cloud_authority"),
            "identity_difference_blocks_simulator": False,
            "buffer_leaf": identity.get("leaves", {}).get("Buffer.sv"),
            "array_request_manager_leaf": identity.get("leaves", {}).get("Array_Request_Manager.sv"),
            "causal_cone_adjudication": "Production compile and c0 simulation passed; actual/cloud identity differences remain nonblocking provenance and target-instance dynamic evidence is authoritative.",
        },
        "source_bound_valid_owner_evidence": {
            "generated_decision": generated_decision,
            "target_epoch_decision": target_decision,
            "clear_payload_decoded": {
                "bank_ready": "0x0f", "buffer_mask": "0xff", "mrm_clear": "0xf0",
                "valid_clear": "0xf0", "mrm_req_valid": "0xf0", "mrm_rw": 0,
                "mrm_addr": 2, "mrm_wvalid": 0, "mrm_wr_en": "0x00",
                "nrm_wr_en": "0x00", "arm_wr_en": "0xff", "buf_wr_en": "0xff",
                "valid_wr_en": "0xff", "buf_wr_addr": 2, "buf_wreq_ready": 0,
                "arm_req_addr": 2, "arm_last": 0, "arm_last_idx": 15,
                "tag_row_empty": 0,
            },
            "post_payload_decoded": {
                "bank_ready": "0x0f", "buffer_mask": "0xff", "mrm_clear": "0x00",
                "valid_clear": "0x00", "mrm_req_valid": "0x00", "mrm_rw": 0,
                "mrm_addr": 0, "mrm_wvalid": 0, "mrm_wr_en": "0x00",
                "nrm_wr_en": "0x00", "arm_wr_en": "0xff", "buf_wr_en": "0xff",
                "valid_wr_en": "0xff", "buf_wr_addr": 2, "buf_wreq_ready": 0,
                "arm_req_addr": 2, "arm_last": 0, "arm_last_idx": 15,
                "tag_row_empty": 0,
            },
            "temporal_claim_boundary": "The p32b no_write_accept name is sample-local: buf_wreq_ready=0 at 2446468000. It does not prove absence of an accepted ARM/MRM/NRM write during 2446437000 < t < 2446468000.",
            "public_final_state": public_summary.get("last"),
            "public_order_status": public_order.get("status"),
            "triggered_status": triggered.get("status"),
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": "compile and c0 simulation; exact target Buffer5 emits f0 clear at row2/bank_ready=0x0f, then target post-state remains 0x0f and final same-row2 block follows",
            "FIRST_DIVERGENCE": "Buffer5 high banks remain nonempty at the post-clear sample; p32b does not observe accepted write ownership over the intervening 31 ns window",
            "HANG_ROOT_CAUSE": {
                "status": "DUT_CAUSAL_LEAF_UNRESOLVED_CLEAR_MASK_OR_INTERVENING_WRITE",
                "closed": [
                    "production compile/XMR failure", "c0 not reached", "wrong target instance/epoch",
                    "final bank_ready=0xff", "aggregate-ready formula disagreement",
                    "MRM f0 clear not issued", "accepted write at the post-state sample",
                ],
                "remaining_observational_equivalents": [
                    "ARM accepted a row2 write between the clear and post samples",
                    "MRM accepted a row2 write between the clear and post samples",
                    "NRM accepted a row2 write between the clear and post samples",
                    "no intervening accepted write; effective per-byte clear mask/application preserved high-bank valid ownership",
                ],
                "functional_rtl_root_cause_proven": False,
                "authorized_config_fix": None,
            },
        },
        "result_conjunction": {
            "compile": compile_pass, "simulator_started": simulation_started,
            "c0_slice_finish": False, "natural_terminal_27_of_27": False,
            "formal_D_320_of_320": False, "mismatch_zero_claim": False,
            "E3": False, "E4": False, "E5": False,
            "performance_claimed": False, "passed": False,
        },
        "blocker_delta": {
            "closed": [
                "B_CONV_NATIVE_P31_TARGET_EPOCH_CORRELATION_ESCAPE",
                "B_CONV_NATIVE_POST_STATE_0F_VS_OTHER_UNRESOLVED",
                "B_CONV_NATIVE_POST_SAMPLE_WRITE_ACCEPT_UNRESOLVED",
            ],
            "added": {
                "B_CONV_NATIVE_CLEAR_TO_POST_ACCEPTED_WRITE_OWNER_UNRESOLVED": "p32b proves no write accept only at its post-state sample, not over the clear-to-post interval",
                "B_CONV_NATIVE_EFFECTIVE_CLEAR_MASK_APPLICATION_UNOBSERVED": "if the interval has no accepted write, per-byte effective clear mask/application remains the final alternative",
            },
            "preserved": [
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN", "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN", "B_CONV_NATIVE4_E4_E5_UNPROVEN",
            ],
        },
        "successor": {
            "required": valid, "package_id": "r5_n4_0cc_p33_wrowner", "fresh_identity": True,
            "highest_information_scope": "exact target/epoch clear-to-post interval with separately edge-qualified ARM, MRM and NRM row2 accepted-write owner events plus unchanged clear/post/final anchors",
            "first_fresh_epoch": "20260810-first-fresh-extra-audit-v1",
            "first_fresh_after_change": False,
            "prior_first_fresh_pass_receipt": {
                "path": FIRST_FRESH.relative_to(ROOT).as_posix(), "sha256": FIRST_FRESH_SHA256,
            },
            "frozen": "87 payload members, numeric/W3/workload/config/mapping/bitstream/execplan/SCA/golden/functional RTL",
            "server_action": False,
        },
        "current_rule_receipts": {
            path: {"bytes": (ROOT / path).stat().st_size, "sha256": base.sha_file(ROOT / path)}
            for path in RULE_PATHS
        },
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
                "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
                "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
                "CDA-SERVER-DIAGNOSTIC-MULTICLASS-EDGE-NO-LOSS-001",
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001",
            ],
            "claim_boundary": "No public rule file is modified. The successor tightens the family-local temporal owner predicate without changing frozen functional assets.",
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise AnalysisError(f"refusing to overwrite formal analysis: {OUTPUT}")
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": status, "valid": valid, "output": str(OUTPUT)}, ensure_ascii=False, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
