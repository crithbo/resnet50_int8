#!/usr/bin/env python3
"""Run the corrected p37 family audit for fresh p37b identity."""

from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p37_saepoch_package as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE = "r5_n4_0cc_p37b_saepoch"
prior.SOURCE = "r5_n4_0cc_p37_saepoch"
prior.SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p37_saepoch.zip"
prior.SOURCE_SHA = "441da07145ee883585ff57dd8bc3320c1486dc2ea47f852759e2ff3443995e9a"


if __name__ == "__main__":
    raise SystemExit(prior.main())
