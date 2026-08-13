#!/usr/bin/env python3
"""Audit exact Requant multiplier occurrence supply without materializing a backend."""

from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
import math
import pathlib
import re
import struct
import subprocess
from typing import Any, Iterator

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[1]
RTL_ROOT = ROOT / "Trassic2.0_RTL"
NDP_SIM = ROOT / "ndp-sim"
MODEL = ROOT / "artifacts/reference_model/resnet50-v1-12-int8.onnx"
LOWERING = ROOT / "contracts/resnet50_r5_lowering_bundle.json"
EVIDENCE = ROOT / "contracts/operator_config/requant_quant_tail_evidence_input_v1.json"
NATIVE_JSON = NDP_SIM / "jsons/prefill_mul_fp32MN_fp32M_fp32MN.json"
REGISTRY = NDP_SIM / "address_remapping/src/address_remapping/registry.py"
CONTROL = NDP_SIM / "model_execplan/src/execution_plan_generator/control_registers.py"
BASE_INFO = NDP_SIM / "model_execplan/config/operator_base_info.json"
PARAMS = RTL_ROOT / "code/NDP_rtl/includes/NDP_Parameters.svh"
INTERCONNECT = (
    RTL_ROOT
    / "code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Group_Interconnect.sv"
)
INBUFFER = RTL_ROOT / "code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv"
PE_CONFIG = RTL_ROOT / "code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Config.sv"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd: list[str], cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def git_identity(repo: pathlib.Path, paths: list[pathlib.Path]) -> dict[str, Any]:
    prefix = ["git", "-c", f"safe.directory={repo.as_posix()}", "-C", str(repo)]
    head = run(prefix + ["rev-parse", "HEAD"])
    if head.returncode:
        raise RuntimeError(head.stderr)
    files: dict[str, Any] = {}
    for path in paths:
        rel = path.relative_to(repo).as_posix()
        current_blob = run(prefix + ["hash-object", rel])
        head_blob = run(prefix + ["rev-parse", f"HEAD:{rel}"])
        status = run(prefix + ["status", "--short", "--", rel])
        files[rel] = {
            "sha256": sha256(path),
            "current_byte_blob": current_blob.stdout.strip(),
            "head_blob": head_blob.stdout.strip() if head_blob.returncode == 0 else None,
            "working_tree_status": status.stdout.strip(),
        }
    return {"head": head.stdout.strip(), "files": files}


def read_varint(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if pos >= len(data) or shift >= 70:
            raise ValueError("invalid protobuf varint")
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
        shift += 7


def protobuf_fields(data: bytes) -> Iterator[tuple[int, int, Any]]:
    pos = 0
    while pos < len(data):
        key, pos = read_varint(data, pos)
        field = key >> 3
        wire = key & 7
        if wire == 0:
            value, pos = read_varint(data, pos)
        elif wire == 1:
            value = data[pos : pos + 8]
            pos += 8
        elif wire == 2:
            size, pos = read_varint(data, pos)
            value = data[pos : pos + size]
            pos += size
        elif wire == 5:
            value = data[pos : pos + 4]
            pos += 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wire}")
        yield field, wire, value


def packed_varints(data: bytes) -> list[int]:
    values = []
    pos = 0
    while pos < len(data):
        value, pos = read_varint(data, pos)
        values.append(value)
    return values


