#!/usr/bin/env python3
"""Build or rebind the local-only minimal two-stage lifecycle E2 evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.minimal_two_stage_lifecycle import (  # noqa: E402
    build_artifact_manifest,
    build_semantic_contract,
    run_local_e2,
)


ARTIFACT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-minimal-two-stage-lifecycle-e2-v1"
)
CONTRACT = (
    ROOT / "contracts/operator_config/minimal_two_stage_lifecycle_v1.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-contract-only",
        action="store_true",
        help="Rebind the checked-in contract to an already validated artifact.",
    )
    args = parser.parse_args()
    try:
        if args.refresh_contract_only:
            artifact_manifest = build_artifact_manifest(ARTIFACT)
            (ARTIFACT / "manifest.json").write_text(
                json.dumps(
                    artifact_manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            value = build_semantic_contract(ROOT, ARTIFACT)
            CONTRACT.parent.mkdir(parents=True, exist_ok=True)
            CONTRACT.write_text(
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            result = {
                "status": value["status"],
                "contract_path": str(CONTRACT),
                "contract_sha256": value["contract_sha256"],
                "artifact_rebuilt": False,
            }
        else:
            result = run_local_e2(ROOT)
    except Exception as error:
        print(f"minimal two-stage lifecycle build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
