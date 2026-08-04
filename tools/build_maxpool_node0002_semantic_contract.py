from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.maxpool_node0002_semantic_contract import (  # noqa: E402
    build_maxpool_node0002_semantic_contract,
)


DEFAULT_EVIDENCE = (
    ROOT
    / "artifacts/operator_config_validation/r5-patched-execplan-evidence/"
    "maxpool-node0002-guarded-wave0-v3"
)
DEFAULT_MAPPING = (
    ROOT
    / "artifacts/operator_config_validation/r5-patched-mapping-evidence/"
    "maxpool-node0002-guarded-address-bound-v2"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the hash-bound node-0002 guarded MaxPool semantic contract."
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=DEFAULT_EVIDENCE / "pipeline_output/graph_withbaseaddr.json",
    )
    parser.add_argument("--mapping-bundle", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "contracts/maxpool_node0002_guarded_wave0_semantic_contract.json",
    )
    args = parser.parse_args()
    try:
        contract = build_maxpool_node0002_semantic_contract(
            ROOT,
            graph_withbaseaddr=args.graph,
            mapping_bundle=args.mapping_bundle,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(contract, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as error:
        print(f"MaxPool semantic contract generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "candidate_semantic_contract_built",
                "output": str(args.output),
                "contract_sha256": contract["contract_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
