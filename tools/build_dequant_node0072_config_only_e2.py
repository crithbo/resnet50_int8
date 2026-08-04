from __future__ import annotations

import json
from pathlib import Path

from resnet50_pipeline.dequant_node0072_config_only import materialize_local_e2


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    report, contract = materialize_local_e2(ROOT)
    print(
        json.dumps(
            {
                "status": report["status"],
                "logical_sha256": report["config_bound_simulator"][
                    "logical_sha256"
                ],
                "bit_mismatch_count": report["config_bound_simulator"][
                    "bit_mismatch_count"
                ],
                "contract_sha256": contract["contract_content_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
