from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .conv_stem_request_address_validator import BUNDLE_REL, REPORT_REL
from .conv_stem_serialized_local_e2 import (
    ARTIFACT_ROOT_REL,
    CONFIG_ROOT_REL,
    CONTRACT_REL,
    GRAPH_REL,
    PATCHSET_REL,
    PHYSICAL_MANIFEST_REL,
    REQUEST_ID,
    REQUEST_SHA256,
    TEST_ID,
)
from .hashing import sha256_file


PLAN_REL = Path(".agents/plan.md")
INDEX_REL = Path(".agents/rules/生成前必读索引.md")
COMMON_REL = Path(".agents/rules/算子配置规则.md")
SA_REL = Path(".agents/rules/INT8_SA点积专项规则.md")
NDP_REL = Path(".agents/rules/NDP硬件字段语义.md")
TAIL_REL = Path(".agents/rules/精确UINT8量化尾专项规则.md")
REQUANT_RULE_REL = Path(".agents/rules/RequantizeUint8算子配置规则.md")
AUTH_REL = Path(
    ".agents/task_records/"
    "20260729_conv_stem_typed_materializer_patchset_authorization.md"
)
LOWERING_REL = Path("contracts/resnet50_r5_lowering_bundle.json")
EXPANSION_REL = Path(
    "contracts/operator_config/conv_sa_remaining52_expansion_v1.json"
)
REQUANT_REL = Path(
    "contracts/operator_config/requant_conv53_tail_signature_binding_v1.json"
)
PHYSICAL_VALIDATION_REL = ARTIFACT_ROOT_REL / "physical_validation.json"

ACTIVE_RULE_SHA256 = {
    INDEX_REL: "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
    COMMON_REL: "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
    SA_REL: "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
    NDP_REL: "18d71520dd4ededc5edd9bb316acd0cc0421a9a261cf14b28ea6997ddd0e844a",
    TAIL_REL: "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
    REQUANT_RULE_REL: (
        "5fcd1c9d2f6fa6dd193e369412c46c16b7bd087b570cc607aa0d0f06ba4c7555"
    ),
}
AUTH_SHA256 = "2a8bb1faf66a801c1a1f2cf718dd10779b5846a2ff5c7512409532797286a185"
EXPANSION_SHA256 = (
    "31065f28bc5c9ec46d150c74a1c3370a6166a3f4bff3fa54c711f3d7b5ef7063"
)
REQUANT_SHA256 = (
    "0cb706c1f95de010e840b212d3fa7b22cb63e20c4939da1eec52afc56e957fee"
)


