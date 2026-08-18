#!/usr/bin/env python3
"""Fail-closed semantic gate for incident-driven rule maintenance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CLASSES = {
    "RULE_SEMANTIC_ERROR",
    "RULE_SEMANTIC_OMISSION",
    "IMPLEMENTATION_ESCAPE",
    "SESSION_EXECUTION_NONCOMPLIANCE",
    "ONE_OFF_OR_DOMAIN_FAILURE",
}
PUBLIC_CHANGES = {"REPLACE_OR_NARROW", "MERGE_OMISSION", "DELETE_OR_ARCHIVE"}
HARD_GATE_CHANGES = {"FIX_IMPLEMENTATION", "ADD_OR_STRENGTHEN"}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_document(document: Any, schema: Any) -> list[str]:
    errors: list[str] = []
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema dependency is required; schema validation may not be skipped"]

    validator = jsonschema.Draft202012Validator(schema)
    for item in sorted(validator.iter_errors(document), key=lambda error: list(error.path)):
        location = "/".join(str(part) for part in item.path) or "$"
        errors.append(f"schema:{location}: {item.message}")
    if errors or not isinstance(document, dict):
        return errors

    classification = document.get("classification")
    action = document.get("action", {})
    audit = document.get("current_rule_audit", {})
    public_change = action.get("public_rule_change")
    hard_gate_change = action.get("hard_gate_change")
    workflow_change = action.get("workflow_change")
    causal_classes = action.get("causal_blocking_classes", [])
    consumers = action.get("affected_consumers", [])
    removed = action.get("replaced_or_removed_sections", [])
    controls_present = bool(document.get("positive_controls")) and bool(document.get("negative_controls"))

    if classification not in CLASSES:
        errors.append("classification is not recognized")
        return errors

    if classification == "RULE_SEMANTIC_ERROR":
        if audit.get("semantic_coverage") != "INCORRECT":
            errors.append("semantic error requires semantic_coverage=INCORRECT")
        if public_change not in {"REPLACE_OR_NARROW", "DELETE_OR_ARCHIVE"}:
            errors.append("semantic error must replace/narrow or delete/archive the wrong rule")
        if not removed:
            errors.append("semantic error must identify replaced or removed text")
    elif classification == "RULE_SEMANTIC_OMISSION":
        if audit.get("semantic_coverage") != "MISSING":
            errors.append("semantic omission requires semantic_coverage=MISSING")
        if public_change not in {"MERGE_OMISSION", "REPLACE_OR_NARROW"}:
            errors.append("semantic omission must merge into or replace the unique owner rule")
    elif classification == "IMPLEMENTATION_ESCAPE":
        if audit.get("semantic_coverage") != "COVERED" or audit.get("implementation_coverage") != "ESCAPED":
            errors.append("implementation escape requires covered semantics and escaped implementation")
        if public_change != "NONE":
            errors.append("implementation escape must not add or rewrite synonymous public semantics")
        if hard_gate_change not in HARD_GATE_CHANGES:
            errors.append("implementation escape must repair or strengthen the machine hard gate")
    elif classification == "SESSION_EXECUTION_NONCOMPLIANCE":
        if public_change != "NONE":
            errors.append("session execution noncompliance must not change public semantics")
        if workflow_change != "SKILL_OR_HANDOFF":
            errors.append("session execution noncompliance must repair the Skill or handoff workflow")
        if hard_gate_change != "NONE" and (not causal_classes or not consumers):
            errors.append("a new session hard gate requires causal blocking class and actual consumer")
    elif classification == "ONE_OFF_OR_DOMAIN_FAILURE":
        if public_change != "NONE" or hard_gate_change != "NONE":
            errors.append("one-off/domain failures stay with the owner and do not change public rule or gate")
        if workflow_change not in {"NONE", "OWNER_LOCAL_FIX"}:
            errors.append("one-off/domain failure may only select no workflow change or owner-local fix")

    if public_change in PUBLIC_CHANGES and not controls_present:
        errors.append("public semantic changes require positive and negative controls")
    if hard_gate_change in HARD_GATE_CHANGES:
        if not controls_present:
            errors.append("hard-gate changes require positive and negative controls")
        if not causal_classes or not consumers:
            errors.append("blocking hard-gate changes require causal class and affected consumer")
    if public_change == "NONE" and removed:
        errors.append("removed rule sections require an explicit public rule change")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "schemas"
        / "rule_maintenance_incident_adjudication_v1.schema.json",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    try:
        document = _load_json(args.input)
        schema = _load_json(args.schema)
        errors = validate_document(document, schema)
    except Exception as exc:
        errors = [f"input/schema unreadable: {exc}"]

    report = {
        "schema_id": "rule-maintenance-incident-adjudication-validation-v1",
        "input": str(args.input),
        "schema": str(args.schema),
        "pass": not errors,
        "classification": document.get("classification") if isinstance(locals().get("document"), dict) else None,
        "errors": errors,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
