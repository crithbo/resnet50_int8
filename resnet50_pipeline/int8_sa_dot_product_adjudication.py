from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mask(width: int) -> int:
    return (1 << width) - 1


def _signed(value: int, width: int) -> int:
    value &= _mask(width)
    return value - (1 << width) if value & (1 << (width - 1)) else value


def _csa4to2(op0: int, op1: int, op2: int, op3: int, width: int) -> tuple[int, int, int]:
    """Bit-exact replay of NDP_copy01/rtl/utils/CSA/CSA_4to2.v."""

    mask = _mask(width)
    op0 &= mask
    op1 &= mask
    op2 &= mask
    op3 &= mask
    s_temp = op0 ^ op1 ^ op2 ^ op3
    cout_array = (op0 & op1) | (op0 & op2) | (op1 & op2)
    cin_array = (cout_array << 1) & mask
    sum_value = (cin_array ^ s_temp) & mask
    carry_temp = ((cin_array & s_temp) | ((~s_temp) & op3)) & mask
    carry = (carry_temp << 1) & mask
    cout = (carry_temp >> (width - 1)) & 1
    return sum_value, carry, cout


def _csa3to2(op0: int, op1: int, op2: int, width: int) -> tuple[int, int]:
    """Bit-exact replay of NDP_copy01/rtl/utils/CSA/CSA_3to2.v."""

    mask = _mask(width)
    op0 &= mask
    op1 &= mask
    op2 &= mask
    return (
        (op0 ^ op1 ^ op2) & mask,
        ((op0 & op1) | (op1 & op2) | (op0 & op2)) & mask,
    )


def stock_rtl_sa_chunk(
    signed_weights: Iterable[int],
    unsigned_activations: Iterable[int],
    psum32: int = 0,
) -> dict[str, int]:
    """Replay one four-lane stock-RTL INT8 SA FMA occurrence."""

    weights = list(signed_weights)
    activations = list(unsigned_activations)
    if len(weights) > 4 or len(activations) > 4 or len(weights) != len(activations):
        raise ValueError("one SA occurrence accepts one to four paired lanes")
    weights += [0] * (4 - len(weights))
    activations += [0] * (4 - len(activations))
    if any(value < -128 or value > 127 for value in weights):
        raise ValueError("weights must fit signed int8")
    if any(value < 0 or value > 255 for value in activations):
        raise ValueError("activations must fit uint8")

    products = [weight * activation for weight, activation in zip(weights, activations)]
    product_bits = [product & 0xFFFF for product in products]
    operands17 = [
        bits | (0x10000 if bits & 0x8000 else 0) for bits in product_bits
    ]
    sum17, carry17, cout17 = _csa4to2(*operands17, width=17)

    # SA_PE_Mul_Array.v:294-296.  carry17 returned by CSA_4to2 is already
    # shifted; this line shifts it again before the second compressor.
    last_a = _signed(sum17, 17) & 0xFFFFFFFF
    last_b = (_signed(carry17, 17) << 1) & 0xFFFFFFFF
    last_c = psum32 & 0xFFFFFFFF
    second_sum, second_carry = _csa3to2(last_a, last_b, last_c, width=32)

    # SA_PE_Mul_Array.v:320-321 and SA_PE_Float_CSA.v:45-54,77.
    out_carry = (second_carry << 1) & 0xFFFFFFFF
    result = _signed(second_sum + out_carry, 32)
    return {
        "product0": products[0],
        "product1": products[1],
        "product2": products[2],
        "product3": products[3],
        "sum17": _signed(sum17, 17),
        "carry17": _signed(carry17, 17),
        "cout17_ignored": cout17,
        "last_a": _signed(last_a, 32),
        "last_b_double_shifted": _signed(last_b, 32),
        "second_sum": _signed(second_sum, 32),
        "second_carry_unshifted": _signed(second_carry, 32),
        "result": result,
    }


