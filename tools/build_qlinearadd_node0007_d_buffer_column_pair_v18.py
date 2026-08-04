from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.qlinearadd_node0007_d_buffer_column_pair_v18 import (
    CONFIG_REL,
    ROOT_REL,
    materialize_local_inputs,
    materialize_mapping_and_execplan,
)


def main() -> int:
    output = ROOT / ROOT_REL
    configs = ROOT / CONFIG_REL
    try:
        local = materialize_local_inputs(ROOT, output, configs)
        native = materialize_mapping_and_execplan(
            ROOT, output, configs, Path(sys.executable)
        )
    except Exception as error:
        print(f"QAdd node0007 D-buffer column-pair build failed: {error}")
        return 1
    receipt = {
        "schema": "qlinearadd-node0007-d-buffer-column-pair-build-v1",
        "status": "LOCAL_NATIVE_CHAIN_MATERIALIZED",
        "local_input_receipt": local,
        "native_chain_receipt": native,
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "config_numeric_analysis_repeated": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    path = output / "build_receipt.json"
    path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
