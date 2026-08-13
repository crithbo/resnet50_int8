#!/usr/bin/env python3
"""Audit that an NDP server root keeps the same direct-child names and types."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any


SCHEMA = "ndp-root-toplevel-exact-set-snapshot-v1"
GATE_SCHEMA = "ndp-root-toplevel-exact-set-gate-v1"


class RootGateError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def entry_type(path: Path) -> str:
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode):
        return "character_device"
    if stat.S_ISBLK(mode):
        return "block_device"
    return "other"


def snapshot(root: Path) -> dict[str, Any]:
    resolved = root.resolve(strict=True)
    if not resolved.is_dir():
        raise RootGateError(f"server root is not a directory: {resolved}")
    entries = [
        {"name": child.name, "type": entry_type(child)}
        for child in resolved.iterdir()
    ]
    entries.sort(key=lambda item: os.fsencode(str(item["name"])))
    exact_set_sha256 = sha256_bytes(canonical_bytes(entries))
    value = {
        "schema": SCHEMA,
        "server_root": str(resolved),
        "entry_count": len(entries),
        "entries": entries,
        "exact_set_sha256": exact_set_sha256,
    }
    value["snapshot_sha256"] = sha256_bytes(canonical_bytes(value))
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RootGateError(f"JSON object required: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def validate_snapshot(value: dict[str, Any]) -> None:
    entries = value.get("entries")
    if value.get("schema") != SCHEMA or not isinstance(entries, list):
        raise RootGateError("snapshot schema differs")
    if any(
        not isinstance(item, dict)
        or not isinstance(item.get("name"), str)
        or not isinstance(item.get("type"), str)
        for item in entries
    ):
        raise RootGateError("snapshot entry differs")
    if entries != sorted(
        entries, key=lambda item: os.fsencode(str(item["name"]))
    ):
        raise RootGateError("snapshot entries are not sorted")
    if len({item["name"] for item in entries}) != len(entries):
        raise RootGateError("snapshot contains duplicate names")
    if value.get("entry_count") != len(entries):
        raise RootGateError("snapshot count differs")
    if value.get("exact_set_sha256") != sha256_bytes(
        canonical_bytes(entries)
    ):
        raise RootGateError("snapshot exact-set SHA differs")
    without_snapshot_sha = dict(value)
    observed_snapshot_sha = without_snapshot_sha.pop(
        "snapshot_sha256", None
    )
    if observed_snapshot_sha != sha256_bytes(
        canonical_bytes(without_snapshot_sha)
    ):
        raise RootGateError("snapshot receipt SHA differs")


def contract(manifest: dict[str, Any]) -> dict[str, Any]:
    value = manifest.get("ndp_root_toplevel_contract")
    if not isinstance(value, dict):
        raise RootGateError("NDP root top-level contract is missing")
    runtime_targets = value.get("runtime_write_targets")
    parents = value.get("root_internal_preexisting_parents")
    external = value.get("root_external_write_roots")
    if (
        not isinstance(runtime_targets, list)
        or not isinstance(parents, list)
        or not isinstance(external, list)
        or any(not isinstance(item, str) for item in runtime_targets)
        or any(not isinstance(item, str) for item in parents)
        or any(not isinstance(item, str) for item in external)
    ):
        raise RootGateError("NDP root top-level contract fields differ")
    return value


def validate_parents(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    resolved = root.resolve(strict=True)
    value = contract(manifest)
    declared = value["root_internal_preexisting_parents"]
    observed: list[dict[str, Any]] = []
    valid = True
    for name in declared:
        if (
            not name
            or "/" in name
            or "\\" in name
            or name in {".", ".."}
        ):
            raise RootGateError(f"invalid direct-child parent name: {name!r}")
        path = resolved / name
        exists_as_directory = path.is_dir() and not path.is_symlink()
        observed.append(
            {
                "name": name,
                "exists_as_directory": exists_as_directory,
            }
        )
        valid = valid and exists_as_directory
    return {
        "schema": "ndp-root-toplevel-parent-preflight-v1",
        "server_root": str(resolved),
        "declared": declared,
        "observed": observed,
        "valid": valid,
    }


def compare(
    *,
    pre_path: Path,
    post_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    pre = load_json(pre_path)
    post = load_json(post_path)
    manifest = load_json(manifest_path)
    validate_snapshot(pre)
    validate_snapshot(post)
    value = contract(manifest)
    parents = validate_parents(Path(str(pre["server_root"])), manifest)
    same_root = pre["server_root"] == post["server_root"]
    same_set = (
        pre["entries"] == post["entries"]
        and pre["exact_set_sha256"] == post["exact_set_sha256"]
    )
    valid = same_root and same_set and parents["valid"]
    return {
        "schema": GATE_SCHEMA,
        "server_root": pre["server_root"],
        "pre_snapshot_sha256": pre["snapshot_sha256"],
        "post_snapshot_sha256": post["snapshot_sha256"],
        "pre_exact_set_sha256": pre["exact_set_sha256"],
        "post_exact_set_sha256": post["exact_set_sha256"],
        "pre_entry_count": pre["entry_count"],
        "post_entry_count": post["entry_count"],
        "ndp_root_toplevel_unchanged": same_root and same_set,
        "root_internal_preexisting_parents_valid": parents["valid"],
        "root_internal_preexisting_parents": value[
            "root_internal_preexisting_parents"
        ],
        "runtime_write_targets": value["runtime_write_targets"],
        "root_external_write_roots": value["root_external_write_roots"],
        "valid": valid,
        "status": (
            "NDP_ROOT_TOPLEVEL_UNCHANGED_PASS"
            if valid
            else "NDP_ROOT_TOPLEVEL_DRIFT_OR_PARENT_MISSING"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--server-root", type=Path, required=True)

    parents_parser = subparsers.add_parser("validate-parents")
    parents_parser.add_argument("--server-root", type=Path, required=True)
    parents_parser.add_argument("--manifest", type=Path, required=True)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--pre", type=Path, required=True)
    compare_parser.add_argument("--post", type=Path, required=True)
    compare_parser.add_argument("--manifest", type=Path, required=True)
    compare_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "snapshot":
        print(
            json.dumps(
                snapshot(args.server_root),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "validate-parents":
        result = validate_parents(
            args.server_root, load_json(args.manifest)
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["valid"] else 23
    if args.command == "compare":
        try:
            result = compare(
                pre_path=args.pre,
                post_path=args.post,
                manifest_path=args.manifest,
            )
        except (OSError, ValueError, RootGateError) as exc:
            result = {
                "schema": GATE_SCHEMA,
                "valid": False,
                "ndp_root_toplevel_unchanged": False,
                "status": "NDP_ROOT_TOPLEVEL_GATE_ERROR",
                "error": str(exc),
            }
        write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("valid") is True else 23
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
