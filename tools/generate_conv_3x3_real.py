from __future__ import annotations

from copy import deepcopy
from typing import Any

from resnet50_pipeline.conv_instance import (
    SA_ONLY_CONFIG_MASK,
    ConvInstanceSpec,
    validate_conv_accumulate_config_mask,
    validate_conv_accumulate_neighbor_ring,
    validate_conv_accumulate_output_route,
)
from resnet50_pipeline.conv_sa_contract import (
    HIGH_RING_STEPS,
    SA_CHANNEL_LANES,
    SA_OUTPUT_LANES,
    SA_SPATIAL_LANES,
    ceil_div,
    validate_conv_3x3_sa_contract,
)


def _pe_mac(
    source0: str,
    *,
    keep_last_index: int,
    constant: int,
    source2: str,
) -> dict[str, Any]:
    return {
        "alu_opcode": "mac",
        "inport2": {
            "src_id": source2,
            "mode": "buffer",
            "keep_last_index": None,
            "constant": 0,
        },
        "inport1": {
            "src_id": None,
            "mode": "constant",
            "keep_last_index": None,
            "constant": constant,
        },
        "inport0": {
            "src_id": source0,
            "mode": "keep",
            "keep_last_index": keep_last_index,
            "constant": 0,
        },
    }


def build_real_3x3(source: dict[str, Any], spec: ConvInstanceSpec) -> dict[str, Any]:
    """Lower node-0005 geometry to a current-ABI 3x3 SA microprogram.

    The static program covers one storage sample.  Batch-16 is scheduled in
    three waves by the typed request.  A is an explicitly staged pad-1 halo in
    ``N-HaloH-Cquartet-HaloW-C4`` order, so every shifted window access remains
    a complete 32-byte Q8xC4 transaction.
    """

    spec.validate()
    if (
        spec.kernel != (3, 3)
        or spec.strides != (1, 1)
        or spec.pads != (1, 1, 1, 1)
        or spec.dilations != (1, 1)
    ):
        raise ValueError("real 3x3 generator requires kernel3/stride1/pad1/dilation1")
    if spec.output_width % SA_SPATIAL_LANES:
        raise ValueError("real 3x3 generator requires an output width divisible by Q8")

    c_quartets = ceil_div(spec.c_tile, SA_CHANNEL_LANES)
    k_blocks = ceil_div(spec.k_tile, SA_OUTPUT_LANES)
    q_blocks = spec.output_width // SA_SPATIAL_LANES
    halo_width = spec.activation_shape[3] + spec.pads[1] + spec.pads[3]
    halo_width_padded = ceil_div(halo_width, SA_SPATIAL_LANES) * SA_SPATIAL_LANES

    config = deepcopy(source)
    config["CONFIG"] = SA_ONLY_CONFIG_MASK
    loops = config["dram_loop_configs"]
    if set(loops) != {f"LC{index}" for index in range(16)}:
        raise ValueError("Conv source loop inventory differs from the reviewed skeleton")
    for loop in loops.values():
        loop.update(
            src_id=None,
            outmost_loop=0,
            start=0,
            end=0,
            stride=0,
            last_index=0,
        )
    loop_contract = {
        "LC0": (None, 1, k_blocks, 0),
        "LC1": ("DRAM_LC.LC0", 0, spec.output_height, 1),
        "LC2": ("DRAM_LC.LC1", 0, q_blocks, 2),
        "LC4": ("DRAM_LC.LC2", 0, 3, 3),
        "LC5": ("DRAM_LC.LC4", 0, 3, 4),
        # Sibling branches load the local activation C quartet once and the
        # destination-relative PREV-ring weight quartets four times.
        "LC3": ("DRAM_LC.LC5", 0, c_quartets, 5),
        "LC6": ("DRAM_LC.LC5", 0, HIGH_RING_STEPS, 5),
        "LC7": ("DRAM_LC.LC6", 0, c_quartets, 6),
        # Value-identical write and bias branches retain the proven physical
        # IGA endpoint split used by the current 1x1 program.
        "LC13": (None, 1, k_blocks, 0),
        "LC14": ("DRAM_LC.LC13", 0, spec.output_height, 1),
        "LC15": ("DRAM_LC.LC14", 0, q_blocks, 2),
        "LC9": ("DRAM_LC.LC15", 0, SA_SPATIAL_LANES, 3),
        "LC10": (None, 1, k_blocks, 0),
        "LC11": ("DRAM_LC.LC10", 0, spec.output_height, 1),
        "LC12": ("DRAM_LC.LC11", 0, q_blocks, 2),
    }
    for name, (source_id, outmost, end, last_index) in loop_contract.items():
        loops[name].update(
            src_id=source_id,
            outmost_loop=outmost,
            start=0,
            end=end,
            stride=1,
            last_index=last_index,
        )

    config["lc_pe_configs"] = {
        # q_input = q_block*8 + kernel_s
        "PE0": _pe_mac(
            "DRAM_LC.LC2",
            keep_last_index=4,
            constant=SA_SPATIAL_LANES,
            source2="DRAM_LC.LC5",
        ),
        # h_input = output_h + kernel_r (the staged halo already owns pad1)
        "PE1": _pe_mac(
            "DRAM_LC.LC1",
            keep_last_index=3,
            constant=1,
            source2="DRAM_LC.LC4",
        ),
        # source_Cquartet = PREV_ring_step*c_quartets + local_c_quartet
        "PE2": _pe_mac(
            "DRAM_LC.LC6",
            keep_last_index=5,
            constant=c_quartets,
            source2="DRAM_LC.LC7",
        ),
        # flattened kernel position = r*3+s
        "PE3": _pe_mac(
            "DRAM_LC.LC4",
            keep_last_index=4,
            constant=3,
            source2="DRAM_LC.LC5",
        ),
        # output Q coordinate = q_block*8+q_lane
        "PE4": _pe_mac(
            "DRAM_LC.LC15",
            keep_last_index=2,
            constant=SA_SPATIAL_LANES,
            source2="DRAM_LC.LC9",
        ),
    }

    streams = config["stream_engine"]

    def reset_stream(name: str, *, target: str, mode: str) -> dict[str, Any]:
        stream = streams[name]
        stream.update(target=target, mode=mode)
        stream["padding_enable"] = [0, 0, 0]
        stream["padding_reg_value"] = None
        stream["idx_padding_range"] = {
            "low_bound": [None, None, None],
            "up_bound": [None, None, None],
        }
        stream["tailing_enable"] = [0, 0, 0]
        stream["idx_tailing_range"] = {
            "low": [None, None, None],
            "up": [None, None, None],
        }
        stream["address_remapping"] = None
        stream["buf_spatial_size"] = 16
        stream["ping_pong"] = 0
        stream["pingpong_last_index"] = None
        return stream

    activation = reset_stream("stream0", target="A", mode="read")
    activation.update(
        idx=["DRAM_LC.LC3", "LC_PE.PE0", "LC_PE.PE1"],
        idx_size=[31, 0, 0],
        dim_stride=[
            halo_width_padded * SA_CHANNEL_LANES,
            SA_CHANNEL_LANES,
            c_quartets * halo_width_padded * SA_CHANNEL_LANES,
        ],
        mem_idx_mode=["buffer", "keep", "keep"],
        mem_idx_keep_last_index=[5, 5, 4],
        buf_idx_mode=["keep", "buffer"],
        buf_idx_keep_last_index=[5, 6],
        buf_spatial_stride=list(range(16)),
        buf_full_last_index=5,
    )

    weight = reset_stream("stream1", target="B", mode="read")
    weight.update(
        idx=["LC_PE.PE2", "LC_PE.PE3", "DRAM_LC.LC0"],
        idx_size=[31, 0, 0],
        dim_stride=[
            k_blocks * SA_OUTPUT_LANES * SA_CHANNEL_LANES,
            HIGH_RING_STEPS
            * c_quartets
            * k_blocks
            * SA_OUTPUT_LANES
            * SA_CHANNEL_LANES,
            SA_OUTPUT_LANES * SA_CHANNEL_LANES,
        ],
        mem_idx_mode=["buffer", "keep", "keep"],
        mem_idx_keep_last_index=[7, 5, 0],
        buf_idx_mode=["keep", "buffer"],
        buf_idx_keep_last_index=[6, 7],
        buf_spatial_stride=list(range(16)),
        buf_full_last_index=6,
    )

    output = reset_stream("stream2", target="D", mode="write")
    output.update(
        idx=["DRAM_LC.LC13", "LC_PE.PE4", "DRAM_LC.LC14"],
        idx_size=[31, 0, 0],
        dim_stride=[
            SA_OUTPUT_LANES * 4,
            k_blocks * SA_OUTPUT_LANES * 4,
            q_blocks * SA_SPATIAL_LANES * k_blocks * SA_OUTPUT_LANES * 4,
        ],
        mem_idx_mode=["keep", "buffer", "keep"],
        mem_idx_keep_last_index=[0, 4, 1],
        buf_idx_mode=["keep", "buffer"],
        buf_idx_keep_last_index=[4, 5],
        buf_spatial_stride=[
            0,
            4,
            8,
            12,
            1,
            5,
            9,
            13,
            2,
            6,
            10,
            14,
            3,
            7,
            11,
            15,
        ],
    )

    bias = reset_stream("stream3", target="C", mode="read")
    bias.update(
        idx=["DRAM_LC.LC10", "DRAM_LC.LC11", "DRAM_LC.LC12"],
        idx_size=[31, 0, 0],
        dim_stride=[SA_OUTPUT_LANES * 4, 0, 0],
        mem_idx_mode=["keep", "keep", "buffer"],
        mem_idx_keep_last_index=[0, 1, 2],
        buf_idx_mode=["keep", "buffer"],
        buf_idx_keep_last_index=[3, 4],
        buf_spatial_stride=list(range(16)),
        buf_full_last_index=2,
    )

    config["n2n"] = {
        "neighbor_stream0": {
            "mem_loop": spec.n2n_mem_loop,
            "src_slice_sel": spec.n2n_src_slice_sel,
            "dst_slice_sel": spec.n2n_dst_slice_sel,
            "ping_pong": spec.n2n_ping_pong,
        }
    }

    group_contract = {
        "GROUP0": ("A", "DRAM_LC.LC5", 4, 5, 6),
        "GROUP1": ("B", "DRAM_LC.LC6", 4, 6, 7),
        "GROUP2": ("C", "DRAM_LC.LC12", 1, 3, 4),
        "GROUP3": ("D", "DRAM_LC.LC9", 4, 4, 5),
    }
    for name, (target, source_id, row_end, row_last, col_last) in group_contract.items():
        group = config["buffer_loop_configs"][name]
        group["target"] = target
        group["ROW_LC"].update(
            src_id=source_id,
            start=0,
            end=row_end,
            stride=1,
            last_index=row_last,
        )
        group["COL_LC"].update(
            src_id=f"{name}.ROW_LC",
            start=0,
            end=32,
            stride=16,
            last_index=col_last,
        )

    buffer_contract = {
        0: (1, 5, 4, 0, 3),
        1: (1, 5, 4, 0, 3),
        2: (0, 6, 4, 1, 3),
        3: (0, 6, 4, 1, 3),
        4: (0, 2, HIGH_RING_STEPS, 0, 0),
        5: (0, 2, 1, 0, 3),
    }
    for index, (nbr, full_last, lifetime, mode, end_row) in buffer_contract.items():
        config["buffer_config"][f"buffer{index}"].update(
            dst_port=0,
            nbr_enable=nbr,
            buf_full_last_index=full_last,
            buffer_nbr_cnt=spec.n2n_mem_loop - 1,
            buffer_life_time=lifetime,
            mode=mode,
            mask=[1] * 8,
            buf_end_row_addr=end_row,
        )

    config["special_array"] = {
        "mode": "gemm",
        "bias_enable": 1,
        "data_type": "int8",
        "transout_last_index": 2,
        "inport0": {
            "enable": 1,
            "pingpong_en": 1,
            "pingpong_last_index": 5,
            "nbr_enable": 1,
        },
        "inport1": {
            "enable": 1,
            "pingpong_en": 1,
            "pingpong_last_index": 6,
            "nbr_enable": 0,
        },
        "inport2": {
            "enable": 1,
            "pingpong_en": 0,
            "pingpong_last_index": None,
            "nbr_enable": 0,
        },
        "outport": {
            "mode": "col",
            "fp32tofp16": "false",
            "fp32tobf16": "false",
        },
    }

    validate_conv_accumulate_output_route(config)
    validate_conv_accumulate_config_mask(config)
    validate_conv_accumulate_neighbor_ring(
        config, expected_group_size=spec.n2n_mem_loop
    )
    validate_conv_3x3_sa_contract(
        config,
        output_height=spec.output_height,
        output_width=spec.output_width,
        c_quartets=c_quartets,
        k_blocks=k_blocks,
        halo_width_padded=halo_width_padded,
    )
    return config


__all__ = ["build_real_3x3"]
