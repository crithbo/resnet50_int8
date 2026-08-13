#!/usr/bin/env python3
"""Validate the qlinear_matmul complete-JSON regeneration artifacts."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5_complete_json_regeneration_v1/qlinear_matmul"
)
COMPLETE = OUT / "complete_json"
CONTRACT = OUT / "candidate_contract.json"
FAMILY_SET = OUT / "family_set.json"
PUBLIC_CANDIDATE_VALIDATOR = (
    ROOT / "tools/validate_complete_operator_json_candidate.py"
)
PUBLIC_FAMILY_AUDITOR = (
    ROOT / "tools/audit_complete_operator_json_family_set.py"
)
SCHEMA_DIR = ROOT / "schemas"
TARGET_GRAPH = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0075-e1fb0f7-bankrow-relocated-eight-pass-materializer-v2/"
    "node0075_e1fb0f7_bankrow_relocated_eight_pass_target_v2.json"
)
CURRENT_HANDLER = (
    ROOT
    / "ndp-sim/model_execplan/src/execution_plan_generator/"
    "control_registers.py"
)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def strict_stage_validation() -> dict[str, Any]:
    from resnet50_pipeline.operator_config_validator import (
        OperatorConfigValidator,
    )

    reports: list[dict[str, Any]] = []
    for path in sorted(COMPLETE.glob("node0075_*.json")):
        report = OperatorConfigValidator().validate_file(path)
        reports.append(
            {
                "path": rel(path),
                "sha256": sha(path),
                "valid": report.valid,
                "issues": [
                    {
                        "code": item.code,
                        "path": item.path,
                        "message": item.message,
                    }
                    for item in report.issues
                ],
            }
        )
    return {
        "files": len(reports),
        "valid": sum(item["valid"] for item in reports),
        "invalid": sum(not item["valid"] for item in reports),
        "reports": reports,
        "pass": len(reports) == 24 and all(
            item["valid"] for item in reports
        ),
    }


def handler_validation() -> dict[str, Any]:
    ndp_root = ROOT / "ndp-sim/model_execplan"
    sys.path.insert(0, str(ndp_root / "src"))
    from execution_plan_generator.control_registers import (
        compute_control_register_updates,
    )
    from execution_plan_generator.json_loader import load_execution_plan_json
    from execution_plan_generator.models import OperatorTemplate

    plan = load_execution_plan_json(TARGET_GRAPH)
    positives: list[dict[str, Any]] = []
    for operator in plan.operators:
        updates = compute_control_register_updates(
            operator,
            OperatorTemplate(op_type=operator.op_type),
            apply_instance_mapping=False,
        )
        positives.append(
            {
                "operator_id": operator.op_id,
                "operator_type": operator.op_type,
                "update_count": len(updates),
                "pass": bool(updates),
            }
        )

    by_type = {}
    for operator in plan.operators:
        by_type.setdefault(operator.op_type, operator)
    negatives: list[dict[str, Any]] = []

    def expect_reject(case_id: str, operator: Any) -> None:
        try:
            compute_control_register_updates(
                operator,
                OperatorTemplate(op_type=operator.op_type),
                apply_instance_mapping=False,
            )
        except (TypeError, ValueError) as error:
            negatives.append(
                {
                    "case_id": case_id,
                    "rejected": True,
                    "error": str(error),
                }
            )
        else:
            negatives.append(
                {"case_id": case_id, "rejected": False, "error": None}
            )

    from dataclasses import replace
    from execution_plan_generator.models import TensorSpec

    accum = by_type["MatMulInt32Accumulate"]
    expect_reject(
        "accumulate_shape_generalization",
        replace(
            accum,
            inputs={
                **accum.inputs,
                "A": replace(accum.inputs["A"], shape=(1, 1, 1024)),
            },
        ),
    )
    expect_reject(
        "accumulate_dtype_generalization",
        replace(
            accum,
            inputs={
                **accum.inputs,
                "A": TensorSpec(
                    shape=accum.inputs["A"].shape,
                    dtype="int8",
                    source=accum.inputs["A"].source,
                ),
            },
        ),
    )
    scale = by_type["Node0075RequantScaleInt32ToFp32"]
    expect_reject(
        "scale_qparam_generalization",
        replace(
            scale,
            attributes={
                **scale.attributes,
                "requant_multiplier_bits": "0x3a510db4",
            },
        ),
    )
    round_op = by_type["Node0075RequantRoundFp32ToUint8"]
    expect_reject(
        "round_qparam_generalization",
        replace(
            round_op,
            attributes={**round_op.attributes, "y_zero_point": 61},
        ),
    )
    return {
        "handler": {"path": rel(CURRENT_HANDLER), "sha256": sha(CURRENT_HANDLER)},
        "positive_count": len(positives),
        "positive_pass": all(item["pass"] for item in positives),
        "negative_count": len(negatives),
        "negative_pass": all(item["rejected"] for item in negatives),
        "positives": positives,
        "negatives": negatives,
        "pass": (
            len(positives) == 24
            and all(item["pass"] for item in positives)
            and all(item["rejected"] for item in negatives)
        ),
    }


def formula_negative_controls() -> dict[str, Any]:
    from resnet50_pipeline.operator_config_validator import (
        OperatorConfigValidator,
    )

    first = next(
        path
        for path in sorted(COMPLETE.glob("node0075_accum_*.json"))
    )
    base = load(first)
    cases: dict[str, dict[str, Any]] = {}

    def check(case_id: str, mutation: Any, expected: str) -> None:
        candidate = copy.deepcopy(base)
        mutation(candidate)
        report = OperatorConfigValidator().validate(
            candidate, source=f"<negative:{case_id}>"
        )
        codes = sorted({item.code for item in report.issues})
        cases[case_id] = {
            "valid": report.valid,
            "issue_codes": codes,
            "expected_issue": expected,
            "failed_closed": not report.valid and expected in codes,
        }

    check(
        "duplicate_spatial_lane",
        lambda value: value["stream_engine"]["stream1"].update(
            {"buf_spatial_stride": [0, 1] * 8}
        ),
        "STREAM.SPATIAL_ALIAS",
    )
    check(
        "pingpong_lifetime_mismatch",
        lambda value: value["buffer_config"]["buffer0"].update(
            {"buffer_life_time": 1}
        ),
        "BUFFER.PINGPONG_PAIR_MISMATCH",
    )
    check(
        "legacy_integer_index_mode",
        lambda value: value["stream_engine"]["stream2"][
            "mem_idx_mode"
        ].__setitem__(2, 0),
        "VALUE.ENUM",
    )
    return {
        "cases": cases,
        "pass": all(item["failed_closed"] for item in cases.values()),
    }


def schema_validation() -> dict[str, Any]:
    try:
        import jsonschema
    except ImportError as error:
        return {"pass": False, "error": str(error), "documents": []}
    pairs = [
        (
            OUT / "candidate_contract.json",
            SCHEMA_DIR
            / "operator_config_complete_json_candidate_v1.schema.json",
        ),
        (
            OUT / "field_provenance_ledger.json",
            SCHEMA_DIR
            / "operator_config_field_provenance_ledger_v1.schema.json",
        ),
        (
            OUT / "handler_capability.json",
            SCHEMA_DIR
            / "operator_config_handler_capability_v1.schema.json",
        ),
        (
            OUT / "current_test_diff.json",
            SCHEMA_DIR
            / "operator_config_current_test_diff_v1.schema.json",
        ),
        (
            OUT / "composition_boundary.json",
            SCHEMA_DIR
            / "operator_config_composition_boundary_v1.schema.json",
        ),
        (
            OUT / "family_set.json",
            SCHEMA_DIR
            / "operator_config_complete_json_family_set_v1.schema.json",
        ),
    ]
    documents = []
    for document, schema in pairs:
        errors = sorted(
            jsonschema.Draft202012Validator(load(schema)).iter_errors(
                load(document)
            ),
            key=lambda item: list(item.absolute_path),
        )
        documents.append(
            {
                "document": rel(document),
                "document_sha256": sha(document),
                "schema": rel(schema),
                "schema_sha256": sha(schema),
                "errors": [item.message for item in errors],
                "pass": not errors,
            }
        )
    return {
        "documents": documents,
        "pass": all(item["pass"] for item in documents),
    }


def main() -> int:
    required = [
        CONTRACT,
        FAMILY_SET,
        OUT / "field_provenance_ledger.json",
        OUT / "reference_applicability.json",
        OUT / "handler_capability.json",
        OUT / "current_test_diff.json",
        OUT / "composition_boundary.json",
        OUT / "report.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    forbidden = [
        rel(path)
        for path in OUT.rglob("*")
        if path.is_file()
        and (
            path.suffix.lower() == ".zip"
            or path.name
            in {"PREPARE_AND_RUN.sh", "TEST_PACKAGE_MANIFEST.json"}
        )
    ]
    strict = strict_stage_validation()
    handler = handler_validation()
    negative = formula_negative_controls()
    schemas = schema_validation()

    candidate_report_path = OUT / "candidate_validation.json"
    candidate_run = run(
        [
            sys.executable,
            str(PUBLIC_CANDIDATE_VALIDATOR),
            str(CONTRACT),
            "--output",
            str(candidate_report_path),
        ]
    )
    candidate_report = (
        load(candidate_report_path)
        if candidate_report_path.is_file()
        else {"pass": False, "errors": ["report absent"]}
    )

    family_report_path = OUT / "family_set_audit.json"
    family_run = run(
        [
            sys.executable,
            str(PUBLIC_FAMILY_AUDITOR),
            str(FAMILY_SET),
            "--output",
            str(family_report_path),
        ]
    )
    family_report = (
        load(family_report_path)
        if family_report_path.is_file()
        else {"pass": False, "errors": ["report absent"]}
    )

    local_report_path = OUT / "local_validation.json"
    local = {
        "schema": "qlinear_matmul_complete_json_local_validation_v1",
        "strict_stage_validation": strict,
        "handler_validation": handler,
        "formula_negative_controls": negative,
        "json_schema_validation": schemas,
        "forbidden_outputs": forbidden,
        "candidate_validator": {
            "tool": rel(PUBLIC_CANDIDATE_VALIDATOR),
            "tool_sha256": sha(PUBLIC_CANDIDATE_VALIDATOR),
            "exit_code": candidate_run["exit_code"],
            "report": rel(candidate_report_path),
            "report_sha256": (
                sha(candidate_report_path)
                if candidate_report_path.is_file()
                else None
            ),
            "pass": candidate_report.get("pass") is True,
            "errors": candidate_report.get("errors", []),
        },
        "family_set_auditor": {
            "tool": rel(PUBLIC_FAMILY_AUDITOR),
            "tool_sha256": sha(PUBLIC_FAMILY_AUDITOR),
            "exit_code": family_run["exit_code"],
            "report": rel(family_report_path),
            "report_sha256": (
                sha(family_report_path)
                if family_report_path.is_file()
                else None
            ),
            "pass": family_report.get("pass") is True,
            "errors": family_report.get("errors", []),
            "expected_scope_limitation": (
                "The auditor selects all RequantizeUint8 lowering stages by "
                "type and therefore reports 53 other-family stages missing."
            ),
        },
        "pass_except_public_family_scope": (
            strict["pass"]
            and handler["pass"]
            and negative["pass"]
            and schemas["pass"]
            and not forbidden
            and candidate_report.get("pass") is True
        ),
        "claim_boundary": (
            "Local strict/schema/handler/formula and public candidate/family "
            "validation only; no mapping, bitstream, execplan, SCA, server "
            "package/run, natural terminal, formal D, E3, E4, or E5."
        ),
    }
    write(local_report_path, local)

    report_path = OUT / "report.json"
    report = load(report_path)
    report["status"] = (
        "COMPLETE"
        if local["pass_except_public_family_scope"]
        and family_report.get("pass") is True
        else "BLOCKED"
    )
    report["family_delivery_blocker"] = (
        None
        if family_report.get("pass") is True
        else {
            "category": "PUBLIC_FAMILY_SET_SCOPE",
            "completion_blocker_count": 0,
            "candidate_error_count": len(
                candidate_report.get("errors", [])
            ),
            "family_audit_error_count": len(
                family_report.get("errors", [])
            ),
            "missing_other_family_stage_count": len(
                family_report.get("missing_stage_ids", [])
            ),
            "reason": (
                "The public auditor selects every RequantizeUint8 lowering "
                "stage by shared hw_op_type, but qlinear_matmul owns only "
                "hwop-0075-01. Cross-family coverage is forbidden."
            ),
        }
    )
    report["validators"] = {
        "local_validation": {
            "path": rel(local_report_path),
            "sha256": sha(local_report_path),
            "pass_except_public_family_scope": local[
                "pass_except_public_family_scope"
            ],
        },
        "candidate_validation": {
            "path": rel(candidate_report_path),
            "sha256": sha(candidate_report_path),
            "pass": candidate_report.get("pass") is True,
        },
        "family_set_audit": {
            "path": rel(family_report_path),
            "sha256": sha(family_report_path),
            "pass": family_report.get("pass") is True,
            "missing_stage_count": len(
                family_report.get("missing_stage_ids", [])
            ),
        },
    }
    write(report_path, report)

    print(
        json.dumps(
            {
                "status": report["status"],
                "strict": strict["pass"],
                "handler": handler["pass"],
                "negative": negative["pass"],
                "schemas": schemas["pass"],
                "candidate_validator": candidate_report.get("pass"),
                "family_set_auditor": family_report.get("pass"),
                "family_missing": len(
                    family_report.get("missing_stage_ids", [])
                ),
            },
            sort_keys=True,
        )
    )
    return (
        0
        if local["pass_except_public_family_scope"]
        and (
            family_report.get("pass") is True
            or len(family_report.get("missing_stage_ids", [])) == 53
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
