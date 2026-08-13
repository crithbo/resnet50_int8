#!/usr/bin/env python3
"""Build the DequantizeLinear complete-JSON family evidence (local only)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.dequantize_linear_complete_json_regeneration import (
    ARTIFACT_REL,
    build_artifacts,
    finalize_public_validation,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--finalize-public", action="store_true")
    args = parser.parse_args(argv)
    root = args.workspace_root.resolve()
    output = args.output.resolve() if args.output else root / ARTIFACT_REL
    if args.finalize_public:
        report = finalize_public_validation(root, output)
        print(json.dumps(report["public_validation"], indent=2, sort_keys=True))
        return 0
    products = build_artifacts(root, output)
    print(
        json.dumps(
            {name: path.relative_to(root).as_posix() for name, path in products.items()},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
