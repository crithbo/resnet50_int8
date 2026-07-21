from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from resnet50_pipeline.hardware_server_trace import analyze_hardware_server_trace_zip  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze structural evidence in a hardware-server trace ZIP. This command does not "
            "perform the frozen P/D numeric comparison and therefore cannot by itself "
            "pass three-way."
        )
    )
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    output = args.output_root.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"output directory is not empty; refusing to mix evidence: {output}")
    output.mkdir(parents=True, exist_ok=True)
    report, extracted = analyze_hardware_server_trace_zip(
        args.archive,
        args.package,
        args.preflight,
    )
    for name, text in extracted.items():
        (output / name).write_text(text, encoding="utf-8")
    report_path = output / "comparison.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    runtime_summary = dict(report["runtime"])
    local_summary = runtime_summary.get("local_slice_execution")
    if isinstance(local_summary, dict) and isinstance(local_summary.get("slices"), list):
        local_summary = dict(local_summary)
        local_summary["slice_detail_count"] = len(local_summary.pop("slices"))
        local_summary["slice_details"] = "see comparison.json"
        runtime_summary["local_slice_execution"] = local_summary
    summary = {
        "status": report["status"],
        "comparison_verdict": report["comparison_verdict"],
        "output": str(report_path),
        "preload": {
            key: report["preload"][key]
            for key in (
                "probe_count",
                "matching_preload_write_count",
                "matching_mc_read_value_count",
                "strict_readback_status",
            )
        },
        "runtime": runtime_summary,
        "hardware_outputs": {
            key: report["hardware_outputs"][key]
            for key in (
                "status",
                "structural_evidence_status",
                "P_bank_write_transactions",
                "staged_D_bank_write_transactions",
                "incomplete_reasons",
            )
        },
        "numeric_hardware_comparison": report["numeric_hardware_comparison"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    numeric_status = report["numeric_hardware_comparison"]["status"]
    if (
        report["status"] == "passed"
        and report["comparison_verdict"] == "three_way_passed"
        and numeric_status == "passed"
    ):
        return 0
    return 1 if report["status"] == "returned_failed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
