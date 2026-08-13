#!/usr/bin/env python3
"""Run the exact p23 runner through the inherited native-Conv harness."""

from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p19_runner_harness as base


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p23_epochflow"
SOURCE_ID = "r5_n4_0cc_p22_eoenfix"
SOURCE_SHA256 = "876f9a16575648ddcb2dd594a881651cf7c678ddb30d344d112c68951f4fd8cf"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"


def main() -> int:
    base.PACKAGE_ID = PACKAGE_ID
    base.SOURCE_ID = SOURCE_ID
    base.SOURCE_SHA256 = SOURCE_SHA256
    base.SOURCE_ZIP = SOURCE_ZIP
    base.INPUT_PREFIX = f"install/cfg_pkg/{PACKAGE_ID}/"
    base.OLD_INPUT_PREFIX = f"install/cfg_pkg/{SOURCE_ID}/"
    base.OLD_OUTPUT_PREFIX = f"install/codex_runs/{SOURCE_ID}/a0/c0/d/"
    base.OUTPUT_PREFIX = f"install/codex_runs/{PACKAGE_ID}/a0/c0/d/"
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
