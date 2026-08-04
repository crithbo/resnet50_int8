from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.conv_sa_family_closure import build_conv_sa_family_closure


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("contracts/conv_sa_family_local_closure_v1.json"),
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = build_conv_sa_family_closure(root)
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

