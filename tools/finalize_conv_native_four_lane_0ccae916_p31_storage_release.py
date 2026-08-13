#!/usr/bin/env python3
"""Record the official p30-tested/p31-pending native-Conv rotation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p31_postclear"
PREVIOUS = "r5_n4_0cc_p30_bankvalid"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
INDEX = STORAGE / "PACKAGE_STORAGE_INDEX.json"
PENDING = STORAGE / "pending" / f"{PACKAGE}.zip"
FINAL = ROOT / f"outputs/conv_native_four_lane_0ccae916_p31_postclear/{PACKAGE}.final_zip_audit.json"
EXTRA = ROOT / "outputs/conv_native_four_lane_0ccae916_p31_postclear/first_fresh_extra_audit/validation.json"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p31_postclear/release_report.json"
ZIP_SHA = "d022977daebb1c633d0c4fa32ca58cf5b660a6f4c4dff6cb11d499a21d2345c9"
ZIP_BYTES = 5_927_263


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p31 storage release report")
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    final = json.loads(FINAL.read_text(encoding="utf-8"))
    extra = json.loads(EXTRA.read_text(encoding="utf-8"))
    records = {item["package_base"]: item for item in index["packages"]}
    checks = {
        "storage_audit_pass": index.get("pass") is True,
        "p30_tested": records[PREVIOUS]["family"] == "conv_native_four_lane" and records[PREVIOUS]["disposition"] == "tested",
        "p31_unique_native_pending": index["pending_by_family"].get("conv_native_four_lane") == [PACKAGE] and records[PACKAGE]["disposition"] == "pending",
        "pickup_zip_only": records[PACKAGE]["pickup_zip"] == f"pending/{PACKAGE}.zip" and records[PACKAGE]["pickup_sidecar"] is None,
        "exact_pending_zip": PENDING.stat().st_size == ZIP_BYTES and sha(PENDING) == ZIP_SHA,
        "final_audit_pass": final.get("valid") is True and final.get("status") == "PACKAGE_READY_NOT_RUN",
        "first_fresh_extra_audit_pass": extra.get("pass") is True and extra.get("upload_authorized") is True,
    }
    valid = all(checks.values())
    matrix = dict(final["release_gate_matrix"])
    matrix["storage_rotation"] = {"applicability": "blocking_applicable", "pass": checks["storage_audit_pass"] and checks["p30_tested"] and checks["p31_unique_native_pending"] and checks["pickup_zip_only"]}
    report = {
        "schema": "conv-native-four-lane-p31-postclear-storage-release-v1",
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_HELD",
        "valid": valid,
        "package_identity": PACKAGE,
        "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE" if valid else "NONE",
        "candidate_release": False,
        "checks": checks,
        "release_gate_matrix": matrix,
        "pickup": {"path": PENDING.relative_to(ROOT).as_posix(), "bytes": PENDING.stat().st_size, "sha256": sha(PENDING)},
        "storage_index": {"path": INDEX.relative_to(ROOT).as_posix(), "bytes": INDEX.stat().st_size, "sha256": sha(INDEX), "counts": index["counts"], "pending_by_family": index["pending_by_family"]},
        "rotation": {"previous": {"package": PREVIOUS, "disposition": records[PREVIOUS]["disposition"]}, "current": {"package": PACKAGE, "disposition": records[PACKAGE]["disposition"]}},
        "expected_server": final["expected_server"],
        "claim_boundary": final["claim_boundary"],
        "rule_feedback": {"type": "RULE_CONFIRMATION", "confirmed": ["CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001", "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001", "CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001", "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001", "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001"], "delta": None},
        "server_action": False,
    }
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": valid, "status": report["status"], "output": str(OUTPUT)}))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
