#!/usr/bin/env python3
"""Validate and adjudicate the formal native-four-lane p21 return."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

import analyze_conv_native_four_lane_0ccae916_p18_return as common


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p21_epochowner"
EXECUTION_ID = "r1786169058630848787_3994777"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads"
    r"\r5_n4_0cc_p21_epochowner_r1786169058630848787_3994777_return.zip"
)
SOURCE_ZIP = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE_ID}.zip"
)
RETURN_BYTES = 723_157
RETURN_SHA256 = "b40d518f9ba834dfd1452a7c658b498024be7083e25513bbb91a6426d41de7a9"
SOURCE_BYTES = 5_876_983
SOURCE_SHA256 = "cd78dd1aa2234bc12e4588b957fa900e71030486bd6eca4c315155451f631c8d"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p21_return_analysis/report_v2.json"
OBSERVER = "tb_probe/native_return_observer.svh"
BAD_IDENTIFIER = "return_obs_enabled"
GOOD_IDENTIFIER = "return_obs_eo_enabled"
BAD_LINE = 4640
EXPECTED_OBSERVER_SHA256 = "755ee7da53eb9550afaad604c4da5495cd071b26291ce76eb747d49506b0b527"
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
        item["path"]: {"size_bytes": item["size_bytes"], "sha256": item["sha256"]}
        for item in value[key]
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
    compile_log_raw = payloads["runs/compile/compile.log"].decode(errors="replace")
    compile_status = int(payloads["evidence/compile_exit_status.txt"].decode().strip())
    run_status = int(payloads["evidence/run_exit_status.txt"].decode().strip())
    signal_status = payloads["evidence/signal_status.txt"].decode().strip()
    observer_text = source_payloads[OBSERVER].decode()
    observer_lines = observer_text.splitlines()

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
        and publication["return_zip"] == f"/home/panqs/ndp/simresult/{RETURN_ZIP.name}"
    )

    error_patterns = re.findall(r"Error-\[[A-Z0-9_]+\]", compile_log)
    exact_compile_escape = (
        compile_status == 2
        and error_patterns == ["Error-[IND]"]
        and f"Identifier '{BAD_IDENTIFIER}' has not been declared yet." in compile_log
        and f"native_return_observer.svh, {BAD_LINE}" in compile_log
        and "1 error" in compile_log
        and "Error-[XMRE]" not in compile_log
        and f"Identifier '{BAD_IDENTIFIER}' has not been declared yet." in compile_log_raw
        and f"native_return_observer.svh, {BAD_LINE}" in compile_log_raw
    )
    source_escape = (
        common.digest(source_payloads[OBSERVER]) == EXPECTED_OBSERVER_SHA256
        and len(observer_lines) >= BAD_LINE
        and observer_lines[BAD_LINE - 1].strip() == f"if ({BAD_IDENTIFIER} && n4d_fd != 0) begin"
        and observer_text.count(f"bit {GOOD_IDENTIFIER};") == 1
        and observer_text.count(f"{GOOD_IDENTIFIER} = $test$plusargs(\"RETURN_OBS_EPOCH_OWNER\");") == 1
        and observer_text.count(f"if ({GOOD_IDENTIFIER} && n4d_fd != 0) begin") == 1
        and not re.search(rf"\b(?:bit|logic|integer)\s+{BAD_IDENTIFIER}\b", observer_text)
    )
    no_dynamic_epoch_ledger = (
        "runs/c0/sim.log" not in payloads
        and "runs/c0/return_observer.log" not in payloads
        and gate["production_rtl_identity"]["valid"] is False
        and gate["feature_binding_receipt"]["valid"] is False
        and public.get("valid") is False
        and buffer5.get("valid") is False
        and triggered.get("valid") is True
        and triggered.get("status") == "SIM_NOT_STARTED"
        and triggered["observer"]["present"] is False
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
        "compile_escape_exact": exact_compile_escape,
        "source_identifier_escape_exact": source_escape,
        "simulation_not_started_no_dynamic_ledger": no_dynamic_epoch_ledger,
    }
    valid = all(checks.values())

    result = {
        "schema": "conv-native-four-lane-0ccae916-p21-return-analysis-v1",
        "status": "P21_PACKAGE_LOCAL_OBSERVER_IDENTIFIER_ESCAPE_P22_REQUIRED" if valid else "RETURN_VALIDATION_FAILED",
        "valid": valid,
        "classification": "PACKAGE_LOCAL_OBSERVER_SCOPE_COMPILE_FAILURE_SIMULATION_NOT_STARTED" if valid else "RETURN_VALIDATION_FAILED",
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
            "observer": {"path": OBSERVER, "bytes": len(source_payloads[OBSERVER]), "sha256": common.digest(source_payloads[OBSERVER])},
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
            "signal_status": signal_status, "production_compile_started": local_status["production_compile_started"],
            "compile_succeeded": False, "dut_simulation_started": False,
            "actual_compile_identity_collected": False, "natural_terminal": False,
            "formal_D_payload_present": False,
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": "All package/path/install/observer preflights and the install-only/root-direct-set gates passed; the production VCS front-end reached the exact package-local epoch-owner observer.",
            "FIRST_DIVERGENCE": f"VCS rejected {OBSERVER}:{BAD_LINE}: the time-zero epoch-owner marker uses undeclared {BAD_IDENTIFIER} instead of the declared {GOOD_IDENTIFIER}.",
            "HANG_ROOT_CAUSE": {
                "status": "ROOT_UNIQUE_PACKAGE_LOCAL_IDENTIFIER_TYPO",
                "classification": "PACKAGE_LOCAL_OBSERVER_EPOCH_OWNER_ENABLE_IDENTIFIER_SCOPE_TYPO",
                "package_audit_escape": True,
                "functional_rtl_root_cause": False,
                "authorized_config_fix": None,
                "exact_fix": {"line": BAD_LINE, "from": BAD_IDENTIFIER, "to": GOOD_IDENTIFIER, "occurrences": 1},
            },
        },
        "epoch_owner_and_post_pekeep3_dflow": {
            "dynamic_ledger_present": False,
            "adjudication": "NOT_REACHED_PRODUCTION_COMPILE_FAILED",
            "held_levels_count_as_transactions": False,
        },
        "result_conjunction": {
            "compile": False, "simulator_started": False, "c0_slice_finish": False,
            "natural_terminal_27_of_27": False, "formal_D_320_of_320": False,
            "mismatch_zero_claim": False, "E3": False, "E4": False, "E5": False,
            "performance_claimed": False, "passed": False,
        },
        "blocker_delta": {
            "closed": ["B_CONV_NATIVE_P21_FORMAL_RETURN_RECEIPT"],
            "opened": ["B_CONV_NATIVE_P21_PACKAGE_LOCAL_EPOCH_OWNER_ENABLE_IDENTIFIER_SCOPE_ESCAPE"],
            "preserved": [
                "B_CONV_NATIVE_MSE4_PER_INPUT_EPOCH_OWNERSHIP_UNOBSERVED",
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN", "B_CONV_NATIVE4_E4_E5_UNPROVEN",
            ],
        },
        "successor": {
            "required": valid, "fresh_identity": True,
            "highest_information_scope": f"change only the one package-local actual-consumer token {BAD_IDENTIFIER} to {GOOD_IDENTIFIER}; add exact declaration/consumer positive compile and mutation-back negative; freeze all config/DUT/numeric payload",
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
                "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-RETURN-REPEATABLE-EXECUTION-IDENTITY-001",
            ],
            "delta": None,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise AnalysisError(f"refusing to overwrite formal analysis: {OUTPUT}")
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "valid": valid, "output": str(OUTPUT)}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
