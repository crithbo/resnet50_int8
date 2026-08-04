from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.qlinearadd_node0007_full_e2 import (  # noqa: E402
    CONFIG_REL,
    ROOT_REL,
    materialize_local_inputs,
    materialize_mapping_and_execplan,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(sys.executable),
        help="Python executable used by isolated native mapper/planner runs",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="materialize strict configs/graph and config-bound simulator only",
    )
    parser.add_argument(
        "--native-only",
        action="store_true",
        help="consume already-materialized local inputs and build mapping/execplan",
    )
    args = parser.parse_args()
    if args.local_only and args.native_only:
        parser.error("--local-only and --native-only are mutually exclusive")
    result: dict[str, object] = {}
    if not args.native_only:
        result["local"] = materialize_local_inputs(
            ROOT, ROOT / ROOT_REL, ROOT / CONFIG_REL
        )
    if not args.local_only:
        result["native"] = materialize_mapping_and_execplan(
            ROOT, ROOT / ROOT_REL, ROOT / CONFIG_REL, args.python
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
