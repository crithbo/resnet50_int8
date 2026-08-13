from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import analyze_gap_node0071_v36_return as base


IDENTITY = "r5_n71_gap_v37_dbclk_rdready_compilefix"
RETURN_ROOT = f"{IDENTITY}_return"
RETURN_SIZE = 203193
RETURN_SHA256 = (
    "dd9f4551f4fd324f100fcb01ff50ec4a7a123df0e0bdc4a8705f02f52ce15f87"
)
SOURCE_SIZE = 1828271
SOURCE_SHA256 = (
    "796312c5c4c5ed941a78fd4a0cf245bb580edac9b1b7ff5960b8e78c3eb8fa7b"
)
OWNER = "019fa366-cb1f-7ae2-880c-f527be0680cd"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"


def record(line: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for token in line.split("|")[-1].strip().split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key] = value
    return fields


def last_line(text: str, marker: str) -> str:
    matches = [line for line in text.splitlines() if marker in line]
    if not matches:
        raise ValueError(f"missing observer marker: {marker}")
    return matches[-1]


def pair(value: str) -> tuple[int, int]:
    left, right = value.split("/", 1)
    return int(left, 0), int(right, 0)


def integer(value: Any) -> int:
    return int(str(value), 0)


def analyze(return_zip: Path, source_zip: Path) -> dict[str, Any]:
    base.IDENTITY = IDENTITY
    base.RETURN_ROOT = RETURN_ROOT
    base.RETURN_SIZE = RETURN_SIZE
    base.RETURN_SHA256 = RETURN_SHA256
    base.SOURCE_SIZE = SOURCE_SIZE
    base.SOURCE_SHA256 = SOURCE_SHA256
    report = base.analyze(return_zip, source_zip)

    with zipfile.ZipFile(return_zip) as archive:
        prefix = f"{RETURN_ROOT}/"
        observer = archive.read(prefix + "runs/return_observer.log").decode(
            "utf-8", errors="replace"
        )
        binding = archive.read(
            prefix + "evidence/observer_binding.txt"
        ).decode("utf-8", errors="replace")
        simulator_argv = archive.read(
            prefix + "evidence/actual_simulator_argv.txt"
        ).decode("utf-8", errors="replace")
        compile_log = archive.read(prefix + "logs/compile.log").decode(
            "utf-8", errors="replace"
        )
        canonical = json.loads(
            archive.read(prefix + "evidence/canonical_decision.json")
        )
        gate = json.loads(
            archive.read(prefix + "evidence/SERVER_RESULT_GATE.json")
        )
        timing = archive.read(
            prefix + "evidence/host_timing.txt"
        ).decode("utf-8", errors="replace")

    counts = record(last_line(observer, "DBCLK_RD_READY_COUNTS_V1"))
    state = record(last_line(observer, "DBCLK_RD_READY_STATE_V1"))
    witness = record(last_line(observer, "DBCLK_RD_READY_WITNESS_V1"))
    event_lines = [
        line for line in observer.splitlines()
        if "DBCLK_RD_READY_EVENT_V1" in line
    ]
    heartbeat_lines = [
        line for line in observer.splitlines()
        if "DBCLK_RD_READY_COUNTS_V1" in line and "event=HEARTBEAT" in line
    ]
    times = {
        key: int(value)
        for key, value in (
            line.split("=", 1)
            for line in timing.splitlines()
            if "=" in line
        )
    }
    wall_seconds = (
        times["final_epoch_ns"] - times["sim_start_epoch_ns"]
    ) / 1_000_000_000

    q_enq = pair(counts["q_enq"])
    q_deq = pair(counts["q_deq"])
    req = pair(counts["req"])
    ib_wr = pair(counts["ib_wr"])
    ib_rd = pair(counts["ib_rd"])
    prep_wr = pair(counts["prep_wr"])
    prep_rd = pair(counts["prep_rd"])
    wr_accept = pair(counts["wr_accept"])
    queue_balance = tuple(q_enq[i] - q_deq[i] for i in range(2))
    cloud_authority_commit = (
        "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
    )
    queue_depth = 32
    v37_monitor_counter_width = 5
    queue_balance_contradiction = any(
        balance > queue_depth or balance < 0
        for balance in queue_balance
    )
    counter_truncation_explains_zero = (
        all(balance == queue_depth for balance in queue_balance)
        and integer(state["bq_count"]) == 0
    )
    final_queue_state = {
        key: integer(state[key])
        for key in (
            "bq_wr", "bq_full", "bq_rd", "bq_empty", "bq_count",
            "bq_out_valid", "bp_pre", "wr_ob_full", "data_ready",
            "data_vld", "prep_count", "rd_ob_full", "barrier",
            "req_vld", "req_ready", "rd_q_full", "rd_q_empty",
            "ib_vld", "ib_sel",
        )
    }
    conjunction_uniquely_reduces_to_data_vld = (
        final_queue_state["bq_full"] == 1
        and final_queue_state["bq_empty"] == 0
        and final_queue_state["bq_out_valid"] == 1
        and final_queue_state["bq_rd"] == 0
        and final_queue_state["wr_ob_full"] == 0
        and final_queue_state["barrier"] == 0
        and final_queue_state["data_ready"] == 0
        and final_queue_state["data_vld"] == 0
        and final_queue_state["rd_ob_full"] == 0
    )
    factor_chain_equal = (
        req == (185, 185)
        and ib_wr == (185, 185)
        and ib_rd == (185, 185)
        and prep_wr == (185, 185)
        and prep_rd == (185, 185)
        and wr_accept == (185, 185)
    )
    feature_enabled = (
        "+RETURN_OBS_DBCLK_RD_READY" in simulator_argv
        and "+RETURN_OBS_DBCLK_RD_READY_LIMIT=256" in simulator_argv
        and "dbclk_rd_ready=1" in observer
        and "dbclk_rd_ready_limit=256" in observer
        and "dbclk_rd_ready_enabled=true" in binding
        and "dbclk_rd_ready_records_returned=true" in binding
    )
    compile_clean = (
        report["execution"]["compile_exit_status"] == 0
        and "Error-[" not in compile_log
    )
    result_terms = gate["result_gate_conjunction"]
    formal_expected = int(gate["readback_count"])
    formal_missing = int(gate["missing_count"])
    formal_present = formal_expected - formal_missing
    natural = bool(canonical["natural_terminal"])
    valid_receipt = (
        not report["errors"]
        and compile_clean
        and feature_enabled
        and len(event_lines) == 256
        and len(heartbeat_lines) > 1
    )

    report.pop("compile_first_failure", None)
    report.update(
        {
            "schema": "gap-node0071-v37-return-analysis-v1",
            "status":
                "ADJUDICATED_INFORMATION_GAIN_SUCCESSOR_REQUIRED",
            "analysis_owner_thread": OWNER,
            "return_target_thread": TARGET,
            "runtime_binding": {
                **report["runtime_binding"],
                "simulator_argv_returned": True,
                "observer_log_returned": True,
                "dbclk_feature_enable_in_actual_argv":
                    "+RETURN_OBS_DBCLK_RD_READY" in simulator_argv,
                "dbclk_feature_limit_in_actual_argv":
                    "+RETURN_OBS_DBCLK_RD_READY_LIMIT=256"
                    in simulator_argv,
                "dbclk_time0_marker": (
                    "dbclk_rd_ready=1" in observer
                    and "dbclk_rd_ready_limit=256" in observer
                ),
                "dbclk_return_binding": (
                    "dbclk_rd_ready_enabled=true" in binding
                    and "dbclk_rd_ready_records_returned=true" in binding
                ),
                "owner_clock_qualified_counts_evaluable": feature_enabled,
                "zero_counts_evaluable": feature_enabled,
                "reason": (
                    "VCS compile succeeded; simulator argv, time-0 feature "
                    "marker, return binding and clk_db qualified records are "
                    "all present."
                ),
            },
            "execution": {
                "compile_exit_status": 0,
                "compile_clean": compile_clean,
                "v36_identifier_typo_closed": compile_clean,
                "simulation_exit_status": 125,
                "simulation_started": True,
                "runner_exit_status": 125,
                "signal": "INT",
                "natural_terminal": natural,
                "host_wall_seconds_from_sim_start": wall_seconds,
                "canonical_decision": canonical["decision"],
                "canonical_boundary": canonical["boundary"],
                "canonical_reason": canonical["reason"],
                "ordered_stage_scope":
                    canonical["final_stage_scope"],
            },
            "dbclk_owner_clock_evidence": {
                "feature_enabled_and_return_bound": feature_enabled,
                "qualified_event_record_count": len(event_lines),
                "qualified_event_record_limit": integer(counts["limit"]),
                "heartbeat_record_count": len(heartbeat_lines),
                "final_owner_clock_edge": integer(counts["edge"]),
                "accepted_counts": {
                    "request": list(req),
                    "buffer_ag_queue_enqueue": list(q_enq),
                    "buffer_ag_queue_dequeue": list(q_deq),
                    "rd_inbuffer_write": list(ib_wr),
                    "rd_inbuffer_read": list(ib_rd),
                    "prepared_data_write": list(prep_wr),
                    "prepared_data_read": list(prep_rd),
                    "wr_buffer_accept": list(wr_accept),
                },
                "factor_chain_185_per_stream": factor_chain_equal,
                "final_state": final_queue_state,
                "first_last_blocking_witness": witness,
                "stable_levels_count_as_progress": False,
                "conjunction_uniquely_reduces_to_data_vld":
                    conjunction_uniquely_reduces_to_data_vld,
                "queue_conservation_check": {
                    "accepted_enqueue_minus_dequeue":
                        list(queue_balance),
                    "declared_fifo_depth": queue_depth,
                    "reported_final_counter_mse0":
                        final_queue_state["bq_count"],
                    "reported_final_full_mse0":
                        final_queue_state["bq_full"],
                    "v37_monitor_counter_width_bits":
                        v37_monitor_counter_width,
                    "cloud_fifo_counter_width_bits": 6,
                    "counter_truncation_explains_zero":
                        counter_truncation_explains_zero,
                    "contradiction_present":
                        queue_balance_contradiction,
                    "interpretation": (
                        "Under cloud-authoritative 0ccae91 the Buffer_AG FIFO "
                        "depth is 32, so accepted enqueue-minus-dequeue=32 is "
                        "exactly full rather than contradictory. The v37 "
                        "monitor was only 5 bits while FIFO_DEPTH=32 requires "
                        "a 6-bit counter; value 32 therefore truncates to zero. "
                        "The full=1/count=0 state is a diagnostic-width drift, "
                        "not evidence of a functional FIFO conservation defect."
                    ),
                },
            },
            "cloud_rtl_authority": {
                "repository": "xlsjdjdk/Trassic2.0_RTL",
                "branch": "master",
                "approved_commit": cloud_authority_commit,
                "comparison_base_commit":
                    "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d",
                "changed_commit_count": 12,
                "changed_file_count": 11,
                "gap_causal_cone_affected": True,
                "affected_facts": {
                    "Buffer_AG_Idx_Queue_depth": "24 -> 32",
                    "RD_Data_Channel_depth": "32 -> 128",
                    "REQ_OOO_QUEUE_TAG_depth": "16 -> 128",
                    "IGA_ROW_LC_Inbuffer": "FIFO refactor",
                    "Array_Request_Manager": "refactor",
                    "SA_Inport_pingpong": "valid-conditioned",
                },
                "v37_actual_compiled_commit_return_bound": False,
                "adjudication": (
                    "The identity gap does not invalidate compile or dynamic "
                    "evidence. It does prevent attributing v37 to a precise "
                    "production commit and requires the successor observer to "
                    "use 0ccae91 field widths and causal semantics."
                ),
            },
            "qualified_path_evidence": {
                "dbclk_feature_started": feature_enabled,
                "owner_clock_qualified_records": len(event_lines),
                "records_evaluable": feature_enabled,
                "queue_to_wr_to_rd_factors_adjudicated": True,
                "stable_levels_count_as_progress": False,
            },
            "canonical_decision_adjudication": {
                "accepted_as_generic_global_stall": True,
                "accepted_as_natural_terminal": False,
                "accepted_as_numeric_evidence": False,
                "new_owner_clock_refinement": (
                    "The direct WR_Buffer_AG conjunction is held because "
                    "RD_Data_Channel data_vld is low, not because output-full "
                    "or nse2mse_req_barrier is asserted."
                ),
            },
            "formal_d": {
                "expected_count": formal_expected,
                "present_count": formal_present,
                "missing_count": formal_missing,
                "mismatch_byte_count": gate["mismatch_byte_count"],
                "mismatch_zero_evaluable": formal_missing == 0,
                "exact_set_complete":
                    result_terms["formal_readback_exact_set_complete"],
                "server_result_gate_all_terms_true":
                    result_terms["all_terms_true"],
                "server_result_status": gate["status"],
            },
            "last_proven_good": (
                "VCS compile succeeds and the exact clk_db feature is enabled, "
                "time-0 marked and return-bound. For both MSE0 and MSE3, 185 "
                "qualified requests traverse RD inbuffer write/read, prepared "
                "write/read and WR_Buffer_AG accept. The queue-to-RD path "
                "therefore makes real owner-clock progress before the stall."
            ),
            "first_divergence": (
                "BUFFER_AG_QUEUE_PENDING_FULL_WHILE_RD_REQUEST_SOURCE_AND_"
                "PREPARED_DATA_PIPELINE_EMPTY_AFTER_185_ACCEPTED_TRANSACTIONS"
            ),
            "hang_root_cause": (
                "LONG_RUNNING_HANG_AT_BUFFER_AG_TO_MEMORY_SUPPLY_SHARED_LC_"
                "BOUNDARY_PENDING_OCCURRENCE_VS_BACKPRESSURE_LEAF"
            ),
            "root_cause_scope": {
                "unique_functional_root": False,
                "closed": [
                    "v36 package-local identifier typo",
                    "wrong sampling clock for the v37 feature",
                    "WR_Buffer_AG output-full as the held conjunction leaf",
                    "nse2mse_req_barrier as the held conjunction leaf",
                    "RD_Data_Channel output-full as the held readiness leaf",
                    "absence of all initial request/return/prepared progress",
                ],
                "remaining_candidates": [
                    "materialized occurrence/terminal stops memory-side supply before buffer demand",
                    "shared LC/backpressure cycle leaves buffer queue pending while no new memory request is issued",
                    "Memory_AG source or queue stops before the direct RD request consumer",
                ],
                "claim_boundary": (
                    "No config or functional RTL defect is yet uniquely "
                    "proven. A fresh read-only information-gain observer is "
                    "required; timeout extension is not justified."
                ),
            },
            "e3_e4_e5": {
                "E3": False,
                "E4": False,
                "E5": False,
                "reason": (
                    "compile=0 but simulation/runner=125 under INT, no natural "
                    "terminal, ordered execution stops in sum_s1, and formal "
                    "D is 0/48. mismatch=0 is unevaluable."
                ),
            },
            "blocker_delta": {
                "closed": [
                    "B_GAP_NODE0071_V36_PACKAGE_OBSERVER_IDENTIFIER_TYPO",
                    "B_GAP_NODE0071_RD_READY_CONJUNCTION_OUTPUT_FULL_OR_BARRIER_LEAF",
                ],
                "opened": (
                    "B_GAP_NODE0071_BUFFER_AG_TO_MEMORY_SUPPLY_SHARED_LC_"
                    "OCCURRENCE_OR_BACKPRESSURE_PENDING_LEAF"
                ),
                "held": [
                    "B_GAP_NODE0071_DYNAMIC_NATURAL_TERMINAL",
                    "B_GAP_NODE0071_FORMAL_D_48",
                ],
            },
            "successor": {
                "required": True,
                "class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "strategy": (
                    "One clk_db owner-clock, qualified/rate-limited package "
                    "covers actual Buffer_AG/Memory_AG FIFO conservation, "
                    "public memory/buffer tag and backpressure inputs, direct "
                    "RD request consumer and the existing data_vld boundary."
                ),
                "candidate_matrix_required": True,
                "config_change": False,
                "timeout_change": False,
                "backpressure_change": False,
                "functional_rtl_change": False,
            },
            "rule_confirmation": [
                "CDA-GAP-HANDSHAKE-CONJUNCTION-FACTOR-OBSERVABILITY-001",
                "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
                "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
            ],
            "rule_delta_proposal": {
                "status": "NONE",
                "reason": (
                    "Current conjunction-factor, owner-clock, information-gain "
                    "and result-gate rules already describe the observed "
                    "success and remaining evidence gap."
                ),
            },
            "numeric_sum_tail_workload_config_golden_repeated": False,
            "valid_receipt": valid_receipt,
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
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid_receipt"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
