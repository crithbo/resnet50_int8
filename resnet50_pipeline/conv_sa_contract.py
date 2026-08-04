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


def validate_first_conv_signed_a_local_contract(
    config: dict[str, Any],
) -> dict[str, Any]:
    """Validate the local signed-A/unsigned-B first-Conv transport.

    The RTL SA interprets inport0 as signed DataA and inport1 as unsigned
    DataB.  Therefore target A carries K8xC4 int8 weights, while targets B and
    B' are identical local Q8xC4 uint8 activation producers for the two
    inport1 ping-pong buffers.  This ABI deliberately has no neighbor stream.
    """

    streams = config.get("stream_engine")
    if not isinstance(streams, dict):
        raise ValueError("signed-A local Conv stream_engine is missing")
    expected_streams = {
        "stream0": ("A", "read", WEIGHT_TRANSACTION_BYTES),
        "stream1": ("B", "read", INPUT_TRANSACTION_BYTES),
        "stream2": ("B'", "read", INPUT_TRANSACTION_BYTES),
        "stream3": ("C", "read", BIAS_TRANSACTION_BYTES),
        "stream4": ("D", "write", OUTPUT_TRANSACTION_BYTES),
    }
    if set(streams) != set(expected_streams):
        raise ValueError("signed-A local Conv must define exactly five streams")
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

    if config.get("n2n") not in ({}, None):
        raise ValueError("signed-A local Conv must not depend on a neighbor stream")

    # B and B' are two physical READ producers for the same activation bytes.
    activation_fields = (
        "mode",
        "base_addr",
        "mem_idx_mode",
        "mem_idx_keep_last_index",
        "idx",
        "idx_size",
        "dim_stride",
        "padding_enable",
        "idx_padding_range",
        "tailing_enable",
        "idx_tailing_range",
        "address_remapping",
        "buf_idx_mode",
        "buf_idx_keep_last_index",
        "buf_spatial_stride",
        "buf_spatial_size",
        "buf_full_last_index",
        "ping_pong",
        "pingpong_last_index",
    )
    for field in activation_fields:
        if streams["stream1"].get(field) != streams["stream2"].get(field):
            raise ValueError(f"B/B' activation producers differ in {field}")

    groups = config.get("buffer_loop_configs")
    expected_group_targets = {
        "GROUP0": "A",
        "GROUP1": "B",
        "GROUP2": "B'",
        "GROUP3": "C",
        "GROUP4": "D",
    }
    if not isinstance(groups, dict) or set(groups) != set(expected_group_targets):
        raise ValueError("signed-A local Conv must define all five buffer groups")
    group_bytes: dict[str, int] = {}
    for name, target in expected_group_targets.items():
        group = groups[name]
        if group.get("target") != target:
            raise ValueError(f"{name} must target {target}")
        group_bytes[name] = buffer_loop_bytes(group)
        stream_name = f"stream{name.removeprefix('GROUP')}"
        stream = streams[stream_name]
        if stream.get("buf_idx_mode") != ["keep", "buffer"]:
            raise ValueError(
                f"{stream_name} Buffer-AG must keep ROW and buffer COL"
            )
        keep_thresholds = stream.get("buf_idx_keep_last_index")
        col_terminal = int(group["COL_LC"].get("last_index", -1))
        if (
            not isinstance(keep_thresholds, list)
            or len(keep_thresholds) != 2
            or int(keep_thresholds[0]) != col_terminal
        ):
            raise ValueError(
                f"{stream_name} ROW keep threshold must equal "
                f"{name}.COL_LC.last_index {col_terminal}"
            )
    for name in ("GROUP0", "GROUP1", "GROUP2", "GROUP4"):
        if group_bytes[name] != INPUT_BUFFER_BYTES:
            raise ValueError(f"{name} must cover one complete 128B SA buffer")
    if group_bytes["GROUP3"] != BIAS_BUFFER_BYTES:
        raise ValueError("GROUP3 must cover one 32B K8 bias row")
    for field in ("ROW_LC", "COL_LC"):
        left = {**groups["GROUP1"][field], "src_id": None}
        right = {**groups["GROUP2"][field], "src_id": None}
        if left != right:
            raise ValueError(f"B/B' buffer groups differ in {field}")

    bias_stream = streams["stream3"]
    if bias_stream.get("idx") != [
        "DRAM_LC.LC10",
        "DRAM_LC.LC11",
        "DRAM_LC.LC12",
    ]:
        raise ValueError("stream3 must use the Kblock/H/Qblock bias tile branch")
    if bias_stream.get("dim_stride") != [BIAS_TRANSACTION_BYTES, 0, 0]:
        raise ValueError("stream3 bias address must change only by 32B per Kblock")
    if (
        groups["GROUP3"]["ROW_LC"].get("src_id") != "DRAM_LC.LC12"
        or groups["GROUP3"]["COL_LC"].get("src_id") != "GROUP3.ROW_LC"
    ):
        raise ValueError("GROUP3 must follow the Qblock bias tile event")

    buffers = config.get("buffer_config")
    if not isinstance(buffers, dict):
        raise ValueError("signed-A local Conv buffer_config is missing")
    for index in range(6):
        buffer = buffers.get(f"buffer{index}")
        if not isinstance(buffer, dict):
            raise ValueError(f"signed-A local Conv buffer{index} is missing")
        if int(buffer.get("nbr_enable", -1)) != 0:
            raise ValueError(f"buffer{index} must be local")
        if int(buffer.get("buffer_nbr_cnt", -1)) != 0:
            raise ValueError(f"buffer{index}.buffer_nbr_cnt must be zero")
    if (
        int(buffers["buffer4"].get("buf_full_last_index", -1)) != 2
        or int(buffers["buffer4"].get("buffer_life_time", -1))
        != SA_BIAS_HANDSHAKES_PER_TILE
    ):
        raise ValueError("buffer4 must provide four bias handshakes per output tile")

    sa = config.get("special_array")
    if not isinstance(sa, dict) or sa.get("data_type") != "int8":
        raise ValueError("signed-A local Conv requires the INT8 SpecialArray")
    if int(sa.get("bias_enable", 0)) != 1:
        raise ValueError("signed-A local Conv must enable bias")
    for inport in ("inport0", "inport1"):
        cfg = sa.get(inport)
        if not isinstance(cfg, dict):
            raise ValueError(f"signed-A local Conv {inport} is missing")
        if int(cfg.get("nbr_enable", -1)) != 0:
            raise ValueError(f"signed-A local Conv {inport} must be local")
        if int(cfg.get("pingpong_en", 0)) != 1:
            raise ValueError(f"signed-A local Conv {inport} must ping-pong")
        if int(cfg.get("pingpong_last_index", -1)) != 4:
            raise ValueError(f"signed-A local Conv {inport} terminal tag must be 4")

    # READ0 is the only producer for the two physical A buffers (buffer0/1).
    # Its MSE-side selector and SA inport0's consumer-side selector are
    # independent RTL state machines; unilateral ping-pong makes SA switch to
    # an unwritten buffer after the first accepted terminal transaction.
    a_stream = streams["stream0"]
    a_inport = sa["inport0"]
    if int(a_stream.get("ping_pong", 0)) != int(
        a_inport.get("pingpong_en", 0)
    ):
        raise ValueError(
            "stream0/SA inport0 ping-pong enables must match for buffer0/1"
        )
    if int(a_stream.get("pingpong_last_index", -1)) != int(
        a_inport.get("pingpong_last_index", -1)
    ):
        raise ValueError(
            "stream0/SA inport0 ping-pong terminal tags must match"
        )
    if sa.get("outport", {}).get("mode") != "row":
        raise ValueError("signed-A local Conv must transpose KxQ to QxK at the SA outport")

    if int(streams["stream0"].get("buf_full_last_index", -1)) != 4:
        raise ValueError("signed weight stream terminal tag must be index4")
    for name in ("stream1", "stream2"):
        if int(streams[name].get("buf_full_last_index", -1)) != 4:
            raise ValueError(f"{name} activation terminal tag must be index4")
    if int(streams["stream3"].get("buf_full_last_index", -1)) != 2:
        raise ValueError("bias stream terminal tag must be index2")

    return {
        "status": "static_signed_a_local_sa_contract_pass",
        "stream_transaction_bytes": stream_bytes,
        "buffer_loop_bytes": group_bytes,
        "activation_read_streams": [1, 2],
        "neighbor_stream_count": 0,
        "sa_data_a_role": "signed_int8_weight",
        "sa_data_b_role": "unsigned_uint8_activation",
        "a_pingpong_binding": {
            "mse_stream": 0,
            "physical_buffers": [0, 1],
            "sa_inport": 0,
            "enabled": True,
            "terminal_tag": 4,
        },
        "output_transaction_bytes": OUTPUT_TRANSACTION_BYTES,
    }


