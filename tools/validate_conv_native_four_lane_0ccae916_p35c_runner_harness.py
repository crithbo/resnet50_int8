#!/usr/bin/env python3
"""Run p35c exact runner through the inherited isolated six-state harness."""

from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p30_runner_harness as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p35c_armknown"
prior.SOURCE_ID = "r5_n4_0cc_p34b_armtoken"
prior.SOURCE_SHA256 = "98d9f8b23824d2b5ec9e90f87fdfa1a3ee6bc61df5c9edca81ff19cf5f5b5fd1"
prior.SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p34b_armtoken.zip"


if __name__ == "__main__":
    raise SystemExit(prior.main())
