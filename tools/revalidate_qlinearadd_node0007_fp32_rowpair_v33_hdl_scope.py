from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_qlinearadd_node0007_split_c_pairmatrix_v29_hdl_scope as base


base.NAME = "r5_qadd_n7_crow32_v33"

if __name__ == "__main__":
    raise SystemExit(base.main())
