#!/usr/bin/env python3
"""Record the completed p29-to-p30 official storage rotation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p30_bankvalid"
PREVIOUS_ID = "r5_n4_0cc_p29_row2own"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
INDEX = STORAGE / "PACKAGE_STORAGE_INDEX.json"
PENDING = STORAGE / "pending" / f"{PACKAGE_ID}.zip"
FINAL_AUDIT = ROOT / "outputs/conv_native_four_lane_0ccae916_p30_bankvalid/r5_n4_0cc_p30_bankvalid.final_zip_audit.json"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p30_bankvalid/release_report.json"
EXPECTED_ZIP_SHA256 = "8229b380c9b33f99c8bd27d3eb21ce2ce17aae1b5eb0278926f27307887cbf34"
EXPECTED_ZIP_BYTES = 5_943_878


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p30 storage release report")
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    final = json.loads(FINAL_AUDIT.read_text(encoding="utf-8"))
    records = {item["package_base"]: item for item in index["packages"]}
    previous = records[PREVIOUS_ID]
    current = records[PACKAGE_ID]
    pending = index["pending_by_family"].get("conv_native_four_lane")
    checks = {
        "official_index_pass": index["pass"] is True,
        "p29_tested": previous["family"] == "conv_native_four_lane" and previous["disposition"] == "tested",
        "p30_unique_native_pending": pending == [PACKAGE_ID] and current["disposition"] == "pending",
        "pickup_zip_only": current["pickup_zip"] == f"pending/{PACKAGE_ID}.zip" and current["pickup_sidecar"] is None,
        "exact_pending_zip": PENDING.stat().st_size == EXPECTED_ZIP_BYTES and sha256(PENDING) == EXPECTED_ZIP_SHA256,
        "final_audit_pass": final["valid"] is True and final["status"] == "PACKAGE_READY_NOT_RUN",
    }
    valid = all(checks.values())
    matrix = dict(final["release_gate_matrix"])
    matrix["storage_rotation"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "pass": checks["official_index_pass"] and checks["p29_tested"] and checks["p30_unique_native_pending"] and checks["pickup_zip_only"],
        "scope": "official no-overwrite rotation; p29 tested, p30 sole native pending, pending ZIP-only",
    }
    report = {
        "schema": "conv-native-four-lane-0ccae916-p30-storage-release-v1",
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_HELD",
        "valid": valid,
        "package_identity": PACKAGE_ID,
        "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE" if valid else "NONE",
        "candidate_release": False,
        "checks": checks,
        "release_gate_matrix": matrix,
        "pickup": {"path": PENDING.relative_to(ROOT).as_posix(), "bytes": PENDING.stat().st_size, "sha256": sha256(PENDING)},
        "storage_index": {"path": INDEX.relative_to(ROOT).as_posix(), "bytes": INDEX.stat().st_size, "sha256": sha256(INDEX), "counts": index["counts"], "pending_by_family": index["pending_by_family"]},
        "rotation": {"previous": {"package": PREVIOUS_ID, "disposition": previous["disposition"]}, "current": {"package": PACKAGE_ID, "disposition": current["disposition"]}},
        "expected_server": final["expected_server"],
        "claim_boundary": final["claim_boundary"],
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
                "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
                "CDA-SERVER-DIAGNOSTIC-MULTICLASS-EDGE-NO-LOSS-001",
                "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
                "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
            ],
            "delta": None,
        },
        "server_action": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": valid, "status": report["status"], "output": str(OUTPUT)}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
