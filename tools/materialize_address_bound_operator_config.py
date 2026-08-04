from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.address_bound_config import (  # noqa: E402
    materialize_address_bound_config,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bind a strict operator config to one native withbaseaddr graph."
    )
    parser.add_argument("strict_materialization", type=Path)
    parser.add_argument("graph_withbaseaddr", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        manifest = materialize_address_bound_config(
            project_root=ROOT,
            strict_materialization_root=args.strict_materialization,
            graph_withbaseaddr=args.graph_withbaseaddr,
            output_root=args.output,
        )
    except Exception as error:
        print(f"address-bound config materialization failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "output": str(args.output),
                "config_sha256": manifest["bound_config"]["sha256"],
                "changed_address_count": len(manifest["changes"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
