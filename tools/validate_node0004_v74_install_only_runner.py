from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tools.validate_node0004_v65_install_only_runner as wrapper
wrapper.validator.INSTALL = "r5_n4_hw_v74_sourcebound_epoch_diag"
if __name__ == "__main__":
    raise SystemExit(wrapper.validator.main())
