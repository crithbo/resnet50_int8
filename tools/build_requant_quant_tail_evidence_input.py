from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.hashing import (  # noqa: E402
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)
from resnet50_pipeline.requant_family_classification import (  # noqa: E402
    ACCUMULATOR_ROOT,
    MODEL_PATH,
    TYPED_PATH,
    _channel_multiplier_view,
    _guarded_magic_replay,
    _initializer_values,
    _magic_replay,
    _multiplier_and_zero_point,
    _standard_replay,
)


SCHEMA = "requant-quant-tail-evidence-input-v1"
OUTPUT_PATH = Path(
    "contracts/operator_config/requant_quant_tail_evidence_input_v1.json"
)
ARTIFACT_ROOT = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-quant-tail-evidence-input-v1"
)
RECEIPT_PATH = ARTIFACT_ROOT / "generation_receipt.json"
FAMILY_REPORT_PATH = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-family-classification-v1/report.json"
)
NODE0001_E2_PATH = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-node0001-two-stage-e2-v1/local_e2_report.json"
)
SHAPE_HOLDOUT_PATH = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-zero-point-shape-holdouts-v1/analysis.json"
)
AUDIT_CONTRACT_PATH = Path(
    "contracts/operator_config/resnet50_ndpsim_reuse_gap_audit_v1.json"
)
AUDIT_RECORD_PATH = Path(
    ".agents/task_records/"
    "20260727_ndpsim_resnet50_reuse_audit_and_replan.md"
)
P0A_CONTRACT_PATH = Path(
    "contracts/operator_config/exact_uint8_quant_tail_capability_v1.json"
)
P0A_RECORD_PATH = Path(
    ".agents/task_records/"
    "20260727_exact_uint8_quant_tail_capability_matrix.md"
)
PLAN_PATH = Path(".agents/plan.md")
READ_INDEX_PATH = Path(".agents/rules/生成前必读索引.md")
SHARED_QUANT_RULE_PATH = Path(
    ".agents/rules/精确UINT8量化尾专项规则.md"
)
REQUANT_RULE_PATH = Path(
    ".agents/rules/RequantizeUint8算子配置规则.md"
)

ACTIVE_RULE_SHA256 = {
    READ_INDEX_PATH.as_posix(): (
        "6ae4c7fe09fcdb39a48357cfef645c272f67e7a81d09b5547ebd9a929e6ce1a4"
    ),
    SHARED_QUANT_RULE_PATH.as_posix(): (
        "5593f9df3bbc5605e9b019b6cc53ee33b0edbeb203d657fdf974cb4b680c2df0"
    ),
    REQUANT_RULE_PATH.as_posix(): (
        "d9ec14cc6975e9596f3fe56e762cd4797c8ba6c70fa235503f5954e97c6f863f"
    ),
}


