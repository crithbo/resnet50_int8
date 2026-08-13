from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_v12_minimal_runtime_chain as base


ROOT_NAME = "r5_n71_gap_v36_dbclk_rdready_diag"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--bash", type=Path, default=Path(r"C:\Program Files\Git\bin\bash.exe")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        base.ROOT_NAME = ROOT_NAME
        with zipfile.ZipFile(args.target_zip.resolve()) as archive:
            observer = archive.read(
                f"{ROOT_NAME}/tb_probe/native_return_observer.svh"
            )
        base.OBSERVER_SHA256 = hashlib.sha256(observer).hexdigest()
        result = base.validate(args.target_zip.resolve(), args.bash.resolve())
        result["schema"] = "gap-node0071-v35-runner-chain-validation-v1"
        result["path_budget_runtime_guard_present"] = True
        result["valid"] = (
            result.get("valid") is True
            and result.get("positive_compile_reached") is True
            and result.get("all_negative_controls_fail_closed") is True
        )
        exit_code = 0 if result["valid"] else 1
    except Exception as error:
        result = {
            "schema": "gap-node0071-v35-runner-chain-validation-v1",
            "valid": False,
            "error": str(error),
        }
        exit_code = 1
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
