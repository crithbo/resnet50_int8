#!/usr/bin/env python3
"""Validate node0073 View metadata and an optional endpoint binding certificate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.flatten_physical_view import (  # noqa: E402
    validate_view_metadata,
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        default=ROOT / "configs/view/node0073_zero_copy_view_v1.json",
    )
    parser.add_argument(
        "--binding",
        type=Path,
        help="Final node0072-D/node0074-A addressed binding certificate.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        config = _load(args.config)
        binding = _load(args.binding) if args.binding is not None else None
        report = validate_view_metadata(config, ROOT, binding)
    except Exception as error:
        print(f"node0073 physical View validation failed: {error}", file=sys.stderr)
        return 1
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            rendered,
            encoding="utf-8",
            newline="\n",
        )
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
