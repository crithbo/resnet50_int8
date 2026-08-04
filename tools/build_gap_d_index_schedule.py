from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_d_index_schedule import (  # noqa: E402
    write_gap_d_index_schedule_artifacts,
)


def main() -> int:
    try:
        value = write_gap_d_index_schedule_artifacts(ROOT)
    except Exception as error:
        print(f"GAP D-index schedule generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": value["status"],
                "derived_config": value["derived_config"]["path"],
                "distinct_bias_count": value["numeric_carrier"][
                    "distinct_bias_count"
                ],
                "native_mapping": value["native_mapping"]["status"],
                "remaining_blockers": value["release"]["remaining_blockers"],
                "contract_sha256": value["contract_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
