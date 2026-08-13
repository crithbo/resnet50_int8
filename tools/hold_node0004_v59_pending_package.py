#!/usr/bin/env python3
"""Move the exact held node0004 v59 package set from pending to superseded."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import manage_server_test_package_storage as storage  # noqa: E402


PACKAGE_BASE = "r5_n4_hw_v59_install_subtree"
FAMILY = "conv_serialized_node0004"
EXPECTED_SHA256 = (
    "e5023a50e827ae3d4b0fc6bb9ac327c9aa38d9e72db068cc4fd567f8e76a216d"
)
REASON = "PACKAGE_HELD_SHARED_LAYOUT_PARENT_PRECONDITION_TOO_STRICT"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    evidence = args.evidence.resolve()
    if not evidence.is_file():
        raise storage.StorageError(f"missing hold evidence: {evidence}")

    annotations = storage.existing_annotations(root)
    before = storage.collect_tree_index(root, annotations)
    current = before.get("pending_by_family", {}).get(FAMILY, [])
    if current != [PACKAGE_BASE]:
        raise storage.StorageError(
            f"unexpected serialized pending set before HOLD: {current}"
        )

    members = storage.pending_members(root, FAMILY, PACKAGE_BASE)
    package = root / "pending" / f"{PACKAGE_BASE}.zip"
    if storage.sha256(package) != EXPECTED_SHA256:
        raise storage.StorageError("v59 ZIP identity mismatch")

    destination = storage.resolved_under(
        root / "superseded" / FAMILY / PACKAGE_BASE,
        root,
    )
    if destination.exists():
        raise storage.StorageError(f"superseded destination exists: {destination}")

    moves: list[tuple[Path, Path]] = []
    for source in members:
        target = storage.resolved_under(destination / source.name, root)
        if target.exists():
            raise storage.StorageError(f"refusing overwrite: {target}")
        moves.append((source, target))

    for source, target in moves:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))

    receipt_dir = storage.pending_receipt_dir(root, FAMILY, PACKAGE_BASE)
    if receipt_dir.exists() and not any(receipt_dir.iterdir()):
        receipt_dir.rmdir()
    family_receipts = receipt_dir.parent
    if family_receipts.exists() and not any(family_receipts.iterdir()):
        family_receipts.rmdir()

    annotations[PACKAGE_BASE] = {
        "family": FAMILY,
        "reason": REASON,
        "evidence": {
            "path": str(evidence),
            "sha256": storage.sha256(evidence),
        },
    }
    after = storage.write_index(root, annotations)
    if after.get("pending_by_family", {}).get(FAMILY):
        raise storage.StorageError("serialized pending set is not empty after HOLD")

    archived_package = destination / f"{PACKAGE_BASE}.zip"
    result = {
        "schema": "conv-node0004-v59-storage-hold-receipt-v1",
        "pass": True,
        "status": REASON,
        "package": {
            "path": str(archived_package),
            "bytes": archived_package.stat().st_size,
            "sha256": storage.sha256(archived_package),
        },
        "moved_member_count": len(moves),
        "pending_before": current,
        "pending_after": after.get("pending_by_family", {}).get(FAMILY, []),
        "storage_counts_after": after.get("counts"),
        "storage_index": {
            "path": str(root / storage.INDEX_NAME),
            "sha256": storage.sha256(root / storage.INDEX_NAME),
        },
        "successor_built": False,
        "server_action": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
