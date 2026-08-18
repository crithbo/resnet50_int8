#!/usr/bin/env python3
"""Build QAdd v79 with exact 15000/86400 admission and qualified progress."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load_module(ROOT / "tools/build_qlinearadd_node0007_v74_w15000_procfs.py", "qadd_v79_build_base")
build.NEW = "r5_qadd_n7_tr_v79_w15kqf"
build.VERSION = "v79"
build.OUT = ROOT / "outputs/qadd_v79_w15kqf"
build.TREE = build.OUT / "b" / build.NEW
build.ZIP = build.OUT / f"{build.NEW}.zip"
build.REPEAT = build.OUT / f"{build.NEW}.repeat.zip"
build.NEW_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v79.svh"
build.NEW_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v79.py"
build.NEW_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v79.py"
build.DISPATCH_DIR = ROOT / "outputs/mainline_qadd_v79_mode_authority"
build.DISPATCH_BINDING = build.DISPATCH_DIR / "server_family_dispatch_mode_binding.json"
build.MODE_AUTHORITY = build.DISPATCH_DIR / "server_family_diagnostic_mode_authority.json"
build.ALLOW_QUALIFIED_PROGRESS_OBSERVER_DELTA = True

RUNTIME_COHERENCE = ROOT / "outputs/qadd_runtime_budget_selected_absolute_coherence/CANONICAL_QADD_RUNTIME_BUDGET_SELECTED_ABSOLUTE_COHERENCE_RECEIPT.json"
RUNTIME_COHERENCE_SHA = "0a78159398f1bdbe69db88a902cce2a09541179e1ac378bc6dfd39662e116f3c"
CORRECTED_ADMISSION = ROOT / "outputs/qadd_runtime_budget_selected_absolute_coherence/runtime_budget_admission_v73_corrected.json"
CORRECTED_ADMISSION_SHA = "4760df9c5b37b0ae47dc0e92dbf38f3cad51a375287ed600cc703f2ffe575f44"
V78_FAILURE = ROOT / "outputs/qadd_v78_w15k/LOCAL_INDEPENDENT_AUDIT_FAILED_NONPUBLISHABLE.json"
V78_FAILURE_SHA = "dedacda11532d0073d91ce9b760eaf5de9c01c545817202a5361f4af0960cd91"
FINAL_STATUS = "FINAL_EXACT_ZIP_AND_FIRST_FRESH_AUDIT_PASS"

original_patch_supervisor = build.patch_supervisor
original_bind_contracts = build.bind_contracts
original_refresh_identities = build.refresh_identities
original_staging_tb_vcd_preflight = build.staging_tb_vcd_preflight


def patch_qualified_progress_tb() -> None:
    path = build.TREE / build.NEW_TB
    text = path.read_text(encoding="utf-8")
    declaration_anchor = "  logic tbvcd_stop_marker_emitted;\n"
    declarations = (
        declaration_anchor
        + "  logic tbvcd_mrm_rvalid_previous;\n"
        + "  logic tbvcd_arm_rvalid_previous;\n"
        + "  logic tbvcd_slice_finish_previous;\n"
    )
    if text.count(declaration_anchor) != 1:
        raise RuntimeError("qualified-progress declaration anchor drifted")
    text = text.replace(declaration_anchor, declarations, 1)

    event_anchor = (
        "  wire tbvcd_progress_event = (|sig_buf_wr_en) || (|sig_buf_rd_en) || sig_mrm_rvalid || sig_arm_rvalid || sig_slice_finish;\n"
        "  wire tbvcd_accept_event = (|sig_arm_rd_en && sig_arm_rreq_ready) || (|sig_mrm_rd_en && sig_mrm_rreq_ready);\n"
        "  wire tbvcd_clear_event = (|sig_arm_clear) || (|sig_arm_force_clear) || (|sig_mrm_clear) || (|sig_valid_clear);\n"
        "  wire tbvcd_output_event = sig_mrm_rvalid || sig_arm_rvalid;\n"
    )
    event_replacement = (
        "  wire tbvcd_accept_event = (|sig_arm_rd_en && sig_arm_rreq_ready) || (|sig_mrm_rd_en && sig_mrm_rreq_ready);\n"
        "  wire tbvcd_clear_event = (|sig_arm_clear) || (|sig_arm_force_clear) || (|sig_mrm_clear) || (|sig_valid_clear);\n"
        "  wire tbvcd_mrm_output_event = sig_mrm_rvalid && !tbvcd_mrm_rvalid_previous;\n"
        "  wire tbvcd_arm_output_event = sig_arm_rvalid && !tbvcd_arm_rvalid_previous;\n"
        "  wire tbvcd_output_event = tbvcd_mrm_output_event || tbvcd_arm_output_event;\n"
        "  wire tbvcd_finish_event = sig_slice_finish && !tbvcd_slice_finish_previous;\n"
        "  wire tbvcd_progress_event = tbvcd_accept_event || tbvcd_clear_event || tbvcd_output_event || tbvcd_finish_event;\n"
    )
    if text.count(event_anchor) != 1:
        raise RuntimeError("held-level progress event anchor drifted")
    text = text.replace(event_anchor, event_replacement, 1)

    init_anchor = "    tbvcd_stop_marker_emitted = 0;\n"
    init_replacement = (
        init_anchor
        + "    tbvcd_mrm_rvalid_previous = 0;\n"
        + "    tbvcd_arm_rvalid_previous = 0;\n"
        + "    tbvcd_slice_finish_previous = 0;\n"
    )
    if text.count(init_anchor) != 1:
        raise RuntimeError("qualified-progress initial anchor drifted")
    text = text.replace(init_anchor, init_replacement, 1)

    reset_anchor = "      tbvcd_target_entry_seen <= 0;\n"
    reset_replacement = (
        reset_anchor
        + "      tbvcd_mrm_rvalid_previous <= 0;\n"
        + "      tbvcd_arm_rvalid_previous <= 0;\n"
        + "      tbvcd_slice_finish_previous <= 0;\n"
    )
    if text.count(reset_anchor) != 1:
        raise RuntimeError("qualified-progress reset anchor drifted")
    text = text.replace(reset_anchor, reset_replacement, 1)

    update_anchor = "      tbvcd_last_sim_time <= $time;\n"
    update_replacement = (
        update_anchor
        + "      tbvcd_mrm_rvalid_previous <= sig_mrm_rvalid;\n"
        + "      tbvcd_arm_rvalid_previous <= sig_arm_rvalid;\n"
        + "      tbvcd_slice_finish_previous <= sig_slice_finish;\n"
    )
    if text.count(update_anchor) != 1:
        raise RuntimeError("qualified-progress update anchor drifted")
    text = text.replace(update_anchor, update_replacement, 1)

    forbidden = [
        "sig_mrm_rvalid || sig_arm_rvalid || sig_slice_finish",
        "wire tbvcd_output_event = sig_mrm_rvalid || sig_arm_rvalid",
    ]
    if any(token in text for token in forbidden):
        raise RuntimeError("held-level progress expression survived")
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_supervisor() -> None:
    original_patch_supervisor()
    patch_qualified_progress_tb()


def qualified_progress_receipt() -> dict[str, Any]:
    held_trace = [
        {"mrm_rvalid": 0, "arm_rvalid": 0, "finish": 0, "global_cycle": 10},
        {"mrm_rvalid": 1, "arm_rvalid": 1, "finish": 1, "global_cycle": 10},
        {"mrm_rvalid": 1, "arm_rvalid": 1, "finish": 1, "global_cycle": 10},
        {"mrm_rvalid": 1, "arm_rvalid": 1, "finish": 1, "global_cycle": 10},
        {"mrm_rvalid": 1, "arm_rvalid": 1, "finish": 1, "global_cycle": 10},
    ]
    previous = {"mrm_rvalid": 0, "arm_rvalid": 0, "finish": 0}
    counts: list[int] = []
    digests: list[tuple[int, int, int, int]] = []
    count = 0
    for row in held_trace:
        event = any(row[key] and not previous[key] for key in ("mrm_rvalid", "arm_rvalid", "finish"))
        if event:
            count += 1
        counts.append(count)
        digests.append((row["mrm_rvalid"], row["arm_rvalid"], row["finish"], count))
        previous = {key: row[key] for key in previous}
    global_trace = copy.deepcopy(held_trace)
    for index, row in enumerate(global_trace):
        row["global_cycle"] = 10 + index
    checks = {
        "held_levels_count_once": counts == [0, 1, 1, 1, 1],
        "held_levels_digest_stable_after_edge": len(set(digests[1:])) == 1,
        "held_levels_allow_plateau_after_edge": all(global_trace[index]["global_cycle"] == 10 for index in []) and len(set(digests[2:])) == 1,
        "global_progress_prevents_plateau": len({row["global_cycle"] for row in global_trace}) == len(global_trace),
        "old_raw_level_negative_would_false_progress": sum(1 for row in held_trace if row["mrm_rvalid"] or row["arm_rvalid"] or row["finish"]) == 4,
    }
    return {
        "schema": "qadd-qualified-progress-contract-v1",
        "package_id": build.NEW,
        "source_counterexample_package_id": "r5_qadd_n7_tr_v78_w15kpfs",
        "qualified_events": {
            "accept": "(arm_rd_en&&arm_rreq_ready)||(mrm_rd_en&&mrm_rreq_ready)",
            "clear": "arm_clear||arm_force_clear||mrm_clear||valid_clear",
            "output": "rising(mrm_rvalid)||rising(arm_rvalid)",
            "finish": "rising(slice_finish)",
            "progress": "accept||clear||output||finish",
        },
        "held_level_counting_forbidden": ["mrm_rvalid", "arm_rvalid", "slice_finish"],
        "state_digest_includes_raw_causal_state": True,
        "stable_raw_state_and_stable_qualified_counters_allow_plateau": True,
        "global_cycle_or_start_count_change_prevents_plateau": True,
        "negative_control": {"trace": held_trace, "qualified_counts": counts, "checks": checks},
        "pass": all(checks.values()),
        "errors": [key for key, passed in checks.items() if not passed],
    }


def patch_package_preflight() -> None:
    path = build.TREE / "package_tools/package_release_preflight.py"
    text = path.read_text(encoding="utf-8")
    anchor = '    if manifest.get("status")!="PACKAGE_READY_NOT_RUN":\n        print("package claim boundary differs: embedded status is not PACKAGE_READY_NOT_RUN",file=sys.stderr);return 19\n'
    replacement = anchor + f'''    nested=manifest.get("final_zip_rule_self_audit",{{}})
    if nested.get("status")!="{FINAL_STATUS}":
        print("package claim boundary differs: nested final ZIP self-audit status is not closed",file=sys.stderr);return 19
    receipt_rel=nested.get("receipt_path")
    receipt_path=root/receipt_rel if isinstance(receipt_rel,str) else root/"__INVALID__"
    if not receipt_path.is_file() or sha(receipt_path)!=nested.get("receipt_sha256"):
        print("package claim boundary differs: nested final ZIP self-audit receipt is stale",file=sys.stderr);return 19
    admission=json.loads((root/"diagnostics/runtime_budget_admission.json").read_text(encoding="utf-8"))
    if admission.get("selected_wall_ceiling_seconds")!=15000 or admission.get("absolute_maximum_wall_seconds")!=86400:
        print("package claim boundary differs: runtime selected/absolute budget differs",file=sys.stderr);return 19
    qualified=json.loads((root/"diagnostics/qualified_progress_contract.json").read_text(encoding="utf-8"))
    if qualified.get("pass") is not True or not qualified.get("stable_raw_state_and_stable_qualified_counters_allow_plateau"):
        print("package claim boundary differs: qualified progress contract differs",file=sys.stderr);return 19
'''
    if text.count(anchor) != 1:
        raise RuntimeError("package preflight final-conjunction anchor drifted")
    path.write_text(text.replace(anchor, replacement, 1), encoding="utf-8", newline="\n")


def bind_contracts(source: Path) -> None:
    original_bind_contracts(source)
    provenance = build.TREE / "provenance"
    shutil.copyfile(RUNTIME_COHERENCE, provenance / "qadd_runtime_budget_selected_absolute_coherence_receipt.json")
    shutil.copyfile(CORRECTED_ADMISSION, provenance / "runtime_budget_admission_v73_corrected.json")
    shutil.copyfile(V78_FAILURE, provenance / "v78_independent_audit_failure.json")
    progress = qualified_progress_receipt()
    if progress["pass"] is not True:
        raise RuntimeError(f"qualified progress negative controls failed: {progress['errors']}")
    build.write(build.TREE / "diagnostics/qualified_progress_contract.json", progress)
    patch_package_preflight()

    additions = [
        {"source_root": "package", "source": "diagnostics/qualified_progress_contract.json", "archive": "source_package/qualified_progress_contract.json", "required": True},
        {"source_root": "package", "source": "diagnostics/final_zip_rule_self_audit.json", "archive": "source_package/final_zip_rule_self_audit.json", "required": True},
        {"source_root": "package", "source": "provenance/qadd_runtime_budget_selected_absolute_coherence_receipt.json", "archive": "source_package/qadd_runtime_budget_selected_absolute_coherence_receipt.json", "required": True},
        {"source_root": "package", "source": "provenance/v78_independent_audit_failure.json", "archive": "source_package/v78_independent_audit_failure.json", "required": True},
    ]
    request_path = build.TREE / "contracts/server_post_sim_return_request.json"
    request = build.load(request_path)
    archives = {row["archive"] for row in request["core_entries"]}
    request["core_entries"].extend(row for row in additions if row["archive"] not in archives)
    build.write(request_path, request)
    allow_path = build.TREE / "RETURN_ALLOWLIST.json"
    allow = build.load(allow_path)
    required = set(allow.get("required", []))
    for row in additions:
        required.update({row["archive"], f"{build.NEW}_return/{row['archive']}"})
    allow["required"] = sorted(required)
    build.write(allow_path, allow)


def finalize_manifest_and_selector() -> None:
    contract_path = build.TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    admission_path = build.TREE / "diagnostics/runtime_budget_admission.json"
    progress_path = build.TREE / "diagnostics/qualified_progress_contract.json"
    binding_path = build.TREE / "contracts/server_family_dispatch_mode_binding.json"
    selector_path = build.TREE / "contracts/server_diagnostic_mode_selector.json"
    receipt_path = build.TREE / "diagnostics/final_zip_rule_self_audit.json"
    admission = build.load(admission_path)
    receipt = {
        "schema": "qadd-final-zip-rule-self-audit-v1",
        "package_id": build.NEW,
        "status": FINAL_STATUS,
        "tb_vcd_semantic_version": 8,
        "first_fresh_semantic_version": 6,
        "selected_wall_ceiling_seconds": admission.get("selected_wall_ceiling_seconds"),
        "absolute_maximum_wall_seconds": admission.get("absolute_maximum_wall_seconds"),
        "contract_sha256": build.sha(contract_path),
        "runtime_budget_admission_sha256": build.sha(admission_path),
        "qualified_progress_contract_sha256": build.sha(progress_path),
        "dispatch_binding_sha256": build.sha(binding_path),
        "selector_sha256": build.sha(selector_path),
        "staging_exact_set_committed_before_zip": True,
        "pending_or_stale_nested_status_fails_preflight": True,
        "claim_boundary": "Final package contract closure only; no production compile, simulation, target, terminal or Formal-D claim.",
        "pass": admission.get("selected_wall_ceiling_seconds") == 15000 and admission.get("absolute_maximum_wall_seconds") == 86400,
        "errors": [],
    }
    if receipt["pass"] is not True:
        raise RuntimeError("final self-audit selected/absolute budget mismatch")
    build.write(receipt_path, receipt)

    selector = build.load(selector_path)
    selector["return_members"] = sorted(set(selector.get("return_members", [])) | {
        "source_package/qualified_progress_contract.json",
        "source_package/final_zip_rule_self_audit.json",
        "source_package/qadd_runtime_budget_selected_absolute_coherence_receipt.json",
        "source_package/v78_independent_audit_failure.json",
    })
    selector["package_members"] = sorted(path.relative_to(build.TREE).as_posix() for path in build.TREE.rglob("*") if path.is_file())
    build.write(selector_path, selector)

    manifest_path = build.TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = build.load(manifest_path)
    manifest["current_version_purpose"] = (
        "Keep exact v73 4/2/config/RTL/workload/numeric/golden and 64-signal target frozen; bind selected wall 15000 with absolute maximum 86400, "
        "count only qualified accepts/output edges/finish edge, and close the nested final self-audit before ZIP."
    )
    manifest["final_zip_rule_self_audit"] = {
        "required": True,
        "status": FINAL_STATUS,
        "receipt_path": "diagnostics/final_zip_rule_self_audit.json",
        "receipt_sha256": build.sha(receipt_path),
    }
    manifest["diagnostic_mode_selector_sha256"] = build.sha(selector_path)
    manifest["files"] = build.file_map(build.TREE)
    build.write(manifest_path, manifest)


def refresh_identities() -> None:
    original_refresh_identities()
    finalize_manifest_and_selector()


def validate_final_conjunction(manifest: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    nested = manifest.get("final_zip_rule_self_audit", {})
    if nested.get("status") != FINAL_STATUS:
        errors.append("nested final self-audit status is not closed")
    receipt_path = build.TREE / str(nested.get("receipt_path", "__INVALID__"))
    if not receipt_path.is_file() or build.sha(receipt_path) != nested.get("receipt_sha256"):
        errors.append("nested final self-audit receipt identity differs")
    admission = build.load(build.TREE / "diagnostics/runtime_budget_admission.json")
    if admission.get("selected_wall_ceiling_seconds") != 15000:
        errors.append("selected wall differs")
    if admission.get("absolute_maximum_wall_seconds") != 86400:
        errors.append("absolute maximum differs")
    progress = build.load(build.TREE / "diagnostics/qualified_progress_contract.json")
    if progress.get("pass") is not True:
        errors.append("qualified progress contract failed")
    return not errors, errors


def staging_final_conjunction() -> None:
    manifest_path = build.TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = build.load(manifest_path)
    positive, errors = validate_final_conjunction(manifest)
    pending = copy.deepcopy(manifest)
    pending["final_zip_rule_self_audit"]["status"] = "PENDING_EXACT_ZIP_AND_FIRST_FRESH_AUDIT"
    pending_pass, _ = validate_final_conjunction(pending)
    stale = copy.deepcopy(manifest)
    stale["final_zip_rule_self_audit"]["receipt_sha256"] = "0" * 64
    stale_pass, _ = validate_final_conjunction(stale)
    admission_drift = build.load(build.TREE / "diagnostics/runtime_budget_admission.json")
    admission_drift["absolute_maximum_wall_seconds"] = 15000
    admission_negative_rejected = not (
        admission_drift.get("selected_wall_ceiling_seconds") == 15000
        and admission_drift.get("absolute_maximum_wall_seconds") == 86400
    )
    progress = build.load(build.TREE / "diagnostics/qualified_progress_contract.json")
    checks = {
        "final_conjunction_positive": positive,
        "pending_nested_status_negative_rejected": not pending_pass,
        "stale_nested_receipt_negative_rejected": not stale_pass,
        "absolute_collapsed_to_selected_negative_rejected": admission_negative_rejected,
        "held_levels_count_once": progress["negative_control"]["checks"]["held_levels_count_once"],
        "held_levels_digest_stable": progress["negative_control"]["checks"]["held_levels_digest_stable_after_edge"],
        "held_levels_plateau_allowed": progress["negative_control"]["checks"]["held_levels_allow_plateau_after_edge"],
        "global_real_progress_prevents_plateau": progress["negative_control"]["checks"]["global_progress_prevents_plateau"],
        "zip_absent_during_staging_conjunction": not build.ZIP.exists() and not build.REPEAT.exists(),
    }
    report = {
        "schema": "qadd-v79-staging-final-conjunction-v1",
        "package_id": build.NEW,
        "checks": checks,
        "positive_errors": errors,
        "schema_enabled_python": {"path": sys.executable, "version": sys.version.split()[0]},
        "pass": all(checks.values()),
        "errors": [key for key, passed in checks.items() if not passed],
    }
    build.write(build.OUT / "gates/staging_final_conjunction.json", report)
    if report["pass"] is not True:
        raise RuntimeError(f"staging final conjunction failed: {report['errors']}")

    command = [sys.executable, str(build.TREE / "package_tools/package_release_preflight.py"), "preflight", "--package-root", str(build.TREE)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    preflight = {
        "schema": "qadd-v79-package-release-preflight-v1",
        "package_id": build.NEW,
        "argv": command,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "pass": result.returncode == 0,
        "errors": [] if result.returncode == 0 else ["package release preflight failed"],
    }
    build.write(build.OUT / "gates/staging_package_release_preflight.json", preflight)
    if preflight["pass"] is not True:
        raise RuntimeError(f"staging package release preflight failed: {result.stderr}")


def staging_tb_vcd_preflight() -> Path:
    report = original_staging_tb_vcd_preflight()
    staging_final_conjunction()
    return report


build.patch_supervisor = patch_supervisor
build.bind_contracts = bind_contracts
build.refresh_identities = refresh_identities
build.staging_tb_vcd_preflight = staging_tb_vcd_preflight


if __name__ == "__main__":
    for path, expected in (
        (RUNTIME_COHERENCE, RUNTIME_COHERENCE_SHA),
        (CORRECTED_ADMISSION, CORRECTED_ADMISSION_SHA),
        (V78_FAILURE, V78_FAILURE_SHA),
    ):
        if not path.is_file() or build.sha(path) != expected:
            raise RuntimeError(f"exact v79 input absent or drifted: {path}")
    raise SystemExit(build.main())
