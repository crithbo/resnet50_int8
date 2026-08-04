from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.maxpool_config_only_e2 import (  # noqa: E402
    generate_maxpool_config_only_e2,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the local E2-only ResNet50 node-0002 MaxPool closure."
    )
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=(
            ROOT
            / "artifacts/operator_config_validation/"
            "maxpool-node0002-config-only-e2-v1"
        ),
    )
    args = parser.parse_args()
    try:
        report = generate_maxpool_config_only_e2(ROOT, args.output)
    except Exception as error:
        print(f"MaxPool E2 generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "valid": report["valid"],
                "claim": report["claim"],
                "evidence_level": report["evidence_level"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
