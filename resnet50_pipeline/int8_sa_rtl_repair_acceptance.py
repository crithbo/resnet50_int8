from __future__ import annotations

import hashlib
import itertools
import json
import struct
from pathlib import Path
from typing import Any, Iterable

from resnet50_pipeline.int8_sa_dot_product_adjudication import (
    conventional_dot,
    sha256_file,
    stock_rtl_sa_chunk,
    stock_rtl_sa_dot,
)


INT32_MIN = -(1 << 31)
INT32_MAX = (1 << 31) - 1


def _signed(value: int, width: int) -> int:
    value &= (1 << width) - 1
    return value - (1 << width) if value & (1 << (width - 1)) else value


def _u32(value: int) -> int:
    return value & 0xFFFFFFFF


def _hex32(value: int) -> str:
    return f"0x{_u32(value):08x}"


def _validate_operands(
    signed_weights: Iterable[int], unsigned_activations: Iterable[int]
) -> tuple[list[int], list[int]]:
    weights = [int(value) for value in signed_weights]
    activations = [int(value) for value in unsigned_activations]
    if len(weights) != len(activations):
        raise ValueError("weight and activation lengths differ")
    if any(value < -128 or value > 127 for value in weights):
        raise ValueError("weights must fit signed int8")
    if any(value < 0 or value > 255 for value in activations):
        raise ValueError("activations must fit uint8")
    return weights, activations


def _pack_msb_first(values: list[int]) -> str:
    padded = values + [0] * (4 - len(values))
    word = 0
    for value in padded:
        word = (word << 8) | (value & 0xFF)
    return f"0x{word:08x}"


def proposal_signed18_chunk(
    signed_weights: Iterable[int],
    unsigned_activations: Iterable[int],
    psum32: int = 0,
) -> dict[str, Any]:
    """Bit-exact model of the proposed INT8-only signed18 repair."""

    weights, activations = _validate_operands(signed_weights, unsigned_activations)
    if not 1 <= len(weights) <= 4:
        raise ValueError("one repaired SA occurrence accepts one to four paired lanes")
    padded_weights = weights + [0] * (4 - len(weights))
    padded_activations = activations + [0] * (4 - len(activations))
    products = [
        weight * activation
        for weight, activation in zip(padded_weights, padded_activations)
    ]
    pair01 = products[0] + products[1]
    pair23 = products[2] + products[3]
    dot4 = pair01 + pair23
    if not -(1 << 16) <= pair01 <= (1 << 16) - 1:
        raise AssertionError("pair01 does not fit signed17")
    if not -(1 << 16) <= pair23 <= (1 << 16) - 1:
        raise AssertionError("pair23 does not fit signed17")
    if not -(1 << 17) <= dot4 <= (1 << 17) - 1:
        raise AssertionError("dot4 does not fit signed18")
    result = _signed(_u32(psum32) + _u32(dot4), 32)
    return {
        "weight_word_msb_first": _pack_msb_first(padded_weights),
        "activation_word_msb_first": _pack_msb_first(padded_activations),
        "products_s16": products,
        "pair01_s17": pair01,
        "pair23_s17": pair23,
        "dot4_s18": dot4,
        "psum_in_s32": _signed(psum32, 32),
        "psum_in_bits": _hex32(psum32),
        "result_s32": result,
        "result_bits": _hex32(result),
        "tail_lane_count": len(weights),
    }


def proposal_signed18_dot(
    signed_weights: Iterable[int],
    unsigned_activations: Iterable[int],
    *,
    x_zero_point: int = 0,
    bias: int = 0,
) -> tuple[int, list[dict[str, Any]], int]:
    weights, activations = _validate_operands(signed_weights, unsigned_activations)
    if not weights:
        raise ValueError("dot product must contain at least one product")
    corrected_initial_psum = bias - x_zero_point * sum(weights)
    psum = _signed(corrected_initial_psum, 32)
    occurrences = []
    for offset in range(0, len(weights), 4):
        occurrence = proposal_signed18_chunk(
            weights[offset : offset + 4],
            activations[offset : offset + 4],
            psum,
        )
        occurrence["occurrence_index"] = len(occurrences)
        occurrences.append(occurrence)
        psum = occurrence["result_s32"]
    return psum, occurrences, _signed(corrected_initial_psum, 32)


