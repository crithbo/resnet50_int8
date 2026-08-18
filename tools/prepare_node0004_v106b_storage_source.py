#!/usr/bin/env python3
"""Prepare an identity-preserving, package-prefixed v106 storage source set."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v106b_lcdup_return2pflight"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v106b_lcdup_return2pflight_release1"
SOURCE = OUT / "storage_source"
INDEPENDENT = ROOT / "outputs/independent_dual_package_final_audit_v2"
EXPECTED_ZIP_BYTES = 5_991_155
EXPECTED_ZIP_SHA256 = (
    "200382857c0310fd4599363564f7e08f0f268c88468e09620deaf85ed81eb116"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def require_pass(path: Path) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("pass") is not True or value.get("errors") not in (None, []):
        raise RuntimeError(f"non-PASS source receipt: {path}")


def main() -> int:
    if SOURCE.exists():
        raise RuntimeError(f"fresh storage source required: {SOURCE}")

    zip_path = OUT / f"{PACKAGE}.zip"
    sidecar_path = OUT / f"{PACKAGE}.zip.sha256"
    if zip_path.stat().st_size != EXPECTED_ZIP_BYTES:
        raise RuntimeError("v106 ZIP byte identity mismatch")
    if sha256(zip_path) != EXPECTED_ZIP_SHA256:
        raise RuntimeError("v106 ZIP SHA-256 identity mismatch")
    sidecar_tokens = sidecar_path.read_text(encoding="utf-8").strip().split()
    if not sidecar_tokens or sidecar_tokens[0].lower() != EXPECTED_ZIP_SHA256:
        raise RuntimeError("v106 source sidecar does not bind the exact ZIP")

    gate_paths = sorted((OUT / "gates").glob("*.json"))
    if not gate_paths:
        raise RuntimeError("v106 gate receipt set is empty")
    for gate in gate_paths:
        require_pass(gate)

    independent_path = INDEPENDENT / "machine_report.json"
    independent = json.loads(independent_path.read_text(encoding="utf-8"))
    serialized = [
        row
        for row in independent.get("packages", [])
        if row.get("package_id") == PACKAGE
    ]
    if len(serialized) != 1 or serialized[0].get("verdict") != "PASS":
        raise RuntimeError("independent serialized v106 verdict is not exact PASS")
    if serialized[0].get("sha256") != EXPECTED_ZIP_SHA256:
        raise RuntimeError("independent v106 ZIP identity mismatch")

    SOURCE.mkdir(parents=True)
    sources: dict[str, Path] = {
        f"{PACKAGE}.zip": zip_path,
        f"{PACKAGE}.zip.sha256": sidecar_path,
        f"{PACKAGE}.build_receipt.json": OUT / "build_receipt.json",
        f"{PACKAGE}.mainline_package_receipt.json": OUT
        / "mainline_package_receipt.json",
        f"{PACKAGE}.task_record.md": OUT / "task_record.md",
        f"{PACKAGE}.final_zip_local_audit.json": OUT / "final_zip_local_audit.json",
        f"{PACKAGE}.independent_package_audit_handoff.json": OUT
        / "INDEPENDENT_PACKAGE_AUDIT_HANDOFF.json",
        f"{PACKAGE}.patch_and_receipt_reuse_disposition.json": OUT
        / "PATCH_AND_RECEIPT_REUSE_DISPOSITION.json",
        f"{PACKAGE}.release_consistency_contract.json": OUT
        / "release_consistency_contract.json",
        f"{PACKAGE}.independent_dual_package_final_audit_v2.json": independent_path,
        f"{PACKAGE}.release_admission_contract.json": OUT
        / "release_admission/contract.json",
        f"{PACKAGE}.release_receipt.json": OUT
        / "release_admission/release_receipt.json",
        f"{PACKAGE}.precompile_failure_core.json": OUT
        / "release_admission/precompile_failure_core.json",
        f"{PACKAGE}.first_fresh_extra_audit_contract.json": OUT
        / "first_fresh_extra_audit/contract.json",
    }
    for gate in gate_paths:
        sources[f"{PACKAGE}.{gate.name}"] = gate
    for report in sorted((OUT / "first_fresh_extra_audit/reports").glob("*.json")):
        sources[f"{PACKAGE}.first_fresh_{report.name}"] = report

    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise RuntimeError(f"v106 storage source inputs absent: {missing}")

    records: list[dict[str, Any]] = []
    for name, source in sorted(sources.items()):
        if not (
            name == f"{PACKAGE}.zip"
            or name == f"{PACKAGE}.zip.sha256"
            or name.startswith(PACKAGE + ".")
            or name.startswith(PACKAGE + "_")
        ):
            raise RuntimeError(f"non-prefixed storage member: {name}")
        target = SOURCE / name
        shutil.copyfile(source, target)
        source_sha = sha256(source)
        if target.stat().st_size != source.stat().st_size or sha256(target) != source_sha:
            raise RuntimeError(f"storage source byte mismatch: {name}")
        records.append(
            {
                "bytes": target.stat().st_size,
                "name": name,
                "sha256": source_sha,
                "source": source.relative_to(ROOT).as_posix(),
            }
        )

    manifest = {
        "family": FAMILY,
        "independent_serialized_verdict": "PASS",
        "managed_storage_touched": False,
        "members": records,
        "package_id": PACKAGE,
        "package_prefixed_member_count": len(records),
        "pass": True,
        "schema": "serialized-conv-v106b-storage-source-v1",
        "server_actions": [],
        "source_zip_preserved": True,
    }
    manifest_path = OUT / "storage_source_manifest.json"
    manifest_path.write_bytes(canonical(manifest))
    print(
        json.dumps(
            {
                "members": len(records),
                "package_id": PACKAGE,
                "pass": True,
                "zip_bytes": zip_path.stat().st_size,
                "zip_sha256": sha256(zip_path),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
