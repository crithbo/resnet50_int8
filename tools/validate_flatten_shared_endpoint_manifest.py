#!/usr/bin/env python3
"""Validate the fail-closed Flatten shared endpoint manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.flatten_shared_endpoint_manifest import (  # noqa: E402
    validate_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=(
            ROOT
            / "contracts/operator_config/"
            "node0072_node0073_node0074_shared_endpoint_manifest_v1.json"
        ),
    )
    args = parser.parse_args()
    try:
        value = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = validate_manifest(value, ROOT)
    except Exception as error:
        print(f"Flatten shared endpoint validation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
