from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.conv_1x1_hardware_freeze import export_hardware_freeze


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the frozen real 1x1 hardware handoff")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "w5" / "hwop-0004-00" / "hardware_freeze",
    )
    args = parser.parse_args()
    manifest = export_hardware_freeze(ROOT, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "freeze_id": manifest["freeze_id"],
                "status": manifest["status"],
                "file_count": len(manifest["files"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
