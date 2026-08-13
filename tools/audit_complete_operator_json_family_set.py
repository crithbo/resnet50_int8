#!/usr/bin/env python3
"""Audit that complete-JSON candidate contracts cover one whole operator family."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validate_complete_operator_json_candidate import (
    DEFAULT_AUTHORITY,
    DEFAULT_LOWERING,
    DEFAULT_POLICY,
    InputError,
    load_bound_file,
    load_json,
    lowering_stage_index,
    sha256_file,
    validate,
)


def audit_family_set(
    *,
    workspace_root: Path,
    manifest_path: Path,
    authority_path: Path,
    policy_path: Path,
    lowering_path: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        manifest = load_json(manifest_path)
        lowering_document = load_json(lowering_path)
    except InputError as error:
        return {
            "schema": "complete_operator_json_family_set_report_v1",
            "pass": False,
            "errors": [str(error)],
            "claim_boundary": "Family-set input binding failure only.",
        }
    if not isinstance(manifest, dict):
        errors.append("family-set manifest must be an object")
        manifest = {}
    if manifest.get("schema") != "operator_config_complete_json_family_set_v1":
        errors.append("family-set manifest schema mismatch")
    family = manifest.get("family")
    if not isinstance(family, str) or not family:
        errors.append("family-set family is missing")
        family = "<invalid>"
    hw_types_raw = manifest.get("target_hw_op_types")
    if (
        not isinstance(hw_types_raw, list)
        or not hw_types_raw
        or any(not isinstance(item, str) or not item for item in hw_types_raw)
        or len(hw_types_raw) != len(set(hw_types_raw))
    ):
        errors.append("target_hw_op_types must be a non-empty unique string array")
        hw_types: set[str] = set()
    else:
        hw_types = set(hw_types_raw)
    if not isinstance(manifest.get("claim_boundary"), str):
        errors.append("family-set claim boundary is missing")

    lowering, lowering_errors = lowering_stage_index(lowering_document)
    errors.extend(lowering_errors)
    lowering_sha256 = sha256_file(lowering_path)
    scope = manifest.get("family_scope")
    exact_scope_receipts: list[dict[str, Any]] = []
    if scope is None:
        scope_mode = "LEGACY_HW_OP_TYPE_SELECTOR"
        expected = {
            stage_id
            for stage_id, request in lowering.items()
            if request["identity"]["hw_op_type"] in hw_types
        }
    else:
        scope_mode = "PINNED_EXACT_STAGE_IDS"
        expected_ids_raw: list[Any] = []
        if not isinstance(scope, dict):
            errors.append("family_scope must be an object")
            scope = {}
        if scope.get("mode") != "PINNED_EXACT_STAGE_IDS":
            errors.append("family_scope mode must be PINNED_EXACT_STAGE_IDS")
        declared_lowering_sha = scope.get("lowering_sha256")
        if declared_lowering_sha != lowering_sha256:
            errors.append(
                "family_scope lowering SHA mismatch: "
                f"declared={declared_lowering_sha}; actual={lowering_sha256}"
            )
        expected_ids_raw = scope.get("expected_stage_ids", [])
        if (
            not isinstance(expected_ids_raw, list)
            or not expected_ids_raw
            or any(not isinstance(item, str) or not item for item in expected_ids_raw)
        ):
            errors.append(
                "family_scope expected_stage_ids must be a non-empty string array"
            )
            expected_ids_raw = []
        elif len(expected_ids_raw) != len(set(expected_ids_raw)):
            errors.append("family_scope expected_stage_ids contains duplicates")
        expected = set(expected_ids_raw)
        for stage_id in expected_ids_raw:
            request = lowering.get(stage_id)
            if request is None:
                errors.append(
                    f"family_scope expected stage is absent from lowering: {stage_id}"
                )
                exact_scope_receipts.append(
                    {
                        "stage_id": stage_id,
                        "present": False,
                        "hw_op_type": None,
                        "onnx_op_type": None,
                    }
                )
                continue
            identity = request["identity"]
            stage_hw_type = identity["hw_op_type"]
            if stage_hw_type not in hw_types:
                errors.append(
                    "family_scope stage hw type is outside target_hw_op_types: "
                    f"{stage_id}: {stage_hw_type}"
                )
            exact_scope_receipts.append(
                {
                    "stage_id": stage_id,
                    "present": True,
                    "hw_op_type": stage_hw_type,
                    "onnx_op_type": identity.get("onnx_op_type"),
                }
            )
    if not expected:
        errors.append(
            f"family scope selects no lowering stages: mode={scope_mode}"
        )

    candidate_refs = manifest.get("candidate_contracts")
    if not isinstance(candidate_refs, list):
        errors.append("candidate_contracts must be an array")
        candidate_refs = []
    seen: dict[str, str] = {}
    candidate_reports: list[dict[str, Any]] = []
    for index, reference in enumerate(candidate_refs):
        try:
            contract_path, contract = load_bound_file(
                workspace_root,
                reference,
                label=f"candidate contract {index}",
            )
        except InputError as error:
            errors.append(str(error))
            continue
        if not isinstance(contract, dict):
            errors.append(f"candidate contract is not an object: {index}")
            continue
        if contract.get("family") != family:
            errors.append(
                f"candidate contract family mismatch: "
                f"{contract_path.relative_to(workspace_root).as_posix()}"
            )
        contract_types = set(contract.get("target_hw_op_types", []))
        if not contract_types or not contract_types.issubset(hw_types):
            errors.append(
                f"candidate contract hw types are outside family set: "
                f"{contract_path.relative_to(workspace_root).as_posix()}"
            )
        report = validate(
            workspace_root=workspace_root,
            contract_path=contract_path,
            authority_path=authority_path,
            policy_path=policy_path,
            lowering_path=lowering_path,
        )
        candidate_reports.append(
            {
                "contract": contract_path.relative_to(workspace_root).as_posix(),
                "contract_sha256": sha256_file(contract_path),
                "stage_ids": contract.get("stage_ids", []),
                "candidate_json_sha256": report.get("candidate_json_sha256"),
                "pass": report.get("pass"),
                "contract_valid": report.get("contract_valid"),
                "blocked_valid": report.get("blocked_valid"),
                "completion_blockers": report.get("completion_blockers", []),
                "errors": report.get("errors", []),
            }
        )
        if report.get("pass") is not True:
            errors.append(
                f"candidate contract did not pass complete-JSON validation: "
                f"{contract_path.relative_to(workspace_root).as_posix()}"
            )
        for stage_id in contract.get("stage_ids", []):
            if stage_id in seen:
                errors.append(
                    f"stage covered by multiple candidates: {stage_id}: "
                    f"{seen[stage_id]} and "
                    f"{contract_path.relative_to(workspace_root).as_posix()}"
                )
            else:
                seen[stage_id] = (
                    contract_path.relative_to(workspace_root).as_posix()
                )

    no_config = manifest.get("no_config_stages")
    if not isinstance(no_config, list):
        errors.append("no_config_stages must be an array")
        no_config = []
    no_config_receipts: list[dict[str, Any]] = []
    for index, item in enumerate(no_config):
        if not isinstance(item, dict):
            errors.append("no-config stage entry must be an object")
            continue
        stage_id = item.get("stage_id")
        reason = item.get("reason_code")
        request = lowering.get(stage_id)
        if request is None:
            errors.append(f"no-config stage is absent from lowering: {stage_id}")
            continue
        if request["identity"]["hw_op_type"] != "View":
            errors.append(
                f"only View may use metadata-only no-config coverage: {stage_id}"
            )
        if reason != "METADATA_ONLY_ALIAS_NO_COMPUTE":
            errors.append(f"invalid no-config reason: {stage_id}: {reason}")
        try:
            evidence_path, evidence = load_bound_file(
                workspace_root,
                item.get("evidence"),
                label=f"no-config evidence {index}",
            )
        except InputError as error:
            errors.append(str(error))
            continue
        if not isinstance(evidence, dict):
            errors.append(f"no-config evidence must be an object: {stage_id}")
        elif evidence.get("metadata_only") is not True:
            errors.append(
                f"no-config evidence does not prove metadata-only alias: {stage_id}"
            )
        if stage_id in seen:
            errors.append(f"stage covered by candidate and no-config: {stage_id}")
        else:
            seen[stage_id] = evidence_path.relative_to(workspace_root).as_posix()
        no_config_receipts.append(
            {
                "stage_id": stage_id,
                "evidence": evidence_path.relative_to(workspace_root).as_posix(),
                "sha256": sha256_file(evidence_path),
            }
        )

    actual = set(seen)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing:
        errors.append(f"family stages missing complete-JSON coverage: {missing}")
    if unexpected:
        errors.append(f"family set covers unexpected stages: {unexpected}")
    type_counts = Counter(
        lowering[stage_id]["identity"]["hw_op_type"]
        for stage_id in expected
        if stage_id in lowering
    )
    errors = sorted(set(errors))
    return {
        "schema": "complete_operator_json_family_set_report_v1",
        "manifest": {
            "path": manifest_path.relative_to(workspace_root).as_posix(),
            "sha256": sha256_file(manifest_path),
        },
        "lowering": {
            "path": lowering_path.relative_to(workspace_root).as_posix(),
            "sha256": sha256_file(lowering_path),
        },
        "family": family,
        "target_hw_op_types": sorted(hw_types),
        "scope_mode": scope_mode,
        "legacy_scope_compatibility": scope_mode == "LEGACY_HW_OP_TYPE_SELECTOR",
        "migration_recommended": scope_mode == "LEGACY_HW_OP_TYPE_SELECTOR",
        "exact_scope_receipts": exact_scope_receipts,
        "expected_stage_count": len(expected),
        "expected_hw_op_type_counts": dict(sorted(type_counts.items())),
        "covered_stage_count": len(actual & expected),
        "missing_stage_ids": missing,
        "unexpected_stage_ids": unexpected,
        "candidate_reports": candidate_reports,
        "no_config_receipts": no_config_receipts,
        "errors": errors,
        "pass": not errors,
        "claim_boundary": (
            "Family-wide lowering-stage coverage by locally validated complete "
            "JSON candidates, plus metadata-only View aliases. No mapping, "
            "bitstream, execplan, SCA, server package, server run, natural "
            "terminal, formal D, E3, E4, or E5 is generated or adjudicated."
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--workspace-root", type=Path, default=ROOT)
    parser.add_argument("--authority", type=Path, default=DEFAULT_AUTHORITY)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--lowering", type=Path, default=DEFAULT_LOWERING)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = audit_family_set(
        workspace_root=args.workspace_root.resolve(),
        manifest_path=args.manifest.resolve(),
        authority_path=args.authority.resolve(),
        policy_path=args.policy.resolve(),
        lowering_path=args.lowering.resolve(),
    )
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report.get("pass") is True else 1


if __name__ == "__main__":
    sys.exit(main())
