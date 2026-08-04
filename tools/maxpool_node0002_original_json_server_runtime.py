"""Server runtime for the immutable original-JSON MaxPool node0002 retest."""

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
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_RETURN_ZIP_BYTES = 16 * 1024 * 1024
MAX_RETURN_EXTRACTED_BYTES = 32 * 1024 * 1024
FORBIDDEN_RETURN_PARTS = {
    "csrc",
    "simv",
    "simv.daidir",
    "archive",
    "sim_results",
}
FORBIDDEN_RETURN_SUFFIXES = {
    ".vcd",
    ".fsdb",
    ".sdb",
    ".so",
    ".a",
}


class MaxPoolRuntimeError(RuntimeError):
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
        raise MaxPoolRuntimeError(f"JSON root must be an object: {path}")
    return value


def safe_relative(value: str) -> PurePosixPath:
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise MaxPoolRuntimeError(f"unsafe relative path: {value}")
    return relative


def inside(root: Path, relative_value: str) -> Path:
    relative = safe_relative(relative_value)
    root_resolved = root.resolve()
    target = root_resolved.joinpath(*relative.parts).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise MaxPoolRuntimeError(f"path escapes root: {relative_value}") from exc
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
            raise MaxPoolRuntimeError(f"symlink is forbidden: {path}")
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    return result


def _runtime_relative(path_value: str, install_name: str) -> PurePosixPath:
    relative = safe_relative(path_value)
    prefix = ("install", "cfg_pkg", install_name)
    if relative.parts[:3] != prefix or len(relative.parts) <= 3:
        raise MaxPoolRuntimeError(
            f"SCA path is outside the package namespace: {path_value}"
        )
    return PurePosixPath(*relative.parts[3:])


def _validate_128bit_text(
    path: Path, *, expected_lines: int | None = None
) -> list[str]:
    if not path.is_file() or path.is_symlink():
        raise MaxPoolRuntimeError(f"missing 128-bit text: {path}")
    payload = path.read_bytes()
    if b"\r" in payload:
        raise MaxPoolRuntimeError(f"CR is forbidden in 128-bit text: {path}")
    lines = payload.decode("ascii").splitlines()
    if not lines or any(len(line) != 128 or set(line) - {"0", "1"} for line in lines):
        raise MaxPoolRuntimeError(f"invalid 128-bit text: {path}")
    if expected_lines is not None and len(lines) != expected_lines:
        raise MaxPoolRuntimeError(
            f"128-bit line count differs: {path}: {len(lines)} != {expected_lines}"
        )
    if len(payload) != len(lines) * 129:
        raise MaxPoolRuntimeError(f"128-bit LF ABI differs: {path}")
    return lines


def _validate_runtime_payload(
    runtime_root: Path, install_name: str, *, output_targets_must_be_absent: bool
) -> dict[str, Any]:
    sca = load_json(runtime_root / "sca_cfg.json")
    sca_d = load_json(runtime_root / "sca_cfg_D.json")
    if (
        sca.get("Exec_Base") != "0x0003_E000"
        or sca.get("Exec_Length") != 5
        or sca.get("Repeat_Num") != 1
    ):
        raise MaxPoolRuntimeError("MaxPool SCA header differs")
    input_reference_count = 0
    for key, item in sca.items():
        if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
            continue
        relative = _runtime_relative(item["path"], install_name)
        target = runtime_root.joinpath(*relative.parts)
        lines = _validate_128bit_text(target)
        declared = item.get("line_count_128bit")
        if declared is not None and declared != len(lines):
            raise MaxPoolRuntimeError(f"SCA line count differs: {key}")
        input_reference_count += 1
    if input_reference_count != 11:
        raise MaxPoolRuntimeError(
            f"MaxPool SCA reference count differs: {input_reference_count}"
        )

    expected_d_keys = {
        "op-native-maxpool-slice0_matrixD_slice0",
        "op-native-maxpool-slice0_matrixD_slice0__axi4_tail",
        "op-native-maxpool-slice1_matrixD_slice1",
        "op-native-maxpool-slice1_matrixD_slice1__axi4_tail",
    }
    if set(sca_d) != expected_d_keys:
        raise MaxPoolRuntimeError("MaxPool SCA_D exact set differs")
    for key, item in sca_d.items():
        if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
            raise MaxPoolRuntimeError(f"invalid SCA_D entry: {key}")
        if not isinstance(item.get("length"), int) or item["length"] <= 0:
            raise MaxPoolRuntimeError(f"invalid SCA_D length: {key}")
        relative = _runtime_relative(item["path"], install_name)
        target = runtime_root.joinpath(*relative.parts)
        if output_targets_must_be_absent and target.exists():
            raise MaxPoolRuntimeError(f"formal readback target is pre-existing: {target}")
    source_json = (
        runtime_root
        / "source_config"
        / "maxpool_config_16_112_112_stride2_padding1.json.original"
    )
    if sha256(source_json) != SOURCE_JSON_SHA256:
        raise MaxPoolRuntimeError("packaged original MaxPool JSON differs")
    return {
        "sca_reference_count": input_reference_count,
        "sca_d_reference_count": len(sca_d),
        "source_json_sha256": SOURCE_JSON_SHA256,
        "source_json_rewritten": False,
    }


