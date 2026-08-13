#!/usr/bin/env python3
"""Validate p33b and recover its exact-target live owner ledger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import analyze_conv_native_four_lane_0ccae916_p32b_return as prior


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p33b_wrowner"
EXECUTION_ID = "r1786374098477088271_679932"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p33b_wrowner_"
    r"r1786374098477088271_679932_return.zip"
)
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PACKAGE_ID}.zip"
RETURN_BYTES = 143_523
RETURN_SHA256 = "0d3cc837c58e1cd0eba8afdc6a03a1dd19809d9ece5493a36e6d95d6c60f022e"
SOURCE_BYTES = 5_931_155
SOURCE_SHA256 = "62b225be794774e1cd8c9a4f8a8d26e2cf5ecb1795ed44fe3d1ed748d81077df"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p33b_return_analysis/report.json"
FIRST_FRESH = ROOT / "outputs/conv_native_four_lane_0ccae916_p31_postclear/first_fresh_extra_audit/validation.json"
FIRST_FRESH_SHA256 = "48c58b614af0ba1fe311d454e5229d4f000a5b944d711e52a8c43ecc85ab0ec1"
TARGET_PARENT = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
    "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU."
    "u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager"
)
WINDOW = "row2_clear_window_write_owner"
FINAL = "final_same_row2_block"
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


def exact_target_live_rows(raw: bytes) -> dict[str, Any]:
    target: list[dict[str, str]] = []
    malformed: list[str] = []
    raw_count = 0
    for line_number, line in enumerate(raw.decode(errors="replace").splitlines(), 1):
        row, error = prior_row(line)
        if error:
            malformed.append(f"line {line_number}: {error}")
            continue
        if row is None:
            continue
        raw_count += 1
        if prior.normalize_parent(row["instance"]) == TARGET_PARENT:
            target.append(row)
    clears = [row for row in target if row.get("boundary") == WINDOW and row.get("kind") == "TRIGGER" and hexint(row, "mask") & 1]
    finals = [row for row in target if row.get("boundary") == FINAL and row.get("kind") == "TRIGGER"]
    clear_time = number(clears[0], "time") if len(clears) == 1 else -1
    final_time = number(finals[0], "time") if len(finals) == 1 else -1
    live = [
        row for row in target
        if row.get("boundary") == WINDOW
        and row.get("kind") == "EVENT"
        and clear_time < number(row, "time") < final_time
    ]
    live.sort(key=lambda row: (number(row, "time"), number(row, "seq")))
    owners = {
        "ARM": [row for row in live if hexint(row, "mask") & (1 << 1)],
        "MRM": [row for row in live if hexint(row, "mask") & (1 << 2)],
        "NRM": [row for row in live if hexint(row, "mask") & (1 << 3)],
    }
    bitmap = sum(1 << index for index, owner in enumerate(("ARM", "MRM", "NRM")) if owners[owner])
    exact = (
        not malformed
        and len(clears) == 1
        and len(finals) == 1
        and clear_time == 2_446_437_000
        and final_time == 2_446_469_000
        and [number(row, "time") for row in owners["ARM"]] == [2_446_438_000, 2_446_448_000]
        and not owners["MRM"]
        and not owners["NRM"]
        and bitmap == 1
    )
    return {
        "exact": exact,
        "raw_record_count": raw_count,
        "target_record_count": len(target),
        "malformed": malformed,
        "target_clear_time": None if clear_time < 0 else clear_time,
        "target_final_time": None if final_time < 0 else final_time,
        "live_rows": live,
        "owner_rows": owners,
        "owner_bitmap": bitmap,
        "decision": "TARGET_INTERVAL_ARM_ACCEPTED_WRITE_ONLY" if exact else "EVIDENCE_INCOMPLETE",
        "claim_boundary": "Live exact-target EVENT rows only; no final-block RING_POST dependency.",
    }


def prior_row(line: str) -> tuple[dict[str, str] | None, str | None]:
    if not line.startswith("CODEX_PROBE_V1 "):
        return None, None
    fields: dict[str, str] = {}
    for token in line.split()[1:]:
        if "=" not in token:
            return None, "malformed logger token"
        key, value = token.split("=", 1)
        if not key or not value:
            return None, "empty logger token"
        fields[key] = value
    if not {"kind", "boundary", "instance"}.issubset(fields):
        return None, "logger record lacks identity"
    return fields, None


def number(row: dict[str, str], key: str) -> int:
    try:
        return int(row[key], 0)
    except (KeyError, ValueError):
        return -1


def hexint(row: dict[str, str], key: str) -> int:
    try:
        return int(row[key], 16)
    except (KeyError, ValueError):
        return -1


def main() -> int:
    for path in (RETURN_ZIP, SOURCE_ZIP, FIRST_FRESH):
        if not path.is_file():
            raise AnalysisError(f"required identity is absent: {path}")
    return_root, records, payloads, return_errors = prior.base.safe_zip(RETURN_ZIP)
    source_root, source_records, source_payloads, source_errors = prior.base.safe_zip(SOURCE_ZIP)
    core = json.loads(payloads["RETURN_CORE_MANIFEST.json"])
    core_status = json.loads(payloads["return_core/RETURN_CORE_STATUS.json"])
    sim_exit = json.loads(payloads["return_core/SIM_EXIT_RECEIPT.json"])
    plugins = json.loads(payloads["return_core/RETURN_PLUGIN_STATUS.json"])
    gate = json.loads(payloads["evidence/SERVER_RESULT_GATE.json"])
    identity = json.loads(payloads["evidence/production_rtl_identity.json"])
    package_status = json.loads(payloads["evidence/package_local_preflight_status.json"])
    target_decision = json.loads(payloads["evidence/target_epoch_write_owner_decision.json"])
    source_decision = json.loads(payloads["evidence/source_bound_causal_decision.json"])
    source_manifest = json.loads(source_payloads["package_manifest.json"])
    request = json.loads(source_payloads["contracts/server_post_sim_return_request.json"])
    receipts = {row["path"]: {"bytes": row["bytes"], "sha256": row["sha256"]} for row in core["core_entry_receipts"]}
    plugin_ids = [row["plugin_id"] for row in request["plugins"]]
    expected = {
        "RETURN_CORE_MANIFEST.json", "return_core/RETURN_CORE_STATUS.json",
        "return_core/RETURN_PLUGIN_STATUS.json", "return_core/SIM_EXIT_RECEIPT.json", *receipts,
    }
    for plugin_id in plugin_ids:
        expected |= {
            f"return_core/plugins/{plugin_id}.status.json",
            f"return_core/plugins/{plugin_id}.stdout.log",
            f"return_core/plugins/{plugin_id}.stderr.log",
        }
    source_files = {
        path: {"size_bytes": row["bytes"], "sha256": row["sha256"]}
        for path, row in source_records.items() if path != "package_manifest.json"
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
    required_failures = core.get("required_plugin_failures")
    plugin_by_id = {row["plugin_id"]: row for row in plugins}
    parser_failure_expected = (
        required_failures == ["target_epoch_write_owner_parser"]
        and plugin_by_id["target_epoch_write_owner_parser"]["pass"] is False
        and plugin_by_id["target_epoch_write_owner_parser"]["exit_code"] == 1
        and target_decision.get("decision") == "EVIDENCE_INCOMPLETE"
        and "target clear window lacks bounded RING_POST records" in target_decision.get("errors", [])
    )
    other_required_pass = all(
        row["pass"] and row["exit_code"] == 0
        for row in plugins if row["plugin_id"] != "target_epoch_write_owner_parser" and row.get("required_for_adjudication")
    )
    live = exact_target_live_rows(payloads["runs/c0/source_bound_causal.log"])
    first = json.loads(FIRST_FRESH.read_text(encoding="utf-8"))
    no_formal = source_manifest.get("formal_readback_count") == 0 and gate["execution_gate"].get("formal_D_claimed") is False and not any(path.startswith("formal_D/") for path in records)
    checks = {
        "transport_identity_exact": RETURN_ZIP.stat().st_size == RETURN_BYTES and prior.base.sha_file(RETURN_ZIP) == RETURN_SHA256,
        "source_identity_exact": SOURCE_ZIP.stat().st_size == SOURCE_BYTES and prior.base.sha_file(SOURCE_ZIP) == SOURCE_SHA256,
        "return_crc_single_root_path_safe": not return_errors and return_root == f"{PACKAGE_ID}_return",
        "source_crc_single_root_path_safe": not source_errors and source_root == PACKAGE_ID,
        "return_exact_set": set(records) == expected,
        "return_core_per_file_receipts_exact": not receipt_mismatches,
        "source_manifest_files_exact": source_manifest["files"] == source_files,
        "returned_source_manifest_exact": payloads["source_package/package_manifest.json"] == source_payloads["package_manifest.json"],
        "execution_and_unique_basename_exact": core["execution_id"] == EXECUTION_ID and core["return_basename"] == RETURN_ZIP.name and sim_exit["execution_id"] == EXECUTION_ID,
        "preflight_compile_and_simulation_started": compile_pass and simulation_started,
        "external_int_partial_return_exact": interrupted and core_status.get("disposition") == "PARTIAL_EXECUTION_RETURN",
        "post_sim_core_preserved_required_plugin_failure": core_status.get("return_publication_independent_of_plugin_success") is True and parser_failure_expected and other_required_pass and not plugin_mismatches,
        "generated_global_decision_corroborates_arm_only": source_decision.get("decision") == "GLOBAL_CLEAR_WINDOW_ARM_MRM_ACCEPT" or source_decision.get("decision") == "GLOBAL_CLEAR_WINDOW_ARM_ACCEPT",
        "exact_target_live_owner_ledger_arm_only": live["exact"],
        "formal_320d_absent_by_diagnostic_design": no_formal,
        "p31_first_fresh_receipt_reuse": prior.base.sha_file(FIRST_FRESH) == FIRST_FRESH_SHA256 and first.get("pass") is True and first.get("upload_authorized") is True,
    }
    valid = all(checks.values())
    status = "P33B_PARTIAL_INTERRUPTED_TARGET_ARM_REWRITE_PROVEN_SUCCESSOR_REQUIRED" if valid else "RETURN_VALIDATION_FAILED"
    report = {
        "schema": "conv-native-four-lane-0ccae916-p33b-return-analysis-v1",
        "status": status, "valid": valid,
        "classification": "PARTIAL_INTERRUPTED_TARGET_POSTCLEAR_ARM_REWRITE_PROVEN_TOKEN_IDENTITY_UNRESOLVED" if valid else "RETURN_VALIDATION_FAILED",
        "return_identity": {"path": str(RETURN_ZIP), "bytes": RETURN_ZIP.stat().st_size, "sha256": prior.base.sha_file(RETURN_ZIP), "execution_id": EXECUTION_ID, "adjacent_sidecar_present": Path(str(RETURN_ZIP) + ".sha256").is_file(), "transport_policy": "USER_ATTESTED_EXTERNAL_SIDECAR_WAIVER"},
        "source_identity": {"path": SOURCE_ZIP.relative_to(ROOT).as_posix(), "bytes": SOURCE_ZIP.stat().st_size, "sha256": prior.base.sha_file(SOURCE_ZIP), "source_manifest_sha256": prior.base.sha_bytes(source_payloads["package_manifest.json"])},
        "internal_receipt": {"return_root": return_root, "return_file_count": len(records), "source_root": source_root, "source_file_count": len(source_records), "return_errors": return_errors, "source_errors": source_errors, "missing": sorted(expected - set(records)), "extra": sorted(set(records) - expected), "core_receipt_mismatches": receipt_mismatches, "plugin_status_mismatches": plugin_mismatches, "checks": checks},
        "execution": {"compile_exit_status": compile_status, "run_exit_status": run_status, "signal_status": signal_status, "sim_exit_code": sim_exit.get("sim_exit_code"), "compile_succeeded": compile_pass, "dut_simulation_started": simulation_started, "natural_terminal": False, "c0_slice_finish": False, "formal_D_payload_present": False, "post_sim_core_disposition": core.get("disposition"), "interruption_adjudication": "INT after qualified c0 progress; missing terminal/D is not a DUT, config, RTL or numeric failure."},
        "production_rtl_identity": {"collection_valid": identity.get("collection_valid"), "actual_differs_cloud_authority": identity.get("actual_differs_cloud_authority"), "identity_difference_blocks_simulator": False, "buffer_leaf": identity.get("leaves", {}).get("Buffer.sv"), "array_request_manager_leaf": identity.get("leaves", {}).get("Array_Request_Manager.sv"), "causal_cone_adjudication": "Production compile and c0 simulation passed; actual/cloud differences are nonblocking provenance."},
        "exact_target_owner_evidence": {"package_local_target_parser": target_decision, "post_hoc_live_record_adjudication": live, "parser_escape": "The required package-local parser depended exclusively on SystemVerilog final-block RING_POST records. External INT preserved live EVENT rows through the independent core return, but the parser ignored them."},
        "failure_localization": {
            "LAST_PROVEN_GOOD": "exact target Buffer5 clear at 2446437000 followed by ARM-only accepted row2 writes at 2446438000 and 2446448000 before the final same-row2 block",
            "FIRST_DIVERGENCE": "Buffer5 is repopulated by ARM after clear; p33b does not distinguish two legitimate advancing ARM tokens from held-token replay or address/counter wrap",
            "HANG_ROOT_CAUSE": {"status": "DUT_CAUSAL_LEAF_NARROWED_TO_POSTCLEAR_ARM_REWRITE_TOKEN_IDENTITY_UNRESOLVED", "closed": ["clear not observed", "MRM accepted rewrite", "NRM accepted rewrite", "no intervening accepted write", "wrong target instance/epoch", "production compile/XMR failure"], "remaining_observational_equivalents": ["two legitimate consecutive ARM row2 tokens", "same ARM token accepted more than once", "ARM address/counter reset or wrap returns to row2"], "functional_rtl_root_cause_proven": False, "authorized_config_fix": None},
        },
        "result_conjunction": {"compile": compile_pass, "simulator_started": simulation_started, "c0_slice_finish": False, "natural_terminal_27_of_27": False, "formal_D_320_of_320": False, "mismatch_zero_claim": False, "E3": False, "E4": False, "E5": False, "performance_claimed": False, "passed": False},
        "blocker_delta": {"closed": ["B_CONV_NATIVE_CLEAR_TO_POST_ACCEPTED_WRITE_OWNER_UNRESOLVED", "B_CONV_NATIVE_EFFECTIVE_CLEAR_MASK_APPLICATION_UNOBSERVED", "B_CONV_NATIVE_POSTCLEAR_MRM_OR_NRM_REWRITE"], "added": {"B_CONV_NATIVE_POSTCLEAR_ARM_TOKEN_ADVANCE_OR_REPLAY_UNRESOLVED": "Two exact-target ARM row2 accepts are proven, but their token/counter identity is not observed."}, "preserved": ["B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN", "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN", "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN", "B_CONV_NATIVE4_E4_E5_UNPROVEN"]},
        "successor": {"required": valid, "package_id": "r5_n4_0cc_p34_armtoken", "fresh_identity": True, "highest_information_scope": "exact-target live Buffer clear/ARM accept anchors plus same-parent Array_Request_Manager accepted-row2 token/counter/reset/last/same payloads", "first_fresh_epoch": "20260810-first-fresh-extra-audit-v1", "first_fresh_after_change": False, "prior_first_fresh_pass_receipt": {"path": FIRST_FRESH.relative_to(ROOT).as_posix(), "sha256": FIRST_FRESH_SHA256}, "frozen": "87 payload members, numeric/W3/workload/config/mapping/bitstream/execplan/SCA/golden/functional RTL", "server_action": False},
        "current_rule_receipts": {path: {"bytes": (ROOT / path).stat().st_size, "sha256": prior.base.sha_file(ROOT / path)} for path in RULE_PATHS},
        "rule_feedback": {"type": "RULE_DELTA_PROPOSAL", "proposal_id": "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001", "evidence": "p33b external INT omitted SystemVerilog final-block RING_POST records while the independent core return preserved decisive exact-target live EVENT rows.", "proposed_requirement": "A required diagnostic parser used for INT/TERM partial returns must consume qualified live records or a signal-safe persisted equivalent; final-block ring dumps must not be its sole causal input.", "public_rule_modified": False},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise AnalysisError(f"refusing to overwrite formal analysis: {OUTPUT}")
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": status, "valid": valid, "output": str(OUTPUT)}, ensure_ascii=False, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
