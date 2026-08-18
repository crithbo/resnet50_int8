#!/usr/bin/env python3
"""Prepare the exact package-prefixed v100 source set for managed storage."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v100b_lcdup_guardv2"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v100b_lcdup_guardv2_release1"
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
        f"{PACKAGE}.release_admission_contract.json": OUT / "release_admission/contract.json",
        f"{PACKAGE}.release_receipt.json": OUT / "release_admission/release_receipt.json",
        f"{PACKAGE}.precompile_failure_core.json": OUT / "release_admission/precompile_failure_core.json",
        f"{PACKAGE}.canonical_guard_v2_activation.json": ROOT / "outputs/observer_operational_guard_live_tree_v2/CANONICAL_ACTIVATION_RECEIPT.json",
    }
    for gate in sorted((OUT / "gates").glob("*.json")):
        sources[f"{PACKAGE}.{gate.name}"] = gate
    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise RuntimeError(f"v100 storage source inputs absent: {missing}")
    records: list[dict[str, Any]] = []
    for name, source in sorted(sources.items()):
        if not name.startswith(PACKAGE + "."):
            raise RuntimeError(f"non-prefixed storage member: {name}")
        target = SOURCE / name
        shutil.copyfile(source, target)
        expected = sha256(source)
        if sha256(target) != expected:
            raise RuntimeError(f"storage source byte mismatch: {name}")
        records.append({"name": name, "source": source.relative_to(ROOT).as_posix(), "bytes": target.stat().st_size, "sha256": expected})
    zip_path = SOURCE / f"{PACKAGE}.zip"
    sidecar = SOURCE / f"{PACKAGE}.zip.sha256"
    sidecar.write_text(f"{sha256(zip_path)}  {zip_path.name}\n", encoding="utf-8", newline="\n")
    records.append({"name": sidecar.name, "source": "GENERATED_FROM_EXACT_STORAGE_SOURCE_ZIP", "bytes": sidecar.stat().st_size, "sha256": sha256(sidecar)})
    manifest = {
        "schema": "serialized-conv-v100b-storage-source-v1",
        "family": FAMILY,
        "package_id": PACKAGE,
        "pass": True,
        "managed_storage_touched": False,
        "server_actions": [],
        "package_prefixed_member_count": len(records),
        "members": sorted(records, key=lambda row: row["name"]),
    }
    manifest_path = OUT / "storage_source_manifest.json"
    manifest_path.write_bytes(canonical(manifest))
    print(json.dumps({"package_id": PACKAGE, "members": len(records), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
