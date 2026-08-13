#!/usr/bin/env python3
"""Fresh source-bound identity after p35b pre-final staging failure."""

from pathlib import Path

import prepare_conv_native_four_lane_0ccae916_p35_armknown_source_bound as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p35c_armknown"
prior.OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p35c_armknown_source_bound"
prior.CATALOG = prior.OUTPUT / "source_bound_probe_catalog.json"
prior.PLAN = prior.OUTPUT / "source_bound_probe_plan.json"
prior.CONTRACT = prior.OUTPUT / "arm_known_contract.json"


if __name__ == "__main__":
    raise SystemExit(prior.main())
