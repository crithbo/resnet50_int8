from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tools.audit_node0004_v73_final_zip as audit
audit.PACKAGE = "r5_n4_hw_v74_sourcebound_epoch_diag"
if __name__ == "__main__":
    raise SystemExit(audit.main())
