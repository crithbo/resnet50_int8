#!/usr/bin/env python3
"""Fresh-identity source-bound preparation after p34 parser dependency escape."""

from pathlib import Path

import prepare_conv_native_four_lane_0ccae916_p34_armtoken_source_bound as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p34b_armtoken"
prior.OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p34b_armtoken_source_bound"
prior.CATALOG = prior.OUTPUT / "source_bound_probe_catalog.json"
prior.PLAN = prior.OUTPUT / "source_bound_probe_plan.json"
prior.CONTRACT = prior.OUTPUT / "arm_token_contract.json"
prior.EPOCH = prior.OUTPUT / "epoch_reuse_receipt.json"


if __name__ == "__main__":
    raise SystemExit(prior.main())
