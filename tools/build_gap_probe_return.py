#!/usr/bin/env python3
"""Build and validate a bounded allowlist-only GAP probe return ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA = "resnet50-gap-probe-return-v1"
MAX_ZIP_BYTES = 16 * 1024 * 1024
MAX_EXTRACTED_BYTES = 32 * 1024 * 1024
MAX_TEXT_BYTES = 8 * 1024 * 1024
FORBIDDEN_SUFFIXES = {
    ".fsdb",
    ".vcd",
    ".vpd",
    ".fst",
    ".wlf",
    ".shm",
    ".tar",
    ".gz",
    ".tgz",
    ".7z",
}
FORBIDDEN_PARTS = {
    "csrc",
    "simv.daidir",
    "work",
    "archive",
    "__pycache__",
}
TEXT_SUFFIXES = {".json", ".log", ".txt", ".cfg", ".md"}


class GapProbeReturnError(ValueError):
    """Raised when a bounded return cannot be built safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: str) -> PurePosixPath:
    relative = PurePosixPath(value.replace("\\", "/"))
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise GapProbeReturnError(f"unsafe relative path: {value!r}")
    return relative


def _inside(root: Path, relative: PurePosixPath) -> Path:
    resolved_root = root.resolve()
    candidate = resolved_root.joinpath(*relative.parts).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise GapProbeReturnError(
            f"path escapes root {resolved_root}: {relative}"
        ) from exc
    return candidate


def _forbidden(relative: PurePosixPath) -> str | None:
    lower_parts = {part.lower() for part in relative.parts}
    forbidden_parts = sorted(lower_parts & FORBIDDEN_PARTS)
    if forbidden_parts:
        return f"forbidden directory: {forbidden_parts[0]}"
    if relative.suffix.lower() in FORBIDDEN_SUFFIXES:
        return f"forbidden suffix: {relative.suffix.lower()}"
    if relative.suffix.lower() == ".zip":
        return "nested ZIP is forbidden"
    return None


def _copy_allowlisted(
    *,
    source: Path,
    staging: Path,
    relative: PurePosixPath,
    role: str,
    required: bool,
    records: list[dict[str, Any]],
    missing: list[dict[str, str]],
    skipped: list[dict[str, Any]],
) -> None:
    reason = _forbidden(relative)
    if reason is not None:
        raise GapProbeReturnError(f"{relative}: {reason}")
    if not source.is_file():
        if required:
            missing.append(
                {
                    "path": relative.as_posix(),
                    "source": source.as_posix(),
                    "role": role,
                }
            )
        return
    size = source.stat().st_size
    if relative.suffix.lower() in TEXT_SUFFIXES and size > MAX_TEXT_BYTES:
        skipped.append(
            {
                "path": relative.as_posix(),
                "source": source.as_posix(),
                "role": role,
                "size_bytes": size,
                "reason": "individual_text_budget_exceeded",
            }
        )
        if required:
            missing.append(
                {
                    "path": relative.as_posix(),
                    "source": source.as_posix(),
                    "role": role,
                }
            )
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


def _first_file(candidates: list[Path]) -> Path:
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _readback_paths(sca_d_path: Path) -> list[PurePosixPath]:
    try:
        document = json.loads(sca_d_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GapProbeReturnError(f"cannot parse SCA_D: {sca_d_path}: {exc}") from exc
    if not isinstance(document, dict) or not document:
        raise GapProbeReturnError("SCA_D must be a non-empty JSON object")
    paths: list[PurePosixPath] = []
    for key, value in sorted(document.items()):
        if not isinstance(value, dict) or not isinstance(value.get("path"), str):
            raise GapProbeReturnError(f"invalid SCA_D entry: {key}")
        paths.append(_safe_relative(value["path"]))
    if len(paths) != len(set(paths)):
        raise GapProbeReturnError("SCA_D contains duplicate readback paths")
    return paths


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_zip(staging: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in staging.rglob("*") if item.is_file()):
            relative = f"{staging.name}/{path.relative_to(staging).as_posix()}"
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            compression = (
                zipfile.ZIP_STORED
                if path.name == "RETURN_MANIFEST.json"
                else zipfile.ZIP_DEFLATED
            )
            info.compress_type = compression
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=compression,
                compresslevel=9,
            )


