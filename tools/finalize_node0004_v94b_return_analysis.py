#!/usr/bin/env python3
"""Finalize the bounded streaming family analysis for the exact v94b return."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v94b_tbvcd_wrdrain_return_analysis"
STREAM = OUT / "streaming"
SUMMARY = OUT / "streaming_summary.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    transitions = STREAM / "causal_transitions.jsonl"
    final = summary["vcd"]["final_values"]
    last_nonclock = summary["vcd"]["last_nonclock_time"]
    last_timestamp = summary["vcd"]["last_timestamp"]

    candidate_disposition = [
        {
            "candidate_id": "prepared_write_without_drain",
            "disposition": "SUPPORTED_BUT_NOT_UNIQUE",
            "evidence": "prepared_count repeatedly reached 32; the final two 16-entry prepared groups had no matching metadata dequeue",
        },
        {
            "candidate_id": "metadata_queue_starvation_or_block",
            "disposition": "SUPPORTED_BOUNDARY_NOT_UNIQUE",
            "evidence": "final WR metadata queue count=0/empty=1 while prepared_count=32 and prepared_valid=1",
        },
        {
            "candidate_id": "prepared_valid_size_gate",
            "disposition": "CLOSED_AS_PRIMARY",
            "evidence": "prepared_valid remained 1; absence of metadata forced transfer size to zero instead of suppressing prepared valid",
        },
        {
            "candidate_id": "output_buffer_selection_gate",
            "disposition": "CLOSED_AS_PRIMARY",
            "evidence": "output-buffer valid=00 with bp_pre=11; selection was not blocked by occupied output state",
        },
        {
            "candidate_id": "output_buffer_backpressure",
            "disposition": "CLOSED",
            "evidence": "wr_ob_vld=00 and wr_ob_bp_pre=11 at the stable endpoint",
        },
        {
            "candidate_id": "memory_wdata_drain_block",
            "disposition": "CLOSED",
            "evidence": "mem2mse_wdata_ready=11 while mse2mem_wdata_valid=00 at the stable endpoint",
        },
        {
            "candidate_id": "prepared_count_accounting",
            "disposition": "NOT_OBSERVED_IN_REGISTERED_UPDATES",
            "evidence": "all observed registered count transitions agree with +16 on prepared write and -16 on matched metadata/output write; the unresolved issue is event-count mismatch",
        },
        {
            "candidate_id": "terminal_lifetime_hold",
            "disposition": "SUPPORTED_CONSEQUENCE",
            "evidence": "global fetch finished, but slice/global slice finish stayed low with prepared/RD/aggregate state nonempty",
        },
    ]

    analysis = {
        "schema": "node0004-v94b-tbvcd-wrdrain-return-analysis-v1",
        "package_id": "r5_n4_hw_v94b_tbvcd_wrdrain",
        "execution_id": "r1786716754307420499_2395883",
        "pass": True,
        "previous_version_progress": "v88b retired the derived ACK comparator as an observer/source-identity false positive; v93d narrowed the real hold to WR_Data_Channel prepared occupancy/drain; v94b added the leaf cone and runtime-v3.",
        "current_version_purpose": "Adjudicate prepared-data write/read accounting, WR metadata queue, output-buffer selection/backpressure, memory write-data drain, and runtime-v3 termination.",
        "integrity": {
            "zip_crc": summary["integrity"]["zip_crc"],
            "manifest_pass": summary["integrity"]["return_manifest"]["pass"],
            "source_package_identity_pass": summary["integrity"]["source_package"]["pass"],
            "vcd_stream_eof": summary["shared_streaming_state"]["status"] == "EOF_REACHED",
            "vcd_catalog_mapped_locally": f"{summary['vcd']['mapped_catalog_count']}/{summary['vcd']['catalog_count']}",
        },
        "production": {
            "compile_exit": 0,
            "simulation_started": True,
            "target_entry": True,
            "termination": "USER_EXTERNAL_INT",
            "sim_exit": 125,
            "natural_terminal": False,
            "process_fully_reaped": True,
            "vcd_archive_identity_bound": True,
            "vcd_dump_off": False,
            "vcd_dump_flush": False,
            "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        },
        "symptom_attribution": {
            "cannot_open_warning": {
                "emitter": "package-local tb_probe/tb_vcd_bounded_causal_cone.svh:221",
                "path": "attempt-local c0/shared_stop.control",
                "count": summary["sim_log"]["counts"]["cannot_open"],
                "fatal": False,
                "cause": "the TB polled an intentionally absent stop-control file with $fopen",
            },
            "binary_like_output": {
                "returned_sim_log_raw_binary_only_lines": 0,
                "returned_sim_log_lines_containing_0001001": summary["sim_log"]["counts"]["literal_0001001"],
                "attribution": "APB configuration read/write echo (for example hexadecimal 0x00001001), not VCD text and not an RTL payload proof",
                "boundary": "the outer interactive terminal stream was not returned, so only archived sim.log is classified",
            },
            "near_theoretical_end": {
                "actual_terminal_observed": False,
                "explanation": "simulation time and clock continued, but the selected causal state had stopped changing and slice completion never asserted; elapsed/theoretical time is not a terminal witness",
            },
        },
        "runtime_v3_audit": {
            "sole_shared_evaluator_authority": True,
            "raw_supervisor_samples": 1974,
            "strictly_advancing_owner_heartbeat_samples": 595,
            "last_progress_owner_cycle": 1966080,
            "full_plateau_stop_cycle": 6422528,
            "first_reached_full_plateau_timestamp_ps": 8030256250,
            "first_reached_full_plateau_wall_seconds": 1075.194482803112,
            "manual_int_owner_cycle": 10846208,
            "excess_cycles_after_full_plateau": 4423680,
            "false_negative_cause": "host polling rows with a newer VCD timestamp but unchanged 16384-cycle heartbeat made owner_clock_advancing false; the shared evaluator reset last_progress_cycle on every such non-eligible row",
            "catalog_finalizer_defect": "the finalizer compared contract signal_id names with VCD leaf references instead of reconstructed full hierarchy, falsely reporting all 73 signals missing",
            "control_warning_defect": "the control file did not exist until stop, so every TB poll emitted a warning",
            "sim_exit_signal_receipt_consistency": "authoritative return_core records INT; the package-local vcd SIM_EXIT receipt wrote NONE and is non-authoritative/inconsistent",
        },
        "causal_analysis": {
            "last_proven_good": {
                "time_ps": 2446430625,
                "statement": "the final observed RD output-buffer dequeue still occurred; prepared data was at 16 and the write-data path drained",
            },
            "first_divergence": {
                "time_ps": 2446431875,
                "statement": "a further prepared-data write raised prepared_count from 16 to 32 without a matching WR metadata entry; prepared backpressure then blocked WR_Data_Channel and RD_Buffer_AG",
            },
            "last_nonclock_change_ps": last_nonclock,
            "last_vcd_timestamp_ps": last_timestamp,
            "stable_endpoint": {
                key: final[key]
                for key in (
                    "sig_prepared_count", "sig_prepared_valid", "sig_prepared_bp",
                    "sig_wr_queue_count", "sig_wr_queue_empty", "sig_wr_queue_full",
                    "sig_wr_ob_vld", "sig_wr_ob_bp_pre", "sig_wdata_valid", "sig_wdata_ready",
                    "sig_wr_data_ready", "sig_rd_ob_count", "sig_rd_ob_full",
                    "sig_queue_count", "sig_queue_full", "sig_global_fetch_finish",
                    "sig_slice_finish", "sig_global_slice_finish",
                )
            },
            "candidate_disposition": candidate_disposition,
            "root_classification": "DYNAMIC_FLOW_CONTROL_STALL_AT_PREPARED_DATA_VS_METADATA_LIFETIME_BOUNDARY",
            "root_confidence": "HIGH_FOR_BOUNDARY_MEDIUM_FOR_PRODUCER_SIDE",
            "remaining_pair": [
                "WR_Memory_AG metadata generation/transfer lifecycle ended two 16-entry groups too early",
                "Buffer_AG/RD_Buffer data production generated two 16-entry groups beyond the matching metadata lifetime",
            ],
            "minimum_closing_evidence": [
                "zero-hop drivers of wr_data_chl_req_valid: transfer_size_valid and mem_ag_ob_bp_pre",
                "transaction_addr_valid/transaction_finish/cur_transaction_size_left/transfer_final_size and metadata accept count",
                "Buffer_AG enqueue/dequeue/last/producer completion and prepared write count",
            ],
        },
        "terminal_boundary": {
            "natural": "NOT_PROVEN",
            "formal_d": "NOT_REACHED",
            "e3": "NOT_PROVEN",
            "e4": "NOT_PROVEN",
            "e5": "NOT_PROVEN",
        },
        "successor_required": True,
        "claim_boundary": "Exact return integrity, actual-source-bound 73-signal VCD transitions and package/runtime defects are proven. The producer-side functional root remains a two-way alternative; no natural-terminal, formal-D, E3, E4 or E5 claim is made.",
        "conflicts": [],
    }
    write_json(OUT / "return_analysis.json", analysis)

    rule_audit = {
        "schema": "node0004-v94b-rule-gap-audit-v1",
        "trigger": "production compile and target execution succeeded, but a one-run unique producer-side root and intended plateau stop were not achieved",
        "disposition": "RULE_DELTA_PROPOSAL_WITH_PACKAGE_IMPLEMENTATION",
        "shared_rule_changes_requested": [
            "state explicitly that host polls between source heartbeat rows cannot reset plateau accumulation",
            "require realistic first-fresh replay with multiple advancing VCD polls per unchanged owner heartbeat",
            "require full-hierarchy VCD catalog reconstruction rather than signal_id-to-leaf-name comparison",
            "require a warning-free absent-stop representation and exact-token stop control",
        ],
        "next_package_implementation": [
            "retain raw host samples but select strictly advancing heartbeat rows for plateau evaluation, while retaining 30-second fixed-timestamp rows for true-freeze adjudication",
            "reconstruct scope-qualified VCD hierarchy for exact catalog matching",
            "precreate an empty attempt-local stop control and stop only on the exact CAUSAL_PLATEAU token",
            "add HIGH zero-hop metadata-lifecycle and Buffer_AG producer-lifetime signals",
            "capture simulator console to an attempt-local returned log instead of flooding the interactive terminal",
            "add real-header, inter-heartbeat-poll, warning-free empty-control and exact-token negative controls",
        ],
        "package_build_failure_rule_audit_triggered": False,
        "reason_not_triggered": "v94b compiled and executed the target; this is not a repeated pre-target package failure",
        "conflicts": [],
    }
    write_json(OUT / "rule_gap_audit.json", rule_audit)

    checkpoint = {
        "kind": "family_final_adjudication",
        "checkpoint_index": 41,
        "byte_offset": summary["vcd"]["bytes"],
        "last_sim_time": last_timestamp,
        "status": "EOF_AND_FAMILY_ADJUDICATION_COMPLETE",
        "analysis_sha256": sha(OUT / "return_analysis.json"),
        "rule_gap_audit_sha256": sha(OUT / "rule_gap_audit.json"),
    }
    with (STREAM / "checkpoints.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True) + "\n")

    state = json.loads((STREAM / "analysis_state.json").read_text(encoding="utf-8"))
    state["checkpoint_count"] = 42
    state["family_adjudication"] = {
        "status": checkpoint["status"],
        "return_analysis": "../return_analysis.json",
        "rule_gap_audit": "../rule_gap_audit.json",
        "successor_required": True,
    }
    write_json(STREAM / "analysis_state.json", state)

    report = STREAM / "report.md"
    with report.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(
            "\n## Family final adjudication\n\n"
            "The exact return is intact, production compile succeeded, target execution started, and the user external INT was fully reaped. "
            "No natural terminal was observed. The final non-clock transition was at 2,446,436,875 ps while the VCD clock continued to 13,571,248,750 ps.\n\n"
            "The last productive WR drain completed at 2,446,430,625 ps. At 2,446,431,875 ps another 16-entry prepared-data group raised occupancy to 32 without a matching metadata lifetime. "
            "The final state has prepared_count=32, WR metadata queue empty, output buffer empty/ready, and memory wdata ready=11. This closes output-buffer and memory-ready backpressure and leaves a two-way producer mismatch: metadata ended too early or Buffer_AG data overproduced.\n\n"
            "Runtime-v3 did not stop at the intended plateau because inter-heartbeat host polls reset shared-evaluator no-progress accumulation. The finalizer also compared signal IDs with VCD leaf names and falsely marked all 73 mapped signals absent. The next package must harden both mechanisms and add the zero-hop producer drivers.\n"
        )
    print(json.dumps({"pass": True, "analysis": str(OUT / "return_analysis.json"), "rule_audit": str(OUT / "rule_gap_audit.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
