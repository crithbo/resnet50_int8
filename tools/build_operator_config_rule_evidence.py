from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.operator_config_rule_extractor import (
    build_operator_config_rule_evidence,
    write_operator_config_rule_evidence,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build same-family and template-to-instance JSON rule evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "contracts/operator_config/config_rule_evidence_v1.json",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    value = build_operator_config_rule_evidence(ROOT)
    write_operator_config_rule_evidence(args.output, value)
    print(
        f"pairs={value['summary']['pair_count']} "
        f"topology_pairs={value['summary']['topology_changing_pair_count']} "
        f"relocation_only={value['summary']['relocation_only_pair_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
