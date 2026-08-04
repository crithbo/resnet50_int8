from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.requant_config_bound_simulator import (
    CONTRACT_RELATIVE,
    OUTPUT_RELATIVE,
    write_config_bound_evidence,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build node0001 final-JSON-bound Requant simulator evidence"
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--contract", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    report, contract = write_config_bound_evidence(
        root,
        output=args.output or root / OUTPUT_RELATIVE,
        contract=args.contract or root / CONTRACT_RELATIVE,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "final_json_count": report["source_identity"]["final_json_count"],
                "occurrence_count": report["lifecycle"]["occurrence_count"],
                "stage_count": report["lifecycle"]["stage_count"],
                "mismatch_count": report["numeric"]["golden_mismatch_count"],
                "contract_sha256": contract["contract_content_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
