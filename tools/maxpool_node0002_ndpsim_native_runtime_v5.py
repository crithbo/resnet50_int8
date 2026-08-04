"""Minimal server runtime for the native ndp-sim MaxPool node0002 package."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

sys.dont_write_bytecode = True

MANIFEST_NAME = "TEST_PACKAGE_MANIFEST.json"
SOURCE_JSON_SHA256 = (
    "a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1"
)
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_RETURN_ZIP_BYTES = 16 * 1024 * 1024
MAX_RETURN_EXTRACTED_BYTES = 32 * 1024 * 1024
FORBIDDEN_RETURN_PARTS = {
    "csrc",
    "simv",
    "simv.daidir",
    "archive",
    "sim_results",
}
FORBIDDEN_RETURN_SUFFIXES = {".vcd", ".fsdb", ".sdb", ".so", ".a"}


class NativeMaxPoolRuntimeError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise NativeMaxPoolRuntimeError(f"JSON root must be an object: {path}")
    return value


def safe_relative(value: str) -> PurePosixPath:
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise NativeMaxPoolRuntimeError(f"unsafe relative path: {value}")
    return relative


def inside(root: Path, relative_value: str) -> Path:
    relative = safe_relative(relative_value)
    root_resolved = root.resolve()
    target = root_resolved.joinpath(*relative.parts).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise NativeMaxPoolRuntimeError(f"path escapes root: {relative_value}") from exc
    return target


def file_records(
    root: Path, *, exclude_manifest: bool = False
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == MANIFEST_NAME:
            continue
        if path.is_symlink():
            raise NativeMaxPoolRuntimeError(f"symlink is forbidden: {path}")
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    return result


def _validate_128bit_text(
    path: Path, *, expected_lines: int | None = None
) -> list[str]:
    if not path.is_file() or path.is_symlink():
        raise NativeMaxPoolRuntimeError(f"missing 128-bit text: {path}")
    payload = path.read_bytes()
    lines = payload.decode("ascii").splitlines()
    if not lines or any(
        len(line) != 128 or set(line) - {"0", "1"} for line in lines
    ):
        raise NativeMaxPoolRuntimeError(f"invalid 128-bit text: {path}")
    if expected_lines is not None and len(lines) != expected_lines:
        raise NativeMaxPoolRuntimeError(
            f"128-bit line count differs: {path}: {len(lines)} != {expected_lines}"
        )
    return lines


def _runtime_relative(path_value: str, install_name: str) -> PurePosixPath:
    relative = safe_relative(path_value)
    prefix = ("install", "cfg_pkg", install_name)
    if relative.parts[:3] != prefix or len(relative.parts) <= 3:
        raise NativeMaxPoolRuntimeError(
            f"SCA path is outside the fresh namespace: {path_value}"
        )
    return PurePosixPath(*relative.parts[3:])


def _json_diffs(left: Any, right: Any, path: str = "$") -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}"
            if key not in left:
                result.append({"path": child, "before": None, "after": right[key]})
            elif key not in right:
                result.append({"path": child, "before": left[key], "after": None})
            else:
                result.extend(_json_diffs(left[key], right[key], child))
    elif isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            result.append(
                {"path": path, "before_length": len(left), "after_length": len(right)}
            )
        else:
            for index, (left_item, right_item) in enumerate(
                zip(left, right, strict=True)
            ):
                result.extend(
                    _json_diffs(left_item, right_item, f"{path}[{index}]")
                )
    elif left != right:
        result.append({"path": path, "before": left, "after": right})
    return result


def validate_native(
    native_root: Path,
    install_name: str,
    *,
    output_targets_must_be_absent: bool,
) -> dict[str, Any]:
    source = native_root / "source_config/maxpool_config_16_112_112_stride2_padding1.json"
    if sha256(source) != SOURCE_JSON_SHA256:
        raise NativeMaxPoolRuntimeError("authoritative source JSON differs")
    materialized = (
        native_root
        / "jsons/op0_maxpool_config_16_112_112_stride2_padding1.json"
    )
    diffs = _json_diffs(load_json(source), load_json(materialized))
    allowed = {
        "$.stream_engine.stream0.base_addr",
        "$.stream_engine.stream1.base_addr",
    }
    if {item["path"] for item in diffs} != allowed:
        raise NativeMaxPoolRuntimeError(
            f"materialized JSON has non-base semantic differences: {diffs}"
        )

    sca = load_json(native_root / "sca_cfg.json")
    sca_d = load_json(native_root / "sca_cfg_D.json")
    if (
        sca.get("Exec_Base") != "0x0003_D800"
        or sca.get("Exec_Length") != 29
        or sca.get("Repeat_Num") != 1
    ):
        raise NativeMaxPoolRuntimeError("native MaxPool SCA header differs")
    referenced = 0
    for key, item in sca.items():
        if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
            continue
        relative = _runtime_relative(str(item["path"]), install_name)
        target = native_root.joinpath(*relative.parts)
        _validate_128bit_text(target)
        referenced += 1
    if referenced != 30:
        raise NativeMaxPoolRuntimeError(
            f"native MaxPool SCA reference count differs: {referenced}"
        )
    if len(sca_d) != 28:
        raise NativeMaxPoolRuntimeError("native MaxPool SCA_D count differs")
    for key, item in sca_d.items():
        if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
            raise NativeMaxPoolRuntimeError(f"invalid SCA_D entry: {key}")
        if item.get("length") != 3136:
            raise NativeMaxPoolRuntimeError(f"SCA_D length differs: {key}")
        relative = _runtime_relative(str(item["path"]), install_name)
        target = native_root.joinpath(*relative.parts)
        if output_targets_must_be_absent and target.exists():
            raise NativeMaxPoolRuntimeError(
                f"formal readback target is pre-existing: {target}"
            )
    return {
        "source_json_sha256": SOURCE_JSON_SHA256,
        "source_json_rewritten": False,
        "materialized_diff_count": len(diffs),
        "materialized_diff_paths": sorted(allowed),
        "sca_reference_count": referenced,
        "sca_d_reference_count": len(sca_d),
        "runtime_D_initially_absent": True,
    }


def package_identity(package_root: Path) -> dict[str, Any]:
    manifest = load_json(package_root.resolve() / MANIFEST_NAME)
    return {
        "install_name": manifest.get("install_name"),
        "return_name": manifest.get("return", {}).get("name"),
    }


def preflight_package(package_root: Path) -> dict[str, Any]:
    package = package_root.resolve()
    manifest = load_json(package / MANIFEST_NAME)
    install_name = str(manifest.get("install_name", ""))
    if not install_name or manifest.get("source_json", {}).get("sha256") != SOURCE_JSON_SHA256:
        raise NativeMaxPoolRuntimeError("package identity differs")
    expected = manifest.get("files")
    if not isinstance(expected, dict):
        raise NativeMaxPoolRuntimeError("manifest files map is missing")
    actual = file_records(package, exclude_manifest=True)
    if actual != expected:
        raise NativeMaxPoolRuntimeError("package exact file set/hash differs")
    facts = validate_native(
        package / "workload/native",
        install_name,
        output_targets_must_be_absent=True,
    )
    return {
        "schema": "maxpool-node0002-ndpsim-native-package-preflight-v1",
        "valid": True,
        "file_count": len(actual) + 1,
        "package_tree_immutable": True,
        **facts,
    }


def preflight_installed(
    package_root: Path, server_root: Path, install_name: str
) -> dict[str, Any]:
    package = package_root.resolve()
    root = server_root.resolve()
    manifest = load_json(package / MANIFEST_NAME)
    if manifest.get("install_name") != install_name:
        raise NativeMaxPoolRuntimeError("installed identity differs")
    cfg_root = root / "install/cfg_pkg" / install_name
    if not cfg_root.is_dir() or cfg_root.is_symlink():
        raise NativeMaxPoolRuntimeError("installed native root is missing")
    expected = manifest.get("installed_files")
    if not isinstance(expected, dict) or file_records(cfg_root) != expected:
        raise NativeMaxPoolRuntimeError("installed exact file set/hash differs")
    facts = validate_native(
        cfg_root, install_name, output_targets_must_be_absent=True
    )
    return {
        "schema": "maxpool-node0002-ndpsim-native-installed-preflight-v1",
        "valid": True,
        "server_source_files_inspected": False,
        **facts,
    }


def _decode_lines(lines: list[str]) -> bytes:
    return b"".join(
        int(line, 2).to_bytes(16, byteorder="little") for line in lines
    )


def compare_readback(
    package_root: Path, server_root: Path, cfg_root: Path
) -> dict[str, Any]:
    sca_d = load_json(cfg_root / "sca_cfg_D.json")
    records: list[dict[str, Any]] = []
    mismatch_total = 0
    missing_count = 0
    invalid_count = 0
    for slice_id in range(28):
        key = f"op0_matrixD_slice{slice_id}"
        item = sca_d[key]
        observed_path = inside(server_root, str(item["path"]))
        golden_path = (
            package_root
            / f"validation/golden/op0/slice{slice_id:02d}/matrix_D_linearized_128bit.txt"
        )
        observed: bytes | None = None
        error: str | None = None
        if not observed_path.is_file():
            missing_count += 1
            error = "missing"
        else:
            try:
                observed = _decode_lines(
                    _validate_128bit_text(observed_path, expected_lines=3136)
                )
            except Exception as exc:  # fail-closed evidence
                invalid_count += 1
                error = str(exc)
        golden = _decode_lines(
            _validate_128bit_text(golden_path, expected_lines=3136)
        )
        mismatch = (
            sum(a != b for a, b in zip(observed, golden, strict=True))
            if observed is not None and len(observed) == len(golden)
            else None
        )
        if mismatch is not None:
            mismatch_total += mismatch
        records.append(
            {
                "slice_id": slice_id,
                "path": str(item["path"]),
                "present": observed is not None,
                "error": error,
                "golden_sha256": hashlib.sha256(golden).hexdigest(),
                "observed_sha256": hashlib.sha256(observed).hexdigest()
                if observed is not None
                else None,
                "byte_mismatch_count": mismatch,
            }
        )
    return {
        "expected_count": 28,
        "present_count": 28 - missing_count - invalid_count,
        "missing_count": missing_count,
        "invalid_count": invalid_count,
        "mismatch_byte_count": mismatch_total
        if missing_count == 0 and invalid_count == 0
        else None,
        "records": records,
    }


def analyze(
    server_root: Path,
    package_root: Path,
    install_name: str,
    run_dir: Path,
    compile_status: int,
    simulation_status: int,
) -> dict[str, Any]:
    root = server_root.resolve()
    package = package_root.resolve()
    run = run_dir.resolve()
    cfg_root = root / "install/cfg_pkg" / install_name
    sim_log_path = run / "sim_results/sim.log"
    sim_log = (
        sim_log_path.read_text(encoding="utf-8", errors="replace")
        if sim_log_path.is_file()
        else ""
    )
    natural_terminal = (
        "Simulation completed successfully!" in sim_log
        and "INFO: slice completed after" in sim_log
    )
    sca_echo = "Using SCA cfg" in sim_log
    sca_d_echo = "Using SCA cfg D" in sim_log
    readback = compare_readback(package, root, cfg_root)
    conjunction = (
        compile_status == 0
        and simulation_status == 0
        and natural_terminal
        and readback["missing_count"] == 0
        and readback["invalid_count"] == 0
        and readback["mismatch_byte_count"] == 0
    )
    if compile_status != 0:
        status = "COMPILE_FAILED"
    elif simulation_status != 0 or not natural_terminal:
        status = "SIMULATION_NOT_NATURALLY_COMPLETE"
    elif readback["missing_count"] or readback["invalid_count"]:
        status = "FORMAL_READBACK_INCOMPLETE"
    elif readback["mismatch_byte_count"]:
        status = "FORMAL_READBACK_MISMATCH"
    else:
        status = "NATIVE_MAXPOOL_SERVER_RESULT_PASS"
    return {
        "schema": "maxpool-node0002-ndpsim-native-result-v1",
        "status": status,
        "result_gate": conjunction,
        "candidate_release": False,
        "server_source_identity_bound": False,
        "compile_exit_status": compile_status,
        "simulation_exit_status": simulation_status,
        "natural_terminal": natural_terminal,
        "sca_echo_observed": sca_echo,
        "sca_d_echo_observed": sca_d_echo,
        "formal_readback": readback,
        "source_json_sha256": SOURCE_JSON_SHA256,
        "functional_rtl_modified": False,
        "observer_present": False,
        "user_override_native_path": True,
    }


def _copy_tail(source: Path, destination: Path, limit: int = 200_000) -> None:
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes()[-limit:])


def collect(
    server_root: Path,
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_dir: Path,
    runner_status: int,
) -> dict[str, Any]:
    root = server_root.resolve()
    package = package_root.resolve()
    evidence = evidence_root.resolve()
    run = run_dir.resolve()
    manifest = load_json(package / MANIFEST_NAME)
    return_name = str(manifest["return"]["name"])
    staging = root / return_name
    zip_path = root / f"{return_name}.zip"
    sidecar = root / f"{return_name}.zip.sha256"
    for target in (staging, zip_path, sidecar):
        if target.exists():
            raise NativeMaxPoolRuntimeError(f"return target must be fresh: {target}")
    staging.mkdir()
    records: list[dict[str, Any]] = []
    missing: list[str] = []

    def add(source: Path, relative_value: str, required: bool = True) -> None:
        relative = safe_relative(relative_value)
        if set(part.lower() for part in relative.parts) & FORBIDDEN_RETURN_PARTS:
            raise NativeMaxPoolRuntimeError(f"forbidden return path: {relative}")
        if relative.suffix.lower() in FORBIDDEN_RETURN_SUFFIXES:
            raise NativeMaxPoolRuntimeError(f"forbidden return suffix: {relative}")
        if not source.is_file() or source.is_symlink():
            if required:
                missing.append(relative.as_posix())
            return
        if source.stat().st_size > MAX_FILE_BYTES:
            raise NativeMaxPoolRuntimeError(f"return file exceeds budget: {source}")
        destination = inside(staging, relative.as_posix())
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        records.append(
            {
                "path": relative.as_posix(),
                "size_bytes": destination.stat().st_size,
                "sha256": sha256(destination),
            }
        )

    def record_staged(relative_value: str) -> None:
        relative = safe_relative(relative_value)
        target = inside(staging, relative.as_posix())
        if target.is_file():
            records.append(
                {
                    "path": relative.as_posix(),
                    "size_bytes": target.stat().st_size,
                    "sha256": sha256(target),
                }
            )

    add(package / MANIFEST_NAME, f"package/{MANIFEST_NAME}")
    for name in (
        "package_preflight.json",
        "installed_preflight.json",
        "actual_compile_argv.txt",
        "actual_simulator_argv.txt",
        "compile_exit_status.txt",
        "simulation_exit_status.txt",
        "runner_exit_status.txt",
        "termination_signal.txt",
        "finalizer_status.json",
        "SERVER_RESULT_GATE.json",
    ):
        add(
            evidence / name,
            f"evidence/{name}",
            required=name
            not in {"termination_signal.txt"},
        )
    cfg_root = root / "install/cfg_pkg" / install_name
    add(cfg_root / "sca_cfg.json", "config/sca_cfg.json")
    add(cfg_root / "sca_cfg_D.json", "config/sca_cfg_D.json")
    sca_d = load_json(cfg_root / "sca_cfg_D.json")
    for key, item in sorted(sca_d.items()):
        add(
            inside(root, str(item["path"])),
            f"formal_readback/{key}.txt",
            required=False,
        )
    for source_name, target_name in (
        ("compile_driver.log", "compile_driver_tail.log"),
        ("sim.log", "sim_tail.log"),
    ):
        tail = staging / "logs" / target_name
        _copy_tail(run / "sim_results" / source_name, tail)
        record_staged(f"logs/{target_name}")
    return_manifest = {
        "schema": "maxpool-node0002-ndpsim-native-return-manifest-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "package_install_name": install_name,
        "return_name": return_name,
        "runner_exit_status": runner_status,
        "status": "complete" if not missing else "incomplete",
        "required_missing": missing,
        "files": sorted(records, key=lambda item: item["path"]),
    }
    write_json(staging / "RETURN_MANIFEST.json", return_manifest)
    extracted = sum(
        path.stat().st_size for path in staging.rglob("*") if path.is_file()
    )
    if extracted > MAX_RETURN_EXTRACTED_BYTES:
        raise NativeMaxPoolRuntimeError("return extracted size exceeds budget")
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in staging.rglob("*") if item.is_file()):
            relative = f"{return_name}/{path.relative_to(staging).as_posix()}"
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    if zip_path.stat().st_size > MAX_RETURN_ZIP_BYTES:
        raise NativeMaxPoolRuntimeError("return ZIP exceeds budget")
    digest = sha256(zip_path)
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    return {
        **return_manifest,
        "zip_path": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    identity = sub.add_parser("identity")
    identity.add_argument("--package-root", type=Path, required=True)
    package = sub.add_parser("preflight-package")
    package.add_argument("--package-root", type=Path, required=True)
    package.add_argument("--output", type=Path, required=True)
    installed = sub.add_parser("preflight-installed")
    installed.add_argument("--package-root", type=Path, required=True)
    installed.add_argument("--server-root", type=Path, required=True)
    installed.add_argument("--install-name", required=True)
    installed.add_argument("--output", type=Path, required=True)
    analysis = sub.add_parser("analyze")
    analysis.add_argument("--server-root", type=Path, required=True)
    analysis.add_argument("--package-root", type=Path, required=True)
    analysis.add_argument("--install-name", required=True)
    analysis.add_argument("--run-dir", type=Path, required=True)
    analysis.add_argument("--compile-status", type=int, required=True)
    analysis.add_argument("--simulation-status", type=int, required=True)
    analysis.add_argument("--output", type=Path, required=True)
    collection = sub.add_parser("collect")
    collection.add_argument("--server-root", type=Path, required=True)
    collection.add_argument("--package-root", type=Path, required=True)
    collection.add_argument("--install-name", required=True)
    collection.add_argument("--evidence-root", type=Path, required=True)
    collection.add_argument("--run-dir", type=Path, required=True)
    collection.add_argument("--runner-status", type=int, required=True)
    args = parser.parse_args()
    try:
        if args.command == "identity":
            print(json.dumps(package_identity(args.package_root), sort_keys=True))
            return 0
        if args.command == "preflight-package":
            result = preflight_package(args.package_root)
        elif args.command == "preflight-installed":
            result = preflight_installed(
                args.package_root, args.server_root, args.install_name
            )
        elif args.command == "analyze":
            result = analyze(
                args.server_root,
                args.package_root,
                args.install_name,
                args.run_dir,
                args.compile_status,
                args.simulation_status,
            )
        else:
            result = collect(
                args.server_root,
                args.package_root,
                args.install_name,
                args.evidence_root,
                args.run_dir,
                args.runner_status,
            )
        if hasattr(args, "output"):
            write_json(args.output, result)
        else:
            print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"MaxPool native runtime error: {exc}", file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
