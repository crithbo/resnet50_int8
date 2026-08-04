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
    OperatorConfigArtifactValidator,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently reconstruct and validate native operator-config artifacts."
    )
    parser.add_argument("config", type=Path, help="strict source operator JSON")
    parser.add_argument("artifact_dir", type=Path, help="directory containing mapping/bitstream artifacts")
    parser.add_argument(
        "mapping_evidence",
        type=Path,
        help="separate zero-penalty/cache/provenance evidence JSON",
    )
    parser.add_argument("--output", type=Path, help="optional validation report path")
    parser.add_argument(
        "--expected-encoder-commit",
        default=ACTIVE_ENCODER_COMMIT,
        help="pinned ndp-sim commit required by the evidence",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        evidence = json.loads(args.mapping_evidence.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"input error: {error}", file=sys.stderr)
        return 2
    if evidence.get("schema") != "operator-config-mapping-evidence-v2":
        print(
            "input error: operational validation requires operator-config-mapping-evidence-v2",
            file=sys.stderr,
        )
        return 2

    report = OperatorConfigArtifactValidator(
        expected_encoder_commit=args.expected_encoder_commit
    ).validate(
        config,
        args.artifact_dir,
        mapping_evidence=evidence,
        source=str(args.config.resolve()),
    )
    payload = report.to_dict()
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "valid": report.valid,
                "issue_count": len(report.issues),
                "first_error": payload["first_error"],
                "unpadded_bits": payload.get("facts", {}).get("mirror", {}).get("unpadded_bits"),
                "bit_range_count": payload.get("facts", {}).get("mirror", {}).get("bit_range_count"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
