#!/usr/bin/env python3
"""Finalize the second admitted v80 same-identity producer-closure patch."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_TOOL = ROOT / "tools/patch_qlinearadd_node0007_v80_same_identity_release_closure.py"
PREPATCH_ZIP_SHA = "7c014c8ea890e3b59b144ad548a8e1bfe955df78399cda9a988b04b415b30647"
PREPATCH_ZIP_BYTES = 108_883_475


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen(base: Path, tool: Any) -> dict[str, Any]:
    contract = tool.load(base / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    paths = [
        "workload",
        "validation",
        "diagnostics/tb_vcd_signal_catalog.json",
        "diagnostics/tb_vcd_candidate_matrix.json",
        contract["execution"]["tb_source_path"],
    ]
    result: dict[str, Any] = {}
    for name in paths:
        path = base / name
        if path.is_dir():
            rows = tool.members(path)
            result[name] = {"member_count": len(rows), "tree_sha256": tool.tree_identity(rows)}
        else:
            result[name] = {"bytes": path.stat().st_size, "sha256": tool.sha(path)}
    result.update({
        "functional_rtl_absent": not (base / "rtl").exists(),
        "signal_count": len(contract["signals"]),
        "candidate_count": len(contract["candidates"]),
        "candidate_matrix_rows": len(contract["candidate_boundary_matrix"]),
        "selected_wall": contract["budget"]["wall_ceiling_seconds"],
        "absolute_maximum_wall": contract["budget"]["absolute_maximum_wall_seconds"],
    })
    return result


def main() -> int:
    tool = load_module(BASE_TOOL, "qadd_v80_patch_base")
    if tool.ZIP.stat().st_size != PREPATCH_ZIP_BYTES or tool.sha(tool.ZIP) != PREPATCH_ZIP_SHA:
        raise RuntimeError("second-prepatch ZIP identity differs")
    pre_root = tool.OUT / "clean_zip_gate_postpatch" / tool.PACKAGE
    if not pre_root.is_dir():
        raise RuntimeError("second-prepatch exact clean extraction absent")
    pre_rows = tool.members(pre_root)
    pre_frozen = frozen(pre_root, tool)

    runner = tool.TREE / "PREPARE_AND_RUN.sh"
    finalizer = tool.TREE / "package_tools/qlinearadd_node0007_tb_vcd_finalize_v80.py"
    alias_names = (
        "catalog.json", "candidate_matrix.json", "tb_source.json", "elaboration.json",
        "runtime.json", "return_manifest.json", "finalization_receipt.json",
    )
    finalizer_text = finalizer.read_text(encoding="utf-8")
    if any(finalizer_text.count(f'"{name}"') != 1 for name in alias_names):
        raise RuntimeError("canonical alias declaration is absent, duplicate, or drifted")
    runner_text = runner.read_text(encoding="utf-8")
    for token in (
        "qadd-tb-vcd-finalization-guard-receipt-v1",
        "set(mapped)!=expected",
        "hashlib.sha256(data).hexdigest()",
        "set(manifest_rows)!=expected-{'return_manifest.json'}",
    ):
        if token not in runner_text:
            raise RuntimeError(f"runner canonical alias guard token absent: {token}")

    for rel in (
        "contracts/server_runner_return_resilience_contract.json",
        "contracts/server_post_sim_return_contract.json",
    ):
        path = tool.TREE / rel
        value = tool.load(path)
        value["runner_sha256"] = tool.sha(runner)
        tool.write(path, value)
    layout_path = tool.TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = tool.load(layout_path)
    layout["runner_bindings"]["runner_sha256"] = tool.sha(runner)
    tool.write(layout_path, layout)

    selector_path = tool.TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = tool.load(selector_path)
    selector["package_members"] = sorted(
        path.relative_to(tool.TREE).as_posix() for path in tool.TREE.rglob("*") if path.is_file()
    )
    tool.write(selector_path, selector)
    manifest_path = tool.TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = tool.load(manifest_path)
    manifest["diagnostic_mode_selector_sha256"] = tool.sha(selector_path)
    manifest["same_identity_patch_policy"]["producer_closure_patch"] = {
        "canonical_alias_count": 7,
        "finalizer_sha256": tool.sha(finalizer),
        "runner_sha256": tool.sha(runner),
        "content_bound": True,
    }
    manifest["files"] = tool.file_map(tool.TREE)
    tool.write(manifest_path, manifest)

    post_rows = tool.members(tool.TREE)
    post_frozen = frozen(tool.TREE, tool)
    if pre_frozen != post_frozen:
        raise RuntimeError("second patch changed frozen functional/config/causal surface")
    added = sorted(set(post_rows) - set(pre_rows))
    removed = sorted(set(pre_rows) - set(post_rows))
    modified = sorted(name for name in set(pre_rows) & set(post_rows) if pre_rows[name] != post_rows[name])
    unchanged = sorted(name for name in set(pre_rows) & set(post_rows) if pre_rows[name] == post_rows[name])
    if added or removed:
        raise RuntimeError(f"second patch member-set drift: added={added}, removed={removed}")
    tool.write(tool.OUT / "SECOND_SAME_IDENTITY_PRODUCER_PATCH_DELTA.json", {
        "schema": "qadd-v80-second-same-identity-producer-patch-delta-v1",
        "package_id": tool.PACKAGE,
        "classification": "LOCAL_UNPUBLISHED_CANDIDATE_PATCH",
        "prepatch_tree": {"member_count": len(pre_rows), "tree_sha256": tool.tree_identity(pre_rows)},
        "postpatch_tree": {"member_count": len(post_rows), "tree_sha256": tool.tree_identity(post_rows)},
        "added_members": added,
        "removed_members": removed,
        "modified_members": modified,
        "modified_member_identities": {name: {"before": pre_rows[name], "after": post_rows[name]} for name in modified},
        "unchanged_members": unchanged,
        "frozen_surface_before": pre_frozen,
        "frozen_surface_after": post_frozen,
        "frozen_surface_equal": True,
        "canonical_aliases": list(alias_names),
        "old_final_zip_receipts_invalidated": True,
        "pass": True,
        "errors": [],
    })

    tool.deterministic_zip(tool.ZIP)
    tool.deterministic_zip(tool.REPEAT)
    if tool.ZIP.read_bytes() != tool.REPEAT.read_bytes():
        raise RuntimeError("second-patch deterministic ZIP mismatch")
    post_sha = tool.sha(tool.ZIP)
    tool.SIDECAR.write_text(f"{post_sha}  {tool.ZIP.name}\n", encoding="ascii", newline="\n")
    tool.write(tool.OUT / "SECOND_POSTPATCH_BUILD_RECEIPT.json", {
        "schema": "qadd-v80-second-postpatch-build-receipt-v1",
        "package_id": tool.PACKAGE,
        "status": "LOCAL_GATES_PENDING",
        "prepatch_zip": {"bytes": PREPATCH_ZIP_BYTES, "sha256": PREPATCH_ZIP_SHA},
        "postpatch_zip": {"path": tool.ZIP.relative_to(ROOT).as_posix(), "bytes": tool.ZIP.stat().st_size, "sha256": post_sha},
        "repeat_zip_sha256": tool.sha(tool.REPEAT),
        "deterministic": True,
        "storage_manager_called": False,
        "server_actions_performed": [],
        "pass": True,
    })
    print(json.dumps({"package_id": tool.PACKAGE, "zip_bytes": tool.ZIP.stat().st_size, "zip_sha256": post_sha, "modified": modified}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
