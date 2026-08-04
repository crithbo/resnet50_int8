from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.stage_config_system import (
    build_stage_config_system,
    write_stage_config_system,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the complete ResNet50 stage-to-operator-config system."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "contracts/operator_config/stage_config_system_v1.json",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    value = build_stage_config_system(ROOT)
    write_stage_config_system(args.output, value)
    summary = value["summary"]
    print(
        f"stages={summary['stage_count']} "
        f"families={summary['family_count']} "
        f"candidate_json_ready={summary['candidate_json_ready_count']} "
        f"zero_copy_ready={summary['zero_copy_binding_ready_count']} "
        f"blocked={summary['blocked_stage_count']} "
        f"formal={summary['formal_release_stage_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
