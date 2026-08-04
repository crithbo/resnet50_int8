#!/usr/bin/env python3
"""Capture reproducible server identity for a GAP deep-probe run."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "resnet50-gap-probe-server-identity-v3"
ACTIVE_FILELIST_REL = Path("rtl/filelists/NDP_Top_phy_filelist.f")
FOCUS_RTL_RELS = (
    Path(
        "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_RD_Stream_Engine/RD_Memory_AG.sv"
    ),
    Path(
        "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_RD_Stream_Engine/RD_Data_Channel.sv"
    ),
    Path("rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv"),
    Path("rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager.sv"),
    Path("rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv"),
    Path("rtl/Slice/General_Array/GA_PE_Group/GA_PE_ALU.sv"),
    Path("rtl/Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv"),
    Path(
        "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_WR_Stream_Engine/WR_Memory_AG.sv"
    ),
    Path(
        "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_WR_Stream_Engine/WR_Data_Channel.sv"
    ),
    Path("rtl/Slice/General_Array/General_Array.sv"),
    Path("rtl/Slice/General_Array/GA_PE_Group/GA_PE_Group.sv"),
    Path("rtl/Slice/General_Array/GA_PE_Group/GA_PE/GA_PE.sv"),
    Path("rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE.sv"),
    Path(
        "rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/"
        "GA_SFU_PE_Postprocess.sv"
    ),
)


class GapProbeIdentityError(ValueError):
    """Raised when the requested server identity cannot be captured safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    canonical = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def file_identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        return {
            "path": resolved.as_posix(),
            "exists": False,
            "size_bytes": None,
            "sha256": None,
        }
    return {
        "path": resolved.as_posix(),
        "exists": True,
        "size_bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def text_file_identity(path: Path) -> dict[str, Any]:
    identity = file_identity(path)
    if not identity["exists"]:
        return {
            **identity,
            "canonical_text_sha256": None,
            "canonical_text_error": None,
        }
    try:
        canonical = canonical_text_sha256(path.resolve())
        error = None
    except UnicodeError as exc:
        canonical = None
        error = f"{type(exc).__name__}: {exc}"
    return {
        **identity,
        "canonical_text_sha256": canonical,
        "canonical_text_error": error,
    }


def tree_identity(root: Path) -> dict[str, Any]:
    resolved = root.resolve()
    if not resolved.is_dir():
        return {
            "path": resolved.as_posix(),
            "exists": False,
            "file_count": 0,
            "size_bytes": 0,
            "tree_sha256": None,
        }
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in resolved.rglob("*") if item.is_file()):
        relative = path.relative_to(resolved).as_posix()
        records[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    digest = hashlib.sha256()
    for relative, item in sorted(records.items()):
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode()
        )
    return {
        "path": resolved.as_posix(),
        "exists": True,
        "file_count": len(records),
        "size_bytes": sum(item["size_bytes"] for item in records.values()),
        "tree_sha256": digest.hexdigest(),
    }


