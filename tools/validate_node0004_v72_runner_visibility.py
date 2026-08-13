from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools.validate_node0004_v65_runner_visibility as validator  # noqa: E402
validator.PACKAGE = "r5_n4_hw_v72_token_origin_accept_diag"
if __name__ == "__main__":
    raise SystemExit(validator.main())
