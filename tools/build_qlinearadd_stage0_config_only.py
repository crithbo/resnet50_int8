from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.qlinearadd_stage0_config_only import (  # noqa: E402
    validate_contract,
    validate_contract_receipts,
    validate_configuration,
    validate_receipts,
    write_contract,
    write_configuration,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "configs/qlinearadd_stage0_config_only/"
            "qlinearadd_stage0_config_only_v1.json"
        ),
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path(
            "contracts/operator_config/"
            "qlinearadd_stage0_config_only_contract_v1.json"
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(
            "artifacts/qlinearadd_stage0_config_only/"
            "validation_report.json"
        ),
    )
    parser.add_argument(
        "--receipts-only",
        action="store_true",
        help="refresh and validate rule/replay/claim receipts without numeric rerun",
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    contract_path = (
        args.contract if args.contract.is_absolute() else ROOT / args.contract
    )
    report_path = args.report if args.report.is_absolute() else ROOT / args.report
    configuration = write_configuration(ROOT, output)
    contract = write_contract(ROOT, output, configuration, contract_path)
    if args.receipts_only:
        config_report = validate_receipts(configuration, ROOT)
        contract_report = validate_contract_receipts(contract, ROOT)
    else:
        config_report = validate_configuration(configuration, ROOT)
        contract_report = validate_contract(contract, ROOT)
    report = {
        "schema": "qlinearadd_stage0_config_only_build_report_v1",
        "valid": config_report["valid"] and contract_report["valid"],
        "numeric_analysis_repeated": not args.receipts_only,
        "configuration_validation": config_report,
        "contract_validation": contract_report,
        "package_release": contract["package_release"],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
