#!/usr/bin/env python3
"""Build the exact W3 GA INT32-to-FP32 input-domain matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.ga_int32_input_domain_matrix import (  # noqa: E402
    CONTRACT_PATH,
    build_ga_int32_input_domain_matrix,
    write_ga_int32_input_domain_matrix,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / CONTRACT_PATH)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        value = build_ga_int32_input_domain_matrix(ROOT)
        write_ga_int32_input_domain_matrix(output, value)
    except Exception as error:
        print(
            f"GA INT32 input-domain matrix generation failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "status": value["status"],
                "summary": value["summary"],
                "contract_sha256": value["contract_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
