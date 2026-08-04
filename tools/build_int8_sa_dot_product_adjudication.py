from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.int8_sa_dot_product_adjudication import (
    build_int8_sa_dot_product_adjudication,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "contracts/operator_config/int8_sa_dot_product_adjudication_v1.json"
        ),
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = build_int8_sa_dot_product_adjudication(root)
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

