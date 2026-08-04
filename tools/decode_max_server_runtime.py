#!/usr/bin/env python3
"""Server-side validation, adjudication, and compact return collection."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST_NAME = "TEST_PACKAGE_MANIFEST.json"
SCHEMA = "deepseek-decode-max-fp32-onecmd-runtime-v1"
RESULT_SCHEMA = "deepseek-decode-max-fp32-server-result-v1"
RETURN_SCHEMA = "deepseek-decode-max-fp32-server-return-v1"
MAX_TEXT_BYTES = 8 * 1024 * 1024
MAX_EXTRACTED_BYTES = 16 * 1024 * 1024
MAX_ZIP_BYTES = 8 * 1024 * 1024
FORBIDDEN_SUFFIXES = {
    ".zip",
    ".tar",
    ".tgz",
    ".gz",
    ".7z",
    ".vcd",
    ".fsdb",
    ".vpd",
    ".wlf",
}
FORBIDDEN_PARTS = {"build", "csrc", "simv.daidir", "wave", "waves"}


class DecodeMaxRuntimeError(RuntimeError):
    """Raised when a server-side gate fails closed."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: str) -> PurePosixPath:
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise DecodeMaxRuntimeError(f"unsafe relative path: {value!r}")
    return relative


def _inside(root: Path, relative: PurePosixPath) -> Path:
    base = root.resolve()
    target = base.joinpath(*relative.parts).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise DecodeMaxRuntimeError(f"path escapes root: {relative}") from exc
    return target


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _records(root: Path, *, exclude_manifest: bool = False) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == MANIFEST_NAME:
            continue
        records[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    return records


def _validate_128bit_text(path: Path, *, expected_lines: int | None = None) -> None:
    raw = path.read_bytes()
    if b"\r" in raw:
        raise DecodeMaxRuntimeError(f"128-bit text contains CR: {path}")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeError as exc:
        raise DecodeMaxRuntimeError(f"128-bit text is not ASCII: {path}") from exc
    if expected_lines is not None and len(lines) != expected_lines:
        raise DecodeMaxRuntimeError(
            f"128-bit line count differs for {path}: {len(lines)} != {expected_lines}"
        )
    if not lines or any(len(line) != 128 or set(line) - {"0", "1"} for line in lines):
        raise DecodeMaxRuntimeError(f"invalid 128-bit text: {path}")
    if raw != ("\n".join(lines) + "\n").encode("ascii"):
        raise DecodeMaxRuntimeError(f"128-bit text is not LF-canonical: {path}")


def _load_manifest(package: Path, install_name: str) -> dict[str, Any]:
    manifest_path = package / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("install_name") != install_name:
        raise DecodeMaxRuntimeError("install name differs from package manifest")
    expected = manifest.get("files")
    actual = _records(package, exclude_manifest=True)
    if expected != actual:
        raise DecodeMaxRuntimeError("package payload differs from manifest exact set")
    return manifest


def _indexed_readbacks(sca_d: dict[str, Any]) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for name, entry in sca_d.items():
        match = re.fullmatch(r"op10_matrixD_slice(\d+)", name)
        if not match or not isinstance(entry, dict):
            raise DecodeMaxRuntimeError(f"unexpected SCA_D entry: {name}")
        slice_id = int(match.group(1))
        if slice_id in indexed:
            raise DecodeMaxRuntimeError(f"duplicate SCA_D slice: {slice_id}")
        indexed[slice_id] = entry
    if set(indexed) != set(range(28)):
        raise DecodeMaxRuntimeError("SCA_D must cover numeric slices 0..27")
    return indexed


def preflight_package(package_root: Path, install_name: str) -> dict[str, Any]:
    package = package_root.resolve()
    manifest = _load_manifest(package, install_name)
    workload = package / "workload"
    sca_path = workload / "sca_cfg.json"
    sca_d_path = workload / "sca_cfg_D.json"
    sca = json.loads(sca_path.read_text(encoding="utf-8"))
    sca_d = json.loads(sca_d_path.read_text(encoding="utf-8"))
    for path, value in ((sca_path, sca), (sca_d_path, sca_d)):
        canonical = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        if path.read_text(encoding="utf-8") != canonical:
            raise DecodeMaxRuntimeError(f"config is not pretty canonical JSON: {path}")
    if sca.get("Repeat_Num") != 1:
        raise DecodeMaxRuntimeError("Repeat_Num must equal the one Start_Comp")
    prefix = PurePosixPath("install", "cfg_pkg", install_name)
    exec_entry = sca.get("ExecutionPlan", {})
    exec_relative = _safe_relative(exec_entry.get("path", ""))
    if exec_relative.parts[: len(prefix.parts)] != prefix.parts:
        raise DecodeMaxRuntimeError("execution plan path is outside namespace")
    exec_local = workload.joinpath(*exec_relative.parts[len(prefix.parts) :])
    _validate_128bit_text(exec_local, expected_lines=29)
    if sca.get("Exec_Length") != 29:
        raise DecodeMaxRuntimeError("Exec_Length must equal 29 128-bit rows")
    payload_count = 0
    for name, entry in sca.items():
        if not isinstance(entry, dict) or "path" not in entry:
            continue
        relative = _safe_relative(entry["path"])
        if relative.parts[: len(prefix.parts)] != prefix.parts:
            raise DecodeMaxRuntimeError(f"SCA path escapes namespace: {name}")
        local = workload.joinpath(*relative.parts[len(prefix.parts) :])
        if not local.is_file():
            raise DecodeMaxRuntimeError(f"SCA payload missing: {name}")
        if local.suffix.lower() in {".txt", ".bin"}:
            _validate_128bit_text(local)
        payload_count += 1
    if payload_count != 30:
        raise DecodeMaxRuntimeError(f"expected 30 preload payloads, got {payload_count}")
    indexed = _indexed_readbacks(sca_d)
    for slice_id, entry in indexed.items():
        if set(entry) != {"base_addr", "path", "length"} or entry["length"] != 1:
            raise DecodeMaxRuntimeError(
                f"slice{slice_id:02d} SCA_D requires base_addr/path/length=1"
            )
        relative = _safe_relative(entry["path"])
        if relative.parts[: len(prefix.parts)] != prefix.parts:
            raise DecodeMaxRuntimeError("SCA_D path escapes namespace")
        readback_local = workload.joinpath(*relative.parts[len(prefix.parts) :])
        if readback_local.exists():
            raise DecodeMaxRuntimeError("formal readback target must be fresh")
        _validate_128bit_text(
            workload / f"golden/slice{slice_id:02d}/matrix_D_128bit.txt",
            expected_lines=1,
        )
    return {
        "schema": SCHEMA,
        "status": "package_preflight_passed",
        "install_name": install_name,
        "candidate_release": False,
        "evidence_level": manifest.get("evidence_level"),
        "payload_count": payload_count,
        "readback_count": len(indexed),
        "exec_length": sca["Exec_Length"],
        "repeat_num": sca["Repeat_Num"],
    }


def preflight_installed(
    package_root: Path, ndp_root: Path, install_name: str
) -> dict[str, Any]:
    package_report = preflight_package(package_root, install_name)
    source = package_root.resolve() / "workload"
    installed = ndp_root.resolve() / "install" / "cfg_pkg" / install_name
    if not installed.is_dir() or _records(source) != _records(installed):
        raise DecodeMaxRuntimeError("installed workload differs byte-for-byte")
    return {
        **package_report,
        "status": "installed_preflight_passed",
        "installed_workload_sha256": hashlib.sha256(
            json.dumps(_records(installed), sort_keys=True).encode()
        ).hexdigest(),
    }


def _simulation_log_gate(
    ndp_root: Path, install_name: str
) -> tuple[dict[str, Any], str]:
    sim_log = ndp_root.resolve() / f"run_{install_name}/sim_results/sim.log"
    text = (
        sim_log.read_text(encoding="utf-8", errors="replace")
        if sim_log.is_file()
        else ""
    )
    expected_sca = f"install/cfg_pkg/{install_name}/sca_cfg.json"
    expected_sca_d = f"install/cfg_pkg/{install_name}/sca_cfg_D.json"
    checks = {
        "sim_log_exists": sim_log.is_file(),
        "sca_echo_exact": text.count(f"Using SCA cfg file: {expected_sca}") == 1,
        "sca_d_echo_exact": text.count(f"Using SCA cfg D file: {expected_sca_d}") == 1,
        "preload_count_exact": bool(
            re.search(r"JSON config:\s*30\s+matrices loaded", text)
        ),
        "formal_dump_count_exact": bool(
            re.search(r"JSON_D config:\s*28\s+matrices dumped", text)
        ),
        "single_start": len(re.findall(r"INFO: slice start", text)) == 1,
        "single_completion": len(
            re.findall(r"INFO: slice completed after\s+\d+\s+cycles", text)
        )
        == 1,
        "natural_completion_marker": "Simulation completed successfully!" in text,
        "no_cannot_open": "Cannot open" not in text,
        "no_skip_matrix_readback": "skip matrix readback" not in text,
        "no_softmax_default": "sca_cfg_D_softmax.json" not in text,
    }
    return (
        {
            "status": "pass" if all(checks.values()) else "fail",
            "sim_log": sim_log.as_posix(),
            "expected_sca": expected_sca,
            "expected_sca_d": expected_sca_d,
            **checks,
        },
        text,
    )


def _formal_d_gate(
    ndp_root: Path, package_root: Path, install_name: str
) -> dict[str, Any]:
    root = ndp_root.resolve()
    package = package_root.resolve()
    cfg_root = root / "install" / "cfg_pkg" / install_name
    sca_d = json.loads((cfg_root / "sca_cfg_D.json").read_text(encoding="utf-8"))
    indexed = _indexed_readbacks(sca_d)
    entries: list[dict[str, Any]] = []
    all_pass = True
    for slice_id, entry in sorted(indexed.items()):
        actual = _inside(root, _safe_relative(entry["path"]))
        golden = package / f"workload/golden/slice{slice_id:02d}/matrix_D_128bit.txt"
        valid = False
        if actual.is_file():
            try:
                _validate_128bit_text(actual, expected_lines=1)
                valid = actual.stat().st_size == 129
            except DecodeMaxRuntimeError:
                valid = False
        matched = valid and actual.read_bytes() == golden.read_bytes()
        all_pass = all_pass and matched
        entries.append(
            {
                "slice": slice_id,
                "path": entry["path"],
                "exists": actual.is_file(),
                "size_bytes": actual.stat().st_size if actual.is_file() else None,
                "lf_only_exact_size": valid,
                "actual_sha256": _sha256(actual) if actual.is_file() else None,
                "golden_sha256": _sha256(golden),
                "full_128bit_line_matches_golden": matched,
                "status": "pass" if matched else "fail",
            }
        )
    return {
        "status": "pass" if all_pass else "fail",
        "slice_count": len(entries),
        "all_28_full_128bit_lines_match": all_pass,
        "entries": entries,
    }


def analyze_server_result(
    *,
    ndp_root: Path,
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_status: int,
) -> dict[str, Any]:
    log_gate, _ = _simulation_log_gate(ndp_root, install_name)
    formal_d = _formal_d_gate(ndp_root, package_root, install_name)
    receipt_path = evidence_root.resolve() / "stock_rtl_identity_receipt.json"
    receipt = (
        json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt_path.is_file()
        else {}
    )
    rtl_identity = (
        receipt.get("status") == "rtl_unchanged"
        and receipt.get("functional_rtl_unchanged") is True
    )
    passed = (
        run_status == 0
        and log_gate["status"] == "pass"
        and formal_d["status"] == "pass"
        and rtl_identity
    )
    return {
        "schema": RESULT_SCHEMA,
        "status": "server_e4_pass" if passed else "server_failure_or_incomplete",
        "install_name": install_name,
        "candidate_release": False,
        "release_gate_passed": False,
        "evidence_level": "E4_SERVER_NUMERIC" if passed else "SERVER_INCOMPLETE",
        "run_exit_status": run_status,
        "scope": (
            "DeepSeek Decode FP32 reduction max control only; this does not "
            "exercise ResNet INT8 MaxPool or clear its RTL blocker"
        ),
        "gates": {
            "simulation_loader_and_completion": log_gate,
            "formal_d_readback": formal_d,
            "stock_rtl_identity": {
                "status": "pass" if rtl_identity else "fail",
                "functional_rtl_unchanged": rtl_identity,
            },
        },
        "remaining_release_gates": [
            "independent repeated E5 server run",
            "ResNet INT8 MaxPool remains orthogonal and blocked",
        ],
    }


def _forbidden_return(relative: PurePosixPath) -> str | None:
    lower_parts = {part.lower() for part in relative.parts}
    forbidden_parts = sorted(lower_parts & FORBIDDEN_PARTS)
    if forbidden_parts:
        return f"forbidden directory: {forbidden_parts[0]}"
    if relative.suffix.lower() in FORBIDDEN_SUFFIXES:
        return f"forbidden suffix: {relative.suffix.lower()}"
    return None


def collect_return(
    *,
    ndp_root: Path,
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_dir: Path,
    output_dir: Path,
    run_status: int,
    server_command: str,
) -> dict[str, Any]:
    root = ndp_root.resolve()
    package = package_root.resolve()
    evidence = evidence_root.resolve()
    run = run_dir.resolve()
    output = output_dir.resolve()
    return_name = f"{install_name}_return"
    staging = output / return_name
    zip_path = output / f"{return_name}.zip"
    sha_path = output / f"{return_name}.zip.sha256"
    for target in (staging, zip_path, sha_path):
        if target.exists():
            raise DecodeMaxRuntimeError(f"return target must be fresh: {target}")
    staging.mkdir(parents=True)
    records: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []

    def add(source: Path, relative_value: str, role: str, required: bool = True) -> None:
        relative = _safe_relative(relative_value)
        reason = _forbidden_return(relative)
        if reason:
            raise DecodeMaxRuntimeError(f"{relative}: {reason}")
        if not source.is_file():
            if required:
                missing.append({"path": relative.as_posix(), "role": role})
            return
        size = source.stat().st_size
        if size > MAX_TEXT_BYTES:
            if required:
                missing.append({"path": relative.as_posix(), "role": role})
            return
        destination = _inside(staging, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        records.append(
            {
                "path": relative.as_posix(),
                "role": role,
                "size_bytes": size,
                "sha256": _sha256(destination),
            }
        )

    add(package / MANIFEST_NAME, f"package/{MANIFEST_NAME}", "package_identity")
    for name in (
        "package_preflight.json",
        "installed_preflight.json",
        "server_identity_pre_install.json",
        "server_identity_post_install.json",
        "server_identity_post_run.json",
        "server_identity_post_restore.json",
        "stock_rtl_identity_receipt.json",
        "server_command.txt",
        "run_started_epoch.txt",
        "compile_exit_status.txt",
        "sim_exit_status.txt",
        "run_exit_status.txt",
        "SERVER_RESULT_GATE.json",
    ):
        add(evidence / name, f"evidence/{name}", "run_and_identity_evidence")
    add(run / "sim_results/compile.log", "logs/compile.log", "compile_log")
    add(run / "sim_results/sim.log", "logs/sim.log", "simulation_log")
    cfg_root = root / "install" / "cfg_pkg" / install_name
    add(cfg_root / "sca_cfg.json", "config/sca_cfg.json", "runtime_sca")
    add(cfg_root / "sca_cfg_D.json", "config/sca_cfg_D.json", "runtime_sca_d")
    sca_d = json.loads((cfg_root / "sca_cfg_D.json").read_text(encoding="utf-8"))
    for slice_id, entry in sorted(_indexed_readbacks(sca_d).items()):
        add(
            _inside(root, _safe_relative(entry["path"])),
            f"readback/slice{slice_id:02d}/matrix_D_128bit.txt",
            "formal_d_readback",
        )
    manifest = {
        "schema": RETURN_SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if not missing else "incomplete",
        "install_name": install_name,
        "candidate_release": False,
        "run_exit_status": run_status,
        "server_command": server_command,
        "allowlist_only": True,
        "waveforms_included": False,
        "build_tree_included": False,
        "nested_archive_included": False,
        "required_missing": missing,
        "payload_file_count": len(records),
        "payload_size_bytes": sum(item["size_bytes"] for item in records),
        "files": sorted(records, key=lambda item: item["path"]),
    }
    _write_json(staging / "RETURN_MANIFEST.json", manifest)
    extracted = sum(path.stat().st_size for path in staging.rglob("*") if path.is_file())
    if extracted > MAX_EXTRACTED_BYTES:
        raise DecodeMaxRuntimeError("return extracted size exceeds budget")
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
    if zip_path.stat().st_size > MAX_ZIP_BYTES:
        raise DecodeMaxRuntimeError("return ZIP exceeds budget")
    digest = _sha256(zip_path)
    sha_path.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n")
    return {
        **manifest,
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sha256_file": sha_path.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    package_parser = subparsers.add_parser("preflight-package")
    package_parser.add_argument("--package-root", type=Path, required=True)
    package_parser.add_argument("--install-name", required=True)
    package_parser.add_argument("--output", type=Path)
    installed_parser = subparsers.add_parser("preflight-installed")
    installed_parser.add_argument("--package-root", type=Path, required=True)
    installed_parser.add_argument("--ndp-root", type=Path, required=True)
    installed_parser.add_argument("--install-name", required=True)
    installed_parser.add_argument("--output", type=Path)
    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--ndp-root", type=Path, required=True)
    analyze_parser.add_argument("--package-root", type=Path, required=True)
    analyze_parser.add_argument("--install-name", required=True)
    analyze_parser.add_argument("--evidence-root", type=Path, required=True)
    analyze_parser.add_argument("--run-status", type=int, required=True)
    analyze_parser.add_argument("--output", type=Path, required=True)
    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--ndp-root", type=Path, required=True)
    collect_parser.add_argument("--package-root", type=Path, required=True)
    collect_parser.add_argument("--install-name", required=True)
    collect_parser.add_argument("--evidence-root", type=Path, required=True)
    collect_parser.add_argument("--run-dir", type=Path, required=True)
    collect_parser.add_argument("--output-dir", type=Path, required=True)
    collect_parser.add_argument("--run-status", type=int, required=True)
    collect_parser.add_argument("--server-command", required=True)
    args = parser.parse_args()
    try:
        if args.command == "preflight-package":
            report = preflight_package(args.package_root, args.install_name)
        elif args.command == "preflight-installed":
            report = preflight_installed(
                args.package_root, args.ndp_root, args.install_name
            )
        elif args.command == "analyze":
            report = analyze_server_result(
                ndp_root=args.ndp_root,
                package_root=args.package_root,
                install_name=args.install_name,
                evidence_root=args.evidence_root,
                run_status=args.run_status,
            )
        else:
            report = collect_return(
                ndp_root=args.ndp_root,
                package_root=args.package_root,
                install_name=args.install_name,
                evidence_root=args.evidence_root,
                run_dir=args.run_dir,
                output_dir=args.output_dir,
                run_status=args.run_status,
                server_command=args.server_command,
            )
        output = getattr(args, "output", None)
        if output is not None:
            _write_json(output, report)
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"decode-max runtime failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
