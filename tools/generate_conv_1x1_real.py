from __future__ import annotations

import argparse
import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from resnet50_pipeline.conv_instance import (
    CONV_GEMM_TRANSPOSED_OUTPORT_JSON_MODE,
    CONV_TRANSPORT_ABI_SIGNED_A_LOCAL,
    FIRST_REAL_CONV_NODE_ID,
    SA_ONLY_CONFIG_MASK,
    ConvInstanceSpec,
    load_conv_instance_spec,
    validate_conv_accumulate_config_mask,
    validate_conv_accumulate_output_route,
)
from resnet50_pipeline.conv_sa_contract import (
    HIGH_RING_STEPS,
    SA_BIAS_HANDSHAKES_PER_TILE,
    SA_CHANNEL_LANES,
    SA_OUTPUT_LANES,
    SA_SPATIAL_LANES,
    ceil_div,
    validate_first_conv_signed_a_local_contract,
)


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def build_real_1x1(
    source: dict[str, Any],
    spec: ConvInstanceSpec | None = None,
) -> dict[str, Any]:
    """Lower the reviewed senior Conv skeleton to the real 1x1 microprogram.

    The static JSON is one sample's SA accumulation microprogram.  Batch-16 and
    the seven HIGH-4 groups are scheduled by the target-request adapter; this
    keeps batch ownership out of a per-slice loop tree that has no batch field.
    """

    spec = spec or load_conv_instance_spec(ROOT, FIRST_REAL_CONV_NODE_ID)
    spec.validate()
    if spec.kernel != (1, 1) or spec.strides != (1, 1) or spec.pads != (0, 0, 0, 0):
        raise ValueError("real 1x1 generator requires kernel1/stride1/pad0")
    c_quartets = ceil_div(spec.c_tile, SA_CHANNEL_LANES)
    k_blocks = ceil_div(spec.k_tile, SA_OUTPUT_LANES)
    q_blocks = ceil_div(spec.output_width, SA_SPATIAL_LANES)

    config = deepcopy(source)
    # The reference SA-only programs advertise only the blocks consumed by
    # accumulation.  Keeping the broader SA+GA mask would leave the parser to
    # silently discard absent GA fields and makes transport audits ambiguous.
    config["CONFIG"] = SA_ONLY_CONFIG_MASK
    # RTL inport0/DataA is signed and inport1/DataB is unsigned.  The v3 ABI
    # therefore puts K8xC4 int8 weights on target A and replicated Q8xC4 uint8
    # activations on targets B/B'.  Both operands are local and follow the same
    # destination-relative PREV C order; no runtime neighbor transfer remains.
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
        # One compute matrix is K8 x Q8.  LC4/LC5 and LC6/LC7 traverse the
        # identical destination-relative PREV C order for activation/weight.
        # LC9 emits eight contiguous K8 P rows after the SA outport transpose.
        "LC0": (None, 1, k_blocks, 0),
        "LC1": ("DRAM_LC.LC0", 0, spec.output_height, 1),
        "LC2": ("DRAM_LC.LC1", 0, q_blocks, 2),
        "LC4": ("DRAM_LC.LC2", 0, HIGH_RING_STEPS, 3),
        "LC5": ("DRAM_LC.LC4", 0, c_quartets, 4),
        "LC6": ("DRAM_LC.LC2", 0, HIGH_RING_STEPS, 3),
        "LC7": ("DRAM_LC.LC6", 0, c_quartets, 4),
        # The WRITE_STREAM0 and READ_STREAM3 endpoints sit on the opposite
        # physical side of the IGA.  A value-identical placement branch avoids
        # the impossible fanout that the official mapper correctly rejects.
        "LC13": (None, 1, k_blocks, 0),
        "LC14": ("DRAM_LC.LC13", 0, spec.output_height, 1),
        "LC15": ("DRAM_LC.LC14", 0, q_blocks, 2),
        "LC9": ("DRAM_LC.LC15", 0, SA_SPATIAL_LANES, 3),
        # READ_STREAM3 needs one 32B K8 bias row for every output matrix
        # tile. Its dedicated placement branch repeats the Kblock address
        # across H/Qblock without adding fanout to the compute/output trees.
        "LC10": (None, 1, k_blocks, 0),
        "LC11": ("DRAM_LC.LC10", 0, spec.output_height, 1),
        "LC12": ("DRAM_LC.LC11", 0, q_blocks, 2),
    }
    for name, (src_id, outmost, end, last_index) in loop_contract.items():
        loops[name].update(
            src_id=src_id,
            outmost_loop=outmost,
            start=0,
            end=end,
            stride=1,
            last_index=last_index,
        )

    pe = config["lc_pe_configs"]

    # PE0 = ring_step*c_quartets + local_c_quartet.
    config["lc_pe_configs"] = {}
    pe = config["lc_pe_configs"]
    pe["PE0"] = {
        "alu_opcode": "mac",
        "inport2": {"src_id": "DRAM_LC.LC7", "mode": "buffer", "keep_last_index": None, "constant": 0},
        "inport1": {"src_id": None, "mode": "constant", "keep_last_index": None, "constant": c_quartets},
        "inport0": {"src_id": "DRAM_LC.LC6", "mode": "keep", "keep_last_index": 3, "constant": 0},
    }
    # PE1 = q_block*8 + output_q_lane.
    pe["PE1"] = {
        "alu_opcode": "mac",
        "inport2": {"src_id": "DRAM_LC.LC9", "mode": "buffer", "keep_last_index": None, "constant": 0},
        "inport1": {"src_id": None, "mode": "constant", "keep_last_index": None, "constant": SA_SPATIAL_LANES},
        "inport0": {"src_id": "DRAM_LC.LC15", "mode": "keep", "keep_last_index": 2, "constant": 0},
    }
    # PE2 = ring_step*c_quartets + local_c_quartet for the replicated
    # activation.  It intentionally mirrors PE0's weight traversal.
    pe["PE2"] = {
        "alu_opcode": "mac",
        "inport2": {"src_id": "DRAM_LC.LC5", "mode": "buffer", "keep_last_index": None, "constant": 0},
        "inport1": {"src_id": None, "mode": "constant", "keep_last_index": None, "constant": c_quartets},
        "inport0": {"src_id": "DRAM_LC.LC4", "mode": "keep", "keep_last_index": 3, "constant": 0},
    }

    stream_templates = config["stream_engine"]
    for required in ("stream0", "stream1", "stream2", "stream3"):
        if required not in stream_templates:
            raise ValueError(f"Conv source is missing {required} stream template")
    # Match the model_execplan/native register order exactly.  This is not
    # cosmetic: address patching resolves rd_stream2 to JSON stream2.
    streams = {
        "stream0": deepcopy(stream_templates["stream0"]),  # A / READ0
        "stream1": deepcopy(stream_templates["stream1"]),  # B / READ1
        "stream2": deepcopy(stream_templates["stream1"]),  # B' / READ2
        "stream3": deepcopy(stream_templates["stream3"]),  # C / READ3
        "stream4": deepcopy(stream_templates["stream2"]),  # D / WRITE0
    }
    config["stream_engine"] = streams
    def reset_stream(name: str, *, target: str, mode: str) -> dict[str, Any]:
        stream = streams[name]
        stream.update(target=target, mode=mode)
        stream["padding_enable"] = [0, 0, 0]
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

    weight = reset_stream("stream0", target="A", mode="read")
    weight.update(
        idx=["LC_PE.PE0", "DRAM_LC.LC0", None],
        idx_size=[31, 0, 0],
        dim_stride=[
            k_blocks * SA_OUTPUT_LANES * SA_CHANNEL_LANES,
            SA_OUTPUT_LANES * SA_CHANNEL_LANES,
            None,
        ],
        mem_idx_mode=["buffer", "keep", None],
        mem_idx_keep_last_index=[4, 0, None],
        buf_idx_mode=["keep", "buffer"],
        # JSON Buffer-AG order is [row, col].  ROW is a keep input and may
        # only be released when the buffered COL terminal (index 5) arrives.
        buf_idx_keep_last_index=[5, 5],
        buf_spatial_stride=list(range(16)),
        buf_full_last_index=4,
        # RTL WR_Buffer_AG uses this selector to alternate READ0 between
        # physical buffers 0/1.  SA inport0 independently alternates between
        # those same buffers at terminal tag 4, so the producer and consumer
        # selectors must have the same enable and boundary.
        ping_pong=1,
        pingpong_last_index=4,
    )

    activation = reset_stream("stream1", target="B", mode="read")
    activation.update(
        idx=["LC_PE.PE2", "DRAM_LC.LC2", "DRAM_LC.LC1"],
        idx_size=[31, 0, 0],
        dim_stride=[
            SA_SPATIAL_LANES * SA_CHANNEL_LANES,
            HIGH_RING_STEPS * c_quartets * SA_SPATIAL_LANES * SA_CHANNEL_LANES,
            q_blocks * HIGH_RING_STEPS * c_quartets * SA_SPATIAL_LANES * SA_CHANNEL_LANES,
        ],
        mem_idx_mode=["buffer", "keep", "keep"],
        mem_idx_keep_last_index=[4, 2, 1],
        buf_idx_mode=["keep", "buffer"],
        buf_idx_keep_last_index=[5, 5],
        buf_spatial_stride=list(range(16)),
        buf_full_last_index=4,
    )

    activation_prime = reset_stream("stream2", target="B'", mode="read")
    activation_prime.update(
        {key: deepcopy(value) for key, value in activation.items() if key != "target"}
    )
    activation_prime["target"] = "B'"

    output = reset_stream("stream4", target="D", mode="write")
    output.update(
        idx=["DRAM_LC.LC13", "LC_PE.PE1", "DRAM_LC.LC14"],
        idx_size=[31, 0, 0],
        dim_stride=[
            SA_OUTPUT_LANES * 4,
            k_blocks * SA_OUTPUT_LANES * 4,
            k_blocks * q_blocks * SA_SPATIAL_LANES * SA_OUTPUT_LANES * 4,
        ],
        mem_idx_mode=["keep", "buffer", "keep"],
        mem_idx_keep_last_index=[0, 3, 1],
        buf_idx_mode=["keep", "buffer"],
        buf_idx_keep_last_index=[5, 5],
        buf_spatial_stride=[0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15],
    )

    bias = reset_stream("stream3", target="C", mode="read")
    bias.update(
        idx=["DRAM_LC.LC10", "DRAM_LC.LC11", "DRAM_LC.LC12"],
        idx_size=[31, 0, 0],
        dim_stride=[SA_OUTPUT_LANES * 4, 0, 0],
        mem_idx_mode=["keep", "keep", "buffer"],
        mem_idx_keep_last_index=[0, 1, 2],
        buf_idx_mode=["keep", "buffer"],
        buf_idx_keep_last_index=[4, 4],
        buf_spatial_stride=list(range(16)),
        buf_full_last_index=2,
    )

    config["n2n"] = {}

    group_contract = {
        "GROUP0": ("A", "DRAM_LC.LC6", 4, 4, 5),
        "GROUP1": ("B", "DRAM_LC.LC4", 4, 4, 5),
        "GROUP2": ("B'", "DRAM_LC.LC4", 4, 4, 5),
        "GROUP3": ("C", "DRAM_LC.LC12", 1, 3, 4),
        "GROUP4": ("D", "DRAM_LC.LC9", 4, 4, 5),
    }
    group_templates = list(config["buffer_loop_configs"].values())
    if not group_templates:
        raise ValueError("Conv source has no buffer-loop template")
    config["buffer_loop_configs"] = {
        name: deepcopy(group_templates[min(index, len(group_templates) - 1)])
        for index, name in enumerate(group_contract)
    }
    for name, (target, source_id, row_end, row_last, col_last) in group_contract.items():
        group = config["buffer_loop_configs"][name]
        group["target"] = target
        group["ROW_LC"].update(
            src_id=source_id, start=0, end=row_end, stride=1, last_index=row_last
        )
        group["COL_LC"].update(
            src_id=f"{name}.ROW_LC", start=0, end=32, stride=16, last_index=col_last
        )

    buffer_contract = {
        # Buffer0/1 carry signed weight rows.  Array_Request_Manager mode=1
        # makes the four-use lifetime the inner counter, so each row remains
        # selected for all four SA handshakes before the row address advances.
        0: (0, 4, 4, 1, 3),
        1: (0, 4, 4, 1, 3),
        2: (0, 4, 4, 1, 3),
        3: (0, 4, 4, 1, 3),
        # JSON lifetime is encoded as N-1. Four reads initialize all four SA
        # outbuffer bias pointers before the compute read pointer advances.
        4: (0, 2, HIGH_RING_STEPS, 0, 0),
        5: (0, 2, 1, 0, 3),
    }
    for index, (nbr, full_last, lifetime, mode, end_row) in buffer_contract.items():
        config["buffer_config"][f"buffer{index}"].update(
            dst_port=0,
            nbr_enable=nbr,
            buf_full_last_index=full_last,
            buffer_nbr_cnt=0,
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
            "pingpong_last_index": 4,
            "nbr_enable": 0,
        },
        "inport1": {
            "enable": 1,
            "pingpong_en": 1,
            "pingpong_last_index": 4,
            "nbr_enable": 0,
        },
        "inport2": {
            "enable": 1,
            "pingpong_en": 0,
            "pingpong_last_index": None,
            "nbr_enable": 0,
        },
        "outport": {
            # Weight rows x activation columns are transposed back to the
            # existing Q8xK8 accumulator layout by RTL major=1.
            "mode": CONV_GEMM_TRANSPOSED_OUTPORT_JSON_MODE,
            "fp32tofp16": "false",
            "fp32tobf16": "false",
        },
    }
    validate_conv_accumulate_output_route(
        config,
        expected_json_mode=CONV_GEMM_TRANSPOSED_OUTPORT_JSON_MODE,
    )
    validate_conv_accumulate_config_mask(config)
    validate_first_conv_signed_a_local_contract(config)
    return config