class EvidenceInputError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceInputError(f"cannot parse JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise EvidenceInputError(f"JSON root must be an object: {path}")
    return value


def _binding(root: Path, relative: Path) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise EvidenceInputError(f"required evidence is missing: {relative}")
    return {
        "path": relative.as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _self_hash(value: Mapping[str, Any], field: str) -> str:
    return sha256_bytes(
        canonical_json_bytes(
            {key: item for key, item in value.items() if key != field}
        )
    )


def _float32_bits(value: np.float32) -> str:
    bits = np.asarray(value, dtype=np.float32).view(np.uint32).item()
    return f"0x{int(bits):08x}"


def _index(mask: np.ndarray) -> tuple[int, ...] | None:
    flat = np.flatnonzero(mask)
    if flat.size == 0:
        return None
    return tuple(int(item) for item in np.unravel_index(int(flat[0]), mask.shape))


def _example(
    *,
    kind: str,
    index: tuple[int, ...],
    accumulator: np.ndarray,
    multiplier: np.ndarray,
    scaled: np.ndarray,
    standard: np.ndarray,
    magic: np.ndarray,
    guarded: np.ndarray,
    zero_point: int,
) -> dict[str, Any]:
    channel = index[1]
    multiplier_value = np.float32(
        multiplier[channel] if multiplier.size > 1 else multiplier[0]
    )
    scaled_value = np.float32(scaled[index])
    rounded = int(np.rint(scaled_value))
    before_clip = rounded + zero_point
    return {
        "kind": kind,
        "logical_index": list(index),
        "channel_index": channel,
        "accumulator_int32": int(accumulator[index]),
        "multiplier_float32": float(multiplier_value),
        "multiplier_float32_bits": _float32_bits(multiplier_value),
        "scaled_float32": float(scaled_value),
        "scaled_float32_bits": _float32_bits(scaled_value),
        "nearest_even_integer": rounded,
        "y_zero_point": zero_point,
        "integer_before_uint8_clip": before_clip,
        "exact_uint8": int(standard[index]),
        "magic_add_zp_inside_round_uint8": int(magic[index]),
        "node0001_guard_recipe_uint8": int(guarded[index]),
    }


def _classify_layout(shape: list[int]) -> dict[str, Any]:
    if len(shape) == 4:
        return {
            "logical_layout": "NCHW",
            "physical_layout_requirement": "HWC8_ADDRESS_AND_BYTE_CONSERVATION",
            "classification": "RANK4_LAYOUT_REQUIRES_PER_SHAPE_MATERIALIZATION",
        }
    if len(shape) == 2:
        return {
            "logical_layout": "NC",
            "physical_layout_requirement": "RANK2_MATMUL_OUTPUT_LAYOUT_CONTRACT",
            "classification": "RANK2_NOT_PROVEN_BY_NODE0001_HWC8",
        }
    raise EvidenceInputError(f"unexpected Requant rank: {shape}")


def build_evidence_input(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    family = _load(root / FAMILY_REPORT_PATH)
    node0001_e2 = _load(root / NODE0001_E2_PATH)
    holdouts = _load(root / SHAPE_HOLDOUT_PATH)
    audit = _load(root / AUDIT_CONTRACT_PATH)
    p0a = _load(root / P0A_CONTRACT_PATH)
    typed = _load(root / TYPED_PATH)
    initializers = _initializer_values(root / MODEL_PATH)
    p0a_decision = p0a.get("pure_configuration_decision", {})
    if (
        p0a.get("schema") != "exact-uint8-quant-tail-capability-v1"
        or p0a_decision.get("decision")
        != "NO_UNCONDITIONAL_PURE_CONFIG_PROVEN"
    ):
        raise EvidenceInputError("P0-A capability decision differs")
    p0a_counterexamples = {
        str(item.get("id")): item
        for item in p0a.get("counterexamples", [])
        if isinstance(item, Mapping)
    }
    required_p0a_counterexamples = {
        "CE_FMA_VS_SEQUENTIAL_ROUND",
        "CE_ODD_ZP_TIE_PARITY",
        "CE_MAGIC_DOMAIN_UNDERFLOW",
        "CE_INT32_NEGATIVE_CONVERSION",
        "CE_FP32_DIVISION_VS_RECIPROCAL_FMA",
    }
    if set(p0a_counterexamples) != required_p0a_counterexamples:
        raise EvidenceInputError("P0-A counterexample set differs")

    typed_by_id = {
        str(item.get("hw_op_id")): item
        for item in typed.get("hw_ops", [])
        if isinstance(item, Mapping)
    }
    records = family.get("records")
    if not isinstance(records, list) or len(records) != 54:
        raise EvidenceInputError("family report must contain exactly 54 records")

    stage_evidence: list[dict[str, Any]] = []
    signed_counterexamples: list[dict[str, Any]] = []
    tie_counterexamples: list[dict[str, Any]] = []
    lower_saturation_examples: list[dict[str, Any]] = []
    upper_saturation_examples: list[dict[str, Any]] = []
    all_stage_lower_saturation_examples: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()

    for source in records:
        if not isinstance(source, Mapping):
            raise EvidenceInputError("family record is not an object")
        request_id = str(source["request_id"])
        hw_op_id = str(source["identity"]["hw_op_id"])
        stage = typed_by_id.get(hw_op_id)
        if not isinstance(stage, Mapping):
            raise EvidenceInputError(f"typed stage missing: {hw_op_id}")
        multiplier, zero_point = _multiplier_and_zero_point(stage, initializers)
        accumulator_path = root / Path(source["w3"]["accumulator"]["path"])
        if sha256_file(accumulator_path) != source["w3"]["accumulator"]["sha256"]:
            raise EvidenceInputError(f"W3 identity differs: {request_id}")
        accumulator = np.load(accumulator_path, allow_pickle=False)
        standard, scaled = _standard_replay(
            accumulator, multiplier, zero_point
        )
        magic = _magic_replay(scaled, zero_point)
        guarded, _ = _guarded_magic_replay(
            accumulator, multiplier, zero_point
        )
        rounded = np.rint(scaled).astype(np.int64)
        before_clip = rounded + np.int64(zero_point)
        tie_mask = (scaled - np.floor(scaled)) == np.float32(0.5)
        signed_mask = standard != guarded
        magic_mask = standard != magic
        lower_mask = before_clip < 0
        upper_mask = before_clip > 255
        lower_count = int(np.count_nonzero(lower_mask))
        upper_count = int(np.count_nonzero(upper_mask))
        tie_count = int(np.count_nonzero(tie_mask))

        examples: dict[str, Any] = {}
        for kind, mask in (
            ("signed_domain_guard_loss", signed_mask),
            ("tie_parity_when_zp_is_added_inside_magic_round", magic_mask),
            ("lower_uint8_saturation", lower_mask),
            ("upper_uint8_saturation", upper_mask),
        ):
            idx = _index(mask)
            if idx is None:
                continue
            item = _example(
                kind=kind,
                index=idx,
                accumulator=accumulator,
                multiplier=multiplier,
                scaled=scaled,
                standard=standard,
                magic=magic,
                guarded=guarded,
                zero_point=zero_point,
            )
            examples[kind] = item
            decorated = {"request_id": request_id, **item}
            if kind == "signed_domain_guard_loss" and zero_point != 0:
                signed_counterexamples.append(decorated)
            elif kind == "tie_parity_when_zp_is_added_inside_magic_round":
                tie_counterexamples.append(decorated)
            elif (
                kind == "lower_uint8_saturation"
                and zero_point != 0
                and not lower_saturation_examples
            ):
                lower_saturation_examples.append(decorated)
            elif (
                kind == "upper_uint8_saturation"
                and zero_point != 0
                and not upper_saturation_examples
            ):
                upper_saturation_examples.append(decorated)
            if (
                kind == "lower_uint8_saturation"
                and not all_stage_lower_saturation_examples
            ):
                all_stage_lower_saturation_examples.append(decorated)

        shape = list(source["logical_shape"])
        channels = int(source["channels"])
        is_node0001 = request_id == "r5:hwop-0001-01"
        numeric_problem = (
            "NONE_EXACT_W3_AND_ZP0_GUARD_COMPATIBLE"
            if zero_point == 0
            else "NUMERIC_RECIPE_GAP_SIGNED_DOMAIN"
        )
        if zero_point % 2:
            numeric_problem += "_PLUS_ODD_ZP_TIE_PARITY_RISK"
        materialization = (
            "PHYSICAL_E2_COMPLETE_CONFIG_BOUND"
            if is_node0001
            else (
                "PHYSICAL_E2_PENDING_NUMERIC_RECIPE_COMPATIBLE"
                if zero_point == 0
                else "PHYSICAL_MATERIALIZATION_DEFERRED_UNTIL_NUMERIC_RECIPE"
            )
        )
        lifetime = (
            {
                "classification": "TWO_STAGE_LIFETIME_MATERIALIZED",
                "barrier_count": node0001_e2["lifecycle"]["barrier_count"],
                "start_comp_count": node0001_e2["lifecycle"][
                    "start_comp_count"
                ],
                "repeat_num": node0001_e2["lifecycle"]["repeat_num"],
                "stage0_d_to_stage1_a_same_address": node0001_e2[
                    "materialized_roundtrip"
                ]["all_producer_consumer_addresses_identical"],
                "stage1_consumer_preload_removed": node0001_e2["lifecycle"][
                    "consumer_sca_sanitization"
                ]["runtime_consumer_preload_key_count"]
                == 0,
            }
            if is_node0001
            else {
                "classification": "ADDRESS_ALIAS_BARRIER_LIFETIME_PENDING",
                "node0001_lifetime_must_not_be_assumed_for_this_shape": True,
            }
        )
        dependency_blockers = [
            "B_QUANT_TAIL_FMA_ROUNDING_POINT",
            "B_QUANT_TAIL_MAGIC_DOMAIN_BOUND",
            "B_QUANT_TAIL_SIGNED_INT32_INGRESS",
            "B_QUANT_TAIL_THREE_PE_TOPOLOGY",
            "B_QUANT_TAIL_TYPED_BINDING",
            "B_QUANT_TAIL_MAPPER_REGISTRATION",
        ]
        applicable_counterexamples = [
            "CE_FMA_VS_SEQUENTIAL_ROUND",
            "CE_MAGIC_DOMAIN_UNDERFLOW",
            "CE_INT32_NEGATIVE_CONVERSION",
        ]
        if zero_point != 0:
            dependency_blockers.append(
                "B_REQUANT_NONZERO_ZP_SIGNED_DOMAIN"
            )
        if zero_point % 2:
            dependency_blockers.append("B_REQUANT_MAGIC_ZP_TIE_PARITY")
            applicable_counterexamples.append("CE_ODD_ZP_TIE_PARITY")
        p0a_classification = (
            "ZP0_W3_COMPATIBLE_BUT_ROUNDING_DOMAIN_RELEASE_BLOCKED"
            if zero_point == 0
            else (
                "NONZERO_ODD_ZP_SIGNED_ROUNDING_DOMAIN_AND_TIE_BLOCKED"
                if zero_point % 2
                else "NONZERO_EVEN_ZP_SIGNED_ROUNDING_AND_DOMAIN_BLOCKED"
            )
        )
        p0a_mapping = {
            "shared_decision": "NO_UNCONDITIONAL_PURE_CONFIG_PROVEN",
            "classification": p0a_classification,
            "blocking_gate_ids": dependency_blockers,
            "applicable_counterexample_ids": applicable_counterexamples,
            "fma_rounding_boundary_unproven": True,
            "finite_magic_domain_unproven": True,
            "negative_int32_seen_in_w3": source["w3"]["negative_count"] > 0,
            "signed_ingress_interpretation": (
                "zp0 guard is numerically compatible on W3 but is only a "
                "conditional workaround, not a released shared signed route"
                if zero_point == 0
                else "zp0 pre-clamp workaround is algebraically invalid"
            ),
            "exact_fp32_division_counterexample_applicability": (
                "NOT_APPLICABLE_TO_REQUANT_MULTIPLIER_PATH"
            ),
            "release_ready": False,
        }
        stage_evidence.append(
            {
                "ordinal": source["ordinal"],
                "request_id": request_id,
                "hw_op_id": hw_op_id,
                "node_id": source["identity"]["node_id"],
                "onnx_op_type": source["identity"]["onnx_op_type"],
                "logical_shape": shape,
                "qparams": {
                    **source["qparams"],
                    "numeric_order": (
                        "float32_multiply_then_nearest_even_then_"
                        "integer_add_zero_point_then_uint8_clip"
                    ),
                },
                "w3": {
                    **source["w3"],
                    "exact_recipe_proven": source["w3"][
                        "standard_round_then_add_zp_mismatch_count"
                    ]
                    == 0,
                    "nearest_even_halfway_input_count": tie_count,
                    "integer_before_clip_below_zero_count": lower_count,
                    "integer_before_clip_above_255_count": upper_count,
                },
                "numeric_classification": source["classification"],
                "numeric_problem_kind": numeric_problem,
                "physical_materialization_classification": materialization,
                "shape_layout": _classify_layout(shape),
                "transaction": {
                    "channels": channels,
                    "lane_count": 8,
                    "channel_tail_mod8": source["channel_tail_mod8"],
                    "shard_count": (channels + 7) // 8,
                    "three_wave_occurrence_forecast_not_emission_authority": (
                        source[
                            "three_wave_occurrence_forecast_not_emission_authority"
                        ]
                    ),
                    "two_stage_count_forecast_not_emission_authority": source[
                        "two_stage_physical_stage_forecast_not_emission_authority"
                    ],
                },
                "lifetime": lifetime,
                "p0a_dependency_mapping": p0a_mapping,
                "counterexamples": examples,
                "formal_target_instance_allowed": False,
            }
        )
        totals["lower_saturation"] += lower_count
        totals["upper_saturation"] += upper_count
        totals["halfway"] += tie_count
        if zero_point != 0:
            totals["nonzero_lower_saturation"] += lower_count
            totals["nonzero_upper_saturation"] += upper_count
            totals["nonzero_halfway"] += tie_count
            totals[
                "p0a_nonzero_odd_blocked"
                if zero_point % 2
                else "p0a_nonzero_even_blocked"
            ] += 1
        else:
            totals["p0a_zp0_rounding_blocked"] += 1
            totals["p0a_zp0_magic_domain_blocked"] += 1
            if source["w3"]["negative_count"] > 0:
                totals["p0a_zp0_negative_w3"] += 1

    summary = family["summary"]
    average_assessment = next(
        item
        for item in audit["operator_assessment"]
        if item["onnx_op_type"] == "QLinearGlobalAveragePool"
    )
    matmul = next(
        item
        for item in stage_evidence
        if item["request_id"] == "r5:hwop-0075-01"
    )
    active_rule_receipts = [
        {
            **_binding(root, READ_INDEX_PATH),
            "role": "mandatory_read_routing",
            "active_rule_ids": [],
        },
        {
            **_binding(root, SHARED_QUANT_RULE_PATH),
            "role": "shared_exact_uint8_quant_tail_fail_closed_semantics",
            "active_rule_ids": [
                "CDA-QUANT-TAIL-NUMERIC-ORDER-001",
                "CDA-QUANT-TAIL-ZP-AFTER-ROUND-001",
                "CDA-QUANT-TAIL-MAGIC-DOMAIN-001",
                "CDA-QUANT-TAIL-CAPABILITY-MATRIX-001",
            ],
        },
        {
            **_binding(root, REQUANT_RULE_PATH),
            "role": "requant_family_semantics_and_instance_magic_scope",
            "active_rule_ids": [
                "CDA-REQUANT-FAMILY-QPARAM-CLASSIFICATION-001",
                "CDA-REQUANT-NONZERO-ZP-GUARD-001",
                "CDA-REQUANT-ROUND-MAGIC-001",
                "CDA-REQUANT-ZP-TIE-PARITY-001",
            ],
        },
    ]
    if any(
        item["sha256"] != ACTIVE_RULE_SHA256[item["path"]]
        for item in active_rule_receipts
    ):
        raise EvidenceInputError("active rule receipt differs")
    evidence: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "P1B_REQUANT_EVIDENCE_READY_FOR_P0A_QUANT_TAIL",
        "owner_family": "RequantizeUint8 / AverageRequantizeUint8",
        "consumer_owner": "QuantizeLinear exact UINT8 quant-tail P0-A",
        "mainline_thread_id": "019fa2ca-72bc-7753-8d58-81e59bc76c88",
        "control_read_receipts": [
            _binding(root, PLAN_PATH),
            _binding(root, AUDIT_RECORD_PATH),
            _binding(root, P0A_RECORD_PATH),
        ],
        "control_receipt_policy": {
            "plan_is_mutable_provenance": True,
            "plan_current_match_is_not_a_semantic_gate": True,
            "generation_time_plan_sha256": sha256_file(root / PLAN_PATH),
        },
        "active_rule_receipts": active_rule_receipts,
        "semantic_source_receipts": [
            _binding(root, AUDIT_CONTRACT_PATH),
            _binding(root, P0A_CONTRACT_PATH),
            _binding(root, FAMILY_REPORT_PATH),
            _binding(root, NODE0001_E2_PATH),
            _binding(root, SHAPE_HOLDOUT_PATH),
            _binding(root, TYPED_PATH),
            _binding(root, MODEL_PATH),
        ],
        "active_rule_integration": {
            "shared_quant_tail_rules_approved": True,
            "approved_shared_rule_ids": [
                "CDA-QUANT-TAIL-NUMERIC-ORDER-001",
                "CDA-QUANT-TAIL-ZP-AFTER-ROUND-001",
                "CDA-QUANT-TAIL-MAGIC-DOMAIN-001",
                "CDA-QUANT-TAIL-CAPABILITY-MATRIX-001",
            ],
            "requant_magic_rule_scope": (
                "NODE0001_FORMAL_W3_DOMAIN_CONDITIONAL_LOCAL_E2_ONLY"
            ),
            "requant_magic_rule_does_not_close_shared_fma_capability": True,
            "family_semantic_classification_changed": False,
            "stage_count_and_partition_unchanged": {
                "w3_exact": 54,
                "zp0_numeric_compatible": 33,
                "nonzero_guard_contradicted": 21,
                "physical_local_e2": 1,
            },
        },
        "quant_tail_semantics": {
            "input_domain_proven_here": "INT32",
            "output_dtype": "UINT8",
            "equation": (
                "clip_uint8(rne(float32(int32_input) * "
                "float32(multiplier)) + int(y_zero_point))"
            ),
            "operation_order_is_normative": [
                "convert INT32 input to FP32",
                "multiply in FP32 by positive finite scalar/per-channel multiplier",
                "round FP32 product to nearest integer, ties to even",
                "add UINT8 zero-point in the integer domain",
                "saturate to [0,255] and store UINT8",
            ],
            "nonzero_zp_prohibition": (
                "do not clamp the signed input before scaling and do not add "
                "zero-point inside the FP32 magic-round expression"
            ),
            "fp32_ingress_not_proven_by_this_evidence": True,
        },
        "summary": {
            "requant_stage_count": summary["requant_stage_count"],
            "w3_exact_stage_count": summary[
                "standard_w3_golden_exact_stage_count"
            ],
            "zero_point_zero_compatible_stage_count": summary[
                "zero_output_zero_point_stage_count"
            ],
            "nonzero_zero_point_guard_contradicted_stage_count": summary[
                "nonzero_output_zero_point_stage_count"
            ],
            "odd_nonzero_zero_point_stage_count": summary[
                "odd_nonzero_output_zero_point_stage_count"
            ],
            "even_nonzero_zero_point_stage_count": summary[
                "even_nonzero_output_zero_point_stage_count"
            ],
            "physical_e2_materialized_stage_count": summary[
                "full_materialized_local_e2_stage_count"
            ],
            "physical_e2_materialized_request_ids": ["r5:hwop-0001-01"],
            "formal_dynamic_pass_count": 0,
            "w3_halfway_input_count": totals["halfway"],
            "w3_lower_saturation_count": totals["lower_saturation"],
            "w3_upper_saturation_count": totals["upper_saturation"],
            "nonzero_zp_w3_halfway_input_count": totals[
                "nonzero_halfway"
            ],
            "nonzero_zp_w3_lower_saturation_count": totals[
                "nonzero_lower_saturation"
            ],
            "nonzero_zp_w3_upper_saturation_count": totals[
                "nonzero_upper_saturation"
            ],
            "signed_domain_counterexample_stage_count": len(
                signed_counterexamples
            ),
            "observed_magic_tie_counterexample_stage_count": len(
                tie_counterexamples
            ),
            "p0a_zp0_rounding_blocked_stage_count": totals[
                "p0a_zp0_rounding_blocked"
            ],
            "p0a_zp0_magic_domain_blocked_stage_count": totals[
                "p0a_zp0_magic_domain_blocked"
            ],
            "p0a_zp0_negative_w3_stage_count": totals[
                "p0a_zp0_negative_w3"
            ],
            "p0a_nonzero_even_blocked_stage_count": totals[
                "p0a_nonzero_even_blocked"
            ],
            "p0a_nonzero_odd_blocked_stage_count": totals[
                "p0a_nonzero_odd_blocked"
            ],
            "p0a_unconditional_pure_config_stage_count": 0,
        },
        "p0a_capability_dependency": {
            "source_owner": "QuantizeLinear",
            "decision": p0a_decision["decision"],
            "family_effect": (
                "54/54 software W3 exactness remains valid, but no stage is "
                "released as an unconditional shared pure-config tail"
            ),
            "first_hardware_unknown": p0a_counterexamples[
                "CE_FMA_VS_SEQUENTIAL_ROUND"
            ],
            "counterexample_mapping": [
                {
                    "counterexample_id": "CE_FMA_VS_SEQUENTIAL_ROUND",
                    "requant_scope": "ALL_54",
                    "effect": (
                        "explicit FP32 multiply rounding point is not proven "
                        "by the existing one-round GA MAC/magic candidate"
                    ),
                },
                {
                    "counterexample_id": "CE_MAGIC_DOMAIN_UNDERFLOW",
                    "requant_scope": "ALL_54",
                    "effect": (
                        "W3 bounds are observations, not a formal legal-input "
                        "finite-domain proof"
                    ),
                },
                {
                    "counterexample_id": "CE_INT32_NEGATIVE_CONVERSION",
                    "requant_scope": "ALL_54_HAVE_NEGATIVE_W3_VALUES",
                    "effect": (
                        "33 zp0 stages retain only the conditional guard "
                        "workaround; 21 nonzero stages cannot use that guard"
                    ),
                },
                {
                    "counterexample_id": "CE_ODD_ZP_TIE_PARITY",
                    "requant_scope": "FIVE_ODD_NONZERO_ZP_STAGES",
                    "effect": (
                        "zero-point must move to the raw subtract constant; "
                        "node0014 independently observes the failure on W3"
                    ),
                },
                {
                    "counterexample_id": (
                        "CE_FP32_DIVISION_VS_RECIPROCAL_FMA"
                    ),
                    "requant_scope": "SHARED_CONTRACT_ONLY_NOT_54_MULTIPLIERS",
                    "effect": (
                        "does not classify Requant multiplier stages, but "
                        "prevents Requant evidence from closing QuantizeLinear"
                    ),
                },
            ],
            "zp0_partition": {
                "stage_count": 33,
                "w3_numeric_compatible_count": 33,
                "still_blocked_by_fma_rounding_boundary_count": 33,
                "still_blocked_by_magic_domain_bound_count": 33,
                "negative_w3_seen_count": 33,
                "formal_release_count": 0,
            },
            "nonzero_partition": {
                "stage_count": 21,
                "even_zp_signed_rounding_domain_blocked_count": 16,
                "odd_zp_signed_rounding_domain_tie_blocked_count": 5,
                "observed_w3_tie_failure_stage_ids": [
                    "r5:hwop-0014-01"
                ],
                "formal_release_count": 0,
            },
            "p0a_rule_dependency_ids": [
                item["proposal_id"] for item in p0a["rule_delta_proposal"]
            ],
            "p0a_blocker_dependency_ids": list(
                p0a["blocker_delta"]["add"]
            ),
            "new_family_rule_or_blocker_proposed_by_this_mapping": False,
        },
        "classification_axes": {
            "numeric_recipe": {
                "exact_all_54": True,
                "current_node0001_guard_compatible_only_for_zp0": True,
                "nonzero_zp_is_a_numeric_recipe_problem": True,
            },
            "shape_layout": {
                "rank4_node0001_materialized": True,
                "other_rank4_shapes_require_independent_address_proof": True,
                "rank2_matmul_not_covered_by_hwc8": True,
            },
            "transaction": {
                "all_forecasts_are_planning_only": True,
                "tail_and_shard_counts_do_not_authorize_emission": True,
            },
            "lifetime": {
                "node0001_alias_barrier_sca_lifetime_proven_at_e2": True,
                "no_cross_shape_lifetime_extrapolation": True,
            },
        },
        "counterexample_sets": {
            "nonzero_zp_signed_domain_one_per_stage": signed_counterexamples,
            "observed_tie_parity": tie_counterexamples,
            "saturation_representatives": {
                "nonzero_zp_lower_observed": lower_saturation_examples,
                "nonzero_zp_upper_observed": upper_saturation_examples,
                "all_stage_lower_observed": (
                    all_stage_lower_saturation_examples
                ),
                "coverage": {
                    "nonzero_zp_lower_observed_count": totals[
                        "nonzero_lower_saturation"
                    ],
                    "nonzero_zp_upper_observed_count": totals[
                        "nonzero_upper_saturation"
                    ],
                    "lower_clip_semantics_still_required": True,
                    "no_synthetic_sample_is_presented_as_w3": True,
                },
            },
            "interpretation": {
                "signed_domain": (
                    "21/21 nonzero-zp stages contradict the zp0 clamp recipe"
                ),
                "tie_parity": (
                    "node0014 has observed W3 mismatches when odd zp=123 is "
                    "added inside magic rounding; absence on another W3 tensor "
                    "is not a proof of generic correctness"
                ),
                "saturation": (
                    "clipping is after nearest-even rounding and integer "
                    "zero-point addition; nonzero-zp W3 observes upper but "
                    "not lower saturation, while zp0 W3 observes lower "
                    "saturation"
                ),
            },
        },
        "stage_evidence": stage_evidence,
        "node0001_physical_e2_oracle": {
            "request_id": "r5:hwop-0001-01",
            "evidence_level": "LOCAL_E2",
            "boundary": node0001_e2["boundary"],
            "full_w3_bit_exact": node0001_e2["numeric_evidence"][
                "full_w3_bit_exact"
            ],
            "strict_json_valid": node0001_e2["materialized_roundtrip"][
                "all_materialized_json_strict_valid"
            ],
            "bitstream_decoded_stage_count": node0001_e2[
                "materialized_roundtrip"
            ]["bitstream_decoded_stage_count"],
            "native_double_rebuild_byte_identical": node0001_e2[
                "native_double_rebuild"
            ]["deterministic_files_byte_identical"],
            "candidate_release": False,
            "counts_as_e4": False,
            "counts_as_e5": False,
        },
        "matmul_requant_case": {
            "request_id": matmul["request_id"],
            "logical_shape": matmul["logical_shape"],
            "y_zero_point": matmul["qparams"]["y_zero_point"],
            "zero_point_parity": matmul["qparams"]["zero_point_parity"],
            "w3_exact": matmul["w3"]["exact_recipe_proven"],
            "current_guard_mismatch_count": matmul["w3"][
                "node0001_guard_recipe_mismatch_count"
            ],
            "numeric_problem_kind": matmul["numeric_problem_kind"],
            "layout_problem_kind": matmul["shape_layout"]["classification"],
            "interpretation": (
                "zp=60 is even, so this W3 payload has no observed odd-zp "
                "magic tie mismatch; it still refutes signed-domain clamping "
                "and independently requires a rank-2 layout contract"
            ),
        },
        "average_requant_input": {
            "consumer": "AverageRequantizeUint8",
            "source_operator": "QLinearGlobalAveragePool",
            "target_specialization": average_assessment[
                "target_specialization"
            ],
            "numeric_tail_reuse": (
                "INT32 sum to exact zp0 UINT8 tail is numerically compatible "
                "with the proven order, conditional on its exact multiplier"
            ),
            "problem_kind": "PHYSICAL_COMPOSITE_MATERIALIZATION",
            "pending": [
                "sum-to-tail typed transport",
                "mapper and address binding",
                "accumulator state and producer-consumer lifetime",
                "shape-49 transaction control",
            ],
            "not_a_requant_numeric_counterexample": True,
        },
        "shape_holdout_planning": {
            "priority": "LOWER_THAN_SHARED_QUANT_TAIL",
            "evidence_level": "LOCAL_E2_PLANNING_ONLY",
            "holdouts": [
                {
                    "representative_request_id": item[
                        "representative_request_id"
                    ],
                    "logical_shape": item["logical_shape"],
                    "same_shape_request_count": item[
                        "same_shape_request_count"
                    ],
                    "status": item["status"],
                }
                for item in holdouts["holdouts"]
            ],
            "no_operator_json_generated": True,
        },
        "quant_tail_evidence_input": {
            "accept": [
                "54 exact INT32-input W3 oracles",
                "nearest-even then integer zero-point then UINT8 saturation",
                "21 signed-domain counterexamples",
                "odd-zp tie-parity counterexample",
                "node0001 physical E2 as a zp0 rank4 transport oracle",
                "MatMul zp60 as numeric-plus-layout split evidence",
            ],
            "must_not_infer": [
                "FP32 ingress closure",
                "generic nonzero-zp support from the node0001 guard",
                "rank2 layout from rank4 HWC8",
                "shape schedule or lifetime from numeric exactness",
                "E4/E5 or candidate release",
            ],
            "p0a_dependency_consumed": True,
            "unconditional_pure_config_proven": False,
        },
        "rule_delta_proposal": {
            "proposal_only": True,
            "add": [
                {
                    "id": "CDA-QUANT-TAIL-RNE-ADD-ZP-SATURATE-001",
                    "text": (
                        "Exact UINT8 quant tails shall perform FP32 multiply, "
                        "nearest-even rounding, integer-domain zero-point add, "
                        "then UINT8 saturation in that order."
                    ),
                    "evidence": (
                        "54/54 W3 exact plus node0014 odd-zp tie counterexample"
                    ),
                },
                {
                    "id": "CDA-QUANT-TAIL-NUMERIC-PHYSICAL-SPLIT-001",
                    "text": (
                        "Numeric recipe closure shall not authorize a target "
                        "shape/layout/transaction/lifetime materialization."
                    ),
                    "evidence": "33 zp0 compatible but only node0001 physical E2",
                },
                {
                    "id": "CDA-QUANT-TAIL-INGRESS-TYPED-001",
                    "text": (
                        "INT32 and FP32 ingress variants require distinct typed "
                        "capability evidence; INT32 Requant evidence cannot "
                        "close QuantizeLinear FP32 ingress."
                    ),
                    "evidence": "this family evidence is INT32 ingress only",
                },
            ],
            "rules_modified": False,
        },
        "blocker_delta": {
            "close": [],
            "keep": [
                "B_REQUANT_NONZERO_ZP_SIGNED_DOMAIN",
                "B_REQUANT_MAGIC_ZP_TIE_PARITY",
                "B_REQUANT_MATMUL_2D_LAYOUT",
                "B_REQUANT_SHAPE_LIFETIME_MATERIALIZED_E2",
                "B_REQUANT_SERVER_E4_E5",
            ],
            "consume_p0a_dependency_if_mainline_approves": list(
                p0a["blocker_delta"]["add"]
            ),
            "add": [],
            "interpretation": (
                "server E4/E5 remains historically open but is not a "
                "prerequisite for the P0-A numeric/typed quant-tail contract"
            ),
        },
        "boundaries": {
            "machine_readable_evidence_only": True,
            "new_operator_json_generated": False,
            "new_server_package_generated": False,
            "server_inspected_uploaded_or_run": False,
            "dynamic_narrow_probe_continued": False,
            "event_edge_packages_modified": False,
            "rtl_modified": False,
            "formal_target_instance_allowed": False,
            "candidate_release": False,
            "counts_as_e4": False,
            "counts_as_e5": False,
        },
    }
    evidence["evidence_sha256"] = _self_hash(evidence, "evidence_sha256")
    validate_evidence_input(evidence)
    return evidence


def validate_evidence_input(value: Mapping[str, Any]) -> None:
    if value.get("schema") != SCHEMA:
        raise EvidenceInputError("schema differs")
    if value.get("evidence_sha256") != _self_hash(value, "evidence_sha256"):
        raise EvidenceInputError("self hash differs")
    rule_receipts = value.get("active_rule_receipts")
    if not isinstance(rule_receipts, list) or len(rule_receipts) != 3:
        raise EvidenceInputError("active rule receipt set differs")
    rule_sha_by_path = {
        item.get("path"): item.get("sha256")
        for item in rule_receipts
        if isinstance(item, Mapping)
    }
    if rule_sha_by_path != ACTIVE_RULE_SHA256:
        raise EvidenceInputError("active rule SHA receipt differs")
    rule_integration = value.get("active_rule_integration", {})
    if (
        rule_integration.get("shared_quant_tail_rules_approved") is not True
        or rule_integration.get("requant_magic_rule_scope")
        != "NODE0001_FORMAL_W3_DOMAIN_CONDITIONAL_LOCAL_E2_ONLY"
        or rule_integration.get("family_semantic_classification_changed")
        is not False
    ):
        raise EvidenceInputError("active rule integration boundary differs")
    summary = value.get("summary", {})
    expected = {
        "requant_stage_count": 54,
        "w3_exact_stage_count": 54,
        "zero_point_zero_compatible_stage_count": 33,
        "nonzero_zero_point_guard_contradicted_stage_count": 21,
        "odd_nonzero_zero_point_stage_count": 5,
        "even_nonzero_zero_point_stage_count": 16,
        "physical_e2_materialized_stage_count": 1,
        "formal_dynamic_pass_count": 0,
        "signed_domain_counterexample_stage_count": 21,
        "observed_magic_tie_counterexample_stage_count": 1,
        "p0a_zp0_rounding_blocked_stage_count": 33,
        "p0a_zp0_magic_domain_blocked_stage_count": 33,
        "p0a_zp0_negative_w3_stage_count": 33,
        "p0a_nonzero_even_blocked_stage_count": 16,
        "p0a_nonzero_odd_blocked_stage_count": 5,
        "p0a_unconditional_pure_config_stage_count": 0,
    }
    if any(summary.get(key) != expected_value for key, expected_value in expected.items()):
        raise EvidenceInputError("closed family totals differ")
    stages = value.get("stage_evidence")
    if not isinstance(stages, list) or len(stages) != 54:
        raise EvidenceInputError("stage evidence set differs")
    ids = [item.get("request_id") for item in stages]
    if len(set(ids)) != 54:
        raise EvidenceInputError("stage evidence IDs are not unique")
    materialized = [
        item["request_id"]
        for item in stages
        if item["physical_materialization_classification"]
        == "PHYSICAL_E2_COMPLETE_CONFIG_BOUND"
    ]
    if materialized != ["r5:hwop-0001-01"]:
        raise EvidenceInputError("node0001 physical boundary differs")
    p0a = value.get("p0a_capability_dependency", {})
    if (
        p0a.get("decision") != "NO_UNCONDITIONAL_PURE_CONFIG_PROVEN"
        or p0a.get("zp0_partition", {}).get(
            "still_blocked_by_fma_rounding_boundary_count"
        )
        != 33
        or p0a.get("zp0_partition", {}).get(
            "still_blocked_by_magic_domain_bound_count"
        )
        != 33
        or p0a.get("nonzero_partition", {}).get(
            "even_zp_signed_rounding_domain_blocked_count"
        )
        != 16
        or p0a.get("nonzero_partition", {}).get(
            "odd_zp_signed_rounding_domain_tie_blocked_count"
        )
        != 5
    ):
        raise EvidenceInputError("P0-A dependency mapping differs")
    first_unknown = p0a.get("first_hardware_unknown", {})
    if (
        first_unknown.get("id") != "CE_FMA_VS_SEQUENTIAL_ROUND"
        or first_unknown.get("inputs", {}).get("int32") != 400
        or first_unknown.get("inputs", {}).get("multiplier_bits")
        != "0x3d828f5c"
        or first_unknown.get("expected_sequential_uint8") != 26
        or first_unknown.get("one_round_fused_model_uint8") != 25
    ):
        raise EvidenceInputError("P0-A first hardware unknown differs")
    tie = value["counterexample_sets"]["observed_tie_parity"]
    if (
        len(tie) != 1
        or tie[0]["request_id"] != "r5:hwop-0014-01"
        or tie[0]["y_zero_point"] != 123
    ):
        raise EvidenceInputError("odd-zp tie counterexample differs")
    matmul = value.get("matmul_requant_case", {})
    if (
        matmul.get("request_id") != "r5:hwop-0075-01"
        or matmul.get("y_zero_point") != 60
        or matmul.get("current_guard_mismatch_count") != 8272
    ):
        raise EvidenceInputError("MatMul requant evidence differs")
    boundaries = value.get("boundaries", {})
    prohibited = (
        boundaries.get("new_operator_json_generated"),
        boundaries.get("new_server_package_generated"),
        boundaries.get("server_inspected_uploaded_or_run"),
        boundaries.get("dynamic_narrow_probe_continued"),
        boundaries.get("event_edge_packages_modified"),
        boundaries.get("rtl_modified"),
        boundaries.get("formal_target_instance_allowed"),
        boundaries.get("candidate_release"),
        boundaries.get("counts_as_e4"),
        boundaries.get("counts_as_e5"),
    )
    if any(prohibited):
        raise EvidenceInputError("evidence boundary was overclaimed")


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_receipt(project_root: Path, evidence: Mapping[str, Any]) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema": "requant-quant-tail-evidence-generation-receipt-v1",
        "scope": "machine-readable P1-B evidence only; no operator JSON/package/server",
        "output": {
            "path": OUTPUT_PATH.as_posix(),
            "evidence_sha256": evidence["evidence_sha256"],
        },
        "control_read_receipts": evidence["control_read_receipts"],
        "control_receipt_policy": evidence["control_receipt_policy"],
        "active_rule_receipts": evidence["active_rule_receipts"],
        "semantic_source_receipts": evidence["semantic_source_receipts"],
        "boundaries": evidence["boundaries"],
    }
    receipt["receipt_sha256"] = _self_hash(receipt, "receipt_sha256")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    evidence = build_evidence_input(root)
    if args.check:
        on_disk = _load(root / OUTPUT_PATH)
        validate_evidence_input(on_disk)
        evidence["control_read_receipts"] = on_disk[
            "control_read_receipts"
        ]
        evidence["control_receipt_policy"] = on_disk[
            "control_receipt_policy"
        ]
        evidence["evidence_sha256"] = _self_hash(
            evidence, "evidence_sha256"
        )
        if on_disk != evidence:
            raise EvidenceInputError("on-disk evidence is stale")
    else:
        write_json(root / OUTPUT_PATH, evidence)
        write_json(root / RECEIPT_PATH, build_receipt(root, evidence))
    print(
        json.dumps(
            {
                "status": evidence["status"],
                "output": OUTPUT_PATH.as_posix(),
                "evidence_sha256": evidence["evidence_sha256"],
                "summary": evidence["summary"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
