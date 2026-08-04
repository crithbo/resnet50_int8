from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.dequant_node0077_config_bound_simulator import (
    write_three_party_evidence,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build node0077 Dequant config-bound three-party evidence"
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    report, contract = write_three_party_evidence(args.root)
    print(
        json.dumps(
            {
                "status": report["status"],
                "ledger_delta": report["project_ledger_delta"],
                "simulator_inverse_sha256": report["physical_layout"][
                    "simulator_inverse_sha256"
                ],
                "contract_sha256": contract["contract_content_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
