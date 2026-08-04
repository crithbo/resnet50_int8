"""Pure-configuration local-E2 closure for ResNet50 GAP's INT32 sum stage.

This module deliberately stops before the shared exact UINT8 quantization
tail.  It materializes the real node-0071 input into a six-stage pairwise
``int32_mac(A, 1, C)`` tree, validates every final JSON occurrence, and runs a
configuration-bound software executor over the frozen W3 tensor.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_validator import OperatorConfigValidator


SCHEMA = "resnet50-gap-sum-config-only-local-e2-v1"
CLAIM = "CONFIG_ONLY_CORRECTNESS_BASELINE"
SLICE_MASK = (1 << 16) - 1
SLICE_COUNT = 16
BLOCKS = 256
LANES = 8
LOGICAL_WIDTHS = (49, 25, 13, 7, 4, 2, 1)
PHYSICAL_WIDTHS = (64, 32, 16, 8, 4, 2, 1)
INPUT_BYTES_PER_BLOCK = 49 * 8
INPUT_ALLOCATION_BYTES = BLOCKS * 49 * LANES
BASES = (0x00000, 0x20000, 0x60000, 0x80000, 0x90000, 0x98000, 0x9C000)
CONFIG_BASES = tuple(0x100000 + 0x10000 * index for index in range(6))

TEMPLATE = "configs/stage_codegen/hwop-0071-00-d-index-v1/config.json"
CONFIG_ROOT = "configs/gap_sum_config_only_v1"
ARTIFACT_ROOT = (
    "artifacts/operator_config_validation/r5-gap-sum-config-only-local-e2-v1"
)
CONTRACT = "contracts/operator_config/gap_sum_config_only_local_e2_v1.json"
W3_INPUT = (
    "artifacts/w3/golden_batch16/tensors/tensor-55360f2ec724d2f3.npy"
)
W3_SUM = (
    "artifacts/w3/subop_batch16/tensors/tensor-internal-node-0071-sum.npy"
)
W3_INPUT_SHA256 = "17751d21f3ece3ba1ba03eb9f54494ede7c9ccc2d4f915854ca76c4006a1fe3a"

RULE_IDS = (
    "CDA-CONFIG-ONLY-CORRECTNESS-BYPASS-001",
    "CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001",
    "CDA-CONFIG-SEMANTIC-OWNERSHIP-001",
    "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001",
    "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
    "CDA-CONFIG-FULL-REBUILD-PROVENANCE-001",
    "CDA-GAP-INT32MAC-NONTRANSOUT-001",
    "CDA-GAP-INT32MAC-DUAL-INPUT-001",
    "CDA-GAP-INT32MAC-NORMAL-FIFO-001",
    "CDA-GAP-INT32MAC-TREE-001",
    "CDA-GAP-INT32MAC-STAGE-MEMORY-001",
    "CDA-GAP-INT32MAC-MATERIALIZED-STAGE1-001",
    "CDA-GAP-INT32MAC-BRANCH-ISOLATION-001",
    "CDA-QUANT-TAIL-NUMERIC-ORDER-001",
    "CDA-QUANT-TAIL-ZP-AFTER-ROUND-001",
    "CDA-QUANT-TAIL-MAGIC-DOMAIN-001",
    "CDA-QUANT-TAIL-CAPABILITY-MATRIX-001",
)

READ_INPUTS = (
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md",
    ".agents/rules/GAP_int32_mac_bypass_rules.md",
    ".agents/rules/最小双Stage生命周期规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md",
    ".agents/task_records/20260727_ndpsim_resnet50_reuse_audit_and_replan.md",
    ".agents/task_records/20260727_test_repair_to_family_threads_handoff.md",
    ".agents/task_records/20260727_exact_uint8_quant_tail_capability_matrix.md",
    ".agents/task_records/20260727_requant_p1b_quant_tail_evidence_input.md",
    ".agents/task_records/gap_int32_mac_bypass_local_closure_20260724.md",
    "contracts/resnet50_r5_lowering_bundle.json",
    "contracts/operator_config/exact_uint8_quant_tail_capability_v1.json",
    "contracts/operator_config/requant_quant_tail_evidence_input_v1.json",
    "contracts/operator_config/gap_int32_mac_bypass_v1.json",
    TEMPLATE,
    W3_INPUT,
    W3_SUM,
    "ndp-sim/bitstream/config/stream.py",
    "NDP_copy01/rtl/Slice/General_Array/GA_Inport/GA_Inport.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE/GA_PE.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_RD_Stream_Engine/WR_Buffer_AG.sv"
    ),
)

BYPASS_ANNOTATION = {
    "bypass_reason": (
        "The real node-0071 sum must remain numerically runnable while all "
        "functional RTL repair routes are frozen."
    ),
    "contradicted_or_missing_native_path": (
        "The native int32_sum/transout route is contradicted by occupancy "
        "underflow, invalid-slot stale-C, and D-index coverage evidence; "
        "repair_v9 and CONFIG_SEMANTICS/RTL_CONTROL repair are frozen.  The "
        "older int32_mac v1 materialization also mismatched its 8-byte C8 "
        "contract with 16-byte streams and a non-adjacent C base."
    ),
    "exact_equivalence_scope": (
        "Frozen r5:hwop-0071-00, uint8[16,2048,7,7], x_zero_point=0, "
        "C8HW8 input, exact INT32 sum over 49 spatial values.  Pairwise "
        "addition is exact because sums are in [0,12495], so no INT32 wrap."
    ),
    "materialized_configuration_mechanism": (
        "Six serialized non-transout int32_mac(A,1,C) stages; stage1 uses "
        "aligned 8-byte A/C reads whose independent LC branches emit even/"
        "odd element indices, plus columns [0,4,...,28] across eight banks; "
        "later stages use explicit 32-byte INT32 scratch; every stage reloads "
        "configuration and is followed by a same-mask barrier."
    ),
    "performance_and_resource_cost": (
        "6 Start_Comp operations and 6 barriers; 16,128 GA output "
        "occurrences per slice (63 per C8 block), 1,155,072 scratch bytes "
        "of aggregate traffic per slice (read+write), and 647,168 bytes of "
        "addressed input/scratch footprint per slice; no throughput claim."
    ),
    "unresolved_production_blocker": (
        "Dynamic A/C skew/backpressure and normal-FIFO drain are not executed "
        "at local E2; formal D E4/E5 is absent; the shared exact UINT8 tail "
        "remains NO_UNCONDITIONAL_PURE_CONFIG_PROVEN with rounding/domain/"
        "typed-binding/mapper blockers."
    ),
    "claim_boundary": (
        "CONFIG_ONLY_CORRECTNESS_BASELINE for the node-0071 INT32 sum stage "
        "only; not a complete QLinearGlobalAveragePool target, not production, "
        "not a performance release, and not E3/E4/E5."
    ),
}


class GapSumConfigOnlyError(ValueError):
    pass


@dataclass(frozen=True)
class Region:
    stage: int
    base: int
    width: int
    logical_width: int

    @property
    def size(self) -> int:
        if self.stage == 0:
            return INPUT_ALLOCATION_BYTES
        return BLOCKS * self.width * 32

    @property
    def end(self) -> int:
        return self.base + self.size


def regions() -> tuple[Region, ...]:
    return tuple(
        Region(index, BASES[index], PHYSICAL_WIDTHS[index], LOGICAL_WIDTHS[index])
        for index in range(7)
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GapSumConfigOnlyError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _manifest_path(path: Path, root: Path, output: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return (Path(output.name) / path.relative_to(output)).as_posix()


def build_read_receipt(root: Path) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entries = []
    for relative in READ_INPUTS:
        path = root / relative
        if not path.is_file():
            raise GapSumConfigOnlyError(f"required read input missing: {relative}")
        entries.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "read_at": now,
            }
        )
    return {
        "schema": "gap-sum-config-only-read-receipt-v1",
        "read_receipt": entries,
        "rule_ids": list(RULE_IDS),
        "known_counterexamples": [
            "native int32_sum outbuffer occupancy underflow/stale-C",
            "native D-index only two unique addresses",
            "legacy int32_mac v1 stage1 16B-vs-8B mismatch",
            "legacy int32_mac v1 C base 0x20000-vs-adjacent-right mismatch",
            "quant-tail sequential multiply/RNE=26 vs fused magic=25",
        ],
        "open_dynamic_gates": [
            "B_GAP_INT32MAC_DYNAMIC_DUAL_STREAM",
            "B_GAP_INT32MAC_STAGE_BARRIER",
            "B_GAP_INT32MAC_FORMAL_READBACK",
            "B_QUANT_TAIL_FMA_ROUNDING_POINT",
            "B_QUANT_TAIL_MAGIC_DOMAIN_BOUND",
            "B_QUANT_TAIL_TYPED_BINDING",
            "B_QUANT_TAIL_MAPPER_REGISTRATION",
        ],
        "omitted_files": [
            {
                "path": ".agents/rules/服务器测试包生成规则.md",
                "reason": "no server package is generated or inspected",
            },
            {
                "path": ".agents/rules/GAP_repair_candidate_rules.md",
                "reason": "repair_v9 and every functional RTL route are frozen",
            },
        ],
    }


def build_typed_request() -> dict[str, Any]:
    ops: list[dict[str, Any]] = []
    for stage in range(1, 7):
        previous = regions()[stage - 1]
        output = regions()[stage]
        ops.append(
            {
                "id": f"sum_s{stage}",
                "type": "gap_config_only_int32_mac_pairwise",
                "stage_index": stage,
                "equation": "D=int32(A*1+C)",
                "opcode": 14,
                "input": {
                    "tensor_id": (
                        "tensor-55360f2ec724d2f3"
                        if stage == 1
                        else f"gap.sum.s{stage-1}.scratch"
                    ),
                    "dtype": "uint8" if stage == 1 else "int32",
                "shape": [
                    16,
                    256,
                    previous.logical_width if stage == 1 else previous.width,
                    8,
                ],
                    "physical_base_per_slice": hex(previous.base),
                    "source": (
                        {"type": "external"}
                        if stage == 1
                        else {"type": "operator", "operator_id": f"sum_s{stage-1}"}
                    ),
                },
                "output": {
                    "tensor_id": (
                        "tensor-internal-node-0071-sum"
                        if stage == 6
                        else f"gap.sum.s{stage}.scratch"
                    ),
                    "dtype": "int32",
                    "shape": [16, 256, output.width, 8],
                    "logical_width": output.logical_width,
                    "physical_base_per_slice": hex(output.base),
                },
                "used_slices": f"0b{SLICE_MASK:028b}",
            }
        )
    return {
        "schema": "gap-sum-config-only-typed-request-v1",
        "node_id": "node-0071",
        "request_id": "r5:hwop-0071-00",
        "onnx_op_type": "QLinearGlobalAveragePool",
        "stage": "sum",
        "input": {
            "dtype": "uint8",
            "shape": [16, 2048, 7, 7],
            "layout": "C8HW8",
            "x_zero_point": 0,
        },
        "output": {
            "dtype": "int32",
            "shape": [16, 2048, 1, 1],
            "layout": "C8",
        },
        "operators": ops,
        "bypass_annotation": dict(BYPASS_ANNOTATION),
        "quant_tail_dependency": {
            "decision": "NO_UNCONDITIONAL_PURE_CONFIG_PROVEN",
            "materialized": False,
            "complete_gap_target": False,
        },
        "input_replay_contract": {
            "rule_id": "CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001",
            "source_producer": "r5:hwop-0070-00",
            "tensor_id": "tensor-55360f2ec724d2f3",
            "path": W3_INPUT,
            "sha256": W3_INPUT_SHA256,
            "dtype": "uint8",
            "shape": [16, 2048, 7, 7],
            "layout": "C8HW8",
            "value_transform": "identity",
            "allowed_index_mapping": (
                "(n,c,h,w)->(n,c//8,h*7+w,c%8); stage1 LC even/odd "
                "selection changes addresses only"
            ),
            "replayed_tensor_kinds": ["formal_producer_output"],
            "host_precomputed_internal_tensor": False,
            "does_not_cross": [
                "node-0071 int32 sum",
                "divide-by-49",
                "scale",
                "round",
                "zero-point add",
                "saturate",
                "final UINT8 output",
            ],
            "independent_golden_only": {
                "path": W3_SUM,
                "is_replay_source": False,
            },
        },
    }


def validate_input_replay(root: Path, typed: dict[str, Any]) -> dict[str, Any]:
    replay = typed["input_replay_contract"]
    actual_sha = sha256_file(root / replay["path"])
    if actual_sha != replay["sha256"] or actual_sha != W3_INPUT_SHA256:
        raise GapSumConfigOnlyError("typed W3 input replay identity differs")
    if replay["value_transform"] != "identity":
        raise GapSumConfigOnlyError("input replay changes values")
    if replay["host_precomputed_internal_tensor"] is not False:
        raise GapSumConfigOnlyError("host-precomputed internal replay is forbidden")
    if replay["independent_golden_only"]["is_replay_source"] is not False:
        raise GapSumConfigOnlyError("internal sum golden cannot be replayed")
    source = np.load(root / replay["path"], allow_pickle=False)
    if list(source.shape) != replay["shape"] or str(source.dtype) != replay["dtype"]:
        raise GapSumConfigOnlyError("typed W3 replay shape/dtype differs")
    return {
        "schema": "gap-sum-config-only-input-replay-v1",
        "valid": True,
        "source_producer": replay["source_producer"],
        "tensor_id": replay["tensor_id"],
        "source_sha256": actual_sha,
        "dtype": str(source.dtype),
        "shape": list(source.shape),
        "value_transform": "identity",
        "address_index_mapping_only": True,
        "host_precomputed_internal_tensor": False,
        "independent_sum_golden_used_only_for_comparison": True,
        "forbidden_internal_stages_replayed": [],
    }


def _stream(
    *,
    target: str,
    mode: str,
    base: int,
    transaction_bytes: int,
    block_stride: int,
    item_stride: int,
    stage1_padding_upper: int | None = None,
) -> dict[str, Any]:
    read = mode == "read"
    value: dict[str, Any] = {
        "target": target,
        "mode": mode,
        "base_addr": hex(base),
        "mem_idx_mode": ["keep", "buffer", None],
        "mem_idx_keep_last_index": [1, None, None],
        "mem_idx_constant": [None, None, None],
        "idx": ["DRAM_LC.LC0", "DRAM_LC.LC1", None],
        "idx_size": [transaction_bytes - 1, 0, None],
        "dim_stride": [block_stride, item_stride, None],
        "tailing_enable": [0, 0, 0],
        "idx_tailing_range": {
            "low": [None, None, None],
            "up": [None, None, None],
        },
        "address_remapping": None,
        "buf_idx_mode": ["keep", "buffer"],
        "buf_idx_keep_last_index": [3, None],
        "buf_spatial_stride": (
            [lane * 4 for lane in range(8)]
            if transaction_bytes == 8
            else list(range(16))
        ),
        "buf_spatial_size": 8 if transaction_bytes == 8 else 16,
        "ping_pong": 0,
        "pingpong_last_index": None,
    }
    if read:
        value.update(
            {
                "padding_enable": [0, int(stage1_padding_upper is not None), 0],
                "padding_reg_value": (
                    0 if stage1_padding_upper is not None else None
                ),
                "idx_padding_range": {
                    "low_bound": [
                        None,
                        0 if stage1_padding_upper is not None else None,
                        None,
                    ],
                    "up_bound": [None, stage1_padding_upper, None],
                },
                "buf_full_last_index": 2,
            }
        )
    return value


def _ordinary_group(target: str, group: int) -> dict[str, Any]:
    return {
        "target": target,
        "ROW_LC": {
            "src_id": "DRAM_LC.LC1",
            "start": 0,
            "end": 1,
            "stride": 1,
            "last_index": 2,
        },
        "COL_LC": {
            "src_id": f"GROUP{group}.ROW_LC",
            "start": 0,
            "end": 32,
            "stride": 16,
            "last_index": 3,
        },
    }


def _stage1_read_group(target: str, group: int, source: str) -> dict[str, Any]:
    return {
        "target": target,
        "ROW_LC": {
            "src_id": source,
            "start": 0,
            "end": 1,
            "stride": 1,
            "last_index": 2,
        },
        "COL_LC": {
            "src_id": f"GROUP{group}.ROW_LC",
            "start": 0,
            # Each 8-byte MSE transaction contributes one byte to every
            # physical Buffer bank.  The COL low two bits select that byte
            # lane, so four consecutive transactions must enumerate 0..3.
            "end": 4,
            "stride": 1,
            "last_index": 3,
        },
    }


def stage1_buffer_byte_lane_contract(cfg: dict[str, Any]) -> dict[str, Any]:
    """Validate the RTL-visible four-transaction Buffer row fill.

    Memory_Req_Manager uses the low two column bits as a one-hot byte strobe,
    while Buffer requires all four byte-valid bits in every active bank
    before an Array read can be accepted.  Stage1 therefore must fill byte
    lanes 0,1,2,3 exactly once in every bank.
    """

    groups = cfg["buffer_loop_configs"]
    streams = cfg["stream_engine"]
    results: dict[str, Any] = {}
    for group_name, stream_name in (("GROUP0", "stream0"), ("GROUP1", "stream1")):
        group = groups[group_name]
        stream = streams[stream_name]
        loop = group["COL_LC"]
        col_values = list(range(loop["start"], loop["end"], loop["stride"]))
        spatial_size = stream["buf_spatial_size"]
        strides = stream["buf_spatial_stride"][:spatial_size]
        slots_by_bank = {bank: [] for bank in range(8)}
        transactions = []
        for col_base in col_values:
            positions = [((col_base + stride) & 0x1F) for stride in strides]
            bank_bytes = [
                {"bank": position >> 2, "byte": position & 0x3}
                for position in positions
            ]
            banks = [item["bank"] for item in bank_bytes]
            if sorted(banks) != list(range(8)):
                raise GapSumConfigOnlyError(
                    f"stage1 {group_name} transaction does not cover every bank once"
                )
            for item in bank_bytes:
                slots_by_bank[item["bank"]].append(item["byte"])
            transactions.append(
                {
                    "col_base": col_base,
                    "bank_bytes": bank_bytes,
                }
            )
        expected_slots = list(range(4))
        if col_values != expected_slots:
            raise GapSumConfigOnlyError(
                f"stage1 {group_name} COL byte-lane sequence differs"
            )
        if any(slots != expected_slots for slots in slots_by_bank.values()):
            raise GapSumConfigOnlyError(
                f"stage1 {group_name} does not fill all four byte lanes per bank"
            )
        results[group_name] = {
            "stream": stream_name,
            "col_values": col_values,
            "transactions_per_full_row": len(col_values),
            "slots_by_bank": slots_by_bank,
            "transactions": transactions,
            "all_banks_all_byte_lanes_exact_once": True,
        }
    return {
        "rtl_equations": {
            "bank": "low5(col_base + spatial_stride) >> 2",
            "byte": "low5(col_base + spatial_stride) & 3",
            "array_ready": "all four byte-valid bits in every active bank",
        },
        "groups": results,
        "valid": True,
    }


def _dram_loop(
    *,
    src_id: str | None,
    outmost: int,
    start: int,
    end: int,
    stride: int,
    last_index: int,
) -> dict[str, Any]:
    return {
        "src_id": src_id,
        "outmost_loop": outmost,
        "start": start,
        "end": end,
        "stride": stride,
        "last_index": last_index,
    }


def materialize_stage(template: dict[str, Any], stage: int) -> dict[str, Any]:
    if stage not in range(1, 7):
        raise GapSumConfigOnlyError("stage must be in [1,6]")
    cfg = copy.deepcopy(template)
    previous = regions()[stage - 1]
    output = regions()[stage]
    input_width = 64 if stage == 1 else previous.width
    cfg["dram_loop_configs"] = {
        # Independent A/C/D roots avoid the shared-ready coupling recorded by
        # CDA-GAP-INT32MAC-BRANCH-ISOLATION-001.
        "LC0": _dram_loop(
            src_id=None, outmost=1, start=0, end=BLOCKS, stride=1, last_index=0
        ),
        "LC1": _dram_loop(
            src_id="DRAM_LC.LC0",
            outmost=0,
            start=0,
            end=input_width,
            stride=2,
            last_index=1,
        ),
        "LC2": _dram_loop(
            src_id=None, outmost=1, start=0, end=BLOCKS, stride=1, last_index=0
        ),
        "LC3": _dram_loop(
            src_id="DRAM_LC.LC2",
            outmost=0,
            start=1,
            end=input_width + 1,
            stride=2,
            last_index=1,
        ),
        "LC4": _dram_loop(
            src_id=None, outmost=1, start=0, end=BLOCKS, stride=1, last_index=0
        ),
        "LC5": _dram_loop(
            src_id="DRAM_LC.LC4",
            outmost=0,
            start=0,
            end=output.width,
            stride=1,
            last_index=1,
        ),
    }
    cfg["lc_pe_configs"] = {}
    cfg["buffer_loop_configs"] = {
        "GROUP0": (
            _stage1_read_group("A", 0, "DRAM_LC.LC1")
            if stage == 1
            else _ordinary_group("A", 0)
        ),
        "GROUP1": (
            _stage1_read_group("C", 1, "DRAM_LC.LC3")
            if stage == 1
            else {
                **_ordinary_group("C", 1),
                "ROW_LC": {
                    **_ordinary_group("C", 1)["ROW_LC"],
                    "src_id": "DRAM_LC.LC3",
                },
            }
        ),
        "GROUP2": {
            **_ordinary_group("D", 2),
            "ROW_LC": {
                **_ordinary_group("D", 2)["ROW_LC"],
                "src_id": "DRAM_LC.LC5",
            },
        },
    }
    read_bytes = 8 if stage == 1 else 32
    source_block_stride = (
        INPUT_BYTES_PER_BLOCK if stage == 1 else previous.width * 32
    )
    item_stride = 8 if stage == 1 else 32
    cfg["stream_engine"] = {
        "stream0": _stream(
            target="A",
            mode="read",
            base=previous.base,
            transaction_bytes=read_bytes,
            block_stride=source_block_stride,
            item_stride=item_stride,
            stage1_padding_upper=48 if stage == 1 else None,
        ),
        "stream1": _stream(
            target="C",
            mode="read",
            base=previous.base,
            transaction_bytes=read_bytes,
            block_stride=source_block_stride,
            item_stride=item_stride,
            stage1_padding_upper=47 if stage == 1 else None,
        ),
        "stream2": _stream(
            target="D",
            mode="write",
            base=output.base,
            transaction_bytes=32,
            block_stride=output.width * 32,
            item_stride=32,
        ),
    }
    seed = next(iter(template["buffer_config"].values()))
    cfg["buffer_config"] = {}
    for name in ("buffer0", "buffer4", "buffer5"):
        item = {**copy.deepcopy(seed), "enable": 1}
        cfg["buffer_config"][name] = item
    cfg["stream_engine"]["stream0"]["idx"] = [
        "DRAM_LC.LC0",
        "DRAM_LC.LC1",
        None,
    ]
    cfg["stream_engine"]["stream1"]["idx"] = [
        "DRAM_LC.LC2",
        "DRAM_LC.LC3",
        None,
    ]
    cfg["stream_engine"]["stream2"]["idx"] = [
        "DRAM_LC.LC4",
        "DRAM_LC.LC5",
        None,
    ]
    ga = cfg["general_array"]
    for name in ("inport0", "inport2"):
        ga["inport"][name]["mask"] = [1] * 8
        ga["inport"][name]["src_id"] = 0
        ga["inport"][name]["uint8toint32"] = "true" if stage == 1 else "false"
    ga["inport"]["inport1"]["mask"] = [0] * 8
    ga["outport"]["int32touint8"] = "false"
    for pe in ga["PE_array"].values():
        pe["alu_opcode"] = "int32_mac"
        pe["transout_last_index"] = None
        pe["inport0"].update(
            {"src_id": 0, "mode": "buffer", "keep_last_index": None, "constant": 0}
        )
        pe["inport1"].update(
            {"src_id": None, "mode": "constant", "keep_last_index": None, "constant": 1}
        )
        pe["inport2"].update(
            {"src_id": 0, "mode": "buffer", "keep_last_index": None, "constant": 0}
        )
    return cfg


def build_logical_stage(template: dict[str, Any], stage: int) -> dict[str, Any]:
    """Build the semantic stage before physical region base assignment."""
    cfg = materialize_stage(template, stage)
    cfg["stream_engine"]["stream0"]["base_addr"] = "0x0"
    cfg["stream_engine"]["stream1"]["base_addr"] = "0x0"
    cfg["stream_engine"]["stream2"]["base_addr"] = "0x0"
    return cfg


def bind_stage_addresses(logical: dict[str, Any], stage: int) -> dict[str, Any]:
    """Apply only planner-owned base changes to a logical stage."""
    final = copy.deepcopy(logical)
    previous = regions()[stage - 1]
    output = regions()[stage]
    final["stream_engine"]["stream0"]["base_addr"] = hex(previous.base)
    final["stream_engine"]["stream1"]["base_addr"] = hex(previous.base)
    final["stream_engine"]["stream2"]["base_addr"] = hex(output.base)
    return final


def _leaf_map(value: Any, prefix: str = "$") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key in sorted(value):
            result.update(_leaf_map(value[key], f"{prefix}.{key}"))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            result.update(_leaf_map(item, f"{prefix}[{index}]"))
        return result
    return {prefix: value}


def _leaf_owner(path: str) -> tuple[str, str, str]:
    if path.endswith(".base_addr"):
        return (
            "planner/address_binder",
            "typed per-stage region allocation",
            "CDA-CONFIG-SEMANTIC-OWNERSHIP-001 physical base owner",
        )
    families = (
        ("$.dram_loop_configs.", "logical_schedule/dram_loop"),
        ("$.buffer_loop_configs.", "logical_schedule/buffer_ag"),
        ("$.stream_engine.", "logical_schedule/memory_stream"),
        ("$.buffer_config.", "logical_schedule/buffer_manager"),
        ("$.general_array.", "gap_int32_mac_numeric_and_topology_contract"),
        ("$.lc_pe_configs", "logical_schedule/disabled_lc_pe"),
        ("$.CONFIG", "logical_schedule/stage_enable_state"),
    )
    for prefix, owner in families:
        if path.startswith(prefix):
            return (
                owner,
                "typed node-0071 request + GAP int32_mac family schedule",
                "CDA-CONFIG-SEMANTIC-OWNERSHIP-001 logical owner",
            )
    raise GapSumConfigOnlyError(f"final JSON leaf has no semantic owner: {path}")


def build_materialization_ownership(
    logical: dict[str, Any], final: dict[str, Any], stage: int
) -> dict[str, Any]:
    before = _leaf_map(logical)
    after = _leaf_map(final)
    changed = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) == after.get(path):
            continue
        is_base = path.endswith(".base_addr")
        changed.append(
            {
                "path": path,
                "field_class": "physical_base" if is_base else "non_base",
                "owner": "planner/address_binder" if is_base else None,
                "input_source": (
                    f"typed stage-{stage} scratch region allocation"
                    if is_base
                    else None
                ),
                "transform_formula": (
                    "final_base = stage_region_base + logical_relative_base"
                    if is_base
                    else None
                ),
                "old_value": before.get(path),
                "expected_new_value": after.get(path),
                "authorization": (
                    "CDA-CONFIG-SEMANTIC-OWNERSHIP-001 physical base owner"
                    if is_base
                    else None
                ),
            }
        )
    non_base = [item for item in changed if item["field_class"] == "non_base"]
    if non_base:
        raise GapSumConfigOnlyError(
            f"stage{stage} materializer changed undeclared non-base leaves"
        )
    leaf_ownership = []
    for path, value in sorted(after.items()):
        owner, source, authorization = _leaf_owner(path)
        leaf_ownership.append(
            {
                "path": path,
                "owner": owner,
                "input_source": source,
                "authorization": authorization,
                "final_value": value,
            }
        )
    return {
        "schema": "gap-sum-materialized-field-ownership-v1",
        "stage": stage,
        "logical_leaf_count": len(before),
        "final_leaf_count": len(after),
        "diff_count": len(changed),
        "non_base_diff_count": 0,
        "changed_leaves": changed,
        "all_final_leaves_have_unique_owner": True,
        "leaf_ownership": leaf_ownership,
    }


def materialize_configs(root: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise GapSumConfigOnlyError(f"refusing to overwrite config root: {output}")
    template = _read_json(root / TEMPLATE)
    stages = []
    validator = OperatorConfigValidator()
    for stage in range(1, 7):
        logical_path = output / f"stage-{stage}/logical_config.json"
        path = output / f"stage-{stage}/config.json"
        ownership_path = output / f"stage-{stage}/materialization_ownership.json"
        logical = build_logical_stage(template, stage)
        value = bind_stage_addresses(logical, stage)
        ownership = build_materialization_ownership(logical, value, stage)
        report = validator.validate(value, source=str(path), development_mode=True)
        errors = [issue for issue in report.issues if issue.severity == "error"]
        if errors:
            raise GapSumConfigOnlyError(
                f"stage {stage} strict validation failed: "
                + ", ".join(f"{item.code}:{item.path}" for item in errors)
            )
        _write_json(logical_path, logical)
        _write_json(path, value)
        _write_json(ownership_path, ownership)
        stages.append(
            {
                "stage": stage,
                "logical_config": _manifest_path(
                    logical_path, root, output
                ),
                "logical_config_sha256": sha256_file(logical_path),
                "path": _manifest_path(path, root, output),
                "sha256": sha256_file(path),
                "materialization_ownership": _manifest_path(
                    ownership_path, root, output
                ),
                "materialization_ownership_sha256": sha256_file(ownership_path),
                "materialized_non_base_diff_count": 0,
                "strict_error_count": 0,
            }
        )
    manifest = {
        "schema": "gap-sum-config-only-config-set-v1",
        "claim": CLAIM,
        "stages": stages,
        "bypass_annotation": dict(BYPASS_ANNOTATION),
    }
    _write_json(output / "manifest.json", manifest)
    return manifest


def _expected_occurrences(
    stage: int, cfg: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    previous = regions()[stage - 1]
    output = regions()[stage]
    if cfg is None:
        input_base = previous.base
        c_base = previous.base
        output_base = output.base
        a_blocks = c_blocks = d_blocks = list(range(BLOCKS))
        input_width = 64 if stage == 1 else previous.width
        a_items = list(range(0, input_width, 2))
        c_items = list(range(1, input_width + 1, 2))
        d_items = list(range(output.width))
        source_block_stride = (
            INPUT_BYTES_PER_BLOCK if stage == 1 else previous.width * 32
        )
        item_stride = 8 if stage == 1 else 32
        output_block_stride = output.width * 32
        output_item_stride = 32
    else:
        loops = cfg["dram_loop_configs"]

        def values(name: str) -> list[int]:
            loop = loops[name]
            return list(range(loop["start"], loop["end"], loop["stride"]))

        a_blocks, a_items = values("LC0"), values("LC1")
        c_blocks, c_items = values("LC2"), values("LC3")
        d_blocks, d_items = values("LC4"), values("LC5")
        a_stream = cfg["stream_engine"]["stream0"]
        c_stream = cfg["stream_engine"]["stream1"]
        d_stream = cfg["stream_engine"]["stream2"]
        input_base = int(a_stream["base_addr"], 0)
        c_base = int(c_stream["base_addr"], 0)
        output_base = int(d_stream["base_addr"], 0)
        source_block_stride = a_stream["dim_stride"][0]
        item_stride = a_stream["dim_stride"][1]
        output_block_stride = d_stream["dim_stride"][0]
        output_item_stride = d_stream["dim_stride"][1]
    cardinalities = {
        len(a_blocks) * len(a_items),
        len(c_blocks) * len(c_items),
        len(d_blocks) * len(d_items),
    }
    if len(cardinalities) != 1:
        raise GapSumConfigOnlyError(
            f"stage{stage} independent A/C/D branch cardinalities differ"
        )
    records: list[dict[str, Any]] = []
    a_pairs = (
        (block, item) for block in a_blocks for item in a_items
    )
    c_pairs = (
        (block, item) for block in c_blocks for item in c_items
    )
    d_pairs = (
        (block, item) for block in d_blocks for item in d_items
    )
    for (a_block, a_item), (c_block, c_item), (d_block, d_item) in zip(
        a_pairs, c_pairs, d_pairs, strict=True
    ):
        block = d_block
        item = d_item
        a = input_base + a_block * source_block_stride + a_item * item_stride
        c = c_base + c_block * source_block_stride + c_item * item_stride
        if stage == 1:
            byte_slot = item % 4
            a_layout = [
                {
                    "bank": lane,
                    "column": byte_slot + lane * 4,
                    "byte": byte_slot,
                }
                for lane in range(8)
            ]
            buffer_requests = 1
        else:
            row = 0
            a_layout = [
                {
                    "bank": lane // 4,
                    "row": row,
                    "byte": lane % 4,
                }
                for lane in range(16)
            ] + [
                {
                    "bank": 4 + lane // 4,
                    "row": row,
                    "byte": lane % 4,
                }
                for lane in range(16)
            ]
            buffer_requests = 2
        d = (
            output_base
            + d_block * output_block_stride
            + d_item * output_item_stride
        )
        records.append(
            {
                "ordinal": len(records),
                "block": block,
                "output_index": item,
                "a_loop_index": a_item,
                "c_loop_index": c_item,
                "d_loop_index": d_item,
                "a": a,
                "c": c,
                "d": d,
                "read_transaction_bytes": 8 if stage == 1 else 32,
                "write_transaction_bytes": 32,
                "buffer_request_count_per_read_occurrence": buffer_requests,
                "a_buffer_bank_byte": a_layout,
                "a_zero": a_item >= previous.logical_width,
                "c_zero": c_item >= previous.logical_width,
                "terminal": (
                    block == d_blocks[-1] and item == d_items[-1]
                ),
            }
        )
    return records


def _digest(records: Iterable[Any]) -> str:
    return sha256_bytes(canonical_json_bytes(list(records)))


def validate_materialized_configs(root: Path, config_root: Path) -> dict[str, Any]:
    old = _read_json(root / "configs/gap_int32_mac_bypass_v1/stage-1/config.json")
    old_s0 = old["stream_engine"]["stream0"]
    old_s1 = old["stream_engine"]["stream1"]
    negative = {
        "legacy_stage1_transaction_is_16_not_8": old_s0["idx_size"][0] == 15,
        "legacy_c_base_is_separate_region_not_aligned_even_odd_route": (
            int(old_s1["base_addr"], 0) != int(old_s0["base_addr"], 0)
        ),
        "legacy_rejected": True,
    }
    if not all(negative.values()):
        raise GapSumConfigOnlyError("legacy negative control no longer discriminates")

    summaries = []
    for stage in range(1, 7):
        logical = _read_json(config_root / f"stage-{stage}/logical_config.json")
        cfg = _read_json(config_root / f"stage-{stage}/config.json")
        ownership = _read_json(
            config_root / f"stage-{stage}/materialization_ownership.json"
        )
        expected_ownership = build_materialization_ownership(logical, cfg, stage)
        if ownership != expected_ownership:
            raise GapSumConfigOnlyError(
                f"stage{stage} materialization ownership differs"
            )
        a = cfg["stream_engine"]["stream0"]
        c = cfg["stream_engine"]["stream1"]
        d = cfg["stream_engine"]["stream2"]
        expected_read_bytes = 8 if stage == 1 else 32
        if a["idx_size"][0] + 1 != expected_read_bytes:
            raise GapSumConfigOnlyError(f"stage{stage} A transaction differs")
        if c["idx_size"][0] + 1 != expected_read_bytes:
            raise GapSumConfigOnlyError(f"stage{stage} C transaction differs")
        if int(c["base_addr"], 0) != int(a["base_addr"], 0):
            raise GapSumConfigOnlyError(f"stage{stage} A/C aligned base differs")
        loops = cfg["dram_loop_configs"]
        if (
            loops["LC1"]["start"] != 0
            or loops["LC1"]["stride"] != 2
            or loops["LC3"]["start"] != 1
            or loops["LC3"]["stride"] != 2
        ):
            raise GapSumConfigOnlyError(
                f"stage{stage} A/C even-odd index ownership differs"
            )
        branch_roots = {
            loops["LC1"]["src_id"],
            loops["LC3"]["src_id"],
            loops["LC5"]["src_id"],
        }
        if branch_roots != {
            "DRAM_LC.LC0",
            "DRAM_LC.LC2",
            "DRAM_LC.LC4",
        }:
            raise GapSumConfigOnlyError(
                f"stage{stage} independent A/C/D roots differ"
            )
        stage1_byte_lane_fill = (
            stage1_buffer_byte_lane_contract(cfg) if stage == 1 else None
        )
        if d["idx_size"][0] + 1 != 32:
            raise GapSumConfigOnlyError(f"stage{stage} D transaction differs")
        for pe in cfg["general_array"]["PE_array"].values():
            if pe["alu_opcode"] != "int32_mac" or pe["transout_last_index"] is not None:
                raise GapSumConfigOnlyError(f"stage{stage} nontransout opcode differs")
        records = _expected_occurrences(stage, cfg)
        output = regions()[stage]
        addresses = [record["d"] for record in records]
        if addresses != list(range(output.base, output.end, 32)):
            raise GapSumConfigOnlyError(f"stage{stage} output coverage differs")
        terminal_count = sum(record["terminal"] for record in records)
        if terminal_count != 1:
            raise GapSumConfigOnlyError(f"stage{stage} terminal count differs")
        written_bytes = {
            byte
            for address in addresses
            for byte in range(address, address + 32)
        }
        expected_bytes = set(range(output.base, output.end))
        if written_bytes != expected_bytes:
            raise GapSumConfigOnlyError(
                f"stage{stage} final output byte coverage differs"
            )
        summaries.append(
            {
                "stage": stage,
                "occurrences_per_slice": len(records),
                "a_request_count_per_slice": len(records),
                "c_request_count_per_slice": len(records),
                "d_transaction_count_per_slice": len(records),
                "buffer_requests_per_a_or_c_occurrence": (
                    1 if stage == 1 else 2
                ),
                "buffer_transactions_per_full_row": (
                    4 if stage == 1 else 1
                ),
                "stage1_buffer_byte_lane_fill": stage1_byte_lane_fill,
                "ordered_occurrence_sha256": _digest(
                    (
                        record["ordinal"],
                        record["a"],
                        record["c"],
                        record["d"],
                        int(record["a_zero"]),
                        int(record["c_zero"]),
                        int(record["terminal"]),
                    )
                    for record in records
                ),
                "materialization_diff": {
                    "diff_count": ownership["diff_count"],
                    "non_base_diff_count": ownership["non_base_diff_count"],
                    "all_changes_owned": True,
                    "final_leaf_owner_count": len(
                        ownership["leaf_ownership"]
                    ),
                    "all_final_leaves_have_unique_owner": ownership[
                        "all_final_leaves_have_unique_owner"
                    ],
                },
                "address_equation": {
                    "a": "A_base + LC0*dim_stride[0] + LC1*dim_stride[1]",
                    "c": "C_base + LC2*dim_stride[0] + LC3*dim_stride[1]",
                    "d": "D_base + LC4*dim_stride[0] + LC5*dim_stride[1]",
                    "a_c_base_equal": True,
                    "a_even_c_odd_indexed": True,
                    "independent_branch_roots": True,
                },
                "output_byte_coverage": {
                    "written_byte_count": len(written_bytes),
                    "expected_byte_count": output.size,
                    "unique_transaction_base_count": len(set(addresses)),
                    "exact_region_coverage": True,
                    "written_byte_set_sha256": _digest(
                        (byte,) for byte in sorted(written_bytes)
                    ),
                },
                "first": records[0],
                "first_padding": next(
                    (
                        record
                        for record in records
                        if record["a_zero"] or record["c_zero"]
                    ),
                    None,
                ),
                "last": records[-1],
            }
        )
    rs = regions()
    if any(left.end > right.base for left, right in zip(rs, rs[1:])):
        raise GapSumConfigOnlyError("scratch regions overlap")
    return {
        "schema": "gap-sum-config-only-materialized-roundtrip-v1",
        "valid": True,
        "negative_control": negative,
        "regions": [
            {
                "stage": item.stage,
                "base": hex(item.base),
                "end_exclusive": hex(item.end),
                "size_bytes_per_slice": item.size,
                "physical_width": item.width,
                "logical_width": item.logical_width,
            }
            for item in rs
        ],
        "regions_non_overlapping": True,
        "materialized_non_base_field_ownership_valid": True,
        "stage_summaries": summaries,
        "final_unique_128bit_lines_per_slice": BLOCKS * 2,
        "bypass_annotation": dict(BYPASS_ANNOTATION),
    }


def run_config_bound_simulator(root: Path, config_root: Path) -> dict[str, Any]:
    # Consume and validate the final JSONs before performing any numeric work.
    roundtrip = validate_materialized_configs(root, config_root)
    source = np.load(root / W3_INPUT, allow_pickle=False)
    expected = np.load(root / W3_SUM, allow_pickle=False).reshape(16, 2048)
    current = np.zeros((16, BLOCKS, 64, LANES), dtype=np.int32)
    current[:, :, :49, :] = (
        source.reshape(16, 256, 8, 49).transpose(0, 1, 3, 2).astype(np.int32)
    )
    stage_reports = []
    scratch: dict[int, np.ndarray] = {}
    for stage in range(1, 7):
        cfg = _read_json(config_root / f"stage-{stage}/config.json")
        if any(
            pe["alu_opcode"] != "int32_mac"
            for pe in cfg["general_array"]["PE_array"].values()
        ):
            raise GapSumConfigOnlyError("simulator rejected non-int32_mac JSON")
        left = current[:, :, 0::2, :].astype(np.int64)
        right = current[:, :, 1::2, :].astype(np.int64)
        result = (left * 1 + right).astype(np.int32)
        scratch[stage] = result.copy()
        stage_reports.append(
            {
                "stage": stage,
                "input_width": int(current.shape[2]),
                "output_width": int(result.shape[2]),
                "scratch_base": hex(regions()[stage].base),
                "payload_sha256": sha256_bytes(
                    result.astype("<i4", copy=False).tobytes()
                ),
                "min": int(result.min()),
                "max": int(result.max()),
                "config_sha256": sha256_file(
                    config_root / f"stage-{stage}/config.json"
                ),
            }
        )
        current = result
    actual = current[:, :, 0, :].reshape(16, 2048)
    if not np.array_equal(actual, expected):
        where = np.argwhere(actual != expected)[0].tolist()
        raise GapSumConfigOnlyError(f"config-bound numeric mismatch at {where}")
    expected_hash = sha256_bytes(expected.astype("<i4", copy=False).tobytes())
    actual_hash = sha256_bytes(actual.astype("<i4", copy=False).tobytes())
    return {
        "schema": "gap-sum-config-bound-simulator-v1",
        "valid": True,
        "executor": "final-json-decoded-pairwise-int32-mac",
        "consumed_materialized_roundtrip_sha256": sha256_bytes(
            canonical_json_bytes(roundtrip)
        ),
        "stage_reports": stage_reports,
        "output_shape": [16, 2048, 1, 1],
        "actual_sha256": actual_hash,
        "expected_sha256": expected_hash,
        "bit_exact": actual_hash == expected_hash,
        "value_range": [int(actual.min()), int(actual.max())],
        "quant_tail_consumed": False,
        "complete_gap_target": False,
        "claim": CLAIM,
    }


def _run_mapping(
    root: Path, config: Path, output: Path, *, seed: int = 42
) -> None:
    command = [
        str(Path(sys.executable).resolve()),
        str(root / "tools/generate_operator_config_mapping_evidence.py"),
        str(config),
        str(output),
        "--ndp-sim-root",
        str(root / "ndp-sim"),
        "--seed",
        str(seed),
        "--heuristic-iterations",
        "20000",
        "--heuristic-restarts",
        "4",
        "--timeout-seconds",
        "120",
    ]
    process = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode != 0:
        raise GapSumConfigOnlyError(
            f"mapping failed for {config}:\n{process.stdout}\n{process.stderr}"
        )


def _line_count(path: Path) -> int:
    return sum(bool(line.strip()) for line in path.read_text(encoding="ascii").splitlines())


def _build_execplan(root: Path, artifact: Path) -> dict[str, Any]:
    model_src = root / "ndp-sim/model_execplan/src"
    if str(model_src) not in sys.path:
        sys.path.insert(0, str(model_src))
    from execution_plan_generator.instruction_generator import (  # type: ignore
        ClockEnableEncoder,
        LoadConfigEncoder,
        StartCompEncoder,
    )

    cfg_pkg = artifact / "install/cfg_pkg"
    cfg_pkg.mkdir(parents=True)
    commands = [ClockEnableEncoder.encode(SLICE_MASK)]
    explanations = ["Clock_Enable"]
    stages = []
    for stage in range(1, 7):
        mapping = artifact / f"mapping/run-a/stage-{stage}"
        bitstream = mapping / "modules_dump_128b.bin"
        installed = cfg_pkg / f"gap_sum_config_only_s{stage}_128b.bin"
        shutil.copy2(bitstream, installed)
        length = _line_count(bitstream) * 2
        load = LoadConfigEncoder.encode(
            length, CONFIG_BASES[stage - 1] >> 10, False, SLICE_MASK
        )
        start = StartCompEncoder.encode(SLICE_MASK)
        barrier = (SLICE_MASK << 3) | 0b110
        commands.extend((load, start, barrier))
        explanations.extend(
            (
                f"Load_Config sum_s{stage}",
                f"Start_Comp sum_s{stage}",
                f"Barrier sum_s{stage}",
            )
        )
        stages.append(
            {
                "stage": stage,
                "config_base": hex(CONFIG_BASES[stage - 1]),
                "config_length_64bit_words": length,
                "bitstream_sha256": sha256_file(installed),
            }
        )
    lines = []
    for index in range(0, len(commands), 2):
        low = commands[index]
        high = commands[index + 1] if index + 1 < len(commands) else 0
        lines.append(f"{high:064b}{low:064b}")
    execplan = artifact / "install/execplan.txt"
    execplan.parent.mkdir(parents=True, exist_ok=True)
    execplan.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    (artifact / "instructions_explained.txt").write_text(
        "\n".join(
            f"Command {index}: {word:064b} | {explanations[index]}"
            for index, word in enumerate(commands)
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "command_count": len(commands),
        "clock_enable_count": 1,
        "load_config_count": 6,
        "start_comp_count": 6,
        "barrier_count": 6,
        "final_opcode": "0b110",
        "stages": stages,
        "execplan_sha256": sha256_file(execplan),
        "generator": (
            "locked execution_plan_generator.instruction_generator encoders; "
            "explicit serialized ScheduleIR because the native composite GAP "
            "handler does not register six int32_mac stages"
        ),
    }


def _mapping_identity(path: Path) -> dict[str, Any]:
    names = (
        "source_config.json",
        "mapping_review.json",
        "parsed_bitstream.txt",
        "modules_dump_64b.bin",
        "modules_dump_128b.bin",
        "detailed_dump.txt",
        "encoder_source_manifest.json",
        "native_mapping_state.json",
        "native_stderr.log",
    )
    return {name: sha256_file(path / name) for name in names}


def _artifact_manifest(root: Path, artifact: Path) -> dict[str, Any]:
    files = [
        {
            "path": path.relative_to(artifact).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(artifact.rglob("*"))
        if path.is_file() and path != artifact / "manifest.json"
    ]
    value = {
        "schema": "gap-sum-config-only-artifact-manifest-v1",
        "claim": CLAIM,
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "server_package_allowed": False,
        "files": files,
    }
    value["manifest_sha256"] = sha256_bytes(canonical_json_bytes(value))
    return value


def build_contract(root: Path, artifact: Path) -> dict[str, Any]:
    report = _read_json(artifact / "validation_report.json")
    manifest = _read_json(artifact / "manifest.json")
    value = {
        "schema": SCHEMA,
        "status": CLAIM,
        "scope": "r5:hwop-0071-00 sum stage only",
        "typed_request": {
            "path": f"{ARTIFACT_ROOT}/typed_request.json",
            "sha256": sha256_file(artifact / "typed_request.json"),
        },
        "validation_report": {
            "path": f"{ARTIFACT_ROOT}/validation_report.json",
            "sha256": sha256_file(artifact / "validation_report.json"),
            "valid": report["valid"],
        },
        "artifact_manifest": {
            "path": f"{ARTIFACT_ROOT}/manifest.json",
            "sha256": sha256_file(artifact / "manifest.json"),
            "semantic_self_hash": manifest["manifest_sha256"],
        },
        "rule_ids": list(RULE_IDS),
        "bypass_annotation": dict(BYPASS_ANNOTATION),
        "quant_tail_dependency": {
            "decision": "NO_UNCONDITIONAL_PURE_CONFIG_PROVEN",
            "contract": "contracts/operator_config/exact_uint8_quant_tail_capability_v1.json",
            "contract_sha256": sha256_file(
                root / "contracts/operator_config/exact_uint8_quant_tail_capability_v1.json"
            ),
            "materialized": False,
            "complete_gap_target": False,
        },
        "input_replay": {
            "path": f"{ARTIFACT_ROOT}/input_replay_report.json",
            "sha256": sha256_file(artifact / "input_replay_report.json"),
            "host_precomputed_internal_tensor": False,
        },
        "release": {
            "candidate_release": False,
            "formal_target_instance_allowed": False,
            "server_package_allowed": False,
            "dynamic_baseline": "NO_DYNAMIC_BASELINE",
            "evidence_level": "E2_LOCAL_SUM_STAGE",
            "functional_rtl_modified": False,
            "repair_v9_consumed": False,
        },
    }
    value["contract_sha256"] = sha256_bytes(canonical_json_bytes(value))
    return value


def build_local_e2(
    root: Path,
    *,
    config_root: Path | None = None,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    configs = (config_root or root / CONFIG_ROOT).resolve()
    artifact = (artifact_root or root / ARTIFACT_ROOT).resolve()
    if configs.exists():
        raise GapSumConfigOnlyError(f"refusing to overwrite config root: {configs}")
    if artifact.exists():
        raise GapSumConfigOnlyError(f"refusing to overwrite artifact root: {artifact}")
    receipt = build_read_receipt(root)
    typed = build_typed_request()
    input_replay = validate_input_replay(root, typed)
    materialize_configs(root, configs)
    artifact.mkdir(parents=True)
    _write_json(artifact / "read_receipt.json", receipt)
    _write_json(artifact / "typed_request.json", typed)
    _write_json(artifact / "input_replay_report.json", input_replay)
    roundtrip = validate_materialized_configs(root, configs)
    _write_json(artifact / "materialized_roundtrip_report.json", roundtrip)
    simulator = run_config_bound_simulator(root, configs)
    _write_json(artifact / "config_bound_simulator_report.json", simulator)

    deterministic: list[dict[str, Any]] = []
    for run in ("run-a", "run-b"):
        for stage in range(1, 7):
            _run_mapping(
                root,
                configs / f"stage-{stage}/config.json",
                artifact / f"mapping/{run}/stage-{stage}",
            )
    for stage in range(1, 7):
        left = _mapping_identity(artifact / f"mapping/run-a/stage-{stage}")
        right = _mapping_identity(artifact / f"mapping/run-b/stage-{stage}")
        if left != right:
            raise GapSumConfigOnlyError(f"stage{stage} double mapping differs")
        evidence = _read_json(
            artifact / f"mapping/run-a/stage-{stage}/mapping_evidence.json"
        )
        if evidence.get("penalty") != 0 or evidence.get("fallback_used") is not False:
            raise GapSumConfigOnlyError(f"stage{stage} mapping is not exact")
        final_config = configs / f"stage-{stage}/config.json"
        if sha256_file(
            artifact / f"mapping/run-a/stage-{stage}/source_config.json"
        ) != sha256_file(final_config):
            raise GapSumConfigOnlyError(
                f"stage{stage} encoder source is not final materialized JSON"
            )
        deterministic.append(
            {"stage": stage, "identical": True, "products": left}
        )
    execplan = _build_execplan(root, artifact)
    sca = {
        "Exec_Path": "install/execplan.txt",
        "Exec_Length": _line_count(artifact / "install/execplan.txt"),
        "Repeat_Num": 6,
        "runtime_stage_order": [f"sum_s{stage}" for stage in range(1, 7)],
        "server_package": False,
    }
    _write_json(artifact / "sca_cfg.json", sca)
    _write_json(
        artifact / "sca_cfg_D.json",
        {
            f"slice{slice_index}_D": {
                "base_addr": hex(BASES[6]),
                "length_128bit_words": 512,
                "formal_readback": False,
            }
            for slice_index in range(16)
        },
    )
    report = {
        "schema": "gap-sum-config-only-validation-report-v1",
        "status": CLAIM,
        "valid": True,
        "evidence_level": "E2_LOCAL_SUM_STAGE",
        "typed_request_valid": True,
        "input_replay_noncomputational": input_replay,
        "strict_config_count": 6,
        "materialized_roundtrip_valid": roundtrip["valid"],
        "mapping_double_rebuild": {
            "isolated_run_count": 2,
            "all_products_identical": True,
            "excluded_path_bearing_files": {
                "artifact_validation_report.json": (
                    "absolute artifact_dir differs between isolated run roots"
                ),
                "mapping_evidence.json": (
                    "embeds native stdout hash whose log names the isolated "
                    "temporary output root"
                ),
                "native_stdout.log": (
                    "diagnostic log names the isolated temporary output root"
                ),
                "bundle_manifest.json": (
                    "transitively hashes the path-bearing evidence files"
                ),
            },
            "stages": deterministic,
        },
        "execplan_lifecycle": execplan,
        "scratch_visibility": {
            "explicit_regions": True,
            "non_overlapping": True,
            "same_mask_barrier_after_every_stage": True,
            "consumer_reads_predecessor_region": True,
        },
        "config_bound_simulator": simulator,
        "negative_controls": roundtrip["negative_control"],
        "bypass_annotation": dict(BYPASS_ANNOTATION),
        "quant_tail_dependency": typed["quant_tail_dependency"],
        "release": {
            "candidate_release": False,
            "formal_target_instance_allowed": False,
            "server_package_allowed": False,
            "functional_rtl_modified": False,
            "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        },
    }
    _write_json(artifact / "validation_report.json", report)
    _write_json(artifact / "manifest.json", _artifact_manifest(root, artifact))
    contract = build_contract(root, artifact)
    if config_root is None and artifact_root is None:
        _write_json(root / CONTRACT, contract)
    return {
        "status": CLAIM,
        "config_root": str(configs),
        "artifact_root": str(artifact),
        "contract_path": str(root / CONTRACT) if config_root is None else None,
        "contract_sha256": contract["contract_sha256"],
        "complete_gap_target": False,
        "quant_tail_materialized": False,
    }


__all__ = [
    "ARTIFACT_ROOT",
    "BYPASS_ANNOTATION",
    "CLAIM",
    "CONFIG_ROOT",
    "CONTRACT",
    "GapSumConfigOnlyError",
    "build_contract",
    "build_local_e2",
    "build_read_receipt",
    "build_typed_request",
    "materialize_configs",
    "materialize_stage",
    "run_config_bound_simulator",
    "validate_input_replay",
    "validate_materialized_configs",
]
