#!/usr/bin/env python3
"""Fresh p35c build profile after p35b pre-final staging failure."""

from pathlib import Path

import prepare_conv_native_four_lane_0ccae916_p35_build_profile as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p35c_armknown"
prior.BASE = "outputs/conv_native_four_lane_0ccae916_p35c_armknown"
prior.BOUND = "outputs/conv_native_four_lane_0ccae916_p35c_armknown_source_bound"
prior.OUTPUT = ROOT / prior.BASE / "server_package_build_spec_v2.json"
prior.BUILDER = "tools/build_conv_native_four_lane_0ccae916_p35c_armknown_package.py"
prior.GENERATION_REPORT = f"{prior.BOUND}/source_bound_generation_report.json"
prior.CHEAP_REPORT = f"{prior.BOUND}/source_bound_observer_generation.json"


if __name__ == "__main__":
    raise SystemExit(prior.main())
