from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_gap_node0071_v35_signal_stub as base


ROOT_NAME = "r5_n71_gap_v37_dbclk_rdready_compilefix"
TARGET = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{ROOT_NAME}.zip"
)
base.ROOT_NAME = ROOT_NAME
base.TARGET = TARGET
base.ZIP_SHA256 = hashlib.sha256(TARGET.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(base.main())