def parse_tensor_proto(data: bytes) -> tuple[str, np.ndarray] | None:
    name: str | None = None
    data_type: int | None = None
    dims: list[int] = []
    raw_data: bytes | None = None
    float_words: list[bytes] = []
    for field, wire, value in protobuf_fields(data):
        if field == 1:
            dims.extend(packed_varints(value) if wire == 2 else [value])
        elif field == 2 and wire == 0:
            data_type = value
        elif field == 4:
            if wire == 2:
                if len(value) % 4:
                    raise ValueError("invalid packed float_data")
                float_words.extend(value[i : i + 4] for i in range(0, len(value), 4))
            elif wire == 5:
                float_words.append(value)
        elif field == 8 and wire == 2:
            name = value.decode("utf-8")
        elif field == 9 and wire == 2:
            raw_data = value
    if name is None or data_type != 1:
        return None
    payload = raw_data if raw_data is not None else b"".join(float_words)
    expected = math.prod(dims) if dims else 1
    if len(payload) != expected * 4:
        raise ValueError(
            f"float initializer {name} byte count {len(payload)} != expected {expected * 4}"
        )
    values = np.frombuffer(payload, dtype="<f4").copy()
    return name, values.reshape(tuple(dims) if dims else ())


def load_float_initializers(path: pathlib.Path) -> dict[str, np.ndarray]:
    model_fields = list(protobuf_fields(path.read_bytes()))
    graph_payloads = [value for field, wire, value in model_fields if field == 7 and wire == 2]
    if len(graph_payloads) != 1:
        raise ValueError(f"expected one ONNX graph, got {len(graph_payloads)}")
    initializers: dict[str, np.ndarray] = {}
    for field, wire, value in protobuf_fields(graph_payloads[0]):
        if field != 5 or wire != 2:
            continue
        parsed = parse_tensor_proto(value)
        if parsed is not None:
            name, array = parsed
            initializers[name] = array
    return initializers


def typed_parameter(request: dict[str, Any], parameter_id: str) -> dict[str, Any]:
    for parameter in request["typed_parameters"]:
        if parameter["parameter_id"] == parameter_id:
            return parameter
    raise KeyError(parameter_id)


def initializer_for_parameter(
    request: dict[str, Any],
    parameter_id: str,
    initializers: dict[str, np.ndarray],
) -> np.ndarray:
    parameter = typed_parameter(request, parameter_id)
    name = parameter["provenance"]["onnx_name"]
    if name not in initializers:
        raise KeyError(f"missing ONNX initializer {name}")
    return initializers[name]


def derive_payload(
    request: dict[str, Any],
    initializers: dict[str, np.ndarray],
) -> np.ndarray:
    multiplier = next(p for p in request["typed_parameters"] if p["name"] == "requant_multiplier")
    source_ids = multiplier["provenance"]["source_parameter_ids"]
    sources = [initializer_for_parameter(request, parameter_id, initializers) for parameter_id in source_ids]
    if len(sources) != 3:
        raise ValueError(f"expected three multiplier sources for {request['identity']['hw_op_id']}")
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        # NumPy float32 operands preserve the required sequential binary32 operations.
        payload = np.asarray(np.asarray(sources[0], dtype=np.float32) * np.asarray(sources[1], dtype=np.float32), dtype=np.float32)
        payload = np.asarray(payload / np.asarray(sources[2], dtype=np.float32), dtype=np.float32)
    return np.ascontiguousarray(payload.reshape(-1), dtype="<f4")


def bits_hex(array: np.ndarray) -> list[str]:
    return [f"0x{value:08x}" for value in array.view("<u4").tolist()]


