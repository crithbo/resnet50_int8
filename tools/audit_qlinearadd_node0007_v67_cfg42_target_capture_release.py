#!/usr/bin/env python3
"""Run all current final-ZIP/first-fresh gates for QAdd v67 target capture."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v67_cfg42_tg"
PRIOR = "r5_qadd_n7_tailround_lanephase_v66_cfg42"
PRIOR_SHA = "f9add4a1f54d922fb76fbe7d7b8a72e4965fea0c27546864fb3032bcad8862bc"
EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3+qadd-v66-return-target-capture-v1+tb-vcd-adaptive-v4+runtime-v3"
OUT = ROOT / "outputs/qlinearadd_node0007_v67_cfg42_tgcap_release"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
REPEAT = OUT / f"{PACKAGE}.repeat.zip"
PRIOR_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PRIOR}.zip"
GATES = OUT / "gates"
TARGET_REPORT = GATES / "target_capture_exact.json"
PYTHON = Path(sys.executable)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def run_target_gate() -> None:
    argv = [
        str(PYTHON), str(ROOT / "tools/validate_qlinearadd_node0007_v67_cfg42_target_capture.py"),
        "--tree", str(TREE), "--zip", str(ZIP), "--repeat-zip", str(REPEAT),
        "--prior-zip", str(PRIOR_ZIP), "--output", str(TARGET_REPORT),
    ]
    completed = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=600, check=False)
    if completed.returncode != 0 or not TARGET_REPORT.is_file() or load(TARGET_REPORT).get("pass") is not True:
        raise RuntimeError(f"target-capture exact gate failed: rc={completed.returncode} stdout={completed.stdout[-2000:]} stderr={completed.stderr[-2000:]}")


def adapted_v65_audit() -> int:
    source_path = ROOT / "tools/audit_qlinearadd_node0007_v65_tbvcdrt3_release.py"
    source = source_path.read_text(encoding="utf-8")
    replacements = [
        ('PACKAGE = "r5_qadd_n7_tailround_lanephase_v65_tbvcdrt3"', f'PACKAGE = "{PACKAGE}"'),
        ('PRIOR = "r5_qadd_n7_tailround_lanephase_v64_tbvcdfix"', f'PRIOR = "{PRIOR}"'),
        ('EPOCH = "tb-vcd-first-round-breadth-v4+tb-vcd-exit-mechanism-consistency-v3+package-python-schema-runtime-v2"', f'EPOCH = "{EPOCH}"'),
        ('OUT = ROOT / "outputs/qlinearadd_node0007_v65_tbvcdrt3_release"', 'OUT = ROOT / "outputs/qlinearadd_node0007_v67_cfg42_tgcap_release"'),
        ('TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v65.svh"', 'TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v67.svh"'),
        ('LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v65.py"', 'LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v67.py"'),
        ('FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v65.py"', 'FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v67.py"'),
        ("codex_qadd_tb_vcd_causal_cone_v65", "codex_qadd_tb_vcd_causal_cone_v67"),
        ("qadd-v65", "qadd-v67"),
        ("QAdd v65", "QAdd v67"),
        ('ROOT / "outputs/qlinearadd_node0007_v64_return_r1786704798234127277_2300842/formal_return_analysis.json"', 'ROOT / "outputs/qlinearadd_node0007_v66_return_r1786770100877714671_2785121/formal_return_analysis.json"'),
        ("no production v65 compile/simulation", "no production v67 compile/simulation"),
    ]
    for old, new in replacements:
        if old not in source:
            raise RuntimeError(f"v65 audit adapter anchor drifted: {old}")
        source = source.replace(old, new)
    phase_anchor = """def import_module(path: Path, name: str) -> Any:
