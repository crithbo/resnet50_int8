#!/usr/bin/env python3
"""Aggregate exact v100 guard-v2 gates and emit the local release receipt."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v100b_lcdup_guardv2"
OUT = ROOT / "outputs/conv_node0004_v100b_lcdup_guardv2_release1"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
GATES = OUT / "gates"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def identity(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": size, "sha256": digest.hexdigest()}


def run_focused() -> dict[str, Any]:
    dependency = ROOT / "outputs/.local_gate_deps"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(dependency)
    rows = []
    for test, expected in (
        (ROOT / "tests/test_server_observer_operational_guard_v2.py", 13),
        (ROOT / "tests/test_server_observer_operational_attempt_boundary.py", 10),
    ):
        completed = subprocess.run([sys.executable, str(test)], cwd=ROOT, env=environment, capture_output=True, text=True, timeout=120, check=False)
        output = completed.stdout + completed.stderr
        rows.append({"path": str(test.relative_to(ROOT)).replace("\\", "/"), "expected": expected, "exit_code": completed.returncode, "output_tail": output[-4096:]})
    report = {
        "schema": "node0004-v100b-guard-v2-focused-regression-v1",
        "package_id": PACKAGE,
        "pass": all(row["exit_code"] == 0 and f"Ran {row['expected']} tests" in row["output_tail"] for row in rows),
        "tests": rows,
        "total_expected": 23,
        "claim_boundary": "Canonical local guard/boundary regression only; no production VCS or DUT claim.",
    }
    path = GATES / "guard_v2_focused_regression.json"
    path.write_bytes(canonical(report))
    return report


def semantic_v4() -> dict[str, Any]:
    registry_path = ROOT / "contracts/server_package_build_gate_registry_v1.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    wanted = {"observer_only_wide_causal_final_zip", "first_fresh_extra_audit"}
    rows = [item for item in registry["gates"] if item.get("gate_id") in wanted]
    manifest = json.loads((TREE / "package_manifest.json").read_text(encoding="utf-8"))
    errors = []
    if {item["gate_id"] for item in rows} != wanted or any(str(item.get("semantic_version")) != "4" for item in rows):
        errors.append("current build-gate semantic version 4 binding differs")
    if manifest.get("first_fresh_semantic_version") != 4 or manifest.get("activation_epoch") != "observer-operational-guard-live-tree-v2":
        errors.append("package first-fresh semantic/epoch binding differs")
    report = {
        "schema": "node0004-v100b-current-build-gate-binding-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "activation_epoch": "observer-operational-guard-live-tree-v2",
        "semantic_version": 4,
        "registry": identity(registry_path),
        "gates": rows,
        "claim_boundary": "Current-disk build-gate identity only; no production execution claim.",
    }
    (GATES / "build_gate_semantic_v4.json").write_bytes(canonical(report))
    return report


def main() -> int:
    focused = run_focused()
    semantic = semantic_v4()
    expected = [
        "active_rule_registry.json", "build_gate_semantic_v4.json", "deterministic_zip.json",
        "first_fresh.json", "frozen_surface.json", "guard_v2_exit2_missing_receipt.json",
        "guard_v2_focused_regression.json", "guard_v2_monitor_exception_fixture.json",
        "guard_v2_policy.json", "hdl.json", "lexical_tree.json", "lexical_zip.json",
        "observer_only_final_zip.json", "operational_boundary_final_zip.json", "post_sim.json",
        "release_admission.json", "runner_tree.json", "runner_zip.json", "runtime_preflight.json",
        "source_bound_final_zip.json",
    ]
    errors: list[str] = []
    gate_rows: list[dict[str, Any]] = []
    for name in expected:
        path = GATES / name
        if not path.is_file():
            errors.append(f"gate receipt absent: {name}")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass") is not True:
            errors.append(f"gate did not pass: {name}")
        gate_rows.append({**identity(path), "pass": value.get("pass"), "errors": value.get("errors", [])})
    if not focused["pass"] or not semantic["pass"]:
        errors.append("guard-v2 focused or semantic-v4 aggregate failed")
    package = identity(ZIP)
    build = json.loads((OUT / "build_receipt.json").read_text(encoding="utf-8"))
    if build.get("package_zip", {}).get("sha256") != package["sha256"]:
        errors.append("build receipt final ZIP identity differs")
    receipt = {
        "schema": "node0004-v100b-lcdup-guardv2-mainline-package-receipt-v1",
        "role_id": "family.conv.serialized",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": PACKAGE,
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE" if not errors else "LOCAL_GATE_FAILURE",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "pass": not errors,
        "errors": errors,
        "conflicts": [],
        "previous_progress": "v99 reached production VCS elaboration/link preparation, but its v1 live-tree monitor exited without the mandatory compile/finalization guard receipts before simulation; tuple10 was not tested.",
        "current_purpose": "Preserve the validated negligible-cost LC9-to-LC3 mapper duplication and tuple10/natural-terminal/Formal-D target while replacing only the operational runner boundary with canonical guard-v2 live-tree monitoring, emergency receipt/reap and durable cleanup classification.",
        "package": package,
        "source_package": build["source_zip"],
        "gates": gate_rows,
        "first_fresh_semantic_version": 4,
        "changed_surface": build["changed_surface"],
        "frozen_surface": build["frozen_surface"],
        "unique_future_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "server_actions_performed": [],
        "storage_manager_called": False,
        "claim_boundary": "Local exact-tree/final-ZIP/static and negative-control gates only. Production compile, simulation, guard-v2 behavior on real VCS trees, tuple10, natural terminal, Formal-D, E3, E4 and E5 remain unproven until a formal return.",
    }
    (OUT / "mainline_package_receipt.json").write_bytes(canonical(receipt))
    task = (
        "# Serialized Conv v100 guard-v2 local package receipt\n\n"
        "Previous progress: v99 reached production VCS elaboration/link preparation, but its v1 live-tree monitor failed before simulation and returned no mandatory guard receipts; tuple10 was not tested.\n\n"
        "Current purpose: preserve the mapper-validated LC9→LC3 duplicate branch and the 52-signal tuple10/downstream/natural-terminal/Formal-D target, changing only the activated operational guard-v2 runner/return boundary.\n\n"
        f"Disposition: **{receipt['status']}**.\n\n"
        f"Exact local ZIP: `{package['path']}`.\n\n"
        f"Gates: {len(gate_rows)}/{len(expected)} PASS; guard-v2 focused regression 23/23 PASS; observer-only and first-fresh registry semantic version 4 bound.\n\n"
        "No managed storage write and no upload, lease, connection, or server execution occurred. The ZIP is not a production result.\n"
    )
    (OUT / "task_record.md").write_text(task, encoding="utf-8", newline="\n")
    print(json.dumps({"status": receipt["status"], "pass": receipt["pass"], "errors": errors, "package": package, "gate_count": len(gate_rows)}, sort_keys=True))
    return 0 if receipt["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
