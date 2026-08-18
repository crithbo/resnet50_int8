#!/usr/bin/env python3
"""Summarize the bounded v95 causal derivative without reopening the 712 MB ZIP.

The input is the append-only, 1,588-row causal transition derivative produced by
the streaming return parser.  Events are sampled after all changes at each
owner-clock phase (time modulo 1,250 ps == 625 ps).
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/conv_node0004_v95b_tbvcd_metapair_return_r1786734268630496410_2597866"
SOURCE = BASE / "streaming/causal_transitions.jsonl"
OUTPUT = BASE / "dynamic_adjudication.json"

EVENTS = {
    "sig_memidx_queue_wr",
    "sig_memidx_queue_rd",
    "sig_prepared_wr_hs",
    "sig_prepared_rd_hs",
    "sig_meta_transfer_valid",
    "sig_meta_transaction_finish",
    "sig_wr_queue_wr",
    "sig_wr_queue_rd",
}
STATE = {
    "sig_memidx_queue_empty",
    "sig_memidx_queue_full",
    "sig_prepared_count",
    "sig_wr_queue_count",
    "sig_meta_transaction_valid",
    "sig_meta_size_left",
    "sig_meta_final_size",
    "sig_cfg_transaction_total_size",
    "sig_mse_buf_spatial_size",
    "sig_cfg_mem_idx_mode",
    "sig_cfg_mem_keep_last",
    "sig_cfg_buf_keep_last",
    "sig_wdata_ready",
    "sig_mse_enable",
}


def integer(bits: str | None) -> int | None:
    if bits is None or any(char in bits.lower() for char in "xz"):
        return None
    return int(bits, 2)


def main() -> int:
    grouped: dict[int, list[dict[str, object]]] = defaultdict(list)
    with SOURCE.open("r", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            grouped[int(row["time"])].append(row)

    values: dict[str, str] = {}
    counts = {signal: 0 for signal in EVENTS}
    event_times: dict[str, list[int]] = {signal: [] for signal in EVENTS}
    trace: list[dict[str, object]] = []
    for tick in sorted(grouped):
        changed = set()
        for row in grouped[tick]:
            signal = str(row["signal_id"])
            values[signal] = str(row["value_4state"])
            changed.add(signal)
        if tick % 1250 != 625:
            continue
        active = []
        for signal in EVENTS:
            if values.get(signal) == "1":
                counts[signal] += 1
                event_times[signal].append(tick)
                active.append(signal)
        if active or (changed & STATE):
            trace.append(
                {
                    "time_ps": tick,
                    "active_events": sorted(active),
                    "state": {name: values.get(name) for name in sorted(STATE)},
                }
            )

    transaction_size = integer(values.get("sig_cfg_transaction_total_size"))
    spatial_size = integer(values.get("sig_mse_buf_spatial_size"))
    metadata_transactions = counts["sig_memidx_queue_wr"]
    prepared_groups = counts["sig_prepared_wr_hs"]
    metadata_units = None if transaction_size is None else metadata_transactions * transaction_size
    prepared_units = None if spatial_size is None else prepared_groups * spatial_size
    deficit = None if metadata_units is None or prepared_units is None else prepared_units - metadata_units

    unmatched_time = None
    metadata_descriptor_capacity = None if transaction_size is None or spatial_size in (None, 0) else metadata_transactions * (transaction_size // spatial_size)
    prepared_times = event_times["sig_prepared_wr_hs"]
    if metadata_descriptor_capacity is not None and len(prepared_times) > metadata_descriptor_capacity:
        unmatched_time = prepared_times[metadata_descriptor_capacity]

    result = {
        "schema": "node0004-v95b-metapair-dynamic-adjudication-v1",
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "sampling": {
            "owner_period_ps": 1250,
            "owner_active_phase_ps": 625,
            "policy": "state after all same-timestamp transition rows",
        },
        "event_counts": counts,
        "event_times_ps": event_times,
        "final_state_4state": {name: values.get(name) for name in sorted(STATE)},
        "derived_ledger": {
            "metadata_tuple_count": metadata_transactions,
            "metadata_transaction_size_units": transaction_size,
            "metadata_units": metadata_units,
            "prepared_group_count": prepared_groups,
            "prepared_group_size_units": spatial_size,
            "prepared_units": prepared_units,
            "metadata_deficit_units": deficit,
            "metadata_descriptor_capacity": metadata_descriptor_capacity,
            "first_prepared_group_without_metadata_capacity_time_ps": unmatched_time,
            "final_prepared_count": integer(values.get("sig_prepared_count")),
            "final_metadata_queue_empty": values.get("sig_memidx_queue_empty"),
            "metadata_queue_full_event_count": sum(
                1 for row in trace if row["state"].get("sig_memidx_queue_full") == "1"
            ),
        },
        "disposition": {
            "validated_boundary": "MEMORY_AG_METADATA_TRANSACTION_SUPPLY_SHORT_BY_ONE_32_UNIT_TRANSACTION",
            "rebutted_candidate": "buffer_data_generation_lifetime_overruns",
            "open_leaf_alternatives": [
                "memory_index_input0_keep_token_or_epoch_ends_early",
                "memory_index_input1_buffer_token_or_last_ends_early",
                "memory_index_input2_keep_token_or_epoch_ends_early",
                "memory_index_same_gotten_mask_suppresses_tenth_tuple",
                "memory_index_split_fifo_or_keep_release_gating_suppresses_tenth_tuple",
            ],
        },
        "critical_trace": [row for row in trace if int(row["time_ps"]) >= 2446410000],
        "claim_boundary": "Counts and arithmetic are dynamic evidence from the complete streaming derivative; the missing per-input Memory_AG token/gotten/mask signals prevent unique leaf adjudication.",
        "pass": deficit == 32 and metadata_transactions == 9 and prepared_groups == 20,
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(OUTPUT), "counts": counts, "derived": result["derived_ledger"], "pass": result["pass"]}, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
