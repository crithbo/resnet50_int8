#!/usr/bin/env python3
"""Capture GitHub/local/server RTL identity without installing or running tests."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from capture_gap_probe_server_identity import (
        ACTIVE_FILELIST_REL,
        FOCUS_RTL_RELS,
        _reference_match,
        file_identity,
        git_identity,
        text_file_identity,
        tree_identity,
    )
except ImportError:
    from tools.capture_gap_probe_server_identity import (
        ACTIVE_FILELIST_REL,
        FOCUS_RTL_RELS,
        _reference_match,
        file_identity,
        git_identity,
        text_file_identity,
        tree_identity,
    )


SCHEMA = "resnet50-gap-rtl-three-way-server-identity-v1"


class GapRtlIdentityError(ValueError):
    """Raised when read-only RTL identity capture cannot start."""


def capture_three_way_identity(
    *,
    ndp_root: Path,
    identity_manifest_path: Path,
) -> dict[str, Any]:
    root = ndp_root.resolve()
    if not root.is_dir():
        raise GapRtlIdentityError(f"missing NDP root: {root}")
    rtl_entry = root / "rtl"
    if not rtl_entry.is_dir():
        raise GapRtlIdentityError(f"missing server RTL directory: {rtl_entry}")
    manifest_path = identity_manifest_path.resolve()
    if not manifest_path.is_file():
        raise GapRtlIdentityError(
            f"missing identity-bundle manifest: {manifest_path}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rtl_tree = tree_identity(rtl_entry)
    focus_files = {
        relative.as_posix(): text_file_identity(root / relative)
        for relative in FOCUS_RTL_RELS
    }
    return {
        "schema": SCHEMA,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "operation": {
            "read_only": True,
            "testbench_modified": False,
            "functional_rtl_modified": False,
            "workload_installed": False,
            "compile_started": False,
            "simulation_started": False,
        },
        "identity_bundle": {
            "manifest": file_identity(manifest_path),
            "schema": manifest.get("schema"),
            "github_reference": manifest.get(
                "github_reference_identity", {}
            ).get("github"),
        },
        "server_paths": {
            "ndp_root": root.as_posix(),
            "rtl_entry": rtl_entry.absolute().as_posix(),
            "rtl_resolved": rtl_entry.resolve().as_posix(),
        },
        "artifacts": {
            "testbench": file_identity(root / "tb_NDP_Top_new_phy.sv"),
            "makefile": file_identity(root / "Makefile.tb_NDP_Top_new_phy"),
            "active_filelist": file_identity(root / ACTIVE_FILELIST_REL),
            "focus_rtl_files": focus_files,
        },
        "rtl_tree": rtl_tree,
        "entry_git": git_identity(root),
        "rtl_git": git_identity(rtl_entry),
        "reference_comparison": _reference_match(
            manifest, rtl_tree, focus_files
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ndp-root", type=Path, required=True)
    parser.add_argument("--identity-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = capture_three_way_identity(
        ndp_root=args.ndp_root,
        identity_manifest_path=args.identity_manifest,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
