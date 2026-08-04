from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_node0071_complete_server_package import (  # noqa: E402
    deterministic_zip,
    write_json,
)
from tools.gap_node0071_complete_server_runtime import (  # noqa: E402
    file_records,
    preflight,
)
from tools.gap_node0071_package_observer_guard import (  # noqa: E402
    observer_precompile_receipt,
)


INSTALL_NAME = "r5_n71_gap_v2_obs"
SOURCE_INSTALL_NAME = "r5_node0071_gap_hw_v1"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_node0071_gap_hw_v1.zip"
)
SOURCE_ZIP_SHA256 = (
    "bb5818c4071eacd220c669941169e181b51018d0591d85d51b01f0a7bd732b74"
)
RETURN_ANALYSIS = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-gap-node0071-hw-v1-return-analysis/report.json"
)
EXPECTED_RETURN_ANALYSIS_SHA256 = (
    "251971737d9a9cf09c361d87bd66cc0479f21e653ce81faa7fa7c839b3cef5f2"
)
OBSERVER_SOURCE = ROOT / "NDP_copy01/native_return_observer.svh"
OBSERVER_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
GUARD_SOURCE = ROOT / "tools/gap_node0071_package_observer_guard.py"
OUTPUT_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
)


class GapNode0071PackageV2Error(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_source_entries(
    archive: zipfile.ZipFile,
) -> list[zipfile.ZipInfo]:
    result: list[zipfile.ZipInfo] = []
    seen: set[str] = set()
    prefix = f"{SOURCE_INSTALL_NAME}/"
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
            or not name.startswith(prefix)
        ):
            raise GapNode0071PackageV2Error(
                f"unsafe source ZIP member: {name}"
            )
        seen.add(name)
        if not info.is_dir():
            result.append(info)
    return result


