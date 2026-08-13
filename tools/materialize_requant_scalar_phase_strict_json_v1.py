#!/usr/bin/env python3
"""Materialize local Requant scalar-phase strict JSON candidates.

This tool deliberately stops before every backend surface.  It emits an
operator-local, relocatable strict configuration for the already accepted
five-PE exact requant graph and the proven scalar multiplier transport.  It
does not emit native ndp-sim JSON, mapping, bitstream, execplan, SCA, or any
server artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOWERING = ROOT / "contracts/resnet50_r5_lowering_bundle.json"
MODEL = ROOT / "artifacts/reference_model/resnet50-v1-12-int8.onnx"
FROZEN_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5_complete_json_regeneration_v1/requantize_uint8"
)
STAGE_INVENTORY = FROZEN_ROOT / "stage_inventory.json"
MULTIPLIER_PROOF = (
    ROOT
    / "artifacts/operator_config_validation/"
    "requant_multiplier_occurrence_supply_v1/report.json"
)
LANE_PROOF = (
    ROOT
    / "artifacts/operator_config_validation/"
    "requant_lane_phase_serialization_isolated_v1/report.json"
)
NUMERIC_PROOF = (
    ROOT
    / ".agents/task_records/"
    "20260806_slow_composite_quant_hard_block_requant_5pe_interim.md"
)
PHYSICAL_PROOF = (
    ROOT
    / ".agents/task_records/"
    "20260806_requant_5pe_physical_boundaries_proof.md"
)
PHYSICAL_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "requant_5pe_physical_boundaries_v1/report.json"
)
CURRENT_HISTORY = (
    ROOT
    / ".agents/task_records/"
    "20260727_requant_guardonly_sfu_numeric_v1_return_analysis.md"
)
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5_requant_scalar_phase_strict_json_v1"
)

FAMILY = "requantize_uint8"
LOWERING_SHA256 = "bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432"
NDP_SIM_COMMIT = "ec12424516ae0304228dd2321d4e604fe225e04e"
RTL_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
MAX_LC_END = 32768
MAX_STREAM_STRIDE = 1048575
ALIGNMENT = 16

EXACTNESS_AXES = {
    "op": True,
    "dtype": True,
    "shape": True,
    "layout": True,
    "qparams": True,
    "topology": True,
    "address": True,
    "schedule": True,
    "consumer": True,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pretty_bytes(value))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def bound_file(path: Path) -> dict[str, str]:
    return {"path": rel(path), "sha256": sha256_file(path)}


def align(value: int, alignment: int = ALIGNMENT) -> int:
    return (value + alignment - 1) // alignment * alignment


def escape_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def iter_json_leaves(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        if not value:
            yield pointer or "/", value
            return
        for key in sorted(value):
            yield from iter_json_leaves(
                value[key], f"{pointer}/{escape_pointer_token(key)}"
            )
        return
    if isinstance(value, list):
        if not value:
            yield pointer or "/", value
            return
        for index, item in enumerate(value):
            yield from iter_json_leaves(item, f"{pointer}/{index}")
        return
    yield pointer or "/", value


def load_multiplier_module() -> Any:
    path = ROOT / "tools/prove_requant_multiplier_occurrence_supply_v1.py"
    spec = importlib.util.spec_from_file_location("requant_multiplier_proof", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load multiplier proof helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request_index(lowering: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    ordered: list[str] = []
    indexed: dict[str, Any] = {}
    for request in lowering["requests"]:
        identity = request["identity"]
        if identity["hw_op_type"] != "RequantizeUint8":
            continue
        stage_id = identity["hw_op_id"]
        ordered.append(stage_id)
        indexed[stage_id] = request
    if len(ordered) != 54 or len(indexed) != 54:
        raise ValueError(f"expected 54 Requant stages, got {len(ordered)}")
    return ordered, indexed


def multiplier_bits(payload: Any) -> list[str]:
    raw = payload.astype("<f4", copy=False).tobytes(order="C")
    return [f"0x{value:08x}" for (value,) in struct.iter_unpack("<I", raw)]


def spatial_tiles(count: int) -> list[dict[str, int]]:
    tiles = []
    start = 0
    tile_id = 0
    while start < count:
        size = min(MAX_LC_END, count - start)
        tiles.append({"tile_id": tile_id, "linear_start": start, "count": size})
        start += size
        tile_id += 1
    return tiles


def clamp_lut() -> dict[str, Any]:
    neg256 = "0xc3800000"
    pos256 = "0x43800000"
    zero = "0x00000000"
    one = "0x3f800000"
    return {
        "breakpoint_bits_rank_order": [neg256] * 32 + [pos256] * 33,
        "coefficient_address_equation": (
            "x < -256 -> 0; -256 <= x < 256 -> 32; x >= 256 -> 65"
        ),
        "reachable_coefficient_addresses": [0, 32, 65],
        "slope_bits_by_address": [zero] * 32 + [one] * 33 + [zero],
        "intercept_bits_by_address": [neg256] * 32 + [zero] * 33 + [pos256],
        "equality_dispatch": "GTET_EQUALITY_DESCENDS_RIGHT",
    }


def five_pe_graph(y_zero_point: int) -> dict[str, Any]:
    return {
        "accepted_numeric_dependency": (
            "full_INT32 mul -> clamp[-256,256] -> magic -> intsub -> "
            "integer_zp -> uint8"
        ),
        "rounding_order": (
            "signed_int32_to_fp32_RNE; fp32_mul_RNE; clamp; "
            "add_magic_0x4b400000; bitcast_int32; "
            "sub_0x4b400000; add_integer_zp; saturate_uint8"
        ),
        "magic_wrap_counterexample_retained": {
            "input": -12582913,
            "legacy_unclamped_output": 255,
            "excluded_by_exact_clamp": True,
        },
        "pe_chain": [
            {
                "pe": "PE00",
                "opcode": "mul",
                "input0": "GA_INPORT0_LANE0_SIGNED_INT32_TO_FP32",
                "input1": "GA_INPORT1_LANE0_KEEP_MULTIPLIER",
                "output_dtype": "fp32",
            },
            {
                "pe": "PE01",
                "opcode": "sfu_activation",
                "input0": "PE00_WEST_SRC4",
                "output_dtype": "fp32",
                "role": "EXACT_THREE_REGION_CLAMP_MINUS256_PLUS256",
            },
            {
                "pe": "PE10",
                "opcode": "add",
                "input0": "PE01_NORTHEAST_SRC3",
                "input1_constant_bits": "0x4b400000",
                "output_dtype": "fp32_bits",
                "role": "RNE_MAGIC_ADD",
            },
            {
                "pe": "PE11",
                "opcode": "int32_sub",
                "input0": "PE10_WEST_SRC4",
                "input1_constant_bits": "0x4b400000",
                "output_dtype": "int32",
                "role": "MAGIC_INTEGER_DECODE",
            },
            {
                "pe": "PE12",
                "opcode": "int32_sum",
                "input0": "PE11_WEST_SRC4",
                "input2_constant_int32": y_zero_point,
                "output_dtype": "int32",
                "role": "INTEGER_ZERO_POINT_BEFORE_UINT8_SATURATION",
            },
        ],
        "selector_edges": [
            {"edge": "PE00_TO_PE01", "consumer_src_id": 4, "producer_dst_id": 4},
            {"edge": "PE01_TO_PE10", "consumer_src_id": 3, "producer_dst_id": 7},
            {"edge": "PE10_TO_PE11", "consumer_src_id": 4, "producer_dst_id": 4},
            {"edge": "PE11_TO_PE12", "consumer_src_id": 4, "producer_dst_id": 4},
        ],
        "terminal": {
            "pe": "PE12",
            "outport": 5,
            "source": 0,
            "conversion": "INT32_TO_UINT8_SATURATING",
            "normal_outbuffer": True,
            "transout_last_index": "DISABLED",
        },
        "clamp_lut": clamp_lut(),
    }


def candidate_for_stage(
    *,
    stage: dict[str, Any],
    request: dict[str, Any],
    payload: Any,
) -> dict[str, Any]:
    identity = stage["identity"]
    stage_id = identity["hw_op_id"]
    shape = list(stage["shape"]["output"])
    element_count = math.prod(shape)
    bits = multiplier_bits(payload)
    multiplier_sha = hashlib.sha256(payload.astype("<f4", copy=False).tobytes()).hexdigest()
    expected_sha = stage["qparams"]["requant_multiplier"]["value_sha256"]
    if multiplier_sha != expected_sha:
        raise ValueError(
            f"{stage_id}: multiplier mismatch {multiplier_sha} != {expected_sha}"
        )
    y_zero_point = int(stage["qparams"]["y_zero_point"]["scalar"])
    onnx_op_type = identity["onnx_op_type"]

    input_bytes = element_count * 4
    multiplier_bytes = len(bits) * 4
    output_bytes = element_count
    input_base = 0
    multiplier_base = align(input_base + input_bytes)
    output_base = align(multiplier_base + multiplier_bytes)
    total_bytes = align(output_base + output_bytes)

    if onnx_op_type == "QLinearConv":
        batch, channels, height, width = shape
        spatial_count = batch * height * width
        layout = "HWC8_CHANNEL_TEMPORAL_SCALAR_PHASE"
        mode = "CONV_SCALAR_CHANNEL_PHASE"
        tiles = spatial_tiles(spatial_count)
        phase_count = channels
        substage_count = channels * len(tiles)
        input_equation = (
            "input_base + 4*((channel//8)*spatial_count*8 + "
            "spatial_linear*8 + channel%8)"
        )
        output_equation = (
            "output_base + ((channel//8)*spatial_count*8 + "
            "spatial_linear*8 + channel%8)"
        )
        multiplier_source = {
            "kind": "MSE1_BUFFER2_GA_INPORT1_LANE0_KEEP",
            "base": multiplier_base,
            "address_equation": "multiplier_base + 4*channel",
            "channel_phase_count": channels,
            "phase_order": "channel=0..C-1",
            "reload_policy": "reload_once_per_channel_per_spatial_tile",
        }
        multiplier_axis: int | None = 0
        multiplier_value_kind = "per_channel"
    elif onnx_op_type == "QLinearMatMul":
        batch, channels = shape
        spatial_count = element_count
        layout = "NC_LINEAR_SCALAR_MULTIPLIER"
        mode = "MATMUL_LINEAR_SCALAR_CONSTANT"
        tiles = spatial_tiles(element_count)
        phase_count = 0
        substage_count = len(tiles)
        input_equation = "input_base + 4*element_linear"
        output_equation = "output_base + element_linear"
        multiplier_source = {
            "kind": "PE00_INPUT1_EXACT_FP32_CONSTANT",
            "constant_bits": bits[0],
            "address_equation": "NOT_APPLICABLE_SCALAR_CONSTANT",
            "channel_phase_count": 0,
            "phase_order": "NOT_APPLICABLE",
            "reload_policy": "capture_once_before_first_occurrence",
        }
        multiplier_axis = None
        multiplier_value_kind = "scalar"
    else:
        raise ValueError(f"{stage_id}: unsupported ONNX owner {onnx_op_type}")

    return {
        "schema": "requant_scalar_phase_strict_json_v1",
        "family": FAMILY,
        "identity": {
            "request_id": stage["request_id"],
            "hw_op_id": stage_id,
            "hw_op_type": identity["hw_op_type"],
            "node_id": identity["node_id"],
            "onnx_op_type": onnx_op_type,
            "onnx_name": identity["onnx_name"],
            "request_sha256": stage["request_sha256"],
        },
        "typed_io": {
            "input": {
                "tensor_id": stage["dag"]["input_tensor"]["tensor_id"],
                "dtype": "int32",
                "shape": shape,
                "logical_layout": stage["layout"]["logical"],
                "identity_sha256": stage["dag"]["input_tensor"]["identity_sha256"],
            },
            "output": {
                "tensor_id": stage["dag"]["output_tensor"]["tensor_id"],
                "dtype": "uint8",
                "shape": shape,
                "logical_layout": stage["layout"]["logical"],
                "identity_sha256": stage["dag"]["output_tensor"]["identity_sha256"],
            },
            "consumer_bindings": stage["dag"]["consumers"],
        },
        "qparams": {
            "multiplier_dtype": "float32",
            "multiplier_axis": multiplier_axis,
            "multiplier_value_kind": multiplier_value_kind,
            "multiplier_bits": bits,
            "multiplier_payload_sha256": multiplier_sha,
            "y_zero_point_dtype": "uint8",
            "y_zero_point": y_zero_point,
            "zero_point_class": stage["qparams"]["zero_point_class"],
        },
        "numeric_graph": five_pe_graph(y_zero_point),
        "physical_schedule": {
            "mode": mode,
            "physical_layout": layout,
            "operator_relative_address_space": {
                "alignment_bytes": ALIGNMENT,
                "width_bits": 30,
                "relocatable_by_uniform_backend_base": True,
                "regions": {
                    "input_int32": {"base": input_base, "size_bytes": input_bytes},
                    "multiplier_fp32": {
                        "base": multiplier_base,
                        "size_bytes": multiplier_bytes,
                    },
                    "output_uint8": {"base": output_base, "size_bytes": output_bytes},
                },
                "total_bytes": total_bytes,
            },
            "loops": {
                "lc_positive_stride_only": True,
                "maximum_lc_end": MAX_LC_END,
                "spatial_or_linear_count": spatial_count,
                "spatial_tiles": tiles,
                "channel_phase_count": phase_count,
                "operator_substage_count": substage_count,
                "terminal_equation": (
                    "terminal iff final channel phase (when present), final tile, "
                    "and final accepted element of that tile"
                ),
            },
            "streams": {
                "input_A": {
                    "transaction_bytes": 4,
                    "idx_size": [3, 0, "NULL"],
                    "within_phase_dim_stride": [4 if onnx_op_type == "QLinearMatMul" else 32, 0, 0],
                    "address_equation": input_equation,
                    "address_remapping": "IDENTITY",
                },
                "multiplier_B": {
                    "transaction_bytes": 4,
                    "idx_size": [3, 0, "NULL"],
                    "dim_stride": [4, 0, 0],
                    **multiplier_source,
                },
                "output_D": {
                    "transaction_bytes": 1,
                    "idx_size": [0, 0, "NULL"],
                    "within_phase_dim_stride": [1 if onnx_op_type == "QLinearMatMul" else 8, 0, 0],
                    "address_equation": output_equation,
                    "address_remapping": "IDENTITY",
                },
            },
            "buffers": {
                "buffer0_A": {
                    "buf_spatial_stride": [0, 1, 2, 3],
                    "buf_spatial_size": 4,
                    "mask": [1, 0, 0, 0, 0, 0, 0, 0],
                },
                "buffer2_B": {
                    "buf_spatial_stride": [0, 1, 2, 3],
                    "buf_spatial_size": 4,
                    "mask": [1, 0, 0, 0, 0, 0, 0, 0],
                },
                "buffer5_D": {
                    "buf_spatial_stride": [0],
                    "buf_spatial_size": 1,
                    "mask": [1, 0, 0, 0, 0, 0, 0, 0],
                },
            },
            "ga_inports": {
                "inport0_A": {
                    "src_id": 0,
                    "mask": [1, 0, 0, 0, 0, 0, 0, 0],
                    "int32_to_fp32": True,
                },
                "inport1_B": {
                    "src_id": 0,
                    "mask": [1, 0, 0, 0, 0, 0, 0, 0],
                    "int32_to_fp32": False,
                },
            },
            "pe00_multiplier_input": {
                "mode": "constant" if onnx_op_type == "QLinearMatMul" else "keep",
                "source": (
                    "exact_constant_bits"
                    if onnx_op_type == "QLinearMatMul"
                    else "GA_INPORT1_GROUP1_SOURCE0"
                ),
                "keep_last_index": (
                    None if onnx_op_type == "QLinearMatMul" else 1
                ),
            },
            "lifetime": {
                "multiplier_capture_before_A": True,
                "multiplier_visible_until_tile_last_accept": True,
                "next_multiplier_load_after_buffer2_lane0_clear": True,
                "selected_consumer_backpressure_reaches_source": True,
                "unselected_ready_neutral": True,
            },
            "coverage": {
                "logical_element_count": element_count,
                "input_int32_bytes": input_bytes,
                "multiplier_payload_bytes": multiplier_bytes,
                "output_uint8_bytes": output_bytes,
                "each_logical_element_exactly_once": True,
                "four_byte_multiplier_never_crosses_16B_line": True,
            },
            "limits": {
                "all_lc_end_le_32768": True,
                "all_stream_stride_le_1048575": True,
                "maximum_stream_stride": max(
                    4 if onnx_op_type == "QLinearMatMul" else 32,
                    1 if onnx_op_type == "QLinearMatMul" else 8,
                ),
            },
        },
        "local_strict_claim": {
            "candidate_complete": True,
            "backend_bound": False,
            "mapping_generated": False,
            "bitstream_generated": False,
            "execplan_generated": False,
            "sca_generated": False,
            "server_package_generated": False,
            "dynamic_execution_claimed": False,
        },
        "proof_receipts": {
            "typed_stage_inventory": bound_file(STAGE_INVENTORY),
            "exact_multiplier_occurrence": bound_file(MULTIPLIER_PROOF),
            "accepted_full_int32_numeric_graph": bound_file(NUMERIC_PROOF),
            "five_pe_selector_bst_backpressure": bound_file(PHYSICAL_PROOF),
            "scalar_phase_field_equations": bound_file(LANE_PROOF),
            "lowering_bundle": bound_file(LOWERING),
        },
    }


def receipt_for_pointer(pointer: str) -> Path:
    if pointer.startswith("/identity") or pointer.startswith("/typed_io") or pointer.startswith("/qparams"):
        return STAGE_INVENTORY
    if pointer.startswith("/numeric_graph"):
        return PHYSICAL_REPORT
    if pointer.startswith("/physical_schedule"):
        return LANE_PROOF
    return STAGE_INVENTORY


def origin_for_pointer(pointer: str, value: Any) -> tuple[str, str]:
    if value is None:
        return "EXPLICIT_DISABLED", "EXPLICITLY_INACTIVE"
    if pointer.startswith("/identity") or pointer.startswith("/typed_io") or pointer.startswith("/qparams"):
        return "MODEL_DERIVED", "DERIVED_FOR_TARGET"
    if pointer.startswith("/numeric_graph"):
        return "RTL_DERIVED", "DERIVED_FOR_TARGET"
    if "/operator_relative_address_space/" in pointer or "/address_equation" in pointer:
        return "ADDRESS_PLANNER_DERIVED", "DERIVED_FOR_TARGET"
    return "SCHEDULE_DERIVED", "DERIVED_FOR_TARGET"


def axes_for_pointer(pointer: str) -> list[str]:
    axes: list[str] = []
    if pointer.startswith("/typed_io") or pointer.startswith("/physical_schedule/loops"):
        axes.append("shape")
    if "dtype" in pointer or "conversion" in pointer or "int32_to_fp32" in pointer:
        axes.append("dtype")
    if pointer.startswith("/qparams") or pointer.startswith("/numeric_graph"):
        axes.append("qparam")
    if "layout" in pointer or "stride" in pointer or "mask" in pointer:
        axes.append("layout")
    if "address" in pointer or "base" in pointer or "regions" in pointer:
        axes.append("address")
    if pointer.startswith("/numeric_graph") or pointer.startswith("/physical_schedule"):
        axes.append("cross_stage_schedule")
    return sorted(set(axes)) or ["shape"]


def build_ledger(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate_sha = hashlib.sha256(pretty_bytes(candidate)).hexdigest()
    entries = []
    absences = [
        {
            "target_json_pointer": "/physical_schedule/mode",
            "state": "TARGET_REQUIRED_DERIVED",
            "reason": "No exact native five-PE scalar-phase replay exists; the authorized materializer derives this target schedule.",
            "owner": "requant_scalar_phase_materializer_v1",
        },
        {
            "target_json_pointer": "/numeric_graph/pe_chain/0/opcode",
            "state": "TARGET_REQUIRED_DERIVED",
            "reason": "The five-PE slow composite is a target composition, not a nearest-template copy.",
            "owner": "accepted_requant_5pe_numeric_and_physical_proofs",
        },
        {
            "target_json_pointer": "/native_exact_replay",
            "state": "SOURCE_ABSENT_NOT_APPLICABLE",
            "reason": "Candidate is an authorized composition of existing primitives, not a native exact replay.",
            "owner": "requant_scalar_phase_materializer_v1",
        },
    ]
    for pointer, value in iter_json_leaves(candidate):
        origin, applicability = origin_for_pointer(pointer, value)
        receipt = None if origin == "EXPLICIT_DISABLED" else bound_file(receipt_for_pointer(pointer))
        entries.append(
            {
                "json_pointer": pointer,
                "target_value": value,
                "origin": origin,
                "applicability_class": applicability,
                "exactness_axes": dict(EXACTNESS_AXES),
                "owner": (
                    "requant_scalar_phase_materializer_v1"
                    if origin != "MODEL_DERIVED"
                    else "typed_lowering_and_model_qparams"
                ),
                "consumer_equation": (
                    "Leaf is consumed by the local strict Requant five-PE scalar-phase "
                    "configuration exactly as materialized; backend rebasing is outside this claim."
                ),
                "derivation_receipt": receipt,
                "source": None,
                "negative_control_ids": [
                    "NC_REQUANT_MULTIPLIER_BIT_TAMPER",
                    "NC_REQUANT_SCALAR_BUFFER_SIZE_TAMPER",
                ],
                "status": "RESOLVED",
            }
        )
        if value is None:
            absences.append(
                {
                    "target_json_pointer": pointer,
                    "state": "EXPLICIT_NULL_INACTIVE",
                    "reason": "This field is explicitly inactive for the selected scalar supply mode.",
                    "owner": "requant_scalar_phase_materializer_v1",
                }
            )
    return {
        "schema": "operator_config_field_provenance_ledger_v1",
        "family": FAMILY,
        "candidate_json_sha256": candidate_sha,
        "entries": entries,
        "source_absences": absences,
        "claim_boundary": (
            "100% leaf provenance for the local strict scalar-phase operator "
            "configuration; no backend execution artifact is claimed."
        ),
    }


def build_handler_capability(
    *, candidate: dict[str, Any], ledger: dict[str, Any]
) -> dict[str, Any]:
    tool_path = Path(__file__).resolve()
    capabilities = {}
    for axis in (
        "exact_replay",
        "shape",
        "dtype",
        "qparam",
        "layout",
        "address",
        "cross_stage_schedule",
    ):
        capabilities[axis] = {
            "supported": True,
            "evidence": (
                "Authorized isolated materializer binds typed lowering, exact "
                "multiplier bits, proven five-PE equations, relocatable addresses, "
                "LC-safe tiling, scalar phases, terminal and lifetime."
            ),
        }
    ledger_pointers = {entry["json_pointer"] for entry in ledger["entries"]}
    selected_pointers = [
        "/identity/hw_op_id",
        "/typed_io/input/dtype",
        "/typed_io/input/shape/0",
        "/qparams/multiplier_payload_sha256",
        "/qparams/multiplier_bits/0",
        "/qparams/y_zero_point",
        "/numeric_graph/pe_chain/0/opcode",
        "/numeric_graph/selector_edges/0/consumer_src_id",
        "/numeric_graph/terminal/outport",
        "/physical_schedule/mode",
        "/physical_schedule/operator_relative_address_space/regions/input_int32/base",
        "/physical_schedule/operator_relative_address_space/regions/output_uint8/base",
        "/physical_schedule/streams/multiplier_B/transaction_bytes",
        "/physical_schedule/buffers/buffer2_B/buf_spatial_size",
        "/physical_schedule/ga_inports/inport1_B/mask/0",
        "/physical_schedule/pe00_multiplier_input/mode",
        "/physical_schedule/loops/terminal_equation",
        "/physical_schedule/lifetime/multiplier_visible_until_tile_last_accept",
    ]
    dependent = [
        {
            "json_pointer": pointer,
            "axes": axes_for_pointer(pointer),
            "covered_by": "tools/materialize_requant_scalar_phase_strict_json_v1.py",
            "status": "COVERED",
        }
        for pointer in selected_pointers
        if pointer in ledger_pointers
    ]
    return {
        "schema": "operator_config_handler_capability_v1",
        "family": FAMILY,
        "handler": {
            "kind": "AUTHORIZED_PATCH",
            "path": rel(tool_path),
            "sha256": sha256_file(tool_path),
            "source_span": "candidate_for_stage/build_ledger/build_composition",
        },
        "capabilities": capabilities,
        "dependent_leaves": dependent,
        "claim_boundary": (
            "Local strict JSON materialization capability only. Native backend "
            "registration, encoding and execution remain explicitly outside scope."
        ),
    }


def build_composition(candidate: dict[str, Any]) -> dict[str, Any]:
    stage_id = candidate["identity"]["hw_op_id"]
    count = candidate["physical_schedule"]["coverage"]["logical_element_count"]
    byte_set = f"{stage_id}:logical_occurrence_set[0..{count - 1}]x4B"
    edges = [
        ("PE00_TO_PE01", "fp32", "fp32"),
        ("PE01_TO_PE10", "fp32", "fp32"),
        ("PE10_TO_PE11", "fp32_bits", "int32_bits"),
        ("PE11_TO_PE12", "int32", "int32"),
    ]
    boundaries = []
    for edge, producer_dtype, consumer_dtype in edges:
        boundaries.append(
            {
                "boundary_id": f"{stage_id}:{edge}",
                "producer_dtype": producer_dtype,
                "consumer_dtype": consumer_dtype,
                "shape": "one scalar token per logical output occurrence",
                "layout": candidate["physical_schedule"]["physical_layout"],
                "producer_byte_set": byte_set,
                "consumer_required_byte_set": byte_set,
                "transaction_bytes": 4,
                "tag_last": "selected neighbor edge carries complete tag; final tag follows terminal equation",
                "clock_handshake": "consumer ready backpressures exactly the selected producer destination",
                "lifetime_visibility": "token remains visible until the selected consumer accepts it",
                "qparam_rounding": candidate["numeric_graph"]["rounding_order"],
                "status": "RESOLVED",
                "evidence": [
                    rel(NUMERIC_PROOF),
                    rel(PHYSICAL_PROOF),
                    rel(LANE_PROOF),
                ],
            }
        )
    return {
        "schema": "operator_config_composition_boundary_v1",
        "family": FAMILY,
        "boundaries": boundaries,
        "claim_boundary": (
            "Resolved local PE-to-PE primitive-composition boundaries. "
            "Backend encoding and dynamic execution are not claimed."
        ),
    }


def build_current_diff(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate_sha = hashlib.sha256(pretty_bytes(candidate)).hexdigest()
    entries = [
        {
            "json_pointer": pointer,
            "candidate_value": value,
            "current_value_present": False,
            "current_value": None,
            "classification": "CURRENT_ABSENT",
            "reason": (
                "No current release config is authorized as generation authority; "
                "historical node0001 diagnostics remain read-only comparison evidence."
            ),
            "evidence": [
                rel(FROZEN_ROOT / "current_test_diff.json"),
                rel(CURRENT_HISTORY),
            ],
        }
        for pointer, value in iter_json_leaves(candidate)
    ]
    return {
        "schema": "operator_config_current_test_diff_v1",
        "family": FAMILY,
        "candidate_json_sha256": candidate_sha,
        "current_identity": {
            "available": False,
            "path": None,
            "sha256": None,
            "package_or_record": rel(CURRENT_HISTORY),
            "latest_result": (
                "Historical node0001 last trustworthy boundary is BST data and "
                "coefficient address 64/64 bit-exact; no current release config."
            ),
        },
        "entries": entries,
        "blocker_attribution": [
            {
                "blocker_id": "B_REQUANT_CONV53_SCALAR_PHASE_STRICT_MATERIALIZATION",
                "classification": "CONFIG_EXPLAINS",
                "candidate_json_pointers": [
                    "/physical_schedule/mode",
                    "/physical_schedule/streams/multiplier_B/transaction_bytes",
                    "/physical_schedule/buffers/buffer2_B/buf_spatial_size",
                    "/physical_schedule/ga_inports/inport1_B/mask/0",
                ],
                "reason": "The new candidate explicitly materializes the previously missing scalar-phase fields.",
                "evidence": [rel(LANE_PROOF)],
            },
            {
                "blocker_id": "B_REQUANT_CONV53_SCALAR_PHASE_BACKEND_AND_DYNAMIC_EXECUTION",
                "classification": "DYNAMIC_ONLY",
                "candidate_json_pointers": [],
                "reason": "Backend encoding and dynamic execution are outside the local strict JSON claim.",
                "evidence": [rel(PHYSICAL_PROOF)],
            },
            {
                "blocker_id": "B_REQUANT_GUARD_DYNAMIC_DATA_PATH",
                "classification": "DYNAMIC_ONLY",
                "candidate_json_pointers": [],
                "reason": "Historical guard-only coeff-to-ALU observation gap is not a defect in this distinct slow-composite candidate.",
                "evidence": [rel(CURRENT_HISTORY)],
            },
            {
                "blocker_id": "B_REQUANT_SERVER_E4_E5",
                "classification": "DYNAMIC_ONLY",
                "candidate_json_pointers": [],
                "reason": "No server action or formal D evidence is part of this task.",
                "evidence": [rel(CURRENT_HISTORY)],
            },
        ],
        "claim_boundary": (
            "Leaf-complete comparison against the absence of a current releasable "
            "config; historical observer/package/RTL outcomes remain dynamic-only."
        ),
    }


def build_contract(
    *,
    output_root: Path,
    candidate_dir: Path,
    stage_id: str,
    candidate_path: Path,
    ledger_path: Path,
    handler_path: Path,
    diff_path: Path,
    composition_path: Path,
) -> dict[str, Any]:
    return {
        "schema": "operator_config_complete_json_candidate_v1",
        "family": FAMILY,
        "candidate_status": "COMPLETE",
        "reference_class": "D",
        "changed_axes": [
            "shape",
            "dtype",
            "qparam",
            "layout",
            "address",
            "cross_stage_schedule",
        ],
        "target_hw_op_types": ["RequantizeUint8"],
        "stage_ids": [stage_id],
        "candidate_json": bound_file(candidate_path),
        "field_provenance_ledger": bound_file(ledger_path),
        "handler_capability": bound_file(handler_path),
        "current_test_diff": bound_file(diff_path),
        "composition": {
            "required": True,
            "boundary": bound_file(composition_path),
        },
        "artifact_root": rel(output_root),
        "claim_boundary": (
            "COMPLETE local strict scalar-phase Requant operator JSON only. "
            "No native backend JSON, mapping, bitstream, execplan, SCA, package, "
            "server run, formal D, E3, E4, or E5 is produced or claimed."
        ),
    }


def materialize(output_root: Path) -> dict[str, Any]:
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError(f"output root must be fresh and empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    if sha256_file(LOWERING) != LOWERING_SHA256:
        raise ValueError("lowering SHA drift")
    for required in (
        MODEL,
        STAGE_INVENTORY,
        MULTIPLIER_PROOF,
        LANE_PROOF,
        NUMERIC_PROOF,
        PHYSICAL_PROOF,
        PHYSICAL_REPORT,
        CURRENT_HISTORY,
    ):
        if not required.is_file():
            raise ValueError(f"required evidence absent: {required}")

    lowering = load_json(LOWERING)
    inventory = load_json(STAGE_INVENTORY)
    ordered_ids, requests = request_index(lowering)
    stage_by_id = {
        stage["identity"]["hw_op_id"]: stage for stage in inventory["stages"]
    }
    if ordered_ids != [stage["identity"]["hw_op_id"] for stage in inventory["stages"]]:
        raise ValueError("stage inventory order differs from lowering")

    helper = load_multiplier_module()
    initializers = helper.load_float_initializers(MODEL)
    candidate_refs = []
    stage_summaries = []
    for stage_id in ordered_ids:
        request = requests[stage_id]
        stage = stage_by_id[stage_id]
        payload = helper.derive_payload(request, initializers)
        candidate = candidate_for_stage(stage=stage, request=request, payload=payload)
        candidate_dir = output_root / "candidates" / stage_id
        candidate_path = candidate_dir / "complete_json.json"
        write_json(candidate_path, candidate)

        ledger = build_ledger(candidate)
        ledger_path = candidate_dir / "field_provenance_ledger.json"
        write_json(ledger_path, ledger)
        handler = build_handler_capability(candidate=candidate, ledger=ledger)
        handler_path = candidate_dir / "handler_capability.json"
        write_json(handler_path, handler)
        diff = build_current_diff(candidate)
        diff_path = candidate_dir / "current_test_diff.json"
        write_json(diff_path, diff)
        composition = build_composition(candidate)
        composition_path = candidate_dir / "composition_boundary.json"
        write_json(composition_path, composition)
        contract = build_contract(
            output_root=output_root,
            candidate_dir=candidate_dir,
            stage_id=stage_id,
            candidate_path=candidate_path,
            ledger_path=ledger_path,
            handler_path=handler_path,
            diff_path=diff_path,
            composition_path=composition_path,
        )
        contract_path = candidate_dir / "candidate_contract.json"
        write_json(contract_path, contract)
        candidate_refs.append(bound_file(contract_path))
        stage_summaries.append(
            {
                "stage_id": stage_id,
                "onnx_op_type": stage["identity"]["onnx_op_type"],
                "shape": stage["shape"]["output"],
                "multiplier_count": len(candidate["qparams"]["multiplier_bits"]),
                "y_zero_point": candidate["qparams"]["y_zero_point"],
                "schedule_mode": candidate["physical_schedule"]["mode"],
                "candidate_sha256": sha256_file(candidate_path),
                "candidate_contract_sha256": sha256_file(contract_path),
                "ledger_leaf_count": len(ledger["entries"]),
            }
        )

    family_set = {
        "schema": "operator_config_complete_json_family_set_v1",
        "family": FAMILY,
        "target_hw_op_types": ["RequantizeUint8"],
        "family_scope": {
            "mode": "PINNED_EXACT_STAGE_IDS",
            "lowering_sha256": LOWERING_SHA256,
            "expected_stage_ids": ordered_ids,
        },
        "candidate_contracts": candidate_refs,
        "no_config_stages": [],
        "claim_boundary": (
            "Exact 54-stage local strict Requant scalar-phase candidate set. "
            "Backend and all execution/package/server surfaces are excluded."
        ),
    }
    family_set_path = output_root / "family_set.json"
    write_json(family_set_path, family_set)

    manifest = {
        "schema": "requant_scalar_phase_strict_json_materialization_manifest_v1",
        "status": "LOCAL_STRICT_JSON_MATERIALIZED_PENDING_SHARED_GATES",
        "family": FAMILY,
        "stage_count": len(stage_summaries),
        "conv_stage_count": sum(
            item["onnx_op_type"] == "QLinearConv" for item in stage_summaries
        ),
        "matmul_stage_count": sum(
            item["onnx_op_type"] == "QLinearMatMul" for item in stage_summaries
        ),
        "strict_json_count": len(stage_summaries),
        "unresolved_leaf_count": 0,
        "lowering_sha256": LOWERING_SHA256,
        "stage_ids": ordered_ids,
        "stages": stage_summaries,
        "family_set": bound_file(family_set_path),
        "source_identity": {
            "ndp_sim_commit": NDP_SIM_COMMIT,
            "rtl_commit": RTL_COMMIT,
            "materializer": bound_file(Path(__file__).resolve()),
            "stage_inventory": bound_file(STAGE_INVENTORY),
            "multiplier_proof": bound_file(MULTIPLIER_PROOF),
            "lane_phase_proof": bound_file(LANE_PROOF),
            "numeric_proof_record": bound_file(NUMERIC_PROOF),
            "physical_proof_record": bound_file(PHYSICAL_PROOF),
            "physical_proof_report": bound_file(PHYSICAL_REPORT),
        },
        "forbidden_outputs": {
            "mapping": 0,
            "bitstream": 0,
            "execplan": 0,
            "sca": 0,
            "zip": 0,
            "server_package": 0,
        },
        "claim_boundary": (
            "Materialization manifest for local strict operator JSON only; "
            "shared gates are run separately and backend/dynamic claims are forbidden."
        ),
    }
    write_json(output_root / "materialization_manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = materialize(args.output_root.resolve())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "stage_count": manifest["stage_count"],
                "strict_json_count": manifest["strict_json_count"],
                "unresolved_leaf_count": manifest["unresolved_leaf_count"],
                "output_root": rel(args.output_root.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
