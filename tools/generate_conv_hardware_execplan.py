from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from resnet50_pipeline.conv_execplan_hardware import (  # noqa: E402
    generate_conv_hardware_execplan,
    validate_conv_hardware_execplan_package,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_package_invariance_report(
    reference: Path, candidate: Path, report_path: Path
) -> dict[str, object]:
    reference = reference.resolve()
    candidate = candidate.resolve()
    reference_validation = validate_conv_hardware_execplan_package(reference)
    candidate_validation = validate_conv_hardware_execplan_package(candidate)
    reference_manifest_path = reference / "manifest.json"
    candidate_manifest_path = candidate / "manifest.json"
    reference_manifest_bytes = reference_manifest_path.read_bytes()
    candidate_manifest_bytes = candidate_manifest_path.read_bytes()
    reference_manifest = json.loads(reference_manifest_bytes.decode("utf-8"))
    candidate_manifest = json.loads(candidate_manifest_bytes.decode("utf-8"))

    identity_fields = {
        "axi4_4kb",
        "bitstream_bindings",
        "config_lengths_64bit_words",
        "files",
        "freeze_id",
        "freeze_manifest_sha256",
        "source_freeze_reference",
        "typed_request_sha256",
    }
    for key in sorted(set(reference_manifest) | set(candidate_manifest)):
        if key not in identity_fields and reference_manifest.get(
            key
        ) != candidate_manifest.get(key):
            raise ValueError(
                f"generated package runtime/numeric contract differs: {key}"
            )

    reference_axi = dict(reference_manifest.get("axi4_4kb", {}))
    candidate_axi = dict(candidate_manifest.get("axi4_4kb", {}))
    reference_axi.pop("report_sha256", None)
    candidate_axi.pop("report_sha256", None)
    if reference_axi != candidate_axi:
        raise ValueError("generated package AXI4 transport structure differs")

    def declared_files(manifest: dict[str, object]) -> dict[str, tuple[int, str]]:
        records = manifest.get("files")
        if not isinstance(records, list):
            raise ValueError("generated package declared file records are missing")
        result: dict[str, tuple[int, str]] = {}
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("generated package declared file record is malformed")
            path = record.get("path")
            size = record.get("size_bytes")
            sha256 = record.get("sha256")
            if (
                not isinstance(path, str)
                or not isinstance(size, int)
                or not isinstance(sha256, str)
                or path in result
            ):
                raise ValueError("generated package declared file record is malformed")
            result[path] = (size, sha256)
        return result

    reference_files = declared_files(reference_manifest)
    candidate_files = declared_files(candidate_manifest)
    if set(reference_files) != set(candidate_files):
        raise ValueError("generated package declared file exact-set differs")
    changed_paths = sorted(
        path
        for path in reference_files
        if reference_files[path] != candidate_files[path]
    )

    allowed_identity_paths = {
        "axi4_4kb_report.json",
        "Bank_data/slice00_Bank00_data.txt",
        "install/cfg_pkg/conv_1x1_real_bitstream_128b.bin",
        "install/execplan.txt",
        "instructions_explained.txt",
        "runner_contract.json",
        "source/execplan_request.json",
        "source/freeze_manifest.json",
    }
    unexpected_changed_paths = [
        path
        for path in changed_paths
        if path not in allowed_identity_paths
        and not path.startswith("install/execplan.txt.axi4-")
    ]
    if unexpected_changed_paths:
        raise ValueError(
            "generated package numerical file identity differs: "
            + ", ".join(unexpected_changed_paths)
        )

    numeric_paths = sorted(
        path
        for path in candidate_files
        if path.startswith("install/data/")
        or path.startswith("install/runtime_scratch/")
        or path
        in {
            "dump_contract.json",
            "sca_cfg.json",
            "sca_cfg_D.json",
            "source/address_table.json",
        }
    )
    if not numeric_paths or any(
        reference_files[path] != candidate_files[path] for path in numeric_paths
    ):
        raise ValueError("generated package numeric payload identity differs")

    axi_record = candidate_manifest.get("axi4_4kb", {})
    report: dict[str, object] = {
        "schema_version": "resnet50-package-numeric-invariance-0.3",
        "status": "numeric_payload_and_runtime_contract_preserved_with_new_hardware_identity",
        "comparison_policy": (
            "authoritative reference and candidate package byte validation, then "
            "exact numerical payload/runtime comparison while permitting only the "
            "declared accumulate-config, bitstream, execplan and provenance identity changes"
        ),
        "reference_package": str(reference),
        "candidate_package": str(candidate),
        "reference_validation_status": reference_validation.get("status"),
        "candidate_validation_status": candidate_validation.get("status"),
        "reference_manifest_sha256": _sha256(reference_manifest_path),
        "candidate_manifest_sha256": _sha256(candidate_manifest_path),
        "reference_freeze_id": reference_manifest.get("freeze_id"),
        "candidate_freeze_id": candidate_manifest.get("freeze_id"),
        "reference_typed_request_sha256": reference_manifest.get(
            "typed_request_sha256"
        ),
        "candidate_typed_request_sha256": candidate_manifest.get(
            "typed_request_sha256"
        ),
        "runtime_operator_count": candidate_manifest.get("runtime_operator_count"),
        "exec_128bit_line_count": candidate_manifest.get("exec_128bit_line_count"),
        "bank_data_file_count": candidate_manifest.get("bank_data_file_count"),
        "declared_file_count": len(candidate_manifest.get("files", [])),
        "numeric_file_count": len(numeric_paths),
        "numeric_file_identity_sha256": hashlib.sha256(
            json.dumps(
                [(path, candidate_files[path]) for path in numeric_paths],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "hardware_identity_changed_paths": changed_paths,
        "axi4_4kb": axi_record,
        "numeric_contracts": [
            "typed input/constant payloads",
            "runtime scratch initialization",
            "runtime_sequence/stage/mask/barrier",
            "SCA/SCA_D transport",
            "golden/readback dump contract",
            "AXI4 4-KiB transport structure",
        ],
    }
    report_path = report_path.resolve()
    if report_path.exists():
        raise FileExistsError(f"refusing to replace invariance report: {report_path}")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a typed Conv model_execplan/Bank_data hardware package."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--node-id")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--freeze-root",
        type=Path,
        help="Override the node-bound hardware_freeze directory.",
    )
    parser.add_argument(
        "--execplan-request",
        type=Path,
        help="Override the typed execplan request, for example the versioned v4 request.",
    )
    parser.add_argument(
        "--legacy-fixed-pair-observer",
        action="store_true",
        help=(
            "Reorder independent requant slice groups and set Repeat_Num for the "
            "immutable server TB that waits slice0-start then slice1-finish."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate an already generated package without rewriting it.",
    )
    parser.add_argument(
        "--full-report",
        action="store_true",
        help="Print the complete package manifest instead of a compact summary.",
    )
    parser.add_argument(
        "--compare-package",
        type=Path,
        help="Approved package whose exact numerical manifest identity must be preserved.",
    )
    parser.add_argument(
        "--invariance-report",
        type=Path,
        help="New machine-readable report path used with --compare-package.",
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    if args.output is None:
        parser.error("--output is required for both generation and --check")
    output = args.output.resolve()
    if (args.compare_package is None) != (args.invariance_report is None):
        parser.error("--compare-package and --invariance-report must be used together")
    if args.invariance_report is not None and args.invariance_report.exists():
        parser.error(
            f"refusing to replace an existing invariance report: {args.invariance_report}"
        )
    if args.check:
        report = validate_conv_hardware_execplan_package(output)
    else:
        missing = [
            flag
            for flag, value in (
                ("--node-id", args.node_id),
                ("--freeze-root", args.freeze_root),
                ("--execplan-request", args.execplan_request),
            )
            if value is None
        ]
        if missing:
            parser.error(
                "formal generation requires explicit " + ", ".join(missing)
            )
        report = generate_conv_hardware_execplan(
            root,
            output,
            node_id=args.node_id,
            freeze_root=args.freeze_root,
            execplan_request_path=args.execplan_request,
            legacy_fixed_pair_observer=args.legacy_fixed_pair_observer,
        )
    if args.compare_package is not None:
        invariance = _write_package_invariance_report(
            args.compare_package, output, args.invariance_report
        )
    else:
        invariance = None
    if args.full_report:
        printable = report
    else:
        printable = {
            key: report[key]
            for key in (
                "status",
                "node_id",
                "runtime_operator_count",
                "exec_128bit_line_count",
                "bank_data_file_count",
            )
            if key in report
        }
        printable["output"] = str(output)
        if invariance is not None:
            printable["numeric_invariance_status"] = invariance["status"]
    print(json.dumps(printable, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
