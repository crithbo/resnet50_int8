#!/usr/bin/env python3
"""Fresh identity after the p37 per-lane tag overconstraint audit escape."""

from pathlib import Path

import prepare_conv_native_four_lane_0ccae916_p37_saepoch_source_bound as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p37b_saepoch"
prior.OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p37b_saepoch_source_bound"
prior.CATALOG = prior.OUTPUT / "source_bound_probe_catalog.json"
prior.PLAN = prior.OUTPUT / "source_bound_probe_plan.json"
prior.ARM_CONTRACT = prior.OUTPUT / "arm_known_contract.json"
prior.SA_CONTRACT = prior.OUTPUT / "sa_epoch_contract.json"
prior.IDENTITY = prior.OUTPUT / "exact_instance_identity.json"


if __name__ == "__main__":
    raise SystemExit(prior.main())
