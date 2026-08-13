from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v48_observer_syntax as implementation


implementation.INSTALL_NAME = "r5_n4_hw_v49_lc9_actual_compilefix"
implementation.BEGIN = "    // v49 LC9_ACTUAL_COMPILEFIX_TRIGGERED_BEGIN"
implementation.END = "    // v49 LC9_ACTUAL_COMPILEFIX_TRIGGERED_END"


if __name__ == "__main__":
    sys.exit(implementation.main())