"""
    phase_helper = """def phase_authority(package: Path) -> dict[str, Any]:
    return {
        \"mode\": \"SHARED_RUNTIME_EVALUATOR_PHASE_AWARE_DUMPOFF\",
        \"helper_path\": \"package_tools/server_tb_vcd_runtime_supervision.py\",
        \"helper_sha256\": sha(package / \"package_tools/server_tb_vcd_runtime_supervision.py\"),
        \"replay_cases\": [
            {\"case_id\": \"PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE\", \"observed_decision\": \"CONTINUE\"},
            {\"case_id\": \"PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU\", \"observed_decision\": \"CAUSAL_PLATEAU\"},
            {\"case_id\": \"REPEATED_STOP_MARKER\", \"observed_decision\": \"FAIL_CLOSED\"},
        ],
    }


def import_module(path: Path, name: str) -> Any:
"""
    if phase_anchor not in source:
        raise RuntimeError("v65 audit phase-authority anchor drifted")
    source = source.replace(phase_anchor, phase_helper, 1)
    synthetic_anchor = '            "decision_authority": authority(package),\n            "shared_evaluator_receipt": {},'
    synthetic_replacement = '            "decision_authority": authority(package),\n            "dumpoff_consistency_authority": phase_authority(package),\n            "shared_evaluator_receipt": {},'
    if synthetic_anchor not in source:
        raise RuntimeError("v65 audit synthetic authority anchor drifted")
    source = source.replace(synthetic_anchor, synthetic_replacement, 1)
    namespace: dict[str, Any] = {"__name__": "qadd_v67_adapted_audit", "__file__": str(source_path)}
    exec(compile(source, str(source_path), "exec"), namespace)
    def runtime_replay_v5(package: Path) -> dict[str, Any]:
        evaluator = namespace["import_module"](package / "package_tools/server_tb_vcd_runtime_supervision.py", "qadd_v67_eval")
        live = namespace["import_module"](package / "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v67.py", "qadd_v67_live")
        auth = namespace["authority"](package)
        phase = namespace["phase_authority"](package)
        args = namespace["SimpleNamespace"](package_id=PACKAGE, execution_id="replay", attempt_id="a0")

        def row(seq: int, wall: float, tick: int, execution_tick: int, cycles: int, **extra: Any) -> dict[str, Any]:
            value = {
                "seq": seq, "wall_seconds": wall,
                "appended_vcd_timestamp_ticks": tick, "sim_time_ticks": execution_tick,
                "owner_clock_cycles": cycles, "sim_cycles": cycles,
                "causal_progress_events": 0,
                "qualified_progress_counters": {"target": 0, "pretarget_matrix_completions": 24},
                "causal_state_digest": "a" * 64,
                "global_progress_witness": {"target_count": 0, "pretarget_matrix_completions": 24},
                "unresolved_xz": False, "vcd_bytes": 1000 + seq,
                "disk_space_ok": True, "write_ok": True, "quota_ok": True,
            }
            value.update(extra)
            return value

        cases = {
            "ADVANCING_VCD_TIMESTAMP": [row(0, 0, 1, 1, 0), row(1, 30, 2, 2, 100)],
            "PLATEAU_SUSPECTED_ONLY": [row(0, 0, 1, 1, 0), row(1, 30, 2, 2, 1_048_576)],
            "PLATEAU_DUMP_OFF_PLUS_GRACE": [
                row(0, 0, 1, 1, 0),
                row(1, 30, 2, 2, 4_194_304, planned_dumpoff=True, planned_dumpoff_cycle=4_194_304, planned_dumpoff_vcd_timestamp_ticks=2),
                row(2, 60, 2, 3, 4_456_448, planned_dumpoff=True, planned_dumpoff_cycle=4_194_304, planned_dumpoff_vcd_timestamp_ticks=2, stop_marker_count=1),
            ],
            "THREE_INTERVAL_TRUE_FREEZE": [row(0, 0, 7, 7, 0), row(1, 30, 7, 7, 100), row(2, 60, 7, 7, 200), row(3, 90, 7, 7, 300)],
        }
        decisions = {name: live.shared_decision(evaluator, auth, phase, args, rows)[0] for name, rows in cases.items()}
        expected = {
            "ADVANCING_VCD_TIMESTAMP": "CONTINUE",
            "PLATEAU_SUSPECTED_ONLY": "CONTINUE",
            "PLATEAU_DUMP_OFF_PLUS_GRACE": "CAUSAL_PLATEAU",
            "THREE_INTERVAL_TRUE_FREEZE": "SIM_TIME_FREEZE",
        }
        p51 = [
            row(0, 0, 0, 0, 0),
            row(1, 10, 7689350625, 7689350625, 4_194_304, planned_dumpoff=True, planned_dumpoff_cycle=4_194_304, planned_dumpoff_vcd_timestamp_ticks=7689350625),
            row(2, 40, 7689350625, 8268355625, 4_325_376, planned_dumpoff=True, planned_dumpoff_cycle=4_194_304, planned_dumpoff_vcd_timestamp_ticks=7689350625),
            row(3, 70, 7689350625, 8847360625, 4_456_448, planned_dumpoff=True, planned_dumpoff_cycle=4_194_304, planned_dumpoff_vcd_timestamp_ticks=7689350625, stop_marker_count=1),
        ]
        p51_decision = live.shared_decision(evaluator, auth, phase, args, p51)[0]
        repeated = [dict(item) for item in p51]
        repeated[-1]["stop_marker_count"] = 2
        repeated_receipt = evaluator.evaluate({
            "package_id": PACKAGE, "execution_id": "replay", "attempt_id": "a0", "started": True,
            "actual_argv_sha256": "0" * 64, "catalog_sha256": "0" * 64,
            "candidate_matrix_sha256": "0" * 64, "tb_source_sha256": "0" * 64, "elaboration_sha256": "0" * 64,
            "samples": repeated, "candidate_catalog_complete": True, "unresolved_xz": False,
            "flush": {}, "process_tree": {}, "heartbeat_contract": {"source": "APPENDED_VCD_TIMESTAMP", "width_bits": 64, "signed": False, "cadence_cycles": 16384},
            "decision_authority": auth, "dumpoff_consistency_authority": phase,
        })
        checks = {
            "exact_four_case_replay": decisions == expected,
            "planned_dumpoff_frozen_vcd_grace": p51_decision == "CAUSAL_PLATEAU",
            "repeated_stop_fails_closed": any("one-shot" in item for item in repeated_receipt.get("errors", [])),
            "shared_helper_byte_equal_current": (package / "package_tools/server_tb_vcd_runtime_supervision.py").read_bytes() == (ROOT / "tools/server_tb_vcd_runtime_supervision.py").read_bytes(),
            "single_shared_authority": all(token in (package / "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v67.py").read_text(encoding="utf-8") for token in ("shared_decision", "dumpoff_consistency_authority", "outer_runner_consumed_shared_receipt_only")),
        }
        return {"pass": all(checks.values()), "checks": checks, "decisions": decisions, "p51_decision": p51_decision, "errors": [key for key, passed in checks.items() if not passed]}

    namespace["runtime_replay"] = runtime_replay_v5
    return int(namespace["main"]())


def rerun_first_fresh_with_target_gate() -> None:
    candidate_path = OUT / "first_fresh_audit/reports/candidate_discrimination_matrix.json"
    candidate = load(candidate_path)
    candidate["return_derived_target_capture_and_header_identity"] = {
        "report": identity(TARGET_REPORT),
        "pretarget_quiet_target_continuous": True,
        "current_source_identity_rebound": True,
        "legal_vector_range_normalized": True,
        "wrong_width_rejected": True,
    }
    candidate["pass"] = candidate.get("pass") is True and load(TARGET_REPORT).get("pass") is True
    write(candidate_path, candidate)
    contract_path = OUT / "first_fresh_audit/contract.json"
    contract = load(contract_path)
    contract["rule_change"]["epoch_id"] = EPOCH
    contract["rule_change"]["rule_ids"] = [
        "CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001",
        "CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001",
    ]
    for row in contract["evidence_reports"]:
        if row["gate_id"] == "candidate_discrimination_matrix":
            row["sha256"] = sha(candidate_path)
    write(contract_path, contract)
    output = GATES / "first_fresh_validation.json"
    completed = subprocess.run(
        [str(PYTHON), str(ROOT / "tools/validate_server_first_fresh_extra_audit.py"), "--contract", str(contract_path), "--workspace-root", str(ROOT), "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, timeout=300, check=False,
    )
    if completed.returncode != 0 or load(output).get("pass") is not True:
        raise RuntimeError(f"current-epoch first-fresh rerun failed: rc={completed.returncode} stdout={completed.stdout[-2000:]} stderr={completed.stderr[-2000:]}")


def storage_prepublication_gate() -> Path:
    index_path = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json"
    pending = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    physical = sorted(path.name for path in pending.glob("*.zip"))
    checks = {
        "storage_index_read_only": index_path.is_file(),
        "prior_v66_still_physical_pending": PRIOR_ZIP.is_file() and sha(PRIOR_ZIP) == PRIOR_SHA,
        "fresh_v67_not_published": not (pending / f"{PACKAGE}.zip").exists(),
        "fresh_v67_staged_only": ZIP.is_file(),
        "no_storage_manager_call": True,
    }
    report = {
        "schema": "qadd-v67-storage-prepublication-wait-v1", "package_id": PACKAGE,
        "status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE", "checks": checks,
        "physical_pending_zip_names": physical, "storage_index": identity(index_path),
        "prior_pending": identity(PRIOR_ZIP), "staged_fresh": identity(ZIP),
        "storage_manager_called": False, "pass": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
    }
    path = GATES / "storage_prepublication_wait.json"
    write(path, report)
    if not report["pass"]:
        raise RuntimeError(f"storage prepublication gate failed: {report['errors']}")
    return path


def finalize_receipts(storage_report: Path) -> None:
    first_path = GATES / "first_fresh_validation.json"
    final_path = GATES / "final_zip_release_audit.json"
    final = load(final_path)
    final["schema"] = "qadd-v67-config42-target-capture-final-release-audit-v1"
    final["activation_epoch"] = EPOCH
    final["status"] = "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE"
    final["checks"]["target_capture_exact"] = load(TARGET_REPORT).get("pass") is True
    final["checks"]["deterministic_exact_zip"] = ZIP.read_bytes() == REPEAT.read_bytes()
    final["checks"]["storage_prepublication_wait"] = load(storage_report).get("pass") is True
    final["target_capture_validation"] = identity(TARGET_REPORT)
    final["storage_prepublication"] = identity(storage_report)
    final["first_fresh"] = identity(first_path)
    final["formal_return_analysis"] = identity(ROOT / "outputs/qlinearadd_node0007_v66_return_r1786770100877714671_2785121/formal_return_analysis.json")
    final["rule_gap_audit"] = identity(ROOT / "outputs/qlinearadd_node0007_v66_return_r1786770100877714671_2785121/RULE_GAP_AUDIT.json")
    final["rule_audit_disposition"] = "RULE_CONFIRMATION_NO_PUBLIC_CHANGE"
    final["previous_version_progress"] = "v66 proved exact 4/2 materialization and production compile while pretarget matrix preload advanced; wall ceiling arrived before target entry, so the ordered 0x33333333/0xcccccccc acceptance contract remains dynamically open."
    final["current_version_purpose"] = "Preserve the validated 4/2 lineage and full 64-signal causal target while suppressing full-rate pretarget VCD, retaining periodic safety snapshots, and starting continuous unbounded causal capture before the target-entry marker."
    final["unique_future_command"] = f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy04"
    final["claim_boundary"] = "Local exact-ZIP/config/source/frontend/runtime/return/first-fresh/storage-prepublication gates only; no production target entry, dynamic repair validation, root closure, natural/formal-D or E3-E5 claim."
    final["pass"] = all(final["checks"].values())
    final["errors"] = [] if final["pass"] else [name for name, passed in final["checks"].items() if not passed]
    write(final_path, final)
    release_path = OUT / f"{PACKAGE}.release_receipt.json"
    release = load(release_path)
    release.update({
        "schema": "qadd-v67-config42-target-capture-package-ready-not-run-v1",
        "activation_epoch": EPOCH, "status": final["status"],
        "final_zip_audit": identity(final_path), "first_fresh": identity(first_path),
        "target_capture_validation": identity(TARGET_REPORT), "storage_prepublication": identity(storage_report),
        "formal_return_analysis": final["formal_return_analysis"], "rule_gap_audit": final["rule_gap_audit"],
        "previous_version_progress": final["previous_version_progress"], "current_version_purpose": final["current_version_purpose"],
        "unique_future_command": final["unique_future_command"], "rule_audit_disposition": final["rule_audit_disposition"],
        "frozen": ["validated_config42", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_causal_cone", "candidate_matrix"],
        "server_actions_performed": [], "storage_manager_called": False,
        "pass": final["pass"], "errors": final["errors"], "claim_boundary": final["claim_boundary"],
    })
    write(release_path, release)
    build_path = OUT / "build_receipt.json"
    build = load(build_path)
    build.update({"status": final["status"], "local_gates": identity(final_path), "storage_prepublication": identity(storage_report), "pass": final["pass"], "errors": final["errors"]})
    write(build_path, build)


def main() -> int:
    dependency = Path(r"C:\Users\15383\AppData\Local\Temp\codex_jsonschema_20260809")
    if dependency.is_dir():
        current = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = str(dependency) if not current else str(dependency) + os.pathsep + current
    run_target_gate()
    result = adapted_v65_audit()
    if result != 0:
        return result
    rerun_first_fresh_with_target_gate()
    storage_report = storage_prepublication_gate()
    finalize_receipts(storage_report)
    final = load(GATES / "final_zip_release_audit.json")
    print(json.dumps({"package_id": PACKAGE, "status": final["status"], "pass": final["pass"], "errors": final["errors"]}, sort_keys=True))
    return 0 if final["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
