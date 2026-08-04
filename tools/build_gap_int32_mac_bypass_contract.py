from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_int32_mac_bypass import (  # noqa: E402
    CONTRACT_PATH,
    build_contract,
    write_contract,
)
from resnet50_pipeline.hashing import sha256_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the local-only GAP int32_mac memory/semantic contract. "
            "No config, bitstream, RTL patch, or server package is generated."
        )
    )
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else (root / CONTRACT_PATH).resolve()
    )
    written = write_contract(
        root,
        output,
        overwrite=args.overwrite,
    )
    contract = build_contract(root)
    print(
        json.dumps(
            {
                "status": "local_contract_written",
                "candidate_release": contract["candidate_release"],
                "server_package_allowed": contract["server_package_allowed"],
                "output": str(written),
                "sha256": sha256_file(written),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
