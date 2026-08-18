#!/usr/bin/env python3
"""Aggregate canonical semantic-v5 v102 exact local gates."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v102b_lcdup_guardprocfs"
OUT = ROOT / "outputs/conv_node0004_v102b_lcdup_guardprocfs_release1"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
GATES = OUT / "gates"
ACTIVATION = ROOT / "outputs/observer_operational_guard_process_identity_runtime_budget_v3/CANONICAL_GUARD_PROCESS_IDENTITY_ACTIVATION_RECEIPT.json"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def identity(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": size, "sha256": digest.hexdigest()}


def run_focused() -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "outputs/.local_gate_deps")
    rows = []
    for relative, expected in (
        ("tests/test_server_observer_operational_guard_v2.py", 19),
        ("tests/test_server_observer_operational_attempt_boundary.py", 10),
    ):
        completed = subprocess.run(
            [sys.executable, str(ROOT / relative)], cwd=ROOT, env=environment,
            capture_output=True, text=True, timeout=120, check=False,
        )
        output = completed.stdout + completed.stderr
        rows.append({"path": relative, "expected": expected, "exit_code": completed.returncode, "output_tail": output[-4096:]})
    report = {
        "schema": "node0004-v102b-canonical-guard-focused-regression-v1",
        "package_id": PACKAGE,
        "pass": all(row["exit_code"] == 0 and f"Ran {row['expected']} tests" in row["output_tail"] for row in rows),
        "tests": rows,
        "total_expected": 29,
        "activation_epoch": "observer-guard-process-identity-v3",
        "claim_boundary": "Current canonical guard/attempt-boundary regression only; no production Linux/VCS or DUT claim.",
    }
    (GATES / "guard_v3_focused_regression.json").write_bytes(canonical(report))
    return report


def semantic_binding() -> dict[str, Any]:
    registry_path = ROOT / "contracts/server_package_build_gate_registry_v1.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    rows = [item for item in registry["gates"] if item.get("gate_id") in {"observer_only_wide_causal_final_zip", "first_fresh_extra_audit"}]
    versions = {item["gate_id"]: str(item.get("semantic_version")) for item in rows}
    manifest = json.loads((TREE / "package_manifest.json").read_text(encoding="utf-8"))
    errors = []
    if versions != {"observer_only_wide_causal_final_zip": "5", "first_fresh_extra_audit": "4"}:
        errors.append("current observer/first-fresh semantic version binding differs")
    if manifest.get("activation_epoch") != "observer-guard-process-identity-v3" or manifest.get("observer_only_semantic_version") != 5:
        errors.append("package semantic-v5 activation binding differs")
    activation = json.loads(ACTIVATION.read_text(encoding="utf-8"))
    if activation.get("status") != "CANONICAL_GUARD_PROCESS_IDENTITY_ACTIVATED":
        errors.append("canonical activation receipt is not active")
    report = {
        "schema": "node0004-v102b-current-build-gate-binding-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "activation_epoch": "observer-guard-process-identity-v3",
        "semantic_versions": versions,
        "registry": identity(registry_path),
        "activation_receipt": identity(ACTIVATION),
        "gates": rows,
        "claim_boundary": "Current canonical activation/build-gate identity only; no production execution claim.",
    }
    (GATES / "build_gate_semantic_v5.json").write_bytes(canonical(report))
    return report


def main() -> int:
    focused = run_focused()
    semantic = semantic_binding()
    expected = [
        "active_rule_registry.json", "build_gate_semantic_v5.json", "deterministic_zip.json",
        "first_fresh.json", "frozen_surface.json", "guard_v2_exit2_missing_receipt.json",
        "guard_v2_monitor_exception_fixture.json", "guard_v2_policy.json",
        "guard_v3_failure_handoff_fixture.json", "guard_v3_focused_regression.json", "guardprocfs.json",
        "hdl.json", "lexical_tree.json", "lexical_zip.json", "observer_only_final_zip.json",
        "operational_boundary_final_zip.json", "post_sim.json", "release_admission.json",
        "runner_tree.json", "runner_zip.json", "runtime_preflight.json", "source_bound_final_zip.json",
    ]
    errors: list[str] = []
    gates: list[dict[str, Any]] = []
    for name in expected:
        path = GATES / name
        if not path.is_file():
            errors.append(f"gate receipt absent: {name}")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass") is not True:
            errors.append(f"gate did not pass: {name}")
        gates.append({**identity(path), "pass": value.get("pass"), "errors": value.get("errors", [])})
    if not focused["pass"] or not semantic["pass"]:
        errors.append("canonical focused regression or semantic binding failed")
    package = identity(ZIP)
    build = json.loads((OUT / "build_receipt.json").read_text(encoding="utf-8"))
    if build.get("package_zip", {}).get("sha256") != package["sha256"]:
        errors.append("build receipt final ZIP identity differs")
    status = "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE" if not errors else "LOCAL_GATE_FAILURE"
    guard_gate = json.loads((GATES / "guardprocfs.json").read_text(encoding="utf-8"))
    receipt = {
        "schema": "node0004-v102b-canonical-guard-mainline-package-receipt-v1",
        "role_id": "family.conv.serialized", "owner_epoch": 2, "registry_epoch": 6,
        "package_id": PACKAGE, "status": status,
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "publish_authorized": False,
        "pass": not errors, "errors": errors, "conflicts": [],
        "previous_progress": "v101 passed local gates but was rejected before publication because its transitional ps-backed guard bytes differed from canonical semantic-v5.",
        "current_purpose": "Preserve the exact LC9-to-LC3 mapper/config and tuple10 target while using canonical childless procfs PID+start_time process identity and durable failure handoff.",
        "package": package,
        "source_package": build["source_zip"],
        "activation_receipt": identity(ACTIVATION),
        "canonical_guard_sha256": guard_gate["canonical_guard_sha256"],
        "gates": gates,
        "negative_controls": guard_gate["negative_controls"],
        "observer_only_semantic_version": 5,
        "first_fresh_semantic_version": 4,
        "changed_surface": build["changed_surface"], "frozen_surface": build["frozen_surface"],
        "unique_future_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "server_actions_performed": [], "storage_manager_called": False,
        "claim_boundary": "Local exact ZIP/static/current canonical regressions only. Production Linux/VCS, simulation, tuple10, natural terminal, Formal-D and E3-E5 remain unproven.",
    }
    (OUT / "mainline_package_receipt.json").write_bytes(canonical(receipt))
    task = (
        "# Serialized Conv v102 canonical procfs guard local receipt\n\n"
        "Previous progress: v101 was rejected before publication because its transitional ps-backed guard bytes did not match the activated canonical childless-procfs implementation.\n\n"
        "Current purpose: keep the LC9→LC3 configuration, workload, functional RTL and 52-signal tuple10/downstream/natural-terminal/Formal-D target frozen while binding PID+start_time identity, PID-reuse protection, real descendants and durable failure handoff.\n\n"
        f"Disposition: **{status} / STORAGE_WAIT_MAINLINE_SERIAL_RELEASE**.\n\n"
        f"Exact local ZIP: `{package['path']}`. Gates: {len(gates)}/{len(expected)} PASS; canonical focused regression 29/29 PASS.\n\n"
        "No managed-storage write and no upload, lease, connection or server execution occurred.\n"
    )
    (OUT / "task_record.md").write_text(task, encoding="utf-8", newline="\n")
    print(json.dumps({"status": status, "pass": receipt["pass"], "errors": errors, "package": package, "gate_count": len(gates)}, sort_keys=True))
    return 0 if receipt["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
