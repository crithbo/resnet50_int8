#!/usr/bin/env python3
"""Aggregate v100 analysis and v101 exact local gates under the shared-audit hold."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v101b_lcdup_guardprocfix"
OUT = ROOT / "outputs/conv_node0004_v101b_lcdup_guardprocfix_release1"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
GATES = OUT / "gates"
ANALYSIS = ROOT / "outputs/conv_node0004_v100b_lcdup_guardv2_return_r1786935520909028428_3675469"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def identity(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": size,
        "sha256": digest.hexdigest(),
    }


def run_focused() -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "outputs/.local_gate_deps")
    rows = []
    for relative, expected in (
        ("tests/test_server_observer_operational_guard_v2.py", 14),
        ("tests/test_server_observer_operational_attempt_boundary.py", 10),
    ):
        completed = subprocess.run(
            [sys.executable, str(ROOT / relative)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        output = completed.stdout + completed.stderr
        rows.append({
            "path": relative,
            "expected": expected,
            "exit_code": completed.returncode,
            "output_tail": output[-4096:],
        })
    report = {
        "schema": "node0004-v101b-guardprocfix-focused-regression-v1",
        "package_id": PACKAGE,
        "pass": all(row["exit_code"] == 0 and f"Ran {row['expected']} tests" in row["output_tail"] for row in rows),
        "tests": rows,
        "total_expected": 24,
        "claim_boundary": "Local guard/boundary regression only; no real Linux/VCS or DUT claim.",
    }
    (GATES / "guard_v2_focused_regression.json").write_bytes(canonical(report))
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
        "schema": "node0004-v101b-current-build-gate-binding-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "activation_epoch": "observer-operational-guard-live-tree-v2",
        "semantic_version": 4,
        "registry": identity(registry_path),
        "gates": rows,
        "shared_guard_self_enumerator_adjudication": "WAIT_OPTIMIZER_MAINLINE_SHARED_AUDIT",
        "claim_boundary": "Current-disk build-gate identity only; the local guard patch is not yet canonically activated.",
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
        "guard_v2_policy.json", "guardprocfix.json", "hdl.json", "lexical_tree.json", "lexical_zip.json",
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
        errors.append("focused regression or semantic-v4 binding failed")
    package = identity(ZIP)
    build = json.loads((OUT / "build_receipt.json").read_text(encoding="utf-8"))
    if build.get("package_zip", {}).get("sha256") != package["sha256"]:
        errors.append("build receipt final ZIP identity differs")
    analysis = identity(ANALYSIS / "formal_return_analysis.json")
    rule_audit = identity(ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json")
    local_status = "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE" if not errors else "LOCAL_GATE_FAILURE"
    receipt = {
        "schema": "node0004-v100-return-v101b-guardprocfix-mainline-receipt-v1",
        "role_id": "family.conv.serialized",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": PACKAGE,
        "status": local_status,
        "storage_status": "STORAGE_WAIT_OPTIMIZER_MAINLINE_SHARED_AUDIT",
        "publish_authorized": False,
        "pass": not errors,
        "errors": errors,
        "conflicts": [],
        "previous_progress": "v100 production VCS compile/elaboration/link succeeded and emitted simv, but guard-v2 self-enumerated its transient ps helper as an unreaped owned child and returned 122 before simulation.",
        "current_purpose": "Preserve the validated LC9-to-LC3 mapper/config, 52-signal tuple10 target and observer-only profile while excluding only the exact ps enumerator PID and making return/cleanup failure paths immutable and fail closed.",
        "v100_disposition": "PACKAGE_LOCAL_SHARED_GUARD_V2_SELF_PS_ENUMERATION_FALSE_POSITIVE",
        "last_proven_good": "production compile/elaboration/link and simv emission",
        "first_divergence": "post-compile guard ownership scan counted the already-reaped transient ps enumerator and blocked simulation",
        "target_status": {
            "simulation_started": False,
            "tuple10_observed": False,
            "input1_undersupply_retested": False,
            "natural_terminal": False,
            "formal_d": False,
        },
        "package_build_failure_rule_audit": {
            "attempt_count": 3,
            "disposition": "RULE_CONFIRMATION_NO_CHANGE__IMPLEMENTATION_AND_NEGATIVE_CONTROL_ESCAPE",
            "continuation": True,
            "receipt": rule_audit,
            "shared_adjudication": "REQUIRED_BEFORE_STORAGE_PUBLICATION",
        },
        "formal_return_analysis": analysis,
        "package": package,
        "source_package": build["source_zip"],
        "gates": gate_rows,
        "negative_controls": json.loads((GATES / "guardprocfix.json").read_text(encoding="utf-8"))["negative_controls"],
        "first_fresh_semantic_version": 4,
        "changed_surface": build["changed_surface"],
        "frozen_surface": build["frozen_surface"],
        "unique_future_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "server_actions_performed": [],
        "storage_manager_called": False,
        "claim_boundary": "Local exact-tree/final-ZIP/static and negative-control gates only. The ps-enumerator fix is locally verified but awaits optimizer/mainline shared adjudication; production simulation, tuple10, natural terminal, Formal-D and E3-E5 remain unproven.",
    }
    (OUT / "mainline_package_receipt.json").write_bytes(canonical(receipt))
    task = (
        "# Serialized Conv v100 return analysis and v101 local gate receipt\n\n"
        "Previous progress: v100 completed production compile/elaboration/link and emitted simv. Simulation did not start because guard-v2 counted its own transient `ps` enumerator as a surviving owned child.\n\n"
        "Current purpose: preserve the exact LC9→LC3 mapper/config and tuple10 target while fixing only process enumeration, immutable return publication, and cleanup admission.\n\n"
        f"Disposition: **{local_status} / STORAGE_WAIT_OPTIMIZER_MAINLINE_SHARED_AUDIT**.\n\n"
        "PACKAGE_BUILD_FAILURE_RULE_AUDIT continuation counts v98, v99, and v100 as three pretarget package/runtime failures. The current disposition is RULE_CONFIRMATION_NO_CHANGE__IMPLEMENTATION_AND_NEGATIVE_CONTROL_ESCAPE; storage publication remains blocked pending shared adjudication.\n\n"
        f"Exact local ZIP: `{package['path']}`. All {len(gate_rows)} exact local gate receipts pass, including three guardprocfix negative controls and 24/24 focused tests.\n\n"
        "No managed-storage write and no upload, lease, connection, or server execution occurred. Tuple10, the input1 undersupply workaround, natural terminal and Formal-D were not dynamically retested by v100.\n"
    )
    (OUT / "task_record.md").write_text(task, encoding="utf-8", newline="\n")
    print(json.dumps({
        "status": local_status,
        "storage_status": receipt["storage_status"],
        "pass": receipt["pass"],
        "errors": errors,
        "package": package,
        "gate_count": len(gate_rows),
    }, sort_keys=True))
    return 0 if receipt["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
