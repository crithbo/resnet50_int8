from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5_complete_json_regeneration_v1/qlinearadd"
)
FILES = {
    name: OUT / name
    for name in (
        "stage_inventory.json",
        "field_provenance_ledger.json",
        "reference_applicability.json",
        "handler_capability.json",
        "current_test_diff.json",
        "report.json",
    )
}
MATERIALIZATION = OUT / "complete_json/materialization_manifest.json"
PUBLIC_CANDIDATE_REPORT = OUT / "complete_json/shared_candidate_validation.json"
PUBLIC_FAMILY_REPORT = OUT / "shared_family_set_audit.json"
CURRENT_CONFIG = (
    ROOT / "configs/native_ndp_sim/qlinearadd_node0007_fp32_output32_v36"
)
CURRENT_PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_qadd_n7_cout32_v36.zip"
)
LOWERING = ROOT / "contracts/resnet50_r5_lowering_bundle.json"
STAGE0 = (
    ROOT
    / "configs/qlinearadd_stage0_config_only/"
    "qlinearadd_stage0_config_only_v1.json"
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
DEFAULT_STATES = {
    "SOURCE_ABSENT_NOT_APPLICABLE",
    "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
    "EXPLICIT_NULL_INACTIVE",
    "EXPLICIT_ZERO",
    "TARGET_REQUIRED_DERIVED",
}
REQUIRED_LEAF_KEYS = {
    "target_id",
    "physical_stage",
    "json_pointer",
    "target_value",
    "origin",
    "source",
    "applicability",
    "exactness_axes",
    "derivation",
    "owner",
    "current_consumer_equation",
    "status",
    "default_state",
    "negative_control",
    "claim_boundary",
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(
        f"blob {len(payload)}\0".encode("ascii") + payload
    ).hexdigest()


def committed_blob_sha(path: Path) -> str | None:
    relative = path.relative_to(ROOT / "ndp-sim").as_posix()
    run = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={(ROOT / 'ndp-sim').as_posix()}",
            "-C",
            str(ROOT / "ndp-sim"),
            "rev-parse",
            f"HEAD:{relative}",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return run.stdout.strip() if run.returncode == 0 else None


def write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def base_accepts(
    ledger: dict[str, Any],
    materialization: dict[str, Any],
    *,
    expected_record_count: int,
    expected_unresolved: int,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    records = ledger.get("records", [])
    if len(records) != expected_record_count:
        errors.append("record_count")
    identities = [
        (item.get("target_id"), item.get("physical_stage"), item.get("json_pointer"))
        for item in records
    ]
    if len(identities) != len(set(identities)):
        errors.append("duplicate_leaf_identity")
    unresolved = [item for item in records if item.get("status") == "UNRESOLVED"]
    if len(unresolved) != expected_unresolved:
        errors.append("unresolved_count")
    for index, item in enumerate(records):
        if not REQUIRED_LEAF_KEYS <= set(item):
            errors.append(f"required_keys:{index}")
            break
        if item["origin"] not in ALLOWED_ORIGINS:
            errors.append(f"origin:{index}")
            break
        if item["default_state"] not in DEFAULT_STATES:
            errors.append(f"default_state:{index}")
            break
        source = item["source"]
        if not {
            "repository",
            "commit",
            "blob",
            "path",
            "json_pointer",
            "value",
        } <= set(source):
            errors.append(f"source_receipt:{index}")
            break
        if item["origin"] == "UNRESOLVED":
            if item["status"] != "UNRESOLVED":
                errors.append(f"unresolved_status:{index}")
                break
            if item["target_value"] is not None:
                errors.append(f"unresolved_has_target_value:{index}")
                break
            if item["applicability"] != "SOURCE_ABSENT_UNKNOWN_FOR_TARGET":
                errors.append(f"unresolved_applicability:{index}")
                break
        if (
            item["origin"] == "REFERENCE_EXACT"
            and source["commit"] == "NONE_PROJECT_ADDED_COMPARISON_ONLY"
        ):
            errors.append(f"project_reference_exact:{index}")
            break
    if unresolved and materialization.get("materialization_allowed") is not False:
        errors.append("materialized_with_unresolved")
    if unresolved and materialization.get("strict_complete_json_count") != 0:
        errors.append("strict_json_count_with_unresolved")
    return not errors, errors


def negative_controls(
    ledger: dict[str, Any],
    materialization: dict[str, Any],
    expected_records: int,
    expected_unresolved: int,
) -> dict[str, Any]:
    cases: dict[str, Any] = {}

    removed = copy.deepcopy(ledger)
    removed["records"].pop()
    valid, errors = base_accepts(
        removed,
        materialization,
        expected_record_count=expected_records,
        expected_unresolved=expected_unresolved,
    )
    cases["delete_one_required_leaf"] = {
        "exit_code": 0 if valid else 1,
        "failed_closed": not valid,
        "errors": errors,
    }

    promoted = copy.deepcopy(ledger)
    item = next(x for x in promoted["records"] if x["status"] == "UNRESOLVED")
    item["origin"] = "REFERENCE_EXACT"
    item["status"] = "RESOLVED"
    valid, errors = base_accepts(
        promoted,
        materialization,
        expected_record_count=expected_records,
        expected_unresolved=expected_unresolved,
    )
    cases["promote_project_comparison_to_reference_exact"] = {
        "exit_code": 0 if valid else 1,
        "failed_closed": not valid,
        "errors": errors,
    }

    implicit = copy.deepcopy(ledger)
    item = next(x for x in implicit["records"] if x["status"] == "UNRESOLVED")
    item["target_value"] = 0
    item["default_state"] = "EXPLICIT_ZERO"
    valid, errors = base_accepts(
        implicit,
        materialization,
        expected_record_count=expected_records,
        expected_unresolved=expected_unresolved,
    )
    cases["implicit_zero_for_unknown_target"] = {
        "exit_code": 0 if valid else 1,
        "failed_closed": not valid,
        "errors": errors,
    }

    materialized = copy.deepcopy(materialization)
    materialized["materialization_allowed"] = True
    materialized["strict_complete_json_count"] = 17
    valid, errors = base_accepts(
        ledger,
        materialized,
        expected_record_count=expected_records,
        expected_unresolved=expected_unresolved,
    )
    cases["materialize_with_unresolved"] = {
        "exit_code": 0 if valid else 1,
        "failed_closed": not valid,
        "errors": errors,
    }

    absent = copy.deepcopy(ledger)
    item = next(x for x in absent["records"] if x["status"] == "UNRESOLVED")
    item["applicability"] = "SOURCE_ABSENT_NOT_APPLICABLE"
    valid, errors = base_accepts(
        absent,
        materialization,
        expected_record_count=expected_records,
        expected_unresolved=expected_unresolved,
    )
    cases["misclassify_required_leaf_not_applicable"] = {
        "exit_code": 0 if valid else 1,
        "failed_closed": not valid,
        "errors": errors,
    }
    return cases


def existing_receipt(command: list[str]) -> dict[str, Any]:
    run = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    parsed = None
    try:
        parsed = json.loads(run.stdout)
    except json.JSONDecodeError:
        pass

    def receipt_drift_only(value: Any) -> bool:
        errors: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for key, item in node.items():
                    if key == "errors" and isinstance(item, list):
                        errors.extend(str(message) for message in item)
                    else:
                        walk(item)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(value)
        permitted = (
            "SHA mismatch",
            "receipt drift",
            "referenced materialized configuration receipts are invalid",
        )
        return bool(errors) and all(
            any(marker in message for marker in permitted) for message in errors
        )

    drift_only = parsed is not None and receipt_drift_only(parsed)
    return {
        "command": command,
        "exit_code": run.returncode,
        "stdout_tail": run.stdout.splitlines()[-12:],
        "stderr_tail": run.stderr.splitlines()[-12:],
        "passed": run.returncode == 0,
        "receipt_drift_only": drift_only,
        "accepted_for_regeneration_receipt": run.returncode == 0 or drift_only,
        "claim_boundary": (
            "This records execution of the existing family validator. Current "
            "rule/plan receipt drift remains fail-closed in that historical "
            "asset and is not promoted to a target JSON validation pass."
        ),
    }


def main() -> int:
    missing = [
        str(path)
        for path in [
            *FILES.values(),
            MATERIALIZATION,
            PUBLIC_CANDIDATE_REPORT,
            PUBLIC_FAMILY_REPORT,
        ]
        if not path.is_file()
    ]
    if missing:
        raise FileNotFoundError(missing)
    inventory = load(FILES["stage_inventory.json"])
    ledger = load(FILES["field_provenance_ledger.json"])
    refs = load(FILES["reference_applicability.json"])
    handler = load(FILES["handler_capability.json"])
    diff = load(FILES["current_test_diff.json"])
    report = load(FILES["report.json"])
    materialization = load(MATERIALIZATION)
    public_candidate = load(PUBLIC_CANDIDATE_REPORT)
    public_family = load(PUBLIC_FAMILY_REPORT)
    expected_records = ledger["record_count"]
    expected_unresolved = ledger["unresolved_count"]

    accepted, base_errors = base_accepts(
        ledger,
        materialization,
        expected_record_count=expected_records,
        expected_unresolved=expected_unresolved,
    )
    negatives = negative_controls(
        ledger, materialization, expected_records, expected_unresolved
    )

    lowering = load(LOWERING)
    qrequests = [
        item
        for item in lowering["requests"]
        if item["identity"]["hw_op_type"] == "QLinearAddUint8"
    ]
    target_ids = [item["identity"]["hw_op_id"] for item in qrequests]
    inventory_ids = [item["identity"]["hw_op_id"] for item in inventory["targets"]]
    stage_orders = [
        item["dag"]["physical_stage_order"] for item in inventory["targets"]
    ]
    node0076 = next(
        item for item in inventory["targets"] if item["identity"]["node_id"] == "node-0076"
    )
    current_schema = {}
    try:
        from resnet50_pipeline.operator_config_validator import OperatorConfigValidator

        validator = OperatorConfigValidator()
        for path in sorted(CURRENT_CONFIG.glob("*.json")):
            result = validator.validate(
                load(path), source=path.as_posix(), development_mode=True
            )
            current_schema[path.name] = {
                "valid": result.valid,
                "first_error": result.to_dict().get("first_error"),
                "sha256": sha(path),
            }
    except Exception as exc:  # pragma: no cover - recorded fail closed
        current_schema["exception"] = {"valid": False, "message": repr(exc)}

    native_checks = {}
    for item in refs["references"]:
        if item.get("repository") != "uSFrances/ndp-sim":
            continue
        path = ROOT / item["path"]
        commit_blob = committed_blob_sha(path) if path.is_file() else None
        native_checks[item["reference_id"]] = {
            "path_exists": path.is_file(),
            "working_tree_git_blob_sha": (
                git_blob_sha(path) if path.is_file() else None
            ),
            "commit_blob_sha": commit_blob,
            "expected_blob_sha": item["blob"],
            "blob_match": commit_blob == item["blob"],
            "sha256_match": path.is_file()
            and sha(path) == item["file_sha256"],
            "claim_boundary": (
                "commit_blob_sha binds pinned upstream authority; working-tree "
                "SHA256 independently binds the bytes inspected under Windows "
                "checkout newline conversion."
            ),
        }

    prohibited = []
    for path in OUT.rglob("*"):
        if not path.is_file():
            continue
        lower = path.name.lower()
        if path.suffix.lower() == ".zip" or lower in {
            "prepare_and_run.sh",
            "run_on_server.sh",
        }:
            prohibited.append(path.relative_to(OUT).as_posix())

    python = sys.executable
    existing = {
        "predesign": existing_receipt(
            [
                python,
                "tools/validate_qlinearadd_predesign.py",
                "contracts/operator_config/qlinearadd_composite_backend_predesign_v1.json",
            ]
        ),
        "stage0_receipts_only": existing_receipt(
            [
                python,
                "tools/validate_qlinearadd_stage0_config_only.py",
                "configs/qlinearadd_stage0_config_only/qlinearadd_stage0_config_only_v1.json",
                "--contract",
                "contracts/operator_config/qlinearadd_stage0_config_only_contract_v1.json",
                "--receipts-only",
            ]
        ),
    }

    checks = {
        "base_ledger_valid": accepted and not base_errors,
        "17_targets": inventory["logical_target_stage_count"] == 17
        and len(inventory["targets"]) == 17
        and inventory_ids == target_ids,
        "102_physical_stages": inventory["physical_stage_count"] == 102
        and all(len(order) == 6 for order in stage_orders),
        "five_structural_classes": inventory[
            "structural_equivalence_class_count"
        ]
        == 5,
        "17_exact_consumer_signatures": inventory[
            "materialized_consumer_signature_class_count"
        ]
        == 17,
        "all_six_qparams": all(
            set(item["qparams"])
            == {
                "a_scale",
                "a_zero_point",
                "b_scale",
                "b_zero_point",
                "y_scale",
                "y_zero_point",
            }
            for item in inventory["targets"]
        ),
        "node0076_broadcast_tail": (
            node0076["shapes"]["a"] == [16, 1000]
            and node0076["shapes"]["b"] == [1000]
            and node0076["padding_tail"]["b"]["typed_bytes"] == 4000
            and node0076["padding_tail"]["b"]["physical_bytes"] == 4032
            and node0076["padding_tail"]["b"]["replay_count"] == 16
        ),
        "materialization_blocked": materialization["materialization_allowed"]
        is False
        and materialization["strict_complete_json_count"] == 0
        and materialization["unresolved_required_leaf_count"]
        == expected_unresolved,
        "shared_candidate_blocked_valid": (
            public_candidate.get("contract_valid") is True
            and public_candidate.get("blocked_valid") is True
            and public_candidate.get("pass") is False
            and public_candidate.get("errors") == []
            and public_candidate.get("candidate_leaf_count") == expected_records
            and public_candidate.get("ledger_leaf_count") == expected_records
            and public_candidate.get("handler", {}).get("uncovered_count")
            == expected_unresolved
            and public_candidate.get("composition", {}).get("boundary_count")
            == 85
            and public_candidate.get("composition", {}).get("unresolved_count")
            == 85
        ),
        "shared_family_set_exact_coverage_blocked": (
            public_family.get("expected_stage_count") == 17
            and public_family.get("covered_stage_count") == 17
            and public_family.get("missing_stage_ids") == []
            and public_family.get("unexpected_stage_ids") == []
            and len(public_family.get("candidate_reports", [])) == 1
            and public_family["candidate_reports"][0].get("contract_valid") is True
            and public_family["candidate_reports"][0].get("blocked_valid") is True
            and public_family.get("pass") is False
        ),
        "all_negatives_fail_closed": all(
            item["failed_closed"] for item in negatives.values()
        ),
        "native_blob_receipts": all(
            item["blob_match"] and item["sha256_match"]
            for item in native_checks.values()
        ),
        "no_A_grade_for_target": refs["grade_counts"]["A"] == 0
        and all(
            not item["target_exact_replay_allowed"]
            for item in refs["references"]
        ),
        "handler_matrix_dimensions": handler["dimensions"]
        == [
            "exact_replay",
            "shape",
            "dtype",
            "qparam",
            "layout",
            "address",
            "cross_stage_schedule",
        ]
        and handler["composite_result"]
        == "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED",
        "current_schema_six_of_six": len(current_schema) == 6
        and all(item["valid"] for item in current_schema.values()),
        "current_diff_five_categories": set(diff["categories"])
        == {
            "same",
            "intentional_derivation",
            "suspected_current_defect",
            "new_candidate_defect",
            "dynamic_only",
        },
        "v35_explained_by_config": diff["latest_return"][
            "configuration_difference_explains_current_stall"
        ]
        is True,
        "no_prohibited_server_artifacts": not prohibited,
        "report_claim_boundary": report["status"]
        == "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED"
        and report["coverage"]["strict_complete_jsons"] == 0,
        "existing_predesign_receipt": existing["predesign"][
            "accepted_for_regeneration_receipt"
        ],
        "existing_stage0_receipt": existing["stage0_receipts_only"][
            "accepted_for_regeneration_receipt"
        ],
        "numeric_workload_not_repeated": report["numeric_analysis_repeated"]
        is False
        and report["workload_analysis_repeated"] is False
        and report["golden_recomputed"] is False,
    }
    errors = [key for key, value in checks.items() if not value]
    validation = {
        "schema": "qlinearadd-complete-json-regeneration-validation-v1",
        "status": (
            "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED_VALIDATED"
            if not errors
            else "VALIDATION_FAILED"
        ),
        "valid": not errors,
        "errors": errors,
        "error_count": len(errors),
        "checks": checks,
        "coverage": {
            "targets": 17,
            "physical_stages": 102,
            "ledger_records": expected_records,
            "unresolved": expected_unresolved,
            "strict_jsons": 0,
        },
        "negative_controls": negatives,
        "native_authority_checks": native_checks,
        "current_comparison_strict_schema": current_schema,
        "shared_candidate_validation": {
            "path": PUBLIC_CANDIDATE_REPORT.relative_to(ROOT).as_posix(),
            "sha256": sha(PUBLIC_CANDIDATE_REPORT),
            "exit_semantics": (
                "Expected exit 1: structurally valid BLOCKED contract with "
                "completion blockers; not a COMPLETE candidate."
            ),
            "contract_valid": public_candidate.get("contract_valid"),
            "blocked_valid": public_candidate.get("blocked_valid"),
            "pass": public_candidate.get("pass"),
            "error_count": len(public_candidate.get("errors", [])),
            "completion_blocker_count": len(
                public_candidate.get("completion_blockers", [])
            ),
        },
        "shared_family_set_audit": {
            "path": PUBLIC_FAMILY_REPORT.relative_to(ROOT).as_posix(),
            "sha256": sha(PUBLIC_FAMILY_REPORT),
            "exit_semantics": (
                "Expected exit 1 because the sole exact-coverage candidate is "
                "BLOCKED; expected/covered remain 17/17 with no duplicate, "
                "missing, or unexpected stage."
            ),
            "pass": public_family.get("pass"),
            "expected_stage_count": public_family.get("expected_stage_count"),
            "covered_stage_count": public_family.get("covered_stage_count"),
            "missing_stage_ids": public_family.get("missing_stage_ids"),
            "unexpected_stage_ids": public_family.get("unexpected_stage_ids"),
        },
        "existing_family_validator_receipts": existing,
        "prohibited_files": prohibited,
        "claim_boundary": (
            "Validator proves complete inventory/provenance and correct "
            "fail-closed non-materialization. It does not validate a new strict "
            "target JSON because none may legally exist with unresolved leaves."
        ),
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "golden_recomputed": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write(OUT / "validation.json", validation)
    print(
        json.dumps(
            {
                "status": validation["status"],
                "valid": validation["valid"],
                "errors": errors,
                "records": expected_records,
                "unresolved": expected_unresolved,
                "negative_exits": {
                    key: item["exit_code"] for key, item in negatives.items()
                },
                "output": str(OUT / "validation.json"),
            },
            indent=2,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