def function_return_keys(path: pathlib.Path, function_name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            keys: list[str] = []
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                    for key in child.value.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            keys.append(key.value)
            return keys
    raise KeyError(function_name)


def require_fragments(path: pathlib.Path, fragments: list[str]) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [fragment for fragment in fragments if fragment not in text]


def analyze_payloads(
    lowering: dict[str, Any],
    evidence: dict[str, Any],
    initializers: dict[str, np.ndarray],
) -> dict[str, Any]:
    requests = [
        request
        for request in lowering["requests"]
        if request["identity"]["hw_op_type"] == "RequantizeUint8"
    ]
    evidence_by_id = {item["hw_op_id"]: item for item in evidence["stage_evidence"]}
    stage_manifest = []
    mismatches = []
    payload_by_id: dict[str, np.ndarray] = {}
    for request in requests:
        identity = request["identity"]
        hw_op_id = identity["hw_op_id"]
        multiplier = next(p for p in request["typed_parameters"] if p["name"] == "requant_multiplier")
        payload = derive_payload(request, initializers)
        payload_by_id[hw_op_id] = payload
        payload_sha = hashlib.sha256(payload.tobytes()).hexdigest()
        expected_sha = multiplier["value"]["value_sha256"]
        ev_sha = evidence_by_id[hw_op_id]["qparams"]["multiplier_sha256"]
        count = payload.size
        shape = multiplier["value"]["shape"]
        row = {
            "hw_op_id": hw_op_id,
            "onnx_op_type": identity["onnx_op_type"],
            "output_shape": request["logical_geometry"]["output_shapes"][0],
            "multiplier_shape": shape,
            "element_count": count,
            "computed_payload_sha256": payload_sha,
            "typed_payload_sha256": expected_sha,
            "accepted_evidence_sha256": ev_sha,
            "hash_match": payload_sha == expected_sha == ev_sha,
            "first_bits": bits_hex(payload[: min(8, count)]),
        }
        if identity["onnx_op_type"] == "QLinearConv":
            n, c, h, w = row["output_shape"]
            row["axis_binding"] = {
                "typed_axis": multiplier["value"]["axis"],
                "channel_axis": 1,
                "native_M": c,
                "native_N": n * h * w,
                "M_divisible_by_8": c % 8 == 0,
                "logical_occurrence": "n,h,w,c",
                "native_payload_index": "c",
                "native_tensor_linear_index": "(c//8)*(N*H*W)*8 + ((n*H+h)*W+w)*8 + c%8",
            }
        else:
            row["axis_binding"] = {
                "kind": "scalar_broadcast",
                "consumer_element_count": math.prod(row["output_shape"]),
            }
        stage_manifest.append(row)
        if not row["hash_match"] or math.prod(shape) != count:
            mismatches.append(hw_op_id)
    return {
        "stage_count": len(stage_manifest),
        "all_exact_payload_hashes_match": not mismatches and len(stage_manifest) == 54,
        "mismatch_stage_ids": mismatches,
        "total_multiplier_elements": sum(row["element_count"] for row in stage_manifest),
        "stage_manifest": stage_manifest,
        "_payload_by_id": payload_by_id,
        "_requests": requests,
    }


def analyze_native_primitive(payload_analysis: dict[str, Any]) -> dict[str, Any]:
    native = json.loads(NATIVE_JSON.read_text(encoding="utf-8"))
    registry_text = REGISTRY.read_text(encoding="utf-8")
    control_text = CONTROL.read_text(encoding="utf-8")
    base_info = json.loads(BASE_INFO.read_text(encoding="utf-8"))["operators"][
        "prefill_mul_fp32MN_fp32M_fp32MN"
    ]
    pe_array = native["general_array"]["PE_array"]
    active_multiply_pes = sorted(
        name for name, config in pe_array.items() if config["alu_opcode"] == "mul"
    )
    pe_to_ga_index = {}
    for pe in active_multiply_pes:
        row = int(pe[2])
        col = int(pe[3])
        pe_to_ga_index[pe] = row + 4 * (col // 2)
    ga_index_to_pe = {index: pe for pe, index in pe_to_ga_index.items()}
    handler_keys = function_return_keys(
        CONTROL, "_compute_prefill_mul_fp32MN_fp32M_fp32MN_control_register_updates"
    )
    required_serialization_fields = [
        "rd_stream1.stream_engine.stream.buf_spatial_stride",
        "rd_stream1.stream_engine.stream.buf_spatial_size",
        "ga_inport1.general_array.inport.mask",
        "ga_pe0.general_array.PE_array.PE.inport1.src_id",
        "ga_pe0.general_array.PE_array.PE.inport1.keep_last_index",
        "lane_phase.loop.end",
    ]
    missing_serialization_fields = [
        field for field in required_serialization_fields if field not in handler_keys
    ]
    anchor_missing = []
    anchor_missing.extend(
        require_fragments(
            REGISTRY,
            [
                '"prefill_mul_fp32MN_fp32M_fp32MN"',
                '{"inA": _port("fp32", elementwise_mn_layout), "inB": _port("fp32", elementwise_m_layout)}',
                '["M_outer8", "N", "m8"]',
                '["M_outer8", "m8"]',
            ],
        )
    )
    anchor_missing.extend(
        require_fragments(
            INTERCONNECT,
            [
                "localparam int GA_INPORT_IDX = GA_ROW_PE_ID + 4*(GA_COL_PE_ID/2);",
                "ga_inport_group_data[GA_PE_INPORT_ID][GA_INPORT_IDX]",
            ],
        )
    )
    anchor_missing.extend(
        require_fragments(
            INBUFFER,
            [
                "ga_pe_inbuffer_bp_pre_keep_mask[GA_PORT_IDX]",
                "ga_pe_keep_last_index[GA_PORT_IDX]",
                "ga_pe_inbuffer_data[GA_PORT_IDX] <= ga_pe_inport_data[GA_PORT_IDX];",
            ],
        )
    )
    anchor_missing.extend(
        require_fragments(
            PE_CONFIG,
            [
                "`GA_PE_CONSTANT_VALUE_WIDTH-1:0",
                "ga_pe_constant_value[INPORT_ID]",
                "ga_pe_constant_valid[INPORT_ID]",
            ],
        )
    )

    payload_by_id = payload_analysis["_payload_by_id"]
    node0001 = payload_by_id["hwop-0001-01"]
    node_bits = bits_hex(node0001)
    counterexample_channel = next(
        index for index in range(1, len(node_bits)) if node_bits[index] != node_bits[0]
    )
    scalar = payload_by_id["hwop-0075-01"]
    scalar_bits = bits_hex(scalar)[0]

    return {
        "registry_semantics": {
            "registered": '"prefill_mul_fp32MN_fp32M_fp32MN"' in registry_text,
            "input_A_axes": ["M", "N"],
            "input_B_axes": ["M"],
            "input_A_linear_order": ["M_outer8", "N", "m8"],
            "input_B_linear_order": ["M_outer8", "m8"],
            "semantic": "B[M] broadcasts across N",
        },
        "native_json_route": {
            "stream1_target": native["stream_engine"]["stream1"]["target"],
            "stream1_mode": native["stream_engine"]["stream1"]["mode"],
            "stream1_idx": native["stream_engine"]["stream1"]["idx"],
            "stream1_idx_size": native["stream_engine"]["stream1"]["idx_size"],
            "stream1_dim_stride": native["stream_engine"]["stream1"]["dim_stride"],
            "stream1_buf_spatial_stride": native["stream_engine"]["stream1"]["buf_spatial_stride"],
            "buffer2_dst_port": native["buffer_config"]["buffer2"]["dst_port"],
            "ga_inport1_mask": native["general_array"]["inport"]["inport1"]["mask"],
            "pe00_inport1": native["general_array"]["PE_array"]["PE00"]["inport1"],
            "active_multiply_pes": active_multiply_pes,
            "pe_to_ga_inport_index": pe_to_ga_index,
            "ga_inport_index_to_pe": {str(k): v for k, v in sorted(ga_index_to_pe.items())},
        },
        "native_template_initial_sizes": base_info["initial_size"],
        "current_handler": {
            "source_labels_itself_placeholder": (
                '"""Placeholder for prefill_mul_fp32MN_fp32M_fp32MN control register logic."""'
                in control_text
            ),
            "updated_fields": handler_keys,
            "required_lane_serialization_fields_not_updated": missing_serialization_fields,
        },
        "one_lane_capability": {
            "status": "PROVEN_FOR_NATIVE_8_WIDE_TEMPLATE",
            "address_equation": "B_addr(c)=B_base+4*c; one 32B transaction covers c=8*g..8*g+7",
            "broadcast_equation": "B[c] is held by PE inport keep-mode across native N",
            "lifetime_equation": (
                "PE00 inport1 mode=keep and keep_last_index=1 reuses its selected lane until "
                "the buffer-input last_index crosses the keep boundary"
            ),
        },
        "single_chain_counterexample": {
            "stage": "hwop-0001-01",
            "channel0_bits": node_bits[0],
            "first_distinct_channel": counterexample_channel,
            "first_distinct_channel_bits": node_bits[counterexample_channel],
            "native_transaction_group": counterexample_channel // 8,
            "native_lane": counterexample_channel % 8,
            "native_destination_pe": ga_index_to_pe[counterexample_channel % 8],
            "required_destination": "PE00.inport1",
            "reason": (
                "The unmodified 8-wide native primitive routes lane c%8 to a distinct GA input/PE. "
                "The 5PE graph consumes the multiplier only at PE00, so c%8!=0 does not reach PE00. "
                "The current handler emits no lane-phase or buffer-spatial remapping that serializes "
                "the other seven lanes into PE00."
            ),
        },
        "scalar_stage": {
            "stage": "hwop-0075-01",
            "exact_bits": scalar_bits,
            "constant_width_bits": 32,
            "status": "PROVEN_AT_RTL_CONSTANT_CAPTURE_EQUATION_LEVEL",
            "scope": (
                "A single exact 32-bit PE00 inport1 constant can persist for every scalar-broadcast "
                "occurrence; this does not prove any other 5PE field or dynamic execution."
            ),
        },
        "source_anchor_missing_fragments": anchor_missing,
    }


def strip_private(payload_analysis: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload_analysis.items() if not key.startswith("_")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=(
            "artifacts/operator_config_validation/"
            "requant_multiplier_occurrence_supply_v1/report.json"
        ),
    )
    args = parser.parse_args()

    lowering = json.loads(LOWERING.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    initializers = load_float_initializers(MODEL)
    payload_analysis = analyze_payloads(lowering, evidence, initializers)
    native = analyze_native_primitive(payload_analysis)

    structural_errors = []
    if not payload_analysis["all_exact_payload_hashes_match"]:
        structural_errors.append("EXACT_PAYLOAD_RECONSTRUCTION_MISMATCH")
    if native["source_anchor_missing_fragments"]:
        structural_errors.append("CURRENT_SOURCE_ANCHOR_MISSING")
    if len(native["native_json_route"]["active_multiply_pes"]) != 8:
        structural_errors.append("NATIVE_MULTIPLY_PE_COUNT_CHANGED")

    conv_stages = [
        row
        for row in payload_analysis["stage_manifest"]
        if row["onnx_op_type"] == "QLinearConv"
    ]
    scalar_stages = [
        row
        for row in payload_analysis["stage_manifest"]
        if row["onnx_op_type"] == "QLinearMatMul"
    ]
    completion_blockers = []
    if conv_stages:
        completion_blockers.append(
            {
                "id": "CONV53_MULTIPLIER_LANES_1_TO_7_NOT_SERIALIZED_TO_PE00_INPUT1",
                "category": "B_REQUANT_5PE_PHYSICAL_MULTIPLIER_SUPPLY",
                "affected_stage_count": len(conv_stages),
                "detail": native["single_chain_counterexample"]["reason"],
            }
        )

    report = {
        "schema": "requant-multiplier-occurrence-supply-proof-v1",
        "status": (
            "EXACT_PAYLOAD_AND_SCALAR_SUPPLY_PROVEN__CONV53_PE00_LANE_SERIALIZATION_BLOCKED"
            if not structural_errors and completion_blockers
            else "PROOF_INVALID"
        ),
        "mainline_thread_id": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "active_rule": {
            "path": ".agents/rules/RequantizeUint8算子配置规则.md",
            "sha256": sha256(ROOT / ".agents/rules/RequantizeUint8算子配置规则.md"),
            "rule_id": "CDA-REQUANT-PER-CHANNEL-MULTIPLIER-OCCURRENCE-SUPPLY-001",
        },
        "scope": {
            "strict_backend_or_execution_assets_generated": False,
            "mapping_bitstream_execplan_sca_generated": False,
            "package_or_server_action": False,
            "numeric_5pe_graph_recomputed": False,
            "active_ndp_sim_or_rtl_modified": False,
        },
        "source_identity": {
            "model": {
                "path": MODEL.relative_to(ROOT).as_posix(),
                "sha256": sha256(MODEL),
                "float_initializer_count_parsed": len(initializers),
            },
            "contracts": {
                LOWERING.relative_to(ROOT).as_posix(): sha256(LOWERING),
                EVIDENCE.relative_to(ROOT).as_posix(): sha256(EVIDENCE),
            },
            "ndp_sim": git_identity(NDP_SIM, [NATIVE_JSON, REGISTRY, CONTROL, BASE_INFO]),
            "trassic": git_identity(RTL_ROOT, [PARAMS, INTERCONNECT, INBUFFER, PE_CONFIG]),
        },
        "exact_payload_bits_and_axis": strip_private(payload_analysis),
        "native_primitive_supply": native,
        "family_adjudication": {
            "conv_stage_count": len(conv_stages),
            "conv_status": "BLOCKED_AT_PE00_LANE_SERIALIZATION",
            "scalar_stage_count": len(scalar_stages),
            "scalar_status": "PROVEN_AT_RTL_CONSTANT_CAPTURE_EQUATION_LEVEL",
            "family_physical_multiplier_supply_proven": False,
        },
        "structural_errors": structural_errors,
        "completion_blockers": completion_blockers,
        "blocked_valid": not structural_errors and bool(completion_blockers),
        "pass": not structural_errors and not completion_blockers,
        "blocker_delta": {
            "close_subleaves": [
                "B_REQUANT_MULTIPLIER_EXACT_PAYLOAD_BITS_AND_CHANNEL_AXIS",
                "B_REQUANT_SCALAR_MULTIPLIER_PE00_CONSTANT_SUPPLY",
                "B_REQUANT_NATIVE_MULTIPLIER_ONE_LANE_ADDRESS_AND_KEEP_LIFETIME",
            ],
            "keep_open": ["B_REQUANT_5PE_PHYSICAL_MULTIPLIER_SUPPLY"],
            "refined_first_break": (
                "CONV53_MULTIPLIER_LANES_1_TO_7_NOT_SERIALIZED_TO_PE00_INPUT1"
            ),
        },
        "rule_delta_proposal": {
            "status": "CONFIRMATION_NO_NEW_RULE",
            "reason": (
                "The current occurrence-supply rule already distinguishes exact inventory and one-lane "
                "capability from family-wide physical supply and correctly fails closed."
            ),
        },
        "claim_boundary": (
            "Read-only payload/source/consumer-equation proof. No new operator JSON, mapping, bitstream, "
            "execplan, SCA, strict/backend, physical E2, package, server, E3, E4, or E5 claim."
        ),
        "package_release": "NONE",
    }

    output = pathlib.Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        display = output.relative_to(ROOT).as_posix()
    except ValueError:
        display = str(output)
    print(
        json.dumps(
            {
                "report": display,
                "report_sha256": sha256(output),
                "status": report["status"],
                "structural_error_count": len(structural_errors),
                "completion_blocker_count": len(completion_blockers),
                "exact_payload_stage_count": payload_analysis["stage_count"],
                "exact_payload_hashes_match": payload_analysis[
                    "all_exact_payload_hashes_match"
                ],
                "conv_blocked": len(conv_stages),
                "scalar_proven": len(scalar_stages),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not structural_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
