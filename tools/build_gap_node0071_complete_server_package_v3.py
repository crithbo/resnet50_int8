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
)


INSTALL_NAME = "r5_n71_gap_v3_cwd"
SOURCE_INSTALL_NAME = "r5_n71_gap_v2_obs"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v2_obs.zip"
)
SOURCE_ZIP_SHA256 = (
    "c3fe06f6e0110b41936b69ae264a24b2dc2d76779efc589c4fe34378b6891b8f"
)
SCREENSHOT_SHA256 = (
    "a4a900636544d1ad49a6da8c86a27327ab49989f9c6c6aa3b8521478ed51a9db"
)
OUTPUT_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
)


class GapNode0071PackageV3Error(ValueError):
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
    prefix = f"{SOURCE_INSTALL_NAME}/"
    result: list[zipfile.ZipInfo] = []
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
            or not name.startswith(prefix)
        ):
            raise GapNode0071PackageV3Error(
                f"unsafe source ZIP member: {name}"
            )
        seen.add(name)
        if not info.is_dir():
            result.append(info)
    return result


def _extract_bound_source(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise GapNode0071PackageV3Error("bound v2 source ZIP identity differs")
    package = destination / INSTALL_NAME
    if package.exists():
        raise GapNode0071PackageV3Error(
            f"fresh package identity required: {package}"
        )
    package.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise GapNode0071PackageV3Error("bound v2 source ZIP CRC failed")
        for info in _safe_source_entries(archive):
            relative = PurePosixPath(info.filename).relative_to(
                SOURCE_INSTALL_NAME
            )
            target = package / Path(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    return package


def _frozen_payload_records(package: Path) -> dict[str, Any]:
    excluded = {
        "PREPARE_AND_RUN.sh",
        "TEST_PACKAGE_MANIFEST.json",
        "workload/sca_cfg.json",
        "workload/sca_cfg_D.json",
    }
    return {
        name: record
        for name, record in file_records(
            package, exclude_manifest=False
        ).items()
        if name not in excluded
    }


def _replace_identity(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(SOURCE_INSTALL_NAME, INSTALL_NAME)
    if isinstance(value, list):
        return [_replace_identity(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _replace_identity(item)
            for key, item in value.items()
        }
    return value


def _rebind_sca(package: Path) -> None:
    for relative in ("workload/sca_cfg.json", "workload/sca_cfg_D.json"):
        path = package / relative
        original = json.loads(path.read_text(encoding="utf-8"))
        rebound = _replace_identity(original)
        if rebound == original:
            raise GapNode0071PackageV3Error(
                f"SCA identity replacement absent: {relative}"
            )
        write_json(path, rebound)
        if SOURCE_INSTALL_NAME in path.read_text(encoding="utf-8"):
            raise GapNode0071PackageV3Error(
                f"stale v2 identity remains: {relative}"
            )


def _patch_runner(package: Path) -> None:
    runner = package / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    if text.count(SOURCE_INSTALL_NAME) != 1:
        raise GapNode0071PackageV3Error(
            "v2 runner install identity is not unique"
        )
    text = text.replace(SOURCE_INSTALL_NAME, INSTALL_NAME)

    receipt_anchor = (
        "; <unique-run>/sim_results/simv "
        "+SCA_CFG=install/cfg_pkg/${install_name}/sca_cfg.json "
        "+SCA_CFG_D=install/cfg_pkg/${install_name}/sca_cfg_D.json"
    )
    receipt_replacement = (
        "; (cd <user-root> && <unique-run>/sim_results/simv "
        "+SCA_CFG=install/cfg_pkg/${install_name}/sca_cfg.json "
        "+SCA_CFG_D=install/cfg_pkg/${install_name}/sca_cfg_D.json)"
    )
    if text.count(receipt_anchor) != 1:
        raise GapNode0071PackageV3Error(
            "server-command receipt anchor differs"
        )
    text = text.replace(receipt_anchor, receipt_replacement)

    simulation_anchor = """if [ "$compile_status" -eq 0 ]; then
  timeout --foreground --signal=TERM --kill-after=30s 12h     "$run_root/sim_results/simv"     -l "$run_root/sim_results/sim.log" +vcs+lic+wait +sim_time=100ms     +BITSTREAM=install/bitstream.txt     +SCA_CFG="install/cfg_pkg/${install_name}/sca_cfg.json"     +SCA_CFG_D="install/cfg_pkg/${install_name}/sca_cfg_D.json"
  simulation_status=$?
fi
"""
    simulation_replacement = """if [ "$compile_status" -eq 0 ]; then
  (
    cd "$server_root"
    timeout --foreground --signal=TERM --kill-after=30s 12h \\
      "$run_root/sim_results/simv" \\
      -l "$run_root/sim_results/sim.log" +vcs+lic+wait +sim_time=100ms \\
      +BITSTREAM=install/bitstream.txt \\
      +SCA_CFG="install/cfg_pkg/${install_name}/sca_cfg.json" \\
      +SCA_CFG_D="install/cfg_pkg/${install_name}/sca_cfg_D.json"
  )
  simulation_status=$?
fi
"""
    if text.count(simulation_anchor) != 1:
        raise GapNode0071PackageV3Error(
            "simulation working-directory anchor differs"
        )
    text = text.replace(simulation_anchor, simulation_replacement)
    runner.write_text(text, encoding="utf-8", newline="\n")


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
        raise GapNode0071PackageV3Error(
            "v3 package preflight failed: "
            f"{process.stdout} {process.stderr}"
        )
    value = json.loads(process.stdout)
    if not isinstance(value, dict) or value.get("valid") is not True:
        raise GapNode0071PackageV3Error(
            "v3 package preflight receipt differs"
        )
    return value


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    package = _extract_bound_source(destination)
    frozen_before = _frozen_payload_records(package)
    _rebind_sca(package)
    _patch_runner(package)

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = _replace_identity(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    manifest.update(
        {
            "schema": "gap-node0071-complete-server-package-v3",
            "status": "PACKAGE_READY_NOT_RUN",
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_ZIP_SHA256,
            "repair_classification":
                "PACKAGE_RUNNER_CWD_NOT_BOUND_TO_SERVER_ROOT",
            "repair_evidence": {
                "screenshot_sha256": SCREENSHOT_SHA256,
                "screenshot_time_ps": 7794000,
                "server_root": "/home/panqs/ndp/NDP_copy02",
                "failed_relative_path": (
                    "install/cfg_pkg/r5_n71_gap_v2_obs/sca_cfg.json"
                ),
                "tb_lines": [3075, 3077],
                "first_divergence":
                    "SCA_CFG_OPEN_FAILED_BEFORE_NUMERIC_EXECUTION",
            },
            "runner_working_directory_contract": {
                "compile_cwd": "server_root via make -C",
                "simulation_cwd": "server_root via explicit subshell cd",
                "relative_path_owner": "server_root",
            },
            "source_numeric_payload_reused_without_rebuild": True,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_run_performed": False,
            "uploaded": False,
            "lease_acquired": False,
        }
    )
    provenance = manifest.get("generation_provenance")
    if not isinstance(provenance, dict):
        raise GapNode0071PackageV3Error("generation provenance differs")
    provenance.update(
        {
            "tool":
                "tools/build_gap_node0071_complete_server_package_v3.py",
            "command": (
                "bundled-python "
                "tools/build_gap_node0071_complete_server_package_v3.py"
            ),
            "bound_source_package_sha256": SOURCE_ZIP_SHA256,
            "numeric_payload_rebuilt": False,
            "runner_only_repair": True,
        }
    )
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    checked = _package_preflight(package)

    frozen_after = _frozen_payload_records(package)
    if frozen_after != frozen_before:
        raise GapNode0071PackageV3Error(
            "frozen numeric/config payload tree drifted"
        )
    runner_text = (package / "PREPARE_AND_RUN.sh").read_text(
        encoding="utf-8"
    )
    if (
        'cd "$server_root"' not in runner_text
        or SOURCE_INSTALL_NAME in runner_text
    ):
        raise GapNode0071PackageV3Error(
            "runner cwd or fresh identity gate differs"
        )
    return package, {
        "frozen_payload_tree_equal": True,
        "frozen_payload_file_count": len(frozen_after),
        "package_preflight": checked,
        "simulation_cwd_bound_to_server_root": True,
    }


def _repeated_build(package: Path, output_zip: Path) -> dict[str, Any]:
    deterministic_zip(package, output_zip, archive_root=INSTALL_NAME)
    first_records = file_records(package, exclude_manifest=False)
    first_sha = sha256(output_zip)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v3-repeat-"
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
            raise GapNode0071PackageV3Error(
                "repeated package trees differ"
            )
        if first_sha != sha256(repeat_zip):
            raise GapNode0071PackageV3Error(
                "repeated deterministic ZIPs differ"
            )
        if not repeat_proof["frozen_payload_tree_equal"]:
            raise GapNode0071PackageV3Error(
                "repeated frozen payload proof differs"
            )
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": first_sha,
    }


def _fresh_extract_bootstrap(zip_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v3-bootstrap-"
    ) as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            if archive.testzip() is not None:
                raise GapNode0071PackageV3Error("v3 ZIP CRC failed")
            archive.extractall(root)
        package = root / INSTALL_NAME
        before = file_records(package, exclude_manifest=False)
        checked = _package_preflight(package)
        after = file_records(package, exclude_manifest=False)
        if before != after:
            raise GapNode0071PackageV3Error(
                "fresh-extract bootstrap changed package tree"
            )
    return {
        "runtime_entry_invoked": True,
        "python_dont_write_bytecode": True,
        "tree_unchanged": True,
        "preflight": checked,
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
            "schema": "gap-node0071-complete-package-validation-v3",
            "status": "PACKAGE_READY_NOT_RUN",
            "package": str(package),
            "zip": str(zip_path),
            "zip_sha256": digest,
            "zip_size_bytes": zip_path.stat().st_size,
            "sidecar": str(sidecar),
            "bound_source_zip": str(SOURCE_ZIP),
            "bound_source_zip_sha256": SOURCE_ZIP_SHA256,
            "screenshot_sha256": SCREENSHOT_SHA256,
            "first_divergence":
                "SCA_CFG_OPEN_FAILED_BEFORE_NUMERIC_EXECUTION",
            "repair_classification":
                "PACKAGE_RUNNER_CWD_NOT_BOUND_TO_SERVER_ROOT",
            "simulation_cwd_bound_to_server_root":
                proof["simulation_cwd_bound_to_server_root"],
            "frozen_payload_tree_equal":
                proof["frozen_payload_tree_equal"],
            "frozen_payload_file_count":
                proof["frozen_payload_file_count"],
            "package_preflight": proof["package_preflight"],
            "preloaded_runtime_readback_target_count": 0,
            "result_gate_fail_closed": True,
            "return_allowlist_only": True,
            "functional_rtl_modified": False,
            "server_action": False,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "repeated_build": repeated,
            "fresh_extract_bootstrap": fresh_extract,
        }
        write_json(validation_path, receipt)
    except Exception as error:
        print(
            f"node0071 GAP v3 package build failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
