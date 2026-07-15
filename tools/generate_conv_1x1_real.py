from __future__ import annotations

import argparse
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from resnet50_pipeline.conv_instance import (
    FIRST_REAL_CONV_NODE_ID,
    ConvInstanceSpec,
    load_conv_instance_spec,
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
    output_blocks = math.ceil(spec.output_channels / 32)
    spatial_blocks = math.ceil(spec.output_height / 32)
    c_quartets = math.ceil(spec.c_tile / 4)
    k_register_groups = math.ceil(spec.k_tile / 4)

    config = deepcopy(source)
    loops = config["dram_loop_configs"]
    ranges = {
        "LC0": (0, output_blocks, 1),  # k_block: ceil(K / 32)
        "LC1": (0, spec.output_width, 1),  # q
        "LC2": (0, spatial_blocks, 1),  # p_block: ceil(P / 32)
        "LC3": (0, c_quartets, 1),  # local C quartets
        "LC4": (0, spec.kernel[1], 1),  # s
        "LC5": (0, spec.kernel[0], 1),  # r
        "LC6": (0, c_quartets, 1),  # weight local C quartets
        "LC7": (0, spec.kernel[1], 1),  # s replica
        "LC8": (0, spec.kernel[0], 1),  # r replica
        "LC9": (0, k_register_groups, 1),  # k register group
        "LC10": (0, 4, 1),  # p register group
        "LC11": (0, 8, 4),  # p PE offset: 0, 4
        "LC12": (0, output_blocks, 1),  # k PE offset
        "LC13": (0, output_blocks, 1),  # placement replica of k_block
        "LC14": (0, spec.output_width, 1),  # placement replica of q
        "LC15": (0, spatial_blocks, 1),  # placement replica of p_block
    }
    if set(loops) != set(ranges):
        raise ValueError("Conv source loop inventory differs from the reviewed skeleton")
    for name, (start, end, stride) in ranges.items():
        loops[name].update(start=start, end=end, stride=stride)

    pe = config["lc_pe_configs"]

    # LC-PE MAC semantics are inport0 * inport1 + inport2.  The official
    # encoder proves only opcode/field encoding; this formula is the explicit
    # adapter contract and is revalidated before every NDPFuncModel request.
    pe["PE0"] = {
        "alu_opcode": "mac",
        "inport2": {"src_id": "DRAM_LC.LC5", "mode": "buffer", "keep_last_index": None, "constant": 0},
        "inport1": {"src_id": None, "mode": "constant", "keep_last_index": None, "constant": 1},
        "inport0": {"src_id": "DRAM_LC.LC4", "mode": "keep", "keep_last_index": 1, "constant": 0},
    }
    pe["PE1"] = {
        "alu_opcode": "mac",
        "inport2": {"src_id": "DRAM_LC.LC8", "mode": "buffer", "keep_last_index": None, "constant": 0},
        "inport1": {"src_id": None, "mode": "constant", "keep_last_index": None, "constant": 32},
        "inport0": {"src_id": "DRAM_LC.LC2", "mode": "keep", "keep_last_index": 2, "constant": 0},
    }
    pe["PE2"] = {
        "alu_opcode": "mac",
        "inport2": {"src_id": "DRAM_LC.LC1", "mode": "keep", "keep_last_index": 1, "constant": 0},
        "inport1": {"src_id": None, "mode": "constant", "keep_last_index": None, "constant": 1},
        "inport0": {"src_id": "DRAM_LC.LC7", "mode": "buffer", "keep_last_index": 2, "constant": 0},
    }
    pe["PE3"] = {
        "alu_opcode": "mac",
        "inport2": {"src_id": "DRAM_LC.LC11", "mode": "buffer", "keep_last_index": None, "constant": 0},
        "inport1": {"src_id": None, "mode": "constant", "keep_last_index": None, "constant": 8},
        "inport0": {"src_id": "DRAM_LC.LC10", "mode": "keep", "keep_last_index": 1, "constant": 0},
    }
    pe["PE4"] = {
        "alu_opcode": "mac",
        "inport2": {"src_id": "LC_PE.PE3", "mode": "buffer", "keep_last_index": None, "constant": 0},
        "inport1": {"src_id": None, "mode": "constant", "keep_last_index": None, "constant": 32},
        "inport0": {"src_id": "DRAM_LC.LC15", "mode": "buffer", "keep_last_index": None, "constant": 0},
    }
    pe["PE5"] = {
        "alu_opcode": "mac",
        "inport2": {"src_id": "DRAM_LC.LC12", "mode": "buffer", "keep_last_index": None, "constant": 0},
        "inport1": {"src_id": None, "mode": "constant", "keep_last_index": None, "constant": 2},
        "inport0": {"src_id": "DRAM_LC.LC9", "mode": "keep", "keep_last_index": 3, "constant": 0},
    }
    pe["PE6"] = {
        "alu_opcode": "mac",
        "inport2": {"src_id": "LC_PE.PE5", "mode": "buffer", "keep_last_index": None, "constant": 0},
        "inport1": {"src_id": None, "mode": "constant", "keep_last_index": None, "constant": 32},
        "inport0": {"src_id": "DRAM_LC.LC13", "mode": "keep", "keep_last_index": 0, "constant": 0},
    }

    streams = config["stream_engine"]
    # Target JSON port names follow the senior skeleton: A=weight,
    # B=activation, C=bias, D=INT32 accumulator writeback.
    streams["stream0"]["dim_stride"] = [128, spec.input_channels * 32, 128]
    streams["stream1"]["idx"] = ["DRAM_LC.LC6", "LC_PE.PE2", "LC_PE.PE1"]
    streams["stream1"]["dim_stride"] = [
        spec.output_height * spec.output_width * 4,
        4,
        spec.output_width * 4,
    ]
    streams["stream1"]["padding_enable"] = [0, 0, 0]
    streams["stream1"]["idx_padding_range"] = {
        "low_bound": [None, None, None],
        "up_bound": [None, None, None],
    }
    streams["stream1"]["tailing_enable"] = [0, 0, 1]
    streams["stream1"]["idx_tailing_range"] = {
        "low": [None, None, 0],
        "up": [None, None, spec.output_width - 1],
    }
    streams["stream2"]["idx"] = ["LC_PE.PE6", "DRAM_LC.LC14", "LC_PE.PE4"]
    streams["stream2"]["dim_stride"] = [
        spec.output_height * spec.output_width * 4,
        4,
        spec.output_width * 4,
    ]
    streams["stream2"]["tailing_enable"] = [0, 0, 1]
    streams["stream2"]["idx_tailing_range"] = {
        "low": [None, None, 0],
        "up": [None, None, spec.output_width - 1],
    }
    neighbor = next(iter(config["n2n"].values()))
    neighbor.update(
        mem_loop=spec.n2n_mem_loop,
        src_slice_sel=spec.n2n_src_slice_sel,
        dst_slice_sel=spec.n2n_dst_slice_sel,
        ping_pong=spec.n2n_ping_pong,
    )
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the reviewed real 1x1 Conv JSON")
    parser.add_argument("--source", type=Path, default=ROOT / "conv_full.json")
    parser.add_argument("--output", type=Path, default=ROOT / "conv_1x1_real.json")
    parser.add_argument("--node-id", default=FIRST_REAL_CONV_NODE_ID)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = json.dumps(
        build_real_1x1(
            _load(args.source), load_conv_instance_spec(ROOT, args.node_id)
        ),
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != payload:
            raise ValueError(f"generated Conv JSON differs: {args.output}")
    else:
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
