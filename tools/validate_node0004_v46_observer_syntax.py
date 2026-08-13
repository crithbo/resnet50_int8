from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v44_observer_syntax as validator


validator.INSTALL_NAME = "r5_n4_hw_v46_lc9_split_cloudrtl"
validator.VERSION = 46
validator.BEGIN = "    // v46 LC9_SPLIT_ACTUAL_CONSUMER_BEGIN"
validator.END = "    // v46 LC9_SPLIT_ACTUAL_CONSUMER_END"


if __name__ == "__main__":
    raise SystemExit(validator.main())
