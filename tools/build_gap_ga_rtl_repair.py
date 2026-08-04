from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_ga_rtl_repair import (  # noqa: E402
    DEFAULT_OUTPUT_REL,
    build_gap_ga_rtl_repair,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the hash-gated GAP GA functional RTL repair bundle."
    )
    parser.add_argument("--output", type=Path, default=ROOT / DEFAULT_OUTPUT_REL)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        manifest = build_gap_ga_rtl_repair(ROOT, output)
    except Exception as error:
        print(f"GAP GA RTL repair generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": output.as_posix(),
                "repair_id": manifest["repair_id"],
                "manifest_sha256": manifest["manifest_sha256"],
                "iverilog_passed": manifest["local_syntax_check"]["passed"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
