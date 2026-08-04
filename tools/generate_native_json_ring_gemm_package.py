#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from resnet50_pipeline.native_json_ring_gemm_package import (
    generate_native_json_ring_gemm_package,
    validate_native_json_ring_gemm_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the hardware-tested native DeepSeek ring-GEMM control package.")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "artifacts/w5/deepseek_ring_gemm_control/v1/hardware_execplan_package",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    report = (
        validate_native_json_ring_gemm_package(output)
        if args.check
        else generate_native_json_ring_gemm_package(PROJECT_ROOT, output)
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
