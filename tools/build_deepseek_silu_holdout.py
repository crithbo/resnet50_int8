from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from resnet50_pipeline.deepseek_silu_holdout import (
    CONTRACT_PATH,
    build_silu_holdout_contract,
    materialize_and_run_silu_holdout,
    validate_silu_holdout_contract,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize and validate the crop-derived DeepSeek prefill SiLU "
            "Stage→JSON→bitstream local E2 holdout."
        )
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(sys.executable),
        help="Python executable used for both isolated native runs.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate existing artifacts without creating new run directories.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    if args.validate_only:
        contract_path = root / CONTRACT_PATH
        checked = json.loads(contract_path.read_text(encoding="utf-8"))
        validate_silu_holdout_contract(checked, root)
        rebuilt = build_silu_holdout_contract(root)
        print(contract_path)
        print(rebuilt["contract_sha256"])
        return 0

    result = materialize_and_run_silu_holdout(
        root, args.python.resolve()
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
