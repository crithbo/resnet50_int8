from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5_complete_json_regeneration_v1"
    / "requantize_uint8"
)
ALLOWED_ORIGINS = {
    "REFERENCE_EXACT",
    "MODEL_DERIVED",
    "RTL_DERIVED",
    "ENCODER_DERIVED",
    "ADDRESS_PLANNER_DERIVED",
    "SCHEDULE_DERIVED",
    "EXPLICIT_DISABLED",
    "UNRESOLVED",
}
FORBIDDEN_NAMES = {"PREPARE_AND_RUN.sh"}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(out: Path) -> dict[str, Any]:
    errors: list[str] = []
    required = [
        "complete_json/index.json",
        "stage_inventory.json",
        "field_provenance_ledger.json",
        "reference_applicability.json",
        "handler_capability.json",
        "current_test_diff.json",
        "validation/strict_schema_consumer_formula.json",
        "validation/negative_controls.json",
        "report.json",
    ]
    for relative in required:
        if not (out / relative).is_file():
            errors.append(f"missing:{relative}")

    if errors:
        return {"schema": "requant-complete-json-delivery-validation-v1", "errors": errors}

    index = _load(out / "complete_json" / "index.json")
    inventory = _load(out / "stage_inventory.json")
    ledger = _load(out / "field_provenance_ledger.json")
    references = _load(out / "reference_applicability.json")
    handler = _load(out / "handler_capability.json")
    current = _load(out / "current_test_diff.json")
    strict = _load(out / "validation" / "strict_schema_consumer_formula.json")
    negative = _load(out / "validation" / "negative_controls.json")
    report = _load(out / "report.json")

    if index.get("materialized_count") != 0 or index.get("files") != []:
        errors.append("complete_json index must contain no emitted target JSON")
    complete_files = sorted(
        path.name for path in (out / "complete_json").iterdir() if path.is_file()
    )
    if complete_files != ["index.json"]:
        errors.append(f"unexpected complete_json files:{complete_files}")
    if len(inventory.get("stages", [])) != 54:
        errors.append("stage inventory must cover exactly 54 stages")
    if len(ledger.get("stages", [])) != 54:
        errors.append("ledger must cover exactly 54 stages")
    if report.get("coverage", {}).get("exact_materialized_consumer_signature_class_count") != 54:
        errors.append("exact materialized-consumer signatures must be 54/54")
    if references.get("counts", {}).get("A") != 0 or references.get("counts", {}).get("B") != 0:
        errors.append("no A/B target reference is allowed")
    if not handler.get("facts", {}).get("placeholder_docstring_present"):
        errors.append("placeholder handler evidence missing")
    if not handler.get("facts", {}).get("remapper_registry_explicit_negative_present"):
        errors.append("remapper negative registry evidence missing")
    if current.get("current_plan_state") != "PLAN_COHERENCE_DRIFT / NO_CURRENT_RELEASE":
        errors.append("current plan boundary not preserved")
    if current.get("categories", {}).get("suspected_current_defect") != []:
        errors.append("unproven current config defect must remain empty")
    if strict.get("target_strict_json", {}).get("status") != "NOT_RUN_NO_TARGET_JSON_EMITTED":
        errors.append("target strict validator boundary incorrect")
    if not negative.get("all_fail_closed"):
        errors.append("negative controls did not all fail closed")

    for stage in ledger.get("stages", []):
        if stage.get("materialized_target_json") is not None:
            errors.append(f"{stage.get('request_id')}: unexpectedly materialized")
        if stage.get("target_required_unresolved_count", 0) <= 0:
            errors.append(f"{stage.get('request_id')}: missing unresolved fail-closed leaf")
        for section_name in (
            "target_requirement_ledger",
            "reference_leaf_applicability_ledger",
        ):
            for row in stage.get(section_name, []):
                missing = {
                    "json_pointer",
                    "target_value",
                    "origin",
                    "source",
                    "applicability",
                    "exactness_axes",
                    "derivation",
                    "current_consumer_equation",
                    "status",
                } - set(row)
                if missing:
                    errors.append(
                        f"{stage.get('request_id')}:{section_name}:missing:{sorted(missing)}"
                    )
                    continue
                if row["origin"] not in ALLOWED_ORIGINS:
                    errors.append(
                        f"{stage.get('request_id')}:{row['json_pointer']}:bad origin"
                    )
                if row["target_value"] == 0 and row.get("target_value_state") not in {
                    "EXPLICIT_ZERO",
                    "TARGET_REQUIRED_DERIVED",
                }:
                    errors.append(
                        f"{stage.get('request_id')}:{row['json_pointer']}:implicit zero"
                    )
        if stage.get("target_required_unresolved_count", 0) > 0 and stage.get(
            "materialized_target_json"
        ):
            errors.append(f"{stage.get('request_id')}: unresolved stage emitted")

    for path in out.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() == ".zip":
            errors.append(f"forbidden ZIP:{path.relative_to(out)}")
        if path.name in FORBIDDEN_NAMES:
            errors.append(f"forbidden runtime:{path.relative_to(out)}")
        if "server" in path.name.lower() and path.name != "current_test_diff.json":
            errors.append(f"forbidden server artifact:{path.relative_to(out)}")

    return {
        "schema": "requant-complete-json-delivery-validation-v1",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "summary": {
            "stage_count": len(inventory.get("stages", [])),
            "ledger_stage_count": len(ledger.get("stages", [])),
            "materialized_json_count": index.get("materialized_count"),
            "negative_controls_all_fail_closed": negative.get("all_fail_closed"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = _validate(OUT)
    rendered = json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
