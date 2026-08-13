from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools.validate_node0004_v65_install_only_runner as wrapper  # noqa: E402
wrapper.validator.INSTALL = "r5_n4_hw_v69_branch_drain_diag"
if __name__ == "__main__":
    raise SystemExit(wrapper.validator.main())
