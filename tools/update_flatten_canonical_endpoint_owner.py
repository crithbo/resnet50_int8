#!/usr/bin/env python3
"""Append the Flatten/View owner projection to the canonical endpoint manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.flatten_canonical_endpoint_owner import (  # noqa: E402
    update_canonical_manifest,
    write_validation_receipt,
)


def main() -> int:
    try:
        report = update_canonical_manifest(ROOT)
        receipt = write_validation_receipt(ROOT, report)
    except Exception as error:
        print(f"Flatten canonical owner update failed: {error}", file=sys.stderr)
        return 1
    result = dict(report)
    result["validation_receipt"] = receipt.relative_to(ROOT).as_posix()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
