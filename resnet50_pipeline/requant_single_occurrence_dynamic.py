"""Materialize the minimal two-stage dynamic contract for node0001 Requant.

The output is a diagnostic-only local E2 asset.  It contains two strict
address-bound JSON configurations, deterministic HWC8 input/golden payloads,
accepted MSE4 write expectations, and the stage0-D -> stage1-A lifecycle
contract.  It does not generate a server package or modify RTL.
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_validator import OperatorConfigValidator
from .requantize_uint8_vertical import (
    GA_MAC_KEYS,
    GA_SUB_KEYS,
    ROUND_MAGIC_BITS,
    guard_sfu_text,
    validate_guard_sfu_payload,
)


SCHEMA = "requant-node0001-single-occurrence-two-stage-dynamic-contract-v2"
RULE_ID = "CDA-REQUANT-ATOMIC-SINGLE-OCCURRENCE-001"
STOCK_TB_RULE_ID = "CDA-REQUANT-ATOMIC-STOCK-TB-MASK-COMPAT-001"
SPATIAL = 4
LANES = 8
ACTIVE_SLICES = (0, 1)
SLICE_MASK = "0b0000000000000000000000000011"
GUARD_A_BASE = 0x00000000
GUARD_D_BASE = 0x00800000
ROUND_D_BASE = 0x01000000
CONFIG_ROOT_REL = Path(
    "configs/native_ndp_sim/"
    "node0001_requant_single_occurrence_two_stage_v2"
)
ARTIFACT_ROOT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-node0001-single-occurrence-two-stage-v2"
)
REPORT_REL = ARTIFACT_ROOT_REL / "local_contract_report.json"
CONTRACT_REL = Path(
    "contracts/operator_config/"
    "requant_node0001_single_occurrence_two_stage_dynamic_v2.json"
)
V1_MANIFEST_REL = Path(
    "configs/native_ndp_sim/"
    "node0001_requant_single_occurrence_two_stage_v1/manifest.json"
)
GUARD_SOURCE_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-node0001-two-stage-e2-v1/native_evidence/jsons/"
    "op_w0_s00_guard_resnet50_requant_guard_node0001.json"
)
ROUND_SOURCE_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-node0001-two-stage-e2-v1/native_evidence/jsons/"
    "op_w0_s00_round_resnet50_requant_round_node0001_s00.json"
)
EXPECTED_SOURCE_SHA256 = {
    GUARD_SOURCE_REL.as_posix(): (
        "c9bb71629553913fe15fe07dc89e24ac504afc4f5c45470199c33273a242abc6"
    ),
    ROUND_SOURCE_REL.as_posix(): (
        "19f42dcd43d0a27f66ac189a2fb20cb475b39fc3bc276ba181fed1cf98120c1a"
    ),
}
READ_SOURCES = {
    "agent_policy": Path(".agents/agent.md"),
    "generation_read_index": Path(".agents/rules/生成前必读索引.md"),
    "operator_rules": Path(".agents/rules/算子配置规则.md"),
    "hardware_field_semantics": Path(".agents/rules/NDP硬件字段语义.md"),
    "requant_rules": Path(".agents/rules/RequantizeUint8算子配置规则.md"),
    "node0001_materializer": Path(
        "resnet50_pipeline/requantize_uint8_vertical.py"
    ),
    "node0001_server_evidence_consumer": Path(
        "tools/requant_node0001_server_runtime.py"
    ),
    "stock_tb_entry_contract": Path("NDP_copy01/README_HARDWARE_SIM_ENTRY.md"),
    "stock_tb_completion_consumer": Path("NDP_copy01/tb_NDP_Top_new_phy.sv"),
    "native_loop_encoder": Path("ndp-sim/bitstream/config/loop.py"),
    "native_stream_encoder": Path("ndp-sim/bitstream/config/stream.py"),
    "native_buffer_encoder": Path("ndp-sim/bitstream/config/buffer.py"),
    "native_ga_encoder": Path("ndp-sim/bitstream/config/general.py"),
    "source_guard_final_json": GUARD_SOURCE_REL,
    "source_round_final_json": ROUND_SOURCE_REL,
    "superseded_v1_manifest": V1_MANIFEST_REL,
}
RULE_IDS = (
    "CDA-CONFIG-SEMANTIC-OWNERSHIP-001",
    "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
    "CDA-REQUANT-QPARAM-001",
    "CDA-REQUANT-INT32-GUARD-001",
    "CDA-REQUANT-SFU-LUT-001",
    "CDA-REQUANT-TWO-STAGE-001",
    "CDA-REQUANT-ROUND-MAGIC-001",
    RULE_ID,
    STOCK_TB_RULE_ID,
)


class RequantAtomicContractError(ValueError):
    """Raised when the minimal dynamic contract is inconsistent."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RequantAtomicContractError(
            f"cannot parse JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise RequantAtomicContractError(f"JSON root is not an object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _binding(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    return {
        "path": resolved.relative_to(root).as_posix(),
        "size_bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def _self_hash(value: Mapping[str, Any], field: str) -> str:
    payload = {key: item for key, item in value.items() if key != field}
    return sha256_bytes(canonical_json_bytes(payload))


def _flatten(value: Any, path: str = "$") -> dict[str, Any]:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value):
            result.update(_flatten(value[key], f"{path}.{key}"))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            result.update(_flatten(item, f"{path}[{index}]"))
        return result
    return {path: value}


def _strict(config: Mapping[str, Any], source: str) -> None:
    report = OperatorConfigValidator().validate(config, source=source)
    if not report.valid:
        raise RequantAtomicContractError(
            f"strict JSON validation failed: {report.to_dict()['first_error']}"
        )


def _check_source_identity(root: Path) -> None:
    for relative, expected in EXPECTED_SOURCE_SHA256.items():
        path = root / relative
        if not path.is_file() or sha256_file(path) != expected:
            observed = sha256_file(path) if path.is_file() else None
            raise RequantAtomicContractError(
                f"trusted final JSON identity differs: {relative}: {observed}"
            )


def _assert_exact_diff(
    source: Mapping[str, Any],
    derived: Mapping[str, Any],
    expected: Mapping[str, tuple[Any, Any]],
    role: str,
) -> list[dict[str, Any]]:
    before = _flatten(source)
    after = _flatten(derived)
    paths = sorted(
        key for key in set(before) | set(after) if before.get(key) != after.get(key)
    )
    if paths != sorted(expected):
        raise RequantAtomicContractError(
            f"{role} derived JSON diff set differs: {paths}"
        )
    records = []
    for path in paths:
        wanted_before, wanted_after = expected[path]
        if before[path] != wanted_before or after[path] != wanted_after:
            raise RequantAtomicContractError(
                f"{role} derived JSON diff value differs at {path}"
            )
        records.append(
            {
                "path": path,
                "source_value": before[path],
                "derived_value": after[path],
                "owner": "single-occurrence four-spatial schedule",
            }
        )
    return records


def derive_configs(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = root.resolve()
    _check_source_identity(root)
    source_guard = _load(root / GUARD_SOURCE_REL)
    source_round = _load(root / ROUND_SOURCE_REL)
    guard = deepcopy(source_guard)
    round_config = deepcopy(source_round)

    guard["dram_loop_configs"]["LC1"]["end"] = SPATIAL
    guard["dram_loop_configs"]["LC2"]["end"] = SPATIAL
    guard["stream_engine"]["stream0"]["dim_stride"][1] = SPATIAL * 32
    guard["stream_engine"]["stream2"]["dim_stride"][1] = SPATIAL * 32

    round_config["dram_loop_configs"]["LC1"]["end"] = SPATIAL
    round_config["dram_loop_configs"]["LC2"]["end"] = SPATIAL // 4
    round_config["stream_engine"]["stream0"]["dim_stride"][1] = SPATIAL * 32
    round_config["stream_engine"]["stream2"]["dim_stride"][1] = (
        (SPATIAL // 4) * 32
    )

    guard_diff = _assert_exact_diff(
        source_guard,
        guard,
        {
            "$.dram_loop_configs.LC1.end": (12544, 4),
            "$.dram_loop_configs.LC2.end": (12544, 4),
            "$.stream_engine.stream0.dim_stride[1]": (401408, 128),
            "$.stream_engine.stream2.dim_stride[1]": (401408, 128),
        },
        "guard",
    )
    round_diff = _assert_exact_diff(
        source_round,
        round_config,
        {
            "$.dram_loop_configs.LC1.end": (12544, 4),
            "$.dram_loop_configs.LC2.end": (3136, 1),
            "$.stream_engine.stream0.dim_stride[1]": (401408, 128),
            "$.stream_engine.stream2.dim_stride[1]": (100352, 32),
        },
        "round_saturate",
    )
    _strict(guard, "node0001-single-occurrence-guard")
    _strict(round_config, "node0001-single-occurrence-round")
    provenance = {
        "derivation_mode": "exact_leaf_diff_from_closed_final_json_topology",
        "source_guard": _binding(root, GUARD_SOURCE_REL),
        "source_round": _binding(root, ROUND_SOURCE_REL),
        "superseded_v1_manifest": _binding(root, V1_MANIFEST_REL),
        "superseded_v1_classification": (
            "STOCK_TB_COMPLETION_MASK_INCOMPATIBLE"
        ),
        "superseded_v1_dynamic_attempt": False,
        "guard_changed_leaves": guard_diff,
        "round_changed_leaves": round_diff,
        "all_other_leaves_byte_semantically_unchanged": True,
    }
    return guard, round_config, provenance


def _lane_constants(round_config: Mapping[str, Any]) -> dict[str, np.ndarray]:
    pe = round_config["general_array"]["PE_array"]
    multiplier = np.asarray(
        [pe[key]["inport1"]["constant"] for key in GA_MAC_KEYS],
        dtype=np.float32,
    )
    magic = np.asarray(
        [pe[key]["inport2"]["constant"] for key in GA_MAC_KEYS],
        dtype=np.float32,
    )
    subtract = np.asarray(
        [pe[key]["inport1"]["constant"] for key in GA_SUB_KEYS],
        dtype=np.int64,
    )
    if (
        not np.isfinite(multiplier).all()
        or not np.all(multiplier > 0)
        or np.any(magic.view(np.uint32) != np.uint32(ROUND_MAGIC_BITS))
        or np.any(subtract != ROUND_MAGIC_BITS)
    ):
        raise RequantAtomicContractError("round lane constants differ")
    return {
        "multiplier": multiplier,
        "magic": magic,
        "subtract": subtract,
    }


def _find_half_tie(multiplier: np.float32) -> int:
    for integer_part in range(256):
        center = (np.float64(integer_part) + 0.5) / np.float64(multiplier)
        candidate = int(round(center))
        for value in range(max(0, candidate - 8), candidate + 9):
            scaled = np.float32(np.float32(value) * multiplier)
            if float(scaled) - math.floor(float(scaled)) == 0.5:
                return value
    raise RequantAtomicContractError(
        f"no exact FP32 half tie found for multiplier {float(multiplier)}"
    )


def build_vectors(
    round_config: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    constants = _lane_constants(round_config)
    multiplier = constants["multiplier"]
    magic = constants["magic"]
    subtract = constants["subtract"]
    tie_values = np.asarray(
        [_find_half_tie(value) for value in multiplier], dtype=np.int32
    )
    saturation = np.asarray(
        [math.ceil(300.0 / float(value)) for value in multiplier],
        dtype=np.int32,
    )
    normal_targets = np.asarray(
        [0.49, 0.51, 1.49, 1.51, 127.4, 127.6, 254.4, 254.6],
        dtype=np.float64,
    )
    normal = np.asarray(
        [
            max(1, int(round(target / float(value))))
            for target, value in zip(normal_targets, multiplier, strict=True)
        ],
        dtype=np.int32,
    )
    slice0_source = np.asarray(
        [
            [
                np.iinfo(np.int32).min,
                -1,
                0,
                1,
                2,
                3,
                4,
                5,
            ],
            tie_values.tolist(),
            saturation.tolist(),
            normal.tolist(),
        ],
        dtype=np.int32,
    )
    source = np.stack(
        [
            slice0_source,
            np.roll(slice0_source, shift=1, axis=0),
        ],
        axis=0,
    )
    guard = np.maximum(source, 0).astype(np.float32)
    scaled = np.multiply(
        guard,
        multiplier.reshape(1, 1, LANES),
        dtype=np.float32,
    )
    biased = np.add(
        scaled,
        magic.reshape(1, 1, LANES),
        dtype=np.float32,
    )
    rounded = (
        biased.view(np.int32).astype(np.int64)
        - subtract.reshape(1, 1, LANES)
    )
    final = np.clip(rounded, 0, 255).astype(np.uint8)
    independent = np.clip(np.rint(scaled), 0, 255).astype(np.uint8)
    if np.any(final != independent):
        where = np.argwhere(final != independent)[0].tolist()
        raise RequantAtomicContractError(
            f"magic and independent half-even differ at {where}"
        )
    tie_mask = np.equal(
        scaled - np.floor(scaled, dtype=np.float32), np.float32(0.5)
    )
    tie_count_by_slice = [
        int(np.count_nonzero(tie_mask[slice_id]))
        for slice_id in range(len(ACTIVE_SLICES))
    ]
    if any(count < LANES for count in tie_count_by_slice):
        raise RequantAtomicContractError(
            "each active slice must cover all eight exact-half lanes"
        )
    tie_floor = np.floor(scaled).astype(np.int64)
    tie_rounded = np.rint(scaled).astype(np.int64)
    coverage = {
        "active_slices": list(ACTIVE_SLICES),
        "physical_slice_instance_count": len(ACTIVE_SLICES),
        "element_count": int(source.size),
        "negative_count": int(np.count_nonzero(source < 0)),
        "minus_one_count": int(np.count_nonzero(source == -1)),
        "zero_count": int(np.count_nonzero(source == 0)),
        "positive_count": int(np.count_nonzero(source > 0)),
        "exact_half_even_tie_count": int(np.count_nonzero(tie_mask)),
        "tie_round_down_to_even_count": int(
            np.count_nonzero(tie_rounded == tie_floor)
        ),
        "tie_round_up_to_even_count": int(
            np.count_nonzero(tie_rounded == tie_floor + 1)
        ),
        "exact_half_even_tie_count_by_slice": tie_count_by_slice,
        "lower_saturation_count": int(np.count_nonzero(final == 0)),
        "upper_saturation_count": int(np.count_nonzero(final == 255)),
        "lane_multiplier_count": int(multiplier.size),
        "lane_multiplier_bits": [
            f"0x{int(value.view(np.uint32)):08x}" for value in multiplier
        ],
        "tie_input_by_lane": [int(value) for value in tie_values],
        "tie_scaled_by_lane": [
            float(value) for value in scaled[0, 1]
        ],
        "slice1_is_slice0_row_rotation": bool(
            np.array_equal(source[1], np.roll(source[0], shift=1, axis=0))
        ),
        "all_required_classes_present": True,
        "magic_vs_independent_mismatch_count": 0,
    }
    required_positive = (
        coverage["negative_count"] > 0
        and coverage["minus_one_count"] > 0
        and coverage["zero_count"] > 0
        and coverage["positive_count"] > 0
        and coverage["exact_half_even_tie_count"] >= LANES
        and coverage["tie_round_down_to_even_count"] > 0
        and coverage["tie_round_up_to_even_count"] > 0
        and coverage["lower_saturation_count"] > 0
        and coverage["upper_saturation_count"] > 0
        and coverage["lane_multiplier_count"] == LANES
    )
    if not required_positive:
        raise RequantAtomicContractError(
            f"diagnostic vector boundary coverage differs: {coverage}"
        )
    return source, guard, final, coverage


def _lines128(payload: bytes) -> list[str]:
    if len(payload) % 16:
        raise RequantAtomicContractError("payload is not 128-bit aligned")
    return [
        f"{int.from_bytes(payload[offset:offset + 16], 'little'):0128b}"
        for offset in range(0, len(payload), 16)
    ]


def _write_128bit_text(path: Path, payload: bytes) -> None:
    lines = _lines128(payload)
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


def _mse4_beats(
    *,
    slice_id: int,
    stage_index: int,
    role: str,
    base: int,
    payload: bytes,
) -> list[dict[str, Any]]:
    records = []
    for beat, offset in enumerate(range(0, len(payload), 16)):
        chunk = payload[offset : offset + 16]
        records.append(
            {
                "slice_id": slice_id,
                "stage_index": stage_index,
                "role": role,
                "beat_index": beat,
                "byte_address": f"0x{base + offset:08x}",
                "word_address_128b": f"0x{(base + offset) // 16:x}",
                "strobe": "0xffff",
                "data": f"0x{int.from_bytes(chunk, 'little'):032x}",
                "data_sha256": hashlib.sha256(chunk).hexdigest(),
            }
        )
    return records


def _stage_semantics(
    guard: Mapping[str, Any],
    round_config: Mapping[str, Any],
) -> dict[str, Any]:
    guard_a = int(str(guard["stream_engine"]["stream0"]["base_addr"]), 0)
    guard_d = int(str(guard["stream_engine"]["stream2"]["base_addr"]), 0)
    round_a = int(str(round_config["stream_engine"]["stream0"]["base_addr"]), 0)
    round_d = int(str(round_config["stream_engine"]["stream2"]["base_addr"]), 0)
    if (guard_a, guard_d, round_a, round_d) != (
        GUARD_A_BASE,
        GUARD_D_BASE,
        GUARD_D_BASE,
        ROUND_D_BASE,
    ):
        raise RequantAtomicContractError("atomic address topology differs")
    if any(
        pe["transout_last_index"] is not None
        for config in (guard, round_config)
        for pe in config["general_array"]["PE_array"].values()
    ):
        raise RequantAtomicContractError("atomic stages are not normal outbuffer")
    return {
        "active_slices": list(ACTIVE_SLICES),
        "slice_mask": SLICE_MASK,
        "logical_occurrence_count": 1,
        "physical_slice_instance_count": len(ACTIVE_SLICES),
        "stage_count": 2,
        "repeat_num": 2,
        "stage_sequence": [
            {
                "stage_index": 0,
                "role": "guard",
                "input_dtype": "int32",
                "output_dtype": "fp32",
                "per_slice_input_shape": [1, SPATIAL, LANES],
                "per_slice_output_shape": [1, SPATIAL, LANES],
                "input_base_addr": f"0x{guard_a:08x}",
                "output_base_addr": f"0x{guard_d:08x}",
                "expected_write_bytes_per_slice": SPATIAL * LANES * 4,
                "expected_write_bytes_total": (
                    len(ACTIVE_SLICES) * SPATIAL * LANES * 4
                ),
                "expected_mse4_accepted_write_beats_per_slice": 8,
                "expected_mse4_accepted_write_beats_total": (
                    len(ACTIVE_SLICES) * 8
                ),
                "normal_outbuffer": True,
            },
            {
                "stage_index": 1,
                "role": "round_saturate",
                "input_dtype": "fp32",
                "output_dtype": "uint8",
                "per_slice_input_shape": [1, SPATIAL, LANES],
                "per_slice_output_shape": [1, SPATIAL, LANES],
                "input_base_addr": f"0x{round_a:08x}",
                "output_base_addr": f"0x{round_d:08x}",
                "expected_write_bytes_per_slice": SPATIAL * LANES,
                "expected_write_bytes_total": (
                    len(ACTIVE_SLICES) * SPATIAL * LANES
                ),
                "expected_mse4_accepted_write_beats_per_slice": 2,
                "expected_mse4_accepted_write_beats_total": (
                    len(ACTIVE_SLICES) * 2
                ),
                "normal_outbuffer": True,
            },
        ],
        "handoff": {
            "stage0_output_equals_stage1_input_address": guard_d == round_a,
            "stage1_external_preload_count": 0,
            "same_slice_mask": True,
            "barrier_scope": "all active slices",
            "required_order": [
                "load RequantGuard once",
                "load guard config",
                "start guard",
                "guard Comp Finish",
                "load round config",
                "start round",
                "round Comp Finish",
            ],
            "stage1_start_requires_stage0_comp_finish": True,
            "stage0_write_visible_before_stage1_read": True,
        },
        "dynamic_acceptance": {
            "natural_completion_required": True,
            "stage_start_group_count": 2,
            "stage_comp_finish_group_count": 2,
            "per_slice_start_event_count": 4,
            "per_slice_comp_finish_event_count": 4,
            "guard_sfu_load_count": 1,
            "guard_sfu_loaded_before_first_start": True,
            "mse4_total_accepted_write_beat_count": 20,
            "unexpected_mse4_write_count": 0,
        },
        "stock_tb_completion_observer": {
            "mask_aware": False,
            "start_sampled_slice": 0,
            "finish_sampled_slice": 1,
            "required_sampled_slices_enabled": True,
            "repeat_num_counts_stages_not_slices": True,
            "tb_or_rtl_modification_authorized": False,
        },
    }


def _graph() -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "plan_id": "node0001-requant-single-occurrence-two-stage-v2",
        "used_slices": SLICE_MASK,
        "params": {
            "request_id": "r5:hwop-0001-01",
            "diagnostic_only": True,
            "candidate_release": False,
            "logical_occurrence_count": 1,
            "physical_slice_instance_count": len(ACTIVE_SLICES),
            "active_slices": list(ACTIVE_SLICES),
            "stock_tb_completion_compatible": True,
        },
        "operators": [
            {
                "id": "op_atomic_guard",
                "type": "resnet50_requant_guard_node0001",
                "stage": "guard",
                "used_slices": SLICE_MASK,
                "inputs": {
                    "A": {
                        "shape": [1, SPATIAL, LANES],
                        "dtype": "int32",
                        "tensor_id": "atomic.A_int32",
                        "source": {"type": "external"},
                        "base_addr": f"0x{GUARD_A_BASE:08x}",
                    }
                },
                "output": {
                    "shape": [1, SPATIAL, LANES],
                    "dtype": "fp32",
                    "tensor_id": "atomic.guard_fp32",
                    "base_addr": f"0x{GUARD_D_BASE:08x}",
                },
            },
            {
                "id": "op_atomic_round",
                "type": "resnet50_requant_round_node0001_s00",
                "stage": "round_saturate",
                "used_slices": SLICE_MASK,
                "inputs": {
                    "A": {
                        "shape": [1, SPATIAL, LANES],
                        "dtype": "fp32",
                        "tensor_id": "atomic.guard_fp32",
                        "source": {
                            "type": "operator",
                            "operator_id": "op_atomic_guard",
                        },
                        "base_addr": f"0x{GUARD_D_BASE:08x}",
                    }
                },
                "output": {
                    "shape": [1, SPATIAL, LANES],
                    "dtype": "uint8",
                    "tensor_id": "atomic.D_uint8",
                    "base_addr": f"0x{ROUND_D_BASE:08x}",
                },
            },
        ],
    }


def _read_receipt(root: Path) -> dict[str, Any]:
    missing = [
        relative.as_posix()
        for relative in READ_SOURCES.values()
        if not (root / relative).is_file()
    ]
    if missing:
        raise RequantAtomicContractError(f"read receipt inputs missing: {missing}")
    receipt: dict[str, Any] = {
        "schema": "requant-atomic-generation-read-receipt-v2",
        "read_at": "2026-07-26",
        "scope": (
            "derive two strict JSONs and deterministic dynamic expectations; "
            "no bitstream, server package, server run, or RTL change"
        ),
        "read_receipt": [
            {
                "label": label,
                **_binding(root, relative),
                "reason": (
                    "rule routing and field semantics"
                    if "rule" in label
                    or label in {
                        "agent_policy",
                        "generation_read_index",
                        "hardware_field_semantics",
                    }
                    else "actual source topology or direct consumer"
                ),
            }
            for label, relative in READ_SOURCES.items()
        ],
        "rule_ids": list(RULE_IDS),
        "known_counterexamples": [
            "CDA-GA-INPORT-CONVERT-001",
            "guard is required before negative INT32 reaches round MAC",
        ],
        "direct_consumer_findings": {
            "stock_tb_repeat_num_semantics": "stage start count",
            "stock_tb_start_sampled_slice": 0,
            "stock_tb_finish_sampled_slice": 1,
            "stock_tb_completion_observer_mask_aware": False,
            "stock_tb_run_time_cycles": 100000000000000,
            "minimum_compatible_active_slices": list(ACTIVE_SLICES),
        },
        "open_dynamic_gates": ["B_REQUANT_SERVER_E4_E5"],
        "omitted_files": [
            {
                "path": ".agents/rules/服务器测试包生成规则.md",
                "reason": "this task does not generate a server package",
            },
            {
                "path": "NDP_copy01/rtl/**",
                "reason": (
                    "no RTL is modified; stable field semantics and the "
                    "already-closed source topology own this derivation"
                ),
            },
        ],
    }
    receipt["receipt_sha256"] = _self_hash(receipt, "receipt_sha256")
    return receipt


def materialize_bundle(root: Path, output_root: Path) -> dict[str, Any]:
    root = root.resolve()
    output = output_root.resolve()
    if output.exists():
        raise RequantAtomicContractError(
            f"refusing to overwrite atomic contract root: {output}"
        )
    output.mkdir(parents=True)
    guard, round_config, provenance = derive_configs(root)
    source, guard_golden, final_golden, coverage = build_vectors(round_config)
    lifecycle = _stage_semantics(guard, round_config)
    input_payloads = {
        slice_id: np.ascontiguousarray(source[index]).tobytes()
        for index, slice_id in enumerate(ACTIVE_SLICES)
    }
    guard_payloads = {
        slice_id: np.ascontiguousarray(guard_golden[index]).tobytes()
        for index, slice_id in enumerate(ACTIVE_SLICES)
    }
    final_payloads = {
        slice_id: np.ascontiguousarray(final_golden[index]).tobytes()
        for index, slice_id in enumerate(ACTIVE_SLICES)
    }
    guard_writes = [
        record
        for slice_id in ACTIVE_SLICES
        for record in _mse4_beats(
            slice_id=slice_id,
            stage_index=0,
            role="guard",
            base=GUARD_D_BASE,
            payload=guard_payloads[slice_id],
        )
    ]
    round_writes = [
        record
        for slice_id in ACTIVE_SLICES
        for record in _mse4_beats(
            slice_id=slice_id,
            stage_index=1,
            role="round_saturate",
            base=ROUND_D_BASE,
            payload=final_payloads[slice_id],
        )
    ]
    expected_writes = {
        "schema": "requant-atomic-mse4-write-contract-v2",
        "physical_engine": "MSE4_WRITE_STREAM0",
        "active_slices": list(ACTIVE_SLICES),
        "address_unit_note": (
            "addresses are local to each physical slice; slice_id plus "
            "word_address_128b is the observer identity"
        ),
        "stages": [
            {
                "stage_index": 0,
                "role": "guard",
                "expected_accepted_write_count_per_slice": 8,
                "expected_accepted_write_count_total": len(guard_writes),
                "writes": guard_writes,
            },
            {
                "stage_index": 1,
                "role": "round_saturate",
                "expected_accepted_write_count_per_slice": 2,
                "expected_accepted_write_count_total": len(round_writes),
                "writes": round_writes,
            },
        ],
        "total_expected_accepted_write_count": (
            len(guard_writes) + len(round_writes)
        ),
        "duplicate_or_extra_write_allowed": False,
    }
    fallback_policy = {
        "schema": "requant-atomic-first-divergence-routing-v2",
        "default_enabled_contracts": [
            "single-occurrence-two-stage"
        ],
        "default_disabled_contracts": [
            "guard-only",
            "round-only",
            "alias-lifetime",
        ],
        "activation": [
            {
                "first_divergence": (
                    "guard accepted write/data or guard completion"
                ),
                "enable_only": "guard-only",
            },
            {
                "first_divergence": (
                    "guard completion to round start, same-address visibility, "
                    "or stage1 external-preload isolation"
                ),
                "enable_only": "alias-lifetime",
            },
            {
                "first_divergence": (
                    "round accepted write/data after round has started"
                ),
                "enable_only": "round-only",
            },
        ],
        "combined_pass_action": "keep_all_additional_atomic_contracts_disabled",
        "both_writes_correct_but_completion_missing": (
            "retain combined completion evidence; do not expand unrelated tests"
        ),
    }
    receipt = _read_receipt(root)
    _write_json(output / "guard.json", guard)
    _write_json(output / "round_saturate.json", round_config)
    _write_json(output / "typed_graph.json", _graph())
    _write_json(output / "derivation_provenance.json", provenance)
    _write_json(output / "coverage_contract.json", coverage)
    _write_json(output / "lifecycle_contract.json", lifecycle)
    _write_json(output / "expected_mse4_writes.json", expected_writes)
    _write_json(output / "first_divergence_routing.json", fallback_policy)
    _write_json(output / "generation_receipt.json", receipt)
    (output / "RequantGuard.txt").write_text(
        guard_sfu_text(), encoding="ascii", newline="\n"
    )
    np.save(output / "input_int32_hwc8.npy", source, allow_pickle=False)
    np.save(
        output / "guard_golden_fp32_hwc8.npy",
        guard_golden,
        allow_pickle=False,
    )
    np.save(
        output / "final_golden_uint8_hwc8.npy",
        final_golden,
        allow_pickle=False,
    )
    for slice_id in ACTIVE_SLICES:
        suffix = f"slice{slice_id:02d}_128b.txt"
        _write_128bit_text(
            output / f"input_int32_{suffix}",
            input_payloads[slice_id],
        )
        _write_128bit_text(
            output / f"guard_golden_{suffix}",
            guard_payloads[slice_id],
        )
        _write_128bit_text(
            output / f"final_golden_{suffix}",
            final_payloads[slice_id],
        )
    files = {
        path.relative_to(output).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(item for item in output.rglob("*") if item.is_file())
    }
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "LOCAL_DYNAMIC_CONTRACT_MATERIALIZED_NOT_RUN",
        "request_id": "r5:hwop-0001-01",
        "scope": (
            "one logical HWC8 occurrence replicated across stock-TB-required "
            "slices0+1, guard then round_saturate"
        ),
        "rule_ids": list(RULE_IDS),
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "dynamic_release_ready": False,
        "server_package": False,
        "evidence_level": "E2_LOCAL_CONTRACT_ONLY",
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "diagnostic_only": True,
        "supersedes_packaging_identity": {
            **_binding(root, V1_MANIFEST_REL),
            "classification": "STOCK_TB_COMPLETION_MASK_INCOMPATIBLE",
            "dynamic_attempt": False,
        },
        "counts": {
            "logical_occurrence": 1,
            "physical_slice_instance": len(ACTIVE_SLICES),
            "stage": 2,
            "element_total": int(source.size),
            "element_per_slice": SPATIAL * LANES,
            "guard_bytes_total": sum(map(len, guard_payloads.values())),
            "guard_bytes_per_slice": SPATIAL * LANES * 4,
            "final_bytes_total": sum(map(len, final_payloads.values())),
            "final_bytes_per_slice": SPATIAL * LANES,
            "guard_mse4_accepted_write_beats_total": len(guard_writes),
            "guard_mse4_accepted_write_beats_per_slice": 8,
            "round_mse4_accepted_write_beats_total": len(round_writes),
            "round_mse4_accepted_write_beats_per_slice": 2,
        },
        "generation_receipt_sha256": receipt["receipt_sha256"],
        "guard_sfu": validate_guard_sfu_payload(guard_sfu_text()),
        "files": files,
        "remaining_blockers": ["B_REQUANT_SERVER_E4_E5"],
        "claim_boundary": (
            "This asset is a minimal diagnostic dynamic contract.  It is not "
            "a bitstream, server package, stock-RTL result, or formal E4/E5."
        ),
    }
    manifest["manifest_sha256"] = _self_hash(manifest, "manifest_sha256")
    _write_json(output / "manifest.json", manifest)
    return manifest


def materialize_project_assets(root: Path) -> dict[str, Any]:
    root = root.resolve()
    config_root = root / CONFIG_ROOT_REL
    report_path = root / REPORT_REL
    contract_path = root / CONTRACT_REL
    if report_path.exists() or contract_path.exists():
        raise RequantAtomicContractError(
            "refusing to overwrite checked-in atomic report/contract"
        )
    manifest = materialize_bundle(root, config_root)
    report: dict[str, Any] = {
        "schema": "requant-atomic-local-contract-report-v2",
        "status": manifest["status"],
        "request_id": manifest["request_id"],
        "rule_ids": manifest["rule_ids"],
        "config_root": CONFIG_ROOT_REL.as_posix(),
        "manifest": _binding(root, config_root / "manifest.json"),
        "counts": manifest["counts"],
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "server_package": False,
        "dynamic_release_ready": False,
        "dynamic_execution_status": "NOT_RUN",
        "stock_tb_completion_compatible": True,
        "active_slices": list(ACTIVE_SLICES),
        "superseded_v1_classification": (
            "STOCK_TB_COMPLETION_MASK_INCOMPATIBLE"
        ),
        "additional_atomic_contracts_enabled": [],
        "remaining_blockers": ["B_REQUANT_SERVER_E4_E5"],
    }
    report["report_sha256"] = _self_hash(report, "report_sha256")
    _write_json(report_path, report)
    contract: dict[str, Any] = {
        "schema": "operator-config-semantic-contract-v1",
        "contract_id": (
            "requant-node0001-single-occurrence-two-stage-dynamic-v2"
        ),
        "status": "LOCAL_DYNAMIC_CONTRACT_MATERIALIZED_NOT_RUN",
        "request_id": "r5:hwop-0001-01",
        "rule_ids": list(RULE_IDS),
        "config_manifest": _binding(root, config_root / "manifest.json"),
        "local_report": _binding(root, report_path),
        "default_dynamic_contract": "single-occurrence-two-stage",
        "logical_occurrence_count": 1,
        "physical_slice_instance_count": len(ACTIVE_SLICES),
        "active_slices": list(ACTIVE_SLICES),
        "stock_tb_completion_compatible": True,
        "additional_atomic_contracts": {
            "guard-only": "disabled_until_matching_first_divergence",
            "round-only": "disabled_until_matching_first_divergence",
            "alias-lifetime": "disabled_until_matching_first_divergence",
        },
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "server_package": False,
        "dynamic_release_ready": False,
        "counts_as_node0001_e4": False,
        "counts_as_node0001_e5": False,
        "remaining_blockers": ["B_REQUANT_SERVER_E4_E5"],
    }
    contract["contract_sha256"] = _self_hash(contract, "contract_sha256")
    _write_json(contract_path, contract)
    return {
        "status": contract["status"],
        "config_root": CONFIG_ROOT_REL.as_posix(),
        "report": REPORT_REL.as_posix(),
        "contract": CONTRACT_REL.as_posix(),
        "manifest_sha256": manifest["manifest_sha256"],
        "candidate_release": False,
        "server_package": False,
    }


__all__ = [
    "ARTIFACT_ROOT_REL",
    "CONFIG_ROOT_REL",
    "CONTRACT_REL",
    "REPORT_REL",
    "RequantAtomicContractError",
    "build_vectors",
    "derive_configs",
    "materialize_bundle",
    "materialize_project_assets",
]