def compare_three_models(
    signed_weights: Iterable[int],
    unsigned_activations: Iterable[int],
    *,
    x_zero_point: int = 0,
    bias: int = 0,
) -> dict[str, Any]:
    weights, activations = _validate_operands(signed_weights, unsigned_activations)
    expected = conventional_dot(
        weights, activations, x_zero_point=x_zero_point, bias=bias
    )
    stock = stock_rtl_sa_dot(
        weights,
        activations,
        x_zero_point=x_zero_point,
        bias=bias,
        apply_static_xzp_bias_correction=True,
    )
    proposal, occurrences, initial_psum = proposal_signed18_dot(
        weights,
        activations,
        x_zero_point=x_zero_point,
        bias=bias,
    )
    serialized = stock_rtl_sa_dot(
        weights,
        activations,
        x_zero_point=x_zero_point,
        bias=bias,
        apply_static_xzp_bias_correction=True,
        serialize_one_product_per_occurrence=True,
    )
    return {
        "target": {"s32": expected, "bits": _hex32(expected)},
        "models": {
            "stock_four_lane": {
                "s32": stock,
                "bits": _hex32(stock),
                "matches_target": stock == expected,
            },
            "proposal_signed18": {
                "s32": proposal,
                "bits": _hex32(proposal),
                "matches_target": proposal == expected,
            },
            "serialized_one_product": {
                "s32": serialized,
                "bits": _hex32(serialized),
                "matches_target": serialized == expected,
            },
        },
        "static_xzp_corrected_initial_psum_s32": initial_psum,
        "proposal_occurrences": occurrences,
    }


def _acceptance_case(
    case_id: str,
    weights: list[int],
    activations: list[int],
    *,
    x_zero_point: int = 0,
    bias: int = 0,
    purpose: str,
) -> dict[str, Any]:
    comparison = compare_three_models(
        weights,
        activations,
        x_zero_point=x_zero_point,
        bias=bias,
    )
    return {
        "case_id": case_id,
        "purpose": purpose,
        "K": len(weights),
        "weights_s8": weights,
        "activations_u8": activations,
        "x_zero_point_u8": x_zero_point,
        "bias_s32": bias,
        **comparison,
    }


def run_small_domain_exhaustive() -> dict[str, Any]:
    pair_domain = tuple(itertools.product((-3, 0, 3), (0, 1, 7)))
    biases = (0, -11, INT32_MAX)
    zero_points = (0, 2)
    digest = hashlib.sha256()
    case_count = 0
    stock_mismatch_count = 0
    first_stock_mismatch = None
    for length in (1, 2, 3, 4):
        for pairs in itertools.product(pair_domain, repeat=length):
            weights = [pair[0] for pair in pairs]
            activations = [pair[1] for pair in pairs]
            for x_zero_point in zero_points:
                for bias in biases:
                    comparison = compare_three_models(
                        weights,
                        activations,
                        x_zero_point=x_zero_point,
                        bias=bias,
                    )
                    target = comparison["target"]["s32"]
                    stock = comparison["models"]["stock_four_lane"]["s32"]
                    proposal = comparison["models"]["proposal_signed18"]["s32"]
                    serialized = comparison["models"]["serialized_one_product"]["s32"]
                    if proposal != target or serialized != target:
                        raise AssertionError("a correctness model diverged in exhaustive proof")
                    if stock != target:
                        stock_mismatch_count += 1
                        if first_stock_mismatch is None:
                            first_stock_mismatch = {
                                "weights_s8": weights,
                                "activations_u8": activations,
                                "x_zero_point_u8": x_zero_point,
                                "bias_s32": bias,
                                "target_s32": target,
                                "stock_s32": stock,
                            }
                    digest.update(
                        struct.pack(
                            "<9i",
                            length,
                            x_zero_point,
                            bias,
                            target,
                            stock,
                            proposal,
                            serialized,
                            sum(weights),
                            sum(activations),
                        )
                    )
                    case_count += 1
    return {
        "status": "PASS",
        "weights_s8": [-3, 0, 3],
        "activations_u8": [0, 1, 7],
        "K": [1, 2, 3, 4],
        "bias_s32": list(biases),
        "x_zero_point_u8": list(zero_points),
        "case_count": case_count,
        "proposal_mismatch_count": 0,
        "serialized_mismatch_count": 0,
        "stock_mismatch_count": stock_mismatch_count,
        "first_stock_mismatch": first_stock_mismatch,
        "ordered_observation_sha256": digest.hexdigest(),
    }


