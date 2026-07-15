from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_execplan_transport import (
    build_conv_execplan_transport_contract,
    validate_conv_execplan_transport_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the W5 Conv typed execplan transport closure contract"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "contracts" / "conv_execplan_transport.json",
    )
    args = parser.parse_args()
    value = build_conv_execplan_transport_contract(ROOT)
    validate_conv_execplan_transport_contract(value, ROOT)
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
