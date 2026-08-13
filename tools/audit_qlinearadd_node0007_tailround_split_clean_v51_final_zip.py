"""Final current-rule audit for fresh-identity isolated tail_round v51."""

from __future__ import annotations

import json
from pathlib import Path

import audit_qlinearadd_node0007_tailround_split_v50_final_zip as audit


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_tailround_split_clean_v51"
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-split-clean-v51-package"


def main() -> int:
    audit.NAME = NAME
    audit.LOCAL = LOCAL
    audit.ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{NAME}.zip"
    audit.RECEIPTS = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/qlinearadd_node0007" / NAME
    audit.SIDECAR = audit.RECEIPTS / f"{NAME}.zip.sha256"
    audit.FAMILY = LOCAL / "family_validation.json"
    audit.SHARED = LOCAL / "shared_runtime_layout_validation.json"
    audit.BUILD = LOCAL / "build_receipt.json"
    audit.REPORT = LOCAL / "final_zip_self_audit.json"
    rc = audit.main()
    report = json.loads(audit.REPORT.read_text(encoding="utf-8"))
    report["schema"] = "qlinearadd-node0007-tailround-split-clean-v51-final-zip-rule-self-audit-v1"
    report["claim_boundary"] = "PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / E2_LOCAL_ONLY; fresh identity avoids the unexecuted v50 server extraction namespace; workload/config/numeric/golden/observer/timeout/RTL remain frozen"
    report["identity_only_reissue"] = True
    audit.write_json(audit.REPORT, report)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
