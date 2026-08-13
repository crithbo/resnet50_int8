#!/usr/bin/env python3
"""Build fresh p36b after p36 final-ZIP semantic-control failure."""

from pathlib import Path

import build_conv_native_four_lane_0ccae916_p36_semfp_package as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p36b_semfp"
prior.SOURCE_BOUND = ROOT / "outputs/conv_native_four_lane_0ccae916_p36b_semfp_source_bound"
prior.GENERATED = prior.SOURCE_BOUND / "generated"
prior.DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p36b_semfp/build"


if __name__ == "__main__":
    raise SystemExit(prior.main())
