from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

try:
    from tools.build_conv53_complete_json_regeneration_v1 import (
        ORIGIN_ENUM,
        OUTPUT_REL,
        PROJECT_RULE_RELS,
        sha256_file,
        write_json,
    )
except ModuleNotFoundError:
    from build_conv53_complete_json_regeneration_v1 import (
        ORIGIN_ENUM,
        OUTPUT_REL,
        PROJECT_RULE_RELS,
        sha256_file,
        write_json,
    )


REQUIRED_LEDGER_FIELDS = {
    "json_pointer",
    "target_value",
    "origin",
    "source",
    "applicability",
    "exactness_axes",
    "derivation",
    "current_consumer_equation",
    "status",
}
FORBIDDEN_NAMES = {
    "PREPARE_AND_RUN.sh",
    "SERVER_RESULT_GATE.json",
}
FORBIDDEN_SUFFIXES = {".zip"}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"root must be object: {path}")
    return value


def validate_payload(root: Path, output: Path) -> dict[str, Any]:
    errors: list[str] = []
    required = (
        "complete_json_manifest.json",
        "stage_catalog.json",
        "equivalence_classes.json",
        "field_provenance_ledger.json",
        "reference_applicability.json",
        "handler_capability.json",
        "current_test_diff.json",
        "report.json",
    )
    for name in required:
        if not (output / name).is_file():
            errors.append(f"missing required output: {name}")
    if errors:
        return {"valid": False, "errors": errors}

    manifest = load(output / "complete_json_manifest.json")
    catalog = load(output / "stage_catalog.json")
    classes = load(output / "equivalence_classes.json")
    ledger = load(output / "field_provenance_ledger.json")
    references = load(output / "reference_applicability.json")
    capability = load(output / "handler_capability.json")
    diff = load(output / "current_test_diff.json")
    report = load(output / "report.json")

    stages = catalog.get("stages", [])
    if len(stages) != 53:
        errors.append(f"stage count differs: {len(stages)}")
    ids = [item.get("identity", {}).get("hw_op_id") for item in stages]
    if len(set(ids)) != 53:
        errors.append("stage identities are not unique")
    if classes.get("class_count") != 20:
        errors.append(f"signature class count differs: {classes.get('class_count')}")
    members = [
        member
        for group in classes.get("classes", [])
        for member in group.get("member_hw_op_ids", [])
    ]
    if sorted(members) != sorted(ids):
        errors.append("equivalence-class member coverage differs")

    stage_ledgers = ledger.get("stages", [])
    if len(stage_ledgers) != 53:
        errors.append("ledger stage count differs")
    expected_pointers = ledger.get("target_schema_surface", {}).get("pointers", [])
    if len(expected_pointers) != len(set(expected_pointers)):
        errors.append("target schema pointers are not unique")
    computed_entries = 0
    computed_unresolved = 0
    for stage in stage_ledgers:
        entries = stage.get("entries", [])
        computed_entries += len(entries)
        pointers = [item.get("json_pointer") for item in entries]
        if pointers != expected_pointers:
            errors.append(f"pointer coverage differs: {stage.get('hw_op_id')}")
        for entry in entries:
            missing = REQUIRED_LEDGER_FIELDS - set(entry)
            if missing:
                errors.append(
                    f"ledger fields missing {stage.get('hw_op_id')}: {sorted(missing)}"
                )
                continue
            if entry["origin"] not in ORIGIN_ENUM:
                errors.append(f"invalid origin: {entry['origin']}")
            source = entry["source"]
            if not isinstance(source, dict) or not {
                "repository",
                "commit",
                "blob",
                "file",
                "pointer",
                "value",
            }.issubset(source):
                errors.append(
                    f"incomplete source identity: {stage.get('hw_op_id')} "
                    f"{entry['json_pointer']}"
                )
            if entry["applicability"].get("template_level") == "D":
                if entry["origin"] == "REFERENCE_EXACT":
                    errors.append("D reference was promoted to REFERENCE_EXACT")
            if entry["status"] in {
                "UNRESOLVED",
                "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
            }:
                computed_unresolved += 1
                if entry["target_value"] is not None:
                    errors.append("unresolved leaf has a target value")

    if computed_entries != ledger.get("coverage", {}).get("ledger_entry_count"):
        errors.append("ledger entry count differs")
    if computed_unresolved != ledger.get("coverage", {}).get(
        "unresolved_or_unknown_count"
    ):
        errors.append("unresolved count differs")
    complete_dir = output / "complete_json"
    materialized = list(complete_dir.iterdir()) if complete_dir.is_dir() else []
    if computed_unresolved and materialized:
        errors.append("strict JSON exists while unresolved leaves remain")
    if manifest.get("materialized_complete_json_count") != len(materialized):
        errors.append("materialized count differs")

    if references.get("classification", {}).get(
        "A_exact_replay_stage_count"
    ) != 0:
        errors.append("unexpected exact upstream Conv replay")
    if capability.get("generalization_claim") != (
        "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED"
    ):
        errors.append("capability conclusion differs")
    rows = capability.get("rows", [])
    upstream_rows = [
        row
        for row in rows
        if row.get("capability") == "pinned_upstream_conv_handler_registry"
    ]
    if len(upstream_rows) != 1 or upstream_rows[0].get("exact_replay"):
        errors.append("upstream Conv handler matrix differs")

    categories = {
        item["classification"] for item in diff.get("physical_leaf_comparison", [])
    }
    if not categories.issubset(
        {
            "same",
            "intentional_derivation",
            "suspected_current_defect",
            "new_candidate_defect",
            "dynamic-only",
        }
    ):
        errors.append("current diff category outside allowed set")
    if diff.get("summary", {}).get("suspected_current_defect_count") != 0:
        errors.append("unsupported current config defect claim")
    if report.get("claim_boundary", {}).get("server_package_generated_or_modified"):
        errors.append("server package mutation claimed")
    if report.get("coverage", {}).get("target_stage_count") != 53:
        errors.append("report stage coverage differs")

    for path in output.rglob("*"):
        if not path.is_file():
            continue
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden package/runtime asset: {path.relative_to(output)}")
        if "server runtime" in path.name.lower():
            errors.append(f"forbidden server runtime name: {path.relative_to(output)}")

    source_receipts = report.get("source_receipts", {})
    for relative in PROJECT_RULE_RELS:
        current = sha256_file(root / relative)
        recorded = source_receipts.get(relative.as_posix(), {}).get("sha256")
        if current != recorded:
            errors.append(f"current rule receipt differs: {relative.as_posix()}")

    return {
        "schema": "conv53-complete-json-regeneration-validation-v1",
        "valid": not errors,
        "error_count": len(errors),
        "errors": errors,
        "stage_count": len(stages),
        "signature_class_count": classes.get("class_count"),
        "ledger_entry_count": computed_entries,
        "unresolved_or_unknown_count": computed_unresolved,
        "materialized_complete_json_count": len(materialized),
        "strict_schema_consumer_validator": (
            "NOT_APPLICABLE_NO_MATERIALIZED_TARGET_JSON"
        ),
        "numeric_w3_golden_repeated": False,
        "server_package_generated_or_modified": False,
    }


