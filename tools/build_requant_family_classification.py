from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.requant_family_classification import (  # noqa: E402
    CONTRACT_PATH,
    REPORT_PATH,
    RECEIPT_PATH,
    build_read_receipt,
    build_requant_family_classification,
    build_requant_family_contract,
    write_json,
)


def main() -> int:
    receipt = build_read_receipt(ROOT)
    report = build_requant_family_classification(ROOT)
    contract = build_requant_family_contract(ROOT, report)
    write_json(ROOT / RECEIPT_PATH, receipt)
    write_json(ROOT / REPORT_PATH, report)
    write_json(ROOT / CONTRACT_PATH, contract)
    print(
        json.dumps(
            {
                "status": report["status"],
                "summary": report["summary"],
                "report_sha256": report["report_sha256"],
                "contract_sha256": contract["contract_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