def _audit_zip(
    *,
    staging: Path,
    zip_path: Path,
    expected_root: str,
) -> dict[str, Any]:
    expected = {
        f"{expected_root}/{path.relative_to(staging).as_posix()}": _sha256(path)
        for path in staging.rglob("*")
        if path.is_file()
    }
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise GapProbeReturnError("return ZIP contains duplicate names")
        if set(names) != set(expected):
            raise GapProbeReturnError("return ZIP exact file set differs")
        for name in names:
            relative = _safe_relative(name)
            if relative.parts[0] != expected_root:
                raise GapProbeReturnError(f"unexpected ZIP root: {name}")
            payload_relative = PurePosixPath(*relative.parts[1:])
            reason = _forbidden(payload_relative)
            if reason is not None:
                raise GapProbeReturnError(f"{name}: {reason}")
            actual_hash = hashlib.sha256(archive.read(name)).hexdigest()
            if actual_hash != expected[name]:
                raise GapProbeReturnError(f"return ZIP payload differs: {name}")
    return {
        "entry_count": len(expected),
        "exact_file_set": True,
        "single_root": expected_root,
        "forbidden_entry_count": 0,
    }


def build_return(
    *,
    ndp_root: Path,
    run_dir: Path,
    evidence_root: Path,
    package_root: Path,
    install_name: str,
    output_dir: Path,
    run_status: int,
    server_command: str,
) -> dict[str, Any]:
    root = ndp_root.resolve()
    run = run_dir.resolve()
    evidence = evidence_root.resolve()
    package = package_root.resolve()
    output = output_dir.resolve()
    for directory, label in (
        (root, "NDP root"),
        (run, "run directory"),
        (evidence, "evidence directory"),
        (package, "test-package root"),
    ):
        if not directory.is_dir():
            raise GapProbeReturnError(f"missing {label}: {directory}")

    return_name = f"{install_name}_return"
    staging = output / return_name
    zip_path = output / f"{return_name}.zip"
    sha_path = output / f"{return_name}.zip.sha256"
    for target in (staging, zip_path, sha_path):
        if target.exists():
            raise GapProbeReturnError(f"return target must be fresh: {target}")
    output.mkdir(parents=True, exist_ok=True)
    staging.mkdir()

    records: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    skipped: list[dict[str, Any]] = []
    package_manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    try:
        package_manifest = json.loads(
            package_manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GapProbeReturnError(
            f"cannot parse test-package manifest: {package_manifest_path}: {exc}"
        ) from exc
    stock_rtl_receipt_required = (
        package_manifest.get("rtl_policy", {}).get("mode")
        == "server_original_unmodified"
    )

    def add(
        source: Path,
        relative: str,
        role: str,
        *,
        required: bool = True,
    ) -> None:
        _copy_allowlisted(
            source=source,
            staging=staging,
            relative=_safe_relative(relative),
            role=role,
            required=required,
            records=records,
            missing=missing,
            skipped=skipped,
        )

    add(
        package_manifest_path,
        "package/TEST_PACKAGE_MANIFEST.json",
        "test_package_identity",
    )
    for name in (
        "server_identity_pre_install.json",
        "server_identity_post_install.json",
        "server_identity_post_run.json",
        "observer_install_report.json",
        "run_exit_status.txt",
        "server_command.txt",
    ):
        add(evidence / name, f"identity/{name}", "run_identity")
    for name in (
        "server_identity_post_restore.json",
        "rtl_patch_install_report.json",
        "rtl_patch_restore_report.json",
    ):
        add(
            evidence / name,
            f"identity/{name}",
            "rtl_repair_identity",
            required=False,
        )
    add(
        evidence / "stock_rtl_identity_receipt.json",
        "identity/stock_rtl_identity_receipt.json",
        "server_original_rtl_identity",
        required=stock_rtl_receipt_required,
    )
    add(
        evidence / "return_observer.log",
        "logs/return_observer.log",
        "targeted_ga_accumulator_state",
    )

    run_sim_results = run / "sim_results"
    root_sim_results = root / "sim_results"
    add(
        _first_file(
            [run_sim_results / "compile.log", root_sim_results / "compile.log"]
        ),
        "logs/compile.log",
        "compile_log",
    )
    add(
        _first_file([run_sim_results / "sim.log", root_sim_results / "sim.log"]),
        "logs/sim.log",
        "simulation_log",
    )

    cfg_root = root / "install" / "cfg_pkg" / install_name
    sca = cfg_root / "sca_cfg.json"
    sca_d = cfg_root / "sca_cfg_D.json"
    add(sca, "config/sca_cfg.json", "runtime_sca")
    add(sca_d, "config/sca_cfg_D.json", "runtime_sca_d")

    readback_paths = _readback_paths(sca_d)
    for relative in readback_paths:
        add(
            _inside(root, relative),
            f"readback/{relative.as_posix()}",
            "formal_sca_d_readback",
        )

    for name in (
        "local_mse0_req.log",
        "local_mse0_rdata.log",
        "local_mse4_req.log",
        "local_mse4_wdata.log",
    ):
        add(
            _first_file(
                [
                    run_sim_results / "local" / "slice0" / name,
                    root_sim_results / "local" / "slice0" / name,
                ]
            ),
            f"logs/local/slice0/{name}",
            "slice0_numeric_path_context",
            required=False,
        )

    manifest_path = staging / "RETURN_MANIFEST.json"
    payload_bytes = sum(record["size_bytes"] for record in records)
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if not missing else "incomplete",
        "install_name": install_name,
        "run_exit_status": run_status,
        "server_command": server_command,
        "wave_policy": {
            "DUMP_VCD": 0,
            "DUMP_FSDB": 0,
            "TB_DUMP_FSDB": 0,
            "waveforms_allowlisted": False,
        },
        "return_policy": {
            "allowlist_only": True,
            "zip_limit_bytes": MAX_ZIP_BYTES,
            "extracted_limit_bytes": MAX_EXTRACTED_BYTES,
            "individual_text_limit_bytes": MAX_TEXT_BYTES,
            "nested_archives_forbidden": True,
        },
        "test_package_manifest_sha256": _sha256(
            package_manifest_path
        ),
        "functional_rtl_mode": (
            package_manifest.get("rtl_policy", {}).get("mode")
            or (
                "transactional_repair"
                if package_manifest.get("repair_policy", {}).get(
                    "functional_rtl_v_or_sv_included"
                )
                is True
                else "unspecified"
            )
        ),
        "stock_rtl_identity_receipt_required": stock_rtl_receipt_required,
        "required_missing": missing,
        "oversize_skipped": skipped,
        "readback_path_count": len(readback_paths),
        "payload_file_count": len(records),
        "payload_size_bytes": payload_bytes,
        "files": sorted(records, key=lambda item: item["path"]),
        "manifest_file": {
            "path": "RETURN_MANIFEST.json",
            "role": "return_manifest",
            "sha256": None,
        },
        "extracted_size_bytes": 0,
        "zip_size_bytes": 0,
        "zip_sha256_source": f"../{return_name}.zip.sha256",
        "zip_audit": {
            "entry_count": len(records) + 1,
            "exact_file_set": True,
            "single_root": return_name,
            "forbidden_entry_count": 0,
        },
    }
    _write_json(manifest_path, manifest)
    zip_size_converged = False
    for _ in range(12):
        for _ in range(3):
            extracted_size = sum(
                path.stat().st_size
                for path in staging.rglob("*")
                if path.is_file()
            )
            if manifest["extracted_size_bytes"] == extracted_size:
                break
            manifest["extracted_size_bytes"] = extracted_size
            _write_json(manifest_path, manifest)
        if manifest["extracted_size_bytes"] > MAX_EXTRACTED_BYTES:
            raise GapProbeReturnError(
                "return extracted size exceeds 32 MiB: "
                f"{manifest['extracted_size_bytes']}"
            )
        _write_zip(staging, zip_path)
        actual_zip_size = zip_path.stat().st_size
        if manifest["zip_size_bytes"] == actual_zip_size:
            zip_size_converged = True
            break
        manifest["zip_size_bytes"] = actual_zip_size
        _write_json(manifest_path, manifest)
    if not zip_size_converged:
        raise GapProbeReturnError("return ZIP size metadata did not converge")
    if zip_path.stat().st_size > MAX_ZIP_BYTES:
        raise GapProbeReturnError(
            f"return ZIP exceeds 16 MiB: {zip_path.stat().st_size}"
        )
    audit = _audit_zip(
        staging=staging,
        zip_path=zip_path,
        expected_root=return_name,
    )
    zip_sha256 = _sha256(zip_path)
    sha_path.write_text(
        f"{zip_sha256}  {zip_path.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        **manifest,
        "directory": staging.as_posix(),
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha256,
        "zip_audit": audit,
        "sha256_file": sha_path.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ndp-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--install-name", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-status", type=int, required=True)
    parser.add_argument("--server-command", required=True)
    args = parser.parse_args()
    try:
        report = build_return(
            ndp_root=args.ndp_root,
            run_dir=args.run_dir,
            evidence_root=args.evidence_root,
            package_root=args.package_root,
            install_name=args.install_name,
            output_dir=args.output_dir,
            run_status=args.run_status,
            server_command=args.server_command,
        )
    except Exception as error:
        print(f"GAP probe return generation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["required_missing"] else 5


if __name__ == "__main__":
    raise SystemExit(main())
