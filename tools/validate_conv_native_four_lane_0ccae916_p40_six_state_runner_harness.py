#!/usr/bin/env python3
"""Run p40 through the inherited six-state install/runtime harness."""

from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p30_runner_harness as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p40_dhpubfix"
prior.SOURCE_ID = "r5_n4_0cc_p39_compilecore"
prior.SOURCE_SHA256 = "d99d078a53ec88f5dc0374f0b080350d2e62a6e2121237f7da4dbce9a6c6b515"
prior.SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p39_compilecore.zip"


if __name__ == "__main__":
    raise SystemExit(prior.main())
