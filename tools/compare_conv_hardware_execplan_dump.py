from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from resnet50_pipeline.conv_execplan_hardware import (  # noqa: E402
    compare_conv_hardware_bank_dump,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract P/D from post-run Bank_data dumps and compare the frozen Conv result."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--sim-bank-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    package = args.package.resolve()
    report = compare_conv_hardware_bank_dump(
        root,
        package,
        args.sim_bank_root,
        args.evidence_root,
    )
    summary = {
        "status": report["status"],
        "comparison": report["comparison"],
        "evidence_root": str(args.evidence_root.resolve()),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
