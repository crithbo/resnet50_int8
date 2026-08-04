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

from tools.qlinearadd_node0007_server_runtime import (  # noqa: E402
    file_records,
    preflight,
)


INSTALL_NAME = "r5_qadd_n7_nested_lc_v4"
PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / INSTALL_NAME
)
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
    package_report = preflight(PACKAGE)
    manifest = load_json(PACKAGE / "TEST_PACKAGE_MANIFEST.json")
    validation = load_json(VALIDATION)
    contract_path = ROOT / manifest["provenance"]["closure_contract"]["path"]
    current_contract = load_json(contract_path)
    digest = sha256(ZIP)
    if SIDECAR.read_text(encoding="ascii").split()[0] != digest:
        errors.append("ZIP sidecar SHA differs")
    if validation.get("zip_sha256") != digest:
        errors.append("validation ZIP SHA differs")
    current_release = current_contract.get("package_release", {})
    if (
        current_release.get("zip_sha256") != digest
        or current_release.get("status") != "PACKAGE_READY_NOT_RUN"
    ):
        errors.append("current contract does not bind the v4 ZIP")

    snapshot_contract = dict(current_contract)
    snapshot_contract["package_release"] = {
        "status": "PENDING_PACKAGE_BUILD",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
    }
    snapshot_bytes = (
        json.dumps(
            snapshot_contract, indent=2, ensure_ascii=False, sort_keys=True
        )
        + "\n"
    ).encode("utf-8")
    snapshot_sha256 = hashlib.sha256(snapshot_bytes).hexdigest()
    manifest_snapshot_sha256 = manifest["provenance"]["closure_contract"][
        "sha256"
    ]
    if snapshot_sha256 != manifest_snapshot_sha256:
        errors.append(
            "package build-input contract snapshot cannot be reconstructed"
        )

    expected_files = file_records(PACKAGE, exclude_manifest=False)
    observed_files: dict[str, dict[str, Any]] = {}
    names: list[str] = []
    unsafe: list[str] = []
    symlinks: list[str] = []
    duplicates: list[str] = []
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
                relative = (
                    PurePosixPath(name)
                    .relative_to(INSTALL_NAME)
                    .as_posix()
                )
                payload = archive.read(info)
                observed_files[relative] = {
                    "size_bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
    if unsafe:
        errors.append(f"unsafe ZIP members: {unsafe[:3]}")
    if duplicates:
        errors.append(f"duplicate ZIP members: {duplicates[:3]}")
    if symlinks:
        errors.append(f"ZIP symlink members: {symlinks[:3]}")
    if observed_files != expected_files:
        errors.append("ZIP/package exact-set differs")

    readback_targets = {
        f"{INSTALL_NAME}/workload/runtime/{item['runtime_path']}"
        for item in manifest["readback_checks"]
    }
    preloaded_targets = sorted(readback_targets & set(names))
    if preloaded_targets:
        errors.append(
            f"formal runtime D targets are packaged: {preloaded_targets[:3]}"
        )
    rtl_entries = [
        name
        for name in names
        if "/rtl/" in name.lower()
        or PurePosixPath(name).suffix.lower() in {".sv", ".svh", ".v", ".vh"}
    ]
    if rtl_entries:
        errors.append(f"RTL/TB entries are packaged: {rtl_entries[:3]}")
    budgets = manifest["budgets"]
    extracted_bytes = sum(item["size_bytes"] for item in observed_files.values())
    if ZIP.stat().st_size > int(budgets["upload_zip_max_bytes"]):
        errors.append("upload ZIP budget exceeded")
    if extracted_bytes > int(budgets["upload_extracted_max_bytes"]):
        errors.append("upload extracted budget exceeded")
    if manifest.get("server_rtl_entries") != 0:
        errors.append("server_rtl_entries is not zero")
    if manifest.get("functional_rtl_modified") is not False:
        errors.append("functional_rtl_modified is not false")
    if manifest.get("numeric_analysis_repeated") is not False:
        errors.append("numeric_analysis_repeated is not false")

    return {
        "schema": "qlinearadd-node0007-nested-lc-package-audit-v4",
        "valid": not errors,
        "status": (
            "PACKAGE_READY_NOT_RUN" if not errors else "PACKAGE_REJECTED"
        ),
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "errors": errors,
        "first_error": errors[0] if errors else None,
        "package_preflight": package_report,
        "package_file_count": len(expected_files),
        "zip_member_count": len(observed_files),
        "zip_sha256": digest,
        "zip_size_bytes": ZIP.stat().st_size,
        "zip_budget_bytes": int(budgets["upload_zip_max_bytes"]),
        "extracted_size_bytes": extracted_bytes,
        "extracted_budget_bytes": int(
            budgets["upload_extracted_max_bytes"]
        ),
        "zip_crc_clean": crc_failure is None,
        "zip_path_traversal_count": len(unsafe),
        "zip_duplicate_count": len(duplicates),
        "zip_symlink_count": len(symlinks),
        "zip_package_exact_set": observed_files == expected_files,
        "rtl_or_tb_entry_count": len(rtl_entries),
        "formal_runtime_d_target_count": len(readback_targets),
        "preloaded_runtime_d_target_count": len(preloaded_targets),
        "result_gate_fail_closed": validation["result_gate_fail_closed"],
        "return_allowlist_only": validation["return_allowlist_only"],
        "server_action": False,
        "server_source_inspected": False,
        "contract_cycle_break": {
            "valid": snapshot_sha256 == manifest_snapshot_sha256,
            "package_build_input_snapshot_sha256": (
                manifest_snapshot_sha256
            ),
            "reconstructed_snapshot_sha256": snapshot_sha256,
            "snapshot_package_release": "PENDING_PACKAGE_BUILD",
            "current_contract_sha256": sha256(contract_path),
            "current_contract_binds_v4_zip": (
                current_release.get("zip_sha256") == digest
            ),
        },
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
