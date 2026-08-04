#!/usr/bin/env python3
"""Validate the producer+View-ready, Quantize-pending canonical endpoint state."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.flatten_canonical_endpoint_owner import (  # noqa: E402
    validate_canonical_manifest,
)


def main() -> int:
    try:
        report = validate_canonical_manifest(ROOT)
    except Exception as error:
        print(f"Flatten canonical owner validation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
