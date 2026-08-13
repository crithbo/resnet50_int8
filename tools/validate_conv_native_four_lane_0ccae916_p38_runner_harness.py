#!/usr/bin/env python3
"""Run p38 through the exact inherited six-state runner harness."""

from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p30_runner_harness as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p38_mse4join"
prior.SOURCE_ID = "r5_n4_0cc_p37b_saepoch"
prior.SOURCE_SHA256 = "d2f0bd8dd532975cebb12dab89fac8a4dbe0aa87e2a0ac6e38323ad7fedc2c80"
prior.SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p37b_saepoch.zip"


if __name__ == "__main__":
    raise SystemExit(prior.main())
