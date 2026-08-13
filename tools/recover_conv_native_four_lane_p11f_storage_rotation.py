#!/usr/bin/env python3
"""Finish the p10->p11f storage index after a post-move evidence lookup."""

from __future__ import annotations

import json
from pathlib import Path

import manage_server_test_package_storage as storage


ROOT = Path(__file__).resolve().parents[1]
STORE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
)
FAMILY = "conv_native_four_lane"
P10 = "r5_n4_0cc_p10_trig"
P11 = "r5_n4_0cc_p11f_pubord"
P10_EVIDENCE = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p10_return_analysis/report.json"
)
P11_EVIDENCE = (
    STORE
    / "pending_receipts"
    / FAMILY
    / P11
    / f"{P11}.final_zip_audit.json"
)


def evidence(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise storage.StorageError(f"missing rotation evidence: {path}")
    return {"path": str(path.resolve()), "sha256": storage.sha256(path)}


def main() -> int:
    if (STORE / "pending" / f"{P10}.zip").exists():
        raise storage.StorageError("p10 unexpectedly remains pending")
    p10_dir = STORE / "tested" / FAMILY / P10
    if not p10_dir.is_dir():
        raise storage.StorageError("p10 tested set is absent")
    p10_members = storage.validate_source_set(p10_dir, P10)
    p11_members = storage.pending_members(STORE, FAMILY, P11)
    annotations = storage.existing_annotations(STORE)
    annotations[P10] = {
        "family": FAMILY,
        "reason": (
            "formal p10 return consumed; qualified c0 stall confirmed "
            "before external HUP"
        ),
        "evidence": evidence(P10_EVIDENCE),
    }
    annotations[P11] = {
        "family": FAMILY,
        "reason": (
            "fresh bounded public-order c0 successor; final ZIP audit "
            "PACKAGE_READY_NOT_RUN"
        ),
        "evidence": evidence(P11_EVIDENCE),
    }
    result = storage.write_index(STORE, annotations)
    print(
        json.dumps(
            {
                "schema": "conv-native-four-lane-storage-rotation-recovery-v1",
                "status": "ROTATION_INDEX_RECOVERED",
                "p10_member_count": len(p10_members),
                "p11_member_count": len(p11_members),
                "pending_native": result["pending_by_family"][FAMILY],
                "counts": result["counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
