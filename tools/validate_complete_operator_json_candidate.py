#!/usr/bin/env python3
"""Validate a complete operator JSON candidate without building a server package.

The validator enforces field-level provenance, pinned native-reference
applicability, handler capability, primitive-composition boundaries, and a
leaf-complete comparison against the currently tested configuration.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTHORITY = (
    ROOT / "contracts/operator_config/operator_config_authority_v1.json"
)
DEFAULT_POLICY = (
    ROOT / "contracts/operator_config/complete_json_generation_contract_v1.json"
)
DEFAULT_LOWERING = ROOT / "contracts/resnet50_r5_lowering_bundle.json"

ORIGINS = {
    "REFERENCE_EXACT",
    "MODEL_DERIVED",
    "RTL_DERIVED",
    "ENCODER_DERIVED",
    "ADDRESS_PLANNER_DERIVED",
    "SCHEDULE_DERIVED",
    "EXPLICIT_DISABLED",
    "UNRESOLVED",
}
DERIVED_ORIGINS = {
    "MODEL_DERIVED",
    "RTL_DERIVED",
    "ENCODER_DERIVED",
    "ADDRESS_PLANNER_DERIVED",
    "SCHEDULE_DERIVED",
}
APPLICABILITY = {
    "EXACT_SOURCE_INSTANCE",
    "PROVEN_INVARIANT",
    "DERIVED_FOR_TARGET",
    "EXPLICITLY_INACTIVE",
    "UNRESOLVED",
}
ABSENCE_STATES = {
    "SOURCE_ABSENT_NOT_APPLICABLE",
    "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
    "EXPLICIT_NULL_INACTIVE",
    "EXPLICIT_ZERO",
    "TARGET_REQUIRED_DERIVED",
}
REFERENCE_CLASSES = {"A", "B", "C", "D"}
CAPABILITY_AXES = {
    "exact_replay",
    "shape",
    "dtype",
    "qparam",
    "layout",
    "address",
    "cross_stage_schedule",
}
CHANGED_AXES = CAPABILITY_AXES - {"exact_replay"}
EXACTNESS_AXES = {
    "op",
    "dtype",
    "shape",
    "layout",
    "qparams",
    "topology",
    "address",
    "schedule",
    "consumer",
}
DIFF_CLASSES = {
    "SAME",
    "INTENTIONAL_DERIVATION",
    "SUSPECTED_CURRENT_DEFECT",
    "NEW_CANDIDATE_DEFECT",
    "DYNAMIC_ONLY",
    "CURRENT_ABSENT",
}
CAPABILITY_TO_EXACTNESS = {
    "shape": "shape",
    "dtype": "dtype",
    "qparam": "qparams",
    "layout": "layout",
    "address": "address",
    "cross_stage_schedule": "schedule",
}


class DuplicateKeyError(ValueError):
    """A JSON object contains a duplicate key."""


class InputError(ValueError):
    """The candidate contract cannot be read or bound."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, DuplicateKeyError) as error:
        raise InputError(f"cannot read strict JSON {path}: {error}") from error


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def workspace_path(workspace_root: Path, value: str) -> Path:
    root = workspace_root.resolve()
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise InputError(f"path escapes workspace: {value}") from error
    return candidate


def load_bound_file(
    workspace_root: Path,
    reference: Any,
    *,
    label: str,
) -> tuple[Path, Any]:
    if not isinstance(reference, dict):
        raise InputError(f"{label} binding must be an object")
    path_text = reference.get("path")
    expected = reference.get("sha256")
    if not isinstance(path_text, str) or not path_text:
        raise InputError(f"{label} path is missing")
    if not isinstance(expected, str) or len(expected) != 64:
        raise InputError(f"{label} SHA-256 is invalid")
    path = workspace_path(workspace_root, path_text)
    if not path.is_file():
        raise InputError(f"{label} file is absent: {path_text}")
    actual = sha256_file(path)
    if actual != expected:
        raise InputError(
            f"{label} SHA-256 mismatch: expected={expected}; actual={actual}"
        )
    return path, load_json(path)


