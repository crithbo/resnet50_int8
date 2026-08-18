#!/usr/bin/env python3
"""Validate that a fresh session can recover the current project from disk.

The check is deliberately path/state based.  Transport digests are provenance,
not a takeover blocker.  Use --state-root when the control worktree reads the
canonical package/task state from another checkout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.session_handoff import load_json, validate_registry


REQUIRED_CONTROL_PATHS = (
    ".agents/agent.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/会话转接与所有权规则.md",
    ".codex/skills/resnet50-server-package-flow/SKILL.md",
    "contracts/server_package_build_gate_registry_v1.json",
    "tools/server_package_pipeline.py",
)
STORAGE_INDEX = (
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "PACKAGE_STORAGE_INDEX.json"
)


def _safe_file(root: Path, relative: str) -> Path | None:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        return None
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        return None
    candidate = root.joinpath(*pure.parts)
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() and not candidate.is_symlink() else None


def validate_takeover(workspace_root: Path, state_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for relative in REQUIRED_CONTROL_PATHS:
        if _safe_file(workspace_root, relative) is None:
            errors.append(f"required control path is absent: {relative}")

    registry_path = state_root / "contracts/current_session_owner_registry_v1.json"
    if not registry_path.is_file():
        registry_path = workspace_root / "contracts/current_session_owner_registry_v1.json"
    plan_path = state_root / ".agents/plan.md"
    if not plan_path.is_file():
        plan_path = workspace_root / ".agents/plan.md"
    if not registry_path.is_file():
        errors.append("current owner registry is absent from state/workspace roots")
    if not plan_path.is_file():
        errors.append("current plan is absent from state/workspace roots")
    build_registry_path = workspace_root / "contracts/server_package_build_gate_registry_v1.json"
    registry: dict[str, Any] = {}
    build_registry: dict[str, Any] = {}
    plan_text = ""
    try:
        registry = load_json(registry_path)
        errors.extend(f"owner_registry:{item}" for item in validate_registry(registry, None))
    except Exception as exc:
        errors.append(f"owner registry unreadable: {exc}")
    try:
        plan_text = plan_path.read_text(encoding="utf-8")
    except Exception as exc:
        errors.append(f"plan unreadable: {exc}")
    try:
        build_registry = load_json(build_registry_path)
    except Exception as exc:
        errors.append(f"build registry unreadable: {exc}")

    roles = registry.get("roles", []) if isinstance(registry, dict) else []
    epoch = registry.get("registry_epoch") if isinstance(registry, dict) else None
    mainline_id = registry.get("mainline_role_id") if isinstance(registry, dict) else None
    mainline = next((role for role in roles if role.get("role_id") == mainline_id), None)
    epoch_token = f"registry_epoch: {epoch}" if epoch is not None else None
    required_plan_tokens: list[str] = []
    if isinstance(mainline, dict):
        required_plan_tokens.extend([mainline_id, mainline.get("thread_id", "")])
    required_plan_tokens.extend(role.get("role_id", "") for role in roles)

    pending_paths: list[str] = []
    pointer_paths: list[str] = []
    for role in roles:
        task = role.get("current_task", {})
        for item in (task.get("pointer"), role.get("latest_task_record")):
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                pointer_paths.append(item["path"])
        flight = role.get("in_flight", {})
        package = flight.get("package") if isinstance(flight, dict) else None
        if isinstance(package, dict) and isinstance(package.get("path"), str):
            pending_paths.append(package["path"])
            required_plan_tokens.append(Path(package["path"]).stem)

    for token in dict.fromkeys(token for token in required_plan_tokens if token):
        if token not in plan_text:
            errors.append(f"plan omits current control token: {token}")
    if epoch_token and epoch_token not in plan_text:
        warnings.append("plan omits registry epoch label; role/package coherence remains authoritative")
    for relative in dict.fromkeys(pointer_paths):
        if _safe_file(state_root, relative) is None and _safe_file(workspace_root, relative) is None:
            errors.append(f"current-state pointer is absent: {relative}")
    for relative in dict.fromkeys(pending_paths):
        if _safe_file(state_root, relative) is None:
            errors.append(f"current pending package is absent: {relative}")

    storage_path = state_root.joinpath(*PurePosixPath(STORAGE_INDEX).parts)
    if storage_path.is_file():
        try:
            storage = load_json(storage_path)
            indexed = {
                package
                for packages in storage.get("pending_by_family", {}).values()
                for package in packages
            }
            registered = {Path(path).stem for path in pending_paths}
            if indexed != registered:
                errors.append(
                    "owner/storage pending mismatch: "
                    f"registry={sorted(registered)} storage={sorted(indexed)}"
                )
        except Exception as exc:
            errors.append(f"storage index unreadable: {exc}")
    else:
        warnings.append("storage index absent; pending exact-set comparison was not run")

    if build_registry.get("mode") != "ACTIVE_PATCH_FIRST_CHANGED_SURFACE":
        errors.append("build registry is not in ACTIVE_PATCH_FIRST_CHANGED_SURFACE mode")
    if build_registry.get("release_admission_required") is not True:
        errors.append("build registry does not require formal release admission")

    return {
        "schema": "project-takeover-readiness-v1",
        "pass": not errors,
        "workspace_root": str(workspace_root.resolve()),
        "state_root": str(state_root.resolve()),
        "registry_epoch": epoch,
        "mainline_role_id": mainline_id,
        "role_ids": [role.get("role_id") for role in roles],
        "pending_package_ids": [Path(path).stem for path in pending_paths],
        "errors": errors,
        "warnings": warnings,
        "claim_boundary": "Current-disk takeover coherence only; no package, storage or server action.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    state_root = args.state_root or args.workspace_root
    report = validate_takeover(args.workspace_root, state_root)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
