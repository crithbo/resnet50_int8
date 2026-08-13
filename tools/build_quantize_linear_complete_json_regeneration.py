#!/usr/bin/env python3
"""Build the fail-closed QuantizeLinear complete-JSON regeneration audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.quantize_linear_complete_json_regeneration import (
    ARTIFACT_REL,
    build_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / ARTIFACT_REL)
    args = parser.parse_args()
    report = build_artifacts(ROOT, args.output_dir.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

