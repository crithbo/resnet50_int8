from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.target_config_audit import build_authority_report


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the official RTL28 JSON/bitstream configuration source")
    parser.add_argument("--source-root", type=Path, default=ROOT / "ndp-sim-ref")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_authority_report(args.source_root.resolve())
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload.encode("utf-8"))
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
