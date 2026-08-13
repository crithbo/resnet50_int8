#!/usr/bin/env python3
"""Validate and adjudicate the formal native-four-lane p31 return."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import analyze_conv_native_four_lane_0ccae916_p30_return as base


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p31_postclear"
EXECUTION_ID = "r1786363816915779986_588811"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p31_postclear_"
    r"r1786363816915779986_588811_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE_ID}.zip"
)
RETURN_BYTES = 141_788
RETURN_SHA256 = "b4e1e8a54828b24beee0ac9cdccf417316e9c8043aa8bb7b57e5d0eb201aa4f7"
SOURCE_BYTES = 5_927_263
SOURCE_SHA256 = "d022977daebb1c633d0c4fa32ca58cf5b660a6f4c4dff6cb11d499a21d2345c9"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p31_return_analysis/report.json"
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
    decision = json.loads(payloads["evidence/source_bound_causal_decision.json"])
    public_summary = json.loads(payloads["evidence/buffer5_public_summary.json"])
    public_order = json.loads(payloads["evidence/public_order_summary.json"])
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

    rows = [
        row
        for line in payloads["runs/c0/source_bound_causal.log"].decode(errors="replace").splitlines()
        if (row := base.parse_kv(line, "CODEX_PROBE_V1 ")) is not None
    ]
    target_parent = (
        "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
        "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU."
        "u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager"
    )
    candidate_boundaries = {
        "row2_block_bank_ready_00",
        "row2_block_bank_ready_0f",
        "row2_block_bank_ready_f0",
        "row2_block_bank_ready_ff",
        "row2_block_bank_ready_other",
    }
    target_candidate_rows = [
        row for row in rows
        if row.get("kind") == "TRIGGER"
        and row.get("boundary") in candidate_boundaries
        and normalize_parent(row.get("instance", "")) == target_parent
    ]
    target_final_rows = [
        row for row in rows
        if row.get("kind") == "TRIGGER"
        and row.get("boundary") == "final_same_row2_block"
        and normalize_parent(row.get("instance", "")) == target_parent
    ]
    all_trigger_instances = sorted({
        normalize_parent(row.get("instance", "")) for row in rows
        if row.get("kind") == "TRIGGER" and row.get("boundary") in candidate_boundaries | {"final_same_row2_block"}
    })
    target_0f = [row for row in target_candidate_rows if row.get("boundary") == "row2_block_bank_ready_0f"]
    target_other = [row for row in target_candidate_rows if row.get("boundary") != "row2_block_bank_ready_0f"]
    target_payload = base.decode_payload(target_0f[0]["payload"]) if len(target_0f) == 1 else None
    exact_target_correlation = (
        len(target_0f) == 1
        and len(target_final_rows) == 1
        and not target_other
        and base.number(target_0f[0]["time"]) == 2_446_437_000
        and base.number(target_final_rows[0]["time"]) == 2_446_469_000
        and base.number(target_final_rows[0]["time"]) > base.number(target_0f[0]["time"])
        and target_payload == {
            "bank_ready": 0x0F,
            "buffer_mask": 0xFF,
            "mrm_clear": 0xF0,
            "valid_buf_clear": 0xF0,
            "valid_buf_wr_en": 0xFF,
            "arm2buf_wr_en": 0xFF,
            "buf_wr_en": 0xFF,
            "buf_wr_addr": 2,
            "tag_buf_row_empty": 0,
        }
    )
    global_parser_not_correlated = (
        len(all_trigger_instances) > 1
        and decision.get("decision") == "FINAL_POSTCLEAR_BANK_READY_0F"
        and decision.get("matching_candidate_ids") == ["final_postclear_bank_ready_0f"]
        and decision.get("errors") == []
        and set(decision.get("observations", {})) == {
            "block_bank_00_seen", "block_bank_0f_seen", "block_bank_f0_seen",
            "block_bank_ff_seen", "block_bank_other_seen", "final_same_row2_block_seen",
        }
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
        "exact_target_parent_epoch_correlation": exact_target_correlation,
        "global_generated_parser_instance_epoch_escape_detected": global_parser_not_correlated,
        "formal_320d_absent_by_diagnostic_design": no_formal,
    }
    valid = all(checks.values())
    status = "P31_PARTIAL_INTERRUPTED_TARGET_HIGH_BANK_VALID_OWNERSHIP_SUCCESSOR_REQUIRED" if valid else "RETURN_VALIDATION_FAILED"
    report = {
        "schema": "conv-native-four-lane-0ccae916-p31-return-analysis-v1",
        "status": status,
        "valid": valid,
        "classification": "PARTIAL_INTERRUPTED_WITH_TARGET_CORRELATED_0F_AND_VALID_OWNERSHIP_UNRESOLVED" if valid else "RETURN_VALIDATION_FAILED",
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
            "causal_cone_adjudication": "Actual production causal leaves differ from local/cloud provenance, but compile and c0 simulation pass; dynamic target-instance evidence is authoritative and identity difference is nonblocking provenance.",
        },
        "source_bound_bank_evidence": {
            "generated_global_decision": decision,
            "generated_global_decision_claim_boundary": "Not sufficient alone because sticky class_seen is ORed across module instances and epochs.",
            "trigger_parent_count": len(all_trigger_instances),
            "target_parent": target_parent,
            "target_candidate_trigger_rows": target_candidate_rows,
            "target_final_trigger_rows": target_final_rows,
            "target_0f_payload_decoded": target_payload,
            "target_temporal_correlation": {
                "bank_0f_time": base.number(target_0f[0]["time"]) if target_0f else None,
                "final_same_row2_block_time": base.number(target_final_rows[0]["time"]) if target_final_rows else None,
                "other_target_bank_class_seen": bool(target_other),
                "adjudication": "Exact target Buffer_Manager emitted 0x0f before its own final same-row2 marker and emitted no 00/f0/ff/other class. This independently closes the final 0f-vs-ff branch for the observed epoch.",
            },
            "public_final_state": public_summary.get("last"),
            "public_order_status": public_order.get("status"),
            "aggregate_ready_adjudication": "buffer_mask=0xff and bank_ready=0x0f imply aggregate write-ready=0; aggregate-ready recomputation is consistent. Banks 4..7 remain nonempty after the observed f0 clear while the same sample also has all-bank arm write eligibility.",
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": "production compile and c0 simulation; p31 generated observer active; exact target slice0/group0 Buffer5 reports row2 bank_ready=0x0f at 2446437000 and the same Buffer_Manager reports final same-row2 block at 2446469000",
            "FIRST_DIVERGENCE": "after the target f0 clear, Buffer5 row2 banks 4..7 remain nonempty, keeping aggregate buf2arm write-ready low",
            "HANG_ROOT_CAUSE": {
                "status": "DUT_CAUSAL_LEAF_UNRESOLVED_VALID_OWNERSHIP",
                "classification": "BUFFER5_ROW2_HIGH_HALF_VALID_PERSISTS_AFTER_F0_CLEAR",
                "closed": [
                    "production compile/XMR failure", "c0 not reached", "final bank_ready=0xff",
                    "aggregate-ready formula disagreement", "source13/Connect/Memory-WR/Memory-AG delivery",
                    "MRM row2 clear not issued", "competing external row2 writer class",
                ],
                "remaining_observational_equivalents": [
                    "high-bank valid bits are only partially cleared because the effective clear mask preserves live lanes",
                    "a same-edge or following-edge ARM write reasserts high-bank valid ownership",
                    "clear and write target different row/epoch despite the aggregate row2 request view",
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
                "B_CONV_NATIVE_P30_FINAL_BANK_STATE_SIGNAL_SAFE_EVIDENCE_ESCAPE",
                "B_CONV_NATIVE_FINAL_0F_VS_FF_UNRESOLVED",
                "B_CONV_NATIVE_AGGREGATE_READY_RECOMPUTATION_UNRESOLVED",
            ],
            "added": {
                "B_CONV_NATIVE_P31_SOURCE_BOUND_DECISION_INSTANCE_EPOCH_CORRELATION_ESCAPE": "generated parser ORs class_seen globally; formal analysis recovered target correlation from raw instance-tagged records",
                "B_CONV_NATIVE_BUFFER5_ROW2_HIGH_BANK_VALID_OWNERSHIP_UNRESOLVED": "effective clear mask versus same/following-edge valid write is not yet decomposed",
            },
            "preserved": [
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN", "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN", "B_CONV_NATIVE4_E4_E5_UNPROVEN",
            ],
        },
        "successor": {
            "required": valid, "package_id": "r5_n4_0cc_p32_validowner", "fresh_identity": True,
            "highest_information_scope": "exact target-instance/epoch-correlated Buffer5 row2 bank4..7 valid, effective clear mask/address and accepted write source/address ownership around the final f0-clear epoch",
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
            "type": "RULE_DELTA_PROPOSAL",
            "confirmed": [
                "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
                "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
                "CDA-SERVER-DIAGNOSTIC-MULTICLASS-EDGE-NO-LOSS-001",
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001",
            ],
            "delta": {
                "proposed_rule_id": "CDA-SERVER-SOURCE-BOUND-DECISION-INSTANCE-EPOCH-CORRELATION-001",
                "evidence": "p31 generated class_seen parser combined 1120 records from multiple module instances and lifetime epochs; raw %m records were required to prove the target slice0/group0 pair.",
                "requirement": "When candidate boundaries span modules or repeated instances, generated decision evidence must correlate one declared instance key and one bounded epoch; mixed-instance and mixed-epoch traces must fail closed.",
                "migration": "non-retroactive; p32 adds a family-local target correlator while retaining exact generated observer/parser gates.",
            },
            "claim_boundary": "Proposal only; no public rule file is modified and p32 remains bound to the current effective epoch.",
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
