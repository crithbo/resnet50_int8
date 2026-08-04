from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import numpy as np

from .qlinearadd_predesign import (
    _affine_reassociation_counterexamples,
    _qlinearadd_records,
)


SCHEMA = "qlinearadd_stage0_config_only_v1"
CLAIM = "CONFIG_ONLY_CORRECTNESS_BASELINE"
ARENA_BASE = 0x0000_0004_0000_0000
ALIGNMENT = 64
VECTOR_LANES_UINT8_DEQUANT = 16
VECTOR_LANES_FP32_ADD = 4
BYPASS_FIELDS = (
    "bypass_reason",
    "contradicted_or_missing_native_path",
    "exact_equivalence_scope",
    "materialized_configuration_mechanism",
    "performance_and_resource_cost",
    "unresolved_production_blocker",
    "claim_boundary",
)
CURRENT_MATCH_RULES = (
    (
        ".agents/rules/算子配置规则.md",
        "407fc0320d0587c362730c74e9b1d87cbd8e2ab686051173ceacadb6ac31c2cc",
        (
            "CDA-CONFIG-ONLY-CORRECTNESS-BYPASS-001",
            "CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001",
            "CDA-CONFIG-SEMANTIC-OWNERSHIP-001",
            "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001",
            "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
            "CDA-CONFIG-FULL-REBUILD-PROVENANCE-001",
        ),
    ),
    (
        ".agents/rules/生成前必读索引.md",
        "3940dc4d6f6d0b5d52347acd6fe5655281562dc09d4082c298cf70c7dbfb4f19",
        ("QLinearAdd", "Flatten/View"),
    ),
    (
        ".agents/rules/QLinearAdd算子配置规则.md",
        "981afd5aa0a0ee240c8e6c863cbac0c89dc299344554eb893d707cf96fe0b4ee",
        (
            "CDA-QADD-W3-OPERATION-ORDER-001",
            "CDA-QADD-SIX-QPARAM-TYPED-TRANSPORT-001",
            "CDA-QADD-RESIDUAL-BROADCAST-DAG-001",
            "CDA-QADD-STAGE0-THREE-PHYSICAL-STAGES-001",
            "CDA-QADD-BROADCAST-REPLAY-TAIL-ACCOUNTING-001",
            "CDA-QADD-STAGE0-CLAIM-BOUNDARY-001",
            "CDA-QADD-READINESS-LIFETIME-001",
            "CDA-QADD-EXACT-QUANT-TAIL-DEPENDENCY-001",
        ),
    ),
    (
        ".agents/rules/精确UINT8量化尾专项规则.md",
        "5593f9df3bbc5605e9b019b6cc53ee33b0edbeb203d657fdf974cb4b680c2df0",
        (
            "CDA-QUANT-TAIL-NUMERIC-ORDER-001",
            "CDA-QUANT-TAIL-ZP-AFTER-ROUND-001",
            "CDA-QUANT-TAIL-MAGIC-DOMAIN-001",
            "CDA-QUANT-TAIL-CAPABILITY-MATRIX-001",
        ),
    ),
)


class QLinearAddStage0Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QLinearAddStage0Error(f"{path}: expected JSON object")
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _align(value: int, alignment: int = ALIGNMENT) -> int:
    return (value + alignment - 1) // alignment * alignment


def _elements(shape: list[int]) -> int:
    result = 1
    for extent in shape:
        result *= int(extent)
    return result


def _fp32_from_bits(bits: str) -> np.float32:
    return np.float32(struct.unpack("<f", int(bits, 16).to_bytes(4, "little"))[0])


def _negative_zero_bits(zero_point: int) -> str:
    value = np.asarray([-float(zero_point)], dtype=np.float32)
    return f"0x{int(value.view(np.uint32)[0]):08x}"


def _allocation(
    *,
    name: str,
    base: int,
    elements: int,
    shape: list[int],
    producer: str,
    first_consumer: str,
    last_consumer: str,
    release: str,
) -> dict[str, Any]:
    logical_size = elements * 4
    size = _align(logical_size)
    return {
        "name": name,
        "dtype": "float32",
        "shape": shape,
        "elements": elements,
        "base_address": f"0x{base:016x}",
        "logical_size_bytes": logical_size,
        "size_bytes": size,
        "padding_bytes": size - logical_size,
        "end_address_exclusive": f"0x{base + size:016x}",
        "alignment_bytes": ALIGNMENT,
        "alias_allowed": False,
        "lifetime": {
            "producer": producer,
            "first_consumer": first_consumer,
            "last_consumer": last_consumer,
            "release": release,
        },
    }


