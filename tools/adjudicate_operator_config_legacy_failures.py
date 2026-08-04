from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.operator_config_adjudication import (  # noqa: E402
    adjudicate_config,
    build_p0_baseline,
    sha256_file,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze P0 identity and prove whether known strict failures are native-bit-equivalent."
    )
    parser.add_argument(
        "--shadow-report",
        type=Path,
        default=ROOT / "artifacts/operator_config_validation/r3-shadow-active-jsons-20260723.json",
    )
    parser.add_argument(
        "--baseline-output",
        type=Path,
        default=ROOT / "artifacts/operator_config_validation/p0-baseline-20260723.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/operator_config_validation/p1-legacy-adjudication-20260723.json",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--heuristic-iterations", type=int, default=10_000)
    parser.add_argument("--heuristic-restarts", type=int, default=10)
    parser.add_argument(
        "--python",
        type=Path,
        default=ROOT / ".venv/Scripts/python.exe",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    report = json.loads(args.shadow_report.read_text(encoding="utf-8"))
    source_paths = sorted((ROOT / "ndp-sim/jsons").glob("*.json"))
    component_paths = [
        ROOT / "resnet50_pipeline/operator_config_validator.py",
        ROOT / "resnet50_pipeline/operator_config_adjudication.py",
        ROOT / "tools/validate_operator_configs.py",
        ROOT / "tools/adjudicate_operator_config_legacy_failures.py",
        ROOT / "tests/test_operator_config_validator.py",
        ROOT / "tests/test_operator_config_adjudication.py",
    ]
    baseline = build_p0_baseline(
        project_root=ROOT,
        ndp_sim_root=ROOT / "ndp-sim",
        config_paths=source_paths,
        shadow_report=args.shadow_report,
        component_paths=component_paths,
    )
    args.baseline_output.parent.mkdir(parents=True, exist_ok=True)
    args.baseline_output.write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    invalid = [item for item in report["reports"] if not item["valid"]]
    entries = []
    for index, item in enumerate(invalid, start=1):
        source = Path(item["source"])
        if not source.is_absolute():
            source = ROOT / source
        print(f"[{index}/{len(invalid)}] adjudicating {source.name}", flush=True)
        entries.append(
            adjudicate_config(
                source_path=source,
                ndp_sim_root=ROOT / "ndp-sim",
                python_executable=args.python,
                seed=args.seed,
                heuristic_iterations=args.heuristic_iterations,
                heuristic_restarts=args.heuristic_restarts,
            )
        )
    payload = {
        "schema": "operator-config-p1-legacy-adjudication-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "read_only_source_policy": True,
        "normalization_materialized": False,
        "seed": args.seed,
        "heuristic_iterations": args.heuristic_iterations,
        "heuristic_restarts": args.heuristic_restarts,
        "baseline": {
            "path": args.baseline_output.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(args.baseline_output),
        },
        "summary": {
            "files": len(entries),
            "normalized_strict_valid": sum(item["normalized_strict_valid"] for item in entries),
            "core_bit_equivalent": sum(
                item["native"]["bit_equivalence_proved"]
                for item in entries
            ),
            "native_field_equivalent": sum(
                item["native"]["field_encoding_equivalent"]
                for item in entries
            ),
            "full_bitstream_mapping_blocked": sum(
                item["classification"]["normalized_identity"]
                == "native-field-equivalent-mapping-blocked"
                for item in entries
            ),
            "zero_penalty_pairs": sum(
                item["native"]["zero_penalty_pair"]
                for item in entries
            ),
            "frozen_cache_fallback_pairs": sum(
                item["native"]["frozen_cache_fallback"] is not None
                for item in entries
            ),
            "frozen_cache_bit_equivalent_pairs": sum(
                bool(
                    item["native"]["frozen_cache_fallback"]
                    and item["native"]["frozen_cache_fallback"]["comparison"][
                        "all_core_artifacts_equal"
                    ]
                )
                for item in entries
            ),
            "direct_fallback_pairs": sum(
                item["native"]["direct_fallback"] is not None
                for item in entries
            ),
            "semantic_contract_blocked": sum(
                item["adjudication"]["normalization_decision"]
                == "blocked-missing-operator-padding-contract"
                for item in entries
            ),
            "normalization_approved": sum(
                item["adjudication"]["normalization_decision"].startswith("approved-")
                for item in entries
            ),
            "legacy_intentional_reject": sum(
                item["adjudication"]["legacy_source_identity"] == "intentional-reject"
                for item in entries
            ),
        },
        "entries": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary = payload["summary"]
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if (
        summary["files"] == summary["normalized_strict_valid"]
        == summary["core_bit_equivalent"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
