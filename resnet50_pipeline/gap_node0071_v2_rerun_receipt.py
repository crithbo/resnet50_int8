from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_ZIP_SHA256 = (
    "c3fe06f6e0110b41936b69ae264a24b2dc2d76779efc589c4fe34378b6891b8f"
)
EXPECTED_ZIP_BYTES = 1777110
EXPECTED_SIDECAR_SHA256 = (
    "d4008551f3e19c1e5960cc3a44a1986b7363deec08246004e6e4391fa152d84f"
)
EXPECTED_OBSERVER_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
PACKAGE_ROOT = "r5_n71_gap_v2_obs"
PACKAGE_RELATIVE = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v2_obs.zip"
)
SIDECAR_RELATIVE = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v2_obs.zip.sha256"
)
MANIFEST_MEMBER = f"{PACKAGE_ROOT}/TEST_PACKAGE_MANIFEST.json"
RUNNER_MEMBER = f"{PACKAGE_ROOT}/PREPARE_AND_RUN.sh"
RUNTIME_MEMBER = (
    f"{PACKAGE_ROOT}/package_tools/"
    "gap_node0071_complete_server_runtime.py"
)
OBSERVER_MEMBER = (
    f"{PACKAGE_ROOT}/tb_probe/native_return_observer.svh"
)
FORBIDDEN_INTERFACE_TOKENS = (
    b"slice_rst",
    b"SA_PE_Mul_Array",
    b"SA_ALU",
)


class GapNode0071V2RerunReceiptError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_members(archive: zipfile.ZipFile) -> list[str]:
    members: list[str] = []
    seen: set[str] = set()
    for info in archive.infolist():
        name = info.filename
        pure = PurePosixPath(name)
        mode = info.external_attr >> 16
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in name
            or name in seen
            or (mode and stat.S_ISLNK(mode))
        ):
            raise GapNode0071V2RerunReceiptError(
                f"unsafe or duplicate ZIP member: {name}"
            )
        seen.add(name)
        if not info.is_dir():
            members.append(name)
    return members