def run_legal_boundary_proof() -> dict[str, Any]:
    single_product_count = 0
    for weight in range(-128, 128):
        for activation in range(256):
            expected = conventional_dot([weight], [activation], bias=INT32_MAX)
            proposal, _, _ = proposal_signed18_dot(
                [weight], [activation], bias=INT32_MAX
            )
            serialized = stock_rtl_sa_dot(
                [weight],
                [activation],
                bias=INT32_MAX,
                apply_static_xzp_bias_correction=True,
                serialize_one_product_per_occurrence=True,
            )
            if proposal != expected or serialized != expected:
                raise AssertionError("single-product legal-domain proof failed")
            single_product_count += 1

    corner_pairs = tuple(itertools.product((-128, 127), (0, 255)))
    four_lane_corner_count = 0
    minimum_dot4 = 0
    maximum_dot4 = 0
    for pairs in itertools.product(corner_pairs, repeat=4):
        weights = [pair[0] for pair in pairs]
        activations = [pair[1] for pair in pairs]
        expected = conventional_dot(weights, activations)
        proposal, occurrences, _ = proposal_signed18_dot(weights, activations)
        serialized = stock_rtl_sa_dot(
            weights,
            activations,
            apply_static_xzp_bias_correction=True,
            serialize_one_product_per_occurrence=True,
        )
        if proposal != expected or serialized != expected:
            raise AssertionError("four-lane corner proof failed")
        dot4 = occurrences[0]["dot4_s18"]
        minimum_dot4 = min(minimum_dot4, dot4)
        maximum_dot4 = max(maximum_dot4, dot4)
        four_lane_corner_count += 1
    if minimum_dot4 != -130560 or maximum_dot4 != 129540:
        raise AssertionError("legal signed18 extrema were not reached")
    return {
        "status": "PASS",
        "single_product_full_domain": {
            "weight_range": [-128, 127],
            "activation_range": [0, 255],
            "bias_s32": INT32_MAX,
            "case_count": single_product_count,
        },
        "four_lane_corner_cross_product": {
            "weight_values": [-128, 127],
            "activation_values": [0, 255],
            "case_count": four_lane_corner_count,
            "observed_dot4_s18_range": [minimum_dot4, maximum_dot4],
            "signed18_range": [-(1 << 17), (1 << 17) - 1],
        },
    }


