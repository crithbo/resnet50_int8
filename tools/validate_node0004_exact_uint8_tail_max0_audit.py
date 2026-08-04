from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.node0004_exact_uint8_tail_max0_audit import (
    CONTRACT_PATH,
    validate_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--contract", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    contract = (
        args.contract.resolve() if args.contract else root / CONTRACT_PATH
    )
    print(json.dumps(validate_contract(contract, root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