def _dequant_stage(
    record: dict[str, Any],
    branch: str,
    output_allocation: dict[str, Any],
) -> dict[str, Any]:
    shape = record[f"{branch}_shape"]
    count = _elements(shape)
    qparams = record["qparams"]
    scale = qparams[f"{branch}_scale"]
    zero = qparams[f"{branch}_zero_point"]
    occurrence_count = (
        count + VECTOR_LANES_UINT8_DEQUANT - 1
    ) // VECTOR_LANES_UINT8_DEQUANT
    tail = count % VECTOR_LANES_UINT8_DEQUANT
    return {
        "stage_id": f"{record['hw_op_id']}:{branch.upper()}_DEQUANT",
        "kind": "UINT8_TO_FP32_W3_DEQUANT",
        "input": {
            "tensor_id": record["tensors"][branch],
            "dtype": "uint8",
            "shape": shape,
            "address_binding": "producer_or_initializer_owned",
        },
        "output": {
            "allocation": output_allocation["name"],
            "base_address": output_allocation["base_address"],
            "dtype": "float32",
            "shape": shape,
        },
        "occurrence": {
            "logical_elements": count,
            "vector_lanes": VECTOR_LANES_UINT8_DEQUANT,
            "count": occurrence_count,
            "tail_elements": tail,
            "tail_identity": (
                "inactive lanes masked; no logical output bytes"
                if tail
                else "not-applicable"
            ),
            "terminal_last_index": occurrence_count - 1,
        },
        "final_output_byte_coverage": {
            "formula": "logical_elements * sizeof(float32)",
            "logical_bytes": count * 4,
            "full_transaction_bytes": 64,
            "full_transactions": count // VECTOR_LANES_UINT8_DEQUANT,
            "tail_valid_bytes": tail * 4,
            "unique_written_byte_count": count * 4,
            "physical_region_bytes": output_allocation["size_bytes"],
            "padding_bytes_not_typed_output": output_allocation["padding_bytes"],
        },
        "materialized_leaf_ownership": {
            "input.tensor_id": "typed QLinearAdd request",
            "output.base_address": "QLinearAdd family scratch arena allocator",
            "occurrence.*": "typed shape and 16-lane dequant schedule formula",
            "ga.negative_zero_point_f32_bits": "typed branch zero point",
            "ga.scale_f32_bits": "typed branch scale exact FP32 bits",
            "ga.topology": "authorized Dequant specialty topology",
        },
        "ga": {
            "ingress_conversion": "uint8tofp32",
            "operation_order": [
                "add(input_f32, negative_zero_point_f32)",
                "mul(previous_f32, scale_f32)",
            ],
            "negative_zero_point_f32_bits": _negative_zero_bits(
                int(zero["value"])
            ),
            "scale_f32_bits": scale["float32_bits"],
            "lanes": 4,
            "topology": "PE00/02/20/22 ADD -> PE10/12/30/32 MUL",
            "normal_outbuffer": True,
            "forbidden": [
                "affine x*scale+(-zero_point*scale)",
                "MAC reassociation",
                "template constant 1",
            ],
        },
    }


def _sum_stage(
    record: dict[str, Any],
    a_allocation: dict[str, Any],
    b_allocation: dict[str, Any],
    sum_allocation: dict[str, Any],
) -> dict[str, Any]:
    count = _elements(record["y_shape"])
    broadcast = record["class"] == "broadcast_bias_add"
    b_elements = _elements(record["b_shape"])
    b_replay = {
        "enabled": broadcast,
        "physical_region_elements": b_elements,
        "logical_consumption_elements": count,
        "source_index": (
            "logical_output_index % 1000" if broadcast else "logical_output_index"
        ),
        "batch_replay_count": 16 if broadcast else 1,
        "region_base_address": b_allocation["base_address"],
        "materialized_16x_copy": False,
        "source_producer": f"{record['hw_op_id']}:B_DEQUANT",
        "source_tensor_identity": b_allocation["name"],
        "source_delivery": (
            "hardware-stage output committed to explicit B_SCALED scratch"
        ),
        "allowed_index_address_mapping": (
            "B_SCALED.base + (logical_output_index % 1000) * sizeof(float32)"
            if broadcast
            else "B_SCALED.base + logical_output_index * sizeof(float32)"
        ),
        "uncrossed_computation_boundary": (
            "address-only broadcast replay; no host scaling, rounding, "
            "saturation, quantization, or final-output computation"
        ),
        "host_precomputed_internal_tensor": False,
    }
    return {
        "stage_id": f"{record['hw_op_id']}:FP32_ADD",
        "kind": "FP32_PAIRWISE_ADD",
        "inputs": [
            {
                "role": "A_SCALED",
                "allocation": a_allocation["name"],
                "base_address": a_allocation["base_address"],
            },
            {
                "role": "B_SCALED",
                "allocation": b_allocation["name"],
                "base_address": b_allocation["base_address"],
                "replay": b_replay,
            },
        ],
        "output": {
            "allocation": sum_allocation["name"],
            "base_address": sum_allocation["base_address"],
            "dtype": "float32",
            "shape": record["y_shape"],
        },
        "occurrence": {
            "logical_elements": count,
            "vector_lanes": VECTOR_LANES_FP32_ADD,
            "count": count // VECTOR_LANES_FP32_ADD,
            "tail_elements": count % VECTOR_LANES_FP32_ADD,
            "terminal_last_index": count // VECTOR_LANES_FP32_ADD - 1,
        },
        "final_output_byte_coverage": {
            "formula": "occurrence_count * 16 == logical_elements * sizeof(float32)",
            "logical_bytes": count * 4,
            "transaction_bytes": 16,
            "transactions": count // VECTOR_LANES_FP32_ADD,
            "unique_written_byte_count": count * 4,
            "physical_region_bytes": sum_allocation["size_bytes"],
            "padding_bytes_not_typed_output": sum_allocation["padding_bytes"],
        },
        "materialized_leaf_ownership": {
            "inputs[*].base_address": "QLinearAdd family scratch arena allocator",
            "output.base_address": "QLinearAdd family scratch arena allocator",
            "occurrence.*": "typed Y shape and four-lane FP32-add schedule formula",
            "readiness.*": "QLinearAdd paired-readiness specialty rule",
            "inputs[1].replay": "typed broadcast geometry and B allocation",
            "ga.topology": "authorized native FP32-add structural topology",
        },
        "readiness": {
            "accepted_pair": "a_valid && b_valid && d_ready",
            "a_ready": "b_valid && d_ready",
            "b_ready": "a_valid && d_ready",
            "shared_lc_backpressure": "AND of A, B, and normal-outbuffer D",
            "no_single_input_advance": True,
            "ready_graph_acyclic": True,
        },
        "ga": {
            "operation": "round_float32(A_SCALED + B_SCALED)",
            "lanes": 4,
            "topology": "four independent FP32 ADD PEs",
            "normal_outbuffer": True,
        },
    }