def build_int8_sa_rtl_repair_acceptance(project_root: Path) -> dict[str, Any]:
    cases = [
        _acceptance_case(
            "carry_duplicate_positive",
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            purpose="duplicate-carry-shift positive witness",
        ),
        _acceptance_case(
            "carry_duplicate_negative",
            [-1, -1, -1, -1],
            [1, 1, 1, 1],
            purpose="duplicate-carry-shift negative witness",
        ),
        _acceptance_case(
            "signed18_positive_extreme",
            [127, 127, 127, 127],
            [255, 255, 255, 255],
            purpose="positive legal dot4 extreme and signed17 overflow",
        ),
        _acceptance_case(
            "signed18_negative_extreme",
            [-128, -128, -128, -128],
            [255, 255, 255, 255],
            purpose="negative legal dot4 extreme and signed17 overflow",
        ),
        _acceptance_case(
            "psum_positive_wrap",
            [1],
            [1],
            bias=INT32_MAX,
            purpose="INT32_MAX plus one wraps modulo 2^32",
        ),
        _acceptance_case(
            "psum_negative_wrap",
            [-1],
            [1],
            bias=INT32_MIN,
            purpose="INT32_MIN minus one wraps modulo 2^32",
        ),
        _acceptance_case(
            "tail_k3_bias_on",
            [1, -2, 3],
            [4, 5, 6],
            bias=7,
            purpose="three-lane tail and bias initialization",
        ),
        _acceptance_case(
            "tail_k5",
            [1, -2, 3, -4, 5],
            [6, 7, 8, 9, 10],
            purpose="full occurrence followed by one-lane tail",
        ),
        _acceptance_case(
            "tail_k6",
            [1, -2, 3, -4, 5, -6],
            [6, 7, 8, 9, 10, 11],
            purpose="full occurrence followed by two-lane tail",
        ),
        _acceptance_case(
            "tail_k7",
            [1, -2, 3, -4, 5, -6, 7],
            [6, 7, 8, 9, 10, 11, 12],
            purpose="full occurrence followed by three-lane tail",
        ),
        _acceptance_case(
            "nonzero_xzp_bias_on",
            [3, -2, 1, 5, -7],
            [120, 114, 130, 90, 200],
            x_zero_point=114,
            bias=-123456,
            purpose="static input-zero-point correction plus bias and K tail",
        ),
    ]
    if not all(
        case["models"]["proposal_signed18"]["matches_target"] for case in cases
    ):
        raise AssertionError("proposal signed18 failed an acceptance vector")
    if not all(
        case["models"]["serialized_one_product"]["matches_target"] for case in cases
    ):
        raise AssertionError("serialized baseline failed an acceptance vector")

    positive_stock = stock_rtl_sa_chunk([1, 1, 1, 1], [1, 1, 1, 1])
    positive_narrow17 = _signed(4 * 127 * 255, 17)
    negative_narrow17 = _signed(4 * -128 * 255, 17)
    receipt_paths = [
        (".agents/plan.md", "current P0-B status and stop gate"),
        (".agents/rules/生成前必读索引.md", "generation routing"),
        (".agents/rules/INT8_SA点积专项规则.md", "operator-family acceptance gate"),
        (
            "contracts/operator_config/int8_sa_dot_product_adjudication_v1.json",
            "accepted common-cause adjudication",
        ),
        (
            "resnet50_pipeline/int8_sa_dot_product_adjudication.py",
            "stock CSA replay and serialized baseline",
        ),
        (
            "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
            "SA_PE_Mul_Array.v",
            "read-only defect consumer and proposed repair boundary",
        ),
        (
            "NDP_copy01/rtl/utils/CSA/CSA_4to2.v",
            "read-only first compressor carry semantics",
        ),
        (
            "NDP_copy01/rtl/utils/CSA/CSA_3to2.v",
            "read-only psum compressor semantics",
        ),
    ]
    receipts = [
        {
            "path": path,
            "sha256": sha256_file(project_root / path),
            "reason": reason,
        }
        for path, reason in receipt_paths
    ]
    receipt_sha = {item["path"]: item["sha256"] for item in receipts}
    return {
        "schema": "resnet50-int8-sa-rtl-repair-acceptance-v1",
        "status": "LOCAL_BIT_EXACT_PROOF_PASS_RTL_IDENTITY_PENDING",
        "candidate_release": False,
        "server_package_allowed": False,
        "functional_rtl_modified": False,
        "target_json_generated": False,
        "receipt_policy": {
            "active_rule_current_match": [
                {
                    "path": ".agents/rules/INT8_SA点积专项规则.md",
                    "sha256": receipt_sha[
                        ".agents/rules/INT8_SA点积专项规则.md"
                    ],
                    "current_match_required": True,
                    "on_mismatch": "FAIL_CLOSED",
                }
            ],
            "routing_generation_receipt": {
                "path": ".agents/rules/生成前必读索引.md",
                "sha256": receipt_sha[".agents/rules/生成前必读索引.md"],
                "current_match_required": False,
            },
            "mutable_provenance": [
                {
                    "path": ".agents/plan.md",
                    "sha256_at_generation": receipt_sha[".agents/plan.md"],
                    "current_match_required": False,
                    "meaning": "historical mutable provenance only",
                }
            ],
        },
        "rule_ids": [
            "CDA-SA-INT8-DOT-ARITHMETIC-RANGE-001",
            "CDA-SA-INT8-SERIALIZED-FALLBACK-001",
            "CDA-SA-INT8-RTL-COMPATIBILITY-001",
            "CDA-SA-INT8-CONV-MATMUL-COMMON-GATE-001",
        ],
        "known_counterexamples": [
            {
                "id": "stock-four-ones",
                "target_s32": 4,
                "stock_s32": 6,
            },
            {
                "id": "signed17-positive-range",
                "target_s32": 129540,
                "signed17_narrowed_s32": positive_narrow17,
            },
            {
                "id": "signed17-negative-range",
                "target_s32": -130560,
                "signed17_narrowed_s32": negative_narrow17,
            },
        ],
        "open_dynamic_gates": [
            "explicit compatible RTL identity input",
            "identity-bound independent RTL testbench",
            "occurrence-by-occurrence bit-exact RTL comparison",
        ],
        "scope": {
            "shared_stage_families": [
                "QLinearConvInt32Accumulate",
                "QLinearMatMulInt32Accumulate",
            ],
            "purpose": (
                "acceptance contract for a future user-provided or explicitly authorized "
                "compatible RTL identity"
            ),
        },
        "model_columns": [
            {
                "id": "stock_four_lane",
                "role": "contradicted negative control",
                "equation": (
                    "stock CSA_4to2 carry handoff plus signed17 reduction, with static "
                    "x_zero_point bias correction"
                ),
            },
            {
                "id": "proposal_signed18",
                "role": "future compatible RTL acceptance oracle",
                "equation": (
                    "signed17 pair01 + signed17 pair23 -> signed18 dot4; "
                    "int32_result=(psum32+signext32(dot4)) mod 2^32"
                ),
            },
            {
                "id": "serialized_one_product",
                "role": "stock-RTL correctness baseline",
                "equation": (
                    "at most one nonzero product lane per occurrence, accumulating psum32 "
                    "modulo 2^32"
                ),
            },
        ],
        "defect_proofs": {
            "duplicate_carry_shift": {
                "input": "four lanes of 1*1, psum32=0",
                "sum17": positive_stock["sum17"],
                "carry17_already_shifted": positive_stock["carry17"],
                "ordinary": 4,
                "stock": positive_stock["result"],
                "status": "STOCK_FAIL_PROPOSAL_PASS",
            },
            "signed17_width": {
                "positive_dot4": 4 * 127 * 255,
                "positive_if_narrowed_to_signed17": positive_narrow17,
                "negative_dot4": 4 * -128 * 255,
                "negative_if_narrowed_to_signed17": negative_narrow17,
                "status": "SIGNED18_REQUIRED",
            },
        },
        "acceptance_vectors": cases,
        "small_domain_exhaustive": run_small_domain_exhaustive(),
        "legal_boundary_proof": run_legal_boundary_proof(),
        "future_rtl_identity_input_interface": {
            "authorization": "USER_PROVIDED_OR_EXPLICITLY_AUTHORIZED_ONLY",
            "required_fields": [
                "identity_label",
                "immutable_source_manifest_with_sha256",
                "top_module_and_int8_repair_module_binding",
                "local_compile_or_simulator_command",
                "testbench_adapter_mapping DataA/DataB/DataC/result and valid timing",
            ],
            "required_semantics": [
                "DataA packs four signed int8 weights",
                "DataB packs four unsigned uint8 activations",
                "DataC is signed int32 psum bits",
                "result equals signed18 dot4 plus psum32 modulo 2^32",
                "one to three zero-padded tail lanes are neutral",
            ],
            "forbidden_automatic_discovery": [
                "server filesystem paths",
                "server directory names",
                "current server RTL identity",
                "server package or return artifacts",
            ],
            "current_binding": None,
        },
        "acceptance_gate": {
            "local_contract_pass_requires": [
                "all proposal_signed18 acceptance vectors match target bits",
                "small-domain exhaustive proposal mismatch count is zero",
                "full single-product legal domain passes",
                "four-lane signed18 legal extrema are reached and pass",
                "psum32 positive and negative wrap cases pass",
                "K tail 1/2/3 lanes, bias and nonzero x_zero_point pass",
            ],
            "future_rtl_pass_requires": [
                "an explicitly supplied compatible RTL identity",
                "the same acceptance vectors driven through an independent RTL testbench",
                "bit-exact occurrence-by-occurrence result comparison",
                "identity-bound compile and run receipts",
            ],
            "not_authorized": [
                "functional RTL edit",
                "Conv or MatMul target JSON materialization",
                "server package generation",
                "server filesystem or identity inspection",
            ],
        },
        "blocker_delta": {
            "keep": [
                "B_CONV_INT8_SA",
                "B_MATMUL_INT8_SA",
                "B_CONV_CONFIG_BOUND_SIMULATOR_RTL_CSA_MISMATCH",
                "B_CONV_STOCK_RTL_INT8_DOT_CAPABILITY",
                "B_SA_INT8_DUPLICATE_CARRY_SHIFT",
                "B_SA_INT8_REDUCTION_WIDTH",
                "B_SA_SERIALIZED_FALLBACK_MATERIALIZATION",
            ],
            "add": ["B_SA_COMPATIBLE_RTL_IDENTITY_PENDING"],
            "close": [],
        },
        "rule_delta_proposal": {
            "proposal_only": True,
            "items": [
                (
                    "A compatible INT8 SA RTL identity must pass the identity-bound repair "
                    "harness occurrence by occurrence; final-only equality is insufficient."
                ),
                (
                    "Acceptance must retain stock four-lane as a negative control and "
                    "serialized one-product as an independent correctness baseline."
                ),
                (
                    "The future RTL identity is an explicit user-supplied interface input; "
                    "its server location or current identity must never be auto-discovered."
                ),
            ],
        },
        "read_receipt": receipts,
        "omitted_files": [
            {
                "path": "server filesystem, package roots and current server identity",
                "reason": "forbidden by the P0-B local-only acceptance-contract scope",
            },
            {
                "path": "Conv/MatMul target JSON and packaging inputs",
                "reason": "materialization remains blocked by the arithmetic compatibility gate",
            },
        ],
    }


