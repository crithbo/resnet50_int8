#!/usr/bin/env python3
"""Run p37b through the exact inherited six-state harness."""

from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p30_runner_harness as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p37b_saepoch"
prior.SOURCE_ID = "r5_n4_0cc_p37_saepoch"
prior.SOURCE_SHA256 = "441da07145ee883585ff57dd8bc3320c1486dc2ea47f852759e2ff3443995e9a"
prior.SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p37_saepoch.zip"


if __name__ == "__main__":
    raise SystemExit(prior.main())
