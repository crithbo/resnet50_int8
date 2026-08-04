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


INSTALL_NAME = "r5_n4_hw_v4_rootbind"
SOURCE_INSTALL_NAME = "r5_n4_hw_v3_obs"
STALE_INSTALL_NAME = "r5_node0004_hw_v2_failclosed"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v3_obs.zip"
)
SOURCE_ZIP_SHA256 = (
    "84c834de989c7912edfd711cd5fb2bdfe51e40998bb493d3e4ec5b99da9a331c"
)
OBSERVER_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
STALE_PREFIX = f"install/cfg_pkg/{STALE_INSTALL_NAME}/"
CURRENT_PREFIX = f"install/cfg_pkg/{INSTALL_NAME}/"
EXPECTED_SCA_FILE_COUNT = 54
EXPECTED_SCA_PATH_LEAF_COUNT = 846
EXPECTED_SCA_INPUT_PATH_LEAF_COUNT = 526
EXPECTED_SCA_D_PATH_LEAF_COUNT = 320


class PackageBuildV4Error(ValueError):
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
            raise PackageBuildV4Error(f"unsafe source ZIP member: {name}")
        seen.add(name)
        if not info.is_dir():
            result.append(info)
    return result


def _extract_bound_v3(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise PackageBuildV4Error("bound v3 source ZIP identity differs")
    package = destination / INSTALL_NAME
    package.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        entries = _safe_source_entries(archive)
        if archive.testzip() is not None:
            raise PackageBuildV4Error("bound v3 source ZIP CRC failed")
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


def _replace_path_leaves(value: Any) -> tuple[Any, int]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        count = 0
        for key, item in value.items():
            result[key], delta = _replace_path_leaves(item)
            count += delta
        return result, count
    if isinstance(value, list):
        result_list: list[Any] = []
        count = 0
        for item in value:
            updated, delta = _replace_path_leaves(item)
            result_list.append(updated)
            count += delta
        return result_list, count
    if isinstance(value, str) and value.startswith(STALE_PREFIX):
        return CURRENT_PREFIX + value[len(STALE_PREFIX) :], 1
    return value, 0


def _normalize_install_root(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_install_root(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_install_root(item) for item in value]
    if isinstance(value, str) and value.startswith(CURRENT_PREFIX):
        return "<INSTALL_ROOT>/" + value[len(CURRENT_PREFIX) :]
    if isinstance(value, str) and value.startswith(STALE_PREFIX):
        return "<INSTALL_ROOT>/" + value[len(STALE_PREFIX) :]
    return value


def _relocate_sca_paths(package: Path) -> dict[str, Any]:
    sca_files = sorted(
        (package / "workload/runtime/runs").glob("*/sca_cfg*.json")
    )
    if len(sca_files) != EXPECTED_SCA_FILE_COUNT:
        raise PackageBuildV4Error(
            f"SCA file count differs: {len(sca_files)}"
        )
    changed_files: list[str] = []
    input_count = 0
    readback_count = 0
    for path in sca_files:
        before = json.loads(path.read_text(encoding="utf-8"))
        after, count = _replace_path_leaves(before)
        if count == 0 or _normalize_install_root(before) != _normalize_install_root(after):
            raise PackageBuildV4Error(
                f"SCA relocation is not a pure install-root rewrite: {path}"
            )
        serialized = json.dumps(after, ensure_ascii=False)
        if STALE_PREFIX in serialized or SOURCE_INSTALL_NAME in serialized:
            raise PackageBuildV4Error(f"stale install identity remains: {path}")
        write_json(path, after)
        relative = path.relative_to(package).as_posix()
        changed_files.append(relative)
        if path.name == "sca_cfg.json":
            input_count += count
        elif path.name == "sca_cfg_D.json":
            readback_count += count
        else:
            raise PackageBuildV4Error(f"unexpected SCA filename: {path}")
    total = input_count + readback_count
    if (
        total != EXPECTED_SCA_PATH_LEAF_COUNT
        or input_count != EXPECTED_SCA_INPUT_PATH_LEAF_COUNT
        or readback_count != EXPECTED_SCA_D_PATH_LEAF_COUNT
    ):
        raise PackageBuildV4Error(
            "SCA path-leaf inventory differs: "
            f"total={total} input={input_count} readback={readback_count}"
        )
    return {
        "changed_sca_files": changed_files,
        "changed_sca_file_count": len(changed_files),
        "rewritten_path_leaf_count": total,
        "input_path_leaf_count": input_count,
        "formal_readback_path_leaf_count": readback_count,
        "non_path_json_semantics_equal": True,
    }


def _path_resolution_receipt(package: Path) -> dict[str, Any]:
    manifest = json.loads(
        (package / "package_manifest.json").read_text(encoding="utf-8")
    )
    tail_inputs = {
        str(record["tail_input"])
        for record in manifest.get("tail_materialization", [])
    }
    static_inputs = 0
    deferred_tail_inputs = 0
    absent_formal_readbacks = 0
    stale = 0
    for path in sorted(
        (package / "workload/runtime/runs").glob("*/sca_cfg*.json")
    ):
        value = json.loads(path.read_text(encoding="utf-8"))
        stack: list[Any] = [value]
        strings: list[str] = []
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, str) and "install/cfg_pkg/" in item:
                strings.append(item)
        for item in strings:
            if not item.startswith(CURRENT_PREFIX):
                stale += 1
                continue
            relative = item[len(CURRENT_PREFIX) :]
            target = package / "workload/runtime" / Path(
                *PurePosixPath(relative).parts
            )
            if path.name == "sca_cfg_D.json":
                if target.exists():
                    raise PackageBuildV4Error(
                        f"formal readback target is preloaded: {target}"
                    )
                absent_formal_readbacks += 1
            elif target.is_file():
                static_inputs += 1
            elif relative in tail_inputs:
                deferred_tail_inputs += 1
            else:
                raise PackageBuildV4Error(
                    f"unresolved package-local SCA input: {relative}"
                )
    if (
        stale != 0
        or static_inputs != 398
        or deferred_tail_inputs != 128
        or absent_formal_readbacks != 320
    ):
        raise PackageBuildV4Error(
            "path-resolution inventory differs: "
            f"stale={stale} static={static_inputs} "
            f"deferred={deferred_tail_inputs} D={absent_formal_readbacks}"
        )
    return {
        "server_cwd_contract": "<user-supplied-NDP-root>",
        "install_root": f"install/cfg_pkg/{INSTALL_NAME}",
        "stale_install_path_count": stale,
        "static_input_path_count": static_inputs,
        "deferred_tail_input_path_count": deferred_tail_inputs,
        "absent_formal_readback_path_count": absent_formal_readbacks,
        "all_static_inputs_resolve": True,
        "all_formal_readbacks_begin_absent": True,
    }


def _patch_runner(package: Path) -> None:
    runner = package / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    if text.count(f'install_name="{SOURCE_INSTALL_NAME}"') != 1:
        raise PackageBuildV4Error("v3 runner install identity differs")
    text = text.replace(
        f'install_name="{SOURCE_INSTALL_NAME}"',
        f'install_name="{INSTALL_NAME}"',
    )
    if SOURCE_INSTALL_NAME in text or STALE_INSTALL_NAME in text:
        raise PackageBuildV4Error("stale install identity remains in runner")
    runner.write_text(text, encoding="utf-8", newline="\n")


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    package = _extract_bound_v3(destination)
    source_records = package_records(package, exclude_manifest=False)
    relocation = _relocate_sca_paths(package)
    _patch_runner(package)
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-assumed-hardware-server-package-v4",
            "install_name": INSTALL_NAME,
            "supersedes_package_sha256": SOURCE_ZIP_SHA256,
            "repair_reason": [
                "v3 return compiled successfully but c0 sim.log first failed "
                "to open a path under the stale v2 install namespace",
                "all 54 SCA/SCA_D files retained the v2 install prefix while "
                "the v3 runner installed under r5_n4_hw_v3_obs",
                "the v3 c0 run timed out with 320/320 formal D targets missing",
            ],
            "package_side_relocation": {
                "classification": "INSTALL_NAMESPACE_REBIND_ONLY",
                "old_prefix": STALE_PREFIX,
                "new_prefix": CURRENT_PREFIX,
                **relocation,
            },
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "source_package_reused_read_only": True,
            "source_non_sca_payload_reused_byte_exact": True,
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY",
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "return_collection_policy": "EXPLICIT_ALLOWLIST_ONLY",
        }
    )
    manifest["files"] = package_records(package)
    write_json(manifest_path, manifest)
    preflight(package)
    resolution = _path_resolution_receipt(package)
    observer = observer_precompile_receipt(package, OBSERVER_SHA256)
    if not observer["valid"]:
        raise PackageBuildV4Error(
            f"observer identity/static gate failed: {observer['errors']}"
        )

    final_records = package_records(package, exclude_manifest=False)
    expected_changed = {
        "PREPARE_AND_RUN.sh",
        "package_manifest.json",
        *relocation["changed_sca_files"],
    }
    observed_changed = {
        name
        for name in set(source_records) | set(final_records)
        if source_records.get(name) != final_records.get(name)
    }
    if observed_changed != expected_changed:
        raise PackageBuildV4Error(
            "v3->v4 changed-file set differs: "
            f"unexpected={sorted(observed_changed - expected_changed)} "
            f"missing={sorted(expected_changed - observed_changed)}"
        )
    return package, {
        "source_file_count": len(source_records),
        "changed_file_count": len(observed_changed),
        "changed_files": sorted(observed_changed),
        "relocation": relocation,
        "path_resolution": resolution,
        "observer": observer,
        "unchanged_file_count": len(source_records) - len(observed_changed),
    }


