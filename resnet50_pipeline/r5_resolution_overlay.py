from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .address_bound_config import validate_address_bound_config
from .deepseek_reduction_rules import validate_deepseek_reduction_rules
from .gap_sum_padding_contract import validate_gap_sum_zero_padding_contract
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .maxpool_guarded_storage import validate_guarded_wave0
from .operator_config_validator import OperatorConfigValidator
from .operator_config_request_address_validator import OperatorConfigRequestAddressValidator
from .server_workload_scale import build_requant_v2_workload_scale
from .strict_config_materialization import validate_materialized_strict_config
from .typed_config_parameters import validate_typed_config_parameter_contract


SCHEMA = "resnet50-r5-local-resolution-overlay-v1"
LAYOUT_BLOCKER = "B_LAYOUT_APPROVAL"
TRANSPORT_BLOCKER = "B_EXECPLAN_TYPED_TRANSPORT"
MAXPOOL_BLOCKERS = {
    "B_MAXPOOL_SHAPE_GENERALIZATION",
    "B_MAXPOOL_UINT8_SEMANTICS",
}
MAXPOOL_HW_OP_ID = "hwop-0002-00"
GAP_SUM_HW_OP_ID = "hwop-0071-00"
DEQUANT_HW_OP_ID = "hwop-0077-00"
REQUANT_HW_OP_ID = "hwop-0001-01"


class R5ResolutionOverlayError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise R5ResolutionOverlayError(f"JSON root must be an object: {path}")
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise R5ResolutionOverlayError(f"resolution evidence is missing: {relative}")
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _all_hw_ops(typed: Mapping[str, Any]) -> list[str]:
    items = typed.get("hw_ops")
    if not isinstance(items, list) or len(items) != 133:
        raise R5ResolutionOverlayError("typed contract must contain 133 stages")
    result = [str(item.get("hw_op_id")) for item in items if isinstance(item, Mapping)]
    if len(result) != 133 or len(set(result)) != 133:
        raise R5ResolutionOverlayError("typed contract hardware stage identities differ")
    return result


def _validate_conv_transport(root: Path, value: Mapping[str, Any]) -> list[str]:
    if value.get("status") != "resolved_for_closed_conv_instances" or value.get("former_blocker") != TRANSPORT_BLOCKER:
        raise R5ResolutionOverlayError("Conv typed transport contract is not resolved")
    result: list[str] = []
    for instance in value.get("instances", []):
        if not isinstance(instance, Mapping):
            raise R5ResolutionOverlayError("malformed Conv transport instance")
        path = root / str(instance.get("path"))
        if (
            not path.is_file()
            or instance.get("sha256") != sha256_file(path)
            or instance.get("size_bytes") != path.stat().st_size
            or instance.get("validation", {}).get("status") != "typed_transport_validated"
        ):
            raise R5ResolutionOverlayError("Conv typed transport evidence differs")
        ids = instance.get("hw_op_ids")
        if not isinstance(ids, list) or len(ids) != 2:
            raise R5ResolutionOverlayError("Conv transport must bind accumulate and requant stages")
        result.extend(str(item) for item in ids)
    if len(result) != 6 or len(set(result)) != 6:
        raise R5ResolutionOverlayError("Conv transport closure must bind exactly six stages")
    return sorted(result)


def _validate_mapping_bundle(root: Path) -> dict[str, Any]:
    manifest_path = root / "bundle_manifest.json"
    manifest = _load(manifest_path)
    if (
        manifest.get("schema") != "operator-config-mapping-evidence-bundle-v1"
        or manifest.get("read_only_native_source") is not True
        or manifest.get("summary", {}).get("valid") is not True
        or manifest.get("summary", {}).get("penalty") != 0.0
        or manifest.get("summary", {}).get("fallback_used") is not False
    ):
        raise R5ResolutionOverlayError("MaxPool mapping evidence is not exact zero penalty")
    files = manifest.get("files")
    if not isinstance(files, Mapping) or not files:
        raise R5ResolutionOverlayError("MaxPool mapping bundle file manifest is missing")
    for relative, item in files.items():
        path = root / str(relative)
        if (
            not isinstance(item, Mapping)
            or not path.is_file()
            or item.get("size") != path.stat().st_size
            or item.get("sha256") != sha256_file(path)
        ):
            raise R5ResolutionOverlayError(
                f"MaxPool mapping bundle file differs: {relative}"
            )
    if (
        manifest.get("source_config_sha256")
        != files.get("source_config.json", {}).get("sha256")
        or manifest.get("mapping_evidence_sha256")
        != files.get("mapping_evidence.json", {}).get("sha256")
        or manifest.get("artifact_validation_report_sha256")
        != files.get("artifact_validation_report.json", {}).get("sha256")
    ):
        raise R5ResolutionOverlayError("MaxPool mapping manifest bindings differ")
    return manifest


