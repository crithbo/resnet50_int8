from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_serialized_one_product_local_e2 import (  # noqa: E402
    PATCHSET_REL,
    materialize_inputs,
)
from resnet50_pipeline.ndp_patch_toolchain import (  # noqa: E402
    CONV_SERIALIZED_PATCHSET_ID,
    build_patchset_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize the node0004 stock-SA serialized-product local E2 inputs."
    )
    parser.add_argument("--project-root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.project_root.resolve()
    try:
        result = materialize_inputs(root)
        patchset = build_patchset_manifest(
            root / "ndp-sim", patchset_id=CONV_SERIALIZED_PATCHSET_ID
        )
        patchset_path = root / PATCHSET_REL
        patchset_path.parent.mkdir(parents=True, exist_ok=True)
        patchset_path.write_text(
            json.dumps(patchset, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        result["patchset"] = str(patchset_path)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
