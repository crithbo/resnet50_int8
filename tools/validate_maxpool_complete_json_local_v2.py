from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.operator_config_validator import OperatorConfigValidator
from tools.build_maxpool_complete_json_public_contract_v1 import (
    ADDRESS_POINTERS,
    CANDIDATE,
    CONTRACT,
    CURRENT_CONFIG,
    CURRENT_DIFF,
    FAMILY_SET,
    GA_INBUFFER,
    HANDLER,
    LEDGER,
    OUT,
    PADDING_POINTER,
    RD_DATA,
    REFERENCE,
    SOURCE,
    SOURCE_BLOB,
    SOURCE_SHA,
    leaves,
    read_json,
    sha,
    write_json,
)

SCHEMA_BINDINGS = {
    "candidate_contract.json": (
        ROOT / "schemas/operator_config_complete_json_candidate_v1.schema.json"
    ),
    "field_provenance_ledger.json": (
        ROOT / "schemas/operator_config_field_provenance_ledger_v1.schema.json"
    ),
    "handler_capability.json": (
        ROOT / "schemas/operator_config_handler_capability_v1.schema.json"
    ),
    "current_test_diff.json": (
        ROOT / "schemas/operator_config_current_test_diff_v1.schema.json"
    ),
    "family_set.json": (
        ROOT / "schemas/operator_config_complete_json_family_set_v1.schema.json"
    ),
}


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def leaf_map(value: Any) -> dict[str, Any]:
    return dict(leaves(value))


