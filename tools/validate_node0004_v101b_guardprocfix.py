#!/usr/bin/env python3
"""Fail closed on the exact v100 guard/process/return regressions."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v101b_lcdup_guardprocfix"


def check(helper: str, runner: str, allow: dict) -> list[str]:
    errors: list[str] = []
    required_helper = (
        "enumerator_pid = process.pid",
        "if pid == enumerator_pid:",
        "continue",
    )
    for token in required_helper:
        if token not in helper:
            errors.append(f"guard self-enumerator exclusion absent: {token}")
    if 'rm -f "$return_zip" "$return_sha"; publish_minimal_return' in runner:
        errors.append("same-basename return replacement path remains")
    for token in (
        "RETURN_PRESERVED_AFTER_FINALIZATION_GUARD_FAILURE",
        "finalization_guard_ok=false",
        'd.get("pass") is True',
        "CLEANUP_BLOCKED_INVALID_FINALIZATION_GUARD",
    ):
        if token not in runner:
            errors.append(f"runner guard/cleanup token absent: {token}")
    required = allow.get("required", [])
    for basename in ("DURABLE_RETURN_RECEIPT.json", "POST_DURABLE_CLEANUP_RECEIPT.json"):
        if not any(isinstance(item, str) and item.endswith("/" + basename) for item in required):
            errors.append(f"operational receipt contract name absent from allowlist: {basename}")
    external = allow.get("external_receipts", [])
    if len(external) != 4:
        errors.append("external durable/cleanup receipt declaration is incomplete")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with zipfile.ZipFile(args.zip) as archive:
        helper_bytes = archive.read(f"{PACKAGE}/package_tools/server_observer_operational_guard_v2.py")
        runner_bytes = archive.read(f"{PACKAGE}/PREPARE_AND_RUN.sh")
        allow = json.loads(archive.read(f"{PACKAGE}/RETURN_ALLOWLIST.json"))
        provenance = json.loads(archive.read(f"{PACKAGE}/provenance/v100b_package_build_failure_rule_audit.json"))
    helper = helper_bytes.decode("utf-8")
    runner = runner_bytes.decode("utf-8")
    errors = check(helper, runner, allow)
    if hashlib.sha256(helper_bytes).hexdigest() != hashlib.sha256((ROOT / "tools/server_observer_operational_guard_v2.py").read_bytes()).hexdigest():
        errors.append("packaged guard helper differs from current local fixed helper")
    if provenance.get("rule_disposition") != "RULE_CONFIRMATION_NO_CHANGE__IMPLEMENTATION_AND_NEGATIVE_CONTROL_ESCAPE":
        errors.append("PACKAGE_BUILD_FAILURE_RULE_AUDIT continuation is absent")
    controls = []
    mutated_helper = helper.replace("if pid == enumerator_pid:\n            continue", "if False:\n            continue")
    helper_negative = check(mutated_helper, runner, allow)
    controls.append({"control": "remove_self_enumerator_exclusion", "pass": any("self-enumerator" in item for item in helper_negative), "errors": helper_negative})
    mutated_runner = runner.replace("RETURN_PRESERVED_AFTER_FINALIZATION_GUARD_FAILURE", "RETURN_REPLACED")
    runner_negative = check(helper, mutated_runner, allow)
    controls.append({"control": "remove_no_overwrite_marker", "pass": any("RETURN_PRESERVED" in item for item in runner_negative), "errors": runner_negative})
    mutated_cleanup = runner.replace("finalization_guard_ok=false", "finalization_guard_ok=true")
    cleanup_negative = check(helper, mutated_cleanup, allow)
    controls.append({"control": "default_cleanup_admission_true", "pass": any("finalization_guard_ok" in item for item in cleanup_negative), "errors": cleanup_negative})
    if not all(item["pass"] for item in controls):
        errors.append("one or more exact negative controls did not fail closed")
    report = {
        "schema": "node0004-v101b-guardprocfix-validation-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "negative_controls": controls,
        "package_build_failure_rule_audit_continued": True,
        "shared_adjudication_status": "WAIT_OPTIMIZER_MAINLINE_SHARED_AUDIT",
        "claim_boundary": "Local package/runtime implementation gate only; no real Linux/VCS, tuple10 or DUT claim.",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
