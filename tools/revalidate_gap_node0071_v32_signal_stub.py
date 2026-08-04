import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_gap_node0071_v31_signal_stub as base

base.ROOT_NAME = "r5_n71_gap_v32_col_ag_mrm_lane_rulebind"
target = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{base.ROOT_NAME}.zip"
)
digest = hashlib.sha256(target.read_bytes()).hexdigest()
base.ZIP_SHA256 = base.base.ZIP_SHA256 = base.base.base.ZIP_SHA256 = digest
ORIGINAL_VALIDATE = base.validate


def validate(target_zip: Path, bash: Path):
    result = ORIGINAL_VALIDATE(target_zip, bash)
    result["schema"] = "gap-node0071-v32-col-ag-mrm-safe-signal-stub-v1"
    return result


base.validate = validate

if __name__ == "__main__":
    raise SystemExit(base.main())
