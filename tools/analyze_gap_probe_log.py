#!/usr/bin/env python3
"""Classify the GAP failure from the read-only TB deep-probe return.

The v4 observer records internal MSE events on ``clk_db`` while the public local
request/return monitor records the physical interface on ``clk_sg``.  The
cross-clock snapshots are useful context but cannot by themselves prove a
request replay.  When the local request/return logs and package root are
provided, this analyzer correlates them per physical channel and treats that
same-interface evidence as authoritative.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analyze_gap_sim_path import (
    associate_returns,
    expected_read_addresses,
    parse_read_returns,
    parse_requests,
    read_128bit_words,
)


EVENT_RE = re.compile(
    r"^\s*(?P<time>\d+)\s+\|\s+(?P<kind>[A-Z0-9_]+)\s+\|\s+(?P<body>.*)$"
)
FIELD_RE = re.compile(r"(?P<key>[A-Za-z0-9_]+)=(?P<value>\S+)")
GA_OUTBUFFER_DEPTH = 2


class GapProbeAnalysisError(RuntimeError):
    """Raised when a return-observer log cannot support diagnosis."""


def _parse_int(value: str) -> int | None:
    normalized = value.lower().replace("_", "")
    digits = normalized[2:] if normalized.startswith(("0x", "0b", "0o")) else normalized
    if any(char in digits for char in "xz"):
        return None
    try:
        return int(normalized, 0)
    except ValueError:
        return None


def parse_probe_events(path: Path) -> list[dict]:
    if not path.is_file():
        raise GapProbeAnalysisError(f"missing observer log: {path}")
    events: list[dict] = []
    for ordinal, line in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines()
    ):
        match = EVENT_RE.match(line)
        if not match:
            continue
        fields = {
            field.group("key"): field.group("value")
            for field in FIELD_RE.finditer(match.group("body"))
        }
        events.append(
            {
                "time": int(match.group("time")),
                "kind": match.group("kind"),
                "ordinal": ordinal,
                "fields": fields,
            }
        )
    if not events:
        raise GapProbeAnalysisError(f"no observer events parsed from: {path}")
    return events


def _field_int(event: dict, field: str) -> int | None:
    value = event["fields"].get(field)
    return None if value is None else _parse_int(value)


def _channel_bit(event: dict, field: str, channel: int) -> int | None:
    value = _field_int(event, field)
    return None if value is None else (value >> channel) & 1


def analyze_events(events: list[dict]) -> dict:
    enqueue_events = [
        event for event in events if event["kind"] == "DEEP_RD_ADDR_ENQUEUE"
    ]
    request_events = [
        event for event in events if event["kind"] == "DEEP_RD_REQ_HANDSHAKE"
    ]
    meta_events = [event for event in events if event["kind"] == "DEEP_RD_META"]
    consume_events = [
        event for event in events if event["kind"] == "DEEP_RD_CONSUME"
    ]
    buffer_events = [
        event for event in events if event["kind"] == "DEEP_MSE0_TO_BUFFER0"
    ]
    ga_events = [event for event in events if event["kind"] == "DEEP_GA"]
    mse4_events = [
        event for event in events if event["kind"] == "DEEP_MSE4_INDEX"
    ]
    accumulator_events = [
        event for event in events if event["kind"] == "GA_ACCUM_STATE"
    ]
    expected_addresses, _ = expected_read_addresses(
        outer_count=256,
        outer_stride_bytes=392,
        inner_start=0,
        inner_end=56,
        inner_stride=4,
        inner_dim_stride_bytes=8,
        transaction_bytes=32,
    )
    ordered_enqueue_events = sorted(
        enqueue_events, key=lambda event: (event["time"], event["ordinal"])
    )
    observed_enqueue_addresses = [
        _field_int(event, "addr_in") for event in ordered_enqueue_events
    ]
    enqueue_input_mismatches = [
        {
            "index_zero_based": index,
            "time": ordered_enqueue_events[index]["time"],
            "expected_address_128bit": f"0x{expected:06x}",
            "actual_address_128bit": (
                None if actual is None else f"0x{actual:06x}"
            ),
        }
        for index, (actual, expected) in enumerate(
            zip(observed_enqueue_addresses, expected_addresses)
        )
        if actual != expected
    ]

    pending: dict[int, collections.deque[dict]] = collections.defaultdict(
        collections.deque
    )
    transport_mismatches: list[dict] = []
    orphan_requests: list[dict] = []
    stale_valid_requests: list[dict] = []

    transport_events = enqueue_events + request_events
    transport_events.sort(
        key=lambda event: (
            event["time"],
            0 if event["kind"] == "DEEP_RD_REQ_HANDSHAKE" else 1,
            event["ordinal"],
        )
    )
    for event in transport_events:
        channel = _field_int(event, "ch")
        if channel is None:
            continue
        if event["kind"] == "DEEP_RD_ADDR_ENQUEUE":
            pending[channel].append(event)
            continue

        address = _field_int(event, "addr")
        if _channel_bit(event, "vld", channel) == 0 and _channel_bit(
            event, "vld_d", channel
        ) == 1:
            stale_valid_requests.append(
                {
                    "time": event["time"],
                    "channel": channel,
                    "address_128bit": (
                        None if address is None else f"0x{address:06x}"
                    ),
                    "vld": event["fields"].get("vld"),
                    "vld_d": event["fields"].get("vld_d"),
                    "ready": event["fields"].get("ready"),
                }
            )

        if not pending[channel]:
            orphan_requests.append(
                {
                    "time": event["time"],
                    "channel": channel,
                    "address_128bit": (
                        None if address is None else f"0x{address:06x}"
                    ),
                }
            )
            continue
        enqueued = pending[channel].popleft()
        expected = _field_int(enqueued, "addr_in")
        if address != expected:
            transport_mismatches.append(
                {
                    "request_time": event["time"],
                    "enqueue_time": enqueued["time"],
                    "channel": channel,
                    "expected_enqueued_address_128bit": (
                        None if expected is None else f"0x{expected:06x}"
                    ),
                    "actual_request_address_128bit": (
                        None if address is None else f"0x{address:06x}"
                    ),
                    "vld": event["fields"].get("vld"),
                    "vld_d": event["fields"].get("vld_d"),
                    "ready": event["fields"].get("ready"),
                }
            )

    pending_count = sum(len(queue) for queue in pending.values())

    lc0_values = {_field_int(event, "lc0") for event in mse4_events}
    lc2_values = {_field_int(event, "lc2") for event in mse4_events}
    pe1_values = {_field_int(event, "pe1") for event in mse4_events}
    idx_values = {_field_int(event, "idx") for event in mse4_events}
    bias_values = {_field_int(event, "addr_bias") for event in mse4_events}
    for values in (lc0_values, lc2_values, pe1_values, idx_values, bias_values):
        values.discard(None)
    fixed_mse4_index = (
        len(lc0_values) > 1
        and lc2_values == {0}
        and pe1_values == {0}
        and idx_values == {0}
        and bias_values == {0}
    )

    invalid_slot_reuse: list[dict] = []
    illegal_outbuffer_counts: list[dict] = []
    accumulator_by_pe: dict[str, list[dict]] = collections.defaultdict(list)
    for event in accumulator_events:
        pe = event["fields"].get("pe", "unknown")
        accumulator_by_pe[pe].append(event)
        read_pointer = _field_int(event, "rd_ptr")
        input_c = _field_int(event, "input2")
        outbuffer_count = _field_int(event, "ob_count")
        if (
            outbuffer_count is not None
            and outbuffer_count > GA_OUTBUFFER_DEPTH
        ):
            illegal_outbuffer_counts.append(
                {
                    "time": event["time"],
                    "event_number": _field_int(event, "n"),
                    "pe": pe,
                    "outbuffer_count": outbuffer_count,
                    "configured_depth": GA_OUTBUFFER_DEPTH,
                    "transout_initial": event["fields"].get("trans_init"),
                    "calculate": event["fields"].get("calc"),
                }
            )
        selected_data = (
            None
            if read_pointer not in (0, 1)
            else _field_int(event, f"ob_data{read_pointer}")
        )
        if (
            _field_int(event, "matched") == 1
            and (_field_int(event, "trans_init") or 0) >= 2
            and _field_int(event, "calc") == 0
            and _field_int(event, "ob_valid") == 0
            and input_c not in (None, 0)
            and selected_data == input_c
        ):
            invalid_slot_reuse.append(
                {
                    "time": event["time"],
                    "event_number": _field_int(event, "n"),
                    "pe": pe,
                    "input_c": event["fields"].get("input2"),
                    "transout_initial": event["fields"].get("trans_init"),
                    "read_pointer": read_pointer,
                    "outbuffer_count": event["fields"].get("ob_count"),
                    "selected_tag": event["fields"].get(
                        f"ob_tag{read_pointer}"
                    ),
                    "selected_data": event["fields"].get(
                        f"ob_data{read_pointer}"
                    ),
                }
            )

    underflow_transitions: list[dict] = []
    for pe, pe_events in sorted(accumulator_by_pe.items()):
        ordered = sorted(
            pe_events, key=lambda event: (event["time"], event["ordinal"])
        )
        for previous, current in zip(ordered, ordered[1:]):
            if (
                _field_int(previous, "ob_count") == 1
                and _field_int(previous, "calc") == 1
                and _field_int(previous, "calc_v0") == 1
                and _field_int(previous, "calc_v2") == 1
                and _field_int(previous, "ob_wr") == 0
                and _field_int(current, "ob_count") == 3
                and _field_int(current, "trans_init") == 0
            ):
                underflow_transitions.append(
                    {
                        "pe": pe,
                        "before_time": previous["time"],
                        "after_time": current["time"],
                        "before_event_number": _field_int(previous, "n"),
                        "after_event_number": _field_int(current, "n"),
                        "before_count": 1,
                        "after_count": 3,
                        "configured_depth": GA_OUTBUFFER_DEPTH,
                        "calculate_count_inference": (
                            "int32 calc_v0=1 and calc_v2=1 implies "
                            "transout_calculate_cnt=2"
                        ),
                        "observed_write_handshake": 0,
                    }
                )

    if underflow_transitions and invalid_slot_reuse:
        classification = (
            "ga_int32_sum_outbuffer_count_underflow_then_invalid_slot_reuse"
        )
        first_decisive_boundary = (
            "GA_PE_Outbuffer transout count update, then "
            "GA_PE_Inbuffer ungated input C feedback"
        )
    elif invalid_slot_reuse:
        classification = "ga_int32_sum_invalid_outbuffer_slot_reused_as_c"
        first_decisive_boundary = (
            "GA_PE_Inbuffer input C selection from invalid outbuffer read slot"
        )
    elif accumulator_events:
        classification = "ga_accumulator_state_captured_without_invalid_slot_match"
        first_decisive_boundary = (
            "inspect transout calculate/reset state at the block boundary"
        )
    elif enqueue_input_mismatches:
        classification = "mse0_address_generation_input_mismatch"
        first_decisive_boundary = (
            "MSE0 request_addr_mapped/mem_ag_ob_addr_in before channel queue"
        )
    elif stale_valid_requests or orphan_requests or transport_mismatches:
        classification = "cross_clock_request_snapshot_requires_correlation"
        first_decisive_boundary = (
            "correlate clk_db observer snapshots with clk_sg local logs"
        )
    elif enqueue_events and request_events:
        classification = "mse0_address_transport_matched_in_probe_window"
        first_decisive_boundary = "inspect RD_Data_Channel metadata/data alignment"
    else:
        classification = "insufficient_deep_probe_events"
        first_decisive_boundary = "observer enablement or execution start"

    return {
        "schema": "gap-tb-deep-probe-analysis-v1",
        "classification": classification,
        "first_decisive_boundary": first_decisive_boundary,
        "mse0_address_transport": {
            "sampling_domain": "clk_db",
            "physical_local_interface_domain": "clk_sg",
            "standalone_replay_claim_allowed": False,
            "enqueue_event_count": len(enqueue_events),
            "request_event_count": len(request_events),
            "enqueue_input_mismatch_count_in_probe_window": len(
                enqueue_input_mismatches
            ),
            "first_enqueue_input_mismatches": enqueue_input_mismatches[:8],
            "orphan_request_count": len(orphan_requests),
            "transport_mismatch_count": len(transport_mismatches),
            "pending_enqueue_count_at_probe_end": pending_count,
            "request_while_only_delayed_valid_count": len(stale_valid_requests),
            "first_orphan_requests": orphan_requests[:8],
            "first_transport_mismatches": transport_mismatches[:8],
            "first_delayed_valid_requests": stale_valid_requests[:8],
        },
        "downstream_probe_coverage": {
            "request_metadata_events": len(meta_events),
            "read_data_consume_events": len(consume_events),
            "mse0_to_buffer0_events": len(buffer_events),
            "ga_events": len(ga_events),
        },
        "mse4_index_path": {
            "event_count": len(mse4_events),
            "lc0_unique": sorted(lc0_values),
            "lc2_unique": sorted(lc2_values),
            "pe1_unique": sorted(pe1_values),
            "idx_unique": sorted(idx_values),
            "address_bias_unique": sorted(bias_values),
            "lc0_changes_but_lc2_pe1_index_bias_remain_zero": fixed_mse4_index,
            "interpretation": (
                "D address is driven by the constant LC2->PE1 path"
                if fixed_mse4_index
                else "probe window does not prove a constant D-index path"
            ),
        },
        "ga_accumulator_state": {
            "event_count": len(accumulator_events),
            "configured_outbuffer_depth": GA_OUTBUFFER_DEPTH,
            "illegal_outbuffer_count_event_count": len(
                illegal_outbuffer_counts
            ),
            "first_illegal_outbuffer_counts": illegal_outbuffer_counts[:16],
            "underflow_transition_count": len(underflow_transitions),
            "first_underflow_transitions": underflow_transitions[:16],
            "invalid_slot_c_reuse_count": len(invalid_slot_reuse),
            "first_invalid_slot_c_reuse": invalid_slot_reuse[:16],
            "decisive_condition": (
                "matched && trans_init>=2 && !calc && !ob_valid && "
                "input2==outbuffer_data[rd_ptr] && input2!=0"
            ),
        },
    }


def correlate_local_logs(
    *,
    events: list[dict],
    request_log: Path,
    return_log: Path,
    matrix_a_path: Path,
) -> dict:
    requests = parse_requests(request_log)
    returns = parse_read_returns(return_log)
    matrix_a = read_128bit_words(matrix_a_path)
    enqueue_events = sorted(
        (
            event
            for event in events
            if event["kind"] == "DEEP_RD_ADDR_ENQUEUE"
        ),
        key=lambda event: (event["time"], event["ordinal"]),
    )
    request_by_channel: dict[int, list] = collections.defaultdict(list)
    enqueue_by_channel: dict[int, list[dict]] = collections.defaultdict(list)
    for request in requests:
        request_by_channel[request.channel].append(request)
    for event in enqueue_events:
        channel = _field_int(event, "ch")
        if channel is not None:
            enqueue_by_channel[channel].append(event)

    channel_fifo_mismatches: list[dict] = []
    compared_enqueue_count = 0
    for channel, channel_enqueues in sorted(enqueue_by_channel.items()):
        channel_requests = request_by_channel[channel]
        for index, event in enumerate(channel_enqueues):
            if index >= len(channel_requests):
                channel_fifo_mismatches.append(
                    {
                        "channel": channel,
                        "channel_index_zero_based": index,
                        "reason": "missing_local_request",
                    }
                )
                continue
            compared_enqueue_count += 1
            expected_address = _field_int(event, "addr_in")
            actual_address = channel_requests[index].address
            if expected_address != actual_address:
                channel_fifo_mismatches.append(
                    {
                        "channel": channel,
                        "channel_index_zero_based": index,
                        "enqueue_address_128bit": (
                            None
                            if expected_address is None
                            else f"0x{expected_address:06x}"
                        ),
                        "local_request_address_128bit": (
                            f"0x{actual_address:06x}"
                        ),
                    }
                )

    associated, unmatched_returns, pending_requests = associate_returns(
        requests, returns
    )
    payload_mismatches = [
        {
            "return_index_zero_based": index,
            "address_128bit": f"0x{address:06x}",
        }
        for index, (address, data) in enumerate(associated)
        if address >= len(matrix_a) or matrix_a[address] != data
    ]

    address_by_return: list[tuple[object, int]] = []
    pending_by_channel: dict[int, collections.deque[int]] = (
        collections.defaultdict(collections.deque)
    )
    for request in requests:
        pending_by_channel[request.channel].append(request.address)
    for returned in returns:
        if pending_by_channel[returned.return_channel]:
            address_by_return.append(
                (
                    returned,
                    pending_by_channel[returned.return_channel].popleft(),
                )
            )

    expected_addresses, _ = expected_read_addresses(
        outer_count=256,
        outer_stride_bytes=392,
        inner_start=0,
        inner_end=56,
        inner_stride=4,
        inner_dim_stride_bytes=8,
        transaction_bytes=32,
    )
    consume_events = [
        event for event in events if event["kind"] == "DEEP_RD_CONSUME"
    ]
    available: dict[int, collections.deque[tuple[object, int]]] = {
        0: collections.deque(),
        1: collections.deque(),
    }
    return_index = 0
    consume_mismatches: list[dict] = []
    consume_raw_mismatches: list[dict] = []
    for index, event in enumerate(consume_events):
        while (
            return_index < len(address_by_return)
            and address_by_return[return_index][0].return_time <= event["time"]
        ):
            returned, address = address_by_return[return_index]
            available[returned.return_channel].append((returned, address))
            return_index += 1
        channel = _field_int(event, "sel")
        if channel is None or not available[channel]:
            consume_mismatches.append(
                {
                    "consume_index_zero_based": index,
                    "reason": "no_available_return_for_selected_channel",
                }
            )
            continue
        returned, address = available[channel].popleft()
        raw_data = _field_int(event, f"raw{channel}")
        if raw_data != returned.data:
            consume_raw_mismatches.append(
                {
                    "consume_index_zero_based": index,
                    "channel": channel,
                }
            )
        expected_address = expected_addresses[index]
        if address != expected_address:
            consume_mismatches.append(
                {
                    "consume_index_zero_based": index,
                    "channel": channel,
                    "expected_address_128bit": f"0x{expected_address:06x}",
                    "actual_address_128bit": f"0x{address:06x}",
                }
            )

    matched = (
        not channel_fifo_mismatches
        and unmatched_returns == 0
        and pending_requests == 0
        and not payload_mismatches
        and not consume_mismatches
        and not consume_raw_mismatches
    )
    return {
        "classification": (
            "mse0_path_matched_in_probe_window"
            if matched
            else "mse0_local_log_correlation_mismatch"
        ),
        "request_enqueue_to_local_channel_fifo": {
            "compared_count": compared_enqueue_count,
            "mismatch_count": len(channel_fifo_mismatches),
            "first_mismatches": channel_fifo_mismatches[:16],
        },
        "ddr_return_payload": {
            "associated_count": len(associated),
            "unmatched_return_count": unmatched_returns,
            "pending_request_count": pending_requests,
            "exact_payload_mismatch_count": len(payload_mismatches),
            "first_mismatches": payload_mismatches[:16],
            "association_policy": "per_physical_return_channel_fifo",
        },
        "metadata_consume_window": {
            "consume_event_count": len(consume_events),
            "address_order_mismatch_count": len(consume_mismatches),
            "raw_payload_mismatch_count": len(consume_raw_mismatches),
            "first_address_mismatches": consume_mismatches[:16],
            "first_raw_payload_mismatches": consume_raw_mismatches[:16],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observer_log", type=Path)
    parser.add_argument("--mse0-request-log", type=Path)
    parser.add_argument("--mse0-return-log", type=Path)
    parser.add_argument("--matrix-a", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    events = parse_probe_events(args.observer_log.resolve())
    report = analyze_events(events)
    correlation_paths = (
        args.mse0_request_log,
        args.mse0_return_log,
        args.matrix_a,
    )
    if any(path is not None for path in correlation_paths):
        if not all(path is not None for path in correlation_paths):
            parser.error(
                "--mse0-request-log, --mse0-return-log and --matrix-a "
                "must be provided together"
            )
        report["local_log_correlation"] = correlate_local_logs(
            events=events,
            request_log=args.mse0_request_log.resolve(),
            return_log=args.mse0_return_log.resolve(),
            matrix_a_path=args.matrix_a.resolve(),
        )
        if (
            report["local_log_correlation"]["classification"]
            == "mse0_path_matched_in_probe_window"
        ):
            report["classification"] = "mse0_path_matched_in_probe_window"
            report["first_decisive_boundary"] = (
                "after MSE0 buffer write; inspect GA and MSE4"
            )
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
