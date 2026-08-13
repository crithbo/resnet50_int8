#!/usr/bin/env python3
"""Record the post-rotation storage identity for serialized Conv v87b."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = "r5_n4_hw_v87b_mandatory_vpd"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v87b_mandatory_vpd_release6"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def receipt(path: Path) -> dict[str, object]:
    return {
        "path": path.resolve().relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> int:
    index_path = STORAGE / "PACKAGE_STORAGE_INDEX.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    pending = STORAGE / "pending" / f"{BASE}.zip"
    build = OUT / "build" / f"{BASE}.zip"
    receipts = STORAGE / "pending_receipts" / FAMILY / BASE
    old_pending = STORAGE / "pending/r5_n4_hw_v86b_observer_xmre_fix.zip"
    old_superseded = (
        STORAGE
        / "superseded/conv_serialized_node0004/r5_n4_hw_v86b_observer_xmre_fix"
        / "r5_n4_hw_v86b_observer_xmre_fix.zip"
    )
    checks = {
        "manager_audit_index_pass": index.get("pass") is True,
        "pending_family_exact": index.get("pending_by_family", {}).get(FAMILY)
        == [BASE],
        "pending_zip_present": pending.is_file(),
        "pending_zip_exact_build_identity": pending.is_file()
        and build.is_file()
        and sha256(pending) == sha256(build),
        "pending_receipt_dir_present": receipts.is_dir(),
        "held_v86b_absent_from_pending": not old_pending.exists(),
        "held_v86b_preserved_superseded": old_superseded.is_file(),
    }
    value = {
        "schema": "conv-node0004-v87b-storage-audit-receipt-v1",
        "pass": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "family": FAMILY,
        "package_id": BASE,
        "status": "PACKAGE_READY_NOT_RUN",
        "storage_index": receipt(index_path),
        "pending_zip": receipt(pending) if pending.is_file() else None,
        "receipt_dir": receipts.resolve().relative_to(ROOT).as_posix(),
        "receipt_members": sorted(path.name for path in receipts.iterdir())
        if receipts.is_dir()
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
