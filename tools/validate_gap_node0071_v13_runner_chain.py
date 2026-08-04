from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_v12_minimal_runtime_chain as base


ROOT_NAME = "r5_n71_gap_v13_buffer_to_ga_diag"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument("--root-name", default=ROOT_NAME)
    parser.add_argument(
        "--bash",
        type=Path,
        default=Path(r"C:\Program Files\Git\bin\bash.exe"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    target = args.target_zip.resolve()
    try:
        import zipfile

        with zipfile.ZipFile(target) as archive:
            manifest = json.loads(
                archive.read(
                    f"{args.root_name}/TEST_PACKAGE_MANIFEST.json"
                ).decode("utf-8")
            )
        observer_relative = manifest["package_local_observer"][
            "relative_path"
        ]
        observer_sha = manifest["files"][observer_relative]["sha256"]
        base.ROOT_NAME = args.root_name
        base.OBSERVER_SHA256 = observer_sha
        result = base.validate(target, args.bash.resolve())
        result["schema"] = (
            "gap-node0071-buffer-to-ga-runner-chain-validation-v13"
        )
        result["fresh_extract_root"] = args.root_name
        result["observer_sha256"] = observer_sha
        if args.output:
            args.output.write_text(
                json.dumps(
                    result, indent=2, ensure_ascii=False, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
    except Exception as error:
        print(f"v13 runner validation failed: {error}")
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
