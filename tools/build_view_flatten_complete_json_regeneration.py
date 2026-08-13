#!/usr/bin/env python3
"""Build the view_flatten complete-JSON regeneration no-config deliverable."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.view_flatten_complete_json_regeneration import (  # noqa: E402
    build_view_flatten_complete_json_regeneration,
    run_negative_controls,
)


def main() -> int:
    try:
        result = build_view_flatten_complete_json_regeneration(ROOT)
        result["negative_controls"] = run_negative_controls(
            ROOT, ROOT / result["output_dir"]
        )
    except Exception as error:
        print(f"view_flatten regeneration failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