def validate_active_rule_receipts(
    project_root: Path, contract: dict[str, Any]
) -> dict[str, Any]:
    """Fail closed on active-rule drift while treating plan as mutable provenance."""

    receipt_sha = {
        item["path"]: item["sha256"] for item in contract["read_receipt"]
    }
    active_results = []
    errors = []
    for item in contract["receipt_policy"]["active_rule_current_match"]:
        path = item["path"]
        expected = item["sha256"]
        current = sha256_file(project_root / path)
        receipt_matches_policy = receipt_sha.get(path) == expected
        current_matches = current == expected
        active_results.append(
            {
                "path": path,
                "expected_sha256": expected,
                "current_sha256": current,
                "receipt_matches_policy": receipt_matches_policy,
                "current_matches": current_matches,
            }
        )
        if not item["current_match_required"] or item["on_mismatch"] != "FAIL_CLOSED":
            errors.append(f"{path}: active rule is not configured fail-closed")
        if not receipt_matches_policy:
            errors.append(f"{path}: read receipt and active-rule policy differ")
        if not current_matches:
            errors.append(f"{path}: active rule SHA no longer matches")

    mutable_results = []
    for item in contract["receipt_policy"]["mutable_provenance"]:
        path = item["path"]
        historical = item["sha256_at_generation"]
        current = sha256_file(project_root / path)
        mutable_results.append(
            {
                "path": path,
                "historical_sha256": historical,
                "current_sha256": current,
                "current_matches": current == historical,
                "current_match_required": False,
            }
        )
        if item["current_match_required"]:
            errors.append(f"{path}: mutable provenance unexpectedly requires current match")

    if contract["future_rtl_identity_input_interface"]["current_binding"] is not None:
        errors.append("future RTL identity current_binding must remain null")
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "status": "PASS",
        "active_rule_results": active_results,
        "mutable_provenance_results": mutable_results,
        "current_binding_is_null": True,
    }


def write_int8_sa_rtl_repair_acceptance(
    project_root: Path, output_path: Path
) -> dict[str, Any]:
    report = build_int8_sa_rtl_repair_acceptance(project_root)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report
