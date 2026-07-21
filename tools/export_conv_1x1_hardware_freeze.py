from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.conv_1x1_hardware_freeze import export_hardware_freeze
from resnet50_pipeline.conv_instance import build_conv_target_request


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a typed Conv instance as a physical hardware freeze"
    )
    parser.add_argument("--node-id", default="node-0004")
    parser.add_argument(
        "--output",
        type=Path,
    )
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--accumulate-encoder-root", type=Path)
    parser.add_argument("--requant-encoder-root", type=Path)
    parser.add_argument(
        "--encoder-candidate",
        type=Path,
        help=(
            "Validated native server-profile candidate directory (or its manifest); "
            "mutually exclusive with legacy encoder roots."
        ),
    )
    parser.add_argument(
        "--revision",
        help="Create a revised first-Conv freeze without inheriting immutable v1 identity.",
    )
    args = parser.parse_args()
    request = build_conv_target_request(ROOT, args.node_id)
    output = args.output or (
        ROOT / "artifacts" / "w5" / request.spec.accumulate_hw_op_id / "hardware_freeze"
    )
    manifest = export_hardware_freeze(
        ROOT,
        output,
        node_id=args.node_id,
        preflight_path=args.preflight,
        accumulate_encoder_root=args.accumulate_encoder_root,
        requant_encoder_root=args.requant_encoder_root,
        encoder_candidate_path=args.encoder_candidate,
        revision=args.revision,
    )
    print(
        json.dumps(
            {
                "node_id": args.node_id,
                "output": str(output.resolve()),
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
