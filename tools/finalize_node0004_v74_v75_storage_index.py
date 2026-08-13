#!/usr/bin/env python3
"""Atomically register the already-placed serialized Conv v74/v75 rotation.

This recovery is intentionally index-only: v74 is already archived under
``tested`` and the byte-identical v75 ZIP/sidecar are already under the flat
``pending``/``pending_receipts`` layout.  The script uses the shared storage
manager to validate the complete tree, preserves every unrelated package
record byte-for-byte at the semantic JSON level, and atomically replaces only
the shared index when its preimage still matches.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
INDEX = STORE / "PACKAGE_STORAGE_INDEX.json"
REPORT = (
    ROOT
    / "outputs/conv_node0004_v74_v75_storage_rotation/storage_audit.json"
)
MANAGER_PATH = ROOT / "tools/manage_server_test_package_storage.py"

FAMILY = "conv_serialized_node0004"
V74 = "r5_n4_hw_v74_sourcebound_epoch_diag"
V75 = "r5_n4_hw_v75_sourcebound_collectfix"
EXPECTED_V74_SHA = "3a780d8e75768ee241c4cfca0ed738a97b691f6329d8ff247e5f5d4c96ef5400"
EXPECTED_V75_SHA = "322214d94af5bdfe75e509612da190a205e7cf4324f9e31dcc6e052bb9b3126c"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manager():
    spec = importlib.util.spec_from_file_location("storage_manager", MANAGER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load shared storage manager")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_records(index: dict, excluded: set[str]) -> list[dict]:
    return sorted(
        (
            record
            for record in index.get("packages", [])
            if record.get("package_base") not in excluded
        ),
        key=lambda record: (record.get("disposition", ""), record.get("family", ""), record.get("package_base", "")),
    )


def validate_unrelated_record_refresh(before: dict, candidate: dict) -> list[str]:
    """Allow only additive, already-present pending receipt records.

    This covers a concurrent family having copied auxiliary validation receipts
    after its own index publication.  Identity, disposition, pickup paths,
    evidence, and every previously indexed file must remain exact.
    """

    before_records = {record["package_base"]: record for record in before["packages"]}
    candidate_records = {
        record["package_base"]: record for record in candidate["packages"]
    }
    excluded = {V74, V75}
    if set(before_records) - excluded != set(candidate_records) - excluded:
        raise RuntimeError("unrelated package identity set changed")
    refreshed: list[str] = []
    for package_base in sorted(set(before_records) - excluded):
        old = before_records[package_base]
        new = candidate_records[package_base]
        old_meta = {key: value for key, value in old.items() if key != "files"}
        new_meta = {key: value for key, value in new.items() if key != "files"}
        if old_meta != new_meta:
            raise RuntimeError(
                f"unrelated package metadata changed: {package_base}"
            )
        old_files = {item["relative_path"]: item for item in old.get("files", [])}
        new_files = {item["relative_path"]: item for item in new.get("files", [])}
        if any(new_files.get(path) != record for path, record in old_files.items()):
            raise RuntimeError(
                f"unrelated indexed file changed or disappeared: {package_base}"
            )
        added = sorted(set(new_files) - set(old_files))
        allowed_prefix = (
            f"pending_receipts/{new['family']}/{package_base}/"
        )
        if any(not path.startswith(allowed_prefix) for path in added):
            raise RuntimeError(
                f"unrelated non-receipt file appeared: {package_base}: {added}"
            )
        if added:
            refreshed.append(package_base)
    return refreshed


def main() -> int:
    manager = load_manager()
    before_bytes = INDEX.read_bytes()
    before_sha = hashlib.sha256(before_bytes).hexdigest()
    before = json.loads(before_bytes)

    v74_zip = STORE / "tested" / FAMILY / V74 / f"{V74}.zip"
    v74_sidecar = STORE / "tested" / FAMILY / V74 / f"{V74}.zip.sha256"
    v75_zip = STORE / "pending" / f"{V75}.zip"
    v75_sidecar = (
        STORE / "pending_receipts" / FAMILY / V75 / f"{V75}.zip.sha256"
    )
    for path in (v74_zip, v74_sidecar, v75_zip, v75_sidecar):
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"required regular file missing: {path}")
    if sha256(v74_zip) != EXPECTED_V74_SHA:
        raise RuntimeError("v74 tested ZIP identity mismatch")
    if sha256(v75_zip) != EXPECTED_V75_SHA:
        raise RuntimeError("v75 pending ZIP identity mismatch")
    manager.validate_sidecar(v74_zip, v74_sidecar)
    manager.validate_sidecar(v75_zip, v75_sidecar)

    annotations = manager.existing_annotations(STORE)
    v74_evidence = ROOT / "outputs/conv_node0004_v74_recovered_return_analysis/report.json"
    v75_evidence = ROOT / "outputs/conv_node0004_v74_recovered_return_v75_successor/release_report.json"
    for path in (v74_evidence, v75_evidence):
        if not path.is_file():
            raise RuntimeError(f"storage evidence missing: {path}")
    annotations[V74] = {
        "family": FAMILY,
        "reason": "formal v74 recovered return consumed without rerun; archived tested",
        "evidence": {"path": str(v74_evidence), "sha256": sha256(v74_evidence)},
    }
    annotations[V75] = {
        "family": FAMILY,
        "reason": "v75 source-bound bounded-collector successor; PACKAGE_READY_NOT_RUN",
        "evidence": {"path": str(v75_evidence), "sha256": sha256(v75_evidence)},
    }

    candidate = manager.collect_tree_index(STORE, annotations)
    excluded = {V74, V75}
    unrelated_receipt_refresh = validate_unrelated_record_refresh(before, candidate)
    if candidate.get("pending_by_family", {}).get(FAMILY) != [V75]:
        raise RuntimeError("serialized Conv pending identity is not uniquely v75")

    by_base = {record["package_base"]: record for record in candidate["packages"]}
    if by_base[V74]["disposition"] != "tested":
        raise RuntimeError("v74 is not registered tested")
    if by_base[V75]["disposition"] != "pending":
        raise RuntimeError("v75 is not registered pending")

    candidate_bytes = (
        json.dumps(candidate, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if sha256(INDEX) != before_sha:
        raise RuntimeError("storage index drifted during validation; refusing overwrite")

    fd, temp_name = tempfile.mkstemp(prefix=".PACKAGE_STORAGE_INDEX.", suffix=".tmp", dir=STORE)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(candidate_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        if sha256(INDEX) != before_sha:
            raise RuntimeError("storage index drifted before atomic replace; refusing overwrite")
        os.replace(temp_name, INDEX)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)

    after_sha = sha256(INDEX)
    audited = manager.audit(STORE)
    if not audited.get("pass"):
        raise RuntimeError("post-publication shared storage audit failed")
    if audited.get("pending_by_family", {}).get(FAMILY) != [V75]:
        raise RuntimeError("post-publication serialized Conv pending audit failed")
    if canonical_records(candidate, set()) != canonical_records(audited, set()):
        raise RuntimeError("post-publication audit differs from published index")
    if sha256(v75_zip) != EXPECTED_V75_SHA:
        raise RuntimeError("v75 ZIP changed during index registration")

    report = {
        "schema": "conv_node0004_v74_v75_storage_rotation_audit_v1",
        "pass": True,
        "operation": "INDEX_ONLY_IDEMPOTENT_ROTATION_COMPLETION",
        "physical_moves_performed": 0,
        "other_family_records_preserved": True,
        "other_family_record_only_receipt_refresh": unrelated_receipt_refresh,
        "storage_manager": {
            "path": str(MANAGER_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(MANAGER_PATH),
        },
        "index": {
            "path": str(INDEX.relative_to(ROOT)).replace("\\", "/"),
            "before_sha256": before_sha,
            "after_sha256": after_sha,
            "pass": audited["pass"],
            "counts": audited["counts"],
        },
        "serialized_conv": {
            "family": FAMILY,
            "v74": {
                "disposition": "tested",
                "zip": str(v74_zip.relative_to(ROOT)).replace("\\", "/"),
                "bytes": v74_zip.stat().st_size,
                "sha256": sha256(v74_zip),
            },
            "v75": {
                "disposition": "pending",
                "zip": str(v75_zip.relative_to(ROOT)).replace("\\", "/"),
                "bytes": v75_zip.stat().st_size,
                "sha256_before_after": [EXPECTED_V75_SHA, sha256(v75_zip)],
                "sidecar": str(v75_sidecar.relative_to(ROOT)).replace("\\", "/"),
                "sidecar_sha256": sha256(v75_sidecar),
            },
            "pending_by_family": audited["pending_by_family"][FAMILY],
        },
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report_bytes = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    REPORT.write_bytes(report_bytes)
    print(json.dumps({**report, "report": {"path": str(REPORT), "sha256": sha256(REPORT)}}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
