from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.network_dry_run import audit_network_candidates
from resnet50_pipeline.w4_evidence import (
    add_legacy16_cli_guard,
    annotate_legacy16_report,
    resolve_legacy16_output,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="[LEGACY16] Audit superseded physical edges, costs and lifetimes"
    )
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--output", type=Path)
    add_legacy16_cli_guard(parser)
    args = parser.parse_args()
    output = resolve_legacy16_output(args.project_root, args.output)
    catalog = json.loads(
        (args.project_root / "artifacts/w3/model_graph.json").read_text(
            encoding="utf-8"
        )
    )
    report = annotate_legacy16_report(audit_network_candidates(catalog))
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(encoded.encode("utf-8"))
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
