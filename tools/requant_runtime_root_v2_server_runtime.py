#!/usr/bin/env python3
"""Version-unbound runtime for the Requant guard-only event-edge diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True

try:
    import requant_atomic_server_runtime as event_runtime
except ModuleNotFoundError:
    from tools import requant_guard_eventedge_server_runtime as event_runtime


PROFILE_RULE = "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001"
TB_RELATIVE = "native_return_observer.svh"
MAX_FILE = 768 * 1024
MAX_EXTRACTED = 6 * 1024 * 1024
MAX_ZIP = 3 * 1024 * 1024
FORBIDDEN_PARTS = {"build", "csrc", "simv.daidir", "waves", "wave"}
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


class RuntimeRootError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_relative(value: str) -> PurePosixPath:
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise RuntimeRootError(f"unsafe relative path: {value!r}")
    return relative


def inside(root: Path, value: str) -> Path:
    base = root.resolve()
    relative = safe_relative(value)
    target = base.joinpath(*relative.parts).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise RuntimeRootError(f"path escapes root: {value}") from exc
    return target


def resolve_user_root(value: Path) -> Path:
    if not value.is_absolute():
        raise RuntimeRootError("user-supplied server root must be absolute")
    root = value.resolve(strict=True)
    if not root.is_dir() or not os.access(root, os.X_OK):
        raise RuntimeRootError("user-supplied server root is not enterable")
    return root


def observer_target(root_value: Path) -> tuple[Path, Path]:
    root = resolve_user_root(root_value)
    literal = root / TB_RELATIVE
    if literal.is_symlink():
        raise RuntimeRootError("observer target symlink is forbidden")
    target = literal.resolve(strict=True)
    if target != literal or target.parent != root or not target.is_file():
        raise RuntimeRootError("observer target is not the exact root-local file")
    return root, target


def preflight_package(
    package_root: Path, install_name: str
) -> dict[str, Any]:
    report = event_runtime.base.preflight_package(package_root, install_name)
    manifest = load_json(package_root.resolve() / "TEST_PACKAGE_MANIFEST.json")
    boundary = manifest.get("version_unbound_compatibility", {})
    if (
        PROFILE_RULE not in manifest.get("rule_ids", [])
        or boundary.get("server_source_identity_bound") is not False
        or boundary.get("counts_as_e4") is not False
        or boundary.get("counts_as_e5") is not False
        or boundary.get("accepted_root_basename") != "any"
        or boundary.get("only_preexisting_server_file_touched")
        != TB_RELATIVE
    ):
        raise RuntimeRootError("version-unbound compatibility boundary differs")
    return {
        **report,
        "status": "package_preflight_passed_version_unbound",
        "version_unbound_diagnostic_only": True,
        "server_source_preflight_performed": False,
        "server_source_identity_captured": False,
        "rule_id": PROFILE_RULE,
    }


def preflight_installed(
    package_root: Path, root_value: Path, install_name: str
) -> dict[str, Any]:
    root = resolve_user_root(root_value)
    report = event_runtime.base.preflight_installed(
        package_root, root, install_name
    )
    return {
        **report,
        "status": "installed_preflight_passed_version_unbound",
        "server_source_preflight_performed": False,
        "server_source_identity_captured": False,
    }


def install_probe(
    root_value: Path, package_root: Path, evidence_root: Path
) -> dict[str, Any]:
    root, target = observer_target(root_value)
    evidence = evidence_root.resolve()
    tail = (
        package_root.resolve()
        / "tb_probe/requant_mse4_guard_observer_tail.svh"
    )
    backup = evidence / "native_return_observer.preimage"
    receipt_path = evidence / "tb_probe_install_receipt.json"
    if not tail.is_file() or backup.exists() or receipt_path.exists():
        raise RuntimeRootError("observer install precondition failed")
    original = target.read_bytes()
    tail_bytes = tail.read_bytes()
    installed = original + (b"" if original.endswith(b"\n") else b"\n") + tail_bytes
    backup.write_bytes(original)
    target.write_bytes(installed)
    receipt = {
        "schema": "requant-runtime-root-v2-observer-transaction-v1",
        "status": "installed_for_compile_only",
        "rule_ids": [
            PROFILE_RULE,
            "CDA-SERVER-TB-TARGET-DIRECTORY-ISOLATION-001",
        ],
        "root_argument_was_absolute": True,
        "root_basename_checked": False,
        "server_source_scan_performed": False,
        "target_relative_path": TB_RELATIVE,
        "target_absolute_path": target.as_posix(),
        "candidate_write_path_count": 1,
        "same_named_file_scan_performed": False,
        "read_only_non_driving": True,
        "functional_rtl_modified": False,
        "preimage_size_bytes": len(original),
        "preimage_sha256": sha256_bytes(original),
        "tail_size_bytes": len(tail_bytes),
        "tail_sha256": sha256_bytes(tail_bytes),
        "installed_size_bytes": len(installed),
        "installed_sha256": sha256_bytes(installed),
        "restored": False,
    }
    write_json(receipt_path, receipt)
    return receipt


def verify_probe(root_value: Path, evidence_root: Path) -> dict[str, Any]:
    _, target = observer_target(root_value)
    evidence = evidence_root.resolve()
    backup = evidence / "native_return_observer.preimage"
    receipt = load_json(evidence / "tb_probe_install_receipt.json")
    if (
        receipt.get("status") != "installed_for_compile_only"
        or receipt.get("target_absolute_path") != target.as_posix()
        or not backup.is_file()
        or sha256(target) != receipt.get("installed_sha256")
        or sha256(backup) != receipt.get("preimage_sha256")
    ):
        raise RuntimeRootError("observer installed/backup identity differs")
    return {
        "schema": "requant-runtime-root-v2-observer-precompile-v1",
        "status": "installed_observer_verified_for_compile",
        "target_absolute_path": target.as_posix(),
        "target_sha256": sha256(target),
        "backup_sha256": sha256(backup),
        "server_source_scan_performed": False,
        "passed": True,
    }


def restore_probe(root_value: Path, evidence_root: Path) -> dict[str, Any]:
    _, target = observer_target(root_value)
    evidence = evidence_root.resolve()
    backup = evidence / "native_return_observer.preimage"
    receipt_path = evidence / "tb_probe_install_receipt.json"
    receipt = load_json(receipt_path)
    if (
        not backup.is_file()
        or receipt.get("target_absolute_path") != target.as_posix()
        or sha256(target) != receipt.get("installed_sha256")
        or sha256(backup) != receipt.get("preimage_sha256")
    ):
        raise RuntimeRootError("observer restore precondition differs")
    original = backup.read_bytes()
    target.write_bytes(original)
    if sha256(target) != receipt["preimage_sha256"]:
        raise RuntimeRootError("observer byte-exact restore failed")
    receipt["status"] = "restored_byte_exact"
    receipt["restored"] = True
    receipt["restored_sha256"] = sha256(target)
    write_json(receipt_path, receipt)
    return receipt


def analyze(
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_dir: Path,
    run_status: int,
) -> dict[str, Any]:
    report = event_runtime.base.analyze(
        package_root, install_name, evidence_root, run_dir, run_status
    )
    gates = report.setdefault("gates", {})
    gates.pop("stock_rtl_and_transactional_observer_identity", None)
    gates["server_source_compatibility_profile"] = {
        "status": "intentionally_unbound",
        "rule_id": PROFILE_RULE,
        "server_source_preflight_performed": False,
        "server_source_identity_captured": False,
        "observer_restore_receipt_required": True,
    }
    report.update(
        {
            "schema": "requant-guard-eventedge-version-unbound-result-v2",
            "status": "VERSION_UNBOUND_DIAGNOSTIC_ONLY",
            "version_unbound_diagnostic_only": True,
            "candidate_release": False,
            "counts_as_node0001_e4": False,
            "counts_as_node0001_e5": False,
            "formal_target_instance_allowed": False,
            "release_gate_passed": False,
            "underlying_diagnostic_status": report.get("status"),
        }
    )
    return report


def copy_tail(source: Path, destination: Path, limit: int = 180_000) -> None:
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes()[-limit:])


def collect(
    root_value: Path,
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_dir: Path,
    run_status: int,
    server_command: str,
) -> dict[str, Any]:
    root = resolve_user_root(root_value)
    package = package_root.resolve()
    evidence = evidence_root.resolve()
    run = run_dir.resolve()
    return_name = f"{install_name}_return"
    staging = root / return_name
    zip_path = root / f"{return_name}.zip"
    sidecar = root / f"{return_name}.zip.sha256"
    for target in (staging, zip_path, sidecar):
        if target.exists():
            raise RuntimeRootError(f"return target must be fresh: {target}")
    staging.mkdir()
    records: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []

    def add(source: Path, relative_value: str, role: str, required: bool = True) -> None:
        relative = safe_relative(relative_value)
        if set(part.lower() for part in relative.parts) & FORBIDDEN_PARTS:
            raise RuntimeRootError(f"forbidden return path: {relative}")
        if relative.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise RuntimeRootError(f"forbidden return suffix: {relative}")
        if not source.is_file() or source.stat().st_size > MAX_FILE:
            if required:
                missing.append({"path": relative.as_posix(), "role": role})
            return
        destination = inside(staging, relative.as_posix())
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        records.append(
            {
                "path": relative.as_posix(),
                "role": role,
                "size_bytes": destination.stat().st_size,
                "sha256": sha256(destination),
            }
        )

    add(
        package / "TEST_PACKAGE_MANIFEST.json",
        "package/TEST_PACKAGE_MANIFEST.json",
        "package_identity",
    )
    required_evidence = (
        "package_preflight.json",
        "installed_preflight.json",
        "tb_probe_install_receipt.json",
        "tb_probe_precompile_receipt.json",
        "VERSION_UNBOUND_PROFILE.json",
        "LIFECYCLE_RECEIPT.json",
        "MSE4_WRITE_OBSERVER_RECEIPT.json",
        "FORMAL_READBACK_RECEIPT.json",
        "FIRST_DIVERGENCE_ROUTING.json",
        "SERVER_RESULT_GATE.json",
        "server_command.txt",
        "compile_exit_status.txt",
        "sim_exit_status.txt",
        "run_exit_status.txt",
    )
    for name in required_evidence:
        add(evidence / name, f"evidence/{name}", "gate_or_receipt")
    for name in ("termination_signal.txt", "GUARD_PATH_CHECKPOINT_RECEIPT.json"):
        add(evidence / name, f"evidence/{name}", "optional_diagnostic", False)
    add(
        root / f"install/cfg_pkg/{install_name}/sca_cfg.json",
        "config/sca_cfg.json",
        "runtime_sca",
    )
    add(
        root / f"install/cfg_pkg/{install_name}/sca_cfg_D.json",
        "config/sca_cfg_D.json",
        "runtime_sca_d",
    )
    profile = load_json(package / "validation/diagnostic_profile.json")
    for slice_id in (0, 1):
        add(
            run
            / "sim_results"
            / profile["observer_log_dir"]
            / f"slice{slice_id:02d}.log",
            f"raw_observer/slice{slice_id:02d}.log",
            "qualified_observer",
            False,
        )
    sca_d = load_json(package / "workload/runtime/sca_cfg_D.json")
    for name, item in sca_d.items():
        add(
            inside(run, item["path"]),
            f"raw_formal_readback/{name}.txt",
            "formal_readback",
            False,
        )
    for source_name, target_name in (
        ("compile.log", "compile_tail.log"),
        ("compile_driver.log", "compile_driver_tail.log"),
        ("sim.log", "sim_tail.log"),
    ):
        copy_tail(
            run / "sim_results" / source_name,
            staging / "logs" / target_name,
        )
        add(
            staging / "logs" / target_name,
            f"logs/{target_name}",
            "bounded_log_tail",
            False,
        )
    gate_path = evidence / "SERVER_RESULT_GATE.json"
    gate = load_json(gate_path) if gate_path.is_file() else {}
    receipt = {
        "schema": "requant-guard-eventedge-version-unbound-return-v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if not missing else "incomplete",
        "classification": "VERSION_UNBOUND_DIAGNOSTIC_ONLY",
        "underlying_result_status": gate.get("status", "missing"),
        "install_name": install_name,
        "candidate_release": False,
        "counts_as_node0001_e4": False,
        "counts_as_node0001_e5": False,
        "server_source_identity_bound": False,
        "server_source_preflight_performed": False,
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
    if extracted > MAX_EXTRACTED:
        raise RuntimeRootError("return extracted size exceeds budget")
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
    if zip_path.stat().st_size > MAX_ZIP:
        raise RuntimeRootError("return ZIP exceeds budget")
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
    install = sub.add_parser("install-probe")
    install.add_argument("--server-root", type=Path, required=True)
    install.add_argument("--package-root", type=Path, required=True)
    install.add_argument("--evidence-root", type=Path, required=True)
    verify = sub.add_parser("verify-probe")
    verify.add_argument("--server-root", type=Path, required=True)
    verify.add_argument("--evidence-root", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)
    restore = sub.add_parser("restore-probe")
    restore.add_argument("--server-root", type=Path, required=True)
    restore.add_argument("--evidence-root", type=Path, required=True)
    analyze_parser = sub.add_parser("analyze")
    analyze_parser.add_argument("--package-root", type=Path, required=True)
    analyze_parser.add_argument("--install-name", required=True)
    analyze_parser.add_argument("--evidence-root", type=Path, required=True)
    analyze_parser.add_argument("--run-dir", type=Path, required=True)
    analyze_parser.add_argument("--run-status", type=int, required=True)
    analyze_parser.add_argument("--output", type=Path, required=True)
    collect_parser = sub.add_parser("collect")
    collect_parser.add_argument("--server-root", type=Path, required=True)
    collect_parser.add_argument("--package-root", type=Path, required=True)
    collect_parser.add_argument("--install-name", required=True)
    collect_parser.add_argument("--evidence-root", type=Path, required=True)
    collect_parser.add_argument("--run-dir", type=Path, required=True)
    collect_parser.add_argument("--run-status", type=int, required=True)
    collect_parser.add_argument("--server-command", required=True)
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
        elif args.command == "install-probe":
            report = install_probe(
                args.server_root, args.package_root, args.evidence_root
            )
        elif args.command == "verify-probe":
            report = verify_probe(args.server_root, args.evidence_root)
            write_json(args.output, report)
        elif args.command == "restore-probe":
            report = restore_probe(args.server_root, args.evidence_root)
        elif args.command == "analyze":
            report = analyze(
                args.package_root,
                args.install_name,
                args.evidence_root,
                args.run_dir,
                args.run_status,
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
        print(f"Requant runtime-root v2 failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
