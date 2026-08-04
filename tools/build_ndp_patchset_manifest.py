from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.ndp_patch_toolchain import (  # noqa: E402
    CONV_PATCHSET_ID,
    GAP_PATCHSET_ID,
    NODE0004_ASSUMED_HW_PATCHSET_ID,
    PATCHSET_ID,
    REQUANT_PATCHSET_ID,
    build_patchset_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a hash-bound NDP-Sim patchset manifest.")
    parser.add_argument(
        "--patchset-id",
        choices=(
            PATCHSET_ID,
            GAP_PATCHSET_ID,
            REQUANT_PATCHSET_ID,
            CONV_PATCHSET_ID,
            NODE0004_ASSUMED_HW_PATCHSET_ID,
        ),
        default=PATCHSET_ID,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        print(f"refusing to overwrite patchset manifest: {output}", file=sys.stderr)
        return 1
    try:
        value = build_patchset_manifest(
            ROOT / "ndp-sim",
            patchset_id=args.patchset_id,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except Exception as error:
        print(f"patchset manifest generation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(output), "patchset_id": value["patchset_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