def escape_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def iter_json_leaves(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        if not value:
            yield pointer or "/", value
            return
        for key in sorted(value):
            child = f"{pointer}/{escape_pointer_token(key)}"
            yield from iter_json_leaves(value[key], child)
        return
    if isinstance(value, list):
        if not value:
            yield pointer or "/", value
            return
        for index, item in enumerate(value):
            child = f"{pointer}/{index}"
            yield from iter_json_leaves(item, child)
        return
    yield pointer or "/", value


def json_pointer(document: Any, pointer: str) -> tuple[bool, Any]:
    if pointer == "/":
        return True, document
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return False, None
    current = document
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            try:
                current = current[int(token)]
            except (ValueError, IndexError):
                return False, None
        elif isinstance(current, dict) and token in current:
            current = current[token]
        else:
            return False, None
    return True, current


def require_object(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    return value


def require_list(value: Any, label: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{label} must be an array")
        return []
    return value


def validate_policy(policy: Any) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    policy = require_object(policy, "policy", errors)
    if policy.get("schema") != "complete_operator_json_generation_policy_v1":
        errors.append("policy schema mismatch")
    if set(policy.get("origins", [])) != ORIGINS:
        errors.append("policy origin enum mismatch")
    if set(policy.get("applicability_classes", [])) != APPLICABILITY:
        errors.append("policy applicability enum mismatch")
    if set(policy.get("source_absence_states", [])) != ABSENCE_STATES:
        errors.append("policy source-absence enum mismatch")
    if set(policy.get("handler_capability_axes", [])) != CAPABILITY_AXES:
        errors.append("policy handler-capability axes mismatch")
    if set(policy.get("exactness_axes", [])) != EXACTNESS_AXES:
        errors.append("policy exactness axes mismatch")
    if set(policy.get("current_diff_classes", [])) != DIFF_CLASSES:
        errors.append("policy current-diff enum mismatch")
    return policy, errors


def authority_index(authority: Any) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    authority = require_object(authority, "authority", errors)
    if authority.get("schema") != "operator-config-user-authority-v1":
        errors.append("operator-config authority schema mismatch")
    records = require_list(authority.get("records"), "authority.records", errors)
    indexed: dict[str, dict[str, Any]] = {}
    for item in records:
        if not isinstance(item, dict):
            errors.append("authority record must be an object")
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path:
            errors.append("authority record path is missing")
            continue
        if path in indexed:
            errors.append(f"duplicate authority record: {path}")
            continue
        indexed[path] = item
    return indexed, errors


def validate_contract_shape(contract: Any) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    contract = require_object(contract, "candidate contract", errors)
    if contract.get("schema") != "operator_config_complete_json_candidate_v1":
        errors.append("candidate contract schema mismatch")
    family = contract.get("family")
    if not isinstance(family, str) or not family:
        errors.append("candidate family is missing")
    if contract.get("candidate_status") not in {"COMPLETE", "BLOCKED"}:
        errors.append("candidate_status must be COMPLETE or BLOCKED")
    if contract.get("reference_class") not in REFERENCE_CLASSES:
        errors.append("reference_class must be A, B, C, or D")
    changed = contract.get("changed_axes")
    if not isinstance(changed, list) or any(item not in CHANGED_AXES for item in changed):
        errors.append("changed_axes contains an unknown axis")
    elif len(changed) != len(set(changed)):
        errors.append("changed_axes contains duplicates")
    hw_types = contract.get("target_hw_op_types")
    if (
        not isinstance(hw_types, list)
        or not hw_types
        or any(not isinstance(item, str) or not item for item in hw_types)
        or len(hw_types) != len(set(hw_types))
    ):
        errors.append(
            "target_hw_op_types must be a non-empty unique string array"
        )
    stages = contract.get("stage_ids")
    if (
        not isinstance(stages, list)
        or not stages
        or any(not isinstance(item, str) or not item for item in stages)
        or len(stages) != len(set(stages))
    ):
        errors.append("stage_ids must be a non-empty unique string array")
    for name in (
        "candidate_json",
        "field_provenance_ledger",
        "handler_capability",
        "current_test_diff",
    ):
        if not isinstance(contract.get(name), dict):
            errors.append(f"{name} binding is missing")
    composition = contract.get("composition")
    if not isinstance(composition, dict) or not isinstance(
        composition.get("required"), bool
    ):
        errors.append("composition contract is missing")
    artifact_root = contract.get("artifact_root")
    if not isinstance(artifact_root, str) or not artifact_root:
        errors.append("artifact_root is missing")
    claim = contract.get("claim_boundary")
    if not isinstance(claim, str) or not claim:
        errors.append("candidate claim_boundary is missing")
    return contract, errors


def lowering_stage_index(
    lowering: Any,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    lowering = require_object(lowering, "lowering bundle", errors)
    requests = require_list(lowering.get("requests"), "lowering.requests", errors)
    indexed: dict[str, dict[str, Any]] = {}
    for request in requests:
        if not isinstance(request, dict):
            errors.append("lowering request must be an object")
            continue
        identity = request.get("identity")
        if not isinstance(identity, dict):
            errors.append("lowering request identity is missing")
            continue
        stage_id = identity.get("hw_op_id")
        hw_op_type = identity.get("hw_op_type")
        if not isinstance(stage_id, str) or not stage_id:
            errors.append("lowering request hw_op_id is missing")
            continue
        if not isinstance(hw_op_type, str) or not hw_op_type:
            errors.append(f"lowering request hw_op_type is missing: {stage_id}")
            continue
        if stage_id in indexed:
            errors.append(f"duplicate lowering stage ID: {stage_id}")
            continue
        indexed[stage_id] = request
    coverage = lowering.get("coverage")
    if isinstance(coverage, dict):
        expected = coverage.get("stage_count")
        if isinstance(expected, int) and expected != len(indexed):
            errors.append(
                f"lowering stage count mismatch: declared={expected}; "
                f"actual={len(indexed)}"
            )
    return indexed, errors


def _check_bound_receipt(
    workspace_root: Path,
    reference: Any,
    label: str,
    errors: list[str],
) -> None:
    if reference is None:
        errors.append(f"{label} receipt is missing")
        return
    try:
        load_bound_file(workspace_root, reference, label=label)
    except InputError as error:
        errors.append(str(error))


def validate_field_ledger(
    *,
    workspace_root: Path,
    ledger: Any,
    candidate: Any,
    candidate_sha: str,
    family: str,
    candidate_status: str,
    authority: dict[str, dict[str, Any]],
) -> tuple[
    dict[str, dict[str, Any]],
    list[str],
    list[str],
    Counter[str],
]:
    errors: list[str] = []
    blockers: list[str] = []
    ledger = require_object(ledger, "field provenance ledger", errors)
    if ledger.get("schema") != "operator_config_field_provenance_ledger_v1":
        errors.append("field provenance ledger schema mismatch")
    if ledger.get("family") != family:
        errors.append("field provenance ledger family mismatch")
    if ledger.get("candidate_json_sha256") != candidate_sha:
        errors.append("field provenance ledger candidate SHA mismatch")
    if not isinstance(ledger.get("claim_boundary"), str):
        errors.append("field provenance ledger claim boundary is missing")

    candidate_leaves = dict(iter_json_leaves(candidate))
    entries = require_list(ledger.get("entries"), "ledger.entries", errors)
    indexed: dict[str, dict[str, Any]] = {}
    origin_counts: Counter[str] = Counter()
    for raw in entries:
        if not isinstance(raw, dict):
            errors.append("ledger entry must be an object")
            continue
        pointer = raw.get("json_pointer")
        if not isinstance(pointer, str) or not pointer.startswith("/"):
            errors.append("ledger entry JSON pointer is invalid")
            continue
        if pointer in indexed:
            errors.append(f"duplicate ledger entry: {pointer}")
            continue
        indexed[pointer] = raw
        if pointer not in candidate_leaves:
            errors.append(f"ledger pointer is not a candidate leaf: {pointer}")
            continue
        if raw.get("target_value") != candidate_leaves[pointer]:
            errors.append(f"ledger target value mismatch: {pointer}")

        origin = raw.get("origin")
        applicability = raw.get("applicability_class")
        status = raw.get("status")
        origin_counts[str(origin)] += 1
        if origin not in ORIGINS:
            errors.append(f"unknown origin at {pointer}: {origin}")
        if applicability not in APPLICABILITY:
            errors.append(
                f"unknown applicability class at {pointer}: {applicability}"
            )
        if status not in {"RESOLVED", "UNRESOLVED"}:
            errors.append(f"unknown ledger status at {pointer}: {status}")
        if candidate_status == "COMPLETE" and (
            origin == "UNRESOLVED"
            or applicability == "UNRESOLVED"
            or status == "UNRESOLVED"
        ):
            errors.append(f"COMPLETE candidate has unresolved leaf: {pointer}")
        if (
            origin == "UNRESOLVED"
            or applicability == "UNRESOLVED"
            or status == "UNRESOLVED"
        ):
            blockers.append(f"unresolved candidate leaf: {pointer}")
        if origin == "UNRESOLVED" and status != "UNRESOLVED":
            errors.append(f"UNRESOLVED origin has non-unresolved status: {pointer}")

        owner = raw.get("owner")
        equation = raw.get("consumer_equation")
        if not isinstance(owner, str) or not owner:
            errors.append(f"leaf owner is missing: {pointer}")
        if not isinstance(equation, str) or not equation:
            errors.append(f"consumer equation is missing: {pointer}")

        axes = raw.get("exactness_axes")
        if not isinstance(axes, dict) or set(axes) != EXACTNESS_AXES:
            errors.append(f"exactness axes are incomplete: {pointer}")
            axes = {}
        elif any(not isinstance(value, bool) for value in axes.values()):
            errors.append(f"exactness axes must be boolean: {pointer}")

        controls = raw.get("negative_control_ids")
        if not isinstance(controls, list) or any(
            not isinstance(item, str) or not item for item in controls
        ):
            errors.append(f"negative_control_ids are invalid: {pointer}")
            controls = []

        source = raw.get("source")
        if origin == "REFERENCE_EXACT":
            if not isinstance(source, dict):
                errors.append(f"REFERENCE_EXACT leaf lacks source: {pointer}")
            else:
                source_path = source.get("path")
                record = authority.get(source_path)
                if record is None:
                    errors.append(
                        f"REFERENCE_EXACT source is not authorized: {pointer}: "
                        f"{source_path}"
                    )
                else:
                    provenance = record.get("provenance", {})
                    expected_commit = provenance.get("pinned_commit")
                    expected_blob = provenance.get("pinned_git_blob_oid")
                    expected_sha = record.get("sha256")
                    if source.get("commit") != expected_commit:
                        errors.append(f"source commit mismatch: {pointer}")
                    if source.get("blob_oid") != expected_blob:
                        errors.append(f"source blob OID mismatch: {pointer}")
                    if source.get("file_sha256") != expected_sha:
                        errors.append(f"source file SHA mismatch: {pointer}")
                    try:
                        source_file = workspace_path(workspace_root, source_path)
                    except InputError as error:
                        errors.append(str(error))
                        source_file = Path()
                    if not source_file.is_file():
                        errors.append(
                            f"authorized source file is absent from workspace: "
                            f"{source_path}"
                        )
                    else:
                        actual_sha = sha256_file(source_file)
                        if actual_sha != expected_sha:
                            errors.append(
                                f"authorized source bytes do not match authority: "
                                f"{source_path}"
                            )
                        try:
                            source_json = load_json(source_file)
                        except InputError as error:
                            errors.append(str(error))
                        else:
                            found, value = json_pointer(
                                source_json, source.get("json_pointer")
                            )
                            if not found:
                                errors.append(
                                    f"source JSON pointer is absent: {pointer}"
                                )
                            elif value != source.get("value"):
                                errors.append(
                                    f"source ledger value mismatch: {pointer}"
                                )
                            elif value != raw.get("target_value"):
                                errors.append(
                                    f"REFERENCE_EXACT target differs from source: "
                                    f"{pointer}"
                                )
            if applicability == "EXACT_SOURCE_INSTANCE" and axes and not all(
                axes.values()
            ):
                errors.append(
                    f"EXACT_SOURCE_INSTANCE has non-exact axis: {pointer}"
                )
            if applicability == "PROVEN_INVARIANT":
                if not controls:
                    errors.append(
                        f"PROVEN_INVARIANT lacks negative control: {pointer}"
                    )
                _check_bound_receipt(
                    workspace_root,
                    raw.get("derivation_receipt"),
                    f"proven invariant {pointer}",
                    errors,
                )
        elif origin in DERIVED_ORIGINS:
            if applicability != "DERIVED_FOR_TARGET":
                errors.append(
                    f"derived origin lacks DERIVED_FOR_TARGET applicability: "
                    f"{pointer}"
                )
            _check_bound_receipt(
                workspace_root,
                raw.get("derivation_receipt"),
                f"derived leaf {pointer}",
                errors,
            )
        elif origin == "EXPLICIT_DISABLED":
            if applicability != "EXPLICITLY_INACTIVE":
                errors.append(
                    f"EXPLICIT_DISABLED leaf is not explicitly inactive: {pointer}"
                )
        if applicability == "EXACT_SOURCE_INSTANCE" and origin != "REFERENCE_EXACT":
            errors.append(
                f"EXACT_SOURCE_INSTANCE must use REFERENCE_EXACT: {pointer}"
            )

    missing = sorted(set(candidate_leaves) - set(indexed))
    extra = sorted(set(indexed) - set(candidate_leaves))
    if missing:
        errors.append(f"candidate leaves missing from ledger: {missing}")
    if extra:
        errors.append(f"ledger contains non-leaf pointers: {extra}")

    absences = require_list(
        ledger.get("source_absences"), "ledger.source_absences", errors
    )
    absence_pointers: set[str] = set()
    for raw in absences:
        if not isinstance(raw, dict):
            errors.append("source absence entry must be an object")
            continue
        pointer = raw.get("target_json_pointer")
        state = raw.get("state")
        if not isinstance(pointer, str) or not pointer.startswith("/"):
            errors.append("source absence pointer is invalid")
            continue
        if pointer in absence_pointers:
            errors.append(f"duplicate source absence entry: {pointer}")
        absence_pointers.add(pointer)
        if state not in ABSENCE_STATES:
            errors.append(f"unknown source absence state: {pointer}: {state}")
        if not isinstance(raw.get("reason"), str) or not raw.get("reason"):
            errors.append(f"source absence reason is missing: {pointer}")
        if not isinstance(raw.get("owner"), str) or not raw.get("owner"):
            errors.append(f"source absence owner is missing: {pointer}")
        found, value = json_pointer(candidate, pointer)
        if state == "SOURCE_ABSENT_UNKNOWN_FOR_TARGET" and candidate_status == "COMPLETE":
            errors.append(
                f"COMPLETE candidate has unknown absent source field: {pointer}"
            )
        if state == "SOURCE_ABSENT_UNKNOWN_FOR_TARGET":
            blockers.append(f"unknown source-absent target field: {pointer}")
        elif state == "EXPLICIT_NULL_INACTIVE":
            if not found or value is not None:
                errors.append(f"explicit-null state does not bind null: {pointer}")
        elif state == "EXPLICIT_ZERO":
            if not found or value != 0 or isinstance(value, bool):
                errors.append(f"explicit-zero state does not bind zero: {pointer}")
        elif state == "TARGET_REQUIRED_DERIVED":
            entry = indexed.get(pointer)
            if not found or entry is None or entry.get("origin") not in DERIVED_ORIGINS:
                errors.append(
                    f"target-required-derived field lacks derived leaf: {pointer}"
                )
    return indexed, errors, blockers, origin_counts


def validate_handler_capability(
    *,
    workspace_root: Path,
    document: Any,
    family: str,
    candidate_status: str,
    reference_class: str,
    changed_axes: set[str],
    ledger: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    blockers: list[str] = []
    document = require_object(document, "handler capability", errors)
    if document.get("schema") != "operator_config_handler_capability_v1":
        errors.append("handler capability schema mismatch")
    if document.get("family") != family:
        errors.append("handler capability family mismatch")
    if not isinstance(document.get("claim_boundary"), str):
        errors.append("handler capability claim boundary is missing")
    handler = require_object(document.get("handler"), "handler", errors)
    kind = handler.get("kind")
    if kind not in {
        "NATIVE_COMPLETE",
        "NATIVE_CONSERVATIVE",
        "PLACEHOLDER",
        "AUTHORIZED_PATCH",
        "NONE",
    }:
        errors.append(f"unknown handler kind: {kind}")
    path_text = handler.get("path")
    handler_sha = handler.get("sha256")
    if kind == "NONE":
        if path_text is not None or handler_sha is not None:
            errors.append("NONE handler must not claim path or SHA")
    else:
        if not isinstance(path_text, str) or not path_text:
            errors.append("handler path is missing")
        elif not isinstance(handler_sha, str) or len(handler_sha) != 64:
            errors.append("handler SHA is invalid")
        else:
            try:
                path = workspace_path(workspace_root, path_text)
            except InputError as error:
                errors.append(str(error))
            else:
                if not path.is_file():
                    errors.append(f"handler file is absent: {path_text}")
                elif sha256_file(path) != handler_sha:
                    errors.append(f"handler SHA mismatch: {path_text}")

    capabilities = require_object(
        document.get("capabilities"), "handler.capabilities", errors
    )
    if set(capabilities) != CAPABILITY_AXES:
        errors.append("handler capabilities do not cover the canonical axes")
    supported: dict[str, bool] = {}
    for axis in CAPABILITY_AXES:
        item = capabilities.get(axis)
        if not isinstance(item, dict):
            errors.append(f"handler capability is absent: {axis}")
            continue
        flag = item.get("supported")
        evidence = item.get("evidence")
        if not isinstance(flag, bool):
            errors.append(f"handler capability flag is invalid: {axis}")
            continue
        if not isinstance(evidence, str) or not evidence:
            errors.append(f"handler capability evidence is missing: {axis}")
        supported[axis] = flag

    if kind in {"NATIVE_CONSERVATIVE", "PLACEHOLDER", "NONE"}:
        forbidden = {
            "shape",
            "dtype",
            "qparam",
            "layout",
            "cross_stage_schedule",
        }
        for axis in sorted(forbidden):
            if supported.get(axis):
                errors.append(
                    f"{kind} handler overclaims generalization capability: {axis}"
                )
    if candidate_status == "COMPLETE":
        if reference_class == "A" and not supported.get("exact_replay", False):
            errors.append("class-A COMPLETE candidate lacks exact-replay capability")
        for axis in sorted(changed_axes):
            if not supported.get(axis, False):
                errors.append(
                    f"COMPLETE candidate changes unsupported handler axis: {axis}"
                )
    else:
        if reference_class == "A" and not supported.get("exact_replay", False):
            blockers.append("class-A candidate lacks exact-replay capability")
        for axis in sorted(changed_axes):
            if not supported.get(axis, False):
                blockers.append(f"unsupported handler axis: {axis}")

    dependent = require_list(
        document.get("dependent_leaves"), "handler.dependent_leaves", errors
    )
    indexed: dict[str, dict[str, Any]] = {}
    for raw in dependent:
        if not isinstance(raw, dict):
            errors.append("handler dependent leaf must be an object")
            continue
        pointer = raw.get("json_pointer")
        if not isinstance(pointer, str) or pointer not in ledger:
            errors.append(f"handler dependent leaf is not in ledger: {pointer}")
            continue
        if pointer in indexed:
            errors.append(f"duplicate handler dependent leaf: {pointer}")
            continue
        indexed[pointer] = raw
        axes = raw.get("axes")
        if (
            not isinstance(axes, list)
            or not axes
            or any(axis not in CHANGED_AXES for axis in axes)
            or len(axes) != len(set(axes))
        ):
            errors.append(f"handler dependent axes are invalid: {pointer}")
        if not isinstance(raw.get("covered_by"), str) or not raw.get("covered_by"):
            errors.append(f"handler dependent leaf has no coverage owner: {pointer}")
        if raw.get("status") not in {"COVERED", "UNCOVERED"}:
            errors.append(f"handler dependent leaf status is invalid: {pointer}")
        if candidate_status == "COMPLETE" and raw.get("status") != "COVERED":
            errors.append(f"COMPLETE candidate has uncovered dependency: {pointer}")
        if raw.get("status") == "UNCOVERED":
            blockers.append(f"uncovered handler-dependent leaf: {pointer}")

    for pointer, entry in ledger.items():
        axes = entry.get("exactness_axes")
        if not isinstance(axes, dict):
            continue
        required = {
            changed
            for changed in changed_axes
            if axes.get(CAPABILITY_TO_EXACTNESS[changed]) is False
        }
        if not required:
            continue
        declared = set(indexed.get(pointer, {}).get("axes", []))
        missing = sorted(required - declared)
        if missing:
            errors.append(
                f"changed-axis dependent leaf is not covered: {pointer}: {missing}"
            )
    summary = {
        "handler_kind": kind,
        "supported_axes": sorted(axis for axis, flag in supported.items() if flag),
        "dependent_leaf_count": len(indexed),
        "uncovered_count": sum(
            1 for item in indexed.values() if item.get("status") == "UNCOVERED"
        ),
    }
    return errors, blockers, summary


def validate_composition(
    *,
    document: Any,
    family: str,
    candidate_status: str,
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    blockers: list[str] = []
    document = require_object(document, "composition boundary", errors)
    if document.get("schema") != "operator_config_composition_boundary_v1":
        errors.append("composition boundary schema mismatch")
    if document.get("family") != family:
        errors.append("composition boundary family mismatch")
    if not isinstance(document.get("claim_boundary"), str):
        errors.append("composition boundary claim boundary is missing")
    boundaries = require_list(
        document.get("boundaries"), "composition.boundaries", errors
    )
    if not boundaries:
        errors.append("composition boundary list is empty")
    unresolved = 0
    for raw in boundaries:
        if not isinstance(raw, dict):
            errors.append("composition boundary must be an object")
            continue
        boundary_id = raw.get("boundary_id")
        if not isinstance(boundary_id, str) or not boundary_id:
            errors.append("composition boundary ID is missing")
            boundary_id = "<unknown>"
        for name in (
            "producer_dtype",
            "consumer_dtype",
            "shape",
            "layout",
            "producer_byte_set",
            "consumer_required_byte_set",
            "tag_last",
            "clock_handshake",
            "lifetime_visibility",
            "qparam_rounding",
        ):
            if not isinstance(raw.get(name), str) or not raw.get(name):
                errors.append(f"composition field is missing: {boundary_id}: {name}")
        if not isinstance(raw.get("transaction_bytes"), int) or raw.get(
            "transaction_bytes", 0
        ) <= 0:
            errors.append(
                f"composition transaction_bytes is invalid: {boundary_id}"
            )
        if raw.get("producer_byte_set") != raw.get("consumer_required_byte_set"):
            errors.append(f"composition byte-set mismatch: {boundary_id}")
        if raw.get("status") == "UNRESOLVED":
            unresolved += 1
            blockers.append(f"unresolved composition boundary: {boundary_id}")
            if candidate_status == "COMPLETE":
                errors.append(
                    f"COMPLETE candidate has unresolved composition: {boundary_id}"
                )
        elif raw.get("status") != "RESOLVED":
            errors.append(f"composition status is invalid: {boundary_id}")
        evidence = raw.get("evidence")
        if (
            not isinstance(evidence, list)
            or not evidence
            or any(not isinstance(item, str) or not item for item in evidence)
        ):
            errors.append(f"composition evidence is missing: {boundary_id}")
    return errors, blockers, {
        "boundary_count": len(boundaries),
        "unresolved_count": unresolved,
    }


def validate_current_diff(
    *,
    workspace_root: Path,
    document: Any,
    family: str,
    candidate: Any,
    candidate_sha: str,
) -> tuple[list[str], Counter[str], dict[str, Any]]:
    errors: list[str] = []
    document = require_object(document, "current-test diff", errors)
    if document.get("schema") != "operator_config_current_test_diff_v1":
        errors.append("current-test diff schema mismatch")
    if document.get("family") != family:
        errors.append("current-test diff family mismatch")
    if document.get("candidate_json_sha256") != candidate_sha:
        errors.append("current-test diff candidate SHA mismatch")
    if not isinstance(document.get("claim_boundary"), str):
        errors.append("current-test diff claim boundary is missing")
    identity = require_object(
        document.get("current_identity"), "current_identity", errors
    )
    available = identity.get("available")
    if not isinstance(available, bool):
        errors.append("current_identity.available must be boolean")
        available = False
    current: Any = None
    if available:
        path_text = identity.get("path")
        expected_sha = identity.get("sha256")
        if not isinstance(path_text, str) or not path_text:
            errors.append("available current identity lacks path")
        elif not isinstance(expected_sha, str) or len(expected_sha) != 64:
            errors.append("available current identity lacks SHA")
        else:
            try:
                path = workspace_path(workspace_root, path_text)
            except InputError as error:
                errors.append(str(error))
            else:
                if not path.is_file():
                    errors.append(f"current config is absent: {path_text}")
                elif sha256_file(path) != expected_sha:
                    errors.append(f"current config SHA mismatch: {path_text}")
                else:
                    try:
                        current = load_json(path)
                    except InputError as error:
                        errors.append(str(error))
    elif identity.get("path") is not None or identity.get("sha256") is not None:
        errors.append("unavailable current identity must use null path and SHA")
    if not isinstance(identity.get("latest_result"), str) or not identity.get(
        "latest_result"
    ):
        errors.append("current identity latest_result is missing")

    candidate_leaves = dict(iter_json_leaves(candidate))
    entries = require_list(document.get("entries"), "current diff entries", errors)
    indexed: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    for raw in entries:
        if not isinstance(raw, dict):
            errors.append("current diff entry must be an object")
            continue
        pointer = raw.get("json_pointer")
        if not isinstance(pointer, str) or pointer not in candidate_leaves:
            errors.append(f"current diff pointer is not a candidate leaf: {pointer}")
            continue
        if pointer in indexed:
            errors.append(f"duplicate current diff entry: {pointer}")
            continue
        indexed[pointer] = raw
        if raw.get("candidate_value") != candidate_leaves[pointer]:
            errors.append(f"current diff candidate value mismatch: {pointer}")
        classification = raw.get("classification")
        if classification not in DIFF_CLASSES:
            errors.append(
                f"current diff classification is invalid: {pointer}: "
                f"{classification}"
            )
        counts[str(classification)] += 1
        if not isinstance(raw.get("reason"), str) or not raw.get("reason"):
            errors.append(f"current diff reason is missing: {pointer}")
        evidence = raw.get("evidence")
        if not isinstance(evidence, list) or any(
            not isinstance(item, str) or not item for item in evidence
        ):
            errors.append(f"current diff evidence is invalid: {pointer}")
        present = raw.get("current_value_present")
        if not isinstance(present, bool):
            errors.append(f"current_value_present is invalid: {pointer}")
            present = False
        found, actual = json_pointer(current, pointer) if current is not None else (
            False,
            None,
        )
        if present != found:
            errors.append(f"current value presence mismatch: {pointer}")
        if found and raw.get("current_value") != actual:
            errors.append(f"current diff bound value mismatch: {pointer}")
        if classification == "SAME":
            if not found or actual != candidate_leaves[pointer]:
                errors.append(f"SAME classification has unequal values: {pointer}")
        if classification == "CURRENT_ABSENT" and found:
            errors.append(f"CURRENT_ABSENT has a current value: {pointer}")
        if current is None and classification != "CURRENT_ABSENT":
            errors.append(
                f"unavailable current config must classify CURRENT_ABSENT: {pointer}"
            )
    missing = sorted(set(candidate_leaves) - set(indexed))
    if missing:
        errors.append(f"candidate leaves missing from current diff: {missing}")

    blocker_attribution = require_list(
        document.get("blocker_attribution"), "blocker_attribution", errors
    )
    blocker_counts: Counter[str] = Counter()
    for raw in blocker_attribution:
        if not isinstance(raw, dict):
            errors.append("blocker attribution must be an object")
            continue
        blocker_id = raw.get("blocker_id")
        classification = raw.get("classification")
        if not isinstance(blocker_id, str) or not blocker_id:
            errors.append("blocker attribution ID is missing")
        if classification not in {
            "CONFIG_EXPLAINS",
            "CONFIG_CONTRIBUTES",
            "CONFIG_EXCLUDED",
            "DYNAMIC_ONLY",
            "INSUFFICIENT_EVIDENCE",
        }:
            errors.append(f"blocker attribution class is invalid: {blocker_id}")
        blocker_counts[str(classification)] += 1
        pointers = raw.get("candidate_json_pointers")
        if not isinstance(pointers, list) or any(
            pointer not in candidate_leaves for pointer in pointers
        ):
            errors.append(f"blocker attribution pointers are invalid: {blocker_id}")
        if not isinstance(raw.get("reason"), str) or not raw.get("reason"):
            errors.append(f"blocker attribution reason is missing: {blocker_id}")
        evidence = raw.get("evidence")
        if not isinstance(evidence, list) or any(
            not isinstance(item, str) or not item for item in evidence
        ):
            errors.append(f"blocker attribution evidence is invalid: {blocker_id}")
    return errors, counts, {
        "available": available,
        "blocker_class_counts": dict(sorted(blocker_counts.items())),
    }


def scan_forbidden_outputs(
    artifact_root: Path,
    patterns: list[str],
) -> list[str]:
    violations: list[str] = []
    if not artifact_root.is_dir():
        return [f"artifact root is absent: {artifact_root}"]
    for path in artifact_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(artifact_root).as_posix()
        if any(
            fnmatch.fnmatchcase(path.name, pattern)
            or fnmatch.fnmatchcase(relative, pattern)
            for pattern in patterns
        ):
            violations.append(relative)
    return sorted(violations)


def validate(
    *,
    workspace_root: Path,
    contract_path: Path,
    authority_path: Path,
    policy_path: Path,
    lowering_path: Path = DEFAULT_LOWERING,
) -> dict[str, Any]:
    errors: list[str] = []
    completion_blockers: list[str] = []
    try:
        contract_raw = load_json(contract_path)
        authority_raw = load_json(authority_path)
        policy_raw = load_json(policy_path)
        lowering_raw = load_json(lowering_path)
    except InputError as error:
        return {
            "schema": "complete_operator_json_validation_report_v1",
            "pass": False,
            "errors": [str(error)],
            "claim_boundary": (
                "Input binding failure only; no operator configuration claim."
            ),
        }

    contract, contract_errors = validate_contract_shape(contract_raw)
    policy, policy_errors = validate_policy(policy_raw)
    authority, authority_errors = authority_index(authority_raw)
    lowering, lowering_errors = lowering_stage_index(lowering_raw)
    errors.extend(contract_errors)
    errors.extend(policy_errors)
    errors.extend(authority_errors)
    errors.extend(lowering_errors)
    family = contract.get("family", "<invalid>")
    candidate_status = contract.get("candidate_status", "<invalid>")
    reference_class = contract.get("reference_class", "<invalid>")
    changed_axes = set(contract.get("changed_axes", []))
    target_hw_op_types = set(contract.get("target_hw_op_types", []))
    for stage_id in contract.get("stage_ids", []):
        request = lowering.get(stage_id)
        if request is None:
            errors.append(f"candidate stage is absent from lowering: {stage_id}")
            continue
        actual_type = request["identity"]["hw_op_type"]
        if actual_type not in target_hw_op_types:
            errors.append(
                f"candidate stage type is outside target_hw_op_types: "
                f"{stage_id}: {actual_type}"
            )

    documents: dict[str, Any] = {}
    paths: dict[str, Path] = {}
    for name in (
        "candidate_json",
        "field_provenance_ledger",
        "handler_capability",
        "current_test_diff",
    ):
        try:
            path, value = load_bound_file(
                workspace_root,
                contract.get(name),
                label=name,
            )
        except InputError as error:
            errors.append(str(error))
        else:
            paths[name] = path
            documents[name] = value

    candidate = documents.get("candidate_json")
    candidate_sha = (
        sha256_file(paths["candidate_json"]) if "candidate_json" in paths else ""
    )
    ledger: dict[str, dict[str, Any]] = {}
    origin_counts: Counter[str] = Counter()
    if candidate is not None and "field_provenance_ledger" in documents:
        (
            ledger,
            ledger_errors,
            ledger_blockers,
            origin_counts,
        ) = validate_field_ledger(
            workspace_root=workspace_root,
            ledger=documents["field_provenance_ledger"],
            candidate=candidate,
            candidate_sha=candidate_sha,
            family=family,
            candidate_status=candidate_status,
            authority=authority,
        )
        errors.extend(ledger_errors)
        completion_blockers.extend(ledger_blockers)

    handler_summary: dict[str, Any] = {}
    if ledger and "handler_capability" in documents:
        (
            handler_errors,
            handler_blockers,
            handler_summary,
        ) = validate_handler_capability(
            workspace_root=workspace_root,
            document=documents["handler_capability"],
            family=family,
            candidate_status=candidate_status,
            reference_class=reference_class,
            changed_axes=changed_axes,
            ledger=ledger,
        )
        errors.extend(handler_errors)
        completion_blockers.extend(handler_blockers)

    composition_summary = {
        "required": False,
        "boundary_count": 0,
        "unresolved_count": 0,
    }
    composition = contract.get("composition")
    if isinstance(composition, dict):
        required = composition.get("required")
        boundary_ref = composition.get("boundary")
        composition_summary["required"] = required
        if required:
            if not isinstance(boundary_ref, dict):
                errors.append("required composition boundary binding is missing")
            else:
                try:
                    _, boundary = load_bound_file(
                        workspace_root,
                        boundary_ref,
                        label="composition boundary",
                    )
                except InputError as error:
                    errors.append(str(error))
                else:
                    (
                        boundary_errors,
                        boundary_blockers,
                        boundary_summary,
                    ) = validate_composition(
                        document=boundary,
                        family=family,
                        candidate_status=candidate_status,
                    )
                    errors.extend(boundary_errors)
                    completion_blockers.extend(boundary_blockers)
                    composition_summary.update(boundary_summary)
        elif boundary_ref is not None:
            errors.append(
                "non-composite candidate must use null composition boundary"
            )

    diff_counts: Counter[str] = Counter()
    current_summary: dict[str, Any] = {}
    if candidate is not None and "current_test_diff" in documents:
        diff_errors, diff_counts, current_summary = validate_current_diff(
            workspace_root=workspace_root,
            document=documents["current_test_diff"],
            family=family,
            candidate=candidate,
            candidate_sha=candidate_sha,
        )
        errors.extend(diff_errors)

    artifact_root_text = contract.get("artifact_root")
    forbidden_outputs: list[str] = []
    if isinstance(artifact_root_text, str) and artifact_root_text:
        try:
            artifact_root = workspace_path(workspace_root, artifact_root_text)
        except InputError as error:
            errors.append(str(error))
        else:
            patterns = policy.get("forbidden_outputs", [])
            if not isinstance(patterns, list):
                errors.append("policy forbidden_outputs must be an array")
            else:
                forbidden_outputs = scan_forbidden_outputs(
                    artifact_root, patterns
                )
                if forbidden_outputs:
                    errors.append(
                        f"server-package outputs are forbidden: {forbidden_outputs}"
                    )

    completion_blockers = sorted(set(completion_blockers))
    if candidate_status == "BLOCKED" and not errors and not completion_blockers:
        errors.append(
            "BLOCKED candidate did not expose a machine-detectable unresolved "
            "field, unsupported capability, or composition boundary"
        )

    errors = sorted(set(errors))
    candidate_leaf_count = (
        sum(1 for _ in iter_json_leaves(candidate)) if candidate is not None else 0
    )
    return {
        "schema": "complete_operator_json_validation_report_v1",
        "contract": {
            "path": contract_path.relative_to(workspace_root).as_posix(),
            "sha256": sha256_file(contract_path),
        },
        "authority": {
            "path": authority_path.relative_to(workspace_root).as_posix(),
            "sha256": sha256_file(authority_path),
            "record_count": len(authority),
        },
        "policy": {
            "path": policy_path.relative_to(workspace_root).as_posix(),
            "sha256": sha256_file(policy_path),
        },
        "lowering": {
            "path": lowering_path.relative_to(workspace_root).as_posix(),
            "sha256": sha256_file(lowering_path),
            "stage_count": len(lowering),
        },
        "family": family,
        "candidate_status": candidate_status,
        "reference_class": reference_class,
        "stage_count": len(contract.get("stage_ids", []))
        if isinstance(contract.get("stage_ids"), list)
        else 0,
        "candidate_json_sha256": candidate_sha or None,
        "candidate_leaf_count": candidate_leaf_count,
        "ledger_leaf_count": len(ledger),
        "origin_counts": dict(sorted(origin_counts.items())),
        "handler": handler_summary,
        "composition": composition_summary,
        "current_diff_counts": dict(sorted(diff_counts.items())),
        "current": current_summary,
        "forbidden_server_package_outputs": forbidden_outputs,
        "completion_blockers": completion_blockers,
        "errors": errors,
        "contract_valid": not errors,
        "blocked_valid": (
            not errors
            and candidate_status == "BLOCKED"
            and bool(completion_blockers)
        ),
        "pass": (
            not errors
            and not completion_blockers
            and candidate_status == "COMPLETE"
        ),
        "claim_boundary": (
            "Local complete-JSON provenance/applicability/capability/composition/"
            "current-diff validation only. No mapping, bitstream, execplan, SCA, "
            "server package, server run, natural terminal, formal D, E3, E4, or "
            "E5 was generated or adjudicated."
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=ROOT,
        help="Workspace root used to resolve every bound relative path.",
    )
    parser.add_argument(
        "--authority",
        type=Path,
        default=DEFAULT_AUTHORITY,
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY,
    )
    parser.add_argument(
        "--lowering",
        type=Path,
        default=DEFAULT_LOWERING,
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_root = args.workspace_root.resolve()
    contract_path = args.contract.resolve()
    authority_path = args.authority.resolve()
    policy_path = args.policy.resolve()
    lowering_path = args.lowering.resolve()
    report = validate(
        workspace_root=workspace_root,
        contract_path=contract_path,
        authority_path=authority_path,
        policy_path=policy_path,
        lowering_path=lowering_path,
    )
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report.get("pass") is True else 1


if __name__ == "__main__":
    sys.exit(main())
