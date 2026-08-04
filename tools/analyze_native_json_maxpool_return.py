#!/usr/bin/env python3
"""Validate one native-JSON MaxPool server return and compare every output byte."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
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
from resnet50_pipeline.native_json_maxpool_package import (  # noqa: E402
    validate_native_json_maxpool_package,
)


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConvHardwareExecplanError(f"cannot read JSON object: {path}") from error
    if not isinstance(value, dict):
        raise ConvHardwareExecplanError(f"JSON root must be an object: {path}")
    return value


def _safe_extract(archive_path: Path, destination: Path) -> tuple[Path, dict[str, Any]]:
    archive_path = archive_path.resolve()
    if not archive_path.is_file():
        raise ConvHardwareExecplanError(f"server return ZIP is missing: {archive_path}")
    destination.mkdir(parents=True, exist_ok=False)
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if not infos:
            raise ConvHardwareExecplanError("server return ZIP is empty")
        seen: set[str] = set()
        roots: set[str] = set()
        prepared: list[tuple[zipfile.ZipInfo, tuple[str, ...]]] = []
        for info in infos:
            raw = info.filename
            if not raw or "\\" in raw or "\x00" in raw or raw.startswith("/"):
                raise ConvHardwareExecplanError(f"unsafe return ZIP entry: {raw!r}")
            posix = PurePosixPath(raw)
            parts = posix.parts
            if (
                not parts
                or any(part in {"", ".", ".."} for part in parts)
                or ":" in parts[0]
                or posix.as_posix() != raw.rstrip("/")
                or posix.as_posix() in seen
            ):
                raise ConvHardwareExecplanError(f"unsafe/duplicate return ZIP entry: {raw!r}")
            seen.add(posix.as_posix())
            roots.add(parts[0])
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            file_type = stat.S_IFMT(unix_mode)
            if info.is_dir():
                if file_type not in (0, stat.S_IFDIR):
                    raise ConvHardwareExecplanError(f"invalid ZIP directory object: {raw}")
            elif file_type not in (0, stat.S_IFREG):
                raise ConvHardwareExecplanError(f"non-regular return ZIP object: {raw}")
            prepared.append((info, parts))
        if len(roots) != 1:
            raise ConvHardwareExecplanError(
                f"return ZIP must contain exactly one root: {sorted(roots)}"
            )
        for info, parts in prepared:
            target = destination.joinpath(*parts)
            if not target.resolve().is_relative_to(destination_root):
                raise ConvHardwareExecplanError(f"return ZIP entry escapes root: {info.filename}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as sink:
                    shutil.copyfileobj(source, sink)
    root = destination / next(iter(roots))
    return root, {
        "path": str(archive_path),
        "size_bytes": archive_path.stat().st_size,
        "sha256": _sha256_file(archive_path),
        "root": root.name,
    }


def _validate_return_exact_set(root: Path) -> dict[PurePosixPath, Path]:
    contract = root / "return_file_contract.tsv"
    if contract.is_symlink() or not contract.is_file():
        raise ConvHardwareExecplanError("return_file_contract.tsv is missing or unsafe")
    expected: dict[PurePosixPath, tuple[int, str]] = {}
    for line_number, line in enumerate(contract.read_text(encoding="utf-8").splitlines(), 1):
        fields = line.split("\t")
        if (
            len(fields) != 3
            or re.fullmatch(r"0|[1-9][0-9]*", fields[1]) is None
            or SHA256_RE.fullmatch(fields[2]) is None
        ):
            raise ConvHardwareExecplanError(f"malformed return contract line: {line_number}")
        raw = fields[0]
        posix = PurePosixPath(raw)
        windows = PureWindowsPath(raw)
        if (
            not raw
            or posix.is_absolute()
            or windows.is_absolute()
            or bool(windows.anchor)
            or "\\" in raw
            or any(part in {"", ".", ".."} for part in posix.parts)
            or posix == PurePosixPath("return_file_contract.tsv")
            or posix in expected
        ):
            raise ConvHardwareExecplanError(f"unsafe return contract path: {line_number}")
        expected[posix] = (int(fields[1]), fields[2])
    if not expected:
        raise ConvHardwareExecplanError("return file contract is empty")
    allowed = {
        "config",
        "diagnostic_allowlist.tsv",
        "preload_readback_report.json",
        "readback_regions",
        "return_archive_policy.json",
        "return_file_contract.tsv",
        "run_metadata.json",
        "run_sim_results",
        "server_source_provenance.json",
        "sim_results",
    }
    actual: dict[PurePosixPath, Path] = {}
    for path in root.rglob("*"):
        relative = PurePosixPath(path.relative_to(root).as_posix())
        if not relative.parts or relative.parts[0] not in allowed:
            raise ConvHardwareExecplanError(f"unapproved return path: {relative}")
        if path.is_symlink():
            raise ConvHardwareExecplanError(f"return contains symlink: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ConvHardwareExecplanError(f"return contains non-regular object: {relative}")
        if relative != PurePosixPath("return_file_contract.tsv"):
            actual[relative] = path
    if set(actual) != set(expected):
        raise ConvHardwareExecplanError(
            "return whole-tree exact set differs: "
            f"missing={sorted(str(item) for item in set(expected) - set(actual))[:4]}, "
            f"extra={sorted(str(item) for item in set(actual) - set(expected))[:4]}"
        )
    for relative, (size, digest) in expected.items():
        path = actual[relative]
        if path.stat().st_size != size or _sha256_file(path) != digest:
            raise ConvHardwareExecplanError(f"return file identity differs: {relative}")
    return actual


def _expected_return_config_hashes(
    package: Path, approved_identity: Mapping[str, Any]
) -> dict[PurePosixPath, str]:
    result = {
        PurePosixPath("config/sca_cfg.json"): str(
            approved_identity["relocated_sca_cfg"]["sha256"]
        ),
        PurePosixPath("config/sca_cfg_D.json"): str(
            approved_identity["relocated_sca_cfg_D"]["sha256"]
        ),
        PurePosixPath("config/metadata/manifest.json"): _sha256_file(
            package / "manifest.json"
        ),
        PurePosixPath("config/metadata/runner_contract.json"): _sha256_file(
            package / "runner_contract.json"
        ),
        PurePosixPath("config/metadata/dump_contract.json"): _sha256_file(
            package / "dump_contract.json"
        ),
    }
    for key in (
        "readback_region_contract",
        "runtime_stage_contract",
        "launch_file_contract",
        "launch_identity",
        "runtime_make_override",
        "run_command_contract",
        "runner_identity",
    ):
        record = approved_identity[key]
        raw = PurePosixPath(str(record["path"]))
        metadata_index = max(i for i, part in enumerate(raw.parts) if part == "metadata")
        result[PurePosixPath("config/metadata") / raw.parts[metadata_index + 1]] = str(
            record["sha256"]
        )
    approved_path = approved_identity.get("schema_version")
    if approved_path != "resnet50-ndp-server-runtime-identity-0.1":
        raise ConvHardwareExecplanError("approved runtime identity schema differs")
    return result


def _integer(metadata: Mapping[str, Any], key: str) -> int:
    value = metadata.get(key)
    if isinstance(value, bool):
        raise ConvHardwareExecplanError(f"metadata field is not an integer: {key}")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ConvHardwareExecplanError(f"metadata field is not an integer: {key}") from error


def _validate_success_metadata(
    root: Path,
    package: Path,
    manifest: Mapping[str, Any],
    runner: Mapping[str, Any],
    approved_identity_path: Path,
    approved_identity: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
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
            raise ConvHardwareExecplanError(
                f"server completion metadata differs: {key}={metadata.get(key)!r}"
            )
    if (
        metadata.get("simulator_exit_status_observed") is not True
        or metadata.get("phase_watchdog_done") is not True
        or _integer(metadata, "phase_stall_seconds") != 0
    ):
        raise ConvHardwareExecplanError("server completion/watchdog evidence differs")
    expected_integers = {
        "completed_runtime_stage_count": 2,
        "expected_runtime_stage_count": 2,
        "expected_testbench_repeat_num": 1,
        "observed_slice0_start_count": 1,
        "observed_slice1_finish_count": 1,
        "reserved_clock_force_marker_count": 1,
        "reserved_clock_failure_marker_count": 0,
        "returned_region_count": 4,
        "expected_region_count": 4,
    }
    for key, expected in expected_integers.items():
        if _integer(metadata, key) != expected:
            raise ConvHardwareExecplanError(f"server count differs: {key}")
    expected_hashes = {
        "freeze_id": str(manifest["freeze_id"]),
        "freeze_manifest_sha256": str(manifest["freeze_manifest_sha256"]),
        "package_manifest_sha256": _sha256_file(package / "manifest.json"),
        "runtime_identity_sha256": _sha256_file(approved_identity_path),
        "sca_cfg_sha256": str(approved_identity["relocated_sca_cfg"]["sha256"]),
        "sca_cfg_D_sha256": str(approved_identity["relocated_sca_cfg_D"]["sha256"]),
        "readback_contract_sha256": str(
            approved_identity["readback_region_contract"]["sha256"]
        ),
    }
    for key, expected in expected_hashes.items():
        if metadata.get(key) != expected:
            raise ConvHardwareExecplanError(f"server identity differs: {key}")
    preload = _json(root / "preload_readback_report.json")
    if preload != {
        "status": "passed",
        "expected_transfer_count": 11,
        "passed_transfer_count": 11,
    }:
        raise ConvHardwareExecplanError("preload/readback report differs")
    return run_id, metadata


def _compare_regions(
    package: Path, root: Path, actual_files: Mapping[PurePosixPath, Path]
) -> list[dict[str, Any]]:
    sca_d = _json(actual_files[PurePosixPath("config/sca_cfg_D.json")])
    expected_tree = _sca_d_readback_contract(sca_d, label="returned SCA_D")
    snapshot = _validate_readback_region_tree(root, expected_tree)
    grouped: dict[str, list[tuple[int, int, bytes]]] = {}
    for key, entry in sca_d.items():
        relative = next(
            item
            for item in expected_tree
            if item.as_posix() in str(entry["path"])
        )
        grouped.setdefault(str(entry["semantic_key"]), []).append(
            (
                int(entry["axi4_segment_index"]),
                int(entry["axi4_segment_count"]),
                bytes(snapshot[relative]["payload"]),
            )
        )
    contract = _json(package / "dump_contract.json")
    expected_by_slice = {int(item["slice_id"]): item for item in contract["semantic_regions"]}
    results: list[dict[str, Any]] = []
    for semantic_key, records in sorted(grouped.items()):
        records.sort(key=lambda item: item[0])
        segment_count = records[0][1]
        if (
            segment_count != len(records)
            or [item[0] for item in records] != list(range(segment_count))
            or any(item[1] != segment_count for item in records)
        ):
            raise ConvHardwareExecplanError(f"readback segment sequence differs: {semantic_key}")
        match = re.search(r"slice(?P<slice>[0-9]+)$", semantic_key)
        if match is None:
            raise ConvHardwareExecplanError(f"semantic readback key has no slice: {semantic_key}")
        slice_id = int(match.group("slice"))
        expected = expected_by_slice.get(slice_id)
        if expected is None:
            raise ConvHardwareExecplanError(f"unexpected semantic slice: {slice_id}")
        actual_payload = b"".join(item[2] for item in records)
        golden_path = package / "evidence" / "golden" / f"slice{slice_id:02d}.bin"
        golden_payload = golden_path.read_bytes()
        mismatch_count = sum(left != right for left, right in zip(actual_payload, golden_payload))
        mismatch_count += abs(len(actual_payload) - len(golden_payload))
        if (
            mismatch_count
            or hashlib.sha256(actual_payload).hexdigest() != expected["raw_sha256"]
        ):
            raise ConvHardwareExecplanError(
                f"MaxPool target output differs from W3 golden: slice={slice_id}, mismatches={mismatch_count}"
            )
        results.append(
            {
                "slice_id": slice_id,
                "semantic_key": semantic_key,
                "segment_count": segment_count,
                "size_bytes": len(actual_payload),
                "sha256": hashlib.sha256(actual_payload).hexdigest(),
                "mismatch_count": mismatch_count,
            }
        )
    if set(expected_by_slice) != {item["slice_id"] for item in results}:
        raise ConvHardwareExecplanError("semantic MaxPool output slice set differs")
    return results


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
    validate_native_json_maxpool_package(package)
    manifest = _json(package / "manifest.json")
    runner = _json(package / "runner_contract.json")
    approved = _json(approved_path)
    actual_files = _validate_return_exact_set(root)
    _validate_returned_config_file_set(actual_files, approved)
    expected_config_hashes = _expected_return_config_hashes(package, approved)
    for relative, expected_hash in expected_config_hashes.items():
        if relative not in actual_files or _sha256_file(actual_files[relative]) != expected_hash:
            raise ConvHardwareExecplanError(f"returned approved config differs: {relative}")
    run_id, metadata = _validate_success_metadata(
        root, package, manifest, runner, approved_path, approved
    )
    console_files = list((root / "run_sim_results").glob("*_console.log"))
    if len(console_files) != 1:
        raise ConvHardwareExecplanError("successful return must contain one console log")
    runtime_operators = manifest["runtime_operators"]
    console = _parse_runtime_completion_console(
        console_files[0],
        expected_preload_transfer_count=11,
        expected_slice_masks=[str(item["slice_mask"]) for item in runtime_operators],
        expected_simulator_exit_status=0,
        observer_contract=runner["execution"]["completion_gate"]["testbench_observer"],
    )
    regions = _compare_regions(package, root, actual_files)
    return {
        "schema_version": "resnet50-native-json-maxpool-return-analysis-0.1",
        "status": "passed_single_server_return",
        "server_run_id": run_id,
        "archive": dict(archive or {}),
        "package_manifest_sha256": _sha256_file(package / "manifest.json"),
        "runtime_identity_sha256": _sha256_file(approved_path),
        "return_file_count": len(actual_files),
        "console_validation": console,
        "regions": regions,
        "logical_mismatch_count": sum(item["mismatch_count"] for item in regions),
        "target_execution_scope": "two real node-0002 channel tiles on slice0/slice1",
        "full_batch16_three_way_validated": False,
        "g6_validated": False,
        "g8_validated": False,
        "simulator_version": metadata["simulator_version"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and compare one node-0002 native MaxPool server return ZIP"
    )
    parser.add_argument("zip", type=Path)
    parser.add_argument(
        "--package",
        type=Path,
        default=Path("artifacts/w5/native_json_maxpool/v2/hardware_execplan_package"),
    )
    parser.add_argument(
        "--runtime-identity",
        type=Path,
        default=Path(
            "artifacts/maxpool_server_v1/NDP_copy01/install/cfg_pkg/"
            "node0002-maxpool1/metadata/runtime_identity.json"
        ),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    package = args.package if args.package.is_absolute() else ROOT / args.package
    runtime_identity = (
        args.runtime_identity
        if args.runtime_identity.is_absolute()
        else ROOT / args.runtime_identity
    )
    with tempfile.TemporaryDirectory(prefix="native-maxpool-return-") as temp_text:
        return_root, archive = _safe_extract(args.zip, Path(temp_text) / "extract")
        report = analyze_return(package, return_root, runtime_identity, archive=archive)
    payload = (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
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
