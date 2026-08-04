from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.node0004_semantic_contract import (  # noqa: E402
    build_node0004_semantic_contract,
)


DEFAULT_GRAPH = (
    ROOT
    / "ndp-sim/model_execplan/output/node0004_accumulate_wave0_nopp_r1_graph"
    / "node0004_accumulate_wave0_nopp_r1_graph_withbaseaddr.json"
)
DEFAULT_MAPPING = (
    ROOT
    / "artifacts/operator_config_validation/r5-patched-mapping-evidence"
    / "node0004-accumulate-wave0-nopp-r1-strict-address-bound-seed42-v1"
)
DEFAULT_OUTPUT = ROOT / "contracts/node0004_accumulate_wave0_nopp_r1_semantic_contract.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the hash-bound candidate semantic contract for node-0004 nopp R1."
    )
    parser.add_argument("--graph-withbaseaddr", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--mapping-bundle", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        contract = build_node0004_semantic_contract(
            ROOT,
            graph_withbaseaddr=args.graph_withbaseaddr,
            mapping_bundle=args.mapping_bundle,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(contract, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as error:
        print(f"node-0004 semantic contract build failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "candidate_semantic_contract_built",
                "output": str(args.output),
                "graph_sha256": contract["graph_sha256"],
                "contract_sha256": contract["contract_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
