from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.w4_audit import audit_w4_gate


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit all W4 profiles/transitions and decide the G4 gate"
    )
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--hardware-approval",
        type=Path,
        help="Optional approved hardware contract; defaults to contracts/hardware_approval.json",
    )
    args = parser.parse_args()
    report = audit_w4_gate(args.project_root, args.hardware_approval)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output
        if not output.is_absolute():
            output = args.project_root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
