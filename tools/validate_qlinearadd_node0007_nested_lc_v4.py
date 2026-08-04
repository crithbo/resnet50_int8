from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.qlinearadd_node0007_nested_lc_v4_closure import (  # noqa: E402
    CONTRACT_REL,
    materialize_closure,
    validate_closure,
)


def main() -> int:
    materialize = "--materialize" in sys.argv[1:]
    report = (
        materialize_closure(ROOT) if materialize else validate_closure(ROOT)
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    if materialize and report["contract_path"] != CONTRACT_REL.as_posix():
        return 1
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
