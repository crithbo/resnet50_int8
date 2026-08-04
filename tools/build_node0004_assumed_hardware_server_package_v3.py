from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_assumed_hardware_server_package as base  # noqa: E402
from tools.node0004_assumed_hardware_server_runtime_v2 import (  # noqa: E402
    package_records,
    preflight,
)
from tools.node0004_package_observer_guard import (  # noqa: E402
    observer_precompile_receipt,
)


INSTALL_NAME = "r5_n4_hw_v3_obs"
SOURCE_INSTALL_NAME = "r5_node0004_hw_v2_failclosed"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_node0004_hw_v2_failclosed.zip"
)
SOURCE_ZIP_SHA256 = (
    "4bc0be9903e877b79cb11a82997ad5d6b5c6eed36666ec5a47771e83eb339446"
)
OBSERVER_SOURCE = ROOT / "NDP_copy01/native_return_observer.svh"
OBSERVER_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
GUARD_SOURCE = ROOT / "tools/node0004_package_observer_guard.py"
RUNTIME_V3_SOURCE = (
    ROOT / "tools/node0004_assumed_hardware_server_runtime_v3.py"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


class PackageBuildV3Error(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _safe_source_entries(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
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
            raise PackageBuildV3Error(f"unsafe source ZIP member: {name}")
        seen.add(name)
        if not info.is_dir():
            result.append(info)
    return result


def _extract_bound_v2(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise PackageBuildV3Error("bound v2 source ZIP identity differs")
    package = destination / INSTALL_NAME
    package.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        entries = _safe_source_entries(archive)
        if archive.testzip() is not None:
            raise PackageBuildV3Error("bound v2 source ZIP CRC failed")
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


def _payload_records(package: Path) -> dict[str, Any]:
    records = package_records(package, exclude_manifest=False)
    return {
        name: value
        for name, value in records.items()
        if name.startswith("workload/") or name.startswith("validation/")
    }


def _patch_runner(script_path: Path) -> None:
    text = script_path.read_text(encoding="utf-8")
    if text.count(SOURCE_INSTALL_NAME) != 1:
        raise PackageBuildV3Error("v2 runner install identity is not unique")
    text = text.replace(SOURCE_INSTALL_NAME, INSTALL_NAME)

    trap_anchor = 'trap \'finalize $?\' EXIT\ncd "$server_root"\n'
    guard_block = f"""trap 'finalize $?' EXIT
observer_guard="${{package_root}}/package_tools/node0004_package_observer_guard.py"
python3 "$observer_guard" --package-root "$package_root" \\
  --expected-sha256 "{OBSERVER_SHA256}" \\
  > "$evidence_root/observer_precompile.json" || exit 7
cd "$server_root"
"""
    if text.count(trap_anchor) != 1:
        raise PackageBuildV3Error("runner trap anchor differs")
    text = text.replace(trap_anchor, guard_block)

    compile_lines = [
        line
        for line in text.splitlines()
        if line.startswith(
            "timeout --foreground --signal=TERM --kill-after=30s 2h"
        )
        and "Makefile.tb_NDP_Top_new_phy compile" in line
    ]
    if len(compile_lines) != 1:
        raise PackageBuildV3Error("runner compile anchor differs")
    compile_replacement = (
        "timeout --foreground --signal=TERM --kill-after=30s 2h \\\n"
        "  make -f Makefile.tb_NDP_Top_new_phy compile "
        "DUMP_VCD=0 DUMP_FSDB=0 \\\n"
        '  TB_DUMP_FSDB=0 RUN_DIR="$run_root/compile" \\\n'
        '  VCS_EXTRA_OPTS="+incdir+$package_root/tb_probe" \\\n'
        '  > "$run_root/compile/sim_results/compile_driver.log" 2>&1'
    )
    text = text.replace(compile_lines[0], compile_replacement)
    script_path.write_text(text, encoding="utf-8", newline="\n")


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    package = _extract_bound_v2(destination)
    source_payload = _payload_records(package)
    tools_dir = package / "package_tools"
    bundled_runtime = (
        tools_dir / "node0004_assumed_hardware_server_runtime.py"
    )
    base_runtime = (
        tools_dir / "node0004_assumed_hardware_server_runtime_v2_base.py"
    )
    bundled_runtime.replace(base_runtime)
    shutil.copy2(RUNTIME_V3_SOURCE, bundled_runtime)
    shutil.copy2(
        GUARD_SOURCE, tools_dir / "node0004_package_observer_guard.py"
    )

    observer = package / "tb_probe/native_return_observer.svh"
    observer.parent.mkdir()
    shutil.copy2(OBSERVER_SOURCE, observer)
    if sha256(observer) != OBSERVER_SHA256:
        raise PackageBuildV3Error("observer source identity differs")
    observer_gate = observer_precompile_receipt(package, OBSERVER_SHA256)
    if not observer_gate["valid"]:
        raise PackageBuildV3Error(
            f"observer static gate failed: {observer_gate['errors']}"
        )

    runner = package / "PREPARE_AND_RUN.sh"
    _patch_runner(runner)
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-assumed-hardware-server-package-v3",
            "install_name": INSTALL_NAME,
            "supersedes_package_sha256": SOURCE_ZIP_SHA256,
            "repair_reason": [
                "v2 return compile.log:2396-2401 reports the server TB "
                "cannot resolve native_return_observer.svh",
                "v2 source package contains zero observer entries",
                "v2 compile command supplies no package-local observer "
                "include directory",
            ],
            "package_local_observer": {
                "relative_path": "tb_probe/native_return_observer.svh",
                "sha256": OBSERVER_SHA256,
                "read_only": True,
                "server_install": False,
                "compile_binding": (
                    "VCS_EXTRA_OPTS=+incdir+<package_root>/tb_probe"
                ),
                "precompile_hash_check": True,
                "precompile_receipt_returned": True,
                "xmr_static_gate": observer_gate["xmr_static_gate"],
            },
            "source_payload_reused_without_numeric_rebuild": True,
            "source_payload_file_count": len(source_payload),
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY",
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_tb_or_observer_install_entries": 0,
            "package_local_tb_or_observer_entries": 1,
            "return_collection_policy": "EXPLICIT_ALLOWLIST_ONLY",
        }
    )
    manifest["files"] = package_records(package)
    write_json(manifest_path, manifest)
    preflight(package)
    final_payload = _payload_records(package)
    if source_payload != final_payload:
        raise PackageBuildV3Error("v2 workload/validation payload drifted")
    return package, {
        "source_payload_tree_equal": True,
        "source_payload_file_count": len(source_payload),
        "observer_static_gate": observer_gate,
    }


def _repeated_build(
    package: Path, output_zip: Path
) -> dict[str, Any]:
    base.deterministic_zip(package, output_zip)
    first_records = package_records(package, exclude_manifest=False)
    first_sha = sha256(output_zip)
    with tempfile.TemporaryDirectory(prefix="node0004-v3-repeat-") as temporary:
        repeat_root = Path(temporary)
        repeat_package, repeat_proof = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        if first_records != package_records(
            repeat_package, exclude_manifest=False
        ):
            raise PackageBuildV3Error("repeated package trees differ")
        if first_sha != sha256(repeat_zip):
            raise PackageBuildV3Error("repeated deterministic ZIPs differ")
        if not repeat_proof["source_payload_tree_equal"]:
            raise PackageBuildV3Error("repeated payload proof differs")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": first_sha,
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
            f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
        )
        receipt = {
            "schema": "node0004-assumed-hardware-package-validation-v3",
            "status": "PACKAGE_READY_NOT_RUN",
            "package": str(package),
            "zip": str(zip_path),
            "zip_sha256": digest,
            "sidecar": str(sidecar),
            "bound_source_zip": str(SOURCE_ZIP),
            "bound_source_zip_sha256": SOURCE_ZIP_SHA256,
            "package_file_count": len(
                package_records(package, exclude_manifest=False)
            ),
            "source_payload_tree_equal": proof[
                "source_payload_tree_equal"
            ],
            "source_payload_file_count": proof["source_payload_file_count"],
            "observer_sha256": OBSERVER_SHA256,
            "observer_static_gate": proof["observer_static_gate"][
                "xmr_static_gate"
            ],
            "preloaded_runtime_readback_target_count": 0,
            "result_gate_fail_closed": True,
            "return_allowlist_only": True,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_file_write_required": False,
            "server_action": False,
            "repeated_build": repeated,
        }
        write_json(validation_path, receipt)
    except Exception as error:
        print(f"package build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
