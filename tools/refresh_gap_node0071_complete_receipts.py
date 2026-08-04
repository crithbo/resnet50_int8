#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_complete_config_only import (  # noqa: E402
    refresh_read_receipt_and_contract,
)


def main() -> int:
    try:
        result = refresh_read_receipt_and_contract(ROOT)
    except Exception as error:
        print(f"GAP receipt refresh failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
