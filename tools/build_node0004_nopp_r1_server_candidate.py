from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.node0004_server_candidate import (  # noqa: E402
    build_node0004_server_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the matrix-complete node0004 nopp-r1 smoke candidate."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "artifacts/operator_config_validation/r5-server-candidates/"
            "node0004-nopp-r1-v2"
        ),
    )
    args = parser.parse_args()
    try:
        value = build_node0004_server_candidate(ROOT, args.output)
    except Exception as error:
        print(f"node0004 server candidate generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": value["status"],
                "output": str(args.output),
                "payload_file_count": value["payload_file_count"],
                "payload_tree_sha256": value["payload_tree_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
