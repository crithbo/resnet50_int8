#!/usr/bin/env python3
"""Validate and write the node0074 exact-division entry audit report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from resnet50_pipeline.quantize_node0074_exact_division_entry_audit import (
    write_report,
)


DEFAULT_CONTRACT = (
    PROJECT_ROOT
    / "contracts/operator_config/quantize_node0074_exact_division_entry_audit_v1.json"
)
DEFAULT_REPORT = (
    PROJECT_ROOT
    / "artifacts/operator_config_validation/"
    "r5-quantize-node0074-exact-division-entry-audit-v1/report.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = write_report(
        args.contract.resolve(), PROJECT_ROOT, args.report.resolve()
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
