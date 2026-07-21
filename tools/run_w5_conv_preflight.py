from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.w5_conv_preflight import build_w5_first_conv_preflight


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the fail-closed first-real-Conv preflight report"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "artifacts"
            / "w5"
            / "hwop-0004-00"
            / "v10"
            / "preflight.json"
        ),
    )
    parser.add_argument(
        "--execplan-request",
        type=Path,
        help="Versioned typed execplan request to bind into the preflight report.",
    )
    parser.add_argument(
        "--encoder-candidate",
        type=Path,
        help=(
            "Native server-profile candidate directory (or its "
            "candidate_manifest.json) to validate and bind."
        ),
    )
    args = parser.parse_args()
    report = build_w5_first_conv_preflight(
        ROOT,
        execplan_request_path=args.execplan_request,
        encoder_candidate_path=args.encoder_candidate,
    )
    payload = (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "size_bytes": len(payload),
                "status": report["status"],
                "tile_id": report["first_tile_golden_preflight"]["tile_id"],
                "p_mismatches": report["first_tile_golden_preflight"][
                    "comparisons"
                ]["P"]["mismatch_count"],
                "d_mismatches": report["first_tile_golden_preflight"][
                    "comparisons"
                ]["D"]["mismatch_count"],
                "target_simulator": report["deepseek_target_simulator_entry"][
                    "status"
                ],
                "native_encoder_candidate_id": report.get(
                    "native_encoder_candidate", {}
                ).get("candidate_id"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
