#!/usr/bin/env python3
"""Build the frozen node0072/View/node0074 identity-fusion contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.quantize_node0074_identity_fusion import write_contract


DEFAULT_CONTRACT = (
    ROOT
    / "contracts/operator_config/"
    "quantize_node0074_dq_view_q_identity_fusion_v1.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args()
    contract = write_contract(ROOT, args.contract.resolve())
    print(json.dumps(contract, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
