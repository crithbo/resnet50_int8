from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.typed_config_parameters import (
    build_typed_config_parameter_contract,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the W4-28 C7 formula-only typed parameter contract"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "contracts" / "typed_config_parameter_contract.json",
    )
    args = parser.parse_args()
    report = build_typed_config_parameter_contract(ROOT)
    payload = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "size_bytes": len(payload),
                "node_count": report["coverage"]["node_count"],
                "hw_op_count": report["coverage"]["hw_op_count"],
                "w5_authorized": report["scope"]["w5_authorized"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
