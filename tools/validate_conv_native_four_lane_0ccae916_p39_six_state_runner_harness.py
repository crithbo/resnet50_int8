#!/usr/bin/env python3
"""Run p39 through the inherited full six-state install/runtime harness."""

from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p30_runner_harness as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p39_compilecore"
prior.SOURCE_ID = "r5_n4_0cc_p38_mse4join"
prior.SOURCE_SHA256 = "328b7ec7b7034a1a2c202fad38d628199cfbbaa2213196d94daab39c25ff4d22"
prior.SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p38_mse4join.zip"


if __name__ == "__main__":
    raise SystemExit(prior.main())
