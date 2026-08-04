"""Local vertical closure for node-0001 INT32->UINT8 requantization.

This module only creates local E2 evidence.  It never edits an active
``ndp-sim`` checkout, never writes below an ``rtl/`` directory, and never
creates a server package.
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
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .dequantize_linear_vertical import (
    _detailed_gape_blocks,
    _parsed_bitstream_sections,
    _verify_raw_bitstream_mirror,
)
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_validator import OperatorConfigValidator
from .w5_conv_preflight import _initializer_values


SCHEMA = "resnet50-node0001-requant-two-stage-local-e2-v1"
REQUEST_ID = "r5:hwop-0001-01"
NODE_ID = "node-0001"
HW_OP_ID = "hwop-0001-01"
SPATIAL = 112 * 112
LANES = 8
SHARD_COUNT = 8
OCCURRENCE_COUNT = 24
STAGE_COUNT = 48
ROUND_MAGIC = np.float32(12_582_912.0)
ROUND_MAGIC_BITS = 0x4B400000
MAPPING_SEED = 42
PYTHON_HASH_SEED = 0
ARTIFACT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-node0001-two-stage-e2-v1"
)
CONFIG_REL = Path("configs/native_ndp_sim/node0001_requant_two_stage_v1")
CONTRACT_REL = Path(
    "contracts/operator_config/requant_node0001_two_stage_contract_v1.json"
)
TASK_RECORD_REL = Path(
    ".agents/task_records/20260725_requant_node0001_two_stage_local_e2.md"
)
TYPED_REL = Path("contracts/typed_config_parameter_contract.json")
LOWERING_REL = Path("contracts/resnet50_r5_lowering_bundle.json")
MODEL_REL = Path("artifacts/reference_model/resnet50-v1-12-int8.onnx")
INPUT_REL = Path(
    "artifacts/w3/subop_batch16/tensors/"
    "tensor-internal-node-0001-accumulate.npy"
)
OUTPUT_REL = Path(
    "artifacts/w3/golden_batch16/tensors/tensor-f6c1a8fb6fd529e8.npy"
)
QUANT_TEMPLATE_REL = Path(
    "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json"
)
SILU_TEMPLATE_REL = Path("ndp-sim/jsons/prefill_silu_fp16MN_fp32MN.json")
RULE_REL = Path(".agents/rules/RequantizeUint8算子配置规则.md")

EXPECTED_SHA256 = {
    ".agents/rules/生成前必读索引.md": (
        "539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7"
    ),
    ".agents/rules/算子配置规则.md": (
        "f7e3f80e7fb4edd2b42d7ff41a70bba55abfde6797013648dfedccdc6385e023"
    ),
    ".agents/rules/NDP硬件字段语义.md": (
        "a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59"
    ),
    RULE_REL.as_posix(): (
        "44e8ee38d1361f15d78bf5d7918fa10e4648370153178ad10d044fd5c9d26265"
    ),
    QUANT_TEMPLATE_REL.as_posix(): (
        "db638f0640e74217e80e61350a2fe400f7b495e2201f17c39915328cdd455ba2"
    ),
    SILU_TEMPLATE_REL.as_posix(): (
        "08101bdc82d615741d6262db57098b3ba3acd04cc427c1d0c1297cc68da5cdbd"
    ),
}

RULE_IDS = (
    "CDA-REQUANT-QPARAM-001",
    "CDA-REQUANT-INT32-GUARD-001",
    "CDA-REQUANT-SFU-LUT-001",
    "CDA-REQUANT-TWO-STAGE-001",
    "CDA-REQUANT-ROUND-MAGIC-001",
    "CDA-REQUANT-LAYOUT-HWC8-001",
    "CDA-REQUANT-MATERIALIZED-ROUNDTRIP-001",
    "CDA-REQUANT-E4-E5-001",
)
GA_MAC_KEYS = ("PE00", "PE02", "PE10", "PE12", "PE20", "PE22", "PE30", "PE32")
GA_SUB_KEYS = ("PE01", "PE03", "PE11", "PE13", "PE21", "PE23", "PE31", "PE33")
GA_SFU_KEYS = GA_SUB_KEYS
WAVE_SAMPLES = (
    (0, 3, 6, 8, 10, 12, 14),
    (1, 4, 7, 9, 11, 13, 15),
    (2, 5),
)
HIGH_RING_OWNERS = (
    (0, 2, 3, 1),
    (4, 6, 7, 5),
    (8, 10, 11, 9),
    (12, 14, 15, 13),
    (16, 18, 19, 17),
    (20, 22, 23, 21),
    (24, 26, 27, 25),
)
VISUALIZATION_EXCLUSIONS = {
    f"config/{op}/placement.png"
    for wave in range(3)
    for shard in range(8)
    for op in (
        f"op_w{wave}_s{shard:02d}_guard",
        f"op_w{wave}_s{shard:02d}_round",
    )
}


class RequantizeUint8VerticalError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RequantizeUint8VerticalError(
            f"cannot parse JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise RequantizeUint8VerticalError(f"JSON root is not an object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _file_binding(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _tree_identity(path: Path) -> dict[str, Any]:
    files = [
        _file_binding(path, item)
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    ]
    return {
        "file_count": len(files),
        "tree_sha256": sha256_bytes(canonical_json_bytes(files)),
    }


def _typed_stage(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    typed = _load(root / TYPED_REL)
    matches = [
        item
        for item in typed.get("hw_ops", [])
        if isinstance(item, dict) and item.get("hw_op_id") == HW_OP_ID
    ]
    if len(matches) != 1:
        raise RequantizeUint8VerticalError(f"typed stage is not unique: {HW_OP_ID}")
    stage = matches[0]
    if (
        stage.get("node_id") != NODE_ID
        or stage.get("hw_op_type") != "RequantizeUint8"
        or stage.get("stage") != "requantize"
        or stage.get("predecessor_hw_op_ids") != ["hwop-0001-00"]
    ):
        raise RequantizeUint8VerticalError("node-0001 typed identity drifted")
    return typed, stage


def _lowering_request(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    bundle = _load(root / LOWERING_REL)
    matches = [
        item
        for item in bundle.get("requests", [])
        if isinstance(item, dict) and item.get("request_id") == REQUEST_ID
    ]
    if len(matches) != 1:
        raise RequantizeUint8VerticalError(
            f"lowering request is not unique: {REQUEST_ID}"
        )
    return bundle, matches[0]


def _parameter(stage: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    matches = [
        item
        for item in stage.get("parameters", [])
        if isinstance(item, Mapping) and item.get("name") == name
    ]
    if len(matches) != 1:
        raise RequantizeUint8VerticalError(f"typed parameter is not unique: {name}")
    return matches[0]


def requant_parameters(root: Path) -> tuple[np.ndarray, int, dict[str, Any]]:
    _, stage = _typed_stage(root)
    initializers = _initializer_values(root / MODEL_REL)
    x_scale = np.asarray(initializers["data_scale"], dtype=np.float32).reshape(-1)
    w_scale = np.asarray(
        initializers["ConvBnFusion_W_resnetv17_conv0_weight_scale"],
        dtype=np.float32,
    ).reshape(-1)
    y_scale = np.asarray(
        initializers["resnetv17_relu0_fwd_scale"], dtype=np.float32
    ).reshape(-1)
    y_zero_point = np.asarray(
        initializers["resnetv17_relu0_fwd_zero_point"]
    ).reshape(-1)
    if (
        x_scale.shape != (1,)
        or w_scale.shape != (64,)
        or y_scale.shape != (1,)
        or y_zero_point.shape != (1,)
    ):
        raise RequantizeUint8VerticalError("node-0001 qparam shapes drifted")
    multiplier = np.asarray(
        np.float32(x_scale[0]) * w_scale / np.float32(y_scale[0]),
        dtype=np.float32,
    )
    zero_point = int(y_zero_point[0])
    expected_sha = _parameter(stage, "requant_multiplier")["value"]["value_sha256"]
    multiplier_sha = hashlib.sha256(
        np.ascontiguousarray(multiplier).tobytes()
    ).hexdigest()
    if (
        zero_point != 0
        or not np.isfinite(multiplier).all()
        or not np.all(multiplier > 0)
        or multiplier_sha != expected_sha
    ):
        raise RequantizeUint8VerticalError(
            "CDA-REQUANT-QPARAM-001 precondition failed"
        )
    return multiplier, zero_point, {
        "x_scale_bits": f"0x{x_scale.view(np.uint32)[0]:08x}",
        "y_scale_bits": f"0x{y_scale.view(np.uint32)[0]:08x}",
        "y_zero_point": zero_point,
        "multiplier_sha256": multiplier_sha,
        "multiplier_minimum": float(multiplier.min()),
        "multiplier_maximum": float(multiplier.max()),
        "all_multiplier_finite_positive": True,
    }


def build_generation_receipt(root: Path) -> dict[str, Any]:
    sources = {
        "agent_policy": Path(".agents/agent.md"),
        "generation_read_index": Path(".agents/rules/生成前必读索引.md"),
        "operator_rules": Path(".agents/rules/算子配置规则.md"),
        "hardware_field_semantics": Path(".agents/rules/NDP硬件字段语义.md"),
        "requant_rules": RULE_REL,
        "lowering_bundle": LOWERING_REL,
        "typed_contract": TYPED_REL,
        "quant_template": QUANT_TEMPLATE_REL,
        "sfu_normal_output_template": SILU_TEMPLATE_REL,
        "operator_base_info": Path(
            "ndp-sim/model_execplan/config/operator_base_info.json"
        ),
        "template_manager": Path(
            "ndp-sim/model_execplan/src/execution_plan_generator/template_manager.py"
        ),
        "control_registers": Path(
            "ndp-sim/model_execplan/src/execution_plan_generator/control_registers.py"
        ),
        "pipeline": Path(
            "ndp-sim/model_execplan/src/execution_plan_generator/pipeline.py"
        ),
        "instruction_generator": Path(
            "ndp-sim/model_execplan/src/execution_plan_generator/"
            "instruction_generator.py"
        ),
        "output_writer": Path(
            "ndp-sim/model_execplan/src/execution_plan_generator/output_writer.py"
        ),
        "bitstream_ga_encoder": Path("ndp-sim/bitstream/config/general.py"),
        "input_npy": INPUT_REL,
        "output_npy": OUTPUT_REL,
    }
    missing = [name for name, relative in sources.items() if not (root / relative).is_file()]
    if missing:
        raise RequantizeUint8VerticalError(
            f"generation receipt inputs are missing: {missing}"
        )
    for relative, expected in EXPECTED_SHA256.items():
        observed = sha256_file(root / relative)
        if observed != expected:
            raise RequantizeUint8VerticalError(
                f"generation source identity drifted: {relative}: {observed}"
            )
    bundle, request = _lowering_request(root)
    _, stage = _typed_stage(root)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    receipt: dict[str, Any] = {
        "schema": "requantize-uint8-generation-read-receipt-v1",
        "status": "generation_gate_satisfied_before_json_materialization",
        "request_id": REQUEST_ID,
        "request_sha256": request["request_sha256"],
        "request_set_sha256": bundle["request_set_sha256"],
        "typed_stage_sha256": sha256_bytes(canonical_json_bytes(stage)),
        "rule_ids": list(RULE_IDS),
        "read_receipt": [
            {
                **_file_binding(root, root / relative),
                "role": name,
                "read_at": now,
            }
            for name, relative in sources.items()
        ],
        "generation_boundary": {
            "candidate_release": False,
            "formal_target_instance_allowed": False,
            "server_package": False,
            "rtl_modification_allowed": False,
        },
    }
    receipt["receipt_sha256"] = sha256_bytes(canonical_json_bytes(receipt))
    return receipt


def build_guard_sfu_words() -> list[int]:
    words = [0] * 65
    words.extend([0] * 66)
    slopes = [0] * 66
    slopes[65] = 0x3F800000
    words.extend(slopes)
    words.extend([0, 0, 0])
    if len(words) != 200:
        raise AssertionError("guard SFU payload must contain 200 words")
    return words


def guard_sfu_text() -> str:
    words = build_guard_sfu_words()
    lines = [
        "".join(f"{word:032b}" for word in words[index : index + 4])
        for index in range(0, len(words), 4)
    ]
    if len(lines) != 50 or any(len(line) != 128 for line in lines):
        raise AssertionError("guard SFU payload must be 50x128 bits")
    return "\n".join(lines) + "\n"


def validate_guard_sfu_payload(text: str) -> dict[str, Any]:
    lines = [line for line in text.splitlines() if line]
    if len(lines) != 50 or any(re.fullmatch(r"[01]{128}", line) is None for line in lines):
        raise RequantizeUint8VerticalError("RequantGuard payload is not 50x128")
    words = [
        int(line[offset : offset + 32], 2)
        for line in lines
        for offset in range(0, 128, 32)
    ]
    if words != build_guard_sfu_words():
        raise RequantizeUint8VerticalError("RequantGuard word ordering differs")
    return {
        "line_count_128b": 50,
        "word_count_32b": 200,
        "meaningful_word_count_32b": 197,
        "padding_word_count_32b": 3,
        "execplan_length_64b": 100,
        "breakpoint_words": 65,
        "intercept_words": 66,
        "slope_words": 66,
        "slope65_bits": "0x3f800000",
        "payload_sha256": hashlib.sha256(text.encode("ascii")).hexdigest(),
    }


def _mask(slice_ids: list[int]) -> str:
    bits = ["0"] * 28
    for slice_id in slice_ids:
        bits[27 - slice_id] = "1"
    return "0b" + "".join(bits)


def wave_active_slices(wave_index: int, shard_index: int) -> list[int]:
    owner_step = shard_index // 2
    return [
        HIGH_RING_OWNERS[group_id][owner_step]
        for group_id in range(len(WAVE_SAMPLES[wave_index]))
    ]


def guard_type() -> str:
    return "resnet50_requant_guard_node0001"


def round_type(shard_index: int) -> str:
    return f"resnet50_requant_round_node0001_s{shard_index:02d}"


def guard_op_id(wave_index: int, shard_index: int) -> str:
    return f"op_w{wave_index}_s{shard_index:02d}_guard"


def round_op_id(wave_index: int, shard_index: int) -> str:
    return f"op_w{wave_index}_s{shard_index:02d}_round"


def _assert_strict_config(config: Mapping[str, Any], source: str) -> None:
    report = OperatorConfigValidator().validate(config, source=source)
    if not report.valid:
        raise RequantizeUint8VerticalError(
            f"strict operator config validation failed: {report.to_dict()['first_error']}"
        )


def build_guard_config(root: Path) -> dict[str, Any]:
    quant = _load(root / QUANT_TEMPLATE_REL)
    silu = _load(root / SILU_TEMPLATE_REL)
    config = deepcopy(quant)
    config["dram_loop_configs"]["LC0"]["end"] = 1
    config["dram_loop_configs"]["LC1"]["end"] = SPATIAL
    config["dram_loop_configs"]["LC2"] = deepcopy(
        silu["dram_loop_configs"]["LC2"]
    )
    config["dram_loop_configs"]["LC2"]["end"] = SPATIAL
    config["stream_engine"]["stream0"]["dim_stride"] = [
        32,
        SPATIAL * 32,
        None,
    ]
    config["stream_engine"]["stream2"] = deepcopy(
        silu["stream_engine"]["stream2"]
    )
    config["stream_engine"]["stream2"]["dim_stride"] = [
        32,
        SPATIAL * 32,
        None,
    ]
    config["buffer_loop_configs"] = {
        "GROUP0": deepcopy(quant["buffer_loop_configs"]["GROUP0"]),
        "GROUP1": deepcopy(silu["buffer_loop_configs"]["GROUP1"]),
    }
    config["general_array"] = deepcopy(silu["general_array"])
    inport0 = config["general_array"]["inport"]["inport0"]
    inport0["fp16tofp32"] = "false"
    inport0["bf16tofp32"] = "false"
    inport0["int32tofp32"] = "true"
    inport0["uint8tofp32"] = "false"
    inport0["uint8toint32"] = "false"
    _assert_strict_config(config, "node0001-requant-guard")
    return config


def build_round_config(root: Path, multiplier: np.ndarray, shard_index: int) -> dict[str, Any]:
    config = deepcopy(_load(root / QUANT_TEMPLATE_REL))
    config["dram_loop_configs"]["LC0"]["end"] = 1
    config["dram_loop_configs"]["LC1"]["end"] = SPATIAL
    config["dram_loop_configs"]["LC2"]["end"] = SPATIAL // 4
    config["stream_engine"]["stream0"]["dim_stride"] = [
        32,
        SPATIAL * 32,
        None,
    ]
    config["stream_engine"]["stream2"]["dim_stride"] = [
        32,
        (SPATIAL // 4) * 32,
        None,
    ]
    inport0 = config["general_array"]["inport"]["inport0"]
    for key in (
        "fp16tofp32",
        "bf16tofp32",
        "int32tofp32",
        "uint8tofp32",
        "uint8toint32",
    ):
        inport0[key] = "false"
    start = shard_index * LANES
    for lane, (mac_key, sub_key) in enumerate(
        zip(GA_MAC_KEYS, GA_SUB_KEYS, strict=True)
    ):
        config["general_array"]["PE_array"][mac_key]["inport1"][
            "constant"
        ] = float(multiplier[start + lane])
        config["general_array"]["PE_array"][mac_key]["inport2"][
            "constant"
        ] = float(ROUND_MAGIC)
        config["general_array"]["PE_array"][sub_key]["inport1"][
            "constant"
        ] = ROUND_MAGIC_BITS
    _assert_strict_config(config, f"node0001-requant-round-shard{shard_index:02d}")
    return config


def build_static_configs(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    multiplier, _, qparams = requant_parameters(root)
    configs: dict[str, dict[str, Any]] = {guard_type(): build_guard_config(root)}
    for shard in range(SHARD_COUNT):
        configs[round_type(shard)] = build_round_config(root, multiplier, shard)
    manifest: dict[str, Any] = {
        "schema": "node0001-requant-two-stage-static-config-set-v1",
        "request_id": REQUEST_ID,
        "qparams": qparams,
        "guard_sfu": validate_guard_sfu_payload(guard_sfu_text()),
        "operator_types": {},
        "candidate_release": False,
        "formal_target_config": False,
    }
    for op_type, config in sorted(configs.items()):
        manifest["operator_types"][op_type] = {
            "role": "guard" if op_type == guard_type() else "round_saturate",
            "canonical_json_sha256": sha256_bytes(canonical_json_bytes(config)),
        }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    return configs, manifest


def build_graph() -> dict[str, Any]:
    operators: list[dict[str, Any]] = []
    for wave in range(3):
        for shard in range(SHARD_COUNT):
            slices = wave_active_slices(wave, shard)
            mask = _mask(slices)
            guard_id = guard_op_id(wave, shard)
            round_id = round_op_id(wave, shard)
            tensor_a = f"node0001.w{wave}.s{shard:02d}.A_int32"
            tensor_mid = f"node0001.w{wave}.s{shard:02d}.D_guard_fp32"
            tensor_d = f"node0001.w{wave}.s{shard:02d}.D_uint8"
            operators.append(
                {
                    "id": guard_id,
                    "type": guard_type(),
                    "instance_id": f"{REQUEST_ID}:w{wave}:s{shard:02d}:guard",
                    "stage": "guard",
                    "used_slices": mask,
                    "attributes": {
                        "wave_index": wave,
                        "shard_index": shard,
                        "sample_ids": list(WAVE_SAMPLES[wave]),
                        "channels": list(range(shard * 8, shard * 8 + 8)),
                        "candidate_release": False,
                    },
                    "inputs": {
                        "A": {
                            "shape": [1, SPATIAL, LANES],
                            "dtype": "int32",
                            "tensor_id": tensor_a,
                            "source": {"type": "external"},
                        }
                    },
                    "output": {
                        "shape": [1, SPATIAL, LANES],
                        "dtype": "fp32",
                        "tensor_id": tensor_mid,
                    },
                }
            )
            operators.append(
                {
                    "id": round_id,
                    "type": round_type(shard),
                    "instance_id": f"{REQUEST_ID}:w{wave}:s{shard:02d}:round",
                    "stage": "round_saturate",
                    "used_slices": mask,
                    "attributes": {
                        "wave_index": wave,
                        "shard_index": shard,
                        "sample_ids": list(WAVE_SAMPLES[wave]),
                        "channels": list(range(shard * 8, shard * 8 + 8)),
                        "candidate_release": False,
                    },
                    "inputs": {
                        "A": {
                            "shape": [1, SPATIAL, LANES],
                            "dtype": "fp32",
                            "tensor_id": tensor_mid,
                            "source": {
                                "type": "operator",
                                "operator_id": guard_id,
                            },
                        }
                    },
                    "output": {
                        "shape": [1, SPATIAL, LANES],
                        "dtype": "uint8",
                        "tensor_id": tensor_d,
                    },
                }
            )
    return {
        "schema_version": "0.1",
        "plan_id": "node0001-requant-two-stage-local-e2-v1",
        "used_slices": _mask(list(range(28))),
        "params": {
            "request_id": REQUEST_ID,
            "occurrence_count": OCCURRENCE_COUNT,
            "stage_count": STAGE_COUNT,
            "candidate_release": False,
        },
        "operators": operators,
    }


def build_numeric_evidence(root: Path) -> dict[str, Any]:
    multiplier, zero_point, qparams = requant_parameters(root)
    accumulator = np.load(root / INPUT_REL, allow_pickle=False)
    golden = np.load(root / OUTPUT_REL, allow_pickle=False)
    if (
        accumulator.shape != (16, 64, 112, 112)
        or accumulator.dtype != np.dtype("int32")
        or golden.shape != accumulator.shape
        or golden.dtype != np.dtype("uint8")
    ):
        raise RequantizeUint8VerticalError("W3 node-0001 tensor ABI drifted")
    converted = accumulator.astype(np.float32)
    guard = np.maximum(converted, np.float32(0.0))
    expected_guard = np.maximum(accumulator, 0).astype(np.float32)
    guard_mismatch = int(
        np.count_nonzero(guard.view(np.uint32) != expected_guard.view(np.uint32))
    )
    scaled = np.multiply(
        guard, multiplier.reshape(1, 64, 1, 1), dtype=np.float32
    )
    rounded = (
        np.add(scaled, np.float32(ROUND_MAGIC + zero_point), dtype=np.float32)
        .view(np.int32)
        .astype(np.int64)
        - np.int64(ROUND_MAGIC_BITS)
    )
    replay = np.clip(rounded, 0, 255).astype(np.uint8)
    final_mismatch = int(np.count_nonzero(replay != golden))
    if guard_mismatch or final_mismatch:
        raise RequantizeUint8VerticalError(
            f"full W3 replay differs: guard={guard_mismatch}, final={final_mismatch}"
        )
    nonnegative = accumulator >= 0
    positive_conversion_mismatch = int(
        np.count_nonzero(
            converted[nonnegative].view(np.uint32)
            != accumulator[nonnegative].astype(np.float32).view(np.uint32)
        )
    )
    return {
        "rule_ids": [
            "CDA-REQUANT-QPARAM-001",
            "CDA-REQUANT-INT32-GUARD-001",
            "CDA-REQUANT-ROUND-MAGIC-001",
        ],
        "qparams": qparams,
        "element_count": int(accumulator.size),
        "negative_element_count": int(np.count_nonzero(accumulator < 0)),
        "minus_one_element_count": int(np.count_nonzero(accumulator == -1)),
        "zero_element_count": int(np.count_nonzero(accumulator == 0)),
        "positive_conversion_mismatch_count": positive_conversion_mismatch,
        "guard_bitwise_mismatch_count": guard_mismatch,
        "final_uint8_mismatch_count": final_mismatch,
        "guard_sha256": hashlib.sha256(
            np.ascontiguousarray(guard).tobytes()
        ).hexdigest(),
        "replay_sha256": hashlib.sha256(
            np.ascontiguousarray(replay).tobytes()
        ).hexdigest(),
        "golden_sha256": hashlib.sha256(
            np.ascontiguousarray(golden).tobytes()
        ).hexdigest(),
        "negative_converter_argument": (
            "RTL preserves the sign bit; all negative converted values route "
            "to SFU coefficient address 0, whose slope/intercept are both zero"
        ),
        "full_w3_bit_exact": True,
    }


def _copy_tree_without_runtime_state(source: Path, target: Path) -> None:
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "*.pyo", "mapping_cache", "output"
        ),
    )


def _patch_isolated_consumers(
    tool_root: Path,
    configs: Mapping[str, Mapping[str, Any]],
    sfu_text: str,
) -> dict[str, Any]:
    json_root = tool_root / "jsons"
    json_root.mkdir(parents=True, exist_ok=True)
    for op_type, config in sorted(configs.items()):
        _write_json(json_root / f"{op_type}.json", config)
    sfu_path = (
        tool_root / "model_execplan/config/SFU_Coeff/RequantGuard.txt"
    )
    sfu_path.write_text(sfu_text, encoding="ascii", newline="\n")

    base_info_path = (
        tool_root / "model_execplan/config/operator_base_info.json"
    )
    base_info = _load(base_info_path)
    table = base_info.get("operators")
    if not isinstance(table, dict):
        raise RequantizeUint8VerticalError("operator_base_info table is malformed")
    table[guard_type()] = {
        "initial_size": {
            "A": [1, SPATIAL, LANES],
            "D": [1, SPATIAL, LANES],
        },
        "config_sfu": "RequantGuard",
    }
    for shard in range(SHARD_COUNT):
        table[round_type(shard)] = {
            "initial_size": {
                "A": [1, SPATIAL, LANES],
                "D": [1, SPATIAL, LANES],
            },
            "config_sfu": None,
        }
    _write_json(base_info_path, base_info)

    template_path = (
        tool_root
        / "model_execplan/src/execution_plan_generator/template_manager.py"
    )
    template_text = template_path.read_text(encoding="utf-8")
    alias_anchor = '            "relu": "ReLU",\n'
    if template_text.count(alias_anchor) != 1:
        raise RequantizeUint8VerticalError("template-manager alias anchor drifted")
    template_path.write_text(
        template_text.replace(
            alias_anchor,
            alias_anchor + '            "requantguard": "RequantGuard",\n',
        ),
        encoding="utf-8",
        newline="\n",
    )

    control_path = (
        tool_root
        / "model_execplan/src/execution_plan_generator/control_registers.py"
    )
    control_text = control_path.read_text(encoding="utf-8")
    dictionary_anchor = "OP_CONTROL_REGISTER_FN = {\n"
    if control_text.count(dictionary_anchor) != 1:
        raise RequantizeUint8VerticalError("control-register map anchor drifted")
    handler_text = f'''
def _compute_resnet50_requant_guard_node0001_control_register_updates(
    operator: OperatorSpec,
    template: OperatorTemplate,
) -> dict[str, int]:
    d_m = operator.output.shape[1]
    return {{
        "iga_lc0.dram_loop_configs.end": 1,
        "iga_lc1.dram_loop_configs.end": d_m,
        "iga_lc2.dram_loop_configs.end": d_m,
        "rd_stream0.stream_engine.stream.dim_stride": pack_dim_stride(
            port0=0, port1=d_m * 32, port2=32
        ),
        "wr_stream.stream_engine.stream.dim_stride": pack_dim_stride(
            port0=0, port1=d_m * 32, port2=32
        ),
    }}


def _compute_resnet50_requant_round_node0001_control_register_updates(
    operator: OperatorSpec,
    template: OperatorTemplate,
) -> dict[str, int]:
    d_m = operator.output.shape[1]
    return {{
        "iga_lc0.dram_loop_configs.end": 1,
        "iga_lc1.dram_loop_configs.end": d_m,
        "iga_lc2.dram_loop_configs.end": d_m // 4,
        "rd_stream0.stream_engine.stream.dim_stride": pack_dim_stride(
            port0=0, port1=d_m * 32, port2=32
        ),
        "wr_stream.stream_engine.stream.dim_stride": pack_dim_stride(
            port0=0, port1=(d_m // 4) * 32, port2=32
        ),
    }}


'''
    map_entries = (
        f'    "{guard_type()}": '
        "_compute_resnet50_requant_guard_node0001_control_register_updates,\n"
        + "".join(
            f'    "{round_type(shard)}": '
            "_compute_resnet50_requant_round_node0001_control_register_updates,\n"
            for shard in range(SHARD_COUNT)
        )
    )
    control_path.write_text(
        control_text.replace(
            dictionary_anchor,
            handler_text + dictionary_anchor + map_entries,
        ),
        encoding="utf-8",
        newline="\n",
    )
    address_path = (
        tool_root
        / "model_execplan/src/execution_plan_generator/address_planner.py"
    )
    address_text = address_path.read_text(encoding="utf-8")
    plan_anchor = (
        "    def plan(\n"
        "        self,\n"
        "        execution_input: ExecutionPlanInput,\n"
        "        config_lengths_by_op: dict[str, int] | None = None,\n"
        "        sfu_config_lengths_by_op: dict[str, int] | None = None,\n"
        "        sfu_types_by_op: dict[str, str] | None = None,\n"
        "    ) -> AddressPlan:\n"
        "        interleave = self._resolve_plan_interleave(execution_input)\n"
    )
    plan_replacement = (
        "    def plan(\n"
        "        self,\n"
        "        execution_input: ExecutionPlanInput,\n"
        "        config_lengths_by_op: dict[str, int] | None = None,\n"
        "        sfu_config_lengths_by_op: dict[str, int] | None = None,\n"
        "        sfu_types_by_op: dict[str, str] | None = None,\n"
        "    ) -> AddressPlan:\n"
        "        if execution_input.operators and all(\n"
        "            op.op_type.startswith(\"resnet50_requant_\")\n"
        "            and \"node0001\" in op.op_type\n"
        "            for op in execution_input.operators\n"
        "        ):\n"
        "            return self._plan_node0001_requant_lifetime(\n"
        "                execution_input,\n"
        "                config_lengths_by_op=config_lengths_by_op,\n"
        "                sfu_config_lengths_by_op=sfu_config_lengths_by_op,\n"
        "                sfu_types_by_op=sfu_types_by_op,\n"
        "            )\n"
        "        interleave = self._resolve_plan_interleave(execution_input)\n"
    )
    helper_anchor = (
        "    # ------------------------------------------------------------------\n"
        "    # Interleave helpers\n"
        "    # ------------------------------------------------------------------\n"
    )
    helper_text = f'''    def _plan_node0001_requant_lifetime(
        self,
        execution_input: ExecutionPlanInput,
        config_lengths_by_op: dict[str, int] | None,
        sfu_config_lengths_by_op: dict[str, int] | None,
        sfu_types_by_op: dict[str, str] | None = None,
    ) -> AddressPlan:
        """Exact W4 HWC8 allocation for the local node-0001 E2 graph.

        Every physical slice owns at most six (three waves x two local
        channel shards) external A and final D occurrences.  The guarded
        FP32 intermediate is reused only after a same-mask completion fence.
        """
        assignments: dict[str, AddressAssignment] = {{}}
        io_map: dict[str, str] = {{}}
        output_tensor_by_op: dict[str, str] = {{}}

        def assignment(
            tensor_name: str,
            dtype: str,
            shape: tuple[int, int, int],
            enabled: list[int],
            bank: int,
            row: int,
        ) -> AddressAssignment:
            size_bytes = self._tensor_size_bytes(
                tensor_name=tensor_name,
                tensor_dtype=dtype,
                shape=shape,
            )
            local = self._pack_address(
                slave=0, bank=bank, row=row, col=0, subword=0
            )
            return AddressAssignment(
                tensor_name=tensor_name,
                base_address=local,
                per_slice_addresses={{
                    slice_id: self._pack_address(
                        slave=slice_id,
                        bank=bank,
                        row=row,
                        col=0,
                        subword=0,
                    )
                    for slice_id in enabled
                }},
                size_bytes=size_bytes,
                shape=shape,
            )

        for op in execution_input.operators:
            parts = op.op_id.split("_")
            wave = int(parts[1][1:])
            shard = int(parts[2][1:])
            local_slot = wave * 2 + (shard % 2)
            enabled = op.enabled_slice_ids()
            if not enabled:
                raise AddressPlanningError(
                    f"node0001 occurrence has no enabled slice: {{op.op_id}}"
                )
            input_a = op.inputs["A"]
            input_key = self._io_key(op.op_id, "input", "A")
            if op.op_id.endswith("_guard"):
                input_name = f"{{op.op_id}}.input.A"
                input_assignment = assignment(
                    input_name,
                    input_a.dtype,
                    input_a.shape,
                    enabled,
                    bank=0,
                    row=local_slot * 392,
                )
                assignments[input_name] = input_assignment
                io_map[input_key] = input_name
                output_bank = 1
                output_row = 0
            else:
                source_op_id = input_a.source.operator_id
                if source_op_id not in output_tensor_by_op:
                    raise AddressPlanningError(
                        f"node0001 round source is unplanned: {{source_op_id}}"
                    )
                io_map[input_key] = output_tensor_by_op[source_op_id]
                output_bank = 2
                output_row = local_slot * 98
            output_name = f"{{op.op_id}}.output.D"
            output_assignment = assignment(
                output_name,
                op.output.dtype,
                op.output.shape,
                enabled,
                bank=output_bank,
                row=output_row,
            )
            assignments[output_name] = output_assignment
            output_tensor_by_op[op.op_id] = output_name
            io_map[self._io_key(op.op_id, "output", "D")] = output_name

        config_lengths_by_op = config_lengths_by_op or {{}}
        sfu_config_lengths_by_op = sfu_config_lengths_by_op or {{}}
        sfu_types_by_op = sfu_types_by_op or {{}}
        config_bases: dict[str, int] = {{}}
        config_lengths: dict[str, int] = {{}}
        sfu_bases: dict[str, int] = {{}}
        sfu_lengths: dict[str, int] = {{}}
        config_row = 0
        for op in execution_input.operators:
            length = int(config_lengths_by_op.get(op.op_id, 0) or 0)
            config_lengths[op.op_id] = length
            if length:
                config_bases[op.op_id] = self._pack_address(
                    slave=0, bank=3, row=config_row, col=0, subword=0
                )
                config_row += ceil(length * 8 / self.ROW_BYTES)
        shared_sfu: dict[str, int] = {{}}
        for op in execution_input.operators:
            length = int(sfu_config_lengths_by_op.get(op.op_id, 0) or 0)
            sfu_lengths[op.op_id] = length
            if not length:
                continue
            sfu_type = sfu_types_by_op.get(op.op_id, "")
            if sfu_type in shared_sfu:
                sfu_bases[op.op_id] = shared_sfu[sfu_type]
                continue
            base = self._pack_address(
                slave=0, bank=3, row=config_row, col=0, subword=0
            )
            sfu_bases[op.op_id] = base
            if sfu_type:
                shared_sfu[sfu_type] = base
            config_row += ceil(length * 8 / self.ROW_BYTES)
        if config_row > 6144:
            raise AddressPlanningError(
                f"node0001 config region exceeds 6144 rows: {{config_row}}"
            )
        return AddressPlan(
            assignments=assignments,
            operator_io_to_tensor=io_map,
            operator_config_base_addresses=config_bases,
            operator_config_lengths=config_lengths,
            operator_sfu_config_base_addresses=sfu_bases,
            operator_sfu_config_lengths=sfu_lengths,
        )

'''
    if (
        address_text.count(plan_anchor) != 1
        or address_text.count(helper_anchor) != 1
    ):
        raise RequantizeUint8VerticalError("address-planner patch anchor drifted")
    address_text = address_text.replace(plan_anchor, plan_replacement)
    address_text = address_text.replace(
        helper_anchor, helper_text + helper_anchor
    )
    address_path.write_text(
        address_text.replace("    MAX_ROWS = 8192\n", "    MAX_ROWS = 6144\n"),
        encoding="utf-8",
        newline="\n",
    )
    return {
        "active_checkout_modified": False,
        "isolated_adapter_scope": [
            "nine hash-bound operator-type registrations",
            "two exact shape/address control handlers",
            "one exact RequantGuard SFU type registration",
            "one exact W4 per-slice lifetime allocator with 6144-row gate",
        ],
        "files": {
            base_info_path.relative_to(tool_root).as_posix(): sha256_file(
                base_info_path
            ),
            template_path.relative_to(tool_root).as_posix(): sha256_file(
                template_path
            ),
            control_path.relative_to(tool_root).as_posix(): sha256_file(
                control_path
            ),
            address_path.relative_to(tool_root).as_posix(): sha256_file(
                address_path
            ),
            sfu_path.relative_to(tool_root).as_posix(): sha256_file(sfu_path),
        },
    }


def _build_tool_copy(
    root: Path,
    run_dir: Path,
    configs: Mapping[str, Mapping[str, Any]],
    sfu_text: str,
) -> tuple[Path, dict[str, Any]]:
    tool_root = run_dir / "tool"
    tool_root.mkdir(parents=True)
    _copy_tree_without_runtime_state(
        root / "ndp-sim/bitstream", tool_root / "bitstream"
    )
    _copy_tree_without_runtime_state(
        root / "ndp-sim/model_execplan/src",
        tool_root / "model_execplan/src",
    )
    _copy_tree_without_runtime_state(
        root / "ndp-sim/model_execplan/config",
        tool_root / "model_execplan/config",
    )
    shutil.copy2(
        root / "ndp-sim/model_execplan/main.py",
        tool_root / "model_execplan/main.py",
    )
    adapter = _patch_isolated_consumers(tool_root, configs, sfu_text)
    cache = tool_root / "bitstream/config/mapping_cache"
    initial_cache = (
        [path for path in cache.iterdir() if path.is_file()]
        if cache.is_dir()
        else []
    )
    if initial_cache:
        raise RequantizeUint8VerticalError("isolated mapping cache is not empty")
    source_files = [
        _file_binding(tool_root, path)
        for path in sorted(item for item in tool_root.rglob("*") if item.is_file())
    ]
    manifest: dict[str, Any] = {
        "schema": "node0001-requant-isolated-tool-copy-v1",
        "source_checkout": "ndp-sim",
        "active_checkout_modified": False,
        "initial_mapping_cache_file_count": 0,
        "isolated_adapters": adapter,
        "files": source_files,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    _write_json(run_dir / "tool_source_manifest.json", manifest)
    return tool_root, manifest


def _execplan_words(path: Path) -> list[int]:
    lines = [
        line.strip()
        for line in path.read_text(encoding="ascii").splitlines()
        if line.strip()
    ]
    if any(len(line) != 128 or set(line) - {"0", "1"} for line in lines):
        raise RequantizeUint8VerticalError("execplan is not strict 128-bit text")
    words: list[int] = []
    for line in lines:
        words.extend((int(line[64:], 2), int(line[:64], 2)))
    if words and words[-1] == 0:
        words.pop()
    return words


def _execplan_explanations(path: Path, count: int) -> list[str]:
    pattern = re.compile(r"^\s*(\d+)\s+<([01]{64})>(?:\s{4}(.*))?$")
    records: dict[int, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(raw)
        if match is not None:
            records[int(match.group(1))] = match.group(3) or ""
    if set(records) != set(range(count)):
        raise RequantizeUint8VerticalError("execplan explanation coverage differs")
    return [records[index] for index in range(count)]


def _barrierize(
    tool_root: Path, graph_path: Path, output_dir: Path
) -> dict[str, Any]:
    execplan_path = output_dir / "install/execplan.txt"
    explanation_path = output_dir / "instructions_explained.txt"
    commands = _execplan_words(execplan_path)
    explanations = _execplan_explanations(explanation_path, len(commands))
    source_root = tool_root / "model_execplan/src"
    prefix = "execution_plan_generator"
    prior_path = list(sys.path)
    prior_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == prefix or name.startswith(f"{prefix}.")
    }
    for name in prior_modules:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(source_root))
    try:
        from execution_plan_generator.json_loader import (  # type: ignore
            load_execution_plan_json,
        )
        from execution_plan_generator.models import ExecutionPlanArtifact  # type: ignore
        from execution_plan_generator.output_writer import (  # type: ignore
            write_instruction_outputs,
        )
        execution_input = load_execution_plan_json(graph_path)
        ordinary = ExecutionPlanArtifact(
            commands=commands,
            command_explanations=explanations,
            metadata={"profile": "ordinary_native_before_local_barriers"},
        )
        sfu_indices = [
            index
            for index, explanation in enumerate(
                ordinary.command_explanations
            )
            if "Load_Config SFU" in str(explanation)
        ]
        if len(sfu_indices) != OCCURRENCE_COUNT:
            raise RequantizeUint8VerticalError(
                "native guard SFU load multiplicity differs before folding: "
                f"{len(sfu_indices)}"
            )
        slice_mask_field = ((1 << 28) - 1) << 3
        fixed_sfu_words = {
            int(ordinary.commands[index]) & ~slice_mask_field
            for index in sfu_indices
        }
        if len(fixed_sfu_words) != 1:
            raise RequantizeUint8VerticalError(
                "guard SFU load length/address/config bit differs across occurrences"
            )
        first_sfu = sfu_indices[0]
        folded_commands: list[int] = []
        folded_explanations: list[str] = []
        sfu_index_set = set(sfu_indices)
        for index, (command, explanation) in enumerate(
            zip(
                ordinary.commands,
                ordinary.command_explanations,
                strict=True,
            )
        ):
            if index not in sfu_index_set:
                folded_commands.append(int(command))
                folded_explanations.append(str(explanation))
                continue
            if index == first_sfu:
                folded_commands.append(
                    next(iter(fixed_sfu_words))
                    | (((1 << 28) - 1) << 3)
                )
                folded_explanations.append(
                    "Load_Config SFU shared RequantGuard once before the first "
                    "Start_Comp: config_sfu_bin=1, "
                    f"slice_mask_bin={((1 << 28) - 1):028b}"
                )
        ordinary = ExecutionPlanArtifact(
            commands=folded_commands,
            command_explanations=folded_explanations,
            metadata={
                **ordinary.metadata,
                "native_sfu_load_count": str(len(sfu_indices)),
                "folded_sfu_load_count": "1",
            },
        )
        barrier_commands: list[int] = []
        barrier_explanations: list[str] = []
        stage_index = 0
        for command, explanation in zip(
            ordinary.commands,
            ordinary.command_explanations,
            strict=True,
        ):
            command_value = int(command)
            if (command_value & 0x7) == 0b110:
                raise RequantizeUint8VerticalError(
                    "ordinary native execplan already contains a completion barrier"
                )
            barrier_commands.append(command_value)
            barrier_explanations.append(str(explanation))
            if (command_value & 0x7) != 0b101:
                continue
            if stage_index >= len(execution_input.operators):
                raise RequantizeUint8VerticalError(
                    "native execplan has more Start_Comp commands than stages"
                )
            operator = execution_input.operators[stage_index]
            expected_mask = int(operator.used_slices)
            observed_mask = (command_value >> 3) & ((1 << 28) - 1)
            if command_value >> 31 or observed_mask != expected_mask:
                raise RequantizeUint8VerticalError(
                    f"Start_Comp mask differs at stage {stage_index}"
                )
            barrier_commands.append((expected_mask << 3) | 0b110)
            barrier_explanations.append(
                "Server completion barrier after operator "
                f"{operator.op_id}: wait for "
                f"slice_mask_bin={expected_mask:028b} before dispatching "
                "the next command"
            )
            stage_index += 1
        if stage_index != len(execution_input.operators):
            raise RequantizeUint8VerticalError(
                "native execplan has fewer Start_Comp commands than stages"
            )
        barrierized = ExecutionPlanArtifact(
            commands=barrier_commands,
            command_explanations=barrier_explanations,
            metadata={
                **ordinary.metadata,
                "barrier_count": str(stage_index),
                "completion_profile": "same_mask_after_each_start_comp_v1",
            },
        )
        write_instruction_outputs(barrierized, output_dir)
    finally:
        for name in list(sys.modules):
            if name == prefix or name.startswith(f"{prefix}."):
                sys.modules.pop(name, None)
        sys.modules.update(prior_modules)
        sys.path[:] = prior_path
    sca_path = output_dir / "sca_cfg.json"
    sca = _load(sca_path)
    words = _execplan_words(execplan_path)
    sca["Exec_Length"] = (len(words) + 1) // 2
    sca["Repeat_Num"] = STAGE_COUNT
    _write_json(sca_path, sca)
    opcodes = [word & 0x7 for word in words]
    if (
        opcodes.count(0b101) != STAGE_COUNT
        or opcodes.count(0b110) != STAGE_COUNT
        or opcodes[-1] != 0b110
    ):
        raise RequantizeUint8VerticalError(
            "48-stage completion barrier insertion differs"
        )
    return {
        "ordinary_command_count": len(commands),
        "barrierized_command_count": len(words),
        "start_comp_count": opcodes.count(0b101),
        "barrier_count": opcodes.count(0b110),
        "repeat_num": STAGE_COUNT,
        "final_opcode": "0b110",
    }


def _remove_consumer_sca_preloads(output_dir: Path) -> dict[str, Any]:
    sca_path = output_dir / "sca_cfg.json"
    sca = _load(sca_path)
    keys = sorted(
        key
        for key in sca
        if re.fullmatch(r"op_w[0-2]_s\d{2}_round_matrixA_slice\d+", key)
    )
    expected = sum(len(WAVE_SAMPLES[wave]) for wave in range(3)) * SHARD_COUNT
    if len(keys) != expected:
        raise RequantizeUint8VerticalError(
            f"native consumer-backed SCA key count differs: {len(keys)} != {expected}"
        )
    removed_bindings = {
        key: deepcopy(sca[key]) for key in keys
    }
    for key in keys:
        del sca[key]
    _write_json(sca_path, sca)
    return {
        "native_consumer_backed_key_count": len(keys),
        "runtime_consumer_preload_key_count": 0,
        "removed_key_set_sha256": sha256_bytes(canonical_json_bytes(keys)),
        "removed_binding_set_sha256": sha256_bytes(
            canonical_json_bytes(removed_bindings)
        ),
        "reason": (
            "round A is producer-backed guard D at the same per-slice address; "
            "preloading it would overwrite the hardware-produced intermediate"
        ),
    }


def _run_native_once(
    root: Path,
    run_dir: Path,
    graph: Mapping[str, Any],
    configs: Mapping[str, Mapping[str, Any]],
    sfu_text: str,
    python: Path,
) -> dict[str, Any]:
    run_dir.mkdir(parents=True)
    tool_root, source_manifest = _build_tool_copy(
        root, run_dir, configs, sfu_text
    )
    input_dir = tool_root / "input"
    input_dir.mkdir()
    graph_path = input_dir / "node0001_requant_two_stage.json"
    _write_json(graph_path, graph)
    seed_hook = run_dir / "seed_hook"
    seed_hook.mkdir()
    (seed_hook / "sitecustomize.py").write_text(
        f"import random\nrandom.seed({MAPPING_SEED})\n",
        encoding="utf-8",
        newline="\n",
    )
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": str(PYTHON_HASH_SEED),
        "PYTHONPATH": os.pathsep.join(
            filter(None, (str(seed_hook.resolve()), os.environ.get("PYTHONPATH")))
        ),
    }
    process = subprocess.run(
        [
            str(python),
            str(tool_root / "model_execplan/main.py"),
            str(graph_path),
        ],
        cwd=tool_root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
        check=False,
    )
    stdout = run_dir / "native_stdout.log"
    stderr = run_dir / "native_stderr.log"
    stdout.write_text(process.stdout, encoding="utf-8", newline="\n")
    stderr.write_text(process.stderr, encoding="utf-8", newline="\n")
    if process.returncode != 0:
        raise RequantizeUint8VerticalError(
            f"native model_execplan failed: rc={process.returncode}; "
            f"see {stdout} and {stderr}"
        )
    if f"Parsed operators: {STAGE_COUNT}" not in process.stdout:
        raise RequantizeUint8VerticalError("native pipeline did not parse 48 stages")
    output_dir = (
        tool_root / "model_execplan/output/node0001_requant_two_stage"
    )
    if not output_dir.is_dir():
        raise RequantizeUint8VerticalError("native output root is missing")
    barrier = _barrierize(tool_root, graph_path, output_dir)
    barrier["consumer_sca_sanitization"] = _remove_consumer_sca_preloads(
        output_dir
    )
    required = [
        output_dir / "install/execplan.txt",
        output_dir / "instructions_explained.txt",
        output_dir / "sca_cfg.json",
        output_dir / "sca_cfg_D.json",
        output_dir / "node0001_requant_two_stage_withbaseaddr.json",
    ]
    for wave in range(3):
        for shard in range(SHARD_COUNT):
            for op_id, op_type in (
                (guard_op_id(wave, shard), guard_type()),
                (round_op_id(wave, shard), round_type(shard)),
            ):
                required.extend(
                    [
                        output_dir / f"jsons/{op_id}_{op_type}.json",
                        output_dir / f"config/{op_id}/mapping_review.json",
                        output_dir / f"config/{op_id}/parsed_bitstream.txt",
                        output_dir / f"config/{op_id}/detailed_dump.txt",
                        output_dir
                        / f"config/{op_id}/{op_id}_{op_type}_bitstream_64b.bin",
                        output_dir
                        / f"config/{op_id}/{op_id}_{op_type}_bitstream_128b.bin",
                    ]
                )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RequantizeUint8VerticalError(
            f"native output silently omitted files: {missing[:8]}"
        )
    return {
        "run_dir": run_dir,
        "tool_root": tool_root,
        "output_dir": output_dir,
        "returncode": process.returncode,
        "barrier": barrier,
        "source_manifest_sha256": source_manifest["manifest_sha256"],
        "stdout": stdout,
        "stderr": stderr,
    }


def _file_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def _compare_outputs(left: Path, right: Path) -> dict[str, Any]:
    files_left = _file_map(left)
    files_right = _file_map(right)
    if set(files_left) != set(files_right):
        raise RequantizeUint8VerticalError("isolated output file sets differ")
    deterministic_paths = sorted(set(files_left) - VISUALIZATION_EXCLUSIONS)
    mismatches = [
        path
        for path in deterministic_paths
        if files_left[path] != files_right[path]
    ]
    if mismatches:
        raise RequantizeUint8VerticalError(
            f"isolated output files differ: {mismatches[:8]}"
        )
    return {
        "file_set_identical": True,
        "deterministic_file_count": len(deterministic_paths),
        "deterministic_files_byte_identical": True,
        "excluded_visualization_files": sorted(VISUALIZATION_EXCLUSIONS),
        "files": {path: files_left[path] for path in deterministic_paths},
    }


def _parse_addr(value: object) -> int:
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        raise RequantizeUint8VerticalError(f"base address is malformed: {value!r}")
    return int(value.replace("_", ""), 0)


def _assert_stage_config(
    config: Mapping[str, Any],
    *,
    role: str,
    multiplier: np.ndarray,
    shard: int,
) -> dict[str, Any]:
    _assert_strict_config(config, f"materialized-{role}-shard{shard}")
    loops = config["dram_loop_configs"]
    expected_ends = (
        (1, SPATIAL, SPATIAL)
        if role == "guard"
        else (1, SPATIAL, SPATIAL // 4)
    )
    observed_ends = tuple(int(loops[f"LC{index}"]["end"]) for index in range(3))
    if observed_ends != expected_ends:
        raise RequantizeUint8VerticalError(
            f"{role} materialized loop ends differ: {observed_ends}"
        )
    stream0 = config["stream_engine"]["stream0"]
    stream2 = config["stream_engine"]["stream2"]
    if stream0["idx_size"][0] != 0 or stream0["idx_size"][1] != 31:
        raise RequantizeUint8VerticalError(f"{role} A transaction is not 32 bytes")
    ga = config["general_array"]
    if role == "guard":
        if (
            ga["inport"]["inport0"]["int32tofp32"] != "true"
            or ga["outport"]["int32touint8"] != "false"
            or sorted(ga["PE_array"]) != sorted(GA_SFU_KEYS)
            or any(
                pe["alu_opcode"] != "sfu_activation"
                or pe["transout_last_index"] is not None
                for pe in ga["PE_array"].values()
            )
            or stream2["idx_size"][0:2] != [0, 31]
            or config["buffer_loop_configs"]["GROUP1"]["COL_LC"][
                "end"
            ] != 32
        ):
            raise RequantizeUint8VerticalError("guard materialized topology differs")
        constants: dict[str, Any] = {}
    else:
        conversion_flags = (
            "fp16tofp32",
            "bf16tofp32",
            "int32tofp32",
            "uint8tofp32",
            "uint8toint32",
        )
        if (
            any(
                ga["inport"]["inport0"][name] != "false"
                for name in conversion_flags
            )
            or ga["outport"]["int32touint8"] != "true"
            or sorted(ga["PE_array"])
            != sorted((*GA_MAC_KEYS, *GA_SUB_KEYS))
            or any(
                pe["transout_last_index"] is not None
                for pe in ga["PE_array"].values()
            )
            or stream2["idx_size"][0:2] != [3, 7]
        ):
            raise RequantizeUint8VerticalError("round materialized topology differs")
        constants = {}
        start = shard * 8
        for lane, (mac_key, sub_key) in enumerate(
            zip(GA_MAC_KEYS, GA_SUB_KEYS, strict=True)
        ):
            observed_multiplier = np.float32(
                ga["PE_array"][mac_key]["inport1"]["constant"]
            )
            observed_magic = np.float32(
                ga["PE_array"][mac_key]["inport2"]["constant"]
            )
            observed_sub = int(
                ga["PE_array"][sub_key]["inport1"]["constant"]
            )
            if (
                observed_multiplier.view(np.uint32)
                != multiplier[start + lane].view(np.uint32)
                or observed_magic.view(np.uint32)
                != ROUND_MAGIC.view(np.uint32)
                or observed_sub != ROUND_MAGIC_BITS
            ):
                raise RequantizeUint8VerticalError(
                    f"round physical lane constant differs: shard={shard}, lane={lane}"
                )
            constants[mac_key] = {
                "multiplier_bits": f"0x{observed_multiplier.view(np.uint32):08x}",
                "magic_bits": f"0x{observed_magic.view(np.uint32):08x}",
                "sub_pe": sub_key,
                "subtract_bits": f"0x{observed_sub:08x}",
            }
    return {
        "role": role,
        "loop_ends": list(observed_ends),
        "read_transaction_bytes": 32,
        "write_transaction_bytes": 32,
        "read_buffer_columns": list(
            range(
                config["buffer_loop_configs"]["GROUP0"]["COL_LC"]["start"],
                config["buffer_loop_configs"]["GROUP0"]["COL_LC"]["end"],
                config["buffer_loop_configs"]["GROUP0"]["COL_LC"]["stride"],
            )
        ),
        "write_buffer_columns": list(
            range(
                next(
                    group["COL_LC"]["start"]
                    for group in config["buffer_loop_configs"].values()
                    if group["target"] == "D"
                ),
                next(
                    group["COL_LC"]["end"]
                    for group in config["buffer_loop_configs"].values()
                    if group["target"] == "D"
                ),
                next(
                    group["COL_LC"]["stride"]
                    for group in config["buffer_loop_configs"].values()
                    if group["target"] == "D"
                ),
            )
        ),
        "normal_outbuffer_only": True,
        "constants": constants,
    }


def _detailed_bitstream_audit(
    output_dir: Path,
    op_id: str,
    op_type: str,
    config: Mapping[str, Any],
    role: str,
) -> dict[str, Any]:
    config_dir = output_dir / f"config/{op_id}"
    detailed_path = config_dir / "detailed_dump.txt"
    parsed_path = config_dir / "parsed_bitstream.txt"
    raw64 = config_dir / f"{op_id}_{op_type}_bitstream_64b.bin"
    raw128 = config_dir / f"{op_id}_{op_type}_bitstream_128b.bin"
    detailed = detailed_path.read_text(encoding="utf-8")
    blocks = _detailed_gape_blocks(detailed_path)
    expected_keys = GA_SFU_KEYS if role == "guard" else (*GA_MAC_KEYS, *GA_SUB_KEYS)
    expected_opcodes = (
        {"11000"}
        if role == "guard"
        else {"01101", "00110"}
    )
    observed_opcodes = {block["fields"]["alu_opcode"] for block in blocks}
    if len(blocks) != len(expected_keys) or observed_opcodes != expected_opcodes:
        raise RequantizeUint8VerticalError(
            f"{op_id} detailed GA opcode/count differs: "
            f"{len(blocks)}, {observed_opcodes}"
        )
    inport_blocks = detailed.count("=== Dump: GAInportConfig ===")
    outport_blocks = detailed.count("=== Dump: GAOutportConfig ===")
    expected_inport_bit = "1" if role == "guard" else "0"
    expected_outport_bit = "0" if role == "guard" else "1"
    if (
        inport_blocks != 3
        or outport_blocks != 1
        or (
            f"int32tofp32                    | value="
            f"{'true' if role == 'guard' else 'false'}"
        )
        not in detailed
        or (
            f"int32touint8                   | value="
            f"{'false' if role == 'guard' else 'true'}"
        )
        not in detailed
        or f"encoded=['{expected_inport_bit}']" not in detailed
        or f"encoded=['{expected_outport_bit}']" not in detailed
    ):
        raise RequantizeUint8VerticalError(
            f"{op_id} detailed inport/outport conversion differs"
        )
    raw_mirror = _verify_raw_bitstream_mirror(
        config, parsed_path, raw64, raw128
    )
    return {
        "active_ga_pe_count": len(blocks),
        "physical_opcode_bits": sorted(observed_opcodes),
        "inport_config_block_count": inport_blocks,
        "outport_config_block_count": outport_blocks,
        "int32tofp32": role == "guard",
        "int32touint8": role == "round_saturate",
        "parsed_section_names": [
            name for name, _ in _parsed_bitstream_sections(parsed_path)
        ],
        "raw_bitstream_mirror": raw_mirror,
    }


def _sca_external_input_keys(sca: Mapping[str, Any]) -> list[str]:
    return sorted(
        key
        for key in sca
        if "_matrixA_" in key or "_matrixB_" in key or "_matrixC_" in key
    )


def audit_materialized(
    root: Path, output_dir: Path, sfu_payload_sha: str
) -> dict[str, Any]:
    multiplier, _, _ = requant_parameters(root)
    addressed = _load(
        output_dir / "node0001_requant_two_stage_withbaseaddr.json"
    )
    operators = addressed.get("operators")
    if not isinstance(operators, list) or len(operators) != STAGE_COUNT:
        raise RequantizeUint8VerticalError("addressed graph does not contain 48 stages")
    by_id = {
        item["id"]: item for item in operators if isinstance(item, dict)
    }
    records: list[dict[str, Any]] = []
    bitstream_representatives: dict[str, Any] = {}
    for wave in range(3):
        for shard in range(SHARD_COUNT):
            guard_id = guard_op_id(wave, shard)
            round_id = round_op_id(wave, shard)
            guard_op = by_id[guard_id]
            round_op = by_id[round_id]
            guard_addr = guard_op["output"]["base_addr"]
            round_addr = round_op["inputs"]["A"]["base_addr"]
            if (
                guard_addr != round_addr
                or round_op["inputs"]["A"]["source"]
                != {"type": "operator", "operator_id": guard_id}
                or guard_op["used_slices"] != round_op["used_slices"]
            ):
                raise RequantizeUint8VerticalError(
                    f"producer/consumer binding differs: wave={wave}, shard={shard}"
                )
            guard_path = (
                output_dir / f"jsons/{guard_id}_{guard_type()}.json"
            )
            round_path = (
                output_dir / f"jsons/{round_id}_{round_type(shard)}.json"
            )
            guard_config = _load(guard_path)
            round_config = _load(round_path)
            guard_audit = _assert_stage_config(
                guard_config,
                role="guard",
                multiplier=multiplier,
                shard=shard,
            )
            round_audit = _assert_stage_config(
                round_config,
                role="round_saturate",
                multiplier=multiplier,
                shard=shard,
            )
            if (
                _parse_addr(guard_config["stream_engine"]["stream2"]["base_addr"])
                != _parse_addr(round_config["stream_engine"]["stream0"]["base_addr"])
            ):
                raise RequantizeUint8VerticalError(
                    f"materialized stream D/A address differs: wave={wave}, shard={shard}"
                )
            bitstream_representatives[guard_id] = _detailed_bitstream_audit(
                output_dir,
                guard_id,
                guard_type(),
                guard_config,
                "guard",
            )
            bitstream_representatives[round_id] = _detailed_bitstream_audit(
                output_dir,
                round_id,
                round_type(shard),
                round_config,
                "round_saturate",
            )
            records.append(
                {
                    "wave_index": wave,
                    "shard_index": shard,
                    "used_slices": guard_op["used_slices"],
                    "sample_ids": list(WAVE_SAMPLES[wave]),
                    "channels": list(range(shard * 8, shard * 8 + 8)),
                    "producer_output_base_addr": guard_addr,
                    "consumer_input_base_addr": round_addr,
                    "same_slice_same_address": True,
                    "guard": guard_audit,
                    "round_saturate": round_audit,
                    "guard_json_sha256": sha256_file(guard_path),
                    "round_json_sha256": sha256_file(round_path),
                }
            )
    sca = _load(output_dir / "sca_cfg.json")
    external_keys = _sca_external_input_keys(sca)
    forbidden = [
        key for key in external_keys if "_round_matrixA_" in key
    ]
    if forbidden:
        raise RequantizeUint8VerticalError(
            f"consumer intermediate input appears in SCA preload: {forbidden[:4]}"
        )
    sfu_path = output_dir / "install/cfg_pkg/RequantGuard.txt"
    if not sfu_path.is_file() or sha256_file(sfu_path) != sfu_payload_sha:
        raise RequantizeUint8VerticalError("installed RequantGuard payload differs")
    explanation = (
        output_dir / "instructions_explained.txt"
    ).read_text(encoding="utf-8")
    sfu_load_count = explanation.count("Load_Config SFU")
    if sfu_load_count != 1:
        raise RequantizeUint8VerticalError(
            "shared RequantGuard must be loaded exactly once: "
            f"observed={sfu_load_count}"
        )
    return {
        "occurrence_count": len(records),
        "stage_count": STAGE_COUNT,
        "records": records,
        "bitstream_decoded_stage_count": len(bitstream_representatives),
        "bitstream_decoded_stages": bitstream_representatives,
        "all_materialized_json_strict_valid": True,
        "all_producer_consumer_addresses_identical": True,
        "consumer_intermediate_external_preload_count": 0,
        "external_sca_input_key_count": len(external_keys),
        "guard_sfu_shared_type_count": 1,
        "guard_sfu_load_count": sfu_load_count,
        "guard_sfu_payload_sha256": sfu_payload_sha,
    }


def materialize_static_assets(
    root: Path,
    configs: Mapping[str, Mapping[str, Any]],
    manifest: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> None:
    config_root = root / CONFIG_REL
    if config_root.exists():
        raise RequantizeUint8VerticalError(
            f"refusing to overwrite static config root: {config_root}"
        )
    config_root.mkdir(parents=True)
    for op_type, config in sorted(configs.items()):
        _write_json(config_root / f"{op_type}.json", config)
    (config_root / "RequantGuard.txt").write_text(
        guard_sfu_text(), encoding="ascii", newline="\n"
    )
    manifest_value = deepcopy(dict(manifest))
    manifest_value["generation_receipt_sha256"] = receipt["receipt_sha256"]
    manifest_value["files"] = {
        path.name: {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(item for item in config_root.iterdir() if item.is_file())
    }
    _write_json(config_root / "manifest.json", manifest_value)


def run_local_e2(
    project_root: Path,
    *,
    artifact_root: Path | None = None,
    python_executable: Path | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    artifact = (
        artifact_root.resolve()
        if artifact_root is not None
        else root / ARTIFACT_REL
    )
    if artifact.exists():
        raise RequantizeUint8VerticalError(
            f"refusing to overwrite local E2 artifact root: {artifact}"
        )
    if artifact_root is None and (root / CONFIG_REL).exists():
        raise RequantizeUint8VerticalError(
            f"refusing to overwrite static configs: {root / CONFIG_REL}"
        )
    python = (python_executable or Path(sys.executable)).resolve()
    receipt = build_generation_receipt(root)
    numeric = build_numeric_evidence(root)
    configs, static_manifest = build_static_configs(root)
    graph = build_graph()
    sfu_text = guard_sfu_text()
    sfu_evidence = validate_guard_sfu_payload(sfu_text)
    active_before = {
        "ndp_sim": _tree_identity(root / "ndp-sim"),
        "rtl": _tree_identity(root / "NDP_copy01/rtl"),
    }
    with tempfile.TemporaryDirectory(prefix="requant-node0001-e2-") as temporary:
        temp = Path(temporary)
        runs = {
            label: _run_native_once(
                root,
                temp / label,
                graph,
                configs,
                sfu_text,
                python,
            )
            for label in ("run-a", "run-b")
        }
        deterministic = _compare_outputs(
            runs["run-a"]["output_dir"], runs["run-b"]["output_dir"]
        )
        roundtrip_a = audit_materialized(
            root,
            runs["run-a"]["output_dir"],
            sfu_evidence["payload_sha256"],
        )
        roundtrip_b = audit_materialized(
            root,
            runs["run-b"]["output_dir"],
            sfu_evidence["payload_sha256"],
        )
        if canonical_json_bytes(roundtrip_a) != canonical_json_bytes(roundtrip_b):
            raise RequantizeUint8VerticalError(
                "two isolated materialized roundtrip audits differ"
            )
        active_after = {
            "ndp_sim": _tree_identity(root / "ndp-sim"),
            "rtl": _tree_identity(root / "NDP_copy01/rtl"),
        }
        if active_before != active_after:
            raise RequantizeUint8VerticalError(
                "active ndp-sim or RTL source identity changed"
            )
        work = temp / "artifact"
        work.mkdir()
        _write_json(work / "generation_receipt.json", receipt)
        _write_json(work / "typed_graph.json", graph)
        _write_json(work / "numeric_evidence.json", numeric)
        _write_json(work / "static_config_manifest.json", static_manifest)
        _write_json(work / "materialized_roundtrip.json", roundtrip_a)
        _write_json(work / "double_rebuild.json", deterministic)
        evidence = work / "native_evidence"
        shutil.copytree(runs["run-a"]["output_dir"], evidence)
        shutil.copy2(runs["run-a"]["stdout"], work / "native_stdout.log")
        shutil.copy2(runs["run-a"]["stderr"], work / "native_stderr.log")
        report: dict[str, Any] = {
            "schema": SCHEMA,
            "status": "NODE0001_REQUANT_TWO_STAGE_LOCAL_E2_COMPLETE",
            "request_id": REQUEST_ID,
            "rule_ids_passed": list(RULE_IDS),
            "candidate_release": False,
            "formal_target_instance_allowed": False,
            "server_package": False,
            "dynamic_release_ready": False,
            "dynamic_baseline": "NO_DYNAMIC_BASELINE",
            "generation_receipt_sha256": receipt["receipt_sha256"],
            "numeric_evidence": numeric,
            "sfu_payload": sfu_evidence,
            "static_config_type_count": len(configs),
            "materialized_roundtrip": roundtrip_a,
            "lifecycle": runs["run-a"]["barrier"],
            "native_double_rebuild": deterministic,
            "source_identity": {
                "active_ndp_sim_unchanged": True,
                "rtl_modified": False,
                "pre_post_identity": active_after,
            },
            "remaining_blocker": "B_REQUANT_SERVER_E4_E5",
            "boundary": (
                "E2 proves typed request -> two-stage JSON -> native mapping/"
                "bitstream/execplan/SCA reconstruction and full W3 software "
                "replay; it does not prove stock-RTL execution or readback"
            ),
        }
        report["report_sha256"] = sha256_bytes(canonical_json_bytes(report))
        _write_json(work / "local_e2_report.json", report)
        manifest_files = _file_map(work)
        manifest: dict[str, Any] = {
            "schema": "node0001-requant-two-stage-artifact-manifest-v1",
            "files": manifest_files,
        }
        manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
        _write_json(work / "manifest.json", manifest)
        shutil.copytree(work, artifact)
    if artifact_root is None:
        materialize_static_assets(root, configs, static_manifest, receipt)
        contract: dict[str, Any] = {
            "schema": "operator-config-semantic-contract-v1",
            "status": "LOCAL_E2_COMPLETE_DYNAMIC_PENDING",
            "request_id": REQUEST_ID,
            "node_id": NODE_ID,
            "hw_op_id": HW_OP_ID,
            "rule_ids": list(RULE_IDS),
            "artifact": _file_binding(root, artifact / "local_e2_report.json"),
            "config_root": CONFIG_REL.as_posix(),
            "candidate_release": False,
            "formal_target_instance_allowed": False,
            "server_package": False,
            "dynamic_baseline": "NO_DYNAMIC_BASELINE",
            "remaining_blockers": ["B_REQUANT_SERVER_E4_E5"],
        }
        contract["contract_sha256"] = sha256_bytes(
            canonical_json_bytes(contract)
        )
        _write_json(root / CONTRACT_REL, contract)
    return {
        "status": "NODE0001_REQUANT_TWO_STAGE_LOCAL_E2_COMPLETE",
        "artifact_root": str(artifact),
        "report_sha256": sha256_file(artifact / "local_e2_report.json"),
        "contract_path": (
            str(root / CONTRACT_REL) if artifact_root is None else None
        ),
        "remaining_blocker": "B_REQUANT_SERVER_E4_E5",
        "candidate_release": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--run-e2", action="store_true")
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    if args.run_e2:
        result = run_local_e2(
            root,
            artifact_root=args.artifact_root,
            python_executable=Path(sys.executable),
        )
    else:
        configs, manifest = build_static_configs(root)
        result = {
            "receipt": build_generation_receipt(root),
            "numeric": build_numeric_evidence(root),
            "config_type_count": len(configs),
            "static_manifest": manifest,
            "graph_stage_count": len(build_graph()["operators"]),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "RequantizeUint8VerticalError",
    "build_generation_receipt",
    "build_graph",
    "build_guard_config",
    "build_guard_sfu_words",
    "build_numeric_evidence",
    "build_round_config",
    "build_static_configs",
    "run_local_e2",
    "validate_guard_sfu_payload",
]
