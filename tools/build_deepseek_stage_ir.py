from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.deepseek_stage_ir import (  # noqa: E402
    build_deepseek_stage_ir,
    write_deepseek_stage_ir,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the hash-bound DeepSeek composite-op to hardware-stage "
            "to authorized-JSON crosswalk."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "contracts/operator_config/deepseek_stage_ir_crosswalk_v1.json"
        ),
    )
    args = parser.parse_args()
    value = build_deepseek_stage_ir(ROOT)
    write_deepseek_stage_ir(args.output, value)
    summary = value["summary"]
    print(
        f"templates={summary['deepseek_template_count']} "
        f"graph_referenced={summary['graph_referenced_template_count']} "
        f"graphs={summary['unique_graph_count']} "
        f"stages={summary['stage_occurrence_count']} "
        f"stage_types={summary['unique_stage_type_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