def _validate_maxpool_chain(root: Path) -> dict[str, Any]:
    guarded_rel = "artifacts/operator_config_validation/r5-maxpool-node0002-guarded-wave0-v1"
    mapping_rel = (
        "artifacts/operator_config_validation/r5-patched-mapping-evidence/"
        "maxpool-node0002-guarded-address-bound-v2"
    )
    execplan_rel = (
        "artifacts/operator_config_validation/r5-patched-execplan-evidence/"
        "maxpool-node0002-guarded-wave0-v3"
    )
    address_rel = (
        "configs/native_ndp_sim/"
        "maxpool_config_16_112_112_stride2_padding1_guarded_address_bound_v2"
    )
    guarded = validate_guarded_wave0(root, root / guarded_rel)
    address = validate_address_bound_config(root / address_rel, project_root=root)
    mapping_root = root / mapping_rel
    mapping = _validate_mapping_bundle(mapping_root)
    execplan_root = root / execplan_rel
    bundle = _load(execplan_root / "bundle_manifest.json")
    request = _load(execplan_root / "request_address_validation_report.json")
    if (
        bundle.get("request_address_validation_report", {}).get("valid") is not True
        or request.get("valid") is not True
        or request.get("facts", {}).get("request_count_with_multiplicity") != 1_517_936
        or guarded.get("summary", {}).get("independent_mismatch_count") != 0
        or mapping.get("source_config_sha256")
        != address.get("bound_config", {}).get("sha256")
    ):
        raise R5ResolutionOverlayError("MaxPool guarded execplan identity differs")
    streams = request.get("facts", {}).get("stages", [{}])[0].get("streams", [])
    read_streams = [
        item
        for item in streams
        if isinstance(item, Mapping) and item.get("resource") == "READ_STREAM0"
    ]
    if len(read_streams) != 28:
        raise R5ResolutionOverlayError("MaxPool request proof must cover 28 read streams")
    for item in read_streams:
        proof = item.get("logical_storage_proof")
        if (
            not isinstance(proof, Mapping)
            or proof.get("valid") is not True
            or proof.get("logical_address_mismatch_count") != 0
            or proof.get("padding_mask_mismatch_count") != 0
            or proof.get("logical_payload_byte_count_with_multiplicity") != 200_704
            or proof.get("padding_masked_byte_count_with_multiplicity") != 3_600
        ):
            raise R5ResolutionOverlayError("MaxPool per-slice logical storage proof differs")
    return {
        "guarded_transport": _binding(root, f"{guarded_rel}/manifest.json"),
        "zero_padding_contract": _binding(root, "contracts/maxpool_node0002_zero_padding_contract.json"),
        "rtl_semantics": _binding(root, "contracts/maxpool_rtl_semantics_evidence.json"),
        "strict_materialization": _binding(
            root,
            "configs/native_ndp_sim/maxpool_config_16_112_112_stride2_padding1_strict_v1/manifest.json",
        ),
        "address_bound_materialization": _binding(root, f"{address_rel}/manifest.json"),
        "mapping_bundle": _binding(root, f"{mapping_rel}/bundle_manifest.json"),
        "execplan_bundle": _binding(root, f"{execplan_rel}/bundle_manifest.json"),
        "request_address_proof": _binding(root, f"{execplan_rel}/request_address_validation_report.json"),
        "summary": {
            "slice_count": 28,
            "request_count_with_multiplicity": 1_517_936,
            "logical_payload_bytes_checked_with_multiplicity": 28 * 200_704,
            "padding_masked_bytes_checked_with_multiplicity": 28 * 3_600,
            "logical_address_mismatch_count": 0,
            "padding_mask_mismatch_count": 0,
            "independent_w3_mismatch_count": 0,
            "mapping_penalty": mapping["summary"]["penalty"],
            "execplan_sha256": bundle["execplan"]["sha256"],
        },
    }


def _validate_gap_sum_semantics(root: Path) -> dict[str, Any]:
    contract_rel = (
        "contracts/operator_config/gap_sum_zero_padding_contract_v1.json"
    )
    strict_rel = (
        "configs/native_ndp_sim/avgpool_config_2048_7_7_strict_v1"
    )
    reduction_rel = (
        "contracts/operator_config/deepseek_reduction_rules_v1.json"
    )
    contract = validate_gap_sum_zero_padding_contract(
        root, root / contract_rel
    )
    manifest = validate_materialized_strict_config(root / strict_rel)
    reduction = _load(root / reduction_rel)
    validate_deepseek_reduction_rules(reduction, root)
    semantics = contract.get("operator_semantics")
    contract_binding = manifest.get("operator_padding_contract")
    reduction_gap = reduction.get("gap_resolution")
    if (
        not isinstance(semantics, Mapping)
        or semantics.get("request_id") != f"r5:{GAP_SUM_HW_OP_ID}"
        or semantics.get("operator") != "GlobalAverageSumInt32"
        or semantics.get("input_zero_point") != 0
        or semantics.get("spatial_element_count") != 49
        or semantics.get("lane_count") != 8
        or semantics.get("lane_opcode") != "int32_sum"
        or semantics.get("additive_identity_byte") != 0
        or manifest.get("source", {}).get("path")
        != "ndp-sim/jsons/avgpool_config_2048_7_7.json"
        or not isinstance(contract_binding, Mapping)
        or contract_binding.get("path") != contract_rel
        or contract_binding.get("sha256")
        != sha256_file(root / contract_rel)
        or contract_binding.get("contract_sha256")
        != contract.get("contract_sha256")
        or not isinstance(reduction_gap, Mapping)
        or reduction_gap.get("request_id") != f"r5:{GAP_SUM_HW_OP_ID}"
        or reduction_gap.get("resolved_local_blockers")
        != [
            "B_EXECPLAN_TYPED_TRANSPORT",
            "B_SUM_COMPLETION",
            "B_SUM_CROSS_SLICE",
        ]
        or reduction_gap.get("exact_schedule", {}).get(
            "wave_active_slice_counts"
        )
        != [16]
        or reduction_gap.get("cross_slice_classification", {}).get(
            "required"
        )
        is not False
    ):
        raise R5ResolutionOverlayError(
            "GAP exact template/strict semantic binding differs"
        )
    return {
        "zero_padding_and_numeric_contract": _binding(root, contract_rel),
        "strict_materialization": _binding(
            root, f"{strict_rel}/manifest.json"
        ),
        "strict_config": _binding(root, f"{strict_rel}/config.json"),
        "deepseek_reduction_rules": _binding(root, reduction_rel),
        "summary": {
            "hw_op_id": GAP_SUM_HW_OP_ID,
            "input_zero_point": semantics["input_zero_point"],
            "spatial_element_count": semantics["spatial_element_count"],
            "lane_count": semantics["lane_count"],
            "lane_opcode": semantics["lane_opcode"],
            "padding_identity": semantics["additive_identity_byte"],
            "strict_config_sha256": manifest["normalized"]["sha256"],
            "wave_active_slice_counts": reduction_gap["exact_schedule"][
                "wave_active_slice_counts"
            ],
            "cross_slice_reduction_required": reduction_gap[
                "cross_slice_classification"
            ]["required"],
            "terminal_possible_last_indices": reduction_gap["completion"][
                "strict_validator"
            ]["possible_last_indices"],
        },
    }


