from __future__ import annotations

import argparse
from pathlib import Path

from resnet50_pipeline.int8_sa_rtl_repair_acceptance import (
    write_int8_sa_rtl_repair_acceptance,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "contracts/operator_config/int8_sa_rtl_repair_acceptance_v1.json"
        ),
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    write_int8_sa_rtl_repair_acceptance(root, output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
