#!/usr/bin/env python3
"""Build the proposal-only node0004 composite C1 predesign contract."""

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
    write_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / CONTRACT_PATH)
    args = parser.parse_args()
    value = write_contract(ROOT, args.output.resolve())
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

