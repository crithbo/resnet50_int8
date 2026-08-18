#!/usr/bin/env python3
"""Build fresh QAdd v72 under TB-VCD semantic v7 from exact published v70."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_qadd_n7_tailround_lanephase_v70_pmapfix"
NEW = "r5_qadd_n7_tailround_lanephase_v72_wall8400_v7"
VERSION = "v72"
OUT = ROOT / "outputs/qlinearadd_node0007_v72_release"
TREE = OUT / "build" / NEW
ZIP = OUT / f"{NEW}.zip"
REPEAT = OUT / f"{NEW}.repeat.zip"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{OLD}.zip"
OLD_SHA = "7df37603b1d6ccab664301f8e998d8eacf1e114c434c56eb17b8904b210eaac8"
V70_PASS = ROOT / "outputs/qlinearadd_node0007_v70_pmapfix_release/gates/final_zip_release_audit.json"
V70_PASS_SHA = "6d6e1bb1212c60e2aa0e211dac0661d1b91f01bed84a680b8988e1b6a423137b"
V7_ACTIVATION = ROOT / "outputs/qadd_predecessor_semantic_compatibility_v7/CANONICAL_PREDECESSOR_SEMANTIC_COMPATIBILITY_ACTIVATION_RECEIPT.json"
V7_ACTIVATION_SHA = "ad8b0391c48916adf0507b7e8f2d664d777c72b0c583bb5e9efcaf20c26412b0"
V7_RECORD = ROOT / ".agents/task_records/20260817_tbvcd_predecessor_semantic_compatibility_v7_activation.md"
V7_RECORD_SHA = "aac89e0b5f58b378235f8651043445aad74b766ac00fdb7571277dbf19e9679c"
EPOCH = "qadd-source-bound-wall-8400-v1+tb-vcd-predecessor-semantic-compatibility-v7"
OLD_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v70.svh"
NEW_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v72.svh"
NEW_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v72.py"
NEW_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v72.py"


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load_module(ROOT / "tools/build_qlinearadd_node0007_v71_wall8400.py", "qadd_v71_build_base")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def identity(path: Path) -> dict[str, Any]:
    try:
        name = path.relative_to(ROOT).as_posix()
    except ValueError:
        name = path.as_posix()
    return {"path": name, "bytes": path.stat().st_size, "sha256": sha(path)}


def configure_base() -> None:
    base.NEW = NEW
    base.EPOCH = EPOCH
    base.OUT = OUT
    base.SOURCE_EXTRACT = OUT / "source_extract"
    base.TREE = TREE
    base.ZIP = ZIP
    base.REPEAT = REPEAT
    base.NEW_TB = NEW_TB
    base.NEW_LIVE = NEW_LIVE
    base.NEW_FINALIZER = NEW_FINALIZER


def fresh_identity() -> None:
    suffixes = {".json", ".py", ".sh", ".svh", ".md"}
    for path in sorted(TREE.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if path.relative_to(TREE).as_posix().startswith("provenance/"):
            continue
        text = path.read_text(encoding="utf-8")
        changed = text.replace(OLD, NEW).replace("v70", VERSION).replace("V70", VERSION.upper()).replace("QAdd v70", f"QAdd {VERSION}")
        if changed != text:
            path.write_text(changed, encoding="utf-8", newline="\n")
    for path in sorted(TREE.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if "v70" in path.name:
            path.rename(path.with_name(path.name.replace("v70", VERSION)))
    for cache in sorted(TREE.rglob("__pycache__"), reverse=True):
        shutil.rmtree(cache)
    for path in TREE.rglob("*.pyc"):
        path.unlink()


def patch_finalizer() -> None:
    path = TREE / NEW_FINALIZER
    text = path.read_text(encoding="utf-8")
    all_reaped = '        "all_reaped": process.get("process_tree_reaped") is True,\n'
    replacement = all_reaped + (
        '        "post_kill_reap_deadline_origin": process.get("post_kill_reap_deadline_origin", "NOT_APPLICABLE" if not any(item.get("signal") == 9 for item in process.get("termination", []) if isinstance(item, dict)) else None),\n'
        '        "last_kill_host_monotonic_ns": process.get("last_kill_host_monotonic_ns"),\n'
        '        "post_kill_reap_deadline_host_monotonic_ns": process.get("post_kill_reap_deadline_host_monotonic_ns"),\n'
        '        "post_kill_reap_completed": process.get("post_kill_reap_completed", not any(item.get("signal") == 9 for item in process.get("termination", []) if isinstance(item, dict))) is True,\n'
    )
    if text.count(all_reaped) != 1:
        raise RuntimeError("finalizer process-tree propagation anchor drifted")
    text = text.replace(all_reaped, replacement, 1)
    samples = '        "samples": samples,\n'
    if text.count(samples) != 1:
        raise RuntimeError("finalizer evaluator request anchor drifted")
    text = text.replace(
        samples,
        samples + '        "runtime_budget_admission": load(package / "diagnostics/runtime_budget_admission.json"),\n',
        1,
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def bind_v7() -> None:
    provenance = TREE / "provenance"
    copied = (
        (V70_PASS, provenance / "v70_published_pass_release_receipt.json"),
        (V7_ACTIVATION, provenance / "tbvcd_predecessor_semantic_v7_activation_receipt.json"),
        (V7_RECORD, provenance / "tbvcd_predecessor_semantic_v7_activation_task_record.md"),
    )
    for source, target in copied:
        shutil.copyfile(source, target)
    contract_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    contract = load(contract_path)
    predecessor = contract["diagnostic_round"]["evolution"]["predecessor"]
    predecessor.update({
        "published_gate_semantic_version": "5",
        "published_pass_receipt_path": "provenance/v70_published_pass_release_receipt.json",
        "published_pass_receipt_sha256": sha(provenance / "v70_published_pass_release_receipt.json"),
    })
    contract["claim_boundary"] = f"{VERSION} changes only fresh identity, exact semantic-v5 predecessor PASS binding, source-bound 8400-second admission, fresh post-KILL reaping, finalizer propagation and gate-harness dependency binding; validated 4/2/config/workload/TB causal semantics remain frozen."
    write(contract_path, contract)

    additions = [
        {"source_root": "package", "source": "provenance/v70_published_pass_release_receipt.json", "archive": "source_package/v70_published_pass_release_receipt.json", "required": True},
        {"source_root": "package", "source": "provenance/tbvcd_predecessor_semantic_v7_activation_receipt.json", "archive": "source_package/tbvcd_predecessor_semantic_v7_activation_receipt.json", "required": True},
        {"source_root": "package", "source": "provenance/tbvcd_predecessor_semantic_v7_activation_task_record.md", "archive": "source_package/tbvcd_predecessor_semantic_v7_activation_task_record.md", "required": True},
    ]
    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = load(request_path)
    archives = {row["archive"] for row in request["core_entries"]}
    request["core_entries"].extend(row for row in additions if row["archive"] not in archives)
    write(request_path, request)
    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = load(allow_path)
    required = set(allow.get("required", []))
    for row in additions:
        required.add(row["archive"])
        required.add(f"{NEW}_return/{row['archive']}")
    allow["required"] = sorted(required)
    write(allow_path, allow)


def refresh_v7_identities() -> None:
    runner = TREE / "PREPARE_AND_RUN.sh"
    request_path = TREE / "contracts/server_post_sim_return_request.json"
    post_path = TREE / "contracts/server_post_sim_return_contract.json"
    post = load(post_path)
    post.update({
        "package_id": NEW,
        "request_sha256": sha(request_path),
        "runner_sha256": sha(runner),
        "helper_sha256": sha(TREE / "package_tools/server_post_sim_return.py"),
    })
    write(post_path, post)
    contract_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    contract = load(contract_path)
    contract["execution"]["tb_source_sha256"] = sha(TREE / NEW_TB)
    write(contract_path, contract)
    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = load(selector_path)
    selector["vcd_contract_sha256"] = sha(contract_path)
    selector["return_members"] = sorted(set(selector.get("return_members", [])) | {
        "source_package/v70_published_pass_release_receipt.json",
        "source_package/tbvcd_predecessor_semantic_v7_activation_receipt.json",
        "source_package/tbvcd_predecessor_semantic_v7_activation_task_record.md",
    })
    selector["package_members"] = sorted(path.relative_to(TREE).as_posix() for path in TREE.rglob("*") if path.is_file())
    write(selector_path, selector)
    manifest_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = load(manifest_path)
    manifest.update({
        "activation_epoch": EPOCH,
        "gate_semantic_versions": {"tb_vcd_bounded_causal_cone_final_zip": 7, "first_fresh_extra_audit": 6, "runtime_layout": 5},
        "previous_version_progress": "v70 reached production simulation and 19/30 advancing pretarget transfers; v71 then exposed only local semantic-compatibility/finalizer/gate-runtime build defects and remains nonpublishable.",
        "current_version_purpose": "Preserve exact v70 validated 4/2 lineage and 64-signal target while applying current semantic-v7 predecessor compatibility, complete runtime/reap finalizer propagation and the existing schema-enabled repository gate runtime.",
        "diagnostic_mode_selector_sha256": sha(selector_path),
    })
    manifest["files"] = base.file_map(TREE)
    write(manifest_path, manifest)
    selector = load(selector_path)
    selector["package_members"] = sorted(path.relative_to(TREE).as_posix() for path in TREE.rglob("*") if path.is_file())
    write(selector_path, selector)
    manifest = load(manifest_path)
    manifest["diagnostic_mode_selector_sha256"] = sha(selector_path)
    manifest["files"] = base.file_map(TREE)
    write(manifest_path, manifest)


def main() -> int:
    configure_base()
    exact = ((SOURCE_ZIP, OLD_SHA), (V70_PASS, V70_PASS_SHA), (V7_ACTIVATION, V7_ACTIVATION_SHA), (V7_RECORD, V7_RECORD_SHA))
    for path, expected in exact:
        if not path.is_file() or sha(path) != expected:
            raise RuntimeError(f"exact input absent or drifted: {path}")
    source = base.extract_source()
    source_identity = identity(SOURCE_ZIP)
    source_validation = base.subtree(source / "validation")
    source_workload = base.subtree(source / "workload", {"runtime/sca_cfg.json", "runtime/sca_cfg_D.json"})
    source_bitstream = sha(source / "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin")
    source_catalog = base.normalized_json(source / "diagnostics/tb_vcd_signal_catalog.json", OLD, "v70")
    source_matrix = base.normalized_json(source / "diagnostics/tb_vcd_candidate_matrix.json", OLD, "v70")
    source_tb = (source / OLD_TB).read_text(encoding="utf-8").replace(OLD, "<PACKAGE_ID>").replace("v70", "vXX")
    fresh_identity()
    base.patch_supervisor()
    base.bind_contracts(source)
    patch_finalizer()
    bind_v7()
    base.refresh_identities()
    refresh_v7_identities()
    contract = load(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    checks = {
        "v70_source_byte_frozen": identity(SOURCE_ZIP) == source_identity,
        "config42_bitstream_exact": sha(TREE / "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin") == source_bitstream == base.GOOD_BITSTREAM,
        "validation_payload_exact": base.subtree(TREE / "validation") == source_validation,
        "workload_payload_exact_except_identity_sca": base.subtree(TREE / "workload", {"runtime/sca_cfg.json", "runtime/sca_cfg_D.json"}) == source_workload,
        "catalog_exact_except_identity": base.normalized_json(TREE / "diagnostics/tb_vcd_signal_catalog.json", NEW, VERSION) == source_catalog,
        "matrix_exact_except_identity": base.normalized_json(TREE / "diagnostics/tb_vcd_candidate_matrix.json", NEW, VERSION) == source_matrix,
        "tb_exact_except_identity": (TREE / NEW_TB).read_text(encoding="utf-8").replace(NEW, "<PACKAGE_ID>").replace(VERSION, "vXX") == source_tb,
        "signal_count_64": len(contract["signals"]) == 64,
        "functional_rtl_absent": not (TREE / "rtl").exists(),
    }
    frozen = {
        "schema": f"qadd-{VERSION}-frozen-surface-v1", "package_id": NEW, "checks": checks,
        "changed_surfaces": ["fresh_identity", "semantic_v7_predecessor_binding", "finalizer_runtime_reap_propagation", "gate_runtime_binding", "source_bound_wall_8400_admission", "fresh_post_kill_reap_deadline", "current_shared_runtime_helpers"],
        "frozen": ["validated_config42", "bitstream", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_cone", "candidate_matrix", "TB_observation_semantics"],
        "storage_manager_called": False, "server_actions_performed": [], "pass": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
    }
    write(OUT / "frozen_surface_receipt.json", frozen)
    if not frozen["pass"]:
        raise RuntimeError(f"frozen surface drift: {frozen['errors']}")
    base.deterministic_zip(ZIP)
    base.deterministic_zip(REPEAT)
    if ZIP.read_bytes() != REPEAT.read_bytes():
        raise RuntimeError("deterministic ZIP mismatch")
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC failure")
    receipt = {
        "schema": f"qadd-{VERSION}-wall8400-semantic-v7-build-v1", "role_id": "family.qlinearadd",
        "owner_epoch": 2, "registry_epoch": 6, "package_id": NEW, "activation_epoch": EPOCH,
        "source_v70": source_identity, "source_return": identity(base.SOURCE_RETURN),
        "runtime_admission": identity(TREE / "diagnostics/runtime_budget_admission.json"),
        "v70_published_pass_receipt": identity(TREE / "provenance/v70_published_pass_release_receipt.json"),
        "semantic_v7_activation": identity(TREE / "provenance/tbvcd_predecessor_semantic_v7_activation_receipt.json"),
        "package": identity(ZIP), "repeat_package": identity(REPEAT), "deterministic_recompute": True,
        "storage_manager_called": False, "server_actions_performed": [],
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES", "pass": True, "errors": [],
        "claim_boundary": "Local fresh package construction only; no server, dynamic 4/2 repair, natural terminal, Formal-D or E3-E5 claim.",
    }
    write(OUT / "build_receipt.json", receipt)
    print(json.dumps({"package_id": NEW, "package": str(ZIP), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
