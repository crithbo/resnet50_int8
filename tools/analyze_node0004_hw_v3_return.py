from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.node0004_v3_return_analysis import (  # noqa: E402
    analyze_node0004_v3_return,
)


DEFAULT_RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_n4_hw_v3_obs_return.zip"
)
OUTPUT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-node0004-hw-v3-return-analysis/report.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--return-zip", type=Path, default=DEFAULT_RETURN)
    args = parser.parse_args()
    try:
        report = analyze_node0004_v3_return(
            args.project_root.resolve(), args.return_zip
        )
        output = args.project_root.resolve() / OUTPUT_REL
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
