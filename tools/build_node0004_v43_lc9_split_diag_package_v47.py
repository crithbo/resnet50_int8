from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v43_lc9_split_diag_package_v46 as prior


builder = prior.builder
builder.INSTALL_NAME = "r5_n4_hw_v47_lc9_split_cloudrtl"
builder.VERSION = 47
builder.OBSERVER_BLOCK = builder.OBSERVER_BLOCK.replace(
    "v46 LC9_SPLIT", "v47 LC9_SPLIT"
)


if __name__ == "__main__":
    raise SystemExit(builder.main())
