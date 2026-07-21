"""Shared physical/stream contract for the RTL28 INT8 Conv SA stage.

The contract deliberately describes bytes and ownership, not model semantics.
It is consumed by the physical packer, the JSON generator and pre-server
static tests so that a change cannot repair only one side of the transport.
"""

from __future__ import annotations

import math
from typing import Any


SA_SPATIAL_LANES = 8
SA_CHANNEL_LANES = 4
SA_OUTPUT_LANES = 8
HIGH_RING_STEPS = 4
SA_BIAS_HANDSHAKES_PER_TILE = 4

INPUT_TRANSACTION_BYTES = SA_SPATIAL_LANES * SA_CHANNEL_LANES
WEIGHT_TRANSACTION_BYTES = SA_OUTPUT_LANES * SA_CHANNEL_LANES
BIAS_TRANSACTION_BYTES = SA_OUTPUT_LANES * 4
OUTPUT_TRANSACTION_BYTES = SA_OUTPUT_LANES * 4

BUFFER_VECTOR_BYTES = 16
INPUT_BUFFER_BYTES = 4 * INPUT_TRANSACTION_BYTES
BIAS_BUFFER_BYTES = BIAS_TRANSACTION_BYTES


def ceil_div(value: int, divisor: int) -> int:
    if value <= 0 or divisor <= 0:
        raise ValueError("ceil_div operands must be positive")
    return math.ceil(value / divisor)


def stream_total_bytes(stream: dict[str, Any]) -> int:
    sizes = stream.get("idx_size")
    if not isinstance(sizes, list) or len(sizes) != 3:
        raise ValueError("stream idx_size must contain three dimensions")
    total = 1
    for size in sizes:
        total *= 1 if size is None else int(size) + 1
    return total


def buffer_loop_bytes(group: dict[str, Any]) -> int:
    row = group["ROW_LC"]
    col = group["COL_LC"]
    row_count = len(range(int(row["start"]), int(row["end"]), int(row["stride"])))
    col_count = len(range(int(col["start"]), int(col["end"]), int(col["stride"])))
    return row_count * col_count * BUFFER_VECTOR_BYTES


