from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v76_return_contract as inherited


inherited.PACKAGE = "r5_n4_hw_v78_buffer_input_owner_diag"


if __name__ == "__main__":
    raise SystemExit(inherited.main())
