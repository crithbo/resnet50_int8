from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.operator_config_validator import OperatorConfigValidator


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed, read-only shadow validation for native ndp-sim JSON configs."
    )
    parser.add_argument("paths", nargs="+", type=Path, help="JSON files or directories")
    parser.add_argument("--output", type=Path, help="optional aggregate JSON report")
    parser.add_argument(
        "--development",
        action="store_true",
        help="require external semantic contracts such as SA physical layout",
    )
    return parser.parse_args()


def _expand(paths: list[Path]) -> list[Path]:
    expanded: set[Path] = set()
    for path in paths:
        if path.is_dir():
            expanded.update(item for item in path.glob("*.json") if item.is_file())
        else:
            expanded.add(path)
    return sorted(expanded, key=lambda item: str(item).lower())


def main() -> int:
    args = _parse_args()
    paths = _expand(args.paths)
    reports = [
        OperatorConfigValidator().validate_file(path, development_mode=args.development)
        for path in paths
    ]
    payload = {
        "schema": "operator-config-shadow-scan-v1",
        "mode": "development" if args.development else "reproduction",
        "read_only": True,
        "summary": {
            "files": len(reports),
            "valid": sum(report.valid for report in reports),
            "invalid": sum(not report.valid for report in reports),
        },
        "reports": [report.to_dict() for report in reports],
    }
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0 if all(report.valid for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
