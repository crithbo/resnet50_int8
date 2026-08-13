#!/usr/bin/env python3
"""Validate and adjudicate the formal p19b per-execution native Conv return."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

import analyze_conv_native_four_lane_0ccae916_p18_return as common


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p19b_dflow"
EXECUTION_ID = "r1786123618156106372_3804102"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads"
    r"\r5_n4_0cc_p19b_dflow_r1786123618156106372_3804102_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE_ID}.zip"
)
RETURN_BYTES = 718_510
RETURN_SHA256 = (
    "3c6881ae5c4e77e63154c2fb9a9a1f83f172031271db8be47ae93d204c4ba826"
)
SOURCE_BYTES = 5_873_801
SOURCE_SHA256 = (
    "ac920faca1e90bcf31371a49529579bd8ec31a0c711a10f6f4820f60778114ef"
)
OUTPUT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p19b_return_analysis"
    / "report.json"
)
REPEAT_RECEIPT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "pending_receipts/conv_native_four_lane/r5_n4_0cc_p19b_dflow/"
    "r5_n4_0cc_p19b_dflow.runtime_layout_harness.json"
)
RULE_PATHS = common.RULE_PATHS


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
    package_preflight = json.loads(
        payloads["evidence/package_preflight.json"]
    )
    install_preflight = json.loads(
        payloads["evidence/install_preflight.json"]
    )
    observer_preflight = json.loads(
        payloads["evidence/observer_precompile.json"]
    )
    local_status = json.loads(
        payloads["evidence/package_local_preflight_status.json"]
    )
    path_budget = json.loads(payloads["evidence/path_budget.json"])
    layout = json.loads(payloads["evidence/runtime_layout_receipt.json"])
    root_gate = json.loads(
        payloads["evidence/ndp_root_toplevel_gate.json"]
    )
    publication = json.loads(
        payloads["evidence/publication_preflight.json"]
    )
    public = json.loads(payloads["evidence/public_order_summary.json"])
    buffer5 = json.loads(payloads["evidence/buffer5_public_summary.json"])
    triggered = json.loads(
        payloads["evidence/triggered_causal_summary.json"]
    )
    source_manifest = json.loads(source_payloads["package_manifest.json"])
    returned_source_manifest = payloads[
        "source_package/package_manifest.json"
    ]
    compile_log = payloads["runs/compile/compile_driver.log"].decode(
        errors="replace"
    )
    compile_status = int(
        payloads["evidence/compile_exit_status.txt"].decode().strip()
    )
    run_status = int(
        payloads["evidence/run_exit_status.txt"].decode().strip()
    )
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
        path: row
        for path, row in source_records.items()
        if path != "package_manifest.json"
    }

    error_rows = [
        {
            "line": index,
            "text": line,
        }
        for index, line in enumerate(compile_log.splitlines(), 1)
        if (
            "Error-[IND]" in line
            or "Identifier 'return_obs_" in line
            or "3 errors" in line
            or "Error 255" in line
        )
    ]
    unresolved_identifiers = sorted(
        set(re.findall(r"Identifier '([^']+)' has not been declared", compile_log))
    )
    compile_escape_exact = (
        compile_status == 2
        and unresolved_identifiers
        == ["return_obs_active", "return_obs_enabled", "return_obs_fd"]
        and compile_log.count("Error-[IND]") == 3
        and "native_return_observer.svh, 2203" in compile_log
        and "native_return_observer.svh, 2238" in compile_log
        and "3 errors" in compile_log
        and "make: *** [Makefile.tb_NDP_Top_new_phy:306: compile] Error 255"
        in compile_log
    )
    unique_basename = (
        RETURN_ZIP.name
        == f"{PACKAGE_ID}_{EXECUTION_ID}_return.zip"
        and manifest["fixed_result_publication"]["return_zip"]
        == f"/home/panqs/ndp/simresult/{RETURN_ZIP.name}"
        and publication["return_zip"]
        == f"/home/panqs/ndp/simresult/{RETURN_ZIP.name}"
        and publication["publication_state"]
        == "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING"
    )
    repeat = json.loads(REPEAT_RECEIPT.read_text(encoding="utf-8"))
    scenarios = repeat.get("scenarios", {})
    repeat_contract = (
        repeat.get("derived_from_zip_sha256") == SOURCE_SHA256
        and set(scenarios)
        == {"normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM"}
        and all(row.get("finalizer_reached") is True for row in scenarios.values())
        and all(
            row.get("fixed_result_return_published") is True
            for row in scenarios.values()
        )
        and all(
            row.get("root_exact_set_unchanged") is True
            for row in scenarios.values()
        )
        and layout["repeat_execution"]["mode"]
        == "RESET_EXACT_PACKAGE_OWNED_RUNTIME_ROOTS"
        and layout["repeat_execution"]["foreign_sibling_policy"] == "PRESERVE"
        and layout["unknown_items_deleted_or_overwritten"] is False
    )
    no_simulation = (
        local_status["production_compile_started"] is True
        and local_status["dut_simulation_started"] is False
        and not any(path.startswith("runs/c0/") for path in records)
        and public["observer"]["present"] is False
        and buffer5["observer_log"]["present"] is False
        and triggered["status"] == "SIM_NOT_STARTED"
    )
    no_formal = (
        source_manifest.get("formal_readback_count") == 0
        and gate["execution_gate"]["formal_D_claimed"] is False
        and not any(path.startswith("formal_D/") for path in records)
    )
    checks = {
        "transport_identity_exact": (
            RETURN_ZIP.stat().st_size == RETURN_BYTES
            and sha256(RETURN_ZIP) == RETURN_SHA256
        ),
        "source_identity_exact": (
            SOURCE_ZIP.stat().st_size == SOURCE_BYTES
            and sha256(SOURCE_ZIP) == SOURCE_SHA256
        ),
        "return_crc_root_path_safe": not return_errors,
        "source_crc_root_path_safe": not source_errors,
        "return_exact_set": set(records) == expected,
        "return_manifest_records_exact": not declared_mismatch,
        "return_allowlist_exact": (
            set(records) == allowed_set and not allowed_mismatch
        ),
        "source_files_exact": source_manifest["files"] == source_files,
        "returned_source_manifest_exact": (
            returned_source_manifest == source_payloads["package_manifest.json"]
            and manifest["source_package_manifest_sha256"]
            == common.digest(returned_source_manifest)
        ),
        "per_execution_unique_return_valid": unique_basename,
        "repeat_owned_reset_contract_valid": repeat_contract,
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
        "package_local_observer_scope_compile_escape_exact": (
            compile_escape_exact
        ),
        "simulation_not_started": no_simulation,
        "formal_320d_absent_by_diagnostic_design": no_formal,
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-0ccae916-p19b-return-analysis-v1",
        "status": (
            "P19B_PACKAGE_LOCAL_OBSERVER_SCOPE_COMPILE_ESCAPE_SUCCESSOR_REQUIRED"
            if valid
            else "RETURN_VALIDATION_FAILED"
        ),
        "valid": valid,
        "classification": (
            "PACKAGE_LOCAL_OBSERVER_SCOPE_BINDING_COMPILE_FAILURE"
            if valid
            else "RETURN_VALIDATION_FAILED"
        ),
        "return_identity": {
            "path": str(RETURN_ZIP),
            "bytes": RETURN_ZIP.stat().st_size,
            "sha256": sha256(RETURN_ZIP),
            "execution_identity": EXECUTION_ID,
            "unique_per_execution_basename_valid": unique_basename,
            "source_mismatch_from_unique_basename": False,
            "adjacent_sidecar_present": Path(
                str(RETURN_ZIP) + ".sha256"
            ).is_file(),
            "transport_policy": "USER_ATTESTED_EXTERNAL_SIDECAR_WAIVER",
        },
        "source_identity": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": sha256(SOURCE_ZIP),
            "source_manifest_sha256": common.digest(
                source_payloads["package_manifest.json"]
            ),
        },
        "internal_receipt": {
            "return_file_count": len(records),
            "source_file_count": len(source_records),
            "return_errors": return_errors,
            "source_errors": source_errors,
            "missing": sorted(expected - set(records)),
            "extra": sorted(set(records) - expected),
            "manifest_record_mismatches": declared_mismatch,
            "allowlist_record_mismatches": allowed_mismatch,
            "checks": checks,
        },
        "repeat_and_install": {
            "local_repeat_validation": {
                "path": REPEAT_RECEIPT.relative_to(ROOT).as_posix(),
                "sha256": sha256(REPEAT_RECEIPT),
                "valid": repeat_contract,
            },
            "runtime_repeat_execution": layout["repeat_execution"],
            "root_gate": root_gate,
            "publication": manifest["fixed_result_publication"],
        },
        "execution": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "production_compile_started": True,
            "compile_succeeded": False,
            "production_rtl_identity_collected": False,
            "dut_simulation_started": False,
            "c0_slice_finish": False,
            "natural_terminal": False,
            "formal_D_present": 0,
        },
        "qualified_d_flow_causal_ledger": {
            "status": "NOT_EXECUTED_COMPILE_GATE",
            "qualified_event_count": 0,
            "held_levels_count_as_transactions": False,
            "root_cause_inference_from_dynamic_D_flow": "FORBIDDEN",
            "triggered_summary": triggered,
            "public_order_summary": public,
            "buffer5_public_summary": buffer5,
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": (
                "path/package/install/observer identity preflights and the "
                "production compiler invocation completed."
            ),
            "FIRST_DIVERGENCE": (
                "VCS parsed the exact package observer and rejected three "
                "out-of-scope identifiers at lines 2203 and 2238 before "
                "elaboration or simulation."
            ),
            "HANG_ROOT_CAUSE": {
                "status": "UNIQUE_PACKAGE_LOCAL_ROOT",
                "classification": (
                    "P19_IMPORTED_DFLOW_TAIL_USED_V64_PRIVATE_OBSERVER_SYMBOLS"
                ),
                "unresolved_identifiers": unresolved_identifiers,
                "compile_error_rows": error_rows,
                "package_audit_escape": (
                    "the focused tail compile fabricated declarations for "
                    "return_obs_enabled/return_obs_fd/return_obs_active and "
                    "therefore did not validate the combined package scope"
                ),
                "functional_rtl_root_cause_proven": False,
                "config_root_cause_proven": False,
            },
        },
        "result_conjunction": {
            "compile": False,
            "simulator_started": False,
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
        "blocker_delta": {
            "closed": [
                "B_CONV_NATIVE_P19B_FORMAL_RETURN_RECEIPT",
                "B_CONV_NATIVE_P19B_TRANSPORT_SOURCE_RESET_INSTALL_IDENTITY",
            ],
            "opened": [
                "B_CONV_NATIVE_P19B_PACKAGE_LOCAL_OBSERVER_SCOPE_COMPILE_ESCAPE"
            ],
            "preserved": [
                "B_CONV_NATIVE_POST_PEKEEP3_D_FLOW_FIRST_DIVERGENCE_UNKNOWN",
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN",
                "B_CONV_NATIVE4_E3_E4_E5_UNPROVEN",
            ],
        },
        "successor": {
            "required": valid,
            "fresh_identity": True,
            "highest_information_scope": (
                "replace only the three imported-tail observer control/file "
                "symbols with the exact p19b module-scope n4d symbols; freeze "
                "all payload, config, numeric, golden, timeout and functional RTL"
            ),
            "server_action": False,
        },
        "current_rule_receipts": {
            path: {
                "bytes": (ROOT / path).stat().st_size,
                "sha256": sha256(ROOT / path),
            }
            for path in RULE_PATHS
        },
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-SERVER-PACKAGE-REPEAT-EXECUTION-EXACT-OWNED-RESET-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
            ],
            "delta": None,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise AnalysisError(f"refusing to overwrite formal analysis: {OUTPUT}")
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {"status": result["status"], "valid": valid, "output": str(OUTPUT)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
