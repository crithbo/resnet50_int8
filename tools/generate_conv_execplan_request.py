from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_execplan_transport import (
    build_conv_execplan_request,
    canonical_execplan_bytes,
)
from resnet50_pipeline.conv_instance import make_conv_target_request

def output_path(project_root: Path, node_id: str) -> Path:
    request = make_conv_target_request(project_root, node_id)
    return request.preflight_path.parent / "execplan_request.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build one content-addressed typed Conv execplan request; change only "
            "--node-id for the frozen first, E1, or E2 instance"
        )
    )
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    value = build_conv_execplan_request(ROOT, args.node_id)
    payload = canonical_execplan_bytes(value)
    path = (args.output or output_path(ROOT, args.node_id)).resolve()
    if args.check:
        if not path.is_file() or path.read_bytes() != payload:
            raise SystemExit(f"typed Conv execplan request differs: {path}")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
