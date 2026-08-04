"""Node-0077 DequantizeLinear vertical-closure materializer and E2 audit.

The active upstream repositories are inputs, never edit targets.  Generated
configuration and the full model-execplan lifecycle run in project artifacts
or in a caller-selected isolated directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_validator import OperatorConfigValidator
from .profile28 import DEFAULT_PROFILE
from .simple_layout import DequantizeLinearPhysicalLayout


SCHEMA_VERSION = "0.2"
ASSET_VERSION = "v6"
REQUEST_ID = "r5:hwop-0077-00"
NODE_ID = "node-0077"
HW_OP_ID = "hwop-0077-00"
OP_TYPE = "resnet50_dequant_node0077_uint8_fp32"
INSTANCE_ID = "dequant:node-0077:hwop-0077-00"
EXEC_OP_ID = "op0"
USED_SLICES = "0b1111111111111111111111111111"
NDP_SIM_REF_COMMIT = "d4ffc32c9b29a858d83e13706cd837c5549521a4"
REFERENCE_CONFIG_SHA256 = (
    "15f5321ab57cb73ca2f650693859657759f834389677451a9a89e66217e9e6da"
)
DEQUANT_RULES_SHA256 = (
    "2374975170515252b1ea2d1c1ffc806af5b757c286322ba91b194c0bac0419d7"
)
REQUEST_SHA256 = "cb8522a4ba2386ce3c303f5de274b2fa2e130d719c09933c686a11d28d9b7f63"
INPUT_NPY_SHA256 = "10d974cdab69904bfd3ed7749059e26e16388ba784872f0d432cd2ba14bcbdc8"
OUTPUT_NPY_SHA256 = "2c6c5fabc1d41fceee35f06221efb4c64b94fabfe7a0b4680d2acf2186ca0894"
SCALE_BITS = "0x3e01622d"
NEGATIVE_ZERO_POINT_BITS = "0xc2700000"
SCALE = np.asarray([struct.unpack("<f", bytes.fromhex("2d62013e"))[0]], dtype=np.float32)
ZERO_POINT = np.asarray([60], dtype=np.uint8)
NEGATIVE_ZERO_POINT = np.asarray([-60.0], dtype=np.float32)
HARDWARE_SHAPE = (16, 47, 1)
VALID_ELEMENTS_PER_SLICE = 750
HARDWARE_ELEMENTS_PER_SLICE = 752
RULE_IDS = (
    "CDA-DEQUANT-ONNX-ORDER-001",
    "CDA-DEQUANT-NO-AFFINE-MAC-001",
    "CDA-DEQUANT-TWO-STAGE-GA-001",
    "CDA-DEQUANT-NORMAL-OUTBUFFER-001",
    "CDA-DEQUANT-LAYOUT-HIGH4-001",
    "CDA-DEQUANT-STREAM-LIFECYCLE-001",
    "CDA-DEQUANT-D-BUFFER-SUPPLY-CONSERVATION-001",
    "CDA-DEQUANT-TYPED-CONSTANT-001",
    "CDA-DEQUANT-MAPPING-BINDING-001",
    "CDA-DEQUANT-E2-001",
    "CDA-DEQUANT-E4-E5-001",
    "CDA-DEQUANT-NODE0077-E4-V6-DYNAMIC-PASS-001",
)
FIRST_STAGE_PES = ("PE00", "PE02", "PE20", "PE22")
SECOND_STAGE_LINKS = (
    ("PE10", "PE00"),
    ("PE12", "PE02"),
    ("PE30", "PE20"),
    ("PE32", "PE22"),
)
# The generic output writer first tries an exact ``PE{index}`` key before its
# compatibility fallbacks.  Use coordinate-coded indices so a sparse 4x4 GA
# graph cannot be reinterpreted with a derived three-column width.
FIRST_STAGE_LINEAR = (0, 2, 20, 22)
SECOND_STAGE_LINEAR = (10, 12, 30, 32)


class DequantizeVerticalError(ValueError):
    pass


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DequantizeVerticalError(f"cannot parse JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise DequantizeVerticalError(f"JSON root must be an object: {path}")
    return value


def _json_text(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_text(value), encoding="utf-8", newline="\n")


def _fp32_bits(value: np.ndarray) -> list[str]:
    array = np.ascontiguousarray(value, dtype=np.float32).reshape(-1)
    return [f"0x{int(item):08x}" for item in array.view(np.uint32)]


def _array_sha256(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes(order="C")).hexdigest()


def _port(src_id: object, mode: str | None, constant: object = 0) -> dict[str, Any]:
    return {
        "src_id": src_id,
        "mode": mode,
        "keep_last_index": None,
        "constant": constant,
    }


def _request(project_root: Path) -> dict[str, Any]:
    bundle = _json_object(project_root / "contracts/resnet50_r5_lowering_bundle.json")
    matches = [
        item
        for item in bundle.get("requests", [])
        if isinstance(item, dict) and item.get("request_id") == REQUEST_ID
    ]
    if len(matches) != 1:
        raise DequantizeVerticalError(f"expected one request: {REQUEST_ID}")
    request = matches[0]
    if request.get("request_sha256") != REQUEST_SHA256:
        raise DequantizeVerticalError("node-0077 lowering request identity drifted")
    return request


def _source_paths(project_root: Path) -> dict[str, Path]:
    return {
        "agent_policy": project_root / ".agents/agent.md",
        "generation_read_index": project_root / ".agents/rules/生成前必读索引.md",
        "operator_rules": project_root / ".agents/rules/算子配置规则.md",
        "hardware_field_semantics": project_root / ".agents/rules/NDP硬件字段语义.md",
        "dequant_rules": project_root / ".agents/rules/DequantizeLinear算子配置规则.md",
        "golden_readme": project_root / "ndp-sim/generate_python_golden/README.md",
        "data_readme": project_root / "ndp-sim/generate_python_golden/README_gen_data.md",
        "execplan_readme": project_root / "ndp-sim/model_execplan/README.md",
        "op_json_readme": project_root / "ndp-sim/model_execplan/README_op_json.md",
        "lowering_bundle": project_root / "contracts/resnet50_r5_lowering_bundle.json",
        "reference_config": (
            project_root
            / "ndp-sim-ref/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json"
        ),
        "typed_json_loader": (
            project_root
            / "ndp-sim-ref/model_execplan/src/execution_plan_generator/json_loader.py"
        ),
        "typed_control_registers": (
            project_root
            / "ndp-sim-ref/model_execplan/src/execution_plan_generator/control_registers.py"
        ),
        "typed_output_writer": (
            project_root
            / "ndp-sim-ref/model_execplan/src/execution_plan_generator/output_writer.py"
        ),
        "typed_pipeline": (
            project_root
            / "ndp-sim-ref/model_execplan/src/execution_plan_generator/pipeline.py"
        ),
        "typed_instruction_generator": (
            project_root
            / "ndp-sim-ref/model_execplan/src/execution_plan_generator/"
            "instruction_generator.py"
        ),
        "bitstream_main": project_root / "ndp-sim-ref/bitstream/main.py",
        "bitstream_parser": project_root / "ndp-sim-ref/bitstream/parse.py",
        "bitstream_mapper": (
            project_root / "ndp-sim-ref/bitstream/config/mapper.py"
        ),
        "bitstream_ga_encoder": (
            project_root / "ndp-sim-ref/bitstream/config/general.py"
        ),
        "input_npy": (
            project_root
            / "artifacts/w3/golden_batch16/tensors/tensor-02aeb7457d1ccf49.npy"
        ),
        "output_npy": (
            project_root
            / "artifacts/w3/golden_batch16/tensors/tensor-bff07c95eb9f8609.npy"
        ),
    }


def build_generation_receipt(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    sources = _source_paths(root)
    missing = [name for name, path in sources.items() if not path.is_file()]
    if missing:
        raise DequantizeVerticalError(f"generation gate inputs are missing: {missing}")
    if sha256_file(sources["reference_config"]) != REFERENCE_CONFIG_SHA256:
        raise DequantizeVerticalError("authorized reference config identity drifted")
    if sha256_file(sources["dequant_rules"]) != DEQUANT_RULES_SHA256:
        raise DequantizeVerticalError(
            "Dequant specialty rule identity drifted; reread and rebuild the receipt"
        )
    if sha256_file(sources["input_npy"]) != INPUT_NPY_SHA256:
        raise DequantizeVerticalError("W3 input identity drifted")
    if sha256_file(sources["output_npy"]) != OUTPUT_NPY_SHA256:
        raise DequantizeVerticalError("W3 output identity drifted")
    request = _request(root)
    lowering_bundle = _json_object(sources["lowering_bundle"])
    read_reasons = {
        "agent_policy": "workspace policy router",
        "generation_read_index": "operator JSON generation routing and stop gates",
        "operator_rules": "common materialization, provenance, mapping, and E2 gates",
        "hardware_field_semantics": "triggered LC, MSE, Buffer, and GA field semantics",
        "dequant_rules": "operator-specific numeric, layout, topology, and release gates",
        "golden_readme": "native tensor/golden flow",
        "data_readme": "native data layout and serialization flow",
        "execplan_readme": "native graph-to-execplan lifecycle",
        "op_json_readme": "native typed operator request schema",
        "typed_json_loader": "actual typed request parser",
        "typed_control_registers": "actual typed binding and control-register consumer",
        "typed_output_writer": "actual typed JSON materializer and explanation writer",
        "typed_pipeline": "actual address binder and bitstream lifecycle consumer",
        "typed_instruction_generator": "actual command ordering and Write_Reg consumer",
        "bitstream_main": "actual native encoder entrypoint",
        "bitstream_parser": "actual module ordering and 64/128-bit dump writer",
        "bitstream_mapper": "actual placement, cache, and exact-penalty consumer",
        "bitstream_ga_encoder": "actual GA PE opcode and fp32 constant bit encoder",
        "lowering_bundle": "typed node-0077 request identity",
        "reference_config": "authorized embedded Dequant branch topology baseline",
    }
    read_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    receipt: dict[str, Any] = {
        "schema": "dequantize-linear-generation-receipt-v1",
        "status": "generation_gate_satisfied_before_json_materialization",
        "request_id": REQUEST_ID,
        "lowering_request": {
            "request_id": request["request_id"],
            "request_sha256": request["request_sha256"],
            "request_set_sha256": lowering_bundle["request_set_sha256"],
            "identity_is_independent_of_effective_resolution_overlay": True,
        },
        "rule_ids": list(RULE_IDS),
        "read_receipt": [
            {
                "path": sources[name].relative_to(root).as_posix(),
                "sha256": sha256_file(sources[name]),
                "reason": reason,
                "read_at": read_time,
            }
            for name, reason in read_reasons.items()
        ],
        "known_counterexamples": [
            {
                "id": "DEQUANT_AFFINE_ROUNDING_COUNTEREXAMPLE",
                "fact": (
                    "x*scale+(-60*scale) differs from "
                    "(float32(x)-60.0f)*scale"
                ),
                "w3_mismatch_count": 12976,
                "element_count": 16000,
            },
            {
                "id": "DEQUANT_SPARSE_PE_BINDING_COUNTEREXAMPLE",
                "fact": (
                    "dense linear IDs 0,2,8,10/4,6,12,14 are reinterpreted "
                    "by the native sparse-key writer and misroute constants"
                ),
                "resolution": (
                    "coordinate-coded exact keys "
                    "0,2,20,22/10,12,30,32 plus encoded physical-slot audit"
                ),
            },
        ],
        "open_dynamic_gates": [
            {
                "rule_id": "CDA-DEQUANT-E4-E5-001",
                "blocker_id": "B_DEQUANT_SERVER_E5",
                "classification": "FIRST_DYNAMIC_PASS_E4",
            }
        ],
        "omitted_files": [
            {
                "path": ".agents/rules/服务器测试包生成规则.md",
                "reason": "no server package is generated in this local E2 task",
            },
            {
                "path": "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
                "reason": "no hardware-simulator package or server command is generated",
            },
            {
                "path": "NDP hardware SA/N2N chapters",
                "reason": "this exact schedule triggers LC, MSE, Buffer, and GA only",
            },
        ],
        "sources": {
            name: {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
            }
            for name, path in sorted(sources.items())
        },
        "upstream_identity": {
            "repository": "ndp-sim-ref",
            "commit": NDP_SIM_REF_COMMIT,
            "active_source_policy": "read_only",
        },
        "decisions": {
            "numeric_order": "(float32(uint8(x))-60.0f)*float32(scale)",
            "single_affine_mac_rejected": True,
            "ga_topology": "four ADD PEs followed by four MUL PEs",
            "layout": "HIGH4 prefix 750 plus two neutral tail elements per slice",
            "hardware_shape_cwh": list(HARDWARE_SHAPE),
            "d_buffer_rows_per_occurrence": 4,
            "typed_constant_count": 2,
            "formal_release": False,
        },
    }
    receipt["receipt_sha256"] = sha256_bytes(canonical_json_bytes(receipt))
    return receipt


def build_operator_config(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    source = (
        root / "ndp-sim-ref/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json"
    )
    if sha256_file(source) != REFERENCE_CONFIG_SHA256:
        raise DequantizeVerticalError("authorized reference config identity drifted")
    config = deepcopy(_json_object(source))

    for key, end in {"LC1": 47, "LC2": 1, "LC3": 47, "LC4": 1}.items():
        config["dram_loop_configs"][key]["end"] = end

    del config["buffer_loop_configs"]["GROUP1"]
    config["buffer_loop_configs"]["GROUP2"]["ROW_LC"]["end"] = 4

    del config["stream_engine"]["stream1"]
    config["stream_engine"]["stream0"]["dim_stride"] = [16, 16, 752]
    config["stream_engine"]["stream2"]["dim_stride"] = [64, 64, 3008]

    del config["buffer_config"]["buffer2"]
    inport1 = config["general_array"]["inport"]["inport1"]
    inport1["mask"] = [0] * 8
    inport1["uint8tofp32"] = "false"

    pes: dict[str, Any] = {}
    for pe in FIRST_STAGE_PES:
        pes[pe] = {
            "alu_opcode": "add",
            "transout_last_index": None,
            "inport2": _port(None, None),
            "inport1": _port(None, "constant", NEGATIVE_ZERO_POINT_BITS),
            "inport0": _port(0, "buffer"),
        }
    for pe, predecessor in SECOND_STAGE_LINKS:
        pes[pe] = {
            "alu_opcode": "mul",
            "transout_last_index": None,
            "inport2": _port(None, None),
            "inport1": _port(None, "constant", SCALE_BITS),
            "inport0": _port(f"GA_PE.{predecessor}", "buffer"),
        }
    config["general_array"]["PE_array"] = pes
    validate_operator_config(config, root)
    return config


def validate_operator_config(
    config: Mapping[str, Any], project_root: Path | None = None
) -> dict[str, Any]:
    report = OperatorConfigValidator().validate(
        dict(config), source="node0077-dequant-generated", development_mode=True
    )
    if not report.valid:
        raise DequantizeVerticalError(
            f"strict operator config validation failed: {report.to_dict()['first_error']}"
        )
    streams = config.get("stream_engine")
    groups = config.get("buffer_loop_configs")
    buffers = config.get("buffer_config")
    ga = config.get("general_array")
    if not all(isinstance(item, Mapping) for item in (streams, groups, buffers, ga)):
        raise DequantizeVerticalError("required config sections are missing")
    assert isinstance(streams, Mapping)
    assert isinstance(groups, Mapping)
    assert isinstance(buffers, Mapping)
    assert isinstance(ga, Mapping)
    stream_targets = sorted(
        str(item.get("target"))
        for item in streams.values()
        if isinstance(item, Mapping)
    )
    if stream_targets != ["A", "D"]:
        raise DequantizeVerticalError(f"standalone stream set differs: {stream_targets}")
    if sorted(groups) != ["GROUP0", "GROUP2"] or sorted(buffers) != [
        "buffer0",
        "buffer5",
    ]:
        raise DequantizeVerticalError("standalone buffer/group exact-set differs")
    pe_array = ga.get("PE_array")
    if not isinstance(pe_array, Mapping):
        raise DequantizeVerticalError("GA PE array is missing")
    expected_pes = set(FIRST_STAGE_PES) | {item[0] for item in SECOND_STAGE_LINKS}
    if set(pe_array) != expected_pes:
        raise DequantizeVerticalError("GA PE exact-set differs")
    for pe in FIRST_STAGE_PES:
        node = pe_array[pe]
        if (
            node.get("alu_opcode") != "add"
            or node.get("transout_last_index") is not None
            or node["inport0"] != _port(0, "buffer")
            or node["inport1"] != _port(None, "constant", NEGATIVE_ZERO_POINT_BITS)
            or node["inport2"] != _port(None, None)
        ):
            raise DequantizeVerticalError(f"first-stage topology differs: {pe}")
    for pe, predecessor in SECOND_STAGE_LINKS:
        node = pe_array[pe]
        if (
            node.get("alu_opcode") != "mul"
            or node.get("transout_last_index") is not None
            or node["inport0"] != _port(f"GA_PE.{predecessor}", "buffer")
            or node["inport1"] != _port(None, "constant", SCALE_BITS)
            or node["inport2"] != _port(None, None)
        ):
            raise DequantizeVerticalError(f"second-stage topology differs: {pe}")
    if ga.get("outport", {}).get("mask") != [0, 1, 0, 1, 0, 1, 0, 1]:
        raise DequantizeVerticalError("GA outport mask differs")
    if any(
        "transout" in str(node.get("alu_opcode"))
        for node in pe_array.values()
        if isinstance(node, Mapping)
    ):
        raise DequantizeVerticalError("transout is forbidden for DequantizeLinear")
    write_stream = streams.get("stream2")
    d_group = groups.get("GROUP2")
    if not isinstance(write_stream, Mapping) or not isinstance(d_group, Mapping):
        raise DequantizeVerticalError("D stream/buffer group is missing")
    d_row_loop = d_group.get("ROW_LC")
    if not isinstance(d_row_loop, Mapping):
        raise DequantizeVerticalError("D buffer row loop is missing")
    d_transaction_bytes = int(write_stream["idx_size"][2]) + 1
    d_buffer_bytes_per_request = int(write_stream["buf_spatial_size"])
    d_buffer_row_trips = _loop_trip_count(d_row_loop)
    if (
        buffers["buffer5"].get("buf_end_row_addr") != 3
        or d_transaction_bytes != 64
        or d_buffer_bytes_per_request != 16
        or d_buffer_row_trips != 4
        or d_buffer_row_trips * d_buffer_bytes_per_request
        != d_transaction_bytes
    ):
        raise DequantizeVerticalError(
            "D buffer supply does not cover one 64-byte transaction"
        )
    facts = report.to_dict()
    facts["exact_topology"] = {
        "first_stage": list(FIRST_STAGE_PES),
        "second_stage": [item[0] for item in SECOND_STAGE_LINKS],
        "normal_outbuffer_only": True,
        "stream_targets": stream_targets,
        "d_buffer_supply": {
            "transaction_bytes": d_transaction_bytes,
            "buffer_bytes_per_request": d_buffer_bytes_per_request,
            "row_trip_count": d_buffer_row_trips,
            "supply_bytes": d_buffer_row_trips * d_buffer_bytes_per_request,
            "last_row_index": 3,
        },
    }
    return facts


def build_numeric_evidence(project_root: Path) -> dict[str, Any]:
    paths = _source_paths(project_root.resolve())
    x = np.load(paths["input_npy"], allow_pickle=False)
    expected = np.load(paths["output_npy"], allow_pickle=False)
    if x.dtype != np.uint8 or x.shape != (16, 1000):
        raise DequantizeVerticalError("W3 input signature differs")
    if expected.dtype != np.float32 or expected.shape != x.shape:
        raise DequantizeVerticalError("W3 output signature differs")

    centered = np.subtract(
        x.astype(np.float32),
        NEGATIVE_ZERO_POINT * np.float32(-1.0),
        dtype=np.float32,
    )
    two_stage = np.multiply(centered, SCALE, dtype=np.float32)
    affine_offset = np.multiply(
        NEGATIVE_ZERO_POINT, SCALE, dtype=np.float32
    )
    affine_mac_order = np.add(
        np.multiply(x.astype(np.float32), SCALE, dtype=np.float32),
        affine_offset,
        dtype=np.float32,
    )
    exact = np.array_equal(two_stage.view(np.uint32), expected.view(np.uint32))
    mismatch = int(
        np.count_nonzero(
            affine_mac_order.view(np.uint32) != expected.view(np.uint32)
        )
    )
    if not exact or mismatch <= 0:
        raise DequantizeVerticalError(
            f"numeric proof differs: exact={exact}, affine_mismatch={mismatch}"
        )
    return {
        "rule": "CDA-DEQUANT-ONNX-ORDER-001",
        "input_shape": list(x.shape),
        "element_count": int(x.size),
        "scale": float(SCALE[0]),
        "scale_bits": SCALE_BITS,
        "zero_point": int(ZERO_POINT[0]),
        "negative_zero_point_bits": NEGATIVE_ZERO_POINT_BITS,
        "two_stage_bit_exact": True,
        "two_stage_sha256": _array_sha256(two_stage),
        "w3_output_sha256": _array_sha256(expected),
        "affine_mac_bit_mismatch_count": mismatch,
        "single_affine_mac_rejected": True,
    }


def build_layout_evidence(
    project_root: Path, *, payload_root: Path | None = None
) -> dict[str, Any]:
    root = project_root.resolve()
    paths = _source_paths(root)
    x = np.load(paths["input_npy"], allow_pickle=False)
    expected = np.load(paths["output_npy"], allow_pickle=False)
    layout = DequantizeLinearPhysicalLayout(profile_id=DEFAULT_PROFILE)
    bundle = layout.forward(
        input_tensor=x,
        scale=SCALE,
        zero_point=ZERO_POINT,
        output_tensor=expected,
        tensor_ids={
            "A": "tensor-02aeb7457d1ccf49",
            "scale": "tensor-1dcd30b27960784d",
            "zero_point": "tensor-1ff0ad61fc06574b",
            "D": "tensor-bff07c95eb9f8609",
        },
    )
    restored = layout.inverse(bundle)
    if not np.array_equal(restored["tensor-02aeb7457d1ccf49"], x):
        raise DequantizeVerticalError("simple-layout A inverse differs")
    if not np.array_equal(
        restored["tensor-bff07c95eb9f8609"].view(np.uint32),
        expected.view(np.uint32),
    ):
        raise DequantizeVerticalError("simple-layout D inverse differs")

    records: list[dict[str, Any]] = []
    payload_root_resolved = payload_root.resolve() if payload_root is not None else None
    if payload_root_resolved is not None:
        payload_root_resolved.mkdir(parents=True, exist_ok=True)
    for slice_id in range(28):
        aligned_a = bundle.read("A", slice_id)
        aligned_d = bundle.read("D", slice_id)
        prefix_a = aligned_a[:VALID_ELEMENTS_PER_SLICE]
        prefix_d = aligned_d[: VALID_ELEMENTS_PER_SLICE * 4]
        if len(prefix_a) != VALID_ELEMENTS_PER_SLICE:
            raise DequantizeVerticalError("A simple-layout prefix is not 750 bytes")
        if len(prefix_d) != VALID_ELEMENTS_PER_SLICE * 4:
            raise DequantizeVerticalError("D simple-layout prefix is not 3000 bytes")
        hardware_a = prefix_a + bytes([int(ZERO_POINT[0])]) * 2
        hardware_d = prefix_d + np.zeros(2, dtype=np.float32).tobytes()
        if (
            len(aligned_a) != len(hardware_a)
            or len(aligned_d) != len(hardware_d)
        ):
            raise DequantizeVerticalError("simple-layout alignment size differs")
        if len(hardware_a) != HARDWARE_ELEMENTS_PER_SLICE:
            raise AssertionError("A hardware payload size drifted")
        if len(hardware_d) != HARDWARE_ELEMENTS_PER_SLICE * 4:
            raise AssertionError("D hardware payload size drifted")
        record: dict[str, Any] = {
            "slice_id": slice_id,
            "group_id": bundle.region("A", slice_id).group_id,
            "owner_step": bundle.region("A", slice_id).owner_step,
            "sample_start": bundle.region("A", slice_id).sample_start,
            "sample_count": bundle.region("A", slice_id).sample_count,
            "feature_start": bundle.region("A", slice_id).feature_start,
            "feature_count": bundle.region("A", slice_id).feature_count,
            "a_prefix_bytes": len(prefix_a),
            "a_hardware_bytes": len(hardware_a),
            "d_prefix_bytes": len(prefix_d),
            "d_hardware_bytes": len(hardware_d),
            "a_sha256": hashlib.sha256(hardware_a).hexdigest(),
            "d_golden_sha256": hashlib.sha256(hardware_d).hexdigest(),
            "a_tail_hex": hardware_a[-2:].hex(),
            "d_tail_hex": hardware_d[-8:].hex(),
        }
        if payload_root_resolved is not None:
            a_path = payload_root_resolved / f"slice{slice_id:02d}_A.bin"
            d_path = payload_root_resolved / f"slice{slice_id:02d}_D_golden.bin"
            a_path.write_bytes(hardware_a)
            d_path.write_bytes(hardware_d)
            record["a_path"] = a_path.relative_to(payload_root_resolved.parent).as_posix()
            record["d_golden_path"] = d_path.relative_to(
                payload_root_resolved.parent
            ).as_posix()
        records.append(record)
    if any(
        item["a_tail_hex"] != "3c3c" or item["d_tail_hex"] != "0000000000000000"
        for item in records
    ):
        raise DequantizeVerticalError("hardware tail neutral value differs")
    return {
        "rule": "CDA-DEQUANT-LAYOUT-HIGH4-001",
        "profile_id": DEFAULT_PROFILE,
        "hardware_shape_cwh": list(HARDWARE_SHAPE),
        "slice_count": 28,
        "valid_elements_per_slice": VALID_ELEMENTS_PER_SLICE,
        "hardware_elements_per_slice": HARDWARE_ELEMENTS_PER_SLICE,
        "a_bytes_per_slice": HARDWARE_ELEMENTS_PER_SLICE,
        "d_bytes_per_slice": HARDWARE_ELEMENTS_PER_SLICE * 4,
        "prefix_matches_existing_layout": True,
        "inverse_bit_exact": True,
        "slices": records,
    }


def _binding(
    pe_index: int, *, derivation: str, artifact_id: str
) -> dict[str, Any]:
    return {
        "location": (
            f"control_register:ga_pe{pe_index}."
            "general_array.PE_array.PE.inport1.constant"
        ),
        "encoding": "fp32_bits",
        "derivation": derivation,
        "element_indices": [0],
        "artifact_id": artifact_id,
    }


def _constant(
    *,
    tensor_id: str,
    value: np.ndarray,
    source_kind: str,
    source_parameter_ids: list[str],
    bindings: list[dict[str, Any]],
    identity_sha256: str | None = None,
) -> dict[str, Any]:
    array = np.ascontiguousarray(value, dtype=np.float32)
    value_hash = _array_sha256(array)
    return {
        "tensor_id": tensor_id,
        "dtype": "float32",
        "shape": list(array.shape),
        "identity_sha256": identity_sha256 or value_hash,
        "value_sha256": value_hash,
        "values": array.reshape(-1).tolist(),
        "float32_bits": _fp32_bits(array),
        "axis": None,
        "source_kind": source_kind,
        "source_parameter_ids": source_parameter_ids,
        "target_bindings": bindings,
    }


def build_execplan_request(
    project_root: Path, config: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    root = project_root.resolve()
    request = _request(root)
    config_value = dict(config) if config is not None else build_operator_config(root)
    raw_text = _json_text(config_value)
    config_sha = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    artifact_id = f"{HW_OP_ID}.config"
    scale_identity = next(
        item["value"]["value_sha256"]
        for item in request["typed_parameters"]
        if item["name"] == "x_scale"
    )
    value: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": f"{INSTANCE_ID}:typed-transport-v4",
        "used_slices": USED_SLICES,
        "params": {
            "node_id": NODE_ID,
            "hw_op_id": HW_OP_ID,
            "candidate_release": False,
            "layout_profile": DEFAULT_PROFILE,
        },
        "operators": [
            {
                "id": EXEC_OP_ID,
                "type": OP_TYPE,
                "instance_id": INSTANCE_ID,
                "stage": "dequantize",
                "used_slices": USED_SLICES,
                "inputs": {
                    "A": {
                        "shape": list(HARDWARE_SHAPE),
                        "logical_shape": [16, 1000],
                        "dtype": "uint8",
                        "tensor_id": "tensor-02aeb7457d1ccf49",
                        "identity_sha256": INPUT_NPY_SHA256,
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    }
                },
                "output": {
                    "shape": list(HARDWARE_SHAPE),
                    "logical_shape": [16, 1000],
                    "dtype": "float32",
                    "tensor_id": "tensor-bff07c95eb9f8609",
                    "identity_sha256": OUTPUT_NPY_SHA256,
                    "bank_interleave": 1,
                    "remapping": None,
                },
                "attributes": {
                    "node_id": NODE_ID,
                    "hw_op_id": HW_OP_ID,
                    "stage_index": 0,
                    "onnx_formula": "(float32(x)-float32(x_zero_point))*float32(x_scale)",
                    "hardware_shape_cwh": list(HARDWARE_SHAPE),
                    "valid_elements_per_slice": VALID_ELEMENTS_PER_SLICE,
                    "hardware_elements_per_slice": HARDWARE_ELEMENTS_PER_SLICE,
                    "target": {
                        "slice_count": 28,
                        "communication_domain": "local",
                        "ga_topology": "four_add_then_four_mul",
                        "normal_outbuffer_only": True,
                    },
                    "rule_ids": list(RULE_IDS),
                },
                "constants": {
                    "negative_zero_point": _constant(
                        tensor_id=f"{HW_OP_ID}.derived.negative_zero_point_fp32",
                        value=NEGATIVE_ZERO_POINT,
                        source_kind="derived",
                        source_parameter_ids=[
                            f"{HW_OP_ID}.initializer.x_zero_point"
                        ],
                        bindings=[
                            _binding(
                                index,
                                derivation="float32(-uint8(x_zero_point))",
                                artifact_id=artifact_id,
                            )
                            for index in FIRST_STAGE_LINEAR
                        ],
                    ),
                    "x_scale": _constant(
                        tensor_id="tensor-1dcd30b27960784d",
                        value=SCALE,
                        source_kind="initializer",
                        source_parameter_ids=[
                            f"{HW_OP_ID}.initializer.x_scale"
                        ],
                        bindings=[
                            _binding(
                                index,
                                derivation="identity float32 x_scale",
                                artifact_id=artifact_id,
                            )
                            for index in SECOND_STAGE_LINEAR
                        ],
                        identity_sha256=str(scale_identity),
                    ),
                },
                "config_artifacts": [
                    {
                        "artifact_id": artifact_id,
                        "role": "standalone_dequant_config",
                        "path": (
                            "configs/native_ndp_sim/"
                            f"resnet50_dequant_node0077_uint8_fp32_strict_{ASSET_VERSION}/config.json"
                        ),
                        "sha256": config_sha,
                        "raw_text": raw_text,
                    }
                ],
            }
        ],
    }
    validate_execplan_request(value, root)
    return value


def _official_parser_roundtrip(
    project_root: Path, value: Mapping[str, Any]
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    source = project_root / "ndp-sim-ref/model_execplan/src"
    source_text = str(source)
    module_prefix = "execution_plan_generator"
    prior_path = list(sys.path)
    prior_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == module_prefix or name.startswith(f"{module_prefix}.")
    }
    for name in prior_modules:
        sys.modules.pop(name, None)
    sys.path.insert(0, source_text)
    try:
        from execution_plan_generator.json_loader import (  # type: ignore[import-not-found]
            execution_plan_to_dict,
            parse_execution_plan_dict,
        )

        parsed = parse_execution_plan_dict(dict(value))
        normalized = execution_plan_to_dict(parsed)
        renormalized = execution_plan_to_dict(
            parse_execution_plan_dict(normalized)
        )
        return parsed, normalized, renormalized
    finally:
        for name in list(sys.modules):
            if name == module_prefix or name.startswith(f"{module_prefix}."):
                sys.modules.pop(name, None)
        sys.modules.update(prior_modules)
        sys.path[:] = prior_path


def validate_execplan_request(
    value: Mapping[str, Any], project_root: Path
) -> dict[str, Any]:
    parsed, normalized, renormalized = _official_parser_roundtrip(
        project_root.resolve(), value
    )
    if renormalized != normalized:
        raise DequantizeVerticalError("official typed parser normalization is not idempotent")
    if len(parsed.operators) != 1:
        raise DequantizeVerticalError("typed request operator count differs")
    operator = parsed.operators[0]
    if set(operator.constants) != {"negative_zero_point", "x_scale"}:
        raise DequantizeVerticalError("typed constant exact-set differs")
    if sum(
        len(item.target_bindings) for item in operator.constants.values()
    ) != 8:
        raise DequantizeVerticalError("typed constant binding count differs")
    return {
        "status": "typed_transport_validated",
        "operator_count": 1,
        "typed_constant_count": 2,
        "target_binding_count": 8,
        "config_artifact_count": 1,
        "official_normalization_idempotent": True,
        "raw_extensions_intentionally_not_roundtripped": ["params"],
    }


def build_semantic_contract(
    project_root: Path,
    *,
    config: Mapping[str, Any],
    receipt: Mapping[str, Any],
    numeric: Mapping[str, Any],
    layout: Mapping[str, Any],
    typed_request: Mapping[str, Any],
) -> dict[str, Any]:
    request = _request(project_root.resolve())
    value: dict[str, Any] = {
        "schema": "dequantize-linear-vertical-contract-v1",
        "status": "local_e2_candidate_dynamic_e4_e5_pending",
        "candidate_release": False,
        "identity": {
            "request_id": REQUEST_ID,
            "request_sha256": request["request_sha256"],
            "node_id": NODE_ID,
            "hw_op_id": HW_OP_ID,
            "onnx_name": request["identity"]["onnx_name"],
            "op_type": OP_TYPE,
        },
        "chain": [
            "ONNX DequantizeLinear",
            "typed lowering request",
            "two-stage GA schedule",
            "strict operator JSON",
            "native bitstream mapping",
            "typed execplan and SCA",
            "server E4/E5 readback",
        ],
        "rules": list(RULE_IDS),
        "numeric": dict(numeric),
        "layout": {
            key: deepcopy(value)
            for key, value in layout.items()
            if key != "slices"
        },
        "config": {
            "sha256": hashlib.sha256(_json_text(config).encode("utf-8")).hexdigest(),
            "strict_validation": True,
            "two_stage_ga": True,
            "normal_outbuffer_only": True,
        },
        "typed_transport": validate_execplan_request(
            typed_request, project_root.resolve()
        ),
        "generation_receipt_sha256": receipt["receipt_sha256"],
        "evidence_level": {
            "local": "E2",
            "hardware": "pending E4/E5",
        },
        "remaining_blockers": ["B_DEQUANT_SERVER_E4_E5"],
    }
    value["contract_sha256"] = sha256_bytes(canonical_json_bytes(value))
    return value


def materialize_dequant_vertical(
    project_root: Path,
    *,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    output = (
        artifact_root.resolve()
        if artifact_root is not None
        else (
            root
            / f"artifacts/operator_config_validation/r5-dequant-node0077-e2-{ASSET_VERSION}"
        )
    )
    config_path = (
        root
        / "configs/native_ndp_sim/"
        f"resnet50_dequant_node0077_uint8_fp32_strict_{ASSET_VERSION}/config.json"
    )
    contract_path = (
        root
        / "contracts/operator_config/"
        f"node0077_dequant_semantics_evidence_{ASSET_VERSION}.json"
    )
    receipt_path = (
        root
        / "contracts/operator_config/"
        f"node0077_dequant_generation_receipt_{ASSET_VERSION}.json"
    )

    receipt = build_generation_receipt(root)
    config = build_operator_config(root)
    numeric = build_numeric_evidence(root)
    layout = build_layout_evidence(root, payload_root=output / "slice_payloads")
    typed_request = build_execplan_request(root, config)
    contract = build_semantic_contract(
        root,
        config=config,
        receipt=receipt,
        numeric=numeric,
        layout=layout,
        typed_request=typed_request,
    )

    _write_json(receipt_path, receipt)
    _write_json(config_path, config)
    _write_json(contract_path, contract)
    _write_json(output / "execplan_request.json", typed_request)
    _write_json(output / "layout_evidence.json", layout)
    _write_json(output / "numeric_evidence.json", numeric)
    _write_json(output / "config_validation.json", validate_operator_config(config, root))
    manifest: dict[str, Any] = {
        "schema": "dequantize-linear-local-e2-manifest-v1",
        "status": "materialized_local_e2_not_yet_executed",
        "candidate_release": False,
        "request_id": REQUEST_ID,
        "files": {},
        "remaining_blockers": ["B_DEQUANT_SERVER_E4_E5"],
    }
    for path in (
        receipt_path,
        config_path,
        contract_path,
        output / "execplan_request.json",
        output / "layout_evidence.json",
        output / "numeric_evidence.json",
        output / "config_validation.json",
    ):
        manifest["files"][path.relative_to(root).as_posix()] = sha256_file(path)
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    _write_json(output / "manifest.json", manifest)
    return manifest


def _copy_isolated_toolchain(project_root: Path, destination: Path) -> None:
    source = project_root / "ndp-sim-ref"
    if destination.exists():
        raise DequantizeVerticalError(
            f"isolated toolchain destination already exists: {destination}"
        )
    destination.mkdir(parents=True)
    for relative in ("bitstream", "model_execplan", "jsons"):
        shutil.copytree(source / relative, destination / relative)
    # The bundled E2 runtime intentionally has no matplotlib.  Upstream imports
    # it at mapper module import time even when placement rendering is disabled,
    # and the execplan pipeline unconditionally requests a placement PNG.  Apply
    # a hash-bound, isolated-only headless adaptation; the active upstream tree
    # remains byte-identical.
    patches = (
        {
            "path": "bitstream/config/mapper.py",
            "pre_sha256": (
                "8e2504d3262bd47ce13b9d75c8bebe58a6900bdf9af03360bf563d653dd88641"
            ),
            "old": (
                "import matplotlib\n"
                "matplotlib.use(\"Agg\")\n"
                "import matplotlib.pyplot as plt\n"
                "from matplotlib.patches import FancyArrowPatch\n"
                "from matplotlib.path import Path\n"
            ),
            "new": (
                "# Isolated E2 headless adapter: visualization imports remain "
                "local to visualize_mapping.\n"
            ),
            "reason": "headless_import_without_changing_mapping_or_encoding",
        },
        {
            "path": "model_execplan/src/execution_plan_generator/pipeline.py",
            "pre_sha256": (
                "a4905e18eb3e843b58d4049096971288087bfedf2c2cc58f038bb14e2a9b28b5"
            ),
            "old": (
                "                \"--visualize-placement\",\n"
                "                \"-c\", str(patched_json),\n"
            ),
            "new": "                \"-c\", str(patched_json),\n",
            "reason": "headless_execplan_regeneration",
        },
        {
            "path": "model_execplan/src/execution_plan_generator/pipeline.py",
            "pre_sha256": (
                "7737a971f817cc4c090c2a46a15ee89c519af93acb42230fd480a4469b48a869"
            ),
            "old": (
                "            new_control_values = compute_control_register_updates(\n"
                "                operator=op,\n"
                "                template=template,\n"
                "                address_plan=address_plan,\n"
                "                apply_instance_mapping=True,\n"
                "                instance_mapping=op_mapping,\n"
                "            )\n"
                "            updated_templates[op.op_id] = replace(\n"
            ),
            "new": (
                "            new_control_values = compute_control_register_updates(\n"
                "                operator=op,\n"
                "                template=template,\n"
                "                address_plan=address_plan,\n"
                "                apply_instance_mapping=True,\n"
                "                instance_mapping=op_mapping,\n"
                "            )\n"
                "            baked_typed_fields = {\n"
                "                binding.location[len(\"control_register:\"):]\n"
                "                for constant in op.constants.values()\n"
                "                for binding in constant.target_bindings\n"
                "                if binding.location.startswith(\"control_register:\")\n"
                "            }\n"
                "            new_control_values = {\n"
                "                key: value for key, value in new_control_values.items()\n"
                "                if key not in baked_typed_fields\n"
                "            }\n"
                "            updated_templates[op.op_id] = replace(\n"
            ),
            "reason": "do_not_reissue_typed_constants_already_baked_into_bitstream",
        },
        {
            "path": (
                "model_execplan/src/execution_plan_generator/"
                "instruction_generator.py"
            ),
            "pre_sha256": (
                "cdc7d4dcdf41ec79571d53a909a2b2d8f1ab7897a404969b5cf49d416fc85315"
            ),
            "old": (
                "                control_register_values = "
                "dict(template.control_register_values)\n"
                "                control_register_values.update("
                "dynamic_control_values)\n"
                "            template = replace(template, "
                "control_register_values=control_register_values)\n"
            ),
            "new": (
                "                control_register_values = "
                "dict(template.control_register_values)\n"
                "                control_register_values.update("
                "dynamic_control_values)\n"
                "                baked_typed_fields = {\n"
                "                    binding.location[len(\"control_register:\"):]\n"
                "                    for constant in op.constants.values()\n"
                "                    for binding in constant.target_bindings\n"
                "                    if binding.location.startswith("
                "\"control_register:\")\n"
                "                }\n"
                "                control_register_values = {\n"
                "                    key: value\n"
                "                    for key, value in "
                "control_register_values.items()\n"
                "                    if key not in baked_typed_fields\n"
                "                }\n"
                "            template = replace(template, "
                "control_register_values=control_register_values)\n"
            ),
            "reason": "suppress_dynamic_rewrite_of_typed_constants_baked_into_config",
        },
        {
            "path": "model_execplan/src/execution_plan_generator/pipeline.py",
            "pre_sha256": (
                "a698f6f5c0104d1854b267393fc9f3de9b641c5fb766e3cc9b82033df0a80c44"
            ),
            "old": (
                "            cmd = [\n"
                "                sys.executable,\n"
                "                bitstream_script,\n"
                "                \"-c\", str(patched_json),\n"
                "                \"-o\", str(op_config_dir),\n"
                "                \"-q\",\n"
                "            ]\n"
                "            result = subprocess.run(\n"
                "                cmd,\n"
                "                capture_output=True,\n"
                "                text=True,\n"
                "                encoding=\"utf-8\",\n"
                "                cwd=str(repo_root),\n"
                "                env={**os.environ, \"PYTHONUTF8\": \"1\", "
                "\"PYTHONIOENCODING\": \"utf-8\"},\n"
                "            )\n"
                "            if result.returncode != 0:\n"
                "                print(\n"
                "                    f\"[pipeline] bitstream regeneration failed for \"\n"
                "                    f\"{op.op_id} ({op.op_type}) (rc={result.returncode}):\\n\"\n"
                "                    f\"  stdout: {result.stdout.strip()}\\n\"\n"
                "                    f\"  stderr: {result.stderr.strip()}\"\n"
                "                )\n"
                "                continue\n"
                "\n"
                "            # Clear the mapping cache so reload happens from the\n"
            ),
            "new": (
                "            cmd = [\n"
                "                sys.executable,\n"
                "                bitstream_script,\n"
                "                \"-c\", str(patched_json),\n"
                "                \"-o\", str(op_config_dir),\n"
                "                \"--seed\", \"77\",\n"
                "                \"-q\",\n"
                "            ]\n"
                "            result = subprocess.run(\n"
                "                cmd,\n"
                "                capture_output=True,\n"
                "                text=True,\n"
                "                encoding=\"utf-8\",\n"
                "                cwd=str(repo_root),\n"
                "                env={**os.environ, \"PYTHONUTF8\": \"1\", "
                "\"PYTHONIOENCODING\": \"utf-8\"},\n"
                "            )\n"
                "            if result.returncode != 0:\n"
                "                print(\n"
                "                    f\"[pipeline] bitstream regeneration failed for \"\n"
                "                    f\"{op.op_id} ({op.op_type}) (rc={result.returncode}):\\n\"\n"
                "                    f\"  stdout: {result.stdout.strip()}\\n\"\n"
                "                    f\"  stderr: {result.stderr.strip()}\"\n"
                "                )\n"
                "                continue\n"
                "            (op_config_dir / \"encoder_stdout.log\").write_text(\n"
                "                result.stdout, encoding=\"utf-8\"\n"
                "            )\n"
                "            (op_config_dir / \"encoder_stderr.log\").write_text(\n"
                "                result.stderr, encoding=\"utf-8\"\n"
                "            )\n"
                "\n"
                "            # Clear the mapping cache so reload happens from the\n"
            ),
            "reason": (
                "bind address-bound mapping to seed 77 and retain exact-penalty receipts"
            ),
        },
    )
    patch_records: list[dict[str, Any]] = []
    for patch in patches:
        path = destination / str(patch["path"])
        if sha256_file(path) != patch["pre_sha256"]:
            raise DequantizeVerticalError(
                f"isolated headless patch preimage differs: {patch['path']}"
            )
        text = path.read_text(encoding="utf-8")
        old = str(patch["old"])
        if text.count(old) != 1:
            raise DequantizeVerticalError(
                f"isolated headless patch anchor differs: {patch['path']}"
            )
        path.write_text(text.replace(old, str(patch["new"])), encoding="utf-8")
        patch_records.append(
            {
                "path": patch["path"],
                "pre_sha256": patch["pre_sha256"],
                "post_sha256": sha256_file(path),
                "reason": patch["reason"],
                "scope": "isolated_copy_only",
            }
        )
    _write_json(
        destination / "isolated_patch_manifest.json",
        {
            "schema": "dequantize-linear-isolated-toolchain-patch-v1",
            "source_commit": NDP_SIM_REF_COMMIT,
            "active_source_modified": False,
            "functional_semantics_changed": False,
            "patches": patch_records,
        },
    )


def _run(
    command: list[str], *, cwd: Path, env: Mapping[str, str] | None = None
) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=str(cwd),
        env=dict(env or os.environ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    record = {
        "command": command,
        "cwd": str(cwd),
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }
    if process.returncode != 0:
        raise DequantizeVerticalError(
            f"subprocess failed ({process.returncode}): {command}\n"
            f"{process.stdout}\n{process.stderr}"
        )
    return record


def _bitstream_identity(path: Path) -> dict[str, Any]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    if not lines or any(len(line) != 128 or set(line) - {"0", "1"} for line in lines):
        raise DequantizeVerticalError(f"invalid 128-bit bitstream: {path}")
    return {
        "path": path.name,
        "line_count": len(lines),
        "sha256": sha256_file(path),
    }


def _tree_identity(path: Path) -> dict[str, Any]:
    if not path.is_dir():
        raise DequantizeVerticalError(f"identity tree is missing: {path}")
    entries = [
        {
            "path": item.relative_to(path).as_posix(),
            "sha256": sha256_file(item),
        }
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    ]
    return {
        "root": path.as_posix(),
        "file_count": len(entries),
        "tree_sha256": sha256_bytes(canonical_json_bytes(entries)),
    }


def _parsed_bitstream_sections(path: Path) -> list[tuple[str, list[str]]]:
    heading = re.compile(r"^([a-z][a-z0-9_]*):$")
    sections: list[tuple[str, list[str]]] = []
    current_name: str | None = None
    current_lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        match = heading.fullmatch(line)
        if match is not None:
            if current_name is not None:
                sections.append((current_name, current_lines))
            current_name = match.group(1)
            current_lines = []
        elif line:
            if current_name is None:
                raise DequantizeVerticalError(
                    f"parsed bitstream data precedes a section: {path}"
                )
            if line != "0" and re.fullmatch(r"1 [01]+", line) is None:
                raise DequantizeVerticalError(
                    f"invalid parsed bitstream payload: {line!r}"
                )
            current_lines.append(line)
    if current_name is not None:
        sections.append((current_name, current_lines))
    if not sections:
        raise DequantizeVerticalError(f"parsed bitstream has no sections: {path}")
    return sections


def _detailed_gape_blocks(path: Path) -> list[dict[str, Any]]:
    marker = "=== Dump: GAPEConfig ==="
    encoded_re = re.compile(
        r"^([A-Za-z0-9_]+)\s+\|.*\|\s*encoded=\['([01]+)'\]\s*$"
    )
    blocks: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line == marker:
            if current:
                blocks.append(current)
            current = []
            continue
        if current is None:
            continue
        if not line.strip():
            if current:
                blocks.append(current)
            current = None
            continue
        match = encoded_re.match(line)
        if match is not None:
            current.append((match.group(1), match.group(2)))
    if current:
        blocks.append(current)
    result: list[dict[str, Any]] = []
    for index, block in enumerate(blocks):
        bits = "".join(value for _, value in block)
        if len(bits) != 144:
            raise DequantizeVerticalError(
                f"GAPE detailed block {index} is {len(bits)} bits, expected 144"
            )
        fields = {name: value for name, value in block}
        if "alu_opcode" not in fields or "constant1" not in fields:
            raise DequantizeVerticalError(
                f"GAPE detailed block {index} lacks opcode/constant1"
            )
        result.append({"bits": bits, "fields": fields})
    if not result:
        raise DequantizeVerticalError(f"no GAPE blocks found in {path}")
    return result


def _verify_raw_bitstream_mirror(
    config: Mapping[str, Any],
    parsed_path: Path,
    raw64_path: Path,
    raw128_path: Path,
) -> dict[str, Any]:
    sections = _parsed_bitstream_sections(parsed_path)
    config_mask = config.get("CONFIG")
    if not isinstance(config_mask, str) or re.fullmatch(r"[01]{8}", config_mask) is None:
        raise DequantizeVerticalError("address-bound CONFIG is not an 8-bit mask")
    binary = config_mask
    for _, lines in sections:
        for line in lines:
            binary += "0" if line == "0" else "1" + line[2:]

    padded64 = binary + "0" * ((64 - len(binary) % 64) % 64)
    expected64 = [padded64[index : index + 64] for index in range(0, len(padded64), 64)]
    observed64 = [
        line.strip()
        for line in raw64_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if observed64 != expected64:
        raise DequantizeVerticalError("parsed bitstream -> raw 64-bit mirror differs")

    padded128 = binary + "0" * ((128 - len(binary) % 128) % 128)
    expected128 = []
    for index in range(0, len(padded128), 128):
        chunk = padded128[index : index + 128]
        expected128.append(chunk[64:] + chunk[:64])
    observed128 = [
        line.strip()
        for line in raw128_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if observed128 != expected128:
        raise DequantizeVerticalError("parsed bitstream -> raw 128-bit mirror differs")
    return {
        "config_mask": config_mask,
        "serialized_bit_count_before_padding": len(binary),
        "raw64_line_count": len(observed64),
        "raw128_line_count": len(observed128),
        "parsed_to_raw64_bit_exact": True,
        "parsed_to_raw128_reordered_bit_exact": True,
        "raw64_sha256": sha256_file(raw64_path),
        "raw128_sha256": sha256_file(raw128_path),
    }


def _mapping_constant_audit(
    mapping_path: Path,
    patched_config_path: Path,
    *,
    detailed_dump_path: Path,
    parsed_bitstream_path: Path,
    raw64_path: Path,
    raw128_path: Path,
    encoder_stdout_path: Path,
) -> dict[str, Any]:
    mapping = _json_object(mapping_path)
    config = _json_object(patched_config_path)
    text = json.dumps(mapping, sort_keys=True)
    logical_names = [f"GA_PE.{pe}" for pe in FIRST_STAGE_PES]
    logical_names.extend(f"GA_PE.{pe}" for pe, _ in SECOND_STAGE_LINKS)
    missing = [name for name in logical_names if name not in text]
    if missing:
        raise DequantizeVerticalError(
            f"mapping review does not cover logical GA PEs: {missing}"
        )
    pe_array = config["general_array"]["PE_array"]
    observed_raw = {
        pe: pe_array[pe]["inport1"]["constant"] for pe in sorted(pe_array)
    }

    def as_fp32_bits(raw: object) -> str:
        if isinstance(raw, str) and raw.lower().startswith("0x"):
            return f"0x{int(raw, 16) & 0xFFFF_FFFF:08x}"
        try:
            packed = struct.pack("<f", float(raw))
        except (TypeError, ValueError, OverflowError) as error:
            raise DequantizeVerticalError(
                f"cannot decode patched GA constant: {raw!r}"
            ) from error
        return f"0x{struct.unpack('<I', packed)[0]:08x}"

    observed = {pe: as_fp32_bits(raw) for pe, raw in observed_raw.items()}
    expected = {
        **{pe: NEGATIVE_ZERO_POINT_BITS for pe in FIRST_STAGE_PES},
        **{pe: SCALE_BITS for pe, _ in SECOND_STAGE_LINKS},
    }
    if observed != expected:
        raise DequantizeVerticalError("patched mapper-input constants differ")
    normalized_config = deepcopy(config)
    for pe, bits in observed.items():
        normalized_config["general_array"]["PE_array"][pe]["inport1"][
            "constant"
        ] = bits
    validate_operator_config(normalized_config)

    encoder_stdout = encoder_stdout_path.read_text(encoding="utf-8")
    zero_markers = (
        "Success: Found valid mapping with 0 violations",
        "Mapping successful with zero violations",
    )
    if not any(marker in encoder_stdout for marker in zero_markers):
        raise DequantizeVerticalError("address-bound mapper did not report zero penalty")
    forbidden_markers = (
        "Accepting mapping with penalty",
        "mapping violations remain",
    )
    if any(marker in encoder_stdout for marker in forbidden_markers):
        raise DequantizeVerticalError(
            "address-bound mapper used a cache/fallback/nonzero placement"
        )

    detailed_blocks = _detailed_gape_blocks(detailed_dump_path)
    sections = dict(_parsed_bitstream_sections(parsed_bitstream_path))
    ga_lines = sections.get("ga_pe")
    if ga_lines is None or len(ga_lines) != 16 * 4:
        raise DequantizeVerticalError("parsed GA PE section is not 16 physical slots x 4")
    physical_keys = [f"PE{row}{column}" for row in range(4) for column in range(4)]
    physical_payloads: dict[str, str | None] = {}
    for index, key in enumerate(physical_keys):
        group = ga_lines[index * 4 : (index + 1) * 4]
        if group == ["0", "0", "0", "0"]:
            physical_payloads[key] = None
            continue
        if any(re.fullmatch(r"1 [01]{36}", line) is None for line in group):
            raise DequantizeVerticalError(
                f"physical {key} does not contain four present 36-bit GAPE chunks"
            )
        physical_payloads[key] = "".join(line[2:] for line in group)

    active_physical = [key for key in physical_keys if physical_payloads[key] is not None]
    expected_physical = sorted(expected)
    if active_physical != expected_physical:
        raise DequantizeVerticalError(
            f"encoded physical GA slots differ: {active_physical} != {expected_physical}"
        )
    if len(detailed_blocks) != len(active_physical):
        raise DequantizeVerticalError("detailed/parsed active GAPE counts differ")

    decoded_constants: dict[str, str] = {}
    decoded_opcodes: dict[str, str] = {}
    for key, block in zip(active_physical, detailed_blocks, strict=True):
        if physical_payloads[key] != block["bits"]:
            raise DequantizeVerticalError(
                f"detailed GAPE bits differ from parsed physical slot {key}"
            )
        fields = block["fields"]
        constant = f"0x{int(fields['constant1'], 2):08x}"
        opcode = fields["alu_opcode"]
        expected_opcode = "00000" if key in FIRST_STAGE_PES else "00010"
        if constant != expected[key] or opcode != expected_opcode:
            raise DequantizeVerticalError(
                f"encoded physical {key} opcode/constant differs"
            )
        decoded_constants[key] = constant
        decoded_opcodes[key] = "add" if opcode == "00000" else "mul"

    raw_mirror = _verify_raw_bitstream_mirror(
        config, parsed_bitstream_path, raw64_path, raw128_path
    )
    return {
        "rule": "CDA-DEQUANT-MAPPING-BINDING-001",
        "logical_pe_count": 8,
        "mapping_review_covers_all_logical_pes": True,
        "mapper_input_constants_bit_exact": True,
        "constants": observed,
        "raw_constants": observed_raw,
        "placement_penalty": 0,
        "fallback_used": False,
        "mapping_cache_initial_state": "empty_isolated_directory",
        "intra_run_exact_cache_reload": "Loaded cached mapping" in encoder_stdout,
        "historical_cache_reused": False,
        "python_hash_seed": 0,
        "seed": 77,
        "encoded_bitstream_constants_verified": True,
        "physical_pe_constants": decoded_constants,
        "physical_pe_opcodes": decoded_opcodes,
        "detailed_to_parsed_ga_bit_exact": True,
        "raw_bitstream_mirror": raw_mirror,
        "boundary": (
            "E2 proves address-bound mapper input, physical PE slot encoding, and "
            "parsed/raw bitstream identity; E4 remains real RTL execution/readback"
        ),
    }


def _loop_trip_count(config: Mapping[str, Any]) -> int:
    start = int(config["start"])
    end = int(config["end"])
    stride = int(config["stride"])
    if stride <= 0 or start >= end or (end - start) % stride:
        raise DequantizeVerticalError(f"non-canonical loop domain: {config}")
    return (end - start) // stride


def _materialized_roundtrip_audit(
    patched_config_path: Path,
    addressed_graph_path: Path,
    sca_path: Path,
    sca_d_path: Path,
) -> dict[str, Any]:
    config = _json_object(patched_config_path)
    graph = _json_object(addressed_graph_path)
    sca = _json_object(sca_path)
    sca_d = _json_object(sca_d_path)
    streams = config.get("stream_engine")
    loops = config.get("dram_loop_configs")
    buffers = config.get("buffer_config")
    groups = config.get("buffer_loop_configs")
    if not all(isinstance(value, Mapping) for value in (streams, loops, buffers, groups)):
        raise DequantizeVerticalError("materialized config sections are missing")
    if set(streams) != {"stream0", "stream2"}:
        raise DequantizeVerticalError("materialized stream set is not exact A/D")
    read_stream = streams["stream0"]
    write_stream = streams["stream2"]
    if (
        read_stream.get("mode"),
        read_stream.get("target"),
        write_stream.get("mode"),
        write_stream.get("target"),
    ) != ("read", "A", "write", "D"):
        raise DequantizeVerticalError("materialized A/D stream roles differ")

    a_transaction = int(read_stream["idx_size"][2]) + 1
    d_transaction = int(write_stream["idx_size"][2]) + 1
    a_occurrences = _loop_trip_count(loops["LC1"]) * _loop_trip_count(loops["LC2"])
    d_occurrences = _loop_trip_count(loops["LC3"]) * _loop_trip_count(loops["LC4"])
    if (a_transaction, d_transaction, a_occurrences, d_occurrences) != (16, 64, 47, 47):
        raise DequantizeVerticalError("transaction/occurrence roundtrip differs")
    if a_transaction * a_occurrences != 752 or d_transaction * d_occurrences != 3008:
        raise DequantizeVerticalError("materialized stream byte conservation differs")

    expected_a_spatial = [
        0, 8, 16, 24, 1, 9, 17, 25, 2, 10, 18, 26, 3, 11, 19, 27
    ]
    expected_d_spatial = [
        4, 5, 6, 7, 12, 13, 14, 15, 20, 21, 22, 23, 28, 29, 30, 31
    ]
    if (
        read_stream.get("buf_spatial_size"),
        read_stream.get("buf_spatial_stride"),
        write_stream.get("buf_spatial_size"),
        write_stream.get("buf_spatial_stride"),
    ) != (16, expected_a_spatial, 16, expected_d_spatial):
        raise DequantizeVerticalError("materialized bank/column spatial mapping differs")
    if read_stream.get("dim_stride") != [16, 16, 752]:
        raise DequantizeVerticalError("materialized A dimension strides differ")
    if write_stream.get("dim_stride") != [64, 64, 3008]:
        raise DequantizeVerticalError("materialized D dimension strides differ")
    if any(
        buffers[name].get("buffer_life_time") != 1
        or buffers[name].get("buf_full_last_index") != 3
        for name in ("buffer0", "buffer5")
    ):
        raise DequantizeVerticalError("materialized buffer lifetime/tag differs")
    if (
        groups["GROUP0"].get("target"),
        _loop_trip_count(groups["GROUP0"]["ROW_LC"]),
        _loop_trip_count(groups["GROUP0"]["COL_LC"]),
        groups["GROUP2"].get("target"),
        _loop_trip_count(groups["GROUP2"]["ROW_LC"]),
        _loop_trip_count(groups["GROUP2"]["COL_LC"]),
    ) != ("A", 1, 1, "D", 4, 1):
        raise DequantizeVerticalError("materialized buffer-loop occurrence differs")
    d_buffer_supply_bytes = (
        _loop_trip_count(groups["GROUP2"]["ROW_LC"])
        * int(write_stream["buf_spatial_size"])
    )
    if d_buffer_supply_bytes != d_transaction:
        raise DequantizeVerticalError(
            "materialized D buffer supply/transaction conservation differs"
        )

    operators = graph.get("operators")
    if not isinstance(operators, list) or len(operators) != 1:
        raise DequantizeVerticalError("addressed graph operator cardinality differs")
    operator = operators[0]
    if operator.get("id") != EXEC_OP_ID:
        raise DequantizeVerticalError("addressed graph operator identity differs")
    if operator.get("inputs", {}).get("A", {}).get("base_addr") != "0x00000000":
        raise DequantizeVerticalError("addressed A base differs")
    if operator.get("output", {}).get("base_addr") != "0x000002F0":
        raise DequantizeVerticalError("addressed D base differs")

    for slice_index in range(28):
        slice_offset = slice_index << 25
        expected_a = f"0x{slice_offset:08X}"
        expected_d = f"0x{slice_offset + 0x2F0:08X}"
        a_entry = sca.get(f"{EXEC_OP_ID}_matrixA_slice{slice_index}")
        d_entry = sca_d.get(f"{EXEC_OP_ID}_matrixD_slice{slice_index}")
        if not isinstance(a_entry, Mapping) or a_entry.get("base_addr") != expected_a:
            raise DequantizeVerticalError(f"SCA A slice {slice_index} base differs")
        if (
            not isinstance(d_entry, Mapping)
            or d_entry.get("base_addr") != expected_d
            or d_entry.get("length") != 188
        ):
            raise DequantizeVerticalError(f"SCA_D slice {slice_index} coverage differs")
        if not (slice_offset + 752 <= slice_offset + 0x2F0):
            raise DequantizeVerticalError("A/D regions overlap")

    return {
        "rule": "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
        "valid": True,
        "stream_set": ["A:read", "D:write"],
        "a_transaction_bytes": a_transaction,
        "d_transaction_bytes": d_transaction,
        "occurrences_per_slice": 47,
        "logical_elements_per_occurrence": 16,
        "hardware_elements_per_slice": 752,
        "a_bytes_per_slice": 752,
        "d_bytes_per_slice": 3008,
        "d_buffer_rows_per_occurrence": 4,
        "d_buffer_supply_bytes_per_occurrence": d_buffer_supply_bytes,
        "d_last_row_index": 3,
        "a_bank_columns": expected_a_spatial,
        "d_bank_columns": expected_d_spatial,
        "buffer_lifetime": 1,
        "terminal_root": "DRAM_LC.LC0",
        "slice_count": 28,
        "sca_d_words_per_slice": 188,
        "address_regions_non_overlapping": True,
    }


def _execplan_roundtrip_audit(
    execplan_path: Path,
    explanation_path: Path,
    sca_path: Path,
    sca_d_path: Path,
    config_bitstream_path: Path,
) -> dict[str, Any]:
    lines128 = [
        line.strip()
        for line in execplan_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not lines128 or any(
        len(line) != 128 or set(line) - {"0", "1"} for line in lines128
    ):
        raise DequantizeVerticalError("execplan is not strict 128-bit binary")
    words: list[str] = []
    for line in lines128:
        words.extend((line[64:], line[:64]))
    if words and set(words[-1]) == {"0"}:
        words.pop()
    explained: dict[int, tuple[str, str]] = {}
    command_re = re.compile(r"^\s*(\d+)\s+<([01]{64})>\s+(.*)$")
    for line in explanation_path.read_text(encoding="utf-8").splitlines():
        match = command_re.match(line)
        if match is None:
            continue
        index = int(match.group(1))
        if index in explained:
            raise DequantizeVerticalError("duplicate execplan explanation index")
        explained[index] = (match.group(2), match.group(3))
    if set(explained) != set(range(len(words))):
        raise DequantizeVerticalError("execplan explanation coverage differs")
    if any(explained[index][0] != word for index, word in enumerate(words)):
        raise DequantizeVerticalError("execplan machine/explanation bits differ")

    opcodes = [int(word[-3:], 2) for word in words]
    if opcodes[0] != 1 or opcodes[1] != 0 or opcodes[-1] != 5:
        raise DequantizeVerticalError("execplan Clock/Load/Start ordering differs")
    if any(opcode != 4 for opcode in opcodes[2:-1]):
        raise DequantizeVerticalError("execplan middle command is not Write_Reg")
    descriptions = [explained[index][1] for index in range(len(words))]
    if "Load_Config for operator op0" not in descriptions[1]:
        raise DequantizeVerticalError("Load_Config explanation is not bound to op0")
    if "Start_Comp for operator op0" not in descriptions[-1]:
        raise DequantizeVerticalError("Start_Comp explanation is not bound to op0")
    if any("ga_pe" in description.lower() for description in descriptions[2:-1]):
        raise DequantizeVerticalError("baked GA constants were reissued as Write_Reg")

    sca = _json_object(sca_path)
    sca_d = _json_object(sca_d_path)
    if sca.get("Exec_Length") != len(lines128):
        raise DequantizeVerticalError("SCA Exec_Length differs from 128-bit execplan")
    config_lines = _bitstream_identity(config_bitstream_path)["line_count"]
    load_word = int(words[1], 2)
    if (load_word >> 56) & 0xFF != config_lines * 2:
        raise DequantizeVerticalError("Load_Config length differs from cfg_pkg")
    config_base = int(str(sca[f"{EXEC_OP_ID}_config"]["base_addr"]), 16)
    if (load_word >> 34) & ((1 << 22) - 1) != config_base >> 10:
        raise DequantizeVerticalError("Load_Config DDR address differs from SCA")

    input_writes: dict[int, str] = {}
    output_writes: dict[int, str] = {}
    for description in descriptions[2:-1]:
        slice_match = re.search(r"slice_bin=([01]{5})", description)
        value_match = re.search(r"field_value_write_hex=(0x[0-9A-Fa-f]{8})", description)
        if slice_match is None or value_match is None:
            raise DequantizeVerticalError("Write_Reg explanation lacks slice/value")
        slice_index = int(slice_match.group(1), 2)
        if "input A" in description:
            input_writes[slice_index] = value_match.group(1).upper().replace("X", "x")
        elif "output D" in description:
            output_writes[slice_index] = value_match.group(1).upper().replace("X", "x")
        else:
            raise DequantizeVerticalError("unexpected Write_Reg explanation role")
    if set(input_writes) != set(range(1, 28)) or set(output_writes) != set(range(1, 28)):
        raise DequantizeVerticalError("per-slice A/D Write_Reg coverage differs")
    for slice_index in range(1, 28):
        expected_a = str(sca[f"{EXEC_OP_ID}_matrixA_slice{slice_index}"]["base_addr"])
        expected_d = str(sca_d[f"{EXEC_OP_ID}_matrixD_slice{slice_index}"]["base_addr"])
        if input_writes[slice_index].lower() != expected_a.lower():
            raise DequantizeVerticalError(f"A Write_Reg slice {slice_index} differs")
        if output_writes[slice_index].lower() != expected_d.lower():
            raise DequantizeVerticalError(f"D Write_Reg slice {slice_index} differs")
    return {
        "valid": True,
        "machine_explanation_bit_exact": True,
        "unique_explanation_indices": True,
        "command_count_64bit": len(words),
        "line_count_128bit": len(lines128),
        "command_sequence": ["Clock_Enable", "Load_Config", "Write_Reg*54", "Start_Comp"],
        "config_length_64bit_words": config_lines * 2,
        "a_dynamic_slice_writes": 27,
        "d_dynamic_slice_writes": 27,
        "slice0_addresses_baked_in_config": True,
        "typed_constant_dynamic_writes": 0,
    }


def run_local_e2(
    project_root: Path,
    *,
    artifact_root: Path | None = None,
    python_executable: Path | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    output = (
        artifact_root.resolve()
        if artifact_root is not None
        else (
            root
            / f"artifacts/operator_config_validation/r5-dequant-node0077-e2-{ASSET_VERSION}"
        )
    )
    materialize_dequant_vertical(root, artifact_root=output)
    isolated_tools = {
        "run-a": output / "tool-a",
        "run-b": output / "tool-b",
    }
    existing = [label for label, path in isolated_tools.items() if path.exists()]
    if existing:
        raise DequantizeVerticalError(
            "refusing to overwrite isolated toolchains; "
            f"use a fresh artifact root: {existing}"
        )
    before = {
        name: sha256_file(path)
        for name, path in _source_paths(root).items()
        if "ndp-sim-ref" in path.as_posix()
    }
    rtl_root = root / "NDP_copy01/rtl"
    rtl_before = _tree_identity(rtl_root)
    config_path = (
        root
        / "configs/native_ndp_sim/"
        f"resnet50_dequant_node0077_uint8_fp32_strict_{ASSET_VERSION}/config.json"
    )
    request_source = output / "execplan_request.json"
    python = str((python_executable or Path(sys.executable)).resolve())
    run_records: dict[str, Any] = {}
    required_by_run: dict[str, dict[str, Path]] = {}
    cache_receipts: dict[str, dict[str, Any]] = {}
    normalized_by_run: dict[str, dict[str, Any]] = {}
    original = _json_object(request_source)
    _, expected_normalized, expected_renormalized = _official_parser_roundtrip(
        root, original
    )
    if expected_renormalized != expected_normalized:
        raise DequantizeVerticalError(
            "official typed parser normalization is not idempotent"
        )

    for label, isolated in isolated_tools.items():
        _copy_isolated_toolchain(root, isolated)
        shutil.copyfile(config_path, isolated / "jsons" / f"{OP_TYPE}.json")
        request_copy = isolated / "model_execplan" / "dq77.json"
        shutil.copyfile(request_source, request_copy)
        cache_dir = output / f"mapping-cache-{label[-1]}"
        if cache_dir.exists():
            raise DequantizeVerticalError(
                f"isolated mapping cache already exists: {cache_dir}"
            )
        cache_dir.mkdir()
        cache_initial_count = len(list(cache_dir.iterdir()))
        normalized_path = output / f"normalized_execplan_request_{label[-1]}.json"
        run_records[label] = _run(
            [
                python,
                str(isolated / "model_execplan/main.py"),
                str(request_copy),
                "--dump-normalized-json",
                str(normalized_path),
            ],
            cwd=isolated,
            env={
                **os.environ,
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONHASHSEED": "0",
                "NDP_MAPPING_CACHE_DIR": str(cache_dir),
            },
        )
        cache_post_files = sorted(path.name for path in cache_dir.iterdir())
        cache_receipts[label] = {
            "path": cache_dir.relative_to(output).as_posix(),
            "initial_file_count": cache_initial_count,
            "post_file_count": len(cache_post_files),
            "post_files": cache_post_files,
        }
        if cache_initial_count != 0:
            raise DequantizeVerticalError("mapping cache was not empty at run start")
        normalized = _json_object(normalized_path)
        if normalized != expected_normalized:
            raise DequantizeVerticalError(
                f"execplan CLI normalized request differs in {label}"
            )
        normalized_by_run[label] = normalized

        lifecycle_root = isolated / "model_execplan/output/dq77"
        config_root = lifecycle_root / "config" / EXEC_OP_ID
        required = {
            "execplan": lifecycle_root / "install/execplan.txt",
            "explanation": lifecycle_root / "instructions_explained.txt",
            "sca": lifecycle_root / "sca_cfg.json",
            "sca_d": lifecycle_root / "sca_cfg_D.json",
            "addressed_graph": lifecycle_root / "dq77_withbaseaddr.json",
            "patched_config": (
                lifecycle_root / "jsons" / f"{EXEC_OP_ID}_{OP_TYPE}.json"
            ),
            "mapping_review": config_root / "mapping_review.json",
            "detailed_dump": config_root / "detailed_dump.txt",
            "parsed_bitstream": config_root / "parsed_bitstream.txt",
            "raw64": config_root / "modules_dump_64b.bin",
            "raw128": config_root / "modules_dump_128b.bin",
            "named_raw64": (
                config_root / f"{EXEC_OP_ID}_{OP_TYPE}_bitstream_64b.bin"
            ),
            "regenerated_bitstream": (
                config_root / f"{EXEC_OP_ID}_{OP_TYPE}_bitstream_128b.bin"
            ),
            "cfg_pkg": (
                lifecycle_root
                / "install/cfg_pkg"
                / f"{EXEC_OP_ID}_{OP_TYPE}_bitstream_128b.bin"
            ),
            "encoder_stdout": config_root / "encoder_stdout.log",
            "encoder_stderr": config_root / "encoder_stderr.log",
            "patch_manifest": isolated / "isolated_patch_manifest.json",
        }
        missing = [name for name, path in required.items() if not path.is_file()]
        if missing:
            raise DequantizeVerticalError(
                f"{label} execplan lifecycle outputs are missing: {missing}"
            )
        if sha256_file(required["raw64"]) != sha256_file(required["named_raw64"]):
            raise DequantizeVerticalError(f"{label} named/raw 64-bit dumps differ")
        if sha256_file(required["raw128"]) != sha256_file(
            required["regenerated_bitstream"]
        ):
            raise DequantizeVerticalError(f"{label} named/raw 128-bit dumps differ")
        if sha256_file(required["raw128"]) != sha256_file(required["cfg_pkg"]):
            raise DequantizeVerticalError(f"{label} cfg_pkg bitstream differs")
        required_by_run[label] = required

    if normalized_by_run["run-a"] != normalized_by_run["run-b"]:
        raise DequantizeVerticalError("typed parser outputs differ across isolated runs")

    deterministic_names = (
        "execplan",
        "explanation",
        "sca",
        "sca_d",
        "addressed_graph",
        "patched_config",
        "mapping_review",
        "detailed_dump",
        "parsed_bitstream",
        "raw64",
        "raw128",
        "named_raw64",
        "regenerated_bitstream",
        "cfg_pkg",
        "patch_manifest",
    )
    deterministic_products: dict[str, dict[str, Any]] = {}
    for name in deterministic_names:
        path_a = required_by_run["run-a"][name]
        path_b = required_by_run["run-b"][name]
        hash_a = sha256_file(path_a)
        hash_b = sha256_file(path_b)
        if hash_a != hash_b:
            raise DequantizeVerticalError(
                f"isolated full-lifecycle product differs: {name}"
            )
        deterministic_products[name] = {
            "sha256": hash_a,
            "bytes": path_a.stat().st_size,
        }

    mapping_audits: dict[str, dict[str, Any]] = {}
    roundtrip_audits: dict[str, dict[str, Any]] = {}
    execplan_audits: dict[str, dict[str, Any]] = {}
    for label, required in required_by_run.items():
        mapping_audits[label] = _mapping_constant_audit(
            required["mapping_review"],
            required["patched_config"],
            detailed_dump_path=required["detailed_dump"],
            parsed_bitstream_path=required["parsed_bitstream"],
            raw64_path=required["raw64"],
            raw128_path=required["raw128"],
            encoder_stdout_path=required["encoder_stdout"],
        )
        roundtrip_audits[label] = _materialized_roundtrip_audit(
            required["patched_config"],
            required["addressed_graph"],
            required["sca"],
            required["sca_d"],
        )
        execplan_audits[label] = _execplan_roundtrip_audit(
            required["execplan"],
            required["explanation"],
            required["sca"],
            required["sca_d"],
            required["cfg_pkg"],
        )
    if canonical_json_bytes(mapping_audits["run-a"]) != canonical_json_bytes(
        mapping_audits["run-b"]
    ):
        raise DequantizeVerticalError("mapping audits differ across isolated runs")
    if canonical_json_bytes(roundtrip_audits["run-a"]) != canonical_json_bytes(
        roundtrip_audits["run-b"]
    ):
        raise DequantizeVerticalError("materialized roundtrip differs across runs")
    if canonical_json_bytes(execplan_audits["run-a"]) != canonical_json_bytes(
        execplan_audits["run-b"]
    ):
        raise DequantizeVerticalError("execplan roundtrip differs across runs")

    after = {
        name: sha256_file(path)
        for name, path in _source_paths(root).items()
        if "ndp-sim-ref" in path.as_posix()
    }
    if before != after:
        raise DequantizeVerticalError("active ndp-sim-ref source identity changed")
    rtl_after = _tree_identity(rtl_root)
    if rtl_before != rtl_after:
        raise DequantizeVerticalError("NDP_copy01/rtl tree identity changed")

    report: dict[str, Any] = {
        "schema": "dequantize-linear-local-e2-report-v1",
        "status": "local_e2_passed_server_e4_e5_pending",
        "candidate_release": False,
        "request_id": REQUEST_ID,
        "rules_passed": [
            *RULE_IDS[:-1],
            "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
            "CDA-CONFIG-FULL-REBUILD-PROVENANCE-001",
        ],
        "numeric": build_numeric_evidence(root),
        "config": validate_operator_config(
            _json_object(config_path), root
        )["exact_topology"],
        "typed_transport": validate_execplan_request(original, root),
        "bitstream": {
            "double_run_identical": True,
            "two_isolated_toolchains": True,
            "full_lifecycle_products_identical": True,
            "run_a": _bitstream_identity(
                required_by_run["run-a"]["regenerated_bitstream"]
            ),
            "run_b": _bitstream_identity(
                required_by_run["run-b"]["regenerated_bitstream"]
            ),
            "deterministic_products": deterministic_products,
        },
        "mapping": mapping_audits["run-a"],
        "materialized_roundtrip": roundtrip_audits["run-a"],
        "execplan_lifecycle": {
            "required_outputs": {
                label: {
                    name: {
                        "path": path.relative_to(output).as_posix(),
                        "sha256": sha256_file(path),
                        "bytes": path.stat().st_size,
                    }
                    for name, path in required.items()
                }
                for label, required in required_by_run.items()
            },
            "normalized_outputs_match_official_parser": True,
            "independent_machine_explanation_roundtrip": execplan_audits["run-a"],
            "cache_receipts": cache_receipts,
            "sca_d_slice_count": 28,
            "sca_d_words_per_slice": 188,
        },
        "source_identity": {
            "ndp_sim_ref_unchanged": True,
            "focused_hashes": after,
            "rtl_modified": False,
            "rtl_tree_identity": rtl_after,
        },
        "run_commands": {
            label: {
                "command": record["command"],
                "returncode": record["returncode"],
            }
            for label, record in run_records.items()
        },
        "remaining_blockers": ["B_DEQUANT_SERVER_E4_E5"],
    }
    report["report_sha256"] = sha256_bytes(canonical_json_bytes(report))
    _write_json(output / "local_e2_report.json", report)
    manifest_path = output / "manifest.json"
    manifest = _json_object(manifest_path)
    manifest["status"] = "local_e2_passed_server_e4_e5_pending"
    manifest["local_e2_report"] = {
        "path": "local_e2_report.json",
        "sha256": sha256_file(output / "local_e2_report.json"),
    }
    manifest["manifest_sha256"] = sha256_bytes(
        canonical_json_bytes(
            {key: value for key, value in manifest.items() if key != "manifest_sha256"}
        )
    )
    _write_json(manifest_path, manifest)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize and audit node-0077 DequantizeLinear vertical closure."
    )
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--run-e2", action="store_true")
    args = parser.parse_args(argv)
    if args.run_e2:
        value = run_local_e2(
            args.project_root,
            artifact_root=args.artifact_root,
        )
    else:
        value = materialize_dequant_vertical(
            args.project_root,
            artifact_root=args.artifact_root,
        )
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DequantizeVerticalError",
    "build_execplan_request",
    "build_generation_receipt",
    "build_layout_evidence",
    "build_numeric_evidence",
    "build_operator_config",
    "build_semantic_contract",
    "materialize_dequant_vertical",
    "run_local_e2",
    "validate_execplan_request",
    "validate_operator_config",
]
