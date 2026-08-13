#!/usr/bin/env python3
"""Record the completed p28-to-p29 official storage rotation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p29_row2own"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
INDEX = STORAGE / "PACKAGE_STORAGE_INDEX.json"
PENDING = STORAGE / "pending" / f"{PACKAGE_ID}.zip"
FINAL_AUDIT = ROOT / "outputs/conv_native_four_lane_0ccae916_p29_row2own/r5_n4_0cc_p29_row2own.final_zip_audit.json"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p29_row2own/release_report.json"
EXPECTED_ZIP_SHA256 = "43cfd63753ee964a92efec955f1dcba05c772c659406bd0142da8e37d2bd0f49"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p29 storage release report")
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    final = json.loads(FINAL_AUDIT.read_text(encoding="utf-8"))
    records = {item["package_base"]: item for item in index["packages"]}
    p28 = records["r5_n4_0cc_p28_b5release"]
    p29 = records[PACKAGE_ID]
    pending = index["pending_by_family"].get("conv_native_four_lane")
    checks = {
        "official_index_pass": index["pass"] is True,
        "p28_tested": p28["family"] == "conv_native_four_lane" and p28["disposition"] == "tested",
        "p29_unique_native_pending": pending == [PACKAGE_ID] and p29["disposition"] == "pending",
        "pickup_zip_only": p29["pickup_zip"] == f"pending/{PACKAGE_ID}.zip" and p29["pickup_sidecar"] is None,
        "exact_pending_zip": PENDING.stat().st_size == 5_920_486 and sha256(PENDING) == EXPECTED_ZIP_SHA256,
        "final_audit_pass": final["valid"] is True and final["status"] == "PACKAGE_READY_NOT_RUN",
    }
    valid = all(checks.values())
    matrix = dict(final["release_gate_matrix"])
    matrix["storage_rotation"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "pass": checks["official_index_pass"] and checks["p28_tested"] and checks["p29_unique_native_pending"] and checks["pickup_zip_only"],
        "scope": "official no-overwrite rotation; p28 tested, p29 sole native pending, pending ZIP-only",
    }
    report = {
        "schema": "conv-native-four-lane-0ccae916-p29-storage-release-v1",
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_HELD",
        "valid": valid,
        "package_identity": PACKAGE_ID,
        "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE" if valid else "NONE",
        "candidate_release": False,
        "checks": checks,
        "release_gate_matrix": matrix,
        "pickup": {"path": PENDING.relative_to(ROOT).as_posix(), "bytes": PENDING.stat().st_size, "sha256": sha256(PENDING)},
        "storage_index": {"path": INDEX.relative_to(ROOT).as_posix(), "bytes": INDEX.stat().st_size, "sha256": sha256(INDEX), "counts": index["counts"], "pending_by_family": index["pending_by_family"]},
        "rotation": {"previous": {"package": "r5_n4_0cc_p28_b5release", "disposition": p28["disposition"]}, "current": {"package": PACKAGE_ID, "disposition": p29["disposition"]}},
        "expected_server": final["expected_server"],
        "claim_boundary": final["claim_boundary"],
        "server_action": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": valid, "status": report["status"], "output": str(OUTPUT)}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
