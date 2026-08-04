from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_sum_padding_contract import (
    write_gap_sum_zero_padding_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build exact ResNet50 GAP-sum zero-padding authorization."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "contracts/operator_config/gap_sum_zero_padding_contract_v1.json",
    )
    args = parser.parse_args()
    value = write_gap_sum_zero_padding_contract(ROOT, args.output)
    print(
        f"status={value['status']} "
        f"request={value['operator_semantics']['request_id']} "
        f"source={value['authorization']['source_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
