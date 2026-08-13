#!/usr/bin/env python3
"""Write the p36b one-shot prebuild aggregate specification."""

from pathlib import Path

import prepare_conv_native_four_lane_0ccae916_p36_semfp_build_profile as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE = "r5_n4_0cc_p36b_semfp"
prior.BASE = "outputs/conv_native_four_lane_0ccae916_p36b_semfp"
prior.BOUND = "outputs/conv_native_four_lane_0ccae916_p36b_semfp_source_bound"
prior.OUTPUT = ROOT / prior.BASE / "server_package_build_spec_v2.json"


if __name__ == "__main__":
    raise SystemExit(prior.main())
