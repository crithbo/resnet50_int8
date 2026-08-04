#!/usr/bin/env python3
"""Validate the frozen node0072/View/node0074 identity-fusion adjudication."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.quantize_node0074_identity_fusion import write_report


DEFAULT_CONTRACT = (
    ROOT
    / "contracts/operator_config/"
    "quantize_node0074_dq_view_q_identity_fusion_v1.json"
)
DEFAULT_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-quantize-node0074-dq-view-q-identity-fusion-v1/report.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = write_report(args.contract.resolve(), ROOT, args.report.resolve())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
