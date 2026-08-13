#!/usr/bin/env python3
"""Run the p32 exact runner through the inherited isolated six-state harness."""

from __future__ import annotations

from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p30_runner_harness as prior


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p32b_validowner"
SOURCE_ID = "r5_n4_0cc_p31_postclear"
SOURCE_SHA256 = "d022977daebb1c633d0c4fa32ca58cf5b660a6f4c4dff6cb11d499a21d2345c9"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"


def main() -> int:
    prior.PACKAGE_ID = PACKAGE_ID
    prior.SOURCE_ID = SOURCE_ID
    prior.SOURCE_SHA256 = SOURCE_SHA256
    prior.SOURCE_ZIP = SOURCE_ZIP
    return prior.main()


if __name__ == "__main__":
    raise SystemExit(main())
