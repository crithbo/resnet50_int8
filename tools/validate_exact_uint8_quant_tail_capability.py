#!/usr/bin/env python3
"""Validate the fail-closed exact UINT8 quant-tail capability proposal."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from resnet50_pipeline.exact_uint8_quant_tail_capability import write_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contract",
        type=Path,
        default=PROJECT_ROOT
        / "contracts/operator_config/exact_uint8_quant_tail_capability_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT
        / "artifacts/operator_config_validation/exact-uint8-quant-tail-capability-v1/report.json",
    )
    args = parser.parse_args()
    report = write_report(args.contract.resolve(), PROJECT_ROOT, args.output.resolve())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