def _git_command(root: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def git_identity(root: Path) -> dict[str, Any]:
    resolved_root = root.resolve()
    top_level_result = _git_command(root, "rev-parse", "--show-toplevel")
    if top_level_result is None or top_level_result.returncode != 0:
        return {
            "requested_path": resolved_root.as_posix(),
            "available": False,
            "top_level": None,
            "head": None,
            "branch": None,
            "origin_url": None,
            "dirty": None,
            "status_entry_count": None,
            "status_sha256": None,
            "status_entries": [],
        }
    head_result = _git_command(root, "rev-parse", "HEAD")
    branch_result = _git_command(root, "branch", "--show-current")
    origin_result = _git_command(root, "remote", "get-url", "origin")
    status_result = _git_command(
        root, "status", "--porcelain=v1", "--untracked-files=all", "--", "."
    )
    status_text = (
        status_result.stdout
        if status_result is not None and status_result.returncode == 0
        else ""
    )
    status_lines = [line for line in status_text.splitlines() if line]
    return {
        "requested_path": resolved_root.as_posix(),
        "available": True,
        "top_level": top_level_result.stdout.strip(),
        "head": (
            head_result.stdout.strip()
            if head_result is not None and head_result.returncode == 0
            else None
        ),
        "branch": (
            branch_result.stdout.strip()
            if branch_result is not None and branch_result.returncode == 0
            else None
        ),
        "origin_url": (
            origin_result.stdout.strip()
            if origin_result is not None and origin_result.returncode == 0
            else None
        ),
        "dirty": bool(status_lines),
        "status_entry_count": len(status_lines),
        "status_sha256": hashlib.sha256(status_text.encode()).hexdigest(),
        "status_entries": status_lines,
    }


def _reference_match(
    package_manifest: Mapping[str, Any],
    rtl_tree: Mapping[str, Any],
    focus_files: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    reference = package_manifest.get("reference_server_identity", {})
    reference_tree = reference.get("rtl_tree", {})
    expected = reference_tree.get("tree_sha256")
    actual = rtl_tree.get("tree_sha256")
    reference_focus = reference.get("focus_rtl_files", {})
    github_reference = package_manifest.get("github_reference_identity", {})
    github_focus = github_reference.get("files", {})
    local_focus_matches = {
        relative: (
            None
            if reference_focus.get(relative, {}).get(
                "canonical_text_sha256"
            )
            is None
            or actual_identity.get("canonical_text_sha256") is None
            else (
                reference_focus[relative]["canonical_text_sha256"]
                == actual_identity["canonical_text_sha256"]
            )
        )
        for relative, actual_identity in focus_files.items()
    }
    github_focus_matches = {
        relative: (
            None
            if github_focus.get(relative, {}).get(
                "github_canonical_text_sha256"
            )
            is None
            or actual_identity.get("canonical_text_sha256") is None
            else (
                github_focus[relative]["github_canonical_text_sha256"]
                == actual_identity["canonical_text_sha256"]
            )
        )
        for relative, actual_identity in focus_files.items()
    }
    three_way: dict[str, str] = {}
    for relative, actual_identity in focus_files.items():
        server_hash = actual_identity.get("canonical_text_sha256")
        local_hash = reference_focus.get(relative, {}).get(
            "canonical_text_sha256"
        )
        github_hash = github_focus.get(relative, {}).get(
            "github_canonical_text_sha256"
        )
        if server_hash is None or local_hash is None or github_hash is None:
            classification = "unknown"
        elif server_hash == local_hash == github_hash:
            classification = "all_three_match"
        elif server_hash == local_hash:
            classification = "server_matches_local_only"
        elif server_hash == github_hash:
            classification = "server_matches_github_only"
        elif local_hash == github_hash:
            classification = "server_differs_from_matching_references"
        else:
            classification = "all_three_differ"
        three_way[relative] = classification
    return {
        "expected_rtl_tree_sha256": expected,
        "actual_rtl_tree_sha256": actual,
        "rtl_tree_matches_reference": (
            None if expected is None or actual is None else expected == actual
        ),
        "focus_rtl_file_matches_local_reference": local_focus_matches,
        "all_focus_rtl_files_match_local_reference": (
            None
            if not local_focus_matches
            or any(value is None for value in local_focus_matches.values())
            else all(local_focus_matches.values())
        ),
        "focus_rtl_file_matches_github_reference": github_focus_matches,
        "all_focus_rtl_files_match_github_reference": (
            None
            if not github_focus_matches
            or any(value is None for value in github_focus_matches.values())
            else all(github_focus_matches.values())
        ),
        "focus_rtl_three_way_classification": three_way,
    }


def capture_identity(
    *,
    ndp_root: Path,
    package_manifest_path: Path,
    install_name: str,
    phase: str,
    server_command: str,
    exit_status: int | None = None,
) -> dict[str, Any]:
    root = ndp_root.resolve()
    if not root.is_dir():
        raise GapProbeIdentityError(f"missing NDP root: {root}")
    manifest_path = package_manifest_path.resolve()
    if not manifest_path.is_file():
        raise GapProbeIdentityError(
            f"missing test-package manifest: {manifest_path}"
        )
    package_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cfg_root = root / "install" / "cfg_pkg" / install_name
    rtl_tree = tree_identity(root / "rtl")
    focus_files = {
        relative.as_posix(): text_file_identity(root / relative)
        for relative in FOCUS_RTL_RELS
    }
    return {
        "schema": SCHEMA,
        "phase": phase,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "ndp_root": root.as_posix(),
        "server_command": server_command,
        "exit_status": exit_status,
        "test_package": {
            "manifest": file_identity(manifest_path),
            "schema": package_manifest.get("schema"),
            "install_name": package_manifest.get("install_name"),
            "payload_tree_sha256": package_manifest.get("payload_tree_sha256"),
            "source_workload": package_manifest.get("source_workload"),
        },
        "artifacts": {
            "testbench": file_identity(root / "tb_NDP_Top_new_phy.sv"),
            "observer": file_identity(root / "native_return_observer.svh"),
            "makefile": file_identity(root / "Makefile.tb_NDP_Top_new_phy"),
            "active_filelist": file_identity(root / ACTIVE_FILELIST_REL),
            "bitstream": file_identity(root / "install" / "bitstream.txt"),
            "execplan": file_identity(root / "install" / "execplan.txt"),
            "sca_cfg": file_identity(cfg_root / "sca_cfg.json"),
            "sca_cfg_d": file_identity(cfg_root / "sca_cfg_D.json"),
            "focus_rtl_files": focus_files,
        },
        "rtl_tree": rtl_tree,
        "reference_comparison": _reference_match(
            package_manifest, rtl_tree, focus_files
        ),
        "git": git_identity(root),
        "rtl_git": git_identity(root / "rtl"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ndp-root", type=Path, required=True)
    parser.add_argument("--package-manifest", type=Path, required=True)
    parser.add_argument("--install-name", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--server-command", required=True)
    parser.add_argument("--exit-status", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = capture_identity(
        ndp_root=args.ndp_root,
        package_manifest_path=args.package_manifest,
        install_name=args.install_name,
        phase=args.phase,
        server_command=args.server_command,
        exit_status=args.exit_status,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
