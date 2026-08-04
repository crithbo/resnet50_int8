from __future__ import annotations

import copy
import itertools
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


SCHEMA = "resnet50-stage-operator-semantics-audit-v1"
CONTRACT_PATH = (
    "contracts/operator_config/stage_operator_semantics_audit_v1.json"
)
GAP_REQUEST_ID = "r5:hwop-0071-00"
GAP_CONFIG_PATH = (
    "configs/native_ndp_sim/"
    "avgpool_config_2048_7_7_strict_v1/config.json"
)
GAP_MAPPING_PATH = (
    "artifacts/operator_config_validation/r5-server-candidates/"
    "gap-hwop0071-sum-v1/config/op0/mapping_review.json"
)
GAP_DUMP_PATH = (
    "artifacts/operator_config_validation/r5-server-candidates/"
    "gap-hwop0071-sum-v1/config/op0/detailed_dump.txt"
)
GAP_SIM6_REPORT_PATH = (
    "server_returns/gap_hwop0071_sim6_20260723/"
    "gap_numeric_path_report.json"
)
GAP_PROBE_V4_ANALYSIS_PATH = (
    "server_returns/gap_hwop0071_probe_v4_return_20260723/"
    "gap_probe_v4_analysis.json"
)
GAP_PROBE_V4_NUMERIC_PATH = (
    "server_returns/gap_hwop0071_probe_v4_return_20260723/"
    "gap_numeric_path_report_v4.json"
)
GAP_PROBE_V4_DIAGNOSIS_PATH = (
    "server_returns/gap_hwop0071_probe_v4_return_20260723/"
    "GAP_PROBE_V4_DIAGNOSIS.md"
)
GAP_PROBE_V5_ANALYSIS_PATH = (
    "server_returns/gap_hwop0071_probe_v5_return_20260723/"
    "GAP_PROBE_V5_ANALYSIS.md"
)
GAP_PROBE_V7_ANALYSIS_PATH = (
    "server_returns/gap_hwop0071_probe_v7_return_20260724/"
    "gap_probe_v7_analysis.json"
)
GAP_PROBE_V7_NUMERIC_PATH = (
    "server_returns/gap_hwop0071_probe_v7_return_20260724/"
    "gap_numeric_path_report_v7.json"
)
GAP_PROBE_V7_ACCEPTANCE_PATH = (
    "server_returns/gap_hwop0071_probe_v7_return_20260724/"
    "native_return_acceptance_v7.json"
)
GAP_PROBE_V7_DIAGNOSIS_PATH = (
    "server_returns/gap_hwop0071_probe_v7_return_20260724/"
    "GAP_PROBE_V7_DIAGNOSIS.md"
)
GAP_RTL_IDENTITY_ANALYSIS_PATH = (
    "server_returns/gap_rtl_three_way_identity_20260723/"
    "SERVER_RTL_THREE_WAY_IDENTITY_ANALYSIS.md"
)
GAP_PROBE_V1_PATH = (
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "gap_hwop0071_sum_probe_v1.zip"
)
GAP_D_INDEX_BLOCKER = "B_GAP_D_INDEX_CARRIER_SEMANTICS"
GAP_GA_ACCUM_STATE_BLOCKER = "B_GAP_GA_ACCUM_STATE"
GA_INT8_MAX_NUMERIC_BLOCKER = "B_GA_INT8_MAX_NUMERIC"
GA_INT8_MAX_FLOW_BLOCKER = "B_GA_INT8_MAX_FLOW"
GA_INT32_TO_FP32_DOMAIN_BLOCKER = "B_GA_INT32TOFP32_INPUT_DOMAIN"
SA_INT8_CSA_NUMERIC_BLOCKER = "B_SA_INT8_CSA_NUMERIC"
N2N_CONFIG_LIFETIME_BLOCKER = "B_N2N_CONFIG_LIFETIME"
AUTHORITY_PATH = "contracts/operator_config/operator_config_authority_v1.json"


SOURCE_PATHS = (
    "contracts/typed_config_parameter_contract.json",
    AUTHORITY_PATH,
    "contracts/operator_config/register_semantics_v1.json",
    "ndp-sim/bitstream/config/base.py",
    "ndp-sim/bitstream/config/loop.py",
    "ndp-sim/bitstream/config/mapper.py",
    "ndp-sim/bitstream/config/stream.py",
    "ndp-sim/bitstream/config/buffer.py",
    "ndp-sim/bitstream/config/special.py",
    "ndp-sim/bitstream/config/general.py",
    "ndp-sim/bitstream/config/neighbor.py",
    "ndp-sim/bitstream/parse.py",
    "ndp-sim/bitstream/index.py",
    "ndp-sim/bitstream/bit.py",
    "NDP_copy01/rtl/includes/NDP_Parameters.svh",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC/"
    "IGA_LC_Config.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC/"
    "IGA_LC_Connect.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC/"
    "IGA_LC_Inbuffer.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC/"
    "IGA_LC_Counter.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
    "IGA_PE_Config.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
    "IGA_PE_Connect.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
    "IGA_PE_Inbuffer.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
    "IGA_PE_ALU.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
    "IGA_PE_INT_ALU.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
    "IGA_PE_Outbuffer.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
    "IGA_PE.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Memory_AG_Idx_Queue.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Buffer_AG_Idx_Queue.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Parallel_Prefix_Sum.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Memory_RD_Stream_Engine/RD_Memory_AG.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Memory_RD_Stream_Engine/RD_Data_Channel.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Memory_WR_Stream_Engine/WR_Memory_AG.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Memory_WR_Stream_Engine/WR_Data_Channel.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine_Config.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine_Connect.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Memory_RD_Stream_Engine/WR_Buffer_AG.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Memory_WR_Stream_Engine/RD_Buffer_AG.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
    "Buffer_Manager_Cluster_Config.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
    "Buffer_Manager_Cluster.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
    "Buffer_Manager_Cluster_Connect.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
    "Buffer_Manager.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
    "Memory_Req_Manager.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
    "Array_Request_Manager.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
    "Neighbor_Req_Manager.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "NDP_copy01/rtl/Slice/Specialized_Array/"
    "Specialized_Array_Config.sv",
    "NDP_copy01/rtl/Slice/Specialized_Array/"
    "Specialized_Array.sv",
    "NDP_copy01/rtl/Slice/Specialized_Array/SA_Inport/"
    "SA_Inport_Connect.sv",
    "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
    "SA_PE_Control_Block.sv",
    "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
    "SA_PE_Outbuffer.sv",
    "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
    "SA_PE_ALU.sv",
    "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
    "SA_PE_Float_Control.v",
    "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
    "SA_PE_Mul_Array.v",
    "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
    "SA_PE_Float_CSA.v",
    "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
    "SA_PE_Float_Last.v",
    "NDP_copy01/rtl/Slice/Specialized_Array/SA_Outport/"
    "SA_Outport_Connect.sv",
    "NDP_copy01/rtl/Slice/Specialized_Array/SA_Outport/"
    "SA_Outport.sv",
    "NDP_copy01/rtl/utils/CSA/CSA_4to2.v",
    "NDP_copy01/rtl/utils/CSA/CSA_3to2.v",
    "NDP_copy01/rtl/Slice/General_Array/GA_Inport/"
    "GA_Inport_Group_Config.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_Inport/"
    "GA_Inport_Connect.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_Inport/GA_Inport.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_Outport/"
    "GA_Outport_Group_Config.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_Outport/"
    "GA_Outport_Connect.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_Outport/GA_Outport.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/"
    "GA_PE_Group_Interconnect.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_Config.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_ALU.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE/GA_PE.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/"
    "GA_PE_Float_Control.v",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/"
    "GA_PE_Float_CSA.v",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/"
    "GA_PE_Float_Last.v",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/"
    "GA_SFU_PE.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/"
    "GA_SFU_PE_Preprocess.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/"
    "GA_SFU_PE_Postprocess.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
    "Neighbor_Stream_Engine/NSE_Controller.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
    "Neighbor_Stream_Engine/Neighbor_In_AG.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
    "Neighbor_Stream_Engine/Neighbor_Out_AG.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine_Config.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine_Connect.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
    "Buffer_Manager_Cluster_Connect.sv",
    "NDP_copy01/rtl/NDP_Top.sv",
    "contracts/ga_int8_pipeline_backpressure_defect_report_20260723.md",
    "NDP_copy01/rtl/Slice/slice2hub_crossbar.sv",
    "NDP_copy01/rtl/Datahub/Datahub_Req_Crossbar/"
    "datahub_req_crossbar.sv",
    GAP_CONFIG_PATH,
    GAP_MAPPING_PATH,
    GAP_DUMP_PATH,
    GAP_SIM6_REPORT_PATH,
    GAP_PROBE_V4_ANALYSIS_PATH,
    GAP_PROBE_V4_NUMERIC_PATH,
    GAP_PROBE_V4_DIAGNOSIS_PATH,
    GAP_PROBE_V5_ANALYSIS_PATH,
    GAP_PROBE_V7_ANALYSIS_PATH,
    GAP_PROBE_V7_NUMERIC_PATH,
    GAP_PROBE_V7_ACCEPTANCE_PATH,
    GAP_PROBE_V7_DIAGNOSIS_PATH,
    GAP_RTL_IDENTITY_ANALYSIS_PATH,
    "tools/analyze_gap_probe_log.py",
    GAP_PROBE_V1_PATH,
    "resnet50_pipeline/operator_config_validator.py",
    "resnet50_pipeline/operator_config_artifact_validator.py",
    "tools/generate_conv_1x1_real.py",
    "tools/generate_conv_3x3_real.py",
)


class StageOperatorSemanticsAuditError(ValueError):
    pass


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StageOperatorSemanticsAuditError(
            f"cannot parse JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise StageOperatorSemanticsAuditError(
            f"JSON root must be an object: {path}"
        )
    return value


def _require_files(root: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for relative in SOURCE_PATHS:
        path = root / relative
        if not path.is_file():
            raise StageOperatorSemanticsAuditError(
                f"required semantics evidence is missing: {relative}"
            )
        result.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return result


def _require_snippets(path: Path, snippets: Iterable[str]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [snippet for snippet in snippets if snippet not in text]
    if missing:
        raise StageOperatorSemanticsAuditError(
            f"source semantics changed in {path}: missing {missing[0]!r}"
        )


def _gap_request(typed: Mapping[str, Any]) -> dict[str, Any]:
    matches = [
        item
        for item in typed.get("hw_ops", [])
        if isinstance(item, Mapping)
        and item.get("hw_op_id") == GAP_REQUEST_ID.removeprefix("r5:")
    ]
    if len(matches) != 1:
        raise StageOperatorSemanticsAuditError(
            "exact GAP typed stage is not unique"
        )
    hw_op = copy.deepcopy(dict(matches[0]))
    geometry = hw_op.get("logical_geometry")
    if (
        hw_op.get("hw_op_type") != "GlobalAverageSumInt32"
        or not isinstance(geometry, Mapping)
        or geometry.get("input_shapes") != [[16, 2048, 7, 7], [1]]
        or geometry.get("output_shapes") != [[16, 2048, 1, 1]]
        or geometry.get("output_dtypes") != ["int32"]
    ):
        raise StageOperatorSemanticsAuditError(
            "exact GAP stage geometry differs"
        )
    return {
        "request_id": GAP_REQUEST_ID,
        "identity": {
            "hw_op_id": hw_op["hw_op_id"],
            "node_id": hw_op["node_id"],
            "onnx_name": hw_op["onnx_name"],
            "onnx_op_type": hw_op["onnx_op_type"],
            "hw_op_type": hw_op["hw_op_type"],
            "stage": hw_op["stage"],
        },
        "logical_geometry": geometry,
    }


def lc_pe_int_result(
    opcode: str,
    inport0: int,
    inport1: int,
    inport2: int = 0,
) -> int:
    """Return the bound RTL LC-PE ALU result as an unsigned 16-bit pattern."""

    mask = (1 << 16) - 1

    def signed16(value: int) -> int:
        bits = int(value) & mask
        return bits - (1 << 16) if bits & (1 << 15) else bits

    operand0 = signed16(inport0)
    operand1 = signed16(inport1)
    if opcode == "add":
        result = operand0 + operand1
    elif opcode == "mul":
        result = operand0 * operand1
    elif opcode == "mac":
        result = operand0 * operand1 + signed16(inport2)
    else:
        raise StageOperatorSemanticsAuditError(
            f"unsupported LC-PE opcode: {opcode!r}"
        )
    return result & mask


def mse_memory_request_address(
    indexes: Iterable[int],
    strides: Iterable[int],
    *,
    base_addr: int,
    address_remapping: Iterable[int] | None = None,
    transfer_bias: int = 0,
) -> int:
    """Return the 26-bit DDR-line request address generated by Memory AG."""

    index_values = list(indexes)
    stride_values = list(strides)
    if len(index_values) != 3 or len(stride_values) != 3:
        raise StageOperatorSemanticsAuditError(
            "MSE address model requires three indexes and three strides"
        )
    if not 0 <= int(base_addr) < (1 << 30):
        raise StageOperatorSemanticsAuditError(
            "MSE base address must fit the 30-bit byte-address field"
        )
    if int(transfer_bias) < 0:
        raise StageOperatorSemanticsAuditError(
            "MSE transfer bias must be nonnegative"
        )

    byte_mask = (1 << 30) - 1
    line_mask = (1 << 26) - 1
    transaction_bias = sum(
        (int(index) & 0xFFFF) * (int(stride) & ((1 << 20) - 1))
        for index, stride in zip(
            index_values, stride_values, strict=True
        )
    ) & byte_mask
    transfer_addr = (transaction_bias + int(transfer_bias)) & byte_mask
    transfer_addr_nooff = transfer_addr >> 4

    remap = (
        list(range(26))
        if address_remapping is None
        else list(address_remapping)
    )
    if len(remap) != 26 or sorted(remap) != list(range(26)):
        raise StageOperatorSemanticsAuditError(
            "MSE address remapping must be a permutation of 0..25"
        )
    mapped = sum(
        ((transfer_addr_nooff >> source_bit) & 1) << output_bit
        for output_bit, source_bit in enumerate(remap)
    )
    return (mapped + (int(base_addr) >> 4)) & line_mask


def mse_transfer_plan(
    transaction_bias: int,
    total_size: int,
) -> list[dict[str, int | bool]]:
    """Split one MSE byte transaction into the RTL's 16-byte transfers."""

    if not 0 <= int(transaction_bias) < (1 << 30):
        raise StageOperatorSemanticsAuditError(
            "MSE transaction bias must fit 30 bits"
        )
    if not 1 <= int(total_size) <= 255:
        raise StageOperatorSemanticsAuditError(
            "MSE total size must be in the nonzero 8-bit domain"
        )

    remaining = int(total_size)
    current_bias = 0
    position = int(transaction_bias) & 0xF
    result: list[dict[str, int | bool]] = []
    while remaining:
        try_size = 16 - position if not result else 16
        final_size = min(remaining, try_size)
        result.append(
            {
                "transfer_bias": current_bias,
                "byte_address": (
                    int(transaction_bias) + current_bias
                )
                & ((1 << 30) - 1),
                "start_position": position,
                "size": final_size,
                "valid_mask": (
                    ((1 << final_size) - 1) << position
                )
                & 0xFFFF,
                "partial": final_size < 16,
            }
        )
        remaining -= final_size
        current_bias += final_size
        position = 0
    return result


def mse_lane_indexes(
    base_indexes: Iterable[int],
    idx_sizes: Iterable[int | None],
    *,
    transfer_bias: int,
    lane: int,
) -> tuple[int, int, int]:
    """Return JSON-order logical indexes for one transaction-relative lane."""

    bases = list(base_indexes)
    encoded_sizes = list(idx_sizes)
    if len(bases) != 3 or len(encoded_sizes) != 3:
        raise StageOperatorSemanticsAuditError(
            "MSE lane model requires three base indexes and idx_size fields"
        )
    if int(transfer_bias) < 0 or not 0 <= int(lane) < 16:
        raise StageOperatorSemanticsAuditError(
            "MSE lane requires nonnegative transfer bias and lane 0..15"
        )
    sizes = [
        1 if item is None else int(item) + 1
        for item in encoded_sizes
    ]
    if any(
        size <= 0 or size & (size - 1)
        for size in sizes
    ):
        raise StageOperatorSemanticsAuditError(
            "MSE lane idx_size+1 values must be powers of two"
        )
    offset = int(transfer_bias) + int(lane)
    increments = [
        offset & (sizes[0] - 1),
        (offset >> int(math.log2(sizes[0]))) & (sizes[1] - 1),
        (
            offset
            >> int(math.log2(sizes[0] * sizes[1]))
        )
        & (sizes[2] - 1),
    ]
    return tuple(
        (int(base) + increment) & 0xFFFF
        for base, increment in zip(bases, increments, strict=True)
    )


def mse_boundary_masks(
    base_indexes: Iterable[int],
    idx_sizes: Iterable[int | None],
    *,
    transfer_bias: int,
    start_position: int,
    valid_mask: int,
    padding_enable: Iterable[int],
    padding_low: Iterable[int | None],
    padding_up: Iterable[int | None],
    tailing_enable: Iterable[int],
    tailing_low: Iterable[int | None],
    tailing_up: Iterable[int | None],
) -> dict[str, Any]:
    """Return the bound RTL padding/tail masks and lane source selections."""

    pad_enable = list(padding_enable)
    pad_low = list(padding_low)
    pad_up = list(padding_up)
    tail_enable = list(tailing_enable)
    tail_low = list(tailing_low)
    tail_up = list(tailing_up)
    vectors = (
        pad_enable,
        pad_low,
        pad_up,
        tail_enable,
        tail_low,
        tail_up,
    )
    if any(len(vector) != 3 for vector in vectors):
        raise StageOperatorSemanticsAuditError(
            "MSE boundary model requires three entries per boundary vector"
        )
    if not 0 <= int(start_position) < 16:
        raise StageOperatorSemanticsAuditError(
            "MSE start_position must be 0..15"
        )

    def outside(
        indexes: tuple[int, int, int],
        enabled: list[int],
        lows: list[int | None],
        ups: list[int | None],
    ) -> bool:
        for index, flag, low, up in zip(
            indexes, enabled, lows, ups, strict=True
        ):
            if not flag:
                continue
            if low is None or up is None:
                raise StageOperatorSemanticsAuditError(
                    "enabled MSE boundary requires low and up"
                )
            if index < int(low) or index > int(up):
                return True
        return False

    lane_indexes = [
        mse_lane_indexes(
            base_indexes,
            idx_sizes,
            transfer_bias=transfer_bias,
            lane=lane,
        )
        for lane in range(16)
    ]
    padding_unshifted = sum(
        int(outside(indexes, pad_enable, pad_low, pad_up)) << lane
        for lane, indexes in enumerate(lane_indexes)
    )
    tailing_unshifted = sum(
        int(outside(indexes, tail_enable, tail_low, tail_up)) << lane
        for lane, indexes in enumerate(lane_indexes)
    )
    padding_mask = (
        padding_unshifted << int(start_position)
    ) & 0xFFFF
    tailing_mask = (
        tailing_unshifted << int(start_position)
    ) & 0xFFFF
    valid = int(valid_mask) & 0xFFFF
    read_sources = []
    write_sources = []
    for physical_lane in range(16):
        bit = 1 << physical_lane
        if not valid & bit:
            read_sources.append("invalid")
        elif padding_mask & bit:
            read_sources.append("padding")
        elif tailing_mask & bit:
            read_sources.append("zero")
        else:
            read_sources.append("ddr")
        write_sources.append(
            "new"
            if valid & bit and not tailing_mask & bit
            else "old_ddr"
        )
    return {
        "transaction_lane_indexes_json_order": [
            list(item) for item in lane_indexes
        ],
        "padding_mask_unshifted": padding_unshifted,
        "tailing_mask_unshifted": tailing_unshifted,
        "padding_mask_physical": padding_mask,
        "tailing_mask_physical": tailing_mask,
        "valid_mask_physical": valid,
        "read_lane_sources": read_sources,
        "write_lane_sources": write_sources,
    }


def mse_buffer_lane_plan(
    row: int,
    col: int,
    spatial_strides: Iterable[int],
    *,
    spatial_size: int | None = None,
) -> dict[str, Any]:
    """Return the Buffer-AG and Memory-Req-Manager lane decode."""

    strides = list(spatial_strides)
    size = len(strides) if spatial_size is None else int(spatial_size)
    if not 0 <= int(row) < 4:
        raise StageOperatorSemanticsAuditError(
            "buffer row must fit the two-bit RTL row address"
        )
    if not 0 <= int(col) < 32:
        raise StageOperatorSemanticsAuditError(
            "buffer column must fit the five-bit RTL column address"
        )
    if not 1 <= size <= 16 or len(strides) != size:
        raise StageOperatorSemanticsAuditError(
            "buffer spatial strides must contain exactly 1..16 active lanes"
        )
    if any(
        isinstance(stride, bool)
        or not isinstance(stride, int)
        or not 0 <= stride < 32
        for stride in strides
    ):
        raise StageOperatorSemanticsAuditError(
            "buffer spatial strides must be five-bit unsigned integers"
        )

    lanes = []
    for lane, stride in enumerate(strides):
        expanded_col = (int(col) + stride) & 0x1F
        lanes.append(
            {
                "lane": lane,
                "row": int(row),
                "stride": stride,
                "expanded_col": expanded_col,
                "bank": expanded_col >> 2,
                "byte_offset": expanded_col & 0x3,
                "bank_strobe": 1 << (expanded_col & 0x3),
            }
        )
    return {
        "request_valid_mask": (1 << size) - 1,
        "row": int(row),
        "base_col": int(col),
        "lanes": lanes,
    }


def buffer_array_request_sequence(
    *,
    mode: int,
    end_row: int,
    logical_lifetime: int,
) -> list[dict[str, Any]]:
    """Return the RTL Array-Request-Manager row/lifetime traversal."""

    if mode not in (0, 1):
        raise StageOperatorSemanticsAuditError(
            "buffer mode must be zero or one"
        )
    if not 0 <= int(end_row) < 4:
        raise StageOperatorSemanticsAuditError(
            "buffer end row must fit two bits"
        )
    if not 1 <= int(logical_lifetime) <= 16:
        raise StageOperatorSemanticsAuditError(
            "buffer logical lifetime must be in 1..16"
        )

    rows = range(int(end_row) + 1)
    lives = range(int(logical_lifetime))
    coordinates = (
        ((row, life) for life in lives for row in rows)
        if mode == 0
        else ((row, life) for row in rows for life in lives)
    )
    return [
        {
            "row": row,
            "lifetime_index": life,
            "expires_after_access": life == int(logical_lifetime) - 1,
        }
        for row, life in coordinates
    ]


def sa_transout_decision(
    *,
    upstream_last: bool,
    upstream_last_index: int,
    transout_last_index: int,
) -> dict[str, bool]:
    """Return the exact SA PE terminal classification."""

    if not 0 <= int(upstream_last_index) < 16:
        raise StageOperatorSemanticsAuditError(
            "SA upstream last index must fit four bits"
        )
    if not 0 <= int(transout_last_index) < 16:
        raise StageOperatorSemanticsAuditError(
            "SA transout last index must fit four bits"
        )
    last = bool(upstream_last)
    index = int(upstream_last_index)
    threshold = int(transout_last_index)
    return {
        "ignore": last and index > threshold,
        "matched": last and index == threshold,
        "out": last and index < threshold,
        "result_last": last and index < threshold,
        "accumulator_bank_change": last and index <= threshold,
    }


def _sa_sign_extend(value: int, width: int) -> int:
    mask = (1 << width) - 1
    bits = int(value) & mask
    return bits | (~mask) if bits & (1 << (width - 1)) else bits


def sa_int8_rtl_trace(
    data_a: Iterable[int],
    data_b: Iterable[int],
    psum: int = 0,
) -> dict[str, Any]:
    """Model the current SA INT8 multiplier/CSA wiring bit-for-bit.

    DataA contains four signed bytes and DataB four unsigned bytes, both in
    MSB-to-LSB lane order. The returned result is the unsigned 32-bit RTL
    pattern. This intentionally preserves the second left shift applied to
    the 4:2 CSA carry by SA_PE_Mul_Array.v.
    """

    a = list(data_a)
    b = list(data_b)
    if len(a) != 4 or len(b) != 4:
        raise StageOperatorSemanticsAuditError(
            "SA INT8 model requires four A and four B lanes"
        )
    if any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or not -128 <= value <= 127
        for value in a
    ):
        raise StageOperatorSemanticsAuditError(
            "SA DataA lanes must be signed int8 values"
        )
    if any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= 255
        for value in b
    ):
        raise StageOperatorSemanticsAuditError(
            "SA DataB lanes must be unsigned uint8 values"
        )
    if (
        isinstance(psum, bool)
        or not isinstance(psum, int)
        or not -(1 << 31) <= psum < (1 << 32)
    ):
        raise StageOperatorSemanticsAuditError(
            "SA psum must fit a signed or unsigned 32-bit pattern"
        )

    mask17 = (1 << 17) - 1
    mask32 = (1 << 32) - 1
    products = [
        (left * right) & mask17
        for left, right in zip(a, b, strict=True)
    ]
    op0, op1, op2, op3 = products
    sum_temp = op0 ^ op1 ^ op2 ^ op3
    cout_array = (op0 & op1) | (op0 & op2) | (op1 & op2)
    cin_array = (cout_array << 1) & mask17
    sum17 = (cin_array ^ sum_temp) & mask17
    carry_temp = (
        (cin_array & sum_temp)
        | (((~sum_temp) & mask17) & op3)
    )
    carry17 = (carry_temp << 1) & mask17
    sum32 = _sa_sign_extend(sum17, 17) & mask32
    carry32 = _sa_sign_extend(carry17, 17) & mask32
    shifted_carry32 = (carry32 << 1) & mask32
    result = (sum32 + shifted_carry32 + (int(psum) & mask32)) & mask32
    conventional = (
        sum(left * right for left, right in zip(a, b, strict=True))
        + int(psum)
    ) & mask32
    return {
        "data_a_signed_msb_to_lsb": a,
        "data_b_unsigned_msb_to_lsb": b,
        "products_17bit_twos_complement": products,
        "csa4_sum17": sum17,
        "csa4_carry17_already_shifted": carry17,
        "csa4_carry_sign_extended_then_shifted_again": shifted_carry32,
        "psum32": int(psum) & mask32,
        "rtl_result32": result,
        "conventional_dot_plus_psum32": conventional,
        "matches_conventional_dot": result == conventional,
    }