def build_configuration(repository_root: Path) -> dict[str, Any]:
    root = repository_root.resolve()
    typed_path = root / "contracts/typed_config_parameter_contract.json"
    typed = _load(typed_path)
    records = _qlinearadd_records(typed)
    if len(records) != 17:
        raise QLinearAddStage0Error("expected exactly 17 QLinearAdd instances")

    cursor = ARENA_BASE
    instances: list[dict[str, Any]] = []
    for record in records:
        y_elements = _elements(record["y_shape"])
        b_elements = _elements(record["b_shape"])
        prefix = record["hw_op_id"]

        cursor = _align(cursor)
        a = _allocation(
            name=f"{prefix}:A_SCALED",
            base=cursor,
            elements=y_elements,
            shape=record["a_shape"],
            producer=f"{prefix}:A_DEQUANT",
            first_consumer=f"{prefix}:FP32_ADD",
            last_consumer=f"{prefix}:FP32_ADD:last_accepted_A_read",
            release="after FP32_ADD completion barrier",
        )
        cursor = _align(cursor + a["size_bytes"])
        b = _allocation(
            name=f"{prefix}:B_SCALED",
            base=cursor,
            elements=b_elements,
            shape=record["b_shape"],
            producer=f"{prefix}:B_DEQUANT",
            first_consumer=f"{prefix}:FP32_ADD",
            last_consumer=f"{prefix}:FP32_ADD:last_accepted_B_read",
            release="after FP32_ADD completion barrier",
        )
        cursor = _align(cursor + b["size_bytes"])
        summed = _allocation(
            name=f"{prefix}:SUM_F32",
            base=cursor,
            elements=y_elements,
            shape=record["y_shape"],
            producer=f"{prefix}:FP32_ADD",
            first_consumer="SHARED_EXACT_UINT8_TAIL_NOT_MATERIALIZED",
            last_consumer="SHARED_EXACT_UINT8_TAIL_NOT_MATERIALIZED",
            release="BLOCKED_UNTIL_EXACT_UINT8_TAIL_FINAL_ACCEPTED_READ",
        )
        cursor = _align(cursor + summed["size_bytes"])

        stages = [
            _dequant_stage(record, "a", a),
            _dequant_stage(record, "b", b),
            _sum_stage(record, a, b, summed),
        ]
        instances.append(
            {
                "node_id": record["node_id"],
                "hw_op_id": record["hw_op_id"],
                "class": record["class"],
                "tensors": record["tensors"],
                "shapes": {
                    "a": record["a_shape"],
                    "b": record["b_shape"],
                    "y": record["y_shape"],
                },
                "qparams": record["qparams"],
                "allocations": [a, b, summed],
                "barriers": [
                    {
                        "after": stages[0]["stage_id"],
                        "before": stages[2]["stage_id"],
                        "condition": "all A_SCALED writes accepted and globally visible",
                    },
                    {
                        "after": stages[1]["stage_id"],
                        "before": stages[2]["stage_id"],
                        "condition": "all B_SCALED writes accepted and globally visible",
                    },
                    {
                        "after": stages[2]["stage_id"],
                        "before": "SHARED_EXACT_UINT8_TAIL_NOT_MATERIALIZED",
                        "condition": "all SUM_F32 writes accepted and globally visible",
                    },
                ],
                "physical_stages": stages,
            }
        )

    bypass = {
        "bypass_reason": (
            "Functional RTL is frozen and the native add_dequant path terminates "
            "at FP32 while reassociating each affine branch; exhaustive scalar "
            "testing finds final-UINT8 counterexamples at node0007 and node0070."
        ),
        "contradicted_or_missing_native_path": (
            "Reject native add_dequant constants 1, MAC affine reassociation, and "
            "its lack of output quantization; native FP32 add is structural only."
        ),
        "exact_equivalence_scope": (
            "All 17 frozen QLinearAdd instances, complete uint8 scalar A/B domain "
            "for W3 branch dequant plus FP32 sum, all stage0 occurrences, "
            "node0076 broadcast replay, scratch non-alias and accepted-handshake "
            "lifetimes. UINT8 output quantization is excluded."
        ),
        "materialized_configuration_mechanism": (
            "Three serialized physical stages per instance: exact W3 A-dequant, "
            "exact W3 B-dequant, and paired FP32 add, with explicit FP32 DRAM "
            "scratch, completion barriers, normal outbuffer, and B replay."
        ),
        "performance_and_resource_cost": (
            "51 physical stages for 17 logical operators, three FP32 scratch "
            "allocations per instance, two dequant write/read round trips before "
            "the sum, serialized barriers, and low GA utilization."
        ),
        "unresolved_production_blocker": (
            "Shared exact UINT8 quant tail remains NO_UNCONDITIONAL_PURE_CONFIG_"
            "PROVEN; native JSON lowering, mapper/bitstream, execplan/SCA and "
            "server E4/E5 are not produced by this partial stage0 artifact."
        ),
        "claim_boundary": (
            f"{CLAIM} is not claimed for complete QLinearAdd. This artifact is "
            "a stage0-only configuration-bound correctness candidate ending at "
            "SUM_F32; Y UINT8, rounding, zero-point addition and saturation remain "
            "outside the materialized scope."
        ),
    }
    configuration: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "STAGE0_MATERIALIZED_TAIL_BLOCKED_NOT_RELEASED",
        "candidate_release": False,
        "claim": None,
        "allowed_claim_name": CLAIM,
        "materialization_scope": "QLinearAdd W3 front half through SUM_F32 only",
        "bypass_annotation": bypass,
        "provenance": {
            "contracts/typed_config_parameter_contract.json": _sha256_file(
                typed_path
            ),
            "ndp-sim/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json": _sha256_file(
                root
                / "ndp-sim/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json"
            ),
            "ndp-sim/jsons/prefill_add_fp32MN_fp32MN_fp32MN.json": _sha256_file(
                root / "ndp-sim/jsons/prefill_add_fp32MN_fp32MN_fp32MN.json"
            ),
            ".agents/rules/DequantizeLinear算子配置规则.md": _sha256_file(
                root / ".agents/rules/DequantizeLinear算子配置规则.md"
            ),
        },
        "current_match_rule_dependencies": [
            {
                "path": path,
                "sha256": sha256,
                "required_rule_ids": list(rule_ids),
            }
            for path, sha256, rule_ids in CURRENT_MATCH_RULES
        ],
        "mutable_read_receipt": {
            ".agents/plan.md": {
                "sha256": _sha256_file(root / ".agents/plan.md"),
                "drift_policy": "warning only; never overwrite to chase plan drift",
            }
        },
        "arena": {
            "base_address": f"0x{ARENA_BASE:016x}",
            "end_address_exclusive": f"0x{cursor:016x}",
            "allocated_bytes": cursor - ARENA_BASE,
            "alignment_bytes": ALIGNMENT,
            "allocation_count": len(instances) * 3,
            "reuse_between_instances": False,
        },
        "dependency_on_quant_tail": {
            "dependency_id": "R5_GAP_EXACT_UINT8_QUANT_TAIL",
            "decision": "NO_UNCONDITIONAL_PURE_CONFIG_PROVEN",
            "materialized": False,
            "output_y_materialized": False,
        },
        "materialization_ownership_gate": {
            "rule_id": "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001",
            "project_stage_configuration_roundtrip": True,
            "native_static_to_address_bound_leaf_diff": "NOT_GENERATED",
            "native_nonbase_leaf_changes": [],
            "native_handler_override_allowed": False,
            "final_output_coverage_recomputed_from_occurrence_and_addresses": True,
            "claim_effect": (
                "native JSON/mapping/bitstream/execplan/SCA gate remains open; "
                "therefore complete CONFIG_ONLY_CORRECTNESS_BASELINE is not claimed"
            ),
        },
        "instances": instances,
        "forbidden_outputs": {
            "uint8_y": False,
            "quant_tail_config": False,
            "server_package": False,
            "server_check_or_run": False,
            "rtl_change": False,
        },
    }
    configuration["configuration_sha256"] = _canonical_sha256(configuration)
    return configuration


