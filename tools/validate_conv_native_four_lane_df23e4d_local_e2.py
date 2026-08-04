from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_native_four_lane_df23e4d_local_e2 import (  # noqa: E402
    CONTRACT_REL,
    build_contract,
)
from resnet50_pipeline.hashing import sha256_file  # noqa: E402


def main() -> int:
    path = ROOT / CONTRACT_REL
    try:
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        rebuilt = build_contract(ROOT)
        if on_disk != rebuilt:
            raise ValueError("on-disk contract differs from rebuilt contract")
    except Exception as error:
        print(f"native four-lane df23e4d validation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "VALIDATION_PASS",
                "contract": str(CONTRACT_REL),
                "sha256": sha256_file(path),
                "mapping_count": rebuilt["native_roundtrip"]["mapping_count"],
                "execplan_count": rebuilt["native_roundtrip"]["execplan_count"],
                "sca_file_count": rebuilt["native_roundtrip"]["sca_file_count"],
                "server_action": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
