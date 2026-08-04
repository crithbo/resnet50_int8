from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_stem_serialized_materialization_gate import (  # noqa: E402
    build_stem_materialization_gate,
    validate_stem_materialization_gate,
)


CONTRACT = (
    ROOT
    / "contracts/operator_config/conv_stem_serialized_materialization_gate_v1.json"
)
VALIDATION = (
    ROOT
    / "artifacts/operator_config_validation/"
    "conv_stem_serialized_materialization_gate_v1.validation.json"
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    contract = build_stem_materialization_gate(ROOT)
    validation = validate_stem_materialization_gate(ROOT, contract)
    if not validation["valid"]:
        return 1
    _write(CONTRACT, contract)
    _write(VALIDATION, validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
