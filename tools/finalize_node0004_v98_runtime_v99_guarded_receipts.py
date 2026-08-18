#!/usr/bin/env python3
"""Bind the v98 static failure audit and fully gated local v99 release receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_n4_hw_v98b_lcdup_tuple10"
NEW = "r5_n4_hw_v99b_lcdup_guarded"
ANALYSIS = ROOT / "outputs/conv_node0004_v98b_runtime_failure_analysis"
RELEASE = ROOT / "outputs/conv_node0004_v99b_lcdup_guarded_release6"
ZIP = RELEASE / f"{NEW}.zip"
SOURCE = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/pending/{OLD}.zip"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    extracted = ANALYSIS / f"extracted_v98b/{OLD}"
    audit = ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"
    report_path = ANALYSIS / "runtime_failure_rootcause_report.json"
    report = {
        "schema": "node0004-v98b-runtime-failure-rootcause-report-v1",
        "role_id": "family.conv.serialized",
        "failed_package": OLD,
        "source_package": identity(SOURCE),
        "server_evidence_status": "MISSING_FORMAL_RETURN",
        "user_observation": {
            "reported_install_codex_runs_growth": "MORE_THAN_50_GB",
            "reported_disk_full": True,
            "reported_return_zip": "ABSENT",
            "evidence_class": "USER_OBSERVATION_NOT_EXACT_REMOTE_FILE_IDENTITY",
        },
        "root_classification": {
            "classification": "PACKAGE_LOCAL_UNBOUNDED_OBSERVER_AND_ARCHIVE_AMPLIFICATION",
            "confidence": "HIGH_FOR_REACHABILITY_LOW_FOR_EXACT_REMOTE_MEMBER_ATTRIBUTION",
            "validated_root": False,
            "reason": "Exact package bytes prove multiple unbounded/re-amplifying paths, but no formal return or remote inventory exists to bind the actual 50 GB to one filename.",
        },
        "proven_reachable_growth_mechanisms": [
            {
                "rank": 1,
                "mechanism": "EVERY_CLOCK_EDGE_JSONL",
                "evidence": [
                    "tb_probe/observer_only_wide_causal.svh:124-127 records sig_clk whenever it changes",
                    "tb_probe/observer_only_wide_causal.svh:403 includes sig_clk in the always sensitivity list",
                    "tb_probe/observer_only_wide_causal.svh:385 flushes periodically but has no byte/disk stop"
                ],
                "growth": "Unbounded with simulated owner-clock edges; all rows are written under the attempt evidence tree in install/codex_runs.",
            },
            {
                "rank": 2,
                "mechanism": "UNBOUNDED_SIM_LOG_AND_FULL_DUPLICATE",
                "evidence": [
                    "PREPARE_AND_RUN.sh:207 sends complete simulator output to attempt c0/sim.log without a live size guard",
                    "PREPARE_AND_RUN.sh:143 copies the complete sim.log to evidence/source_bound_causal.log"
                ],
                "growth": "Reachable 2x on a repetitive console/log stream before ZIP staging.",
            },
            {
                "rank": 3,
                "mechanism": "WHOLE_CHUNK_PARSER_ATOMIC_REWRITE",
                "evidence": [
                    "package_tools/node0004_observerwide_event_parser.py:58 reads the complete JSONL into memory",
                    "package_tools/node0004_observerwide_event_parser.py:112-113 serializes and atomically replaces the complete chunk"
                ],
                "growth": "The old and temporary rewritten observer chunks coexist during replacement, doubling peak attempt-tree bytes.",
            },
            {
                "rank": 4,
                "mechanism": "FINALIZER_STAGING_INSIDE_ATTEMPT",
                "evidence": [
                    "package_tools/server_post_sim_return.py:806 creates .return_core_* under attempt_root",
                    "package_tools/server_post_sim_return.py:811-831 copies every return entry into that staging tree before ZIP creation"
                ],
                "growth": "Observer, logs and compile evidence are copied again inside install/codex_runs during finalization.",
            },
            {
                "rank": 5,
                "mechanism": "FRESH_ATTEMPT_RETENTION",
                "evidence": [
                    "PREPARE_AND_RUN.sh creates execution-unique attempt/bootstrap roots",
                    "v98 contains no durable-return-bound exact-attempt cleanup"
                ],
                "growth": "Earlier package-owned attempts can accumulate; exact remote residue is unknown.",
            },
        ],
        "not_primary_or_unproven": [
            {
                "mechanism": "RECURSIVE_LOCAL_INSTALL_COPY",
                "disposition": "RULED_OUT_AS_PRIMARY_BY_PACKAGE_CODE",
                "evidence": "PREPARE_AND_RUN.sh:181 performs one cp -a from package-owned workload/runtime into cfg_root; it does not copy install/codex_runs back into itself.",
            },
            {
                "mechanism": "REPEATED_SOURCE_CAPTURE",
                "disposition": "FINITE_ONE_SHOT_IN_PACKAGE_CODE",
                "evidence": "Source identity capture is invoked once after compile and is not a periodic writer.",
            },
            {
                "mechanism": "SIMULATOR_OR_COMPILE_ARTIFACT",
                "disposition": "PLAUSIBLE_CONTRIBUTOR_NOT_IDENTITY_BOUND",
                "evidence": "The native compile/run directories are under the attempt tree, but no return or remote inventory binds their actual size.",
            },
            {
                "mechanism": "WAVEFORM",
                "disposition": "DISABLED_BY_EXACT_PACKAGE",
                "evidence": "DUMP_VCD=0, DUMP_FSDB=0 and TB_DUMP_FSDB=0; no VPD/FSDB/VCD/FST writer is enabled.",
            },
        ],
        "v98_safeguard_audit": {
            "wall_timeout_seconds": 21600,
            "observer_soft_warning_bytes": 100000000,
            "observer_hard_limit": None,
            "live_observer_size_stop": False,
            "live_sim_log_size_stop": False,
            "live_attempt_growth_stop": False,
            "minimum_disk_free_reserve": False,
            "post_return_attempt_cleanup": False,
            "why_disk_exhaustion_preceded_stop": "The 100 MB threshold was only a post-return warning, while the only live stop was the six-hour wall timeout. Disk exhaustion can therefore occur first.",
        },
        "package_build_failure_rule_audit": identity(audit),
        "claim_boundary": "Static reachability and safeguard audit of exact v98 package bytes. No exact remote filename, byte count, execution phase, target entry, DUT result or server residue is claimed without a formal return.",
        "conflicts": [],
    }
    write_json(report_path, report)

    gate_rows = []
    for path in sorted((RELEASE / "gates").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        gate_rows.append({**identity(path), "pass": value.get("pass"), "errors": value.get("errors", [])})
    if not gate_rows or any(row["pass"] is not True or row["errors"] for row in gate_rows):
        raise RuntimeError("one or more release6 gates did not pass")
    package_receipt_path = RELEASE / "mainline_package_receipt.json"
    package_receipt = {
        "schema": "node0004-v99b-lcdup-guarded-mainline-package-receipt-v1",
        "role_id": "family.conv.serialized",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": NEW,
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "package": identity(ZIP),
        "source_package": identity(SOURCE),
        "runtime_failure_analysis": identity(report_path),
        "package_build_failure_rule_audit": identity(audit),
        "previous_progress": "v97 closed the one-missing-metadata-tuple boundary and local mapper A/B proved the LC9-to-LC3 duplication mathematically/address/command/traffic equivalent with one additional LC. v98 preserved that target but produced no return after reported install/codex_runs growth above 50 GB and disk exhaustion.",
        "current_purpose": "Run the identical LC-duplication tuple10/natural-terminal/Formal-D diagnostic with deterministic clock-edge exclusion and compile/simulation/finalization operational guards, fail-closed partial return, complete process reap and exact-attempt cleanup.",
        "changed_behavior": {
            "functional_rtl_config_numeric_workload_golden": "FROZEN_BYTE_EQUAL_OR_IDENTITY_NORMALIZED_EQUAL_TO_V98",
            "retired_ack_comparator": "ABSENT",
            "waveform": "DISABLED_DUMP_VCD0_DUMP_FSDB0_TB_DUMP_FSDB0",
            "clock_transport": "INITIAL_END_PLUS_PERIODIC_262144_OWNER_CYCLE_HEARTBEAT_NO_PER_EDGE_JSONL",
            "compile_log_stop_bytes": 200000000,
            "simulation_log_stop_bytes": 200000000,
            "observer_stop_bytes": 400000000,
            "compile_growth_stop_bytes": 8000000000,
            "simulation_growth_stop_bytes": 800000000,
            "finalization_growth_stop_bytes": 2000000000,
            "minimum_disk_free_bytes": 20000000000,
            "simulation_wall_seconds": 3600,
            "guard_disposition": "STOP_WHOLE_ATTEMPT_PRESERVE_ALL_COMPLETED_ROWS_DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "post_return_exact_attempt_cleanup": True,
        },
        "footprint_contract": {
            "maximum_transient_install_codex_runs_growth_over_initial_bytes": 10800000000,
            "persistent_exact_attempt_bytes_after_durable_return": 0,
            "result_root_return_retained": True,
            "foreign_siblings_preserved": True,
        },
        "gates": gate_rows,
        "unique_future_command": f"bash {NEW}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "server_actions_performed": [],
        "storage_manager_called": False,
        "claim_boundary": "Local exact-tree/final-ZIP/static negative-control gates only. Production compile, simulation, resource-guard behavior, tuple10, natural terminal, Formal-D, E3, E4 and E5 remain unproven until a formal return.",
        "conflicts": [],
    }
    write_json(package_receipt_path, package_receipt)

    task = RELEASE / "task_record.md"
    task.write_text(
        "# Serialized Conv v98 runtime failure audit and guarded v99 package\n\n"
        "## Previous progress\n\n"
        "v97 validated that the original configuration supplied one fewer 32-unit Memory_AG input-1 metadata tuple than prepared data required. The user-authorized local mapper A/B then proved that copying logical LC9 to dormant LC3 and routing PE1.inport2 to LC3 preserves ordered addresses, output mathematics, command count, data-plane traffic and configured cycle bound. The only cost is one additional LC (15/20 active, five spare) plus one 64-bit configuration word.\n\n"
        "## Current purpose and v98 failure\n\n"
        "v98 was the targeted production confirmation for tuple 10, natural terminal and Formal-D. The user reported more than 50 GB under install/codex_runs, disk exhaustion and no return ZIP. Because no formal return exists, the exact remote filename and target-entry state cannot be asserted. Static analysis of the exact pending ZIP nevertheless proves a package defect: the observer recorded the deterministic owner clock on every edge into unbounded JSONL; sim.log was unbounded and copied in full; the parser atomically rewrote the whole chunk; finalization staged the whole return inside the attempt tree; and old attempts were not removed. The active 100 MB observer threshold was warning-only and evaluated after return, while the only live stop was six hours.\n\n"
        "## Rule/build audit\n\n"
        "PACKAGE_BUILD_FAILURE_RULE_AUDIT is triggered and recorded. This is both a package implementation escape and a shared-rule gap: the current observer rule forbids hard event retention caps but does not distinguish silent truncation from safely terminating the whole attempt while keeping every completed row. The narrow proposal retains no sampling/truncation/deletion and requires compile/simulation/finalization growth guards, disk reserve, TERM-wait-KILL/reap, partial return and durable-return-bound cleanup. No shared rule file was modified.\n\n"
        "## Fresh package\n\n"
        f"`{NEW}` preserves the v98 mapper/config/workload/numeric/golden/functional-RTL target and keeps the retired ACK comparator absent. It removes only redundant per-edge clock JSONL; initial/end clock state, exact timestamps and a 262,144-owner-cycle heartbeat remain. Compile and sim logs stop at 200 MB, observer at 400 MB, compile growth at 8 GB, simulation growth at 800 MB, finalization growth at 2 GB, disk reserve at 20 GB and simulation wall at 60 minutes. A guard stop terminates/reaps the whole process tree, retains all completed evidence and marks DIAGNOSTIC_EVIDENCE_INCOMPLETE. After a durable return, exact run/bootstrap leaves are removed while the unique return and foreign siblings remain. Maximum transient install/codex_runs growth is 10.8 GB over the initial attempt; persistent exact-attempt bytes after return are zero.\n\n"
        "## Validation and status\n\n"
        "All exact release6 gates pass: package preflight, bash syntax, full HDL and lexical, frozen mapper surface, observer-only/source-bound, runner/compile-core, runtime-preflight noninterference, post-sim, six-exit/current first-fresh, operational negative controls, deterministic ZIP, release admission and active-rule audit.\n\n"
        "Status: `PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE / STORAGE_WAIT_MAINLINE_SERIAL_RELEASE`.\n\n"
        f"Future command after storage publication and separate run authorization: `bash {NEW}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`.\n\n"
        "No upload, lease, connection, server execution or storage-manager action occurred. Local gates do not prove production compile/simulation, tuple10, natural terminal, Formal-D, E3, E4 or E5.\n",
        encoding="utf-8", newline="\n",
    )
    print(package_receipt_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
