#!/usr/bin/env python3
"""Build the fresh QAdd v71 8400-second/reap successor from exact managed v70."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_qadd_n7_tailround_lanephase_v70_pmapfix"
NEW = "r5_qadd_n7_tailround_lanephase_v71_wall8400"
OLD_SHA = "7df37603b1d6ccab664301f8e998d8eacf1e114c434c56eb17b8904b210eaac8"
RETURN_SHA = "ae317f36edd28ecf0b9c3bf7d5c7734612d18755932f9fedb371a1203addb369"
GOOD_BITSTREAM = "a7d42a980945cbfa7292b6e41140f57d51125b242ac302b2602a52651fb2be0f"
EPOCH = "qadd-source-bound-wall-8400-v1"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{OLD}.zip"
SOURCE_RETURN = Path("C:/Users/15383/Downloads/r5_qadd_n7_tailround_lanephase_v70_pmapfix_r1786935559104408108_3677225_return.zip")
SOURCE_ANALYSIS = ROOT / "outputs/qlinearadd_node0007_v70_return_r1786935559104408108_3677225/formal_return_analysis.json"
SOURCE_AUDIT = ROOT / "outputs/qlinearadd_node0007_v70_return_r1786935559104408108_3677225/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"
SOURCE_DISPOSITION = ROOT / "outputs/qlinearadd_node0007_v70_return_r1786935559104408108_3677225/RULE_AUDIT_DISPOSITION.json"
ACTIVATION = ROOT / "outputs/qadd_runtime_budget_8400_activation/CANONICAL_QADD_SOURCE_BOUND_WALL_8400_ACTIVATION_RECEIPT.json"
OUT = ROOT / "outputs/qlinearadd_node0007_v71_wall8400_release"
SOURCE_EXTRACT = OUT / "source_extract"
TREE = OUT / "build" / NEW
ZIP = OUT / f"{NEW}.zip"
REPEAT = OUT / f"{NEW}.repeat.zip"
OLD_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v70.svh"
NEW_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v71.svh"
OLD_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v70.py"
NEW_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v71.py"
OLD_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v70.py"
NEW_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v71.py"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    try:
        name = path.relative_to(ROOT).as_posix()
    except ValueError:
        name = path.as_posix()
    return {"path": name, "bytes": path.stat().st_size, "sha256": sha(path)}


def file_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def subtree(root: Path, ignore: set[str] | None = None) -> dict[str, str]:
    ignored = ignore or set()
    return {
        path.relative_to(root).as_posix(): sha(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in ignored
    }


def normalized_json(path: Path, package: str, version: str) -> Any:
    text = path.read_text(encoding="utf-8")
    return json.loads(text.replace(package, "<PACKAGE_ID>").replace(version, "vXX"))


def deterministic_zip(target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        for path in sorted(TREE.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(f"{NEW}/{path.relative_to(TREE).as_posix()}", (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py" else 0o644) << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=1)


def extract_source() -> Path:
    if OUT.exists():
        raise RuntimeError(f"fresh output exists: {OUT}")
    OUT.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        names = archive.namelist()
        if archive.testzip() is not None:
            raise RuntimeError("source ZIP CRC failure")
        for name in names:
            parts = PurePosixPath(name).parts
            if not parts or parts[0] != OLD or any(part in {"", ".", ".."} for part in parts):
                raise RuntimeError(f"unsafe source ZIP member: {name}")
        archive.extractall(SOURCE_EXTRACT)
    source = SOURCE_EXTRACT / OLD
    shutil.copytree(source, TREE)
    return source


def fresh_identity() -> None:
    suffixes = {".json", ".py", ".sh", ".svh", ".md"}
    for path in sorted(TREE.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if path.relative_to(TREE).as_posix().startswith("provenance/"):
            continue
        text = path.read_text(encoding="utf-8")
        changed = text.replace(OLD, NEW).replace("v70", "v71").replace("V70", "V71").replace("QAdd v70", "QAdd v71")
        if changed != text:
            path.write_text(changed, encoding="utf-8", newline="\n")
    for path in sorted(TREE.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if "v70" in path.name:
            path.rename(path.with_name(path.name.replace("v70", "v71")))
    for cache in sorted(TREE.rglob("__pycache__"), reverse=True):
        shutil.rmtree(cache)
    for path in TREE.rglob("*.pyc"):
        path.unlink()


def runtime_admission() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("server_runtime_budget_admission", ROOT / "tools/server_runtime_budget_admission.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("runtime budget admission tool cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    request = {
        "package_id": NEW,
        "execution_id": "BOUND_AT_FRESH_ATTEMPT",
        "mode": "MEASURED_PRETARGET_AWARE",
        "source_measurement": {
            "source_package_id": OLD,
            "source_return_path": SOURCE_RETURN.as_posix(),
            "source_return_sha256": RETURN_SHA,
            "qualified_progress_source": "PRETARGET_MATRIX_TRANSFER_COMPLETE",
            "qualified_units_completed": 19,
            "total_pretarget_units": 30,
            "elapsed_seconds": 3608.29,
            "target_entry_observed": False,
            "progress_was_advancing": True,
        },
        "safety_factor": 1.25,
        "target_diagnostic_margin_seconds": 900,
        "selected_wall_ceiling_seconds": 8400,
        "independent_operational_guards": {
            "vcd_operational_budget_bytes": 8_000_000_000,
            "return_budget_bytes": 10_000_000_000,
            "disk_space_guard_enabled": True,
            "growth_projection_enabled": True,
            "write_failure_guard_enabled": True,
            "quota_guard_enabled": True,
        },
    }
    receipt = module.calculate(request)
    if receipt.get("pass") is not True or receipt.get("projection", {}).get("recommended_wall_ceiling_seconds") != 8022:
        raise RuntimeError(f"runtime budget admission failed: {receipt.get('errors')}")
    return receipt


def patch_supervisor() -> None:
    supervisor = TREE / NEW_LIVE
    text = supervisor.read_text(encoding="utf-8")
    if text.count("WALL_SECONDS = 3600.0") != 1:
        raise RuntimeError("wall anchor drifted")
    text = text.replace("WALL_SECONDS = 3600.0", "WALL_SECONDS = 8400.0", 1)
    request_anchor = '        "samples": samples,\n        "candidate_catalog_complete": True,'
    request_replacement = '        "samples": samples,\n        "runtime_budget_admission": json.loads((Path(__file__).resolve().parents[1] / "diagnostics/runtime_budget_admission.json").read_text(encoding="utf-8")),\n        "candidate_catalog_complete": True,'
    if text.count(request_anchor) != 1:
        raise RuntimeError("shared evaluator request anchor drifted")
    text = text.replace(request_anchor, request_replacement, 1)
    process_anchor = '            "all_reaped": False,\n        },'
    process_replacement = '            "all_reaped": False,\n            "post_kill_reap_deadline_origin": "NOT_APPLICABLE",\n            "last_kill_host_monotonic_ns": None,\n            "post_kill_reap_deadline_host_monotonic_ns": None,\n            "post_kill_reap_completed": True,\n        },'
    if text.count(process_anchor) != 1:
        raise RuntimeError("live process-receipt anchor drifted")
    text = text.replace(process_anchor, process_replacement, 1)
    decl_anchor = "    root_exit: int | None = None\n"
    decl_replacement = "    root_exit: int | None = None\n    last_kill_host_monotonic_ns: int | None = None\n    post_kill_reap_deadline_host_monotonic_ns: int | None = None\n    post_kill_reap_completed = True\n"
    if text.count(decl_anchor) != 1:
        raise RuntimeError("post-KILL declaration anchor drifted")
    text = text.replace(decl_anchor, decl_replacement, 1)
    old_block = '''        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline and owned(process.pid, pgid, known):
            reaped.extend(reap(min(deadline, time.monotonic() + 0.25), known))
            time.sleep(0.05)
        remaining = owned(process.pid, pgid, known)
        if remaining:
            actions.append(signal_owned(process.pid, pgid, known, signal.SIGKILL))
        try:
            root_exit = process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            actions.append(signal_owned(process.pid, pgid, known, signal.SIGKILL))
            try:
                root_exit = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                root_exit = None
        reap_deadline = time.monotonic() + 60.0
        reaped.extend(reap(reap_deadline, known))
        remaining = owned(process.pid, pgid, known)
        if remaining:
            actions.append(signal_owned(process.pid, pgid, known, signal.SIGKILL))
        while remaining and time.monotonic() < reap_deadline:
            reaped.extend(reap(min(reap_deadline, time.monotonic() + 1.0), known))
            time.sleep(0.1)
            remaining = owned(process.pid, pgid, known)
'''
    new_block = '''        term_deadline = time.monotonic() + 30.0
        while time.monotonic() < term_deadline and owned(process.pid, pgid, known):
            reaped.extend(reap(min(term_deadline, time.monotonic() + 0.25), known))
            time.sleep(0.05)
        remaining = owned(process.pid, pgid, known)
        if remaining:
            actions.append(signal_owned(process.pid, pgid, known, signal.SIGKILL))
            last_kill_host_monotonic_ns = time.monotonic_ns()
        try:
            root_exit = process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            actions.append(signal_owned(process.pid, pgid, known, signal.SIGKILL))
            last_kill_host_monotonic_ns = time.monotonic_ns()
            try:
                root_exit = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                root_exit = None
        reap_deadline = time.monotonic() + 60.0
        if last_kill_host_monotonic_ns is not None:
            post_kill_reap_deadline_host_monotonic_ns = int(reap_deadline * 1_000_000_000)
        reaped.extend(reap(reap_deadline, known))
        remaining = owned(process.pid, pgid, known)
        if remaining:
            actions.append(signal_owned(process.pid, pgid, known, signal.SIGKILL))
            last_kill_host_monotonic_ns = time.monotonic_ns()
            reap_deadline = time.monotonic() + 60.0
            post_kill_reap_deadline_host_monotonic_ns = int(reap_deadline * 1_000_000_000)
            reaped.extend(reap(reap_deadline, known))
            remaining = owned(process.pid, pgid, known)
        post_kill_reap_completed = not remaining
'''
    if text.count(old_block) != 1:
        raise RuntimeError("termination/reap block drifted")
    text = text.replace(old_block, new_block, 1)
    receipt_anchor = '        "process_tree_reaped": not remaining,\n        "sim_time_progress_observed": last_vcd_tick > 0,'
    receipt_replacement = '        "process_tree_reaped": not remaining,\n        "post_kill_reap_deadline_origin": "FRESH_AFTER_LAST_KILL" if last_kill_host_monotonic_ns is not None else "NOT_APPLICABLE",\n        "last_kill_host_monotonic_ns": last_kill_host_monotonic_ns,\n        "post_kill_reap_deadline_host_monotonic_ns": post_kill_reap_deadline_host_monotonic_ns,\n        "post_kill_reap_completed": post_kill_reap_completed,\n        "runtime_budget_admission": json.loads((Path(__file__).resolve().parents[1] / "diagnostics/runtime_budget_admission.json").read_text(encoding="utf-8")),\n        "sim_time_progress_observed": last_vcd_tick > 0,'
    if text.count(receipt_anchor) != 1:
        raise RuntimeError("process output receipt anchor drifted")
    text = text.replace(receipt_anchor, receipt_replacement, 1)
    safety_anchor = '            "thresholds": {\n                "sim_time_freeze_intervals": FREEZE_INTERVALS,'
    safety_replacement = '            "runtime_budget_admission": json.loads((Path(__file__).resolve().parents[1] / "diagnostics/runtime_budget_admission.json").read_text(encoding="utf-8")),\n            "thresholds": {\n                "sim_time_freeze_intervals": FREEZE_INTERVALS,'
    if text.count(safety_anchor) != 1:
        raise RuntimeError("safety receipt anchor drifted")
    supervisor.write_text(text.replace(safety_anchor, safety_replacement, 1), encoding="utf-8", newline="\n")


def bind_contracts(source: Path) -> None:
    provenance = TREE / "provenance"
    for src, name in (
        (SOURCE_ANALYSIS, "v70_formal_return_analysis.json"),
        (SOURCE_AUDIT, "v70_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"),
        (SOURCE_DISPOSITION, "v70_RULE_AUDIT_DISPOSITION.json"),
        (ACTIVATION, "qadd_source_bound_wall_8400_activation_receipt.json"),
        (source / "contracts/server_tb_vcd_bounded_causal_cone_contract.json", "v70_server_tb_vcd_bounded_causal_cone_contract.json"),
        (source / OLD_LIVE, "v70_tb_vcd_live_supervision.py"),
    ):
        shutil.copyfile(src, provenance / name)
    admission_path = TREE / "diagnostics/runtime_budget_admission.json"
    write(admission_path, runtime_admission())
    reap_contract = {
        "schema": "qadd-post-kill-fresh-reap-contract-v1",
        "package_id": NEW,
        "source_package_id": OLD,
        "deadline_origin": "FRESH_AFTER_LAST_KILL",
        "expired_term_deadline_reuse_forbidden": True,
        "stubborn_adopted_descendant_must_fail_closed": True,
        "owned_survivors_allowed": False,
        "functional_delta": False,
        "pass": True,
        "errors": [],
    }
    write(TREE / "diagnostics/post_kill_fresh_reap_contract.json", reap_contract)
    contract_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    contract = load(contract_path)
    signals = [row["signal_id"] for row in contract["signals"]]
    candidates = [row["candidate_id"] for row in contract["candidates"]]
    predecessor_copy = provenance / "v70_server_tb_vcd_bounded_causal_cone_contract.json"
    contract["package_id"] = NEW
    contract["diagnostic_round"]["round_index"] = 5
    contract["diagnostic_round"]["round_kind"] = "EVIDENCE_REFINED_SUCCESSOR"
    contract["diagnostic_round"]["evolution"] = {
        "predecessor": {
            "package_id": OLD,
            "round_index": 4,
            "contract_path": "provenance/v70_server_tb_vcd_bounded_causal_cone_contract.json",
            "contract_sha256": sha(predecessor_copy),
            "pinned_rtl_tree_sha256": contract["diagnostic_round"]["source_identity"]["pinned_rtl_tree_sha256"],
        },
        "added_signal_ids": [],
        "removed_signal_ids": [],
        "unchanged_signal_ids": signals,
        "removal_evidence": [],
        "candidate_preservation": {
            "preserved_candidate_ids": candidates,
            "closed_candidate_ids": [],
            "new_candidate_ids": [],
            "closure_evidence": [],
        },
    }
    contract["execution"]["tb_source_path"] = NEW_TB
    contract["execution"]["tb_source_sha256"] = sha(TREE / NEW_TB)
    contract["budget"].update({
        "wall_ceiling_seconds": 8400,
        "runtime_budget_mode": "MEASURED_PRETARGET_AWARE",
        "absolute_maximum_wall_seconds": 86400,
        "runtime_budget_admission_path": "diagnostics/runtime_budget_admission.json",
        "runtime_budget_admission_sha256": sha(admission_path),
    })
    contract["runtime_policy"].update({
        "post_kill_reap_deadline_origin": "FRESH_AFTER_LAST_KILL",
        "stubborn_adopted_descendant_fail_closed": True,
    })
    contract["claim_boundary"] = "v71 changes only fresh identity, exact source-bound 8400-second admission and fresh post-KILL reaping; validated 4/2/config/workload/TB causal semantics remain frozen."
    write(contract_path, contract)

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = load(request_path)
    request["package_id"] = NEW
    additions = [
        {"source_root": "package", "source": "diagnostics/runtime_budget_admission.json", "archive": "source_package/runtime_budget_admission.json", "required": True},
        {"source_root": "package", "source": "diagnostics/post_kill_fresh_reap_contract.json", "archive": "source_package/post_kill_fresh_reap_contract.json", "required": True},
        {"source_root": "package", "source": "provenance/v70_formal_return_analysis.json", "archive": "source_package/v70_formal_return_analysis.json", "required": True},
        {"source_root": "package", "source": "provenance/v70_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json", "archive": "source_package/v70_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json", "required": True},
        {"source_root": "package", "source": "provenance/qadd_source_bound_wall_8400_activation_receipt.json", "archive": "source_package/qadd_source_bound_wall_8400_activation_receipt.json", "required": True},
    ]
    archives = {row["archive"] for row in request["core_entries"]}
    request["core_entries"].extend(row for row in additions if row["archive"] not in archives)
    write(request_path, request)
    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = load(allow_path)
    allow["package_id"] = NEW
    required = set(allow.get("required", []))
    for row in additions:
        required.add(row["archive"])
        required.add(f"{NEW}_return/{row['archive']}")
    allow["required"] = sorted(required)
    write(allow_path, allow)


def refresh_identities() -> None:
    for source_name in ("server_tb_vcd_runtime_supervision.py", "server_tb_vcd_retention_analysis.py", "server_package_runtime_layout.py", "server_post_sim_return.py"):
        shutil.copyfile(ROOT / "tools" / source_name, TREE / "package_tools" / source_name)
    runner = TREE / "PREPARE_AND_RUN.sh"
    runner_sha = sha(runner)
    resilience_path = TREE / "contracts/server_runner_return_resilience_contract.json"
    resilience = load(resilience_path)
    resilience.update({"package_id": NEW, "runner_sha256": runner_sha})
    write(resilience_path, resilience)
    layout_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = load(layout_path)
    layout.update({"package_id": NEW, "install_name": NEW, "semantic_version": 5})
    projected = f"install/cfg_pkg/{NEW}/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin"
    projected_abs = layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(projected)
    layout["path_budget"]["max_projected_absolute_path_chars"] = projected_abs
    if isinstance(layout.get("runner_bindings"), dict):
        layout["runner_bindings"]["runner_sha256"] = runner_sha
    write(layout_path, layout)
    request_path = TREE / "contracts/server_post_sim_return_request.json"
    post_path = TREE / "contracts/server_post_sim_return_contract.json"
    post = load(post_path)
    post.update({"package_id": NEW, "request_sha256": sha(request_path), "runner_sha256": runner_sha, "helper_sha256": sha(TREE / "package_tools/server_post_sim_return.py")})
    write(post_path, post)
    contract_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    contract = load(contract_path)
    contract["execution"]["tb_source_sha256"] = sha(TREE / NEW_TB)
    write(contract_path, contract)
    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = load(selector_path)
    selector.update({"package_id": NEW, "vcd_contract_sha256": sha(contract_path)})
    selector["return_members"] = sorted(set(selector.get("return_members", [])) | {
        "source_package/runtime_budget_admission.json",
        "source_package/post_kill_fresh_reap_contract.json",
        "source_package/v70_formal_return_analysis.json",
        "source_package/v70_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json",
        "source_package/qadd_source_bound_wall_8400_activation_receipt.json",
    })
    selector["package_members"] = sorted(path.relative_to(TREE).as_posix() for path in TREE.rglob("*") if path.is_file())
    write(selector_path, selector)
    manifest_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = load(manifest_path)
    manifest.update({
        "package_id": NEW,
        "package_identity": NEW,
        "install_name": NEW,
        "activation_epoch": EPOCH,
        "status": "PACKAGE_READY_NOT_RUN",
        "previous_version_progress": "v70 repaired the PID/start-time map and proved production compile/simulation with 19 progressing pretarget transfers, but the fixed 3600-second wall stopped before target entry and post-KILL cleanup reused an expired deadline.",
        "current_version_purpose": "Preserve exact validated 4/2 lineage and the unchanged 64-signal tail-round candidate matrix while selecting the authorized source-bound 8400-second wall and enforcing a fresh bounded reap deadline after every KILL.",
        "runtime_budget_admission": "diagnostics/runtime_budget_admission.json",
        "post_kill_reap_contract": "diagnostics/post_kill_fresh_reap_contract.json",
        "package_build_failure_rule_audit": "provenance/v70_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json",
        "gate_semantic_versions": {"tb_vcd_bounded_causal_cone_final_zip": 6, "first_fresh_extra_audit": 5, "runtime_layout": 5},
        "diagnostic_mode_selector_sha256": sha(selector_path),
    })
    manifest["path_length_budget"]["longest_projected_relative_path"] = projected
    manifest["path_length_budget"]["longest_projected_relative_path_chars"] = len(projected)
    manifest["path_length_budget"]["max_projected_absolute_path_chars"] = projected_abs
    manifest["files"] = file_map(TREE)
    write(manifest_path, manifest)
    selector = load(selector_path)
    selector["package_members"] = sorted(path.relative_to(TREE).as_posix() for path in TREE.rglob("*") if path.is_file())
    write(selector_path, selector)
    manifest = load(manifest_path)
    manifest["diagnostic_mode_selector_sha256"] = sha(selector_path)
    manifest["files"] = file_map(TREE)
    write(manifest_path, manifest)


def main() -> int:
    exact_assets = {
        "source_zip": (SOURCE_ZIP, OLD_SHA),
        "source_return": (SOURCE_RETURN, RETURN_SHA),
        "activation": (ACTIVATION, "317c621673d58079c7b7a34015624a13edd4a591d54e4c621401864f03ace449"),
    }
    for label, (path, expected) in exact_assets.items():
        if not path.is_file() or sha(path) != expected:
            raise RuntimeError(f"{label} absent or drifted")
    source = extract_source()
    source_identity = identity(SOURCE_ZIP)
    source_validation = subtree(source / "validation")
    source_workload = subtree(source / "workload", {"runtime/sca_cfg.json", "runtime/sca_cfg_D.json"})
    source_bitstream = sha(source / "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin")
    source_config = sha(source / "provenance/config_lineage/op_tail_round_4_2.json")
    source_catalog = normalized_json(source / "diagnostics/tb_vcd_signal_catalog.json", OLD, "v70")
    source_matrix = normalized_json(source / "diagnostics/tb_vcd_candidate_matrix.json", OLD, "v70")
    source_tb = (source / OLD_TB).read_text(encoding="utf-8").replace(OLD, "<PACKAGE_ID>").replace("v70", "vXX")
    fresh_identity()
    patch_supervisor()
    bind_contracts(source)
    refresh_identities()
    contract = load(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    frozen_checks = {
        "v70_source_byte_frozen": identity(SOURCE_ZIP) == source_identity,
        "source_return_byte_frozen": sha(SOURCE_RETURN) == RETURN_SHA,
        "config42_bitstream_exact": sha(TREE / "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin") == source_bitstream == GOOD_BITSTREAM,
        "config_json_exact": sha(TREE / "provenance/config_lineage/op_tail_round_4_2.json") == source_config,
        "validation_payload_exact": subtree(TREE / "validation") == source_validation,
        "workload_payload_exact_except_identity_sca": subtree(TREE / "workload", {"runtime/sca_cfg.json", "runtime/sca_cfg_D.json"}) == source_workload,
        "catalog_exact_except_identity": normalized_json(TREE / "diagnostics/tb_vcd_signal_catalog.json", NEW, "v71") == source_catalog,
        "matrix_exact_except_identity": normalized_json(TREE / "diagnostics/tb_vcd_candidate_matrix.json", NEW, "v71") == source_matrix,
        "tb_exact_except_identity": (TREE / NEW_TB).read_text(encoding="utf-8").replace(NEW, "<PACKAGE_ID>").replace("v71", "vXX") == source_tb,
        "signal_count_64": len(contract["signals"]) == 64,
        "functional_rtl_absent": not (TREE / "rtl").exists(),
    }
    frozen = {
        "schema": "qadd-v71-frozen-surface-v1",
        "package_id": NEW,
        "checks": frozen_checks,
        "changed_surfaces": ["fresh_identity", "source_bound_wall_8400_admission", "fresh_post_kill_reap_deadline", "current_shared_runtime_helpers", "audit_provenance"],
        "frozen": ["validated_config42", "bitstream", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_cone", "candidate_matrix", "TB_observation_semantics"],
        "storage_manager_called": False,
        "server_actions_performed": [],
        "pass": all(frozen_checks.values()),
        "errors": [name for name, passed in frozen_checks.items() if not passed],
    }
    write(OUT / "frozen_surface_receipt.json", frozen)
    if not frozen["pass"]:
        raise RuntimeError(f"frozen surface drift: {frozen['errors']}")
    deterministic_zip(ZIP)
    deterministic_zip(REPEAT)
    if sha(ZIP) != sha(REPEAT) or ZIP.read_bytes() != REPEAT.read_bytes():
        raise RuntimeError("deterministic ZIP mismatch")
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC failure")
    receipt = {
        "schema": "qadd-v71-wall8400-build-v1",
        "role_id": "family.qlinearadd",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": NEW,
        "activation_epoch": EPOCH,
        "source_v70": source_identity,
        "source_return": identity(SOURCE_RETURN),
        "return_analysis": identity(SOURCE_ANALYSIS),
        "package_build_failure_rule_audit": identity(SOURCE_AUDIT),
        "runtime_admission": identity(TREE / "diagnostics/runtime_budget_admission.json"),
        "package": identity(ZIP),
        "repeat_package": identity(REPEAT),
        "deterministic_recompute": True,
        "storage_manager_called": False,
        "server_actions_performed": [],
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES",
        "pass": True,
        "errors": [],
        "claim_boundary": "Local fresh identity/runtime/reap construction only; no server, dynamic 4/2 repair, natural terminal, Formal-D or E3-E5 claim.",
    }
    write(OUT / "build_receipt.json", receipt)
    print(json.dumps({"package_id": NEW, "package": str(ZIP), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
