#!/usr/bin/env python3
"""Build the reuse-only node0072-D -> node0073 -> node0074-A endpoint manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.flatten_shared_endpoint_manifest import build_assets  # noqa: E402


def main() -> int:
    try:
        result = build_assets(ROOT)
    except Exception as error:
        print(f"Flatten shared endpoint build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
