#!/usr/bin/env python3
"""Run the p33b exact runner through the inherited isolated six-state harness."""

from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p30_runner_harness as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p33b_wrowner"
prior.SOURCE_ID = "r5_n4_0cc_p32b_validowner"
prior.SOURCE_SHA256 = "fc21dc0fccb4fbf612e55418964f78ba482678ec232a4bb438b50f97e03a2d47"
prior.SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p32b_validowner.zip"


if __name__ == "__main__":
    raise SystemExit(prior.main())
