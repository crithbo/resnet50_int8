"""Fresh v56 identity for the corrected v55 pre-release package surface."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_qlinearadd_node0007_tailround_lanephase_v55_package as impl


impl.TARGET = "r5_qadd_n7_tailround_lanephase_v56"
impl.CANDIDATE = (
    impl.ROOT
    / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-v56-candidate"
)
impl.LOCAL = (
    impl.ROOT
    / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-v56-package"
)
impl.OUT_ZIP = impl.LOCAL / f"{impl.TARGET}.zip"


if __name__ == "__main__":
    raise SystemExit(impl.main())
