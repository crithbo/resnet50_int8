from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.maxpool_padding_contract import (  # noqa: E402
    DEFAULT_SOURCE_CONFIG,
    write_maxpool_zero_padding_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the hash-bound UINT8 MaxPool zero-padding contract."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "contracts/maxpool_uint8_zero_padding_contract.json",
    )
    parser.add_argument(
        "--source-config",
        default=DEFAULT_SOURCE_CONFIG,
        help="project-relative, explicitly supported active ndp-sim MaxPool JSON",
    )
    args = parser.parse_args()
    try:
        value = write_maxpool_zero_padding_contract(
            ROOT, args.output, args.source_config
        )
    except Exception as error:
        print(f"MaxPool padding contract failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": value["status"],
                "output": str(args.output),
                "contract_sha256": value["contract_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
