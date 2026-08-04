from __future__ import annotations

import json
from pathlib import Path

from resnet50_pipeline.deepseek_rope_validation import (
    CONTRACT_PATH,
    build_rope_blocker_contract,
)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    output = root / CONTRACT_PATH
    value = build_rope_blocker_contract(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(output)
    print(value["contract_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
