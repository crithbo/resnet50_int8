from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.operator_config_artifact_validator import (  # noqa: E402
    ACTIVE_ENCODER_COMMIT,
)
from resnet50_pipeline.operator_config_evidence_bundle import (  # noqa: E402
    create_mapping_evidence_bundle,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a portable, independently validated native mapping evidence bundle."
    )
    parser.add_argument("config", type=Path, help="strict source operator JSON")
    parser.add_argument("output_dir", type=Path, help="new bundle directory; must not already exist")
    parser.add_argument("--ndp-sim-root", type=Path, default=ROOT / "ndp-sim")
    parser.add_argument("--python", type=Path, default=ROOT / ".venv/Scripts/python.exe")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--heuristic-iterations", type=int, default=10_000)
    parser.add_argument("--heuristic-restarts", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--expected-encoder-commit", default=ACTIVE_ENCODER_COMMIT)
    parser.add_argument(
        "--patchset-manifest",
        type=Path,
        help="optional locked project patchset applied only to the disposable tool copy",
    )
    parser.add_argument(
        "--frozen-mapping-cache",
        type=Path,
        help=(
            "optional portable native cache candidate; accepted only when the native "
            "mapper loads it and recomputes exact zero constraint cost"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    try:
        result = create_mapping_evidence_bundle(
            ndp_sim_root=args.ndp_sim_root,
            config_path=args.config,
            output_dir=args.output_dir,
            python_executable=args.python,
            seed=args.seed,
            heuristic_iterations=args.heuristic_iterations,
            heuristic_restarts=args.heuristic_restarts,
            expected_encoder_commit=args.expected_encoder_commit,
            timeout_seconds=args.timeout_seconds,
            patchset_manifest_path=args.patchset_manifest,
            frozen_cache_path=args.frozen_mapping_cache,
        )
    except Exception as error:
        print(f"evidence generation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "valid": result.valid,
                "output_dir": str(result.output_dir),
                "penalty": result.penalty,
                "mapping_review_sha256": result.mapping_review_sha256,
                "bundle_tree_sha256": result.bundle_tree_sha256,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
