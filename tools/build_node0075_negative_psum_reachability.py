from __future__ import annotations

import argparse
from pathlib import Path

from resnet50_pipeline.node0075_negative_psum_reachability import (
    build_report,
    write_report,
)


DEFAULT_OUTPUT = Path(
    "contracts/operator_config/"
    "node0075_negative_psum_reachability_v1.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    write_report(output, build_report(root))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
