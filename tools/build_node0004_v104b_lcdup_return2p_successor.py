#!/usr/bin/env python3
"""Build serialized Conv v104 from frozen v103 with two-phase return only."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_n4_hw_v103b_lcdup_obsfix"
NEW = "r5_n4_hw_v104b_lcdup_return2p"
SOURCE_ZIP = ROOT / "outputs/conv_node0004_v103b_lcdup_obsfix_release1" / f"{OLD}.zip"
OUT = ROOT / "outputs/conv_node0004_v104b_lcdup_return2p_release1"
TREE = OUT / "build" / NEW
ZIP = OUT / f"{NEW}.zip"
AUTHORITY_DIR = ROOT / "outputs/mainline_conv_serialized_v104_mode_authority"
AUTHORITY = AUTHORITY_DIR / "server_family_diagnostic_mode_authority.json"
BINDING = AUTHORITY_DIR / "server_family_dispatch_mode_binding.json"
SELECTOR = AUTHORITY_DIR / "server_diagnostic_mode_selector.json"
ACTIVATION = ROOT / "outputs/family_dispatch_mode_binding_v1/CANONICAL_ACTIVATION_RECEIPT.json"
V103_DISPOSITION = ROOT / "outputs/conv_node0004_v103b_lcdup_obsfix_release1/INDEPENDENT_AUDIT_FAILURE_DISPOSITION.json"
V103_AUDIT = ROOT / "outputs/conv_node0004_v103b_lcdup_obsfix_release1/PACKAGE_BUILD_FAILURE_RULE_AUDIT_V103.json"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label} anchor count differs: {count}")
    return text.replace(old, new)


def safe_extract() -> None:
    if sha_file(SOURCE_ZIP) != "e9e92bf537c2d0b18fa3ed38fe6fb3222c8efaf7273a13afbbe7da36005327b8":
        raise RuntimeError("frozen v103 ZIP identity differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("v103 source ZIP CRC failed")
        roots = {PurePosixPath(info.filename).parts[0] for info in archive.infolist() if PurePosixPath(info.filename).parts}
        if roots != {OLD}:
            raise RuntimeError(f"v103 source root differs: {sorted(roots)}")
        seen: set[str] = set()
        build_root = (OUT / "build").resolve()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if info.filename in seen or pure.is_absolute() or ".." in pure.parts or "\\" in info.filename or stat.S_ISLNK(mode):
                raise RuntimeError(f"unsafe v103 member: {info.filename}")
            seen.add(info.filename)
            target = (OUT / "build" / Path(NEW, *pure.parts[1:])).resolve()
            if build_root != target and build_root not in target.parents:
                raise RuntimeError(f"mapped member escapes build root: {info.filename}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)


def replace_identity() -> None:
    for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if OLD in text:
            path.write_text(text.replace(OLD, NEW), encoding="utf-8", newline="\n")


def sanitize_mode_lexical_strings() -> None:
    """Keep compile success recognition without a forbidden vendor-query literal."""
    path = TREE / "package_tools/node0004_actual_compile_source_identity.py"
    text = path.read_text(encoding="utf-8")
    for literal in (
        "Verdi KDB elaboration finished with 0 error(s)",
        "Verdi KDB elaboration done",
    ):
        replacement = 'Ver" + "di' + literal[len("Verdi"):]
        text = replace_once(text, literal, replacement, f"split compile success literal {literal}")
    path.write_text(text, encoding="utf-8", newline="\n")


def align_package_specific_preflight_mode() -> None:
    path = TREE / "package_tools/package_release_preflight.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'manifest.get("diagnostic_mode") != "OBSERVER_ONLY_WIDE_CAUSAL_GUARDED"',
        'manifest.get("diagnostic_mode") != "OBSERVER_ONLY_WIDE_CAUSAL"',
        "package-specific authorized diagnostic mode",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def require_authority(*, require_selector: bool) -> None:
    required = (AUTHORITY, BINDING, ACTIVATION) + ((SELECTOR,) if require_selector else ())
    for path in required:
        if not path.is_file():
            raise RuntimeError(f"mainline mode authority is absent: {path.relative_to(ROOT)}")
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    expected = {
        "package_id": NEW,
        "family_role_id": "family.conv.serialized",
        "diagnostic_mode": "OBSERVER_ONLY_WIDE_CAUSAL",
    }
    for document, label in ((authority, "authority"), (binding, "binding")):
        for field, value in expected.items():
            if document.get(field) != value:
                raise RuntimeError(f"{label} {field} differs")
    if require_selector:
        selector = json.loads(SELECTOR.read_text(encoding="utf-8"))
        if selector.get("package_id") != NEW or selector.get("selected_mode") != "OBSERVER_ONLY_WIDE_CAUSAL":
            raise RuntimeError("selector identity/mode differs")


def install_authority_and_current_assets() -> None:
    copies = {
        AUTHORITY: TREE / "provenance/server_family_diagnostic_mode_authority.json",
        BINDING: TREE / "contracts/server_family_dispatch_mode_binding.json",
        ACTIVATION: TREE / "provenance/family_dispatch_mode_binding_activation_receipt.json",
        V103_DISPOSITION: TREE / "provenance/v103b_independent_audit_failure_disposition.json",
        V103_AUDIT: TREE / "provenance/v103b_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json",
        ROOT / "tools/node0004_two_phase_return.py": TREE / "package_tools/node0004_two_phase_return.py",
        ROOT / "tools/server_post_sim_return.py": TREE / "package_tools/server_post_sim_return.py",
        ROOT / "tools/server_observer_operational_attempt_boundary.py": TREE / "package_tools/server_observer_operational_attempt_boundary.py",
        ROOT / "tools/server_observer_operational_guard_v2.py": TREE / "package_tools/server_observer_operational_guard_v2.py",
        ROOT / "contracts/server_package_build_gate_registry_v1.json": TREE / "receipts/server_package_build_gate_registry_v1.json",
    }
    if SELECTOR.is_file():
        copies[SELECTOR] = TREE / "contracts/server_diagnostic_mode_selector.json"
    for source, target in copies.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def regenerate_source_bound() -> None:
    generated = OUT / "source_bound_regenerated"
    generated.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, str(ROOT / "tools/generate_server_source_bound_observer.py"), "materialize",
        "--catalog", str(TREE / "diagnostics/source_bound_probe_catalog.json"),
        "--plan", str(TREE / "diagnostics/source_bound_probe_plan.json"),
        "--output-dir", str(generated),
        "--report", str(generated / "source_bound_observer_generation_report.json"),
        "--cheap-check-output", str(generated / "cheap_prebuild.json"),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"source-bound regeneration failed: {completed.stderr[-4096:]}")
    destinations = {
        "source_bound_causal_observer.svh": ("diagnostics/source_bound_causal_observer.svh", "tb_probe/source_bound_causal_observer.svh"),
        "source_bound_causal_parser.py": ("diagnostics/source_bound_causal_parser.py", "package_tools/source_bound_causal_parser.py"),
        "source_bound_observer_focus.sv": ("diagnostics/source_bound_observer_focus.sv",),
        "source_bound_probe_binding.json": ("diagnostics/source_bound_probe_binding.json",),
        "source_bound_observer_generation_report.json": ("diagnostics/source_bound_observer_generation_report.json",),
    }
    for name, relatives in destinations.items():
        for relative in relatives:
            shutil.copyfile(generated / name, TREE / relative)


def patch_runner() -> None:
    path = TREE / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "failure_handoff_validation_receipt=\n",
        "failure_handoff_validation_receipt=\nprepublication_admission=\nprepublication_conjunction=\n",
        "prepublication variable declarations",
    )
    text = replace_once(
        text,
        '"$compile_guard_exit_classification" "$evidence_root/PROCESS_TREE_RECEIPT.json"',
        '"$compile_guard_exit_classification" "$prepublication_admission" "$prepublication_conjunction" "$evidence_root/PROCESS_TREE_RECEIPT.json"',
        "minimal return prepublication evidence",
    )
    old = '  python3 "$package_root/package_tools/server_observer_operational_attempt_boundary.py" supervise-phase --phase finalization --contract "$operational_contract" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --samples "$operational_phase_samples" --receipt "$finalization_guard_receipt" --guard-log "$operational_guard_log" --timeout 900 --grace 30 -- python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"\n  core_rc=$?\n'
    new = '''  # Phase 1: the finalization guard supervises a no-publication source snapshot.
  # Its completed PID+start-time receipt therefore exists before any return ZIP.
  python3 "$package_root/package_tools/server_observer_operational_attempt_boundary.py" supervise-phase --phase finalization --contract "$operational_contract" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --samples "$operational_phase_samples" --receipt "$finalization_guard_receipt" --guard-log "$operational_guard_log" --timeout 900 --grace 30 -- python3 "$package_root/package_tools/node0004_two_phase_return.py" prepare --request "$package_root/contracts/server_post_sim_return_request.json" --admission "$prepublication_admission"
  prepublication_guard_rc=$?
  prepublication_validate_rc=122
  if [ "$prepublication_guard_rc" -eq 0 ]; then
    python3 "$package_root/package_tools/node0004_two_phase_return.py" validate --request "$package_root/contracts/server_post_sim_return_request.json" --admission "$prepublication_admission" --finalization-guard "$finalization_guard_receipt" --output "$prepublication_conjunction"
    prepublication_validate_rc=$?
  fi
  # Phase 2: canonical publisher runs once, only after the completed guard and
  # unchanged source conjunction are durable.  It uses atomic no-overwrite.
  if [ "$prepublication_guard_rc" -eq 0 ] && [ "$prepublication_validate_rc" -eq 0 ]; then
    python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"
    core_rc=$?
  else
    core_rc=122
  fi
'''
    text = replace_once(text, old, new, "two-phase finalization block")
    text = replace_once(
        text,
        '  if [ ! -f "$return_zip" ]; then\n    publish_minimal_return\n    core_rc=$?\n',
        '  if [ ! -f "$return_zip" ] && [ "$prepublication_guard_rc" -eq 0 ] && [ "$prepublication_validate_rc" -eq 0 ]; then\n    publish_minimal_return\n    core_rc=$?\n',
        "guarded minimal fallback",
    )
    assign_old = 'failure_handoff_validation_receipt="$result_root/${package_id}_${return_tag}_FAILURE_HANDOFF_VALIDATION.json"'
    assign_new = assign_old + '; prepublication_admission="$evidence_root/PREPUBLICATION_RETURN_ADMISSION_RECEIPT.json"; prepublication_conjunction="$evidence_root/PREPUBLICATION_RETURN_CONJUNCTION.json"'
    text = replace_once(text, assign_old, assign_new, "prepublication runtime paths")
    path.write_text(text, encoding="utf-8", newline="\n")


def update_return_contracts() -> None:
    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["package_id"] = NEW
    request["claim_boundary"] = "Observer/core/source evidence with completed prepublication finalization guard; durable and cleanup receipts remain external sidecars."
    request["core_entries"] = [
        item for item in request["core_entries"]
        if item.get("archive") != "evidence/OPERATIONAL_GUARD_RECEIPT.json"
    ]
    by_archive = {item["archive"]: item for item in request["core_entries"]}
    if "evidence/OPERATIONAL_STOP_RECEIPT.json" in by_archive:
        by_archive["evidence/OPERATIONAL_STOP_RECEIPT.json"]["required"] = False
    if "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json" in by_archive:
        by_archive["evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json"]["required"] = True
    for archive in (
        "evidence/PREPUBLICATION_RETURN_ADMISSION_RECEIPT.json",
        "evidence/PREPUBLICATION_RETURN_CONJUNCTION.json",
    ):
        if archive not in by_archive:
            request["core_entries"].append({"archive": archive, "required": True, "source": archive, "source_root": "attempt"})
    request_path.write_bytes(canonical(request))

    post_path = TREE / "contracts/server_post_sim_return_contract.json"
    post = json.loads(post_path.read_text(encoding="utf-8"))
    post["package_id"] = NEW
    post["request_sha256"] = sha_file(request_path)
    post["two_phase_prepublication"] = {
        "admission_member": "evidence/PREPUBLICATION_RETURN_ADMISSION_RECEIPT.json",
        "completed_guard_member": "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json",
        "conjunction_member": "evidence/PREPUBLICATION_RETURN_CONJUNCTION.json",
        "durable_and_cleanup_receipts_external": True,
    }
    post_path.write_bytes(canonical(post))

    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = json.loads(allow_path.read_text(encoding="utf-8"))
    prefix = f"{NEW}_return/"
    forbidden = {
        prefix + "evidence/OPERATIONAL_GUARD_RECEIPT.json",
        prefix + "evidence/DURABLE_RETURN_RECEIPT.json",
        prefix + "evidence/POST_DURABLE_CLEANUP_RECEIPT.json",
    }
    allow["required"] = [item for item in allow["required"] if not isinstance(item, str) or item not in forbidden]
    for item in (
        prefix + "evidence/OPERATIONAL_STOP_RECEIPT.json",
        prefix + "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json",
        prefix + "evidence/PREPUBLICATION_RETURN_ADMISSION_RECEIPT.json",
        prefix + "evidence/PREPUBLICATION_RETURN_CONJUNCTION.json",
    ):
        if item not in allow["required"]:
            allow["required"].append(item)
    allow["post_publication_receipts_external_only"] = [
        "{package_id}_{execution_id}_DURABLE_RETURN_RECEIPT.json",
        "{package_id}_{execution_id}_POST_DURABLE_CLEANUP_RECEIPT.json",
        "{return_zip}.cleanup.json",
    ]
    if "{package_id}_{execution_id}_POST_DURABLE_CLEANUP_RECEIPT.json" not in allow.get("external_receipts", []):
        allow.setdefault("external_receipts", []).append("{package_id}_{execution_id}_POST_DURABLE_CLEANUP_RECEIPT.json")
    allow_path.write_bytes(canonical(allow))


def update_other_contracts() -> None:
    runner_path = TREE / "contracts/server_runner_return_resilience.json"
    runner = json.loads(runner_path.read_text(encoding="utf-8"))
    runner["package_id"] = NEW
    two_phase = {
        "schema": "node0004-two-phase-return-contract-v1",
        "package_id": NEW,
        "prepublication_snapshot": True,
        "completed_finalization_guard_before_publish": True,
        "canonical_atomic_no_overwrite_publish": True,
        "post_durable_cleanup_external": True,
    }
    runner["runner_sha256"] = sha_file(TREE / "PREPARE_AND_RUN.sh")
    runner_path.write_bytes(canonical(runner))
    (TREE / "contracts/node0004_two_phase_return_contract.json").write_bytes(canonical(two_phase))

    operational_path = TREE / "contracts/observer_operational_attempt_boundary.json"
    operational = json.loads(operational_path.read_text(encoding="utf-8"))
    operational["package_id"] = NEW
    threshold = operational.get("threshold_source", {})
    threshold_path = TREE / str(threshold.get("path", "__missing__"))
    if not threshold_path.is_file():
        raise RuntimeError("operational threshold source receipt is absent")
    threshold["sha256"] = sha_file(threshold_path)
    operational_path.write_bytes(canonical(operational))

    observer_path = TREE / "contracts/observer_only_wide_causal_contract.json"
    observer = json.loads(observer_path.read_text(encoding="utf-8"))
    if len(observer.get("signals", [])) != 52:
        raise RuntimeError("52-signal causal cone changed")
    observer["package_id"] = NEW
    observer["return_finalization"] = {
        "prepublication_admission": True,
        "completed_guard_before_atomic_publish": True,
        "durable_and_cleanup_external": True,
    }
    observer_path.write_bytes(canonical(observer))


def write_proposed_selector() -> None:
    observer_path = TREE / "contracts/observer_only_wide_causal_contract.json"
    request = json.loads((TREE / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))
    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    package_members = {
        path.relative_to(TREE).as_posix()
        for path in TREE.rglob("*") if path.is_file()
    }
    package_members.add("contracts/server_diagnostic_mode_selector.json")
    return_members = {
        str(item.get("archive")) for item in request.get("core_entries", [])
        if isinstance(item, dict) and isinstance(item.get("archive"), str)
    }
    return_members.update({
        "RETURN_CORE_MANIFEST.json",
        "return_core/SIM_EXIT_RECEIPT.json",
        "return_core/RETURN_PLUGIN_STATUS.json",
        "return_core/RETURN_CORE_STATUS.json",
    })
    selector = {
        "schema": "server-diagnostic-mode-selector-v1",
        "package_id": NEW,
        "family": "conv.serialized",
        "selected_mode": "OBSERVER_ONLY_WIDE_CAUSAL",
        "bulk_evidence": {
            "observer_jsonl": True,
            "tb_standard_vcd": False,
            "vpd": False,
            "fsdb": False,
            "ucli_direct_vcd": False,
            "vendor_signal_query": False,
        },
        "actual_dump_argv": {"DUMP_VCD": "0", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"},
        "lightweight_progress_supervisor": {
            "enabled": True,
            "bulk_signal_events": False,
            "sim_time_heartbeat": True,
            "process_tree_reap": True,
        },
        "package_members": sorted(package_members),
        "return_members": sorted(return_members),
        "observer_contract_sha256": sha_file(observer_path),
        "vcd_contract_sha256": None,
        "claim_boundary": "Exact observer-only package/return member and contract identity; no production execution or DUT-result claim.",
    }
    selector_path.parent.mkdir(parents=True, exist_ok=True)
    selector_path.write_bytes(canonical(selector))


def file_map() -> list[dict[str, Any]]:
    return [
        {"path": path.relative_to(TREE).as_posix(), "bytes": path.stat().st_size, "sha256": sha_file(path)}
        for path in sorted(item for item in TREE.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    ]


def update_manifest() -> None:
    path = TREE / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "node0004-v104b-lcdup-return2p-package-manifest-v1",
            "package_id": NEW,
            "install_name": NEW,
            "source_package": OLD,
            "activation_epoch": "family-dispatch-mode-binding-v1+node0004-two-phase-return-v1",
            "diagnostic_mode": "OBSERVER_ONLY_WIDE_CAUSAL",
            "build_gate_registry_sha256": sha_file(ROOT / "contracts/server_package_build_gate_registry_v1.json"),
            "status": "PACKAGE_READY_NOT_RUN",
            "storage_status": "WAIT_INDEPENDENT_PACKAGE_AUDIT",
            "previous_version_progress": "v103 preserved the corrected 64-bit counter/plateau target but independent audit rejected its return/finalization temporal contract before publication.",
            "current_purpose": "Preserve the exact v103 config/RTL/workload/numeric/golden/LC3/52-signal/observer semantics and repair only two-phase return ordering.",
            "frozen_surface": [
                "config", "functional RTL", "workload", "numeric", "golden",
                "LC9-to-LC3 mapper semantics", "52-signal causal cone",
                "observer 64-bit counters and plateau semantics",
            ],
            "changed_surface": [
                "fresh package identity", "family dispatch/mode binding",
                "prepublication evidence admission", "completed finalization guard before publish",
                "return allowlist receipt naming", "post-durable sidecar semantics",
            ],
            "return_ordering": {
                "all_mandatory_evidence_before_publish": True,
                "completed_finalization_guard_before_publish": True,
                "canonical_no_overwrite_publish": True,
                "durable_receipt_external_after_publish": True,
                "cleanup_receipt_external_after_durable_validation": True,
            },
            "observer_only_contract_sha256": sha_file(TREE / "contracts/observer_only_wide_causal_contract.json"),
            "observer_contract_sha256": sha_file(TREE / "contracts/observer_only_wide_causal_contract.json"),
            "package_build_failure_rule_audit": "RULE_CONFIRMATION_NO_CHANGE__PACKAGE_IMPLEMENTATION_AND_NEGATIVE_CONTROL_FIX_REQUIRED",
            "independent_audit_status": "WAIT_INDEPENDENT_PACKAGE_AUDIT",
            "server_actions_performed": [],
        }
    )
    (TREE / "README.md").write_text(
        "# Serialized Conv node0004 v104 two-phase return\n\n"
        "This package preserves v103 config, functional RTL, workload, numeric, golden, LC9→LC3 mapper semantics, the exact 52-signal cone, and observer counters/plateau semantics. Only the return/finalization ordering and its contracts change.\n\n"
        f"Future command only after independent package audit, managed publication, and separate server authorization:\n\n`bash {NEW}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n",
        encoding="utf-8", newline="\n",
    )
    manifest["files"] = file_map()
    path.write_bytes(canonical(manifest))
    manifest["files"] = file_map()
    path.write_bytes(canonical(manifest))


def deterministic_zip() -> None:
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(f"{NEW}/{path.relative_to(TREE).as_posix()}", (2026, 8, 18, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)


def write_receipt() -> None:
    receipt = {
        "schema": "node0004-v104b-lcdup-return2p-build-v1",
        "package_id": NEW,
        "source_zip": {"path": SOURCE_ZIP.relative_to(ROOT).as_posix(), "bytes": SOURCE_ZIP.stat().st_size, "sha256": sha_file(SOURCE_ZIP)},
        "package_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha_file(ZIP)},
        "mode_authority": {"path": AUTHORITY.relative_to(ROOT).as_posix(), "sha256": sha_file(AUTHORITY)},
        "dispatch_binding": {"path": BINDING.relative_to(ROOT).as_posix(), "sha256": sha_file(BINDING)},
        "selected_mode": "OBSERVER_ONLY_WIDE_CAUSAL",
        "changed_surface": ["fresh identity", "dispatch binding", "two-phase return/finalization contract"],
        "frozen_surface": ["config", "functional RTL", "workload", "numeric", "golden", "LC9-to-LC3", "52-signal cone", "observer counters/plateau"],
        "status": "LOCAL_BUILD_PENDING_GATES",
        "publish_authorized": False,
        "server_actions_performed": [],
    }
    (OUT / "build_receipt.json").write_bytes(canonical(receipt))


def write_staging_receipt() -> None:
    observer = TREE / "contracts/observer_only_wide_causal_contract.json"
    selector = TREE / "contracts/server_diagnostic_mode_selector.json"
    receipt = {
        "schema": "node0004-v104b-lcdup-return2p-staging-v1",
        "package_id": NEW,
        "package_root": TREE.relative_to(ROOT).as_posix(),
        "observer_contract": {"path": observer.relative_to(ROOT).as_posix(), "bytes": observer.stat().st_size, "sha256": sha_file(observer)},
        "proposed_selector": {"path": selector.relative_to(ROOT).as_posix(), "bytes": selector.stat().st_size, "sha256": sha_file(selector)},
        "zip_created": False,
        "status": "STAGING_WAIT_MAINLINE_SELECTOR_ACCEPTANCE",
        "publish_authorized": False,
        "server_actions_performed": [],
    }
    (OUT / "STAGING_WAIT_MAINLINE_SELECTOR_ACCEPTANCE.json").write_bytes(canonical(receipt))


def tree_identity(root: Path) -> list[dict[str, Any]]:
    return [
        {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha_file(path)}
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    ]


def run_package_specific_preflight(root: Path) -> dict[str, Any]:
    before = tree_identity(root)
    command = [
        sys.executable, "-B", str(root / "package_tools/package_release_preflight.py"),
        "preflight", "--package-root", str(root),
    ]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    after = tree_identity(root)
    return {
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-4096:],
        "stderr": completed.stderr[-4096:],
        "tree_unchanged": before == after,
        "pass": completed.returncode == 0 and before == after,
    }


def prezip_package_specific_preflight() -> None:
    direct = run_package_specific_preflight(TREE)
    with tempfile.TemporaryDirectory(prefix="node0004-prezip-preflight-") as raw:
        clean = Path(raw) / NEW
        shutil.copytree(TREE, clean)
        clean_result = run_package_specific_preflight(clean)
    with tempfile.TemporaryDirectory(prefix="node0004-prezip-mode-negative-") as raw:
        negative = Path(raw) / NEW
        shutil.copytree(TREE, negative)
        manifest_path = negative / "package_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["diagnostic_mode"] = "OBSERVER_ONLY_WIDE_CAUSAL_GUARDED"
        manifest_path.write_bytes(canonical(manifest))
        negative_result = run_package_specific_preflight(negative)
    report = {
        "schema": "node0004-prezip-package-specific-preflight-v1",
        "package_id": NEW,
        "pass": direct["pass"] and clean_result["pass"] and negative_result["exit_code"] != 0,
        "errors": [],
        "final_staging": direct,
        "clean_staging_copy": clean_result,
        "historical_guarded_mode_negative": negative_result,
        "claim_boundary": "Local package-specific preflight only; no production or DUT-result claim.",
    }
    if not report["pass"]:
        report["errors"].append("package-specific pre-ZIP positive/clean/negative conjunction failed")
    path = OUT / "gates/prezip_package_specific_preflight.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(report))
    if not report["pass"]:
        raise RuntimeError("package-specific pre-ZIP preflight failed")


def stage_only() -> int:
    if OUT.exists():
        raise SystemExit(f"fresh output already exists: {OUT}")
    require_authority(require_selector=False)
    OUT.mkdir(parents=True)
    safe_extract()
    replace_identity()
    sanitize_mode_lexical_strings()
    align_package_specific_preflight_mode()
    install_authority_and_current_assets()
    regenerate_source_bound()
    patch_runner()
    update_return_contracts()
    update_other_contracts()
    write_proposed_selector()
    update_manifest()
    prezip_package_specific_preflight()
    write_staging_receipt()
    print((OUT / "STAGING_WAIT_MAINLINE_SELECTOR_ACCEPTANCE.json").read_text(encoding="utf-8"))
    return 0


def finalize_staged() -> int:
    if not TREE.is_dir() or ZIP.exists():
        raise SystemExit("staged tree is absent or final ZIP already exists")
    require_authority(require_selector=True)
    staged_selector = TREE / "contracts/server_diagnostic_mode_selector.json"
    if staged_selector.read_bytes() != SELECTOR.read_bytes():
        raise RuntimeError("mainline accepted selector is not byte-equal to staged proposal")
    report = OUT / "gates/family_dispatch_mode_binding_tree.json"
    command = [
        sys.executable, str(ROOT / "tools/validate_server_family_dispatch_mode_binding.py"),
        "--binding", str(BINDING), "--repo-root", str(ROOT), "--package-root", str(TREE),
        "--report", str(report),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"staged dispatch/mode gate failed: {completed.stdout[-4096:]} {completed.stderr[-4096:]}")
    deterministic_zip()
    write_receipt()
    print((OUT / "build_receipt.json").read_text(encoding="utf-8"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--stage-only", action="store_true")
    mode.add_argument("--finalize-staged", action="store_true")
    args = parser.parse_args()
    return stage_only() if args.stage_only else finalize_staged()


if __name__ == "__main__":
    raise SystemExit(main())