class StemContractError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise StemContractError(f"JSON root must be object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _binding(root: Path, path: Path) -> dict[str, Any]:
    absolute = root / path
    return {
        "path": path.as_posix(),
        "bytes": absolute.stat().st_size,
        "sha256": sha256_file(absolute),
    }


def _stem_requant_row(root: Path) -> dict[str, Any]:
    manifest = _load(root / REQUANT_REL)
    rows = [
        row
        for row in manifest.get("stage_bindings", [])
        if isinstance(row, dict)
        and row.get("typed_request", {}).get("request_id") == "r5:hwop-0001-01"
    ]
    if len(rows) != 1:
        raise StemContractError("stem Requant binding is not unique")
    return rows[0]


def build_stem_contract(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    for path, expected in ACTIVE_RULE_SHA256.items():
        actual = sha256_file(root / path)
        if actual != expected:
            raise StemContractError(
                f"active rule current-match failed: {path}: {actual}"
            )
    if sha256_file(root / AUTH_REL) != AUTH_SHA256:
        raise StemContractError("stem narrow authorization identity differs")
    if sha256_file(root / EXPANSION_REL) != EXPANSION_SHA256:
        raise StemContractError("remaining52 expansion identity differs")
    if sha256_file(root / REQUANT_REL) != REQUANT_SHA256:
        raise StemContractError("Requant tail manifest identity differs")

    physical = _load(root / PHYSICAL_VALIDATION_REL)
    request = _load(root / REPORT_REL)
    bundle = _load(root / BUNDLE_REL)
    patchset = _load(root / PATCHSET_REL)
    if (
        physical.get("valid") is not True
        or physical.get("config_bound_w3_mismatch") != 0
        or request.get("valid") is not True
        or bundle.get("valid") is not True
        or patchset.get("patchset_sha256")
        != "216359f140740c149a28cb8c34a087ae50518cf851e831b457804c1fca6c381a"
    ):
        raise StemContractError("stem local E2 evidence is incomplete")

    requant = _stem_requant_row(root)
    profile = requant["physical_tail_schedule_dependencies"]["profile_id"]
    if (
        profile != "TAIL_N16_C64_H112_W112_HWC8"
        or requant["existing_w3_classification"]["classification"]
        != "FULL_LOCAL_E2_MATERIALIZED_EXACT_NODE0001"
    ):
        raise StemContractError("stem Requant reuse profile differs")

    configs = {
        f"wave-{wave}.json": _binding(
            root, CONFIG_ROOT_REL / f"wave-{wave}.json"
        )
        for wave in range(3)
    }
    return {
        "schema": "resnet50-conv-stem-serialized-local-e2-contract-v1",
        "test_id": TEST_ID,
        "classification": "CONFIG_ONLY_CORRECTNESS_BASELINE",
        "status": "LOCAL_E2_ACCUMULATE_COMPLETE",
        "identity": {
            "request_id": REQUEST_ID,
            "request_sha256": REQUEST_SHA256,
            "node_id": "node-0001",
            "hw_op_id": "hwop-0001-00",
            "hw_op_type": "ConvInt32Accumulate",
            "typed_input": {
                "shape": [16, 3, 224, 224],
                "dtype": "uint8",
                "layout": "NCHW",
            },
            "weight": {
                "shape": [64, 3, 7, 7],
                "dtype": "int8",
                "layout": "OIHW",
            },
            "typed_output": {
                "shape": [16, 64, 112, 112],
                "dtype": "int32",
                "logical_layout": "NCHW",
                "physical_layout": "HWC8-compatible two adjacent C8 shards",
            },
            "stride": [2, 2],
            "padding": [3, 3, 3, 3],
            "logical_k": 147,
            "serialized_k": 148,
            "x_zero_point": 114,
        },
        "active_rule_receipts": {
            path.as_posix(): expected
            for path, expected in ACTIVE_RULE_SHA256.items()
        },
        "rule_ids": [
            "CDA-CONFIG-ONLY-CORRECTNESS-BYPASS-001",
            "CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001",
            "CDA-CONFIG-SEMANTIC-OWNERSHIP-001",
            "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001",
            "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
            "CDA-CONFIG-FULL-REBUILD-PROVENANCE-001",
            "CDA-SA-INT8-DOT-ARITHMETIC-RANGE-001",
            "CDA-SA-INT8-CONV-MATMUL-COMMON-GATE-001",
        ],
        "mutable_plan_provenance": {
            "path": PLAN_REL.as_posix(),
            "sha256_at_build": sha256_file(root / PLAN_REL),
            "semantic_gate": False,
        },
        "authorization": {
            **_binding(root, AUTH_REL),
            "preimage_current_match_performed": True,
            "active_ndp_sim_modified": False,
            "functional_rtl_modified": False,
        },
        "source_receipts": {
            "typed_lowering": _binding(root, LOWERING_REL),
            "remaining52_domain": _binding(root, EXPANSION_REL),
            "requant_tail_manifest": _binding(root, REQUANT_REL),
            "patchset": _binding(root, PATCHSET_REL),
            "graph": _binding(root, GRAPH_REL),
            "physical_manifest": _binding(root, PHYSICAL_MANIFEST_REL),
            "configs": configs,
        },
        "bypass_annotation": {
            "bypass_reason": (
                "the frozen stem final dot4 domain is [-101231,95485] and "
                "2,499,984 actual occurrences exceed signed17; the historical "
                "four-lane reduction also ignored cout.  The authorized route "
                "therefore restricts each occurrence to one nonzero product "
                "lane while retaining DataC psum."
            ),
            "contradicted_or_missing_native_path": (
                "no immutable server RTL identity with signed18 four-lane dot4 "
                "is bound for stem; the latest server compile stops earlier at "
                "the SA_ALU/SA_PE_Mul_Array.slice_rst interface mismatch"
            ),
            "exact_equivalence_scope": (
                "the complete frozen W3 stem instance: batch16, 64 output "
                "channels, 112x112 output, K=147, x_zp=114, bias enabled, "
                "padded serialized K=148, modulo-s32 accumulation"
            ),
            "materialized_configuration_mechanism": (
                "three fresh native waves with 28/28/8 slice-regions; each "
                "serialized occurrence has at most one nonzero s8*u8 lane; "
                "C starts at bias-114*sum(weight); k147 carries zero weight; "
                "four-bank word striping and native planner/mapper/encoder/"
                "execplan/SCA are consumed by the config-bound inverse"
            ),
            "performance_and_resource_cost": {
                "normal_dot4_occurrences": 475_267_072,
                "serialized_padded_occurrences": 1_901_068_288,
                "occurrence_ratio": 4.0,
                "lane_utilization": physical["lane_utilization"],
                "physical_asset_bytes": 526_685_952,
                "request_count_with_multiplicity": request["facts"][
                    "request_count_with_multiplicity"
                ],
                "valid_request_bytes_with_multiplicity": request["facts"][
                    "valid_byte_count_with_multiplicity"
                ],
            },
            "unresolved_production_blocker": (
                "server RTL identity is not bound and the current server source "
                "does not compile due to slice_rst interface mismatch; there is "
                "no E3/E4/E5.  The accepted Requant tail is not yet composed "
                "into the same physical graph/address/lifetime."
            ),
            "claim_boundary": (
                "accumulate-only LOCAL_E2 and CONFIG_ONLY_CORRECTNESS_BASELINE; "
                "not a production/performance release, not a server package, "
                "not a complete Conv UINT8 node, and not evidence for rank2 "
                "QLinearMatMul"
            ),
        },
        "input_replay_boundary": {
            "activation": (
                "formal W3 producer output tensor, value-preserving im2col replay"
            ),
            "weight": "frozen ONNX int8 initializer",
            "bias": "frozen ONNX int32 initializer",
            "correction_leaf": (
                "static per-output-channel constant "
                "bias-114*sum(weight), modulo 2^32"
            ),
            "host_precomputed_partial_sum": False,
            "host_precomputed_final_accumulator": False,
            "host_precomputed_scaled_rounded_saturated_tensor": False,
        },
        "materialized_leaf_ownership": {
            "typed_and_numeric_leaves": (
                "typed request plus stem serialized schedule contract"
            ),
            "base_fields": (
                "native graph planner and execplan per-slice Write_Reg/SCA binding"
            ),
            "mapper_encoder_fields": "locked isolated patchset and native mapper",
            "nonbase_leaf_diff_count": request["facts"][
                "nonbase_leaf_diff_count"
            ],
            "unauthorized_nonbase_leaf_changes": [],
            "final_output_coverage_recomputed_from_final_occurrences": True,
        },
        "numeric_and_physical_e2": {
            "physical_validation": _binding(root, PHYSICAL_VALIDATION_REL),
            "config_bound_w3_int32_element_count": 12_845_056,
            "config_bound_w3_mismatch_count": 0,
            "nonzero_product_lanes_per_occurrence_max": 1,
            "k_tail": {"k": 147, "weight_zero": True},
            "bias_xzp_correction": "bit-exact modulo-s32",
            "request_address_validation": _binding(root, REPORT_REL),
            "native_bundle": _binding(root, BUNDLE_REL),
            "request_count_with_multiplicity": request["facts"][
                "request_count_with_multiplicity"
            ],
            "unique_request_address_count": request["facts"][
                "unique_request_address_count"
            ],
            "ordered_request_address_sha256": request["facts"][
                "ordered_request_address_sha256"
            ],
            "unique_request_addresses_sha256": request["facts"][
                "unique_request_addresses_sha256"
            ],
            "typed_output_bytes": request["facts"]["typed_output_bytes"],
            "formal_output_write_bytes": request["facts"][
                "output_write_bytes_all_slices"
            ],
            "maximum_data_row": request["facts"]["maximum_data_row"],
            "row_limit_exclusive": request["facts"]["row_limit_exclusive"],
            "sca_tensor_entry_count": request["facts"][
                "sca_tensor_entry_count"
            ],
            "mapping_bitstream_execplan_sca_roundtrip": True,
            "deterministic_native_double_run": True,
        },
        "requant_read_only_binding": {
            "request_id": "r5:hwop-0001-01",
            "source_manifest_sha256": REQUANT_SHA256,
            "existing_classification": requant["existing_w3_classification"][
                "classification"
            ],
            "profile_id": profile,
            "numeric_classification_repeated": False,
            "multiplier_payload_copied": False,
            "logical_identity_compatible": True,
            "layout_equation_compatible": True,
            "address_lifetime_binding_status": (
                "NOT_COMPOSED_IN_ONE_MULTI_OPERATOR_GRAPH"
            ),
            "first_unclosed_boundary": (
                "accumulate D to Requant A zero-copy/shared-address allocation "
                "and inter-stage barrier/lifetime"
            ),
        },
        "blocker_delta": {
            "close": [
                "B_CONV_STEM_TYPED_MATERIALIZER_AND_HANDLER",
                "B_CONV_STEM_PHYSICAL_COVERAGE",
                "B_CONV_STEM_CONFIG_BOUND_W3",
                "B_CONV_STEM_ACCUMULATE_LOCAL_E2",
            ],
            "keep": [
                "B_CONV_STEM_REQUANT_SHARED_ADDRESS_LIFETIME_BINDING",
                "B_CONV_STEM_SERVER_E3_E4_E5",
                "B_NODE0004_DYNAMIC_RESULT_PENDING",
                "B_NODE0004_SERVER_RTL_COMPILE_INTERFACE_MISMATCH",
            ],
        },
        "claim_controls": {
            "numeric_analysis_repeated": False,
            "remaining52_numeric_domain_consumed_read_only": True,
            "requant_numeric_classification_consumed_read_only": True,
            "node0004_identity_or_constants_consumed": False,
            "server_package_generated": False,
            "package_release": "NONE",
            "counts_as_E4": False,
            "counts_as_E5": False,
        },
    }


def validate_stem_contract(
    project_root: Path, contract: Mapping[str, Any]
) -> dict[str, Any]:
    root = project_root.resolve()
    errors: list[str] = []
    try:
        expected = build_stem_contract(root)
        comparable_contract = deepcopy(dict(contract))
        comparable_expected = deepcopy(expected)
        for value in (comparable_contract, comparable_expected):
            provenance = value.get("mutable_plan_provenance")
            if isinstance(provenance, dict):
                provenance.pop("sha256_at_build", None)
        if comparable_contract != comparable_expected:
            errors.append("published contract differs from current inputs")
    except (OSError, KeyError, TypeError, ValueError) as error:
        expected = None
        errors.append(str(error))
    controls = contract.get("claim_controls", {})
    if (
        not isinstance(controls, Mapping)
        or controls.get("numeric_analysis_repeated") is not False
        or controls.get("server_package_generated") is not False
        or controls.get("package_release") != "NONE"
    ):
        errors.append("claim controls differ")
    if contract.get("classification") != "CONFIG_ONLY_CORRECTNESS_BASELINE":
        errors.append("classification differs")
    return {
        "schema": "resnet50-conv-stem-serialized-local-e2-contract-validation-v1",
        "valid": not errors,
        "errors": errors,
        "current_binding_matches": expected is not None and not errors,
        "numeric_analysis_repeated": False,
        "server_package_generated": False,
        "package_release": "NONE",
    }


def write_stem_contract(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    contract = build_stem_contract(root)
    _write(root / CONTRACT_REL, contract)
    validation = validate_stem_contract(root, contract)
    validation_path = root / ARTIFACT_ROOT_REL / "contract_validation.json"
    _write(validation_path, validation)
    return {
        "contract": contract,
        "validation": validation,
        "contract_path": CONTRACT_REL.as_posix(),
        "validation_path": validation_path.relative_to(root).as_posix(),
    }


__all__ = [
    "ACTIVE_RULE_SHA256",
    "StemContractError",
    "build_stem_contract",
    "validate_stem_contract",
    "write_stem_contract",
]
