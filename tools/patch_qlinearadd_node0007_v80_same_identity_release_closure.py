#!/usr/bin/env python3
"""Apply the admitted same-identity v80 return-phase closure patch once."""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tr_v80_w15kqf"
OUT = ROOT / "outputs/qadd_v80_w15kqf"
TREE = OUT / "b" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
REPEAT = OUT / f"{PACKAGE}.repeat.zip"
SIDECAR = OUT / f"{PACKAGE}.zip.sha256"
POLICY = ROOT / "outputs/mainline_package_build_slowness_rule_skill_audit_v1/CANONICAL_LOCAL_UNPUBLISHED_CANDIDATE_PATCH_POLICY_RECONCILIATION_RECEIPT.json"
POLICY_SHA = "21556c8e64d5171c5d04d36aa4b4445c26fa32c9f8eb4f3d877b3b63be905360"
PREPATCH_ZIP_SHA = "7741d5251a4e9dec826781d82eb3bbb7f51f043758d4427846cd1714ea82a37f"
PREPATCH_ZIP_BYTES = 108_881_653


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def members(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {"bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def tree_identity(rows: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for name, row in sorted(rows.items()):
        digest.update(f"{name}\0{row['bytes']}\0{row['sha256']}\n".encode("utf-8"))
    return digest.hexdigest()


def file_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(root.rglob("*")) if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def deterministic_zip(target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        for path in sorted(TREE.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(f"{PACKAGE}/{path.relative_to(TREE).as_posix()}", (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py" else 0o644) << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=1)


def frozen_snapshot() -> dict[str, Any]:
    contract = load(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    paths = [
        "workload",
        "validation",
        "diagnostics/tb_vcd_signal_catalog.json",
        "diagnostics/tb_vcd_candidate_matrix.json",
        contract["execution"]["tb_source_path"],
    ]
    result: dict[str, Any] = {}
    for name in paths:
        path = TREE / name
        if path.is_dir():
            rows = members(path)
            result[name] = {"member_count": len(rows), "tree_sha256": tree_identity(rows)}
        else:
            result[name] = {"bytes": path.stat().st_size, "sha256": sha(path)}
    result["functional_rtl_absent"] = not (TREE / "rtl").exists()
    result["signal_count"] = len(contract["signals"])
    result["candidate_count"] = len(contract["candidates"])
    result["candidate_matrix_rows"] = len(contract["candidate_boundary_matrix"])
    result["selected_wall"] = contract["budget"]["wall_ceiling_seconds"]
    result["absolute_maximum_wall"] = contract["budget"]["absolute_maximum_wall_seconds"]
    return result


def patch_runner() -> None:
    path = TREE / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    guard_anchor = "    diagnostic_status=$?\n"
    guard_replacement = guard_anchor + '''    finalization_guard_receipt="$evidence_root/vcd/finalization_receipt.json"
    finalization_guard_complete=false
    if [ -f "$finalization_guard_receipt" ]; then
      phase_FINALIZATION_GUARD_COMPLETE=1
      finalization_guard_complete=true
    else
      diagnostic_status=122
    fi
'''
    if text.count(guard_anchor) != 1:
        raise RuntimeError("v80 finalization guard anchor drifted")
    text = text.replace(guard_anchor, guard_replacement, 1)

    publish_anchor = '''    python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"
    collect_status=$?
    final="$original"
'''
    publish_replacement = '''    collect_status=122
    if [ "$finalization_guard_complete" = true ]; then
      python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"
      collect_status=$?
      [ "$collect_status" -ne 0 ] || phase_RETURN_PUBLISH=1
    fi
    durable_status=98
    cleanup_status=98
    durable_return_receipt="$result_root/${package_id}_${return_tag}_DURABLE_RETURN_RECEIPT.json"
    post_durable_cleanup_receipt="$result_root/${package_id}_${return_tag}_POST_DURABLE_CLEANUP_RECEIPT.json"
    if [ "$collect_status" -eq 0 ] && [ -f "$return_zip" ] && [ -f "$return_sha" ]; then
      python3 - "$return_zip" "$return_sha" "$durable_return_receipt" "$package_id" "$return_tag" "$attempt" <<'PY'
import hashlib,json,os,pathlib,sys,zipfile
z,side,out=map(pathlib.Path,sys.argv[1:4]);pkg,exe,att=sys.argv[4:7]
h=hashlib.sha256(); size=0
with z.open('rb') as stream:
    for block in iter(lambda:stream.read(1048576),b''): size+=len(block); h.update(block)
digest=h.hexdigest(); token=side.read_text(encoding='ascii').strip().split()
with zipfile.ZipFile(z) as archive: bad=archive.testzip(); count=len([n for n in archive.namelist() if not n.endswith('/')])
if bad is not None or len(token)<2 or token[0]!=digest or token[1]!=z.name: raise SystemExit(98)
value={'schema':'qadd-durable-return-receipt-v1','package_id':pkg,'execution_id':exe,'attempt_id':att,'return_zip':str(z),'bytes':size,'sha256':digest,'member_count':count,'sidecar':str(side),'pass':True}
tmp=out.with_name('.'+out.name+'.tmp.'+str(os.getpid()));tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\\n');os.replace(tmp,out)
PY
      durable_status=$?
      [ "$durable_status" -ne 0 ] || phase_DURABLE_RETURN_RECEIPT=1
    fi
    if [ "$durable_status" -eq 0 ]; then
      python3 - "$server_root" "$package_id" "$install_name" "$attempt" "$return_tag" "$run_root" "$bootstrap_root" "$return_zip" "$durable_return_receipt" "$post_durable_cleanup_receipt" <<'PY'
import json,os,pathlib,shutil,sys
server=pathlib.Path(sys.argv[1]).resolve();pkg,install,att,exe=sys.argv[2:6];run=pathlib.Path(sys.argv[6]).resolve();boot=pathlib.Path(sys.argv[7]).resolve();ret=pathlib.Path(sys.argv[8]).resolve();durable=pathlib.Path(sys.argv[9]).resolve();out=pathlib.Path(sys.argv[10])
parent=(server/'install/codex_runs'/pkg).resolve(); expected_run=(parent/att).resolve(); expected_boot=(parent/('.compile-return-'+exe)).resolve(); marker=parent/('.codex_owner.'+att+'.json')
if run!=expected_run or boot!=expected_boot or any(p.is_symlink() or not p.is_dir() for p in (server,parent,run,boot)): raise SystemExit(98)
if not marker.is_file() or marker.is_symlink() or not ret.is_file() or ret.is_symlink() or not durable.is_file() or durable.is_symlink(): raise SystemExit(98)
owner=json.loads(marker.read_text()); expected={'package_id':pkg,'install_name':install,'attempt':att,'kind':'run_root'}
if any(owner.get(k)!=v for k,v in expected.items()): raise SystemExit(98)
def size(path): return sum(p.stat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink())
before={'run_root_bytes':size(run),'bootstrap_root_bytes':size(boot)};shutil.rmtree(run);shutil.rmtree(boot);marker.unlink()
removed_parent=False
if parent.is_dir() and not any(parent.iterdir()): parent.rmdir();removed_parent=True
value={'schema':'qadd-post-durable-cleanup-receipt-v1','package_id':pkg,'execution_id':exe,'attempt_id':att,'return_zip':str(ret),'durable_return_receipt':str(durable),'removed':{'run_root':str(run),'bootstrap_root':str(boot),'ownership_marker':str(marker),'empty_package_parent':removed_parent},'bytes_before':before,'foreign_siblings_preserved':True,'pass':True}
tmp=out.with_name('.'+out.name+'.tmp.'+str(os.getpid()));tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\\n');os.replace(tmp,out)
PY
      cleanup_status=$?
      [ "$cleanup_status" -ne 0 ] || phase_POST_DURABLE_CLEANUP_RECEIPT=1
    fi
    final="$original"
'''
    if text.count(publish_anchor) != 1:
        raise RuntimeError("v80 return publication anchor drifted")
    text = text.replace(publish_anchor, publish_replacement, 1)
    status_anchor = '''    [ "$diagnostic_status" -eq 0 ] || [ "$final" -ne 0 ] || final="$diagnostic_status"
'''
    status_replacement = status_anchor + '''    [ "$durable_status" -eq 0 ] || [ "$final" -ne 0 ] || final="$durable_status"
    [ "$cleanup_status" -eq 0 ] || [ "$final" -ne 0 ] || final="$cleanup_status"
'''
    if text.count(status_anchor) != 1:
        raise RuntimeError("v80 final status anchor drifted")
    text = text.replace(status_anchor, status_replacement, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    if not POLICY.is_file() or sha(POLICY) != POLICY_SHA:
        raise RuntimeError("same-identity patch policy receipt absent or drifted")
    if ZIP.stat().st_size != PREPATCH_ZIP_BYTES or sha(ZIP) != PREPATCH_ZIP_SHA:
        raise RuntimeError("prepatch v80 ZIP identity differs")
    pre_rows = members(TREE)
    pre_frozen = frozen_snapshot()
    old_receipts = {}
    for path in (
        OUT / "gates/final_zip_release_audit.json",
        OUT / "INDEPENDENT_PACKAGE_AUDIT_HANDOFF.json",
        OUT / "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE.json",
    ):
        if path.is_file():
            old_receipts[path.relative_to(ROOT).as_posix()] = {"bytes": path.stat().st_size, "sha256": sha(path), "disposition": "INVALIDATED_BY_SAME_IDENTITY_PATCH"}
    write(OUT / "PREPATCH_IDENTITY_AND_RECEIPT_INVALIDATION.json", {
        "schema": "qadd-v80-prepatch-identity-and-receipt-invalidation-v1",
        "package_id": PACKAGE,
        "policy_receipt": {"path": POLICY.relative_to(ROOT).as_posix(), "sha256": POLICY_SHA},
        "prepatch_tree": {"member_count": len(pre_rows), "tree_sha256": tree_identity(pre_rows)},
        "prepatch_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": PREPATCH_ZIP_BYTES, "sha256": PREPATCH_ZIP_SHA},
        "invalidated_receipts": old_receipts,
        "pass": True,
    })

    patch_runner()
    request = load(TREE / "contracts/server_post_sim_return_request.json")
    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = load(allow_path)
    required = set(allow.get("required", []))
    required.update(row["archive"] for row in request["core_entries"] if row.get("required") is True)
    allow["required"] = sorted(required)
    write(allow_path, allow)

    runner = TREE / "PREPARE_AND_RUN.sh"
    resilience_path = TREE / "contracts/server_runner_return_resilience_contract.json"
    resilience = load(resilience_path); resilience["runner_sha256"] = sha(runner); write(resilience_path, resilience)
    post_path = TREE / "contracts/server_post_sim_return_contract.json"
    post = load(post_path); post["runner_sha256"] = sha(runner); write(post_path, post)
    layout_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = load(layout_path)
    if isinstance(layout.get("runner_bindings"), dict): layout["runner_bindings"]["runner_sha256"] = sha(runner)
    write(layout_path, layout)

    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = load(selector_path)
    selector["package_members"] = sorted(path.relative_to(TREE).as_posix() for path in TREE.rglob("*") if path.is_file())
    write(selector_path, selector)
    manifest_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = load(manifest_path)
    manifest["diagnostic_mode_selector_sha256"] = sha(selector_path)
    manifest["same_identity_patch_policy"] = {
        "classification": "LOCAL_UNPUBLISHED_CANDIDATE_PATCH",
        "policy_receipt_sha256": POLICY_SHA,
        "prepatch_zip_sha256": PREPATCH_ZIP_SHA,
        "patched_surfaces": ["RETURN_ALLOWLIST.required exact closure", "PREPARE_AND_RUN guard-publish-durable-cleanup temporal closure"],
    }
    manifest["files"] = file_map(TREE)
    write(manifest_path, manifest)

    post_rows = members(TREE)
    post_frozen = frozen_snapshot()
    if pre_frozen != post_frozen:
        raise RuntimeError("frozen functional/config/causal surface changed")
    added = sorted(set(post_rows) - set(pre_rows))
    removed = sorted(set(pre_rows) - set(post_rows))
    modified = sorted(name for name in set(pre_rows) & set(post_rows) if pre_rows[name] != post_rows[name])
    unchanged = sorted(name for name in set(pre_rows) & set(post_rows) if pre_rows[name] == post_rows[name])
    write(OUT / "SAME_IDENTITY_PATCH_DELTA.json", {
        "schema": "qadd-v80-same-identity-patch-delta-v1",
        "package_id": PACKAGE,
        "classification": "LOCAL_UNPUBLISHED_CANDIDATE_PATCH",
        "prepatch_tree": {"member_count": len(pre_rows), "tree_sha256": tree_identity(pre_rows)},
        "postpatch_tree": {"member_count": len(post_rows), "tree_sha256": tree_identity(post_rows)},
        "added_members": added,
        "removed_members": removed,
        "modified_members": modified,
        "unchanged_member_count": len(unchanged),
        "frozen_surface_before": pre_frozen,
        "frozen_surface_after": post_frozen,
        "frozen_surface_equal": True,
        "old_final_zip_receipts_invalidated": True,
        "receipt_reuse_disposition": "RERUN_ALL_RECEIPT_REUSE_FALSE_FINAL_ZIP_GATES_AND_ALL_CHANGED_DEPENDENCY_GATES",
        "pass": not removed,
        "errors": [] if not removed else ["member removal is forbidden"],
    })
    if removed:
        raise RuntimeError(f"unexpected removed members: {removed}")
    deterministic_zip(ZIP); deterministic_zip(REPEAT)
    if ZIP.read_bytes() != REPEAT.read_bytes():
        raise RuntimeError("postpatch deterministic ZIP mismatch")
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("postpatch ZIP CRC failure")
    SIDECAR.write_text(f"{sha(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n")
    write(OUT / "POSTPATCH_BUILD_RECEIPT.json", {
        "schema": "qadd-v80-postpatch-build-receipt-v1",
        "package_id": PACKAGE,
        "status": "LOCAL_GATES_PENDING",
        "prepatch_zip_sha256": PREPATCH_ZIP_SHA,
        "postpatch_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)},
        "repeat_zip_sha256": sha(REPEAT),
        "deterministic": True,
        "storage_manager_called": False,
        "server_actions_performed": [],
        "pass": True,
    })
    print(json.dumps({"package_id": PACKAGE, "zip_sha256": sha(ZIP), "modified_members": modified}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
