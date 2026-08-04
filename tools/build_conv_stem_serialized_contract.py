from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_stem_serialized_contract import (  # noqa: E402
    write_stem_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = write_stem_contract(args.project_root)
    print(
        json.dumps(
            {
                "valid": result["validation"]["valid"],
                "classification": result["contract"]["classification"],
                "contract": result["contract_path"],
                "validation": result["validation_path"],
                "package_release": result["contract"]["claim_controls"][
                    "package_release"
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
