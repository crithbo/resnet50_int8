#!/usr/bin/env python3
"""Aggregate v103 local gates and prepare an independent-audit handoff."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v103b_lcdup_obsfix"
OUT = ROOT / "outputs/conv_node0004_v103b_lcdup_obsfix_release1"
ZIP = OUT / f"{PACKAGE}.zip"
GATES = OUT / "gates"
TREE = OUT / "build" / PACKAGE
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
    ]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "outputs/.local_gate_deps")
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", *modules], cwd=ROOT, env=environment,
        capture_output=True, text=True, timeout=180, check=False,
    )
    output = completed.stdout + completed.stderr
    passed = completed.returncode == 0 and "Ran 158 tests" in output and output.rstrip().endswith("OK")
    report = {
        "schema": "node0004-v103b-focused-regression-v1", "package_id": PACKAGE,
        "pass": passed, "errors": [] if passed else ["focused regression did not pass 158/158"],
        "modules": modules, "expected_tests": 158, "exit_code": completed.returncode,
        "output_tail": output[-8192:],
        "claim_boundary": "Current observer/guard/release/return shared regression only; no production VCS or DUT claim.",
    }
    write(GATES / "focused_regression.json", report)
    return report


def semantic_binding() -> dict[str, Any]:
    registry_path = ROOT / "contracts/server_package_build_gate_registry_v1.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    selected = {row["gate_id"]: str(row.get("semantic_version")) for row in registry["gates"] if row.get("gate_id") in {"observer_only_wide_causal_final_zip", "first_fresh_extra_audit"}}
    manifest = json.loads((TREE / "package_manifest.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    if selected != {"observer_only_wide_causal_final_zip": "5", "first_fresh_extra_audit": "6"}:
        errors.append("current observer/first-fresh semantic versions differ")
    if manifest.get("observer_only_semantic_version") != 5 or manifest.get("first_fresh_semantic_version") != 6:
        errors.append("manifest semantic versions differ")
    if manifest.get("build_gate_registry_sha256") != sha(registry_path):
        errors.append("manifest build-gate registry identity differs")
    report = {
        "schema": "node0004-v103b-build-gate-semantic-binding-v1", "package_id": PACKAGE,
        "pass": not errors, "errors": errors, "semantic_versions": selected,
        "registry": identity(registry_path),
        "claim_boundary": "Current build-gate semantic identity only; no production execution claim.",
    }
    write(GATES / "build_gate_semantic_v5_first_fresh_v6.json", report)
    return report


def production_shaped_preflight() -> dict[str, Any]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="node0004-v103-production-shaped-") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(ZIP) as archive:
            archive.extractall(root)
        package = root / PACKAGE
        before = {p.relative_to(package).as_posix(): sha(p) for p in package.rglob("*") if p.is_file()}
        preflight = subprocess.run(
            [sys.executable, "-B", str(package / "package_tools/package_release_preflight.py"),
             "preflight", "--package-root", str(package)],
            cwd=package, capture_output=True, text=True, timeout=60, check=False,
        )
        after = {p.relative_to(package).as_posix(): sha(p) for p in package.rglob("*") if p.is_file()}
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        observer = (package / "tb_probe/observer_only_wide_causal.svh").read_text(encoding="utf-8")
        bridge = (package / "package_tools/node0004_observer_counter_guard_bridge.py").read_text(encoding="utf-8")
        cleanup = (package / "package_tools/server_package_attempt_cleanup.py").read_text(encoding="utf-8")
        guard = package / "package_tools/server_observer_operational_guard_v2.py"
        manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
        simulation_lines = [line for line in runner.splitlines() if "supervise-phase --phase simulation" in line]

        checks = {
            "clean_exact_zip_runtime_preflight": preflight.returncode == 0 and before == after,
            "compile_argv_and_actual_source_capture": all(token in runner for token in ("compile_argv=(make -f Makefile.tb_NDP_Top_new_phy compile", "node0004_actual_compile_source_identity.py", "node0004_observerwide_source_identity.py", "--target-instance")),
            "source_bound_xmr_and_full_hdl_gate": json.loads((GATES / "source_bound_final_zip.json").read_text()).get("pass") is True and json.loads((GATES / "hdl.json").read_text()).get("pass") is True,
            "simulation_started_after_simv_exists": "[ -x \"$simv\" ]" in runner and runner.find("sim_started=true") < runner.find("supervise-phase --phase simulation"),
            "observer_64bit_time_and_counter_transport": "codex_counter_time_ps = $time" in observer and "$rtoi" not in observer and "$realtime" not in observer and "+CODEX_COUNTER_CHUNK=$counter_chunk" in runner,
            "accept_qualified_tuple_metadata_and_downstream_counters": "cnt_metadata_emit = cnt_metadata_emit + 2" in observer and "if (sig_mem_tag_valid) begin cnt_metadata_emit" not in observer and "sig_wdata_valid[0] && sig_wdata_ready[0]" in observer and "sig_wdata_valid[1] && sig_wdata_ready[1]" in observer,
            "complete_state_global_witness_plateau": all(token in observer for token in ("reg [255:0] codex_causal_state", "codex_global_witness", "$isunknown", "codex_plateau_cycles >= 1048576", "PLANNED_PLATEAU_STOP")),
            "single_wall_and_exit_authority": len(simulation_lines) == 1 and "--timeout 3660" in simulation_lines[0] and "server_observer_runtime_supervision.py" not in simulation_lines[0] and "--timeout 3600" not in runner,
            "completed_guard_before_return_parse": "trap 'finalize $?' EXIT" in runner and "node0004_observer_counter_guard_bridge.py" in runner and "node0004_observerwide_event_parser.py" in runner and "process_fully_reaped" in bridge,
            "pid_start_time_term_kill_reap_surface": sha(guard) == manifest.get("canonical_guard_sha256") and all(token in guard.read_text(encoding="utf-8") for token in ("start_time_ticks", "TERM", "KILL", "process_fully_reaped", "owned_process_identities_remaining")),
            "durable_return_no_overwrite_cleanup_order": all(token in runner for token in ("RETURN_PRESERVED_AFTER_FINALIZATION_GUARD_FAILURE", "DURABLE_RETURN_RECEIPT", "cleanup-after-durable-return", "--finalization-guard-receipt", "owned_process_identities_remaining")) and "finalization_guard_receipt" in cleanup,
            "process_and_plateau_negative_controls": json.loads((GATES / "observer_runtime_fix.json").read_text()).get("pass") is True,
            "release_and_first_fresh_conjunction": json.loads((GATES / "release_admission.json").read_text()).get("pass") is True and json.loads((GATES / "first_fresh.json").read_text()).get("pass") is True,
        }
        for name, passed in checks.items():
            if not passed:
                errors.append(name)
        report = {
            "schema": "node0004-v103b-production-shaped-preflight-checklist-v1", "package_id": PACKAGE,
            "pass": not errors, "errors": errors, "checks": checks,
            "preflight": {"exit_code": preflight.returncode, "stdout": preflight.stdout[-4096:], "stderr": preflight.stderr[-4096:], "tree_unchanged": before == after},
            "exact_zip": identity(ZIP),
            "limitations": ["No local gate substitutes for the first real Linux/VCS compile, XMR elaboration, simv execution, tuple10, natural terminal or Formal-D proof."],
            "claim_boundary": "Production-shaped exact-ZIP static/dry-run/preflight checklist only; no production server execution claim.",
        }
    write(GATES / "production_shaped_preflight.json", report)
    return report


def main() -> int:
    focused = focused_regression()
    semantic = semantic_binding()
    production = production_shaped_preflight()
    expected = [
        "active_rule_registry.json", "build_gate_semantic_v5_first_fresh_v6.json",
        "deterministic_zip.json", "first_fresh.json", "focused_regression.json", "hdl.json",
        "lexical_tree.json", "lexical_zip.json", "observer_only_final_zip.json",
        "observer_runtime_fix.json", "operational_boundary_final_zip.json", "post_sim.json",
        "production_shaped_preflight.json", "release_admission.json", "runner_tree.json",
        "runner_zip.json", "runtime_preflight.json", "source_bound_final_zip.json",
    ]
    errors: list[str] = []
    gates: list[dict[str, Any]] = []
    for name in expected:
        path = GATES / name
        if not path.is_file():
            errors.append(f"gate absent: {name}")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass") is not True:
            errors.append(f"gate failed: {name}")
        gates.append({**identity(path), "pass": value.get("pass"), "errors": value.get("errors", [])})
    if not focused["pass"] or not semantic["pass"] or not production["pass"]:
        errors.append("new aggregate gate failed")

    package = identity(ZIP)
    sidecar = OUT / f"{PACKAGE}.zip.sha256"
    sidecar.write_text(f"{package['sha256']}  {PACKAGE}.zip\n", encoding="ascii", newline="\n")
    audit = {
        "schema": "node0004-v103b-final-zip-local-audit-v1", "package_id": PACKAGE,
        "pass": not errors, "errors": errors, "package": package, "sidecar": identity(sidecar),
        "gate_count": len(gates), "expected_gate_count": len(expected), "gates": gates,
        "analysis": {name: identity(ANALYSIS / name) for name in ("formal_return_analysis.json", "RULE_GAP_AUDIT.json", "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json", "analysis_state.json", "checkpoints.jsonl", "report.md")},
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE" if not errors else "LOCAL_GATE_FAILURE",
        "review_status": "WAIT_INDEPENDENT_PACKAGE_AUDIT",
        "publish_authorized": False, "storage_manager_called": False, "server_actions_performed": [],
        "claim_boundary": "Family local gates and audit handoff only; independent package audit, production Linux/VCS, tuple10, natural terminal, Formal-D and E3-E5 remain open.",
    }
    audit_path = OUT / "final_zip_local_audit.json"; write(audit_path, audit)
    handoff = {
        "schema": "node0004-v103b-independent-package-audit-handoff-v1", "package_id": PACKAGE,
        "status": audit["status"], "review_status": "WAIT_INDEPENDENT_PACKAGE_AUDIT",
        "package": package, "sidecar": identity(sidecar), "final_audit": identity(audit_path),
        "gate_receipts": gates, "production_shaped_preflight": identity(GATES / "production_shaped_preflight.json"),
        "required_independent_checks": ["exact ZIP/sidecar/manifest/CRC", "compile argv and actual source/XMR binding", "simv start ordering", "64-bit observer counters", "complete-state/global-witness plateau", "single 3660-second wall authority", "completed guard before parse/return", "TERM-wait-KILL and PID+start-time reap", "durable return no-overwrite and cleanup ordering"],
        "publish_authorized": False,
        "claim_boundary": "Handoff material for an independent second audit; this receipt does not itself authorize publication or execution.",
    }
    handoff_path = OUT / "INDEPENDENT_PACKAGE_AUDIT_HANDOFF.json"; write(handoff_path, handoff)
    receipt = {
        "schema": "node0004-v103b-mainline-package-receipt-v1", "role_id": "family.conv.serialized",
        "owner_epoch": 2, "registry_epoch": 6, "package_id": PACKAGE,
        "status": audit["status"], "review_status": "WAIT_INDEPENDENT_PACKAGE_AUDIT",
        "pass": not errors, "errors": errors, "package": package, "sidecar": identity(sidecar),
        "final_audit": identity(audit_path), "independent_audit_handoff": identity(handoff_path),
        "formal_return_analysis": identity(ANALYSIS / "formal_return_analysis.json"),
        "previous_progress": "v102 compiled, started simulation and entered the frozen copied-LC3/PE8/Memory_AG target, but runtime authority/time/progress defects prevented tuple10 adjudication.",
        "current_purpose": "Preserve config/functional RTL/workload/numeric/golden/LC9-to-LC3/52-signal cone and change only observer counters, plateau, exit, reap and return handling.",
        "frozen_surface": ["config", "functional RTL", "workload", "numeric", "golden", "LC9-to-LC3 mapper semantics", "52-signal causal cone"],
        "changed_surface": ["fresh identity", "64-bit observer time", "accept-qualified counters", "complete-state/global-witness plateau", "single simulation wall/exit authority", "guard-before-return and durable cleanup"],
        "unique_future_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "publish_authorized": False, "storage_status": "STORAGE_WAIT_INDEPENDENT_PACKAGE_AUDIT",
        "storage_manager_called": False, "server_actions_performed": [], "conflicts": [],
        "claim_boundary": audit["claim_boundary"],
    }
    write(OUT / "mainline_package_receipt.json", receipt)
    task = (
        "# Serialized Conv v103 observer/runtime correction\n\n"
        "v102 proved compile, simulation start and target entry, but did not count tuple10 reliably.\n\n"
        "v103 freezes config, functional RTL, workload, numeric/golden data, LC9→LC3 mapper semantics and the 52-signal cone. It changes only 64-bit observer time, accepted-event counters, complete-state/global-witness plateau, one simulation exit authority, PID+start-time reap and durable return ordering.\n\n"
        f"Local disposition: **{audit['status']} / WAIT_INDEPENDENT_PACKAGE_AUDIT**. Exact ZIP `{package['path']}`; {len(gates)}/{len(expected)} local gates PASS.\n\n"
        "No managed-storage write, upload, lease, connection or server run occurred.\n"
    )
    (OUT / "task_record.md").write_text(task, encoding="utf-8", newline="\n")
    print(json.dumps({"pass": not errors, "status": audit["status"], "review_status": "WAIT_INDEPENDENT_PACKAGE_AUDIT", "package": package, "gates": len(gates)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
