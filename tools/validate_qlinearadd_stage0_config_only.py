from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.qlinearadd_stage0_config_only import (  # noqa: E402
    validate_contract_receipts,
    validate_contract_path,
    validate_configuration_path,
    validate_receipts,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("configuration", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument(
        "--receipts-only",
        action="store_true",
        help="validate provenance/replay/claim receipts without numeric rerun",
    )
    args = parser.parse_args()
    path = (
        args.configuration
        if args.configuration.is_absolute()
        else ROOT / args.configuration
    )
    if args.receipts_only:
        report = validate_receipts(
            json.loads(path.read_text(encoding="utf-8")), ROOT
        )
    else:
        report = validate_configuration_path(path, ROOT)
    if args.contract is not None:
        contract_path = (
            args.contract if args.contract.is_absolute() else ROOT / args.contract
        )
        if args.receipts_only:
            contract_report = validate_contract_receipts(
                json.loads(contract_path.read_text(encoding="utf-8")), ROOT
            )
        else:
            contract_report = validate_contract_path(contract_path, ROOT)
        report = {
            "schema": "qlinearadd_stage0_config_only_combined_validation_v1",
            "valid": report["valid"] and contract_report["valid"],
            "configuration_validation": report,
            "contract_validation": contract_report,
            "claim": None,
            "package_release": contract_report["package_release"],
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