def preflight_package(package_root: Path, install_name: str) -> dict[str, Any]:
    package = package_root.resolve()
    manifest = load_json(package / MANIFEST_NAME)
    if (
        manifest.get("install_name") != install_name
        or manifest.get("source_json", {}).get("sha256") != SOURCE_JSON_SHA256
        or manifest.get("source_json", {}).get("rewritten") is not False
    ):
        raise MaxPoolRuntimeError("package identity differs")
    facts = _validate_runtime_payload(
        package / "workload/runtime",
        install_name,
        output_targets_must_be_absent=True,
    )
    return {
        "schema": "maxpool-original-json-package-preflight-v1",
        "status": "pass",
        "package_exact_file_set_check_performed": False,
        "package_tree_immutable": False,
        "required_runtime_payload_validated": True,
        **facts,
    }


def preflight_installed(
    package_root: Path, server_root: Path, install_name: str
) -> dict[str, Any]:
    package = package_root.resolve()
    root = server_root.resolve()
    cfg_root = root / "install" / "cfg_pkg" / install_name
    if not cfg_root.is_dir() or cfg_root.is_symlink():
        raise MaxPoolRuntimeError("installed workload root is missing or unsafe")
    facts = _validate_runtime_payload(
        cfg_root, install_name, output_targets_must_be_absent=True
    )
    return {
        "schema": "maxpool-original-json-installed-preflight-v1",
        "status": "pass",
        "installed_exact_file_set_check_performed": False,
        "required_runtime_payload_validated": True,
        "server_source_preflight_performed": False,
        "server_source_identity_bound": False,
        **facts,
    }


def _decode_lines(lines: list[str]) -> bytes:
    return b"".join(
        int(line, 2).to_bytes(16, byteorder="little") for line in lines
    )


def _compare_formal_readback(
    server_root: Path, cfg_root: Path
) -> dict[str, Any]:
    sca_d = load_json(cfg_root / "sca_cfg_D.json")
    slices: list[dict[str, Any]] = []
    total_mismatch = 0
    all_present = True
    all_format_valid = True
    for slice_id in (0, 1):
        prefix = f"op-native-maxpool-slice{slice_id}_matrixD_slice{slice_id}"
        items = [
            (key, item)
            for key, item in sca_d.items()
            if key == prefix or key.startswith(prefix + "__")
        ]
        items.sort(key=lambda pair: int(pair[1].get("axi4_segment_index", 0)))
        observed_lines: list[str] = []
        missing: list[str] = []
        format_errors: list[str] = []
        for key, item in items:
            target = inside(server_root, str(item["path"]))
            if not target.is_file():
                missing.append(str(item["path"]))
                continue
            try:
                observed_lines.extend(
                    _validate_128bit_text(target, expected_lines=int(item["length"]))
                )
            except Exception as exc:
                format_errors.append(f"{key}: {exc}")
        golden_path = cfg_root / "golden" / f"slice{slice_id:02d}.txt"
        golden_lines = _validate_128bit_text(golden_path, expected_lines=3136)
        observed = _decode_lines(observed_lines) if not format_errors else b""
        golden = _decode_lines(golden_lines)
        mismatch_count = (
            sum(left != right for left, right in zip(observed, golden, strict=True))
            if len(observed) == len(golden) and not format_errors
            else None
        )
        if missing:
            all_present = False
        if format_errors or mismatch_count is None:
            all_format_valid = False
        if mismatch_count is not None:
            total_mismatch += mismatch_count
        slices.append(
            {
                "slice_id": slice_id,
                "expected_segment_count": 2,
                "observed_segment_count": len(items) - len(missing),
                "missing_paths": missing,
                "format_errors": format_errors,
                "observed_bytes": len(observed),
                "golden_bytes": len(golden),
                "observed_sha256": hashlib.sha256(observed).hexdigest()
                if observed
                else None,
                "golden_sha256": hashlib.sha256(golden).hexdigest(),
                "byte_mismatch_count": mismatch_count,
            }
        )
    return {
        "all_readbacks_present": all_present,
        "all_readbacks_format_valid": all_format_valid,
        "total_byte_mismatch_count": total_mismatch
        if all_present and all_format_valid
        else None,
        "slices": slices,
    }


