#!/usr/bin/env python3
"""Run p34 exact runner through the inherited six-state harness."""

from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p30_runner_harness as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p34_armtoken"
prior.SOURCE_ID = "r5_n4_0cc_p33b_wrowner"
prior.SOURCE_SHA256 = "62b225be794774e1cd8c9a4f8a8d26e2cf5ecb1795ed44fe3d1ed748d81077df"
prior.SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p33b_wrowner.zip"


if __name__ == "__main__":
    raise SystemExit(prior.main())
