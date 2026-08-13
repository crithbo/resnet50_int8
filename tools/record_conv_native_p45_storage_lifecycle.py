#!/usr/bin/env python3
"""Record the post-rotation p45 storage lifecycle and global audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
PACKAGE = "r5_n4_0cc_p45_obswide"
OLD = "r5_n4_0cc_p44_fsdbvq"
FAMILY = "conv_native_four_lane"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    command = [str(args.python), str(ROOT / "tools/manage_server_test_package_storage.py"), "audit", "--root", str(STORAGE)]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-4096:])
    audit = json.loads(completed.stdout)
    records = {row["package_base"]: row for row in audit["packages"]}
    p45 = records[PACKAGE]
    p44 = records[OLD]
    if audit.get("pass") is not True or audit.get("pending_by_family", {}).get(FAMILY) != [PACKAGE]:
        raise RuntimeError("native pending or global audit differs")
    if p45.get("disposition") != "pending" or p44.get("disposition") != "superseded":
        raise RuntimeError("p44/p45 storage disposition differs")
    p45_zip = STORAGE / "pending" / f"{PACKAGE}.zip"
    p44_zip = STORAGE / "superseded" / FAMILY / OLD / f"{OLD}.zip"
    index = STORAGE / "PACKAGE_STORAGE_INDEX.json"
    receipt = {
        "schema": "conv-native-p45-storage-lifecycle-v1",
        "status": "STORAGE_LIFECYCLE_COMPLETE",
        "package_status": "PACKAGE_READY_NOT_RUN",
        "package_id": PACKAGE,
        "family": FAMILY,
        "owner": {"role_id": "family.conv.native", "owner_epoch": 2, "registry_epoch": 6},
        "pending": identity(p45_zip),
        "superseded_p44": identity(p44_zip),
        "global_audit": {"pass": True, "counts": audit["counts"], "pending_by_family": audit["pending_by_family"]},
        "storage_index": identity(index),
        "previous_version_progress": "p41 passed production compile beyond the Datahub repair; p42 fixed the two-bit vector predicate; p43 stopped at time zero; p44 FSDB-v3 was built but never run and is now preserved superseded.",
        "current_version_purpose": "Preserve the p42 vector predicate and MSE4 wdata/slice-finish target while returning broad unbounded source-bound actual-signal observer evidence in one run.",
        "claim_boundary": "Local storage publication and audit only; no upload, lease, connection, server compile, simulation or dynamic DUT claim.",
        "server_actions_performed": [],
        "pass": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