def _validate_dequant_semantics(root: Path) -> dict[str, Any]:
    receipt_rel = (
        "contracts/operator_config/node0077_dequant_generation_receipt_v5.json"
    )
    contract_rel = (
        "contracts/operator_config/node0077_dequant_semantics_evidence_v5.json"
    )
    config_rel = (
        "configs/native_ndp_sim/"
        "resnet50_dequant_node0077_uint8_fp32_strict_v5/config.json"
    )
    e2_root_rel = (
        "artifacts/operator_config_validation/r5-dequant-node0077-e2-v5"
    )
    report_rel = f"{e2_root_rel}/local_e2_report.json"
    manifest_rel = f"{e2_root_rel}/manifest.json"
    request_rel = f"{e2_root_rel}/execplan_request.json"
    dynamic_e4_rel = (
        "server_returns/"
        "dequant_node0077_stockrtl_e4_return_analysis_20260725.json"
    )
    receipt = _load(root / receipt_rel)
    contract = _load(root / contract_rel)
    config = _load(root / config_rel)
    report = _load(root / report_rel)
    manifest = _load(root / manifest_rel)
    request = _load(root / request_rel)
    dynamic_e4 = _load(root / dynamic_e4_rel)
    lowering_request = receipt.get("lowering_request")

    read_receipt = {
        str(item.get("path")): item
        for item in receipt.get("read_receipt", [])
        if isinstance(item, Mapping)
    }
    current_read_paths = (
        ".agents/agent.md",
        ".agents/rules/生成前必读索引.md",
        ".agents/rules/算子配置规则.md",
        ".agents/rules/NDP硬件字段语义.md",
        ".agents/rules/DequantizeLinear算子配置规则.md",
    )
    for relative in current_read_paths:
        item = read_receipt.get(relative)
        if (
            not isinstance(item, Mapping)
            or item.get("sha256") != sha256_file(root / relative)
        ):
            raise R5ResolutionOverlayError(
                f"Dequant generation read receipt differs: {relative}"
            )

    validation = OperatorConfigValidator().validate(
        config,
        source=str(root / config_rel),
        development_mode=True,
    )
    mapping = report.get("mapping")
    roundtrip = report.get("materialized_roundtrip")
    bitstream = report.get("bitstream")
    lifecycle = report.get("execplan_lifecycle")
    numeric = report.get("numeric")
    source_identity = report.get("source_identity")
    dynamic_verdict = dynamic_e4.get("verdict")
    dynamic_lifecycle = dynamic_e4.get("lifecycle")
    dynamic_readback = dynamic_e4.get("formal_readback")
    dynamic_divergence = dynamic_e4.get("earliest_direct_divergence")
    if (
        receipt.get("status")
        != "generation_gate_satisfied_before_json_materialization"
        or not isinstance(lowering_request, Mapping)
        or lowering_request.get("request_id") != f"r5:{DEQUANT_HW_OP_ID}"
        or lowering_request.get("request_sha256")
        != "cb8522a4ba2386ce3c303f5de274b2fa2e130d719c09933c686a11d28d9b7f63"
        or lowering_request.get(
            "identity_is_independent_of_effective_resolution_overlay"
        )
        is not True
        or contract.get("status")
        != "local_e2_candidate_dynamic_e4_e5_pending"
        or contract.get("candidate_release") is not False
        or contract.get("identity", {}).get("hw_op_id") != DEQUANT_HW_OP_ID
        or contract.get("generation_receipt_sha256")
        != receipt.get("receipt_sha256")
        or contract.get("config", {}).get("sha256")
        != sha256_file(root / config_rel)
        or not validation.valid
        or report.get("status")
        != "local_e2_passed_server_e4_e5_pending"
        or report.get("candidate_release") is not False
        or report.get("remaining_blockers") != ["B_DEQUANT_SERVER_E4_E5"]
        or manifest.get("status")
        != "local_e2_passed_server_e4_e5_pending"
        or manifest.get("candidate_release") is not False
        or not isinstance(mapping, Mapping)
        or mapping.get("placement_penalty") != 0
        or mapping.get("fallback_used") is not False
        or mapping.get("historical_cache_reused") is not False
        or mapping.get("encoded_bitstream_constants_verified") is not True
        or not isinstance(roundtrip, Mapping)
        or roundtrip.get("valid") is not True
        or roundtrip.get("hardware_elements_per_slice") != 752
        or roundtrip.get("slice_count") != 28
        or not isinstance(bitstream, Mapping)
        or bitstream.get("two_isolated_toolchains") is not True
        or bitstream.get("full_lifecycle_products_identical") is not True
        or not isinstance(lifecycle, Mapping)
        or lifecycle.get(
            "independent_machine_explanation_roundtrip", {}
        ).get("valid")
        is not True
        or not isinstance(numeric, Mapping)
        or numeric.get("two_stage_bit_exact") is not True
        or numeric.get("affine_mac_bit_mismatch_count") != 12976
        or not isinstance(source_identity, Mapping)
        or source_identity.get("ndp_sim_ref_unchanged") is not True
        or source_identity.get("rtl_modified") is not False
        or request.get("operators", [{}])[0].get("id") != "op0"
        or dynamic_e4.get("schema")
        != "dequant-node0077-stockrtl-e4-return-analysis-v1"
        or dynamic_e4.get("archive_validation", {}).get(
            "package_identity_matches"
        )
        is not True
        or dynamic_e4.get("archive_validation", {}).get("allowlist_only")
        is not True
        or not isinstance(dynamic_verdict, Mapping)
        or dynamic_verdict.get("status") != "E4_FAIL_OR_INCOMPLETE"
        or dynamic_verdict.get("normalized_classification")
        != "FIRST_DYNAMIC_FAILURE"
        or dynamic_verdict.get("dynamic_baseline") != "NO_DYNAMIC_BASELINE"
        or dynamic_verdict.get("candidate_release") is not False
        or dynamic_verdict.get("evidence_level") != "SERVER_INCOMPLETE"
        or dynamic_verdict.get("run_exit_status") != 124
        or dynamic_verdict.get("remaining_blockers")
        != ["B_DEQUANT_SERVER_E4_E5"]
        or dynamic_verdict.get("e5_generation_allowed") is not False
        or dynamic_e4.get("passed_gates", {}).get(
            "functional_rtl_unchanged"
        )
        is not True
        or not isinstance(dynamic_lifecycle, Mapping)
        or dynamic_lifecycle.get("slice_count") != 28
        or dynamic_lifecycle.get("comp_finish_slice_count") != 0
        or not isinstance(dynamic_readback, Mapping)
        or dynamic_readback.get("present_files") != 0
        or dynamic_readback.get("golden_comparison_performed") is not False
        or not isinstance(dynamic_divergence, Mapping)
        or dynamic_divergence.get("checkpoint")
        != "compute_started_not_completed"
        or dynamic_divergence.get("last_proven_boundary")
        != "slice Start Comp"
    ):
        raise R5ResolutionOverlayError("Dequant local E2 evidence identity differs")
    return {
        "generation_receipt": _binding(root, receipt_rel),
        "semantic_contract": _binding(root, contract_rel),
        "strict_config": _binding(root, config_rel),
        "typed_execplan_request": _binding(root, request_rel),
        "local_e2_manifest": _binding(root, manifest_rel),
        "local_e2_report": _binding(root, report_rel),
        "dynamic_e4_return_analysis": _binding(root, dynamic_e4_rel),
        "summary": {
            "hw_op_id": DEQUANT_HW_OP_ID,
            "request_id": f"r5:{DEQUANT_HW_OP_ID}",
            "local_evidence_level": "E2",
            "candidate_release": False,
            "hardware_shape_cwh": [16, 47, 1],
            "slice_count": 28,
            "hardware_elements_per_slice": 752,
            "w3_element_count": 16000,
            "w3_bit_exact": True,
            "affine_mac_mismatch_count": 12976,
            "mapping_penalty": 0,
            "encoded_physical_pe_constants_verified": True,
            "full_lifecycle_two_copy_deterministic": True,
            "dynamic_e4_status": "FIRST_DYNAMIC_FAILURE",
            "dynamic_evidence_level": "SERVER_INCOMPLETE",
            "dynamic_baseline": "NO_DYNAMIC_BASELINE",
            "e4_pass": False,
            "e5_generation_allowed": False,
            "last_proven_dynamic_boundary": "slice Start Comp",
            "completed_slice_count": 0,
            "formal_d_file_count": 0,
            "remaining_blocker": "B_DEQUANT_SERVER_E4_E5",
        },
    }


