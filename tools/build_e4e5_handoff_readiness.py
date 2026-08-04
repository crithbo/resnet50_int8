from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.e4e5_handoff import (  # noqa: E402
    build_e4e5_handoff_readiness,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build fail-closed E4/E5 representative handoff readiness."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "contracts/resnet50_e4e5_handoff_readiness.json",
    )
    args = parser.parse_args()
    try:
        report = build_e4e5_handoff_readiness(ROOT)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as error:
        print(f"E4/E5 handoff readiness generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": report["status"],
                "output": str(args.output),
                "coverage": report["coverage"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
