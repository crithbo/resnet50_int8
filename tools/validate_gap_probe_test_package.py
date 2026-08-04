#!/usr/bin/env python3
"""Validate the checked GAP v7 server probe directory, ZIP, and SHA sidecar."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_probe_test_package import (  # noqa: E402
    DEFAULT_OUTPUT_REL,
    GapProbePackageError,
    validate_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=ROOT / DEFAULT_OUTPUT_REL)
    args = parser.parse_args()
    package = args.package if args.package.is_absolute() else ROOT / args.package
    try:
        report = validate_package(ROOT, package)
    except (GapProbePackageError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"GAP probe package validation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
