import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_gap_node0071_v31_observer_hdl_scope as base

base.INSTALL_NAME = "r5_n71_gap_v32_col_ag_mrm_lane_rulebind"
target = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{base.INSTALL_NAME}.zip"
)
base.EXPECTED_ZIP_SHA256 = base.sha256_path(target)
base.EXPECTED_ZIP_BYTES = target.stat().st_size

if __name__ == "__main__":
    raise SystemExit(base.main())
