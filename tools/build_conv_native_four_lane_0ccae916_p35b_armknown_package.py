#!/usr/bin/env python3
"""Fresh package identity after p35 prebuild-only spec failure."""

from pathlib import Path

import build_conv_native_four_lane_0ccae916_p35_armknown_package as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p35b_armknown"
prior.SOURCE_BOUND = ROOT / "outputs/conv_native_four_lane_0ccae916_p35b_armknown_source_bound"
prior.GENERATED = prior.SOURCE_BOUND / "generated"
prior.DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p35b_armknown/build"


if __name__ == "__main__":
    raise SystemExit(prior.main())
