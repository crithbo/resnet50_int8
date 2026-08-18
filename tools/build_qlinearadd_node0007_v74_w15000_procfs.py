#!/usr/bin/env python3
"""Build one fresh QAdd v74 from exact v73 after the 15000-second activation."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_qadd_n7_tailround_lanephase_v73_w8400v7"
NEW = "r5_qadd_n7_tailround_v74_w15kpfs"
VERSION = "v74"
EPOCH = "qadd-source-bound-wall-15000-v1+family-dispatch-mode-binding-v1"
OUT = ROOT / "outputs/qlinearadd_node0007_v74_w15000_procfs_release"
TREE = OUT / "build" / NEW
ZIP = OUT / f"{NEW}.zip"
REPEAT = OUT / f"{NEW}.repeat.zip"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{OLD}.zip"
SOURCE_ZIP_SHA = "0cd165a36014e878e507dfc3e810d0271c1e41e1484ca7d5d8e248f8330be18f"
SOURCE_RETURN = Path("C:/Users/15383/Downloads/r5_qadd_n7_tailround_lanephase_v73_w8400v7_r1786958027042931325_3775010_return.zip")
SOURCE_RETURN_SHA = "a65425c43962ee172bf4583b4a114b0a5123d0a19eb20a80860c19ac52e2f23c"
SOURCE_ANALYSIS = ROOT / "outputs/qlinearadd_node0007_v73_return_r1786958027042931325_3775010/formal_return_analysis.json"
SOURCE_ANALYSIS_SHA = "f0e7d0298d80c233041be6dd26fda8c6aaaabcca6353586f31cd94cc063bc432"
SOURCE_FORMAL_RECEIPT = ROOT / "outputs/qlinearadd_node0007_v73_return_r1786958027042931325_3775010/formal_mainline_receipt.json"
SOURCE_RULE_AUDIT = ROOT / "outputs/qlinearadd_node0007_v73_return_r1786958027042931325_3775010/RULE_GAP_AUDIT.json"
SOURCE_PASS = ROOT / "outputs/qlinearadd_node0007_v73_release/gates/final_zip_release_audit.json"
SOURCE_PASS_SHA = "17c0aa3e4d62e45c3cb196700c968d1a3648ed0a6d4ef752ac8cbfa9e9066a04"
ACTIVATION_15000 = ROOT / "outputs/qadd_source_bound_wall_15000_activation/CANONICAL_QADD_15000_ACTIVATION_RECEIPT.json"
ACTIVATION_15000_SHA = "fbe6416d667def0dbf46976e0d7310f0d6dee1004c05c481c9cf2c043b243abf"
DISPATCH_ACTIVATION = ROOT / "outputs/family_dispatch_mode_binding_v1/CANONICAL_ACTIVATION_RECEIPT.json"
DISPATCH_ACTIVATION_SHA = "5e5a3d22b96b132da20d2a393d16a0013188a5efa5aef093267cdeb23eabc335"
SEMANTIC8_COHERENCE = ROOT / "outputs/qadd_tbvcd_semantic8_validator_coherence/CANONICAL_QADD_TBVCD_SEMANTIC8_VALIDATOR_COHERENCE_RECEIPT.json"
SEMANTIC8_COHERENCE_SHA = "9b7b5dc5beabff367aa502d56aa58b3def864b9bc400f987e2876e56839d8977"
DISPATCH_DIR = ROOT / "outputs/mainline_qadd_v74_mode_authority"
DISPATCH_BINDING = DISPATCH_DIR / "server_family_dispatch_mode_binding.json"
MODE_AUTHORITY = DISPATCH_DIR / "server_family_diagnostic_mode_authority.json"
V74_FAILURE = ROOT / "outputs/qlinearadd_node0007_v74_w15000_procfs_release/LOCAL_BUILD_FAILED_PATH_BUDGET.json"
V75_FAILURE = ROOT / "outputs/qadd_v75_w15k/LOCAL_BUILD_NOT_PUBLISHABLE_DISPATCH_IDENTITY_MISMATCH.json"
BUILD_FAILURE_AUDIT = ROOT / "outputs/qadd_v75_w15k/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"
V76_FAILURE = ROOT / "outputs/qadd_v76_w15k/LOCAL_BUILD_FAILED_STAGING_DISPATCH_FAMILY.json"
V77_FAILURE = ROOT / "outputs/qadd_v77_w15k/LOCAL_GATE_FAILURE_TBVCD_SEMANTIC8_VALIDATOR_DRIFT.json"
CANONICAL_GUARD = ROOT / "tools/server_observer_operational_guard_v2.py"
CANONICAL_GUARD_SHA = "e77e4bd32005f7621f0ece3be7e2c8c2d6d6f07162f72c740f15b0b49839703c"
OLD_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v73.svh"
NEW_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v74.svh"
OLD_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v73.py"
NEW_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v74.py"
OLD_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v73.py"
NEW_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v74.py"
ALLOW_QUALIFIED_PROGRESS_OBSERVER_DELTA = False
BUILD_FAILURE_AUDIT_SHA = "2923798f6b0613cdf50d87df482b228f8278f9c4a2936d9e3add364b594e3006"


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


def file_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def subtree(root: Path, ignored: set[str] | None = None) -> dict[str, str]:
    skip = ignored or set()
    return {
        path.relative_to(root).as_posix(): sha(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in skip
    }


def normalized_json(path: Path, package: str, version: str) -> Any:
    return json.loads(path.read_text(encoding="utf-8").replace(package, "<PACKAGE_ID>").replace(version, "vXX"))


def extract_source() -> Path:
    if OUT.exists():
        raise RuntimeError(f"fresh output exists: {OUT}")
    OUT.mkdir(parents=True)
    source_extract = OUT / "source_extract"
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("source ZIP CRC failure")
        for name in archive.namelist():
            parts = PurePosixPath(name).parts
            if not parts or parts[0] != OLD or any(part in {"", ".", ".."} for part in parts):
                raise RuntimeError(f"unsafe source ZIP member: {name}")
        archive.extractall(source_extract)
    source = source_extract / OLD
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
        changed = text.replace(OLD, NEW).replace("v73", VERSION).replace("V73", VERSION.upper()).replace("QAdd v73", f"QAdd {VERSION}")
        if changed != text:
            path.write_text(changed, encoding="utf-8", newline="\n")
    for path in sorted(TREE.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if "v73" in path.name:
            path.rename(path.with_name(path.name.replace("v73", VERSION)))
    for cache in sorted(TREE.rglob("__pycache__"), reverse=True):
        shutil.rmtree(cache)
    for path in TREE.rglob("*.pyc"):
        path.unlink()


def runtime_admission() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("server_runtime_budget_admission", ROOT / "tools/server_runtime_budget_admission.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("runtime budget admission tool unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    request = {
        "package_id": NEW,
        "execution_id": "BOUND_AT_FRESH_ATTEMPT",
        "mode": "MEASURED_PRETARGET_AWARE",
        "source_measurement": {
            "authorization_profile_id": "qadd-v73-target-progress-15000",
            "source_package_id": OLD,
            "source_return_path": SOURCE_RETURN.as_posix(),
            "source_return_sha256": SOURCE_RETURN_SHA,
            "source_formal_analysis_path": SOURCE_ANALYSIS.relative_to(ROOT).as_posix(),
            "source_formal_analysis_sha256": SOURCE_ANALYSIS_SHA,
            "qualified_progress_source": "TARGET_COMPLEMENTARY_PAIR_ACCEPT_CLEAR_OUTPUT",
            "measurement_phase": "TARGET",
            "qualified_units_completed": 12440,
            "total_pretarget_units": 18816,
            "elapsed_seconds": 2855.939969378058,
            "fixed_overhead_seconds": 5562.327059702948,
            "target_entry_observed": True,
            "progress_was_advancing": True,
        },
        "user_authorization": {
            "source_thread_id": "019ff027-e7db-72a3-b282-cfad8708da05",
            "exact_text": "qadd预算允许到15000秒确定跑完",
            "utf8_sha256": "60602079640071373a013309304df0d0e9099a2481a93dfe7953298ac3eb8d58",
            "family": "qlinearadd_node0007",
            "source_package_id": OLD,
            "source_return_sha256": SOURCE_RETURN_SHA,
            "selected_wall_ceiling_seconds": 15000,
            "authorization_scope": "EXACT_V73_MEASURED_RETURN_TO_ONE_NEXT_FRESH_QADD_SUCCESSOR",
        },
        "safety_factor": 1.25,
        "target_diagnostic_margin_seconds": 900,
        "selected_wall_ceiling_seconds": 15000,
        "absolute_maximum_wall_seconds": 86400,
        "independent_operational_guards": {
            "vcd_operational_budget_bytes": 8_000_000_000,
            "return_budget_bytes": 10_000_000_000,
            "disk_space_guard_enabled": True,
            "growth_projection_enabled": True,
            "write_failure_guard_enabled": True,
            "quota_guard_enabled": True,
            "signal_guard_enabled": True,
            "plateau_protection_unchanged": True,
            "return_integrity_fail_closed": True,
        },
    }
    receipt = module.calculate(request)
    if receipt.get("pass") is not True or receipt.get("selected_wall_ceiling_seconds") != 15000:
        raise RuntimeError(f"15000 runtime admission failed: {receipt.get('errors')}")
    if receipt.get("absolute_maximum_wall_seconds") != 86400:
        raise RuntimeError("runtime admission absolute maximum must remain 86400")
    if receipt.get("projection", {}).get("recommended_wall_ceiling_seconds") != 11862:
        raise RuntimeError("15000 runtime admission recommendation drifted")
    return receipt


def patch_supervisor() -> None:
    helper_target = TREE / "package_tools/server_observer_operational_guard_v2.py"
    shutil.copyfile(CANONICAL_GUARD, helper_target)
    path = TREE / NEW_LIVE
    text = path.read_text(encoding="utf-8")
    if text.count("WALL_SECONDS = 8400.0") != 1:
        raise RuntimeError("v73 wall anchor drifted")
    text = text.replace("WALL_SECONDS = 8400.0", "WALL_SECONDS = 15000.0", 1)
    start = text.index("def process_rows()")
    end = text.index("def scan_log(", start)
    procfs = '''def _load_procfs_helper() -> Any:
    helper_path = Path(__file__).with_name("server_observer_operational_guard_v2.py")
    spec = importlib.util.spec_from_file_location("qadd_procfs_identity_helper", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("canonical procfs identity helper unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PROCFS = _load_procfs_helper()


def process_rows() -> list[dict[str, Any]]:
    return _PROCFS.ps_table()


def remember(known: dict[int, int | None], row: dict[str, Any]) -> None:
    known[int(row["pid"])] = int(row["start_time_ticks"])


def _known_keys(known: dict[int, int | None]) -> set[tuple[int, int]]:
    return {(pid, int(start)) for pid, start in known.items() if isinstance(start, int)}


def _sync_known(known: dict[int, int | None], keys: set[tuple[int, int]]) -> None:
    known.clear()
    known.update({pid: start for pid, start in keys})


def owned(root_pid: int, pgid: int, known: dict[int, int | None]) -> list[dict[str, Any]]:
    keys = _known_keys(known)
    start = known.get(root_pid)
    root_identity = (root_pid, int(start)) if isinstance(start, int) else None
    rows = _PROCFS.owned_processes(root_identity, pgid, keys)
    for row in rows:
        keys.add(_PROCFS.process_key(row))
    _sync_known(known, keys)
    return rows


def signal_owned(root_pid: int, pgid: int, known: dict[int, int | None], number: int) -> dict[str, Any]:
    keys = _known_keys(known)
    start = known.get(root_pid)
    root_identity = (root_pid, int(start)) if isinstance(start, int) else None
    receipt = _PROCFS.signal_owned(root_identity, pgid, keys, number)
    _sync_known(known, keys)
    receipt["signal"] = number
    return receipt


def reap(deadline: float, known: dict[int, int | None]) -> list[int]:
    keys = _known_keys(known)
    result = _PROCFS.reap_adopted(keys, deadline)
    _sync_known(known, keys)
    return result


'''
    text = text[:start] + procfs + text[end:]
    process_anchor = '        "owned_pids_remaining": [row["pid"] for row in remaining],\n        "owned_process_identity": "PID_PLUS_PROC_START_TIME_TICKS",\n'
    process_replacement = process_anchor + '        "owned_process_identities_remaining": [{"pid": row["pid"], "start_time_ticks": row["start_time_ticks"]} for row in remaining],\n        "child_process_identity": {"pid": root_row["pid"], "start_time_ticks": root_row["start_time_ticks"]},\n        "process_identity_model": {"snapshot_backend": "PROCFS_NO_CHILD_ENUMERATOR", "identity_fields": ["pid", "start_time_ticks"], "pid_reuse_protection": True, "self_enumerator_child_process": False},\n'
    if text.count(process_anchor) != 1:
        raise RuntimeError("process identity receipt anchor drifted")
    path.write_text(text.replace(process_anchor, process_replacement, 1), encoding="utf-8", newline="\n")


def bind_contracts(source: Path) -> None:
    provenance = TREE / "provenance"
    copied = (
        (SOURCE_ANALYSIS, "v73_formal_return_analysis.json"),
        (SOURCE_FORMAL_RECEIPT, "v73_formal_mainline_receipt.json"),
        (SOURCE_RULE_AUDIT, "v73_RULE_GAP_AUDIT.json"),
        (SOURCE_PASS, "v73_published_pass_release_receipt.json"),
        (ACTIVATION_15000, "qadd_source_bound_wall_15000_activation_receipt.json"),
        (DISPATCH_ACTIVATION, "family_dispatch_mode_binding_activation_receipt.json"),
        (SEMANTIC8_COHERENCE, "qadd_tbvcd_semantic8_validator_coherence_receipt.json"),
        (source / "contracts/server_tb_vcd_bounded_causal_cone_contract.json", "v73_server_tb_vcd_bounded_causal_cone_contract.json"),
        (source / OLD_LIVE, "v73_tb_vcd_live_supervision.py"),
        (V74_FAILURE, "v74_local_build_failed_path_budget.json"),
        (V75_FAILURE, "v75_dispatch_identity_mismatch.json"),
        (BUILD_FAILURE_AUDIT, "PACKAGE_BUILD_FAILURE_RULE_AUDIT_V74_V75.json"),
        (V76_FAILURE, "v76_staging_dispatch_family_failure.json"),
        (V77_FAILURE, "v77_tbvcd_semantic8_gate_failure.json"),
    )
    for src, name in copied:
        shutil.copyfile(src, provenance / name)
    shutil.copyfile(DISPATCH_BINDING, TREE / "contracts/server_family_dispatch_mode_binding.json")
    shutil.copyfile(MODE_AUTHORITY, provenance / "server_family_diagnostic_mode_authority.json")
    admission_path = TREE / "diagnostics/runtime_budget_admission.json"
    write(admission_path, runtime_admission())
    process_contract = {
        "schema": "qadd-procfs-pid-start-time-reap-contract-v1",
        "package_id": NEW,
        "snapshot_backend": "PROCFS_NO_CHILD_ENUMERATOR",
        "identity_fields": ["pid", "start_time_ticks"],
        "pid_reuse_protection": True,
        "subprocess_ps_enumerator_forbidden": True,
        "deadline_origin": "FRESH_AFTER_LAST_KILL",
        "expired_deadline_reuse_forbidden": True,
        "stubborn_adopted_descendant_fail_closed": True,
        "canonical_helper_sha256": CANONICAL_GUARD_SHA,
        "pass": True,
        "errors": [],
    }
    write(TREE / "diagnostics/procfs_process_identity_reap_contract.json", process_contract)
    contract_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    contract = load(contract_path)
    signals = [row["signal_id"] for row in contract["signals"]]
    candidates = [row["candidate_id"] for row in contract["candidates"]]
    predecessor_copy = provenance / "v73_server_tb_vcd_bounded_causal_cone_contract.json"
    contract["package_id"] = NEW
    contract["diagnostic_round"]["round_index"] = 6
    contract["diagnostic_round"]["round_kind"] = "EVIDENCE_REFINED_SUCCESSOR"
    contract["diagnostic_round"]["evolution"] = {
        "predecessor": {
            "package_id": OLD,
            "round_index": 5,
            "contract_path": "provenance/v73_server_tb_vcd_bounded_causal_cone_contract.json",
            "contract_sha256": sha(predecessor_copy),
            "pinned_rtl_tree_sha256": contract["diagnostic_round"]["source_identity"]["pinned_rtl_tree_sha256"],
            "published_gate_semantic_version": "7",
            "published_pass_receipt_path": "provenance/v73_published_pass_release_receipt.json",
            "published_pass_receipt_sha256": sha(provenance / "v73_published_pass_release_receipt.json"),
        },
        "added_signal_ids": [], "removed_signal_ids": [], "unchanged_signal_ids": signals,
        "removal_evidence": [],
        "candidate_preservation": {"preserved_candidate_ids": candidates, "closed_candidate_ids": [], "new_candidate_ids": [], "closure_evidence": []},
    }
    contract["execution"].update({"tb_source_path": NEW_TB, "tb_source_sha256": sha(TREE / NEW_TB)})
    contract["budget"].update({
        "wall_ceiling_seconds": 15000,
        "runtime_budget_mode": "MEASURED_PRETARGET_AWARE",
        "absolute_maximum_wall_seconds": 86400,
        "runtime_budget_admission_path": "diagnostics/runtime_budget_admission.json",
        "runtime_budget_admission_sha256": sha(admission_path),
    })
    contract["runtime_policy"].update({"post_kill_reap_deadline_origin": "FRESH_AFTER_LAST_KILL", "stubborn_adopted_descendant_fail_closed": True})
    contract["claim_boundary"] = f"{VERSION} changes only exact v73-bound 15000-second admission plus canonical childless-procfs PID/start-time and fresh post-KILL reap/return reliability; validated 4/2/config/RTL/workload/numeric/golden/64-signal causal semantics remain frozen."
    write(contract_path, contract)

    additions = [
        {"source_root": "package", "source": "diagnostics/runtime_budget_admission.json", "archive": "source_package/runtime_budget_admission.json", "required": True},
        {"source_root": "package", "source": "diagnostics/procfs_process_identity_reap_contract.json", "archive": "source_package/procfs_process_identity_reap_contract.json", "required": True},
        {"source_root": "package", "source": "provenance/v73_formal_return_analysis.json", "archive": "source_package/v73_formal_return_analysis.json", "required": True},
        {"source_root": "package", "source": "provenance/v73_formal_mainline_receipt.json", "archive": "source_package/v73_formal_mainline_receipt.json", "required": True},
        {"source_root": "package", "source": "provenance/v73_RULE_GAP_AUDIT.json", "archive": "source_package/v73_RULE_GAP_AUDIT.json", "required": True},
        {"source_root": "package", "source": "provenance/qadd_source_bound_wall_15000_activation_receipt.json", "archive": "source_package/qadd_source_bound_wall_15000_activation_receipt.json", "required": True},
        {"source_root": "package", "source": "provenance/family_dispatch_mode_binding_activation_receipt.json", "archive": "source_package/family_dispatch_mode_binding_activation_receipt.json", "required": True},
        {"source_root": "package", "source": "provenance/qadd_tbvcd_semantic8_validator_coherence_receipt.json", "archive": "source_package/qadd_tbvcd_semantic8_validator_coherence_receipt.json", "required": True},
        {"source_root": "package", "source": "contracts/server_family_dispatch_mode_binding.json", "archive": "source_package/server_family_dispatch_mode_binding.json", "required": True},
        {"source_root": "package", "source": "provenance/v74_local_build_failed_path_budget.json", "archive": "source_package/v74_local_build_failed_path_budget.json", "required": True},
        {"source_root": "package", "source": "provenance/v75_dispatch_identity_mismatch.json", "archive": "source_package/v75_dispatch_identity_mismatch.json", "required": True},
        {"source_root": "package", "source": "provenance/v76_staging_dispatch_family_failure.json", "archive": "source_package/v76_staging_dispatch_family_failure.json", "required": True},
        {"source_root": "package", "source": "provenance/v77_tbvcd_semantic8_gate_failure.json", "archive": "source_package/v77_tbvcd_semantic8_gate_failure.json", "required": True},
        {"source_root": "package", "source": "provenance/PACKAGE_BUILD_FAILURE_RULE_AUDIT_V74_V75.json", "archive": "source_package/PACKAGE_BUILD_FAILURE_RULE_AUDIT_V74_V75.json", "required": True},
    ]
    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = load(request_path)
    request["package_id"] = NEW
    archives = {row["archive"] for row in request["core_entries"]}
    request["core_entries"].extend(row for row in additions if row["archive"] not in archives)
    write(request_path, request)
    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = load(allow_path)
    allow["package_id"] = NEW
    required = set(allow.get("required", []))
    for row in additions:
        required.update({row["archive"], f"{NEW}_return/{row['archive']}"})
    allow["required"] = sorted(required)
    write(allow_path, allow)


def staging_dispatch_preflight() -> Path:
    """Run the activated binding/selector/manifest conjunction before any ZIP exists."""
    binding = load(DISPATCH_BINDING)
    embedded = TREE / "contracts/server_family_dispatch_mode_binding.json"
    selector = load(TREE / "contracts/server_diagnostic_mode_selector.json")
    manifest = load(TREE / "TEST_PACKAGE_MANIFEST.json")
    checks = {
        "mainline_binding_package_id_exact": binding.get("package_id") == NEW,
        "embedded_binding_byte_exact": embedded.read_bytes() == DISPATCH_BINDING.read_bytes(),
        "selector_package_id_exact": selector.get("package_id") == NEW,
        "selector_mode_exact": selector.get("selected_mode") == "TB_VCD_BOUNDED_CAUSAL_CONE",
        "manifest_package_id_exact": manifest.get("package_id") == NEW,
        "manifest_mode_exact": manifest.get("diagnostic_mode") == "TB_VCD_BOUNDED_CAUSAL_CONE",
    }
    if not all(checks.values()):
        raise RuntimeError(f"pre-ZIP dispatch conjunction failed: {[key for key, ok in checks.items() if not ok]}")
    report = OUT / "gates/staging_dispatch_mode_binding_preflight.json"
    command = [
        sys.executable,
        str(ROOT / "tools/validate_server_family_dispatch_mode_binding.py"),
        "--binding", str(DISPATCH_BINDING),
        "--repo-root", str(ROOT),
        "--package-root", str(TREE),
        "--report", str(report),
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not report.is_file() or load(report).get("pass") is not True:
        raise RuntimeError(
            "pre-ZIP dispatch-mode validator failed: "
            + json.dumps({"exit": result.returncode, "stdout": result.stdout, "stderr": result.stderr}, ensure_ascii=False)
        )
    write(OUT / "gates/staging_dispatch_mode_binding_conjunction.json", {
        "schema": "qadd-pre-zip-dispatch-mode-conjunction-v1",
        "package_id": NEW,
        "checks": checks,
        "validator": identity(ROOT / "tools/validate_server_family_dispatch_mode_binding.py"),
        "schema_enabled_python": {"path": sys.executable, "version": sys.version.split()[0]},
        "binding": identity(DISPATCH_BINDING),
        "validator_report": identity(report),
        "zip_existed_when_checked": ZIP.exists() or REPEAT.exists(),
        "pass": True,
        "errors": [],
    })
    if load(OUT / "gates/staging_dispatch_mode_binding_conjunction.json")["zip_existed_when_checked"]:
        raise RuntimeError("pre-ZIP dispatch conjunction ran after ZIP creation")
    return report


def staging_tb_vcd_preflight() -> Path:
    """Run current semantic TB-VCD validation before deterministic ZIP creation."""
    report = OUT / "gates/staging_tb_vcd_semantic_preflight.json"
    command = [
        sys.executable,
        str(ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py"),
        "--contract", str(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"),
        "--root", str(TREE),
        "--output", str(report),
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not report.is_file() or load(report).get("pass") is not True:
        raise RuntimeError(
            "pre-ZIP TB-VCD semantic validator failed: "
            + json.dumps({"exit": result.returncode, "stdout": result.stdout, "stderr": result.stderr}, ensure_ascii=False)
        )
    if ZIP.exists() or REPEAT.exists():
        raise RuntimeError("pre-ZIP TB-VCD semantic gate ran after ZIP creation")
    return report


def refresh_identities() -> None:
    for name in ("server_tb_vcd_runtime_supervision.py", "server_tb_vcd_retention_analysis.py", "server_package_runtime_layout.py", "server_post_sim_return.py"):
        shutil.copyfile(ROOT / "tools" / name, TREE / "package_tools" / name)
    runner = TREE / "PREPARE_AND_RUN.sh"
    resilience_path = TREE / "contracts/server_runner_return_resilience_contract.json"
    resilience = load(resilience_path); resilience.update({"package_id": NEW, "runner_sha256": sha(runner)}); write(resilience_path, resilience)
    layout_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = load(layout_path); layout.update({"package_id": NEW, "install_name": NEW, "semantic_version": 5})
    projected = f"install/cfg_pkg/{NEW}/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin"
    projected_abs = layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(projected)
    layout["path_budget"]["max_projected_absolute_path_chars"] = projected_abs
    if isinstance(layout.get("runner_bindings"), dict): layout["runner_bindings"]["runner_sha256"] = sha(runner)
    write(layout_path, layout)
    request_path = TREE / "contracts/server_post_sim_return_request.json"
    post_path = TREE / "contracts/server_post_sim_return_contract.json"
    post = load(post_path); post.update({"package_id": NEW, "request_sha256": sha(request_path), "runner_sha256": sha(runner), "helper_sha256": sha(TREE / "package_tools/server_post_sim_return.py")}); write(post_path, post)
    contract_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    contract = load(contract_path); contract["execution"]["tb_source_sha256"] = sha(TREE / NEW_TB); write(contract_path, contract)
    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = load(selector_path); selector.update({"package_id": NEW, "family": "qlinearadd", "vcd_contract_sha256": sha(contract_path)})
    selector["return_members"] = sorted(set(selector.get("return_members", [])) | {
        "source_package/runtime_budget_admission.json", "source_package/procfs_process_identity_reap_contract.json",
        "source_package/v73_formal_return_analysis.json", "source_package/v73_formal_mainline_receipt.json",
        "source_package/v73_RULE_GAP_AUDIT.json", "source_package/qadd_source_bound_wall_15000_activation_receipt.json",
        "source_package/family_dispatch_mode_binding_activation_receipt.json", "source_package/server_family_dispatch_mode_binding.json",
    })
    selector["package_members"] = sorted(path.relative_to(TREE).as_posix() for path in TREE.rglob("*") if path.is_file())
    write(selector_path, selector)
    manifest_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = load(manifest_path)
    manifest.update({
        "package_id": NEW, "package_identity": NEW, "install_name": NEW, "activation_epoch": EPOCH,
        "status": "PACKAGE_READY_NOT_RUN", "diagnostic_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "previous_version_progress": "v73 dynamically validated exact 4/2 ordered complementary accept/clear/read-output for 12440/18816 pairs; the authorized 8400-second wall stopped while target progress remained live.",
        "current_version_purpose": "Keep the exact v73 functional and causal surface frozen; select the exact user-authorized 15000-second wall and replace only process ownership/reap/return transport with canonical childless-procfs PID plus start-time.",
        "runtime_budget_admission": "diagnostics/runtime_budget_admission.json",
        "post_kill_reap_contract": "diagnostics/procfs_process_identity_reap_contract.json",
        "gate_semantic_versions": {"tb_vcd_bounded_causal_cone_final_zip": 8, "first_fresh_extra_audit": 6, "runtime_layout": 5, "family_dispatch_mode_binding_final_zip": 1},
        "diagnostic_mode_selector_sha256": sha(selector_path),
    })
    manifest["path_length_budget"]["longest_projected_relative_path"] = projected
    manifest["path_length_budget"]["longest_projected_relative_path_chars"] = len(projected)
    manifest["path_length_budget"]["max_projected_absolute_path_chars"] = projected_abs
    manifest["files"] = file_map(TREE); write(manifest_path, manifest)
    selector = load(selector_path); selector["package_members"] = sorted(path.relative_to(TREE).as_posix() for path in TREE.rglob("*") if path.is_file()); write(selector_path, selector)
    manifest = load(manifest_path); manifest["diagnostic_mode_selector_sha256"] = sha(selector_path); manifest["files"] = file_map(TREE); write(manifest_path, manifest)


def deterministic_zip(target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        for path in sorted(TREE.rglob("*")):
            if not path.is_file(): continue
            info = zipfile.ZipInfo(f"{NEW}/{path.relative_to(TREE).as_posix()}", (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = (0o755 if path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py" else 0o644) << 16; info.create_system = 3
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=1)


def main() -> int:
    exact = ((SOURCE_ZIP, SOURCE_ZIP_SHA), (SOURCE_RETURN, SOURCE_RETURN_SHA), (SOURCE_ANALYSIS, SOURCE_ANALYSIS_SHA), (SOURCE_PASS, SOURCE_PASS_SHA), (ACTIVATION_15000, ACTIVATION_15000_SHA), (DISPATCH_ACTIVATION, DISPATCH_ACTIVATION_SHA), (SEMANTIC8_COHERENCE, SEMANTIC8_COHERENCE_SHA), (CANONICAL_GUARD, CANONICAL_GUARD_SHA), (V74_FAILURE, "c0c20715e83cfc29fb3d03c0a482f0c9fbdc70d5f25a4fd64ee96184eec4a38d"), (V75_FAILURE, "307f53011979d62a53fa66ff7a7e7c3fa6ce56d0c7bac2083704ebe03c4a1e4d"), (BUILD_FAILURE_AUDIT, BUILD_FAILURE_AUDIT_SHA), (V76_FAILURE, "222e8090e5d04ecc3131e1121617ce039960af747be5015c73cc71802520c033"), (V77_FAILURE, "d85daee1cfebb1caadc3a87bcfc24309ae5559e6172cebbd20305f95d8454300"))
    for path, expected in exact:
        if not path.is_file() or sha(path) != expected: raise RuntimeError(f"exact input absent or drifted: {path}")
    for path in (DISPATCH_BINDING, MODE_AUTHORITY):
        if not path.is_file(): raise RuntimeError(f"mainline dispatch binding absent: {path}")
    source = extract_source()
    validation = subtree(source / "validation")
    workload = subtree(source / "workload", {"runtime/sca_cfg.json", "runtime/sca_cfg_D.json"})
    bitstream = sha(source / "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin")
    catalog = normalized_json(source / "diagnostics/tb_vcd_signal_catalog.json", OLD, "v73")
    matrix = normalized_json(source / "diagnostics/tb_vcd_candidate_matrix.json", OLD, "v73")
    tb = (source / OLD_TB).read_text(encoding="utf-8").replace(OLD, "<PACKAGE_ID>").replace("v73", "vXX")
    fresh_identity(); patch_supervisor(); bind_contracts(source); refresh_identities()
    contract = load(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    checks = {
        "source_v73_byte_frozen": sha(SOURCE_ZIP) == SOURCE_ZIP_SHA,
        "config42_bitstream_exact": sha(TREE / "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin") == bitstream == "a7d42a980945cbfa7292b6e41140f57d51125b242ac302b2602a52651fb2be0f",
        "validation_payload_exact": subtree(TREE / "validation") == validation,
        "workload_payload_exact_except_identity_sca": subtree(TREE / "workload", {"runtime/sca_cfg.json", "runtime/sca_cfg_D.json"}) == workload,
        "catalog_exact_except_identity": normalized_json(TREE / "diagnostics/tb_vcd_signal_catalog.json", NEW, VERSION) == catalog,
        "matrix_exact_except_identity": normalized_json(TREE / "diagnostics/tb_vcd_candidate_matrix.json", NEW, VERSION) == matrix,
        "tb_exact_except_identity_or_qualified_progress_only": (
            (TREE / NEW_TB).read_text(encoding="utf-8").replace(NEW, "<PACKAGE_ID>").replace(VERSION, "vXX") == tb
            or ALLOW_QUALIFIED_PROGRESS_OBSERVER_DELTA
        ),
        "signal_count_64": len(contract["signals"]) == 64,
        "functional_rtl_absent": not (TREE / "rtl").exists(),
        "wall_15000_exact": contract["budget"]["wall_ceiling_seconds"] == 15000,
        "canonical_procfs_helper_exact": sha(TREE / "package_tools/server_observer_operational_guard_v2.py") == CANONICAL_GUARD_SHA,
    }
    frozen = {"schema": "qadd-v74-frozen-surface-v1", "package_id": NEW, "checks": checks, "changed_surfaces": ["fresh_identity", "exact_v73_bound_wall_15000_admission", "canonical_childless_procfs_pid_start_time", "fresh_post_kill_reap_and_return_transport", "dispatch_mode_binding"], "frozen": ["validated_config42", "bitstream", "functional_rtl", "workload", "numeric", "golden", "64_signal_cone", "candidate_matrix", "target_terminal_formal_d_predicates"], "pass": all(checks.values()), "errors": [key for key, ok in checks.items() if not ok], "storage_manager_called": False, "server_actions_performed": []}
    write(OUT / "frozen_surface_receipt.json", frozen)
    if not frozen["pass"]: raise RuntimeError(f"frozen surface drift: {frozen['errors']}")
    staging_dispatch_report = staging_dispatch_preflight()
    staging_tb_vcd_report = staging_tb_vcd_preflight()
    deterministic_zip(ZIP); deterministic_zip(REPEAT)
    if ZIP.read_bytes() != REPEAT.read_bytes(): raise RuntimeError("deterministic ZIP mismatch")
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None: raise RuntimeError("ZIP CRC failure")
    receipt = {"schema": "qadd-v74-w15000-procfs-build-v1", "role_id": "family.qlinearadd", "owner_epoch": 2, "registry_epoch": 6, "package_id": NEW, "activation_epoch": EPOCH, "source_v73": identity(SOURCE_ZIP), "source_return": identity(SOURCE_RETURN), "source_analysis": identity(SOURCE_ANALYSIS), "runtime_admission": identity(TREE / "diagnostics/runtime_budget_admission.json"), "activation_15000": identity(ACTIVATION_15000), "dispatch_activation": identity(DISPATCH_ACTIVATION), "staging_dispatch_preflight": identity(staging_dispatch_report), "staging_tb_vcd_preflight": identity(staging_tb_vcd_report), "package_build_failure_rule_audit": identity(BUILD_FAILURE_AUDIT), "package": identity(ZIP), "repeat_package": identity(REPEAT), "deterministic_recompute": True, "status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES", "pass": True, "errors": [], "storage_manager_called": False, "server_actions_performed": [], "claim_boundary": "Local fresh construction only; production compile/simulation, terminal, Formal-D and E3-E5 remain unproven."}
    write(OUT / "build_receipt.json", receipt)
    print(json.dumps({"package_id": NEW, "package": str(ZIP), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
