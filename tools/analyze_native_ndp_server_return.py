from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.native_server_return import (  # noqa: E402
    analyze_native_server_return,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze a native NDP server return directory/ZIP, classify the "
            "furthest hardware checkpoint, and compare returned D matrices."
        )
    )
    parser.add_argument("return_path", type=Path)
    parser.add_argument("--workload", type=Path, required=True)
    parser.add_argument("--profile", type=Path)
    parser.add_argument(
        "--run-id", choices=("run1", "run2", "diagnostic"), default="run1"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return_path = (
        args.return_path
        if args.return_path.is_absolute()
        else (ROOT / args.return_path)
    )
    workload = args.workload if args.workload.is_absolute() else ROOT / args.workload
    profile = (
        args.profile
        if args.profile is None or args.profile.is_absolute()
        else ROOT / args.profile
    )
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        print(f"output must be a fresh path: {output}", file=sys.stderr)
        return 1
    try:
        report = analyze_native_server_return(
            return_path,
            workload,
            profile_path=profile,
            run_id=args.run_id,
        )
    except Exception as error:
        print(f"native NDP server return analysis failed: {error}", file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "classification": report["classification"],
                "furthest_checkpoint": report["checkpoint_analysis"][
                    "furthest_direct_checkpoint"
                ],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
