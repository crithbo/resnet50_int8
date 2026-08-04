from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.operator_config_request_address_validator import (
    OperatorConfigRequestAddressValidator,
)


def _parse_binding(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("binding must be OP_ID=PATH")
    op_id, raw_path = value.split("=", 1)
    if not op_id or not raw_path:
        raise argparse.ArgumentTypeError("binding must be OP_ID=PATH")
    return op_id, Path(raw_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay stream Write_Reg commands and enumerate RTL-remapped memory requests."
    )
    parser.add_argument("graph_root", type=Path)
    parser.add_argument("graph_json", type=Path)
    parser.add_argument(
        "--source-config",
        action="append",
        default=[],
        type=_parse_binding,
        metavar="OP_ID=PATH",
        help="hash-bound source config for one graph operator (repeatable)",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = OperatorConfigRequestAddressValidator().validate(
        args.graph_root,
        graph_path=args.graph_json,
        source_configs=dict(args.source_config),
    ).to_dict()
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
