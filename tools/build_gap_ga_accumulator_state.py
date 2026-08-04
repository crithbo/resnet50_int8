from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_ga_accumulator_state import (  # noqa: E402
    CONTRACT_PATH,
    build_gap_ga_accumulator_state_contract,
    write_gap_ga_accumulator_state_contract,
)


def main() -> int:
    try:
        value = build_gap_ga_accumulator_state_contract(ROOT)
        write_gap_ga_accumulator_state_contract(
            ROOT / CONTRACT_PATH, value
        )
    except Exception as error:
        print(
            f"GAP GA accumulator contract generation failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "status": value["status"],
                "server_test": value["server_test"]["status"],
                "package_sha256": value["server_test"]["zip"]["sha256"],
                "blocker": value["release"]["blocker"],
                "contract_sha256": value["contract_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
