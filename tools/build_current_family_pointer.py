#!/usr/bin/env python3
"""Build the unique pending-family pointer without treating plan as authority."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "contracts/current_family_pointer_registry_v1.json"
DATE_PREFIX = re.compile(r"^(20[0-9]{6})_")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def receipt(path: Path, source_root: Path) -> dict[str, Any]:
    try:
        name = path.resolve().relative_to(source_root.resolve()).as_posix()
    except ValueError:
        name = str(path.resolve())
    return {
        "path": name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def canonical_sha256(value: Any) -> str:
    data = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _record_key(path: Path) -> tuple[str, str]:
    match = DATE_PREFIX.match(path.name)
    return (match.group(1) if match else "00000000", path.name)


def build_pointer(
    source_root: Path,
    storage_index_path: Path,
    task_records_dir: Path,
    plan_path: Path,
    registry_path: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    storage = json.loads(storage_index_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    plan_text = plan_path.read_text(encoding="utf-8")
    if storage.get("schema") != "server_test_package_storage_index_v1":
        errors.append("storage index schema mismatch")
    if storage.get("pass") is not True:
        errors.append("storage index is not PASS")
    if registry.get("schema") != "current-family-pointer-registry-v1":
        errors.append("pointer registry schema mismatch")

    packages = [
        item
        for item in storage.get("packages", [])
        if isinstance(item, dict) and item.get("disposition") == "pending"
    ]
    by_family: dict[str, list[dict[str, Any]]] = {}
    for package in packages:
        by_family.setdefault(str(package.get("family", "")), []).append(package)
    pending_by_family = storage.get("pending_by_family", {})
    family_registry = registry.get("families", {})
    entries: list[dict[str, Any]] = []
    missing_plan: list[str] = []

    for family in sorted(by_family):
        current = by_family[family]
        if len(current) != 1:
            errors.append(f"{family}: pending package count is {len(current)}, expected 1")
            continue
        package = current[0]
        package_base = package.get("package_base")
        if pending_by_family.get(family) != [package_base]:
            errors.append(f"{family}: pending_by_family disagrees with package list")
        family_config = family_registry.get(family)
        if not isinstance(family_config, dict):
            errors.append(f"{family}: no pointer-registry record globs")
            continue
        family_records: set[Path] = set()
        for pattern in family_config.get("record_globs", []):
            family_records.update(
                path
                for path in task_records_dir.glob(pattern)
                if path.is_file()
            )
        package_records = []
        for path in family_records:
            if package_base in path.read_text(encoding="utf-8", errors="replace"):
                package_records.append(path)
        if not family_records:
            errors.append(f"{family}: no family task records")
            continue
        if not package_records:
            errors.append(f"{family}: no task record binds exact package {package_base}")
            continue
        latest_record = max(package_records, key=_record_key)

        pickup_zip = package.get("pickup_zip")
        zip_path = storage_index_path.parent / str(pickup_zip)
        zip_files = [
            item
            for item in package.get("files", [])
            if isinstance(item, dict)
            and item.get("relative_path") == pickup_zip
        ]
        if len(zip_files) != 1:
            errors.append(f"{family}: exact pickup ZIP receipt count is {len(zip_files)}")
            continue
        declared_zip = zip_files[0]
        if not zip_path.is_file():
            errors.append(f"{family}: pickup ZIP missing: {pickup_zip}")
            continue
        actual_zip = receipt(zip_path, source_root)
        if (
            declared_zip.get("bytes") != actual_zip["bytes"]
            or declared_zip.get("sha256") != actual_zip["sha256"]
        ):
            errors.append(f"{family}: pickup ZIP receipt mismatch")

        mentions = package_base in plan_text
        if not mentions:
            missing_plan.append(package_base)
        entries.append(
            {
                "family": family,
                "package_base": package_base,
                "storage_reason": str(package.get("reason", "")),
                "pickup_zip": pickup_zip,
                "zip_receipt": actual_zip,
                "latest_package_record": receipt(latest_record, source_root),
                "record_selection": {
                    "matching_family_records": len(family_records),
                    "matching_package_records": len(package_records),
                    "algorithm": "EXACT_PACKAGE_BASE_THEN_DATE_FILENAME_MAX",
                },
                "plan_mentions_current_package": mentions,
            }
        )

    source_receipts = {
        "storage_index": receipt(storage_index_path, source_root),
        "registry": receipt(registry_path, ROOT),
        "plan": receipt(plan_path, source_root),
    }
    identity_preimage = {
        "storage_index": source_receipts["storage_index"],
        "registry": source_receipts["registry"],
        "families": entries,
    }
    return {
        "schema": "current-family-pointer-v1",
        "pass": not errors,
        "pointer_id": canonical_sha256(identity_preimage),
        "sources": source_receipts,
        "families": entries,
        "plan_coherence": {
            "pass": not missing_plan,
            "missing_current_package_tokens": missing_plan,
            "drift_is_report_only": True,
        },
        "errors": errors,
        "claim_boundary": (
            "Storage index plus exact package-linked task records are the current "
            "pending-package pointer. Plan drift is reported only; this tool does "
            "not edit plan, packages, release state, or server state."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--storage-index", type=Path)
    parser.add_argument("--task-records", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    storage_index = (
        args.storage_index.resolve()
        if args.storage_index
        else source_root
        / "artifacts/operator_config_validation/r5-server-test-packages"
        / "PACKAGE_STORAGE_INDEX.json"
    )
    task_records = (
        args.task_records.resolve()
        if args.task_records
        else source_root / ".agents/task_records"
    )
    plan = args.plan.resolve() if args.plan else source_root / ".agents/plan.md"
    result = build_pointer(
        source_root,
        storage_index,
        task_records,
        plan,
        args.registry.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "pass": result["pass"],
                "pointer_id": result["pointer_id"],
                "families": len(result["families"]),
                "plan_coherent": result["plan_coherence"]["pass"],
                "errors": len(result["errors"]),
                "output": str(args.output.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
