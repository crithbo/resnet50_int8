from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.maxpool_config_only_e2 import (  # noqa: E402
    validate_maxpool_config_only_e2,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the final materialized MaxPool node-0002 E2 bundle."
    )
    parser.add_argument(
        "artifact",
        type=Path,
        nargs="?",
        default=(
            ROOT
            / "artifacts/operator_config_validation/"
            "maxpool-node0002-config-only-e2-v1"
        ),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = validate_maxpool_config_only_e2(ROOT, args.artifact)
    except Exception as error:
        print(f"MaxPool E2 validation failed: {error}", file=sys.stderr)
        return 1
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
