#!/usr/bin/env python3
"""Adapt the independent p35c audit to the p36 semantic-fingerprint epoch."""

from __future__ import annotations

import json
from pathlib import Path

import prepare_conv_native_four_lane_0ccae916_p35c_first_fresh_extra_audit as prior


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p36_semfp"
PACKAGE_BASE = "outputs/conv_native_four_lane_0ccae916_p36_semfp"
BASE = ROOT / "outputs/p36_first_fresh_audit_v2"
FINAL_REPORT = ROOT / f"outputs/conv_native_four_lane_0ccae916_p36_semfp/build/{PACKAGE}.source_bound_final_zip.json"
EPOCH = "20260811-exact-instance-payload-semantic-fingerprint-v2"
RULE_IDS = [
    "CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001",
    "CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001",
    "CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001",
]
_write = prior.write


def write(path: Path, value):
    if path == prior.CONTRACT:
        final = json.loads(FINAL_REPORT.read_text(encoding="utf-8"))
        value["rule_change"] = {
            "epoch_id": EPOCH,
            "rule_ids": RULE_IDS,
            "first_fresh_for_family": True,
            "notification_acknowledged": True,
        }
        value["diagnostic_semantics"] = {
            "fingerprint_sha256": final["diagnostic_semantics_sha256"],
            "final_zip_report_path": FINAL_REPORT.relative_to(ROOT).as_posix(),
            "final_zip_report_sha256": prior.sha(FINAL_REPORT),
            "prior_fingerprint_sha256": None,
            "disposition": "FIRST_USE_AUDITED",
            "prior_audit_receipt": None,
        }
    _write(path, value)


def main() -> int:
    prior.PACKAGE = PACKAGE
    prior.ZIP = ROOT / f"{PACKAGE_BASE}/build/{PACKAGE}.zip"
    prior.BASE = BASE
    prior.CLEAN = BASE / "clean_extract"
    prior.REPORTS = BASE / "reports"
    prior.CONTRACT = BASE / "contract.json"
    prior.EPOCH = EPOCH
    prior.write = write
    return prior.main()


if __name__ == "__main__":
    raise SystemExit(main())
