from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.stage_config_backend import materialize_stage_candidate


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize one fail-closed, address-unbound stage config candidate."
    )
    parser.add_argument("request_id")
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--lowering-bundle",
        type=Path,
        default=ROOT / "contracts/resnet50_r5_lowering_bundle.json",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = materialize_stage_candidate(
        ROOT,
        lowering_bundle_path=args.lowering_bundle,
        request_id=args.request_id,
        output_root=args.output,
    )
    print(
        f"request={manifest['request_id']} status={manifest['status']} "
        f"manifest_sha256={manifest['manifest_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
