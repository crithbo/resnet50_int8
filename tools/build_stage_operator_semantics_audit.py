from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.stage_operator_semantics_audit import (
    CONTRACT_PATH,
    write_stage_operator_semantics_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the hash-bound stage-to-operator JSON/RTL semantics audit."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / CONTRACT_PATH,
    )
    args = parser.parse_args()
    value = write_stage_operator_semantics_audit(ROOT, args.output)
    findings = {
        item["issue_id"]: item["classification"]
        for item in value["findings"]
    }
    print(
        f"status={value['status']} "
        f"contract={value['contract_sha256']} "
        f"findings={findings}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
