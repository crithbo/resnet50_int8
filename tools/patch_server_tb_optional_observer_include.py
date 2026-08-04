#!/usr/bin/env python3
"""Make native_return_observer.svh an optional server-TB dependency.

The script modifies exactly:

    <server_root>/tb_NDP_Top_new_phy.sv

It never searches recursively and never touches <server_root>/rtl.
Before changing the TB it creates a content-addressed backup next to it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Any


TB_NAME = "tb_NDP_Top_new_phy.sv"
OBSERVER_NAME = "native_return_observer.svh"
ENABLE_MACRO = "NATIVE_RETURN_OBSERVER_ENABLE"

INCLUDE_PATTERN = re.compile(
    rb'(?m)^(?P<indent>[ \t]*)`include[ \t]+"native_return_observer\.svh"'
    rb"[ \t]*(?P<newline>\r?\n|$)"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_atomic(path: Path, data: bytes, mode: int) -> None:
    handle = tempfile.NamedTemporaryFile(
        mode="wb",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, stat.S_IMODE(mode))
        os.replace(temp_path, path)
    except BaseException:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def resolved_target(server_root_arg: str) -> tuple[Path, Path]:
    server_root = Path(server_root_arg).expanduser().resolve(strict=True)
    if not server_root.is_dir():
        raise RuntimeError(f"server root is not a directory: {server_root}")

    target = (server_root / TB_NAME).resolve(strict=True)
    expected = server_root / TB_NAME

    if target != expected:
        raise RuntimeError(
            "refusing symlink/redirected TB target: "
            f"expected={expected}, resolved={target}"
        )
    if target.parent != server_root:
        raise RuntimeError(f"TB target escaped server root: {target}")
    if not target.is_file():
        raise RuntimeError(f"TB target is not a regular file: {target}")

    rtl_root = (server_root / "rtl").resolve(strict=False)
    if target == rtl_root or rtl_root in target.parents:
        raise RuntimeError(f"refusing RTL target: {target}")

    return server_root, target


def guarded_block(indent: bytes, newline: bytes) -> bytes:
    if not newline:
        newline = b"\n"
    return (
        indent
        + b"`ifdef "
        + ENABLE_MACRO.encode("ascii")
        + newline
        + indent
        + b'`include "'
        + OBSERVER_NAME.encode("ascii")
        + b'"'
        + newline
        + indent
        + b"`endif"
        + newline
    )


def is_already_guarded(data: bytes) -> bool:
    expression = re.compile(
        rb"(?m)^[ \t]*`ifdef[ \t]+NATIVE_RETURN_OBSERVER_ENABLE[ \t]*\r?\n"
        rb'[ \t]*`include[ \t]+"native_return_observer\.svh"[ \t]*\r?\n'
        rb"[ \t]*`endif[ \t]*(?:\r?\n|$)"
    )
    return expression.search(data) is not None


def create_backup(target: Path, preimage: bytes, pre_sha256: str) -> Path:
    backup = target.with_name(
        f"{target.name}.pre_optional_observer_{pre_sha256[:16]}.bak"
    )
    if backup.exists():
        existing = backup.read_bytes()
        if sha256_bytes(existing) != pre_sha256:
            raise RuntimeError(f"existing backup has wrong content: {backup}")
        return backup

    with backup.open("xb") as handle:
        handle.write(preimage)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(backup, stat.S_IMODE(target.stat().st_mode))
    return backup


def write_receipt(server_root: Path, receipt: dict[str, Any]) -> Path:
    receipt_path = server_root / "tb_optional_observer_patch_receipt.json"
    payload = (
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    mode = receipt_path.stat().st_mode if receipt_path.exists() else 0o644
    write_atomic(receipt_path, payload, mode)
    return receipt_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Guard the server TB native_return_observer.svh include with "
            f"`ifdef {ENABLE_MACRO}."
        )
    )
    parser.add_argument(
        "server_root",
        help=f"Exact NDP_copyXX root containing {TB_NAME}",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check only; do not modify the TB",
    )
    args = parser.parse_args()

    try:
        server_root, target = resolved_target(args.server_root)
        preimage = target.read_bytes()
        pre_sha256 = sha256_bytes(preimage)

        if is_already_guarded(preimage):
            result = {
                "schema": "server-tb-optional-observer-patch-v1",
                "status": "ALREADY_GUARDED",
                "server_root": str(server_root),
                "target": str(target),
                "target_sha256": pre_sha256,
                "observer": OBSERVER_NAME,
                "enable_macro": ENABLE_MACRO,
                "rtl_modified": False,
                "tb_modified": False,
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0

        matches = list(INCLUDE_PATTERN.finditer(preimage))
        if len(matches) != 1:
            raise RuntimeError(
                "expected exactly one standalone unconditional observer include; "
                f"found {len(matches)}"
            )

        match = matches[0]
        postimage = (
            preimage[: match.start()]
            + guarded_block(
                match.group("indent"),
                match.group("newline") or b"\n",
            )
            + preimage[match.end() :]
        )
        post_sha256 = sha256_bytes(postimage)

        if args.check:
            result = {
                "schema": "server-tb-optional-observer-patch-v1",
                "status": "PATCH_REQUIRED",
                "server_root": str(server_root),
                "target": str(target),
                "pre_sha256": pre_sha256,
                "expected_post_sha256": post_sha256,
                "observer": OBSERVER_NAME,
                "enable_macro": ENABLE_MACRO,
                "rtl_modified": False,
                "tb_modified": False,
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 2

        backup = create_backup(target, preimage, pre_sha256)
        original_mode = target.stat().st_mode
        write_atomic(target, postimage, original_mode)

        observed_postimage = target.read_bytes()
        observed_post_sha256 = sha256_bytes(observed_postimage)
        if observed_post_sha256 != post_sha256:
            raise RuntimeError(
                "post-write identity mismatch: "
                f"expected={post_sha256}, observed={observed_post_sha256}"
            )

        receipt = {
            "schema": "server-tb-optional-observer-patch-v1",
            "status": "PATCH_APPLIED",
            "server_root": str(server_root),
            "target": str(target),
            "backup": str(backup),
            "pre_sha256": pre_sha256,
            "post_sha256": post_sha256,
            "backup_sha256": sha256_bytes(backup.read_bytes()),
            "observer": OBSERVER_NAME,
            "enable_macro": ENABLE_MACRO,
            "replacement": [
                f"`ifdef {ENABLE_MACRO}",
                f'`include "{OBSERVER_NAME}"',
                "`endif",
            ],
            "rtl_modified": False,
            "tb_modified": True,
        }
        receipt_path = write_receipt(server_root, receipt)
        receipt["receipt"] = str(receipt_path)
        print(json.dumps(receipt, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
