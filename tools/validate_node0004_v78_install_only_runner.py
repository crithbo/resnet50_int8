from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v77_install_only_runner as inherited


inherited.inherited.wrapper.wrapper.validator.INSTALL = (
    "r5_n4_hw_v78_buffer_input_owner_diag"
)


if __name__ == "__main__":
    raise SystemExit(inherited.inherited.wrapper.wrapper.validator.main())
