#!/usr/bin/env python3
"""Validate the checked GAP v10 corrected-config plus stock-RTL test ZIP."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_PATH = Path(__file__).resolve().parents[1]
if str(ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(ROOT_PATH))

from tools.build_gap_stock_rtl_decision_test_package import (  # noqa: E402
    DEFAULT_OUTPUT_REL,
    ROOT,
    validate_package,
)


def main() -> int:
    try:
        report = validate_package(ROOT, ROOT / DEFAULT_OUTPUT_REL)
    except Exception as error:
        print(
            f"GAP v10 stock RTL decision package validation failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
