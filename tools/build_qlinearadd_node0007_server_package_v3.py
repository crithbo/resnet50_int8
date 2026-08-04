from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.qlinearadd_node0007_server_runtime import file_records, preflight


OUTPUT_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
SOURCE_NAME = "r5_qadd_n7_relocated_v2"
INSTALL_NAME = "r5_qadd_n7_relocated_v3"
SOURCE_PACKAGE = OUTPUT_ROOT / SOURCE_NAME
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = (
    "60534faad0894a8b6507687159d43c824dd968f6c6a3386fa7877fc2007bf0bc"
)
RETURN2_SHA256 = (
    "7a7b1c68dbf582c070cbdb4daa310facdcfb46a6a3b796294300979f80551afb"
)
SIMULATION_TIMEOUT = "48h"


class PackageBuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PackageBuildError(f"JSON root must be object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _replace_namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _replace_namespace(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_namespace(item) for item in value]
    if isinstance(value, str):
        return value.replace(SOURCE_NAME, INSTALL_NAME)
    return value


def _normalized_namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalized_namespace(item) for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalized_namespace(item) for item in value]
    if isinstance(value, str):
        return value.replace(INSTALL_NAME, "<INSTALL_NAME>").replace(
            SOURCE_NAME, "<INSTALL_NAME>"
        )
    return value


def _assert_reused_payloads(package: Path) -> dict[str, bool]:
    source_install = file_records(
        SOURCE_PACKAGE / "workload/runtime/install", exclude_manifest=False
    )
    target_install = file_records(
        package / "workload/runtime/install", exclude_manifest=False
    )
    source_golden = file_records(
        SOURCE_PACKAGE / "validation/golden", exclude_manifest=False
    )
    target_golden = file_records(
        package / "validation/golden", exclude_manifest=False
    )
    runtime_name = "qlinearadd_node0007_server_runtime.py"
    runtime_equal = (
        sha256(SOURCE_PACKAGE / "package_tools" / runtime_name)
        == sha256(package / "package_tools" / runtime_name)
    )
    sca_equal = all(
        _normalized_namespace(
            load_json(SOURCE_PACKAGE / "workload/runtime" / name)
        )
        == _normalized_namespace(load_json(package / "workload/runtime" / name))
        for name in ("sca_cfg.json", "sca_cfg_D.json")
    )
    result = {
        "install_payload_exact": source_install == target_install,
        "golden_exact": source_golden == target_golden,
        "runtime_gate_exact": runtime_equal,
        "sca_semantics_equal_after_namespace_rebind": sca_equal,
    }
    if not all(result.values()):
        raise PackageBuildError(f"frozen v2 workload reuse differs: {result}")
    return result


