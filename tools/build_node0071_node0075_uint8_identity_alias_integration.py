#!/usr/bin/env python3
"""Build the node0071-D to node0075-A metadata-alias overlay contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.node0071_node0075_uint8_identity_alias_integration import (
    write_contract,
)

DEFAULT_CONTRACT = (
    ROOT
    / "contracts/operator_config/"
    "node0071_node0075_uint8_identity_alias_integration_v1.json"
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