def validate_configuration(
    configuration: dict[str, Any], repository_root: Path
) -> dict[str, Any]:
    root = repository_root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    if configuration.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    if configuration.get("status") != "STAGE0_MATERIALIZED_TAIL_BLOCKED_NOT_RELEASED":
        errors.append("status is not stage0-only fail-closed")
    if configuration.get("candidate_release") is not False:
        errors.append("candidate_release must be false")
    if configuration.get("claim") is not None:
        errors.append("complete CONFIG_ONLY_CORRECTNESS_BASELINE claim is forbidden")
    annotation = configuration.get("bypass_annotation", {})
    if set(annotation) != set(BYPASS_FIELDS):
        errors.append("bypass annotation does not contain exactly seven required fields")
    elif any(not isinstance(annotation[field], str) or not annotation[field] for field in BYPASS_FIELDS):
        errors.append("all seven bypass fields must be non-empty strings")
    elif CLAIM not in annotation["claim_boundary"]:
        errors.append("claim_boundary does not name the only allowed claim")

    for dependency in configuration.get("current_match_rule_dependencies", []):
        relative = dependency.get("path")
        source = root / str(relative)
        if not source.is_file():
            errors.append(f"current-match rule missing: {relative}")
            continue
        if _sha256_file(source) != dependency.get("sha256"):
            errors.append(f"current-match rule SHA mismatch: {relative}")
            continue
        text = source.read_text(encoding="utf-8")
        for rule_id in dependency.get("required_rule_ids", []):
            if rule_id not in text:
                errors.append(f"current-match rule ID missing: {relative}: {rule_id}")
    for relative, receipt in configuration.get("mutable_read_receipt", {}).items():
        source = root / relative
        if not source.is_file() or _sha256_file(source) != receipt.get("sha256"):
            warnings.append(f"mutable read receipt drift: {relative}")

    expected = build_configuration(root)
    expected.pop("mutable_read_receipt")
    actual = dict(configuration)
    actual.pop("mutable_read_receipt", None)
    if actual != expected:
        errors.append("materialized configuration differs from typed-source rebuild")

    allocations: list[tuple[int, int, str]] = []
    branch_domains_checked = 0
    sum_pairs_checked = 0
    replay_occurrences_checked = 0
    for instance in configuration.get("instances", []):
        stages = instance.get("physical_stages", [])
        if len(stages) != 3:
            errors.append(f"{instance.get('hw_op_id')}: physical stage count is not 3")
            continue
        for allocation in instance.get("allocations", []):
            start = int(allocation["base_address"], 16)
            end = int(allocation["end_address_exclusive"], 16)
            if (
                start % ALIGNMENT
                or end - start != allocation["size_bytes"]
                or allocation["size_bytes"] % ALIGNMENT
                or allocation["logical_size_bytes"] + allocation["padding_bytes"]
                != allocation["size_bytes"]
            ):
                errors.append(f"{allocation['name']}: alignment/size mismatch")
            allocations.append((start, end, allocation["name"]))
        for branch_index in (0, 1):
            stage = stages[branch_index]
            values = np.arange(256, dtype=np.uint8)
            ingress = values.astype(np.float32)
            negative_zero = _fp32_from_bits(
                stage["ga"]["negative_zero_point_f32_bits"]
            )
            scale = _fp32_from_bits(stage["ga"]["scale_f32_bits"])
            simulated = np.float32(np.float32(ingress + negative_zero) * scale)
            zero = -int(negative_zero)
            golden = np.float32((values.astype(np.int32) - zero).astype(np.float32) * scale)
            if not np.array_equal(simulated.view(np.uint32), golden.view(np.uint32)):
                errors.append(f"{stage['stage_id']}: W3 branch mismatch")
            occurrence = stage["occurrence"]
            coverage = stage["final_output_byte_coverage"]
            expected_occurrences = (
                occurrence["logical_elements"] + occurrence["vector_lanes"] - 1
            ) // occurrence["vector_lanes"]
            expected_tail = (
                occurrence["logical_elements"] % occurrence["vector_lanes"]
            )
            if (
                occurrence["count"] != expected_occurrences
                or occurrence["tail_elements"] != expected_tail
                or occurrence["terminal_last_index"] != expected_occurrences - 1
                or coverage["logical_bytes"]
                != occurrence["logical_elements"] * 4
                or coverage["unique_written_byte_count"]
                != coverage["logical_bytes"]
                or coverage["tail_valid_bytes"] != expected_tail * 4
            ):
                errors.append(f"{stage['stage_id']}: final output byte coverage mismatch")
            branch_domains_checked += 256
        a_stage, b_stage, sum_stage = stages
        av = np.arange(256, dtype=np.uint8)
        bv = np.arange(256, dtype=np.uint8)
        a_scale = _fp32_from_bits(a_stage["ga"]["scale_f32_bits"])
        b_scale = _fp32_from_bits(b_stage["ga"]["scale_f32_bits"])
        a_zero = -int(_fp32_from_bits(a_stage["ga"]["negative_zero_point_f32_bits"]))
        b_zero = -int(_fp32_from_bits(b_stage["ga"]["negative_zero_point_f32_bits"]))
        a_scaled = np.float32((av.astype(np.int32) - a_zero).astype(np.float32) * a_scale)
        b_scaled = np.float32((bv.astype(np.int32) - b_zero).astype(np.float32) * b_scale)
        simulated_sum = np.float32(a_scaled[:, None] + b_scaled[None, :])
        golden_sum = np.float32(
            np.float32((av.astype(np.int32) - a_zero).astype(np.float32) * a_scale)[:, None]
            + np.float32((bv.astype(np.int32) - b_zero).astype(np.float32) * b_scale)[None, :]
        )
        if not np.array_equal(simulated_sum.view(np.uint32), golden_sum.view(np.uint32)):
            errors.append(f"{sum_stage['stage_id']}: FP32 sum mismatch")
        sum_pairs_checked += 65536
        occurrence = sum_stage["occurrence"]
        coverage = sum_stage["final_output_byte_coverage"]
        if occurrence["tail_elements"] != 0:
            errors.append(f"{sum_stage['stage_id']}: unexpected FP32 add tail")
        if (
            coverage["transactions"] * coverage["transaction_bytes"]
            != coverage["logical_bytes"]
            or coverage["unique_written_byte_count"] != coverage["logical_bytes"]
        ):
            errors.append(f"{sum_stage['stage_id']}: final output byte coverage mismatch")
        replay = sum_stage["inputs"][1]["replay"]
        if replay["enabled"]:
            count = occurrence["logical_elements"]
            base = int(replay["region_base_address"], 16)
            addresses = [base + (index % 1000) * 4 for index in range(count)]
            if addresses[:1000] * 16 != addresses:
                errors.append("node0076 B-scaled address replay sequence mismatch")
            replay_occurrences_checked += count
            if replay["materialized_16x_copy"] is not False:
                errors.append("node0076 illegally materializes a 16x B copy")

    allocations.sort()
    for previous, current in zip(allocations, allocations[1:]):
        if previous[1] > current[0]:
            errors.append(f"scratch overlap: {previous[2]} -> {current[2]}")

    typed = _load(root / "contracts/typed_config_parameter_contract.json")
    negative_control = _affine_reassociation_counterexamples(typed)
    expected_negative = [
        {
            "node_id": "node-0007",
            "mismatch_pair_count": 2,
            "first": {
                "a": 120,
                "b": 232,
                "w3": 246,
                "affine_reassociated": 245,
            },
        },
        {
            "node_id": "node-0070",
            "mismatch_pair_count": 1,
            "first": {
                "a": 213,
                "b": 1,
                "w3": 151,
                "affine_reassociated": 152,
            },
        },
    ]
    if negative_control != expected_negative:
        errors.append("native affine-reassociation negative control drifted")

    return {
        "schema": "qlinearadd_stage0_config_only_validation_v1",
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "claim": None,
        "allowed_claim_name": CLAIM,
        "materialization_scope": configuration.get("materialization_scope"),
        "coverage": {
            "instances": len(configuration.get("instances", [])),
            "physical_stages": sum(
                len(item.get("physical_stages", []))
                for item in configuration.get("instances", [])
            ),
            "scratch_allocations": len(allocations),
            "branch_scalar_values_checked": branch_domains_checked,
            "fp32_sum_scalar_pairs_checked": sum_pairs_checked,
            "node0076_replay_elements_checked": replay_occurrences_checked,
        },
        "negative_control": negative_control,
        "configuration_sha256": configuration.get("configuration_sha256"),
        "dependency_on_quant_tail": configuration.get("dependency_on_quant_tail"),
        "package_release": {
            "status": "NOT_GENERATED_NO_LEASE_AND_COMPLETE_QADD_UNCLOSED",
            "server_inspected": False,
            "uploaded": False,
            "run": False,
        },
    }