def _json(payload: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise GapNode0071V2RerunReceiptError(
            f"cannot parse JSON: {name}"
        ) from error
    if not isinstance(value, dict):
        raise GapNode0071V2RerunReceiptError(
            f"JSON root differs: {name}"
        )
    return value


def audit_gap_node0071_v2_rerun_receipt(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    package = root / PACKAGE_RELATIVE
    sidecar = root / SIDECAR_RELATIVE
    if not package.is_file() or not sidecar.is_file():
        raise GapNode0071V2RerunReceiptError(
            "package ZIP or sidecar is absent"
        )
    package_sha = sha256_file(package)
    sidecar_sha = sha256_file(sidecar)
    expected_sidecar = f"{EXPECTED_ZIP_SHA256}  {package.name}\n"
    if (
        package.stat().st_size != EXPECTED_ZIP_BYTES
        or package_sha != EXPECTED_ZIP_SHA256
        or sidecar_sha != EXPECTED_SIDECAR_SHA256
        or sidecar.read_text(encoding="ascii") != expected_sidecar
    ):
        raise GapNode0071V2RerunReceiptError(
            "package or sidecar identity differs"
        )

    with zipfile.ZipFile(package) as archive:
        members = _safe_members(archive)
        if archive.testzip() is not None:
            raise GapNode0071V2RerunReceiptError("package ZIP CRC failed")
        if len(members) != 123:
            raise GapNode0071V2RerunReceiptError(
                "package file count differs"
            )
        manifest_bytes = archive.read(MANIFEST_MEMBER)
        manifest = _json(manifest_bytes, MANIFEST_MEMBER)
        runner = archive.read(RUNNER_MEMBER).decode("utf-8")
        runtime = archive.read(RUNTIME_MEMBER).decode("utf-8")
        observer = archive.read(OBSERVER_MEMBER)
        interface_token_hits = {
            token.decode("ascii"): [
                name for name in members if token in archive.read(name)
            ]
            for token in FORBIDDEN_INTERFACE_TOKENS
        }
        rtl_like_entries = [
            name
            for name in members
            if PurePosixPath(name).suffix.lower()
            in {".v", ".sv", ".vh", ".svh"}
        ]
        runtime_readback_entries = [
            name for name in members if "/readback/" in name
        ]

    observer_manifest = manifest.get("package_local_observer")
    if (
        manifest.get("schema")
        != "gap-node0071-complete-server-package-v2"
        or manifest.get("package_name") != PACKAGE_ROOT
        or manifest.get("install_name") != PACKAGE_ROOT
        or manifest.get("run_name") != f"run_{PACKAGE_ROOT}"
        or manifest.get("return_name") != f"{PACKAGE_ROOT}_return"
        or manifest.get("functional_rtl_modified") is not False
        or manifest.get("server_rtl_entries") != 0
        or manifest.get("server_tb_or_observer_install_entries") != 0
        or manifest.get("package_local_tb_or_observer_entries") != 1
        or manifest.get("server_source_identity_bound") is not False
        or manifest.get("server_source_preflight_performed") is not False
        or not isinstance(observer_manifest, dict)
        or observer_manifest.get("relative_path")
        != "tb_probe/native_return_observer.svh"
        or observer_manifest.get("sha256") != EXPECTED_OBSERVER_SHA256
        or observer_manifest.get("read_only") is not True
        or observer_manifest.get("server_install") is not False
        or sha256_bytes(observer) != EXPECTED_OBSERVER_SHA256
        or rtl_like_entries != [OBSERVER_MEMBER]
        or runtime_readback_entries
        or any(interface_token_hits.values())
    ):
        raise GapNode0071V2RerunReceiptError(
            "package RTL/interface boundary differs"
        )
    if (
        'Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX'
        not in runner
        or 'VCS_EXTRA_OPTS="+incdir+$package_root/tb_probe"'
        not in runner
        or 'make -C "$server_root" -f Makefile.tb_NDP_Top_new_phy compile'
        not in runner
        or 'destination = server_root / f"{install_name}_return"'
        not in runtime
        or "archive_path = destination.with_suffix(\".zip\")"
        not in runtime
        or 'sidecar = Path(str(archive_path) + ".sha256")'
        not in runtime
    ):
        raise GapNode0071V2RerunReceiptError(
            "runner or return identity binding differs"
        )

    return {
        "schema": "resnet50-gap-node0071-v2-rerun-receipt-v1",
        "status": "PACKAGE_RERUN_READY",
        "package_identity": {
            "path": PACKAGE_RELATIVE.as_posix(),
            "size_bytes": package.stat().st_size,
            "sha256": package_sha,
            "sidecar_path": SIDECAR_RELATIVE.as_posix(),
            "sidecar_sha256": sidecar_sha,
            "sidecar_content_valid": True,
            "zip_crc_valid": True,
            "zip_file_count": len(members),
            "manifest_sha256": sha256_bytes(manifest_bytes),
        },
        "package_boundary": {
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_tb_or_observer_install_entries": 0,
            "package_local_observer_entries": 1,
            "only_rtl_like_entry": OBSERVER_MEMBER,
            "observer_sha256": EXPECTED_OBSERVER_SHA256,
            "observer_read_only": True,
            "observer_server_install": False,
            "server_source_identity_bound": False,
            "server_source_preflight_performed": False,
            "old_interface_token_hits": interface_token_hits,
            "binds_old_slice_rst_interface": False,
            "requires_package_update_after_server_rtl_fix": False,
        },
        "runtime_boundary": {
            "runtime_readback_target_count_in_zip": 0,
            "package_local_observer_incdir_bound": True,
            "server_command": (
                "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
            ),
            "fresh_namespace_required": True,
            "expected_return_zip": "r5_n71_gap_v2_obs_return.zip",
            "expected_return_sidecar": (
                "r5_n71_gap_v2_obs_return.zip.sha256"
            ),
        },
        "claim_boundary": {
            "receipt_only": True,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "package_rebuilt_or_modified": False,
            "server_files_inspected": False,
            "uploaded_or_run": False,
            "accepted_reuse_assets_consumed": True,
            "local_claim": "CONFIG_ONLY_CORRECTNESS_BASELINE",
            "dynamic_or_production_claim": False,
        },
    }


__all__ = [
    "GapNode0071V2RerunReceiptError",
    "audit_gap_node0071_v2_rerun_receipt",
]
