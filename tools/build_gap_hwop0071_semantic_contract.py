from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_native_package import (  # noqa: E402
    MAPPING_REL,
    SEMANTIC_REL,
    build_gap_semantic_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the hash-bound GAP sum semantic contract.")
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--request-proof", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, default=ROOT / MAPPING_REL)
    parser.add_argument("--output", type=Path, default=ROOT / SEMANTIC_REL)
    args = parser.parse_args()
    paths = {
        key: value if value.is_absolute() else ROOT / value
        for key, value in {
            "graph": args.graph,
            "request_proof": args.request_proof,
            "mapping": args.mapping,
            "output": args.output,
        }.items()
    }
    if paths["output"].exists():
        print(f"refusing to overwrite semantic contract: {paths['output']}", file=sys.stderr)
        return 1
    try:
        value = build_gap_semantic_contract(
            ROOT,
            graph_withbaseaddr=paths["graph"],
            mapping_bundle=paths["mapping"],
            request_proof=paths["request_proof"],
        )
        paths["output"].parent.mkdir(parents=True, exist_ok=True)
        paths["output"].write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except Exception as error:
        print(f"GAP semantic contract generation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(paths["output"]), "contract_sha256": value["contract_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