def sa_int8_rtl_result(
    data_a: Iterable[int],
    data_b: Iterable[int],
    psum: int = 0,
) -> int:
    """Return only the unsigned 32-bit result of :func:`sa_int8_rtl_trace`."""

    return int(sa_int8_rtl_trace(data_a, data_b, psum)["rtl_result32"])


def sa_fp32_output_conversion(value: int, target: str) -> int:
    """Return the exact 16-bit SA outport conversion result."""

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value < (1 << 32)
    ):
        raise StageOperatorSemanticsAuditError(
            "SA FP32 conversion input must be a 32-bit pattern"
        )
    if target not in {"fp16", "bf16"}:
        raise StageOperatorSemanticsAuditError(
            "SA output conversion target must be fp16 or bf16"
        )

    sign = (value >> 31) & 1
    exponent = (value >> 23) & 0xFF
    fraction = value & ((1 << 23) - 1)
    if target == "fp16":
        ceil = (fraction >> 13) & 0x3FF
        guard = (fraction >> 12) & 1
        stick = bool(fraction & 0xFFF)
        if exponent >= 0x8F:
            return (sign << 15) | (0x1F << 10)
        if exponent <= 0x70:
            return sign << 15
        exponent_increment = (
            ceil == 0x3FF and bool(guard) and stick
        )
        out_exponent = (
            exponent + (0x91 if exponent_increment else 0x90)
        ) & 0x1F
        if guard and not stick:
            out_fraction = (ceil + (ceil & 1)) & 0x3FF
        elif guard:
            out_fraction = 0 if ceil == 0x3FF else ceil + 1
        else:
            out_fraction = ceil
        return (sign << 15) | (out_exponent << 10) | out_fraction

    ceil = (fraction >> 16) & 0x7F
    guard = (fraction >> 15) & 1
    stick = bool(fraction & 0x7FFF)
    exponent_increment = ceil == 0x7F and bool(guard) and stick
    out_exponent = (exponent + int(exponent_increment)) & 0xFF
    if guard and not stick:
        out_fraction = (ceil + (ceil & 1)) & 0x7F
    elif guard:
        out_fraction = 0 if ceil == 0x7F else ceil + 1
    else:
        out_fraction = ceil
    return (sign << 15) | (out_exponent << 7) | out_fraction


def ga_int32_to_fp32_rtl_trace(value: int) -> dict[str, Any]:
    """Model the exact GA input INT32-to-FP32 converter wiring."""

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not -(1 << 31) <= value < (1 << 32)
    ):
        raise StageOperatorSemanticsAuditError(
            "GA INT32 conversion input must fit a signed or unsigned 32-bit pattern"
        )
    bits = int(value) & 0xFFFFFFFF
    sign = (bits >> 31) & 1
    low31 = bits & 0x7FFFFFFF
    magnitude31 = ((~low31 + 1) & 0x7FFFFFFF) if sign else low31
    lzd_input = (magnitude31 << 1) & 0xFFFFFFFF
    lzd_position = (
        32 - lzd_input.bit_length() if lzd_input else 0
    )
    shifted = (lzd_input << lzd_position) & 0xFFFFFFFF
    int32_shift = (shifted >> 1) & 0x7FFFFFFF
    zero_flag = bits == 0
    rtl_min_flag = bits == 0xFFFFFFFF
    fraction_ceil = (int32_shift >> 7) & 0x7FFFFF
    guard = (int32_shift >> 6) & 1
    sticky = bool(int32_shift & 0x3F)
    fraction_overflow = fraction_ceil == 0x7FFFFF and bool(guard)
    if zero_flag or rtl_min_flag:
        fraction = 0
    elif guard and not sticky:
        fraction = (fraction_ceil + (fraction_ceil & 1)) & 0x7FFFFF
    elif guard:
        fraction = (fraction_ceil + 1) & 0x7FFFFF
    else:
        fraction = fraction_ceil
    if zero_flag:
        exponent = 0
    elif rtl_min_flag:
        exponent = 0x9E
    else:
        exponent = (
            (0x9E if fraction_overflow else 0x9D) - lzd_position
        ) & 0xFF
    result = (sign << 31) | (exponent << 23) | fraction
    return {
        "input_bits": bits,
        "sign": sign,
        "rtl_magnitude_low31": magnitude31,
        "lzd_position": lzd_position,
        "rtl_min_flag_is_all_ones": rtl_min_flag,
        "fraction_ceil": fraction_ceil,
        "guard": guard,
        "sticky": sticky,
        "result_bits": result,
    }


def ga_int32_to_fp32_rtl_result(value: int) -> int:
    """Return only the GA converter's unsigned FP32 result pattern."""

    return int(ga_int32_to_fp32_rtl_trace(value)["result_bits"])


def ga_int8_max_rtl_result(data_a: int, data_c: int) -> int:
    """Return the current GA ``int8_max`` byte-lane result.

    The RTL compares four unsigned byte lanes from A and C. Its final select is
    inverted relative to the symbolic opcode name, so the exact result is the
    lane-wise unsigned minimum.
    """

    for label, value in (("A", data_a), ("C", data_c)):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value < (1 << 32)
        ):
            raise StageOperatorSemanticsAuditError(
                f"GA INT8 max input {label} must be a 32-bit pattern"
            )
    result = 0
    for shift in (0, 8, 16, 24):
        a_lane = (int(data_a) >> shift) & 0xFF
        c_lane = (int(data_c) >> shift) & 0xFF
        result |= min(a_lane, c_lane) << shift
    return result


def ga_transout_decision(
    *,
    reduction_opcode: bool,
    upstream_last: bool,
    upstream_last_index: int,
    transout_last_index: int,
) -> dict[str, bool]:
    """Return the GA terminal/reduction comparisons before pipeline flushing."""

    if not 0 <= int(upstream_last_index) < 16:
        raise StageOperatorSemanticsAuditError(
            "GA upstream last index must fit four bits"
        )
    if not 0 <= int(transout_last_index) < 16:
        raise StageOperatorSemanticsAuditError(
            "GA transout last index must fit four bits"
        )
    last = bool(upstream_last)
    index = int(upstream_last_index)
    threshold = int(transout_last_index)
    trigger = bool(reduction_opcode) and last and index <= threshold
    return {
        "ordinary_result_last": last and index < threshold,
        "reduction_flush_trigger": trigger,
        "reduction_result_forces_last_after_flush": trigger,
        "threshold_equal_suppresses_pre_flush_last": last and index == threshold,
    }


_N2N_LOW_PREV = (1, 3, 14, 5, 2, 7, 4, 6, 9, 11, 26, 10, 0, 12,
                 16, 13, 18, 15, 20, 17, 22, 19, 24, 21, 8, 23, 27, 25)
_N2N_LOW_NEXT = (12, 0, 4, 1, 6, 3, 7, 5, 24, 8, 11, 9, 13, 15,
                 2, 17, 14, 19, 16, 21, 18, 23, 20, 25, 22, 27, 10, 26)
_N2N_HIGH_PREV = (1, 3, 0, 2, 5, 7, 4, 6, 9, 11, 8, 10, 14, 12,
                  15, 13, 18, 16, 19, 17, 22, 20, 23, 21, 26, 24, 27, 25)
_N2N_HIGH_NEXT = (2, 0, 3, 1, 6, 4, 7, 5, 10, 8, 11, 9, 13, 15,
                  12, 14, 17, 19, 16, 18, 21, 23, 20, 22, 25, 27, 24, 26)


def n2n_neighbor(slice_id: int, selector: int, direction: str) -> int:
    """Resolve the exact NDP_Top low/high previous/next neighbor map."""

    if (
        isinstance(slice_id, bool)
        or not isinstance(slice_id, int)
        or not 0 <= slice_id < 28
    ):
        raise StageOperatorSemanticsAuditError(
            "N2N slice id must be an integer in 0..27"
        )
    if selector not in (0, 1):
        raise StageOperatorSemanticsAuditError(
            "N2N selector must be zero (low ring) or one (high ring)"
        )
    tables = {
        ("previous", 0): _N2N_LOW_PREV,
        ("next", 0): _N2N_LOW_NEXT,
        ("previous", 1): _N2N_HIGH_PREV,
        ("next", 1): _N2N_HIGH_NEXT,
    }
    try:
        return int(tables[(direction, selector)][slice_id])
    except KeyError as error:
        raise StageOperatorSemanticsAuditError(
            "N2N direction must be previous or next"
        ) from error


def n2n_transfer_plan(mem_loop: int, stream_index: int = 0) -> dict[str, Any]:
    """Return transfer count and hard-wired source/destination bank sequence."""

    if (
        isinstance(mem_loop, bool)
        or not isinstance(mem_loop, int)
        or not 1 <= mem_loop <= 32
    ):
        raise StageOperatorSemanticsAuditError(
            "N2N mem_loop must be an integer in 1..32"
        )
    if stream_index not in (0, 1):
        raise StageOperatorSemanticsAuditError(
            "N2N stream index must be zero or one"
        )
    pair = (("buffer0", "buffer1"), ("buffer2", "buffer3"))[stream_index]
    transfers = mem_loop - 1
    return {
        "encoded_nse_cnt_size": transfers,
        "row_addresses_per_transfer": [0, 1, 2, 3],
        "transfer_count": transfers,
        "source_buffers": [pair[index % 2] for index in range(transfers)],
        "destination_buffers": [
            pair[(index + 1) % 2] for index in range(transfers)
        ],
        "json_ping_pong_bit_controls_sequence": False,
    }


def _authorized_ga_corpus(root: Path) -> dict[str, Any]:
    authority = _load_object(root / AUTHORITY_PATH)
    records = authority.get("records")
    authorized = [
        item
        for item in records
        if isinstance(item, Mapping)
        and item.get("configuration_correctness")
        == "user_authorized_correct_reference"
    ] if isinstance(records, list) else []
    if len(authorized) != 65:
        raise StageOperatorSemanticsAuditError(
            "authorized GA corpus baseline count differs"
        )

    paths: list[str] = []
    opcode_counts: Counter[str] = Counter()
    transout_counts: Counter[str] = Counter()
    mode_counts = [Counter() for _ in range(3)]
    conversion_counts = [Counter() for _ in range(3)]
    output_conversion_counts: Counter[str] = Counter()
    pe_count = 0
    sfu_column_violation_count = 0
    input_pingpong_enabled_count = 0
    for record in sorted(authorized, key=lambda item: str(item.get("path"))):
        relative = record.get("path")
        if not isinstance(relative, str):
            raise StageOperatorSemanticsAuditError(
                "authorized GA path is malformed"
            )
        path = root / relative
        if (
            not path.is_file()
            or sha256_file(path) != record.get("sha256")
            or path.stat().st_size != record.get("size_bytes")
        ):
            raise StageOperatorSemanticsAuditError(
                f"authorized config identity differs: {relative}"
            )
        config = _load_object(path)
        ga = config.get("general_array")
        if not isinstance(ga, Mapping):
            continue
        paths.append(relative)
        pes = ga.get("PE_array")
        if isinstance(pes, Mapping):
            for name, pe in pes.items():
                if not isinstance(pe, Mapping):
                    continue
                pe_count += 1
                opcode = str(pe.get("alu_opcode"))
                opcode_counts[opcode] += 1
                transout_counts[str(pe.get("transout_last_index"))] += 1
                if opcode in {"rec", "sqrt", "rec_sqrt", "sfu_activation"}:
                    column = int(str(name)[-1]) if str(name)[-1:].isdigit() else -1
                    if column not in {1, 3}:
                        sfu_column_violation_count += 1
                for index in range(3):
                    port = pe.get(f"inport{index}")
                    if isinstance(port, Mapping):
                        mode_counts[index][str(port.get("mode"))] += 1
        inports = ga.get("inport")
        if isinstance(inports, Mapping):
            for index in range(3):
                port = inports.get(f"inport{index}")
                if not isinstance(port, Mapping):
                    continue
                if port.get("pingpong_en") == 1:
                    input_pingpong_enabled_count += 1
                enabled = [
                    field
                    for field in (
                        "fp16tofp32",
                        "bf16tofp32",
                        "int32tofp32",
                        "uint8tofp32",
                        "uint8toint32",
                    )
                    if port.get(field) in (True, "true")
                ]
                conversion_counts[index][enabled[0] if enabled else "none"] += 1
        outport = ga.get("outport")
        if isinstance(outport, Mapping):
            enabled = [
                field
                for field in ("fp32tofp16", "fp32tobf16", "int32touint8")
                if outport.get(field) in (True, "true")
            ]
            output_conversion_counts[enabled[0] if enabled else "none"] += 1

    actual = {
        "ga_config_count": len(paths),
        "pe_instance_count": pe_count,
        "sfu_column_violation_count": sfu_column_violation_count,
        "input_pingpong_enabled_count": input_pingpong_enabled_count,
    }
    expected = {
        "ga_config_count": 60,
        "pe_instance_count": 511,
        "sfu_column_violation_count": 0,
        "input_pingpong_enabled_count": 0,
    }
    if actual != expected:
        raise StageOperatorSemanticsAuditError(
            "authorized GA inventory differs"
        )
    return {
        "authorized_config_count": 65,
        **actual,
        "paths": paths,
        "opcode_counts": dict(sorted(opcode_counts.items())),
        "transout_last_index_counts": dict(sorted(transout_counts.items())),
        "inport_mode_counts": [
            dict(sorted(counter.items())) for counter in mode_counts
        ],
        "input_conversion_counts": [
            dict(sorted(counter.items())) for counter in conversion_counts
        ],
        "output_conversion_counts": dict(
            sorted(output_conversion_counts.items())
        ),
        "sample_boundary": (
            "the 60 GA references contain no input ping-pong, BF16 input/output "
            "conversion, sqrt opcode or int32_mac opcode. INT8 max appears in "
            "two native MaxPool references and is dynamically stalled before "
            "writeback by the independently recorded pipeline0 defect"
        ),
    }


def _authorized_n2n_corpus(root: Path) -> dict[str, Any]:
    authority = _load_object(root / AUTHORITY_PATH)
    records = authority.get("records")
    authorized = [
        item
        for item in records
        if isinstance(item, Mapping)
        and item.get("configuration_correctness")
        == "user_authorized_correct_reference"
    ] if isinstance(records, list) else []
    if len(authorized) != 65:
        raise StageOperatorSemanticsAuditError(
            "authorized N2N corpus baseline count differs"
        )

    paths: list[str] = []
    stream_count = 0
    mem_loop_counts: Counter[str] = Counter()
    selector_counts: Counter[str] = Counter()
    pingpong_counts: Counter[str] = Counter()
    missing_pair_count = 0
    for record in sorted(authorized, key=lambda item: str(item.get("path"))):
        relative = record.get("path")
        if not isinstance(relative, str):
            raise StageOperatorSemanticsAuditError(
                "authorized N2N path is malformed"
            )
        path = root / relative
        if (
            not path.is_file()
            or sha256_file(path) != record.get("sha256")
            or path.stat().st_size != record.get("size_bytes")
        ):
            raise StageOperatorSemanticsAuditError(
                f"authorized config identity differs: {relative}"
            )
        config = _load_object(path)
        n2n = config.get("n2n")
        if not isinstance(n2n, Mapping) or not n2n:
            continue
        paths.append(relative)
        buffers = config.get("buffer_config")
        buffer_map = buffers if isinstance(buffers, Mapping) else {}
        for name, stream in n2n.items():
            if not isinstance(stream, Mapping):
                continue
            stream_count += 1
            mem_loop_counts[str(stream.get("mem_loop"))] += 1
            selector_counts[
                f"{stream.get('src_slice_sel')}->{stream.get('dst_slice_sel')}"
            ] += 1
            pingpong_counts[str(stream.get("ping_pong"))] += 1
            index = int(str(name)[-1]) if str(name)[-1:].isdigit() else -1
            pair = (
                ("buffer0", "buffer1"),
                ("buffer2", "buffer3"),
            )[index] if index in (0, 1) else ()
            if any(
                not isinstance(buffer_map.get(buffer_name), Mapping)
                or buffer_map[buffer_name].get("nbr_enable") != 1
                or buffer_map[buffer_name].get("buf_end_row_addr") != 3
                for buffer_name in pair
            ):
                missing_pair_count += 1

    actual = {
        "n2n_config_count": len(paths),
        "neighbor_stream_count": stream_count,
        "missing_enabled_full_row_pair_count": missing_pair_count,
    }
    expected = {
        "n2n_config_count": 3,
        "neighbor_stream_count": 3,
        "missing_enabled_full_row_pair_count": 0,
    }
    if actual != expected:
        raise StageOperatorSemanticsAuditError(
            "authorized N2N inventory differs"
        )
    return {
        "authorized_config_count": 65,
        **actual,
        "paths": paths,
        "mem_loop_counts": dict(sorted(mem_loop_counts.items())),
        "selector_counts": dict(sorted(selector_counts.items())),
        "ping_pong_counts": dict(sorted(pingpong_counts.items())),
        "sample_boundary": (
            "all three references use neighbor_stream0 and ping_pong=1. Two "
            "four-slice references use high-ring selectors 1->1; one 28-slice "
            "reference uses low-ring selectors 0->0. No neighbor_stream1 or "
            "mixed-direction selector pair is authorized"
        ),
    }


def _authorized_sa_corpus(root: Path) -> dict[str, Any]:
    authority = _load_object(root / AUTHORITY_PATH)
    records = authority.get("records")
    authorized = [
        item
        for item in records
        if isinstance(item, Mapping)
        and item.get("configuration_correctness")
        == "user_authorized_correct_reference"
    ] if isinstance(records, list) else []
    if len(authorized) != 65:
        raise StageOperatorSemanticsAuditError(
            "authorized SA corpus baseline count differs"
        )

    paths: list[str] = []
    mode_counts: Counter[str] = Counter()
    data_type_counts: Counter[str] = Counter()
    bias_counts: Counter[str] = Counter()
    transout_counts: Counter[str] = Counter()
    out_mode_counts: Counter[str] = Counter()
    fp32tofp16_counts: Counter[str] = Counter()
    fp32tobf16_counts: Counter[str] = Counter()
    inport_counters: list[Counter[str]] = [Counter() for _ in range(3)]
    pair_threshold_match_count = 0
    inport2_topology_violation_count = 0

    for record in sorted(authorized, key=lambda item: str(item.get("path"))):
        relative = record.get("path")
        if not isinstance(relative, str):
            raise StageOperatorSemanticsAuditError(
                "authorized SA path is malformed"
            )
        path = root / relative
        if (
            not path.is_file()
            or sha256_file(path) != record.get("sha256")
            or path.stat().st_size != record.get("size_bytes")
        ):
            raise StageOperatorSemanticsAuditError(
                f"authorized config identity differs: {relative}"
            )
        config = _load_object(path)
        sa = config.get("special_array")
        if not isinstance(sa, Mapping):
            continue
        paths.append(relative)
        mode_counts[str(sa.get("mode"))] += 1
        data_type_counts[str(sa.get("data_type"))] += 1
        bias_counts[str(sa.get("bias_enable"))] += 1
        transout_counts[str(sa.get("transout_last_index"))] += 1
        out = sa.get("outport")
        if isinstance(out, Mapping):
            out_mode_counts[str(out.get("mode"))] += 1
            fp32tofp16_counts[str(out.get("fp32tofp16"))] += 1
            fp32tobf16_counts[str(out.get("fp32tobf16"))] += 1
        buffers = config.get("buffer_config")
        buffer_map = buffers if isinstance(buffers, Mapping) else {}
        for index in range(3):
            port = sa.get(f"inport{index}")
            if not isinstance(port, Mapping):
                continue
            signature = "|".join(
                str(port.get(field))
                for field in (
                    "enable",
                    "pingpong_en",
                    "pingpong_last_index",
                    "nbr_enable",
                )
            )
            inport_counters[index][signature] += 1
            if index < 2 and port.get("pingpong_en") == 1:
                pair = (("buffer0", "buffer1"), ("buffer2", "buffer3"))[
                    index
                ]
                threshold = port.get("pingpong_last_index")
                left = buffer_map.get(pair[0])
                right = buffer_map.get(pair[1])
                if (
                    isinstance(left, Mapping)
                    and isinstance(right, Mapping)
                    and left.get("buf_full_last_index") == threshold
                    and right.get("buf_full_last_index") == threshold
                ):
                    pair_threshold_match_count += 1
            if index == 2 and (
                port.get("enable") != 0
                or port.get("pingpong_en") != 0
                or port.get("pingpong_last_index") is not None
                or port.get("nbr_enable") != 0
            ):
                inport2_topology_violation_count += 1

    actual = {
        "sa_config_count": len(paths),
        "pair_threshold_match_count": pair_threshold_match_count,
        "inport2_topology_violation_count": inport2_topology_violation_count,
    }
    expected = {
        "sa_config_count": 8,
        "pair_threshold_match_count": 16,
        "inport2_topology_violation_count": 0,
    }
    if actual != expected:
        raise StageOperatorSemanticsAuditError(
            "authorized SA inventory differs"
        )
    return {
        "authorized_config_count": 65,
        **actual,
        "paths": paths,
        "mode_counts": dict(sorted(mode_counts.items())),
        "data_type_counts": dict(sorted(data_type_counts.items())),
        "bias_enable_counts": dict(sorted(bias_counts.items())),
        "transout_last_index_counts": dict(sorted(transout_counts.items())),
        "outport_mode_counts": dict(sorted(out_mode_counts.items())),
        "fp32tofp16_counts": dict(sorted(fp32tofp16_counts.items())),
        "fp32tobf16_counts": dict(sorted(fp32tobf16_counts.items())),
        "inport_signatures": [
            dict(sorted(counter.items())) for counter in inport_counters
        ],
        "sample_boundary": (
            "all eight authorized SA references are FP16 with bias disabled; "
            "INT8, BF16 and enabled-bias arithmetic are RTL-only. All sixteen "
            "enabled inport0/inport1 ping-pong thresholds equal both physical "
            "buffer-pair full thresholds"
        ),
    }


