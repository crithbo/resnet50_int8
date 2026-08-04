#!/usr/bin/env python3
"""Materialize the local config-bound 26-vs-25 diagnostic bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from resnet50_pipeline.exact_uint8_quant_tail_rounding_discriminator import (
    build_bundle,
    write_report,
)


DEFAULT_CONTRACT = (
    PROJECT_ROOT
    / "contracts/operator_config/exact_uint8_quant_tail_rounding_discriminator_v1.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "configs/native_ndp_sim/exact_uint8_quant_tail_rounding_26_vs25_config_only_v1"
)
DEFAULT_REPORT = (
    PROJECT_ROOT
    / "artifacts/operator_config_validation/"
    "exact-uint8-quant-tail-rounding-26-vs25-config-only-v1/report.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    contract = args.contract.resolve()
    output_dir = args.output_dir.resolve()
    build_bundle(contract, PROJECT_ROOT, output_dir)
    report = write_report(contract, PROJECT_ROOT, output_dir, args.report.resolve())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
