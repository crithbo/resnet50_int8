#!/usr/bin/env python3
"""Fresh-identity wrapper for the self-contained p34b ARM-token parser."""

from pathlib import Path

import build_conv_native_four_lane_0ccae916_p34_armtoken_package as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p34b_armtoken"
prior.SOURCE_BOUND = ROOT / "outputs/conv_native_four_lane_0ccae916_p34b_armtoken_source_bound"
prior.GENERATED = prior.SOURCE_BOUND / "generated"
prior.DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p34b_armtoken/build"


if __name__ == "__main__":
    raise SystemExit(prior.main())
