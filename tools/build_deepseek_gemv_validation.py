from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from resnet50_pipeline.deepseek_gemv_validation import (
    materialize_gemv_native_e2,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the crop-derived DeepSeek decode FFN gate "
            "GEMV through two isolated native toolchains."
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
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = materialize_gemv_native_e2(
        args.project_root.resolve(), args.python.resolve()
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
