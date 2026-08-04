from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_repair_release import (  # noqa: E402
    DEFAULT_EXECPLAN_REL,
    DEFAULT_OUTPUT_REL,
    DEFAULT_RTL_REPAIR_REL,
    build_gap_repair_release_gate,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the GAP repair local release-gate report."
    )
    parser.add_argument("--execplan", type=Path, default=ROOT / DEFAULT_EXECPLAN_REL)
    parser.add_argument(
        "--rtl-repair", type=Path, default=ROOT / DEFAULT_RTL_REPAIR_REL
    )
    parser.add_argument("--output", type=Path, default=ROOT / DEFAULT_OUTPUT_REL)
    args = parser.parse_args()
    execplan = args.execplan if args.execplan.is_absolute() else ROOT / args.execplan
    repair = (
        args.rtl_repair
        if args.rtl_repair.is_absolute()
        else ROOT / args.rtl_repair
    )
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        print(f"refusing to overwrite GAP release gate: {output}", file=sys.stderr)
        return 1
    try:
        value = build_gap_repair_release_gate(
            ROOT,
            execplan_root=execplan,
            rtl_repair_root=repair,
        )
        output.mkdir(parents=True)
        report = output / "GAP_REPAIR_RELEASE_GATE.json"
        report.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except Exception as error:
        print(f"GAP repair release gate failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": value["status"],
                "candidate_release": value["candidate_release"],
                "output": str(report),
                "gate_sha256": value["gate_sha256"],
                "remaining_blockers": value["remaining_blockers"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