def run_negative_controls(root: Path, output: Path) -> dict[str, Any]:
    ledger = load(output / "field_provenance_ledger.json")
    base = validate_payload(root, output)
    results: list[dict[str, Any]] = []

    def check(name: str, mutate: Any, expected_token: str) -> None:
        mutated = copy.deepcopy(ledger)
        mutate(mutated)
        errors: list[str] = []
        entry = mutated["stages"][0]["entries"][0]
        if REQUIRED_LEDGER_FIELDS - set(entry):
            errors.append("missing ledger fields")
        if entry.get("origin") not in ORIGIN_ENUM:
            errors.append("invalid origin")
        if (
            entry.get("applicability", {}).get("template_level") == "D"
            and entry.get("origin") == "REFERENCE_EXACT"
        ):
            errors.append("D reference promoted")
        if entry.get("status") in {
            "UNRESOLVED",
            "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
        } and entry.get("target_value") is not None:
            errors.append("unresolved target value")
        results.append(
            {
                "name": name,
                "fail_closed": expected_token in errors,
                "observed_errors": errors,
                "expected_error": expected_token,
            }
        )

    check(
        "unresolved_leaf_with_implicit_zero",
        lambda item: item["stages"][0]["entries"][0].update(target_value=0),
        "unresolved target value",
    )
    check(
        "project_D_reference_promoted_to_exact",
        lambda item: item["stages"][0]["entries"][0].update(
            origin="REFERENCE_EXACT",
            applicability={"template_level": "D"},
        ),
        "D reference promoted",
    )
    check(
        "missing_source_provenance_field",
        lambda item: item["stages"][0]["entries"][0].pop("source"),
        "missing ledger fields",
    )
    check(
        "invented_origin_enum",
        lambda item: item["stages"][0]["entries"][0].update(origin="NEAREST"),
        "invalid origin",
    )
    return {
        "schema": "conv53-complete-json-regeneration-negative-controls-v1",
        "positive_validation_pass": base["valid"],
        "negative_control_count": len(results),
        "all_negative_controls_fail_closed": all(
            item["fail_closed"] for item in results
        ),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = (
        args.output.resolve()
        if args.output
        else (root / OUTPUT_REL).resolve()
    )
    validation = validate_payload(root, output)
    negatives = run_negative_controls(root, output)
    write_json(output / "validation.json", validation)
    write_json(output / "negative_controls.json", negatives)
    print(json.dumps(validation, ensure_ascii=False, sort_keys=True))
    print(json.dumps(negatives, ensure_ascii=False, sort_keys=True))
    return 0 if validation["valid"] and negatives[
        "all_negative_controls_fail_closed"
    ] else 1


if __name__ == "__main__":
    raise SystemExit(main())
