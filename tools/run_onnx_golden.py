from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from resnet50_pipeline.golden.onnx_runtime import run_all_node_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump every ONNX node output reproducibly")
    parser.add_argument("model", type=Path)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    input_data = np.load(args.input, allow_pickle=False)
    manifest = run_all_node_outputs(
        args.model,
        input_data,
        args.output,
        expected_sha256=args.expected_sha256,
    )
    print(
        f"saved {len(manifest['nodes'])} node records and "
        f"{len(manifest['tensors'])} runtime tensors to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
