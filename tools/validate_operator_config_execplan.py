from __future__ import annotations

import argparse
import json
from pathlib import Path

from resnet50_pipeline.operator_config_execplan_validator import (
    OperatorConfigExecPlanValidator,
)


def _pairs(values: list[str], *, label: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"{label} must use OP_ID=PATH: {value!r}")
        op_id, raw_path = value.split("=", 1)
        if not op_id or not raw_path or op_id in result:
            raise ValueError(f"invalid or duplicate {label}: {value!r}")
        result[op_id] = Path(raw_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bind native Load_Config commands to strict JSON/mapping/bitstream state"
    )
    parser.add_argument("graph_root", type=Path)
    parser.add_argument("graph", type=Path)
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="OP_ID=PATH",
        help="explicit source JSON for one graph operator",
    )
    parser.add_argument(
        "--mapping-evidence",
        action="append",
        default=[],
        metavar="OP_ID=PATH",
        help="portable mapping evidence JSON for one graph operator",
    )
    parser.add_argument(
        "--artifact-dir",
        action="append",
        default=[],
        metavar="OP_ID=PATH",
        help="override graph_root/config/OP_ID artifact directory",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        sources = _pairs(args.source, label="--source")
        evidence_paths = _pairs(args.mapping_evidence, label="--mapping-evidence")
        artifact_dirs = _pairs(args.artifact_dir, label="--artifact-dir")
        evidence = {
            op_id: json.loads(path.read_text(encoding="utf-8"))
            for op_id, path in evidence_paths.items()
        }
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    report = OperatorConfigExecPlanValidator().validate(
        args.graph_root,
        graph_path=args.graph,
        source_configs=sources,
        mapping_evidence=evidence,
        artifact_dirs=artifact_dirs,
    )
    payload = report.to_dict()
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output is None:
        print(serialized, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    return 0 if report.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
