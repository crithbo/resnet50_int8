from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_sa_remaining52_expansion import (  # noqa: E402
    build_remaining52_expansion,
    validate_remaining52_expansion,
)


OUTPUT = (
    ROOT
    / "contracts/operator_config/conv_sa_remaining52_expansion_v1.json"
)
VALIDATION = (
    ROOT
    / "artifacts/operator_config_validation/"
    "conv_sa_remaining52_expansion_v1.validation.json"
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    report = build_remaining52_expansion(ROOT)
    validation = validate_remaining52_expansion(ROOT, report)
    if not validation["valid"]:
        print(json.dumps(validation, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    _write(OUTPUT, report)
    _write(VALIDATION, validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
