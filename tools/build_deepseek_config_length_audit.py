from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.deepseek_config_length_audit import (
    CONTRACT_PATH,
    build_deepseek_config_length_audit,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the cross-family DeepSeek config-length audit."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    return parser.parse_args()


def main() -> int:
    root = parse_args().project_root.resolve()
    payload = build_deepseek_config_length_audit(root)
    path = root / CONTRACT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(path)
    print(payload["contract_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
