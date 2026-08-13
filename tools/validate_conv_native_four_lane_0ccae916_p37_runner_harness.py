#!/usr/bin/env python3
"""Run p37 exact runner through the inherited six-state harness."""

from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p30_runner_harness as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p37_saepoch"
prior.SOURCE_ID = "r5_n4_0cc_p36b_semfp"
prior.SOURCE_SHA256 = "0111176e62fca03a023bbd83098067191113bdc4a91a7bf5c7e0e37c3d288e0e"
prior.SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p36b_semfp.zip"


if __name__ == "__main__":
    raise SystemExit(prior.main())
