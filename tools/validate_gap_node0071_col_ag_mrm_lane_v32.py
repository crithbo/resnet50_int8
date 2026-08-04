import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_col_ag_mrm_lane_v31 as base

base.ROOT_NAME = "r5_n71_gap_v32_col_ag_mrm_lane_rulebind"
base.TEST_ID = "r5-gap-node0071-v32-col-ag-mrm-byte-lane-rulebind-diagnostic"

if __name__ == "__main__":
    raise SystemExit(base.main())
