"""Fresh config-only audit of the node0004 raw-signed max0 tail proposal.

The proposal is mathematically useful for the real node0004 qparams, but this
module deliberately fails closed unless the active encoder and RTL expose a
raw signed INT32 comparison/select before INT32-to-FP32 conversion.  It reads
no historical node0004 config, candidate, report, simulator result, or package.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from resnet50_pipeline.node0004_exact_uint8_tail_fresh_c1 import (
    ACCUMULATOR_PATH,
    CURRENT_MATCH_SOURCES as FRESH_CURRENT_MATCH_SOURCES,
    FORBIDDEN_SOURCE_FRAGMENTS,
    GOLDEN_PATH,
    PLAN_PATH,
    Node0004FreshTailError,
    _semantic_analysis,
    sha256_file,
)


SCHEMA = "node0004-exact-uint8-tail-max0-audit-v1"
REPORT_SCHEMA = "node0004-exact-uint8-tail-max0-audit-report-v1"
CONTRACT_PATH = (
    "contracts/operator_config/node0004_exact_uint8_tail_max0_audit_v1.json"
)
REPORT_PATH = (
    "artifacts/operator_config_validation/"
    "node0004-exact-uint8-tail-max0-audit-v1/report.json"
)

AUTHORIZATION_PATH = (
    ".agents/task_records/"
    "20260728_conv_c0_mainline_adjudication_and_composite_c1_authorization.md"
)
MAINLINE_ADJUDICATION_PATH = (
    ".agents/task_records/"
    "20260728_conv_node0004_composite_c1_mainline_adjudication.md"
)
INT8_SA_RULE_PATH = ".agents/rules/INT8_SA点积专项规则.md"
GENERAL_ENCODER_PATH = "ndp-sim/bitstream/config/general.py"
PARAMETERS_PATH = "NDP_copy01/rtl/includes/NDP_Parameters.svh"
GA_PE_ALU_PATH = (
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_ALU.sv"
)
GA_ALU_PATH = (
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/GA_ALU.v"
)
GA_CONTROL_PATH = (
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/"
    "GA_PE_Float_Control.v"
)
GA_LAST_PATH = (
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/"
    "GA_PE_Float_Last.v"
)
GA_INPORT_PATH = (
    "NDP_copy01/rtl/Slice/General_Array/GA_Inport/GA_Inport.sv"
)

FOCUSED_CURRENT_MATCH_SOURCES = [
    (AUTHORIZATION_PATH, "mainline composite-C1 authorization"),
    (MAINLINE_ADJUDICATION_PATH, "mainline composite-C1 final adjudication"),
    (INT8_SA_RULE_PATH, "current composite INT8-SA boundary"),
    (GENERAL_ENCODER_PATH, "active symbolic GA opcode encoder"),
    (PARAMETERS_PATH, "active GA opcode constants"),
    (GA_PE_ALU_PATH, "active GA opcode class decode"),
    (GA_ALU_PATH, "active GA ALU integration"),
    (GA_CONTROL_PATH, "active GA mode/precision/opcode decode"),
    (GA_LAST_PATH, "active FP32/int8 max result selection"),
    (GA_INPORT_PATH, "active INT32-to-FP32 converter"),
]


class Node0004Max0AuditError(Node0004FreshTailError):
    """Raised when the fresh max0 audit contract no longer holds."""


RECEIPT_REFRESH = {
    "kind": "RECEIPT_ONLY_INTEGRATION_REFRESH",
    "numeric_analysis_repeated": False,
    "mathematical_conclusion_changed": False,
    "hardware_conclusion_changed": False,
    "raw_signed_guard_rule_bound": "CDA-QUANT-TAIL-RAW-SIGNED-GUARD-001",
    "mainline_adjudication_bound": MAINLINE_ADJUDICATION_PATH,
    "target_or_package_generation_performed": False,
}


def _text(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _required_tokens(source: str, tokens: tuple[str, ...], label: str) -> None:
    missing = [token for token in tokens if token not in source]
    if missing:
        raise Node0004Max0AuditError(
            f"{label} no longer contains required tokens: {missing}"
        )


def _opcode_rtl_audit(root: Path) -> dict[str, Any]:
    encoder = _text(root, GENERAL_ENCODER_PATH)
    parameters = _text(root, PARAMETERS_PATH)
    pe_alu = _text(root, GA_PE_ALU_PATH)
    control = _text(root, GA_CONTROL_PATH)
    last = _text(root, GA_LAST_PATH)
    inport = _text(root, GA_INPORT_PATH)

    _required_tokens(
        encoder,
        (
            '"max": 3',
            '"int8_max": 11',
            '"int32_sum": 12',
            '"int32_sub": 13',
            '"int32_mac": 14',
        ),
        "GA encoder",
    )
    if '"int32_max"' in encoder:
        raise Node0004Max0AuditError(
            "active encoder gained int32_max; this fail-closed audit needs rework"
        )
    _required_tokens(
        parameters,
        (
            "`define GA_PE_ALU_OPCODE_FP32_MAX",
            "`define GA_PE_ALU_OPCODE_INT8_MAX",
            "`define GA_PE_ALU_OPCODE_INT32_SUM",
            "`define GA_PE_ALU_OPCODE_INT32_SUB",
            "`define GA_PE_ALU_OPCODE_INT32_MAC",
        ),
        "GA opcode constants",
    )
    if "GA_PE_ALU_OPCODE_INT32_MAX" in parameters:
        raise Node0004Max0AuditError(
            "active RTL gained an INT32 max constant; re-adjudication required"
        )
    _required_tokens(
        pe_alu,
        (
            "assign alu_opcode     = ga_pe_alu_opcode[4] ? 3'b110 : ga_pe_alu_opcode[2:0]",
            "assign alu_mode       = (!ga_pe_alu_opcode[4] & !ga_pe_alu_opcode[3]) | ga_pe_alu_opcode[4]",
            "assign alu_precision  = !(!ga_pe_alu_opcode[4] & ga_pe_alu_opcode[3] & !ga_pe_alu_opcode[2])",
        ),
        "GA PE class decode",
    )
    _required_tokens(
        control,
        (
            "assign is_fp32  =  i_Mode &  (i_Precision == 1'b1)",
            "assign is_int32 = !i_Mode && (i_Precision == 1'b1)",
            "assign is_int8  = !i_Mode && (i_Precision == 1'b0)",
            "assign c_FmaIsMax     = gr_Opcode==3'b011",
        ),
        "GA ALU control",
    )
    _required_tokens(
        last,
        (
            "if(i_opcode_is_max)",
            "if(i_opcode_is_max & !i_is_int8)",
            "assign o_Rst = i_Mode ? o_FpRst : o_IntRst",
        ),
        "GA max result",
    )
    _required_tokens(
        inport,
        (
            "assign ga_inport_int32_sign = ga_inport_ib_data",
            "assign ga_inport_int32tofp32_data =",
            "ga_inport_fp32_frac_guard & !ga_inport_fp32_frac_stick",
        ),
        "GA INT32-to-FP32 converter",
    )

    # An INT32-class opcode must have bits [4:2] == 3'b011.  A max opcode
    # must have bits [2:0] == 3'b011.  Those conditions disagree on bit 2,
    # so no 5-bit value can select both paths.
    values = range(32)
    int32_class = [v for v in values if (v & 0b11100) == 0b01100]
    max_decode = [v for v in values if (v & 0b00111) == 0b00011]
    intersection = sorted(set(int32_class).intersection(max_decode))
    if intersection:
        raise Node0004Max0AuditError(
            f"unexpected INT32/max encoding intersection: {intersection}"
        )
    return {
        "symbolic_encoder_opcodes": {
            "fp32_max": 3,
            "int8_max": 11,
            "int32_sum": 12,
            "int32_sub": 13,
            "int32_mac": 14,
            "int32_max": None,
        },
        "five_bit_decode_proof": {
            "int32_class_predicate": "opcode[4:2] == 3'b011",
            "int32_class_values": int32_class,
            "max_predicate": "opcode[2:0] == 3'b011",
            "max_decode_values": max_decode,
            "intersection": intersection,
            "conclusion": "NO_RAW_SIGNED_INT32_MAX_ENCODING",
        },
        "fp32_max_is_not_a_raw_guard": {
            "opcode": 3,
            "alu_mode": "FP32",
            "requires_conversion_before_numeric_fp32_compare": True,
            "reason": (
                "The raw accumulator bits are not an IEEE FP32 value; using "
                "opcode 3 therefore cannot prove max(int32_acc,0) before the "
                "contradicted signed converter."
            ),
        },
        "int8_max_is_not_a_word_guard": {
            "opcode": 11,
            "precision": "four independent int8 lanes",
            "preserves_signed_int32_word": False,
            "reason": (
                "The RTL selects per-byte integer results and is not a signed "
                "32-bit comparison/select; current rules also contradict its "
                "numeric/flow behavior."
            ),
        },
        "raw_integer_fallback_set": ["int32_sum", "int32_sub", "int32_mac"],
        "raw_integer_fallback_limit": (
            "Without compare/select/shift/bitwise state, these arithmetic "
            "operators cannot provide the required signed-word max0 claim."
        ),
        "status": "CONTRADICTED_NO_RAW_SIGNED_INT32_MAX0",
    }


def _bits_to_float32(values: list[str]) -> np.ndarray:
    words = np.asarray([int(value, 16) for value in values], dtype=np.uint32)
    return words.view(np.float32)


def _max0_math_and_w3(root: Path, fresh: dict[str, Any]) -> dict[str, Any]:
    multipliers = _bits_to_float32(
        fresh["qparam_identity"]["requant_multiplier"]["float32_bits"]
    )
    if not np.all(np.isfinite(multipliers)) or not np.all(multipliers > 0):
        raise Node0004Max0AuditError(
            "max0 equivalence requires finite strictly-positive multipliers"
        )
    y_zp = fresh["qparam_identity"]["y_zero_point"]["value"]
    if y_zp != 0:
        raise Node0004Max0AuditError(
            "this instance-specific max0 proof requires y_zero_point=0"
        )

    accumulator = np.load(root / ACCUMULATOR_PATH, allow_pickle=False)
    golden = np.load(root / GOLDEN_PATH, allow_pickle=False)
    if accumulator.dtype != np.int32 or golden.dtype != np.uint8:
        raise Node0004Max0AuditError("formal W3 tensor dtype changed")
    max0 = np.maximum(accumulator, np.int32(0))
    with np.errstate(over="raise", invalid="raise"):
        original_scaled = np.multiply(
            accumulator.astype(np.float32),
            multipliers.reshape(1, 64, 1, 1),
            dtype=np.float32,
        )
        max0_scaled = np.multiply(
            max0.astype(np.float32),
            multipliers.reshape(1, 64, 1, 1),
            dtype=np.float32,
        )
    original_q = np.clip(np.rint(original_scaled), 0, 255).astype(np.uint8)
    max0_q = np.clip(np.rint(max0_scaled), 0, 255).astype(np.uint8)

    original_vs_max0 = int(np.count_nonzero(original_q != max0_q))
    max0_vs_golden = int(np.count_nonzero(max0_q != golden))
    if original_vs_max0 or max0_vs_golden:
        raise Node0004Max0AuditError(
            "formal W3 contradicts node0004 max0 mathematical equivalence"
        )
    max0_sha = hashlib.sha256(max0.tobytes(order="C")).hexdigest()
    return {
        "domain_preconditions": {
            "accumulator": "all signed int32 values",
            "multiplier": "finite float32 and strictly positive for all 64 channels",
            "y_zero_point": 0,
            "rounding": "nearest-even after sequential float32 multiply",
            "saturation": "[0,255]",
        },
        "case_proof": [
            {
                "case": "acc >= 0",
                "argument": "max(acc,0)=acc, so every later intermediate is identical.",
            },
            {
                "case": "acc < 0",
                "argument": (
                    "positive multiplier keeps the scaled value non-positive; "
                    "nearest-even is non-positive and UINT8 saturation returns "
                    "zero, equal to the max0 branch."
                ),
            },
        ],
        "full_signed_domain_conclusion": (
            "final_uint8(acc) == final_uint8(max(acc,0)) under the stated "
            "instance preconditions"
        ),
        "formal_w3": {
            "shape": list(accumulator.shape),
            "element_count": int(accumulator.size),
            "accumulator_minimum": int(accumulator.min()),
            "accumulator_maximum": int(accumulator.max()),
            "negative_count": int(np.count_nonzero(accumulator < 0)),
            "max0_minimum": int(max0.min()),
            "max0_maximum": int(max0.max()),
            "max0_tensor_sha256_validation_only": max0_sha,
            "original_vs_max0_final_mismatch_count": original_vs_max0,
            "max0_vs_formal_golden_mismatch_count": max0_vs_golden,
            "max0_values_exactly_representable_in_ieee_fp32": bool(
                int(max0.max()) <= (1 << 24)
            ),
            "host_tensor_use": (
                "validation-only; never emitted, replayed, or supplied to "
                "hardware/configuration"
            ),
        },
        "mathematical_equivalence": True,
        "hardware_materialization": False,
    }


def _downstream_audit(fresh: dict[str, Any]) -> dict[str, Any]:
    native = fresh["native_source_audit"]
    return {
        "nonnegative_int32_to_fp32": {
            "active_primitive_present": True,
            "rtl_rounding_logic": "guard/sticky nearest-even",
            "formal_w3_conditional_domain": "[0,57876] <= 2^24",
            "status": "CONDITIONALLY_REACHABLE_ONLY_AFTER_MISSING_MAX0",
            "claim_boundary": (
                "This does not repair raw signed ingress and is not an "
                "end-to-end converter proof for the full legal INT32 domain."
            ),
        },
        "sequential_mul_then_rne_then_saturation": {
            "required_stages": [
                "materialized FP32 multiply result",
                "separate rounded magic add/RNE decode",
                "zero-point after rounding",
                "UINT8 saturation",
            ],
            "fused_fma_accepted": False,
            "status": "NOT_MATERIALIZED_AFTER_FIRST_BREAK",
            "inherited_counterexample": (
                "400 * bits(0x3d828f5c): sequential=26, fused=25"
            ),
        },
        "per_channel_constant_transport": {
            "qparam_identity_sha256": fresh["qparam_identity"][
                "requant_multiplier"
            ]["sha256"],
            "channel_count": 64,
            "typed_handler_status": native["typed_transport"]["status"],
            "native_per_channel_transport": native["execplan_transport"][
                "per_channel_multiplier_transport"
            ],
            "manual_materializer": "NOT_IMPLEMENTED_WITHOUT_A_REACHABLE_TAIL_PATH",
            "status": "BLOCKED",
        },
        "mapper_and_endpoint": {
            "mapper_status": native["mapper"]["status"],
            "composite_int32_endpoint": {
                "same_storage": None,
                "base": None,
                "offset": None,
                "read_coverage": None,
                "accepted_lifetime": None,
                "terminal": None,
            },
            "status": "DEPENDENCY_INTERFACE_UNBOUND",
        },
    }


def _analysis(root: Path) -> dict[str, Any]:
    fresh = _semantic_analysis(root)
    opcode = _opcode_rtl_audit(root)
    math_w3 = _max0_math_and_w3(root, fresh)
    downstream = _downstream_audit(fresh)
    first_break = {
        "id": "B_QUANT_TAIL_RAW_SIGNED_INT32_MAX0_OPCODE",
        "status": "OPEN_CONTRADICTED",
        "minimum_counterexample": {
            "input_int32": -1,
            "required_raw_max0": 0,
            "encoder_int32_max_opcode": None,
            "fp32_max_requires_prior_conversion": True,
            "final_uint8_masking_is_not_intermediate_evidence": True,
        },
        "reason": (
            "The max0 transform is mathematically exact for node0004, but the "
            "active encoder/RTL has no raw signed INT32 max opcode. FP32 max "
            "is downstream of conversion, and int8_max is per-byte."
        ),
    }
    return {
        "request": fresh["request"],
        "tail_class": fresh["tail_class"],
        "qparam_identity": fresh["qparam_identity"],
        "shape_layout": fresh["shape_layout"],
        "max0_math_and_w3": math_w3,
        "active_opcode_rtl_audit": opcode,
        "downstream_capability_audit": downstream,
        "pure_configuration_decision": {
            "exact_path_exists": False,
            "decision": "NO_CONFIG_ONLY_CORRECTNESS_BASELINE",
            "first_unavoidable_capability": first_break["id"],
            "mathematical_rewrite_valid": True,
            "hardware_rewrite_materializable": False,
        },
        "blockers": [
            first_break,
            {
                "id": "B_QUANT_TAIL_NONNEGATIVE_INT32_TO_FP32_FULL_DOMAIN",
                "status": "OPEN_DOWNSTREAM_NOT_REACHED",
            },
            {
                "id": "B_QUANT_TAIL_FMA_ROUNDING_POINT",
                "status": "OPEN_DOWNSTREAM_NOT_MATERIALIZED",
            },
            {
                "id": "B_QUANT_TAIL_PER_CHANNEL_CONSTANT_TRANSPORT",
                "status": "OPEN_PLACEHOLDER",
            },
            {
                "id": "B_QUANT_TAIL_MAPPER_REGISTRATION",
                "status": "OPEN_MISSING_OR_UNPROVEN",
            },
            {
                "id": "B_NODE0004_COMPOSITE_ENDPOINT_BINDING",
                "status": "OPEN_DEPENDENCY_INTERFACE",
            },
        ],
        "bypass_annotation": {
            "classification": "NOT_ACTIVATED",
            "config_only_correctness_baseline": False,
            "bypass_reason": (
                "avoid contradicted signed INT32-to-FP32 conversion by "
                "clamping raw signed accumulator to zero first"
            ),
            "contradicted_or_missing_native_path": (
                "raw signed INT32 compare/select max(acc,0)"
            ),
            "exact_equivalence_scope": (
                "all signed int32 inputs for node0004's finite positive "
                "per-channel multipliers and y_zp=0; confirmed on full frozen W3"
            ),
            "materialized_configuration_mechanism": None,
            "performance_and_resource_cost": (
                "at least one additional serialized guard stage if a real "
                "signed-word compare/select primitive becomes available"
            ),
            "unresolved_production_blocker": [
                "B_QUANT_TAIL_RAW_SIGNED_INT32_MAX0_OPCODE",
                "B_QUANT_TAIL_FMA_ROUNDING_POINT",
                "B_QUANT_TAIL_PER_CHANNEL_CONSTANT_TRANSPORT",
                "B_QUANT_TAIL_MAPPER_REGISTRATION",
                "B_NODE0004_COMPOSITE_ENDPOINT_BINDING",
            ],
            "claim_boundary": (
                "Fail-closed capability audit only; no target JSON, tail "
                "configuration, full Conv assembly, server package, or release."
            ),
        },
        "dependency_for_node0004_c1": {
            "authorization": "PATH_FRESH_COMPOSITE_CONFIG_C1=AUTHORIZED",
            "tail_leg_status": "BLOCKED_AT_RAW_SIGNED_MAX0",
            "accumulate_leg_consumed_or_assembled": False,
            "endpoint_interface": downstream["mapper_and_endpoint"][
                "composite_int32_endpoint"
            ],
            "provided_to_conv_consumer": [
                "fresh qparam identity",
                "full-domain mathematical max0 proof",
                "full frozen W3 max0 replay",
                "active opcode/RTL impossibility proof",
                "first unavoidable capability",
            ],
        },
        "scope": {
            "old_node0004_assets_consumed": False,
            "host_internal_tensor_supplied_to_hardware": False,
            "tail_config_generated": False,
            "target_json_generated": False,
            "mapping_generated": False,
            "bitstream_generated": False,
            "execplan_or_sca_generated": False,
            "full_conv_assembled": False,
            "server_files_inspected": False,
            "server_package_generated": False,
            "server_run_performed": False,
            "candidate_release": False,
            "package_release": "NONE",
        },
    }


def _source_identities(root: Path) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for path, reason in [
        *FRESH_CURRENT_MATCH_SOURCES,
        *FOCUSED_CURRENT_MATCH_SOURCES,
    ]:
        if path in seen:
            continue
        seen.add(path)
        result.append(
            {
                "path": path,
                "sha256": sha256_file(root / path),
                "reason": reason,
                "gate": "current_match_fail_closed",
            }
        )
    return result


def build_contract(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    return {
        "schema": SCHEMA,
        "status": "FAIL_CLOSED_RAW_SIGNED_MAX0_NOT_MATERIALIZABLE",
        "mainline_thread_id": "019fa2ca-72bc-7753-8d58-81e59bc76c88",
        "plan_read_receipt": {
            "path": PLAN_PATH,
            "sha256": sha256_file(root / PLAN_PATH),
            "gate": "mutable_provenance_only",
            "current_match_required": False,
        },
        "source_policy": {
            "allowed_classes": [
                "typed lowering/request",
                "formal ONNX model and W3 tensors/manifests",
                "current rules and mainline authorization",
                "hash-bound active local encoder/RTL/native source",
            ],
            "forbidden_source_fragments": list(FORBIDDEN_SOURCE_FRAGMENTS),
            "old_node0004_assets_consumed": False,
        },
        "source_identities": _source_identities(root),
        "integration_refresh": RECEIPT_REFRESH,
        **_analysis(root),
    }


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Node0004Max0AuditError(f"JSON root must be an object: {path}")
    return value


def refresh_receipts(
    contract_path: Path, project_root: Path
) -> dict[str, Any]:
    """Refresh only mutable/current source receipts; never recompute W3."""
    root = project_root.resolve()
    contract = _load_json(contract_path)
    if contract.get("schema") != SCHEMA:
        raise Node0004Max0AuditError("unexpected max0 audit schema")
    contract["plan_read_receipt"] = {
        "path": PLAN_PATH,
        "sha256": sha256_file(root / PLAN_PATH),
        "gate": "mutable_provenance_only",
        "current_match_required": False,
    }
    contract["source_identities"] = _source_identities(root)
    contract["integration_refresh"] = RECEIPT_REFRESH
    contract_path.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return contract


def _validate_frozen_conclusions(
    contract: dict[str, Any], root: Path
) -> None:
    """Validate committed conclusions without loading/replaying W3 arrays."""
    qparams = contract["qparam_identity"]
    if qparams["requant_multiplier"]["sha256"] != (
        "e83328d8589db8cfc2c5a1ff033d3c0e08d9bd87d8d8fcf52b8cb22189956bb2"
    ):
        raise Node0004Max0AuditError("frozen multiplier identity changed")
    if qparams["y_zero_point"]["value"] != 0:
        raise Node0004Max0AuditError("frozen y_zero_point changed")

    math_w3 = contract["max0_math_and_w3"]
    frozen_w3 = math_w3["formal_w3"]
    expected_w3 = {
        "element_count": 3211264,
        "negative_count": 1262480,
        "accumulator_minimum": -1148879,
        "accumulator_maximum": 57876,
        "max0_minimum": 0,
        "max0_maximum": 57876,
        "original_vs_max0_final_mismatch_count": 0,
        "max0_vs_formal_golden_mismatch_count": 0,
    }
    for key, value in expected_w3.items():
        if frozen_w3.get(key) != value:
            raise Node0004Max0AuditError(
                f"frozen W3 conclusion changed without analysis authority: {key}"
            )
    if not math_w3["mathematical_equivalence"]:
        raise Node0004Max0AuditError("mathematical max0 conclusion changed")
    if math_w3["hardware_materialization"]:
        raise Node0004Max0AuditError("hardware materialization was widened")

    opcode = contract["active_opcode_rtl_audit"]
    if opcode["five_bit_decode_proof"]["intersection"] != []:
        raise Node0004Max0AuditError("frozen opcode impossibility changed")
    if opcode["status"] != "CONTRADICTED_NO_RAW_SIGNED_INT32_MAX0":
        raise Node0004Max0AuditError("raw signed max0 RTL conclusion changed")

    decision = contract["pure_configuration_decision"]
    if decision != {
        "decision": "NO_CONFIG_ONLY_CORRECTNESS_BASELINE",
        "exact_path_exists": False,
        "first_unavoidable_capability": (
            "B_QUANT_TAIL_RAW_SIGNED_INT32_MAX0_OPCODE"
        ),
        "hardware_rewrite_materializable": False,
        "mathematical_rewrite_valid": True,
    }:
        raise Node0004Max0AuditError("pure configuration conclusion changed")

    if contract.get("integration_refresh") != RECEIPT_REFRESH:
        raise Node0004Max0AuditError("receipt-only integration marker changed")
    exact_rule = _text(root, FRESH_CURRENT_MATCH_SOURCES[4][0])
    _required_tokens(
        exact_rule,
        (
            "CDA-QUANT-TAIL-RAW-SIGNED-GUARD-001",
            "B_QUANT_TAIL_RAW_SIGNED_INT32_MAX0_OPCODE=OPEN_CONTRADICTED",
        ),
        "published exact-tail raw signed guard rule",
    )
    adjudication = _text(root, MAINLINE_ADJUDICATION_PATH)
    _required_tokens(
        adjudication,
        (
            "C1_TARGET_MATERIALIZATION = BLOCKED_BEFORE_JSON",
            "B_QUANT_TAIL_RAW_SIGNED_INT32_MAX0_OPCODE = OPEN_CONTRADICTED",
            "PACKAGE_RELEASE = NONE",
        ),
        "mainline C1 adjudication",
    )


def validate_contract(
    contract_path: Path, project_root: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    contract = _load_json(contract_path)
    if contract.get("schema") != SCHEMA:
        raise Node0004Max0AuditError("unexpected max0 audit schema")
    if contract.get("status") != (
        "FAIL_CLOSED_RAW_SIGNED_MAX0_NOT_MATERIALIZABLE"
    ):
        raise Node0004Max0AuditError("max0 audit status changed")

    expected_sources = _source_identities(root)
    if contract.get("source_identities") != expected_sources:
        raise Node0004Max0AuditError(
            "hard semantic source identity changed or source set drifted"
        )
    for item in expected_sources:
        normalized = item["path"].replace("\\", "/").lower()
        if any(
            fragment.lower() in normalized
            for fragment in FORBIDDEN_SOURCE_FRAGMENTS
        ):
            raise Node0004Max0AuditError(
                f"forbidden historical source consumed: {item['path']}"
            )

    _validate_frozen_conclusions(contract, root)
    scope = contract["scope"]
    forbidden_true = [
        key
        for key, value in scope.items()
        if key != "package_release" and bool(value)
    ]
    if forbidden_true or scope["package_release"] != "NONE":
        raise Node0004Max0AuditError(
            f"forbidden generation/release scope widened: {forbidden_true}"
        )

    current_plan_sha = sha256_file(root / PLAN_PATH)
    return {
        "schema": REPORT_SCHEMA,
        "status": "PASS_FAIL_CLOSED_RAW_SIGNED_MAX0_NOT_MATERIALIZABLE",
        "integration_refresh": {
            **RECEIPT_REFRESH,
            "hard_source_receipts_current_match": True,
            "conclusion_unchanged": True,
        },
        "contract": {
            "path": contract_path.relative_to(root).as_posix(),
            "sha256": sha256_file(contract_path),
        },
        "source_identity_count": len(expected_sources),
        "source_identities_current_match": True,
        "plan_read_receipt": {
            "recorded_sha256": contract["plan_read_receipt"]["sha256"],
            "current_sha256": current_plan_sha,
            "current_match": (
                contract["plan_read_receipt"]["sha256"] == current_plan_sha
            ),
            "gate": "mutable_provenance_only",
        },
        "request_id": contract["request"]["request_id"],
        "multiplier_sha256": contract["qparam_identity"][
            "requant_multiplier"
        ]["sha256"],
        "y_zero_point": contract["qparam_identity"]["y_zero_point"]["value"],
        "w3_element_count": contract["max0_math_and_w3"]["formal_w3"][
            "element_count"
        ],
        "w3_negative_count": contract["max0_math_and_w3"]["formal_w3"][
            "negative_count"
        ],
        "w3_original_vs_max0_mismatch_count": contract[
            "max0_math_and_w3"
        ]["formal_w3"]["original_vs_max0_final_mismatch_count"],
        "w3_max0_vs_golden_mismatch_count": contract[
            "max0_math_and_w3"
        ]["formal_w3"]["max0_vs_formal_golden_mismatch_count"],
        "opcode_intersection": contract["active_opcode_rtl_audit"][
            "five_bit_decode_proof"
        ]["intersection"],
        "first_unavoidable_capability": contract[
            "pure_configuration_decision"
        ]["first_unavoidable_capability"],
        "exact_path_exists": contract["pure_configuration_decision"][
            "exact_path_exists"
        ],
        "numeric_analysis_repeated": False,
        "conclusion_unchanged": True,
        "tail_config_generated": scope["tail_config_generated"],
        "target_json_generated": scope["target_json_generated"],
        "server_package_generated": scope["server_package_generated"],
        "full_conv_assembled": scope["full_conv_assembled"],
        "package_release": scope["package_release"],
    }


def write_contract(project_root: Path, output_path: Path) -> dict[str, Any]:
    contract = build_contract(project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return contract


def write_report(
    contract_path: Path, project_root: Path, output_path: Path
) -> dict[str, Any]:
    report = validate_contract(contract_path, project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
