#!/usr/bin/env python3
"""Run the frozen v40 EXIT/TERM signal controls against the v41 identity."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_gap_node0071_v40_signal_stub as base


base.ROOT_NAME = "r5_n71_gap_v41_branch_isolated_config_fix"
base.TARGET = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-gap-node0071-v41-branch-isolated-config-fix"
    / "r5_n71_gap_v41_branch_isolated_config_fix.zip"
)


if __name__ == "__main__":
    raise SystemExit(base.main())
