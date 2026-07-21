from __future__ import annotations

import json
from pathlib import Path

from resnet50_pipeline.conv_instance import audit_generated_conv_output_routes


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    report = audit_generated_conv_output_routes(ROOT)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