def validate_receipts(
    configuration: dict[str, Any], repository_root: Path
) -> dict[str, Any]:
    """Validate provenance/replay/claim gates without repeating numeric analysis."""
    root = repository_root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    if configuration.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    if configuration.get("candidate_release") is not False:
        errors.append("candidate_release must be false")
    if configuration.get("claim") is not None:
        errors.append("complete CONFIG_ONLY_CORRECTNESS_BASELINE claim is forbidden")
    annotation = configuration.get("bypass_annotation", {})
    if set(annotation) != set(BYPASS_FIELDS):
        errors.append("bypass annotation does not contain exactly seven required fields")

    for dependency in configuration.get("current_match_rule_dependencies", []):
        relative = dependency.get("path")
        source = root / str(relative)
        if not source.is_file():
            errors.append(f"current-match rule missing: {relative}")
            continue
        if _sha256_file(source) != dependency.get("sha256"):
            errors.append(f"current-match rule SHA mismatch: {relative}")
            continue
        text = source.read_text(encoding="utf-8")
        for rule_id in dependency.get("required_rule_ids", []):
            if rule_id not in text:
                errors.append(f"current-match rule ID missing: {relative}: {rule_id}")
    for relative, receipt in configuration.get("mutable_read_receipt", {}).items():
        source = root / relative
        if not source.is_file() or _sha256_file(source) != receipt.get("sha256"):
            warnings.append(f"mutable read receipt drift: {relative}")

    replay_nodes = []
    for instance in configuration.get("instances", []):
        stages = instance.get("physical_stages", [])
        if len(stages) != 3:
            errors.append(f"{instance.get('hw_op_id')}: physical stage count is not 3")
            continue
        replay = stages[2]["inputs"][1]["replay"]
        if replay.get("enabled"):
            replay_nodes.append(instance.get("node_id"))
            expected_identity = instance["allocations"][1]["name"]
            if (
                replay.get("source_producer")
                != f"{instance['hw_op_id']}:B_DEQUANT"
                or replay.get("source_tensor_identity") != expected_identity
                or replay.get("host_precomputed_internal_tensor") is not False
                or "address-only broadcast replay"
                not in replay.get("uncrossed_computation_boundary", "")
                or replay.get("materialized_16x_copy") is not False
            ):
                errors.append(
                    f"{instance.get('hw_op_id')}: replay crosses computation boundary"
                )
    if replay_nodes != ["node-0076"]:
        errors.append("replay must be enabled only for node0076")

    digest = configuration.get("configuration_sha256")
    unhashed = dict(configuration)
    unhashed.pop("configuration_sha256", None)
    if digest != _canonical_sha256(unhashed):
        errors.append("configuration canonical SHA mismatch")
    gate = configuration.get("materialization_ownership_gate", {})
    if (
        gate.get("native_static_to_address_bound_leaf_diff") != "NOT_GENERATED"
        or gate.get("native_handler_override_allowed") is not False
    ):
        errors.append("native materialization gate was upgraded without proof")
    return {
        "schema": "qlinearadd_stage0_receipt_validation_v1",
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "numeric_analysis_repeated": False,
        "current_match_dependencies_checked": len(
            configuration.get("current_match_rule_dependencies", [])
        ),
        "replay_nodes_checked": replay_nodes,
        "claim": None,
        "dependency_on_quant_tail": configuration.get("dependency_on_quant_tail"),
    }


