from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.maxpool_instance import (
    load_maxpool_instance,
    write_maxpool_instance,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate or verify the frozen MaxPool instance")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("configs/maxpool/hwop-0002-00"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else project_root / args.output
    instance = (
        load_maxpool_instance(project_root, output)
        if args.check
        else write_maxpool_instance(project_root, output)
    )
    print(
        json.dumps(
            {
                "status": "validated" if args.check else "generated_and_validated",
                "root": str(instance.root),
                "wave_count": len(instance.configs),
                "config_sha256": [item["config_sha256"] for item in instance.manifest["waves"]],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
