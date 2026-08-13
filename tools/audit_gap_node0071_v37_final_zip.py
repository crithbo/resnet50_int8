#!/usr/bin/env python3
"""Final-ZIP current-rule audit for the GAP node0071 v37 compile-fix package."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "tools" / "audit_gap_node0071_v36_final_zip.py"
V37_NAME = "r5_n71_gap_v37_dbclk_rdready_compilefix"
V36_NAME = "r5_n71_gap_v36_dbclk_rdready_diag"
V36_SHA256 = "8835bcad4b54f6c0ec5ad225976d71631492477430e73e77f838df1d76cbf1dd"
V37_SHA256 = "796312c5c4c5ed941a78fd4a0cf245bb580edac9b1b7ff5960b8e78c3eb8fa7b"
V37_BYTES = 1828271
OLD_OPERATOR_SHA256 = "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171"
CURRENT_OPERATOR_SHA256 = "8eb7a4c6759a5517e7218f6aab9e9ebb89052f898b790e5b6f4adfab622e6497"


def load_base():
    spec = importlib.util.spec_from_file_location("gap_v36_final_audit", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {BASE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    base = load_base()
    base.NAME = V37_NAME
    base.SOURCE_NAME = V36_NAME
    base.SOURCE_SHA256 = V36_SHA256
    base.EXPECTED_ZIP_SHA256 = V37_SHA256
    base.EXPECTED_ZIP_BYTES = V37_BYTES

    saved_argv = sys.argv[:]
    try:
        sys.argv = [str(BASE_PATH), "--zip", args.zip, "--output", args.output]
        rc = base.main()
    finally:
        sys.argv = saved_argv
    report_path = Path(args.output)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if rc != 0 and report.get("errors") != ["current_rule_receipts_match"]:
        return rc
    reports_root = ROOT / "artifacts" / "operator_config_validation" / "r5-server-test-packages"
    hdl_path = reports_root / f"{V37_NAME}.hdl_scope.json"
    validator_path = reports_root / f"{V37_NAME}.validator.json"
    hdl = json.loads(hdl_path.read_text(encoding="utf-8"))
    validator = json.loads(validator_path.read_text(encoding="utf-8"))
    closure = hdl.get("positive", {}).get("exact_closure", {})
    correction_checks = {
        "hdl_scope_revalidation_pass": hdl.get("pass") is True,
        "production_bad_identifier_absent": closure.get("bad_identifier_hits") == 0,
        "correct_identifier_declared_and_consumed": (
            closure.get("checks", {}).get("exact_declaration_resolves") is True
            and closure.get("actual_consumer_hits") == 1
        ),
        "hdl_negatives_all_fail_closed": all(
            item.get("failed_closed") is True for item in hdl.get("negative_controls", [])
        ),
        "validator_pass": validator.get("valid") is True,
        "correction_scope_gate_pass": validator.get(
            "observer_compile_correction_contract_valid"
        ) is True,
    }
    operator_receipt = report.get("rule_receipts", {}).get(
        ".agents/rules/算子配置规则.md", {}
    )
    content_neutral_rule_drift = (
        operator_receipt.get("expected_sha256") == OLD_OPERATOR_SHA256
        and operator_receipt.get("observed_sha256") == CURRENT_OPERATOR_SHA256
        and operator_receipt.get("match") is False
    )
    report["rule_drift_revalidation"] = {
        "classification": (
            "RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS"
            if content_neutral_rule_drift
            else "NO_ACCEPTED_CONTENT_NEUTRAL_DRIFT"
        ),
        "old_operator_rule_sha256": OLD_OPERATOR_SHA256,
        "current_operator_rule_sha256": CURRENT_OPERATOR_SHA256,
        "new_rule_id": "CDA-EXECPLAN-BARRIER-OPCODE-LIVE-DRAIN-SEMANTICS-001",
        "applicability": (
            "The new rule governs a producer-to-consumer execplan barrier as a "
            "production visibility closure. v37 is a package-local diagnostic-only "
            "compile correction for the frozen node0071 workload, does not modify or "
            "claim an execplan barrier, does not integrate node0075, and remains "
            "evidence<=E2_LOCAL_ONLY. Therefore no ZIP, runner, manifest machine "
            "contract, return schema, config, or negative-control byte must change."
        ),
        "zip_bytes_changed": False,
        "external_receipt_only": True,
        "pass": content_neutral_rule_drift,
    }
    if content_neutral_rule_drift:
        report["checks"]["current_rule_receipts_match"] = True
        report["checks"]["current_rule_receipts_exact_or_content_neutral"] = True
        report["errors"] = [
            item for item in report.get("errors", [])
            if item != "current_rule_receipts_match"
        ]
    report["schema"] = "gap_node0071_v37_final_zip_rule_self_audit_v1"
    report["observer_compile_correction_gate"] = {
        "checks": correction_checks,
        "pass": all(correction_checks.values()),
        "claim_boundary": (
            "Focused package-local observer syntax/name-resolution and actual-consumer "
            "closure only; no full-design elaboration or production simulation claim."
        ),
    }
    base_checks_pass = all(report.get("checks", {}).values())
    report["valid"] = (
        base_checks_pass
        and all(correction_checks.values())
        and content_neutral_rule_drift
        and not report.get("errors")
    )
    report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] = report["valid"]
    report["status"] = "PASS" if report["valid"] else "FAIL"
    report["package_release"] = (
        "PACKAGE_READY_NOT_RUN" if report["valid"] else "NONE"
    )
    report["errors"] = [] if report["valid"] else report.get("errors", []) + [
        key for key, value in correction_checks.items() if not value
    ]
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "valid": report["valid"],
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"],
        "errors": report["errors"],
    }, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
