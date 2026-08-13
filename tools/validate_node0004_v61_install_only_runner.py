from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.validate_node0004_v60_install_only_runner as validator


validator.INSTALL = "r5_n4_hw_v61_lcmap_argv_fix"


if __name__ == "__main__":
    raise SystemExit(validator.main())
