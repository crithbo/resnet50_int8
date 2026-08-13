#!/usr/bin/env python3
"""Rotate consumed serialized Conv v80 to tested and publish v81 pending."""

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
OUT = ROOT / "outputs/conv_node0004_v80_return_v81_successor"
SOURCE = OUT / "build_fix4"
FAMILY = "conv_serialized_node0004"
PREVIOUS = "r5_n4_hw_v80_ack_phase_diag"
CURRENT = "r5_n4_hw_v81_ack_phase_targetfix"
PREVIOUS_EVIDENCE = ROOT / "outputs/conv_node0004_v79_return_v80_successor/release_report.json"
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
    before = storage.audit(STORE)
    if before.get("pending_by_family", {}).get(FAMILY) != [PREVIOUS]:
        raise SystemExit(f"unexpected serialized pending preimage: {before.get('pending_by_family', {}).get(FAMILY)}")
    unrelated_before = package_identity_map(before, {PREVIOUS, CURRENT})
    result = storage.rotate(
        root=STORE,
        source_dir=SOURCE,
        family=FAMILY,
        new_base=CURRENT,
        previous_disposition="tested",
        previous_reason="formal v80 return consumed; phase report invalidated by wrong-instance parser scope",
        previous_evidence=PREVIOUS_EVIDENCE,
        new_reason="v81 exact-target live phase diagnostic; final ZIP and first-fresh independent audits PASS",
        new_evidence=CURRENT_EVIDENCE,
    )
    after = storage.audit(STORE)
    unrelated_after = package_identity_map(after, {PREVIOUS, CURRENT})
    pending = STORE / "pending" / f"{CURRENT}.zip"
    tested = STORE / "tested" / FAMILY / PREVIOUS / f"{PREVIOUS}.zip"
    index = STORE / storage.INDEX_NAME
    errors = []
    if after.get("pending_by_family", {}).get(FAMILY) != [CURRENT]:
        errors.append("serialized pending identity mismatch")
    if unrelated_after != unrelated_before:
        errors.append("unrelated family package records changed")
    if not pending.is_file() or sha(pending) != "fc3e7049822af17d956bfed7b95c9c13abdf9d151ef2881e2b68107d7b0c0389":
        errors.append("v81 pending ZIP missing or changed")
    if not tested.is_file() or sha(tested) != "cd3dd4f78f1ed75c0fc94b3113f6afb447c507e61fe9d289a20d90854e117a8a":
        errors.append("v80 tested ZIP missing or changed")
    report = {
        "schema": "conv-node0004-v80-v81-storage-rotation-v1",
        "pass": not errors,
        "errors": errors,
        "family": FAMILY,
        "previous": {"package_id": PREVIOUS, "disposition": "tested", "zip": tested.relative_to(ROOT).as_posix(), "sha256": sha(tested) if tested.is_file() else None},
        "current": {"package_id": CURRENT, "disposition": "pending", "zip": pending.relative_to(ROOT).as_posix(), "bytes": pending.stat().st_size if pending.is_file() else None, "sha256": sha(pending) if pending.is_file() else None},
        "other_family_records_preserved": unrelated_after == unrelated_before,
        "pending_by_family": after.get("pending_by_family"),
        "storage_index": {"path": index.relative_to(ROOT).as_posix(), "bytes": index.stat().st_size, "sha256": sha(index)},
        "rotation_result_semantic_sha256": hashlib.sha256((json.dumps(result, sort_keys=True) + "\n").encode()).hexdigest(),
        "claim_boundary": "Storage disposition and byte identity only; no server execution claim.",
    }
    target = OUT / "storage_rotation_report.json"
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": not errors, "errors": errors, "index_sha256": sha(index), "pending_zip": str(pending)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
