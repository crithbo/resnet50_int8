from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.deepseek_prefill_stage_producer import (
    CONTRACT_PATH,
    OUTPUT_PATH,
    build_prefill_stage_producer_contract,
    build_rule_normalized_prefill_stage,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the rule-normalized active DeepSeek prefill Stage graph."
        )
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()

    graph, _ = build_rule_normalized_prefill_stage(root)
    output = root / OUTPUT_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(graph, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    contract = build_prefill_stage_producer_contract(root)
    contract_path = root / CONTRACT_PATH
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)
    print(contract_path)
    print(contract["contract_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
