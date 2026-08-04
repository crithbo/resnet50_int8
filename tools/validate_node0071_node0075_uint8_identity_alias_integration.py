#!/usr/bin/env python3
"""Validate the node0071-D to node0075-A metadata-alias overlay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.node0071_node0075_uint8_identity_alias_integration import (
    write_report,
)

DEFAULT_CONTRACT = (
    ROOT
    / "contracts/operator_config/"
    "node0071_node0075_uint8_identity_alias_integration_v1.json"
)
DEFAULT_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0071-node0075-uint8-identity-alias-integration-v1/report.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = write_report(
        args.contract.resolve(), ROOT, args.report.resolve()
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
