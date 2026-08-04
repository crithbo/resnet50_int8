from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.conv_instance import make_conv_target_request
from resnet50_pipeline.conv_instance_preflight import build_conv_instance_preflight


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one typed Conv candidate preflight")
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--encoder-candidate",
        type=Path,
        help="Native server-profile candidate directory (or candidate_manifest.json).",
    )
    args = parser.parse_args()
    request = make_conv_target_request(ROOT, args.node_id)
    output = args.output or request.preflight_path
    report = build_conv_instance_preflight(
        ROOT, args.node_id, encoder_candidate_path=args.encoder_candidate
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "node_id": args.node_id,
                "output": str(output.resolve()),
                "status": report["status"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
