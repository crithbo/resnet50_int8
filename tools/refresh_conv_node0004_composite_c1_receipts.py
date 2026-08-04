#!/usr/bin/env python3
"""Refresh active-rule receipts without rerunning node0004 numeric analysis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_node0004_composite_c1_predesign import (
    CONTRACT_PATH,
    write_receipt_refresh,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=ROOT / CONTRACT_PATH)
    parser.add_argument("--output", type=Path, default=ROOT / CONTRACT_PATH)
    args = parser.parse_args()
    value = write_receipt_refresh(
        args.contract.resolve(), ROOT, args.output.resolve()
    )
    print(
        json.dumps(
            {
                "status": value["status"],
                **value["receipt_only_integration_refresh"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
