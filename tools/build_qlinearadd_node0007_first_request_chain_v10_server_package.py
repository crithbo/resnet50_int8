from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import (
    build_qlinearadd_node0007_first_request_chain_v9_server_package as base,
)


def configure() -> None:
    base.INSTALL_NAME = "r5_qadd_n7_first_request_chain_v10"
    base.VERSION_TAG = "v10"
    base.VALIDATION_PATH = (
        base.PACKAGE_ROOT / f"{base.INSTALL_NAME}.validation.json"
    )
    base.VALIDATOR_REL = (
        "tools/validate_qlinearadd_node0007_first_request_chain_v10.py"
    )
    base.REPORT_REL = (
        "artifacts/operator_config_validation/"
        "r5-qlinearadd-node0007-first-request-chain-v10/report.json"
    )
    base.LOCAL_SUPERSEDED = {
        "zip": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            "r5_qadd_n7_first_request_chain_v9.zip"
        ),
        "sha256": (
            "c9be314f01244ca6a6f68f4f9777862d1c58875490ab99a039e230c199e7ad95"
        ),
        "status": "QUARANTINED_NOT_RUN_EVENT_QUALIFICATION_SELF_AUDIT",
        "reason": (
            "v9 counted the actual slice_start_run level without an explicit "
            "rising-edge witness; v10 qualifies it as a unique start event"
        ),
        "functional_workload_unchanged": True,
    }


def main() -> int:
    configure()
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
