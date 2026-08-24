#!/usr/bin/env python3
"""Plan and build a clean Git-based ResNet50 project migration handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "project-migration-manifest-v1"
EXCLUDED = [
    ".venv/",
    ".tmp/",
    "work/",
    "outputs/",
    "server_returns/",
    "__pycache__/",
    ".pytest_cache/",
]
LOCK_CANDIDATES = [
    "requirements-resnet50.lock.txt",
    "requirements-resnet50.txt",
    "repos.lock.json",
    "pyproject.toml",
    "package-lock.json",
    "pnpm-lock.yaml",
    "uv.lock",
    "Cargo.lock",
]


class MigrationError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def run_git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    command = ["git", "-c", f"safe.directory={root}", "-C", str(root), *args]
    result = subprocess.run(command, check=False, capture_output=True)
    if check and result.returncode != 0:
        raise MigrationError(result.stderr.decode("utf-8", errors="replace").strip())
    return result


def git_text(root: Path, *args: str) -> str:
    return run_git(root, *args).stdout.decode("utf-8", errors="strict").strip()


def file_receipt(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MigrationError(f"JSON root must be an object: {path}")
    return value


def control_plane(root: Path) -> dict[str, Any]:
    registry = load_json(root / "contracts/current_session_owner_registry_v1.json")
    storage = load_json(root / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json")
    return {
        "registry_epoch": registry["registry_epoch"],
        "mainline_role_id": registry["mainline_role_id"],
        "role_ids": [item["role_id"] for item in registry.get("roles", [])],
        "pending_packages": sorted(
            item["package_base"] for item in storage.get("packages", []) if item.get("disposition") == "pending"
        ),
    }


def plan(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    status = [item for item in run_git(root, "status", "--porcelain=v1", "--untracked-files=all").stdout.splitlines() if item]
    branch = git_text(root, "branch", "--show-current") or "DETACHED"
    commit = git_text(root, "rev-parse", "HEAD")
    tracked = [item for item in run_git(root, "ls-files", "-z").stdout.split(b"\0") if item]
    locks = []
    for relative in LOCK_CANDIDATES:
        path = root / relative
        if path.is_file():
            locks.append({"path": relative, "bytes": path.stat().st_size})
    errors = [] if not status else [f"working tree is not clean: {len(status)} status entries"]
    warnings: list[str] = []
    return {
        "schema": SCHEMA,
        "generated_at_utc": now(),
        "repo_root": str(root),
        "git": {
            "commit": commit,
            "branch": branch,
            "clean": not status,
            "status_count": len(status),
            "tracked_file_count": len(tracked),
        },
        "control_plane": control_plane(root),
        "lock_files": locks,
        "excluded_regenerable_roots": EXCLUDED,
        "ready_for_build": not errors,
        "errors": errors,
        "warnings": warnings,
        "claim_boundary": "Git/control-plane migration readiness only; no dependency install, data copy, package or server action."
    }


def build(root: Path, output_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if manifest.get("schema") != SCHEMA or manifest.get("ready_for_build") is not True:
        raise MigrationError("migration build requires a clean ready manifest")
    if manifest["git"]["commit"] != git_text(root, "rev-parse", "HEAD"):
        raise MigrationError("repository HEAD drifted after migration plan")
    fresh = plan(root)
    if fresh["ready_for_build"] is not True:
        raise MigrationError("repository became dirty after migration plan")
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = output_dir / "resnet50_int8.bundle"
    archive = output_dir / "resnet50_int8_source.zip"
    if bundle.exists() or archive.exists():
        raise MigrationError("migration output already exists; refusing overwrite")
    run_git(root, "bundle", "create", str(bundle), "--all")
    run_git(root, "archive", "--format=zip", "-o", str(archive), "HEAD")
    verify = run_git(root, "bundle", "verify", str(bundle), check=False)
    forbidden: list[str] = []
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        if not names or zipped.testzip() is not None:
            forbidden.append("ARCHIVE_EMPTY_OR_CRC_FAILURE")
        for name in names:
            normalized = name.replace("\\", "/")
            if any(normalized.startswith(prefix) or f"/{prefix}" in normalized for prefix in EXCLUDED):
                forbidden.append(name)
    errors: list[str] = []
    if verify.returncode != 0:
        errors.append(verify.stderr.decode("utf-8", errors="replace").strip())
    if forbidden:
        errors.append("source archive includes forbidden regenerable members")
    return {
        "schema": "project-migration-build-receipt-v1",
        "generated_at_utc": now(),
        "repo_commit": manifest["git"]["commit"],
        "bundle": file_receipt(bundle),
        "source_archive": file_receipt(archive),
        "bundle_verify_pass": verify.returncode == 0,
        "archive_forbidden_members": forbidden,
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "Git history bundle and tracked-source archive only; ignored generated data and dependencies are excluded."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "build"])
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.action == "plan":
        result = plan(args.repo_root)
        write_json(args.output_dir / "MIGRATION_MANIFEST.json", result)
    else:
        if args.manifest is None:
            parser.error("build requires --manifest")
        result = build(args.repo_root, args.output_dir, load_json(args.manifest))
        write_json(args.output_dir / "MIGRATION_BUILD_RECEIPT.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ready_for_build", result.get("pass", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
