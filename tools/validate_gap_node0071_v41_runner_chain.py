#!/usr/bin/env python3
"""Run the frozen v40 runner-chain controls against the v41 identity."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_v40_runner_chain as base


base.NAME = "r5_n71_gap_v41_branch_isolated_config_fix"


if __name__ == "__main__":
    raise SystemExit(base.main())