def _authorized_buffer_corpus(root: Path) -> dict[str, Any]:
    authority = _load_object(root / AUTHORITY_PATH)
    records = authority.get("records")
    authorized = [
        item
        for item in records if isinstance(item, Mapping)
        and item.get("configuration_correctness")
        == "user_authorized_correct_reference"
    ] if isinstance(records, list) else []
    if len(authorized) != 65:
        raise StageOperatorSemanticsAuditError(
            "authorized buffer corpus count differs"
        )

    buffer_names: Counter[str] = Counter()
    modes: Counter[str] = Counter()
    lifetimes: Counter[str] = Counter()
    masks: Counter[str] = Counter()
    spatial_sizes: Counter[str] = Counter()
    pingpong_thresholds: Counter[str] = Counter()
    buffer_instance_count = 0
    implicit_enable_count = 0
    explicit_enable_one_count = 0
    disabled_count = 0
    neighbor_enabled_count = 0
    neighbor_enabled_default_27_count = 0
    neighbor_enabled_explicit_3_count = 0
    read_threshold_match_count = 0
    mapped_buffer_missing_count = 0
    pingpong_enabled_count = 0
    pingpong_non_read_a_count = 0
    pingpong_pair_mismatch_count = 0
    read_buffer_ignored_dst_port_count = 0
    buffer5_sa_source_count = 0
    buffer5_ga_source_count = 0

    target_buffer = {"A": 0, "B": 2, "B'": 3, "C": 4, "D": 4}
    for record in sorted(authorized, key=lambda item: str(item.get("path"))):
        relative = record.get("path")
        if not isinstance(relative, str):
            raise StageOperatorSemanticsAuditError(
                "authorized buffer path is malformed"
            )
        path = root / relative
        if (
            not path.is_file()
            or sha256_file(path) != record.get("sha256")
            or path.stat().st_size != record.get("size_bytes")
        ):
            raise StageOperatorSemanticsAuditError(
                f"authorized config identity differs: {relative}"
            )
        config = _load_object(path)
        raw_buffers = config.get("buffer_config")
        buffers = raw_buffers if isinstance(raw_buffers, Mapping) else {}
        for name, value in sorted(buffers.items()):
            if not isinstance(value, Mapping):
                continue
            buffer_instance_count += 1
            buffer_names[str(name)] += 1
            modes[str(value.get("mode"))] += 1
            lifetimes[str(value.get("buffer_life_time"))] += 1
            mask = value.get("mask")
            masks[
                "".join(str(item) for item in mask)
                if isinstance(mask, list)
                else str(mask)
            ] += 1
            if "enable" not in value:
                implicit_enable_count += 1
            elif value.get("enable") == 1:
                explicit_enable_one_count += 1
            else:
                disabled_count += 1
            if name != "buffer5":
                read_buffer_ignored_dst_port_count += 1
            elif value.get("dst_port") == 0:
                buffer5_sa_source_count += 1
            elif value.get("dst_port") == 1:
                buffer5_ga_source_count += 1
            if value.get("nbr_enable") == 1:
                neighbor_enabled_count += 1
                if value.get("buffer_nbr_cnt") is None:
                    neighbor_enabled_default_27_count += 1
                elif value.get("buffer_nbr_cnt") == 3:
                    neighbor_enabled_explicit_3_count += 1

        raw_streams = config.get("stream_engine")
        streams = raw_streams if isinstance(raw_streams, Mapping) else {}
        for stream in streams.values():
            if not isinstance(stream, Mapping):
                continue
            spatial_sizes[str(stream.get("buf_spatial_size"))] += 1
            pingpong = stream.get("ping_pong")
            threshold = stream.get("pingpong_last_index")
            pingpong_thresholds[f"{pingpong}|{threshold}"] += 1
            mode = stream.get("mode")
            target = stream.get("target")
            mapped_index = (
                5 if mode == "write" else target_buffer.get(str(target))
            )
            mapped_name = (
                f"buffer{mapped_index}"
                if mapped_index is not None
                else None
            )
            mapped = buffers.get(mapped_name) if mapped_name else None
            if not isinstance(mapped, Mapping):
                mapped_buffer_missing_count += 1
            elif (
                mode == "read"
                and stream.get("buf_full_last_index")
                == mapped.get("buf_full_last_index")
            ):
                read_threshold_match_count += 1
            if pingpong == 1:
                pingpong_enabled_count += 1
                if mode != "read" or target != "A":
                    pingpong_non_read_a_count += 1
                if buffers.get("buffer0") != buffers.get("buffer1"):
                    pingpong_pair_mismatch_count += 1

    expected = {
        "buffer_instance_count": 193,
        "implicit_enable_count": 48,
        "explicit_enable_one_count": 145,
        "disabled_count": 0,
        "neighbor_enabled_count": 6,
        "neighbor_enabled_default_27_count": 4,
        "neighbor_enabled_explicit_3_count": 2,
        "read_threshold_match_count": 112,
        "mapped_buffer_missing_count": 0,
        "pingpong_enabled_count": 5,
        "pingpong_non_read_a_count": 0,
        "pingpong_pair_mismatch_count": 0,
        "read_buffer_ignored_dst_port_count": 128,
        "buffer5_sa_source_count": 5,
        "buffer5_ga_source_count": 60,
    }
    actual = {
        "buffer_instance_count": buffer_instance_count,
        "implicit_enable_count": implicit_enable_count,
        "explicit_enable_one_count": explicit_enable_one_count,
        "disabled_count": disabled_count,
        "neighbor_enabled_count": neighbor_enabled_count,
        "neighbor_enabled_default_27_count": (
            neighbor_enabled_default_27_count
        ),
        "neighbor_enabled_explicit_3_count": (
            neighbor_enabled_explicit_3_count
        ),
        "read_threshold_match_count": read_threshold_match_count,
        "mapped_buffer_missing_count": mapped_buffer_missing_count,
        "pingpong_enabled_count": pingpong_enabled_count,
        "pingpong_non_read_a_count": pingpong_non_read_a_count,
        "pingpong_pair_mismatch_count": pingpong_pair_mismatch_count,
        "read_buffer_ignored_dst_port_count": (
            read_buffer_ignored_dst_port_count
        ),
        "buffer5_sa_source_count": buffer5_sa_source_count,
        "buffer5_ga_source_count": buffer5_ga_source_count,
    }
    if actual != expected:
        raise StageOperatorSemanticsAuditError(
            "authorized buffer inventory differs"
        )
    return {
        "authorized_config_count": 65,
        **actual,
        "buffer_name_counts": dict(sorted(buffer_names.items())),
        "mode_counts": dict(sorted(modes.items())),
        "logical_lifetime_counts": dict(sorted(lifetimes.items())),
        "mask_pattern_counts": dict(sorted(masks.items())),
        "spatial_size_counts": dict(sorted(spatial_sizes.items())),
        "pingpong_threshold_counts": dict(
            sorted(pingpong_thresholds.items())
        ),
        "sample_boundary": (
            "all enabled ping-pong samples are READ_STREAM0/target A and "
            "configure identical buffer0/buffer1 pairs; neighbor-enabled "
            "samples cover only six buffer instances"
        ),
    }


def _authorized_padding_tail_corpus(root: Path) -> dict[str, Any]:
    authority = _load_object(root / AUTHORITY_PATH)
    records = authority.get("records")
    authorized = [
        item
        for item in records if isinstance(item, Mapping)
        and item.get("configuration_correctness")
        == "user_authorized_correct_reference"
    ] if isinstance(records, list) else []
    if len(authorized) != 65:
        raise StageOperatorSemanticsAuditError(
            "authorized padding/tail corpus count differs"
        )

    read_stream_count = 0
    write_stream_count = 0
    padding_enabled_stream_count = 0
    padding_enabled_dimension_count = 0
    enabled_padding_null_value_count = 0
    tailing_enabled_stream_count = 0
    legacy_write_padding_field_count = 0
    padding_examples: list[dict[str, Any]] = []

    for record in sorted(authorized, key=lambda item: str(item.get("path"))):
        relative = record.get("path")
        if not isinstance(relative, str):
            raise StageOperatorSemanticsAuditError(
                "authorized padding/tail path is malformed"
            )
        path = root / relative
        if (
            not path.is_file()
            or sha256_file(path) != record.get("sha256")
            or path.stat().st_size != record.get("size_bytes")
        ):
            raise StageOperatorSemanticsAuditError(
                f"authorized config identity differs: {relative}"
            )
        config = _load_object(path)
        raw_streams = config.get("stream_engine")
        streams = raw_streams if isinstance(raw_streams, Mapping) else {}
        for stream_name, stream in sorted(streams.items()):
            if not isinstance(stream, Mapping):
                continue
            mode = stream.get("mode")
            if mode == "read":
                read_stream_count += 1
                enabled = stream.get("padding_enable")
                enabled_count = (
                    sum(int(item) for item in enabled)
                    if isinstance(enabled, list) and len(enabled) == 3
                    else 0
                )
                if enabled_count:
                    padding_enabled_stream_count += 1
                    padding_enabled_dimension_count += enabled_count
                    if stream.get("padding_reg_value") is None:
                        enabled_padding_null_value_count += 1
                    padding_examples.append(
                        {
                            "path": relative,
                            "stream": stream_name,
                            "target": stream.get("target"),
                            "padding_enable": list(enabled),
                            "idx_padding_range": copy.deepcopy(
                                stream.get("idx_padding_range")
                            ),
                            "padding_reg_value": stream.get(
                                "padding_reg_value"
                            ),
                        }
                    )
            elif mode == "write":
                write_stream_count += 1
                if any(
                    field in stream
                    for field in (
                        "padding_enable",
                        "padding_reg_value",
                        "idx_padding_range",
                        "buf_full_last_index",
                    )
                ):
                    legacy_write_padding_field_count += 1
            enabled_tail = stream.get("tailing_enable")
            if (
                isinstance(enabled_tail, list)
                and any(enabled_tail)
            ):
                tailing_enabled_stream_count += 1

    if (
        read_stream_count != 112
        or write_stream_count != 65
        or padding_enabled_stream_count != 3
        or padding_enabled_dimension_count != 5
        or enabled_padding_null_value_count != 3
        or tailing_enabled_stream_count != 0
        or legacy_write_padding_field_count != 1
    ):
        raise StageOperatorSemanticsAuditError(
            "authorized padding/tail inventory differs"
        )
    return {
        "authorized_config_count": 65,
        "read_stream_count": read_stream_count,
        "write_stream_count": write_stream_count,
        "padding_enabled_stream_count": padding_enabled_stream_count,
        "padding_enabled_dimension_count": padding_enabled_dimension_count,
        "enabled_padding_null_value_count": (
            enabled_padding_null_value_count
        ),
        "tailing_enabled_stream_count": tailing_enabled_stream_count,
        "legacy_write_padding_field_count": (
            legacy_write_padding_field_count
        ),
        "padding_examples": padding_examples,
        "sample_boundary": (
            "padding has three authorized reference streams; tailing has no "
            "authorized enabled instance and is RTL-only in this corpus"
        ),
    }


def _authorized_mse_corpus(root: Path) -> dict[str, Any]:
    authority = _load_object(root / AUTHORITY_PATH)
    records = authority.get("records")
    if not isinstance(records, list):
        raise StageOperatorSemanticsAuditError(
            "operator-config authority records are missing"
        )
    authorized = [
        item
        for item in records
        if isinstance(item, Mapping)
        and item.get("configuration_correctness")
        == "user_authorized_correct_reference"
    ]
    if len(authorized) != 65:
        raise StageOperatorSemanticsAuditError(
            f"authorized operator-config baseline count differs: {len(authorized)}"
        )

    stream_modes: Counter[str] = Counter()
    mem_patterns: Counter[str] = Counter()
    buf_patterns: Counter[str] = Counter()
    total_sizes: Counter[int] = Counter()
    remap_kinds: Counter[str] = Counter()
    ignored_thresholds: Counter[str] = Counter()
    stream_count = 0
    legacy_zero_null_alias_count = 0
    constant_mode_count = 0
    violations: list[dict[str, Any]] = []

    def label(value: Any) -> str:
        return "null" if value is None else str(value)

    for record in sorted(authorized, key=lambda item: str(item.get("path"))):
        relative = record.get("path")
        if not isinstance(relative, str):
            raise StageOperatorSemanticsAuditError(
                "authorized config path is not a string"
            )
        path = root / relative
        if (
            not path.is_file()
            or sha256_file(path) != record.get("sha256")
            or path.stat().st_size != record.get("size_bytes")
        ):
            raise StageOperatorSemanticsAuditError(
                f"authorized config identity differs: {relative}"
            )
        config = _load_object(path)
        raw_streams = config.get("stream_engine")
        streams = raw_streams if isinstance(raw_streams, Mapping) else {}
        for stream_name, raw_stream in sorted(streams.items()):
            if not isinstance(raw_stream, Mapping):
                continue
            stream_count += 1
            stream_modes[str(raw_stream.get("mode"))] += 1
            mem_modes = raw_stream.get("mem_idx_mode")
            buf_modes = raw_stream.get("buf_idx_mode")
            indexes = raw_stream.get("idx")
            constants = raw_stream.get("mem_idx_constant")
            mem_keep = raw_stream.get("mem_idx_keep_last_index")
            buf_keep = raw_stream.get("buf_idx_keep_last_index")
            sizes = raw_stream.get("idx_size")
            remap = raw_stream.get("address_remapping")

            if not isinstance(mem_modes, list) or len(mem_modes) != 3:
                violations.append(
                    {
                        "path": relative,
                        "stream": stream_name,
                        "reason": "mem_mode_arity",
                    }
                )
                continue
            if not isinstance(buf_modes, list) or len(buf_modes) != 2:
                violations.append(
                    {
                        "path": relative,
                        "stream": stream_name,
                        "reason": "buf_mode_arity",
                    }
                )
                continue
            mem_patterns[",".join(label(item) for item in mem_modes)] += 1
            buf_patterns[",".join(label(item) for item in buf_modes)] += 1

            if (
                not isinstance(indexes, list)
                or len(indexes) != 3
                or not isinstance(constants, list)
                or len(constants) != 3
                or not isinstance(mem_keep, list)
                or len(mem_keep) != 3
                or not isinstance(buf_keep, list)
                or len(buf_keep) != 2
            ):
                violations.append(
                    {
                        "path": relative,
                        "stream": stream_name,
                        "reason": "companion_field_arity",
                    }
                )
                continue

            for index, mode in enumerate(mem_modes):
                normalized_mode = None if mode == 0 else mode
                if mode == 0:
                    legacy_zero_null_alias_count += 1
                if normalized_mode == "constant":
                    constant_mode_count += 1
                if normalized_mode in {"buffer", "keep"}:
                    if indexes[index] is None:
                        violations.append(
                            {
                                "path": relative,
                                "stream": stream_name,
                                "dimension": index,
                                "reason": "active_mode_without_source",
                            }
                        )
                elif indexes[index] is not None:
                    violations.append(
                        {
                            "path": relative,
                            "stream": stream_name,
                            "dimension": index,
                            "reason": "inactive_mode_with_source",
                        }
                    )
                if normalized_mode == "constant":
                    if constants[index] is None:
                        violations.append(
                            {
                                "path": relative,
                                "stream": stream_name,
                                "dimension": index,
                                "reason": "constant_mode_without_constant",
                            }
                        )
                elif constants[index] is not None:
                    violations.append(
                        {
                            "path": relative,
                            "stream": stream_name,
                            "dimension": index,
                            "reason": "nonconstant_mode_with_constant",
                        }
                    )
                if (
                    normalized_mode != "keep"
                    and mem_keep[index] is not None
                ):
                    ignored_thresholds[
                        f"mem_{label(normalized_mode)}"
                    ] += 1

            if buf_modes != ["keep", "buffer"]:
                violations.append(
                    {
                        "path": relative,
                        "stream": stream_name,
                        "reason": "unexpected_row_col_mode_pair",
                        "modes": list(buf_modes),
                    }
                )
            if buf_keep[1] is not None:
                ignored_thresholds["buf_buffer"] += 1

            if not isinstance(sizes, list) or len(sizes) != 3:
                violations.append(
                    {
                        "path": relative,
                        "stream": stream_name,
                        "reason": "idx_size_arity",
                    }
                )
            else:
                dimensions = [
                    1 if item is None else int(item) + 1
                    for item in sizes
                ]
                total_sizes[math.prod(dimensions)] += 1

            if remap is None:
                remap_kinds["null_default_identity"] += 1
            elif remap == list(range(26)):
                remap_kinds["explicit_identity"] += 1
            elif (
                isinstance(remap, list)
                and len(remap) == 26
                and sorted(remap) == list(range(26))
            ):
                remap_kinds["explicit_permutation"] += 1
            else:
                violations.append(
                    {
                        "path": relative,
                        "stream": stream_name,
                        "reason": "invalid_remap",
                    }
                )

    if violations:
        first = violations[0]
        raise StageOperatorSemanticsAuditError(
            "authorized MSE corpus violates the RTL-derived field relation: "
            f"{first}"
        )
    if (
        stream_count != 177
        or stream_modes != Counter({"read": 112, "write": 65})
        or legacy_zero_null_alias_count != 4
        or constant_mode_count != 0
    ):
        raise StageOperatorSemanticsAuditError(
            "authorized MSE corpus inventory differs"
        )

    return {
        "authorized_config_count": len(authorized),
        "stream_count": stream_count,
        "stream_mode_counts": dict(sorted(stream_modes.items())),
        "mem_mode_patterns": dict(sorted(mem_patterns.items())),
        "buf_mode_patterns": dict(sorted(buf_patterns.items())),
        "derived_total_size_counts": {
            str(key): value for key, value in sorted(total_sizes.items())
        },
        "address_remapping_counts": dict(sorted(remap_kinds.items())),
        "legacy_integer_zero_null_alias_count": legacy_zero_null_alias_count,
        "constant_mode_count": constant_mode_count,
        "ignored_nonnull_keep_threshold_counts": dict(
            sorted(ignored_thresholds.items())
        ),
        "json_to_rtl_dimension_order": {
            "json[0]": "RTL port2; innermost transaction dimension",
            "json[1]": "RTL port1; middle transaction dimension",
            "json[2]": "RTL port0; outermost transaction dimension",
            "buf_idx_mode": "JSON [row,col] maps to RTL [port1,port0]",
        },
        "corpus_relation_violation_count": 0,
    }


def _authorized_lc_pe_corpus(root: Path) -> dict[str, Any]:
    authority = _load_object(root / AUTHORITY_PATH)
    records = authority.get("records")
    if not isinstance(records, list):
        raise StageOperatorSemanticsAuditError(
            "operator-config authority records are missing"
        )
    authorized = [
        item
        for item in records
        if isinstance(item, Mapping)
        and item.get("configuration_correctness")
        == "user_authorized_correct_reference"
    ]
    if len(authorized) != 65:
        raise StageOperatorSemanticsAuditError(
            f"authorized operator-config baseline count differs: {len(authorized)}"
        )

    source_roots: Counter[str] = Counter()
    opcode_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    pattern_counts: Counter[tuple[str, tuple[Any, ...]]] = Counter()
    constant_counts: Counter[int] = Counter()
    keep_threshold_counts: Counter[int] = Counter()
    config_with_lc_pe_count = 0
    pe_instance_count = 0
    examples: dict[str, dict[str, Any]] = {}
    violations: list[dict[str, Any]] = []

    for record in sorted(authorized, key=lambda item: str(item.get("path"))):
        relative = record.get("path")
        if not isinstance(relative, str):
            raise StageOperatorSemanticsAuditError(
                "authorized config path is not a string"
            )
        path = root / relative
        if (
            not path.is_file()
            or sha256_file(path) != record.get("sha256")
            or path.stat().st_size != record.get("size_bytes")
        ):
            raise StageOperatorSemanticsAuditError(
                f"authorized config identity differs: {relative}"
            )
        source_roots[str(record.get("source_root"))] += 1
        config = _load_object(path)
        raw_pes = config.get("lc_pe_configs")
        pes = raw_pes if isinstance(raw_pes, Mapping) else {}
        if pes:
            config_with_lc_pe_count += 1

        for name, raw_pe in sorted(pes.items()):
            if not isinstance(raw_pe, Mapping) or not raw_pe:
                continue
            pe_instance_count += 1
            opcode = raw_pe.get("alu_opcode")
            if not isinstance(opcode, str):
                violations.append(
                    {
                        "path": relative,
                        "pe": name,
                        "reason": "opcode_not_symbolic",
                    }
                )
                continue
            ports = [
                raw_pe.get(f"inport{index}")
                if isinstance(raw_pe.get(f"inport{index}"), Mapping)
                else {}
                for index in range(3)
            ]
            modes = tuple(port.get("mode") for port in ports)
            opcode_counts[opcode] += 1
            pattern_counts[(opcode, modes)] += 1
            for mode in modes:
                mode_counts["null" if mode is None else str(mode)] += 1

            used = {0, 1, 2} if opcode == "mac" else {0, 1}
            if opcode not in {"add", "mul", "mac"}:
                violations.append(
                    {
                        "path": relative,
                        "pe": name,
                        "reason": "unsupported_opcode",
                        "opcode": opcode,
                    }
                )
            if sum(mode == "buffer" for mode in modes) != 1:
                violations.append(
                    {
                        "path": relative,
                        "pe": name,
                        "reason": "buffer_carrier_count",
                        "modes": list(modes),
                    }
                )
            for index, (port, mode) in enumerate(zip(ports, modes)):
                if (index in used and mode is None) or (
                    index not in used and mode is not None
                ):
                    violations.append(
                        {
                            "path": relative,
                            "pe": name,
                            "reason": "opcode_operand_arity",
                            "opcode": opcode,
                            "port": index,
                            "mode": mode,
                        }
                    )
                threshold = port.get("keep_last_index")
                if mode == "keep":
                    if not isinstance(threshold, int):
                        violations.append(
                            {
                                "path": relative,
                                "pe": name,
                                "reason": "keep_threshold_missing",
                                "port": index,
                            }
                        )
                    else:
                        keep_threshold_counts[threshold] += 1
                elif threshold is not None:
                    violations.append(
                        {
                            "path": relative,
                            "pe": name,
                            "reason": "threshold_on_nonkeep",
                            "port": index,
                        }
                    )
                if mode == "constant":
                    constant = port.get("constant")
                    if (
                        isinstance(constant, bool)
                        or not isinstance(constant, int)
                        or not -(1 << 15) <= constant < (1 << 15)
                    ):
                        violations.append(
                            {
                                "path": relative,
                                "pe": name,
                                "reason": "constant_not_signed_int16",
                                "port": index,
                                "constant": constant,
                            }
                        )
                    else:
                        constant_counts[constant] += 1
                    if port.get("src_id") is not None:
                        violations.append(
                            {
                                "path": relative,
                                "pe": name,
                                "reason": "constant_has_source",
                                "port": index,
                            }
                        )
            examples.setdefault(
                opcode,
                {
                    "path": relative,
                    "pe": name,
                    "modes_inport0_to_2": list(modes),
                },
            )

    if violations:
        raise StageOperatorSemanticsAuditError(
            "authorized LC-PE corpus violates the RTL-derived strict subset: "
            f"{violations[0]}"
        )

    return {
        "authorized_config_count": len(authorized),
        "source_root_counts": dict(sorted(source_roots.items())),
        "config_with_lc_pe_count": config_with_lc_pe_count,
        "lc_pe_instance_count": pe_instance_count,
        "opcode_counts": dict(sorted(opcode_counts.items())),
        "mode_counts": dict(sorted(mode_counts.items())),
        "observed_patterns": [
            {
                "opcode": opcode,
                "modes_inport0_to_2": list(modes),
                "instance_count": count,
            }
            for (opcode, modes), count in sorted(
                pattern_counts.items(),
                key=lambda item: (
                    item[0][0],
                    tuple("" if value is None else str(value) for value in item[0][1]),
                ),
            )
        ],
        "constant_value_counts": {
            str(value): count
            for value, count in sorted(constant_counts.items())
        },
        "keep_threshold_counts": {
            str(value): count
            for value, count in sorted(keep_threshold_counts.items())
        },
        "examples": dict(sorted(examples.items())),
        "strict_subset_violation_count": 0,
        "evidence_boundary": (
            "the authorized corpus proves the observed mul/mac combinations "
            "are used; add and unobserved mode/topology combinations rely on "
            "RTL equations only and are not approved stage migrations"
        ),
    }


def _loop_domain(
    config: Mapping[str, Any], source: str
) -> tuple[set[int] | None, dict[str, Any]]:
    if not source.startswith("DRAM_LC."):
        return None, {
            "source": source,
            "reason": "not_a_dram_lc",
        }
    name = source.split(".", 1)[1]
    loops = config.get("dram_loop_configs")
    loop = loops.get(name) if isinstance(loops, Mapping) else None
    if not isinstance(loop, Mapping):
        return None, {
            "source": source,
            "reason": "missing_loop",
        }
    start, end, stride = (
        loop.get("start"),
        loop.get("end"),
        loop.get("stride"),
    )
    if (
        isinstance(start, bool)
        or not isinstance(start, int)
        or isinstance(end, bool)
        or not isinstance(end, int)
        or isinstance(stride, bool)
        or not isinstance(stride, int)
        or stride <= 0
        or start >= end
    ):
        return None, {
            "source": source,
            "reason": "unsupported_or_nonprogress_loop",
        }
    values = set(range(start, end, stride))
    return values, {
        "source": source,
        "kind": "local_lc_counter_domain",
        "src_id_role": "trigger_tag_dependency_only",
        "start": start,
        "end": end,
        "stride": stride,
        "value_count": len(values),
    }


