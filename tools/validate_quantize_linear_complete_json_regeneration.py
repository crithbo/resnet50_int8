#!/usr/bin/env python3
"""Validate QuantizeLinear full-family complete-JSON regeneration artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.quantize_linear_complete_json_regeneration import (
    ARTIFACT_REL,
    QuantizeCompleteJsonError,
    sha256_file,
    validate_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / ARTIFACT_REL)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        validation = validate_artifacts(ROOT, args.output_dir.resolve())
    except QuantizeCompleteJsonError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2))
        return 1
    report_path = args.report or (args.output_dir / "validation_report.json")
    shared_reports = [
        args.output_dir
        / "public_gate/hwop-0000-00/shared_validation_report.json",
        args.output_dir
        / "public_gate/hwop-0074-00/shared_validation_report.json",
        args.output_dir / "family_set_audit_report.json",
    ]
    validation["shared_report_receipts"] = [
        {
            "path": path.resolve().relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in shared_reports
        if path.is_file()
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
