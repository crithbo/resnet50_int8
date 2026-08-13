#!/usr/bin/env python3
"""Reissue the four current packages with repeat-safe install runtime state.

Only runner/runtime-layout/return-publication surfaces are changed.  Package
identity, workload, config, mapping, bitstream, execplan, observer and RTL
members remain byte-equal to the exact source ZIPs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SHARED_HELPER = ROOT / "tools/server_package_runtime_layout.py"
OLD_HELPER_SHA = (
    "7969ca56e13a7e0a0a83bdfd48d1409d28eef2ae0fd63ad08f0ec5c39e2d848a"
)
REPEAT_CONTRACT = {
    "mode": "RESET_EXACT_PACKAGE_OWNED_RUNTIME_ROOTS",
    "cfg_root_policy": "RESET_AND_RECREATE_EXACT_INSTALL_NAME",
    "run_root_policy": "RESET_AND_RECREATE_EXACT_PACKAGE_ATTEMPT",
    "foreign_sibling_policy": "PRESERVE",
    "symlink_or_special_entry_policy": "FAIL_CLOSED",
    "ownership_marker": ".codex_owner.{name}.json",
    "return_name_policy": "UNIQUE_PER_EXECUTION_PRESERVE_PRIOR_RETURNS",
}
SOURCES = {
    "r5_n71_gap_v50_ga_ob_conjunction_diag": {
        "sha256": (
            "e0eb03f4cba385e054b280c1e3915765a7465bb17f359bf7048669a6951a1c5a"
        ),
        "manifest": "TEST_PACKAGE_MANIFEST.json",
        "runtime": "package_tools/gap_node0071_complete_server_runtime.py",
        "family": "gap_node0071",
    },
    "r5_qadd_n7_fullchain_returnfix_v46": {
        "sha256": (
            "58f5204886fef6015501dedc7e4443936c8ba118be248d12c102b46bf5afa3c5"
        ),
        "manifest": "TEST_PACKAGE_MANIFEST.json",
        "runtime": (
            "package_tools/qlinearadd_node0007_split_server_runtime_v25.py"
        ),
        "family": "qlinearadd_node0007",
    },
    "r5_n4_hw_v64_dskew_diag": {
        "sha256": (
            "e2ad1cbb94bec3379b5a810352cdfe8d9d5cfa17f2870696a862650b593d7e25"
        ),
        "manifest": "package_manifest.json",
        "runtime": "package_tools/node0004_hang_localization_runtime_v7.py",
        "family": "conv_serialized_node0004",
    },
    "r5_n4_0cc_p18_pekeep3": {
        "sha256": (
            "381e0d8597e72350d5403b73c98ea4d5986d220481cf643b188252b34286eada"
        ),
        "manifest": "package_manifest.json",
        "runtime": "package_tools/fixed_simresult_publisher.py",
        "family": "conv_native_four_lane",
    },
}


class BuildError(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise BuildError(f"{label}: replacement count {count}, expected 1")
    return text.replace(old, new)


def safe_extract(zip_path: Path, destination: Path, package_id: str) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise BuildError(f"CRC failure: {zip_path}")
        roots: set[str] = set()
        names: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in names
                or stat.S_ISLNK(mode)
            ):
                raise BuildError(f"unsafe source member: {info.filename}")
            names.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {package_id}:
            raise BuildError(f"source root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / package_id


def deterministic_zip(package: Path, target: Path) -> None:
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = (
                f"{package.name}/{path.relative_to(package).as_posix()}"
            )
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def patch_common_runner_header(text: str, package_id: str) -> str:
    old = (
        f'package_id="{package_id}"\n'
        'result_root="/home/panqs/ndp/simresult"\n'
    )
    new = (
        f'package_id="{package_id}"\n'
        'return_tag="r$(date -u +%s%N)_$$"\n'
        'result_root="/home/panqs/ndp/simresult"\n'
    )
    text = replace_once(text, old, new, f"{package_id} return tag")
    fixed = f'return_zip="$result_root/${{install_name}}_return.zip"'
    if fixed not in text:
        fixed = f'return_zip="${{result_root}}/${{install_name}}_return.zip"'
    unique = (
        'return_zip="$result_root/'
        '${install_name}_${return_tag}_return.zip"'
    )
    return replace_once(text, fixed, unique, f"{package_id} return name")


def patch_gap_runner(path: Path, package_id: str) -> None:
    text = patch_common_runner_header(path.read_text(encoding="utf-8"), package_id)
    text = replace_once(
        text,
        '--result-root "$result_root" --package-root "$package_root"',
        '--result-root "$result_root" --return-zip "$return_zip" '
        '--package-root "$package_root"',
        "GAP collect return",
    )
    text = replace_once(
        text,
        '"external_write_targets":["/home/panqs/ndp/simresult/'
        '${install_name}_return.zip","/home/panqs/ndp/simresult/'
        '${install_name}_return.zip.sha256"]',
        '"external_write_targets":["${return_zip}","${return_sha}"]',
        "GAP external return paths",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_qadd_runner(path: Path, package_id: str) -> None:
    text = patch_common_runner_header(path.read_text(encoding="utf-8"), package_id)
    text = replace_once(
        text,
        'python3 "$runtime" collect --server-root "$server_root"       '
        '--install-name "$install_name" --package-root "$package_root"       '
        '--evidence-root "$evidence_root" --run-root "$run_root"',
        'python3 "$runtime" collect --server-root "$server_root"       '
        '--install-name "$install_name" --package-root "$package_root"       '
        '--evidence-root "$evidence_root" --run-root "$run_root" '
        '--return-zip "$return_zip"',
        "QAdd collect return",
    )
    text = replace_once(
        text,
        '"return_zip":"/home/panqs/ndp/simresult/${install_name}_return.zip",\n'
        '"return_sidecar":"/home/panqs/ndp/simresult/'
        '${install_name}_return.zip.sha256"}',
        '"return_zip":"${return_zip}",\n'
        '"return_sidecar":"${return_sha}"}',
        "QAdd preflight return paths",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_serialized_runner(path: Path, package_id: str) -> None:
    text = patch_common_runner_header(path.read_text(encoding="utf-8"), package_id)
    text = replace_once(
        text,
        'python3 "$runtime" collect --server-root "$result_root"       '
        '--ndp-root "$server_root" --install-name "$install_name"       '
        '--evidence-root "$evidence_root" --run-root "$run_root"',
        'python3 "$runtime" collect --server-root "$result_root"       '
        '--ndp-root "$server_root" --install-name "$install_name"       '
        '--evidence-root "$evidence_root" --run-root "$run_root" '
        '--return-zip "$return_zip"',
        "serialized Conv collect return",
    )
    text = replace_once(
        text,
        '"return_zip": "/home/panqs/ndp/simresult/'
        '${install_name}_return.zip",\n'
        '  "return_sidecar": "/home/panqs/ndp/simresult/'
        '${install_name}_return.zip.sha256",',
        '"return_zip": "${return_zip}",\n'
        '  "return_sidecar": "${return_sha}",',
        "serialized Conv preflight return paths",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_native_runner(path: Path, package_id: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        f'install_name="{package_id}"\n'
        'attempt="a0"\n',
        f'install_name="{package_id}"\n'
        'attempt="a0"\n'
        'return_tag="r$(date -u +%s%N)_$$"\n',
        "native Conv return tag",
    )
    text = replace_once(
        text,
        f'return_zip="/home/panqs/ndp/simresult/{package_id}_return.zip"\n'
        f'return_sha="/home/panqs/ndp/simresult/{package_id}_return.zip.sha256"',
        'return_zip="/home/panqs/ndp/simresult/'
        '${package_identity}_${return_tag}_return.zip"\n'
        'return_sha="${return_zip}.sha256"',
        "native Conv return name",
    )
    text = text.replace(
        '--server-root "$server_root"',
        '--server-root "$server_root" --return-zip "$return_zip"',
        1,
    )
    text = replace_once(
        text,
        '--evidence-root "$evidence_root" --run-root "$run_root")"',
        '--evidence-root "$evidence_root" --run-root "$run_root" '
        '--return-zip "$return_zip")"',
        "native Conv collect return",
    )
    text = replace_once(
        text,
        f'"return_zip": "/home/panqs/ndp/simresult/{package_id}_return.zip",\n'
        f'  "return_sidecar": "/home/panqs/ndp/simresult/'
        f'{package_id}_return.zip.sha256",',
        '"return_zip": "${return_zip}",\n'
        '  "return_sidecar": "${return_sha}",',
        "native Conv preflight return paths",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_gap_runtime(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    package_root: Path,\n) -> dict[str, Any]:\n"
        "    result_root.mkdir(parents=True, exist_ok=True)\n"
        '    final_archive = result_root / f"{install_name}_return.zip"\n'
        '    final_sidecar = result_root / f"{install_name}_return.zip.sha256"\n',
        "    package_root: Path,\n"
        "    return_zip: Path,\n"
        ") -> dict[str, Any]:\n"
        "    result_root.mkdir(parents=True, exist_ok=True)\n"
        "    final_archive = return_zip\n"
        "    final_sidecar = Path(str(return_zip) + \".sha256\")\n"
        "    if (\n"
        "        not final_archive.is_absolute()\n"
        "        or final_archive.parent.resolve() != result_root.resolve()\n"
        "        or not final_archive.name.startswith(install_name + \"_r\")\n"
        "        or not final_archive.name.endswith(\"_return.zip\")\n"
        "    ):\n"
        "        raise RuntimeGateError(\"per-execution return path differs\")\n",
        "GAP runtime target",
    )
    text = replace_once(
        text,
        '    col.add_argument("--package-root", type=Path, required=True)\n',
        '    col.add_argument("--package-root", type=Path, required=True)\n'
        '    col.add_argument("--return-zip", type=Path, required=True)\n',
        "GAP runtime CLI",
    )
    text = replace_once(
        text,
        "                args.package_root,\n"
        "            )\n",
        "                args.package_root,\n"
        "                args.return_zip,\n"
        "            )\n",
        "GAP runtime call",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_qadd_runtime(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    cfg_root: Path,\n) -> dict[str, Any]:\n"
        '    fixed = Path("/home/panqs/ndp/simresult")\n'
        "    fixed.mkdir(parents=True, exist_ok=True)\n"
        "    if not fixed.is_dir():\n"
        '        raise RuntimeGateError("fixed result root is not a directory")\n'
        '    final_zip = fixed / f"{install_name}_return.zip"\n'
        "    final_sha = Path(str(final_zip) + \".sha256\")\n",
        "    cfg_root: Path,\n"
        "    return_zip: Path,\n"
        ") -> dict[str, Any]:\n"
        '    fixed = Path("/home/panqs/ndp/simresult")\n'
        "    fixed.mkdir(parents=True, exist_ok=True)\n"
        "    if not fixed.is_dir():\n"
        '        raise RuntimeGateError("fixed result root is not a directory")\n'
        "    final_zip = return_zip\n"
        "    final_sha = Path(str(final_zip) + \".sha256\")\n"
        "    if (\n"
        "        not final_zip.is_absolute()\n"
        "        or final_zip.parent.resolve() != fixed.resolve()\n"
        "        or not final_zip.name.startswith(install_name + \"_r\")\n"
        "        or not final_zip.name.endswith(\"_return.zip\")\n"
        "    ):\n"
        "        raise RuntimeGateError(\"per-execution return path differs\")\n",
        "QAdd runtime target",
    )
    text = replace_once(
        text,
        '    ret.add_argument("--cfg-root", type=Path, required=True)\n',
        '    ret.add_argument("--cfg-root", type=Path, required=True)\n'
        '    ret.add_argument("--return-zip", type=Path, required=True)\n',
        "QAdd runtime CLI",
    )
    text = replace_once(
        text,
        "                        args.cfg_root,\n"
        "                    )\n",
        "                        args.cfg_root,\n"
        "                        args.return_zip,\n"
        "                    )\n",
        "QAdd runtime call",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_serialized_runtime(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    run_root: Path,\n) -> dict[str, Any]:\n"
        '    fixed = Path("/home/panqs/ndp/simresult")\n'
        "    if server_root != fixed:\n"
        '        raise DiagnosticRuntimeError("fixed result root differs")\n'
        '    final_zip = fixed / f"{install_name}_return.zip"\n'
        "    final_sha = Path(str(final_zip) + \".sha256\")\n",
        "    run_root: Path,\n"
        "    return_zip: Path,\n"
        ") -> dict[str, Any]:\n"
        '    fixed = Path("/home/panqs/ndp/simresult")\n'
        "    if server_root != fixed:\n"
        '        raise DiagnosticRuntimeError("fixed result root differs")\n'
        "    final_zip = return_zip\n"
        "    final_sha = Path(str(final_zip) + \".sha256\")\n"
        "    if (\n"
        "        not final_zip.is_absolute()\n"
        "        or final_zip.parent.resolve() != fixed.resolve()\n"
        "        or not final_zip.name.startswith(install_name + \"_r\")\n"
        "        or not final_zip.name.endswith(\"_return.zip\")\n"
        "    ):\n"
        "        raise DiagnosticRuntimeError(\"per-execution return path differs\")\n",
        "serialized Conv runtime target",
    )
    text = replace_once(
        text,
        '    col.add_argument("--run-root", type=Path, required=True)\n',
        '    col.add_argument("--run-root", type=Path, required=True)\n'
        '    col.add_argument("--return-zip", type=Path, required=True)\n',
        "serialized Conv runtime CLI",
    )
    text = replace_once(
        text,
        "            args.run_root,\n"
        "        )\n",
        "            args.run_root,\n"
        "            args.return_zip,\n"
        "        )\n",
        "serialized Conv runtime call",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_native_publisher(path: Path, package_id: str) -> None:
    text = path.read_text(encoding="utf-8")
    helper = '''

def requested_return_targets(
    package_identity: str, return_zip: Path
) -> tuple[Path, Path]:
    if (
        not return_zip.is_absolute()
        or return_zip.parent.resolve() != RESULT_ROOT.resolve()
        or not return_zip.name.startswith(package_identity + "_r")
        or not return_zip.name.endswith("_return.zip")
    ):
        raise PublishError("per-execution return path differs")
    return return_zip, Path(str(return_zip) + ".sha256")
'''
    text = replace_once(
        text,
        "\ndef safe_child(root: Path, relative: str) -> Path:\n",
        helper + "\ndef safe_child(root: Path, relative: str) -> Path:\n",
        "native publisher target helper",
    )
    text = replace_once(
        text,
        "    *, package_root: Path, evidence_root: Path, run_root: Path\n",
        "    *, package_root: Path, evidence_root: Path, run_root: Path,\n"
        "    return_zip: Path\n",
        "native publisher collect signature",
    )
    old_targets = (
        f'    final_zip = result_root / f"{{package_identity}}_return.zip"\n'
        "    final_sidecar = Path(str(final_zip) + \".sha256\")\n"
    )
    new_targets = (
        "    final_zip, final_sidecar = requested_return_targets(\n"
        "        package_identity, return_zip\n"
        "    )\n"
    )
    if text.count(old_targets) != 2:
        raise BuildError("native publisher target blocks differ")
    text = text.replace(old_targets, new_targets)
    text = replace_once(
        text,
        "    server_root: str,\n) -> dict[str, Any]:\n",
        "    server_root: str,\n"
        "    return_zip: Path,\n"
        ") -> dict[str, Any]:\n",
        "native publisher bootstrap signature",
    )
    text = replace_once(
        text,
        '    parser.add_argument("--server-root", default="")\n',
        '    parser.add_argument("--server-root", default="")\n'
        '    parser.add_argument("--return-zip", type=Path, required=True)\n',
        "native publisher CLI",
    )
    text = replace_once(
        text,
        "            server_root=args.server_root,\n"
        "        )\n",
        "            server_root=args.server_root,\n"
        "            return_zip=args.return_zip,\n"
        "        )\n",
        "native publisher bootstrap call",
    )
    text = replace_once(
        text,
        "            run_root=args.run_root.resolve(),\n"
        "        )\n",
        "            run_root=args.run_root.resolve(),\n"
        "            return_zip=args.return_zip,\n"
        "        )\n",
        "native publisher collect call",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_sha_values(value: Any, old: str, new: str) -> Any:
    if isinstance(value, dict):
        return {
            key: replace_sha_values(item, old, new)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [replace_sha_values(item, old, new) for item in value]
    if value == old:
        return new
    return value


def refresh_manifest_files(package: Path, manifest: dict[str, Any]) -> None:
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise BuildError("manifest files map is absent")
    for relative, receipt in files.items():
        path = package / relative
        if not path.is_file():
            raise BuildError(f"manifest member absent: {relative}")
        digest = sha256_file(path)
        if isinstance(receipt, str):
            files[relative] = digest
        elif isinstance(receipt, dict):
            receipt["sha256"] = digest
            if "size_bytes" in receipt:
                receipt["size_bytes"] = path.stat().st_size
        else:
            raise BuildError(f"manifest receipt shape differs: {relative}")


def patch_contract(package: Path, helper_sha: str) -> None:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["shared_layout_helper"]["sha256"] = helper_sha
    contract["repeat_execution"] = dict(REPEAT_CONTRACT)
    additional = contract["path_budget"]["additional_projected_paths"]
    marker_paths = [
        "install/cfg_pkg/.codex_owner.{name}.json",
        (
            f"install/codex_runs/{contract['package_id']}/"
            ".codex_owner.{attempt}.json"
        ),
    ]
    for marker in marker_paths:
        if marker not in additional:
            additional.append(marker)
    additional.sort()
    write_json(path, contract)


def patch_manifest(
    package: Path,
    manifest_name: str,
    helper_sha: str,
) -> None:
    path = package / manifest_name
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest = replace_sha_values(manifest, OLD_HELPER_SHA, helper_sha)
    manifest["repeat_execution_contract"] = {
        **REPEAT_CONTRACT,
        "runtime_state_scope": (
            "NDP_copy0x/install/cfg_pkg/<install_name> and "
            "NDP_copy0x/install/codex_runs/<package_id>/<attempt> only"
        ),
        "prior_return_policy": "PRESERVE",
    }
    for field in ("fixed_result_publication", "fixed_server_result_publication"):
        value = manifest.get(field)
        if isinstance(value, dict):
            value["return_name_policy"] = (
                "UNIQUE_PER_EXECUTION_PRESERVE_PRIOR_RETURNS"
            )
            value["target_conflict"] = (
                "FAIL_CLOSED_ONLY_ON_EXACT_UNIQUE_TAG_COLLISION"
            )
            value["target_conflict_fail_closed"] = True
            if "zip_path" in value:
                value["zip_path_template"] = (
                    "/home/panqs/ndp/simresult/"
                    f"{package.name}_<return_tag>_return.zip"
                )
            if "sidecar_path" in value:
                value["sidecar_path_template"] = (
                    "/home/panqs/ndp/simresult/"
                    f"{package.name}_<return_tag>_return.zip.sha256"
                )
            if "return_zip" in value:
                value["return_zip_template"] = (
                    "/home/panqs/ndp/simresult/"
                    f"{package.name}_<return_tag>_return.zip"
                )
            if "return_sidecar" in value:
                value["return_sidecar_template"] = (
                    "/home/panqs/ndp/simresult/"
                    f"{package.name}_<return_tag>_return.zip.sha256"
                )
    refresh_manifest_files(package, manifest)
    write_json(path, manifest)


def patch_package(package: Path, spec: dict[str, str]) -> list[str]:
    package_id = package.name
    helper_target = package / "package_tools/server_package_runtime_layout.py"
    shutil.copyfile(SHARED_HELPER, helper_target)
    runner = package / "PREPARE_AND_RUN.sh"
    runtime = package / spec["runtime"]
    if package_id.startswith("r5_n71_gap_"):
        patch_gap_runner(runner, package_id)
        patch_gap_runtime(runtime)
    elif package_id.startswith("r5_qadd_"):
        patch_qadd_runner(runner, package_id)
        patch_qadd_runtime(runtime)
    elif package_id.startswith("r5_n4_hw_"):
        patch_serialized_runner(runner, package_id)
        patch_serialized_runtime(runtime)
    elif package_id.startswith("r5_n4_0cc_"):
        patch_native_runner(runner, package_id)
        patch_native_publisher(runtime, package_id)
    else:
        raise BuildError(f"unsupported package: {package_id}")
    helper_sha = sha256_file(SHARED_HELPER)
    patch_contract(package, helper_sha)
    patch_manifest(package, spec["manifest"], helper_sha)
    return sorted(
        {
            "PREPARE_AND_RUN.sh",
            "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
            "package_tools/server_package_runtime_layout.py",
            spec["runtime"],
            spec["manifest"],
        }
    )


def member_hashes(package: Path) -> dict[str, str]:
    return {
        path.relative_to(package).as_posix(): sha256_file(path)
        for path in sorted(item for item in package.rglob("*") if item.is_file())
    }


def zip_member_hashes(zip_path: Path, package_id: str) -> dict[str, str]:
    result: dict[str, str] = {}
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise BuildError(f"CRC failure: {zip_path}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if info.is_dir():
                continue
            if not pure.parts or pure.parts[0] != package_id:
                raise BuildError(f"ZIP root differs: {info.filename}")
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            result[relative] = sha256_bytes(archive.read(info))
    return result


def allowed_changed_members(spec: dict[str, str]) -> list[str]:
    return sorted(
        {
            "PREPARE_AND_RUN.sh",
            "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
            "package_tools/server_package_runtime_layout.py",
            spec["runtime"],
            spec["manifest"],
        }
    )


def inspect_completed_reissue(
    source_root: Path,
    output_root: Path,
    package_id: str,
    spec: dict[str, str],
) -> dict[str, Any]:
    source_zip = source_root / f"{package_id}.zip"
    zip_path = output_root / f"{package_id}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    digest = sha256_file(zip_path)
    if sidecar.read_text(encoding="ascii").split() != [digest, zip_path.name]:
        raise BuildError(f"resume sidecar differs: {package_id}")
    before = zip_member_hashes(source_zip, package_id)
    after = zip_member_hashes(zip_path, package_id)
    changed = sorted(
        name
        for name in set(before) | set(after)
        if before.get(name) != after.get(name)
    )
    allowed = allowed_changed_members(spec)
    if changed != allowed:
        raise BuildError(
            f"{package_id} resumed changed surface differs: "
            f"{changed} != {allowed}"
        )
    return {
        "package_id": package_id,
        "family": spec["family"],
        "source_zip": str(source_zip),
        "source_zip_bytes": source_zip.stat().st_size,
        "source_zip_sha256": spec["sha256"],
        "reissued_zip": str(zip_path),
        "reissued_zip_bytes": zip_path.stat().st_size,
        "reissued_zip_sha256": digest,
        "sidecar_sha256": sha256_file(sidecar),
        "changed_members": changed,
        "unchanged_member_count": len(after) - len(changed),
        "functional_assets_byte_equal": True,
        "deterministic_double_build": True,
        "resumed_from_completed_sidecar": True,
    }


def build_one(
    source_root: Path,
    output_root: Path,
    package_id: str,
    spec: dict[str, str],
) -> dict[str, Any]:
    source_zip = source_root / f"{package_id}.zip"
    if not source_zip.is_file():
        raise BuildError(f"source ZIP absent: {source_zip}")
    if sha256_file(source_zip) != spec["sha256"]:
        raise BuildError(f"source ZIP SHA differs: {package_id}")
    with tempfile.TemporaryDirectory(prefix=f".{package_id}.repeatable.") as temp:
        package = safe_extract(source_zip, Path(temp), package_id)
        before = member_hashes(package)
        allowed = patch_package(package, spec)
        after = member_hashes(package)
        changed = sorted(
            name
            for name in set(before) | set(after)
            if before.get(name) != after.get(name)
        )
        if changed != allowed:
            raise BuildError(
                f"{package_id} changed surface differs: {changed} != {allowed}"
            )
        zip_path = output_root / f"{package_id}.zip"
        deterministic_zip(package, zip_path)
        with tempfile.TemporaryDirectory(
            prefix=f".{package_id}.repeat-check."
        ) as repeat_temp:
            repeat_package = safe_extract(
                source_zip, Path(repeat_temp), package_id
            )
            patch_package(repeat_package, spec)
            repeat_zip = Path(repeat_temp) / f"{package_id}.zip"
            deterministic_zip(repeat_package, repeat_zip)
            if repeat_zip.read_bytes() != zip_path.read_bytes():
                raise BuildError(f"deterministic rebuild differs: {package_id}")
    digest = sha256_file(zip_path)
    sidecar = Path(str(zip_path) + ".sha256")
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    return {
        "package_id": package_id,
        "family": spec["family"],
        "source_zip": str(source_zip),
        "source_zip_bytes": source_zip.stat().st_size,
        "source_zip_sha256": spec["sha256"],
        "reissued_zip": str(zip_path),
        "reissued_zip_bytes": zip_path.stat().st_size,
        "reissued_zip_sha256": digest,
        "sidecar_sha256": sha256_file(sidecar),
        "changed_members": changed,
        "unchanged_member_count": len(after) - len(changed),
        "functional_assets_byte_equal": True,
        "deterministic_double_build": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    packages = []
    for package_id, spec in SOURCES.items():
        zip_path = output_root / f"{package_id}.zip"
        sidecar = Path(str(zip_path) + ".sha256")
        if zip_path.exists() or sidecar.exists():
            if not args.resume or not zip_path.is_file() or not sidecar.is_file():
                raise BuildError(
                    f"refusing to overwrite repeatable-package output: {package_id}"
                )
            packages.append(
                inspect_completed_reissue(
                    source_root, output_root, package_id, spec
                )
            )
        else:
            packages.append(
                build_one(source_root, output_root, package_id, spec)
            )
    report = {
        "schema": "current-four-repeatable-server-packages-v1",
        "status": "FOUR_LOCAL_REISSUES_BUILT_NOT_RUN",
        "shared_helper": {
            "path": str(SHARED_HELPER),
            "sha256": sha256_file(SHARED_HELPER),
        },
        "repeat_execution_contract": REPEAT_CONTRACT,
        "packages": packages,
        "claim_boundary": (
            "Runner/runtime-layout/return-publication only. No config, numeric, "
            "workload, mapping, bitstream, execplan, observer, RTL, upload, "
            "server run or lease change."
        ),
    }
    write_json(output_root / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
