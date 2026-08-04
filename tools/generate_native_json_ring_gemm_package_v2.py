#!/usr/bin/env python3
"""Generate or validate the four-participant upstream Ring4 GEMM package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from resnet50_pipeline.native_json_ring_gemm_package_v2 import (  # noqa: E402
    generate_native_json_ring_gemm_package_v2,
    validate_native_json_ring_gemm_package_v2,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate or validate the v2 DeepSeek Ring4 package from the fresh "
            "upstream JSON and run_all_slices encoder evidence"
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/w5/deepseek_ring_gemm_control/v2/hardware_execplan_package"
        ),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    report = (
        validate_native_json_ring_gemm_package_v2(output)
        if args.check
        else generate_native_json_ring_gemm_package_v2(PROJECT_ROOT, output)
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
