#!/usr/bin/env python3
"""Run p42 through the inherited six-state install/runtime harness."""

from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p41_six_state_runner_harness as p41


ROOT = Path(__file__).resolve().parents[1]
p41.prior.PACKAGE_ID = "r5_n4_0cc_p42_vecjoinfix"
p41.prior.SOURCE_ID = "r5_n4_0cc_p41_vpdfull"
p41.prior.SOURCE_SHA256 = "339d8f4e17cbf34132be9bc84f33dec637ea3fd6ecc8deeec5aa5620a012a95a"
p41.prior.SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / "r5_n4_0cc_p41_vpdfull.zip"
)


if __name__ == "__main__":
    raise SystemExit(p41.prior.main())
