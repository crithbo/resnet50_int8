from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.validate_node0004_v61_lcmap_observer as validator


validator.INSTALL = "r5_n4_hw_v63_runnerdiag"


if __name__ == "__main__":
    raise SystemExit(validator.main())
