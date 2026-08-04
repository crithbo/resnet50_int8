from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.register_semantics import (
    build_register_semantics_contract,
    write_register_semantics_contract,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the register semantic contract from xlsx or repository CSV."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--workbook", type=Path)
    source.add_argument("--csv", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "contracts/operator_config/register_semantics_v1.json",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    value = build_register_semantics_contract(
        ROOT, workbook_path=args.workbook, csv_path=args.csv
    )
    write_register_semantics_contract(args.output, value)
    summary = value["summary"]
    print(
        f"config_rows={summary['config_row_count']} "
        f"matched={summary['direct_json_match_count'] + summary['alias_json_match_count']} "
        f"unmatched={summary['unmatched_json_count']} "
        f"width_conflicts={summary['declared_width_range_conflict_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
