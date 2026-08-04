from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_native_package import (  # noqa: E402
    TRANSPORT_REL,
    write_gap_native_transport,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the 16-slice native C8HW8 GAP sum transport."
    )
    parser.add_argument("--output", type=Path, default=ROOT / TRANSPORT_REL)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        value = write_gap_native_transport(ROOT, output)
    except Exception as error:
        print(f"GAP native transport generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(output),
                "status": value["status"],
                "matrix_file_count": value["summary"]["matrix_file_count"],
                "independent_mismatch_count": value["summary"][
                    "independent_mismatch_count"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
