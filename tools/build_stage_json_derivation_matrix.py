from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.stage_json_derivation_matrix import (  # noqa: E402
    build_stage_json_derivation_matrix,
    write_stage_json_derivation_matrix,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the hash-bound stage JSON derivation matrix."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "contracts/operator_config/"
            "stage_json_derivation_matrix_v1.json"
        ),
    )
    args = parser.parse_args()
    try:
        value = build_stage_json_derivation_matrix(ROOT)
        write_stage_json_derivation_matrix(args.output, value)
    except Exception as error:
        print(
            f"stage JSON derivation matrix generation failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "status": value["status"],
                "output": str(args.output),
                "summary": value["summary"],
                "contract_sha256": value["contract_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
