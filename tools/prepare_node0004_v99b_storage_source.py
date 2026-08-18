#!/usr/bin/env python3
"""Prepare the exact flat v99b source set for the package storage manager."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v99b_lcdup_guarded"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v99b_lcdup_guarded_release6"
ANALYSIS = ROOT / "outputs/conv_node0004_v98b_runtime_failure_analysis"
SOURCE = OUT / "storage_source"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    if SOURCE.exists():
        raise RuntimeError(f"fresh storage source required: {SOURCE}")
    SOURCE.mkdir(parents=True)

    sources: dict[str, Path] = {
        f"{PACKAGE}.zip": OUT / f"{PACKAGE}.zip",
        f"{PACKAGE}.build_receipt.json": OUT / "build_receipt.json",
        f"{PACKAGE}.mainline_package_receipt.json": OUT / "mainline_package_receipt.json",
        f"{PACKAGE}.task_record.md": OUT / "task_record.md",
        f"{PACKAGE}.v98_runtime_failure_rootcause_report.json": ANALYSIS / "runtime_failure_rootcause_report.json",
        f"{PACKAGE}.v98_package_build_failure_rule_audit.json": ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json",
    }
    for gate_name in (
        "active_rule_registry.json",
        "deterministic_zip.json",
        "first_fresh.json",
        "frozen_mapper_surface.json",
        "hdl.json",
        "lexical_tree.json",
        "lexical_zip.json",
        "observer_only.json",
        "operational_guard.json",
        "post_sim.json",
        "release_admission.json",
        "runner_tree.json",
        "runner_zip.json",
        "runtime_preflight.json",
        "source_bound_final_zip.json",
    ):
        sources[f"{PACKAGE}.{gate_name}"] = OUT / "gates" / gate_name

    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise RuntimeError(f"v99 storage source inputs absent: {missing}")

    records: list[dict[str, Any]] = []
    for name, source in sorted(sources.items()):
        target = SOURCE / name
        shutil.copyfile(source, target)
        source_sha = sha256(source)
        if sha256(target) != source_sha:
            raise RuntimeError(f"storage source byte mismatch: {name}")
        records.append({
            "bytes": target.stat().st_size,
            "name": name,
            "sha256": source_sha,
            "source": source.relative_to(ROOT).as_posix(),
        })

    zip_path = SOURCE / f"{PACKAGE}.zip"
    sidecar = SOURCE / f"{PACKAGE}.zip.sha256"
    sidecar.write_text(f"{sha256(zip_path)}  {zip_path.name}\n", encoding="utf-8", newline="\n")
    records.append({
        "bytes": sidecar.stat().st_size,
        "name": sidecar.name,
        "sha256": sha256(sidecar),
        "source": "GENERATED_FROM_EXACT_STORAGE_SOURCE_ZIP",
    })

    manifest = {
        "family": FAMILY,
        "managed_storage_touched": False,
        "members": sorted(records, key=lambda row: row["name"]),
        "package_id": PACKAGE,
        "pass": True,
        "schema": "serialized-conv-v99b-storage-source-v1",
        "server_actions": [],
    }
    manifest_path = OUT / "storage_source_manifest.json"
    manifest_path.write_bytes(canonical(manifest))
    print(json.dumps({"members": len(records), "package_id": PACKAGE, "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
