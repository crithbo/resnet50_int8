from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_native_package import (  # noqa: E402
    build_gap_server_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the matrix-complete GAP hwop-0071-00 server candidate."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "artifacts/operator_config_validation/r5-server-candidates/"
            "gap-hwop0071-sum-v1"
        ),
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        value = build_gap_server_candidate(ROOT, output)
    except Exception as error:
        print(f"GAP server candidate generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(output),
                "status": value["status"],
                "matrix_file_count": value["execution_payload"]["matrix_file_count"],
                "payload_tree_sha256": value["payload_tree_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
