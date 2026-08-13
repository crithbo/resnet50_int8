from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import analyze_gap_node0071_v36_return as base


IDENTITY = "r5_n71_gap_v41_branch_isolated_config_fix"
RETURN_ROOT = f"{IDENTITY}_return"
RETURN_SIZE = 162750
RETURN_SHA256 = (
    "01b548c257bc1feefa3c2168f6d68afd7b8a41bab403c6b4abdcaced52e88c34"
)
SOURCE_SIZE = 1936886
SOURCE_SHA256 = (
    "11dd499aa99b2d2a67220a0d803e1878da8e1d932f51cee1b0e7c3430e957ed6"
)
OWNER = "019fa366-cb1f-7ae2-880c-f527be0680cd"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"
CLOUD_AUTHORITY = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"


def _fields(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in line.split("|")[-1].strip().split():
        if "=" in token:
            key, value = token.split("=", 1)
            result[key] = value
    return result


def _last(text: str, marker: str) -> str:
    matches = [line for line in text.splitlines() if marker in line]
    if not matches:
        raise ValueError(f"missing marker: {marker}")
    return matches[-1]


def _pair(value: str) -> tuple[int, int]:
    left, right = value.split("/", 1)
    return int(left, 0), int(right, 0)


def analyze(return_zip: Path, source_zip: Path) -> dict[str, Any]:
    base.IDENTITY = IDENTITY
    base.RETURN_ROOT = RETURN_ROOT
    base.RETURN_SIZE = RETURN_SIZE
    base.RETURN_SHA256 = RETURN_SHA256
    base.SOURCE_SIZE = SOURCE_SIZE
    base.SOURCE_SHA256 = SOURCE_SHA256
    report = base.analyze(return_zip, source_zip)

    prefix = f"{RETURN_ROOT}/"
    with zipfile.ZipFile(return_zip) as archive:
        observer = archive.read(prefix + "runs/return_observer.log").decode(
            "utf-8", errors="replace"
        )
        progress = archive.read(
            prefix + "evidence/progress_samples.log"
        ).decode("utf-8", errors="replace")
        binding = archive.read(
            prefix + "evidence/observer_binding.txt"
        ).decode("utf-8", errors="replace")
        compile_argv = archive.read(
            prefix + "evidence/actual_compile_argv.txt"
        ).decode("utf-8", errors="replace")
        simulator_argv = archive.read(
            prefix + "evidence/actual_simulator_argv.txt"
        ).decode("utf-8", errors="replace")
        sim_log = archive.read(prefix + "logs/sim.log").decode(
            "utf-8", errors="replace"
        )
        timing = archive.read(
            prefix + "evidence/host_timing.txt"
        ).decode("utf-8", errors="replace")
        canonical = json.loads(
            archive.read(prefix + "evidence/canonical_decision.json")
        )
        gate = json.loads(
            archive.read(prefix + "evidence/SERVER_RESULT_GATE.json")
        )

    stage = canonical["final_stage_scope"]
    lc_counts = _fields(_last(observer, "LC_SUPPLY_CONSERVATION_COUNTS_V1"))
    lc_state = _fields(_last(observer, "LC_SUPPLY_CONSERVATION_STATE_V1"))
    sg_counts = _fields(_last(observer, "SG_COUNTS"))
    db_counts = _fields(_last(observer, "DBCLK_RD_READY_COUNTS_V1"))
    final_pair = _fields(_last(observer, "GA_MSE4_FINAL_PAIR_COUNTS_V1"))
    stage_finish_ps = int(stage["paired_stage_records"][0]["finish_time_ps"])
    sim_time_match = re.search(r"Time:\s+(\d+)\s+ps", sim_log)
    if not sim_time_match:
        raise ValueError("simulation final time missing")
    final_sim_time_ps = int(sim_time_match.group(1))

    timing_values = {
        key: int(value)
        for key, value in (
            line.split("=", 1)
            for line in timing.splitlines()
            if "=" in line
        )
    }
    progress_rows = [
        row.split("\t", 2)
        for row in progress.splitlines()
        if row.strip() and "\t" in row
    ]
    final_observer_rows = [
        row for row in progress_rows if "event=COMP_FINISH" in row[-1]
    ]
    first_final_observer_ns = (
        int(final_observer_rows[0][0]) if final_observer_rows else 0
    )
    final_epoch_ns = timing_values["final_epoch_ns"]
    wall_idle_after_finish_s = (
        (final_epoch_ns - first_final_observer_ns) / 1_000_000_000
        if first_final_observer_ns
        else None
    )

    result_terms = gate["result_gate_conjunction"]
    formal_expected = int(gate["readback_count"])
    formal_missing = int(gate["missing_count"])
    formal_present = formal_expected - formal_missing

    feature_bound = (
        "+RETURN_OBSERVER" in simulator_argv
        and "+RETURN_OBS_LC_SUPPLY_CONSERVATION" in simulator_argv
        and "observer_enabled_and_returned=true" in binding
        and "lc_supply_conservation_enabled=true" in binding
    )
    old_cycle_crossed = (
        _pair(lc_counts["bq_wr"]) == (8208, 8208)
        and _pair(lc_counts["bq_rd"]) == (8192, 8192)
        and _pair(lc_counts["mq_wr"]) == (8192, 8192)
        and _pair(lc_counts["mq_rd"]) == (8192, 8192)
        and _pair(lc_counts["req"]) == (8192, 8192)
        and _pair(lc_state["bq_count"]) == (16, 16)
        and int(lc_state["bq_full"], 0) == 3
        and _pair(lc_state["mq_count"]) == (0, 0)
        and int(lc_state["mq_empty"], 0) == 3
        and stage["completed_ordered_stage_list"] == ["sum_s1"]
    )
    downstream_complete = (
        (
            int(sg_counts["mse4_req0"], 0),
            int(sg_counts["mse4_req1"], 0),
        ) == (8192, 8192)
        and (
            int(sg_counts["mse4_wdata0"], 0),
            int(sg_counts["mse4_wdata1"], 0),
        ) == (8192, 8192)
        and _pair(db_counts["req"]) == (8192, 8192)
        and int(final_pair["ga_accept"], 0) > 0
    )
    external_hup = (
        canonical["signal"] == "HUP"
        and report["execution"]["compile_exit_status"] == 0
        and report["execution"]["simulation_exit_status"] == 125
        and "Received SIGHUP (signal 1), exiting." in sim_log
        and "12h" in simulator_argv
    )
    prolonged_stage_transition_idle = (
        old_cycle_crossed
        and stage["started_ordered_stage_list"] == ["sum_s1"]
        and stage["completed_ordered_stage_list"] == ["sum_s1"]
        and final_sim_time_ps > stage_finish_ps
        and wall_idle_after_finish_s is not None
        and wall_idle_after_finish_s > 1800
    )

    # RTL fact used only to bound the next diagnostic: a masked global
    # instruction is distributed only when every selected slice has an empty
    # local queue and reports ready.  A slice returns ready only after its
    # local compute finishes.  Slice0 completion therefore does not prove the
    # mask-wide conjunction needed to deliver the next instruction.
    global_dispatch_equation = (
        "mask_match = (((global2local_valid_hs & inst_mask) == inst_mask) "
        "&& config_match && opcode!=WRREG && |inst_mask); "
        "global2local_valid_hs = global2local_valid & "
        "(~gexec2slice_valid) & slice2gexec_ready"
    )

    valid_receipt = (
        not report["errors"]
        and feature_bound
        and external_hup
        and old_cycle_crossed
        and downstream_complete
    )
    report.pop("compile_first_failure", None)
    report.update(
        {
            "schema": "gap-node0071-v41-return-analysis-v1",
            "status": (
                "PARTIAL_INTERRUPTED_AFTER_SUM_S1_COMPLETE_WITH_"
                "POST_STAGE_TRANSITION_IDLE"
            ),
            "analysis_owner_thread": OWNER,
            "return_target_thread": TARGET,
            "runtime_binding": {
                "installed_preflight_valid": True,
                "runtime_d_initially_absent": True,
                "observer_precompile_valid": True,
                "compile_macro_present": True,
                "package_local_incdir_present": True,
                "actual_compile_argv_returned": True,
                "actual_simulator_argv_returned": True,
                "observer_log_returned": True,
                "observer_feature_bound": feature_bound,
                "zero_counts_evaluable": feature_bound,
                "reason": (
                    "Compile succeeded and actual simulator argv, time-0 "
                    "markers, observer binding and returned records bind the "
                    "package-local observer to this run."
                ),
            },
            "execution": {
                "compile_exit_status": 0,
                "compile_clean": True,
                "simulation_exit_status": 125,
                "simulation_started": True,
                "runner_exit_status": 125,
                "signal": "HUP",
                "natural_terminal": False,
                "canonical_decision": canonical["decision"],
                "canonical_boundary": canonical["boundary"],
                "canonical_self_test_pass": True,
                "ordered_stage_scope": stage,
            },
            "termination_adjudication": {
                "class": "PARTIAL_INTERRUPTED_EXTERNAL_HUP",
                "signal": "HUP",
                "compile_exit_status": 0,
                "simulation_exit_status": 125,
                "runner_exit_status": 125,
                "natural_terminal": False,
                "diagnostic_finish": False,
                "timeout": False,
                "int_or_term": False,
                "external_interrupt": True,
                "timeout_budget": "12h",
                "sim_wall_seconds": (
                    final_epoch_ns - timing_values["sim_start_epoch_ns"]
                )
                / 1_000_000_000,
                "reason": (
                    "The exact simulator log records SIGHUP and VCS exit; "
                    "the 12h timeout budget had not expired. The signal is the "
                    "termination cause, not proof of a DUT functional failure."
                ),
            },
            "progress_adjudication": {
                "canonical_decision_returned": canonical["decision"],
                "canonical_decision_accepted_for_active_sum_s1_windows": True,
                "canonical_decision_rejected_as_progress_at_interruption": True,
                "stage_finish_time_ps": stage_finish_ps,
                "final_sim_time_ps": final_sim_time_ps,
                "sim_time_after_stage_finish_ps": (
                    final_sim_time_ps - stage_finish_ps
                ),
                "wall_idle_after_first_finish_snapshot_seconds": (
                    wall_idle_after_finish_s
                ),
                "observer_bytes_after_finish_unchanged": True,
                "qualified_progress_at_interruption": False,
                "stable_repeated_snapshot_counts_as_progress": False,
                "reason": (
                    "The canonical parser evaluates the latest complete "
                    "stage-active windows, where sum_s1 progressed. The "
                    "observer then froze at COMP_FINISH while host samples "
                    "repeated the same bytes for over 35 minutes and VCS time "
                    "advanced without a sum_s2 EXEC_START."
                ),
            },
            "branch_isolation_adjudication": {
                "old_shared_lc_topology_cycle_crossed": old_cycle_crossed,
                "sum_s1_completed_on_observed_slice": True,
                "accepted_counts": {
                    "buffer_ag_enqueue": list(_pair(lc_counts["bq_wr"])),
                    "buffer_ag_dequeue": list(_pair(lc_counts["bq_rd"])),
                    "memory_ag_enqueue": list(_pair(lc_counts["mq_wr"])),
                    "memory_ag_dequeue": list(_pair(lc_counts["mq_rd"])),
                    "memory_request": list(_pair(lc_counts["req"])),
                    "mse4_request": [
                        int(sg_counts["mse4_req0"], 0),
                        int(sg_counts["mse4_req1"], 0),
                    ],
                    "mse4_write_data": [
                        int(sg_counts["mse4_wdata0"], 0),
                        int(sg_counts["mse4_wdata1"], 0),
                    ],
                },
                "final_queue_state": {
                    "buffer_ag_count": list(_pair(lc_state["bq_count"])),
                    "buffer_ag_full": lc_state["bq_full"],
                    "memory_ag_count": list(_pair(lc_state["mq_count"])),
                    "memory_ag_empty": lc_state["mq_empty"],
                },
                "claim_boundary": (
                    "This closes the exact v40 shared-root cycle on sum_s1. "
                    "It does not prove mask-wide selected-slice completion, "
                    "sum_s2 start, natural terminal, or formal D."
                ),
            },
            "rtl_stage_transition_boundary": {
                "source_commit": CLOUD_AUTHORITY,
                "files": [
                    "code/NDP_rtl/Global/global_exec_manager.sv",
                    "code/NDP_rtl/Slice/Slice_Execution_Manager.sv",
                ],
                "selected_mask": "0x0000ffff",
                "global_dispatch_equation": global_dispatch_equation,
                "slice_ready_equation": (
                    "slice2gexec_ready is 0 in CMPT and returns 1 in IDLE "
                    "only after slice_cmpt_finish moves sem_ns to IDLE"
                ),
                "deduction": (
                    "Because slice0 reached COMP_FINISH but the next masked "
                    "instruction did not reach slice0, at least one factor of "
                    "the mask-wide local-queue-empty / slice-ready / config-ready "
                    "dispatch conjunction was not proven."
                ),
                "unique_leaf": False,
            },
            "last_proven_good": (
                "sum_s1 completes on observed slice0 after both independent "
                "Buffer_AG/Memory_AG branches reach 8192 request/dequeue "
                "occurrences and both MSE4 request/write-data channels accept "
                "8192 items. This definitively crosses the former shared-LC "
                "topology cycle."
            ),
            "first_divergence": (
                "SUM_S2_EXEC_START_ABSENT_AFTER_SLICE0_SUM_S1_COMP_FINISH_"
                "WITH_MASK_WIDE_DISPATCH_CONJUNCTION_UNOBSERVED"
            ),
            "hang_root_cause": (
                "LONG_IDLE_AT_POST_SUM_S1_GLOBAL_STAGE_TRANSITION_PENDING_"
                "SELECTED_SLICE_READY_OR_LOCAL_QUEUE_OR_CONFIG_READY_LEAF"
            ),
            "formal_d": {
                "expected_count": formal_expected,
                "present_count": formal_present,
                "missing_count": formal_missing,
                "mismatch_byte_count": gate["mismatch_byte_count"],
                "mismatch_zero_evaluable": formal_missing == 0,
                "exact_set_complete": result_terms[
                    "formal_readback_exact_set_complete"
                ],
                "server_result_gate_all_terms_true": result_terms[
                    "all_terms_true"
                ],
                "missing_is_functional_failure": False,
            },
            "e3_e4_e5": {
                "E3": False,
                "E4": False,
                "E5": False,
                "reason": (
                    "Compile succeeds, but the run ends under external HUP "
                    "without natural terminal and formal D is 0/48. Missing D "
                    "and mismatch=0 are unevaluable, not a numeric failure or pass."
                ),
            },
            "qualified_path_evidence": {
                "lc_supply_feature_started": feature_bound,
                "owner_clock_qualified_records": int(lc_counts["records"], 0),
                "sum_s1_supply_and_write_path_adjudicated": (
                    old_cycle_crossed and downstream_complete
                ),
                "records_evaluable": feature_bound,
                "stable_levels_count_as_progress": False,
            },
            "blocker_delta": {
                "closed": [
                    "B_GAP_NODE0071_SHARED_LC_AND_READY_CONFIG_TOPOLOGY_CYCLE",
                ],
                "opened": [
                    "B_GAP_NODE0071_POST_SUM_S1_MASK_WIDE_STAGE_TRANSITION_"
                    "CONJUNCTION_PENDING_LEAF",
                ],
                "held": [
                    "B_GAP_NODE0071_DYNAMIC_NATURAL_TERMINAL",
                    "B_GAP_NODE0071_FORMAL_D_48",
                    "B_GAP_NODE0071_ACTUAL_COMPILED_COMMIT_BINDING",
                ],
            },
            "successor": {
                "required": prolonged_stage_transition_idle,
                "original_package_rerun_recommended": False,
                "class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "strategy": (
                    "Retain byte-identical v41 workload/config/golden and add "
                    "low-rate global-clock evidence for the full selected-slice "
                    "ready/valid, per-slice exec/finish, local/global queue and "
                    "config-ready dispatch conjunction. Keep natural-terminal "
                    "and 48D collection enabled."
                ),
                "timeout_change": False,
                "backpressure_change": False,
                "functional_rtl_change": False,
            },
            "rule_confirmation": [
                "CDA-GAP-INT32MAC-BRANCH-ISOLATION-001",
                "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
                "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
                "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
            ],
            "rule_delta_proposal": {
                "status": "NONE",
                "reason": (
                    "Current progress, signal, canonical and continuous-closure "
                    "rules already distinguish completed-window progress from "
                    "external interruption and require the next causal boundary."
                ),
            },
            "rtl_identity_binding": {
                "current_cloud_authority_commit": CLOUD_AUTHORITY,
                "actual_compile_root": "/home/panqs/ndp/NDP_copy03",
                "actual_compile_argv": compile_argv.strip(),
                "actual_compiled_commit_return_bound": False,
                "actual_compiled_commit": "UNBOUND_BY_RETURN",
                "observer_surface_compile_bound": True,
            },
            "root_cause_scope": {
                "unique": False,
                "owner": (
                    "mask-wide global execution dispatch conjunction, exact "
                    "leaf pending dynamic evidence"
                ),
                "minimal_next_evidence": (
                    "selected-mask per-slice exec/finish/ready plus global and "
                    "local queue/config-ready direct-consumer factors"
                ),
                "claim_boundary": (
                    "The return proves a post-sum_s1 stage-transition idle, "
                    "but slice0-only stage markers cannot distinguish which "
                    "selected slice or global dispatch factor blocks sum_s2."
                ),
            },
            "numeric_sum_tail_workload_config_golden_repeated": False,
            "valid_receipt": valid_receipt,
            "errors": report["errors"],
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("return_zip", type=Path)
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.return_zip.resolve(), args.source_zip.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["valid_receipt"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
