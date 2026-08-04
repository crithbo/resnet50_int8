#!/usr/bin/env python3
"""Materialize the node0077 atomic single-stage Dequant contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.dequant_atomic_dynamic import materialize_project_assets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = materialize_project_assets(args.project_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
