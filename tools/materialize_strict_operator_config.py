from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.strict_config_materialization import (  # noqa: E402
    materialize_strict_config,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize a root-owned strict config only after native changed-field "
            "equivalence and normalization adjudication pass."
        )
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--ndp-sim", type=Path, default=ROOT / "ndp-sim")
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument(
        "--operator-padding-contract",
        type=Path,
        help="required hash-bound semantic contract for explicit zero padding",
    )
    args = parser.parse_args()
    try:
        manifest = materialize_strict_config(
            project_root=ROOT,
            ndp_sim_root=args.ndp_sim,
            source_path=args.source,
            output_root=args.output,
            python_executable=args.python,
            expected_source_sha256=args.expected_source_sha256,
            operator_padding_contract_path=args.operator_padding_contract,
        )
    except Exception as error:
        print(f"strict config materialization failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "output": str(args.output),
                "normalized_sha256": manifest["normalized"]["sha256"],
                "normalization_decision": manifest["adjudication"][
                    "normalization_decision"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
