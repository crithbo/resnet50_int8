from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_native_package import (  # noqa: E402
    CONFIG_ROOT_REL,
    TRANSPORT_REL,
    write_conv_native_inputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate complete three-wave node-0004 Conv inputs."
    )
    parser.add_argument("--output", type=Path, default=ROOT / TRANSPORT_REL)
    parser.add_argument(
        "--config-output", type=Path, default=ROOT / CONFIG_ROOT_REL
    )
    args = parser.parse_args()
    try:
        value = write_conv_native_inputs(
            ROOT, args.output, args.config_output
        )
    except Exception as error:
        print(f"Conv native input generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "config_output": str(args.config_output),
                "operator_count": value["dispatch"]["operator_count"],
                "record_count": value["dispatch"][
                    "operator_slice_record_count"
                ],
                "matrix_file_count": value["dispatch"][
                    "matrix_file_count"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
