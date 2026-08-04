from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.maxpool_guarded_storage import write_guarded_wave0  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate node-0002 guarded C4HWC4 wave-0 graph and W3 tensors."
    )
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        manifest = write_guarded_wave0(ROOT, output)
    except Exception as error:
        print(f"guarded MaxPool generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "output": str(output),
                "graph_sha256": manifest["graph"]["sha256"],
                "slice_count": manifest["summary"]["slice_count"],
                "independent_mismatch_count": manifest["summary"]["independent_mismatch_count"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
