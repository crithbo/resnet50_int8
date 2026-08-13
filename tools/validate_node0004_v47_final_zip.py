from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v46_final_zip as validator


validator.INSTALL_NAME = "r5_n4_hw_v47_lc9_split_cloudrtl"
validator.VERSION = 47
validator.ZIP_SHA256 = (
    "516173e54132e2ee31cf2d4f750c46a595bb0bf31afb7f5b6661fc5a0ed6a015"
)


if __name__ == "__main__":
    raise SystemExit(validator.main())
