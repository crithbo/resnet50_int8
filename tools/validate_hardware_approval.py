from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.hardware_approval import validate_hardware_approval_file


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a versioned hardware approval contract without generating W5 artifacts"
    )
    parser.add_argument("approval", type=Path)
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    approval = args.approval
    if not approval.is_absolute():
        approval = args.project_root / approval
    result = validate_hardware_approval_file(
        approval, args.project_root / "contracts/architecture.json"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
