from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.network_dry_run import audit_network_candidates


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit all W4 physical edges, profile costs and candidate lifetimes"
    )
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    catalog = json.loads(
        (args.project_root / "artifacts/w3/model_graph.json").read_text(
            encoding="utf-8"
        )
    )
    report = audit_network_candidates(catalog)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output
        if not output.is_absolute():
            output = args.project_root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
