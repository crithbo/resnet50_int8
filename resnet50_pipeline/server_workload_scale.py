from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .hashing import sha256_file


REQUANT_PACKAGE = (
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "requant_node0001_e4_stockrtl_v2"
)
DEQUANT_PACKAGE = (
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "dequant_node0077_stockrtl_e4_onecmd_v1"
)
REQUANT_PARTIAL_ANALYSIS = (
    "server_returns/requant_node0001_e4_v2_partial_12_analysis_20260725.json"
)


class ServerWorkloadScaleError(ValueError):
    pass


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ServerWorkloadScaleError(f"JSON root must be an object: {path}")
    return value


def _manifest_bound_file(
    package: Path, manifest: Mapping[str, Any], relative: str
) -> Path:
    path = package / relative
    files = manifest.get("files")
    record = files.get(relative) if isinstance(files, Mapping) else None
    if (
        not isinstance(record, Mapping)
        or not path.is_file()
        or record.get("size_bytes") != path.stat().st_size
        or record.get("sha256") != sha256_file(path)
    ):
        raise ServerWorkloadScaleError(
            f"package file identity differs: {package.name}/{relative}"
        )
    return path


def _nonempty_line_count(path: Path) -> int:
    return sum(
        bool(line.strip())
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def _sca_file_entry_count(sca: Mapping[str, Any]) -> int:
    return sum(
        isinstance(value, Mapping) and isinstance(value.get("path"), str)
        for value in sca.values()
    )


def _sca_d_line_count(sca_d: Mapping[str, Any]) -> int:
    lengths = [
        value.get("length")
        for value in sca_d.values()
        if isinstance(value, Mapping)
    ]
    if len(lengths) != len(sca_d) or any(
        not isinstance(length, int) or length < 0 for length in lengths
    ):
        raise ServerWorkloadScaleError("SCA_D length fields differ")
    return sum(lengths)


def build_requant_v2_workload_scale(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    requant_package = root / REQUANT_PACKAGE
    dequant_package = root / DEQUANT_PACKAGE
    requant_manifest = _load_object(
        requant_package / "TEST_PACKAGE_MANIFEST.json"
    )
    dequant_manifest = _load_object(
        dequant_package / "TEST_PACKAGE_MANIFEST.json"
    )

    requant_sca_path = _manifest_bound_file(
        requant_package, requant_manifest, "workload/runtime/sca_cfg.json"
    )
    requant_sca_d_path = _manifest_bound_file(
        requant_package, requant_manifest, "workload/runtime/sca_cfg_D.json"
    )
    requant_execplan_path = _manifest_bound_file(
        requant_package,
        requant_manifest,
        "workload/runtime/payloads/execplan.txt",
    )
    requant_input_path = _manifest_bound_file(
        requant_package,
        requant_manifest,
        "workload/runtime/compact/input_nchw_int32.raw.xz",
    )
    requant_runner_path = _manifest_bound_file(
        requant_package, requant_manifest, "PREPARE_AND_RUN.sh"
    )
    requant_sca = _load_object(requant_sca_path)
    requant_sca_d = _load_object(requant_sca_d_path)

    compact_input = requant_manifest.get("compact_data", {}).get("input")
    input_file_record = requant_manifest.get("files", {}).get(
        "workload/runtime/compact/input_nchw_int32.raw.xz"
    )
    if (
        not isinstance(compact_input, Mapping)
        or not isinstance(input_file_record, Mapping)
        or compact_input.get("compressed_size_bytes")
        != input_file_record.get("size_bytes")
        or compact_input.get("compressed_sha256")
        != input_file_record.get("sha256")
        or compact_input.get("compressed_size_bytes")
        != requant_input_path.stat().st_size
    ):
        raise ServerWorkloadScaleError("Requant compact input binding differs")

    dequant_sca_path = _manifest_bound_file(
        dequant_package, dequant_manifest, "workload/runtime/sca_cfg.json"
    )
    dequant_sca_d_path = _manifest_bound_file(
        dequant_package, dequant_manifest, "workload/runtime/sca_cfg_D.json"
    )
    dequant_execplan_path = _manifest_bound_file(
        dequant_package,
        dequant_manifest,
        "workload/runtime/payloads/execplan.txt",
    )
    dequant_sca = _load_object(dequant_sca_path)
    dequant_sca_d = _load_object(dequant_sca_d_path)
    dequant_input_paths = sorted(
        (
            dequant_package
            / "workload/runtime/payloads/op0"
        ).glob("slice*/matrix_A_linearized_128bit.txt")
    )
    for path in dequant_input_paths:
        _manifest_bound_file(
            dequant_package,
            dequant_manifest,
            path.relative_to(dequant_package).as_posix(),
        )

    partial = _load_object(root / REQUANT_PARTIAL_ANALYSIS)
    progress = partial.get("simulation_progress")
    local_monitors = (
        progress.get("local_monitor_files_announced")
        if isinstance(progress, Mapping)
        else None
    )
    bank_monitors = (
        progress.get("bank_frame_monitor_files_announced_at_snapshot")
        if isinstance(progress, Mapping)
        else None
    )
    if not isinstance(local_monitors, Mapping) or not isinstance(
        bank_monitors, Mapping
    ):
        raise ServerWorkloadScaleError("partial snapshot monitor evidence differs")

    requant_repeat = requant_sca.get("Repeat_Num")
    requant_exec_length = requant_sca.get("Exec_Length")
    requant_preload_count = _sca_file_entry_count(requant_sca)
    requant_formal_d_lines = _sca_d_line_count(requant_sca_d)
    requant_input_bytes = compact_input.get("raw_size_bytes")
    dequant_repeat = dequant_sca.get("Repeat_Num")
    dequant_exec_length = dequant_sca.get("Exec_Length")
    dequant_preload_count = _sca_file_entry_count(dequant_sca)
    dequant_formal_d_lines = _sca_d_line_count(dequant_sca_d)
    dequant_input_lines = sum(
        _nonempty_line_count(path) for path in dequant_input_paths
    )
    runner = requant_runner_path.read_text(encoding="utf-8")

    expected = (
        requant_manifest.get("run_kind") == "stock_rtl_e4_first_dynamic"
        and requant_manifest.get("execution_contract", {}).get("stage_count")
        == 48
        and requant_repeat == 48
        and requant_exec_length == 317
        and _nonempty_line_count(requant_execplan_path) == 317
        and len(requant_sca) == 181
        and requant_preload_count == 178
        and len(requant_sca_d) == 156
        and requant_formal_d_lines == 1_505_280
        and requant_input_bytes == 51_380_224
        and dequant_repeat == 1
        and dequant_exec_length == 29
        and _nonempty_line_count(dequant_execplan_path) == 29
        and len(dequant_sca) == 33
        and dequant_preload_count == 30
        and len(dequant_sca_d) == 28
        and dequant_formal_d_lines == 5_264
        and len(dequant_input_paths) == 28
        and all(_nonempty_line_count(path) == 47 for path in dequant_input_paths)
        and dequant_input_lines == 1_316
        and progress.get("repeat_num") == 48
        and sum(int(value) for value in local_monitors.values()) == 420
        and progress.get("bank_frame_monitor_expected_per_kind") == 112
        and sum(int(value) for value in bank_monitors.values()) == 326
        and "DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0" in runner
    )
    if not expected:
        raise ServerWorkloadScaleError(
            "Requant/Dequant E4 workload scale identity differs"
        )

    dequant_input_bytes = dequant_input_lines * 16
    requant_element_count = requant_input_bytes // 4
    requant_formal_d_bytes = requant_formal_d_lines * 16
    dequant_formal_d_bytes = dequant_formal_d_lines * 16
    return {
        "classification": "FULL_TWO_STAGE_W3_E4_NOT_ATOMIC_SMOKE",
        "requant": {
            "repeat_num": requant_repeat,
            "execplan_length": requant_exec_length,
            "sca_property_count": len(requant_sca),
            "preload_file_entry_count": requant_preload_count,
            "raw_input_bytes": requant_input_bytes,
            "int32_element_count": requant_element_count,
            "formal_d_entry_count": len(requant_sca_d),
            "formal_d_128bit_line_count": requant_formal_d_lines,
            "formal_d_bytes": requant_formal_d_bytes,
            "guard_round_element_stage_operations": (
                requant_element_count * 2
            ),
        },
        "dequant_reference": {
            "repeat_num": dequant_repeat,
            "execplan_length": dequant_exec_length,
            "sca_property_count": len(dequant_sca),
            "preload_file_entry_count": dequant_preload_count,
            "raw_input_bytes": dequant_input_bytes,
            "formal_d_entry_count": len(dequant_sca_d),
            "formal_d_128bit_line_count": dequant_formal_d_lines,
            "formal_d_bytes": dequant_formal_d_bytes,
        },
        "relative_scale": {
            "raw_input_bytes_exact_ratio": (
                f"{requant_input_bytes}/{dequant_input_bytes}"
            ),
            "raw_input_bytes_approx_multiple": round(
                requant_input_bytes / dequant_input_bytes, 3
            ),
            "formal_d_bytes_exact_ratio": (
                f"{requant_formal_d_bytes}/{dequant_formal_d_bytes}"
            ),
            "formal_d_bytes_approx_multiple": round(
                requant_formal_d_bytes / dequant_formal_d_bytes, 3
            ),
            "start_comp_multiple": requant_repeat // dequant_repeat,
        },
        "stock_text_monitor_evidence": {
            "waveform_dump_flags_disabled": True,
            "local_files_announced": 420,
            "bank_files_expected": 336,
            "bank_files_announced_at_snapshot": 326,
            "total_files_expected_after_first_start": 756,
            "text_monitors_remain_active_with_waveform_dump_disabled": True,
        },
        "runtime_risk_classification": (
            "PLAUSIBLE_TEXT_IO_AND_SERIAL_FENCE_DOMINANCE_"
            "NOT_PROVEN_ROOT_CAUSE"
        ),
        "snapshot_proves_hang": False,
        "counts_as_formal_e4_attempt": False,
    }


__all__ = [
    "ServerWorkloadScaleError",
    "build_requant_v2_workload_scale",
]
