"""Fresh package identity after v53 pre-release predicate-scope audit blocked."""

from pathlib import Path

import build_qlinearadd_node0007_tailround_bufready_v53_package as implementation


ROOT = Path(__file__).resolve().parents[1]
implementation.TARGET = "r5_qadd_n7_tailround_bufready_v54"
implementation.LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-bufready-v54-package"
implementation.OUT_ZIP = implementation.LOCAL / f"{implementation.TARGET}.zip"


if __name__ == "__main__":
    raise SystemExit(implementation.main())
