#!/usr/bin/env python3
"""Fresh-identity wrapper for the p33b hexadecimal-mask parser fix."""

from pathlib import Path

import build_conv_native_four_lane_0ccae916_p33_wrowner_package as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p33b_wrowner"
prior.SOURCE_BOUND = ROOT / "outputs/conv_native_four_lane_0ccae916_p33b_wrowner_source_bound"
prior.GENERATED = prior.SOURCE_BOUND / "generated"
prior.DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p33b_wrowner/build"


if __name__ == "__main__":
    raise SystemExit(prior.main())