def conventional_dot(
    signed_weights: Iterable[int],
    unsigned_activations: Iterable[int],
    *,
    x_zero_point: int = 0,
    bias: int = 0,
) -> int:
    total = bias + sum(
        int(weight) * (int(activation) - x_zero_point)
        for weight, activation in zip(signed_weights, unsigned_activations)
    )
    return _signed(total, 32)


def stock_rtl_sa_dot(
    signed_weights: Iterable[int],
    unsigned_activations: Iterable[int],
    *,
    x_zero_point: int = 0,
    bias: int = 0,
    apply_static_xzp_bias_correction: bool = False,
    serialize_one_product_per_occurrence: bool = False,
) -> int:
    weights = list(signed_weights)
    activations = list(unsigned_activations)
    if len(weights) != len(activations):
        raise ValueError("weight and activation lengths differ")
    psum = bias
    if apply_static_xzp_bias_correction:
        psum -= x_zero_point * sum(weights)
    step = 1 if serialize_one_product_per_occurrence else 4
    for offset in range(0, len(weights), step):
        psum = stock_rtl_sa_chunk(
            weights[offset : offset + step],
            activations[offset : offset + step],
            psum,
        )["result"]
    return psum


def _case(
    case_id: str,
    weights: list[int],
    activations: list[int],
    *,
    x_zero_point: int = 0,
    bias: int = 0,
) -> dict[str, Any]:
    expected = conventional_dot(
        weights, activations, x_zero_point=x_zero_point, bias=bias
    )
    stock = stock_rtl_sa_dot(
        weights, activations, x_zero_point=x_zero_point, bias=bias
    )
    corrected = stock_rtl_sa_dot(
        weights,
        activations,
        x_zero_point=x_zero_point,
        bias=bias,
        apply_static_xzp_bias_correction=True,
    )
    serialized = stock_rtl_sa_dot(
        weights,
        activations,
        x_zero_point=x_zero_point,
        bias=bias,
        apply_static_xzp_bias_correction=True,
        serialize_one_product_per_occurrence=True,
    )
    first_chunk = stock_rtl_sa_chunk(weights[:4], activations[:4], bias)
    return {
        "case_id": case_id,
        "K": len(weights),
        "weights_s8": weights,
        "activations_u8": activations,
        "x_zero_point": x_zero_point,
        "bias": bias,
        "ordinary_dot": expected,
        "stock_rtl_four_lane": stock,
        "stock_rtl_with_static_xzp_bias_correction": corrected,
        "stock_rtl_one_product_serialized": serialized,
        "four_lane_matches": stock == expected,
        "corrected_four_lane_matches": corrected == expected,
        "serialized_matches": serialized == expected,
        "first_chunk_internal": first_chunk,
    }


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def build_int8_sa_dot_product_adjudication(project_root: Path) -> dict[str, Any]:
    bundle_path = project_root / "contracts/resnet50_r5_lowering_bundle.json"
    bundle = _load_json(bundle_path)
    conv_requests = [
        request
        for request in bundle["requests"]
        if request["identity"]["hw_op_type"] == "ConvInt32Accumulate"
    ]
    matmul_requests = [
        request
        for request in bundle["requests"]
        if request["identity"]["hw_op_type"] == "MatMulInt32Accumulate"
    ]
    conv_xzps = []
    for request in conv_requests:
        parameter = next(
            item for item in request["typed_parameters"] if item["name"] == "x_zero_point"
        )
        conv_xzps.append(int(parameter["value"]["scalar"]))
    matmul_azp = int(
        next(
            item
            for item in matmul_requests[0]["typed_parameters"]
            if item["name"] == "a_zero_point"
        )["value"]["scalar"]
    )

    candidate_path = (
        project_root / "ndp-sim/jsons/node0004_accumulate_wave0_nopp_r1.json"
    )
    candidate = _load_json(candidate_path)
    sa = candidate["special_array"]
    parsed_path = (
        project_root
        / "artifacts/operator_config_validation/r5-server-candidates/"
        "node0004-nopp-r1-v2/config/op0/parsed_bitstream.txt"
    )
    parsed_text = parsed_path.read_text(encoding="utf-8")
    encoded_sa_line = parsed_text.split("special_array:\n", 1)[1].strip().splitlines()[0]

    cases = [
        _case("positive_no_carry_single_lane", [1], [1]),
        _case("positive_four_ones", [1, 1, 1, 1], [1, 1, 1, 1]),
        _case("negative_four_ones", [-1, -1, -1, -1], [1, 1, 1, 1]),
        _case("mixed_sign", [1, -1, 2, -2], [7, 5, 3, 1]),
        _case("intra_word_carry_two_lanes", [1, 1], [3, 1]),
        _case("odd_k3", [1, -2, 3], [4, 5, 6]),
        _case("odd_k5", [1, -2, 3, -4, 5], [6, 7, 8, 9, 10]),
        _case("positive_range_overflow17", [127, 127, 127, 127], [255] * 4),
        _case("negative_range_overflow17", [-128, -128, -128, -128], [255] * 4),
        _case("bias_on_four_ones", [1, 1, 1, 1], [1, 1, 1, 1], bias=7),
        _case("nonzero_xzp_single_lane", [1], [5], x_zero_point=3),
        _case("nonzero_xzp_three_lanes", [1, 1, 1], [5, 6, 7], x_zero_point=5),
    ]
    if not all(case["serialized_matches"] for case in cases):
        raise AssertionError("one-product serialized fallback is not exact")

    receipt_paths = [
        ".agents/plan.md",
        ".agents/task_records/20260727_ndpsim_resnet50_reuse_audit_and_replan.md",
        "contracts/operator_config/resnet50_ndpsim_reuse_gap_audit_v1.json",
        "contracts/resnet50_r5_lowering_bundle.json",
        "ndp-sim/jsons/node0004_accumulate_wave0_nopp_r1.json",
        "ndp-sim/bitstream/config/special.py",
        "ndp-sim/bitstream/config/mapper.py",
        "artifacts/operator_config_validation/r5-server-candidates/"
        "node0004-nopp-r1-v2/config/op0/parsed_bitstream.txt",
        "NDP_copy01/rtl/Slice/Specialized_Array/Specialized_Array_Config.sv",
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_Control_Block.sv",
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU.sv",
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_ALU.v",
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
        "SA_PE_Float_Control.v",
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
        "SA_PE_Mul_Array.v",
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
        "SA_PE_Float_CSA.v",
        "NDP_copy01/rtl/utils/CSA/CSA_4to2.v",
        "NDP_copy01/rtl/utils/CSA/CSA_3to2.v",
        "NDPFuncModel/component/SpecialPEA.py",
        "contracts/operator_config/gap_int32_mac_bypass_v1.json",
    ]
    receipts = [
        {"path": path, "sha256": sha256_file(project_root / path)}
        for path in receipt_paths
    ]

    return {
        "schema": "resnet50-int8-sa-dot-product-adjudication-v1",
        "status": "FIRST_DIVERGENCE_CLOSED_OPTIONS_ADJUDICATED",
        "candidate_release": False,
        "server_package_allowed": False,
        "scope": {
            "qlinearconv_accumulate_stage_count": len(conv_requests),
            "qlinearmatmul_accumulate_stage_count": len(matmul_requests),
            "conv_x_zero_point_distribution": {
                "zero": conv_xzps.count(0),
                "nonzero": len(conv_xzps) - conv_xzps.count(0),
                "nonzero_values": sorted({value for value in conv_xzps if value != 0}),
            },
            "matmul_a_zero_point": matmul_azp,
        },
        "json_to_rtl_trace": [
            {
                "boundary": "JSON",
                "evidence": {
                    "path": str(candidate_path.relative_to(project_root)).replace("\\", "/"),
                    "special_array": sa,
                },
                "adjudication": "int8/gemm selects the intended signed-A unsigned-B SA mode",
            },
            {
                "boundary": "mapper_and_bitstream",
                "evidence": {
                    "encoded_line": encoded_sa_line,
                    "mapping_does_not_transform_numeric_operands": True,
                },
                "adjudication": "data_type int8 reaches RTL as computation_data_type=2'b00",
            },
            {
                "boundary": "SA_config_and_control",
                "evidence": {
                    "mode_effect": "GEMM/GEMV changes PE enable and serialization only",
                    "bias_effect": "selects inport2 versus zero only",
                    "operand_wiring": "inport0->DataA, inport1->DataB, outbuffer psum->DataC",
                },
                "adjudication": "no opcode/config field selects an alternative integer adder",
            },
            {
                "boundary": "operand_packing",
                "evidence": {
                    "DataA": "four signed int8 lanes converted to magnitude plus sign bits",
                    "DataB": "four unsigned int8 lanes",
                    "per_lane_product": "exact signed16 for the full s8*u8 range",
                },
                "adjudication": "packing and signed/unsigned orientation match the target",
            },
            {
                "boundary": "CSA_4to2_int",
                "evidence": {
                    "four_ones_sum17": 2,
                    "four_ones_carry17": 2,
                    "carry_is_already_shifted_by": "CSA_4to2.v carry={carry_temp[..],1'b0}",
                },
                "adjudication": "first compressor represents 4 as sum17+carry17",
            },
            {
                "boundary": "SA_PE_Mul_Array carry handoff",
                "evidence": {
                    "source_line_semantics": "last_B={carry_int[30:0],1'b0}",
                    "later_line_semantics": "o_Carry={o_Carry_wire[30:0],1'b0}",
                    "four_ones_result": 6,
                },
                "adjudication": "FIRST_DIVERGENCE: carry17 is shifted a second time",
            },
            {
                "boundary": "17_bit_range",
                "evidence": {
                    "legal_dot_range": [-130560, 129540],
                    "signed_17_bit_range": [-65536, 65535],
                    "cout17_is_ignored": True,
                },
                "adjudication": (
                    "independent full-range defect remains even if the duplicate carry shift "
                    "alone is removed"
                ),
            },
        ],
        "counterexample_matrix": cases,
        "compatibility_matrix": {
            "A_config_only": {
                "full_four_lane_mode": "IMPOSSIBLE",
                "reason": (
                    "gemm/gemv, bias, transout and output-major fields do not alter the "
                    "integer compressor; fp16/bf16 reinterpret the domain and are not exact int32"
                ),
                "correctness_fallback": "ONE_PRODUCT_PER_SA_OCCURRENCE",
                "fallback_proof": (
                    "with three product lanes forced to zero, first-CSA carry is always zero; "
                    "the remaining 32-bit product+psum CSA path is exact modulo 2^32"
                ),
                "cost": {
                    "SA_product_lane_utilization": "1/4",
                    "minimum_compute_occurrence_multiplier": 4,
                    "minimum_operand_traffic_multiplier_if_not_reused": 4,
                    "expected_conv_throughput_upper_bound_vs_nominal": "25%",
                },
                "release_state": "THEORETICAL_SOURCE_PROOF_ONLY_NO_JSON_MATERIALIZATION",
            },
            "B_alternative_topology": {
                "GA_int32_mac_tree": "NOT_CURRENTLY_RELEASABLE",
                "correctness_basis": "GA opcode14 equation is scalar A*B+C",
                "blocking_evidence": [
                    "no authorized opcode14 reference sample",
                    "opcode14 non-transout/normal-FIFO route lacks dynamic proof",
                    "existing GAP six-stage tree is local E2 only and its server route is frozen",
                    "s8 sign extension ingress is not an approved direct byte-to-int32 recipe",
                ],
                "performance": {
                    "GA_scalar_mac_pe_count": 16,
                    "nominal_SA_int8_products_per_occurrence": 256,
                    "raw_product_throughput_upper_bound_vs_nominal_SA": "6.25%",
                    "assessment": "not acceptable for production ResNet Conv; diagnostic fallback only",
                },
            },
            "C_rtl": {
                "preferred": True,
                "authorization": "PROPOSAL_ONLY_FUNCTIONAL_RTL_NOT_MODIFIED",
                "required_semantic_change": (
                    "replace the INT8 dot reduction with a signed 18-bit four-product sum, "
                    "then add signed psum32 exactly modulo 2^32"
                ),
                "exact_patch_proposal": {
                    "target": (
                        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
                        "SA_PE_Mul_Array.v:279-296"
                    ),
                    "scope": "INT8 branch only; leave shared CSA modules and FP branches unchanged",
                    "replacement": [
                        (
                            "form signed17 pair01 from sign-extended pipe_int_sum1 and "
                            "pipe_int_sum2"
                        ),
                        (
                            "form signed17 pair23 from sign-extended pipe_int_sum3 and "
                            "pipe_int_sum4"
                        ),
                        "form signed18 dot4 from sign-extended pair01 plus pair23",
                        "drive integer last_A with signext32(dot4)",
                        "drive integer last_B with 32'b0 instead of shifted carry_int",
                        "retain integer last_C=pipe_FractC[31:0] and the existing 32-bit CSA_3to2",
                    ],
                    "why_not_width_only": (
                        "widening CSA_4to2 without an explicit signed carry/cout identity can "
                        "still mis-handle modular carry representation; the proposed signed "
                        "adder tree states the required arithmetic directly"
                    ),
                },
                "affected_semantics": {
                    "changed": "INT8 four-lane reduction only",
                    "preserved": [
                        "DataA=s8",
                        "DataB=u8",
                        "DataC=psum32",
                        "32-bit modulo accumulation",
                        "FP16 and BF16 paths",
                        "SA configuration encoding and interfaces",
                    ],
                },
                "acceptance_matrix": "all counterexample_matrix cases plus exhaustive small-domain and edge-range tests",
            },
        },
        "recommended_conv_path": {
            "production": "C_COMPATIBLE_RTL_IDENTITY",
            "interim_correctness_baseline": "A_ONE_PRODUCT_PER_SA_OCCURRENCE",
            "reason": (
                "C restores nominal SA utilization; A is source-proven exact but caps product-lane "
                "utilization at 25%; B is lower-throughput and has unresolved GA routing/ingress gates"
            ),
            "next_authorization_needed": (
                "mainline/user choice between an interim serialized config experiment and a "
                "separately authorized RTL repair/new RTL identity"
            ),
        },
        "blocker_delta": {
            "keep": [
                "B_CONV_INT8_SA",
                "B_MATMUL_INT8_SA",
                "B_CONV_CONFIG_BOUND_SIMULATOR_RTL_CSA_MISMATCH",
                "B_CONV_STOCK_RTL_INT8_DOT_CAPABILITY",
            ],
            "add": [
                "B_SA_INT8_DUPLICATE_CARRY_SHIFT",
                "B_SA_INT8_REDUCTION_WIDTH",
                "B_SA_SERIALIZED_FALLBACK_MATERIALIZATION",
            ],
            "close": [],
        },
        "rule_delta_proposal": {
            "proposal_only": True,
            "items": [
                (
                    "INT8 SA arithmetic approval must cover both duplicate-carry-shift and full "
                    "signed four-product range; the four-ones witness alone is insufficient."
                ),
                (
                    "A stock-RTL config-only fallback may use at most one nonzero product lane per "
                    "SA occurrence until a corrected RTL identity is approved; it remains a "
                    "candidate until materialized E2/E4/E5."
                ),
                (
                    "QLinearConv and QLinearMatMul share this arithmetic gate; neither may progress "
                    "to bias/psum/tiling/tail or packaging independently."
                ),
            ],
        },
        "read_receipt": receipts,
    }
