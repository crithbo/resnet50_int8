from __future__ import annotations

import argparse
from pathlib import Path

from resnet50_pipeline.node0004_exact_uint8_tail_max0_audit import (
    CONTRACT_PATH,
    REPORT_PATH,
    refresh_receipts,
    write_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.project_root.resolve()
    contract = root / CONTRACT_PATH
    report = root / REPORT_PATH
    refresh_receipts(contract, root)
    result = write_report(contract, root, report)
    print(result["status"])
    print(f"numeric_analysis_repeated={result['numeric_analysis_repeated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
