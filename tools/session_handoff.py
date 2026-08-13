#!/usr/bin/env python3
"""Validate and materialize exclusive Codex session ownership handoffs.

The helper never creates, messages, archives, or resumes a Codex task.  It
builds machine receipts around those UI operations so a role has exactly one
ACTIVE writer and completions always resolve the current mainline dynamically.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


REGISTRY_SCHEMA = "session-owner-registry-v1"
CAPSULE_SCHEMA = "session-handoff-capsule-v1"
ACCEPTANCE_SCHEMA = "session-handoff-acceptance-v1"
ACTIVATION_SCHEMA = "session-handoff-activation-v1"
PUBLICATION_SCHEMA = "session-handoff-publication-v1"
REPORT_SCHEMA = "session-handoff-validation-v1"
THREAD_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MANDATORY_READS = {
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/会话转接与所有权规则.md",
}


class HandoffError(ValueError):
    """A registry or handoff transition is unsafe."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_bytes(json_bytes(value))
    os.replace(temporary, path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_relative(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise HandoffError(f"unsafe relative path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise HandoffError(f"unsafe relative path: {value!r}")
    return path


def path_from_root(project_root: Path, relative: str) -> Path:
    path = project_root.joinpath(*safe_relative(relative).parts)
    resolved = path.resolve()
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError as error:
        raise HandoffError(f"path escapes project root: {relative}") from error
    if path.is_symlink() or not path.is_file():
        raise HandoffError(f"receipt source is absent or not a regular file: {relative}")
    return path


def receipt(project_root: Path, relative: str) -> dict[str, Any]:
    path = path_from_root(project_root, relative)
    data = path.read_bytes()
    return {"path": safe_relative(relative).as_posix(), "bytes": len(data), "sha256": sha256(data)}


def verify_receipt(project_root: Path, item: Any) -> str | None:
    if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
        return "receipt fields mismatch"
    try:
        actual = receipt(project_root, item["path"])
    except HandoffError as error:
        return str(error)
    if actual != item:
        return f"receipt drift: {item.get('path')}"
    return None


def _role_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        role.get("role_id"): role
        for role in registry.get("roles", [])
        if isinstance(role, dict) and isinstance(role.get("role_id"), str)
    }


def validate_registry(registry: Any, project_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(registry, dict):
        return ["registry must be an object"]
    required = {
        "schema",
        "registry_epoch",
        "mainline_role_id",
        "roles",
        "active_rule_receipts",
        "claim_boundary",
    }
    if set(registry) != required:
        errors.append("registry fields mismatch")
    if registry.get("schema") != REGISTRY_SCHEMA:
        errors.append("registry schema mismatch")
    if not isinstance(registry.get("registry_epoch"), int) or registry.get("registry_epoch", 0) < 1:
        errors.append("registry_epoch must be positive")
    roles = registry.get("roles")
    if not isinstance(roles, list) or not roles:
        errors.append("roles must be a non-empty array")
        roles = []
    role_ids: list[str] = []
    thread_ids: list[str] = []
    mainlines: list[dict[str, Any]] = []
    for index, role in enumerate(roles):
        if not isinstance(role, dict):
            errors.append(f"roles[{index}] must be an object")
            continue
        role_id = role.get("role_id")
        thread_id = role.get("thread_id")
        if not isinstance(role_id, str) or SAFE_NAME.fullmatch(role_id) is None:
            errors.append(f"roles[{index}].role_id is invalid")
        else:
            role_ids.append(role_id)
        if not isinstance(thread_id, str) or THREAD_ID.fullmatch(thread_id) is None:
            errors.append(f"roles[{index}].thread_id is invalid")
        else:
            thread_ids.append(thread_id)
        if role.get("role_kind") == "MAINLINE":
            mainlines.append(role)
        if role.get("status") != "ACTIVE":
            errors.append(f"roles[{index}] is not ACTIVE")
        if not isinstance(role.get("owner_epoch"), int) or role.get("owner_epoch", 0) < 1:
            errors.append(f"roles[{index}].owner_epoch is invalid")
        latest = role.get("latest_task_record")
        if latest is not None and project_root is not None:
            drift = verify_receipt(project_root, latest)
            if drift:
                errors.append(f"roles[{index}].latest_task_record: {drift}")
        task = role.get("current_task")
        if not isinstance(task, dict):
            errors.append(f"roles[{index}].current_task is invalid")
        elif task.get("pointer") is not None and project_root is not None:
            drift = verify_receipt(project_root, task["pointer"])
            if drift:
                errors.append(f"roles[{index}].current_task.pointer: {drift}")
        flight = role.get("in_flight")
        if not isinstance(flight, dict):
            errors.append(f"roles[{index}].in_flight is invalid")
        else:
            state = flight.get("state")
            package = flight.get("package")
            returned = flight.get("return_zip")
            root = flight.get("server_root")
            lease = flight.get("lease_id")
            if state == "NONE" and any(value is not None for value in (package, returned, root, lease)):
                errors.append(f"roles[{index}] NONE in_flight carries external state")
            if state in {"PACKAGE_READY_NOT_RUN", "SERVER_RUNNING"} and package is None:
                errors.append(f"roles[{index}] in-flight package receipt is absent")
            if state == "SERVER_RUNNING" and (root is None or lease is None):
                errors.append(f"roles[{index}] SERVER_RUNNING root/lease is absent")
            if state in {"RETURN_COLLECTED", "ANALYZING"} and returned is None:
                errors.append(f"roles[{index}] return receipt is absent")
            if project_root is not None:
                for label, item in (("package", package), ("return_zip", returned)):
                    if item is not None:
                        drift = verify_receipt(project_root, item)
                        if drift:
                            errors.append(f"roles[{index}].in_flight.{label}: {drift}")
    if len(role_ids) != len(set(role_ids)):
        errors.append("role IDs are not unique")
    if len(thread_ids) != len(set(thread_ids)):
        errors.append("one thread owns multiple ACTIVE roles")
    if len(mainlines) != 1:
        errors.append("registry must contain exactly one MAINLINE role")
    elif registry.get("mainline_role_id") != mainlines[0].get("role_id"):
        errors.append("mainline_role_id does not bind the sole MAINLINE role")
    rule_receipts = registry.get("active_rule_receipts")
    if not isinstance(rule_receipts, list) or len(rule_receipts) < 3:
        errors.append("at least three active rule receipts are required")
    elif project_root is not None:
        for index, item in enumerate(rule_receipts):
            drift = verify_receipt(project_root, item)
            if drift:
                errors.append(f"active_rule_receipts[{index}]: {drift}")
    return errors


def mainline_thread(registry: dict[str, Any]) -> str:
    roles = _role_map(registry)
    role = roles.get(registry.get("mainline_role_id"))
    if role is None:
        raise HandoffError("mainline role is absent")
    return role["thread_id"]


def build_capsule(
    registry_path: Path,
    request_path: Path,
    project_root: Path,
) -> dict[str, Any]:
    registry = load_json(registry_path)
    errors = validate_registry(registry, project_root)
    if errors:
        raise HandoffError("; ".join(errors))
    request = load_json(request_path)
    expected = {
        "schema",
        "role_id",
        "new_thread_id",
        "reason",
        "required_read_paths",
        "active_artifact_paths",
        "pending_messages",
        "first_action",
    }
    if not isinstance(request, dict) or set(request) != expected:
        raise HandoffError("handoff request fields mismatch")
    if request.get("schema") != "session-handoff-request-v1":
        raise HandoffError("handoff request schema mismatch")
    role = _role_map(registry).get(request["role_id"])
    if role is None:
        raise HandoffError("requested role is absent")
    new_thread = request["new_thread_id"]
    if not isinstance(new_thread, str) or THREAD_ID.fullmatch(new_thread) is None:
        raise HandoffError("new_thread_id is invalid")
    if new_thread == role["thread_id"]:
        raise HandoffError("new thread must differ from old thread")
    if new_thread in {item["thread_id"] for item in registry["roles"]}:
        raise HandoffError("new thread already owns an ACTIVE role")
    reads = request.get("required_read_paths")
    if not isinstance(reads, list) or not all(isinstance(item, str) for item in reads):
        raise HandoffError("required_read_paths is invalid")
    if not MANDATORY_READS.issubset(set(reads)):
        raise HandoffError(f"mandatory handoff reads are missing: {sorted(MANDATORY_READS - set(reads))}")
    artifacts = request.get("active_artifact_paths")
    if not isinstance(artifacts, list) or not all(isinstance(item, str) for item in artifacts):
        raise HandoffError("active_artifact_paths is invalid")
    registry_relative = registry_path.resolve().relative_to(project_root.resolve()).as_posix()
    registry_receipt = receipt(project_root, registry_relative)
    identity = {
        "role_id": role["role_id"],
        "old_thread_id": role["thread_id"],
        "new_thread_id": new_thread,
        "registry_sha256": registry_receipt["sha256"],
        "owner_epoch_after": role["owner_epoch"] + 1,
    }
    handoff_id = "handoff-" + sha256(json_bytes(identity))[:32]
    return {
        "schema": CAPSULE_SCHEMA,
        "handoff_id": handoff_id,
        "role_id": role["role_id"],
        "role_kind": role["role_kind"],
        "old_thread_id": role["thread_id"],
        "new_thread_id": new_thread,
        "registry_epoch_before": registry["registry_epoch"],
        "owner_epoch_before": role["owner_epoch"],
        "owner_epoch_after": role["owner_epoch"] + 1,
        "current_mainline_thread_id": mainline_thread(registry),
        "registry_before": registry_receipt,
        "reason": request["reason"],
        "required_read_receipts": [receipt(project_root, item) for item in reads],
        "active_artifact_receipts": [receipt(project_root, item) for item in artifacts],
        "current_task_snapshot": copy.deepcopy(role["current_task"]),
        "in_flight_snapshot": copy.deepcopy(role["in_flight"]),
        "pending_messages": request["pending_messages"],
        "authority": {
            "new_owner_before_activation": "READ_ONLY_ACCEPTANCE",
            "old_owner_after_activation": "RETIRED_READ_ONLY",
            "overlap_writers_allowed": False,
        },
        "first_action": request["first_action"],
        "claim_boundary": "Ownership continuity only; no package, server, RTL, config or result claim.",
    }


def build_acceptance(
    capsule_path: Path,
    registry_path: Path,
    new_thread_id: str,
    project_root: Path,
) -> dict[str, Any]:
    capsule = load_json(capsule_path)
    registry = load_json(registry_path)
    if capsule.get("schema") != CAPSULE_SCHEMA:
        raise HandoffError("capsule schema mismatch")
    if new_thread_id != capsule.get("new_thread_id"):
        raise HandoffError("accepting thread does not match capsule")
    if mainline_thread(registry) != capsule.get("current_mainline_thread_id"):
        raise HandoffError("current mainline changed before acceptance; rebuild capsule")
    registry_relative = registry_path.resolve().relative_to(project_root.resolve()).as_posix()
    observed = receipt(project_root, registry_relative)
    if observed != capsule.get("registry_before"):
        raise HandoffError("registry changed before acceptance; rebuild capsule")
    conflicts: list[str] = []
    for item in [*capsule.get("required_read_receipts", []), *capsule.get("active_artifact_receipts", [])]:
        drift = verify_receipt(project_root, item)
        if drift:
            conflicts.append(drift)
    if conflicts:
        raise HandoffError("; ".join(conflicts))
    capsule_relative = capsule_path.resolve().relative_to(project_root.resolve()).as_posix()
    return {
        "schema": ACCEPTANCE_SCHEMA,
        "handoff_id": capsule["handoff_id"],
        "role_id": capsule["role_id"],
        "new_thread_id": new_thread_id,
        "capsule": receipt(project_root, capsule_relative),
        "registry_observed": observed,
        "all_receipts_current": True,
        "snapshot_understood": True,
        "conflicts": [],
        "status": "ACCEPTED_READ_ONLY",
        "first_action": capsule["first_action"],
        "external_action_taken": False,
        "claim_boundary": "Read-only acceptance only. Authority remains with the old owner until activation.",
    }


def activate(
    registry_path: Path,
    capsule_path: Path,
    acceptance_path: Path,
    registry_output: Path,
    activation_order: int,
    project_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = load_json(registry_path)
    capsule = load_json(capsule_path)
    acceptance = load_json(acceptance_path)
    errors = validate_registry(registry, project_root)
    if errors:
        raise HandoffError("; ".join(errors))
    if registry_output.resolve() == registry_path.resolve():
        raise HandoffError("activation must first write a separate successor registry")
    registry_relative = registry_path.resolve().relative_to(project_root.resolve()).as_posix()
    if receipt(project_root, registry_relative) != capsule.get("registry_before"):
        raise HandoffError("registry changed after capsule preparation")
    if acceptance.get("status") != "ACCEPTED_READ_ONLY":
        raise HandoffError("handoff acceptance is not read-only accepted")
    for field in ("handoff_id", "role_id", "new_thread_id"):
        if acceptance.get(field) != capsule.get(field):
            raise HandoffError(f"acceptance {field} mismatch")
    capsule_relative = capsule_path.resolve().relative_to(project_root.resolve()).as_posix()
    if receipt(project_root, capsule_relative) != acceptance.get("capsule"):
        raise HandoffError("acceptance does not bind the exact capsule")
    acceptance_relative = acceptance_path.resolve().relative_to(project_root.resolve()).as_posix()
    roles = _role_map(registry)
    role = roles.get(capsule["role_id"])
    if role is None or role["thread_id"] != capsule["old_thread_id"]:
        raise HandoffError("old owner is no longer current")
    if role["owner_epoch"] != capsule["owner_epoch_before"]:
        raise HandoffError("old owner epoch drifted")
    if capsule["new_thread_id"] in {item["thread_id"] for item in registry["roles"]}:
        raise HandoffError("new thread already owns an ACTIVE role")
    successor = copy.deepcopy(registry)
    successor["registry_epoch"] += 1
    successor_role = _role_map(successor)[capsule["role_id"]]
    successor_role["thread_id"] = capsule["new_thread_id"]
    successor_role["owner_epoch"] = capsule["owner_epoch_after"]
    write_json(registry_output, successor)
    successor_errors = validate_registry(successor, project_root)
    if successor_errors:
        raise HandoffError("successor registry invalid: " + "; ".join(successor_errors))
    after_relative = registry_output.resolve().relative_to(project_root.resolve()).as_posix()
    activation = {
        "schema": ACTIVATION_SCHEMA,
        "handoff_id": capsule["handoff_id"],
        "role_id": capsule["role_id"],
        "old_thread_id": capsule["old_thread_id"],
        "new_thread_id": capsule["new_thread_id"],
        "registry_epoch_before": registry["registry_epoch"],
        "registry_epoch_after": successor["registry_epoch"],
        "registry_before": receipt(project_root, registry_relative),
        "registry_after": receipt(project_root, after_relative),
        "acceptance": receipt(project_root, acceptance_relative),
        "old_owner_status": "RETIRED_READ_ONLY",
        "new_owner_status": "ACTIVE",
        "current_mainline_thread_id": mainline_thread(successor),
        "activation_order": activation_order,
        "claim_boundary": "Atomic ownership-pointer successor receipt only; UI archival is a separate post-activation action.",
    }
    # The exact capsule receipt is already transitively bound by acceptance.
    assert receipt(project_root, capsule_relative) == acceptance["capsule"]
    return successor, activation


def publish_activation(
    registry_path: Path,
    successor_path: Path,
    activation_path: Path,
    project_root: Path,
) -> dict[str, Any]:
    """Atomically publish one already-validated successor as the current registry.

    The exact current bytes must still match the activation's expected-before
    receipt.  This prevents a stale handoff from overwriting a newer owner.
    """

    if registry_path.resolve() == successor_path.resolve():
        raise HandoffError("successor registry must be separate from current registry")
    activation = load_json(activation_path)
    if activation.get("schema") != ACTIVATION_SCHEMA:
        raise HandoffError("activation schema mismatch")
    registry_relative = registry_path.resolve().relative_to(project_root.resolve()).as_posix()
    successor_relative = successor_path.resolve().relative_to(project_root.resolve()).as_posix()
    activation_relative = activation_path.resolve().relative_to(project_root.resolve()).as_posix()
    current_before = receipt(project_root, registry_relative)
    successor_receipt = receipt(project_root, successor_relative)
    if current_before != activation.get("registry_before"):
        raise HandoffError("current registry drifted; stale activation cannot publish")
    if successor_receipt != activation.get("registry_after"):
        raise HandoffError("successor registry does not match activation")
    successor = load_json(successor_path)
    errors = validate_registry(successor, project_root)
    if errors:
        raise HandoffError("successor registry invalid: " + "; ".join(errors))
    roles = _role_map(successor)
    role = roles.get(activation.get("role_id"))
    if (
        role is None
        or role.get("thread_id") != activation.get("new_thread_id")
        or activation.get("current_mainline_thread_id") != mainline_thread(successor)
    ):
        raise HandoffError("activation identity does not match successor registry")
    data = successor_path.read_bytes()
    temporary = registry_path.with_name(f".{registry_path.name}.publish.{os.getpid()}")
    temporary.write_bytes(data)
    os.replace(temporary, registry_path)
    published = receipt(project_root, registry_relative)
    if published["sha256"] != successor_receipt["sha256"] or published["bytes"] != successor_receipt["bytes"]:
        raise HandoffError("published current registry bytes differ from successor")
    return {
        "schema": PUBLICATION_SCHEMA,
        "handoff_id": activation["handoff_id"],
        "role_id": activation["role_id"],
        "old_thread_id": activation["old_thread_id"],
        "new_thread_id": activation["new_thread_id"],
        "activation": receipt(project_root, activation_relative),
        "expected_registry_before": current_before,
        "published_current_registry": published,
        "atomic_replace": True,
        "status": "REGISTRY_ACTIVATED",
        "claim_boundary": "Current ownership pointer publication only; no UI, package, server, RTL, config or result action.",
    }


def audit_campaign(
    before: dict[str, Any],
    after: dict[str, Any],
    activations: list[dict[str, Any]],
    excluded_thread_ids: set[str],
) -> list[str]:
    errors: list[str] = []
    before_roles = _role_map(before)
    after_roles = _role_map(after)
    if set(before_roles) != set(after_roles):
        errors.append("campaign changed the role exact-set")
        return errors
    expected_changed = {
        role_id
        for role_id, role in before_roles.items()
        if role["thread_id"] not in excluded_thread_ids
    }
    actual_changed = {
        role_id
        for role_id in before_roles
        if before_roles[role_id]["thread_id"] != after_roles[role_id]["thread_id"]
    }
    if actual_changed != expected_changed:
        errors.append(
            f"campaign changed role set mismatch: expected={sorted(expected_changed)} actual={sorted(actual_changed)}"
        )
    for role_id, role in before_roles.items():
        if role["thread_id"] in excluded_thread_ids:
            if after_roles[role_id] != role:
                errors.append(f"excluded role changed: {role_id}")
    by_role = {item.get("role_id"): item for item in activations if isinstance(item, dict)}
    if set(by_role) != expected_changed:
        errors.append("activation receipt role exact-set mismatch")
    orders = sorted(item.get("activation_order") for item in activations if isinstance(item.get("activation_order"), int))
    if orders != list(range(1, len(expected_changed) + 1)):
        errors.append("activation_order must be contiguous from 1")
    mainline_role = before["mainline_role_id"]
    if mainline_role in expected_changed and by_role.get(mainline_role, {}).get("activation_order") != 1:
        errors.append("mainline must be activated first")
    for role_id in expected_changed:
        item = by_role.get(role_id, {})
        if item.get("old_thread_id") != before_roles[role_id]["thread_id"]:
            errors.append(f"activation old owner mismatch: {role_id}")
        if item.get("new_thread_id") != after_roles[role_id]["thread_id"]:
            errors.append(f"activation new owner mismatch: {role_id}")
        if after_roles[role_id]["owner_epoch"] != before_roles[role_id]["owner_epoch"] + 1:
            errors.append(f"owner epoch mismatch: {role_id}")
    if after["registry_epoch"] != before["registry_epoch"] + len(expected_changed):
        errors.append("final registry epoch does not equal one increment per activation")
    return errors


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-registry")
    validate.add_argument("--registry", type=Path, required=True)
    validate.add_argument("--project-root", type=Path, default=Path("."))
    validate.add_argument("--output", type=Path, required=True)
    capsule = commands.add_parser("build-capsule")
    capsule.add_argument("--registry", type=Path, required=True)
    capsule.add_argument("--request", type=Path, required=True)
    capsule.add_argument("--project-root", type=Path, default=Path("."))
    capsule.add_argument("--output", type=Path, required=True)
    acceptance = commands.add_parser("build-acceptance")
    acceptance.add_argument("--capsule", type=Path, required=True)
    acceptance.add_argument("--registry", type=Path, required=True)
    acceptance.add_argument("--new-thread-id", required=True)
    acceptance.add_argument("--project-root", type=Path, default=Path("."))
    acceptance.add_argument("--output", type=Path, required=True)
    activate_command = commands.add_parser("activate")
    activate_command.add_argument("--registry", type=Path, required=True)
    activate_command.add_argument("--capsule", type=Path, required=True)
    activate_command.add_argument("--acceptance", type=Path, required=True)
    activate_command.add_argument("--registry-output", type=Path, required=True)
    activate_command.add_argument("--activation-output", type=Path, required=True)
    activate_command.add_argument("--activation-order", type=int, required=True)
    activate_command.add_argument("--project-root", type=Path, default=Path("."))
    publish = commands.add_parser("publish-activation")
    publish.add_argument("--registry", type=Path, required=True)
    publish.add_argument("--successor", type=Path, required=True)
    publish.add_argument("--activation", type=Path, required=True)
    publish.add_argument("--project-root", type=Path, default=Path("."))
    publish.add_argument("--output", type=Path, required=True)
    resolve = commands.add_parser("resolve-mainline")
    resolve.add_argument("--registry", type=Path, required=True)
    resolve.add_argument("--output", type=Path, required=True)
    campaign = commands.add_parser("audit-campaign")
    campaign.add_argument("--before", type=Path, required=True)
    campaign.add_argument("--after", type=Path, required=True)
    campaign.add_argument("--activation", type=Path, action="append", default=[])
    campaign.add_argument("--exclude-thread-id", action="append", default=[])
    campaign.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "validate-registry":
            errors = validate_registry(load_json(args.registry), args.project_root.resolve())
            result = {"schema": REPORT_SCHEMA, "kind": "registry", "pass": not errors, "errors": errors}
            write_json(args.output, result)
            return 0 if not errors else 1
        if args.command == "build-capsule":
            write_json(
                args.output,
                build_capsule(args.registry, args.request, args.project_root.resolve()),
            )
            return 0
        if args.command == "build-acceptance":
            write_json(
                args.output,
                build_acceptance(
                    args.capsule,
                    args.registry,
                    args.new_thread_id,
                    args.project_root.resolve(),
                ),
            )
            return 0
        if args.command == "activate":
            _, activation = activate(
                args.registry,
                args.capsule,
                args.acceptance,
                args.registry_output,
                args.activation_order,
                args.project_root.resolve(),
            )
            write_json(args.activation_output, activation)
            return 0
        if args.command == "publish-activation":
            write_json(
                args.output,
                publish_activation(
                    args.registry,
                    args.successor,
                    args.activation,
                    args.project_root.resolve(),
                ),
            )
            return 0
        if args.command == "resolve-mainline":
            registry = load_json(args.registry)
            errors = validate_registry(registry)
            result = {
                "schema": "session-mainline-resolution-v1",
                "pass": not errors,
                "errors": errors,
                "registry_epoch": registry.get("registry_epoch"),
                "mainline_thread_id": mainline_thread(registry) if not errors else None,
            }
            write_json(args.output, result)
            return 0 if not errors else 1
        before = load_json(args.before)
        after = load_json(args.after)
        activations = [load_json(path) for path in args.activation]
        errors = [*validate_registry(before), *validate_registry(after)]
        errors.extend(audit_campaign(before, after, activations, set(args.exclude_thread_id)))
        result = {
            "schema": REPORT_SCHEMA,
            "kind": "campaign",
            "pass": not errors,
            "errors": errors,
            "excluded_thread_ids": sorted(set(args.exclude_thread_id)),
            "mainline_first": True,
        }
        write_json(args.output, result)
        return 0 if not errors else 1
    except (OSError, ValueError, json.JSONDecodeError) as error:
        result = {
            "schema": REPORT_SCHEMA,
            "kind": args.command,
            "pass": False,
            "errors": [f"{type(error).__name__}: {error}"],
        }
        output = getattr(args, "output", None) or getattr(args, "activation_output", None)
        if output is not None:
            write_json(output, result)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