def _repeated_build(package: Path, output_zip: Path) -> dict[str, Any]:
    base.deterministic_zip(package, output_zip)
    first_records = package_records(package, exclude_manifest=False)
    first_sha = sha256(output_zip)
    with tempfile.TemporaryDirectory(prefix="node0004-v4-repeat-") as temporary:
        repeat_root = Path(temporary)
        repeat_package, repeat_proof = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        if first_records != package_records(
            repeat_package, exclude_manifest=False
        ):
            raise PackageBuildV4Error("repeated package trees differ")
        if first_sha != sha256(repeat_zip):
            raise PackageBuildV4Error("repeated deterministic ZIPs differ")
        if repeat_proof["path_resolution"]["stale_install_path_count"] != 0:
            raise PackageBuildV4Error("repeated path-resolution proof differs")
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
            "schema": "node0004-assumed-hardware-package-validation-v4",
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
            "v3_to_v4_changed_file_count": proof["changed_file_count"],
            "v3_to_v4_unchanged_file_count": proof["unchanged_file_count"],
            "relocation": proof["relocation"],
            "path_resolution": proof["path_resolution"],
            "observer_sha256": OBSERVER_SHA256,
            "observer_static_gate": proof["observer"]["xmr_static_gate"],
            "preloaded_runtime_readback_target_count": 0,
            "result_gate_fail_closed": True,
            "return_allowlist_only": True,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
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
