#!/usr/bin/env python3
"""Validate one DeepSeek native ring-GEMM control return and its zero output."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_execplan_hardware import (  # noqa: E402
    ConvHardwareExecplanError,
    _parse_runtime_completion_console,
    _sca_d_readback_contract,
    _validate_readback_region_tree,
    _validate_returned_config_file_set,
)
from resnet50_pipeline.native_json_ring_gemm_package import (  # noqa: E402
    validate_native_json_ring_gemm_package,
)
from resnet50_pipeline.native_json_ring_gemm_package_v2 import (  # noqa: E402
    PACKAGE_KIND as PACKAGE_KIND_V2,
    validate_native_json_ring_gemm_package_v2,
)
from tools.analyze_native_json_maxpool_return import (  # noqa: E402
    _expected_return_config_hashes,
    _integer,
    _json,
    _safe_extract,
    _sha256_file,
    _validate_return_exact_set,
)


def _validate_success_metadata(
    root: Path,
    package: Path,
    manifest: Mapping[str, Any],
    runner: Mapping[str, Any],
    approved_identity_path: Path,
    approved_identity: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    runtime_stage_count = int(manifest["runtime_operator_count"])
    repeat_num = int(manifest["testbench_observer"]["repeat_num"])
    region_count = int(manifest["semantic_dump_region_count"])
    preload_transfer_count = int(manifest["preload_transfer_segment_count"])
    metadata = _json(root / "run_metadata.json")
    run_id = str(metadata.get("server_run_id"))
    if run_id not in {"run1", "run2"}:
        raise ConvHardwareExecplanError("server run ID must be run1 or run2")
    for key in runner["required_return_metadata"]:
        if metadata.get(key) in (None, "", [], {}):
            raise ConvHardwareExecplanError(f"required return metadata is missing: {key}")
    for key in (
        "exit_status",
        "process_exit_status",
        "make_exit_status",
        "tee_exit_status",
        "phase_watchdog_exit_status",
        "raw_phase_watchdog_exit_status",
        "simulator_exit_status",
    ):
        if _integer(metadata, key) != 0:
            raise ConvHardwareExecplanError(f"server success status differs: {key}")
    expected_strings = {
        "execution_environment": "rtl_simulation",
        "termination_kind": "natural_process_exit",
        "preflight_status": "passed",
        "timeout_status": "not_timed_out",
        "phase_timeout_status": "not_timed_out",
        "phase_failure_reason": "none",
        "stage_marker_status": "passed",
        "all_stages_marker_status": "passed",
        "readback_region_contract_status": "passed",
        "make_archive_policy": "runner_no_archive_target_v1",
        "return_archive_policy": "bounded_exact_set_allowlist_v2",
        "testbench_observer_mode": "fixed_slice0_start_slice1_finish",
    }
    for key, expected in expected_strings.items():
        if metadata.get(key) != expected:
            raise ConvHardwareExecplanError(f"server completion metadata differs: {key}")
    expected_integers = {
        "completed_runtime_stage_count": runtime_stage_count,
        "expected_runtime_stage_count": runtime_stage_count,
        "expected_testbench_repeat_num": repeat_num,
        "observed_slice0_start_count": repeat_num,
        "observed_slice1_finish_count": repeat_num,
        "reserved_clock_force_marker_count": 1,
        "reserved_clock_failure_marker_count": 0,
        "returned_region_count": region_count,
        "expected_region_count": region_count,
    }
    for key, expected in expected_integers.items():
        if _integer(metadata, key) != expected:
            raise ConvHardwareExecplanError(f"server count differs: {key}")
    if (
        metadata.get("simulator_exit_status_observed") is not True
        or metadata.get("phase_watchdog_done") is not True
        or _integer(metadata, "phase_stall_seconds") != 0
    ):
        raise ConvHardwareExecplanError("server completion/watchdog evidence differs")
    expected_hashes = {
        "freeze_id": str(manifest["freeze_id"]),
        "freeze_manifest_sha256": str(manifest["freeze_manifest_sha256"]),
        "package_manifest_sha256": _sha256_file(package / "manifest.json"),
        "runtime_identity_sha256": _sha256_file(approved_identity_path),
        "sca_cfg_sha256": str(approved_identity["relocated_sca_cfg"]["sha256"]),
        "sca_cfg_D_sha256": str(approved_identity["relocated_sca_cfg_D"]["sha256"]),
        "readback_contract_sha256": str(approved_identity["readback_region_contract"]["sha256"]),
    }
    for key, expected in expected_hashes.items():
        if metadata.get(key) != expected:
            raise ConvHardwareExecplanError(f"server identity differs: {key}")
    preload = _json(root / "preload_readback_report.json")
    if preload != {
        "status": "passed",
        "expected_transfer_count": preload_transfer_count,
        "passed_transfer_count": preload_transfer_count,
    }:
        raise ConvHardwareExecplanError("preload/readback report differs")
    return run_id, metadata


def analyze_return(
    package_root: Path,
    return_root: Path,
    approved_runtime_identity_path: Path,
    *,
    archive: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    package = package_root.resolve()
    root = return_root.resolve()
    approved_path = approved_runtime_identity_path.resolve()
    manifest = _json(package / "manifest.json")
    package_kind = manifest.get("kind")
    if package_kind == PACKAGE_KIND_V2:
        validate_native_json_ring_gemm_package_v2(package)
    else:
        validate_native_json_ring_gemm_package(package)
    runner = _json(package / "runner_contract.json")
    approved = _json(approved_path)
    actual_files = _validate_return_exact_set(root)
    _validate_returned_config_file_set(actual_files, approved)
    for relative, expected_hash in _expected_return_config_hashes(package, approved).items():
        if relative not in actual_files or _sha256_file(actual_files[relative]) != expected_hash:
            raise ConvHardwareExecplanError(f"returned approved config differs: {relative}")
    run_id, metadata = _validate_success_metadata(
        root, package, manifest, runner, approved_path, approved
    )
    console_files = list((root / "run_sim_results").glob("*_console.log"))
    if len(console_files) != 1:
        raise ConvHardwareExecplanError("successful return must contain one console log")
    console = _parse_runtime_completion_console(
        console_files[0],
        expected_preload_transfer_count=int(manifest["preload_transfer_segment_count"]),
        expected_slice_masks=[str(item["slice_mask"]) for item in manifest["runtime_operators"]],
        expected_simulator_exit_status=0,
        observer_contract=runner["execution"]["completion_gate"]["testbench_observer"],
    )
    sca_d = _json(actual_files[PurePosixPath("config/sca_cfg_D.json")])
    expected_tree = _sca_d_readback_contract(sca_d, label="returned SCA_D")
    snapshot = _validate_readback_region_tree(root, expected_tree)
    expected_region_count = int(manifest["semantic_dump_region_count"])
    if len(snapshot) != expected_region_count:
        raise ConvHardwareExecplanError("ring-GEMM return region count differs")
    output_regions = []
    combined_payload = bytearray()
    mismatch_count = 0
    for region_path, record in sorted(snapshot.items()):
        payload = bytes(record["payload"])
        region_mismatch_count = sum(byte != 0 for byte in payload)
        if len(payload) != 4096 or region_mismatch_count:
            raise ConvHardwareExecplanError(
                "zero-input ring-GEMM output differs: "
                f"region={region_path}, size={len(payload)}, "
                f"nonzero={region_mismatch_count}"
            )
        combined_payload.extend(payload)
        mismatch_count += region_mismatch_count
        output_regions.append(
            {
                "path": str(region_path),
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "nonzero_byte_count": region_mismatch_count,
            }
        )
    return {
        "schema_version": (
            "deepseek-native-json-ring-gemm-return-analysis-0.2"
            if package_kind == PACKAGE_KIND_V2
            else "deepseek-native-json-ring-gemm-return-analysis-0.1"
        ),
        "status": "passed_single_server_return",
        "server_run_id": run_id,
        "archive": dict(archive or {}),
        "package_manifest_sha256": _sha256_file(package / "manifest.json"),
        "runtime_identity_sha256": _sha256_file(approved_path),
        "return_file_count": len(actual_files),
        "console_validation": console,
        "output_region_count": len(output_regions),
        "output_regions": output_regions,
        "output_size_bytes": len(combined_payload),
        "output_sha256": hashlib.sha256(combined_payload).hexdigest(),
        "nonzero_byte_count": mismatch_count,
        "hardware_control_scope": "upstream hardware-completed DeepSeek M64N128K16 ring-GEMM JSON",
        "stored_hardware_numeric_bit_exact_evidence": False,
        "simulator_version": metadata["simulator_version"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate one DeepSeek native ring-GEMM server return ZIP")
    parser.add_argument("zip", type=Path)
    parser.add_argument(
        "--package",
        type=Path,
        default=Path("artifacts/w5/deepseek_ring_gemm_control/v1/hardware_execplan_package"),
    )
    parser.add_argument(
        "--runtime-identity",
        type=Path,
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    package = args.package if args.package.is_absolute() else ROOT / args.package
    if args.runtime_identity is None:
        package_kind = _json(package / "manifest.json").get("kind")
        identity = ROOT / (
            "artifacts/w5/dg/dg3_overlay/NDP_copy01/install/cfg_pkg/"
            "hwop-deepseek-ring-dg3/metadata/runtime_identity.json"
            if package_kind == PACKAGE_KIND_V2
            else "artifacts/w5/dg/dg1_overlay/NDP_copy01/install/cfg_pkg/"
            "hwop-deepseek-ring-dg1/metadata/runtime_identity.json"
        )
    else:
        identity = (
            args.runtime_identity
            if args.runtime_identity.is_absolute()
            else ROOT / args.runtime_identity
        )
    with tempfile.TemporaryDirectory(prefix="native-ring-gemm-return-") as temp_text:
        return_root, archive = _safe_extract(args.zip, Path(temp_text) / "extract")
        report = analyze_return(package, return_root, identity, archive=archive)
    payload = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if args.output is not None:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        if output.exists():
            raise ConvHardwareExecplanError(f"refusing to overwrite report: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
    print(payload.decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
