#!/usr/bin/env python3
"""Build the fail-closed Requant config-only bypass adjudication."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.requant_config_only_bypass import (  # noqa: E402
    CONTRACT_REL,
    build_adjudication,
    validate_adjudication,
    write_adjudication,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    if args.check:
        path = root / CONTRACT_REL
        value = json.loads(path.read_text(encoding="utf-8"))
        result = validate_adjudication(root, value)
    else:
        result = write_adjudication(root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