def validate_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    candidate = bundle["candidate"]
    source = bundle["source"]
    current = bundle["current"]
    ledger = bundle["ledger"]
    handler = bundle["handler"]
    current_diff = bundle["current_diff"]
    reference = bundle["reference"]
    family_set = bundle["family_set"]

    candidate_leaves = leaf_map(candidate)
    source_leaves = leaf_map(source)
    current_leaves = leaf_map(current)
    check(
        set(candidate_leaves) == set(source_leaves) == set(current_leaves),
        "source/candidate/current leaf exact-set mismatch",
    )
    entries = ledger["entries"]
    check(len(entries) == len(candidate_leaves), "ledger leaf count mismatch")
    by_pointer = {item["json_pointer"]: item for item in entries}
    check(set(by_pointer) == set(candidate_leaves), "ledger pointer exact-set mismatch")
    for pointer, value in candidate_leaves.items():
        item = by_pointer[pointer]
        check(item["target_value"] == value, f"ledger target mismatch: {pointer}")
        check(item["status"] == "RESOLVED", f"unresolved leaf: {pointer}")
        if pointer in ADDRESS_POINTERS:
            check(
                item["origin"] == "ADDRESS_PLANNER_DERIVED",
                f"address origin mismatch: {pointer}",
            )
        elif pointer == PADDING_POINTER:
            check(item["origin"] == "RTL_DERIVED", "padding origin mismatch")
            check(value == 0, "strict MaxPool padding is not explicit zero")
        else:
            check(item["origin"] == "REFERENCE_EXACT", f"origin mismatch: {pointer}")
            check(value == source_leaves[pointer], f"exact source mismatch: {pointer}")
            source_info = item["source"]
            check(source_info["file_sha256"] == SOURCE_SHA, "source SHA mismatch")
            check(source_info["blob_oid"] == SOURCE_BLOB, "source blob mismatch")

    check(
        candidate_leaves["/stream_engine/stream0/base_addr"] == "0x0",
        "input planner address mismatch",
    )
    check(
        candidate_leaves["/stream_engine/stream1/base_addr"] == "0x31000",
        "output planner address mismatch",
    )
    changed = {
        pointer
        for pointer, value in candidate_leaves.items()
        if value != current_leaves[pointer]
    }
    check(changed == {PADDING_POINTER}, "candidate/current diff is not one leaf")
    diff_entries = {item["json_pointer"]: item for item in current_diff["entries"]}
    check(set(diff_entries) == set(candidate_leaves), "current diff coverage mismatch")
    check(
        diff_entries[PADDING_POINTER]["classification"]
        == "SUSPECTED_CURRENT_DEFECT",
        "padding current-diff classification mismatch",
    )
    check(
        sum(
            item["classification"] == "SAME"
            for item in current_diff["entries"]
        )
        == len(candidate_leaves) - 1,
        "current SAME count mismatch",
    )
    check(
        handler["capabilities"]["exact_replay"]["supported"] is True,
        "exact replay capability missing",
    )
    check(
        handler["capabilities"]["address"]["supported"] is True,
        "address patch capability missing",
    )
    for axis in ("shape", "dtype", "qparam", "layout", "cross_stage_schedule"):
        check(
            handler["capabilities"][axis]["supported"] is False,
            f"handler overclaims {axis}",
        )
    class_a = reference["reference_classes"]["A"]
    check(len(class_a) == 1, "class-A authority count mismatch")
    check(class_a[0]["path"] == SOURCE.relative_to(ROOT).as_posix(), "A path mismatch")
    check(class_a[0]["blob_oid"] == SOURCE_BLOB, "A blob mismatch")
    check(
        family_set["target_hw_op_types"] == ["MaxPoolUint8"],
        "family hw type mismatch",
    )
    check(
        len(family_set["candidate_contracts"]) == 1,
        "family candidate count mismatch",
    )
    check(family_set["no_config_stages"] == [], "unexpected no-config stage")

    rd_text = RD_DATA.read_text(encoding="utf-8")
    check(
        "rd_chl_queue_rd_padding_mask[PADDING_INDEX] ? mse_padding_reg_value"
        in rd_text,
        "current RTL padding substitution equation absent",
    )
    ga_text = GA_INBUFFER.read_text(encoding="utf-8")
    check("alu_is_int32" in ga_text and "alu_is_fp32" in ga_text, "GA flow evidence absent")
    pipeline_lines = [
        line
        for line in ga_text.splitlines()
        if "alu_pipeline0_bp_post" in line
    ]
    check(pipeline_lines, "GA pipeline0 equation absent")
    check(
        not any("alu_is_int8" in line for line in pipeline_lines),
        "GA pipeline0 now contains INT8 branch; blocker receipt is stale",
    )
    forbidden = [
        path.relative_to(OUT).as_posix()
        for path in OUT.rglob("*")
        if path.is_file()
        and (
            path.name.endswith(".zip")
            or path.name.endswith(".zip.sha256")
            or path.name
            in {
                "PREPARE_AND_RUN.sh",
                "TEST_PACKAGE_MANIFEST.json",
                "SERVER_RESULT_GATE.json",
            }
        )
    ]
    check(not forbidden, f"forbidden server-package outputs: {forbidden}")
    shadow = OperatorConfigValidator().validate_file(CANDIDATE).to_dict()
    check(shadow["valid"] is True, "strict operator-config validation failed")
    ga_int8_max = shadow.get("facts", {}).get("ga_int8_max")
    expected_ga_int8_max = {
        "rule_results": {
            "CDA-GA-INT8-MAX-NUMERIC-001": "LOCAL_SOURCE_PASS",
            "CDA-GA-INT8-MAX-PIPE-001": "CONTRADICTED",
        },
        "numeric_classification": "LOCAL_SOURCE_PASS",
        "numeric_equation": "unsigned bytewise max(A,C)",
        "pipeline_classification": "CONTRADICTED",
        "pipeline0_accepts_second_item": False,
    }
    check(
        ga_int8_max == expected_ga_int8_max,
        "operator-config GA int8_max facts differ from current split rules",
    )
    return {
        "candidate_leaf_count": len(candidate_leaves),
        "reference_exact_count": sum(
            item["origin"] == "REFERENCE_EXACT" for item in entries
        ),
        "address_derived_count": sum(
            item["origin"] == "ADDRESS_PLANNER_DERIVED" for item in entries
        ),
        "rtl_derived_count": sum(item["origin"] == "RTL_DERIVED" for item in entries),
        "unresolved_count": 0,
        "candidate_current_diff_count": len(changed),
        "forbidden_outputs": forbidden,
        "shadow_validation": {
            "valid": shadow["valid"],
            "first_error": shadow["first_error"],
            "issue_count": len(shadow["issues"]),
            "metadata_coherence": {
                "field": "facts.ga_int8_max",
                "validator_value": ga_int8_max,
                "current_rule_value": expected_ga_int8_max["rule_results"],
                "coherent": True,
                "pipeline_failure_promoted_to_numeric_failure": False,
            },
        },
    }


