from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.model import load_model_graph


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an auditable ONNX graph catalog")
    parser.add_argument("model", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    catalog = load_model_graph(args.model, expected_sha256=args.expected_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(catalog.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {len(catalog.nodes)} nodes and {len(catalog.tensors)} tensors "
        f"to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