def _refresh_contract_semantics(
    contract: dict[str, Any], config: dict[str, Any]
) -> None:
    """Bind the human/machine semantic record to the generated graph."""

    static_report = validate_first_conv_signed_a_local_contract(config)
    contract["transport_abi"] = CONV_TRANSPORT_ABI_SIGNED_A_LOCAL

    contract["port_semantics"].update(
        {
            "target_A": {
                "logical_role": "weight_k8c4_in_destination_prev_order",
                "project_port": "B",
                "dtype": "int8",
            },
            "target_B": {
                "logical_role": "destination_local_activation_q8c4",
                "project_port": "A",
                "dtype": "uint8",
            },
            "target_B_prime": {
                "logical_role": "destination_local_activation_q8c4_pingpong_replica",
                "project_port": "A",
                "dtype": "uint8",
            },
        }
    )
    symbols = {
        "LC0": "k_block_compute",
        "LC1": "p_compute",
        "LC2": "q_block_compute",
        "LC4": "destination_prev_step_activation",
        "LC5": "local_c_quartet_activation",
        "LC6": "high_ring_step",
        "LC7": "local_c_quartet_weight",
        "LC9": "q_lane_write",
        "LC10": "k_block_bias",
        "LC11": "p_bias",
        "LC12": "q_block_bias",
        "LC13": "k_block_write_replica",
        "LC14": "p_write_replica",
        "LC15": "q_block_write_replica",
    }
    contract["lc_semantics"] = [
        {
            "lc": name,
            "symbol": symbols.get(name, "unused"),
            "range": [loop["start"], loop["end"], loop["stride"]],
            "src_id": loop["src_id"],
            "last_index": loop["last_index"],
        }
        for name, loop in sorted(
            config["dram_loop_configs"].items(),
            key=lambda item: int(item[0].removeprefix("LC")),
        )
    ]
    contract["lc_pe_contract"] = {
        "mac_formula": "inport0 * inport1 + inport2",
        "encoding_evidence": (
            "official encoder maps both address PEs at constraint cost zero"
        ),
        "pes": [
            {
                "pe": "PE0",
                "result": "ring_step_c_quartet",
                "formula": "LC6*c_quartets+LC7",
                "sources": ["LC6", "constant:c_quartets", "LC7"],
            },
            {
                "pe": "PE1",
                "result": "q_linear",
                "formula": "LC15*8+LC9",
                "sources": ["LC15", "constant:8", "LC9"],
            },
            {
                "pe": "PE2",
                "result": "activation_prev_step_c_quartet",
                "formula": "LC4*c_quartets+LC5",
                "sources": ["LC4", "constant:c_quartets", "LC5"],
            },
        ],
    }
    roles = {
        "stream0": "signed_weight_k8c4_read",
        "stream1": "unsigned_activation_q8c4_read_buffer2",
        "stream2": "unsigned_activation_q8c4_read_buffer3",
        "stream3": "int32_bias_k8_read",
        "stream4": "int32_p_k8_write",
    }
    contract["stream_semantics"] = [
        {
            "stream": name,
            "target": stream["target"],
            "role": roles[name],
            "idx": stream["idx"],
            "idx_size_minus_one": stream["idx_size"],
            "byte_stride": stream["dim_stride"],
            "buf_full_last_index": stream.get("buf_full_last_index"),
            "tail": None,
        }
        for name, stream in sorted(config["stream_engine"].items())
    ]
    contract["ring_semantics"]["neighbor_stream"] = None
    contract["ring_semantics"]["payload_role"] = "no_runtime_neighbor_payload"
    contract["ring_semantics"]["weight_order"] = (
        "destination-relative PREV traversal: destination, prev1, prev2, prev3"
    )
    contract["ring_semantics"]["activation_order"] = (
        "same destination-relative PREV traversal, replicated locally per destination"
    )
    contract["bias_runtime_contract"] = {
        "schedule": "one_32B_K8_row_per_Kblock_H_Qblock_tile",
        "loop_branch": ["DRAM_LC.LC10", "DRAM_LC.LC11", "DRAM_LC.LC12"],
        "memory_byte_stride": [SA_OUTPUT_LANES * 4, 0, 0],
        "transaction_bytes": static_report["stream_transaction_bytes"]["stream3"],
        "sa_handshakes_per_tile": SA_BIAS_HANDSHAKES_PER_TILE,
        "buffer4_json_lifetime": config["buffer_config"]["buffer4"]["buffer_life_time"],
        "buffer4_encoded_lifetime": config["buffer_config"]["buffer4"]["buffer_life_time"] - 1,
        "terminal_last_index": config["stream_engine"]["stream3"]["buf_full_last_index"],
    }
    contract["resolved_pseudocode_conflicts"] = [
        "RTL DataA is signed and DataB is unsigned, so weight is target A/inport0 and activation is target B/B-prime/inport1",
        "both activation ping-pong buffers have explicit local READ producers; runtime N2N is removed",
        "RTL outport major=1 transposes K-row/Q-column compute order into the existing Q8xK8 P layout",
        "WRITE_STREAM0 uses a value-identical LC13-LC15 placement branch required by physical IGA connectivity",
        "READ_STREAM3 uses an independent LC10-LC12 Kblock/H/Qblock branch so every output tile receives four bias handshakes",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the reviewed real 1x1 Conv JSON")
    parser.add_argument("--source", type=Path, default=ROOT / "conv_full.json")
    parser.add_argument("--output", type=Path, default=ROOT / "conv_1x1_real.json")
    parser.add_argument("--node-id", default=FIRST_REAL_CONV_NODE_ID)
    parser.add_argument(
        "--contract",
        type=Path,
        default=ROOT / "contracts" / "conv_1x1_lc_pe_stream_semantics.json",
    )
    parser.add_argument(
        "--update-contract-config",
        action="store_true",
        help="Update the bound config SHA and mark encoder evidence pending refresh.",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = json.dumps(
        build_real_1x1(
            _load(args.source), load_conv_instance_spec(ROOT, args.node_id)
        ),
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    config_sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != payload:
            raise ValueError(f"generated Conv JSON differs: {args.output}")
        if args.update_contract_config:
            contract = _load(args.contract)
            if contract.get("config", {}).get("sha256") != config_sha256:
                raise ValueError(f"Conv contract config SHA differs: {args.contract}")
    else:
        args.output.write_text(payload, encoding="utf-8", newline="\n")
        if args.update_contract_config:
            contract = _load(args.contract)
            contract["config"]["sha256"] = config_sha256
            _refresh_contract_semantics(contract, json.loads(payload))
            contract["status"] = "candidate_pending_official_encoder_refresh"
            args.contract.write_text(
                json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
