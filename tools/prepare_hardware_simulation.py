from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from resnet50_pipeline.hardware_simulation_frontend import (  # noqa: E402
    prepare_hardware_simulation,
)


DEFAULT_PACKAGE = Path("artifacts/w5/hwop-0004-00/hardware_execplan")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and decode a model_execplan/Bank_data package into generic "
            "Start_Comp invocations without running numerical operator kernels."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--package",
        type=Path,
        help="Hardware package root; defaults to the current frozen Conv package.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the machine-readable preparation report.",
    )
    parser.add_argument(
        "--full-report",
        action="store_true",
        help="Print the complete stage report instead of a compact summary.",
    )
    args = parser.parse_args()

    root = args.project_root.resolve()
    package = (args.package or (root / DEFAULT_PACKAGE)).resolve()
    prepared = prepare_hardware_simulation(package)
    report = prepared.report()
    if args.output is not None:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    printable = report if args.full_report else {
        "status": report["status"],
        "scope": report["scope"],
        "node_id": report["node_id"],
        "command_count": report["command_count"],
        "command_counts": report["command_counts"],
        "runtime_stage_count": report["runtime_stage_count"],
        "bank_image_count": len(report["bank_images"]),
        "numeric_executor": report["numeric_executor"]["status"],
        "package": str(package),
    }
    if args.output is not None:
        printable["output"] = str(args.output.resolve())
    print(json.dumps(printable, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
