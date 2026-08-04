from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_gap_node0071_v24_signal_stub as base


ROOT_NAME = "r5_n71_gap_v25_hdl_scope_rulefix"
ZIP_SHA256 = (
    "51f66d9771fb2a951e5cc71a786b607b24492602f3f810c83a6e8d9a6aa907f3"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--bash",
        type=Path,
        default=Path(r"C:\Program Files\Git\bin\bash.exe"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base.ROOT_NAME = ROOT_NAME
    base.ZIP_SHA256 = ZIP_SHA256
    try:
        result = base.validate(
            args.target_zip.resolve(), args.bash.resolve()
        )
        result["schema"] = (
            "gap-node0071-v25-safe-signal-stub-revalidation-v1"
        )
    except Exception as error:
        result = {
            "schema": "gap-node0071-v25-safe-signal-stub-revalidation-v1",
            "status": "FAIL",
            "error": str(error),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
