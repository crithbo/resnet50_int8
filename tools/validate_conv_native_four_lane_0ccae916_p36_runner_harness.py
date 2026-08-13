#!/usr/bin/env python3
"""Run the p36 exact runner through the inherited six-state harness."""

from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p30_runner_harness as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p36_semfp"
prior.SOURCE_ID = "r5_n4_0cc_p35c_armknown"
prior.SOURCE_SHA256 = "b755592dbd01f05a63f0471ed76ede7673ab987b57a2cf579a8566a3d26f59fc"
prior.SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p35c_armknown.zip"


if __name__ == "__main__":
    raise SystemExit(prior.main())
