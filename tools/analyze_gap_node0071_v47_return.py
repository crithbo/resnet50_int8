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


IDENTITY = "r5_n71_gap_v47_stage_transition_rootfix"
RETURN_ROOT = f"{IDENTITY}_return"
RETURN_SIZE = 179683
RETURN_SHA256 = (
    "a219978583f67d89974b9ffb584f50658c6acfe6e33fc475423a0d88a1d0ca5a"
)
SOURCE_SIZE = 1944021
SOURCE_SHA256 = (
    "e5e1e010970230fb9f9706bc2dd2381dbfecd2c304fd48e212587827110567ab"
)
OWNER = "019fa366-cb1f-7ae2-880c-f527be0680cd"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"
CLOUD_AUTHORITY = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"


def _kv(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def _first_host_epoch_for_stage_heartbeat(
    progress: str,
) -> tuple[int, int, int]:
    pattern = re.compile(
        r"^(\d+)\tobserver_bytes=(\d+)\t(\d+) \| "
        r"GEXEC_STAGE_TRANSITION_STATE_V1 \| "
        r"event=HEARTBEAT n=(\d+) edge=(\d+)"
    )
    first_by_n: dict[int, tuple[int, int, int]] = {}
    for line in progress.splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        epoch, _size, sim_ps, number, edge = map(int, match.groups())
        first_by_n.setdefault(number, (epoch, sim_ps, edge))
    if not first_by_n:
        raise ValueError("no returned stage-transition heartbeat sample")
    return first_by_n[max(first_by_n)]


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
        def text(relative: str) -> str:
            return archive.read(prefix + relative).decode(
                "utf-8", errors="replace"
            )

        def document(relative: str) -> dict[str, Any]:
            value = json.loads(text(relative))
            if not isinstance(value, dict):
                raise ValueError(f"{relative} is not a JSON object")
            return value

        observer = text("runs/return_observer.log")
        progress = text("evidence/progress_samples.log")
        binding = text("evidence/observer_binding.txt")
        simulator_argv = text("evidence/actual_simulator_argv.txt")
        compile_argv = text("evidence/actual_compile_argv.txt")
        sim_log = text("logs/sim.log")
        timing = _kv(text("evidence/host_timing.txt"))
        signal = _kv(text("evidence/signal_status.txt"))
        stage = document("evidence/stage_transition_decision.json")
        stage_self_test = document(
            "evidence/stage_transition_predicate_self_test.json"
        )
        canonical = document("evidence/canonical_decision.json")
        gate = document("evidence/SERVER_RESULT_GATE.json")
        root_receipt = document(
            "evidence/ndp_root_toplevel_exact_set.json"
        )

    compile_status = int(signal["compile_status"])
    simulation_status = int(signal["simulation_status"])
    runner_status = int(signal["runner_status"])
    package_start_ns = int(timing["package_start_epoch_ns"])
    sim_start_ns = int(timing["sim_start_epoch_ns"])
    final_ns = int(timing["final_epoch_ns"])
    sim_wall_seconds = (final_ns - sim_start_ns) / 1_000_000_000
    package_wall_seconds = (final_ns - package_start_ns) / 1_000_000_000
    last_heartbeat_epoch, last_heartbeat_ps, last_heartbeat_edge = (
        _first_host_epoch_for_stage_heartbeat(progress)
    )
    wall_without_new_stage_heartbeat_seconds = (
        final_ns - last_heartbeat_epoch
    ) / 1_000_000_000

    input_loads = re.findall(
        r"JSON: Loading matrix\[\d+\]: .*?/input/slice(\d\d)/"
        r"matrix_A_128bit\.txt -> (0x[0-9a-fA-F]+)",
        sim_log,
    )
    loaded_slices = sorted({int(slice_id) for slice_id, _ in input_loads})
    loaded_addresses = {
        int(slice_id): address.lower() for slice_id, address in input_loads
    }

    selected = int(stage["selected_mask"], 0)
    blocked = int(stage["blocked_ready_mask"], 0)
    compute_blocked = int(stage["compute_active_blocked_mask"], 0)
    noncompute_blocked = int(stage["noncompute_blocked_mask"], 0)
    ready = int(stage["ready_mask"], 0)
    local_empty = int(stage["local_empty_mask"], 0)
    exec_seen_match = re.search(
        r"exec_seen=(0x[0-9a-fA-F]+) "
        r"finish_seen=(0x[0-9a-fA-F]+)",
        progress.splitlines()[-1],
    )
    if exec_seen_match is None:
        raise ValueError("last progress sample lacks stage seen masks")
    exec_seen = int(exec_seen_match.group(1), 0)
    finish_seen = int(exec_seen_match.group(2), 0)

    stage_bound = (
        "+RETURN_OBS_STAGE_TRANSITION" in simulator_argv
        and "stage_transition_enabled=true" in binding
        and "stage_transition_records_returned=true" in binding
        and "stage_transition_owner_clock=global_clk" in binding
        and stage_self_test.get("pass") is True
    )
    selected_slice_root = (
        stage.get("decision") == "SELECTED_SLICE_COMPUTE_UNFINISHED"
        and selected == 0xFFFF
        and blocked == 0xFFFE
        and compute_blocked == 0xFFFE
        and noncompute_blocked == 0
        and (ready & selected) == 1
        and (local_empty & selected) == selected
        and exec_seen == selected
        and finish_seen == 1
        and stage.get("config_match") is True
        and stage.get("gconfig_ready") is True
    )
    timeout = (
        compile_status == 0
        and simulation_status == 124
        and runner_status == 124
        and signal.get("signal") == "NONE"
        and 43190 <= sim_wall_seconds <= 43220
    )
    canonical_stale_at_timeout = (
        canonical.get("decision") == "STILL_PROGRESSING_NOT_FINISHED"
        and canonical.get("final_stage_scope", {}).get(
            "completed_ordered_stage_list"
        ) == ["sum_s1"]
        and wall_without_new_stage_heartbeat_seconds > 300
    )

    conjunction = gate["result_gate_conjunction"]
    formal_expected = int(gate["readback_count"])
    formal_missing = int(gate["missing_count"])
    formal_present = formal_expected - formal_missing
    valid_receipt = (
        not report["errors"]
        and compile_status == 0
        and stage_bound
        and timeout
        and selected_slice_root
        and loaded_slices == list(range(16))
        and root_receipt.get("ndp_root_toplevel_unchanged") is True
    )

    report.pop("compile_first_failure", None)
    report.update(
        {
            "schema": "gap-node0071-v47-return-analysis-v1",
            "status": (
                "LONG_RUNNING_HANG_AT_SELECTED_SLICES_1_TO_15_"
                "COMPUTE_UNFINISHED_PENDING_LOCAL_PIPELINE_LEAF"
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
                "stage_transition_feature_bound": stage_bound,
                "stage_transition_predicate_self_test_pass": (
                    stage_self_test.get("pass") is True
                ),
                "zero_counts_evaluable": stage_bound,
            },
            "execution": {
                "compile_exit_status": compile_status,
                "compile_clean": compile_status == 0,
                "simulation_exit_status": simulation_status,
                "simulation_started": True,
                "runner_exit_status": runner_status,
                "signal": signal.get("signal"),
                "natural_terminal": False,
                "termination_class": "TIMEOUT_12H",
                "sim_wall_seconds": sim_wall_seconds,
                "package_wall_seconds": package_wall_seconds,
                "canonical_decision": canonical.get("decision"),
                "canonical_decision_accepted_for_early_windows": True,
                "canonical_decision_rejected_as_progress_at_timeout": (
                    canonical_stale_at_timeout
                ),
                "stage_transition_decision": stage.get("decision"),
            },
            "progress_adjudication": {
                "qualified_progress_at_timeout": False,
                "stable_level_counts_as_progress": False,
                "last_stage_heartbeat_time_ps": last_heartbeat_ps,
                "last_stage_heartbeat_global_edge": last_heartbeat_edge,
                "wall_without_new_stage_heartbeat_seconds": (
                    wall_without_new_stage_heartbeat_seconds
                ),
                "selected_mask": f"0x{selected:07x}",
                "exec_seen_mask": f"0x{exec_seen:07x}",
                "finish_seen_mask": f"0x{finish_seen:07x}",
                "ready_mask": f"0x{ready:07x}",
                "blocked_ready_mask": f"0x{blocked:07x}",
                "compute_active_blocked_mask": (
                    f"0x{compute_blocked:07x}"
                ),
                "noncompute_blocked_mask": (
                    f"0x{noncompute_blocked:07x}"
                ),
                "local_empty_mask": f"0x{local_empty:07x}",
                "config_match": stage.get("config_match"),
                "gconfig_ready": stage.get("gconfig_ready"),
                "all_16_input_payloads_loaded": (
                    loaded_slices == list(range(16))
                ),
                "loaded_slice_ids": loaded_slices,
                "loaded_slice_addresses": loaded_addresses,
            },
            "qualified_path_evidence": {
                "stage_transition_feature_started": stage_bound,
                "owner_clock": "global_clk",
                "owner_clock_qualified_records": 128,
                "selected_slice_compute_boundary_adjudicated": (
                    selected_slice_root
                ),
                "records_evaluable": stage_bound,
                "stable_levels_count_as_progress": False,
            },
            "last_proven_good": (
                "All 16 selected slices load their package-bound input payload "
                "and observe the sum_s1 EXEC_START. Slice0 completes sum_s1 "
                "through the already-proven MSE0/MSE3→GA→MSE4 path; the global "
                "owner-clock observer proves local queues empty plus config and "
                "gconfig ready at the stalled stage-transition boundary."
            ),
            "first_divergence": (
                "SELECTED_SLICES_1_TO_15_SUM_S1_COMPUTE_REMAINS_ACTIVE_"
                "AFTER_SHARED_EXEC_START_WHILE_SLICE0_COMPLETES"
            ),
            "hang_root_cause": (
                "LONG_RUNNING_HANG_WITHIN_NONZERO_SELECTED_SLICE_SUM_S1_"
                "LOCAL_COMPUTE_PIPELINE_PENDING_CONFIG_DELIVERY_OR_"
                "FIRST_MISSING_ACCEPTED_CHECKPOINT"
            ),
            "root_cause_scope": {
                "unique_global_conjunct": True,
                "unique_local_leaf": False,
                "owner": (
                    "selected slices 1..15 local sum_s1 pipeline after "
                    "EXEC_START and before slice_cmpt_finish"
                ),
                "excluded": [
                    "package compile/observer binding",
                    "external HUP/INT/TERM",
                    "global selected-mask dispatch",
                    "global config/gconfig-ready",
                    "selected-slice local-queue-empty conjunction",
                    "missing input preload for slices 1..15",
                ],
                "minimal_next_evidence": (
                    "one owner-clock qualified mask snapshot spanning per-slice "
                    "config start/finish, MSE0/MSE3 accepted ingress, GA accepted "
                    "input/output, MSE4 accepted request/write-data, and finish"
                ),
                "claim_boundary": (
                    "The exact return localizes the hang to the nonzero selected "
                    "slice compute pipelines, but does not distinguish missed "
                    "per-slice config completion from the first missing accepted "
                    "compute checkpoint. It is not yet a unique RTL leaf."
                ),
            },
            "formal_d": {
                "expected_count": formal_expected,
                "present_count": formal_present,
                "missing_count": formal_missing,
                "mismatch_byte_count": gate["mismatch_byte_count"],
                "mismatch_zero_evaluable": formal_missing == 0,
                "exact_set_complete": conjunction[
                    "formal_readback_exact_set_complete"
                ],
                "server_result_gate_all_terms_true": conjunction[
                    "all_terms_true"
                ],
                "missing_is_numeric_failure": False,
            },
            "e3_e4_e5": {
                "E3": False,
                "E4": False,
                "E5": False,
                "reason": (
                    "Compile succeeds, but the simulator times out without a "
                    "natural terminal. Formal D is 0/48; mismatch=0 is "
                    "unevaluable when all expected readbacks are missing."
                ),
            },
            "blocker_delta": {
                "closed": [
                    "B_GAP_NODE0071_POST_SUM_S1_MASK_WIDE_STAGE_TRANSITION_"
                    "CONJUNCTION_PENDING_LEAF",
                ],
                "opened": [
                    "B_GAP_NODE0071_SELECTED_SLICES_1_TO_15_SUM_S1_LOCAL_"
                    "PIPELINE_PENDING_CONFIG_OR_FIRST_ACCEPTED_CHECKPOINT",
                ],
                "held": [
                    "B_GAP_NODE0071_DYNAMIC_NATURAL_TERMINAL",
                    "B_GAP_NODE0071_FORMAL_D_48",
                    "B_GAP_NODE0071_ACTUAL_COMPILED_COMMIT_BINDING",
                ],
            },
            "successor": {
                "required": True,
                "class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "strategy": (
                    "Retain the frozen workload/config/golden/timeout and all "
                    "low-cost proven masks. Add a single mask-wide information-"
                    "gain feature over the per-slice config and accepted compute "
                    "pipeline checkpoints, using already exported package-local "
                    "observer surfaces and qualified edge/sticky semantics."
                ),
                "install_subtree_runtime_layout_required": True,
                "fixed_simresult_required": True,
                "ndp_root_direct_child_exact_set_required": True,
                "timeout_change": False,
                "backpressure_change": False,
                "functional_rtl_change": False,
            },
            "successor_hold": {
                "status": "WAIT_SHARED_PARENT_CONTRACT_FIX",
                "package_release": "NONE",
                "candidate_identity_reserved": (
                    "r5_n71_gap_v48_multislice_pipeline_diag"
                ),
                "candidate_zip_generated": False,
                "reason": (
                    "Mainline reported a real p14 preflight failure caused by "
                    "the old shared helper requiring install/cfg_pkg and "
                    "install/codex_runs to pre-exist. Fresh materialization must "
                    "wait for corrected exact rule/tool/schema receipts where "
                    "only $server_root/install is pre-existing."
                ),
            },
            "package_release": "NONE",
            "rtl_identity_binding": {
                "current_cloud_authority_commit": CLOUD_AUTHORITY,
                "actual_compile_root": "/home/panqs/ndp/NDP_copy03",
                "actual_compile_argv": compile_argv.strip(),
                "actual_compiled_commit_return_bound": False,
                "actual_compiled_commit": "UNBOUND_BY_RETURN",
                "observer_surface_compile_bound": True,
                "claim_boundary": (
                    "The return proves the exact production compile invocation "
                    "and active observer surface, but contains no immutable "
                    "server RTL commit receipt. Current cloud authority is not "
                    "silently promoted to actual compiled identity."
                ),
            },
            "rule_confirmation": [
                "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
                "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
                "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
            ],
            "rule_delta_proposal": {
                "status": "NONE",
                "reason": (
                    "Current signal, progress, canonical, formal-D conjunction, "
                    "and information-gain rules already require this adjudication "
                    "and the next causal boundary."
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