def write_configuration(repository_root: Path, output_path: Path) -> dict[str, Any]:
    configuration = build_configuration(repository_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(configuration, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return configuration


def build_contract(
    configuration_path: Path, configuration: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema": "qlinearadd_stage0_config_only_contract_v1",
        "status": "STAGE0_CONFIG_BOUND_VALIDATION_ONLY_TAIL_BLOCKED",
        "candidate_release": False,
        "claim": None,
        "allowed_claim_name": CLAIM,
        "bypass_annotation": configuration["bypass_annotation"],
        "materialized_configuration": {
            "path": configuration_path.as_posix(),
            "file_sha256": _sha256_file(configuration_path),
            "canonical_configuration_sha256": configuration[
                "configuration_sha256"
            ],
            "instance_count": len(configuration["instances"]),
            "physical_stage_count": sum(
                len(item["physical_stages"])
                for item in configuration["instances"]
            ),
            "scratch_allocation_count": sum(
                len(item["allocations"]) for item in configuration["instances"]
            ),
        },
        "closed_scope": [
            "six-qparam typed transport into stage0 constants",
            "W3 per-operation float32 A and B dequantization",
            "paired FP32 add and shared-LC backpressure equation",
            "node0076 1000-element B-scaled replay across 16 batches",
            "explicit scratch allocation, non-overlap, barriers and stage0 lifetime",
            "complete uint8 scalar A/B domain for stage0 numeric semantics",
            "native affine-reassociation negative control",
        ],
        "open_scope": [
            "exact UINT8 quant tail",
            "final Y allocation/write/readback",
            "native static JSON lowering",
            "mapping and bitstream",
            "execplan and SCA/SCA_D",
            "server E4/E5",
        ],
        "dependency_on_quant_tail": configuration["dependency_on_quant_tail"],
        "package_release": {
            "status": "NOT_GENERATED_NO_LEASE_AND_COMPLETE_QADD_UNCLOSED",
            "server_inspected": False,
            "uploaded": False,
            "run": False,
        },
    }


def write_contract(
    repository_root: Path,
    configuration_path: Path,
    configuration: dict[str, Any],
    contract_path: Path,
) -> dict[str, Any]:
    relative_config = configuration_path.resolve().relative_to(
        repository_root.resolve()
    )
    contract = build_contract(
        repository_root.resolve() / relative_config, configuration
    )
    contract["materialized_configuration"]["path"] = relative_config.as_posix()
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return contract


def validate_contract(
    contract: dict[str, Any], repository_root: Path
) -> dict[str, Any]:
    errors: list[str] = []
    if contract.get("schema") != "qlinearadd_stage0_config_only_contract_v1":
        errors.append("contract schema mismatch")
    if contract.get("candidate_release") is not False:
        errors.append("contract candidate_release must be false")
    if contract.get("claim") is not None:
        errors.append("contract must not claim complete QLinearAdd baseline")
    annotation = contract.get("bypass_annotation", {})
    if set(annotation) != set(BYPASS_FIELDS):
        errors.append("contract bypass annotation must contain exactly seven fields")
    descriptor = contract.get("materialized_configuration", {})
    path = repository_root.resolve() / str(descriptor.get("path", ""))
    config_report: dict[str, Any] = {
        "valid": False,
        "errors": ["materialized configuration missing"],
        "warnings": [],
    }
    if not path.is_file():
        errors.append("contract materialized configuration is missing")
    else:
        if _sha256_file(path) != descriptor.get("file_sha256"):
            errors.append("contract materialized configuration file SHA mismatch")
        configuration = _load(path)
        if (
            configuration.get("configuration_sha256")
            != descriptor.get("canonical_configuration_sha256")
        ):
            errors.append("contract canonical configuration SHA mismatch")
        if configuration.get("bypass_annotation") != annotation:
            errors.append("contract/config seven-field bypass annotation mismatch")
        config_report = validate_configuration(configuration, repository_root)
        if not config_report["valid"]:
            errors.append("referenced materialized configuration is invalid")
    return {
        "schema": "qlinearadd_stage0_config_only_contract_validation_v1",
        "valid": not errors,
        "errors": errors,
        "warnings": config_report.get("warnings", []),
        "claim": None,
        "allowed_claim_name": CLAIM,
        "configuration_validation": config_report,
        "package_release": contract.get("package_release"),
    }


def validate_contract_receipts(
    contract: dict[str, Any], repository_root: Path
) -> dict[str, Any]:
    errors: list[str] = []
    if contract.get("schema") != "qlinearadd_stage0_config_only_contract_v1":
        errors.append("contract schema mismatch")
    if contract.get("candidate_release") is not False or contract.get("claim") is not None:
        errors.append("contract release/claim boundary mismatch")
    if set(contract.get("bypass_annotation", {})) != set(BYPASS_FIELDS):
        errors.append("contract bypass annotation must contain exactly seven fields")
    descriptor = contract.get("materialized_configuration", {})
    path = repository_root.resolve() / str(descriptor.get("path", ""))
    config_report: dict[str, Any] = {
        "valid": False,
        "errors": ["materialized configuration missing"],
        "warnings": [],
    }
    if not path.is_file():
        errors.append("contract materialized configuration is missing")
    else:
        if _sha256_file(path) != descriptor.get("file_sha256"):
            errors.append("contract materialized configuration file SHA mismatch")
        configuration = _load(path)
        if (
            configuration.get("configuration_sha256")
            != descriptor.get("canonical_configuration_sha256")
        ):
            errors.append("contract canonical configuration SHA mismatch")
        if (
            configuration.get("bypass_annotation")
            != contract.get("bypass_annotation")
        ):
            errors.append("contract/config seven-field bypass annotation mismatch")
        config_report = validate_receipts(configuration, repository_root)
        if not config_report["valid"]:
            errors.append("referenced materialized configuration receipts are invalid")
    return {
        "schema": "qlinearadd_stage0_contract_receipt_validation_v1",
        "valid": not errors,
        "errors": errors,
        "warnings": config_report.get("warnings", []),
        "numeric_analysis_repeated": False,
        "configuration_receipt_validation": config_report,
        "claim": None,
        "package_release": contract.get("package_release"),
    }


def validate_configuration_path(
    path: Path, repository_root: Path
) -> dict[str, Any]:
    return validate_configuration(_load(path.resolve()), repository_root)


def validate_contract_path(path: Path, repository_root: Path) -> dict[str, Any]:
    return validate_contract(_load(path.resolve()), repository_root)