def _index_domain(
    config: Mapping[str, Any], source: str
) -> tuple[set[int] | None, dict[str, Any]]:
    direct, direct_evidence = _loop_domain(config, source)
    if direct is not None:
        return direct, direct_evidence
    if not source.startswith("LC_PE."):
        return None, {
            "source": source,
            "reason": "unsupported_index_source",
        }
    name = source.split(".", 1)[1]
    pes = config.get("lc_pe_configs")
    pe = pes.get(name) if isinstance(pes, Mapping) else None
    if not isinstance(pe, Mapping):
        return None, {
            "source": source,
            "reason": "missing_lc_pe",
        }
    ports = [
        pe.get(f"inport{index}")
        for index in range(3)
    ]
    buffered = [
        (index, port)
        for index, port in enumerate(ports)
        if isinstance(port, Mapping) and port.get("mode") == "buffer"
    ]
    constants = [
        int(port.get("constant"))
        for port in ports
        if isinstance(port, Mapping)
        and port.get("mode") == "constant"
        and isinstance(port.get("constant"), int)
        and not isinstance(port.get("constant"), bool)
    ]
    if len(buffered) != 1:
        return None, {
            "source": source,
            "reason": "lc_pe_buffer_carrier_is_not_unique",
        }
    carrier = buffered[0][1].get("src_id")
    if not isinstance(carrier, str):
        return None, {
            "source": source,
            "reason": "lc_pe_buffer_source_is_not_named",
        }
    values, carrier_evidence = _loop_domain(config, carrier)
    if values is None:
        return None, {
            "source": source,
            "reason": "lc_pe_buffer_domain_unresolved",
            "carrier": carrier_evidence,
        }
    opcode = pe.get("alu_opcode")
    if opcode == "mul" and constants == [1]:
        return values, {
            "source": source,
            "kind": "lc_pe_identity_mul_domain",
            "opcode": opcode,
            "constant_operands": constants,
            "carrier": carrier_evidence,
            "value_count": len(values),
        }
    if opcode == "add" and constants == [0]:
        return values, {
            "source": source,
            "kind": "lc_pe_identity_add_domain",
            "opcode": opcode,
            "constant_operands": constants,
            "carrier": carrier_evidence,
            "value_count": len(values),
        }
    return None, {
        "source": source,
        "reason": "lc_pe_arithmetic_domain_not_proven",
        "opcode": opcode,
        "constant_operands": constants,
        "carrier": carrier_evidence,
    }


def analyze_gap_d_index_coverage(
    config: Mapping[str, Any],
    request: Mapping[str, Any],
) -> dict[str, Any]:
    geometry = request.get("logical_geometry")
    identity = request.get("identity")
    if (
        request.get("request_id") != GAP_REQUEST_ID
        or not isinstance(identity, Mapping)
        or identity.get("hw_op_type") != "GlobalAverageSumInt32"
        or not isinstance(geometry, Mapping)
    ):
        raise StageOperatorSemanticsAuditError(
            "GAP D-index check requires the exact typed GAP request"
        )
    output_shapes = geometry.get("output_shapes")
    output_dtypes = geometry.get("output_dtypes")
    if (
        not isinstance(output_shapes, list)
        or len(output_shapes) != 1
        or not isinstance(output_shapes[0], list)
        or len(output_shapes[0]) < 2
        or output_dtypes != ["int32"]
    ):
        raise StageOperatorSemanticsAuditError(
            "GAP output geometry is malformed"
        )
    output_shape = output_shapes[0]
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in output_shape
    ):
        raise StageOperatorSemanticsAuditError(
            "GAP output shape must be positive integers"
        )
    output_bytes_per_sample = math.prod(output_shape[1:]) * 4

    streams = config.get("stream_engine")
    writes = [
        (name, stream)
        for name, stream in (
            streams.items() if isinstance(streams, Mapping) else []
        )
        if isinstance(stream, Mapping)
        and stream.get("target") == "D"
        and stream.get("mode") == "write"
    ]
    if len(writes) != 1:
        raise StageOperatorSemanticsAuditError(
            "GAP config requires exactly one D write stream"
        )
    stream_name, stream = writes[0]
    sizes = stream.get("idx_size")
    indices = stream.get("idx")
    strides = stream.get("dim_stride")
    if not (
        isinstance(sizes, list)
        and isinstance(indices, list)
        and isinstance(strides, list)
        and len(sizes) == len(indices) == len(strides) == 3
    ):
        raise StageOperatorSemanticsAuditError(
            "GAP D stream index vectors are malformed"
        )
    active_sizes = [
        value
        for value in sizes
        if isinstance(value, int) and not isinstance(value, bool)
    ]
    if not active_sizes or any(value < 0 for value in active_sizes):
        raise StageOperatorSemanticsAuditError(
            "GAP D stream transaction size is not derivable"
        )
    transaction_bytes = math.prod(value + 1 for value in active_sizes)
    required_bases = math.ceil(output_bytes_per_sample / transaction_bytes)

    dimension_domains: list[set[int]] = []
    dimension_evidence: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for dimension, (source, stride) in enumerate(zip(indices, strides)):
        if source is None:
            continue
        if (
            not isinstance(source, str)
            or isinstance(stride, bool)
            or not isinstance(stride, int)
        ):
            unresolved.append(
                {
                    "dimension": dimension,
                    "source": source,
                    "stride_bytes": stride,
                    "reason": "malformed_active_dimension",
                }
            )
            continue
        values, evidence = _index_domain(config, source)
        record = {
            "dimension": dimension,
            "source": source,
            "stride_bytes": stride,
            "domain": evidence,
        }
        dimension_evidence.append(record)
        if values is None:
            unresolved.append(record)
            continue
        dimension_domains.append({value * stride for value in values})

    distinct_biases: set[int] | None
    if unresolved or not dimension_domains:
        distinct_biases = None
    else:
        distinct_biases = {
            sum(parts)
            for parts in itertools.product(*dimension_domains)
        }
    derived_count = (
        None if distinct_biases is None else len(distinct_biases)
    )
    classification = (
        "TEST_REQUIRED"
        if derived_count is None
        else (
            "CONTRADICTED"
            if derived_count < required_bases
            else "RTL_PROVEN"
        )
    )
    return {
        "request_id": GAP_REQUEST_ID,
        "write_stream": stream_name,
        "output_shape": output_shape,
        "output_dtype": "int32",
        "output_bytes_per_sample": output_bytes_per_sample,
        "transaction_bytes": transaction_bytes,
        "required_distinct_transaction_bases": required_bases,
        "derived_distinct_transaction_bases": derived_count,
        "first_derived_biases_bytes": (
            []
            if distinct_biases is None
            else sorted(distinct_biases)[:16]
        ),
        "dimensions": dimension_evidence,
        "unresolved_dimensions": unresolved,
        "classification": classification,
        "necessary_condition_passed": (
            derived_count is not None and derived_count >= required_bases
        ),
        "scope": (
            "necessary D-address coverage only; passing does not prove "
            "ordering, tag/completion, payload, mapping, E4 or E5"
        ),
    }


def require_gap_d_index_coverage(
    config: Mapping[str, Any],
    request: Mapping[str, Any],
) -> dict[str, Any]:
    result = analyze_gap_d_index_coverage(config, request)
    if not result["necessary_condition_passed"]:
        raise StageOperatorSemanticsAuditError(
            "GAP D index carrier cannot cover the typed output: "
            f"derived={result['derived_distinct_transaction_bases']} "
            f"required={result['required_distinct_transaction_bases']}"
        )
    return result


