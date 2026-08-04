from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_native_package import (  # noqa: E402
    CANDIDATE_REL,
    SEMANTIC_REL,
    build_conv_server_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the matrix-complete three-wave node-0004 Conv candidate."
    )
    parser.add_argument("--output", type=Path, default=ROOT / CANDIDATE_REL)
    parser.add_argument(
        "--semantic-output", type=Path, default=ROOT / SEMANTIC_REL
    )
    args = parser.parse_args()
    if args.semantic_output.exists():
        print(
            f"refusing to overwrite semantic contract: {args.semantic_output}",
            file=sys.stderr,
        )
        return 1
    try:
        value = build_conv_server_candidate(ROOT, args.output)
        args.semantic_output.parent.mkdir(parents=True, exist_ok=True)
        args.semantic_output.write_bytes(
            (args.output / "semantic_contract.json").read_bytes()
        )
    except Exception as error:
        print(f"Conv server candidate generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "status": value["status"],
                "matrix_file_count": value["execution_payload"][
                    "matrix_file_count"
                ],
                "payload_tree_sha256": value["payload_tree_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
