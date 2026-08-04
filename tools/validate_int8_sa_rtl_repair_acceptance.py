from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.int8_sa_rtl_repair_acceptance import (
    validate_active_rule_receipts,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path(
            "contracts/operator_config/int8_sa_rtl_repair_acceptance_v1.json"
        ),
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    contract_path = (
        args.contract if args.contract.is_absolute() else root / args.contract
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    result = validate_active_rule_receipts(root, contract)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
