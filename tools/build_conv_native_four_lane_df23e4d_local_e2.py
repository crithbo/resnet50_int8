from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_native_four_lane_df23e4d_local_e2 import (  # noqa: E402
    CONTRACT_REL,
    write_contract,
)
from resnet50_pipeline.hashing import sha256_file  # noqa: E402


def main() -> int:
    path = ROOT / CONTRACT_REL
    if path.exists():
        print(f"refusing to overwrite: {path}", file=sys.stderr)
        return 1
    try:
        contract = write_contract(ROOT)
    except Exception as error:
        print(f"native four-lane df23e4d E2 failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "contract": str(CONTRACT_REL),
                "sha256": sha256_file(path),
                "status": contract["status"],
                "roundtrip": contract["native_roundtrip"][
                    "json_mapping_bitstream_execplan_sca"
                ],
                "performance": contract["address_lifetime_terminal"][
                    "actual_performance_inversion"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
