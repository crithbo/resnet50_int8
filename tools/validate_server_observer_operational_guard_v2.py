#!/usr/bin/env python3
"""Fail-closed validator for operational guard v2 receipts and exit claims."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = Path(__file__).resolve().with_name("server_observer_operational_guard_v2.py")
SCHEMA_PATH = ROOT / "schemas" / "server_observer_operational_guard_receipt_v2.schema.json"
POLICY_SCHEMA_PATH = ROOT / "schemas" / "server_observer_operational_live_tree_policy_v2.schema.json"
HANDOFF_SCHEMA_PATH = ROOT / "schemas" / "server_observer_operational_failure_handoff_v1.schema.json"
SPEC = importlib.util.spec_from_file_location("server_observer_operational_guard_v2", RUNTIME_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot import operational guard v2 runtime")
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def schema_errors(document: Any, schema: Any) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema dependency is required and may not be skipped"]
    validator = jsonschema.Draft202012Validator(schema)
    errors: list[str] = []
    for item in sorted(validator.iter_errors(document), key=lambda error: list(error.path)):
        location = "/".join(str(part) for part in item.path) or "$"
        errors.append(f"schema:{location}: {item.message}")
    return errors


def validate_receipt(document: Any) -> dict[str, Any]:
    errors = schema_errors(document, load_json(SCHEMA_PATH))
    if isinstance(document, dict):
        errors.extend(RUNTIME.validate_receipt(document)["errors"])
    else:
        errors.append("receipt must be a JSON object")
    return {
        "schema": "server-observer-operational-guard-v2-validation-v1",
        "phase": "receipt",
        "errors": sorted(set(errors)),
        "pass": not errors,
        "claim_boundary": "Guard receipt integrity only; no production compile or DUT result claim.",
    }


def validate_policy(document: Any) -> dict[str, Any]:
    errors = schema_errors(document, load_json(POLICY_SCHEMA_PATH))
    return {
        "schema": "server-observer-operational-guard-v2-validation-v1",
        "phase": "live_tree_policy",
        "errors": sorted(set(errors)),
        "pass": not errors,
        "claim_boundary": "Package-local live-tree monitoring policy only; no server execution or DUT claim.",
    }


def validate_failure_handoff(document: Any) -> dict[str, Any]:
    errors = schema_errors(document, load_json(HANDOFF_SCHEMA_PATH))
    if isinstance(document, dict):
        returns = document.get("published_returns")
        returns = returns if isinstance(returns, list) else []
        paths = [item.get("path") for item in returns if isinstance(item, dict)]
        if len(paths) != len(returns) or len(paths) != len(set(paths)):
            errors.append("published return paths must be a unique exact set")
        selected = document.get("selected_formal_return")
        if isinstance(selected, dict):
            matches = [item for item in returns if item == selected]
            if len(matches) != 1:
                errors.append("selected formal return must match exactly one published identity")
        if document.get("same_basename_overwrite") is not False:
            errors.append("a published failure return must never be replaced at the same basename")
        if document.get("cleanup_executed") is True and (
            document.get("finalization_guard_receipt_valid") is not True
            or document.get("durable_return_receipt_valid") is not True
        ):
            errors.append("cleanup requires valid finalization guard and durable return receipts")
    else:
        errors.append("failure handoff must be a JSON object")
    return {
        "schema": "server-observer-operational-guard-v2-validation-v1",
        "phase": "failure_handoff",
        "errors": sorted(set(errors)),
        "pass": not errors,
        "claim_boundary": "Failure return identity and cleanup ordering only; no DUT result claim.",
    }


def classify_exit(exit_code: int, receipt_path: Path | None) -> dict[str, Any]:
    document = load_json(receipt_path) if receipt_path is not None and receipt_path.exists() else None
    classification = RUNTIME.classify_phase_exit(exit_code, document)
    errors: list[str] = []
    if document is not None:
        receipt_report = validate_receipt(document)
        errors.extend(receipt_report["errors"])
    if receipt_path is None or not receipt_path.exists():
        if classification.get("production_compile_error") is not False:
            errors.append("missing guard receipt cannot authorize production compile error")
        if exit_code == 2 and classification.get("classification") != "GUARD_RECEIPT_MISSING_INFRASTRUCTURE_FAILURE":
            errors.append("exit 2 without receipt must be infrastructure failure")
    return {
        "schema": "server-observer-operational-guard-v2-validation-v1",
        "phase": "exit_classification",
        "exit_code": exit_code,
        "receipt": str(receipt_path) if receipt_path is not None else None,
        "classification": classification,
        "errors": sorted(set(errors)),
        "pass": not errors,
        "claim_boundary": "Exit attribution only; missing/invalid guard evidence cannot be called a production compile error.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("validate-receipt")
    check.add_argument("--receipt", type=Path, required=True)
    policy = sub.add_parser("validate-policy")
    policy.add_argument("--policy", type=Path, required=True)
    handoff = sub.add_parser("validate-failure-handoff")
    handoff.add_argument("--handoff", type=Path, required=True)
    classify = sub.add_parser("classify-exit")
    classify.add_argument("--exit-code", type=int, required=True)
    classify.add_argument("--receipt", type=Path)
    for command in (check, policy, handoff, classify):
        command.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "validate-receipt":
        report = validate_receipt(load_json(args.receipt))
    elif args.command == "validate-policy":
        report = validate_policy(load_json(args.policy))
    elif args.command == "validate-failure-handoff":
        report = validate_failure_handoff(load_json(args.handoff))
    else:
        report = classify_exit(args.exit_code, args.receipt)
    payload = RUNTIME.canonical_bytes(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
    else:
        print(payload.decode("utf-8"), end="")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
