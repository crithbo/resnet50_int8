from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.operator_config_package_validator import (  # noqa: E402
    OperatorConfigPackageValidator,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate SCA addresses, files, aliasing and semantic contracts."
    )
    parser.add_argument("graph_root", type=Path)
    parser.add_argument("graph", type=Path)
    parser.add_argument("contract", type=Path)
    parser.add_argument(
        "--provenance-root",
        type=Path,
        help="root for contract provenance artifacts (default: graph_root)",
    )
    parser.add_argument(
        "--allow-missing-matrix-files",
        action="store_true",
        help="validate planner layout without requiring assembled matrix payloads",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        contract = json.loads(args.contract.read_text(encoding="utf-8"))
        report = OperatorConfigPackageValidator().validate(
            args.graph_root,
            graph_path=args.graph,
            semantic_contract=contract,
            require_matrix_files=not args.allow_missing_matrix_files,
            provenance_root=args.provenance_root,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    payload = json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
