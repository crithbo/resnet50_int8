#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.native_json_maxpool_package import (
    generate_native_json_maxpool_package,
    validate_native_json_maxpool_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or validate the immutable native-JSON ResNet MaxPool server package"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/w5/native_json_maxpool/v1/hardware_execplan_package"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else project_root / args.output
    report = (
        validate_native_json_maxpool_package(output)
        if args.check
        else generate_native_json_maxpool_package(project_root, output)
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
