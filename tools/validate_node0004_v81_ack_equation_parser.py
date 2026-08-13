from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools.validate_node0004_v79_ack_equation_parser as base
base.PACKAGE = "r5_n4_hw_v81_ack_phase_targetfix"
if __name__ == "__main__": raise SystemExit(base.main())
