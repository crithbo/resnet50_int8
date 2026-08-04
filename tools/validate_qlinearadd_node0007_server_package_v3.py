from __future__ import annotations

import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package_v3 import (
    INSTALL_NAME,
    OUTPUT_ROOT,
    SIMULATION_TIMEOUT,
    SOURCE_ZIP,
    SOURCE_ZIP_SHA256,
    _assert_reused_payloads,
)
from tools.qlinearadd_node0007_server_runtime import file_records, preflight

PACKAGE = OUTPUT_ROOT / INSTALL_NAME
ZIP = PACKAGE.with_suffix(".zip")
SIDECAR = Path(str(ZIP) + ".sha256")
VALIDATION = PACKAGE.with_suffix(".validation.json")
AUDIT = PACKAGE.with_suffix(".audit.json")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return value


def audit() -> dict[str, Any]:
    errors: list[str] = []
    package_preflight = preflight(PACKAGE)
    manifest = load_json(PACKAGE / "TEST_PACKAGE_MANIFEST.json")
    validation = load_json(VALIDATION)
    digest = sha256(ZIP)
    if sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        errors.append("source v2 ZIP identity differs")
    if SIDECAR.read_text(encoding="ascii").split()[0] != digest:
        errors.append("v3 ZIP sidecar differs")
    if validation.get("zip_sha256") != digest:
        errors.append("v3 validation ZIP identity differs")
    if (
        manifest.get("install_name") != INSTALL_NAME
        or manifest.get("simulation_timeout") != SIMULATION_TIMEOUT
        or manifest.get("workload_rebuilt") is not False
        or manifest.get("numeric_analysis_repeated") is not False
    ):
        errors.append("v3 runner-only claim differs")

    runner = (PACKAGE / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    if (
        f'install_name="{INSTALL_NAME}"' not in runner
        or f'{SIMULATION_TIMEOUT} "$simv"' not in runner
        or '12h "$simv"' in runner
    ):
        errors.append("v3 runner timeout or namespace differs")

    expected_files = file_records(PACKAGE, exclude_manifest=False)
    observed_files: dict[str, dict[str, Any]] = {}
    unsafe: list[str] = []
    duplicates: list[str] = []
    symlinks: list[str] = []
    names: list[str] = []
    seen: set[str] = set()
    with zipfile.ZipFile(ZIP) as archive:
        crc_failure = archive.testzip()
        if crc_failure is not None:
            errors.append(f"ZIP CRC failure: {crc_failure}")
        for info in archive.infolist():
            name = info.filename
            names.append(name)
            pure = PurePosixPath(name)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in name
                or not name.startswith(f"{INSTALL_NAME}/")
            ):
                unsafe.append(name)
            if name in seen:
                duplicates.append(name)
            seen.add(name)
            if mode and stat.S_ISLNK(mode):
                symlinks.append(name)
            if not info.is_dir():
                relative = pure.relative_to(INSTALL_NAME).as_posix()
                payload = archive.read(info)
                observed_files[relative] = {
                    "size_bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
    if unsafe or duplicates or symlinks:
        errors.append("ZIP path/symlink/duplicate safety differs")
    if observed_files != expected_files:
        errors.append("ZIP/package exact-set differs")

    rtl_entries = [
        name
        for name in names
        if "/rtl/" in name.lower()
        or PurePosixPath(name).suffix.lower() in {".sv", ".svh", ".v", ".vh"}
    ]
    if rtl_entries:
        errors.append("v3 unexpectedly packages RTL/TB entries")
    runtime_d_targets = {
        f"{INSTALL_NAME}/workload/runtime/{item['runtime_path']}"
        for item in manifest["readback_checks"]
    }
    preloaded_d = sorted(runtime_d_targets & set(names))
    if preloaded_d:
        errors.append("formal runtime D target is packaged")

    reuse = _assert_reused_payloads(PACKAGE)
    contract_path = ROOT / manifest["provenance"]["closure_contract"]["path"]
    contract = load_json(contract_path)
    release = contract.get("package_release", {})
    contract_bound = (
        release.get("zip_sha256") == digest
        and release.get("status") == "PACKAGE_READY_NOT_RUN"
        and release.get("simulation_timeout") == SIMULATION_TIMEOUT
    )
    if not contract_bound:
        errors.append("family closure contract does not bind v3")
    snapshot_contract = dict(contract)
    snapshot_contract["package_release"] = {
        "status": "PACKAGE_READY_NOT_RUN",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "zip": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            "r5_qadd_n7_relocated_v2.zip"
        ),
        "zip_sha256": SOURCE_ZIP_SHA256,
        "sidecar": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            "r5_qadd_n7_relocated_v2.zip.sha256"
        ),
    }
    snapshot_bytes = (
        json.dumps(
            snapshot_contract, indent=2, ensure_ascii=False, sort_keys=True
        )
        + "\n"
    ).encode("utf-8")
    reconstructed_snapshot_sha = hashlib.sha256(snapshot_bytes).hexdigest()
    package_snapshot_sha = manifest["provenance"]["closure_contract"]["sha256"]
    cycle_break_valid = reconstructed_snapshot_sha == package_snapshot_sha
    if not cycle_break_valid:
        errors.append("v3 pre-build contract snapshot cannot be reconstructed")

    return {
        "schema": "qlinearadd-node0007-package-zip-audit-v3",
        "valid": not errors,
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "PACKAGE_REJECTED",
        "errors": errors,
        "first_error": errors[0] if errors else None,
        "package_preflight": package_preflight,
        "zip_sha256": digest,
        "zip_size_bytes": ZIP.stat().st_size,
        "zip_crc_clean": crc_failure is None,
        "zip_package_exact_set": observed_files == expected_files,
        "zip_path_traversal_count": len(unsafe),
        "zip_duplicate_count": len(duplicates),
        "zip_symlink_count": len(symlinks),
        "rtl_or_tb_entry_count": len(rtl_entries),
        "formal_runtime_d_target_count": len(runtime_d_targets),
        "preloaded_runtime_d_target_count": len(preloaded_d),
        "simulation_timeout": SIMULATION_TIMEOUT,
        "source_v2_zip_sha256": SOURCE_ZIP_SHA256,
        "reuse_equivalence": reuse,
        "contract_binds_v3": contract_bound,
        "contract_cycle_break": {
            "valid": cycle_break_valid,
            "package_build_input_snapshot_sha256": package_snapshot_sha,
            "reconstructed_snapshot_sha256": reconstructed_snapshot_sha,
            "snapshot_package_release": "v2 package identity",
            "current_contract_sha256": sha256(contract_path),
        },
        "candidate_release": False,
        "server_action": False,
        "server_source_inspected": False,
    }


def main() -> int:
    report = audit()
    AUDIT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
