#!/usr/bin/env python3
"""Build the node0073 zero-copy physical View contract and local proof."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.flatten_physical_view import (  # noqa: E402
    build_node0073_view_assets,
)


def main() -> int:
    try:
        result = build_node0073_view_assets(ROOT)
    except Exception as error:
        print(f"node0073 physical View build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
