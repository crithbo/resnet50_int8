from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_stem_request_address_validator import (  # noqa: E402
    write_stem_bundle_manifest,
    write_stem_request_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=ROOT)
    args = parser.parse_args()
    report = write_stem_request_report(args.project_root)
    bundle = write_stem_bundle_manifest(args.project_root)
    print(
        json.dumps(
            {
                "valid": report["valid"] and bundle["valid"],
                "request_count_with_multiplicity": report["facts"][
                    "request_count_with_multiplicity"
                ],
                "unique_request_address_count": report["facts"][
                    "unique_request_address_count"
                ],
                "ordered_request_address_sha256": report["facts"][
                    "ordered_request_address_sha256"
                ],
                "unique_request_addresses_sha256": report["facts"][
                    "unique_request_addresses_sha256"
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
