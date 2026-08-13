#!/usr/bin/env python3
"""Run the frozen p31 exact runner through the isolated six-state harness."""

from __future__ import annotations

import sys
from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p30_runner_harness as prior


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p31_postclear"
SOURCE_ID = "r5_n4_0cc_p30_bankvalid"
SOURCE_SHA256 = "8229b380c9b33f99c8bd27d3eb21ce2ce17aae1b5eb0278926f27307887cbf34"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"


def main() -> int:
    prior.PACKAGE_ID = PACKAGE_ID
    prior.SOURCE_ID = SOURCE_ID
    prior.SOURCE_SHA256 = SOURCE_SHA256
    prior.SOURCE_ZIP = SOURCE_ZIP
    return prior.main()


if __name__ == "__main__":
    raise SystemExit(main())
