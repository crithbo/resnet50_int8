from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.requant_native_package import (  # noqa: E402
    CONFIG_ROOT_REL,
    TRANSPORT_REL,
    write_requant_native_inputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate all node-0004 requant shards, three-wave dispatch, "
            "and independent W3 A/D transport."
        )
    )
    parser.add_argument("--output", type=Path, default=ROOT / TRANSPORT_REL)
    parser.add_argument(
        "--config-root", type=Path, default=ROOT / CONFIG_ROOT_REL
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    config_root = (
        args.config_root
        if args.config_root.is_absolute()
        else ROOT / args.config_root
    )
    try:
        value = write_requant_native_inputs(ROOT, output, config_root)
    except Exception as error:
        print(f"node-0004 requant generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(output),
                "config_root": str(config_root),
                "operator_count": value["dispatch"]["operator_count"],
                "matrix_file_count": value["dispatch"]["matrix_file_count"],
                "mismatch_count": value["independent_numeric_replay"][
                    "mismatch_count"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
