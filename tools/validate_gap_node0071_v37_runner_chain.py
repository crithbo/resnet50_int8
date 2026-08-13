from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_v35_runner_chain as base


base.ROOT_NAME = "r5_n71_gap_v37_dbclk_rdready_compilefix"


if __name__ == "__main__":
    raise SystemExit(base.main())
