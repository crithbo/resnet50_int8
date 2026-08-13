#!/usr/bin/env python3
"""Validate and adjudicate the formal native-four-lane p23 return."""

from __future__ import annotations

import collections
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

import analyze_conv_native_four_lane_0ccae916_p18_return as common


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p23_epochflow"
EXECUTION_ID = "r1786189179254670581_4095589"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p23_epochflow_"
    r"r1786189179254670581_4095589_return.zip"
)
SOURCE_ZIP = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE_ID}.zip"
)
RETURN_BYTES = 2_161_834
RETURN_SHA256 = "2287d88e98c3affbf155e010a364cec7ca9985a9dc6deba534f2591ff756d6be"
SOURCE_BYTES = 5_878_970
SOURCE_SHA256 = "f70f9a7643012a013736df3026057ca981f19d543c572064d3cd69edaa46a788"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p23_return_analysis/report.json"
OBSERVER = "tb_probe/native_return_observer.svh"
EXPECTED_OBSERVER_SHA256 = "00ed2bd1295ac51bfb7ef8aa1476a0ace09f4246d7fa4c92bf258aec7c580911"
RULE_PATHS = (
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/INT8_SA点积专项规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md",
    ".agents/rules/整网测试收敛优化专项规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
)


class AnalysisError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def record_map(value: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {
        item["path"]: {"size_bytes": item["size_bytes"], "sha256": item["sha256"]}
        for item in value[key]
    }


def kv(line: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"(?:^| )([A-Za-z0-9_]+)=([^ ]+)", line)
    }


