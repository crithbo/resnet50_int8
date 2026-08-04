#!/usr/bin/env python3
"""Materialize the node0001 single-occurrence two-stage dynamic contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.requant_single_occurrence_dynamic import (
    materialize_project_assets,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = materialize_project_assets(args.project_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
