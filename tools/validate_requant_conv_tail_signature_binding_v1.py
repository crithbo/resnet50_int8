from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.requant_conv_tail_signature_binding_v1 import (  # noqa: E402
    CONTRACT_REL,
    load_json,
    validate_manifest,
)


def main() -> None:
    value = load_json(CONTRACT_REL)
    validation = validate_manifest(value)
    print(
        json.dumps(
            validation,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    if not validation["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