def _validate_requant_semantics(root: Path) -> dict[str, Any]:
    paths = {
        "generation_receipt": (
            "artifacts/operator_config_validation/"
            "r5-requant-node0001-two-stage-e2-v1/generation_receipt.json"
        ),
        "typed_graph": (
            "artifacts/operator_config_validation/"
            "r5-requant-node0001-two-stage-e2-v1/typed_graph.json"
        ),
        "local_e2_report": (
            "artifacts/operator_config_validation/"
            "r5-requant-node0001-two-stage-e2-v1/local_e2_report.json"
        ),
        "artifact_manifest": (
            "artifacts/operator_config_validation/"
            "r5-requant-node0001-two-stage-e2-v1/manifest.json"
        ),
        "static_config_manifest": (
            "configs/native_ndp_sim/node0001_requant_two_stage_v1/manifest.json"
        ),
        "semantic_contract": (
            "contracts/operator_config/"
            "requant_node0001_two_stage_contract_v1.json"
        ),
        "dynamic_e4_return_analysis": (
            "server_returns/"
            "requant_node0001_stockrtl_e4_return_analysis_20260725.json"
        ),
        "v2_partial_snapshot_analysis": (
            "server_returns/"
            "requant_node0001_e4_v2_partial_12_analysis_20260725.json"
        ),
        "v2_package_manifest": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            "requant_node0001_e4_stockrtl_v2/TEST_PACKAGE_MANIFEST.json"
        ),
        "v2_sca": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            "requant_node0001_e4_stockrtl_v2/workload/runtime/sca_cfg.json"
        ),
        "v2_sca_d": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            "requant_node0001_e4_stockrtl_v2/workload/runtime/sca_cfg_D.json"
        ),
        "dequant_e4_package_manifest": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            "dequant_node0077_stockrtl_e4_onecmd_v1/"
            "TEST_PACKAGE_MANIFEST.json"
        ),
        "dequant_e4_sca": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            "dequant_node0077_stockrtl_e4_onecmd_v1/workload/runtime/"
            "sca_cfg.json"
        ),
        "dequant_e4_sca_d": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            "dequant_node0077_stockrtl_e4_onecmd_v1/workload/runtime/"
            "sca_cfg_D.json"
        ),
    }
    values = {name: _load(root / relative) for name, relative in paths.items()}
    receipt = values["generation_receipt"]
    graph = values["typed_graph"]
    report = values["local_e2_report"]
    artifact_manifest = values["artifact_manifest"]
    static_manifest = values["static_config_manifest"]
    contract = values["semantic_contract"]
    dynamic_e4 = values["dynamic_e4_return_analysis"]
    v2_partial = values["v2_partial_snapshot_analysis"]
    roundtrip = report.get("materialized_roundtrip")
    lifecycle = report.get("lifecycle")
    numeric = report.get("numeric_evidence")
    deterministic = report.get("native_double_rebuild")
    source_identity = report.get("source_identity")
    dynamic_verdict = dynamic_e4.get("verdict")
    dynamic_failure = dynamic_e4.get("first_failure")
    dynamic_evidence = dynamic_e4.get("dynamic_evidence")
    dynamic_boundary = dynamic_e4.get("claim_boundary")
    partial_classification = v2_partial.get("classification")
    partial_compile = v2_partial.get("compile_and_identity")
    partial_progress = v2_partial.get("simulation_progress")
    partial_decision = v2_partial.get("decision")
    workload_scale = build_requant_v2_workload_scale(root)
    operators = graph.get("operators")
    if (
        receipt.get("status")
        != "generation_gate_satisfied_before_json_materialization"
        or receipt.get("request_id") != f"r5:{REQUANT_HW_OP_ID}"
        or receipt.get("request_sha256")
        != "d1521e88ac08c4768c3d4bcd8c66820bc59b0d49b31d4a1c7481c089050fbe9e"
        or not isinstance(operators, list)
        or len(operators) != 48
        or sum(item.get("stage") == "guard" for item in operators) != 24
        or sum(
            item.get("stage") == "round_saturate" for item in operators
        )
        != 24
        or report.get("status")
        != "NODE0001_REQUANT_TWO_STAGE_LOCAL_E2_COMPLETE"
        or report.get("request_id") != f"r5:{REQUANT_HW_OP_ID}"
        or report.get("candidate_release") is not False
        or report.get("formal_target_instance_allowed") is not False
        or report.get("server_package") is not False
        or report.get("dynamic_baseline") != "NO_DYNAMIC_BASELINE"
        or report.get("remaining_blocker") != "B_REQUANT_SERVER_E4_E5"
        or not isinstance(numeric, Mapping)
        or numeric.get("element_count") != 12_845_056
        or numeric.get("negative_element_count") != 3_246_544
        or numeric.get("minus_one_element_count") != 80
        or numeric.get("guard_bitwise_mismatch_count") != 0
        or numeric.get("final_uint8_mismatch_count") != 0
        or numeric.get("replay_sha256") != numeric.get("golden_sha256")
        or not isinstance(roundtrip, Mapping)
        or roundtrip.get("occurrence_count") != 24
        or roundtrip.get("stage_count") != 48
        or roundtrip.get("bitstream_decoded_stage_count") != 48
        or roundtrip.get("consumer_intermediate_external_preload_count")
        != 0
        or roundtrip.get("guard_sfu_load_count") != 1
        or not isinstance(lifecycle, Mapping)
        or lifecycle.get("start_comp_count") != 48
        or lifecycle.get("barrier_count") != 48
        or lifecycle.get("repeat_num") != 48
        or not isinstance(deterministic, Mapping)
        or deterministic.get("deterministic_files_byte_identical") is not True
        or deterministic.get("deterministic_file_count") != 486
        or not isinstance(source_identity, Mapping)
        or source_identity.get("active_ndp_sim_unchanged") is not True
        or source_identity.get("rtl_modified") is not False
        or static_manifest.get("candidate_release") is not False
        or static_manifest.get("formal_target_config") is not False
        or len(static_manifest.get("operator_types", {})) != 9
        or contract.get("status") != "LOCAL_E2_COMPLETE_DYNAMIC_PENDING"
        or contract.get("request_id") != f"r5:{REQUANT_HW_OP_ID}"
        or contract.get("remaining_blockers") != ["B_REQUANT_SERVER_E4_E5"]
        or artifact_manifest.get("schema")
        != "node0001-requant-two-stage-artifact-manifest-v1"
        or dynamic_e4.get("schema")
        != "requant-node0001-stockrtl-e4-return-analysis-v1"
        or dynamic_e4.get("archive_validation", {}).get("allowlist_only")
        is not True
        or dynamic_e4.get("package_identity", {}).get(
            "matches_formal_e4_package"
        )
        is not True
        or not isinstance(dynamic_verdict, Mapping)
        or dynamic_verdict.get("status") != "E4_FAIL_OR_INCOMPLETE"
        or dynamic_verdict.get("classification") != "FIRST_DYNAMIC_FAILURE"
        or dynamic_verdict.get("dynamic_baseline") != "NO_DYNAMIC_BASELINE"
        or dynamic_verdict.get("evidence_level") != "SERVER_INCOMPLETE"
        or dynamic_verdict.get("candidate_release") is not False
        or dynamic_verdict.get("compile_exit_status") != 2
        or dynamic_verdict.get("simulation_started") is not False
        or dynamic_verdict.get("remaining_blockers")
        != ["B_REQUANT_SERVER_E4_E5"]
        or dynamic_verdict.get("e5_generation_allowed") is not False
        or dynamic_e4.get("passed_pre_run_gates", {}).get(
            "stock_functional_rtl_unchanged"
        )
        is not True
        or dynamic_e4.get("passed_pre_run_gates", {}).get(
            "transactional_tb_probe_restored_byte_exact"
        )
        is not True
        or not isinstance(dynamic_failure, Mapping)
        or dynamic_failure.get("checkpoint") != "compile"
        or dynamic_failure.get("tool_error")
        != "Error-[SFCOR] Source file cannot be opened"
        or dynamic_failure.get("missing_include")
        != "native_return_observer.svh"
        or not isinstance(dynamic_evidence, Mapping)
        or dynamic_evidence.get("lifecycle_start_groups") != 0
        or dynamic_evidence.get(
            "historical_guard_actual_nonempty_entries"
        )
        != 0
        or dynamic_evidence.get("formal_readback_actual_present_entries")
        != 0
        or dynamic_evidence.get("numeric_comparison_performed") is not False
        or not isinstance(dynamic_boundary, Mapping)
        or dynamic_boundary.get("failure_class")
        != "server_test_infrastructure_compile_failure"
        or dynamic_boundary.get("not_an_rtl_failure") is not True
        or dynamic_boundary.get("not_a_requant_semantic_failure") is not True
        or dynamic_boundary.get("same_package_rerun_recommended") is not False
        or v2_partial.get("schema")
        != "requant-node0001-e4-v2-partial-return-analysis-v1"
        or v2_partial.get("source", {}).get("archive_safety_passed")
        is not True
        or not isinstance(partial_classification, Mapping)
        or partial_classification.get("return_kind")
        != "RETURN_SNAPSHOT_NONAUTHORITATIVE"
        or partial_classification.get("dynamic_baseline")
        != "NO_DYNAMIC_BASELINE"
        or partial_classification.get("e4_status") != "SERVER_INCOMPLETE"
        or partial_classification.get("hardware_hang_proven") is not False
        or partial_classification.get("rtl_error_proven") is not False
        or partial_classification.get("configuration_error_proven") is not False
        or partial_classification.get("numeric_mismatch_proven") is not False
        or not isinstance(partial_compile, Mapping)
        or partial_compile.get("compile_passed") is not True
        or partial_compile.get("observer_precompile_identity_passed")
        is not True
        or partial_compile.get(
            "observer_restored_byte_exact_after_compile"
        )
        is not True
        or not isinstance(partial_progress, Mapping)
        or partial_progress.get("repeat_num") != 48
        or partial_progress.get("preload_completed") != 178
        or partial_progress.get("preload_bit_exact_readback_passed") != 178
        or partial_progress.get("requant_guard_load_count") != 1
        or partial_progress.get("slice_start_count") != 1
        or partial_progress.get("slice_completion_count") != 0
        or partial_progress.get("formal_readback_count") != 0
        or partial_progress.get("error_marker_count") != 0
        or partial_progress.get("fatal_marker_count") != 0
        or partial_progress.get("timeout_marker_count") != 0
        or partial_progress.get("sim_log_ends_with_lf") is not False
        or not isinstance(partial_decision, Mapping)
        or partial_decision.get("blockers")
        != ["B_REQUANT_SERVER_E4_E5"]
        or workload_scale.get("classification")
        != "FULL_TWO_STAGE_W3_E4_NOT_ATOMIC_SMOKE"
        or workload_scale.get("requant", {}).get("int32_element_count")
        != numeric.get("element_count")
        or workload_scale.get("requant", {}).get("repeat_num")
        != lifecycle.get("repeat_num")
        or workload_scale.get("counts_as_formal_e4_attempt") is not False
        or workload_scale.get("snapshot_proves_hang") is not False
    ):
        raise R5ResolutionOverlayError(
            "node-0001 Requant local E2 evidence identity differs"
        )
    config_root = root / "configs/native_ndp_sim/node0001_requant_two_stage_v1"
    config_files = static_manifest.get("files")
    if not isinstance(config_files, Mapping) or len(config_files) != 10:
        raise R5ResolutionOverlayError("Requant static config exact-set differs")
    for relative, record in config_files.items():
        path = config_root / str(relative)
        if (
            not isinstance(record, Mapping)
            or not path.is_file()
            or record.get("sha256") != sha256_file(path)
            or record.get("size_bytes") != path.stat().st_size
        ):
            raise R5ResolutionOverlayError(
                f"Requant static config binding differs: {relative}"
            )
    return {
        **{
            name: _binding(root, relative)
            for name, relative in paths.items()
        },
        "summary": {
            "hw_op_id": REQUANT_HW_OP_ID,
            "request_id": f"r5:{REQUANT_HW_OP_ID}",
            "local_evidence_level": "E2",
            "candidate_release": False,
            "occurrence_count": 24,
            "stage_count": 48,
            "static_config_type_count": 9,
            "w3_element_count": 12_845_056,
            "negative_element_count": 3_246_544,
            "minus_one_element_count": 80,
            "w3_bit_exact": True,
            "bitstream_decoded_stage_count": 48,
            "two_copy_deterministic_file_count": 486,
            "consumer_intermediate_preload_count": 0,
            "dynamic_e4_status": "FIRST_DYNAMIC_FAILURE",
            "dynamic_evidence_level": "SERVER_INCOMPLETE",
            "dynamic_baseline": "NO_DYNAMIC_BASELINE",
            "failure_class": "server_test_infrastructure_compile_failure",
            "simulation_started": False,
            "lifecycle_start_count": 0,
            "historical_guard_observation_count": 0,
            "formal_d_file_count": 0,
            "e4_pass": False,
            "e5_generation_allowed": False,
            "same_package_rerun_allowed": False,
            "v2_partial_snapshot_return_kind": (
                "RETURN_SNAPSHOT_NONAUTHORITATIVE"
            ),
            "v2_partial_snapshot_counts_as_e4_attempt": False,
            "v2_compile_repair_server_verified": True,
            "v2_simulation_started": True,
            "v2_preload_completed": 178,
            "v2_slice_start_count": 1,
            "v2_slice_completion_count": 0,
            "v2_formal_d_file_count": 0,
            "v2_hardware_hang_proven": False,
            "v2_process_state": "UNKNOWN_CHECK_EXISTING_PROCESS_FIRST",
            "v2_workload_scale": workload_scale,
            "remaining_blocker": "B_REQUANT_SERVER_E4_E5",
        },
    }


