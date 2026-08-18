#!/usr/bin/env python3
"""Aggregate v106 gates and prepare the mandatory independent-audit handoff."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v106b_lcdup_return2pflight"
OUT = ROOT / "outputs/conv_node0004_v106b_lcdup_return2pflight_release1"
ZIP = OUT / f"{PACKAGE}.zip"
TREE = OUT / "build" / PACKAGE
GATES = OUT / "gates"
ANALYSIS = ROOT / "outputs/conv_node0004_v102b_lcdup_guardprocfs_return_r1786958038398677116_3776638"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def active_rule_audit() -> dict[str, Any]:
    path = GATES / "active_rule_registry.json"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools/audit_active_rule_registry.py"), "--repo-root", str(ROOT), "--report", str(path)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"pass": False, "errors": ["active-rule report absent"]}
    if completed.returncode != 0:
        value.setdefault("errors", []).append("active-rule audit exited nonzero")
        value["pass"] = False
        write(path, value)
    return value


def focused_regression() -> dict[str, Any]:
    modules = [
        "tests.test_server_observer_only_wide_causal",
        "tests.test_server_observer_operational_attempt_boundary",
        "tests.test_server_observer_operational_guard_v2",
        "tests.test_server_package_local_hdl_lexical",
        "tests.test_server_package_release_admission",
        "tests.test_server_post_sim_return",
        "tests.test_server_runner_return_resilience",
        "tests.test_server_runtime_preflight_native_flow",
        "tests.test_server_source_bound_observer",
        "tests.test_server_first_fresh_extra_audit",
        "tests.test_server_diagnostic_mode_selector",
        "tests.test_server_family_dispatch_mode_binding",
        "tests.test_server_release_consistency",
    ]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "outputs/.local_gate_deps")
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", *modules], cwd=ROOT, env=environment,
        capture_output=True, text=True, timeout=300, check=False,
    )
    output = completed.stdout + completed.stderr
    match = re.search(r"Ran (\d+) tests?", output)
    report = {
        "schema": "node0004-v106-focused-regression-v1",
        "package_id": PACKAGE,
        "pass": completed.returncode == 0 and re.search(r"(?:^|\n)OK(?: \(skipped=\d+\))?\s*$", output) is not None and match is not None,
        "errors": [],
        "modules": modules,
        "tests_run": int(match.group(1)) if match else None,
        "exit_code": completed.returncode,
        "output_tail": output[-12000:],
        "claim_boundary": "Current release/observer/return shared regression only; no production or DUT claim.",
    }
    if not report["pass"]:
        report["errors"].append("focused canonical regression failed")
    write(GATES / "focused_regression.json", report)
    return report


def semantic_binding() -> dict[str, Any]:
    registry_path = ROOT / "contracts/server_package_build_gate_registry_v1.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    wanted = {
        "observer_only_wide_causal_final_zip": "5",
        "first_fresh_extra_audit": "6",
        "family_dispatch_mode_binding_final_zip": "1",
        "release_cross_member_temporal_consistency_final_zip": "1",
    }
    actual = {
        row["gate_id"]: str(row.get("semantic_version"))
        for row in registry.get("gates", []) if row.get("gate_id") in wanted
    }
    manifest = json.loads((TREE / "package_manifest.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    if actual != wanted:
        errors.append("current semantic versions differ")
    if manifest.get("build_gate_registry_sha256") != sha(registry_path):
        errors.append("manifest build-gate registry SHA differs")
    if manifest.get("final_zip_rule_self_audit", {}).get("status") != "PASS":
        errors.append("manifest final-ZIP self-audit status is not terminal PASS")
    report = {
        "schema": "node0004-v106-build-gate-semantic-binding-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "semantic_versions": actual,
        "registry": identity(registry_path),
        "claim_boundary": "Current build-gate identity only; no production claim.",
    }
    write(GATES / "build_gate_semantic_binding.json", report)
    return report


def production_shaped_preflight() -> dict[str, Any]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="node0004-v106-production-shaped-") as raw:
        root = Path(raw)
        with zipfile.ZipFile(ZIP) as archive:
            archive.extractall(root)
        package = root / PACKAGE
        before = {p.relative_to(package).as_posix(): sha(p) for p in package.rglob("*") if p.is_file()}
        completed = subprocess.run(
            [sys.executable, "-B", str(package / "package_tools/package_release_preflight.py"),
             "preflight", "--package-root", str(package)],
            cwd=package, capture_output=True, text=True, check=False,
        )
        after = {p.relative_to(package).as_posix(): sha(p) for p in package.rglob("*") if p.is_file()}
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        observer = (package / "tb_probe/observer_only_wide_causal.svh").read_text(encoding="utf-8")
        checks = {
            "clean_exact_zip_package_preflight": completed.returncode == 0 and before == after,
            "compile_argv_source_xmr_capture": all(token in runner for token in (
                "compile_argv=(make -f Makefile.tb_NDP_Top_new_phy compile",
                "node0004_actual_compile_source_identity.py", "node0004_observerwide_source_identity.py", "--target-instance")),
            "simv_start_order": "[ -x \"$simv\" ]" in runner and runner.find("sim_started=true") < runner.find("supervise-phase --phase simulation"),
            "observer_64bit_accept_counters": "codex_counter_time_ps = $time" in observer and "$rtoi" not in observer and all(token in observer for token in ("cnt_lc3_accept", "cnt_input1_accept", "cnt_mem_tuple_wr", "cnt_metadata_emit", "cnt_prepared_wr", "cnt_prepared_rd")),
            "complete_state_global_witness_plateau": all(token in observer for token in ("reg [255:0] codex_causal_state", "codex_global_witness", "$isunknown", "codex_plateau_cycles >= 1048576")),
            "single_wall_exit_authority": runner.count("supervise-phase --phase simulation") == 1 and "--timeout 3660" in next(line for line in runner.splitlines() if "supervise-phase --phase simulation" in line) and "--timeout 3600" not in runner,
            "guard_before_publish_order": runner.find("# RELEASE_PHASE_FINALIZATION_GUARD_COMPLETE") < runner.find("# RELEASE_PHASE_RETURN_PUBLISH"),
            "durable_cleanup_after_publish": runner.find("# RELEASE_PHASE_RETURN_PUBLISH") < runner.find("# RELEASE_PHASE_DURABLE_RETURN_RECEIPT") < runner.find("# RELEASE_PHASE_POST_DURABLE_CLEANUP_RECEIPT"),
            "pid_start_time_full_reap": all(token in (package / "package_tools/server_observer_operational_guard_v2.py").read_text(encoding="utf-8") for token in ("start_time_ticks", "TERM", "KILL", "process_fully_reaped", "owned_process_identities_remaining")),
            "cross_member_temporal_gate": json.loads((GATES / "release_cross_member_temporal_consistency_final_zip.json").read_text(encoding="utf-8")).get("pass") is True,
            "mode_dispatch_final_zip": json.loads((GATES / "family_dispatch_mode_binding_final_zip.json").read_text(encoding="utf-8")).get("pass") is True and json.loads((GATES / "mode_selector_final_zip.json").read_text(encoding="utf-8")).get("pass") is True,
            "frozen_observer_and_two_phase_negatives": json.loads((GATES / "observer_runtime_frozen.json").read_text(encoding="utf-8")).get("pass") is True and json.loads((GATES / "two_phase_return_fix.json").read_text(encoding="utf-8")).get("pass") is True,
        }
        errors.extend(name for name, passed in checks.items() if not passed)
        report = {
            "schema": "node0004-v106-production-shaped-preflight-v1",
            "package_id": PACKAGE,
            "pass": not errors,
            "errors": errors,
            "checks": checks,
            "preflight": {"exit_code": completed.returncode, "stdout": completed.stdout[-4096:], "stderr": completed.stderr[-4096:], "tree_unchanged": before == after},
            "exact_zip": identity(ZIP),
            "limitations": ["No local dry-run substitutes for production Linux/VCS, simulation, tuple10, natural terminal or Formal-D."],
            "claim_boundary": "Production-shaped exact-ZIP static/preflight checklist only; no production claim.",
        }
    write(GATES / "production_shaped_preflight.json", report)
    return report


def main() -> int:
    active = active_rule_audit()
    focused = focused_regression()
    semantic = semantic_binding()
    production = production_shaped_preflight()
    patch_disposition = {
        "schema": "node0004-v106-patch-receipt-reuse-disposition-v1",
        "package_id": PACKAGE,
        "same_identity_patch_authorized": True,
        "same_identity_patch_policy_receipt": identity(ROOT / "outputs/mainline_package_build_slowness_rule_skill_audit_v1/CANONICAL_LOCAL_UNPUBLISHED_CANDIDATE_PATCH_POLICY_RECONCILIATION_RECEIPT.json"),
        "prepatch_zip": {
            "bytes": 5990935,
            "sha256": "2eff4e640285b352e41984b9dec3407c15c6f7045fcb17050ee51f13cda8588a",
        },
        "zip_existed_before_patch": True,
        "patch_delta": [
            "replace package-local server_package_build_gate_registry_v1.json receipt with current canonical exact bytes",
            "update only package_manifest build_gate_registry_sha256 and matching file identity",
        ],
        "frozen_surfaces": [
            "config", "functional RTL", "workload", "numeric", "golden",
            "LC9-to-LC3 mapper semantics", "52-signal causal cone",
            "observer accepted-event counters", "plateau semantics", "two-phase return ordering",
        ],
        "final_zip_receipts_reused": [],
        "final_zip_receipts_rerun_after_exact_zip": True,
        "invalidated_prepatch_final_receipts": True,
        "staging_receipts_reused": [
            "mainline family dispatch authority/binding/accepted selector (exact identities unchanged)",
            "pre-ZIP release consistency surfaces (package source inputs unchanged except current registry receipt binding)",
        ],
        "shared_gate_consumed_before_zip": "release_cross_member_temporal_consistency_final_zip",
        "pass": True,
        "errors": [],
        "claim_boundary": "Local build receipt reuse disposition only; no publication or server claim.",
    }
    write(OUT / "PATCH_AND_RECEIPT_REUSE_DISPOSITION.json", patch_disposition)

    excluded = {"production_shaped_preflight.json", "focused_regression.json", "active_rule_registry.json", "build_gate_semantic_binding.json"}
    gate_paths = sorted(path for path in GATES.glob("*.json") if path.name not in excluded)
    gate_paths.extend([GATES / name for name in sorted(excluded)])
    errors: list[str] = []
    gates: list[dict[str, Any]] = []
    for path in gate_paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass") is not True:
            errors.append(f"gate failed: {path.name}")
        gates.append({**identity(path), "pass": value.get("pass"), "errors": value.get("errors", [])})
    if not all(item.get("pass") is True for item in (active, focused, semantic, production)):
        errors.append("aggregate current gate failed")

    package = identity(ZIP)
    sidecar = OUT / f"{PACKAGE}.zip.sha256"
    sidecar.write_text(f"{package['sha256']}  {PACKAGE}.zip\n", encoding="ascii", newline="\n")
    audit = {
        "schema": "node0004-v106-final-zip-local-audit-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "package": package,
        "sidecar": identity(sidecar),
        "gate_count": len(gates),
        "gates": gates,
        "patch_reuse_disposition": identity(OUT / "PATCH_AND_RECEIPT_REUSE_DISPOSITION.json"),
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE" if not errors else "LOCAL_GATE_FAILURE",
        "review_status": "WAIT_INDEPENDENT_PACKAGE_AUDIT",
        "publish_authorized": False,
        "storage_manager_called": False,
        "server_actions_performed": [],
        "claim_boundary": "Family local gates only; independent package audit, production Linux/VCS, tuple10, natural terminal, Formal-D and E3-E5 remain open.",
    }
    audit_path = OUT / "final_zip_local_audit.json"
    write(audit_path, audit)
    handoff = {
        "schema": "node0004-v106-independent-package-audit-handoff-v1",
        "package_id": PACKAGE,
        "status": audit["status"],
        "review_status": "WAIT_INDEPENDENT_PACKAGE_AUDIT",
        "package": package,
        "sidecar": identity(sidecar),
        "final_audit": identity(audit_path),
        "gate_receipts": gates,
        "production_shaped_preflight": identity(GATES / "production_shaped_preflight.json"),
        "required_independent_checks": [
            "exact ZIP/sidecar/manifest/CRC and accepted selector",
            "compile argv/source/XMR and simv start order",
            "64-bit accepted-event counters and plateau",
            "single 3660-second wall authority and 86400 absolute maximum identity",
            "completed finalization guard before immutable publish",
            "external durable/cleanup receipts and no overwrite",
            "TERM-wait-KILL plus PID+start-time full reap",
            "cross-member producer and held-level replay closure",
        ],
        "publish_authorized": False,
        "claim_boundary": "Independent-audit handoff only; this receipt does not authorize publication or execution.",
    }
    handoff_path = OUT / "INDEPENDENT_PACKAGE_AUDIT_HANDOFF.json"
    write(handoff_path, handoff)
    receipt = {
        "schema": "node0004-v106-mainline-package-receipt-v1",
        "role_id": "family.conv.serialized",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "status": audit["status"],
        "review_status": "WAIT_INDEPENDENT_PACKAGE_AUDIT",
        "package": package,
        "sidecar": identity(sidecar),
        "final_audit": identity(audit_path),
        "independent_audit_handoff": identity(handoff_path),
        "formal_return_analysis": identity(ANALYSIS / "formal_return_analysis.json"),
        "previous_progress": "v102 compiled, started simulation and entered the frozen copied-LC3/PE8/Memory_AG target; tuple10 remained uncountable under runtime/return defects.",
        "current_purpose": "Preserve config/RTL/workload/numeric/golden/LC9-to-LC3/52-signal/counter-plateau surfaces and repair only two-phase return plus activated cross-member consistency.",
        "unique_future_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "publish_authorized": False,
        "storage_status": "STORAGE_WAIT_INDEPENDENT_PACKAGE_AUDIT",
        "storage_manager_called": False,
        "server_actions_performed": [],
        "conflicts": [],
        "claim_boundary": audit["claim_boundary"],
    }
    write(OUT / "mainline_package_receipt.json", receipt)
    task = (
        "# Serialized Conv v106 two-phase return and consistency package\n\n"
        "Frozen config, functional RTL, workload, numeric/golden data, LC9→LC3 mapper semantics, 52-signal cone and v103 observer counters/plateau.\n\n"
        "Changed only fresh identity, exact family mode binding, two-phase finalization/return ordering and required cross-member release-consistency surfaces.\n\n"
        f"Status: **{audit['status']} / WAIT_INDEPENDENT_PACKAGE_AUDIT**. Gates: {len(gates)}/{len(gates)} PASS when package pass=true.\n\n"
        "No managed-storage write, upload, lease, connection or server execution occurred.\n"
    )
    (OUT / "task_record.md").write_text(task, encoding="utf-8", newline="\n")
    print(json.dumps({"pass": not errors, "status": audit["status"], "package": package, "gates": len(gates)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
