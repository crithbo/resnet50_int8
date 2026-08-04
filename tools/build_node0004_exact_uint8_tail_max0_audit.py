from __future__ import annotations

import argparse
from pathlib import Path

from resnet50_pipeline.node0004_exact_uint8_tail_max0_audit import (
    CONTRACT_PATH,
    REPORT_PATH,
    write_contract,
    write_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.project_root.resolve()
    contract_path = root / CONTRACT_PATH
    report_path = root / REPORT_PATH
    write_contract(root, contract_path)
    report = write_report(contract_path, root, report_path)
    print(report["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