def build_r5_resolution_overlay(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    typed = _load(root / "contracts/typed_config_parameter_contract.json")
    validate_typed_config_parameter_contract(typed)
    hw_op_ids = _all_hw_ops(typed)
    known_blockers = {
        str(blocker)
        for item in typed["hw_ops"]
        for binding in item.get("field_bindings", [])
        for blocker in binding.get("blockers", [])
    }
    hardware = _load(root / "contracts/hardware_approval.json")
    if (
        hardware.get("status") != "approved"
        or hardware.get("approval_scope") != "w4_profile_and_physical_layout_only"
        or set(hardware.get("operator_bindings", {}))
        != {"simple", "view", "conv", "maxpool", "add", "global_average_pool", "matmul"}
    ):
        raise R5ResolutionOverlayError("W4 hardware layout approval identity differs")
    transport = _load(root / "contracts/conv_execplan_transport.json")
    transport_ids = _validate_conv_transport(root, transport)
    maxpool_evidence = _validate_maxpool_chain(root)
    gap_sum_evidence = _validate_gap_sum_semantics(root)
    dequant_evidence = _validate_dequant_semantics(root)
    requant_evidence = _validate_requant_semantics(root)
    typed_transport_ids = sorted(
        set(transport_ids)
        | {GAP_SUM_HW_OP_ID, DEQUANT_HW_OP_ID, REQUANT_HW_OP_ID}
    )

    resolution_specs = {
        LAYOUT_BLOCKER: {
            "resolution_id": "r5-resolution-layout-w4-approved-v1",
            "status": "resolved",
            "scope": "all_typed_stages",
            "hw_op_ids": hw_op_ids,
            "evidence": [_binding(root, "contracts/hardware_approval.json")],
            "claim_boundary": "profile and physical layout only; no operator numeric/server claim",
        },
        TRANSPORT_BLOCKER: {
            "resolution_id": (
                "r5-resolution-conv-and-gap-typed-transport-closed-v2"
            ),
            "status": "resolved",
            "scope": (
                "three_exact_closed_conv_instances_and_exact_gap_zero_point_"
                "compile_time_specialization"
            ),
            "hw_op_ids": typed_transport_ids,
            "evidence": [
                _binding(root, "contracts/conv_execplan_transport.json"),
                gap_sum_evidence["deepseek_reduction_rules"],
                dequant_evidence["typed_execplan_request"],
                dequant_evidence["local_e2_report"],
                requant_evidence["typed_graph"],
                requant_evidence["local_e2_report"],
            ],
            "claim_boundary": (
                "only the six listed accumulate/requant stages and "
                "hwop-0071-00 x_zero_point=0 specialization, exact "
                "hwop-0077-00 Dequant typed transport, and exact "
                "hwop-0001-01 two-stage Requant typed transport"
            ),
        },
        "B_REQUANT_TARGET_NUMERICS": {
            "resolution_id": (
                "r5-resolution-hwop0001-requant-two-stage-local-e2-v1"
            ),
            "status": "resolved",
            "scope": (
                "hwop0001_exact_positive_multiplier_yzp0_int32_hwc8_"
                "guard_then_round_saturate"
            ),
            "hw_op_ids": [REQUANT_HW_OP_ID],
            "evidence": [
                requant_evidence["generation_receipt"],
                requant_evidence["typed_graph"],
                requant_evidence["static_config_manifest"],
                requant_evidence["semantic_contract"],
                requant_evidence["artifact_manifest"],
                requant_evidence["local_e2_report"],
            ],
            "claim_boundary": (
                "exact node-0001 local E2 only: positive per-channel "
                "multipliers, y_zero_point=0, 24 occurrences and two-stage "
                "guard/round path; stock-RTL E4/E5 remain unresolved"
            ),
        },
        "B_DEQUANT_STANDALONE": {
            "resolution_id": (
                "r5-resolution-hwop0077-dequant-standalone-local-e2-v1"
            ),
            "status": "resolved",
            "scope": "hwop0077_exact_uint8_16x1000_to_fp32_two_stage_ga",
            "hw_op_ids": [DEQUANT_HW_OP_ID],
            "evidence": [
                dequant_evidence["generation_receipt"],
                dequant_evidence["semantic_contract"],
                dequant_evidence["strict_config"],
                dequant_evidence["typed_execplan_request"],
                dequant_evidence["local_e2_manifest"],
                dequant_evidence["local_e2_report"],
            ],
            "claim_boundary": (
                "exact node-0077 local E2, strict address-unbound JSON, "
                "address-bound two-copy lifecycle and independent W3 golden only; "
                "server E3/E4/E5 and formal release remain unresolved"
            ),
        },
        "B_MAXPOOL_SHAPE_GENERALIZATION": {
            "resolution_id": "r5-resolution-node0002-maxpool-shape-address-v1",
            "status": "resolved",
            "scope": "node0002_exact_112x112x16_tile",
            "hw_op_ids": [MAXPOOL_HW_OP_ID],
            "evidence": [
                maxpool_evidence["guarded_transport"],
                maxpool_evidence["strict_materialization"],
                maxpool_evidence["address_bound_materialization"],
                maxpool_evidence["mapping_bundle"],
                maxpool_evidence["execplan_bundle"],
                maxpool_evidence["request_address_proof"],
            ],
            "claim_boundary": "exact node-0002 local tile only; not arbitrary MaxPool shapes",
        },
        "B_MAXPOOL_UINT8_SEMANTICS": {
            "resolution_id": "r5-resolution-node0002-maxpool-uint8-padding-v1",
            "status": "resolved",
            "scope": "node0002_exact_uint8_zero_padding",
            "hw_op_ids": [MAXPOOL_HW_OP_ID],
            "evidence": [
                maxpool_evidence["zero_padding_contract"],
                maxpool_evidence["rtl_semantics"],
                maxpool_evidence["guarded_transport"],
                maxpool_evidence["request_address_proof"],
            ],
            "claim_boundary": "static/isolated RTL plus local independent numerics; E4/E5 remain required",
        },
        "B_GAP_CENTERED_SUM": {
            "resolution_id": (
                "r5-resolution-hwop0071-gap-centered-sum-zero-zp-v1"
            ),
            "status": "resolved",
            "scope": "hwop0071_exact_16x2048x7x7_zero_point_zero",
            "hw_op_ids": [GAP_SUM_HW_OP_ID],
            "evidence": [
                gap_sum_evidence["zero_padding_and_numeric_contract"],
                gap_sum_evidence["strict_materialization"],
                gap_sum_evidence["strict_config"],
            ],
            "claim_boundary": (
                "exact x_zero_point=0 local eight-lane int32 sum and strict "
                "address-unbound JSON only; typed transport, cross-slice "
                "completion, address binding and E4/E5 remain unresolved"
            ),
        },
        "B_SUM_CROSS_SLICE": {
            "resolution_id": (
                "r5-resolution-hwop0071-gap-sample-local-reduction-v1"
            ),
            "status": "resolved",
            "scope": "hwop0071_exact_batch16_sample_per_slice_schedule",
            "hw_op_ids": [GAP_SUM_HW_OP_ID],
            "evidence": [
                gap_sum_evidence["deepseek_reduction_rules"],
                gap_sum_evidence["strict_config"],
            ],
            "claim_boundary": (
                "the exact reduction axes are spatial and each active slice "
                "owns one complete sample; arbitrary partitioning is not covered"
            ),
        },
        "B_SUM_COMPLETION": {
            "resolution_id": (
                "r5-resolution-hwop0071-gap-terminal-chain-v1"
            ),
            "status": "resolved",
            "scope": "hwop0071_exact_strict_config_terminal_chain",
            "hw_op_ids": [GAP_SUM_HW_OP_ID],
            "evidence": [
                gap_sum_evidence["deepseek_reduction_rules"],
                gap_sum_evidence["strict_materialization"],
            ],
            "claim_boundary": (
                "static terminal-zero and exact authorized template semantics "
                "only; server E3/E4/E5 are not claimed"
            ),
        },
    }
    if not set(resolution_specs) <= known_blockers:
        raise R5ResolutionOverlayError("overlay resolves a blocker absent from the historical contract")
    applications = Counter()
    for item in typed["hw_ops"]:
        hw_op_id = str(item["hw_op_id"])
        for binding in item.get("field_bindings", []):
            for blocker in binding.get("blockers", []):
                spec = resolution_specs.get(str(blocker))
                if spec is not None and hw_op_id in spec["hw_op_ids"]:
                    applications[str(blocker)] += 1
    overlay: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "local_evidence_overlay_active_formal_server_release_not_granted",
        "historical_contract": _binding(root, "contracts/typed_config_parameter_contract.json"),
        "policy": {
            "historical_w4_contract_is_immutable": True,
            "resolution_is_scope_and_hash_bound": True,
            "candidate_config_emission_requires_no_unresolved_config_blockers": True,
            "formal_target_release_requires_separate_e4_e5_approval": True,
            "resolved_blocker_does_not_imply_server_execution": True,
        },
        "resolutions": resolution_specs,
        "application_counts": dict(sorted(applications.items())),
        "maxpool_local_closure": maxpool_evidence["summary"],
        "gap_sum_local_semantics": gap_sum_evidence["summary"],
        "dequant_local_closure": dequant_evidence["summary"],
        "requant_local_closure": requant_evidence["summary"],
    }
    overlay["overlay_sha256"] = sha256_bytes(canonical_json_bytes(overlay))
    return overlay


def validate_r5_resolution_overlay(value: Mapping[str, Any], project_root: Path) -> None:
    if value != build_r5_resolution_overlay(project_root):
        raise R5ResolutionOverlayError("R5 resolution overlay differs from current evidence")


def blocker_resolution(
    overlay: Mapping[str, Any], blocker: str, hw_op_id: str
) -> Mapping[str, Any] | None:
    resolutions = overlay.get("resolutions")
    item = resolutions.get(blocker) if isinstance(resolutions, Mapping) else None
    if (
        isinstance(item, Mapping)
        and item.get("status") == "resolved"
        and hw_op_id in item.get("hw_op_ids", [])
    ):
        return item
    return None


__all__ = [
    "R5ResolutionOverlayError",
    "SCHEMA",
    "blocker_resolution",
    "build_r5_resolution_overlay",
    "validate_r5_resolution_overlay",
]
