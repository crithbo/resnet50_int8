#!/usr/bin/env python3
"""Archive the formally consumed GAP v54 pending set as tested, without a successor."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import manage_server_test_package_storage as storage


PACKAGE = "r5_n71_gap_v54_remote_owner_false_accept_diag"
FAMILY = "gap_node0071"
SOURCE_SHA = "131e9de37698c8e0470db0c42120c0b2d793c84ce0c2ee62a02eb24cefbd87c9"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    evidence = args.evidence.resolve()
    receipt = args.receipt.resolve()
    if not evidence.is_file():
        raise storage.StorageError(f"missing evidence: {evidence}")
    annotations = storage.existing_annotations(root)
    before = storage.collect_tree_index(root, annotations)
    pending_before = before["pending_by_family"]
    if pending_before.get(FAMILY) != [PACKAGE]:
        raise storage.StorageError(
            f"GAP pending identity changed: {pending_before.get(FAMILY)}"
        )
    members = storage.pending_members(root, FAMILY, PACKAGE)
    zip_path = next((path for path in members if path.name == f"{PACKAGE}.zip"), None)
    if zip_path is None or sha(zip_path) != SOURCE_SHA:
        raise storage.StorageError("v54 source ZIP identity mismatch")
    destination = root / "tested" / FAMILY / PACKAGE
    if destination.exists():
        raise storage.StorageError(f"tested destination exists: {destination}")
    moves = [(source, destination / source.name) for source in members]
    destination.mkdir(parents=True, exist_ok=False)
    for source, target in moves:
        shutil.move(str(source), str(target))
    old_receipt = storage.pending_receipt_dir(root, FAMILY, PACKAGE)
    if old_receipt.exists() and not any(old_receipt.iterdir()):
        old_receipt.rmdir()
        if old_receipt.parent.exists() and not any(old_receipt.parent.iterdir()):
            old_receipt.parent.rmdir()
    annotations[PACKAGE] = {
        "family": FAMILY,
        "reason": "v54 formal return consumed; WAIT_RTL_FIX remote wdata priority-owner false accept proven",
        "evidence": {"path": str(evidence), "sha256": sha(evidence)},
    }
    after = storage.write_index(root, annotations)
    pending_after = after["pending_by_family"]
    unrelated_unchanged = {
        key: value for key, value in pending_before.items() if key != FAMILY
    } == {
        key: value for key, value in pending_after.items() if key != FAMILY
    }
    valid = (
        FAMILY not in pending_after
        and unrelated_unchanged
        and (destination / f"{PACKAGE}.zip").is_file()
        and sha(destination / f"{PACKAGE}.zip") == SOURCE_SHA
    )
    result = {
        "schema": "gap-node0071-v54-tested-storage-transition-v1",
        "valid": valid,
        "package": PACKAGE,
        "source_sha256": SOURCE_SHA,
        "evidence_path": str(evidence),
        "evidence_sha256": sha(evidence),
        "pending_gap_before": pending_before.get(FAMILY, []),
        "pending_gap_after": pending_after.get(FAMILY, []),
        "unrelated_pending_unchanged": unrelated_unchanged,
        "tested_destination": str(destination),
        "storage_index_sha256": sha(root / storage.INDEX_NAME),
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({**result, "receipt": str(receipt), "receipt_sha256": sha(receipt)}))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
