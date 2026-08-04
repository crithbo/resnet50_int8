from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.stage_state_lifetime_contract import (  # noqa: E402
    CONTRACT_PATH,
    build_stage_state_lifetime_contract,
    write_stage_state_lifetime_contract,
)


def main() -> int:
    try:
        value = build_stage_state_lifetime_contract(ROOT)
        write_stage_state_lifetime_contract(
            ROOT / CONTRACT_PATH, value
        )
    except Exception as error:
        print(
            f"stage state/lifetime generation failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "status": value["status"],
                "stage_count": value["ordered_config_plan"]["stage_count"],
                "edge_count": value["typed_tensor_dag"]["edge_count"],
                "logical_view_proven": value["view"][
                    "logical_zero_copy_proven"
                ],
                "physical_view_proven": value["view"][
                    "physical_zero_copy_proven"
                ],
                "n2n_selected": value["n2n"]["selected_n2n_config_count"],
                "contract_sha256": value["contract_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
