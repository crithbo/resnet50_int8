#!/usr/bin/env python3
"""Record the post-manager storage audit for serialized Conv v88b."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = "r5_n4_hw_v88b_portvcd"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v88b_portable_ack_identity_release1"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def receipt(path: Path) -> dict[str, object]:
    return {
        "path": path.resolve().relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def main() -> int:
    index_path = STORAGE / "PACKAGE_STORAGE_INDEX.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    pending = STORAGE / "pending" / f"{BASE}.zip"
    build = OUT / "build" / f"{BASE}.zip"
    receipt_dir = STORAGE / "pending_receipts" / FAMILY / BASE
    release = receipt_dir / f"{BASE}.release_receipt.json"
    expected_other_families = {
        "conv_native_four_lane",
        "gap_node0071",
        "qlinearadd_node0007",
    }
    pending_families = set(index.get("pending_by_family", {}))
    checks = {
        "manager_audit_index_pass": index.get("pass") is True,
        "serialized_pending_exact": index.get("pending_by_family", {}).get(FAMILY)
        == [BASE],
        "pending_zip_present": pending.is_file(),
        "pending_zip_exact_build_identity": pending.is_file()
        and build.is_file()
        and sha(pending) == sha(build),
        "receipt_dir_present": receipt_dir.is_dir(),
        "release_evidence_present": release.is_file(),
        "other_pending_families_preserved": expected_other_families.issubset(
            pending_families
        ),
        "one_pending_per_family": all(
            len(items) == 1 for items in index.get("pending_by_family", {}).values()
        ),
    }
    value = {
        "schema": "conv-node0004-v88b-storage-audit-receipt-v1",
        "pass": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "status": "PACKAGE_READY_NOT_RUN",
        "family": FAMILY,
        "package_id": BASE,
        "storage_index": receipt(index_path),
        "pending_zip": receipt(pending) if pending.is_file() else None,
        "receipt_dir": receipt_dir.resolve().relative_to(ROOT).as_posix(),
        "receipt_members": sorted(path.name for path in receipt_dir.iterdir())
        if receipt_dir.is_dir()
        else [],
        "server_action": False,
    }
    target = OUT / f"{BASE}.storage_audit_receipt.json"
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0 if value["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
