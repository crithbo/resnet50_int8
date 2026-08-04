from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_sa_remaining52_expansion import (  # noqa: E402
    validate_remaining52_expansion,
)


REPORT = (
    ROOT
    / "contracts/operator_config/conv_sa_remaining52_expansion_v1.json"
)


def main() -> int:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    validation = validate_remaining52_expansion(ROOT, report)
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if validation["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
