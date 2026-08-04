from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_server_workload import (  # noqa: E402
    DEFAULT_OUTPUT_REL,
    build_gap_server_workload,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Assemble the validated GAP candidate into the same directory shape "
            "as the locally generated server-passed Decode package."
        )
    )
    parser.add_argument("--output", type=Path, default=ROOT / DEFAULT_OUTPUT_REL)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        value = build_gap_server_workload(ROOT, output)
    except Exception as error:
        print(f"GAP server workload generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": value["status"],
                "output": str(output),
                "file_count": value["file_count"],
                "tree_sha256": value["tree_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
