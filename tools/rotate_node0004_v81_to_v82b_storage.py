#!/usr/bin/env python3
"""Rotate consumed serialized Conv v81 to tested and publish v82b pending."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import manage_server_test_package_storage as storage


STORE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
OUT = ROOT / "outputs/conv_node0004_v81_return_v82_successor"
SOURCE = OUT / "build_v82b"
FAMILY = "conv_serialized_node0004"
PREVIOUS = "r5_n4_hw_v81_ack_phase_targetfix"
CURRENT = "r5_n4_hw_v82b_phase_collectfix"
EXPECTED_INDEX_PREIMAGE = "b4b6d0aae7004bf041827921747d7fe59f9bfc49914cafaeec09e87a41374fb3"
PREVIOUS_EVIDENCE = OUT / "return_analysis.json"
CURRENT_EVIDENCE = SOURCE / f"{CURRENT}.release_evidence.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_identity_map(index: dict, exclude: set[str]) -> dict[str, tuple[str, str, tuple[tuple[str, str, int], ...]]]:
    result = {}
    for row in index.get("packages", []):
        base = row.get("package_base")
        if not base or base in exclude:
            continue
        result[base] = (
            row.get("family"),
            row.get("disposition"),
            tuple(sorted((item.get("relative_path"), item.get("sha256"), item.get("bytes")) for item in row.get("files", []))),
        )
    return result


def main() -> int:
    index = STORE / storage.INDEX_NAME
    actual_preimage = sha(index)
    if actual_preimage != EXPECTED_INDEX_PREIMAGE:
        raise SystemExit(f"storage index preimage drift: expected={EXPECTED_INDEX_PREIMAGE} actual={actual_preimage}")
    before = storage.audit(STORE)
    if before.get("pending_by_family", {}).get(FAMILY) != [PREVIOUS]:
        raise SystemExit(f"unexpected serialized pending preimage: {before.get('pending_by_family', {}).get(FAMILY)}")
    expected_other_pending = {
        "conv_native_four_lane": ["r5_n4_0cc_p36b_semfp"],
        "qlinearadd_node0007": ["r5_qadd_n7_tailround_bufready_v54"],
    }
    for family, packages in expected_other_pending.items():
        if before.get("pending_by_family", {}).get(family) != packages:
            raise SystemExit(f"concurrent pending preimage mismatch for {family}: {before.get('pending_by_family', {}).get(family)}")
    unrelated_before = package_identity_map(before, {PREVIOUS, CURRENT})
    result = storage.rotate(
        root=STORE,
        source_dir=SOURCE,
        family=FAMILY,
        new_base=CURRENT,
        previous_disposition="tested",
        previous_reason="formal v81 return consumed; exact phase EVENT records were erased by package-local post-sim projection ordering",
        previous_evidence=PREVIOUS_EVIDENCE,
        new_reason="v82b exact-instance known-width semantic-fingerprint phase collector-order diagnostic; all local and independent first-fresh gates PASS",
        new_evidence=CURRENT_EVIDENCE,
    )
    after = storage.audit(STORE)
    unrelated_after = package_identity_map(after, {PREVIOUS, CURRENT})
    pending = STORE / "pending" / f"{CURRENT}.zip"
    tested = STORE / "tested" / FAMILY / PREVIOUS / f"{PREVIOUS}.zip"
    errors = []
    if after.get("pending_by_family", {}).get(FAMILY) != [CURRENT]:
        errors.append("serialized pending identity mismatch")
    if unrelated_after != unrelated_before:
        errors.append("unrelated family package records changed")
    for family, packages in expected_other_pending.items():
        if after.get("pending_by_family", {}).get(family) != packages:
            errors.append(f"concurrent pending identity changed for {family}")
    if not pending.is_file() or sha(pending) != "cdd4dc08b616d29e891973267fff0dd00c380bada05c12e50e2a6d119bd7ee07":
        errors.append("v82b pending ZIP missing or changed")
    if not tested.is_file() or sha(tested) != "fc3e7049822af17d956bfed7b95c9c13abdf9d151ef2881e2b68107d7b0c0389":
        errors.append("v81 tested ZIP missing or changed")
    report = {
        "schema": "conv-node0004-v81-v82b-storage-rotation-v1",
        "pass": not errors,
        "errors": errors,
        "family": FAMILY,
        "storage_index_preimage_sha256": actual_preimage,
        "previous": {"package_id": PREVIOUS, "disposition": "tested", "zip": tested.relative_to(ROOT).as_posix(), "sha256": sha(tested) if tested.is_file() else None},
        "current": {"package_id": CURRENT, "disposition": "pending", "zip": pending.relative_to(ROOT).as_posix(), "bytes": pending.stat().st_size if pending.is_file() else None, "sha256": sha(pending) if pending.is_file() else None},
        "other_family_records_preserved": unrelated_after == unrelated_before,
        "explicit_concurrent_pending_preserved": all(after.get("pending_by_family", {}).get(f) == p for f, p in expected_other_pending.items()),
        "pending_by_family": after.get("pending_by_family"),
        "storage_index": {"path": index.relative_to(ROOT).as_posix(), "bytes": index.stat().st_size, "sha256": sha(index)},
        "rotation_result_semantic_sha256": hashlib.sha256((json.dumps(result, sort_keys=True) + "\n").encode()).hexdigest(),
        "claim_boundary": "Storage disposition and byte identity only; no server execution claim.",
    }
    target = OUT / "storage_rotation_v82b.json"
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": not errors, "errors": errors, "index_sha256": sha(index), "pending_zip": str(pending)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