def negative_controls(base: dict[str, Any]) -> list[dict[str, Any]]:
    controls: list[tuple[str, Callable[[dict[str, Any]], None]]] = []

    def delete_ledger(value: dict[str, Any]) -> None:
        value["ledger"]["entries"].pop()

    def unresolved_leaf(value: dict[str, Any]) -> None:
        value["ledger"]["entries"][0]["status"] = "UNRESOLVED"

    def mutate_exact_leaf(value: dict[str, Any]) -> None:
        value["candidate"]["dram_loop_configs"]["LC0"]["end"] += 1

    def restore_padding_null(value: dict[str, Any]) -> None:
        value["candidate"]["stream_engine"]["stream0"]["padding_reg_value"] = None

    def wrong_address(value: dict[str, Any]) -> None:
        value["candidate"]["stream_engine"]["stream0"]["base_addr"] = "0x10"

    def overclaim_shape(value: dict[str, Any]) -> None:
        value["handler"]["capabilities"]["shape"]["supported"] = True

    def promote_project_reference(value: dict[str, Any]) -> None:
        value["reference"]["reference_classes"]["A"][0]["path"] = (
            "configs/native_ndp_sim/"
            "maxpool_config_16_112_112_stride2_padding1_strict/config.json"
        )

    def drop_family_candidate(value: dict[str, Any]) -> None:
        value["family_set"]["candidate_contracts"] = []

    controls.extend(
        [
            ("delete_one_ledger_leaf", delete_ledger),
            ("mark_one_leaf_unresolved", unresolved_leaf),
            ("tamper_reference_exact_leaf", mutate_exact_leaf),
            ("restore_enabled_padding_to_null", restore_padding_null),
            ("tamper_planner_owned_address", wrong_address),
            ("overclaim_shape_generalization", overclaim_shape),
            ("promote_project_json_to_class_A", promote_project_reference),
            ("drop_family_stage_candidate", drop_family_candidate),
        ]
    )
    results: list[dict[str, Any]] = []
    for name, mutate in controls:
        value = deepcopy(base)
        mutate(value)
        try:
            validate_bundle(value)
        except Exception as error:
            results.append(
                {
                    "name": name,
                    "expected_exit": 1,
                    "observed_exit": 1,
                    "failed_closed": True,
                    "reason": str(error),
                }
            )
        else:
            results.append(
                {
                    "name": name,
                    "expected_exit": 1,
                    "observed_exit": 0,
                    "failed_closed": False,
                    "reason": "negative mutation was accepted",
                }
            )
    return results


def main() -> int:
    base = {
        "candidate": read_json(CANDIDATE),
        "source": read_json(SOURCE),
        "current": read_json(CURRENT_CONFIG),
        "ledger": read_json(LEDGER),
        "handler": read_json(HANDLER),
        "current_diff": read_json(CURRENT_DIFF),
        "reference": read_json(REFERENCE),
        "family_set": read_json(FAMILY_SET),
    }
    summary = validate_bundle(base)
    schema_validation = []
    for document_name, schema_path in SCHEMA_BINDINGS.items():
        document_path = OUT / document_name
        jsonschema.validate(read_json(document_path), read_json(schema_path))
        schema_validation.append(
            {
                "document": document_path.relative_to(ROOT).as_posix(),
                "document_sha256": sha(document_path),
                "schema": schema_path.relative_to(ROOT).as_posix(),
                "schema_sha256": sha(schema_path),
                "pass": True,
            }
        )
    controls = negative_controls(base)
    check(
        all(item["failed_closed"] for item in controls),
        "one or more negative controls did not fail closed",
    )
    report = {
        "schema": "maxpool_complete_json_local_validation_v2",
        "family": "maxpool_uint8",
        "status": "PASS",
        "summary": summary,
        "schema_validation": schema_validation,
        "all_public_schemas_pass": True,
        "negative_controls": controls,
        "negative_control_count": len(controls),
        "all_negative_controls_failed_closed": True,
        "candidate_contract": {
            "path": CONTRACT.relative_to(ROOT).as_posix(),
            "sha256": sha(CONTRACT),
        },
        "family_set": {
            "path": FAMILY_SET.relative_to(ROOT).as_posix(),
            "sha256": sha(FAMILY_SET),
        },
        "hard_boundary": {
            "mapping_generated": False,
            "bitstream_generated": False,
            "execplan_generated": False,
            "sca_generated": False,
            "server_package_generated": False,
        },
        "claim_boundary": (
            "JSON-only strict/schema/provenance/consumer-equation/current-diff "
            "validation. No downstream hardware artifact or dynamic claim."
        ),
        "errors": [],
    }
    write_json(OUT / "local_validation_report.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
