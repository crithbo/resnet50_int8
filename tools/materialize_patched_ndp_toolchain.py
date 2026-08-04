from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.ndp_patch_toolchain import (  # noqa: E402
    materialize_patched_toolchain,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize the hash-bound ResNet50 ndp-sim patch toolchain."
    )
    parser.add_argument("output", type=Path)
    parser.add_argument("--ndp-sim", type=Path, default=ROOT / "ndp-sim")
    args = parser.parse_args()
    try:
        manifest = materialize_patched_toolchain(args.ndp_sim, args.output)
    except Exception as error:
        print(f"patched toolchain generation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
