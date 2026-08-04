from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_stage_schedule_evidence import (  # noqa: E402
    build_conv_stage_schedule_evidence,
    write_conv_stage_schedule_evidence,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the exact node-0004 wave-0 static schedule evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "contracts/operator_config/node0004_conv_schedule_evidence_v1.json"
        ),
    )
    args = parser.parse_args()
    try:
        value = build_conv_stage_schedule_evidence(ROOT)
        write_conv_stage_schedule_evidence(args.output, value)
    except Exception as error:
        print(f"Conv schedule evidence generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": value["status"],
                "output": str(args.output),
                "evidenced_tile_count": value["logical_schedule"][
                    "evidenced_tile_count"
                ],
                "full_logical_tile_count": value["logical_schedule"][
                    "full_logical_tile_count"
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