def validate_conv_3x3_sa_contract(
    config: dict[str, Any],
    *,
    output_height: int,
    output_width: int,
    c_quartets: int,
    k_blocks: int,
    halo_width_padded: int,
) -> dict[str, Any]:
    """Validate the transaction-packed 3x3/pad1 SA microprogram.

    The activation port is an explicit x-zero-point halo staged as
    ``N-HaloH-Cquartet-HaloW-C4``.  This keeps every shifted Q8xC4 read a
    complete 32-byte transaction; the stream engine never has to synthesize a
    partial four-byte padding lane.
    """

    if (
        output_height <= 0
        or output_width <= 0
        or output_width % SA_SPATIAL_LANES
        or c_quartets <= 0
        or k_blocks <= 0
        or halo_width_padded < output_width + 2
        or halo_width_padded % SA_SPATIAL_LANES
    ):
        raise ValueError("3x3 SA geometry is not transaction aligned")
    q_blocks = output_width // SA_SPATIAL_LANES
    loops = config["dram_loop_configs"]
    loop_contract = {
        "LC0": (None, k_blocks, 0),
        "LC1": ("DRAM_LC.LC0", output_height, 1),
        "LC2": ("DRAM_LC.LC1", q_blocks, 2),
        "LC4": ("DRAM_LC.LC2", 3, 3),
        "LC5": ("DRAM_LC.LC4", 3, 4),
        "LC3": ("DRAM_LC.LC5", c_quartets, 5),
        "LC6": ("DRAM_LC.LC5", HIGH_RING_STEPS, 5),
        "LC7": ("DRAM_LC.LC6", c_quartets, 6),
        "LC13": (None, k_blocks, 0),
        "LC14": ("DRAM_LC.LC13", output_height, 1),
        "LC15": ("DRAM_LC.LC14", q_blocks, 2),
        "LC9": ("DRAM_LC.LC15", SA_SPATIAL_LANES, 3),
        "LC10": (None, k_blocks, 0),
        "LC11": ("DRAM_LC.LC10", output_height, 1),
        "LC12": ("DRAM_LC.LC11", q_blocks, 2),
    }
    for name, (source, count, last_index) in loop_contract.items():
        loop = loops.get(name)
        if not isinstance(loop, dict):
            raise ValueError(f"3x3 SA loop is missing {name}")
        if (
            loop.get("src_id") != source
            or _loop_trip_count(loop, name=name) != count
            or int(loop.get("last_index", -1)) != last_index
            or int(loop.get("outmost_loop", -1)) != (1 if source is None else 0)
        ):
            raise ValueError(f"3x3 SA loop contract differs: {name}")
    unused = loops.get("LC8")
    if not isinstance(unused, dict) or any(
        unused.get(field) != value
        for field, value in (
            ("src_id", None),
            ("outmost_loop", 0),
            ("start", 0),
            ("end", 0),
            ("stride", 0),
            ("last_index", 0),
        )
    ):
        raise ValueError("3x3 SA LC8 must remain explicitly unused")

    pe = config["lc_pe_configs"]
    expected_pe = {
        "PE0": ("DRAM_LC.LC2", SA_SPATIAL_LANES, "DRAM_LC.LC5"),
        "PE1": ("DRAM_LC.LC1", 1, "DRAM_LC.LC4"),
        "PE2": ("DRAM_LC.LC6", c_quartets, "DRAM_LC.LC7"),
        "PE3": ("DRAM_LC.LC4", 3, "DRAM_LC.LC5"),
        "PE4": ("DRAM_LC.LC15", SA_SPATIAL_LANES, "DRAM_LC.LC9"),
    }
    if set(pe) != set(expected_pe):
        raise ValueError("3x3 SA LC-PE inventory differs")
    for name, (source0, constant, source2) in expected_pe.items():
        record = pe[name]
        if (
            record.get("alu_opcode") != "mac"
            or record.get("inport0", {}).get("src_id") != source0
            or record.get("inport1", {}).get("src_id") is not None
            or record.get("inport1", {}).get("mode") != "constant"
            or int(record.get("inport1", {}).get("constant", -1)) != constant
            or record.get("inport2", {}).get("src_id") != source2
        ):
            raise ValueError(f"3x3 SA LC-PE formula differs: {name}")

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
        actual = stream_total_bytes(stream)
        if (
            stream.get("target") != target
            or stream.get("mode") != mode
            or actual != expected_bytes
        ):
            raise ValueError(f"3x3 {name} route/transaction differs")
        if stream.get("padding_enable") != [0, 0, 0]:
            raise ValueError(f"3x3 {name} must not use dynamic stream padding")
        stream_bytes[name] = actual

    activation = streams["stream0"]
    if (
        activation.get("idx") != ["DRAM_LC.LC3", "LC_PE.PE0", "LC_PE.PE1"]
        or activation.get("idx_size") != [31, 0, 0]
        or activation.get("dim_stride")
        != [
            halo_width_padded * SA_CHANNEL_LANES,
            SA_CHANNEL_LANES,
            c_quartets * halo_width_padded * SA_CHANNEL_LANES,
        ]
        or activation.get("mem_idx_mode") != ["buffer", "keep", "keep"]
        or int(activation.get("buf_full_last_index", -1)) != 5
    ):
        raise ValueError("3x3 activation halo address contract differs")
    weight = streams["stream1"]
    if (
        weight.get("idx") != ["LC_PE.PE2", "LC_PE.PE3", "DRAM_LC.LC0"]
        or weight.get("idx_size") != [31, 0, 0]
        or weight.get("dim_stride")
        != [
            k_blocks * WEIGHT_TRANSACTION_BYTES,
            HIGH_RING_STEPS * c_quartets * k_blocks * WEIGHT_TRANSACTION_BYTES,
            WEIGHT_TRANSACTION_BYTES,
        ]
        or weight.get("mem_idx_mode") != ["buffer", "keep", "keep"]
        or int(weight.get("buf_full_last_index", -1)) != 6
    ):
        raise ValueError("3x3 weight address contract differs")
    output = streams["stream2"]
    if (
        output.get("idx") != ["DRAM_LC.LC13", "LC_PE.PE4", "DRAM_LC.LC14"]
        or output.get("idx_size") != [31, 0, 0]
        or output.get("dim_stride")
        != [
            OUTPUT_TRANSACTION_BYTES,
            k_blocks * OUTPUT_TRANSACTION_BYTES,
            q_blocks
            * SA_SPATIAL_LANES
            * k_blocks
            * OUTPUT_TRANSACTION_BYTES,
        ]
    ):
        raise ValueError("3x3 output address contract differs")
    bias = streams["stream3"]
    if (
        bias.get("idx") != ["DRAM_LC.LC10", "DRAM_LC.LC11", "DRAM_LC.LC12"]
        or bias.get("idx_size") != [31, 0, 0]
        or bias.get("dim_stride") != [BIAS_TRANSACTION_BYTES, 0, 0]
        or bias.get("mem_idx_mode") != ["keep", "keep", "buffer"]
        or int(bias.get("buf_full_last_index", -1)) != 2
    ):
        raise ValueError("3x3 bias tile address contract differs")

    n2n = config.get("n2n")
    if not isinstance(n2n, dict) or set(n2n) != {"neighbor_stream0"}:
        raise ValueError("3x3 activation must use neighbor_stream0")
    if n2n["neighbor_stream0"] != {
        "mem_loop": HIGH_RING_STEPS,
        "src_slice_sel": 1,
        "dst_slice_sel": 1,
        "ping_pong": 0,
    }:
        raise ValueError("3x3 HIGH-4 neighbor contract differs")

    groups = config["buffer_loop_configs"]
    group_bytes = {name: buffer_loop_bytes(group) for name, group in groups.items()}
    if (
        group_bytes.get("GROUP0") != INPUT_BUFFER_BYTES
        or group_bytes.get("GROUP1") != INPUT_BUFFER_BYTES
        or group_bytes.get("GROUP2") != BIAS_BUFFER_BYTES
    ):
        raise ValueError("3x3 SA input/bias buffer byte contract differs")
    group_sources = {
        "GROUP0": ("A", "DRAM_LC.LC5", 5, 6),
        "GROUP1": ("B", "DRAM_LC.LC6", 6, 7),
        "GROUP2": ("C", "DRAM_LC.LC12", 3, 4),
        "GROUP3": ("D", "DRAM_LC.LC9", 4, 5),
    }
    for name, (target, row_source, row_last, col_last) in group_sources.items():
        group = groups[name]
        if (
            group.get("target") != target
            or group["ROW_LC"].get("src_id") != row_source
            or int(group["ROW_LC"].get("last_index", -1)) != row_last
            or group["COL_LC"].get("src_id") != f"{name}.ROW_LC"
            or int(group["COL_LC"].get("last_index", -1)) != col_last
        ):
            raise ValueError(f"3x3 buffer-loop contract differs: {name}")

    buffers = config["buffer_config"]
    for index in range(6):
        if int(buffers[f"buffer{index}"].get("buffer_nbr_cnt", -1)) != 3:
            raise ValueError("3x3 buffers must encode HIGH-4 as neighbor count 3")
    if [int(buffers[f"buffer{index}"].get("nbr_enable", -1)) for index in range(6)] != [
        1,
        1,
        0,
        0,
        0,
        0,
    ]:
        raise ValueError("3x3 neighbor buffer ownership differs")
    if (
        [int(buffers[f"buffer{index}"].get("buf_full_last_index", -1)) for index in range(6)]
        != [5, 5, 6, 6, 2, 2]
        or int(buffers["buffer4"].get("buffer_life_time", -1))
        != SA_BIAS_HANDSHAKES_PER_TILE
    ):
        raise ValueError("3x3 buffer terminal/lifetime contract differs")

    sa = config["special_array"]
    if (
        int(sa.get("bias_enable", 0)) != 1
        or int(sa["inport0"].get("nbr_enable", 0)) != 1
        or int(sa["inport1"].get("nbr_enable", 0)) != 0
        or int(sa["inport0"].get("pingpong_last_index", -1)) != 5
        or int(sa["inport1"].get("pingpong_last_index", -1)) != 6
    ):
        raise ValueError("3x3 SpecialArray port contract differs")

    return {
        "status": "static_3x3_sa_contract_pass",
        "stream_transaction_bytes": stream_bytes,
        "buffer_loop_bytes": group_bytes,
        "activation_neighbor_stream": 0,
        "high_ring_steps": HIGH_RING_STEPS,
        "kernel_shape": [3, 3],
        "explicit_halo": {
            "width_padded": halo_width_padded,
            "padding_source": "x_zero_point",
            "dynamic_stream_padding": False,
        },
        "bias_extent_bytes": k_blocks * BIAS_TRANSACTION_BYTES,
        "bias_transaction_count": k_blocks * output_height * q_blocks,
        "bias_unique_address_count": k_blocks,
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
    "validate_conv_3x3_sa_contract",
    "validate_first_conv_sa_contract",
]