def _extract_bound_source(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise GapNode0071PackageV2Error("bound v1 source ZIP identity differs")
    package = destination / INSTALL_NAME
    if package.exists():
        raise GapNode0071PackageV2Error(
            f"fresh package identity required: {package}"
        )
    package.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        entries = _safe_source_entries(archive)
        if archive.testzip() is not None:
            raise GapNode0071PackageV2Error("bound v1 source ZIP CRC failed")
        for info in entries:
            relative = PurePosixPath(info.filename).relative_to(
                SOURCE_INSTALL_NAME
            )
            target = package / Path(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    preflight(package)
    return package


def _numeric_payload_records(package: Path) -> dict[str, Any]:
    records = file_records(package, exclude_manifest=False)
    excluded = {
        "PREPARE_AND_RUN.sh",
        "TEST_PACKAGE_MANIFEST.json",
        "workload/sca_cfg.json",
        "workload/sca_cfg_D.json",
        "package_tools/gap_node0071_complete_server_runtime.py",
        "package_tools/gap_node0071_package_observer_guard.py",
        "tb_probe/native_return_observer.svh",
    }
    return {
        name: value
        for name, value in records.items()
        if name not in excluded
    }


def _replace_identity(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(SOURCE_INSTALL_NAME, INSTALL_NAME)
    if isinstance(value, list):
        return [_replace_identity(item) for item in value]
    if isinstance(value, dict):
        return {key: _replace_identity(item) for key, item in value.items()}
    return value


def _rebind_sca(package: Path) -> None:
    for relative in ("workload/sca_cfg.json", "workload/sca_cfg_D.json"):
        path = package / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        rebound = _replace_identity(value)
        if rebound == value:
            raise GapNode0071PackageV2Error(
                f"SCA identity replacement absent: {relative}"
            )
        write_json(path, rebound)
        if SOURCE_INSTALL_NAME in path.read_text(encoding="utf-8"):
            raise GapNode0071PackageV2Error(
                f"stale source install identity remains: {relative}"
            )


def _patch_runtime(package: Path) -> None:
    runtime = (
        package
        / "package_tools/gap_node0071_complete_server_runtime.py"
    )
    text = runtime.read_text(encoding="utf-8")
    anchor = "not isinstance(allowlist, list) or len(allowlist) != 59"
    replacement = "not isinstance(allowlist, list) or len(allowlist) != 60"
    if text.count(anchor) != 1:
        raise GapNode0071PackageV2Error(
            "runtime allowlist cardinality anchor differs"
        )
    runtime.write_text(
        text.replace(anchor, replacement),
        encoding="utf-8",
        newline="\n",
    )


def _patch_runner(package: Path) -> None:
    runner = package / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    if text.count(SOURCE_INSTALL_NAME) != 1:
        raise GapNode0071PackageV2Error(
            "v1 runner install identity is not unique"
        )
    text = text.replace(SOURCE_INSTALL_NAME, INSTALL_NAME)

    command_anchor = (
        "DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=<unique-run>; "
    )
    command_replacement = (
        "DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=<unique-run> "
        "VCS_EXTRA_OPTS=+incdir+<package-root>/tb_probe; "
    )
    if text.count(command_anchor) != 1:
        raise GapNode0071PackageV2Error(
            "runner server-command receipt anchor differs"
        )
    text = text.replace(command_anchor, command_replacement)

    trap_anchor = "trap 'finalize $?' EXIT HUP INT TERM\n\nset +e\n"
    guard_block = f"""trap 'finalize $?' EXIT HUP INT TERM

observer_guard="${{package_root}}/package_tools/gap_node0071_package_observer_guard.py"
python3 "$observer_guard" --package-root "$package_root" \\
  --expected-sha256 "{OBSERVER_SHA256}" \\
  >"${{evidence_root}}/observer_precompile.json" || exit 7

set +e
"""
    if text.count(trap_anchor) != 1:
        raise GapNode0071PackageV2Error("runner trap anchor differs")
    text = text.replace(trap_anchor, guard_block)

    compile_anchor = (
        '  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$run_root"\n'
    )
    compile_replacement = (
        '  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$run_root" \\\n'
        '  VCS_EXTRA_OPTS="+incdir+$package_root/tb_probe"\n'
    )
    if text.count(compile_anchor) != 1:
        raise GapNode0071PackageV2Error("runner compile anchor differs")
    runner.write_text(
        text.replace(compile_anchor, compile_replacement),
        encoding="utf-8",
        newline="\n",
    )


def _package_preflight(package: Path) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.run(
        [
            sys.executable,
            str(
                package
                / "package_tools/gap_node0071_complete_server_runtime.py"
            ),
            "preflight",
            "--package-root",
            str(package),
        ],
        cwd=package,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode != 0:
        raise GapNode0071PackageV2Error(
            "v2 package preflight failed: "
            f"{process.stdout} {process.stderr}"
        )
    value = json.loads(process.stdout)
    if not isinstance(value, dict) or value.get("valid") is not True:
        raise GapNode0071PackageV2Error(
            "v2 package preflight receipt differs"
        )
    return value


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    if sha256(RETURN_ANALYSIS) != EXPECTED_RETURN_ANALYSIS_SHA256:
        raise GapNode0071PackageV2Error(
            "bound v1 return analysis identity differs"
        )
    package = _extract_bound_source(destination)
    source_numeric_payload = _numeric_payload_records(package)

    _rebind_sca(package)
    _patch_runtime(package)
    _patch_runner(package)
    tools_dir = package / "package_tools"
    shutil.copy2(
        GUARD_SOURCE,
        tools_dir / "gap_node0071_package_observer_guard.py",
    )
    observer = package / "tb_probe/native_return_observer.svh"
    observer.parent.mkdir()
    shutil.copy2(OBSERVER_SOURCE, observer)
    if sha256(observer) != OBSERVER_SHA256:
        raise GapNode0071PackageV2Error("observer source identity differs")
    observer_gate = observer_precompile_receipt(package, OBSERVER_SHA256)
    if not observer_gate["valid"]:
        raise GapNode0071PackageV2Error(
            f"observer static gate failed: {observer_gate['errors']}"
        )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = _replace_identity(manifest)
    manifest.update(
        {
            "schema": "gap-node0071-complete-server-package-v2",
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_ZIP_SHA256,
            "bound_return_analysis": {
                "path": RETURN_ANALYSIS.relative_to(ROOT).as_posix(),
                "sha256": EXPECTED_RETURN_ANALYSIS_SHA256,
            },
            "repair_classification":
                "PACKAGE_LOCAL_OBSERVER_INCLUDE_BINDING_MISSING",
            "repair_evidence": {
                "return_zip_sha256":
                    "f084ccbae33a1e998ed99047da4d8f98d22ed85895b7ed4457ac090449843205",
                "compile_exit_status": 2,
                "simulation_exit_status": 125,
                "compile_log_error_line": 2394,
                "missing_include": "native_return_observer.svh",
            },
            "package_local_observer": {
                "relative_path": "tb_probe/native_return_observer.svh",
                "sha256": OBSERVER_SHA256,
                "read_only": True,
                "server_install": False,
                "compile_binding":
                    "VCS_EXTRA_OPTS=+incdir+<package_root>/tb_probe",
                "precompile_hash_check": True,
                "precompile_receipt_returned": True,
                "xmr_static_gate": observer_gate["xmr_static_gate"],
            },
            "source_numeric_payload_reused_without_rebuild": True,
            "source_numeric_payload_file_count": len(source_numeric_payload),
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_tb_or_observer_install_entries": 0,
            "package_local_tb_or_observer_entries": 1,
            "return_collection_policy": "EXPLICIT_ALLOWLIST_ONLY",
        }
    )
    provenance = manifest.get("generation_provenance")
    if not isinstance(provenance, dict):
        raise GapNode0071PackageV2Error("generation provenance differs")
    provenance.update(
        {
            "tool":
                "tools/build_gap_node0071_complete_server_package_v2.py",
            "command": (
                "bundled-python "
                "tools/build_gap_node0071_complete_server_package_v2.py"
            ),
            "bound_source_package_sha256": SOURCE_ZIP_SHA256,
            "numeric_payload_rebuilt": False,
        }
    )
    observer_allowlist = {
        "source_root": "evidence",
        "source_path": "observer_precompile.json",
        "target_path": "evidence/observer_precompile.json",
        "required": True,
        "max_bytes": 1024 * 1024,
        "missing_meaning": "package-local observer precompile gate unavailable",
    }
    allowlist = manifest.get("return_allowlist")
    if not isinstance(allowlist, list) or len(allowlist) != 59:
        raise GapNode0071PackageV2Error("v1 return allowlist differs")
    allowlist.insert(7, observer_allowlist)
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    checked = _package_preflight(package)

    final_numeric_payload = _numeric_payload_records(package)
    if final_numeric_payload != source_numeric_payload:
        raise GapNode0071PackageV2Error(
            "bound source numeric payload tree drifted"
        )
    return package, {
        "source_numeric_payload_tree_equal": True,
        "source_numeric_payload_file_count": len(source_numeric_payload),
        "observer_static_gate": observer_gate,
        "package_preflight": checked,
    }


def _repeated_build(package: Path, output_zip: Path) -> dict[str, Any]:
    deterministic_zip(package, output_zip, archive_root=INSTALL_NAME)
    first_records = file_records(package, exclude_manifest=False)
    first_sha = sha256(output_zip)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v2-repeat-"
    ) as temporary:
        repeat_root = Path(temporary)
        repeat_package, repeat_proof = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        deterministic_zip(
            repeat_package, repeat_zip, archive_root=INSTALL_NAME
        )
        if first_records != file_records(
            repeat_package, exclude_manifest=False
        ):
            raise GapNode0071PackageV2Error(
                "repeated package trees differ"
            )
        if first_sha != sha256(repeat_zip):
            raise GapNode0071PackageV2Error(
                "repeated deterministic ZIPs differ"
            )
        if not repeat_proof["source_numeric_payload_tree_equal"]:
            raise GapNode0071PackageV2Error(
                "repeated numeric payload proof differs"
            )
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": first_sha,
    }


def _fresh_extract_bootstrap(zip_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v2-bootstrap-"
    ) as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            if archive.testzip() is not None:
                raise GapNode0071PackageV2Error("v2 ZIP CRC failed")
            archive.extractall(root)
        package = root / INSTALL_NAME
        before = file_records(package, exclude_manifest=False)
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        process = subprocess.run(
            [
                sys.executable,
                str(
                    package
                    / "package_tools/"
                    "gap_node0071_complete_server_runtime.py"
                ),
                "preflight",
                "--package-root",
                str(package),
            ],
            cwd=package,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        after = file_records(package, exclude_manifest=False)
        if process.returncode != 0 or before != after:
            raise GapNode0071PackageV2Error(
                "fresh-extract bootstrap immutability failed: "
                f"{process.stdout} {process.stderr}"
            )
    return {
        "runtime_entry_invoked": True,
        "python_dont_write_bytecode": True,
        "tree_unchanged": True,
    }


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
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    output_root.mkdir(parents=True, exist_ok=True)
    try:
        package, proof = build_directory(output_root)
        repeated = _repeated_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        fresh_extract = _fresh_extract_bootstrap(zip_path)
        receipt = {
            "schema": "gap-node0071-complete-package-validation-v2",
            "status": "PACKAGE_READY_NOT_RUN",
            "package": str(package),
            "zip": str(zip_path),
            "zip_sha256": digest,
            "zip_size_bytes": zip_path.stat().st_size,
            "sidecar": str(sidecar),
            "bound_source_zip": str(SOURCE_ZIP),
            "bound_source_zip_sha256": SOURCE_ZIP_SHA256,
            "source_numeric_payload_tree_equal":
                proof["source_numeric_payload_tree_equal"],
            "source_numeric_payload_file_count":
                proof["source_numeric_payload_file_count"],
            "observer_sha256": OBSERVER_SHA256,
            "observer_static_gate":
                proof["observer_static_gate"]["xmr_static_gate"],
            "package_preflight": proof["package_preflight"],
            "preloaded_runtime_readback_target_count": 0,
            "result_gate_fail_closed": True,
            "return_allowlist_only": True,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_file_write_required": False,
            "server_action": False,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "repeated_build": repeated,
            "fresh_extract_bootstrap": fresh_extract,
        }
        write_json(validation_path, receipt)
    except Exception as error:
        print(f"node0071 GAP v2 package build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
