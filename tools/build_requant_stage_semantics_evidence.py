from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.requant_stage_semantics_evidence import (  # noqa: E402
    build_requant_stage_semantics_evidence,
    write_requant_stage_semantics_evidence,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build node-0004 requant formula and GA-placement evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "contracts/operator_config/node0004_requant_semantics_evidence_v1.json"
        ),
    )
    args = parser.parse_args()
    try:
        value = build_requant_stage_semantics_evidence(ROOT)
        write_requant_stage_semantics_evidence(args.output, value)
    except Exception as error:
        print(f"requant evidence generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": value["status"],
                "output": str(args.output),
                "shard_count": value["parameter_placement"]["shard_count"],
                "mismatch_count": value["independent_local_numeric_replay"][
                    "mismatch_count"
                ],
                "candidate_config_emission_allowed": value["emission_gate"][
                    "candidate_config_emission_allowed"
                ],
                "contract_sha256": value["contract_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
