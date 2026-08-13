#!/usr/bin/env python3
"""Validate and adjudicate the formal native-four-lane p22 return."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

import analyze_conv_native_four_lane_0ccae916_p18_return as common


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p22_eoenfix"
EXECUTION_ID = "r1786179884579791346_4051767"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads"
    r"\r5_n4_0cc_p22_eoenfix_r1786179884579791346_4051767_return.zip"
)
SOURCE_ZIP = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE_ID}.zip"
)
RETURN_BYTES = 2_160_417
RETURN_SHA256 = "1a791abaa445287ac68ae0cdaa4e47dc68ab3ecd756ca75a29eefd9f5a56f2da"
SOURCE_BYTES = 5_876_663
SOURCE_SHA256 = "876f9a16575648ddcb2dd594a881651cf7c678ddb30d344d112c68951f4fd8cf"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p22_return_analysis/report_v2.json"
OBSERVER = "tb_probe/native_return_observer.svh"
EXPECTED_OBSERVER_SHA256 = "9e43d5300050a9df1a559a376f375ee81f1dfcb326c0ec677f24231e73d80c26"
RULE_PATHS = common.RULE_PATHS


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
        and sha256(SOURCE_ZIP) == SOURCE_SHA256
        and common.digest(source_payloads[OBSERVER]) == EXPECTED_OBSERVER_SHA256
        and "return_obs_enabled" not in observer_text
        and observer_text.count("if (return_obs_eo_enabled && n4d_fd != 0) begin") == 2
    )
    simulation_started = (
        "+RETURN_OBSERVER" in simulator_argv
        and "+RETURN_OBS_EPOCH_OWNER" in simulator_argv
        and "[RETURN_OBSERVER] enabled N4D_FEATURE_ENABLE_V2" in sim_log
        and "feature=RETURN_OBS_EPOCH_OWNER enabled=1" in observer_log
    )
    epoch_rows = [
        kv(line.split("|", 2)[-1])
        for line in observer_log.splitlines() if "EPOCH_OWNER_V1" in line
    ]
    if not epoch_rows:
        raise AnalysisError("epoch-owner dynamic ledger is absent")
    terminal2 = next(row for row in epoch_rows if int(row["desc_terminal"], 0) == 2)
    terminal3 = next(row for row in epoch_rows if int(row["desc_terminal"], 0) == 3)
    final = epoch_rows[-1]
    tuple_fields = (
        "desc_terminal", "desc", "prepared", "delta", "buf_push", "buf_pop",
        "valid", "same", "gotten", "masked", "bp", "match", "qempty",
        "mode0", "mode1", "mode2", "keep0", "keep1", "keep2",
        "idx0", "idx1", "idx2", "tag0", "tag1", "tag2",
        "lc6", "bp6", "lc8", "bp8", "lc17", "bp17", "lc18", "bp18",
        "row_full", "col_full", "bufq_full", "prepared_count", "prepared_bp",
    )
    displayed_keys = [tuple(row.get(field) for field in tuple_fields) for row in epoch_rows]
    consecutive_duplicates = sum(
        left == right for left, right in zip(displayed_keys, displayed_keys[1:])
    )
    epoch_boundary = (
        len(epoch_rows) == 128
        and int(terminal2["desc"], 0) == 16
        and int(terminal2["prepared"], 0) == 17
        and int(terminal3["desc"], 0) == 18
        and int(terminal3["prepared"], 0) == 19
        and int(final["desc"], 0) == 18
        and int(final["prepared"], 0) == 20
        and int(final["buf_push"], 0) == 27
        and int(final["buf_pop"], 0) == 23
        and int(final["valid"], 16) == 1
        and int(final["same"], 16) == 1
        and int(final["gotten"], 16) == 7
        and int(final["masked"], 16) == 0
        and int(final["bp"], 16) == 7
        and int(final["match"], 0) == 0
        and int(final["qempty"], 0) == 1
        and int(final["mode0"], 16) == 2
        and int(final["mode1"], 16) == 1
        and int(final["mode2"], 16) == 2
        and int(final["keep1"], 0) == 3
        and int(final["tag0"], 16) == 0x51
        and int(final["tag1"], 16) == 0x03
        and int(final["tag2"], 16) == 0
    )
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
    interrupted = run_status == 125 and signal_status == "INT"
    no_formal = (
        source_manifest.get("formal_readback_count") == 0
        and gate["execution_gate"]["formal_D_claimed"] is False
        and not any(path.startswith("formal_D/") for path in records)
    )
    memory_ag_identity_missing = "Memory_AG_Idx_Queue.sv" not in identity.get("leaves", {})

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
            package_preflight["valid"] is True
            and install_preflight["valid"] is True
            and observer_preflight["valid"] is True
            and path_budget["valid"] is True
            and path_budget["longest_projected_relative_path_chars"]
            == len(path_budget["longest_projected_relative_path"])
            == path_budget["max_projected_relative_path_chars"]
        ),
        "install_only_root_gate_valid": (
            root_gate["valid"] is True
            and root_gate["ndp_root_toplevel_unchanged"] is True
            and layout["all_package_owned_paths_under_install"] is True
            and layout["root_exact_set_unchanged"] is True
            and layout["unknown_items_deleted_or_overwritten"] is False
        ),
        "eo_enable_fix_production_compile_pass": compile_success,
        "simulation_and_epoch_feature_started": simulation_started,
        "external_int_after_qualified_stall": interrupted and qualified_stall,
        "epoch_owner_boundary_observed": epoch_boundary,
        "formal_320d_absent_by_diagnostic_design": no_formal,
        "actual_memory_ag_leaf_identity_gap_identified": memory_ag_identity_missing,
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-0ccae916-p22-return-analysis-v1",
        "status": "P22_EO_FIX_PASS_EPOCH_FLOW_SUCCESSOR_REQUIRED" if valid else "RETURN_VALIDATION_FAILED",
        "valid": valid,
        "classification": "PARTIAL_INTERRUPTED_AFTER_EPOCH_OWNER_BRANCH_DIVERGENCE" if valid else "RETURN_VALIDATION_FAILED",
        "return_identity": {
            "path": str(RETURN_ZIP), "bytes": RETURN_ZIP.stat().st_size,
            "sha256": sha256(RETURN_ZIP), "execution_identity": EXECUTION_ID,
            "unique_per_execution_basename_valid": unique_return,
            "adjacent_sidecar_present": Path(str(RETURN_ZIP) + ".sha256").is_file(),
            "transport_policy": "USER_ATTESTED_EXTERNAL_SIDECAR_WAIVER",
        },
        "source_identity": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "bytes": SOURCE_ZIP.stat().st_size, "sha256": sha256(SOURCE_ZIP),
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
            "eo_enable_token_fix_production_validated": compile_success,
            "dut_simulation_started": simulation_started,
            "reported_preflight_stage": local_status["preflight_stage"],
            "external_interruption": interrupted, "natural_terminal": False,
            "formal_D_payload_present": False,
        },
        "production_rtl_identity": {
            "valid": identity.get("collection_valid") is True,
            "actual_differs_cloud_authority": identity.get("actual_differs_cloud_authority"),
            "identity_difference_blocks_simulator": False,
            "memory_ag_idx_queue_leaf_collected": not memory_ag_identity_missing,
            "collected_leaf_names": sorted(identity.get("leaves", {})),
        },
        "same_clock_epoch_owner_ledger": {
            "record_count": len(epoch_rows), "record_limit_reached": len(epoch_rows) == 128,
            "consecutive_displayed_tuple_duplicates": consecutive_duplicates,
            "terminal2": terminal2, "terminal3": terminal3, "final": final,
            "adjudication": (
                "descriptor/address ownership stops at 18 while the Buffer branch prepares two "
                "additional groups; input0 is the only raw-valid/same owner, input1 buffer-mode "
                "is not valid, input2 keep-mode has no raw token, all bp bits remain asserted, "
                "mem_all_idx_matched remains zero and the Memory_AG queue remains empty"
            ),
            "held_levels_count_as_transactions": False,
            "qualification_escape": {
                "present": consecutive_duplicates > 0,
                "impact": "the bounded ledger saturated on repeated displayed tuples; it proves the stable boundary but not the missing producer/queue event ownership",
            },
        },
        "post_pekeep3_dflow": {
            "public_event_counts": public["observer"]["event_counts"],
            "buffer5_last": buffer5["last"],
            "natural_slice_finish_observed": False,
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": "p22 production compile validates the eo-enabled token repair; descriptor terminal 3 is observed and Buffer prepares two post-boundary groups while qualified Buffer5/SA backpressure remains live.",
            "FIRST_DIVERGENCE": "MSE4 Memory_AG input1 is buffer-mode but raw-valid is absent after terminal 3; mem_all_idx_matched stays zero and the Memory_AG index queue stays empty while the descriptor count remains 18.",
            "HANG_ROOT_CAUSE": {
                "status": "ROOT_NOT_YET_UNIQUE_MSE4_PRODUCER_VS_LEAF_HANDSHAKE",
                "classification": "MSE4_INPUT1_EPOCH_TOKEN_ABSENT_AT_MEMORY_AG_BOUNDARY",
                "remaining_observational_equivalents": [
                    "upstream IGA/connection does not issue the next input1 token",
                    "Memory_AG same/gotten/bp ownership suppresses the next input1 token",
                    "queue write/read ownership prevents a newly matched tuple from becoming visible",
                ],
                "actual_leaf_identity_gap": "Memory_AG_Idx_Queue.sv not collected by p22 production identity",
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
            "closed": ["B_CONV_NATIVE_P22_FORMAL_RETURN_RECEIPT", "B_CONV_NATIVE_P21_EO_ENABLE_TOKEN_COMPILE_ESCAPE", "B_CONV_NATIVE_MSE4_PER_INPUT_EPOCH_OWNER_UNOBSERVED"],
            "opened": ["B_CONV_NATIVE_MSE4_INPUT1_PRODUCER_VS_MEMORY_AG_LEAF_HANDSHAKE_UNRESOLVED", "B_CONV_NATIVE_P22_EPOCH_LEDGER_QUALIFICATION_SATURATION", "B_CONV_NATIVE_ACTUAL_MEMORY_AG_IDX_QUEUE_IDENTITY_UNCOLLECTED"],
            "preserved": ["B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN", "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN", "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN", "B_CONV_NATIVE4_E4_E5_UNPROVEN"],
        },
        "successor": {
            "required": valid, "fresh_identity": True,
            "highest_information_scope": "one bounded edge-qualified MSE4 epoch-flow ledger that binds the exact actual Memory_AG_Idx_Queue leaf and distinguishes upstream input issue/accept, leaf masks, queue write/read, and descriptor/Buffer ownership; freeze DUT/config/numeric payload",
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
                "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
                "CDA-SERVER-DIAGNOSTIC-EVENT-QUALIFICATION-001",
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
