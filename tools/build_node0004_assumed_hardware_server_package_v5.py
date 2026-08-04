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


INSTALL_NAME = "r5_n4_hw_v5_observe"
SOURCE_INSTALL_NAME = "r5_n4_hw_v4_rootbind"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v4_rootbind.zip"
)
SOURCE_ZIP_SHA256 = (
    "61e28a7c218230869ad1a5247023edb9bf8ee9af5a0660124fc8966ce5ad239e"
)
OBSERVER_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
RUNTIME_SOURCE = ROOT / "tools/node0004_assumed_hardware_server_runtime_v5.py"
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_PREFIX = f"install/cfg_pkg/{SOURCE_INSTALL_NAME}/"
CURRENT_PREFIX = f"install/cfg_pkg/{INSTALL_NAME}/"


class PackageBuildV5Error(ValueError):
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
            raise PackageBuildV5Error(f"unsafe source ZIP member: {name}")
        seen.add(name)
        if not info.is_dir():
            result.append(info)
    return result


def _extract_bound_v4(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise PackageBuildV5Error("bound v4 source ZIP identity differs")
    package = destination / INSTALL_NAME
    package.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        entries = _safe_source_entries(archive)
        if archive.testzip() is not None:
            raise PackageBuildV5Error("bound v4 source ZIP CRC failed")
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


def _replace_prefix(value: Any) -> tuple[Any, int]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        count = 0
        for key, item in value.items():
            result[key], delta = _replace_prefix(item)
            count += delta
        return result, count
    if isinstance(value, list):
        result_list: list[Any] = []
        count = 0
        for item in value:
            updated, delta = _replace_prefix(item)
            result_list.append(updated)
            count += delta
        return result_list, count
    if isinstance(value, str) and value.startswith(SOURCE_PREFIX):
        return CURRENT_PREFIX + value[len(SOURCE_PREFIX) :], 1
    return value, 0


def _normalize_prefix(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_prefix(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_prefix(item) for item in value]
    if isinstance(value, str) and value.startswith(SOURCE_PREFIX):
        return "<INSTALL_ROOT>/" + value[len(SOURCE_PREFIX) :]
    if isinstance(value, str) and value.startswith(CURRENT_PREFIX):
        return "<INSTALL_ROOT>/" + value[len(CURRENT_PREFIX) :]
    return value


def _relocate_sca(package: Path) -> dict[str, Any]:
    files = sorted(
        (package / "workload/runtime/runs").glob("*/sca_cfg*.json")
    )
    if len(files) != 54:
        raise PackageBuildV5Error(f"SCA file count differs: {len(files)}")
    changed: list[str] = []
    input_count = 0
    readback_count = 0
    for path in files:
        before = json.loads(path.read_text(encoding="utf-8"))
        after, count = _replace_prefix(before)
        if count == 0 or _normalize_prefix(before) != _normalize_prefix(after):
            raise PackageBuildV5Error(
                f"SCA relocation is not root-only: {path}"
            )
        write_json(path, after)
        changed.append(path.relative_to(package).as_posix())
        if path.name == "sca_cfg.json":
            input_count += count
        else:
            readback_count += count
    if input_count != 526 or readback_count != 320:
        raise PackageBuildV5Error(
            f"SCA leaf inventory differs: {input_count}/{readback_count}"
        )
    return {
        "changed_sca_files": changed,
        "changed_sca_file_count": len(changed),
        "rewritten_path_leaf_count": input_count + readback_count,
        "input_path_leaf_count": input_count,
        "formal_readback_path_leaf_count": readback_count,
        "non_path_json_semantics_equal": True,
    }


def _patch_runner(package: Path) -> None:
    runner = package / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    if text.count(f'install_name="{SOURCE_INSTALL_NAME}"') != 1:
        raise PackageBuildV5Error("v4 runner identity differs")
    text = text.replace(
        f'install_name="{SOURCE_INSTALL_NAME}"',
        f'install_name="{INSTALL_NAME}"',
    )
    old = (
        'timeout --foreground --signal=TERM --kill-after=30s 12h "$simv"'
        '     -l "$run_root/$id/sim.log" +vcs+lic+wait'
        '     "+SCA_CFG=$cfg_root/runs/$id/sca_cfg.json"'
        '     "+SCA_CFG_D=$cfg_root/runs/$id/sca_cfg_D.json"'
    )
    new = (
        'timeout --foreground --signal=TERM --kill-after=30s 12h "$simv" \\\n'
        '    -l "$run_root/$id/sim.log" +vcs+lic+wait \\\n'
        '    "+SCA_CFG=$cfg_root/runs/$id/sca_cfg.json" \\\n'
        '    "+SCA_CFG_D=$cfg_root/runs/$id/sca_cfg_D.json" \\\n'
        '    +RETURN_OBSERVER +RETURN_OBS_SLICE=0 \\\n'
        '    +RETURN_OBS_STALL_CYCLES=4096 \\\n'
        '    +RETURN_OBS_HEARTBEAT_CYCLES=1048576 \\\n'
        '    +RETURN_OBS_DEEP +RETURN_OBS_DEEP_LIMIT=256 \\\n'
        '    +RETURN_OBS_ACCUM_STATE +RETURN_OBS_ACCUM_LIMIT=512 \\\n'
        '    "+RETURN_OBS_FILE=$run_root/$id/return_observer.log"'
    )
    if text.count(old) != 1:
        raise PackageBuildV5Error("v4 run command anchor differs")
    text = text.replace(old, new)
    runner.write_text(text, encoding="utf-8", newline="\n")


def _resolution_receipt(package: Path) -> dict[str, Any]:
    manifest = json.loads(
        (package / "package_manifest.json").read_text(encoding="utf-8")
    )
    tail_inputs = {
        str(record["tail_input"])
        for record in manifest.get("tail_materialization", [])
    }
    static_inputs = 0
    deferred_inputs = 0
    absent_d = 0
    stale = 0
    for path in sorted(
        (package / "workload/runtime/runs").glob("*/sca_cfg*.json")
    ):
        text = path.read_text(encoding="utf-8")
        stale += text.count(SOURCE_PREFIX)
        value = json.loads(text)
        stack: list[Any] = [value]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, str) and item.startswith(CURRENT_PREFIX):
                relative = item[len(CURRENT_PREFIX) :]
                target = package / "workload/runtime" / Path(
                    *PurePosixPath(relative).parts
                )
                if path.name == "sca_cfg_D.json":
                    if target.exists():
                        raise PackageBuildV5Error(
                            f"preloaded formal D target: {target}"
                        )
                    absent_d += 1
                elif target.is_file():
                    static_inputs += 1
                elif relative in tail_inputs:
                    deferred_inputs += 1
                else:
                    raise PackageBuildV5Error(
                        f"unresolved SCA input: {relative}"
                    )
    if (stale, static_inputs, deferred_inputs, absent_d) != (0, 398, 128, 320):
        raise PackageBuildV5Error(
            "path resolution differs: "
            f"{stale}/{static_inputs}/{deferred_inputs}/{absent_d}"
        )
    return {
        "stale_install_path_count": stale,
        "static_input_path_count": static_inputs,
        "deferred_tail_input_path_count": deferred_inputs,
        "absent_formal_readback_path_count": absent_d,
        "all_static_inputs_resolve": True,
        "all_formal_readbacks_begin_absent": True,
    }


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    package = _extract_bound_v4(destination)
    source_records = package_records(package, exclude_manifest=False)
    relocation = _relocate_sca(package)
    _patch_runner(package)
    shutil.copy2(
        RUNTIME_SOURCE,
        package / "package_tools/node0004_assumed_hardware_server_runtime.py",
    )
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-assumed-hardware-server-package-v5",
            "install_name": INSTALL_NAME,
            "supersedes_package_sha256": SOURCE_ZIP_SHA256,
            "repair_reason": [
                "v4 compile and all 86 c0 matrix transfers succeeded",
                "v4 simulator command omitted +RETURN_OBSERVER, so the "
                "compiled package-local observer remained disabled",
                "v4 c0 hit the external 12h timeout after slice start with "
                "no internal checkpoint evidence and no formal D",
            ],
            "package_side_relocation": {
                "classification": "INSTALL_NAMESPACE_REBIND_ONLY",
                "old_prefix": SOURCE_PREFIX,
                "new_prefix": CURRENT_PREFIX,
                **relocation,
            },
            "observer_runtime_binding": {
                "enabled": True,
                "slice": 0,
                "stall_cycles": 4096,
                "heartbeat_cycles": 1048576,
                "deep_enabled": True,
                "deep_limit": 256,
                "accum_state_enabled": True,
                "accum_limit": 512,
                "per_run_output": "runs/<run_id>/return_observer.log",
                "return_allowlisted": True,
                "max_return_bytes_per_log": 8388608,
            },
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "source_package_reused_read_only": True,
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
    resolution = _resolution_receipt(package)
    observer = observer_precompile_receipt(package, OBSERVER_SHA256)
    if not observer["valid"]:
        raise PackageBuildV5Error(
            f"observer static gate failed: {observer['errors']}"
        )
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    required_runner_tokens = (
        "+RETURN_OBSERVER",
        "+RETURN_OBS_DEEP",
        "+RETURN_OBS_ACCUM_STATE",
        "return_observer.log",
    )
    if any(token not in runner for token in required_runner_tokens):
        raise PackageBuildV5Error("observer runtime binding is incomplete")

    final_records = package_records(package, exclude_manifest=False)
    expected_changed = {
        "PREPARE_AND_RUN.sh",
        "package_manifest.json",
        "package_tools/node0004_assumed_hardware_server_runtime.py",
        *relocation["changed_sca_files"],
    }
    observed_changed = {
        name
        for name in set(source_records) | set(final_records)
        if source_records.get(name) != final_records.get(name)
    }
    if observed_changed != expected_changed:
        raise PackageBuildV5Error(
            "v4->v5 changed-file set differs: "
            f"unexpected={sorted(observed_changed - expected_changed)} "
            f"missing={sorted(expected_changed - observed_changed)}"
        )
    return package, {
        "source_file_count": len(source_records),
        "changed_file_count": len(observed_changed),
        "unchanged_file_count": len(source_records) - len(observed_changed),
        "relocation": relocation,
        "path_resolution": resolution,
        "observer": observer,
    }


def _repeated_build(package: Path, output_zip: Path) -> dict[str, Any]:
    base.deterministic_zip(package, output_zip)
    first_records = package_records(package, exclude_manifest=False)
    first_sha = sha256(output_zip)
    with tempfile.TemporaryDirectory(prefix="node0004-v5-repeat-") as temporary:
        repeat_root = Path(temporary)
        repeat_package, repeat_proof = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        if first_records != package_records(
            repeat_package, exclude_manifest=False
        ):
            raise PackageBuildV5Error("repeated package trees differ")
        if first_sha != sha256(repeat_zip):
            raise PackageBuildV5Error("repeated deterministic ZIPs differ")
        if repeat_proof["path_resolution"]["stale_install_path_count"] != 0:
            raise PackageBuildV5Error("repeat resolution differs")
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
            "schema": "node0004-assumed-hardware-package-validation-v5",
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
            "v4_to_v5_changed_file_count": proof["changed_file_count"],
            "v4_to_v5_unchanged_file_count": proof["unchanged_file_count"],
            "relocation": proof["relocation"],
            "path_resolution": proof["path_resolution"],
            "observer_sha256": OBSERVER_SHA256,
            "observer_static_gate": proof["observer"]["xmr_static_gate"],
            "observer_runtime_enabled": True,
            "observer_log_return_allowlisted": True,
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
