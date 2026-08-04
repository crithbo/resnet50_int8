from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.maxpool_guarded_storage import write_address_seed  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize the flat address seed for guarded node-0002 MaxPool."
    )
    parser.add_argument("guarded_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    guarded = args.guarded_root if args.guarded_root.is_absolute() else ROOT / args.guarded_root
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        result = write_address_seed(ROOT, guarded, output)
    except Exception as error:
        print(f"MaxPool address seed failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
