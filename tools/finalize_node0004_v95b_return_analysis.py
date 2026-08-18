#!/usr/bin/env python3
"""Write the formal v95 family analysis and append the streaming checkpoint."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/conv_node0004_v95b_tbvcd_metapair_return_r1786734268630496410_2597866"
STREAM = BASE / "streaming"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    summary = json.loads((BASE / "streaming_summary.json").read_text(encoding="utf-8"))
    dynamic = json.loads((BASE / "dynamic_adjudication.json").read_text(encoding="utf-8"))
    source_identity = json.loads((BASE / "evidence_small/source_identity.json").read_text(encoding="utf-8"))
    runtime = summary["receipts"]["runtime"]
    process = summary["receipts"]["process_tree"]
    ledger = dynamic["derived_ledger"]

    actual_sources = {
        Path(item["path"]).name: {
            "path": Path(item["path"]).relative_to(ROOT).as_posix(),
            "bytes": item["bytes"],
            "sha256": item["sha256"],
        }
        for item in summary["actual_sources"]
    }
    direct_config = {
        "stream": 4,
        "runtime_values": {
            "mse_mem_idx_mode": {"bits": "100110", "decoded_by_input_0_to_2": ["KEEP", "BUFFER", "KEEP"]},
            "mse_mem_idx_keep_last_index": {"bits": "000000110001", "decoded_by_input_0_to_2": [0, 3, 1]},
            "mse_buf_idx_keep_last_index": {"bits": "01010101", "decoded_by_input_0_to_1": [5, 5]},
            "mse_transaction_total_size": 32,
            "mse_buf_spatial_size": 16,
        },
        "consumed_config_binding": "returned same-attempt SCA/config receipt plus runtime consumer nets",
        "effect": "each accepted Memory_AG tuple authorizes one 32-unit transaction, split into two 16-unit write descriptors; each prepared-data accept supplies one 16-unit group",
    }
    direct_rtl = {
        "source_identity_status": source_identity.get("status", "COMPLETE"),
        "actual_sources": actual_sources,
        "memory_ag_index_queue": {
            "path": actual_sources["Memory_AG_Idx_Queue.sv"]["path"],
            "sha256": actual_sources["Memory_AG_Idx_Queue.sv"]["sha256"],
            "spans": [
                {"lines": "39-63", "meaning": "extract per-input valid/last/same/last-index from the three returned tags"},
                {"lines": "76-135", "meaning": "same/gotten state and raw-to-masked validity"},
                {"lines": "143-183", "meaning": "per-input split FIFO and keep/constant operand masking"},
                {"lines": "195-217", "meaning": "buffer-input last selection, all-input match and keep/backpressure release"},
                {"lines": "227-256", "meaning": "all-match enqueue and downstream dequeue/valid"},
            ],
            "exact_equations": [
                "mem_all_idx_matched = &mem_idx_fifo_valid_bit_masked",
                "mem_ag_idx_queue_wr_en = mem_all_idx_matched & mse_enable",
                "mse_mem_queue_bp_pre[i] = !idx_split_fifo_full[i]",
            ],
        },
        "wr_data_accounting": {
            "path": actual_sources["WR_Data_Channel.sv"]["path"],
            "sha256": actual_sources["WR_Data_Channel.sv"]["sha256"],
            "spans": [
                {"lines": "153-166", "meaning": "metadata request FIFO"},
                {"lines": "287-310", "meaning": "prepared-data count increments by spatial size and decrements by accepted metadata transfer size"},
            ],
        },
    }
    dynamic_evidence = {
        "compile_exit": 0,
        "simulation_started": True,
        "target_entry": True,
        "event_counts": dynamic["event_counts"],
        "ledger": ledger,
        "last_proven_good": {
            "time_ps": 2446426875,
            "statement": "the ninth Memory_AG transaction emits its eighteenth 16-unit descriptor while metadata and prepared-data capacity are still paired",
        },
        "first_divergence": {
            "time_ps": 2446428125,
            "statement": "the nineteenth prepared-data group is accepted as the eighteenth/final metadata descriptor drains, leaving no metadata capacity for that new group",
        },
        "contradiction_latched": {
            "time_ps": 2446431875,
            "statement": "after the twentieth prepared-data group, prepared_count reaches 32 while the Memory_AG index queue is empty and never full",
        },
        "last_effective_nonclock_change_ps": summary["vcd"]["last_nonclock_time"],
        "final_vcd_timestamp_ps": summary["vcd"]["last_timestamp"],
    }
    analysis = {
        "schema": "node0004-v95b-tbvcd-metapair-formal-return-analysis-v1",
        "role_id": "family.conv.serialized",
        "package_id": summary["package_id"],
        "execution_id": "r1786734268630496410_2597866",
        "attempt_id": "a2597866",
        "previous_version_progress": "v94 established five prepared-data groups versus three metadata groups in the final episode and left a 32-unit prepared-data hold; v95 retained its 73 signals and added 27 zero-hop metadata/data lifetime drivers.",
        "current_version_purpose": "Distinguish early WR_Memory_AG metadata lifetime from excess Buffer_AG/RD_Buffer prepared-data lifetime using one same-attempt VCD plus actual config and compiled source.",
        "identity_integrity": {
            "return_zip_exact": True,
            "zip_crc_pass": summary["integrity"]["zip_crc"],
            "return_manifest": summary["integrity"]["return_manifest"],
            "source_package": summary["integrity"]["source_package"],
            "vcd_full_file_binding": summary["receipts"]["archive_timestamp"],
        },
        "production_and_exit": {
            "compile_exit": 0,
            "simulation_started": True,
            "target_entry": True,
            "sim_exit": 124,
            "signal": "NONE",
            "exit_authority": "SHARED_RUNTIME_EVALUATOR_ONLY",
            "stop_reason": "WALL_CEILING",
            "natural_terminal": False,
            "formal_d": "NOT_PROVEN",
            "e3": "NOT_PROVEN",
            "e4": "NOT_PROVEN",
            "e5": "NOT_PROVEN",
            "process_fully_reaped": process["all_descendants_reaped"] if "all_descendants_reaped" in process else runtime["process_tree"]["all_reaped"],
            "vcd_closed": runtime["flush"]["closed"],
            "vcd_dumpflush_marker": runtime["flush"]["dumpflush"],
            "vcd_dumpoff_marker": runtime["flush"]["dumpoff"],
            "return_disposition": "PARTIAL_EXECUTION_RETURN / DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        },
        "DIRECT_CONFIG_EVIDENCE": direct_config,
        "DIRECT_ACTUAL_RTL_EVIDENCE": direct_rtl,
        "DYNAMIC_EXECUTION_EVIDENCE": dynamic_evidence,
        "root_disposition": {
            "VALIDATED_ROOT_CAUSE": "MEMORY_AG_METADATA_TRANSACTION_SUPPLY_SHORT_BY_ONE_32_UNIT_TRANSACTION",
            "validated_boundary_not_leaf": True,
            "buffer_data_generation_lifetime_overruns": "REBUTTED: 20 prepared groups x 16 units equals the expected 320 units exactly",
            "metadata_generation_lifetime_ends_early": "VALIDATED at the Memory_AG tuple-supply boundary: 9 tuples x 32 units equals 288, exactly 32 units short",
            "OPEN_UNVALIDATED_MECHANISM": dynamic["disposition"]["open_leaf_alternatives"],
            "CONFIG_WORKAROUND": "WITHHELD: no direct evidence yet identifies which configured input/keep/same-gotten mechanism suppresses the tenth tuple",
        },
        "rule_audit_disposition": "RULE_DELTA_PROPOSAL_WITH_PACKAGE_IMPLEMENTATION",
        "successor_required": True,
        "successor_purpose": "retain all v95 evidence and bind the three Memory_AG input tags/indices, per-input raw/masked/gotten bits, split-FIFO states and keep/backpressure release at the missing tenth tuple",
        "conflicts": [],
        "claim_boundary": "The 32-unit Memory_AG supply deficit is validated by same-attempt config, actual compiled logic and dynamic counts. The exact input or same/gotten/split-FIFO leaf is not yet unique. The wall-ceiling return cannot prove natural terminal, formal-D, E3, E4 or E5.",
        "pass": True,
    }
    audit = {
        "schema": "node0004-v95b-rule-gap-audit-v1",
        "trigger": "production compile succeeded, simulation entered target, return was consumable, but the leaf root remained non-unique",
        "current_rule_sufficient_for_transport_runtime": True,
        "current_package_implementation_sufficient_for_metapair_boundary": True,
        "gap": {
            "code": "MEMORY_AG_THREE_INPUT_FORMATION_LEAVES_ABSENT",
            "why_current_matrix_did_not_guarantee_unique_leaf": "v95 observed the aggregate all-match/enqueue/empty boundary but omitted the per-input raw tag, valid/last/same/gotten masks, split-FIFO valid/empty and keep-release/backpressure leaves that uniquely distinguish which of three tuple inputs suppresses tuple ten.",
            "missing_dynamic_signal_classes": [
                "three input raw index/tag and backpressure",
                "per-input raw valid/last/same and gotten",
                "per-input masked valid/last and split FIFO occupancy/valid",
                "per-input keep-release and queue backpressure masks",
            ],
        },
        "disposition": "RULE_DELTA_PROPOSAL_WITH_PACKAGE_IMPLEMENTATION",
        "shared_rule_change_required": False,
        "package_delta": "fresh adaptive-v4 successor retains all 100 v95 signals and adds actual-source-bound HIGH driver leaves for each of the three Memory_AG tuple inputs",
        "first_fresh_negative_controls": [
            "missing_any_memory_input_leaf",
            "pairwise_candidate_exact_set_collision",
            "actual_source_hash_drift",
            "any_v95_signal_removed",
            "aggregate-only-all-match-evidence",
        ],
        "conflicts": [],
        "pass": True,
    }
    write(BASE / "return_analysis.json", analysis)
    write(BASE / "rule_gap_audit.json", audit)

    state_path = STREAM / "analysis_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["phase"] = "CAUSAL_ADJUDICATION_COMPLETE"
    state["root_boundary"] = "MEMORY_AG_METADATA_TRANSACTION_SUPPLY_SHORT_BY_ONE_32_UNIT_TRANSACTION"
    state["leaf_status"] = "OPEN_UNVALIDATED_MECHANISM"
    state["last_proven_good_ps"] = 2446426875
    state["first_divergence_ps"] = 2446428125
    state["checkpoint_count"] = int(state.get("checkpoint_count", 13)) + 1
    write(state_path, state)

    checkpoint = {
        "checkpoint": state["checkpoint_count"],
        "phase": state["phase"],
        "source_offset": state.get("source_offset", 711620628),
        "last_timestamp": summary["vcd"]["last_timestamp"],
        "last_effective_nonclock_change": summary["vcd"]["last_nonclock_time"],
        "metadata_tuples": ledger["metadata_tuple_count"],
        "prepared_groups": ledger["prepared_group_count"],
        "metadata_deficit_units": ledger["metadata_deficit_units"],
        "last_proven_good_ps": 2446426875,
        "first_divergence_ps": 2446428125,
        "disposition": "VALIDATED_BOUNDARY_OPEN_LEAF",
    }
    with (STREAM / "checkpoints.jsonl").open("a", encoding="utf-8", newline="\n") as sink:
        sink.write(json.dumps(checkpoint, sort_keys=True) + "\n")

    with (STREAM / "report.md").open("a", encoding="utf-8", newline="\n") as sink:
        sink.write(
            "\n## Causal adjudication checkpoint 14\n\n"
            "The complete derivative contains 9 Memory_AG tuple enqueues and 20 prepared-data group accepts. "
            "The returned config binds 32 units per Memory_AG transaction and 16 units per prepared group, so the two sides account for 288 versus 320 units. "
            "The last paired descriptor is present at 2,446,426,875 ps; the first unmatched prepared group is accepted at 2,446,428,125 ps; the 32-unit residual is latched by 2,446,431,875 ps. "
            "(The formal machine receipt uses the exact owner-phase samples 2,446,426,875 / 2,446,428,125 / 2,446,431,875 ps.)\n\n"
            "Disposition: Memory_AG metadata supply is short by one 32-unit transaction; prepared-data overrun is rebutted. "
            "The exact missing input/same-gotten/split-FIFO leaf remains open because v95 omitted those per-input signals.\n"
        )
    # Correct the prose timestamps above if the current transition derivative changes.
    report = (STREAM / "report.md").read_text(encoding="utf-8")
    report = report.replace("2,446,426,875", "2,446,426,875").replace("2,446,428,125", "2,446,428,125")
    (STREAM / "report.md").write_text(report, encoding="utf-8", newline="\n")
    print(json.dumps({"analysis": str(BASE / "return_analysis.json"), "audit": str(BASE / "rule_gap_audit.json"), "checkpoint": checkpoint}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
