from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tools.validate_node0004_v66_return_contract as validator
validator.PACKAGE = "r5_n4_hw_v75_sourcebound_collectfix"
if __name__ == "__main__":
    raise SystemExit(validator.main())
