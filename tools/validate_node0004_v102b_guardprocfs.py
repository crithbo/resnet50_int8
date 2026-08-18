#!/usr/bin/env python3
"""Fail closed on canonical procfs identity and failure-handoff regressions."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v102b_lcdup_guardprocfs"
TRANSITIONAL = "r5_n4_hw_v101b_lcdup_guardprocfix"
CANONICAL_GUARD = ROOT / "tools/server_observer_operational_guard_v2.py"
CANONICAL_VALIDATOR = ROOT / "tools/validate_server_observer_operational_guard_v2.py"
FAILURE_SCHEMA = ROOT / "schemas/server_observer_operational_failure_handoff_v1.schema.json"
FAILURE_FIXTURE = ROOT / "fixtures/server_observer_operational_guard_live_tree_v2/positive_failure_handoff.json"
ACTIVATION = ROOT / "outputs/observer_operational_guard_process_identity_runtime_budget_v3/CANONICAL_GUARD_PROCESS_IDENTITY_ACTIVATION_RECEIPT.json"
REGISTRY = ROOT / "contracts/server_package_build_gate_registry_v1.json"


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def check(
    guard: bytes,
    validator: bytes,
    schema: bytes,
    fixture_bytes: bytes,
    activation: bytes,
    registry: bytes,
    runner: str,
    allow: dict[str, Any],
    manifest: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    exact = (
        (guard, CANONICAL_GUARD.read_bytes(), "canonical guard"),
        (validator, CANONICAL_VALIDATOR.read_bytes(), "canonical guard validator"),
        (schema, FAILURE_SCHEMA.read_bytes(), "failure handoff schema"),
        (fixture_bytes, FAILURE_FIXTURE.read_bytes(), "failure handoff fixture"),
        (activation, ACTIVATION.read_bytes(), "activation receipt"),
        (registry, REGISTRY.read_bytes(), "current build-gate registry"),
    )
    for actual, expected, label in exact:
        if actual != expected:
            errors.append(f"{label} is not byte-exact current canonical")
    guard_text = guard.decode("utf-8", errors="replace")
    for token in (
        "PROCFS_NO_CHILD_ENUMERATOR", "start_time_ticks", "pid_reuse_protection",
        "def ps_table(proc_root", "def identity_matches(", "def owned_processes(",
    ):
        if token not in guard_text:
            errors.append(f"canonical process identity token absent: {token}")
    if 'subprocess.Popen(["ps"' in guard_text or "enumerator_pid = process.pid" in guard_text:
        errors.append("transitional subprocess-backed process enumeration remains")
    for token in (
        "write_failure_handoff", "validate-failure-handoff", "same_basename_overwrite",
        "prior_published_returns_preserved", "RETURN_PRESERVED_AFTER_FINALIZATION_GUARD_FAILURE",
        "finalization_guard_ok", "durable_ok", "cleanup_ok", "FAILURE_HANDOFF_RECEIPT.json",
    ):
        if token not in runner:
            errors.append(f"runner process/failure-handoff token absent: {token}")
    if 'rm -f "$return_zip"' in runner:
        errors.append("same-basename formal return deletion remains reachable")
    external = allow.get("external_receipts", [])
    for token in ("FAILURE_HANDOFF_RECEIPT.json", "FAILURE_HANDOFF_VALIDATION.json"):
        if not any(isinstance(item, str) and token in item for item in external):
            errors.append(f"external failure handoff receipt declaration absent: {token}")
    if manifest.get("activation_epoch") != "observer-guard-process-identity-v3":
        errors.append("manifest activation epoch differs")
    if manifest.get("observer_only_semantic_version") != 5:
        errors.append("manifest observer-only semantic version differs")
    if manifest.get("canonical_guard_sha256") != digest(CANONICAL_GUARD.read_bytes()):
        errors.append("manifest canonical guard SHA differs")
    model = manifest.get("process_identity_model", {})
    if model != {
        "snapshot_backend": "PROCFS_NO_CHILD_ENUMERATOR",
        "identity_fields": ["pid", "start_time_ticks"],
        "pid_reuse_protection": True,
        "real_descendants_preserved": True,
    }:
        errors.append("manifest process identity model differs")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    prefix = PACKAGE + "/"
    names = {
        "guard": "package_tools/server_observer_operational_guard_v2.py",
        "validator": "package_tools/validate_server_observer_operational_guard_v2.py",
        "schema": "schemas/server_observer_operational_failure_handoff_v1.schema.json",
        "fixture": "receipts/observer_operational_failure_handoff_positive_fixture.json",
        "activation": "receipts/CANONICAL_GUARD_PROCESS_IDENTITY_ACTIVATION_RECEIPT.json",
        "registry": "receipts/server_package_build_gate_registry_v1.json",
        "runner": "PREPARE_AND_RUN.sh",
        "allow": "RETURN_ALLOWLIST.json",
        "manifest": "package_manifest.json",
    }
    with zipfile.ZipFile(args.zip) as archive:
        raw = {key: archive.read(prefix + relative) for key, relative in names.items()}
    fixture = json.loads(raw["fixture"])
    allow = json.loads(raw["allow"])
    manifest = json.loads(raw["manifest"])
    runner = raw["runner"].decode("utf-8")
    errors = check(raw["guard"], raw["validator"], raw["schema"], raw["fixture"], raw["activation"], raw["registry"], runner, allow, manifest)

    spec = importlib.util.spec_from_file_location("guard_validator", CANONICAL_VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load canonical guard validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fixture_report = module.validate_failure_handoff(fixture)
    if fixture_report.get("pass") is not True:
        errors.append("canonical positive failure-handoff fixture did not validate")

    controls: list[dict[str, Any]] = []
    transitional_path = ROOT / "outputs/conv_node0004_v101b_lcdup_guardprocfix_release1/build" / TRANSITIONAL / "package_tools/server_observer_operational_guard_v2.py"
    transitional_errors = check(transitional_path.read_bytes(), raw["validator"], raw["schema"], raw["fixture"], raw["activation"], raw["registry"], runner, allow, manifest)
    controls.append({"control": "restore_transitional_ps_guard", "pass": any("canonical guard" in item for item in transitional_errors), "errors": transitional_errors})
    no_identity = raw["guard"].replace(b"start_time_ticks", b"start_time_tick_x")
    identity_errors = check(no_identity, raw["validator"], raw["schema"], raw["fixture"], raw["activation"], raw["registry"], runner, allow, manifest)
    controls.append({"control": "remove_pid_start_time_identity", "pass": any("canonical guard" in item or "start_time_ticks" in item for item in identity_errors), "errors": identity_errors})
    no_overwrite = runner.replace("RETURN_PRESERVED_AFTER_FINALIZATION_GUARD_FAILURE", "RETURN_REPLACED_AFTER_FAILURE")
    overwrite_errors = check(raw["guard"], raw["validator"], raw["schema"], raw["fixture"], raw["activation"], raw["registry"], no_overwrite, allow, manifest)
    controls.append({"control": "remove_no_overwrite_marker", "pass": any("RETURN_PRESERVED" in item for item in overwrite_errors), "errors": overwrite_errors})
    premature = json.loads(json.dumps(fixture))
    premature["finalization_guard_receipt_valid"] = False
    controls.append({"control": "cleanup_without_valid_finalization", "pass": module.validate_failure_handoff(premature).get("pass") is False})
    duplicate = json.loads(json.dumps(fixture))
    duplicate["published_returns"][0]["path"] = duplicate["published_returns"][1]["path"]
    controls.append({"control": "same_basename_replacement", "pass": module.validate_failure_handoff(duplicate).get("pass") is False})
    if not all(item["pass"] for item in controls):
        errors.append("one or more canonical process/failure-handoff negative controls did not fail closed")
    report = {
        "schema": "node0004-v102b-guardprocfs-validation-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "canonical_guard_sha256": digest(CANONICAL_GUARD.read_bytes()),
        "activation_epoch": "observer-guard-process-identity-v3",
        "observer_only_semantic_version": 5,
        "failure_handoff_positive_fixture": fixture_report,
        "negative_controls": controls,
        "package_build_failure_rule_audit_continued": True,
        "claim_boundary": "Local canonical process identity/failure-handoff package gate only; no production Linux/VCS or DUT claim.",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
