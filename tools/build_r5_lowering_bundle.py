from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.r5_lowering_bundle import build_r5_lowering_bundle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the 133-stage hash-bound R5 typed lowering request bundle."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "contracts/resnet50_r5_lowering_bundle.json",
    )
    args = parser.parse_args()
    try:
        report = build_r5_lowering_bundle(ROOT)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as error:
        print(f"R5 lowering bundle generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": report["status"],
                "output": str(args.output),
                "coverage": report["coverage"],
                "request_set_sha256": report["request_set_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