def analyze(
    server_root: Path,
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_dir: Path,
    compile_status: int,
    sim_status: int,
) -> dict[str, Any]:
    root = server_root.resolve()
    package = package_root.resolve()
    evidence = evidence_root.resolve()
    run = run_dir.resolve()
    cfg_root = root / "install" / "cfg_pkg" / install_name
    sim_log_path = run / "sim_results" / "sim.log"
    sim_log = sim_log_path.read_text(encoding="utf-8", errors="replace") if sim_log_path.is_file() else ""
    completion_marker = "Simulation completed successfully!" in sim_log
    sca_echo = "Using SCA cfg" in sim_log
    sca_d_echo = "Using SCA cfg D" in sim_log
    readback = _compare_formal_readback(root, cfg_root)
    if compile_status != 0:
        status = "SERVER_TEST_INFRASTRUCTURE_COMPILE_FAILURE"
    elif sim_status != 0 or not completion_marker:
        status = "FIRST_DYNAMIC_FAILURE"
    elif not readback["all_readbacks_present"] or not readback["all_readbacks_format_valid"]:
        status = "FIRST_DYNAMIC_FAILURE_FORMAL_READBACK"
    elif readback["total_byte_mismatch_count"] != 0:
        status = "FIRST_DYNAMIC_FAILURE_NUMERIC"
    else:
        status = "VERSION_UNBOUND_DIAGNOSTIC_PASS"
    report = {
        "schema": "maxpool-node0002-original-json-result-v1",
        "status": status,
        "classification": "NO_DYNAMIC_BASELINE",
        "candidate_release": False,
        "counts_as_e4": False,
        "counts_as_e5": False,
        "server_source_identity_bound": False,
        "server_source_preflight_performed": False,
        "source_json_sha256": SOURCE_JSON_SHA256,
        "source_json_rewritten": False,
        "compile_exit_status": compile_status,
        "sim_exit_status": sim_status,
        "natural_completion_marker": completion_marker,
        "sca_echo_observed": sca_echo,
        "sca_d_echo_observed": sca_d_echo,
        "formal_readback": readback,
        "package_preflight_present": (evidence / "package_preflight.json").is_file(),
        "installed_preflight_present": (evidence / "installed_preflight.json").is_file(),
        "functional_rtl_modified": False,
        "tb_or_observer_modified": False,
        "claim_boundary": "VERSION_UNBOUND_DIAGNOSTIC_ONLY_NOT_E4_E5",
    }
    return report


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
    run_status: int,
    server_command: str,
) -> dict[str, Any]:
    root = server_root.resolve()
    package = package_root.resolve()
    evidence = evidence_root.resolve()
    run = run_dir.resolve()
    return_name = f"{install_name}_return"
    staging = root / return_name
    zip_path = root / f"{return_name}.zip"
    sidecar = root / f"{return_name}.zip.sha256"
    for target in (staging, zip_path, sidecar):
        if target.exists():
            raise MaxPoolRuntimeError(f"return target must be fresh: {target}")
    staging.mkdir()
    records: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []

    def add(
        source: Path, relative_value: str, role: str, required: bool = True
    ) -> None:
        relative = safe_relative(relative_value)
        if set(part.lower() for part in relative.parts) & FORBIDDEN_RETURN_PARTS:
            raise MaxPoolRuntimeError(f"forbidden return path: {relative}")
        if relative.suffix.lower() in FORBIDDEN_RETURN_SUFFIXES:
            raise MaxPoolRuntimeError(f"forbidden return suffix: {relative}")
        if (
            not source.is_file()
            or source.is_symlink()
            or source.stat().st_size > MAX_FILE_BYTES
        ):
            if required:
                missing.append({"path": relative.as_posix(), "role": role})
            return
        destination = inside(staging, relative.as_posix())
        destination.parent.mkdir(parents=True, exist_ok=True)
        source_resolved = source.resolve()
        destination_resolved = destination.resolve()
        if source_resolved != destination_resolved:
            if destination.exists():
                raise MaxPoolRuntimeError(
                    f"return destination collision: {destination}"
                )
            shutil.copyfile(source, destination)
        records.append(
            {
                "path": relative.as_posix(),
                "role": role,
                "size_bytes": destination.stat().st_size,
                "sha256": sha256(destination),
            }
        )

    add(package / MANIFEST_NAME, f"package/{MANIFEST_NAME}", "package_identity")
    for name in (
        "VERSION_UNBOUND_PROFILE.json",
        "package_preflight.json",
        "installed_preflight.json",
        "SERVER_RESULT_GATE.json",
        "server_command.txt",
        "compile_exit_status.txt",
        "sim_exit_status.txt",
        "run_exit_status.txt",
    ):
        add(evidence / name, f"evidence/{name}", "gate_or_receipt")
    add(
        evidence / "termination_signal.txt",
        "evidence/termination_signal.txt",
        "optional_signal",
        False,
    )
    cfg_root = root / "install" / "cfg_pkg" / install_name
    add(cfg_root / "sca_cfg.json", "config/sca_cfg.json", "runtime_sca")
    add(cfg_root / "sca_cfg_D.json", "config/sca_cfg_D.json", "runtime_sca_d")
    sca_d = load_json(cfg_root / "sca_cfg_D.json")
    for key, item in sca_d.items():
        add(
            inside(root, str(item["path"])),
            f"formal_readback/{key}.txt",
            "formal_readback",
            False,
        )
    for source_name, target_name in (
        ("compile_driver.log", "compile_driver_tail.log"),
        ("compile.log", "compile_tail.log"),
        ("sim.log", "sim_tail.log"),
    ):
        tail = staging / "logs" / target_name
        _copy_tail(run / "sim_results" / source_name, tail)
        add(tail, f"logs/{target_name}", "bounded_log_tail", False)
    gate_path = evidence / "SERVER_RESULT_GATE.json"
    gate = load_json(gate_path) if gate_path.is_file() else {}
    receipt = {
        "schema": "maxpool-node0002-original-json-return-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if not missing else "incomplete",
        "classification": gate.get("status", "RESULT_GATE_MISSING"),
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "install_name": install_name,
        "candidate_release": False,
        "counts_as_e4": False,
        "counts_as_e5": False,
        "server_source_identity_bound": False,
        "server_source_preflight_performed": False,
        "source_json_sha256": SOURCE_JSON_SHA256,
        "source_json_rewritten": False,
        "run_exit_status": run_status,
        "server_command": server_command,
        "allowlist_only": True,
        "required_missing": missing,
        "payload_file_count": len(records),
        "payload_size_bytes": sum(item["size_bytes"] for item in records),
        "files": sorted(records, key=lambda item: item["path"]),
    }
    write_json(staging / "RETURN_RECEIPT.json", receipt)
    extracted = sum(path.stat().st_size for path in staging.rglob("*") if path.is_file())
    if extracted > MAX_RETURN_EXTRACTED_BYTES:
        raise MaxPoolRuntimeError("return extracted size exceeds budget")
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
        raise MaxPoolRuntimeError("return ZIP exceeds budget")
    digest = sha256(zip_path)
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    return {
        **receipt,
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": sidecar.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    package = sub.add_parser("preflight-package")
    package.add_argument("--package-root", type=Path, required=True)
    package.add_argument("--install-name", required=True)
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
    analysis.add_argument("--evidence-root", type=Path, required=True)
    analysis.add_argument("--run-dir", type=Path, required=True)
    analysis.add_argument("--compile-status", type=int, required=True)
    analysis.add_argument("--sim-status", type=int, required=True)
    analysis.add_argument("--output", type=Path, required=True)
    collection = sub.add_parser("collect")
    collection.add_argument("--server-root", type=Path, required=True)
    collection.add_argument("--package-root", type=Path, required=True)
    collection.add_argument("--install-name", required=True)
    collection.add_argument("--evidence-root", type=Path, required=True)
    collection.add_argument("--run-dir", type=Path, required=True)
    collection.add_argument("--run-status", type=int, required=True)
    collection.add_argument("--server-command", required=True)
    args = parser.parse_args()
    try:
        if args.command == "preflight-package":
            report = preflight_package(args.package_root, args.install_name)
            write_json(args.output, report)
        elif args.command == "preflight-installed":
            report = preflight_installed(
                args.package_root, args.server_root, args.install_name
            )
            write_json(args.output, report)
        elif args.command == "analyze":
            report = analyze(
                args.server_root,
                args.package_root,
                args.install_name,
                args.evidence_root,
                args.run_dir,
                args.compile_status,
                args.sim_status,
            )
            write_json(args.output, report)
        else:
            report = collect(
                args.server_root,
                args.package_root,
                args.install_name,
                args.evidence_root,
                args.run_dir,
                args.run_status,
                args.server_command,
            )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"MaxPool original-JSON runtime failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
