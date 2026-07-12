from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.lowering import legacy_mapping_dict, lower_model_graph
from resnet50_pipeline.model import load_model_graph


def main() -> int:
    parser = argparse.ArgumentParser(description="Map the legacy 77 ResNet primitives")
    parser.add_argument("model", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    graph = load_model_graph(args.model)
    value = legacy_mapping_dict(graph, lower_model_graph(graph))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"mapped {value['primitive_count']} legacy primitives to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
