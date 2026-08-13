#!/usr/bin/env python3
"""Run the independent first-use audit for p36b."""

from pathlib import Path

import prepare_conv_native_four_lane_0ccae916_p36_first_fresh_extra_audit as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE = "r5_n4_0cc_p36b_semfp"
prior.PACKAGE_BASE = "outputs/conv_native_four_lane_0ccae916_p36b_semfp"
prior.BASE = ROOT / "outputs/p36b_first_fresh_audit_v2_retry"
prior.FINAL_REPORT = ROOT / "outputs/conv_native_four_lane_0ccae916_p36b_semfp/build/r5_n4_0cc_p36b_semfp.source_bound_final_zip.json"


if __name__ == "__main__":
    raise SystemExit(prior.main())
