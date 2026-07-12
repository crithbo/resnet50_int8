from __future__ import annotations

import argparse
from pathlib import Path

from resnet50_pipeline.golden import generate_subop_golden
from resnet50_pipeline.lowering import lower_model_graph
from resnet50_pipeline.model import load_model_graph


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate lowering-boundary subop golden")
    parser.add_argument("model", type=Path)
    parser.add_argument("runtime_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    graph = load_model_graph(args.model, expected_sha256=args.expected_sha256)
    manifest = generate_subop_golden(
        args.model,
        args.runtime_root,
        args.output,
        graph,
        lower_model_graph(graph),
    )
    print(f"saved {len(manifest['internal_tensors'])} internal tensors to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
