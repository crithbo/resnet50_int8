from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v7_four_way_binding_package_v8 as base  # noqa: E402


SOURCE_NAME = "r5_n4_hw_v27_dwrite_path_diag"
INSTALL_NAME = "r5_n4_hw_v28_dwrite_path_diag_bind"
SOURCE_SHA256 = (
    "9c6c2e18435a52817e68079ccfd8c965332bff83384049eef841a19713ec1778"
)
RETURN_SHA256 = (
    "2a3e041737376a8afdfcb70d85e30c9f4c7fbc12d5bdad94c9ec2c9b7fa78d68"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"


class BuildError(RuntimeError):
    pass


def extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v27 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v27 source CRC failed")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                raise BuildError(f"unsafe/duplicate member: {info.filename}")
            seen.add(info.filename)
            if path.parts:
                roots.add(path.parts[0])
        if roots != {SOURCE_NAME}:
            raise BuildError(f"v27 root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE_NAME


def replace_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".bin":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_NAME in text:
            path.write_text(
                text.replace(SOURCE_NAME, INSTALL_NAME),
                encoding="utf-8",
                newline="\n",
            )


def patch_runtime(package: Path) -> dict[str, str]:
    path = package / "package_tools/node0004_hang_localization_runtime.py"
    old_sha = base.sha256(path)
    text = path.read_text(encoding="utf-8")
    anchor = """    {
        "feature": "RETURN_OBS_FINAL_RELEASE",
        "enable": "+RETURN_OBS_FINAL_RELEASE",
        "limits": ("+RETURN_OBS_FINAL_RELEASE_LIMIT=256",),
        "marker_tokens": (
            "feature=RETURN_OBS_FINAL_RELEASE",
            "enabled=1",
            "limit=256",
        ),
    },
)
"""
    replacement = """    {
        "feature": "RETURN_OBS_FINAL_RELEASE",
        "enable": "+RETURN_OBS_FINAL_RELEASE",
        "limits": ("+RETURN_OBS_FINAL_RELEASE_LIMIT=256",),
        "marker_tokens": (
            "feature=RETURN_OBS_FINAL_RELEASE",
            "enabled=1",
            "limit=256",
        ),
    },
    {
        "feature": "RETURN_OBS_DWRITE_PATH",
        "enable": "+RETURN_OBS_DWRITE_PATH",
        "limits": ("+RETURN_OBS_DWRITE_PATH_LIMIT=64",),
        "marker_tokens": (
            "feature=RETURN_OBS_DWRITE_PATH",
            "enabled=1",
            "limit=64",
        ),
    },
)
"""
    if text.count(anchor) != 1:
        raise BuildError("runtime feature-contract anchor differs")
    path.write_text(
        text.replace(anchor, replacement, 1),
        encoding="utf-8",
        newline="\n",
    )
    return {"old_sha256": old_sha, "new_sha256": base.sha256(path)}


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v28-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    repair = patch_runtime(package)
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": (
                "resnet50-node0004-dwrite-path-diagnostic-binding-package-v28"
            ),
            "install_name": INSTALL_NAME,
            "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": False,
            "configuration_rebuilt_in_this_successor": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
        }
    )
    manifest["diagnostic_feature_receipt_fix"] = {
        "classification": "PACKAGE_LOCAL_RETURN_RECEIPT_BINDING_FIX",
        "bound_v26_return_sha256": RETURN_SHA256,
        "path": "package_tools/node0004_hang_localization_runtime.py",
        **repair,
        "mechanism": (
            "add RETURN_OBS_DWRITE_PATH to the collector's feature contracts "
            "so actual argv, time0 marker and returned observer log are "
            "jointly fail-closed"
        ),
        "observer_changed": False,
        "configuration_changed": False,
    }
    manifest["superseded_v27_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_SHA256,
        "status": "QUARANTINED_FEATURE_RECEIPT_BINDING_INCOMPLETE",
    }
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    observer_sha = base.sha256(package / "tb_probe/native_return_observer.svh")
    receipt = base.observer_precompile_receipt(package, observer_sha)
    if not receipt["valid"]:
        raise BuildError(f"observer gate failed: {receipt['errors']}")
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    targets = [
        output / INSTALL_NAME,
        output / f"{INSTALL_NAME}.zip",
        output / f"{INSTALL_NAME}.zip.sha256",
        output / f"{INSTALL_NAME}.validation.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite existing v28 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v28-repeat-") as temp:
        repeat_root = Path(temp)
        repeat = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v28 deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-v28-dwrite-path-binding-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v27_sha256": SOURCE_SHA256,
        "bound_v26_return_sha256": RETURN_SHA256,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "final_zip_rule_self_audit_pending": True,
    }
    base.write_json(output / f"{INSTALL_NAME}.validation.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
