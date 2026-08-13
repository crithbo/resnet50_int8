#!/usr/bin/env python3
"""Validate the view_flatten no-config complete-JSON regeneration bundle."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.view_flatten_complete_json_regeneration import (  # noqa: E402
    run_negative_controls,
    validate_regeneration_bundle,
)


def main() -> int:
    output = (
        ROOT
        / "artifacts/operator_config_validation/"
        "r5_complete_json_regeneration_v1/view_flatten"
    )
    try:
        result = validate_regeneration_bundle(ROOT, output)
        result["negative_controls"] = run_negative_controls(ROOT, output)
    except Exception as error:
        print(f"view_flatten regeneration validation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
