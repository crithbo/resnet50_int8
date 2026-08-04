from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.qlinearadd_predesign import validate_qlinearadd_predesign


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the fail-closed QLinearAdd P1-A predesign contract."
    )
    parser.add_argument("contract", type=Path)
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate_qlinearadd_predesign(
        args.contract, repository_root=args.repository_root
    )
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
