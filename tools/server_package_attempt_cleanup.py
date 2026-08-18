#!/usr/bin/env python3
"""Remove only one identity-bound package attempt after its return is durable."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any


SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class CleanupError(ValueError):
    pass


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def tree_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file() and not item.is_symlink()) if path.exists() else 0


def atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def strict_real_directory(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise CleanupError(f"{label} is not a real directory: {path}")
    return path.resolve()


def cleanup(args: argparse.Namespace) -> dict[str, Any]:
    for label, value in (("package_id", args.package_id), ("execution_id", args.execution_id), ("attempt_id", args.attempt_id)):
        if SAFE.fullmatch(value) is None:
            raise CleanupError(f"unsafe {label}")
    server_root = strict_real_directory(args.server_root, "server root")
    package_parent = server_root / "install/codex_runs" / args.package_id
    run_root = args.run_root.resolve(strict=True)
    bootstrap_root = args.bootstrap_root.resolve(strict=True)
    expected_run = (package_parent / args.attempt_id).resolve()
    expected_bootstrap = (package_parent / f"bootstrap-{args.execution_id}").resolve()
    if run_root != expected_run or bootstrap_root != expected_bootstrap:
        raise CleanupError("cleanup path identity differs")
    for label, path in (("run root", run_root), ("bootstrap root", bootstrap_root)):
        if path.is_symlink() or not path.is_dir():
            raise CleanupError(f"{label} is unsafe")
    marker = package_parent / f".codex_owner.{args.attempt_id}.json"
    if marker.is_symlink() or not marker.is_file():
        raise CleanupError("attempt ownership marker is absent or unsafe")
    marker_value = json.loads(marker.read_text(encoding="utf-8"))
    if marker_value.get("package_id") != args.package_id or marker_value.get("attempt") != args.attempt_id:
        raise CleanupError("attempt ownership marker identity differs")
    bootstrap_marker = bootstrap_root / ".codex_bootstrap_owner.json"
    if bootstrap_marker.is_symlink() or not bootstrap_marker.is_file():
        raise CleanupError("bootstrap ownership marker is absent or unsafe")
    boot = json.loads(bootstrap_marker.read_text(encoding="utf-8"))
    if boot != {"attempt_id": args.attempt_id, "execution_id": args.execution_id, "package_id": args.package_id}:
        raise CleanupError("bootstrap ownership marker identity differs")
    return_zip = args.return_zip.resolve(strict=True)
    if return_zip.is_symlink() or not return_zip.is_file():
        raise CleanupError("formal return is absent or unsafe")
    before = {"run_root_bytes": tree_bytes(run_root), "bootstrap_root_bytes": tree_bytes(bootstrap_root)}
    return_identity = {"path": str(return_zip), "bytes": return_zip.stat().st_size, "sha256": sha(return_zip)}
    finalization_guard_identity = None
    if getattr(args, "finalization_guard_receipt", None) is not None:
        finalization_guard = args.finalization_guard_receipt.resolve(strict=True)
        try:
            finalization_guard.relative_to(run_root)
        except ValueError as error:
            raise CleanupError("finalization guard receipt escapes exact run root") from error
        if finalization_guard.is_symlink() or not finalization_guard.is_file():
            raise CleanupError("finalization guard receipt is absent or unsafe")
        finalization_guard_identity = {
            "path": str(finalization_guard), "bytes": finalization_guard.stat().st_size,
            "sha256": sha(finalization_guard),
        }
    shutil.rmtree(run_root)
    shutil.rmtree(bootstrap_root)
    marker.unlink()
    package_parent_removed = False
    if package_parent.is_dir() and not any(package_parent.iterdir()):
        package_parent.rmdir()
        package_parent_removed = True
    return {
        "schema": "server-package-attempt-cleanup-receipt-v1",
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "return_zip": return_identity,
        "finalization_guard_receipt": finalization_guard_identity,
        "removed": before,
        "run_root_absent": not run_root.exists(),
        "bootstrap_root_absent": not bootstrap_root.exists(),
        "package_parent_removed_if_empty": package_parent_removed,
        "persistent_install_codex_runs_bytes_for_exact_attempt": 0,
        "foreign_siblings_preserved": True,
        "pass": True,
        "claim_boundary": "Exact identity-bound package attempt cleanup after durable return only.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-root", type=Path, required=True)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--bootstrap-root", type=Path, required=True)
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--finalization-guard-receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = cleanup(args)
    except (CleanupError, OSError, json.JSONDecodeError) as error:
        report = {"schema": "server-package-attempt-cleanup-receipt-v1", "pass": False, "error": str(error)}
        atomic(args.output, report)
        print(json.dumps(report, sort_keys=True), file=sys.stderr)
        return 3
    atomic(args.output, report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
