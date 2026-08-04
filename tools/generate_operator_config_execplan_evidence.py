from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.operator_config_execplan_evidence import (  # noqa: E402
    create_execplan_evidence_bundle,
)


def _bindings(values: list[str], option: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"{option} must use OP_ID=PATH, got {value!r}")
        op_id, raw_path = value.split("=", 1)
        if not op_id or not raw_path or op_id in result:
            raise ValueError(f"invalid or duplicate {option} binding: {value!r}")
        result[op_id] = Path(raw_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a double-run native execplan evidence bundle from validated mappings."
    )
    parser.add_argument("graph", type=Path, help="native model_execplan graph JSON")
    parser.add_argument("output", type=Path, help="new evidence output directory")
    parser.add_argument(
        "--mapping-bundle",
        action="append",
        default=[],
        metavar="OP_ID=PATH",
        help="validated zero-penalty mapping bundle; repeat once per graph operator",
    )
    parser.add_argument("--ndp-sim", type=Path, default=ROOT / "ndp-sim")
    parser.add_argument(
        "--semantic-contract",
        type=Path,
        help="optional hash-bound qparam/layout/stage/tail/provenance contract",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=ROOT / ".venv" / "Scripts" / "python.exe",
    )
    parser.add_argument(
        "--patchset-manifest",
        type=Path,
        help="optional locked project patchset; mapping bundles must bind the same identity",
    )
    args = parser.parse_args()
    try:
        mappings = _bindings(args.mapping_bundle, "--mapping-bundle")
        result = create_execplan_evidence_bundle(
            ndp_sim_root=args.ndp_sim,
            graph_path=args.graph,
            mapping_bundles=mappings,
            output_dir=args.output,
            python_executable=args.python,
            semantic_contract_path=args.semantic_contract,
            patchset_manifest_path=args.patchset_manifest,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "schema": "operator-config-execplan-evidence-cli-result-v1",
                "valid": result.valid,
                "output_dir": str(result.output_dir),
                "manifest": str(result.manifest_path),
                "validation_report": str(result.validation_report_path),
                "execplan_sha256": result.execplan_sha256,
                "deterministic_file_count": result.deterministic_file_count,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
