from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.stage_config_backend import (
    build_stage_backend_catalog,
    write_stage_backend_catalog,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the stage-to-JSON backend catalog.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "contracts/operator_config/stage_backend_catalog_v1.json",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    value = build_stage_backend_catalog(ROOT)
    write_stage_backend_catalog(args.output, value)
    print(
        f"families={value['summary']['hw_op_type_count']} "
        f"candidate_emitters={value['summary']['candidate_emitter_count']} "
        f"zero_copy_emitters={value['summary']['zero_copy_emitter_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
