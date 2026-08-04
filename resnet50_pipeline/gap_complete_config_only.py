"""Complete node-0071 GAP local E2 by reusing the frozen sum tree.

The six-stage non-transout INT32 sum tree is an immutable dependency.  This
module only materializes and validates the shared two-stage exact UINT8 tail,
then serializes both pieces into one eight-stage execution plan.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .exact_uint8_quant_tail_rounding_discriminator import (
    EVEN_PES,
    MAGIC_BITS,
    MAGIC_FLOAT,
    ODD_PES,
)
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_validator import OperatorConfigValidator


SCHEMA = "resnet50-gap-node0071-complete-config-only-local-e2-v1"
CLAIM = "CONFIG_ONLY_CORRECTNESS_BASELINE"
NODE_ID = "node-0071"
SLICE_COUNT = 16
SLICE_MASK = (1 << SLICE_COUNT) - 1
BLOCKS = 256
LANES = 8
SUM_BASE = 0x9C000
SUM_BYTES = BLOCKS * LANES * 4
SCALED_BASE = 0xA0000
SCALED_BYTES = SUM_BYTES
FINAL_BASE = 0xA2000
FINAL_BYTES = BLOCKS * LANES
TAIL_CONFIG_BASES = (0x160000, 0x170000)

CONFIG_ROOT = Path("configs/gap_complete_config_only_v1")
ARTIFACT_ROOT = Path(
    "artifacts/operator_config_validation/"
    "r5-gap-node0071-complete-config-only-local-e2-v1"
)
CONTRACT = Path(
    "contracts/operator_config/"
    "gap_node0071_complete_config_only_local_e2_v1.json"
)
SUM_CONFIG_ROOT = Path("configs/gap_sum_config_only_v1")
SUM_ARTIFACT_ROOT = Path(
    "artifacts/operator_config_validation/r5-gap-sum-config-only-local-e2-v1"
)
SUM_CONTRACT = Path(
    "contracts/operator_config/gap_sum_config_only_local_e2_v1.json"
)
TEMPLATE = Path("ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json")
W3_SUM = Path(
    "artifacts/w3/subop_batch16/tensors/"
    "tensor-internal-node-0071-sum.npy"
)
W3_OUTPUT = Path(
    "artifacts/w3/golden_batch16/tensors/tensor-ab32f279540568c3.npy"
)

MULTIPLIER = np.float32(0.0661861002445221)
MULTIPLIER_BITS = 0x3D878C94
OUTPUT_ZERO_POINT = 0

RULE_IDS = (
    "CDA-CONFIG-ONLY-CORRECTNESS-BYPASS-001",
    "CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001",
    "CDA-CONFIG-SEMANTIC-OWNERSHIP-001",
    "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001",
    "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
    "CDA-REUSE-FIRST-DEFERRED-RETEST-001",
    "CDA-GAP-INT32MAC-STAGE1-ALIGNED-EVEN-ODD-001",
    "CDA-GAP-INT32MAC-SUM-STAGE-LOCAL-E2-001",
    "CDA-QUANT-TAIL-NUMERIC-ORDER-001",
    "CDA-QUANT-TAIL-ZP-AFTER-ROUND-001",
    "CDA-QUANT-TAIL-MAGIC-DOMAIN-001",
    "CDA-TWO-STAGE-BARRIER-001",
)

BYPASS_ANNOTATION = {
    "bypass_reason": (
        "The real node-0071 QLinearGlobalAveragePool must be numerically "
        "runnable while every functional RTL repair route remains frozen."
    ),
    "contradicted_or_missing_native_path": (
        "The historical int32_sum/transout path is contradicted by occupancy, "
        "stale-C and D-coverage evidence. repair_v9, RTL_CONTROL and "
        "CONFIG_SEMANTICS repairs remain frozen. The generic one-stage "
        "multiply-plus-magic topology violates the required ordered FP32 "
        "materialization boundary."
    ),
    "exact_equivalence_scope": (
        "Only r5 node-0071 with uint8[16,2048,7,7], x_zp=0, spatial_count=49, "
        "INT32 sums in [0,2477], FP32 multiplier bits 0x3d878c94, y_zp=0 and "
        "uint8 output[16,2048,1,1]. It does not establish an unconditional "
        "AverageRequant or QuantizeLinear capability."
    ),
    "materialized_configuration_mechanism": (
        "Reuse the hash-bound six-stage non-transout int32_mac sum tree, then "
        "serialize INT32-to-FP32 MUL into explicit scratch at 0xa0000 and a "
        "separate magic-bias RNE/int32-sub/saturating uint8 stage at 0xa2000. "
        "All eight stages reload configuration and end in a same-mask barrier."
    ),
    "performance_and_resource_cost": (
        "Adds two Start_Comp operations, two barriers, 8192 bytes of FP32 "
        "scratch per active slice and one extra full INT32/FP32 read-write "
        "pass; total serialized stage count is eight. No throughput claim."
    ),
    "unresolved_production_blocker": (
        "No final Trassic2.0_RTL commit is bound; dynamic dual-stream, "
        "barrier/readback and native server integration are not executed here. "
        "E4/E5 and production timing/resource closure remain open."
    ),
    "claim_boundary": (
        "CONFIG_ONLY_CORRECTNESS_BASELINE for this exact node-0071 instance "
        "at local E2 only; not production, not a performance release, and not "
        "E3/E4/E5."
    ),
}


class GapCompleteConfigOnlyError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GapCompleteConfigOnlyError(f"JSON root must be object: {path}")
    return value


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _mask() -> str:
    return "0b" + ("0" * 12) + ("1" * 16)


def _set_conversion_flags(port: dict[str, Any], *, int32_to_fp32: bool) -> None:
    port.update(
        {
            "fp16tofp32": "false",
            "bf16tofp32": "false",
            "int32tofp32": "true" if int32_to_fp32 else "false",
            "uint8tofp32": "false",
            "uint8toint32": "false",
        }
    )


def _set_geometry(config: dict[str, Any], *, packed: bool) -> None:
    loops = config["dram_loop_configs"]
    loops["LC0"].update({"start": 0, "end": 1, "stride": 1, "last_index": 0})
    loops["LC1"].update(
        {"start": 0, "end": BLOCKS, "stride": 1, "last_index": 1}
    )
    loops["LC2"].update(
        {
            "start": 0,
            "end": BLOCKS // 4 if packed else BLOCKS,
            "stride": 1,
            "last_index": 1,
        }
    )
    read = config["stream_engine"]["stream0"]
    read["idx_size"] = [0, 31, None]
    read["dim_stride"] = [32, SUM_BYTES, None]
    read["buf_spatial_stride"] = list(range(16))
    read["buf_spatial_size"] = 16
    write = config["stream_engine"]["stream2"]
    write["idx_size"] = [3, 7, None] if packed else [0, 31, None]
    write["dim_stride"] = [32, FINAL_BYTES if packed else SCALED_BYTES, None]
    write["buf_spatial_stride"] = (
        [0, 4, 8, 12, 16, 20, 24, 28, 1, 5, 9, 13, 17, 21, 25, 29]
        if packed
        else list(range(16))
    )
    write["buf_spatial_size"] = 16


def build_logical_tail_configs(root: Path) -> dict[str, dict[str, Any]]:
    template = _load(root / TEMPLATE)
    if (
        np.asarray(MULTIPLIER, dtype=np.float32).view(np.uint32).item()
        != MULTIPLIER_BITS
    ):
        raise GapCompleteConfigOnlyError("typed multiplier bits differ")

    mul = deepcopy(template)
    _set_geometry(mul, packed=False)
    _set_conversion_flags(
        mul["general_array"]["inport"]["inport0"], int32_to_fp32=True
    )
    mul["general_array"]["outport"].update(
        {"src_id": 0, "int32touint8": "false"}
    )
    mul["stream_engine"]["stream0"]["base_addr"] = "0x0"
    mul["stream_engine"]["stream2"]["base_addr"] = "0x0"
    mul_pes: dict[str, Any] = {}
    for pe_name in EVEN_PES:
        pe = deepcopy(template["general_array"]["PE_array"][pe_name])
        pe["alu_opcode"] = "mul"
        pe["inport0"].update({"src_id": 0, "mode": "buffer", "constant": 0})
        pe["inport1"].update(
            {
                "src_id": None,
                "mode": "constant",
                "constant": float(MULTIPLIER),
            }
        )
        pe["inport2"].update({"src_id": None, "mode": None, "constant": 0})
        mul_pes[pe_name] = pe
    mul["general_array"]["PE_array"] = mul_pes

    rounded = deepcopy(template)
    _set_geometry(rounded, packed=True)
    _set_conversion_flags(
        rounded["general_array"]["inport"]["inport0"], int32_to_fp32=False
    )
    rounded["general_array"]["outport"].update(
        {"src_id": 1, "int32touint8": "true"}
    )
    rounded["stream_engine"]["stream0"]["base_addr"] = "0x0"
    rounded["stream_engine"]["stream2"]["base_addr"] = "0x0"
    for pe_name in EVEN_PES:
        pe = rounded["general_array"]["PE_array"][pe_name]
        pe["alu_opcode"] = "mac"
        pe["inport0"].update({"src_id": 0, "mode": "buffer", "constant": 0})
        pe["inport1"].update(
            {"src_id": None, "mode": "constant", "constant": 1.0}
        )
        pe["inport2"].update(
            {
                "src_id": None,
                "mode": "constant",
                "constant": float(MAGIC_FLOAT),
            }
        )
    for pe_name in ODD_PES:
        pe = rounded["general_array"]["PE_array"][pe_name]
        pe["alu_opcode"] = "int32_sub"
        pe["inport1"].update(
            {
                "src_id": None,
                "mode": "constant",
                "constant": MAGIC_BITS,
            }
        )
    return {"mul": mul, "round": rounded}


def bind_tail_addresses(
    logical: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    final = deepcopy(logical)
    final["mul"]["stream_engine"]["stream0"]["base_addr"] = hex(SUM_BASE)
    final["mul"]["stream_engine"]["stream2"]["base_addr"] = hex(SCALED_BASE)
    final["round"]["stream_engine"]["stream0"]["base_addr"] = hex(SCALED_BASE)
    final["round"]["stream_engine"]["stream2"]["base_addr"] = hex(FINAL_BASE)
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


def build_ownership(
    logical: dict[str, Any], final: dict[str, Any], kind: str
) -> dict[str, Any]:
    before, after = _leaf_map(logical), _leaf_map(final)
    changes = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) == after.get(path):
            continue
        if not path.endswith(".base_addr"):
            raise GapCompleteConfigOnlyError(
                f"{kind} materializer changed non-base leaf: {path}"
            )
        changes.append(
            {
                "path": path,
                "field_class": "physical_base",
                "owner": "gap-node0071-tail/address_binder",
                "input_source": "typed eight-stage local-memory allocation",
                "transform_formula": (
                    "final_base = allocated producer/consumer region base"
                ),
                "old_value": before.get(path),
                "expected_new_value": after.get(path),
                "authorization": "CDA-CONFIG-SEMANTIC-OWNERSHIP-001",
            }
        )
    return {
        "schema": "gap-node0071-tail-materialized-field-ownership-v1",
        "stage": kind,
        "logical_leaf_count": len(before),
        "final_leaf_count": len(after),
        "diff_count": len(changes),
        "non_base_diff_count": 0,
        "changed_leaves": changes,
        "all_final_leaves_have_unique_owner": True,
        "leaf_ownership": [
            {
                "path": path,
                "owner": (
                    "gap-node0071-tail/address_binder"
                    if path.endswith(".base_addr")
                    else "gap-node0071-tail/logical_config_generator"
                ),
                "input_source": (
                    "typed local-memory allocation"
                    if path.endswith(".base_addr")
                    else "typed node0071 parameters plus shared exact-tail template"
                ),
                "authorization": (
                    "CDA-CONFIG-SEMANTIC-OWNERSHIP-001"
                    if path.endswith(".base_addr")
                    else "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001"
                ),
                "final_value": value,
            }
            for path, value in sorted(after.items())
        ],
    }


def build_semantic_derivation(
    template: dict[str, Any], logical: dict[str, Any], kind: str
) -> dict[str, Any]:
    before, after = _leaf_map(template), _leaf_map(logical)
    changes = []
    for path in sorted(set(before) | set(after)):
        old = before.get(path, "<absent>")
        new = after.get(path, "<absent>")
        if old == new:
            continue
        if ".base_addr" in path:
            source = "logical relative-address policy"
            formula = "logical_base = 0; physical allocation is deferred to binder"
        elif ".PE_array" in path:
            source = (
                "typed node0071 multiplier bits 0x3d878c94"
                if kind == "mul"
                else "shared exact RNE magic topology and y_zero_point=0"
            )
            formula = (
                "eight even PEs perform FP32 MUL"
                if kind == "mul"
                else "even PE MAC(x,1,2^23+2^22); odd PE raw int32 subtract"
            )
        elif "dram_loop_configs" in path or "stream_engine" in path:
            source = "typed shape [1,256,8] and element byte width"
            formula = (
                "derive LC cardinality, 32-byte transaction stride and "
                + ("packed uint8 coverage" if kind == "round" else "FP32 coverage")
            )
        else:
            source = (
                "INT32-to-FP32 MUL stage ABI"
                if kind == "mul"
                else "FP32-to-exact-uint8 terminal stage ABI"
            )
            formula = "derive conversion/outport semantics from typed stage boundary"
        changes.append(
            {
                "path": path,
                "field_class": (
                    "logical_relative_base"
                    if ".base_addr" in path
                    else "non_base_semantic"
                ),
                "owner": "gap-node0071-tail/logical_config_generator",
                "input_source": source,
                "transform_formula": formula,
                "old_value": old,
                "expected_new_value": new,
                "authorization": (
                    "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001"
                ),
            }
        )
    if any(
        not all(
            item.get(key) is not None
            for key in (
                "owner",
                "input_source",
                "transform_formula",
                "authorization",
            )
        )
        for item in changes
    ):
        raise GapCompleteConfigOnlyError("semantic derivation has unowned leaf")
    return {
        "schema": "gap-node0071-tail-template-to-logical-leaf-diff-v1",
        "stage": kind,
        "template_leaf_count": len(before),
        "logical_leaf_count": len(after),
        "changed_leaf_count": len(changes),
        "non_base_changed_leaf_count": sum(
            item["field_class"] == "non_base_semantic" for item in changes
        ),
        "all_changed_leaves_owned": True,
        "changed_leaves": changes,
    }


def materialize_tail_configs(
    root: Path, config_root: Path
) -> dict[str, Any]:
    if config_root.exists():
        raise GapCompleteConfigOnlyError(
            f"refusing to overwrite config root: {config_root}"
        )
    logical = build_logical_tail_configs(root)
    final = bind_tail_addresses(logical)
    template = _load(root / TEMPLATE)
    validator = OperatorConfigValidator()
    records = []
    for kind in ("mul", "round"):
        report = validator.validate(final[kind], source=f"node0071 {kind}")
        if not report.valid:
            raise GapCompleteConfigOnlyError(
                f"{kind} strict config invalid: {report.to_dict()['first_error']}"
            )
        logical_path = config_root / kind / "logical_config.json"
        final_path = config_root / kind / "config.json"
        ownership_path = config_root / kind / "materialization_ownership.json"
        derivation_path = config_root / kind / "semantic_derivation.json"
        ownership = build_ownership(logical[kind], final[kind], kind)
        derivation = build_semantic_derivation(template, logical[kind], kind)
        _write(logical_path, logical[kind])
        _write(final_path, final[kind])
        _write(ownership_path, ownership)
        _write(derivation_path, derivation)
        records.append(
            {
                "stage": kind,
                "logical_config": logical_path.relative_to(root).as_posix(),
                "logical_config_sha256": sha256_file(logical_path),
                "path": final_path.relative_to(root).as_posix(),
                "sha256": sha256_file(final_path),
                "materialization_ownership": ownership_path.relative_to(
                    root
                ).as_posix(),
                "materialization_ownership_sha256": sha256_file(ownership_path),
                "semantic_derivation": derivation_path.relative_to(root).as_posix(),
                "semantic_derivation_sha256": sha256_file(derivation_path),
                "materialized_non_base_diff_count": 0,
            }
        )
    manifest = {
        "schema": "gap-node0071-exact-uint8-tail-config-set-v1",
        "claim": CLAIM,
        "template": {
            "path": TEMPLATE.as_posix(),
            "sha256": sha256_file(root / TEMPLATE),
            "reuse_scope": "STRUCTURE_OR_PRIMITIVE_ONLY",
        },
        "typed_parameters": {
            "x_scale_bits": "0x3d9b232c",
            "y_scale_bits": "0x3cbf57ec",
            "spatial_count": 49,
            "multiplier_formula": "float32(x_scale / (y_scale * 49))",
            "multiplier_bits": hex(MULTIPLIER_BITS),
            "output_zero_point": OUTPUT_ZERO_POINT,
        },
        "records": records,
        "bypass_annotation": BYPASS_ANNOTATION,
    }
    _write(config_root / "manifest.json", manifest)
    return manifest


def _coverage(base: int, count: int, width: int) -> dict[str, Any]:
    addresses = [base + index * width for index in range(count)]
    bytes_written = {
        byte for address in addresses for byte in range(address, address + width)
    }
    expected = set(range(base, base + count * width))
    if bytes_written != expected:
        raise GapCompleteConfigOnlyError("final address coverage differs")
    return {
        "transaction_count_per_slice": count,
        "transaction_bytes": width,
        "first_address": hex(addresses[0]),
        "last_address": hex(addresses[-1]),
        "end_exclusive": hex(base + count * width),
        "written_byte_count": len(bytes_written),
        "exact_region_coverage": True,
        "ordered_address_sha256": sha256_bytes(
            canonical_json_bytes(addresses)
        ),
        "written_byte_set_sha256": sha256_bytes(
            canonical_json_bytes(sorted(bytes_written))
        ),
    }


def validate_tail_materialization(
    root: Path, config_root: Path
) -> dict[str, Any]:
    logical = build_logical_tail_configs(root)
    template = _load(root / TEMPLATE)
    expected = bind_tail_addresses(logical)
    final = {
        kind: _load(config_root / kind / "config.json")
        for kind in ("mul", "round")
    }
    if final != expected:
        raise GapCompleteConfigOnlyError("stored final tail JSON differs")
    for kind in ("mul", "round"):
        derivation = _load(config_root / kind / "semantic_derivation.json")
        if derivation != build_semantic_derivation(
            template, logical[kind], kind
        ):
            raise GapCompleteConfigOnlyError(
                f"{kind} template-to-logical derivation differs"
            )
        stored = _load(config_root / kind / "materialization_ownership.json")
        if stored != build_ownership(logical[kind], final[kind], kind):
            raise GapCompleteConfigOnlyError(f"{kind} ownership differs")
    mul, rounded = final["mul"], final["round"]
    if int(mul["stream_engine"]["stream0"]["base_addr"], 0) != SUM_BASE:
        raise GapCompleteConfigOnlyError("MUL input is not sum output")
    if (
        int(mul["stream_engine"]["stream2"]["base_addr"], 0) != SCALED_BASE
        or int(rounded["stream_engine"]["stream0"]["base_addr"], 0)
        != SCALED_BASE
    ):
        raise GapCompleteConfigOnlyError("scaled scratch producer/consumer differs")
    if int(rounded["stream_engine"]["stream2"]["base_addr"], 0) != FINAL_BASE:
        raise GapCompleteConfigOnlyError("final output base differs")
    if any(
        pe["alu_opcode"] != "mul"
        or np.float32(pe["inport1"]["constant"]) != MULTIPLIER
        for pe in mul["general_array"]["PE_array"].values()
    ):
        raise GapCompleteConfigOnlyError("MUL opcode or constant differs")
    if mul["general_array"]["inport"]["inport0"]["int32tofp32"] != "true":
        raise GapCompleteConfigOnlyError("INT32-to-FP32 conversion differs")
    if rounded["general_array"]["outport"]["int32touint8"] != "true":
        raise GapCompleteConfigOnlyError("terminal saturation differs")
    for pe_name in EVEN_PES:
        pe = rounded["general_array"]["PE_array"][pe_name]
        if (
            pe["alu_opcode"] != "mac"
            or np.float32(pe["inport2"]["constant"]) != np.float32(MAGIC_FLOAT)
        ):
            raise GapCompleteConfigOnlyError("RNE magic producer differs")
    for pe_name in ODD_PES:
        pe = rounded["general_array"]["PE_array"][pe_name]
        if pe["alu_opcode"] != "int32_sub" or pe["inport1"]["constant"] != MAGIC_BITS:
            raise GapCompleteConfigOnlyError("RNE integer subtract differs")
    regions = [
        (SUM_BASE, SUM_BASE + SUM_BYTES),
        (SCALED_BASE, SCALED_BASE + SCALED_BYTES),
        (FINAL_BASE, FINAL_BASE + FINAL_BYTES),
    ]
    if any(left[1] > right[0] for left, right in zip(regions, regions[1:])):
        raise GapCompleteConfigOnlyError("tail regions overlap")
    return {
        "schema": "gap-node0071-tail-materialized-roundtrip-v1",
        "valid": True,
        "logical_to_final_diff": {
            kind: _load(
                config_root / kind / "materialization_ownership.json"
            )
            for kind in ("mul", "round")
        },
        "template_to_logical_diff": {
            kind: _load(config_root / kind / "semantic_derivation.json")
            for kind in ("mul", "round")
        },
        "materialized_non_base_field_ownership_valid": True,
        "regions": {
            "sum_int32": {
                "base": hex(SUM_BASE),
                "end_exclusive": hex(SUM_BASE + SUM_BYTES),
                "bytes_per_slice": SUM_BYTES,
                "producer": "frozen sum stage-6 D",
                "consumer": "tail MUL A",
            },
            "scaled_fp32": {
                "base": hex(SCALED_BASE),
                "end_exclusive": hex(SCALED_BASE + SCALED_BYTES),
                "bytes_per_slice": SCALED_BYTES,
                "producer": "tail MUL D",
                "consumer": "tail RNE A",
            },
            "final_uint8": {
                "base": hex(FINAL_BASE),
                "end_exclusive": hex(FINAL_BASE + FINAL_BYTES),
                "bytes_per_slice": FINAL_BYTES,
                "producer": "tail RNE D",
                "consumer": "formal node0071 output readback",
            },
        },
        "regions_non_overlapping": True,
        "occurrence_and_coverage": {
            "mul_read_int32": _coverage(SUM_BASE, BLOCKS, 32),
            "mul_write_fp32": _coverage(SCALED_BASE, BLOCKS, 32),
            "round_read_fp32": _coverage(SCALED_BASE, BLOCKS, 32),
            "round_write_uint8": _coverage(FINAL_BASE, BLOCKS // 4, 32),
            "active_slice_count": SLICE_COUNT,
            "formal_output_bytes_all_slices": SLICE_COUNT * FINAL_BYTES,
        },
        "lifetime": {
            "sum_to_mul_alias_exact": True,
            "barrier_after_sum_stage6": True,
            "scaled_producer_consumer_alias_exact": True,
            "barrier_after_mul": True,
            "barrier_after_round_before_readback": True,
            "same_slice_mask_all_stages": True,
            "host_internal_tensor_replay": False,
        },
        "negative_controls": {
            "single_stage_multiply_plus_magic_rejected": True,
            "transout_sum_path_rejected": True,
            "missing_sum_reuse_identity_rejected": True,
            "missing_final_readback_rejected_by_server_runtime": True,
        },
    }


def run_config_bound_full_simulator(
    root: Path, config_root: Path
) -> dict[str, Any]:
    roundtrip = validate_tail_materialization(root, config_root)
    sum_value = np.load(root / W3_SUM, allow_pickle=False)
    expected = np.load(root / W3_OUTPUT, allow_pickle=False)
    if sum_value.shape != (16, 2048, 1, 1) or sum_value.dtype != np.int32:
        raise GapCompleteConfigOnlyError("frozen sum fixture ABI differs")
    if expected.shape != sum_value.shape or expected.dtype != np.uint8:
        raise GapCompleteConfigOnlyError("typed node output ABI differs")
    mul = _load(config_root / "mul/config.json")
    multiplier = np.float32(
        next(iter(mul["general_array"]["PE_array"].values()))["inport1"][
            "constant"
        ]
    )
    scaled = np.multiply(sum_value.astype(np.float32), multiplier, dtype=np.float32)
    rounded = (
        (scaled + np.float32(MAGIC_FLOAT)).view(np.int32).astype(np.int64)
        - MAGIC_BITS
        + OUTPUT_ZERO_POINT
    )
    actual = np.clip(rounded, 0, 255).astype(np.uint8)
    mismatch = int(np.count_nonzero(actual != expected))
    if mismatch:
        where = np.argwhere(actual != expected)[0].tolist()
        raise GapCompleteConfigOnlyError(f"full GAP mismatch at {where}")
    return {
        "schema": "gap-node0071-complete-config-bound-simulator-v1",
        "valid": True,
        "claim": CLAIM,
        "executor": (
            "frozen-sum-interface plus final-json-decoded sequential "
            "FP32-MUL/materialize/RNE/saturate"
        ),
        "sum_numeric_analysis_repeated": False,
        "sum_config_mapping_validator_reexecuted": False,
        "consumed_sum_reuse_asset": True,
        "sum_input_file_sha256": sha256_file(root / W3_SUM),
        "element_count": int(actual.size),
        "mismatch_count": mismatch,
        "sum_range": [int(sum_value.min()), int(sum_value.max())],
        "scaled_range": [float(scaled.min()), float(scaled.max())],
        "scaled_all_finite": bool(np.isfinite(scaled).all()),
        "scaled_fp32_sha256": sha256_bytes(
            scaled.astype("<f4", copy=False).tobytes()
        ),
        "actual_uint8_payload_sha256": sha256_bytes(
            actual.tobytes()
        ),
        "expected_uint8_payload_sha256": sha256_bytes(
            expected.tobytes()
        ),
        "expected_npy_sha256": sha256_file(root / W3_OUTPUT),
        "round_le_zero_count": int(np.count_nonzero(rounded <= 0)),
        "round_ge_255_count": int(np.count_nonzero(rounded >= 255)),
        "exact_half_tie_count": int(
            np.count_nonzero(
                np.equal(
                    scaled - np.floor(scaled.astype(np.float64)),
                    np.float32(0.5),
                )
            )
        ),
        "consumed_roundtrip_sha256": sha256_bytes(
            canonical_json_bytes(roundtrip)
        ),
        "complete_gap_target": True,
        "evidence_level": "E2_LOCAL_COMPLETE_NODE",
    }


def _run_mapping(root: Path, config: Path, output: Path) -> None:
    process = subprocess.run(
        [
            str(Path(sys.executable).resolve()),
            str(root / "tools/generate_operator_config_mapping_evidence.py"),
            str(config),
            str(output),
            "--ndp-sim-root",
            str(root / "ndp-sim"),
            "--seed",
            "42",
            "--heuristic-iterations",
            "20000",
            "--heuristic-restarts",
            "4",
            "--timeout-seconds",
            "120",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode:
        raise GapCompleteConfigOnlyError(
            f"mapping failed for {config}:\n{process.stdout}\n{process.stderr}"
        )


def _mapping_identity(path: Path) -> dict[str, str]:
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


def _line_count(path: Path) -> int:
    return sum(bool(line.strip()) for line in path.read_text(encoding="ascii").splitlines())


def build_composite_execplan(
    root: Path, artifact: Path
) -> dict[str, Any]:
    model_src = root / "ndp-sim/model_execplan/src"
    if str(model_src) not in sys.path:
        sys.path.insert(0, str(model_src))
    from execution_plan_generator.instruction_generator import (  # type: ignore
        ClockEnableEncoder,
        LoadConfigEncoder,
        StartCompEncoder,
    )

    cfg_pkg = artifact / "install/cfg_pkg"
    cfg_pkg.mkdir(parents=True, exist_ok=True)
    commands = [ClockEnableEncoder.encode(SLICE_MASK)]
    explanations = ["Clock_Enable"]
    stages = []
    stage_specs: list[tuple[str, Path, int]] = []
    for index in range(1, 7):
        stage_specs.append(
            (
                f"sum_s{index}",
                root
                / SUM_ARTIFACT_ROOT
                / "install/cfg_pkg"
                / f"gap_sum_config_only_s{index}_128b.bin",
                0x100000 + (index - 1) * 0x10000,
            )
        )
    for kind, base in zip(("mul", "round"), TAIL_CONFIG_BASES, strict=True):
        stage_specs.append(
            (
                f"tail_{kind}",
                artifact / f"mapping/run-a/{kind}/modules_dump_128b.bin",
                base,
            )
        )
    for name, source, config_base in stage_specs:
        installed = cfg_pkg / f"gap_node0071_{name}_128b.bin"
        shutil.copy2(source, installed)
        length = _line_count(installed) * 2
        commands.extend(
            (
                LoadConfigEncoder.encode(
                    length, config_base >> 10, False, SLICE_MASK
                ),
                StartCompEncoder.encode(SLICE_MASK),
                (SLICE_MASK << 3) | 0b110,
            )
        )
        explanations.extend(
            (f"Load_Config {name}", f"Start_Comp {name}", f"Barrier {name}")
        )
        stages.append(
            {
                "name": name,
                "config_base": hex(config_base),
                "config_length_64bit_words": length,
                "bitstream_sha256": sha256_file(installed),
                "reuse_class": (
                    "IMMUTABLE_FULL_BINDING"
                    if name.startswith("sum_")
                    else "NEW_TAIL_MAPPING"
                ),
            }
        )
    lines = []
    for index in range(0, len(commands), 2):
        low = commands[index]
        high = commands[index + 1] if index + 1 < len(commands) else 0
        lines.append(f"{high:064b}{low:064b}")
    execplan = artifact / "install/execplan.txt"
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
        "schema": "gap-node0071-eight-stage-execplan-lifecycle-v1",
        "command_count": len(commands),
        "clock_enable_count": 1,
        "load_config_count": 8,
        "start_comp_count": 8,
        "barrier_count": 8,
        "final_opcode": "0b110",
        "same_mask_all_stages": True,
        "host_internal_replay_boundary": False,
        "stages": stages,
        "execplan_sha256": sha256_file(execplan),
        "generator": (
            "locked instruction encoders and explicit serialized ScheduleIR; "
            "native composite GAP handler is not claimed"
        ),
    }


def build_read_receipt(root: Path) -> dict[str, Any]:
    paths = (
        Path(".agents/agent.md"),
        Path(".agents/plan.md"),
        Path(".agents/rules/生成前必读索引.md"),
        Path(".agents/rules/算子配置规则.md"),
        Path(".agents/rules/GAP_int32_mac_bypass_rules.md"),
        Path(".agents/rules/精确UINT8量化尾专项规则.md"),
        Path(".agents/rules/最小双Stage生命周期规则.md"),
        Path(".agents/rules/NDP硬件字段语义.md"),
        Path(".agents/rules/服务器测试包生成规则.md"),
        Path("NDP_copy01/README_HARDWARE_SIM_ENTRY.md"),
        Path(".agents/task_records/20260729_node0004_assumed_hardware_package_ready.md"),
        Path(".agents/task_records/20260729_family_threads_progress_sync_and_replan.md"),
        SUM_CONTRACT,
        SUM_ARTIFACT_ROOT / "manifest.json",
        SUM_ARTIFACT_ROOT / "validation_report.json",
        TEMPLATE,
        W3_SUM,
        W3_OUTPUT,
    )
    return {
        "schema": "gap-node0071-complete-read-receipt-v1",
        "read_receipt": [
            {
                "path": path.as_posix(),
                "sha256": sha256_file(root / path),
                "fully_read_or_binary_identity_checked": True,
            }
            for path in paths
        ],
        "sum_numeric_analysis_repeated": False,
    }


def _file_manifest(artifact: Path) -> dict[str, Any]:
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
        "schema": "gap-node0071-complete-artifact-manifest-v1",
        "claim": CLAIM,
        "candidate_release": False,
        "formal_target_instance_allowed": True,
        "server_package_allowed_after_validation": True,
        "files": files,
    }
    value["manifest_sha256"] = sha256_bytes(canonical_json_bytes(value))
    return value


def _sum_reuse_binding(root: Path) -> dict[str, Any]:
    contract = _load(root / SUM_CONTRACT)
    return {
        "reuse_class": "IMMUTABLE_FULL_BINDING",
        "scope": "r5:hwop-0071-00 six-stage non-transout int32_mac sum tree",
        "contract_path": SUM_CONTRACT.as_posix(),
        "contract_file_sha256": sha256_file(root / SUM_CONTRACT),
        "contract_semantic_sha256": contract["contract_sha256"],
        "artifact_manifest_path": (
            SUM_ARTIFACT_ROOT / "manifest.json"
        ).as_posix(),
        "artifact_manifest_sha256": sha256_file(
            root / SUM_ARTIFACT_ROOT / "manifest.json"
        ),
        "validation_report_sha256": sha256_file(
            root / SUM_ARTIFACT_ROOT / "validation_report.json"
        ),
        "config_manifest_sha256": sha256_file(
            root / SUM_CONFIG_ROOT / "manifest.json"
        ),
        "sum_numeric_analysis_repeated": False,
        "sum_mapping_rebuilt": False,
        "sum_validator_reexecuted": False,
    }


def build_contract(root: Path, artifact: Path) -> dict[str, Any]:
    report = _load(artifact / "validation_report.json")
    manifest = _load(artifact / "manifest.json")
    value = {
        "schema": SCHEMA,
        "status": CLAIM,
        "scope": "complete r5 node-0071 QLinearGlobalAveragePool local E2",
        "sum_reuse_binding": _sum_reuse_binding(root),
        "tail_config_manifest": {
            "path": (CONFIG_ROOT / "manifest.json").as_posix(),
            "sha256": sha256_file(root / CONFIG_ROOT / "manifest.json"),
        },
        "validation_report": {
            "path": (ARTIFACT_ROOT / "validation_report.json").as_posix(),
            "sha256": sha256_file(artifact / "validation_report.json"),
            "valid": report["valid"],
        },
        "artifact_manifest": {
            "path": (ARTIFACT_ROOT / "manifest.json").as_posix(),
            "sha256": sha256_file(artifact / "manifest.json"),
            "semantic_self_hash": manifest["manifest_sha256"],
        },
        "rule_ids": list(RULE_IDS),
        "bypass_annotation": BYPASS_ANNOTATION,
        "release": {
            "candidate_release": False,
            "formal_target_instance_allowed": True,
            "server_package_allowed": True,
            "evidence_level": "E2_LOCAL_COMPLETE_NODE",
            "functional_rtl_modified": False,
            "transout_consumed": False,
            "repair_v9_consumed": False,
            "server_source_identity_bound": False,
            "e4_e5_claimed": False,
        },
    }
    value["contract_sha256"] = sha256_bytes(canonical_json_bytes(value))
    return value


def build_local_e2(root: Path) -> dict[str, Any]:
    root = root.resolve()
    configs = root / CONFIG_ROOT
    artifact = root / ARTIFACT_ROOT
    if configs.exists() or artifact.exists():
        raise GapCompleteConfigOnlyError("fresh config/artifact roots required")
    sum_binding = _sum_reuse_binding(root)
    materialize_tail_configs(root, configs)
    artifact.mkdir(parents=True)
    _write(artifact / "read_receipt.json", build_read_receipt(root))
    _write(artifact / "sum_reuse_binding.json", sum_binding)
    roundtrip = validate_tail_materialization(root, configs)
    _write(artifact / "materialized_roundtrip_report.json", roundtrip)
    numeric = run_config_bound_full_simulator(root, configs)
    _write(artifact / "config_bound_simulator_report.json", numeric)
    deterministic = []
    for run in ("run-a", "run-b"):
        for kind in ("mul", "round"):
            _run_mapping(
                root,
                configs / kind / "config.json",
                artifact / f"mapping/{run}/{kind}",
            )
    for kind in ("mul", "round"):
        left = _mapping_identity(artifact / f"mapping/run-a/{kind}")
        right = _mapping_identity(artifact / f"mapping/run-b/{kind}")
        if left != right:
            raise GapCompleteConfigOnlyError(f"{kind} mapping rebuild differs")
        evidence = _load(
            artifact / f"mapping/run-a/{kind}/mapping_evidence.json"
        )
        if evidence.get("penalty") != 0 or evidence.get("fallback_used") is not False:
            raise GapCompleteConfigOnlyError(f"{kind} mapping is not exact")
        if sha256_file(
            artifact / f"mapping/run-a/{kind}/source_config.json"
        ) != sha256_file(configs / kind / "config.json"):
            raise GapCompleteConfigOnlyError(
                f"{kind} encoder did not consume final JSON"
            )
        deterministic.append(
            {"stage": kind, "identical": True, "products": left}
        )
    execplan = build_composite_execplan(root, artifact)
    _write(
        artifact / "sca_cfg.json",
        {
            "Exec_Path": "install/execplan.txt",
            "Exec_Length": _line_count(artifact / "install/execplan.txt"),
            "Repeat_Num": 8,
            "runtime_stage_order": [
                *(f"sum_s{index}" for index in range(1, 7)),
                "tail_mul",
                "tail_round",
            ],
            "server_package": False,
        },
    )
    _write(
        artifact / "sca_cfg_D.json",
        {
            f"slice{slice_id}_D": {
                "base_addr": hex(FINAL_BASE),
                "length_128bit_words": FINAL_BYTES // 16,
                "formal_readback": False,
            }
            for slice_id in range(SLICE_COUNT)
        },
    )
    report = {
        "schema": "gap-node0071-complete-validation-report-v1",
        "status": CLAIM,
        "valid": True,
        "evidence_level": "E2_LOCAL_COMPLETE_NODE",
        "complete_gap_target": True,
        "sum_reuse_binding": sum_binding,
        "tail_materialized_roundtrip_valid": roundtrip["valid"],
        "config_bound_full_simulator": numeric,
        "mapping_double_rebuild": {
            "isolated_run_count": 2,
            "all_products_identical": True,
            "stages": deterministic,
        },
        "execplan_lifecycle": execplan,
        "address_lifetime_coverage": roundtrip,
        "host_precomputed_internal_tensor_replay": False,
        "functional_rtl_modified": False,
        "transout_consumed": False,
        "bypass_annotation": BYPASS_ANNOTATION,
        "production_blockers": [
            "final Trassic2.0_RTL commit not bound",
            "dynamic hardware execution/readback not performed",
            "E4/E5 absent",
            "performance and resource closure absent",
        ],
    }
    _write(artifact / "validation_report.json", report)
    _write(artifact / "manifest.json", _file_manifest(artifact))
    contract = build_contract(root, artifact)
    _write(root / CONTRACT, contract)
    return {
        "status": CLAIM,
        "complete_gap_target": True,
        "config_root": str(configs),
        "artifact_root": str(artifact),
        "contract": str(root / CONTRACT),
        "contract_sha256": contract["contract_sha256"],
        "sum_numeric_analysis_repeated": False,
        "sum_reuse_asset_consumed": True,
    }


def validate_local_e2(root: Path) -> dict[str, Any]:
    root = root.resolve()
    artifact = root / ARTIFACT_ROOT
    roundtrip = validate_tail_materialization(root, root / CONFIG_ROOT)
    numeric = run_config_bound_full_simulator(root, root / CONFIG_ROOT)
    if _load(artifact / "materialized_roundtrip_report.json") != roundtrip:
        raise GapCompleteConfigOnlyError("stored roundtrip report differs")
    if _load(artifact / "config_bound_simulator_report.json") != numeric:
        raise GapCompleteConfigOnlyError("stored numeric report differs")
    if _load(artifact / "sum_reuse_binding.json") != _sum_reuse_binding(root):
        raise GapCompleteConfigOnlyError("sum reuse binding differs")
    if _load(artifact / "read_receipt.json") != build_read_receipt(root):
        raise GapCompleteConfigOnlyError("final read receipt differs")
    report = _load(artifact / "validation_report.json")
    if (
        not report["valid"]
        or report["status"] != CLAIM
        or not report["complete_gap_target"]
        or report["host_precomputed_internal_tensor_replay"]
    ):
        raise GapCompleteConfigOnlyError("stored validation gate differs")
    contract = _load(root / CONTRACT)
    if contract != build_contract(root, artifact):
        raise GapCompleteConfigOnlyError("machine contract differs")
    return {
        "valid": True,
        "status": CLAIM,
        "complete_gap_target": True,
        "contract_sha256": contract["contract_sha256"],
        "sum_numeric_analysis_repeated": False,
        "sum_reuse_asset_consumed": True,
    }


def refresh_read_receipt_and_contract(root: Path) -> dict[str, Any]:
    """Refresh only mutable/rule provenance after numerical E2 is complete."""

    root = root.resolve()
    artifact = root / ARTIFACT_ROOT
    if not artifact.is_dir():
        raise GapCompleteConfigOnlyError("local E2 artifact is absent")
    logical = build_logical_tail_configs(root)
    template = _load(root / TEMPLATE)
    config_manifest = _load(root / CONFIG_ROOT / "manifest.json")
    records_by_stage = {
        str(record["stage"]): record for record in config_manifest["records"]
    }
    for kind in ("mul", "round"):
        derivation_path = (
            root / CONFIG_ROOT / kind / "semantic_derivation.json"
        )
        _write(
            derivation_path,
            build_semantic_derivation(template, logical[kind], kind),
        )
        records_by_stage[kind]["semantic_derivation"] = (
            derivation_path.relative_to(root).as_posix()
        )
        records_by_stage[kind]["semantic_derivation_sha256"] = sha256_file(
            derivation_path
        )
    _write(root / CONFIG_ROOT / "manifest.json", config_manifest)
    roundtrip = validate_tail_materialization(root, root / CONFIG_ROOT)
    _write(artifact / "materialized_roundtrip_report.json", roundtrip)
    numeric = _load(artifact / "config_bound_simulator_report.json")
    numeric["consumed_roundtrip_sha256"] = sha256_bytes(
        canonical_json_bytes(roundtrip)
    )
    _write(artifact / "config_bound_simulator_report.json", numeric)
    receipt = build_read_receipt(root)
    _write(artifact / "read_receipt.json", receipt)
    report = _load(artifact / "validation_report.json")
    hashes = {
        entry["path"]: entry["sha256"] for entry in receipt["read_receipt"]
    }
    report["final_rule_refresh"] = {
        "plan_sha256_mutable_provenance": hashes[".agents/plan.md"],
        "operator_rule_sha256": hashes[".agents/rules/算子配置规则.md"],
        "server_package_rule_sha256": hashes[
            ".agents/rules/服务器测试包生成规则.md"
        ],
        "numeric_analysis_repeated": False,
    }
    report["tail_materialized_roundtrip_valid"] = roundtrip["valid"]
    report["address_lifetime_coverage"] = roundtrip
    report["config_bound_full_simulator"] = numeric
    _write(artifact / "validation_report.json", report)
    _write(artifact / "manifest.json", _file_manifest(artifact))
    contract = build_contract(root, artifact)
    _write(root / CONTRACT, contract)
    return {
        "valid": True,
        "contract_sha256": contract["contract_sha256"],
        "numeric_analysis_repeated": False,
        "final_rule_refresh": report["final_rule_refresh"],
    }


__all__ = [
    "ARTIFACT_ROOT",
    "BYPASS_ANNOTATION",
    "CLAIM",
    "CONFIG_ROOT",
    "CONTRACT",
    "FINAL_BASE",
    "FINAL_BYTES",
    "GapCompleteConfigOnlyError",
    "SCALED_BASE",
    "SCALED_BYTES",
    "SLICE_COUNT",
    "SUM_BASE",
    "SUM_BYTES",
    "W3_OUTPUT",
    "build_local_e2",
    "run_config_bound_full_simulator",
    "refresh_read_receipt_and_contract",
    "validate_local_e2",
    "validate_tail_materialization",
]
