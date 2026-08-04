from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_repair_workload import (  # noqa: E402
    ADDRESS_BOUND_CONFIG_REL,
    build_address_bound_d_index_config,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the address-bound GAP D-index repair config."
    )
    parser.add_argument("--output", type=Path, default=ROOT / ADDRESS_BOUND_CONFIG_REL)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        manifest = build_address_bound_d_index_config(ROOT, output)
    except Exception as error:
        print(f"GAP D-index address-bound config failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": output.as_posix(),
                "config_sha256": manifest["config"]["sha256"],
                "distinct_transaction_bases": manifest["d_index_coverage"][
                    "derived_distinct_transaction_bases"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
