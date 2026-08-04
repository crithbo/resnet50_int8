from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_COUNTS = {
    "typed_stage_count": 133,
    "conv_stage_count": 53,
    "matmul_stage_count": 1,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _signed32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def rtl_int8_csa_from_reduced_words(
    sum17: int, carry17: int, psum32: int = 0
) -> int:
    """Replay the stock RTL boundary after its first 17-bit INT8 CSA.

    `carry17` is the carry vector emitted by CSA_4to2_int.  The RTL first
    presents it to the 32-bit CSA as `{carry_int[30:0],1'b0}` and then shifts
    that second CSA's carry output once more at the module output.
    """

    sum32 = _signed32((sum17 & 0x1FFFF) | (0xFFFE0000 if sum17 & 0x10000 else 0))
    carry32 = _signed32(
        (carry17 & 0x1FFFF) | (0xFFFE0000 if carry17 & 0x10000 else 0)
    )
    return _signed32(sum32 + (carry32 << 1) + _signed32(psum32))


def build_conv_sa_family_closure(project_root: Path) -> dict[str, Any]:
    bundle_path = project_root / "contracts/resnet50_r5_lowering_bundle.json"
    bundle = _load_json(bundle_path)
    requests = bundle["requests"]
    conv_requests = [
        item
        for item in requests
        if item["identity"]["hw_op_type"] == "ConvInt32Accumulate"
    ]
    matmul_requests = [
        item
        for item in requests
        if item["identity"]["hw_op_type"] == "MatMulInt32Accumulate"
    ]
    counts = {
        "typed_stage_count": len(requests),
        "conv_stage_count": len(conv_requests),
        "matmul_stage_count": len(matmul_requests),
    }
    if counts != REQUIRED_COUNTS:
        raise ValueError(f"typed-stage census drifted: {counts!r}")

    representative = next(
        item for item in conv_requests if item["identity"]["hw_op_id"] == "hwop-0004-00"
    )
    geometry = representative["logical_geometry"]
    parameters = {item["name"]: item["value"] for item in representative["typed_parameters"]}
    if geometry["attributes"]["kernel_shape"] != [1, 1]:
        raise ValueError("hwop-0004-00 is no longer the frozen 1x1 representative")
    if parameters["x_zero_point"]["scalar"] != 0:
        raise ValueError("representative x_zero_point drifted")
    if parameters["w_zero_point"]["minimum"] != 0 or parameters["w_zero_point"]["maximum"] != 0:
        raise ValueError("representative w_zero_point is no longer all-zero")

    rtl_path = (
        project_root
        / "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Mul_Array.v"
    )
    model_path = project_root / "NDPFuncModel/component/SpecialPEA.py"
    rtl_text = rtl_path.read_text(encoding="utf-8")
    model_text = model_path.read_text(encoding="utf-8")
    rtl_witnesses = [
        "CSA_4to2_int",
        "assign last_B = pipe_IsFloat ?",
        "{carry_int[30:0], 1'b0}",
        "assign o_Carry[31:0]= {o_Carry_wire[30:0],1'b0};",
    ]
    model_witnesses = [
        "vec_a_calc = vec_a_pe.view(np.int8).astype(np.int32)",
        "vec_b_calc = vec_b_pe.astype(np.uint8).astype(np.int32)",
        "dot_val = np.sum(vec_a_calc * vec_b_calc, dtype=np.int64)",
        "psum_out = np.int64(np.int32(psum_in)) + np.int64(dot_val)",
    ]
    missing = [text for text in rtl_witnesses if text not in rtl_text]
    missing += [text for text in model_witnesses if text not in model_text]
    if missing:
        raise ValueError(f"SA arithmetic source witnesses drifted: {missing!r}")

    # For four products equal to one, CSA_4to2_int emits sum=2 and carry=2.
    # Its carry is already left-shifted by CSA_4to2.v.  SA_PE_Mul_Array then
    # shifts that carry again, so stock RTL returns 6 rather than 4.
    rtl_counterexample = rtl_int8_csa_from_reduced_words(2, 2, 0)
    conventional_counterexample = 4
    if rtl_counterexample != 6:
        raise AssertionError("stock RTL counterexample replay drifted")

    receipt_paths = [
        ".agents/agent.md",
        ".agents/plan.md",
        ".agents/rules/生成前必读索引.md",
        ".agents/rules/算子配置规则.md",
        ".agents/rules/NDP硬件字段语义.md",
        ".agents/rules/服务器测试包生成规则.md",
        "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
        "contracts/resnet50_r5_lowering_bundle.json",
        "ndp-sim/bitstream/config/special.py",
        "ndp-sim/bitstream/config/mapper.py",
        "ndp-sim/model_execplan/src/execution_plan_generator/pipeline.py",
        "NDP_copy01/rtl/Slice/Specialized_Array/Specialized_Array_Config.sv",
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_Control_Block.sv",
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_Outbuffer.sv",
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Mul_Array.v",
        "NDPFuncModel/component/SpecialPEA.py",
    ]
    read_receipt = [
        {
            "path": relative,
            "sha256": sha256_file(project_root / relative),
            "reason": "required rule, typed source, mapper/execplan, simulator, or RTL consumer",
        }
        for relative in receipt_paths
    ]

    return {
        "schema": "conv-sa-family-local-closure-v1",
        "status": "BLOCKED_RTL_ARITHMETIC_AND_SIMULATOR_SEMANTICS_DIVERGE",
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "evidence_level": "E1_STATIC_SOURCE_BOUNDARY",
        "stage_census": counts,
        "representative": {
            "request_id": representative["request_id"],
            "hw_op_id": representative["identity"]["hw_op_id"],
            "node_id": representative["identity"]["node_id"],
            "onnx_name": representative["identity"]["onnx_name"],
            "input_shapes": geometry["input_shapes"],
            "output_shapes": geometry["output_shapes"],
            "attributes": geometry["attributes"],
            "x_zero_point": parameters["x_zero_point"],
            "w_zero_point": parameters["w_zero_point"],
            "bias": parameters["bias"],
            "request_sha256": representative["request_sha256"],
        },
        "arithmetic_boundary": {
            "onnx_and_ndpfuncmodel": "psum32 + sum_i(s8(weight_i) * u8(activation_i))",
            "stock_rtl_after_first_int8_csa": (
                "psum32 + signext32(sum17) + (signext32(carry17) << 1)"
            ),
            "counterexample": {
                "signed_weight_lanes": [1, 1, 1, 1],
                "unsigned_activation_lanes": [1, 1, 1, 1],
                "psum32": 0,
                "first_csa_sum17": 2,
                "first_csa_carry17": 2,
                "onnx_and_ndpfuncmodel": conventional_counterexample,
                "stock_rtl": rtl_counterexample,
            },
            "issue_id": "CDA-SA-INT8-CSA-001",
            "adjudication": "CONTRADICTED",
        },
        "closure_matrix": {
            "input_weight_tiling": "STRUCTURALLY_MODELED_NOT_NUMERICALLY_RELEASABLE",
            "bias_initialization": "STRUCTURALLY_MODELED_NOT_NUMERICALLY_RELEASABLE",
            "psum_accumulation": "BLOCKED_BY_CDA-SA-INT8-CSA-001",
            "tail_and_padding": "NOT_REACHED_AFTER_ARITHMETIC_STOP_GATE",
            "sa_to_requant_handoff": "NOT_REACHED_AND_OUTSIDE_THIS_FAMILY_RELEASE",
            "buffer_address_lifetime": "NOT_REACHED_AFTER_ARITHMETIC_STOP_GATE",
            "mse_occurrence": "NOT_REACHED_AFTER_ARITHMETIC_STOP_GATE",
            "mapping_bitstream_execplan_sca": "MUST_NOT_BE_MATERIALIZED_AS_RELEASE_CANDIDATE",
            "config_bound_simulator": "INCOMPATIBLE_CONVENTIONAL_DOT_MODEL",
        },
        "blocker_delta": {
            "keep": [
                "B_CONV_INT8_SA",
                "B_CONV_BIAS_PSUM",
                "B_EXECPLAN_TYPED_TRANSPORT",
                "B_LAYOUT_APPROVAL",
            ],
            "add": [
                "B_CONV_CONFIG_BOUND_SIMULATOR_RTL_CSA_MISMATCH",
                "B_CONV_STOCK_RTL_INT8_DOT_CAPABILITY",
            ],
            "close": [],
        },
        "minimum_next_action": {
            "acceptable_path_a": (
                "new stock RTL identity whose INT8 SA implements the conventional signed-weight/"
                "unsigned-activation dot, followed by fresh E2/E4/E5"
            ),
            "acceptable_path_b": (
                "an explicitly authorized hardware topology that computes the exact ONNX dot "
                "without the contradicted INT8 SA path, plus a config-bound simulator for it"
            ),
            "not_sufficient": [
                "retiling",
                "bias correction",
                "tail masking",
                "mapping success",
                "encoder success",
                "natural server completion",
            ],
        },
        "rule_delta_proposal": {
            "proposal_only": True,
            "text": (
                "Any Conv/MatMul config-bound simulator using NDPFuncModel SpecialPEA ordinary "
                "INT8 dot semantics must be rejected for stock-RTL release while "
                "CDA-SA-INT8-CSA-001 remains CONTRADICTED."
            ),
        },
        "read_receipt": read_receipt,
        "omitted_files": [
            {
                "path": "server package assets",
                "reason": "generation stopped before E2; no package is authorized",
            }
        ],
    }
