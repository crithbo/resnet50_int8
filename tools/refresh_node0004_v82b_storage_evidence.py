#!/usr/bin/env python3
"""Refresh only v82b release-evidence hash after correcting its byte receipt."""

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
INDEX = STORE / storage.INDEX_NAME
PACKAGE_ID = "r5_n4_hw_v82b_phase_collectfix"
EXPECTED_PREIMAGE = "07b1a6ef4b60da2095a743f596b5d3f03f0f5957557a27d7ab90a8f3db4bf8f8"
EVIDENCE = STORE / "pending_receipts/conv_serialized_node0004" / PACKAGE_ID / f"{PACKAGE_ID}.release_evidence.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_rows(index: dict, exclude: str) -> dict[str, tuple]:
    result = {}
    for row in index.get("packages", []):
        base = row.get("package_base")
        if not base or base == exclude:
            continue
        result[base] = (
            row.get("family"),
            row.get("disposition"),
            row.get("reason"),
            row.get("evidence"),
            tuple((f.get("relative_path"), f.get("bytes"), f.get("sha256")) for f in row.get("files", [])),
        )
    return result


def main() -> int:
    actual_preimage = sha(INDEX)
    if actual_preimage != EXPECTED_PREIMAGE:
        raise SystemExit(f"storage index preimage drift: expected={EXPECTED_PREIMAGE} actual={actual_preimage}")
    before = json.loads(INDEX.read_text(encoding="utf-8"))
    unrelated_before = stable_rows(before, PACKAGE_ID)
    annotations = storage.existing_annotations(STORE)
    if PACKAGE_ID not in annotations:
        raise SystemExit("v82b annotation missing")
    annotations[PACKAGE_ID]["evidence"] = {
        "path": str(EVIDENCE.resolve()),
        "sha256": sha(EVIDENCE),
    }
    after = storage.write_index(STORE, annotations)
    audited = storage.audit(STORE)
    errors = []
    if stable_rows(after, PACKAGE_ID) != unrelated_before:
        errors.append("unrelated indexed rows changed")
    if stable_rows(audited, PACKAGE_ID) != unrelated_before:
        errors.append("unrelated audited rows changed")
    if after.get("pending_by_family") != before.get("pending_by_family"):
        errors.append("pending_by_family changed")
    package_rows = [row for row in after.get("packages", []) if row.get("package_base") == PACKAGE_ID]
    if len(package_rows) != 1 or package_rows[0].get("evidence", {}).get("sha256") != sha(EVIDENCE):
        errors.append("v82b evidence annotation not refreshed")
    report = {
        "schema": "conv-node0004-v82b-storage-evidence-refresh-v1",
        "pass": not errors,
        "errors": errors,
        "index_preimage_sha256": actual_preimage,
        "index_sha256": sha(INDEX),
        "evidence_sha256": sha(EVIDENCE),
        "pending_by_family_unchanged": after.get("pending_by_family") == before.get("pending_by_family"),
        "unrelated_rows_unchanged": stable_rows(after, PACKAGE_ID) == unrelated_before,
        "claim_boundary": "Receipt metadata correction only; package ZIP bytes and all package dispositions are unchanged."
    }
    target = ROOT / "outputs/conv_node0004_v81_return_v82_successor/storage_evidence_refresh_v82b.json"
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