def _validate_static_sources(root: Path) -> None:
    _require_snippets(
        root / "ndp-sim/bitstream/config/loop.py",
        (
            '("src_id", 4, lambda self, x: Connect(x, self.id) if x else None)',
            '("outmost_loop", 1)',
            '("start", 17)',
            '("stride", 17)',
            '("end", 17)',
            '("last_index", 4)',
        ),
    )
    _require_snippets(
        root / "ndp-sim/bitstream/index.py",
        (
            "if src_type == \"LC\" and dst_type == \"LC\":",
            "return 5  # left 2",
            "return 8  # right 2",
        ),
    )
    _require_snippets(
        root / "NDP_copy01/rtl/includes/NDP_Parameters.svh",
        (
            "`define IGA_LC_ROW_NUM                     2",
            "`define IGA_LC_COL_NUM                     10",
            "`define IGA_LC_SRC_LC_NUM                  9",
            "`define IGA_LC_INITIAL_VALUE_WIDTH         `IGA_LC_PORT_DATA_WIDTH + 1",
            "`define IGA_LC_STRIDE_VALUE_WIDTH          `IGA_LC_PORT_DATA_WIDTH + 1",
            "`define IGA_LC_END_VALUE_WIDTH             `IGA_LC_PORT_DATA_WIDTH + 1",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC/"
        "IGA_LC_Config.sv",
        (
            "assign iga_lc_src_id        = iga_lc_configure_reg",
            "assign iga_lc_outmost_loop  = iga_lc_configure_reg",
            "assign iga_lc_initial_value = iga_lc_configure_reg",
            "assign iga_lc_stride_value  = iga_lc_configure_reg",
            "assign iga_lc_end_value     = iga_lc_configure_reg",
            "assign iga_lc_index         = iga_lc_configure_reg",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC/"
        "IGA_LC_Connect.sv",
        (
            "assign iga_lc_sel_inport = iga_lc_inport[iga_lc_src_id];",
            "assign iga_lc_inport_tag = iga_lc_sel_inport",
            "(iga_lc_src_id == IGA_LC_SRC_IDX)",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC/"
        "IGA_LC_Inbuffer.sv",
        (
            "iga_lc_outmost_loop ? slice_start_run",
            "iga_lc_outmost_loop ? 1'b0",
            "iga_lc_outmost_loop ? slice_start_run_delay",
            "iga_lc_outmost_loop ? {`PORT_LAST_INDEX{1'b0}}",
            "iga_lc_same_gotten_mask",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC/"
        "IGA_LC_Counter.sv",
        (
            "iga_lc_outbuf_cnt_value = iga_lc_initial_value;",
            "signed'(iga_lc_outbuf_cnt_rd_data) + signed'(iga_lc_stride_value)",
            "signed'(iga_lc_end_value) - signed'(iga_lc_stride_value)",
            "iga_lc_inbuffer_last_bit ? iga_lc_inbuffer_last_index : iga_lc_index",
        ),
    )
    _require_snippets(
        root / "ndp-sim/bitstream/config/loop.py",
        (
            '("_padding", 16)',
            '("opcode", 2, lambda x: LCPEConfig.opcode_map()[x] if x is not None else 0)',
            '("inport2_src", 4)',
            '("inport2_last_index", 4)',
            '("inport2_mode", 2, lambda x: LCPEConfig.inport_mode_map()[x] if x is not None else 0)',
            '("constant2", 16, lambda x: LCPEConfig._encode_constant(x))',
            '"add": 0',
            '"mul": 1',
            '"mac": 2',
            '"buffer": 1',
            '"keep": 2',
            '"constant": 3',
        ),
    )
    _require_snippets(
        root / "ndp-sim/bitstream/parse.py",
        (
            "MODULE_CFG_CHUNK_SIZES = [1, 1, 1, 2, 10, 8, 1, 1, 1, 1, 1, 4]",
            "chunks = [config[i:i + chunk_size] for i in range(0, len(config), chunk_size)]",
        ),
    )
    _require_snippets(
        root / "ndp-sim/bitstream/index.py",
        (
            "elif src_type == \"LC\" and dst_type == \"PE\":",
            "return 0 if src_row == 0 else 3",
            "return 2 if src_row == 0 else 5",
            "return 6  # left 2",
            "return 9  # right 2",
        ),
    )
    _require_snippets(
        root / "NDP_copy01/rtl/includes/NDP_Parameters.svh",
        (
            "`define IGA_PE_PORT_DATA_WIDTH             16",
            "`define IGA_PE_INPORT_NUM                  3",
            "`define IGA_PE_INPORT_NULL                 2'b00",
            "`define IGA_PE_INPORT_BUFFER_MODE          2'b01",
            "`define IGA_PE_INPORT_KEEP_MODE            2'b10",
            "`define IGA_PE_INPORT_CONSTANT_MODE        2'b11",
            "`define IGA_PE_CONSTANT_VALUE_WIDTH        16",
            "`define IGA_PE_ALU_OPCODE_WIDTH            2",
            "`define IGA_PE_CFG_PORT_WIDTH              48",
            "`define IGA_PE_CFG_CNT                     2",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
        "IGA_PE_Config.sv",
        (
            "iga_pe_configure_reg[`IGA_PE_CFG_REG_WIDTH-1:0] <= sem_wreg_cmd_data",
            "iga_pe_configure_reg <= iga_pe_configure_inport[`IGA_PE_CFG_REG_WIDTH-1:0];",
            "iga_pe_constant_valid[INPORT_ID]  = (iga_pe_configure_inport_valid && (|iga_pe_cfg_cnt) && (&iga_pe_inport_mode[INPORT_ID]))",
            "iga_pe_constant_value[INPORT_ID]",
            "iga_pe_alu_opcode,",
            "iga_pe_src_id[2],",
            "iga_pe_keep_last_index[0],",
            "iga_pe_inport_enable[0] = |iga_pe_inport_mode[0];",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
        "IGA_PE_Connect.sv",
        (
            "iga_pe_inport[iga_pe_src_id[IGA_PE_INPORT_IDX]]",
            "iga_pe_enable & iga_pe_inport_enable[IGA_PE_INPORT_IDX]",
            "iga_pe_connect2ob_bp_post = &iga_pe_outport_bp_post;",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
        "IGA_PE_Inbuffer.sv",
        (
            "iga_pe_inbuffer_data[IGA_PORT_IDX] <= {{(`IGA_PE_ALU_DATA_WIDTH-`IGA_PE_CONSTANT_VALUE_WIDTH){iga_pe_constant_value",
            "iga_pe_inport_mode[0] == `IGA_PE_INPORT_BUFFER_MODE ? iga_pe_inbuffer_last_index[0]",
            "(!(iga_pe_buffer_inport_last_index > iga_pe_keep_last_index[IGA_PORT_IDX]) && iga_pe_buffer_inport_last_bit)",
            "iga_pe_inbuffer_matched = iga_pe_enable & (&((~iga_pe_inport_enable) | iga_pe_inbuffer_valid_bit));",
            "iga_pe_inbuffer2alu_last_bit   = iga_pe_inbuffer_matched && iga_pe_buffer_inport_last_bit;",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
        "IGA_PE_ALU.sv",
        (
            "`IGA_PE_ALU_OPCODE_INT_ADD",
            "iga_pe_int_alu_inport1 = 12'd1;",
            "`IGA_PE_ALU_OPCODE_INT_MULT",
            "`IGA_PE_ALU_OPCODE_INT_MAC",
            "iga_pe_int_alu_inport2 = iga_pe_inbuffer2alu_data[2];",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
        "IGA_PE_INT_ALU.sv",
        (
            "DW02_mult #(",
            ".TC       ( 1'b1",
            "multi_result[`IGA_PE_ALU_DATA_WIDTH-1:0]",
            "assign iga_pe_int_alu_outport = cla_result;",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
        "IGA_PE_Outbuffer.sv",
        (
            "normal_mode_wr_tag        = {normal_mode_valid_bit, normal_mode_last_bit, normal_mode_last_index};",
            "iga_pe_outbuffer_same_bit <= 1'b1;",
            "iga_pe_outbuffer_port = {iga_pe_outbuffer_valid_bit,",
        ),
    )
    _require_snippets(
        root / "ndp-sim/bitstream/config/stream.py",
        (
            '("mem_idx_mode", 6,',
            '("mem_idx_keep_last_index", 12)',
            '("idx", 15)',
            '("mem_idx_constant", 24)',
            '("buf_idx_mode", 2,',
            '("buf_idx_keep_last_index", 8)',
            '("base_addr", 30,',
            '("idx_size", 24)',
            '("idx_size_log", 9)',
            '("total_size", 8)',
            '("dim_stride", 60)',
            '("address_remapping", 130,',
            "dim_size[i] = idx_size[i] + 1 if idx_size[i] is not None else 1",
            'self.values["idx_size_log"] = [int(log2(dim0)), int(log2(dim1)), 0]',
            "None: 0,",
            '"buffer": 1,',
            '"keep": 2,',
            '"constant": 3,',
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
        "Stream_Engine_Config.sv",
        (
            "mse_mem_idx_mode[RD_MSE_IDX]",
            "mse_mem_idx_src_id[RD_MSE_IDX]",
            "mse_mem_idx_constant[RD_MSE_IDX]",
            "mse_transaciton_layout_size[RD_MSE_IDX]",
            "mse_transaciton_layout_size_log[RD_MSE_IDX]",
            "mse_transaciton_total_size[RD_MSE_IDX]",
            "mse_transaciton_mult[RD_MSE_IDX]",
            "mse_map_matrix_b[RD_MSE_IDX]",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_AG_Idx_Queue.sv",
        (
            "assign mse_mem_idx_buffer_mode[INPORT_IDX] = !mse_mem_idx_mode[INPORT_IDX][1] & mse_mem_idx_mode[INPORT_IDX][0];",
            "assign mse_mem_idx_keep_mode[INPORT_IDX]   = mse_mem_idx_mode[INPORT_IDX][1] & !mse_mem_idx_mode[INPORT_IDX][0];",
            "assign mse_mem_idx_cons_mode[INPORT_IDX]   = &mse_mem_idx_mode[INPORT_IDX];",
            "mse_mem_idx_constant[INPORT_IDX][`MEM_INPORT_CONSTANT_WIDTH-1]",
            "assign mem_all_idx_matched = &mem_idx_valid_bit_masked;",
            "mem_buffer_idx_last_index > mse_mem_idx_keep_last_index[INPORT_IDX]",
            "localparam MEM_AG_IDX_QUEUE_DEPTH = 8;",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Buffer_AG_Idx_Queue.sv",
        (
            "assign mse_buf_idx_keep_mode = mse_buf_idx_mode;",
            "} = mse_buf_queue_col_tag;",
            "} = mse_buf_queue_row_tag;",
            "assign buf_all_idx_matched = &buf_idx_valid_bit_masked;",
            "buf_buffer_idx_last_index > mse_buf_idx_keep_last_index[INPORT_IDX]",
            "localparam BUF_AG_IDX_QUEUE_DEPTH = 16;",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_RD_Stream_Engine/RD_Memory_AG.sv",
        (
            "assign transaction_dim0_addr = mse_mem_ag_idx[0] * mse_transaciton_mult[0];",
            "assign transaction_addr_wire   = transaction_addr_bias;",
            "assign transaction_addr_offset = transaction_addr_wire[`DDR_ADDR_OFFSET_WIDTH-1:0];",
            "assign first_col_remain_size   = {1'b0, ~transaction_addr_offset} + 1;",
            "assign transfer_final_size = transfer_try_size_overflow ? cur_transaction_size_left",
            "assign transfer_valid_mask_temp = ((16'h0001 << transfer_final_size) - 1) << transfer_start_position;",
            "assign transfer_addr_nooff = transfer_addr[`GLOBAL_DDR_ADDR_WIDTH-1 : `DDR_ADDR_OFFSET_WIDTH];",
            "request_addr_mapped[ADDR_BIT_INDEX] = transfer_addr_nooff[mse_map_matrix_b[ADDR_BIT_INDEX]];",
            "request_addr_mapped + mse_stream_base_addr[`GLOBAL_DDR_ADDR_WIDTH-1 :`DDR_ADDR_OFFSET_WIDTH]",
            "assign mem_ag_ob_chl_clr[MSE_REQ_CHL_IDX]",
            "mem_ag_ob_chl_vld_d[MSE_REQ_CHL_IDX] <= mem_ag_ob_chl_vld[MSE_REQ_CHL_IDX];",
            "mem_ag_ob_chl_vld_d[MSE_REQ_CHL_IDX] || mem_ag_ob_chl_vld[MSE_REQ_CHL_IDX]",
            "assign mse2mem_request_valid = mem_ag_ob_vld;",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_WR_Stream_Engine/WR_Memory_AG.sv",
        (
            "assign transaction_dim0_addr = mse_mem_ag_idx[0] * mse_transaciton_mult[0];",
            "assign transaction_addr_wire   = transaction_addr_bias;",
            "assign transfer_valid_mask_temp = ((16'h0001 << transfer_final_size) - 1) << transfer_start_position;",
            "assign transfer_mask_flag       = transfer_valid_mask_flag || wr_data_chl_req_branch_mask_flag;",
            "assign mem_ag_ob_bp_pre_barrier = mem_ag_ob_chl_rw[mem_ag_ob_sel];",
            "else if (transfer_mask_flag) begin",
            "mem_ag_ob_chl_rw[MSE_REQ_CHL_IDX] <= 0;",
            "mem_ag_ob_chl_vld_d[MSE_REQ_CHL_IDX] <= mem_ag_ob_chl_vld[MSE_REQ_CHL_IDX];",
            "mem_ag_ob_chl_vld_d[MSE_REQ_CHL_IDX] || mem_ag_ob_chl_vld[MSE_REQ_CHL_IDX]",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_RD_Stream_Engine/RD_Data_Channel.sv",
        (
            "return_data_tsf_bias_addr[return_data_idx] = rd_data_chl_req_tsf_bias_addr + return_data_idx;",
            "return_data_tsf_bias_addr[return_data_idx] >> mse_transaciton_layout_size_log[1]",
            "return_data_tsa_idx0[return_data_idx] = rd_data_chl_req_tsa_idx[0] + return_data_tsf_idx0[return_data_idx];",
            "return_data_tsa_idx0[return_data_idx] < {4'b0, mse_padding_low_bound[0]}",
            "return_data_tsa_idx0[return_data_idx] > {4'b0, mse_padding_up_bound[0]}",
            "return_data_padding_mask << rd_data_chl_req_position;",
            "return_data_branch_mask << rd_data_chl_req_position;",
            "rd_chl_queue_rd_padding_mask[PADDING_INDEX] ? mse_padding_reg_value",
            "rd_chl_queue_rd_branch_mask[PADDING_INDEX] ? {`DDR_DATA_MIN_WIDTH{1'b0}}",
            "rd_data_chl_data_reorder[rd_chl_queue_rd_valid_rank[i]-1] = rd_data_chl_data[i];",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_WR_Stream_Engine/WR_Data_Channel.sv",
        (
            "return_data_tsf_bias_addr[return_data_idx] = wr_data_chl_req_tsf_bias_addr + return_data_idx;",
            "return_data_tsa_idx0[return_data_idx] < {4'b0, mse_branch_low_bound[0]}",
            "return_data_tsa_idx0[return_data_idx] > {4'b0, mse_branch_up_bound[0]}",
            "return_data_branch_mask << wr_data_chl_req_position;",
            "wr_chl_queue_rd_mask      = (wr_chl_queue_rd_valid_mask & (~wr_chl_queue_rd_branch_mask));",
            "wr_data_chl_data_reorder[i] = wr_data_chl_prepared_data[wr_chl_queue_rd_valid_rank[i]-1];",
            "wr_chl_queue_rd_mask[WR_DATA_INDEX] ?",
            "wr_chl_mask_buf_data[wr_chl_ob_sel]",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Parallel_Prefix_Sum.sv",
        (
            "prefix_sum_stage0[idx] = mask[idx] + mask[idx-1];",
            "assign rank = prefix_sum_stage3;",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
        "Stream_Engine_Connect.sv",
        (
            "assign mem2mse_request_ready = hub2mse_req_ready;",
            "assign mse2hub_req_valid     = mse2mem_request_valid;",
            "assign se2buf_mem_wreq_buf_sel[MSE_IDX]  = {mse_rreq_pingpong_sel[MSE_IDX], !mse_rreq_pingpong_sel[MSE_IDX]}",
            "assign se2buf_mem_rreq_buf_sel[MSE_IDX]  = {mse_wreq_pingpong_sel[MSE_IDX], !mse_wreq_pingpong_sel[MSE_IDX]}",
            "buf2se_mem_rvalid[MSE_IDX][mse_wdata_pingpong_sel[MSE_IDX]]",
        ),
    )
    _require_snippets(
        root / "ndp-sim/bitstream/config/buffer.py",
        (
            '("dst_port", 1)',
            '("buf_full_last_index", 4)',
            '("buffer_nbr_cnt", 5,lambda x: x if x is not None else 27)',
            '("buffer_life_time", 4, lambda x : x-1)',
            '("mode", 1)',
            '("mask", 8,',
            '("buf_end_row_addr", 2)',
            "if not self.enable:",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_RD_Stream_Engine/WR_Buffer_AG.sv",
        (
            "buf_ag_col_idx + mse_buf_spatial_stride[SPATIAL_INDEX]",
            "{`MSE_BUF_REQ_NUM{1'b1}} >> (`MSE_BUF_REQ_NUM - mse_buf_spatial_size)",
            "mse2buf_last_index <= mse_pingpong_last_index",
            "assign mse2buf_req_pingpong_sel  = buf_ag_req_pingpong;",
            "assign mse2buf_data_pingpong_sel = buf_ag_req_pingpong;",
            "mse2buf_last_index <= mse_buf_full_last_index",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_WR_Stream_Engine/RD_Buffer_AG.sv",
        (
            "buf_ag_col_idx + mse_buf_spatial_stride[SPATIAL_INDEX]",
            "{`MSE_BUF_REQ_NUM{1'b1}} >> (`MSE_BUF_REQ_NUM - mse_buf_spatial_size)",
            "mse2buf_last_index <= mse_pingpong_last_index",
            "buf_ag_req_pingpong_d <= buf_ag_req_pingpong;",
            "assign mse2buf_data_pingpong_sel = buf_ag_req_pingpong_d;",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Buffer_Manager_Cluster_Config.sv",
        (
            "buf_src_id,",
            "buf_full_last_index,",
            "buffer_nbr_cnt,",
            "buf_nbr_enable,",
            "buffer_life_time,",
            "buffer_mode,",
            "buffer_mask,",
            "buffer_end_row_addr",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Buffer_Manager_Cluster.sv",
        (
            "assign buffer_rw = {{`WR_BUFFER_NUM{1'b1}}, {`RD_BUFFER_NUM{1'b0}}};",
            "partner_arm_buf_rd_finish[0] = arm_buf_rd_finish[1]",
            "partner_arm_buf_rd_finish[2] = arm_buf_rd_finish[3]",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Buffer_Manager_Cluster_Connect.sv",
        (
            "if (BUF_IDX < 2) begin",
            "se2buf_mem_wreq_buf_sel[BUF_IDX/2][BUF_IDX%2]",
            "else if (BUF_IDX < `RD_BUFFER_NUM) begin",
            "assign se2mrm_req_valid[BUF_IDX]    = se2buf_mem_wreq_valid[BUF_IDX-1];",
            "assign se2mrm_req_valid[BUF_IDX]    = se2buf_mem_rreq_valid[0];",
            "assign array2arm_bp_post[BUF_IDX] = spec_array2buf_bp_post[BUF_IDX/2][BUF_IDX%2] & gene_array2buf_bp_post[BUF_IDX/2][BUF_IDX%2];",
            "buf_src_id[BUF_IDX] ? gene_array2buf_wtag",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Memory_Req_Manager.sv",
        (
            "se2buf_mem_req_col_addr[REQ_IDX][(`BUFFER_COL_ADDR_WIDTH-1):`BUFFER_BANK_OFFEST_WIDTH]",
            "se2buf_mem_req_col_addr[REQ_IDX][`BUFFER_BANK_OFFEST_WIDTH-1:0]",
            "mrm2buf_req_strb[bank_idx]  = mrm2buf_req_strb[bank_idx]",
            "assign mrm2buf_clear = mrm2buf_req_valid",
            "se2buf_mem_last_index <= buf_full_last_index",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Array_Request_Manager.sv",
        (
            "array_counter_0_end_value = buffer_mode ? buffer_life_time",
            "array_counter_1_end_value = buffer_mode ?",
            "array_req_addr = buffer_mode ? array_counter_1",
            "array_life_cnt = buffer_mode ? array_counter_0",
            "array_life_cnt == buffer_life_time",
            "arm_finish_cnt == buffer_nbr_cnt",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
        (
            "mrm2buf_req_valid[BANK_IDX] &  mrm2buf_req_rw & mrm2buf_wvalid",
            "mrm2buf_req_valid[BANK_IDX] & !mrm2buf_req_rw",
            "~(valid_buf[BANK_IDX][mrm2buf_req_addr] & mrm2buf_req_strb[BANK_IDX])",
            "valid_buf[BANK_IDX][mrm2buf_req_addr] | ~mrm2buf_req_strb[BANK_IDX]",
            "mrm2buf_clear[BANK_IDX] ? valid_buf_mrm_clr_mask[BANK_IDX]",
        ),
    )
    _require_snippets(
        root / "ndp-sim/bitstream/config/special.py",
        (
            '("mode", 1, lambda x: 0 if x == "gemm" else 1)',
            '("pingpong_last_index", 4)',
            '"int8": 0',
            '"fp16": 2',
            '"bf16": 3',
            '("transout_last_index", 4)',
            '("mode", 1, lambda x: 0 if x == "col" else (1 if x == "row" else x))',
            '("fp32tofp16", 1',
            '("fp32tobf16", 1',
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Specialized_Array/"
        "Specialized_Array_Config.sv",
        (
            "sa_mode,                        // 0: GEMM; 1: GEMV",
            "sa_inport_pingpong_last_index[2],",
            "sa_pe_computation_data_type,",
            "sa_pe_transout_last_index,",
            "sa_outport_fp32tobf16",
            "assign sa_pe_enable[SA_PE_ROW_IDX][SA_PE_COL_IDX] = !sa_mode && sa_enable;",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Buffer_Manager_Cluster_Connect.sv",
        (
            "buf2spec_array_rtag[BUF_IDX/2][BUF_IDX%2]  = arm2array_rtag[BUF_IDX]",
            "buf2spec_array_rtag[BUF_IDX/2][BUF_IDX%2]  = 0;",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Specialized_Array/"
        "Specialized_Array.sv",
        (
            "sa_pe_inport[SA_PE_ROW_IDX][SA_PE_COL_IDX][0] = {sa_inport_group_out_tag[0][SA_PE_ROW_IDX]",
            "sa_pe_inport[SA_PE_ROW_IDX][SA_PE_COL_IDX][1] = {sa_inport_group_out_tag[1][SA_PE_COL_IDX]",
            "sa_pe_inport[SA_PE_ROW_IDX][SA_PE_COL_IDX][2] = {sa_inport_group_out_tag[2][SA_PE_COL_IDX]",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Specialized_Array/SA_Inport/"
        "SA_Inport_Connect.sv",
        (
            "sa_inport_group_in_tag[sa_inport_src_sel]",
            "sa_inport_pingpong_en ? (sa_inport_group_in_tag[1]",
            "sa_inport_last_bit_pingpong_masked & (~sa_inport_nbr_enable)",
            "{1'b0, sa_inport_pingpong_last_index} - {1'b0, sa_inport_last_index}",
            "sa_inport_pingpong_change = sa_enable & sa_inport_pingpong_en && sa_inport_last_bit && sa_inport_pingpong_last_gte && sa_inport_bp_post;",
            "sa_inport_same_bit_mask = sa_inport_src_sel_delay ^ sa_inport_src_sel;",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_Control_Block.sv",
        (
            "sa_pe_all_inport_matched = &sa_pe_inport_valid_bit_masked[1:0];",
            "sa_pe_inport_valid_bit_masked[2] | ~sa_pe_bias_enable",
            "sa_pe_transout_last_index_diff = sa_pe_buffer_port_last_index - sa_pe_transout_last_index;",
            "sa_pe_transout_last_ignore",
            "sa_pe_transout_last_matched",
            "sa_pe_transout_last_out",
            "sa_pe_alu_inport[2] = sa_pe_bias_enable ? sa_pe_inport_data[2]",
            "alu_result_last_bit   = sa_pe_transout_last_out;",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_Outbuffer.sv",
        (
            "alu2ob_buffer_change  = (sa_pe_alu_result_last_matched || alu_result_last_bit)",
            "outbuffer_group_count[outbuffer_group_index] <= outbuffer_group_count[outbuffer_group_index] + 4;",
            "ob_out_rd_ready[alu2ob_pingpong_buffer_select] <= 1;",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU.sv",
        (
            ".FMA_Mode           ( sa_pe_computation_data_type[1] )",
            ".FMA_Precision      ( sa_pe_computation_data_type[0] )",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
        "SA_PE_Float_Control.v",
        (
            "assign c_MulDataA1_int = (gr_DataA[31]) ? ((~gr_DataA[31:24]) + 1'b1)",
            "assign c_MulDataB1_int = gr_DataB[31:24];",
            "assign o_Sign_int8 = {gr_DataA[7],gr_DataA[15],gr_DataA[23],gr_DataA[31]};",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
        "SA_PE_Mul_Array.v",
        (
            ".csa_4to2_width ( 17 )",
            "assign sum_int[31:17]   = {15{sum_int[16]}};",
            "assign carry_int[31:17] = {15{carry_int[16]}};",
            "assign last_B = pipe_IsFloat ? {attend_sum2[31:0]} : {carry_int[30:0], 1'b0};",
            "assign o_Carry[31:0]= {o_Carry_wire[30:0],1'b0};",
        ),
    )
    _require_snippets(
        root / "NDP_copy01/rtl/utils/CSA/CSA_4to2.v",
        (
            "assign cin_array = {cout_array[csa_4to2_width-2:0], cin};",
            "assign carry  = {carry_temp[csa_4to2_width-2:0], 1'd0};",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Specialized_Array/SA_Outport/"
        "SA_Outport_Connect.sv",
        (
            "sa_outport_major ? sa_outport_group_in_tag[OUTPORT_SRC_IDX][OUTPORT_IDX]",
            "sa_outport_major ? sa_outport_group_in_data[OUTPORT_SRC_IDX][OUTPORT_IDX]",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/Specialized_Array/SA_Outport/"
        "SA_Outport.sv",
        (
            "sa_outport_dynamic_cnt_end_flag = sa_mode ? 1'b1 : &sa_outport_dynamic_cnt;",
            "sa_outport_fp32_exp[7:0] >= 8'h8f",
            "sa_outport_fp32_exp[7:0] <= 8'h70",
            "sa_outport_fp16_exp_plus1_condition = sa_outport_fp32tofp16_frac_ceil_ones & sa_outport_fp32tofp16_frac_guard & sa_outport_fp32tofp16_frac_stick;",
            "sa_outport_bf16_exp_plus1_condition = sa_outport_fp32tobf16_frac_ceil_ones & sa_outport_fp32tobf16_frac_guard & sa_outport_fp32tobf16_frac_stick;",
            "sa_outport_ob_data[15:0] <= sa_outport_fp16_data;",
            "sa_outport_ob_data[31:16] <= sa_outport_fp16_data;",
        ),
    )
    _require_snippets(
        root / "ndp-sim/bitstream/config/general.py",
        (
            '("alu_opcode", 5',
            '("transout_last_index", 4)',
            '("inport2_src_id", 3)',
            '("constant0", 32',
            '"int8_max": 11',
            '"int32_mac": 14',
            '"sfu_activation": 24',
            '"constant": 3',
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/General_Array/GA_Inport/"
        "GA_Inport_Connect.sv",
        (
            "ga_inport_src_id ? ga_inport_group_sa_tag[0]",
            "ga_inport_last_bit & (~ga_inport_nbr_enable) & ga_inport_last_bit_mask",
            "{1'b0, ga_inport_pingpong_last_index} - {1'b0, ga_inport_last_index}",
            "ga_inport_pingpong_change & !ga_inport_src_id",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/General_Array/GA_Inport/GA_Inport.sv",
        (
            "ga_inport_fp16tofp32 || ga_inport_bf16tofp32 || ga_inport_int32tofp32 || ga_inport_uint8tofp32 || ga_inport_uint8toint32",
            "ga_inport_int32_min  = &ga_inport_ib_data",
            "ga_inport_fp16tofp32   ? ga_inport_fp16_valid",
            "ga_inport_uint8toint32 ? ga_inport_uint8toint32_data",
            "ga_inport_fp16_last       = ga_inport_ib_last && ga_inport_convert_cnt[0]",
            "ga_inport_uint8tofp32_last       = ga_inport_ib_last && (&ga_inport_convert_cnt)",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/"
        "GA_PE_Group_Interconnect.sv",
        (
            "GA_INPORT_IDX = GA_ROW_PE_ID + 4*(GA_COL_PE_ID/2)",
            "SRC_PE_ROW_OFFSET[`GA_PE_SRC_GA_PE_NUM] = '{-1, -1, -1,  0,  0}",
            "SRC_PE_COL_OFFSET[`GA_PE_SRC_GA_PE_NUM] = '{-1,  0,  1, -1,  1}",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/"
        "GA_PE_Inbuffer.sv",
        (
            "ga_pe_inport_mode[GA_PORT_IDX] == `GA_PE_INPORT_BUFFER_MODE || (!(ga_pe_buffer_inport_last_index > ga_pe_keep_last_index[GA_PORT_IDX])",
            "ga_pe_inbuffer2alu_last_bit   = ga_pe_inbuffer_matched && ga_pe_buffer_inport_last_bit && (ga_pe_buffer_inport_last_index<ga_pe_transout_last_index);",
            "ga_pe_transout_calculate_wire = alu_op_is_transout && ga_pe_buffer_inport_last_bit && ga_pe_buffer_inport_last_index<=ga_pe_transout_last_index;",
            "assign alu_pipeline0_bp_post      = (alu_is_int32 && ga_pe_inbuffer_bp_post)",
            "assign ga_pe_alu_pipeline0_enable = !alu_pipeline0_valid_bit || alu_pipeline0_bp_post;",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/"
        "GA_PE_Float_Control.v",
        (
            "assign c_AddData         = gr_DataC",
            "assign c_FmaIsMax     = gr_Opcode==3'b011",
            "assign c_FmaIsSum_Add = gr_Opcode==3'b100",
            "assign c_FmaIsSum_Mac = (is_fp32 && gr_Opcode==3'b101 )",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/"
        "GA_PE_Float_CSA.v",
        (
            "assign add_A = i_is_int8",
            "assign o_Int8_Result[31:24] = c_Result0[44] ? i_AddDataA_uint8[31:24] : i_AddDataB_uint8[31:24];",
            "assign o_IntResult = i_is_int8 ? o_Int8_Result : c_Result0[32:1];",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/"
        "GA_PE_Outbuffer.sv",
        (
            "alu_is_fp32  && transout_calculate_cnt==3'h7",
            "alu_is_int32 && transout_calculate_cnt==3'h3",
            "alu_is_int8 && ga_pe_transout_calculate",
            "ga_pe_transout_result_valid <= 1'b1;",
            "ga_pe_transout_result_last_bit <= 1'b1;",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/General_Array/GA_Outport/"
        "GA_Outport_Connect.sv",
        (
            "GA_PE_ROW_ID = (4*(OUTPORT_ID%4) + 2*(OUTPORT_ID/4) + OUTPORT_SRC_ID) / `GA_ROW_PE_NUM",
            "GA_OUTPORT_ID  = GA_PE_ROW_ID + 4*(GA_COL_PE_NUM/2)",
            "GA_OUTPORT_SRC = GA_COL_PE_NUM % 2",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/General_Array/GA_Outport/GA_Outport.sv",
        (
            "ga_outport_fp32_exp[7:0] >= 8'h8f",
            "ga_outport_fp32_exp[7:0] <= 8'h70",
            "ga_outport_int32_sign ? 8'b0",
            "(|ga_outport_in_data[30:8]) ? 8'hFF",
            "ga_outport_ob_data[31:24] <= ga_outport_uint8_data;",
        ),
    )
    _require_snippets(
        root / "ndp-sim/bitstream/config/neighbor.py",
        (
            '("src_slice_sel", 1)',
            '("dst_slice_sel", 1)',
            '("ping_pong", 1)',
            '("mem_loop", 5, lambda x : x-1',
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
        "Neighbor_Stream_Engine/NSE_Controller.sv",
        (
            "nse_rd_ctrl_cnt == nse_cnt_size",
            "nse_wr_ctrl_cnt == nse_cnt_size",
            "nse2mse_req_barrier = (|nse_rd_ctrl_cnt) || (|nse_wr_ctrl_cnt)",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
        "Neighbor_Stream_Engine/Neighbor_In_AG.sv",
        (
            "nbr_in_row_addr == `BUFFER_ROW_SIZE - 1",
            "end_nbr_in_row_addr || (nse_enable && mse2nse_req_valid)",
            "nse_wreq_pingpong_sel  = nse2buf_pingpong_sel",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
        "Neighbor_Stream_Engine/Neighbor_Out_AG.sv",
        (
            "nbr_out_row_addr == `BUFFER_ROW_SIZE - 1",
            "end_nbr_out_row_addr || (mse2nse_req_valid && nse_enable)",
            "nse_rdata_pingpong_sel = buf2nse_pingpong_sel_d",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
        "Stream_Engine_Config.sv",
        (
            "nse_in_src_slice_sel[NSE_IDX]",
            "nse_out_dst_slice_sel[NSE_IDX]",
            "nse_pingpong_enable[NSE_IDX]",
            "nse_cnt_size[NSE_IDX]} = nse_configure_reg[NSE_IDX]",
            "else if (se_nse_configure_clear) begin",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
        "Stream_Engine_Connect.sv",
        (
            "nbr_slice2se_wvalid[NSE_IDX][nse_in_src_slice_sel[NSE_IDX]]",
            "nbr_slice2se_rready[NSE_IDX][nse_out_dst_slice_sel[NSE_IDX]]",
            "se2buf_nbr_rreq_valid[NSE_IDX][0]",
            "se2buf_nbr_wreq_valid[NSE_IDX][1]",
        ),
    )
    _require_snippets(
        root / "NDP_copy01/rtl/NDP_Top.sv",
        (
            "LOW_PREV_MAP [0:27]",
            "LOW_NEXT_MAP [0:27]",
            "HIGH_PREV_MAP[SLICE_ID]",
            "HIGH_NEXT_MAP[SLICE_ID]",
        ),
    )
    _require_snippets(
        root / "NDP_copy01/rtl/Slice/slice2hub_crossbar.sv",
        (
            "mse2hub_req_valid[MSE_IDX][CHL_IDX]",
            "slice_local_req_ready[MSE_IDX][CHL_IDX]",
        ),
    )
    _require_snippets(
        root
        / "NDP_copy01/rtl/Datahub/Datahub_Req_Crossbar/"
        "datahub_req_crossbar.sv",
        (
            "total_req_match[BANK_IDX] & total_req_valid",
            "total_req_ready[BANK_IDX][LOCAL_REQ_IDX] & req_cb_ready[BANK_IDX]",
        ),
    )


def build_stage_operator_semantics_audit(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    sources = _require_files(root)
    _validate_static_sources(root)

    typed = _load_object(root / "contracts/typed_config_parameter_contract.json")
    register_semantics = _load_object(
        root / "contracts/operator_config/register_semantics_v1.json"
    )
    lc_pe_corpus = _authorized_lc_pe_corpus(root)
    mse_corpus = _authorized_mse_corpus(root)
    padding_tail_corpus = _authorized_padding_tail_corpus(root)
    buffer_corpus = _authorized_buffer_corpus(root)
    sa_corpus = _authorized_sa_corpus(root)
    ga_corpus = _authorized_ga_corpus(root)
    n2n_corpus = _authorized_n2n_corpus(root)
    request = _gap_request(typed)
    config = _load_object(root / GAP_CONFIG_PATH)
    mapping = _load_object(root / GAP_MAPPING_PATH)
    sim6 = _load_object(root / GAP_SIM6_REPORT_PATH)
    probe_v4 = _load_object(root / GAP_PROBE_V4_ANALYSIS_PATH)
    probe_v4_numeric = _load_object(root / GAP_PROBE_V4_NUMERIC_PATH)
    dump_text = (root / GAP_DUMP_PATH).read_text(encoding="utf-8")

    register_rows = {
        item.get("config_name"): item
        for item in register_semantics.get("rows", [])
        if isinstance(item, Mapping)
    }
    for name in (
        "dram_loop_configs.start",
        "dram_loop_configs.stride",
        "dram_loop_configs.end",
    ):
        row = register_rows.get(name)
        if (
            not isinstance(row, Mapping)
            or row.get("declared_width") != 17
            or row.get("range_span") != 13
        ):
            raise StageOperatorSemanticsAuditError(
                f"LC spreadsheet width/range conflict differs: {name}"
            )
    lc_pe_expected_rows = {
        "lc_pe_configs.alu_opcode": (2, 2),
        "lc_pe_configs.inport2.src_id": (4, 4),
        "lc_pe_configs.inport2.keep_last_index": (4, 4),
        "lc_pe_configs.inport2.mode": (2, 2),
        "lc_pe_configs.inport1.src_id": (4, 4),
        "lc_pe_configs.inport1.keep_last_index": (4, 4),
        "lc_pe_configs.inport1.mode": (2, 2),
        "lc_pe_configs.inport0.src_id": (4, 4),
        "lc_pe_configs.inport0.keep_last_index": (4, 4),
        "lc_pe_configs.inport0.mode": (2, 2),
        "lc_pe_configs.inport2.cfg_constant_pos": (16, 12),
        "lc_pe_configs.inport1.cfg_constant_pos": (16, 12),
        "lc_pe_configs.inport0.cfg_constant_pos": (16, 12),
    }
    for name, (declared_width, range_span) in lc_pe_expected_rows.items():
        row = register_rows.get(name)
        if (
            not isinstance(row, Mapping)
            or row.get("declared_width") != declared_width
            or row.get("range_span") != range_span
        ):
            raise StageOperatorSemanticsAuditError(
                f"LC-PE spreadsheet field differs: {name}"
            )

    mapping_by_node = {
        item.get("node"): item.get("resource")
        for item in mapping.get("node_to_resource", [])
        if isinstance(item, Mapping)
    }
    if (
        mapping_by_node.get("DRAM_LC.LC0") != "LC4"
        or mapping_by_node.get("DRAM_LC.LC2") != "LC6"
        or mapping_by_node.get("LC_PE.PE1") != "PE6"
        or "Connect(DRAM_LC.LC0 -> DRAM_LC.LC2) | encoded=['0101']"
        not in dump_text
    ):
        raise StageOperatorSemanticsAuditError(
            "GAP LC physical mapping or encoded selector differs"
        )

    coverage = analyze_gap_d_index_coverage(config, request)
    if (
        coverage["classification"] != "CONTRADICTED"
        or coverage["derived_distinct_transaction_bases"] != 1
        or coverage["required_distinct_transaction_bases"] != 256
    ):
        raise StageOperatorSemanticsAuditError(
            "GAP D-index contradiction no longer reproduces"
        )

    request_check = sim6.get("mse0_request_address_check")
    write_check = sim6.get("mse4_write_address_check")
    first_divergence = sim6.get("first_divergence")
    if (
        not isinstance(request_check, Mapping)
        or request_check.get("expected_count") != 8960
        or request_check.get("actual_count") != 8960
        or request_check.get("mismatch_count") != 1264
        or not isinstance(first_divergence, Mapping)
        or first_divergence.get("expected_address_128bit") != "0x000001"
        or first_divergence.get("actual_address_128bit") != "0x000002"
        or not isinstance(write_check, Mapping)
        or write_check.get("request_count") != 512
        or write_check.get("unique_addresses_128bit")
        != ["0x001884", "0x001885"]
    ):
        raise StageOperatorSemanticsAuditError(
            "GAP sim6 evidence differs"
        )

    v4_transport = probe_v4.get("mse0_address_transport")
    v4_correlation = probe_v4.get("local_log_correlation")
    v4_request_check = probe_v4_numeric.get("mse0_request_address_check")
    v4_first_divergence = probe_v4_numeric.get("first_divergence")
    if (
        probe_v4.get("classification") != "mse0_path_matched_in_probe_window"
        or not isinstance(v4_transport, Mapping)
        or v4_transport.get("transport_mismatch_count") != 0
        or not isinstance(v4_correlation, Mapping)
        or v4_correlation.get("ddr_return_payload", {}).get(
            "exact_payload_mismatch_count"
        )
        != 0
        or v4_correlation.get("metadata_consume_window", {}).get(
            "address_order_mismatch_count"
        )
        != 0
        or not isinstance(v4_request_check, Mapping)
        or v4_request_check.get("expected_count") != 8960
        or v4_request_check.get("actual_count") != 8960
        or v4_request_check.get("missing_expected_address_occurrence_count")
        != 0
        or v4_request_check.get("extra_actual_address_occurrence_count") != 0
        or not isinstance(v4_first_divergence, Mapping)
        or v4_first_divergence.get("stage") != "post_mse0_pre_mse4"
    ):
        raise StageOperatorSemanticsAuditError(
            "GAP probe_v4 transport evidence differs"
        )
    _require_snippets(
        root / GAP_PROBE_V5_ANALYSIS_PATH,
        (
            "MSE4 请求 512 次、写数据 512 次",
            "2048 个 INT32",
            "10 个相等、",
            "2038 个不等",
            "700313000",
            "700388000",
            "Buffer→GA 路由",
        ),
    )
    _require_snippets(
        root / GAP_RTL_IDENTITY_ANALYSIS_PATH,
        (
            "14/14 服务器文件与本地 `NDP_copy01` 规范化文本一致",
            "当前 GAP 使用 `opcode=0x0c=5'b01100`",
            "当前不需要为了身份再次运行服务器",
        ),
    )
    v7_analysis = _load_object(root / GAP_PROBE_V7_ANALYSIS_PATH)
    v7_numeric = _load_object(root / GAP_PROBE_V7_NUMERIC_PATH)
    v7_acceptance = _load_object(root / GAP_PROBE_V7_ACCEPTANCE_PATH)
    v7_state = v7_analysis.get("ga_accumulator_state", {})
    v7_d_address = v7_numeric.get("mse4_write_address_check", {})
    if (
        v7_analysis.get("classification")
        != "ga_int32_sum_outbuffer_count_underflow_then_invalid_slot_reuse"
        or v7_state.get("underflow_transition_count") != 8
        or v7_state.get("invalid_slot_c_reuse_count") != 217
        or v7_d_address.get("request_count") != 512
        or v7_d_address.get("unique_address_count") != 2
        or v7_acceptance.get("numeric", {}).get("expected_matrix_count") != 16
    ):
        raise StageOperatorSemanticsAuditError(
            "GAP probe_v7 dynamic adjudication evidence differs"
        )

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "probe_v7_ingested_gap_ga_dynamic_root_cause_closed",
        "classification_vocabulary": [
            "RTL_PROVEN",
            "SAMPLE_SUPPORTED",
            "TEST_REQUIRED",
            "CONTRADICTED",
        ],
        "scope": {
            "closed": [
                "DRAM LC src_id/outmost/value/tag/last/same core semantics",
                "LC_PE packing/input-select/mode/opcode/keep/tag/signed-truncation core semantics",
                "MSE packing/index-mode/address/remap/split/write-RMW static semantics",
                "padding/tail per-lane index/bounds/priority/mask/reorder static semantics",
                "Buffer AG lane/bank/ping-pong and Buffer Manager traversal/ownership static semantics",
                "SA packing/topology/psum/terminal/outport static semantics and exact current INT8 CSA equation",
                "GA packing/routing/operand/opcode/terminal/conversion static semantics",
                "N2N ring selection/row transfer/bank rotation/controller/config-lifetime static semantics",
                "exact r5:hwop-0071-00 D-index necessary coverage",
                "RD Memory AG delayed-valid replay precondition",
                "probe_v4 per-channel MSE0 request/return/payload/metadata association",
                "probe_v5 MSE4 handshake count, packing and GA integer-add boundary",
                "server/local critical GAP-path RTL normalized identity for 14/14 files",
            ],
            "not_closed": [
                "LC_PE usefulness for any new stage/shape/topology",
                "MSE first/stall/resume dynamic transport safety",
                "GAP block1 Buffer-to-GA/inbuffer/tag/accumulator first divergence",
                "GA SFU numerical conformance outside the configured LUT sample domain",
                "N2N mixed-selector/neighbor_stream1 dynamic execution coverage",
            ],
            "functional_rtl_modified": False,
        },
        "source_identities": sources,
        "c0_ledger": [
            {
                "ledger_id": "C0-LC",
                "priority": 1,
                "classification": "RTL_PROVEN",
                "audit_state": "core_control_and_counter_semantics_closed",
                "remaining": (
                    "audit every template/generator consumer; value-domain "
                    "correctness remains stage-specific"
                ),
            },
            {
                "ledger_id": "C0-LC-PE",
                "priority": 2,
                "classification": "RTL_PROVEN",
                "audit_state": "core_packing_data_tag_and_flow_semantics_closed",
                "remaining": (
                    "new stage arithmetic domains and schedules remain "
                    "stage-specific; add has no authorized corpus instance"
                ),
            },
            {
                "ledger_id": "C0-MSE-MEMORY-AG",
                "priority": 3,
                "classification": "TEST_REQUIRED",
                "audit_state": "static_equations_closed_dynamic_outbuffer_pending",
                "remaining": (
                    "generic first/stall/resume cycle behavior; the earlier sim6 "
                    "GAP replay attribution is superseded by probe_v4/v5"
                ),
            },
            {
                "ledger_id": "C0-PADDING-TAIL-KEEP",
                "priority": 4,
                "classification": "RTL_PROVEN",
                "audit_state": "static_lane_boundary_and_merge_semantics_closed",
                "remaining": (
                    "stage-specific bound selection and dynamic delayed-valid "
                    "transport remain separate"
                ),
            },
            {
                "ledger_id": "C0-BUFFER",
                "priority": 5,
                "classification": "RTL_PROVEN",
                "audit_state": "static_address_owner_lifetime_semantics_closed",
                "remaining": (
                    "neighbor multi-slice switch completion is retained under "
                    "the N2N ledger; cycle-level MSE transport remains separate"
                ),
            },
            {
                "ledger_id": "C0-SA",
                "priority": 6,
                "classification": "CONTRADICTED",
                "audit_state": "static_equations_closed_int8_dot_and_ieee_corner_assumptions_contradicted",
                "remaining": (
                    "cycle-level floating-point numerical conformance and "
                    "enabled-bias execution have no authorized corpus sample; "
                    "current INT8 Conv promotion is blocked by the exact CSA equation"
                ),
            },
            {
                "ledger_id": "C0-GA",
                "priority": 7,
                "classification": "CONTRADICTED",
                "audit_state": "static_equations_closed_int8_max_pipeline_and_int32_conversion_assumptions_contradicted",
                "remaining": (
                    "cycle-level FP/SFU numerical conformance; sqrt and int32_mac "
                    "have no authorized sample; GAP block1 accumulation state is "
                    "localized but not yet rooted"
                ),
            },
            {
                "ledger_id": "C0-N2N-CONFIG-LIFETIME",
                "priority": 8,
                "classification": "CONTRADICTED",
                "audit_state": "static_equations_closed_ping_pong_field_and_zero_copy_assumptions_contradicted",
                "remaining": (
                    "neighbor_stream1, mixed selector pairs and dynamic "
                    "multi-stage clear/reconfigure sequencing lack authorized traces"
                ),
            },
        ],
        "findings": [
            {
                "issue_id": "CDA-LC-SRC-001",
                "classification": "RTL_PROVEN",
                "title": "DRAM LC src_id selects a trigger/tag input, not a numeric value",
                "json_paths": [
                    "$.dram_loop_configs.LC*.src_id",
                    "$.dram_loop_configs.LC*.outmost_loop",
                    "$.dram_loop_configs.LC*.start",
                    "$.dram_loop_configs.LC*.stride",
                    "$.dram_loop_configs.LC*.end",
                    "$.dram_loop_configs.LC*.last_index",
                ],
                "bitstream_and_register": {
                    "config_width_bits": 60,
                    "fields_msb_to_lsb": [
                        {"field": "src_id", "bits": "[59:56]", "width": 4},
                        {"field": "outmost_loop", "bits": "[55]", "width": 1},
                        {"field": "start", "bits": "[54:38]", "width": 17},
                        {"field": "stride", "bits": "[37:21]", "width": 17},
                        {"field": "end", "bits": "[20:4]", "width": 17},
                        {"field": "last_index", "bits": "[3:0]", "width": 4},
                    ],
                    "src_encoding": (
                        "logical edge is placed first; Connect encodes the "
                        "destination-relative physical inport selector"
                    ),
                    "default_encoding": (
                        "None and inactive fields encode as zero; outmost_loop "
                        "determines whether a zero src selector is semantically used"
                    ),
                    "gap_example": {
                        "logical_edge": "DRAM_LC.LC0 -> DRAM_LC.LC2",
                        "physical_edge": "LC4 -> LC6",
                        "relative_selector": 5,
                        "encoded_bits": "0101",
                    },
                    "spreadsheet_arbitration": (
                        "spreadsheet [47:0] ranges conflict with declared "
                        "17-bit start/stride/end; encoder and RTL agree on "
                        "the 60-bit layout above, so spreadsheet offsets are "
                        "not target packing authority"
                    ),
                },
                "rtl_effect": {
                    "selected_input": "iga_lc_inport[iga_lc_src_id]",
                    "selected_payload_used": (
                        "tag only: valid,last,same,last_index; selected data "
                        "is not consumed by the counter"
                    ),
                    "outmost": (
                        "outmost_loop=1 replaces the selected tag with "
                        "slice_start_run and ignores src_id for triggering"
                    ),
                    "counter_value": (
                        "initial_value, then signed(previous_data)+"
                        "signed(stride_value); output is truncated to 16 data bits"
                    ),
                    "last": (
                        "valid && signed(next_value) >= "
                        "signed(end_value)-signed(stride_value)"
                    ),
                    "last_index": (
                        "upstream_last ? upstream_last_index : local_index"
                    ),
                    "same": (
                        "upstream same suppresses duplicate trigger capture; "
                        "outgoing same is regenerated while this LC output stalls"
                    ),
                    "backpressure": (
                        "only the selected input receives the LC inbuffer "
                        "backpressure when outmost_loop=0"
                    ),
                },
                "signedness_and_legal_subset": {
                    "rtl_arithmetic": (
                        "17-bit start/stride/end are explicitly cast signed "
                        "for addition and end comparison"
                    ),
                    "current_strict_validator": (
                        "start/end signed 17-bit; generated stride positive "
                        "unsigned 17-bit; active loop requires start<end"
                    ),
                    "negative_stride": (
                        "not approved by this audit even though a two's-"
                        "complement bit pattern can be packed"
                    ),
                },
                "minimal_examples": {
                    "positive": (
                        "LC2 src_id=LC0, start=100,end=104,stride=2: each "
                        "accepted LC0 trigger causes local values 100,102"
                    ),
                    "negative": (
                        "LC2 src_id=LC0, start=0,end=1,stride=1 does not "
                        "copy LC0 values; it emits local value 0 per trigger"
                    ),
                },
                "scope": (
                    "all DRAM LC instances in the bound NDP_copy01 RTL and "
                    "the bound ndp-sim encoder; numeric usefulness remains "
                    "specific to the consuming stage"
                ),
            },
            {
                "issue_id": "CDA-LCPE-PACK-001",
                "classification": "RTL_PROVEN",
                "title": "LC-PE is a two-beat 96-bit configuration with a 32-bit control register and three 16-bit constants",
                "json_paths": [
                    "$.lc_pe_configs.PE*.alu_opcode",
                    "$.lc_pe_configs.PE*.inport[0-2].src_id",
                    "$.lc_pe_configs.PE*.inport[0-2].keep_last_index",
                    "$.lc_pe_configs.PE*.inport[0-2].mode",
                    "$.lc_pe_configs.PE*.inport[0-2].constant",
                ],
                "bitstream_and_register": {
                    "total_bits": 96,
                    "configure_beats": 2,
                    "configure_beat_width_bits": 48,
                    "fields_msb_to_lsb": [
                        {"field": "reserved_padding", "bits": "[95:80]", "width": 16},
                        {"field": "alu_opcode", "bits": "[79:78]", "width": 2},
                        {"field": "inport2.src_id", "bits": "[77:74]", "width": 4},
                        {"field": "inport2.keep_last_index", "bits": "[73:70]", "width": 4},
                        {"field": "inport2.mode", "bits": "[69:68]", "width": 2},
                        {"field": "inport1.src_id", "bits": "[67:64]", "width": 4},
                        {"field": "inport1.keep_last_index", "bits": "[63:60]", "width": 4},
                        {"field": "inport1.mode", "bits": "[59:58]", "width": 2},
                        {"field": "inport0.src_id", "bits": "[57:54]", "width": 4},
                        {"field": "inport0.keep_last_index", "bits": "[53:50]", "width": 4},
                        {"field": "inport0.mode", "bits": "[49:48]", "width": 2},
                        {"field": "inport2.constant", "bits": "[47:32]", "width": 16},
                        {"field": "inport1.constant", "bits": "[31:16]", "width": 16},
                        {"field": "inport0.constant", "bits": "[15:0]", "width": 16},
                    ],
                    "rtl_load": (
                        "beat 0 low 32 bits load opcode/src/keep/mode; beat 1 "
                        "presents constant0/1/2 in 16-bit lanes and only a "
                        "port whose already-latched mode is 2'b11 captures it"
                    ),
                    "source_selector": (
                        "the 4-bit src_id indexes ten physical inputs; mapper "
                        "encodes LC neighbors as selectors 0..5 and LC-PE "
                        "neighbors as selectors 6..9"
                    ),
                    "spreadsheet_arbitration": (
                        "spreadsheet control widths agree, but its three "
                        "constant rows declare 16 bits while each shown range "
                        "spans only 12; encoder chunking and RTL 16-bit lanes "
                        "are the packing authority"
                    ),
                },
                "minimal_examples": {
                    "positive": (
                        "mul, port0=buffer(LC), port1=constant(1), port2=null "
                        "encodes one control beat followed by constants "
                        "{0,1,0}"
                    ),
                    "negative": (
                        "copying spreadsheet [35:0] constant offsets would "
                        "produce three 12-bit lanes and cannot drive the RTL "
                        "48-bit constant beat"
                    ),
                },
                "scope": (
                    "all IGA LC-PE instances in the bound encoder/RTL; this "
                    "does not approve any particular stage arithmetic schedule"
                ),
            },
            {
                "issue_id": "CDA-LCPE-ALU-001",
                "classification": "RTL_PROVEN",
                "title": "LC-PE add, multiply and MAC are signed-input modulo-2^16 integer equations",
                "rtl_equations": {
                    "add_opcode_0": (
                        "D = low16(s16(inport0) * 1 + s16(inport1)); "
                        "inport2 is numerically ignored"
                    ),
                    "mul_opcode_1": (
                        "D = low16(s16(inport0) * s16(inport1)); "
                        "inport2 is numerically ignored"
                    ),
                    "mac_opcode_2": (
                        "D = low16(s16(inport0) * s16(inport1) + "
                        "s16(inport2))"
                    ),
                    "implementation": (
                        "DW02_mult uses TC=1 and produces 32 bits; only its "
                        "low 16 bits enter the 16-bit CLA, whose carry is "
                        "discarded"
                    ),
                    "opcode_3": (
                        "RTL default drives all ALU operands to zero; encoder "
                        "and strict validator do not expose it as a legal opcode"
                    ),
                },
                "signedness_and_constants": {
                    "data_width_bits": 16,
                    "constant_width_bits": 16,
                    "integer_interpretation": "two's-complement signed inputs",
                    "output_interpretation": (
                        "16-bit bit pattern; the consuming address/tag logic "
                        "decides whether that pattern is useful"
                    ),
                    "strict_constant_domain": (
                        "signed int16 decimal or exact 0x0000..0xffff raw bit "
                        "pattern; floating/fractional LC-PE constants are "
                        "rejected because the generic encoder would take the "
                        "low 16 bits of an FP32 encoding"
                    ),
                },
                "operand_enable_contract": {
                    "add": "inport0 and inport1 enabled; inport2 null",
                    "mul": "inport0 and inport1 enabled; inport2 null",
                    "mac": "inport0, inport1 and inport2 enabled",
                    "reason": (
                        "a null used port leaves its data register without a "
                        "defined operand; an enabled ignored port still gates "
                        "matched/backpressure and is therefore not inert"
                    ),
                },
                "authorized_corpus": lc_pe_corpus,
                "micro_examples_unsigned_hex": {
                    "add_ffff_plus_0002": f"0x{lc_pe_int_result('add', 0xffff, 2):04x}",
                    "mul_ffff_times_0002": f"0x{lc_pe_int_result('mul', 0xffff, 2):04x}",
                    "mac_8000_times_0002_plus_0001": f"0x{lc_pe_int_result('mac', 0x8000, 2, 1):04x}",
                },
                "validator_enforcement": [
                    "LC_PE.OPERAND_DISABLED",
                    "LC_PE.UNUSED_OPERAND_ENABLED",
                    "LC_PE.CONSTANT_DOMAIN",
                    "VALUE.SIGNED_RANGE",
                ],
                "evidence_boundary": (
                    "RTL proves all three equations; the 65 authorized configs "
                    "contain 151 mul and 42 mac instances but zero add "
                    "instances, so add has no sample-backed stage migration"
                ),
            },
            {
                "issue_id": "CDA-LCPE-MODE-TAG-001",
                "classification": "RTL_PROVEN",
                "title": "LC-PE mode controls operand lifetime while one buffer port owns output terminal tags",
                "mode_table": {
                    "null_00": (
                        "port disabled and excluded from all-enabled matching"
                    ),
                    "buffer_01": (
                        "capture each accepted source value; release after "
                        "each matched output handshake"
                    ),
                    "keep_10": (
                        "capture a source value and retain it until the buffer "
                        "carrier reports last=1 and last_index <= "
                        "keep_last_index"
                    ),
                    "constant_11": (
                        "capture the signed 16-bit configuration constant on "
                        "the second configure beat and retain it"
                    ),
                },
                "tag_and_flow_equations": {
                    "matched": (
                        "iga_pe_enable && every enabled port has a valid "
                        "inbuffer value"
                    ),
                    "buffer_tag_owner": (
                        "RTL selects the first buffer-mode port in priority "
                        "order port0, port1, port2 for last/last_index"
                    ),
                    "strict_subset": (
                        "validator requires exactly one buffer carrier, making "
                        "the priority unambiguous"
                    ),
                    "keep_release": (
                        "buffer_last && buffer_last_index <= configured "
                        "keep_last_index (inclusive)"
                    ),
                    "output_tag": (
                        "valid=matched; last and last_index come only from the "
                        "buffer carrier, not keep/constant operands"
                    ),
                    "same_and_backpressure": (
                        "source same suppresses duplicate capture; the two-entry "
                        "outbuffer regenerates same while stalled, and only "
                        "selected enabled sources receive port backpressure"
                    ),
                },
                "ignored_field_gates": {
                    "constant_src_id": "rejected as GRAPH.UNUSED_SOURCE",
                    "keep_last_index_on_nonkeep": (
                        "rejected as TAG.UNUSED_KEEP_THRESHOLD"
                    ),
                },
                "minimal_examples": {
                    "positive": (
                        "mac(keep x, constant stride, buffer y) holds x across "
                        "y iterations and refreshes x at the configured "
                        "inclusive y terminal boundary"
                    ),
                    "negative": (
                        "changing the keep port's last_index cannot make it "
                        "the output terminal carrier; only the buffer port "
                        "drives output last/last_index"
                    ),
                },
                "scope": (
                    "core LC-PE lifetime/tag/backpressure semantics; the "
                    "correct threshold for a stage still requires its loop "
                    "nest and terminal contract"
                ),
            },
            {
                "issue_id": "CDA-MSE-PACK-MODE-001",
                "classification": "RTL_PROVEN",
                "title": "MSE vector packing reverses JSON dimensions into RTL ports and modes control index lifetime",
                "json_paths": [
                    "$.stream_engine.stream*.mem_idx_mode",
                    "$.stream_engine.stream*.mem_idx_keep_last_index",
                    "$.stream_engine.stream*.idx",
                    "$.stream_engine.stream*.mem_idx_constant",
                    "$.stream_engine.stream*.buf_idx_mode",
                    "$.stream_engine.stream*.buf_idx_keep_last_index",
                ],
                "bitstream_and_register": {
                    "read_config_bits": 580,
                    "read_config_beats": "10 x 58-bit",
                    "write_config_bits": 496,
                    "write_config_beats": "8 x 62-bit",
                    "write_reserved_msb_bits": 3,
                    "field_widths_msb_to_lsb": {
                        "mem_idx_mode": "3 x 2",
                        "mem_idx_keep_last_index": "3 x 4",
                        "idx": "3 x 5",
                        "mem_idx_constant": "3 x 8",
                        "buf_idx_mode": "2 x 1",
                        "buf_idx_keep_last_index": "2 x 4",
                        "ping_pong": 1,
                        "pingpong_last_index": 4,
                        "base_addr": 30,
                        "idx_size": "3 x 8",
                        "idx_size_log": "3 x 3 derived",
                        "total_size": "8 derived",
                        "dim_stride": "3 x 20",
                        "address_remapping": "26 x 5",
                    },
                    "dimension_order": (
                        "BaseConfig packs list element 0 on the MSB side. "
                        "Therefore JSON [dim0,dim1,dim2] maps to RTL "
                        "[port2,port1,port0]; dim0 is the innermost byte "
                        "layout dimension"
                    ),
                    "buffer_index_order": (
                        "JSON buf_idx_mode=[row,col] maps to RTL port1=row "
                        "and port0=col"
                    ),
                },
                "memory_index_modes": {
                    "null_00": (
                        "index value is zero and the port is treated "
                        "always-valid; source selector is numerically unused"
                    ),
                    "buffer_01": (
                        "selected 16-bit source is consumed for every matched "
                        "index tuple and owns terminal last/last_index"
                    ),
                    "keep_10": (
                        "selected source is retained until buffer_last && "
                        "buffer_last_index <= keep_last_index"
                    ),
                    "constant_11": (
                        "8-bit configuration pattern is sign-extended to a "
                        "16-bit index, then subsequent address multiplication "
                        "treats that 16-bit vector as unsigned"
                    ),
                    "matching": (
                        "buffer/keep require selected-source valid; null/"
                        "constant are synthesized valid; all three must match "
                        "before the depth-8 Memory AG index FIFO is written"
                    ),
                    "tag_owner": (
                        "first buffer port in RTL priority port0,port1,port2; "
                        "strict target requires exactly one buffer"
                    ),
                },
                "buffer_index_modes": {
                    "buffer_0": "consume row/col source each matched tuple",
                    "keep_1": (
                        "retain row/col source through the same inclusive "
                        "terminal threshold equation"
                    ),
                    "matching": (
                        "both row and col are always valid-required; the "
                        "depth-16 Buffer AG index FIFO has no null/constant mode"
                    ),
                    "strict_pair": (
                        "exactly one buffer and one keep; in all 177 authorized "
                        "streams the JSON pair is [keep,buffer], meaning row is "
                        "kept and col is the terminal carrier"
                    ),
                },
                "authorized_corpus": mse_corpus,
                "legacy_boundary": (
                    "four authorized exact-reference GEMM streams use integer "
                    "0, which the native mapper collapses to null. The strict "
                    "target schema intentionally requires typed null and uses "
                    "an encoding-equivalence materialization rather than "
                    "silently accepting arbitrary integer modes"
                ),
                "dont_care_boundary": (
                    "RTL consults keep_last_index only in keep mode. The "
                    "authorized corpus contains non-null ignored thresholds, "
                    "so those fields are documented as don't-care and are not "
                    "retroactively declared incorrect"
                ),
            },
            {
                "issue_id": "CDA-MSE-ADDR-001",
                "classification": "RTL_PROVEN",
                "title": "MSE request address is remapped transaction bias plus aligned base address",
                "json_paths": [
                    "$.stream_engine.stream*.idx",
                    "$.stream_engine.stream*.mem_idx_constant",
                    "$.stream_engine.stream*.dim_stride",
                    "$.stream_engine.stream*.base_addr",
                    "$.stream_engine.stream*.address_remapping",
                ],
                "rtl_equations": {
                    "transaction_bias": (
                        "B = low30(sum(i=0..2, u16(rtl_idx[i]) * "
                        "u20(rtl_stride[i])))"
                    ),
                    "transfer_byte_address": (
                        "T = low30(B + transfer_bias_bytes)"
                    ),
                    "drop_byte_offset": "U = T[29:4]",
                    "remap": (
                        "R[out_bit] = U[address_remapping[out_bit]] for "
                        "out_bit 0..25; JSON null encodes identity"
                    ),
                    "request_line_address": (
                        "A = low26(R + base_addr[29:4])"
                    ),
                },
                "ordering_consequences": [
                    "remapping applies to transaction bias, not to base_addr",
                    "base_addr low four bits are discarded, so strict target requires 16-byte alignment",
                    "the 30-bit byte-address sum and final 26-bit line-address addition wrap at their RTL widths",
                    "a sign-extended constant index such as 0xff becomes u16(0xffff) for multiplication because the address operands are not declared signed",
                ],
                "micro_examples": {
                    "identity_request": mse_memory_request_address(
                        [1, 2, 3],
                        [4, 32, 256],
                        base_addr=0x1000,
                    ),
                    "identity_request_hex": (
                        f"0x{mse_memory_request_address([1, 2, 3], [4, 32, 256], base_addr=0x1000):07x}"
                    ),
                    "next_line_after_12_bytes_hex": (
                        f"0x{mse_memory_request_address([1, 2, 3], [4, 32, 256], base_addr=0x1000, transfer_bias=12):07x}"
                    ),
                },
                "scope": (
                    "static RD and WR Memory AG address equations. It does not "
                    "prove dynamic outbuffer handshakes or stage-specific "
                    "index-domain coverage"
                ),
            },
            {
                "issue_id": "CDA-MSE-SPLIT-001",
                "classification": "RTL_PROVEN",
                "title": "idx_size defines a power-of-two byte transaction split across 16-byte DDR lines",
                "json_paths": [
                    "$.stream_engine.stream*.idx_size",
                    "$.stream_engine.stream*.buf_spatial_size",
                ],
                "derived_fields": {
                    "dimension_size": (
                        "S[j] = 1 when idx_size[j] is null, otherwise "
                        "idx_size[j] + 1"
                    ),
                    "total_size": "S[0] * S[1] * S[2], encoded in 8 bits",
                    "idx_size_log_json": (
                        "[log2(S0), log2(S0*S1), 0], which becomes the "
                        "corresponding reversed RTL vector"
                    ),
                    "power_of_two_reason": (
                        "Data Channel derives per-lane inner coordinates with "
                        "right shifts and bitwise masks, so each S[j] must be a "
                        "power of two"
                    ),
                },
                "split_equations": {
                    "first_position": "P0 = transaction_bias[3:0]",
                    "first_try_size": "16 - P0",
                    "later_try_size": 16,
                    "final_size": "min(bytes_remaining, try_size)",
                    "valid_mask": (
                        "low16((((1 << final_size) - 1) << "
                        "start_position))"
                    ),
                    "next_transfer_bias": (
                        "current transfer_bias + final_size"
                    ),
                    "partial_flag": "final_size < 16",
                },
                "unaligned_32_byte_example": mse_transfer_plan(4, 32),
                "authorized_corpus_total_sizes": mse_corpus[
                    "derived_total_size_counts"
                ],
                "scope": (
                    "static transaction derivation, line split, size and valid "
                    "mask; first/stall/resume handshake timing remains "
                    "TEST_REQUIRED because of the delayed-valid outbuffers"
                ),
            },
            {
                "issue_id": "CDA-MSE-WR-RMW-001",
                "classification": "RTL_PROVEN",
                "title": "WR MSE performs read-modify-write for partial or tailed DDR lines",
                "trigger": (
                    "transfer_mask_flag = (transfer_size < 16) || "
                    "(any tail/branch lane is outside its inclusive range)"
                ),
                "rtl_sequence": {
                    "full_unmasked_line": (
                        "rw remains 1 and the selected channel emits one direct "
                        "write request"
                    ),
                    "masked_line_step_1": (
                        "accepted transfer changes rw from 1 to 0 while "
                        "capturing the line address, producing a read request"
                    ),
                    "masked_line_step_2": (
                        "upstream address acceptance is held while rw=0; after "
                        "the read request is accepted, the same channel changes "
                        "rw back to 1 and emits the write to the held address"
                    ),
                    "merge": (
                        "new buffer byte is selected only where valid_mask=1 "
                        "and tail_mask=0; every other lane comes from returned "
                        "old DDR data"
                    ),
                },
                "dynamic_risk": (
                    "WR uses the same unreset vld_d and external "
                    "valid=(vld_d||vld) equation as RD. The static RMW "
                    "sequence is proven, but duplicate-request safety under "
                    "ready/stall timing requires a cycle trace"
                ),
            },
            {
                "issue_id": "CDA-MSE-LANE-BOUND-001",
                "classification": "RTL_PROVEN",
                "title": "Padding and tail bounds compare inclusive JSON-order per-byte indexes",
                "json_paths": [
                    "$.stream_engine.stream*.idx_size",
                    "$.stream_engine.stream*.padding_enable",
                    "$.stream_engine.stream*.idx_padding_range",
                    "$.stream_engine.stream*.tailing_enable",
                    "$.stream_engine.stream*.idx_tailing_range",
                ],
                "packing": {
                    "padding_value_bits": 8,
                    "padding_enable_bits": "3 x 1, read only",
                    "padding_bounds_bits": "low[3] + up[3], each 12 bits",
                    "tailing_enable_bits": "3 x 1, read and write",
                    "tailing_bounds_bits": "low[3] + up[3], each 12 bits",
                    "dimension_alignment": (
                        "JSON dimension 0 fields land on RTL element 2, "
                        "dimension 1 on element 1 and dimension 2 on element 0, "
                        "matching the reversed transaction index vector"
                    ),
                },
                "json_order_lane_equations": {
                    "offset": "q = transfer_bias + conceptual_lane",
                    "dim0": "idx0 = low16(base0 + (q & (S0-1)))",
                    "dim1": (
                        "idx1 = low16(base1 + ((q >> log2(S0)) & "
                        "(S1-1)))"
                    ),
                    "dim2": (
                        "idx2 = low16(base2 + ((q >> log2(S0*S1)) & "
                        "(S2-1)))"
                    ),
                    "outside": (
                        "enabled && (idx < low || idx > up); therefore "
                        "low and up are both inclusive"
                    ),
                    "dimension_combine": (
                        "outside flags from the three dimensions are ORed"
                    ),
                },
                "width_boundary": (
                    "per-byte indexes are 16-bit modulo additions while bounds "
                    "are zero-extended 12-bit values; strict target bounds "
                    "therefore stay in 0..4095 and must be explicit only for "
                    "enabled dimensions"
                ),
                "micro_indexes": {
                    "base_10_20_30_size_4x2x1_offset_0": list(
                        mse_lane_indexes(
                            [10, 20, 30],
                            [3, 1, None],
                            transfer_bias=0,
                            lane=0,
                        )
                    ),
                    "base_10_20_30_size_4x2x1_offset_5": list(
                        mse_lane_indexes(
                            [10, 20, 30],
                            [3, 1, None],
                            transfer_bias=0,
                            lane=5,
                        )
                    ),
                },
                "authorized_corpus": padding_tail_corpus,
                "evidence_boundary": (
                    "three authorized read streams enable padding, but all "
                    "authorized streams disable tailing. Tailing equations are "
                    "RTL-proven without an enabled reference sample"
                ),
            },
            {
                "issue_id": "CDA-PADDING-TAIL-DATA-001",
                "classification": "RTL_PROVEN",
                "title": "Padding, tailing, valid-mask shift and reorder select exact RD/WR byte sources",
                "mask_equations": {
                    "conceptual_masks": (
                        "padding/tail comparisons are evaluated for conceptual "
                        "transaction lanes 0..15 at transfer_bias+lane"
                    ),
                    "physical_masks": (
                        "mask_physical = low16(mask_conceptual << "
                        "transfer_start_position)"
                    ),
                    "valid_mask": (
                        "valid physical DDR lanes come only from line split: "
                        "low16(((1<<size)-1)<<position)"
                    ),
                    "rank": (
                        "rank[i] = popcount(valid_mask[0:i]); every valid "
                        "physical lane i is compacted to output rank[i]-1"
                    ),
                },
                "read_selection": {
                    "priority": (
                        "padding_mask ? padding_reg_value : "
                        "tail_mask ? 8'h00 : returned_DDR_byte"
                    ),
                    "reorder": (
                        "valid-mask rank compacts all valid bytes. Padded and "
                        "tailed bytes remain present as replacement data; they "
                        "are not removed from the stream"
                    ),
                    "request_behavior": (
                        "padding/tail does not suppress the Memory AG read "
                        "request, even when all valid bytes are replaced"
                    ),
                },
                "write_selection": {
                    "new_byte_mask": "valid_mask & ~tail_mask",
                    "masked_byte": (
                        "new buffer byte when new_byte_mask=1, otherwise the "
                        "old byte returned by the RMW read"
                    ),
                    "padding": "write stream has no encoded padding fields",
                    "request_behavior": (
                        "a fully tailed line still performs RMW and writes the "
                        "old line back; RTL does not elide the transaction"
                    ),
                },
                "unaligned_overlap_example": mse_boundary_masks(
                    [0, 0, 0],
                    [3, 1, None],
                    transfer_bias=0,
                    start_position=4,
                    valid_mask=0xFFF0,
                    padding_enable=[1, 0, 0],
                    padding_low=[1, None, None],
                    padding_up=[2, None, None],
                    tailing_enable=[0, 1, 0],
                    tailing_low=[None, 0, None],
                    tailing_up=[None, 0, None],
                ),
                "strict_materialization_boundary": (
                    "all three authorized padding examples encode null "
                    "padding_reg_value as zero through BaseConfig. Exact "
                    "references remain correct; derived strict targets must "
                    "make the byte explicit under a hash-bound operator "
                    "padding contract. One authorized legacy write stream also "
                    "contains read-only padding keys and requires explicit "
                    "encoding-equivalent materialization"
                ),
                "dynamic_boundary": (
                    "the byte-selection equations are static and closed. RD "
                    "request/data and WR request/write-data delayed-valid "
                    "outbuffers still require cycle-level first/stall/resume "
                    "proof"
                ),
            },
            {
                "issue_id": "CDA-BUFFER-AG-001",
                "classification": "RTL_PROVEN",
                "title": "Buffer AG expands modulo-32 columns and ping-pong selects only physical buffer banks",
                "json_paths": [
                    "$.stream_engine.stream*.buf_spatial_stride",
                    "$.stream_engine.stream*.buf_spatial_size",
                    "$.stream_engine.stream*.buf_full_last_index",
                    "$.stream_engine.stream*.ping_pong",
                    "$.stream_engine.stream*.pingpong_last_index",
                ],
                "rtl_equations": {
                    "active_lanes": (
                        "request_valid=(1<<buf_spatial_size)-1 over lanes "
                        "0..size-1; encoder reverses the JSON list for MSB-first "
                        "packing, so RTL stride[i] still equals JSON stride[i]"
                    ),
                    "lane_address": (
                        "row_lane=row; col_lane=low5(col+stride[lane]); "
                        "five-bit column overflow wraps within the same row and "
                        "never carries into the two-bit row"
                    ),
                    "bank_decode": (
                        "bank=col_lane[4:2], byte_offset=col_lane[1:0], "
                        "strobe=1<<byte_offset; lanes hitting one bank OR their "
                        "strobes into one 32-bit bank request"
                    ),
                    "collision": (
                        "strict configs require distinct active five-bit "
                        "strides. If exact columns collide, the write-data loop's "
                        "highest numbered lane wins that byte; this alias is not "
                        "an approved generated semantic"
                    ),
                    "read_stream_pingpong": (
                        "request and write-data select the current bank; after "
                        "an accepted last tag with last_index<=threshold, the "
                        "selection toggles for the next request"
                    ),
                    "write_stream_pingpong": (
                        "buffer-read request uses the current selection and "
                        "returned data uses its one-cycle delayed copy, matching "
                        "the synchronous Buffer response"
                    ),
                    "physical_topology": (
                        "only READ_STREAM0 has a real buffer0/buffer1 pair. "
                        "READ_STREAM1/2/3 are fixed to buffer2/3/4; WRITE_STREAM0 "
                        "is fixed to buffer5 and its second selection returns "
                        "ready with zero data"
                    ),
                    "terminal_threshold": (
                        "ping-pong toggles on last && "
                        "last_index<=pingpong_last_index. A read stream also "
                        "raises its NSE-full notification on last && "
                        "last_index<=stream.buf_full_last_index"
                    ),
                },
                "minimal_example": mse_buffer_lane_plan(
                    2,
                    30,
                    [0, 1, 2, 3],
                    spatial_size=4,
                ),
                "authorized_corpus": buffer_corpus,
                "sample_boundary": (
                    "all five enabled authorized ping-pong instances are "
                    "target A/READ_STREAM0, have an explicit inclusive "
                    "threshold and configure identical buffer0/buffer1 pairs"
                ),
            },
            {
                "issue_id": "CDA-BUFFER-MANAGER-001",
                "classification": "RTL_PROVEN",
                "title": "Buffer Manager separates MSE byte ownership from Array row lifetime and dst_port is buffer5 source-only",
                "json_paths": [
                    "$.buffer_config.buffer*.enable",
                    "$.buffer_config.buffer*.dst_port",
                    "$.buffer_config.buffer*.buf_full_last_index",
                    "$.buffer_config.buffer*.buffer_nbr_cnt",
                    "$.buffer_config.buffer*.nbr_enable",
                    "$.buffer_config.buffer*.buffer_life_time",
                    "$.buffer_config.buffer*.mode",
                    "$.buffer_config.buffer*.mask",
                    "$.buffer_config.buffer*.buf_end_row_addr",
                ],
                "bitstream_and_register": {
                    "config_width_bits": 26,
                    "fields_msb_to_lsb": [
                        {"field": "dst_port/buf_src_id", "bits": "[25]", "width": 1},
                        {"field": "buf_full_last_index", "bits": "[24:21]", "width": 4},
                        {"field": "buffer_nbr_cnt", "bits": "[20:16]", "width": 5},
                        {"field": "nbr_enable", "bits": "[15]", "width": 1},
                        {"field": "buffer_life_time-1", "bits": "[14:11]", "width": 4},
                        {"field": "mode", "bits": "[10]", "width": 1},
                        {"field": "mask", "bits": "[9:2]", "width": 8},
                        {"field": "buf_end_row_addr", "bits": "[1:0]", "width": 2},
                    ],
                    "enable": (
                        "enable is not in the 26-bit register. A present buffer "
                        "object defaults enabled; disabled/empty configuration "
                        "drives the configure-port enable low"
                    ),
                    "defaults": (
                        "null/missing buffer_nbr_cnt encodes 27; logical "
                        "buffer_life_time L encodes L-1 and therefore permits "
                        "exactly L visits"
                    ),
                },
                "ownership_and_readiness": {
                    "buffers_0_to_4": (
                        "MSE read streams write bytes into the buffer and the "
                        "Array side reads them. MSE writes wait until every "
                        "requested byte is invalid; Array reads wait until all "
                        "four bytes in every masked bank are valid"
                    ),
                    "buffer_5": (
                        "the selected Array output writes buffer5 and the sole "
                        "write stream consumes it. MSE reads require all "
                        "requested bytes valid and clear exactly their strobed "
                        "valid bits on acceptance"
                    ),
                    "mask": (
                        "buffer_mask is the Array-side active bank set; it gates "
                        "Array all-bank ready/valid, and N2N bank requests. It is "
                        "not the MSE spatial-lane selector"
                    ),
                    "dst_port_correction": (
                        "for buffer5, 0 selects Specialized Array output and 1 "
                        "selects General Array output as the writer. For "
                        "buffers0..4 the field does not select a destination: "
                        "read data is wired to both arrays and downstream "
                        "backpressure is ANDed"
                    ),
                    "buffer_full_threshold": (
                        "on an accepted MSE write, Buffer Manager signals its "
                        "Neighbor manager when last && "
                        "last_index<=buffer.buf_full_last_index. The authorized "
                        "read stream and its mapped buffer use equal thresholds"
                    ),
                },
                "array_traversal": {
                    "mode_0": (
                        "row is inner: for life=0..L-1, visit "
                        "row=0..buf_end_row_addr"
                    ),
                    "mode_1": (
                        "lifetime is inner: for row=0..buf_end_row_addr, repeat "
                        "life=0..L-1"
                    ),
                    "expiration": (
                        "for buffers0..4, the accepted Array read whose "
                        "life_index=L-1 marks that row for clearing; neighbor "
                        "mode can defer the physical clear until local/partner "
                        "completion accounting permits it"
                    ),
                    "examples": {
                        "mode_0_end_row_1_lifetime_2": (
                            buffer_array_request_sequence(
                                mode=0,
                                end_row=1,
                                logical_lifetime=2,
                            )
                        ),
                        "mode_1_end_row_1_lifetime_2": (
                            buffer_array_request_sequence(
                                mode=1,
                                end_row=1,
                                logical_lifetime=2,
                            )
                        ),
                    },
                },
                "dynamic_boundary": (
                    "single-slice Buffer ownership/readiness and the two "
                    "counter equations are static and closed. Multi-slice "
                    "neighbor barriers, finish-count interpretation and N2N "
                    "ping-pong remain assigned to C0-N2N"
                ),
            },
            {
                "issue_id": "CDA-SA-PACK-TOPOLOGY-001",
                "classification": "RTL_PROVEN",
                "title": "SA is a 32-bit config whose three inports bind fixed Buffer pairs and PE axes",
                "json_paths": [
                    "$.special_array.mode",
                    "$.special_array.inport*.enable",
                    "$.special_array.inport*.pingpong_en",
                    "$.special_array.inport*.pingpong_last_index",
                    "$.special_array.inport*.nbr_enable",
                    "$.special_array.data_type",
                    "$.special_array.transout_last_index",
                    "$.special_array.bias_enable",
                    "$.special_array.outport.*",
                ],
                "bitstream_and_register": {
                    "config_width_bits": 32,
                    "fields_msb_to_lsb": [
                        {"field": "mode", "bits": "[31]", "width": 1},
                        {"field": "inport2", "bits": "[30:24]", "width": 7},
                        {"field": "inport1", "bits": "[23:17]", "width": 7},
                        {"field": "inport0", "bits": "[16:10]", "width": 7},
                        {"field": "data_type", "bits": "[9:8]", "width": 2},
                        {"field": "transout_last_index", "bits": "[7:4]", "width": 4},
                        {"field": "bias_enable", "bits": "[3]", "width": 1},
                        {"field": "outport.mode/major", "bits": "[2]", "width": 1},
                        {"field": "fp32tofp16", "bits": "[1]", "width": 1},
                        {"field": "fp32tobf16", "bits": "[0]", "width": 1},
                    ],
                    "inport_subfield": (
                        "each seven-bit inport is "
                        "{enable,pingpong_en,pingpong_last_index[3:0],nbr_enable}"
                    ),
                    "encoder_comment_correction": (
                        "SpecialArrayConfig's 24-bit/5-bit-inport docstring is "
                        "stale; FIELD_MAP and RTL concatenate exactly 32 bits"
                    ),
                    "data_type_encoding": {
                        "int8": "2'b00",
                        "2'b01": "unsupported: no PE pipeline/tag branch",
                        "fp16": "2'b10",
                        "bf16": "2'b11",
                    },
                },
                "mode_and_physical_topology": {
                    "mode": (
                        "gemm encodes 0 and enables all 8x8 PEs; gemv encodes "
                        "1 and enables only PE row 0, all eight columns"
                    ),
                    "inport0": (
                        "source0=buffer0, source1=buffer1; one selected 8-word "
                        "row vector is broadcast across every PE column"
                    ),
                    "inport1": (
                        "source0=buffer2, source1=buffer3; one selected 8-word "
                        "column vector is broadcast across every PE row"
                    ),
                    "inport2": (
                        "source0=buffer4 and source1 is hard zero because "
                        "buffer5 is write-direction; it is column-broadcast. "
                        "Therefore inport2 has no physical ping-pong pair"
                    ),
                },
                "inport_switch_and_tags": {
                    "initial_source": 0,
                    "toggle": (
                        "on sa_enable && pingpong_en && selected_last && "
                        "selected_last_index<=pingpong_last_index && all-PE-ready"
                    ),
                    "pingpong_last_mask": (
                        "with ping-pong enabled, source0 last is suppressed and "
                        "only source1 last can propagate; this hides the first "
                        "half boundary and exposes the second"
                    ),
                    "neighbor_last_mask": (
                        "nbr_enable clears every propagated last bit; N2N must "
                        "supply the later completion boundary"
                    ),
                    "same_mask": (
                        "same is suppressed for one cycle after source selection "
                        "changes"
                    ),
                },
                "authorized_corpus": sa_corpus,
            },
            {
                "issue_id": "CDA-SA-ACCUM-TAG-001",
                "classification": "RTL_PROVEN",
                "title": "SA seeds a 16-entry psum bank from bias or zero and transout compares loop depth",
                "json_paths": [
                    "$.special_array.bias_enable",
                    "$.special_array.transout_last_index",
                    "$.special_array.inport2.*",
                ],
                "operand_and_psum_equations": {
                    "operand_match": (
                        "one MAC launches when inport0.valid && inport1.valid; "
                        "inport2 does not participate in operand matching"
                    ),
                    "bias_disabled": (
                        "the initial port is forced valid with data=0 and "
                        "last_index=15, so every accumulator slot is seeded zero"
                    ),
                    "bias_enabled": (
                        "inport2 valid/data seed the accumulator. Each accepted "
                        "bias word is written to positions p,p+4,p+8,p+12 and "
                        "increments the selected bank count by four, filling all "
                        "16 slots after four handshakes"
                    ),
                    "recurrence": (
                        "each matched A/B pair computes FMA(A,B,stored_psum); the "
                        "result overwrites the current psum slot until a "
                        "transout boundary makes that ping-pong bank readable"
                    ),
                },
                "terminal_equations": {
                    "source_last": (
                        "last=last0||last1; if both assert, last_index0 has "
                        "priority over last_index1"
                    ),
                    "ignore": "last && upstream_last_index>transout_last_index",
                    "matched": "last && upstream_last_index==transout_last_index",
                    "out": "last && upstream_last_index<transout_last_index",
                    "effect": (
                        "equal closes/switches the accumulator bank but does not "
                        "set output last; below closes the bank and propagates "
                        "result_last=1; above continues accumulation"
                    ),
                    "minimal_truth_table": [
                        {
                            "upstream_last_index": index,
                            **sa_transout_decision(
                                upstream_last=True,
                                upstream_last_index=index,
                                transout_last_index=2,
                            ),
                        }
                        for index in (3, 2, 1)
                    ],
                },
                "dynamic_boundary": (
                    "the recurrence, bank-close predicate and terminal tag are "
                    "static RTL equations. The authorized corpus has bias "
                    "disabled in all eight SA samples, so enabled-bias timing "
                    "still needs a focused execution trace"
                ),
            },
            {
                "issue_id": "CDA-SA-INT8-CSA-001",
                "classification": "CONTRADICTED",
                "title": "Current SA INT8 RTL is not the conventional four-lane signed-A times unsigned-B dot product",
                "contradicted_assumption": (
                    "INT8 SA computes "
                    "psum + sum_j(s8(DataA[j]) * u8(DataB[j])) modulo 2^32"
                ),
                "rtl_equation": {
                    "lane_roles": (
                        "DataA bytes [31:24]..[7:0] are converted from signed "
                        "two's-complement to magnitude; DataB bytes are unsigned"
                    ),
                    "products": (
                        "p_j is the 17-bit sign extension of the signed 16-bit "
                        "lane product"
                    ),
                    "csa4": (
                        "(s17,c17)=CSA_4to2(p0,p1,p2,p3), where c17 already "
                        "contains carry_temp<<1"
                    ),
                    "wired_result": (
                        "rtl32 = psum32 + signext32(s17) + "
                        "(signext32(c17)<<1) mod 2^32"
                    ),
                    "defect": (
                        "SA_PE_Mul_Array shifts c17 left a second time in "
                        "last_B; the later CSA_3to2/CLA therefore cannot recover "
                        "the ordinary four-product sum"
                    ),
                },
                "counterexamples": {
                    "four_positive_ones": sa_int8_rtl_trace(
                        [1, 1, 1, 1],
                        [1, 1, 1, 1],
                    ),
                    "four_negative_ones": sa_int8_rtl_trace(
                        [-1, -1, -1, -1],
                        [1, 1, 1, 1],
                    ),
                },
                "project_impact": (
                    "the signed-A/unsigned-B port-role conclusion remains true, "
                    "but it is insufficient to approve ResNet INT8 Conv or "
                    "MatMul arithmetic. Existing project contracts that model a "
                    "normal four-lane dot must remain blocked until the active "
                    "RTL is fixed or a bit-accurate server trace proves a "
                    "different synthesized implementation"
                ),
                "sample_boundary": (
                    "none of the eight user-authorized correct SA references "
                    "uses INT8; all are FP16. Encoder success and layout tests "
                    "therefore do not contradict this RTL-level finding"
                ),
            },
            {
                "issue_id": "CDA-SA-OUTPORT-001",
                "classification": "RTL_PROVEN",
                "title": "SA outport major bit controls transpose, mode controls serialization, and 16-bit conversion packs pairs",
                "json_paths": [
                    "$.special_array.mode",
                    "$.special_array.outport.mode",
                    "$.special_array.outport.fp32tofp16",
                    "$.special_array.outport.fp32tobf16",
                ],
                "routing_and_serialization": {
                    "legacy_label_encoding": "JSON col->major bit 0; row->major bit 1",
                    "major_0": "out[out][source]=PE[out][source], no transpose",
                    "major_1": "out[out][source]=PE[source][out], transpose",
                    "gemm": (
                        "each of eight outports serializes source index 0..7; "
                        "input last propagates only on source 7"
                    ),
                    "gemv": (
                        "the source counter terminates every accepted item and "
                        "therefore consumes source index 0 only"
                    ),
                    "no_conversion": "one 32-bit PE result becomes one output word",
                    "fp16_or_bf16_conversion": (
                        "two converted results share one output word: first "
                        "result in bits[15:0], second in bits[31:16]"
                    ),
                },
                "conversion_conflict": (
                    "if both flags are one, RTL prioritizes fp32tofp16 in both "
                    "exponent selection and data writes; strict JSON forbids "
                    "the ambiguous pair"
                ),
                "authorized_corpus": {
                    "outport_mode_counts": sa_corpus["outport_mode_counts"],
                    "fp32tofp16_counts": sa_corpus["fp32tofp16_counts"],
                    "fp32tobf16_counts": sa_corpus["fp32tobf16_counts"],
                },
            },
            {
                "issue_id": "CDA-SA-FP-CONVERT-001",
                "classification": "CONTRADICTED",
                "title": "SA FP32 narrowing is not a complete IEEE round-to-nearest-even conversion",
                "fp16_equation": {
                    "overflow": "FP32 exponent>=0x8f becomes signed infinity with zero fraction",
                    "underflow": (
                        "FP32 exponent<=0x70 becomes signed zero; the implemented "
                        "subnormal path is commented out"
                    ),
                    "normal": (
                        "keep fraction[22:13], guard=fraction[12], "
                        "sticky=OR(fraction[11:0]); round nearest-even"
                    ),
                },
                "bf16_equation": (
                    "keep exponent, fraction[22:16], guard=fraction[15], "
                    "sticky=OR(fraction[14:0]); round nearest-even"
                ),
                "shared_corner_defect": (
                    "exponent increments only when kept_fraction_is_all_ones && "
                    "guard && sticky. At an exact halfway tie with an odd all-one "
                    "kept fraction, the fraction rounds to zero but the exponent "
                    "does not increment"
                ),
                "counterexamples": [
                    {
                        "target": "fp16",
                        "fp32_bits": "0x3ffff000",
                        "rtl_bits": (
                            f"0x{sa_fp32_output_conversion(0x3FFFF000, 'fp16'):04x}"
                        ),
                        "ieee_rne_bits": "0x4000",
                    },
                    {
                        "target": "bf16",
                        "fp32_bits": "0x3fff8000",
                        "rtl_bits": (
                            f"0x{sa_fp32_output_conversion(0x3FFF8000, 'bf16'):04x}"
                        ),
                        "ieee_rne_bits": "0x4000",
                    },
                ],
                "sample_boundary": (
                    "four authorized SA references enable FP32-to-FP16 and none "
                    "enable BF16 narrowing. Their configuration correctness does "
                    "not prove exhaustive numerical behavior at the contradicted "
                    "tie or subnormal corners"
                ),
            },
            {
                "issue_id": "CDA-GA-PACK-ROUTE-001",
                "classification": "RTL_PROVEN",
                "title": "GA config widths and all physical input, PE-neighbor and output selectors are exact",
                "json_paths": [
                    "$.general_array.inport.inport*",
                    "$.general_array.PE_array.PE**.inport*.src_id",
                    "$.general_array.outport",
                ],
                "packing": {
                    "inport": (
                        "20 bits: mask[19:12], src_id[11], pingpong[10], "
                        "threshold[9:6], nbr[5], fp16[4], bf16[3], "
                        "int32fp[2], uint8fp[1], uint8int32[0]"
                    ),
                    "outport": (
                        "12 bits: mask[11:4], src_id[3], fp16[2], "
                        "bf16[1], int32uint8[0]"
                    ),
                    "pe": (
                        "144 bits in four 36-bit beats. Beat0 is opcode5, "
                        "transout4 and three {src3,keep4,mode2} ports; beats1..3 "
                        "are {pad4,constant32} for ports0..2"
                    ),
                    "mode_encoding": {
                        "null": 0,
                        "buffer": 1,
                        "keep": 2,
                        "constant": 3,
                    },
                    "null_transout_encoding": 15,
                },
                "routing": {
                    "ga_input_src0": "physical Buffer pair selected by the inport ping-pong state",
                    "ga_input_src1": "SA outport source0; ping-pong cannot switch this source",
                    "pe_src0": (
                        "external GA input index row + 4*floor(col/2), shared by "
                        "each two-column half"
                    ),
                    "pe_src1_to_5": ["northwest", "north", "northeast", "west", "east"],
                    "outport": (
                        "ports0..3 select rows0..3 from global column src_id 0/1; "
                        "ports4..7 select rows0..3 from column src_id 2/3"
                    ),
                },
                "authorized_corpus": ga_corpus,
            },
            {
                "issue_id": "CDA-GA-OPCODE-OPERAND-001",
                "classification": "RTL_PROVEN",
                "title": "GA opcode names decode to fixed A/B/C equations and SFU placement",
                "equations": {
                    "add_0": "A+B",
                    "sub_1": "A-B",
                    "mul_2": "A*B",
                    "max_3": "max_fp32(A,C)",
                    "sum_4": "A+C, with transout self-accumulation",
                    "summac_5": "A*B+C, with transout self-accumulation",
                    "mac_6": "A*B+C",
                    "int8_max_11": (
                        "bytewise comparator between A and C; its current select "
                        "polarity is contradicted separately"
                    ),
                    "int32_sum_12": "A+C, with transout self-accumulation",
                    "int32_sub_13": "A-B",
                    "int32_mac_14": "A*B+C",
                    "sfu_17_18_20_24": (
                        "normalize A for breakpoint search, select LUT slope/"
                        "intercept, execute x_norm*slope+intercept, then restore "
                        "reciprocal/sqrt/reciprocal-sqrt exponent or return the "
                        "activation affine result"
                    ),
                },
                "required_operands": {
                    "A_B": ["add", "sub", "mul", "int32_sub"],
                    "A_C": ["max", "sum", "int32_sum"],
                    "A_B_C": ["summac", "mac", "int32_mac"],
                    "A_only": ["rec", "sqrt", "rec_sqrt", "sfu_activation"],
                    "A_with_internal_C_seed": [
                        "int8_max: C is forced to zero initially and then fed "
                        "from the transout outbuffer"
                    ],
                },
                "nonnumeric_enabled_port_rule": (
                    "an operand ignored by the arithmetic may still be enabled "
                    "as an intentional matching/backpressure dependency; the "
                    "authorized four-slice remote-sum reference does this on B"
                ),
                "sfu_topology": (
                    "only PE columns1 and3 instantiate GA_SFU_PE. Columns0 and2 "
                    "force sfu_compute_en=0 and cannot implement opcode>=16"
                ),
                "sample_boundary": ga_corpus["sample_boundary"],
            },
            {
                "issue_id": "CDA-GA-INPORT-CONVERT-001",
                "classification": "CONTRADICTED",
                "title": "GA input serialization is exact, but INT32-to-FP32 has two swapped extreme-value failures",
                "serialization": {
                    "fp16_or_bf16": (
                        "two outputs per word, low half first; last only on high half"
                    ),
                    "int32tofp32": "one output per word",
                    "uint8tofp32_or_int32": (
                        "four outputs per word in byte order [7:0],[15:8],"
                        "[23:16],[31:24]; last only on byte3"
                    ),
                    "flag_priority": (
                        "fp16 > bf16 > int32fp > uint8fp > uint8int32; strict "
                        "JSON rejects multiple enabled flags"
                    ),
                },
                "defect": (
                    "negative magnitude discards the sign bit, while the special "
                    "minimum detector is '&input' and therefore recognizes "
                    "0xffffffff (-1), not 0x80000000 (INT_MIN)"
                ),
                "counterexamples": [
                    {
                        "input": "0xffffffff (-1)",
                        "rtl_bits": f"0x{ga_int32_to_fp32_rtl_result(0xFFFFFFFF):08x}",
                        "expected_bits": "0xbf800000",
                        "trace": ga_int32_to_fp32_rtl_trace(0xFFFFFFFF),
                    },
                    {
                        "input": "0x80000000 (INT_MIN)",
                        "rtl_bits": f"0x{ga_int32_to_fp32_rtl_result(0x80000000):08x}",
                        "expected_bits": "0xcf000000",
                        "trace": ga_int32_to_fp32_rtl_trace(0x80000000),
                    },
                ],
                "project_impact": (
                    "do not approve a general signed INT32-to-FP32 contract. "
                    "The sole authorized use proves only its exact observed input "
                    "domain, not these extreme patterns"
                ),
            },
            {
                "issue_id": "CDA-GA-TRANSOUT-OUTPORT-001",
                "classification": "RTL_PROVEN",
                "title": "GA terminal comparison, reduction flush, output routing and packing are exact",
                "terminal": {
                    "ordinary_result_last": "buffer_last && buffer_last_index < T",
                    "reduction_opcodes": [
                        "max",
                        "sum",
                        "summac",
                        "int8_max",
                        "int32_sum",
                    ],
                    "flush_trigger": "reduction && buffer_last && buffer_last_index <= T",
                    "flush_cycles": {"fp32_or_sfu": 8, "int32": 4, "int8": 1},
                    "final_tag": (
                        "after flush, valid and last are forced for one cycle; "
                        "last_index is retained from the outbuffer entry"
                    ),
                    "equal_boundary": ga_transout_decision(
                        reduction_opcode=True,
                        upstream_last=True,
                        upstream_last_index=3,
                        transout_last_index=3,
                    ),
                },
                "operand_modes": {
                    "buffer": "consume and release normally",
                    "keep": (
                        "retain until some buffer carrier ends with "
                        "last_index<=keep threshold"
                    ),
                    "constant": "sign-extend the configured 32-bit pattern and never request upstream",
                    "null": "disable the operand valid gate",
                },
                "output_conversion": {
                    "none": "one result per 32-bit word",
                    "fp16_or_bf16": "two converted results pack low16 then high16",
                    "int32touint8": (
                        "signed saturate to [0,255], four results pack from low "
                        "byte to high byte"
                    ),
                    "fp_narrowing": (
                        "same exponent/subnormal/exact-half limitations as the "
                        "SA converter; both modules contain the same equations"
                    ),
                },
            },
            {
                "issue_id": "CDA-GA-INT8-MAX-PIPE-001",
                "classification": "CONTRADICTED",
                "title": "GA int8_max is both numerically inverted and unable to accept a second item",
                "numeric_equation": (
                    "for each unsigned byte lane, the current final select returns "
                    "min(A_lane,C_lane), not max(A_lane,C_lane)"
                ),
                "numeric_counterexample": {
                    "A": "0x04030201",
                    "C": "0x01020304",
                    "rtl": f"0x{ga_int8_max_rtl_result(0x04030201, 0x01020304):08x}",
                    "expected_unsigned_max": "0x04030304",
                },
                "flow_equation": (
                    "alu_pipeline0_bp_post=(is_int32&&downstream)||"
                    "(is_fp32&&pipeline1_enable). For int8_max both terms are "
                    "zero; after the first valid item pipeline0_enable becomes "
                    "zero and cannot clear or accept the second item"
                ),
                "dynamic_scope": (
                    "both native UINT8 MaxPool references reproduce reads and "
                    "write-address requests but no write data/natural completion. "
                    "The exact server RTL identity and a fixed-build rerun remain "
                    "separate dynamic requirements"
                ),
                "evidence_report": (
                    "contracts/ga_int8_pipeline_backpressure_defect_report_20260723.md"
                ),
                "project_impact": (
                    "all GA UINT8 MaxPool/int8_max promotion remains blocked. "
                    "Changing only the ready path would still leave the min/max "
                    "polarity defect"
                ),
            },
            {
                "issue_id": "CDA-N2N-ROUTE-TRANSFER-001",
                "classification": "RTL_PROVEN",
                "title": "N2N selectors choose fixed low/high rings and mem_loop controls full-row material transfers",
                "packing": (
                    "8 bits: src_slice_sel[7], dst_slice_sel[6], ping_pong[5], "
                    "nse_cnt_size[4:0]=mem_loop-1"
                ),
                "route": {
                    "selector0": (
                        "receive from LOW_PREV_MAP and use LOW_NEXT_MAP ready; "
                        "the map is one 28-slice ring"
                    ),
                    "selector1": (
                        "receive from HIGH_PREV_MAP and use HIGH_NEXT_MAP ready; "
                        "the map is seven four-slice rings"
                    ),
                    "endpoint_contract": (
                        "src_slice_sel chooses the incoming predecessor, while "
                        "dst_slice_sel chooses which next-neighbor ready controls "
                        "the outgoing stream. A coherent ring requires compatible "
                        "selectors on every participating slice"
                    ),
                    "examples": {
                        "slice0_low": {
                            "previous": n2n_neighbor(0, 0, "previous"),
                            "next": n2n_neighbor(0, 0, "next"),
                        },
                        "slice0_high": {
                            "previous": n2n_neighbor(0, 1, "previous"),
                            "next": n2n_neighbor(0, 1, "next"),
                        },
                    },
                },
                "transfer": {
                    "count": "mem_loop L performs L-1 neighbor transfers",
                    "each_transfer": (
                        "addresses rows0,1,2,3; each row carries 256 data bits, "
                        "32 valid bits, tag, same and ready/valid flow control"
                    ),
                    "stream0_buffers": "read buffer0/write buffer1, then alternate",
                    "stream1_buffers": "read buffer2/write buffer3, then alternate",
                    "barrier": (
                        "MSE is blocked while either independent incoming-write "
                        "or outgoing-read controller count is nonzero"
                    ),
                    "four_slice_example": n2n_transfer_plan(4),
                },
                "authorized_corpus": n2n_corpus,
            },
            {
                "issue_id": "CDA-N2N-PINGPONG-LIFETIME-001",
                "classification": "CONTRADICTED",
                "title": "N2N ping_pong is a decoded but unused bit, config persists, and handoff is not zero-copy",
                "ping_pong": {
                    "json_claim": "ping_pong selects whether alternating buffers are used",
                    "rtl_fact": (
                        "nse_pingpong_enable is decoded but its connection into "
                        "Neighbor_Stream_Engine is commented out. In/out selectors "
                        "toggle unconditionally on every MSE trigger and full "
                        "four-row completion"
                    ),
                    "initial_transfer": (
                        "outgoing selector resets to buffer1 then trigger toggles "
                        "to buffer0; incoming selector resets to buffer0 then "
                        "trigger toggles to buffer1"
                    ),
                    "strict_rule": (
                        "enabled N2N must encode ping_pong=1 to describe the "
                        "hard-wired behavior; zero is rejected as semantically false"
                    ),
                },
                "config_lifetime": (
                    "nse_enable is not cleared when the controller finishes. It "
                    "persists until reset, slice_rst or se_nse_configure_clear. A "
                    "disabled config beat clears the config register but has no "
                    "symmetric nse_enable<=0 branch"
                ),
                "handoff": (
                    "the engine issues real local buffer reads, transmits four "
                    "256-bit rows, and writes the partner buffer. This is a "
                    "buffer-to-buffer material copy/rotation, not pointer aliasing "
                    "or zero-copy ownership transfer"
                ),
                "project_impact": (
                    "cross-stage reuse must prove a configure-clear/reconfigure "
                    "boundary and matching neighbor-enabled physical pair. Do not "
                    "derive a local/ring transform by adding only $.n2n"
                ),
                "sample_boundary": n2n_corpus["sample_boundary"],
            },
            {
                "issue_id": "CDA-GAP-D-INDEX-001",
                "classification": "CONTRADICTED",
                "title": "Current GAP D index carrier cannot cover the typed output",
                "stage_intent": {
                    "request_id": GAP_REQUEST_ID,
                    "output_shape": [16, 2048, 1, 1],
                    "output_dtype": "int32",
                    "per_active_slice": "one batch sample",
                    "required_channel_blocks": 256,
                },
                "json_chain": [
                    "LC2 local domain is [0,1) => {0}",
                    "PE1 is LC2 * constant(1) => {0}",
                    "D stream idx[0]=PE1 and dim_stride[0]=32",
                    "one 32-byte C8 output transaction base is reachable",
                ],
                "coverage_diagnostic": coverage,
                "dynamic_confirmation": {
                    "sim6_write_request_count": 512,
                    "sim6_unique_request_addresses_128bit": [
                        "0x001884",
                        "0x001885",
                    ],
                    "occurrences_per_unique_address": 256,
                },
                "impact": {
                    "stage_backend": (
                        "must fail closed with "
                        f"{GAP_D_INDEX_BLOCKER} until a new explicit "
                        "0..255 numeric index carrier is proven"
                    ),
                    "generic_validator": (
                        "schema/topology/terminal checks passing do not prove "
                        "typed output address-domain coverage"
                    ),
                    "invalidated_outputs": [
                        GAP_CONFIG_PATH,
                        "configs/stage_codegen/hwop-0071-00-v1/config.json",
                        "configs/stage_codegen/"
                        "hwop-0071-00-native-address-bound-v1/config.json",
                        "artifacts/operator_config_validation/"
                        "r5-server-candidates/gap-hwop0071-sum-v1/**",
                        "artifacts/operator_config_validation/"
                        "r5-server-workloads/gap_hwop0071_sum_graph/**",
                    ],
                    "regeneration": (
                        "all derived mapping/bitstream/execplan/package "
                        "artifacts require a new identity after the schedule fix"
                    ),
                    "other_generators": (
                        "current Conv generators use src_id as trigger chains "
                        "and create separate local-value roots where equal "
                        "numeric branches are needed; no direct numeric "
                        "inheritance was found, but their full semantics remain "
                        "under their existing blockers"
                    ),
                    "resnet133": (
                        "the exact GAP-sum stage is blocked; other stages are "
                        "not automatically invalidated, but every derived LC "
                        "numeric carrier must be audited independently"
                    ),
                },
            },
            {
                "issue_id": "CDA-MSE-RD-VALID-001",
                "classification": "RTL_PROVEN",
                "title": "RD Memory AG can expose one stale-valid cycle after clear",
                "json_paths": [
                    "$.stream_engine.stream*.mode",
                    "$.stream_engine.stream*.idx",
                    "$.stream_engine.stream*.idx_size",
                    "$.stream_engine.stream*.dim_stride",
                    "$.stream_engine.stream*.address_remapping",
                    "$.stream_engine.stream*.base_addr",
                ],
                "rtl_effect": {
                    "enqueue": (
                        "selected empty channel captures mem_ag_ob_addr_in "
                        "when transfer_addr_valid is asserted"
                    ),
                    "clear": "vld && downstream ready clears current vld",
                    "delay": "vld_d <= previous vld every cycle",
                    "delay_register_reset": (
                        "vld_d has no explicit reset branch; startup convergence "
                        "depends on clocking after current vld is reset"
                    ),
                    "external_valid": "vld_d || vld",
                    "replay_precondition": (
                        "after a ready clear, current vld=0 and vld_d=1 can "
                        "present the stored address for one additional cycle"
                    ),
                    "accepted_replay_condition": (
                        "the same channel's downstream ready must also be 1 "
                        "during that delayed-only cycle"
                    ),
                    "configurability": (
                        "no JSON/register bit disables vld_d; JSON determines "
                        "the address sequence but not this control equation"
                    ),
                    "downstream_path": (
                        "Stream_Engine_Connect and slice2hub_crossbar pass "
                        "valid/address and ready directly to the Datahub "
                        "valid/ready arbitration path"
                    ),
                },
                "scope": (
                    "generic replay precondition in the bound read Memory AG; "
                    "not proof that the sim6 mismatches used this condition"
                ),
            },
            {
                "issue_id": "CDA-MSE0-RD-REPLAY-001",
                "classification": "CONTRADICTED",
                "title": "probe_v4/v5 overturn the sim6 MSE0 replay attribution",
                "superseded_claim": (
                    "the cross-channel positional sequence mismatch and TB-derived "
                    "IssueCh/IssueTime association identified an accepted vld_d "
                    "address replay or MSE0 payload/metadata mismatch"
                ),
                "replacement_facts": {
                    "request_occurrence_expected": 8960,
                    "request_occurrence_actual": 8960,
                    "missing_request_occurrences": 0,
                    "extra_request_occurrences": 0,
                    "deep_enqueue_to_local_request_compared": 256,
                    "deep_enqueue_to_local_request_mismatches": 0,
                    "ddr_return_payload_associated": 8960,
                    "ddr_return_payload_mismatches": 0,
                    "metadata_consume_window_events": 256,
                    "metadata_address_mismatches": 0,
                    "metadata_payload_mismatches": 0,
                },
                "reason": (
                    "the two physical channels may interleave in different global "
                    "orders. Per-channel FIFO association is the correct carrier "
                    "identity and it matches throughout the measured MSE0 path"
                ),
                "scope": (
                    "contradicts the GAP-specific sim6 replay attribution, not the "
                    "generic RTL fact that delayed valid can be exposed after clear"
                ),
                "evidence": [
                    GAP_PROBE_V4_ANALYSIS_PATH,
                    GAP_PROBE_V4_NUMERIC_PATH,
                    GAP_PROBE_V4_DIAGNOSIS_PATH,
                    GAP_PROBE_V5_ANALYSIS_PATH,
                ],
            },
            {
                "issue_id": "CDA-GAP-GA-ACCUM-STATE-001",
                "classification": "CONTRADICTED",
                "title": "Current GAP execution loses numerical state before the second GA output block",
                "dynamic_boundary": {
                    "block0_time_ps": 700313000,
                    "block0_packed_output": [330, 113, 710, 43, 1560, 106, 124, 57],
                    "block0_matches_golden": True,
                    "block1_time_ps": 700388000,
                    "block1_packed_actual": [187, 193, 429, 156, 929, 111, 75, 34],
                    "block1_packed_golden": [59, 407, 237, 436, 424, 198, 22, 7],
                    "first_known_wrong_boundary": (
                        "GA final accumulation operands for C8 block1"
                    ),
                    "full_int32_match_count": 10,
                    "full_int32_mismatch_count": 2038,
                },
                "proven_downstream": {
                    "mse4_request_handshakes": 512,
                    "mse4_write_data_handshakes": 512,
                    "old_511_count_was_monitor_loss": True,
                    "mse4_packing_matches_ga_input0_plus_input2": True,
                    "ga_integer_add_matches_supplied_operands": True,
                },
                "dynamic_root_cause": {
                    "classification": (
                        "ga_int32_sum_outbuffer_count_underflow_then_"
                        "invalid_slot_reuse"
                    ),
                    "outbuffer_depth": 2,
                    "underflow_transition_count": 8,
                    "first_transition": "700313000->700316000 ps count 1->3",
                    "invalid_slot_c_reuse_count": 217,
                    "first_reuse_time_ps": 700318000,
                },
                "rule_ids": [
                    "CDA-GA-OUTBUFFER-OCCUPANCY-001",
                    "CDA-GA-INVALID-SLOT-ISOLATION-001",
                    "CDA-GA-CROSS-BLOCK-INIT-001",
                    "CDA-GAP-ORTHOGONAL-DEFECTS-001",
                    "CDA-GAP-D-READBACK-COVERAGE-001",
                    "CDA-MSE4-MONITOR-EVIDENCE-001",
                    "CDA-SERVER-FOCUSED-IDENTITY-001",
                ],
                "independent_config_failure": {
                    "classification": "CONFIG_SEMANTICS",
                    "mse4_request_count": 512,
                    "unique_d_address_count": 2,
                    "slice_count": 16,
                    "expected_lines_per_slice": 512,
                    "released_by_ga_fix": False,
                },
                "rtl_identity": {
                    "server_local_critical_file_match_count": 14,
                    "server_local_critical_file_total": 14,
                    "github_differences_relevant_to_non_sfu_gap": False,
                    "static_local_rtl_analysis_allowed": True,
                },
                "project_impact": (
                    "GlobalAverageSumInt32 must carry "
                    f"{GAP_GA_ACCUM_STATE_BLOCKER}; fixing the independent D-index "
                    "carrier is necessary but cannot make this stage numerically "
                    "compatible"
                ),
                "next_action": (
                    "keep RTL_CONTROL and CONFIG_SEMANTICS blockers orthogonal; "
                    "require a functional RTL fix for GA and complete per-slice "
                    "512-line D coverage plus golden before release"
                ),
                "evidence": [
                    GAP_PROBE_V5_ANALYSIS_PATH,
                    GAP_RTL_IDENTITY_ANALYSIS_PATH,
                    GAP_PROBE_V7_DIAGNOSIS_PATH,
                    GAP_PROBE_V7_ANALYSIS_PATH,
                    GAP_PROBE_V7_NUMERIC_PATH,
                    GAP_PROBE_V7_ACCEPTANCE_PATH,
                ],
            },
        ],
        "next_audit": {
            "ledger_id": "C1-DYNAMIC-CONFORMANCE",
            "fields": [
                "GAP block0/block1 Buffer-to-GA and accumulator-state equation",
                "generic MSE first/stall/resume conformance",
                "GA floating-point and LUT numerical conformance",
                "fixed-build GA int8_max rerun",
                "N2N multi-stage clear/reconfigure sequence",
            ],
            "reason": (
                "All requested LC_PE, MSE static, padding/tail, buffer, SA, GA "
                "and N2N JSON-to-RTL equation groups are now closed or carry an "
                "explicit contradiction. Remaining work requires cycle traces, "
                "active-build identity or numerical conformance evidence"
            ),
        },
        "contract_sha256": "",
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_stage_operator_semantics_audit(
    project_root: Path,
    contract_path: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    checked = _load_object(contract_path.resolve())
    rebuilt = build_stage_operator_semantics_audit(root)
    if checked != rebuilt:
        raise StageOperatorSemanticsAuditError(
            "checked stage/operator semantics audit is stale or tampered"
        )
    return checked


def write_stage_operator_semantics_audit(
    project_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    value = build_stage_operator_semantics_audit(project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return value


__all__ = [
    "CONTRACT_PATH",
    "GAP_D_INDEX_BLOCKER",
    "GAP_GA_ACCUM_STATE_BLOCKER",
    "GA_INT8_MAX_FLOW_BLOCKER",
    "GA_INT8_MAX_NUMERIC_BLOCKER",
    "GA_INT32_TO_FP32_DOMAIN_BLOCKER",
    "N2N_CONFIG_LIFETIME_BLOCKER",
    "SA_INT8_CSA_NUMERIC_BLOCKER",
    "SCHEMA",
    "StageOperatorSemanticsAuditError",
    "analyze_gap_d_index_coverage",
    "buffer_array_request_sequence",
    "build_stage_operator_semantics_audit",
    "ga_int32_to_fp32_rtl_result",
    "ga_int32_to_fp32_rtl_trace",
    "ga_int8_max_rtl_result",
    "ga_transout_decision",
    "lc_pe_int_result",
    "mse_buffer_lane_plan",
    "mse_boundary_masks",
    "mse_lane_indexes",
    "mse_memory_request_address",
    "mse_transfer_plan",
    "n2n_neighbor",
    "n2n_transfer_plan",
    "require_gap_d_index_coverage",
    "sa_fp32_output_conversion",
    "sa_int8_rtl_result",
    "sa_int8_rtl_trace",
    "sa_transout_decision",
    "validate_stage_operator_semantics_audit",
    "write_stage_operator_semantics_audit",
]