def _loop_trip_count(loop: dict[str, Any], *, name: str) -> int:
    try:
        values = range(int(loop["start"]), int(loop["end"]), int(loop["stride"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must define an integer [start,end) loop") from exc
    count = len(values)
    if count <= 0:
        raise ValueError(f"{name} must execute at least once")
    return count


def validate_first_conv_sa_contract(config: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on the byte, route and terminal-tag invariants.

    This validation intentionally rejects the v8 layout: its weight stream
    totals four bytes and its bias range is 128 bytes.  Passing the official
    encoder alone is insufficient because those values are perfectly
    encodable while being physically incompatible with the buffers.
    """

    streams = config["stream_engine"]
    expected_streams = {
        "stream0": ("A", "read", INPUT_TRANSACTION_BYTES),
        "stream1": ("B", "read", WEIGHT_TRANSACTION_BYTES),
        "stream2": ("D", "write", OUTPUT_TRANSACTION_BYTES),
        "stream3": ("C", "read", BIAS_TRANSACTION_BYTES),
    }
    stream_bytes: dict[str, int] = {}
    for name, (target, mode, expected_bytes) in expected_streams.items():
        stream = streams[name]
        if stream.get("target") != target or stream.get("mode") != mode:
            raise ValueError(f"{name} route must be {mode} target {target}")
        actual = stream_total_bytes(stream)
        if actual != expected_bytes:
            raise ValueError(
                f"{name} transaction is {actual}B; expected {expected_bytes}B"
            )
        stream_bytes[name] = actual

    n2n = config.get("n2n")
    if not isinstance(n2n, dict) or set(n2n) != {"neighbor_stream0"}:
        raise ValueError("activation must circulate through neighbor_stream0")
    neighbor = n2n["neighbor_stream0"]
    if int(neighbor.get("mem_loop", -1)) != HIGH_RING_STEPS:
        raise ValueError("neighbor_stream0 must traverse all four HIGH owners")

    buffers = config["buffer_config"]
    for index in range(6):
        if int(buffers[f"buffer{index}"].get("buffer_nbr_cnt", -1)) != 3:
            raise ValueError(f"buffer{index}.buffer_nbr_cnt must encode HIGH-4 as 3")
    for index in (0, 1):
        if int(buffers[f"buffer{index}"].get("nbr_enable", 0)) != 1:
            raise ValueError("both activation ping-pong buffers must enable neighbors")
    for index in (2, 3, 4, 5):
        if int(buffers[f"buffer{index}"].get("nbr_enable", 0)) != 0:
            raise ValueError(f"buffer{index} must remain local")

    sa = config["special_array"]
    if int(sa.get("bias_enable", 0)) != 1:
        raise ValueError("SA bias input must be enabled")
    if int(sa["inport0"].get("nbr_enable", 0)) != 1:
        raise ValueError("SA inport0 must consume the activation neighbor ring")
    if int(sa["inport1"].get("nbr_enable", 0)) != 0:
        raise ValueError("SA inport1 weights must be local")

    groups = config["buffer_loop_configs"]
    group_bytes = {name: buffer_loop_bytes(group) for name, group in groups.items()}
    if group_bytes["GROUP0"] != INPUT_BUFFER_BYTES:
        raise ValueError("GROUP0 must read one complete 128B activation buffer")
    if group_bytes["GROUP1"] != INPUT_BUFFER_BYTES:
        raise ValueError("GROUP1 must read one complete 128B weight buffer")
    if group_bytes["GROUP2"] != BIAS_BUFFER_BYTES:
        raise ValueError("GROUP2 must read exactly one K8 int32 bias row (32B)")

    loops = config["dram_loop_configs"]
    bias_branch = ("LC10", "LC11", "LC12")
    expected_bias_sources = (None, "DRAM_LC.LC10", "DRAM_LC.LC11")
    expected_last_indices = (0, 1, 2)
    expected_main_loops = ("LC0", "LC1", "LC2")
    for name, source, last_index, main_name in zip(
        bias_branch,
        expected_bias_sources,
        expected_last_indices,
        expected_main_loops,
        strict=True,
    ):
        loop = loops.get(name)
        if not isinstance(loop, dict):
            raise ValueError(f"bias tile branch is missing {name}")
        if loop.get("src_id") != source:
            raise ValueError(f"{name}.src_id must be {source!r} for the bias tile branch")
        if int(loop.get("last_index", -1)) != last_index:
            raise ValueError(f"{name}.last_index must be {last_index}")
        if int(loop.get("outmost_loop", -1)) != (1 if name == "LC10" else 0):
            raise ValueError(f"{name}.outmost_loop does not match the bias tile branch")
        if _loop_trip_count(loop, name=name) != _loop_trip_count(
            loops[main_name], name=main_name
        ):
            raise ValueError(f"{name} must match {main_name} tile count")

    bias_stream = streams["stream3"]
    if bias_stream.get("idx") != [
        "DRAM_LC.LC10",
        "DRAM_LC.LC11",
        "DRAM_LC.LC12",
    ]:
        raise ValueError("stream3 must be driven by the Kblock/H/Qblock bias tile branch")
    if bias_stream.get("mem_idx_mode") != ["keep", "keep", "buffer"]:
        raise ValueError("stream3 must buffer on Qblock and keep Kblock/H")
    if bias_stream.get("mem_idx_keep_last_index") != [0, 1, 2]:
        raise ValueError("stream3 memory last-index chain must be 0/1/2")
    if bias_stream.get("dim_stride") != [BIAS_TRANSACTION_BYTES, 0, 0]:
        raise ValueError("stream3 bias address must change only by 32B per Kblock")
    if bias_stream.get("buf_idx_mode") != ["keep", "buffer"]:
        raise ValueError("stream3 buffer address must keep ROW and buffer COL")
    if bias_stream.get("buf_idx_keep_last_index") != [3, 4]:
        raise ValueError("stream3 buffer last-index chain must be GROUP2 row/col 3/4")

    group2 = groups["GROUP2"]
    row2 = group2["ROW_LC"]
    col2 = group2["COL_LC"]
    if row2.get("src_id") != "DRAM_LC.LC12" or int(row2.get("last_index", -1)) != 3:
        raise ValueError("GROUP2 row must start from the Qblock bias tile event/index3")
    if col2.get("src_id") != "GROUP2.ROW_LC" or int(col2.get("last_index", -1)) != 4:
        raise ValueError("GROUP2 col must complete the bias row at index4")

    bias_buffer = buffers["buffer4"]
    if int(bias_buffer.get("buf_full_last_index", -1)) != 2:
        raise ValueError("buffer4 must become full on the Qblock bias tile event/index2")
    if int(bias_buffer.get("buffer_life_time", -1)) != SA_BIAS_HANDSHAKES_PER_TILE:
        raise ValueError("buffer4 must provide four bias handshakes per output tile")

    # The producer completes exactly on the loop index used to release its
    # buffer.  A wider threshold is encodable but can hide an unreachable tag.
    if int(streams["stream0"].get("buf_full_last_index", -1)) != 3:
        raise ValueError("stream0 terminal tag must be LC3/index3")
    if int(streams["stream1"].get("buf_full_last_index", -1)) != 4:
        raise ValueError("stream1 terminal tag must be LC7/index4")
    if int(streams["stream3"].get("buf_full_last_index", -1)) != 2:
        raise ValueError("stream3 terminal tag must be the Qblock bias tile loop/index2")

    bias_trip_counts = [
        _loop_trip_count(loops[name], name=name) for name in bias_branch
    ]
    bias_transaction_count = math.prod(bias_trip_counts)
    bias_unique_addresses = bias_trip_counts[0]

    return {
        "status": "static_sa_contract_pass",
        "stream_transaction_bytes": stream_bytes,
        "buffer_loop_bytes": group_bytes,
        "activation_neighbor_stream": 0,
        "high_ring_steps": HIGH_RING_STEPS,
        "bias_extent_bytes": bias_unique_addresses * BIAS_TRANSACTION_BYTES,
        "bias_transaction_count": bias_transaction_count,
        "bias_unique_address_count": bias_unique_addresses,
        "bias_handshakes_per_tile": SA_BIAS_HANDSHAKES_PER_TILE,
        "output_transaction_bytes": OUTPUT_TRANSACTION_BYTES,
    }


__all__ = [
    "BIAS_BUFFER_BYTES",
    "BIAS_TRANSACTION_BYTES",
    "BUFFER_VECTOR_BYTES",
    "HIGH_RING_STEPS",
    "INPUT_BUFFER_BYTES",
    "INPUT_TRANSACTION_BYTES",
    "OUTPUT_TRANSACTION_BYTES",
    "SA_CHANNEL_LANES",
    "SA_BIAS_HANDSHAKES_PER_TILE",
    "SA_OUTPUT_LANES",
    "SA_SPATIAL_LANES",
    "WEIGHT_TRANSACTION_BYTES",
    "buffer_loop_bytes",
    "ceil_div",
    "stream_total_bytes",
    "validate_first_conv_sa_contract",
]
