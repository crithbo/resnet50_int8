from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.deepseek_primitive_rules import (  # noqa: E402
    build_deepseek_primitive_rules,
    write_deepseek_primitive_rules,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit native ndp-sim GA, SA and N2N capabilities and record "
            "ResNet transfer boundaries without implementing another generator."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "contracts/operator_config/"
            "deepseek_primitive_rules_v1.json"
        ),
    )
    args = parser.parse_args()
    value = build_deepseek_primitive_rules(ROOT)
    write_deepseek_primitive_rules(args.output, value)
    summary = value["summary"]
    print(
        f"status={value['status']} "
        f"ga={summary['ga_elementwise_template_count']} "
        f"sa={summary['sa_template_count']} "
        f"ring={summary['ring_template_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
