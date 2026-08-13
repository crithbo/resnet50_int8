#!/usr/bin/env python3
"""Validate and adjudicate the formal native-four-lane p20 return."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

import analyze_conv_native_four_lane_0ccae916_p18_return as common


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p20_obsbindfix"
EXECUTION_ID = "r1786159986792917726_3954624"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads"
    r"\r5_n4_0cc_p20_obsbindfix_r1786159986792917726_3954624_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane"
    / PACKAGE_ID
    / f"{PACKAGE_ID}.zip"
)
RETURN_BYTES = 2_068_706
RETURN_SHA256 = (
    "67441ee6c11d67cf4dec6159f5dca5ae4b3d0e7a96048793e6dadc95f451076d"
)
SOURCE_BYTES = 5_874_994
SOURCE_SHA256 = (
    "68e2fc8f98fa1c6c95fa8eb56a7d5a46e9ac132719cf252be5748b3da2dca208"
)
OUTPUT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p20_return_analysis/report_v3.json"
)
REPEAT_RECEIPT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "tested/conv_native_four_lane/r5_n4_0cc_p20_obsbindfix/"
    "r5_n4_0cc_p20_obsbindfix.runtime_layout_harness.json"
)
RULE_PATHS = common.RULE_PATHS

EXPECTED_FEATURES = {
    "RETURN_OBS_DWRITE_PATH",
    "RETURN_OBS_DATAHUB_DRAIN",
    "RETURN_OBS_MSE4_DESCRIPTOR",
    "RETURN_OBS_MSE4_INDEX",
    "RETURN_OBS_LC18_PE7",
    "RETURN_OBS_ROWLC4_BUFAG",
    "RETURN_OBS_B5RD",
    "RETURN_OBS_WRDRAIN",
    "RETURN_OBS_WRTERM",
    "RETURN_OBS_LC9_SPLIT",
    "RETURN_OBS_LC9_ACTUAL",
    "RETURN_OBS_DTERM_OWNER",
    "RETURN_OBS_LC13_LC14",
    "RETURN_OBS_DSKEW",
}


class AnalysisError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def record_map(value: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {
        item["path"]: {
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in value[key]
    }


def kv(line: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"(?:^| )([A-Za-z0-9_]+)=([^ ]+)", line)
    }


def event_rows(text: str, marker: str) -> list[dict[str, str]]:
    return [kv(line.split("|", 2)[-1]) for line in text.splitlines() if marker in line]


def main() -> int:
    for path in (RETURN_ZIP, SOURCE_ZIP, REPEAT_RECEIPT):
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
        for path, row in declared.items()
        if records.get(path) != row
    }
    allowed_mismatch = {
        path: {"expected": row, "observed": records.get(path)}
        for path, row in allowed.items()
        if records.get(path) != row
    }
    source_files = {
        path: row for path, row in source_records.items() if path != "package_manifest.json"
    }

    repeat = json.loads(REPEAT_RECEIPT.read_text(encoding="utf-8"))
    scenarios = repeat.get("scenarios", {})
    repeat_valid = (
        repeat.get("derived_from_zip_sha256") == SOURCE_SHA256
        and set(scenarios) == {"normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM"}
        and all(row.get("finalizer_reached") is True for row in scenarios.values())
        and all(row.get("fixed_result_return_published") is True for row in scenarios.values())
        and all(row.get("root_exact_set_unchanged") is True for row in scenarios.values())
    )
    unique_return = (
        RETURN_ZIP.name == f"{PACKAGE_ID}_{EXECUTION_ID}_return.zip"
        and manifest["fixed_result_publication"]["return_zip"]
        == f"/home/panqs/ndp/simresult/{RETURN_ZIP.name}"
        and publication["return_zip"]
        == f"/home/panqs/ndp/simresult/{RETURN_ZIP.name}"
        and publication["publication_state"] == "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING"
    )

    compile_success = (
        compile_status == 0
        and "Verdi KDB elaboration finished with 0 error(s)" in compile_log
        and "Compilation completed!" in compile_log
        and "Error-[IND]" not in compile_log
        and "Error-[XMRE]" not in compile_log
        and "return_obs_enabled" not in compile_log
    )
    features = {
        row.get("feature")
        for row in event_rows(observer_log, "DIAGNOSTIC_FEATURE_ENABLE_V1")
        if row.get("enabled") == "1"
    }
    simulation_started = (
        "+RETURN_OBSERVER" in simulator_argv
        and "[RETURN_OBSERVER] enabled N4D_FEATURE_ENABLE_V2" in sim_log
        and "N4D_FEATURE_ENABLE_V2" in observer_log
        and EXPECTED_FEATURES == features
    )

    dskew = event_rows(observer_log, "DSKEW_EDGE_V1")
    mse4 = event_rows(observer_log, "MSE4_INDEX_EDGE_V1")
    rowbuf = event_rows(observer_log, "ROWLC4_BUFAG_EDGE_V1")
    wrterm = event_rows(observer_log, "WRTERM2_EDGE_V1")
    dterm = event_rows(observer_log, "DTERM_OWNER_EDGE_V1")
    if not all((dskew, mse4, rowbuf, wrterm, dterm)):
        raise AnalysisError("required qualified D-flow event family is absent")
    last_ds, last_mi, last_rb, last_wt = dskew[-1], mse4[-1], rowbuf[-1], wrterm[-1]
    third_terminal_index = next(
        index for index, row in enumerate(dskew) if int(row.get("desc_terminal", "0"), 0) >= 3
    )
    third_terminal = dskew[third_terminal_index]
    post_third = dskew[third_terminal_index:]
    coarse_branch_boundary = (
        int(third_terminal["desc"], 0) == 18
        and int(third_terminal["desc_pop"], 0) == 18
        and int(third_terminal["prepared"], 0) == 19
        and int(third_terminal["delta"], 0) == 1
        and int(last_ds["desc"], 0) == 18
        and int(last_ds["desc_pop"], 0) == 18
        and int(last_ds["prepared"], 0) == 20
        and int(last_ds["delta"], 0) == 2
        and int(last_ds["source_push"], 0) == 27
        and int(last_ds["source_pop"], 0) == 23
        and int(last_ds["desc_terminal"], 0) == 3
        and int(last_mi["input_vld"], 0) == 1
        and int(last_mi["input_same"], 0) == 1
        and int(last_mi["gotten"], 0) == 7
        and int(last_mi["matched"], 0) == 0
        and int(last_mi["q_empty"], 0) == 1
        and any(
            int(row["row_full"], 0) == 1
            and int(row["col_full"], 0) == 1
            and int(row["prepared_count"], 0) == 32
            and int(row["prepared_bp"], 0) == 0
            for row in rowbuf
        )
        and int(last_rb["bufq_full"], 0) == 1
        and int(last_rb["rd_full"], 0) == 1
        and int(last_rb["prepared_count"], 0) == 32
        and int(last_rb["prepared_bp"], 0) == 0
        and int(last_wt["desc_count"], 0) == 0
        and int(last_wt["tag_last"], 0) == 1
        and int(last_wt["tag_index"], 0) == 4
        and int(last_wt["head_last"], 0) == 1
        and int(last_wt["head_index"], 0) == 5
    )
    qualified_stall = (
        triggered.get("valid") is True
        and triggered.get("status") == "DYNAMIC_FLOW_CONTROL_STALL"
        and triggered["observer"]["trigger_counts"].get("NO_PROGRESS_WINDOW") == 4
        and triggered["observer"]["natural_slice_finish_observed"] is False
        and public.get("valid") is True
        and public["observer"]["event_counts"]
        == {"SA_IN_ACCEPT": 30, "SA_OUT_ACCEPT": 5, "MSE4_INDEX_ACCEPT": 3}
        and buffer5.get("valid") is True
        and int(buffer5["last"]["arm_accept"]) == 5
        and int(buffer5["last"]["blocked_cycles"]) > 1_000_000
    )
    no_formal = (
        source_manifest.get("formal_readback_count") == 0
        and gate["execution_gate"]["formal_D_claimed"] is False
        and not any(path.startswith("formal_D/") for path in records)
    )
    interrupted = run_status == 125 and signal_status == "INT"
    generic_held_level_escape = (
        "decision=STILL_PROGRESSING" in observer_log
        and qualified_stall
        and int(buffer5["last"]["blocked_cycles"]) > 1_000_000
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
        "repeat_owned_reset_contract_valid": repeat_valid,
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
        "lexical_observer_binding_production_compile_pass": compile_success,
        "simulation_and_all_dflow_features_started": simulation_started,
        "external_int_after_qualified_stall": interrupted and qualified_stall,
        "coarse_branch_boundary_closed": coarse_branch_boundary,
        "formal_320d_absent_by_diagnostic_design": no_formal,
    }
    valid = all(checks.values())
    relevant_actual = {
        name: row
        for name, row in identity.get("leaves", {}).items()
        if name in {
            "Array_Request_Manager.sv", "Buffer.sv", "Buffer_AG_Idx_Queue.sv",
            "Buffer_Manager.sv", "Memory_Req_Manager.sv", "RD_Data_Channel.sv",
        }
    }
    result = {
        "schema": "conv-native-four-lane-0ccae916-p20-return-analysis-v1",
        "status": "P20_COMPILE_FIX_PASS_PER_INPUT_EPOCH_OWNER_SUCCESSOR_REQUIRED" if valid else "RETURN_VALIDATION_FAILED",
        "valid": valid,
        "classification": "PARTIAL_INTERRUPTED_AFTER_REPEATABLE_QUALIFIED_DFLOW_STALL" if valid else "RETURN_VALIDATION_FAILED",
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
            "lexical_observer_binding_fix_production_validated": compile_success,
            "dut_simulation_started": simulation_started,
            "stale_package_local_status_bit": {
                "reported": local_status.get("dut_simulation_started"),
                "contradicted_by": ["simulator argv", "sim.log N4D marker", "observer log N4D marker", "14 imported feature markers"],
                "blocking": False,
            },
            "external_interruption": interrupted, "natural_terminal": False,
            "formal_D_payload_present": False,
        },
        "production_rtl_identity": {
            "valid": identity.get("collection_valid") is True,
            "actual_differs_cloud_authority": identity.get("actual_differs_cloud_authority"),
            "identity_difference_blocks_simulator": False,
            "relevant_actual_leaves": relevant_actual,
            "claim_boundary": "Dynamic evidence is bound to exact compiled production leaves; actual/cloud differences remain nonblocking provenance and forbid cloud-wide E4/E5 promotion.",
        },
        "qualified_post_pekeep3_dflow": {
            "enabled_features": sorted(features),
            "public_event_counts": public["observer"]["event_counts"],
            "buffer5_last": buffer5["last"],
            "third_terminal_first_snapshot": third_terminal,
            "post_third_dskew_records": post_third,
            "final": {"dskew": last_ds, "mse4_index": last_mi, "rowlc4_bufag": last_rb, "wrterm": last_wt},
            "coarse_branch_boundary_closed": coarse_branch_boundary,
            "held_levels_count_as_transactions": False,
            "generic_progress_escape": {
                "present": generic_held_level_escape,
                "disposition": "NON_CANONICAL_RECORD_ONLY",
                "reason": "raw valid/write levels grow legacy counters while specialized qualified handshakes remain unchanged",
            },
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": "Production compile validates the p20 lexical binding fix; the third descriptor terminal reaches desc=18/pop=18/prepared=19 and then the Buffer data branch accepts one further prepared group.",
            "FIRST_DIVERGENCE": "After descriptor terminal 3, descriptor/address issuance remains at 18 while prepared reaches 20 and Buffer source push/pop reaches 27/23; Memory_AG has raw/same/gotten/masked=1/1/7/0 with match=0 and empty queue.",
            "HANG_ROOT_CAUSE": {
                "status": "ROOT_NOT_YET_UNIQUE_PER_INPUT_EPOCH_OWNERSHIP_UNOBSERVED",
                "classification": "MSE4_ADDRESS_BRANCH_VS_BUFFER_BRANCH_EPOCH_SKEW",
                "closed_candidates": ["p19 lexical observer binding", "PE keep_last_index=3", "fixed descriptor shortage per epoch"],
                "remaining_observational_equivalents": [
                    "shared-LC partial capture", "physical LC terminal/keep stop",
                    "Memory_AG same/gotten suppression", "Buffer next-epoch early acceptance",
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
            "closed": ["B_CONV_NATIVE_P20_FORMAL_RETURN_RECEIPT", "B_CONV_NATIVE_P19B_PACKAGE_LOCAL_OBSERVER_SCOPE_COMPILE_ESCAPE", "B_CONV_NATIVE_POST_PEKEEP3_COARSE_DFLOW_BOUNDARY"],
            "opened": ["B_CONV_NATIVE_MSE4_PER_INPUT_EPOCH_OWNERSHIP_UNOBSERVED"],
            "preserved": ["B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN", "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN", "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN", "B_CONV_NATIVE4_E4_E5_UNPROVEN"],
        },
        "successor": {
            "required": valid, "fresh_identity": True,
            "highest_information_scope": "add one bounded same-clock per-input epoch-owner ledger equivalent to the already-validated serialized v66 observer; also make partial-INT feature binding and simulation-start receipts signal-safe; freeze all DUT/config/numeric payload",
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