def main() -> int:
    for path in (RETURN_ZIP, SOURCE_ZIP):
        if not path.is_file():
            raise AnalysisError(f"required identity is absent: {path}")

    with zipfile.ZipFile(RETURN_ZIP) as archive:
        records, payloads, return_errors = common.safe_records(
            archive, f"{PACKAGE_ID}_return"
        )
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        source_records, source_payloads, source_errors = common.safe_records(
            archive, PACKAGE_ID
        )

    manifest = json.loads(payloads["RETURN_MANIFEST.json"])
    allowlist = json.loads(payloads["RETURN_ALLOWLIST.json"])
    gate = json.loads(payloads["evidence/SERVER_RESULT_GATE.json"])
    identity = json.loads(payloads["evidence/production_rtl_identity.json"])
    package_preflight = json.loads(payloads["evidence/package_preflight.json"])
    install_preflight = json.loads(payloads["evidence/install_preflight.json"])
    observer_preflight = json.loads(payloads["evidence/observer_precompile.json"])
    local_status = json.loads(payloads["evidence/package_local_preflight_status.json"])
    path_budget = json.loads(payloads["evidence/path_budget.json"])
    layout = json.loads(payloads["evidence/runtime_layout_receipt.json"])
    root_gate = json.loads(payloads["evidence/ndp_root_toplevel_gate.json"])
    publication = json.loads(payloads["evidence/publication_preflight.json"])
    public = json.loads(payloads["evidence/public_order_summary.json"])
    buffer5 = json.loads(payloads["evidence/buffer5_public_summary.json"])
    triggered = json.loads(payloads["evidence/triggered_causal_summary.json"])
    source_manifest = json.loads(source_payloads["package_manifest.json"])
    returned_source_manifest = payloads["source_package/package_manifest.json"]
    compile_log = payloads["runs/compile/compile_driver.log"].decode(errors="replace")
    sim_log = payloads["runs/c0/sim.log"].decode(errors="replace")
    observer_log = payloads["runs/c0/return_observer.log"].decode(errors="replace")
    simulator_argv = payloads["runs/c0/simulator_argv.txt"].decode(errors="replace")
    compile_status = int(payloads["evidence/compile_exit_status.txt"].decode().strip())
    run_status = int(payloads["evidence/run_exit_status.txt"].decode().strip())
    signal_status = payloads["evidence/signal_status.txt"].decode().strip()

    declared = record_map(manifest, "records_excluding_this_manifest")
    expected = set(declared) | {"RETURN_MANIFEST.json", "RETURN_ALLOWLIST.json"}
    allowed = record_map(allowlist, "records")
    allowed_set = set(allowed) | {"RETURN_ALLOWLIST.json"}
    declared_mismatch = {
        path: {"expected": row, "observed": records.get(path)}
        for path, row in declared.items() if records.get(path) != row
    }
    allowed_mismatch = {
        path: {"expected": row, "observed": records.get(path)}
        for path, row in allowed.items() if records.get(path) != row
    }
    source_files = {
        path: row for path, row in source_records.items() if path != "package_manifest.json"
    }
    unique_return = (
        RETURN_ZIP.name == f"{PACKAGE_ID}_{EXECUTION_ID}_return.zip"
        and manifest["fixed_result_publication"]["return_zip"]
        == f"/home/panqs/ndp/simresult/{RETURN_ZIP.name}"
        and publication["return_zip"]
        == f"/home/panqs/ndp/simresult/{RETURN_ZIP.name}"
    )

    observer_text = source_payloads[OBSERVER].decode()
    compile_success = (
        compile_status == 0
        and "Verdi KDB elaboration finished with 0 error(s)" in compile_log
        and "Compilation completed!" in compile_log
        and "Error-[IND]" not in compile_log
        and "Error-[XMRE]" not in compile_log
        and common.digest(source_payloads[OBSERVER]) == EXPECTED_OBSERVER_SHA256
        and "p23 EPOCH_FLOW_ACTUAL_CONSUMER_BEGIN" in observer_text
    )
    simulation_started = (
        "+RETURN_OBS_EPOCH_FLOW" in simulator_argv
        and "[RETURN_OBSERVER] enabled N4D_FEATURE_ENABLE_V2" in sim_log
        and "feature=RETURN_OBS_EPOCH_FLOW enabled=1" in observer_log
    )
    flow_rows = [
        kv(line.split("|", 2)[-1])
        for line in observer_log.splitlines() if "EPOCH_FLOW_V1" in line
    ]
    if not flow_rows:
        raise AnalysisError("epoch-flow dynamic ledger is absent")
    flow_events = collections.Counter(row["event"] for row in flow_rows)
    queue_write = next(row for row in flow_rows if row["event"] == "QUEUE_WRITE")
    queue_read = next(row for row in flow_rows if row["event"] == "QUEUE_READ")
    terminal3 = next(row for row in flow_rows if int(row["desc_terminal"], 0) == 3)
    final = flow_rows[-1]
    mse_rows = [
        kv(line.split("|", 2)[-1])
        for line in observer_log.splitlines() if "MSE4_INDEX_EDGE_V1" in line
    ]
    pe_rows = [
        kv(line.split("|", 2)[-1])
        for line in observer_log.splitlines() if "LC18_PE7_EDGE_V1" in line
    ]
    final_pe = pe_rows[-1]
    edge_flow_closed = (
        len(flow_rows) == 10
        and flow_events == collections.Counter({
            "DESC_TERMINAL": 2, "QUEUE_WRITE": 1, "QUEUE_READ": 1,
            "BUFFER_ACCEPT": 3, "DESC_ACCEPT": 2, "PREPARED_ACCEPT": 1,
        })
        and int(queue_write["match"], 0) == 1
        and int(queue_write["qwr"], 0) == 1
        and int(queue_write["idx1"], 16) == 7
        and int(queue_read["qempty"], 0) == 0
        and int(queue_read["tag_valid"], 0) == 1
        and int(terminal3["desc"], 0) == 18
        and int(final["desc"], 0) == 18
        and int(final["prepared"], 0) == 20
        and int(final["buf_push"], 0) == 27
        and int(final["buf_pop"], 0) == 23
        and int(final["idx1"], 16) == 7
        and int(final_pe["pe7_out"], 16) == 0x430008
        and int(final_pe["mse_in1_valid"], 0) == 1
        and int(final_pe["mse_in1_bp"], 0) == 1
    )
    logger_semantic_gap = any(
        row.get("valid_same_get") == "z" for row in flow_rows
    ) and any(
        int(row["match"], 0) == 1 and int(row["valid_mask"], 16) == 0
        for row in flow_rows
    )
    interrupted = run_status == 125 and signal_status == "INT"
    qualified_stall = (
        public.get("valid") is True
        and public.get("status") == "SA_OUTPUT_HELD_BY_BUFFER_BACKPRESSURE"
        and public["observer"]["event_counts"]
        == {"SA_IN_ACCEPT": 30, "SA_OUT_ACCEPT": 5, "MSE4_INDEX_ACCEPT": 3}
        and buffer5.get("valid") is True
        and int(buffer5["last"]["sa_accept"]) == 5
        and int(buffer5["last"]["blocked_cycles"]) > 1_000_000
        and triggered.get("valid") is True
        and triggered.get("status") == "DYNAMIC_FLOW_CONTROL_STALL"
        and triggered["observer"]["natural_slice_finish_observed"] is False
    )
    no_formal = (
        source_manifest.get("formal_readback_count") == 0
        and gate["execution_gate"]["formal_D_claimed"] is False
        and not any(path.startswith("formal_D/") for path in records)
    )
    memory_leaf = identity.get("leaves", {}).get("Memory_AG_Idx_Queue.sv", {})
    actual_leaf_bound = (
        identity.get("collection_valid") is True
        and memory_leaf.get("sha256")
        == "2f534813b8d73ff19961541b910c03b417f401d73ae98b2e446e728f384a7b3e"
        and memory_leaf.get("matches_cloud_authority") is False
    )

    checks = {
        "transport_identity_exact": RETURN_ZIP.stat().st_size == RETURN_BYTES and sha256(RETURN_ZIP) == RETURN_SHA256,
        "source_identity_exact": SOURCE_ZIP.stat().st_size == SOURCE_BYTES and sha256(SOURCE_ZIP) == SOURCE_SHA256,
        "return_crc_root_path_safe": not return_errors,
        "source_crc_root_path_safe": not source_errors,
        "return_exact_set": set(records) == expected,
        "return_manifest_records_exact": not declared_mismatch,
        "return_allowlist_exact": set(records) == allowed_set and not allowed_mismatch,
        "source_files_exact": source_manifest["files"] == source_files,
        "returned_source_manifest_exact": (
            returned_source_manifest == source_payloads["package_manifest.json"]
            and manifest["source_package_manifest_sha256"] == common.digest(returned_source_manifest)
        ),
        "per_execution_unique_return_valid": unique_return,
        "package_install_observer_preflights_valid": (
            package_preflight["valid"] is True and install_preflight["valid"] is True
            and observer_preflight["valid"] is True and path_budget["valid"] is True
            and path_budget["longest_projected_relative_path_chars"]
            == len(path_budget["longest_projected_relative_path"])
            == path_budget["max_projected_relative_path_chars"]
        ),
        "install_only_root_gate_valid": (
            root_gate["valid"] is True and root_gate["ndp_root_toplevel_unchanged"] is True
            and layout["all_package_owned_paths_under_install"] is True
            and layout["root_exact_set_unchanged"] is True
            and layout["unknown_items_deleted_or_overwritten"] is False
        ),
        "p23_production_compile_pass": compile_success,
        "simulation_and_epoch_flow_started": simulation_started,
        "external_int_after_qualified_stall": interrupted and qualified_stall,
        "edge_qualified_memory_flow_observed": edge_flow_closed,
        "actual_memory_ag_leaf_bound": actual_leaf_bound,
        "formal_320d_absent_by_diagnostic_design": no_formal,
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-0ccae916-p23-return-analysis-v1",
        "status": "P23_EPOCH_FLOW_PASS_CONNECT_SELECTION_SUCCESSOR_REQUIRED" if valid else "RETURN_VALIDATION_FAILED",
        "valid": valid,
        "classification": "PARTIAL_INTERRUPTED_AFTER_QUALIFIED_CONNECT_FLOW_DIVERGENCE" if valid else "RETURN_VALIDATION_FAILED",
        "return_identity": {
            "path": str(RETURN_ZIP), "bytes": RETURN_ZIP.stat().st_size,
            "sha256": sha256(RETURN_ZIP), "execution_identity": EXECUTION_ID,
            "unique_per_execution_basename_valid": unique_return,
            "adjacent_sidecar_present": Path(str(RETURN_ZIP) + ".sha256").is_file(),
            "transport_policy": "USER_ATTESTED_EXTERNAL_SIDECAR_WAIVER",
        },
        "source_identity": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(), "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": sha256(SOURCE_ZIP),
            "source_manifest_sha256": common.digest(source_payloads["package_manifest.json"]),
            "observer_sha256": common.digest(source_payloads[OBSERVER]),
        },
        "internal_receipt": {
            "return_file_count": len(records), "source_file_count": len(source_records),
            "return_errors": return_errors, "source_errors": source_errors,
            "missing": sorted(expected - set(records)), "extra": sorted(set(records) - expected),
            "manifest_record_mismatches": declared_mismatch,
            "allowlist_record_mismatches": allowed_mismatch, "checks": checks,
        },
        "execution": {
            "compile_exit_status": compile_status, "run_exit_status": run_status,
            "signal_status": signal_status, "compile_succeeded": compile_success,
            "dut_simulation_started": simulation_started,
            "reported_preflight_stage": local_status["preflight_stage"],
            "external_interruption": interrupted, "natural_terminal": False,
            "formal_D_payload_present": False,
        },
        "production_rtl_identity": {
            "valid": identity.get("collection_valid") is True,
            "actual_differs_cloud_authority": identity.get("actual_differs_cloud_authority"),
            "identity_difference_blocks_simulator": False,
            "memory_ag_idx_queue": memory_leaf,
            "causal_cone_adjudication": "recorded_nonblocking_for_simulation_but_directly_affected_for_post_run_root_cause",
        },
        "edge_qualified_epoch_flow": {
            "record_count": len(flow_rows), "event_counts": dict(flow_events),
            "queue_write": queue_write, "queue_read": queue_read,
            "terminal3": terminal3, "final": final, "final_pe7": final_pe,
            "mse4_index_edge_count": len(mse_rows), "pe7_edge_count": len(pe_rows),
            "held_levels_count_as_transactions": False,
            "adjudication": (
                "The actual Memory_AG queue performs a qualified write/read and descriptors advance "
                "16->18.  The final PE7 public output presents valid index 8 with backpressure accept, "
                "while the selected Memory_AG input1 remains at index 7 and no next queue write forms."
            ),
            "observer_format_semantic_gap": {
                "present": logger_semantic_gap,
                "evidence": "valid_same_get=z and valid_mask=0 coexist with match=1 in rendered EPOCH_FLOW rows",
                "claim_impact": "private derived-mask fields are not used as functional evidence; public producer/selected-port comparison is required",
            },
        },
        "post_pekeep3_dflow": {
            "public_event_counts": public["observer"]["event_counts"],
            "buffer5_last": buffer5["last"], "natural_slice_finish_observed": False,
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": "p23 production compile and simulation reach a qualified Memory_AG queue write/read; descriptor count advances to 18 and PE7 emits a valid accepted index-8 word.",
            "FIRST_DIVERGENCE": "after PE7 emits 0x430008, the selected Memory_AG input1 remains index 7 and no next queue write/descriptor 19 appears.",
            "HANG_ROOT_CAUSE": {
                "status": "ROOT_NOT_YET_UNIQUE_PE7_TO_STREAM_CONNECT_SELECTION",
                "classification": "MSE4_INPUT1_SELECTED_SOURCE_OR_CONNECT_TRANSPORT_DIVERGENCE",
                "remaining_observational_equivalents": [
                    "MSE4 input1 src_id selects a source other than PE7",
                    "the selected Stream_Engine_Connect public input does not carry PE7 index 8",
                    "the connect output carries index 8 but the actual Memory_AG public input fails to receive it",
                ],
                "authorized_config_fix": None, "functional_rtl_root_cause_proven": False,
            },
        },
        "result_conjunction": {
            "compile": compile_success, "simulator_started": simulation_started,
            "c0_slice_finish": False, "natural_terminal_27_of_27": False,
            "formal_D_320_of_320": False, "mismatch_zero_claim": False,
            "E3": False, "E4": False, "E5": False, "performance_claimed": False,
            "passed": False,
        },
        "blocker_delta": {
            "closed": [
                "B_CONV_NATIVE_P23_FORMAL_RETURN_RECEIPT",
                "B_CONV_NATIVE_ACTUAL_MEMORY_AG_IDX_QUEUE_IDENTITY_UNCOLLECTED",
                "B_CONV_NATIVE_MEMORY_AG_QUEUE_WRITE_READ_UNOBSERVED",
            ],
            "opened": [
                "B_CONV_NATIVE_PE7_TO_MSE4_SELECTED_SOURCE_CONNECT_UNRESOLVED",
                "B_CONV_NATIVE_P23_PRIVATE_DERIVED_MASK_RENDER_SEMANTIC_GAP",
            ],
            "preserved": [
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN",
                "B_CONV_NATIVE4_E4_E5_UNPROVEN",
            ],
        },
        "successor": {
            "required": valid, "fresh_identity": True,
            "highest_information_scope": (
                "one bounded same-clock public-port ledger across PE7 output, Stream_Engine_Connect "
                "configured src_id and selected input/output, and Memory_AG input1; freeze DUT/config/numeric payload"
            ),
            "server_action": False,
        },
        "current_rule_receipts": {
            path: {"bytes": (ROOT / path).stat().st_size, "sha256": sha256(ROOT / path)}
            for path in RULE_PATHS
        },
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-DIAGNOSTIC-EVENT-QUALIFICATION-001",
                "CDA-SERVER-DIAGNOSTIC-LOGGER-PARSER-EXACT-FORMAT-TRACE-001",
                "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
            ],
            "delta": None,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise AnalysisError(f"refusing to overwrite formal analysis: {OUTPUT}")
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({"status": result["status"], "valid": valid, "output": str(OUTPUT)}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
