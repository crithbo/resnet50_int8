from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_native_four_lane_performance import (  # noqa: E402
    build_negative_psum_reachability,
    write_report,
)
from resnet50_pipeline.hashing import sha256_file  # noqa: E402


DEFAULT_OUTPUT = (
    ROOT
    / "contracts/operator_config/"
    "conv_native_four_lane_negative_psum_reachability_v1.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scan frozen ResNet50 Conv W3 occurrences for the two named "
            "SA_PE_Float_CSA negative-psum counterexamples."
        )
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--hw-op-id",
        action="append",
        default=[],
        help="restrict to one or more Conv hw_op ids; default scans all 53",
    )
    parser.add_argument(
        "--no-stop-on-hit",
        action="store_true",
        help="continue after a hit instead of the required fail-fast default",
    )
    parser.add_argument("--position-chunk", type=int, default=256)
    parser.add_argument("--output-value-budget", type=int, default=4_000_000)
    args = parser.parse_args()
    if args.position_chunk <= 0 or args.output_value_budget <= 0:
        parser.error("chunk and budget must be positive")
    try:
        report = build_negative_psum_reachability(
            ROOT,
            selected_hw_op_ids=set(args.hw_op_id) or None,
            stop_on_first_hit=not args.no_stop_on_hit,
            position_chunk=args.position_chunk,
            output_value_budget=args.output_value_budget,
        )
        write_report(args.output, report)
    except Exception as error:
        print(f"native-four-lane reachability failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "bytes": args.output.stat().st_size,
                "sha256": sha256_file(args.output),
                "status": report["status"],
                "scope": report["scope"],
                "result": report["result"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if report["status"] == "EXACT_REACHABILITY_PASS":
        return 0
    if report["status"] == "HARDWARE_CAPABILITY_BLOCKED":
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
