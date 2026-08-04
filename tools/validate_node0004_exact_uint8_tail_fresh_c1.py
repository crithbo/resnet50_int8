#!/usr/bin/env python3
"""Validate the fresh, dependency-only node0004 exact UINT8-tail contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from resnet50_pipeline.node0004_exact_uint8_tail_fresh_c1 import (
    CONTRACT_PATH,
    REPORT_PATH,
    write_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contract",
        type=Path,
        default=PROJECT_ROOT / CONTRACT_PATH,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / REPORT_PATH,
    )
    args = parser.parse_args()
    report = write_report(
        args.contract.resolve(), PROJECT_ROOT, args.output.resolve()
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
