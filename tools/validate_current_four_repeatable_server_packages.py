#!/usr/bin/env python3
"""Validate the four repeatable runner-only package reissues."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_current_four_repeatable_server_packages import (
    REPEAT_CONTRACT,
    SHARED_HELPER,
    SOURCES,
    allowed_changed_members,
    sha256_bytes,
    sha256_file,
    zip_member_hashes,
)
from tools.server_package_runtime_layout import LayoutError, prepare_layout
from tools.validate_server_package_runtime_layout import (
    _generated_heredoc_syntax_checks,
)


def load_members(zip_path: Path, package_id: str) -> dict[str, bytes]:
    members: dict[str, bytes] = {}
    with zipfile.ZipFile(zip_path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"CRC failure: {bad}")
        names: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if info.filename in names:
                raise ValueError(f"duplicate member: {info.filename}")
            names.add(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or not pure.parts
                or pure.parts[0] != package_id
            ):
                raise ValueError(f"unsafe member: {info.filename}")
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            members[relative] = archive.read(info)
    return members


def manifest_file_binding(
    members: dict[str, bytes],
    manifest_name: str,
    errors: list[str],
) -> dict[str, Any]:
    try:
        manifest = json.loads(members[manifest_name].decode("utf-8"))
    except (KeyError, UnicodeError, json.JSONDecodeError) as error:
        errors.append(f"manifest invalid: {error}")
        return {}
    files = manifest.get("files")
    if not isinstance(files, dict):
        errors.append("manifest files map missing")
        return manifest
    for relative, receipt in files.items():
        data = members.get(relative)
        if data is None:
            errors.append(f"manifest member absent: {relative}")
            continue
        digest = sha256_bytes(data)
        if isinstance(receipt, str):
            observed = receipt
        elif isinstance(receipt, dict):
            observed = receipt.get("sha256")
            if (
                "size_bytes" in receipt
                and receipt.get("size_bytes") != len(data)
            ):
                errors.append(f"manifest size differs: {relative}")
        else:
            observed = None
        if observed != digest:
            errors.append(f"manifest SHA differs: {relative}")
    if manifest.get("repeat_execution_contract", {}).get(
        "return_name_policy"
    ) != REPEAT_CONTRACT["return_name_policy"]:
        errors.append("manifest repeat-execution contract missing")
    return manifest


def validate_package(
    source_root: Path,
    reissue_root: Path,
    package_id: str,
    spec: dict[str, str],
    bash_path: Path | None,
) -> dict[str, Any]:
    errors: list[str] = []
    source_zip = source_root / f"{package_id}.zip"
    reissued_zip = reissue_root / f"{package_id}.zip"
    if not source_zip.is_file() or sha256_file(source_zip) != spec["sha256"]:
        errors.append("source ZIP identity differs")
        source_hashes: dict[str, str] = {}
    else:
        source_hashes = zip_member_hashes(source_zip, package_id)
    try:
        members = load_members(reissued_zip, package_id)
    except (OSError, zipfile.BadZipFile, ValueError) as error:
        errors.append(str(error))
        members = {}
    reissued_hashes = {
        name: sha256_bytes(data) for name, data in members.items()
    }
    changed = sorted(
        name
        for name in set(source_hashes) | set(reissued_hashes)
        if source_hashes.get(name) != reissued_hashes.get(name)
    )
    expected_changed = allowed_changed_members(spec)
    if changed != expected_changed:
        errors.append(
            f"changed surface differs: {changed} != {expected_changed}"
        )
    helper_member = "package_tools/server_package_runtime_layout.py"
    helper = members.get(helper_member)
    helper_sha = sha256_file(SHARED_HELPER)
    if helper is None or sha256_bytes(helper) != helper_sha:
        errors.append("shared helper bytes differ")
    contract_member = "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    try:
        contract = json.loads(members[contract_member].decode("utf-8"))
    except (KeyError, UnicodeError, json.JSONDecodeError) as error:
        errors.append(f"runtime contract invalid: {error}")
        contract = {}
    if contract.get("repeat_execution") != REPEAT_CONTRACT:
        errors.append("runtime repeat-execution contract differs")
    if contract.get("shared_layout_helper", {}).get("sha256") != helper_sha:
        errors.append("runtime helper binding differs")
    runner_data = members.get("PREPARE_AND_RUN.sh", b"")
    try:
        runner = runner_data.decode("utf-8")
    except UnicodeError:
        runner = ""
        errors.append("runner is not UTF-8")
    required_runner_tokens = (
        'return_tag="r$(date -u +%s%N)_$$"',
        "${install_name}_${return_tag}_return.zip"
        if package_id != "r5_n4_0cc_p18_pekeep3"
        else "${package_identity}_${return_tag}_return.zip",
        '--return-zip "$return_zip"',
    )
    for token in required_runner_tokens:
        if token not in runner:
            errors.append(f"runner repeat token missing: {token}")
    fixed_old_name = f"/{package_id}_return.zip"
    if fixed_old_name in runner:
        errors.append("runner still binds one fixed return name")
    heredoc_errors: list[str] = []
    heredoc_receipt = _generated_heredoc_syntax_checks(
        members, "PREPARE_AND_RUN.sh", heredoc_errors
    )
    errors.extend(heredoc_errors)
    bash_receipt: dict[str, Any] = {"executed": False}
    if bash_path is not None:
        completed = subprocess.run(
            [str(bash_path), "-n"],
            input=runner_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        bash_receipt = {
            "executed": True,
            "path": str(bash_path),
            "exit_code": completed.returncode,
            "stderr": completed.stderr.decode("utf-8", errors="replace"),
        }
        if completed.returncode != 0:
            errors.append("runner bash -n syntax failed")
    runtime_data = members.get(spec["runtime"], b"")
    try:
        compile(runtime_data, spec["runtime"], "exec")
    except (SyntaxError, ValueError) as error:
        errors.append(f"runtime Python syntax invalid: {error}")
    if b"--return-zip" not in runtime_data:
        errors.append("runtime explicit return path binding missing")
    manifest = manifest_file_binding(
        members, spec["manifest"], errors
    )
    sidecar = Path(str(reissued_zip) + ".sha256")
    digest = sha256_file(reissued_zip) if reissued_zip.is_file() else None
    if (
        not sidecar.is_file()
        or sidecar.read_text(encoding="ascii").split()
        != [digest, reissued_zip.name]
    ):
        errors.append("local package sidecar differs")
    return {
        "package_id": package_id,
        "pass": not errors,
        "errors": sorted(set(errors)),
        "source_zip_sha256": spec["sha256"],
        "reissued_zip_sha256": digest,
        "reissued_zip_bytes": (
            reissued_zip.stat().st_size if reissued_zip.is_file() else None
        ),
        "changed_members": changed,
        "unchanged_member_count": len(reissued_hashes) - len(changed),
        "manifest_status": manifest.get("status"),
        "functional_assets_byte_equal": changed == expected_changed,
        "generated_heredoc_syntax": heredoc_receipt,
        "bash_syntax": bash_receipt,
    }


def validate_repeat_layout() -> dict[str, Any]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="repeat-layout-") as temporary:
        server_root = Path(temporary) / "NDP_copy01"
        (server_root / "install").mkdir(parents=True)
        (server_root / "rtl").mkdir()
        first = prepare_layout(
            server_root, "pkg", "install_name", "a0", create=True
        )
        cfg_root = Path(first["cfg_root"])
        run_root = Path(first["run_root"])
        (cfg_root / "old.bin").write_bytes(b"old")
        (run_root / "old.log").write_bytes(b"old")
        foreign_cfg = server_root / "install/cfg_pkg/foreign"
        foreign_run = server_root / "install/codex_runs/foreign/a0"
        foreign_cfg.mkdir()
        foreign_run.mkdir(parents=True)
        (foreign_cfg / "keep").write_bytes(b"cfg")
        (foreign_run / "keep").write_bytes(b"run")
        before = sorted(
            (path.name, path.is_dir()) for path in server_root.iterdir()
        )
        second = prepare_layout(
            server_root, "pkg", "install_name", "a0", create=True
        )
        after = sorted(
            (path.name, path.is_dir()) for path in server_root.iterdir()
        )
        if before != after:
            errors.append("NDP root direct entry set changed")
        if (cfg_root / "old.bin").exists() or (run_root / "old.log").exists():
            errors.append("same-package stale runtime state survived")
        if (foreign_cfg / "keep").read_bytes() != b"cfg":
            errors.append("foreign cfg sibling changed")
        if (foreign_run / "keep").read_bytes() != b"run":
            errors.append("foreign run sibling changed")
        if not second.get("exact_package_owned_items_replaced"):
            errors.append("repeat replacement receipt missing")
        bad_cfg = server_root / "install/cfg_pkg/bad_install"
        bad_cfg.write_bytes(b"do-not-delete")
        try:
            prepare_layout(
                server_root, "bad_pkg", "bad_install", "a0", create=True
            )
        except LayoutError:
            pass
        else:
            errors.append("non-directory cfg root was not rejected")
        if bad_cfg.read_bytes() != b"do-not-delete":
            errors.append("non-directory cfg root was modified")
    return {
        "pass": not errors,
        "errors": errors,
        "first_schema": first["schema"],
        "second_schema": second["schema"],
        "exact_package_owned_items_replaced": second[
            "exact_package_owned_items_replaced"
        ],
        "root_exact_set_unchanged": second["root_exact_set_unchanged"],
        "foreign_siblings_preserved": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--reissue-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bash", type=Path)
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    reissue_root = args.reissue_root.resolve()
    packages = [
        validate_package(
            source_root, reissue_root, package_id, spec, args.bash
        )
        for package_id, spec in SOURCES.items()
    ]
    layout = validate_repeat_layout()
    errors = [
        f"{row['package_id']}: {error}"
        for row in packages
        for error in row["errors"]
    ] + [f"layout: {error}" for error in layout["errors"]]
    report = {
        "schema": "current-four-repeatable-server-packages-validation-v1",
        "pass": not errors,
        "errors": errors,
        "shared_helper": {
            "path": str(SHARED_HELPER),
            "sha256": sha256_file(SHARED_HELPER),
        },
        "repeat_layout": layout,
        "packages": packages,
        "claim_boundary": (
            "Exact source/reissued ZIP changed-surface, manifest/helper binding, "
            "unique return naming and local package-owned reset only. No server "
            "compile, simulation, terminal, formal-D, E4 or E5 claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