def build_directory(destination: Path) -> tuple[Path, dict[str, bool]]:
    if sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise PackageBuildError("source v2 ZIP identity differs")
    preflight(SOURCE_PACKAGE)
    package = destination / INSTALL_NAME
    if package.exists():
        raise PackageBuildError(f"fresh package identity required: {package}")
    shutil.copytree(SOURCE_PACKAGE, package)

    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        path = package / "workload/runtime" / name
        write_json(path, _replace_namespace(load_json(path)))

    runner = package / "PREPARE_AND_RUN.sh"
    runner_text = runner.read_text(encoding="utf-8")
    old_install = f'install_name="{SOURCE_NAME}"'
    old_timeout = '12h "$simv"'
    if runner_text.count(old_install) != 1 or runner_text.count(old_timeout) != 1:
        raise PackageBuildError("source v2 runner signature differs")
    runner_text = runner_text.replace(
        old_install, f'install_name="{INSTALL_NAME}"'
    ).replace(old_timeout, f'{SIMULATION_TIMEOUT} "$simv"')
    if SOURCE_NAME in runner_text or '12h "$simv"' in runner_text:
        raise PackageBuildError("stale v2 runner identity or timeout remains")
    runner.write_text(runner_text, encoding="utf-8", newline="\n")
    os.chmod(runner, 0o755)

    (package / "README.md").write_text(
        "# ResNet50 node0007 QLinearAdd relocated full-E2 test v3\n\n"
        "Run exactly once from this extracted directory:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "This fresh identity reuses the frozen v2 workload byte-for-byte "
        "(apart from install namespace rebinding) and changes only the "
        "package-owned simulation watchdog from 12h to 48h. It uses stock "
        "RTL, packages no formal D target, and preserves the conjunctive "
        "compile/run/natural-terminal/readback gate.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = load_json(manifest_path)
    manifest.pop("files", None)
    manifest.update(
        {
            "schema": "qlinearadd-node0007-relocated-server-package-v3",
            "install_name": INSTALL_NAME,
            "claim_boundary": (
                "candidate_release=false; E2 local only; fresh runner-timeout "
                "identity; no binding to a final Trassic2.0_RTL commit"
            ),
            "simulation_timeout": SIMULATION_TIMEOUT,
            "numeric_analysis_repeated": False,
            "consumed_reuse_assets": True,
            "workload_rebuilt": False,
            "supersedes_runtime_timeout_identity": {
                "zip": SOURCE_ZIP.relative_to(ROOT).as_posix(),
                "zip_sha256": SOURCE_ZIP_SHA256,
                "return_zip_sha256": RETURN2_SHA256,
                "first_divergence": (
                    "PACKAGE_SIMULATION_WATCHDOG_EXPIRED_AFTER_SLICE_START"
                ),
                "old_simulation_timeout": "12h",
                "new_simulation_timeout": SIMULATION_TIMEOUT,
                "v2_release_allowed": False,
            },
        }
    )
    provenance = dict(manifest["provenance"])
    contract_path = ROOT / provenance["closure_contract"]["path"]
    provenance["closure_contract"] = {
        "path": contract_path.relative_to(ROOT).as_posix(),
        "sha256": sha256(contract_path),
    }
    provenance["generator"] = (
        "tools/build_qlinearadd_node0007_server_package_v3.py"
    )
    provenance["source_package"] = {
        "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
        "sha256": SOURCE_ZIP_SHA256,
    }
    manifest["provenance"] = provenance
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)

    reuse = _assert_reused_payloads(package)
    preflight(package)
    return package, reuse


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{package.name}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, (2026, 7, 30, 0, 0, 0))
            info.create_system = 3
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def _publish_contract(package_zip: Path, sidecar: Path) -> str:
    manifest = load_json(OUTPUT_ROOT / INSTALL_NAME / "TEST_PACKAGE_MANIFEST.json")
    contract_path = ROOT / manifest["provenance"]["closure_contract"]["path"]
    contract = load_json(contract_path)
    contract["package_release"] = {
        "status": "PACKAGE_READY_NOT_RUN",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "zip": package_zip.relative_to(ROOT).as_posix(),
        "zip_sha256": sha256(package_zip),
        "sidecar": sidecar.relative_to(ROOT).as_posix(),
        "simulation_timeout": SIMULATION_TIMEOUT,
    }
    write_json(contract_path, contract)
    return sha256(contract_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    package_path = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation_path = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, validation_path):
        if path.exists():
            raise PackageBuildError(f"refusing to overwrite: {path}")
    output_root.mkdir(parents=True, exist_ok=True)

    package, reuse = build_directory(output_root)
    deterministic_zip(package, zip_path)
    first_records = file_records(package, exclude_manifest=False)
    first_sha = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="qadd-node0007-v3-repeat-") as tmp:
        repeat_package, repeat_reuse = build_directory(Path(tmp))
        repeat_zip = Path(tmp) / f"{INSTALL_NAME}.zip"
        deterministic_zip(repeat_package, repeat_zip)
        repeated = {
            "package_tree_equal": (
                first_records
                == file_records(repeat_package, exclude_manifest=False)
            ),
            "zip_equal": first_sha == sha256(repeat_zip),
            "reuse_receipt_equal": reuse == repeat_reuse,
        }
    if not all(repeated.values()):
        raise PackageBuildError(f"repeated build differs: {repeated}")

    sidecar.write_text(
        f"{first_sha}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    contract_sha = _publish_contract(zip_path, sidecar)
    receipt = {
        "schema": "qlinearadd-node0007-package-validation-v3",
        "status": "PACKAGE_READY_NOT_RUN",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "package": package.relative_to(ROOT).as_posix(),
        "zip": zip_path.relative_to(ROOT).as_posix(),
        "zip_sha256": first_sha,
        "zip_size_bytes": zip_path.stat().st_size,
        "sidecar": sidecar.relative_to(ROOT).as_posix(),
        "simulation_timeout": SIMULATION_TIMEOUT,
        "source_v2_zip_sha256": SOURCE_ZIP_SHA256,
        "trigger_return_sha256": RETURN2_SHA256,
        "numeric_analysis_repeated": False,
        "consumed_reuse_assets": True,
        "reuse_equivalence": reuse,
        "formal_readback_count": 28,
        "preloaded_runtime_readback_target_count": 0,
        "result_gate_fail_closed": True,
        "return_allowlist_only": True,
        "functional_rtl_modified": False,
        "rtl_or_tb_entry_count": 0,
        "server_action": False,
        "server_source_inspected": False,
        "repeated_build": repeated,
        "closure_contract_sha256": contract_sha,
        "single_command": (
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy02"
        ),
        "expected_return_zip": f"{INSTALL_NAME}_return.zip",
        "expected_return_sidecar": f"{INSTALL_NAME}_return.zip.sha256",
    }
    write_json(validation_path, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
