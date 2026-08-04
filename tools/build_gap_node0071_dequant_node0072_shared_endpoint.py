from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_node0071_dequant_node0072_shared_endpoint import (  # noqa: E402
    validate_manifest,
    write_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build or validate the GAP node0071-D producer-owned canonical "
            "shared endpoint for Dequant node0072-A. No numeric execution or "
            "package generation is performed."
        )
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    report = (
        validate_manifest(args.root)
        if args.validate_only
        else write_outputs(args.root)
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
