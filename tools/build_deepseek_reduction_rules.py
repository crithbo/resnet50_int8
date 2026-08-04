from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.deepseek_reduction_rules import (  # noqa: E402
    build_deepseek_reduction_rules,
    write_deepseek_reduction_rules,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Extract DeepSeek local/remote reduction and exact ResNet GAP rules."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "contracts/operator_config/"
            "deepseek_reduction_rules_v1.json"
        ),
    )
    args = parser.parse_args()
    value = build_deepseek_reduction_rules(ROOT)
    write_deepseek_reduction_rules(args.output, value)
    gap = value["gap_resolution"]
    print(
        f"status={value['status']} "
        f"request={gap['request_id']} "
        f"active_slices={gap['exact_schedule']['active_slice_count']} "
        f"resolved={','.join(gap['resolved_local_blockers'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
