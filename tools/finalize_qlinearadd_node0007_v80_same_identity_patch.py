#!/usr/bin/env python3
"""Finalize v80's admitted same-identity patch after phase-marker hardening."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PATCH_TOOL = ROOT / "tools/patch_qlinearadd_node0007_v80_same_identity_release_closure.py"


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    patch = load_module(PATCH_TOOL, "qadd_v80_same_identity_patch")
    runner = patch.TREE / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    markers = [
        "phase_FINALIZATION_GUARD_COMPLETE=1",
        "phase_RETURN_PUBLISH=1",
        "phase_DURABLE_RETURN_RECEIPT=1",
        "phase_POST_DURABLE_CLEANUP_RECEIPT=1",
    ]
    positions = [text.count(marker) for marker in markers]
    if positions != [1, 1, 1, 1]:
        raise RuntimeError(f"phase markers are not one-shot exact: {positions}")
    offsets = [text.index(marker) for marker in markers]
    if offsets != sorted(offsets):
        raise RuntimeError("phase markers are not in guard/publish/durable/cleanup order")

    for rel in (
        "contracts/server_runner_return_resilience_contract.json",
        "contracts/server_post_sim_return_contract.json",
    ):
        path = patch.TREE / rel
        value = patch.load(path)
        value["runner_sha256"] = patch.sha(runner)
        patch.write(path, value)
    layout_path = patch.TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = patch.load(layout_path)
    if not isinstance(layout.get("runner_bindings"), dict):
        raise RuntimeError("runtime layout runner_bindings missing")
    layout["runner_bindings"]["runner_sha256"] = patch.sha(runner)
    patch.write(layout_path, layout)

    selector_path = patch.TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = patch.load(selector_path)
    selector["package_members"] = sorted(
        path.relative_to(patch.TREE).as_posix()
        for path in patch.TREE.rglob("*")
        if path.is_file()
    )
    patch.write(selector_path, selector)
    manifest_path = patch.TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = patch.load(manifest_path)
    manifest["diagnostic_mode_selector_sha256"] = patch.sha(selector_path)
    manifest["files"] = patch.file_map(patch.TREE)
    patch.write(manifest_path, manifest)

    delta_path = patch.OUT / "SAME_IDENTITY_PATCH_DELTA.json"
    delta = patch.load(delta_path)
    prepatch_root = patch.OUT / "clean_zip_gate" / patch.PACKAGE
    if not prepatch_root.is_dir():
        raise RuntimeError("exact prepatch clean extraction is absent")
    pre_rows = patch.members(prepatch_root)
    rows = patch.members(patch.TREE)
    frozen = patch.frozen_snapshot()
    if frozen != delta["frozen_surface_before"]:
        raise RuntimeError("frozen functional/config/causal surface changed")
    delta["postpatch_tree"] = {
        "member_count": len(rows),
        "tree_sha256": patch.tree_identity(rows),
    }
    added = sorted(set(rows) - set(pre_rows))
    removed = sorted(set(pre_rows) - set(rows))
    modified = sorted(name for name in set(pre_rows) & set(rows) if pre_rows[name] != rows[name])
    unchanged = sorted(name for name in set(pre_rows) & set(rows) if pre_rows[name] == rows[name])
    delta["added_members"] = added
    delta["removed_members"] = removed
    delta["modified_members"] = modified
    delta["modified_member_identities"] = {
        name: {"before": pre_rows[name], "after": rows[name]} for name in modified
    }
    delta["unchanged_members"] = unchanged
    delta["unchanged_member_count"] = len(unchanged)
    if added or removed:
        raise RuntimeError(f"same-identity patch member-set drift: added={added}, removed={removed}")
    delta["frozen_surface_after"] = frozen
    delta["phase_marker_hardening"] = {
        "markers": markers,
        "one_shot_exact": True,
        "ordered": True,
        "completion_bound": True,
    }
    patch.write(delta_path, delta)

    patch.deterministic_zip(patch.ZIP)
    patch.deterministic_zip(patch.REPEAT)
    if patch.ZIP.read_bytes() != patch.REPEAT.read_bytes():
        raise RuntimeError("postpatch deterministic ZIP mismatch")
    post_sha = patch.sha(patch.ZIP)
    patch.SIDECAR.write_text(f"{post_sha}  {patch.ZIP.name}\n", encoding="ascii", newline="\n")
    receipt_path = patch.OUT / "POSTPATCH_BUILD_RECEIPT.json"
    receipt = patch.load(receipt_path)
    receipt["postpatch_zip"] = {
        "path": patch.ZIP.relative_to(ROOT).as_posix(),
        "bytes": patch.ZIP.stat().st_size,
        "sha256": post_sha,
    }
    receipt["repeat_zip_sha256"] = patch.sha(patch.REPEAT)
    receipt["phase_markers_bound"] = markers
    patch.write(receipt_path, receipt)
    print(json.dumps({
        "package_id": patch.PACKAGE,
        "zip_bytes": patch.ZIP.stat().st_size,
        "zip_sha256": post_sha,
        "tree_sha256": delta["postpatch_tree"]["tree_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
