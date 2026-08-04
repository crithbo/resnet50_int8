from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.deepseek_gemm_numeric import (
    CONTRACT_PATH,
    build_gemm_numeric_contract,
    materialize_gemm_numeric_payload,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic GEMM local numeric E2 payload."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()
    materialize_gemm_numeric_payload(root)
    contract = build_gemm_numeric_contract(root)
    output = root / CONTRACT_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)
    print(contract["contract_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
