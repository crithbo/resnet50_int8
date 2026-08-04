from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_repair_workload import (  # noqa: E402
    DEFAULT_OUTPUT_REL,
    build_gap_repair_workload,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the fully regenerated GAP v9 server workload."
    )
    parser.add_argument("--output", type=Path, default=ROOT / DEFAULT_OUTPUT_REL)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        manifest = build_gap_repair_workload(ROOT, output)
    except Exception as error:
        print(f"GAP repair workload generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": output.as_posix(),
                "status": manifest["status"],
                "candidate_release": manifest["candidate_release"],
                "tree_sha256": manifest["tree_sha256"],
                "runtime_bitstream_sha256": manifest["full_rebuild"]["controls"][
                    "runtime_bitstream"
                ]["installed_sha256"],
                "dynamic_release_pending": manifest["dynamic_release_pending"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
