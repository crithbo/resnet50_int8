from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.r5_resolution_overlay import build_r5_resolution_overlay  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the hash-bound R5 local resolution overlay.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "contracts/resnet50_r5_resolution_overlay.json",
    )
    args = parser.parse_args()
    try:
        value = build_r5_resolution_overlay(ROOT)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception as error:
        print(f"R5 resolution overlay generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": value["status"],
                "output": str(args.output),
                "application_counts": value["application_counts"],
                "overlay_sha256": value["overlay_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
