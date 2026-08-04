"""Validate the node0075 first-blocking-leaf receipt against current disk."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from resnet50_pipeline.node0075_materializer_blocking_leaf import (
    validate_report,
    load_json,
)


REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0075-materializer-blocking-leaf-v1/report.json"
)


def main() -> None:
    result = validate_report(ROOT, load_json(REPORT))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
