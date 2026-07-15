from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.conv_1x1_hardware_freeze import compare_hardware_dump


def main() -> int:
    parser = argparse.ArgumentParser(description="Inverse and compare frozen real 1x1 P/D dumps")
    parser.add_argument("--freeze-root", type=Path, required=True)
    parser.add_argument("--dump-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare_hardware_dump(args.freeze_root, args.dump_root)
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
