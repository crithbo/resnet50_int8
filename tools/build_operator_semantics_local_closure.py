#!/usr/bin/env python3
"""Build the fail-closed local closure for plan 0.3 operator semantics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.operator_semantics_local_closure import (  # noqa: E402
    CONTRACT_PATH,
    build_operator_semantics_local_closure,
    write_operator_semantics_local_closure,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / CONTRACT_PATH)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        value = build_operator_semantics_local_closure(ROOT)
        write_operator_semantics_local_closure(output, value)
    except Exception as error:
        print(
            f"operator semantics local closure generation failed: {error}",
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
