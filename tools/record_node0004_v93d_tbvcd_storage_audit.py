#!/usr/bin/env python3
"""Record the post-rotation v93d storage state without mutating indexed storage."""

from __future__ import annotations

import json
from pathlib import Path

from manage_server_test_package_storage import audit


ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
OUT = ROOT / "outputs/conv_node0004_v93d_tbvcd_hardened_release3/storage_audit.json"


def main() -> int:
    index = audit(STORE)
    pending = index.get("pending_by_family", {})
    flat_pending = sorted(path.stem for path in (STORE / "pending").glob("*.zip"))
    checks = {
        "global_audit_pass": index.get("pass") is True,
        "serialized_sole_pending_v93d": pending.get("conv_serialized_node0004")
        == ["r5_n4_hw_v93d_tbvcd_hardened"],
        "v92_absent_from_pending": "r5_n4_hw_v92b_tbvcdcone"
        not in sum((list(value) for value in pending.values()), []),
        "v92_preserved_in_tested": (
            STORE
            / "tested/conv_serialized_node0004/r5_n4_hw_v92b_tbvcdcone/"
            "r5_n4_hw_v92b_tbvcdcone.zip"
        ).is_file(),
        "pending_count_matches_flat_pickup": index.get("counts", {}).get("pending")
        == len(flat_pending),
    }
    receipt = {
        "schema": "conv-node0004-v93d-post-rotation-storage-audit-v1",
        "pass": all(checks.values()),
        "checks": checks,
        "counts": index.get("counts"),
        "pending_by_family": pending,
        "flat_pending": flat_pending,
        "storage_index": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            "PACKAGE_STORAGE_INDEX.json"
        ),
        "errors": [key for key, value in checks.items() if not value],
        "claim_boundary": "Local package storage/index state only; no server action.",
    }
    OUT.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
