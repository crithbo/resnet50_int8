#!/usr/bin/env python3
"""Prepare repeatable package-owned directories below an NDP install tree.

This helper is intended to be copied byte-for-byte into a future server test
package.  It never writes a direct child of the supplied NDP root.  Only the
real, non-symlink ``install`` directory must pre-exist.  Shared
``install/cfg_pkg`` and ``install/codex_runs`` parents are created safely when
absent.  Exact package-owned cfg and attempt roots are reset on a repeated
execution, while sibling packages and unknown paths remain untouched.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import stat
import sys
from pathlib import Path
from typing import Any


SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
REQUIRED_PREEXISTING_PARENTS = (Path("install"),)
PACKAGE_CREATABLE_PARENTS = (
    Path("install/cfg_pkg"),
    Path("install/codex_runs"),
)
OWNERSHIP_MARKER_PATTERN = ".codex_owner.{name}.json"


class LayoutError(ValueError):
    """The requested runtime layout is unsafe or unavailable."""


def _entry_type(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "file"
    return "other"


def root_snapshot(server_root: Path) -> list[dict[str, str]]:
    return [
        {"name": path.name, "type": _entry_type(path)}
        for path in sorted(server_root.iterdir(), key=lambda item: item.name)
    ]


def _safe_name(label: str, value: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or SAFE_NAME.fullmatch(value) is None
    ):
        raise LayoutError(
            f"{label} must match {SAFE_NAME.pattern} and be <= {maximum} chars"
        )
    return value


def _strict_child(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise LayoutError(f"unsafe relative path: {relative.as_posix()}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise LayoutError(
            f"path escapes server root: {relative.as_posix()}"
        ) from error
    return candidate


def _require_preexisting_parents(server_root: Path) -> list[dict[str, str]]:
    receipts: list[dict[str, str]] = []
    for relative in REQUIRED_PREEXISTING_PARENTS:
        path = server_root / relative
        if not path.exists():
            raise LayoutError(
                f"required pre-existing parent is absent: {relative.as_posix()}"
            )
        if path.is_symlink() or not path.is_dir():
            raise LayoutError(
                "required pre-existing parent is not a real directory: "
                f"{relative.as_posix()}"
            )
        resolved = _strict_child(server_root, relative)
        receipts.append(
            {
                "relative_path": relative.as_posix(),
                "resolved_path": str(resolved),
                "type": "directory",
            }
        )
    return receipts


def _ensure_real_directory(
    server_root: Path,
    relative: Path,
    *,
    create: bool,
) -> dict[str, Any]:
    path = server_root / relative
    existed_before = path.exists() or path.is_symlink()
    created_by_this_process = False
    if not existed_before and create:
        try:
            path.mkdir(parents=False, exist_ok=False)
            created_by_this_process = True
        except FileExistsError:
            # A concurrent package may have atomically created this shared
            # parent.  Accept only the same real-directory result.
            pass
    exists_after = path.exists() or path.is_symlink()
    if exists_after and (path.is_symlink() or not path.is_dir()):
        raise LayoutError(
            "package-creatable parent is not a real directory: "
            f"{relative.as_posix()}"
        )
    if create and not exists_after:
        raise LayoutError(
            f"package-creatable parent was not created: {relative.as_posix()}"
        )
    resolved = _strict_child(server_root, relative)
    return {
        "relative_path": relative.as_posix(),
        "resolved_path": str(resolved),
        "existed_before": existed_before,
        "created_by_this_process": created_by_this_process,
        "type_after": "directory" if exists_after else "planned_directory",
    }


def _scan_resettable_tree(path: Path) -> dict[str, Any]:
    """Prove an exact package-owned tree contains only inert filesystem nodes."""

    files = 0
    directories = 1
    total_bytes = 0
    pending = [path]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                entry_path = Path(entry.path)
                if entry.is_symlink():
                    raise LayoutError(
                        f"package-owned reset tree contains symlink: {entry_path}"
                    )
                mode = entry.stat(follow_symlinks=False).st_mode
                if stat.S_ISDIR(mode):
                    directories += 1
                    pending.append(entry_path)
                elif stat.S_ISREG(mode):
                    files += 1
                    total_bytes += entry.stat(follow_symlinks=False).st_size
                else:
                    raise LayoutError(
                        "package-owned reset tree contains special filesystem "
                        f"entry: {entry_path}"
                    )
    return {
        "file_count": files,
        "directory_count": directories,
        "total_file_bytes": total_bytes,
    }


def _reset_exact_package_directory(
    *,
    root: Path,
    path: Path,
    relative: Path,
    package_id: str,
    install_name: str,
    attempt: str,
    kind: str,
    marker_path: Path,
    create: bool,
) -> dict[str, Any]:
    """Reset only the exact cfg or attempt root selected by validated names."""

    expected = _strict_child(root, relative)
    if path != expected:
        raise LayoutError(f"{kind} reset target identity differs")
    existed_before = path.exists() or path.is_symlink()
    prior: dict[str, Any] | None = None
    legacy_exact_path_adopted = False
    if existed_before:
        if path.is_symlink() or not path.is_dir():
            raise LayoutError(
                f"{kind} exists but is not a real directory: {relative.as_posix()}"
            )
        prior = _scan_resettable_tree(path)
        marker = None
        if marker_path.exists() or marker_path.is_symlink():
            if marker_path.is_symlink() or not marker_path.is_file():
                raise LayoutError(
                    f"{kind} ownership marker is not a regular file: "
                    f"{marker_path}"
                )
            try:
                marker_value = json.loads(
                    marker_path.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
                raise LayoutError(
                    f"{kind} ownership marker is invalid: {marker_path}"
                ) from error
            if not isinstance(marker_value, dict):
                raise LayoutError(
                    f"{kind} ownership marker is not an object: {marker_path}"
                )
            marker = marker_value
        expected_marker = {
            "package_id": package_id,
            "install_name": install_name,
            "attempt": attempt if kind == "run_root" else None,
            "kind": kind,
        }
        if marker is None:
            # Compatibility for a first repeat of packages emitted before the
            # ownership marker existed.  The validated exact path is the
            # authority; no sibling or parent is adopted.
            legacy_exact_path_adopted = True
        elif any(marker.get(key) != value for key, value in expected_marker.items()):
            raise LayoutError(
                f"{kind} ownership marker differs: {relative.as_posix()}"
            )
        if create:
            shutil.rmtree(path)
    if create:
        path.mkdir(parents=False, exist_ok=False)
        marker_value = {
            "schema": "server-package-runtime-owner-v1",
            "package_id": package_id,
            "install_name": install_name,
            "attempt": attempt if kind == "run_root" else None,
            "kind": kind,
            "exact_relative_path": relative.as_posix(),
        }
        if marker_path.parent.is_symlink() or not marker_path.parent.is_dir():
            raise LayoutError(f"{kind} ownership marker parent differs")
        marker_path.write_text(
            json.dumps(marker_value, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return {
        "kind": kind,
        "relative_path": relative.as_posix(),
        "existed_before": existed_before,
        "reset_performed": create and existed_before,
        "legacy_exact_path_adopted": legacy_exact_path_adopted,
        "prior_tree": prior,
        "ownership_marker": str(marker_path.relative_to(root)),
        "type_after": "directory" if create else (
            "directory" if existed_before else "planned_directory"
        ),
    }


def prepare_layout(
    server_root: Path,
    package_id: str,
    install_name: str,
    attempt: str,
    *,
    create: bool,
) -> dict[str, Any]:
    package_id = _safe_name("package_id", package_id, 96)
    install_name = _safe_name("install_name", install_name, 96)
    attempt = _safe_name("attempt", attempt, 48)
    if (
        not server_root.is_absolute()
        or server_root.is_symlink()
        or not server_root.is_dir()
    ):
        raise LayoutError("server_root must be an existing real absolute directory")
    root = server_root.resolve()

    before = root_snapshot(root)
    parents = _require_preexisting_parents(root)
    planned_creatable_parents = [
        _ensure_real_directory(root, relative, create=False)
        for relative in PACKAGE_CREATABLE_PARENTS
    ]
    creatable_parents = (
        [
            _ensure_real_directory(root, relative, create=True)
            for relative in PACKAGE_CREATABLE_PARENTS
        ]
        if create
        else planned_creatable_parents
    )
    cfg_relative = Path("install/cfg_pkg") / install_name
    package_relative = Path("install/codex_runs") / package_id
    run_relative = Path("install/codex_runs") / package_id / attempt
    cfg_root = _strict_child(root, cfg_relative)
    package_root = _strict_child(root, package_relative)
    run_root = _strict_child(root, run_relative)
    evidence_root = _strict_child(root, run_relative / "evidence")
    compile_root = _strict_child(root, run_relative / "compile")

    if package_root.exists() or package_root.is_symlink():
        if package_root.is_symlink() or not package_root.is_dir():
            raise LayoutError(
                "package run parent is not a real directory: "
                f"{package_relative.as_posix()}"
            )

    if create and not package_root.exists():
        try:
            package_root.mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            pass
    if create:
        if package_root.is_symlink() or not package_root.is_dir():
            raise LayoutError(
                "package run parent is not a real directory: "
                f"{package_relative.as_posix()}"
            )
    replacements = [
        _reset_exact_package_directory(
            root=root,
            path=cfg_root,
            relative=cfg_relative,
            package_id=package_id,
            install_name=install_name,
            attempt=attempt,
            kind="cfg_root",
            marker_path=cfg_root.parent
            / OWNERSHIP_MARKER_PATTERN.format(name=install_name),
            create=create,
        ),
        _reset_exact_package_directory(
            root=root,
            path=run_root,
            relative=run_relative,
            package_id=package_id,
            install_name=install_name,
            attempt=attempt,
            kind="run_root",
            marker_path=package_root
            / OWNERSHIP_MARKER_PATTERN.format(name=attempt),
            create=create,
        ),
    ]
    if create:
        # The exact run root was recreated above.  These children therefore
        # cannot collide with stale evidence or compile products.
        evidence_root.mkdir(parents=False, exist_ok=False)
        compile_root.mkdir(parents=False, exist_ok=False)

    after = root_snapshot(root)
    if after != before:
        raise LayoutError("server root direct-child name/type set changed")

    return {
        "schema": "server_package_runtime_layout_receipt_v2",
        "server_root": str(root),
        "package_id": package_id,
        "install_name": install_name,
        "attempt": attempt,
        "required_preexisting_parents": parents,
        "package_creatable_parents": creatable_parents,
        "cfg_root": str(cfg_root),
        "run_root": str(run_root),
        "evidence_root": str(evidence_root),
        "compile_root": str(compile_root),
        "repeat_execution": {
            "mode": "RESET_EXACT_PACKAGE_OWNED_RUNTIME_ROOTS",
            "cfg_root_policy": "RESET_AND_RECREATE_EXACT_INSTALL_NAME",
            "run_root_policy": "RESET_AND_RECREATE_EXACT_PACKAGE_ATTEMPT",
            "foreign_sibling_policy": "PRESERVE",
            "symlink_or_special_entry_policy": "FAIL_CLOSED",
            "ownership_marker_pattern": OWNERSHIP_MARKER_PATTERN,
            "replacements": replacements,
        },
        "all_package_owned_paths_under_install": all(
            "install" == path.relative_to(root).parts[0]
            for path in (cfg_root, run_root, evidence_root, compile_root)
        ),
        "root_direct_entries_before": before,
        "root_direct_entries_after": after,
        "root_exact_set_unchanged": before == after,
        "created": create,
        "unknown_items_deleted_or_overwritten": False,
        "exact_package_owned_items_replaced": any(
            item["reset_performed"] for item in replacements
        ),
        "claim_boundary": (
            "Exact package-owned runtime reset plus NDP-root direct-entry and "
            "foreign-sibling preservation only; no compile, simulation, "
            "terminal, formal-D, E4, or E5 claim."
        ),
    }


def _write_receipt(receipt: dict[str, Any], receipt_name: str) -> Path:
    name = _safe_name("receipt_name", receipt_name, 96)
    path = Path(receipt["evidence_root"]) / name
    path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _shell_output(receipt: dict[str, Any], receipt_path: Path | None) -> str:
    values = {
        "CFG_ROOT": receipt["cfg_root"],
        "RUN_ROOT": receipt["run_root"],
        "EVIDENCE_ROOT": receipt["evidence_root"],
        "COMPILE_ROOT": receipt["compile_root"],
    }
    if receipt_path is not None:
        values["RUNTIME_LAYOUT_RECEIPT"] = str(receipt_path)
    return "\n".join(
        f"{key}={shlex.quote(str(value))}" for key, value in values.items()
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare repeatable package-owned cfg/run/evidence/compile "
            "directories below a pre-existing real NDP install directory. "
            "Exact same-package roots are reset; siblings are preserved."
        )
    )
    parser.add_argument("command", choices=("plan", "prepare"))
    parser.add_argument("--server-root", required=True, type=Path)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--install-name", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument(
        "--receipt-name", default="runtime_layout_receipt.json"
    )
    parser.add_argument("--format", choices=("json", "shell"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = prepare_layout(
            args.server_root,
            args.package_id,
            args.install_name,
            args.attempt,
            create=args.command == "prepare",
        )
        receipt_path = (
            _write_receipt(receipt, args.receipt_name)
            if args.command == "prepare"
            else None
        )
    except (LayoutError, OSError) as error:
        print(
            json.dumps(
                {
                    "schema": "server_package_runtime_layout_error_v1",
                    "error": str(error),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    if args.format == "shell":
        print(_shell_output(receipt, receipt_path))
    else:
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
