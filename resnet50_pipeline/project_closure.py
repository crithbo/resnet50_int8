from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .ndp_patch_toolchain import validate_patchset_manifest
from .network28_audit import audit_network28_candidates
from .maxpool_padding_contract import validate_maxpool_zero_padding_contract
from .maxpool_server_candidate import validate_maxpool_server_candidate
from .node0004_server_candidate import validate_node0004_server_candidate
from .operator_config_artifact_validator import OperatorConfigArtifactValidator
from .r5_lowering_bundle import validate_r5_lowering_bundle
from .r5_resolution_overlay import validate_r5_resolution_overlay
from .server_workload_scale import build_requant_v2_workload_scale
from .operator_semantics_local_closure import (
    validate_operator_semantics_local_closure,
)
from .stage_config_system import validate_stage_config_system
from .stage_json_derivation_matrix import (
    validate_stage_json_derivation_matrix,
)
from .stage_state_lifetime_contract import (
    validate_stage_state_lifetime_contract,
)
from .strict_config_materialization import validate_materialized_strict_config
from .typed_config_parameters import validate_typed_config_parameter_contract


SCHEMA = "resnet50-project-closure-v1"
EXPECTED_NODES = 78
EXPECTED_HW_OPS = 133
EXPECTED_RUNTIME_EDGES = 93


class ProjectClosureError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProjectClosureError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise ProjectClosureError(f"required closure input is missing: {relative}")
    return {"path": relative, "sha256": _sha256(path), "size": path.stat().st_size}


def _candidate_config(root: Path, hw_op: Mapping[str, Any]) -> dict[str, Any]:
    node_index = hw_op["node_id"].split("-")[-1]
    base = f"hwop-{node_index}-00"
    stage = hw_op["stage"]
    paths: list[Path] = []
    if stage == "accumulate":
        candidate = root / "configs" / "conv" / base / "accumulate.json"
        if candidate.is_file():
            paths.append(candidate)
    elif stage == "requantize":
        directory = root / "configs" / "conv" / base / "requant"
        if directory.is_dir():
            paths.extend(sorted(directory.glob("shard-*.json")))
    elif stage == "pool" and hw_op["hw_op_type"] == "MaxPoolUint8":
        directory = root / "configs" / "maxpool" / base
        if directory.is_dir():
            paths.extend(sorted(directory.glob("wave-*.json")))
    digest = hashlib.sha256()
    records = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        sha = _sha256(path)
        records.append({"path": relative, "sha256": sha})
        digest.update(f"{relative}\0{sha}\n".encode("utf-8"))
    return {
        "present": bool(records),
        "file_count": len(records),
        "tree_sha256": digest.hexdigest() if records else None,
        "files": records,
        "authority": "historical_candidate_only",
    }


def _validate_patched_mapping(root: Path, relative: str) -> dict[str, Any]:
    bundle = root / relative
    config = _load(bundle / "source_config.json")
    evidence = _load(bundle / "mapping_evidence.json")
    report = OperatorConfigArtifactValidator().validate(
        config,
        bundle,
        mapping_evidence=evidence,
        source=(bundle / "source_config.json").as_posix(),
    )
    if not report.valid:
        first = report.issues[0]
        raise ProjectClosureError(
            f"patched mapping evidence is invalid: {first.code} at {first.path}"
        )
    return {
        "path": relative,
        "source_config_sha256": _sha256(bundle / "source_config.json"),
        "mapping_evidence_sha256": _sha256(bundle / "mapping_evidence.json"),
        "mapping_review_sha256": _sha256(bundle / "mapping_review.json"),
        "penalty": evidence["penalty"],
        "fallback_used": evidence["fallback_used"],
        "mapping_mode": evidence["mapping_mode"],
        "cache": evidence["cache"],
        "patchset_sha256": evidence["encoder"]["patchset"]["patchset_sha256"],
        "valid": True,
    }


def _validate_patched_execplan(root: Path, relative: str) -> dict[str, Any]:
    bundle = root / relative
    required = {
        "execplan": "execplan_validation_report.json",
        "package": "package_validation_report.json",
        "requests": "request_address_validation_report.json",
        "double_run": "double_run_comparison.json",
        "manifest": "bundle_manifest.json",
    }
    values = {name: _load(bundle / filename) for name, filename in required.items()}
    if not all(values[name].get("valid") is True for name in ("execplan", "package", "requests")):
        raise ProjectClosureError("patched execplan evidence contains a failed validator")
    if values["double_run"].get("equal") is not True:
        raise ProjectClosureError("patched execplan evidence is not double-run deterministic")
    patchset = values["manifest"].get("native_repository", {}).get("patchset")
    if not isinstance(patchset, Mapping):
        raise ProjectClosureError("patched execplan evidence omits patchset identity")
    execplan_path = bundle / "pipeline_output" / "install" / "execplan.txt"
    return {
        "path": relative,
        "bundle_manifest_sha256": _sha256(bundle / "bundle_manifest.json"),
        "execplan_sha256": _sha256(execplan_path),
        "patchset_sha256": patchset.get("patchset_sha256"),
        "deterministic_file_count": len(values["double_run"].get("files", {})),
        "request_count_with_multiplicity": values["requests"]["facts"][
            "request_count_with_multiplicity"
        ],
        "source_config_sha256": values["execplan"]["facts"]["stages"][0][
            "source_config_sha256"
        ],
        "valid": True,
    }


def _validate_dequant_local_chain(root: Path) -> dict[str, Any]:
    paths = {
        "generation_receipt": (
            "contracts/operator_config/"
            "node0077_dequant_generation_receipt_v5.json"
        ),
        "semantic_contract": (
            "contracts/operator_config/"
            "node0077_dequant_semantics_evidence_v5.json"
        ),
        "config": (
            "configs/native_ndp_sim/"
            "resnet50_dequant_node0077_uint8_fp32_strict_v5/config.json"
        ),
        "local_e2_report": (
            "artifacts/operator_config_validation/"
            "r5-dequant-node0077-e2-v5/local_e2_report.json"
        ),
        "stage_candidate": (
            "configs/stage_codegen/"
            "hwop-0077-00-dequant-v1/manifest.json"
        ),
        "dynamic_e4_return_analysis": (
            "server_returns/"
            "dequant_node0077_stockrtl_e4_return_analysis_20260725.json"
        ),
    }
    values = {name: _load(root / relative) for name, relative in paths.items()}
    report = values["local_e2_report"]
    contract = values["semantic_contract"]
    candidate = values["stage_candidate"]
    dynamic_e4 = values["dynamic_e4_return_analysis"]
    dynamic_verdict = dynamic_e4.get("verdict")
    dynamic_lifecycle = dynamic_e4.get("lifecycle")
    dynamic_readback = dynamic_e4.get("formal_readback")
    dynamic_divergence = dynamic_e4.get("earliest_direct_divergence")
    if (
        contract.get("status")
        != "local_e2_candidate_dynamic_e4_e5_pending"
        or contract.get("candidate_release") is not False
        or report.get("status")
        != "local_e2_passed_server_e4_e5_pending"
        or report.get("candidate_release") is not False
        or report.get("mapping", {}).get(
            "encoded_bitstream_constants_verified"
        )
        is not True
        or report.get("materialized_roundtrip", {}).get("valid") is not True
        or candidate.get("status") != "candidate_address_unbound_not_formal"
        or candidate.get("request_id") != "r5:hwop-0077-00"
        or candidate.get("claims", {}).get("formal_target_config") is not False
        or candidate.get("claims", {}).get("hardware_execution") is not False
        or candidate.get("operator_config", {}).get("source_sha256")
        != _sha256(root / paths["config"])
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
        or dynamic_verdict.get("remaining_blockers")
        != ["B_DEQUANT_SERVER_E4_E5"]
        or dynamic_verdict.get("e5_generation_allowed") is not False
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
        raise ProjectClosureError("Dequant local E2/stage candidate chain differs")
    return {
        "status": "local_e2_complete_e4_first_dynamic_failure",
        "bindings": {
            name: _binding(root, relative)
            for name, relative in paths.items()
        },
        "bitstream_sha256": report["bitstream"]["run_a"]["sha256"],
        "execplan_sha256": report["bitstream"]["deterministic_products"][
            "execplan"
        ]["sha256"],
        "materialized_roundtrip_valid": True,
        "candidate_release": False,
        "dynamic_e4_status": "FIRST_DYNAMIC_FAILURE",
        "dynamic_evidence_level": "SERVER_INCOMPLETE",
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "e4_pass": False,
        "e5_generation_allowed": False,
        "last_proven_dynamic_boundary": "slice Start Comp",
        "completed_slice_count": 0,
        "formal_d_file_count": 0,
        "remaining_blockers": ["B_DEQUANT_SERVER_E4_E5"],
    }


def _validate_requant_node0001_local_chain(
    root: Path,
) -> dict[str, Any]:
    paths = {
        "semantic_contract": (
            "contracts/operator_config/"
            "requant_node0001_two_stage_contract_v1.json"
        ),
        "static_config_manifest": (
            "configs/native_ndp_sim/"
            "node0001_requant_two_stage_v1/manifest.json"
        ),
        "local_e2_report": (
            "artifacts/operator_config_validation/"
            "r5-requant-node0001-two-stage-e2-v1/local_e2_report.json"
        ),
        "stage_candidate": (
            "configs/stage_codegen/"
            "hwop-0001-01-requant-v1/manifest.json"
        ),
        "dynamic_e4_return_analysis": (
            "server_returns/"
            "requant_node0001_stockrtl_e4_return_analysis_20260725.json"
        ),
        "v2_partial_snapshot_analysis": (
            "server_returns/"
            "requant_node0001_e4_v2_partial_12_analysis_20260725.json"
        ),
        "v2_final_return_analysis": (
            "server_returns/"
            "requant_node0001_e4_v2_final_return_analysis_20260726.json"
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
    contract = values["semantic_contract"]
    static_manifest = values["static_config_manifest"]
    report = values["local_e2_report"]
    candidate = values["stage_candidate"]
    dynamic_e4 = values["dynamic_e4_return_analysis"]
    v2_partial = values["v2_partial_snapshot_analysis"]
    v2_final = values["v2_final_return_analysis"]
    roundtrip = report.get("materialized_roundtrip", {})
    numeric = report.get("numeric_evidence", {})
    lifecycle = report.get("lifecycle", {})
    rebuild = report.get("native_double_rebuild", {})
    config_set = candidate.get("operator_config_set", {})
    dynamic_verdict = dynamic_e4.get("verdict")
    dynamic_failure = dynamic_e4.get("first_failure")
    dynamic_evidence = dynamic_e4.get("dynamic_evidence")
    dynamic_boundary = dynamic_e4.get("claim_boundary")
    partial_classification = v2_partial.get("classification")
    partial_compile = v2_partial.get("compile_and_identity")
    partial_progress = v2_partial.get("simulation_progress")
    partial_decision = v2_partial.get("decision")
    final_adjudication = v2_final.get("adjudication")
    final_execution = v2_final.get("execution")
    final_lifecycle = v2_final.get("lifecycle")
    final_tracker = v2_final.get("stock_tb_completion_tracker_failure")
    final_readback = v2_final.get("formal_readback")
    final_observer = v2_final.get("transient_guard_observer")
    final_next = v2_final.get("next_action")
    workload_scale = build_requant_v2_workload_scale(root)
    if (
        contract.get("status")
        != "LOCAL_E2_COMPLETE_DYNAMIC_PENDING"
        or contract.get("candidate_release") is not False
        or contract.get("remaining_blockers")
        != ["B_REQUANT_SERVER_E4_E5"]
        or static_manifest.get("request_id") != "r5:hwop-0001-01"
        or static_manifest.get("candidate_release") is not False
        or static_manifest.get("formal_target_config") is not False
        or report.get("status")
        != "NODE0001_REQUANT_TWO_STAGE_LOCAL_E2_COMPLETE"
        or report.get("request_id") != "r5:hwop-0001-01"
        or report.get("candidate_release") is not False
        or report.get("formal_target_instance_allowed") is not False
        or report.get("dynamic_release_ready") is not False
        or report.get("server_package") is not False
        or report.get("dynamic_baseline") != "NO_DYNAMIC_BASELINE"
        or report.get("remaining_blocker")
        != "B_REQUANT_SERVER_E4_E5"
        or numeric.get("element_count") != 12_845_056
        or numeric.get("full_w3_bit_exact") is not True
        or numeric.get("final_uint8_mismatch_count") != 0
        or roundtrip.get("all_materialized_json_strict_valid") is not True
        or roundtrip.get("all_producer_consumer_addresses_identical")
        is not True
        or roundtrip.get("occurrence_count") != 24
        or roundtrip.get("stage_count") != 48
        or roundtrip.get("bitstream_decoded_stage_count") != 48
        or roundtrip.get("guard_sfu_load_count") != 1
        or roundtrip.get("consumer_intermediate_external_preload_count")
        != 0
        or lifecycle.get("start_comp_count") != 48
        or lifecycle.get("barrier_count") != 48
        or lifecycle.get("repeat_num") != 48
        or rebuild.get("deterministic_files_byte_identical") is not True
        or candidate.get("status") != "candidate_address_unbound_not_formal"
        or candidate.get("request_id") != "r5:hwop-0001-01"
        or candidate.get("claims", {}).get("formal_target_config") is not False
        or candidate.get("claims", {}).get("hardware_execution") is not False
        or candidate.get("operator_config") is not None
        or config_set.get("file_count") != 10
        or config_set.get("semantic_identity") is not True
        or config_set.get("strict_json_validation") != "passed"
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
        or not isinstance(dynamic_failure, Mapping)
        or dynamic_failure.get("checkpoint") != "compile"
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
        or v2_final.get("schema")
        != "requant-node0001-e4-v2-final-return-analysis-v1"
        or v2_final.get("return_identity", {}).get(
            "return_receipt_exact_set_and_hashes"
        )
        is not True
        or not isinstance(final_adjudication, Mapping)
        or final_adjudication.get("return_kind")
        != "AUTHORITATIVE_FINALIZER_RETURN"
        or final_adjudication.get("counts_as_formal_e4_attempt") is not True
        or final_adjudication.get(
            "same_run_as_prior_nonauthoritative_12_zip_snapshot"
        )
        is not True
        or final_adjudication.get(
            "prior_snapshot_counts_as_additional_attempt"
        )
        is not False
        or final_adjudication.get("status") != "E4_FAIL_OR_INCOMPLETE"
        or final_adjudication.get("classification") != "FIRST_DYNAMIC_FAILURE"
        or final_adjudication.get("dynamic_baseline") != "NO_DYNAMIC_BASELINE"
        or final_adjudication.get("candidate_release") is not False
        or final_adjudication.get("e5_allowed") is not False
        or not isinstance(final_execution, Mapping)
        or final_execution.get("compile_exit_status") != 0
        or final_execution.get("simulation_exit_status") != 124
        or final_execution.get("run_exit_status") != 124
        or final_execution.get("functional_rtl_unchanged") is not True
        or not isinstance(final_lifecycle, Mapping)
        or final_lifecycle.get("start_group_count") != 48
        or final_lifecycle.get("finish_group_count") != 48
        or final_lifecycle.get("same_mask_fence_pass_count") != 48
        or final_lifecycle.get("all_48_stages_naturally_completed") is not True
        or not isinstance(final_tracker, Mapping)
        or final_tracker.get("classification")
        != "STOCK_TB_COMPLETION_MASK_INCOMPATIBLE"
        or final_tracker.get("mask_aware") is not False
        or final_tracker.get("root_cause_of_run_timeout") is not True
        or not isinstance(final_readback, Mapping)
        or final_readback.get("status") != "not_reached"
        or final_readback.get("actual_file_count") != 0
        or final_readback.get("numeric_mismatch_proven") is not False
        or not isinstance(final_observer, Mapping)
        or final_observer.get("status") != "fail_unresolved"
        or final_observer.get("pass_count") != 0
        or final_observer.get("raw_observer_logs_in_return") is not False
        or not isinstance(final_next, Mapping)
        or final_next.get("rerun_same_full_v2_package") is not False
        or final_next.get("atomic_package")
        != (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            "rq_node0001_atomic2_stock_v1.zip"
        )
        or workload_scale.get("classification")
        != "FULL_TWO_STAGE_W3_E4_NOT_ATOMIC_SMOKE"
        or workload_scale.get("requant", {}).get("int32_element_count")
        != numeric.get("element_count")
        or workload_scale.get("requant", {}).get("repeat_num")
        != lifecycle.get("repeat_num")
        or workload_scale.get("counts_as_formal_e4_attempt") is not False
        or workload_scale.get("snapshot_proves_hang") is not False
    ):
        raise ProjectClosureError(
            "Requant node0001 local E2/stage candidate chain differs"
        )
    return {
        "status": (
            "local_e2_complete_e4_stock_tb_completion_mask_incompatible"
        ),
        "bindings": {
            name: _binding(root, relative)
            for name, relative in paths.items()
        },
        "occurrence_count": 24,
        "physical_stage_count": 48,
        "bitstream_decoded_stage_count": 48,
        "consumer_intermediate_preload_count": 0,
        "candidate_release": False,
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "dynamic_e4_status": "FIRST_DYNAMIC_FAILURE",
        "dynamic_evidence_level": "SERVER_INCOMPLETE",
        "formal_e4_attempt_count": 2,
        "v1_failure_class": "server_test_infrastructure_compile_failure",
        "failure_class": "STOCK_TB_COMPLETION_MASK_INCOMPATIBLE",
        "simulation_started": True,
        "lifecycle_start_count": 48,
        "lifecycle_finish_count": 48,
        "same_mask_fence_count": 48,
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
        "v2_slice_start_count": 48,
        "v2_slice_completion_count": 48,
        "v2_same_mask_fence_count": 48,
        "v2_formal_d_file_count": 0,
        "v2_hardware_hang_proven": False,
        "v2_process_state": "FINALIZED_TIMEOUT_124",
        "v2_final_return_kind": "AUTHORITATIVE_FINALIZER_RETURN",
        "v2_counts_as_formal_e4_attempt": True,
        "v2_failure_class": "STOCK_TB_COMPLETION_MASK_INCOMPATIBLE",
        "v2_guard_observer_status": "fail_unresolved",
        "v2_guard_observer_pass_count": 0,
        "v2_guard_observer_coverage_ratio": (
            final_observer["coverage_ratio"]
        ),
        "v2_guard_observer_root_cause_resolved": False,
        "v2_numeric_mismatch_proven": False,
        "v2_rerun_allowed": False,
        "next_atomic_package": final_next["atomic_package"],
        "v2_workload_scale": workload_scale,
        "remaining_blockers": ["B_REQUANT_SERVER_E4_E5"],
    }


def build_project_closure(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    typed_path = root / "contracts/typed_config_parameter_contract.json"
    graph_path = root / "artifacts/w3/model_graph.json"
    subop_path = root / "artifacts/w3/subop_batch16/manifest.json"
    runtime_path = root / "artifacts/w3/golden_batch16/manifest.json"
    approval_path = root / "contracts/hardware_approval.json"
    patchset_path = root / "contracts/ndp_patch_toolchain_v1.json"
    lowering_bundle_path = root / "contracts/resnet50_r5_lowering_bundle.json"
    resolution_overlay_path = root / "contracts/resnet50_r5_resolution_overlay.json"
    stage_system_path = (
        root / "contracts/operator_config/stage_config_system_v1.json"
    )
    derivation_matrix_path = (
        root
        / "contracts/operator_config/stage_json_derivation_matrix_v1.json"
    )
    lifetime_path = (
        root
        / "contracts/operator_config/stage_state_lifetime_contract_v1.json"
    )
    minimal_two_stage_path = (
        root
        / "contracts/operator_config/minimal_two_stage_lifecycle_v1.json"
    )
    local_closure_path = (
        root
        / "contracts/operator_config/operator_semantics_local_closure_v1.json"
    )
    repos_lock_path = root / "repos.lock.json"

    typed = _load(typed_path)
    validate_typed_config_parameter_contract(typed)
    graph = _load(graph_path)
    subop = _load(subop_path)
    runtime = _load(runtime_path)
    approval = _load(approval_path)
    patchset = _load(patchset_path)
    lowering_bundle = _load(lowering_bundle_path)
    resolution_overlay = _load(resolution_overlay_path)
    stage_system = _load(stage_system_path)
    derivation_matrix = _load(derivation_matrix_path)
    lifetime = _load(lifetime_path)
    minimal_two_stage = _load(minimal_two_stage_path)
    local_closure = _load(local_closure_path)
    repos_lock = _load(repos_lock_path)
    requant_node0001_local_chain = _validate_requant_node0001_local_chain(
        root
    )
    validate_patchset_manifest(patchset, root / "ndp-sim")
    validate_r5_lowering_bundle(lowering_bundle, root)
    validate_r5_resolution_overlay(resolution_overlay, root)
    validate_stage_config_system(stage_system, root)
    validate_stage_json_derivation_matrix(derivation_matrix, root)
    validate_stage_state_lifetime_contract(lifetime, root)
    validate_operator_semantics_local_closure(local_closure, root)
    requant_family_classification = local_closure.get(
        "closed_local_work", {}
    ).get("requantize_uint8_family", {})
    if (
        requant_family_classification.get("request_count") != 54
        or requant_family_classification.get(
            "standard_w3_golden_exact_stage_count"
        )
        != 54
        or requant_family_classification.get(
            "zero_point_zero_numeric_compatible_stage_count"
        )
        != 33
        or requant_family_classification.get(
            "nonzero_zero_point_guard_contradicted_stage_count"
        )
        != 21
        or requant_family_classification.get(
            "physical_materialized_e2_stage_count"
        )
        != 1
        or requant_family_classification.get("new_json_emission_allowed")
        is not False
    ):
        raise ProjectClosureError(
            "Requant full-family numeric classification differs"
        )
    if (
        minimal_two_stage.get("status")
        != "local_e2_complete_dynamic_hardware_pending"
        or minimal_two_stage.get("candidate_release") is not False
        or minimal_two_stage.get("formal_target_config") is not False
        or minimal_two_stage.get("server_package") is not False
        or lifetime.get("minimal_two_stage_lifecycle", {}).get(
            "full_network_projection_allowed"
        )
        is not False
    ):
        raise ProjectClosureError(
            "minimal two-stage lifecycle closure boundary differs"
        )
    network = audit_network28_candidates(graph)

    if len(graph.get("nodes", [])) != EXPECTED_NODES:
        raise ProjectClosureError("model graph is not the frozen 78-node graph")
    if len(typed.get("hw_ops", [])) != EXPECTED_HW_OPS:
        raise ProjectClosureError("typed lowering does not contain 133 stages")
    if network.get("formal_runtime_edge_count") != EXPECTED_RUNTIME_EDGES:
        raise ProjectClosureError("network audit does not contain 93 runtime edges")
    if runtime.get("model_sha256") != graph.get("model_sha256"):
        raise ProjectClosureError("W3 runtime/model graph identities differ")
    if subop.get("runtime_manifest_sha256") != _sha256(runtime_path):
        raise ProjectClosureError("W3 subop manifest does not bind the runtime manifest")
    replays = subop.get("node_replays")
    if not isinstance(replays, dict) or set(replays) != {
        item["node_id"] for item in graph["nodes"]
    }:
        raise ProjectClosureError("W3 subop replay does not exactly cover all graph nodes")
    failed_replays = sorted(
        node_id for node_id, value in replays.items() if value.get("matches_ort") is not True
    )
    if failed_replays:
        raise ProjectClosureError(f"W3 formula replay mismatch: {failed_replays[:3]}")

    blocker_counts: Counter[str] = Counter()
    effective_blocker_counts: Counter[str] = Counter()
    stage_records: list[dict[str, Any]] = []
    candidate_stage_count = 0
    effective_by_id = {
        item["hw_op_id"]: item for item in lowering_bundle["effective_resolutions"]
    }
    for hw_op in typed["hw_ops"]:
        blockers = sorted(
            {
                blocker
                for binding in hw_op["field_bindings"]
                for blocker in binding.get("blockers", [])
            }
        )
        blocker_counts.update(blockers)
        effective = effective_by_id.get(hw_op["hw_op_id"])
        if not isinstance(effective, Mapping):
            raise ProjectClosureError(
                f"effective lowering resolution is missing: {hw_op['hw_op_id']}"
            )
        effective_blocker_counts.update(effective["effective_blockers"])
        candidate = _candidate_config(root, hw_op)
        candidate_stage_count += int(candidate["present"])
        replay = replays[hw_op["node_id"]]
        stage_records.append(
            {
                "hw_op_id": hw_op["hw_op_id"],
                "node_id": hw_op["node_id"],
                "onnx_op_type": hw_op["onnx_op_type"],
                "hw_op_type": hw_op["hw_op_type"],
                "stage": hw_op["stage"],
                "local_formula": replay["formula"],
                "local_formula_matches_ort": True,
                "formal_target_instance_allowed": hw_op[
                    "formal_target_instance_allowed"
                ],
                "blockers": blockers,
                "effective_resolved_blockers": effective["resolved_blockers"],
                "effective_unresolved_blockers": effective["unresolved_blockers"],
                "rtl_semantic_blockers": effective["rtl_semantic_blockers"],
                "effective_blockers": effective["effective_blockers"],
                "local_lowering_resolved": effective["local_lowering_resolved"],
                "readiness_axes": effective["readiness_axes"],
                "local_disposition": effective["disposition"],
                "candidate_config": candidate,
                "e4_rtl_status": "not_run_no_approved_target_config",
                "e5_repeat_status": "not_run_no_e4_result",
            }
        )

    patched_mapping = _validate_patched_mapping(
        root,
        "artifacts/operator_config_validation/r5-patched-mapping-evidence/"
        "decode_summac-seed42-v1",
    )
    patched_execplan = _validate_patched_execplan(
        root,
        "artifacts/operator_config_validation/r5-patched-execplan-evidence/"
        "decode_summac-double-run-v1",
    )
    node0004_mapping = _validate_patched_mapping(
        root,
        "artifacts/operator_config_validation/r5-patched-mapping-evidence/"
        "node0004-accumulate-wave0-nopp-r1-strict-address-bound-seed42-v1",
    )
    node0004_execplan = _validate_patched_execplan(
        root,
        "artifacts/operator_config_validation/r5-patched-execplan-evidence/"
        "node0004-nopp-r1-v2",
    )
    node0004_contract = _load(
        root / "contracts/node0004_accumulate_wave0_nopp_r1_semantic_contract.json"
    )
    maxpool_mapping = _validate_patched_mapping(
        root,
        "artifacts/operator_config_validation/r5-patched-mapping-evidence/"
        "maxpool-node0002-guarded-address-bound-v2",
    )
    maxpool_execplan = _validate_patched_execplan(
        root,
        "artifacts/operator_config_validation/r5-patched-execplan-evidence/"
        "maxpool-node0002-guarded-wave0-v5",
    )
    dequant_local_chain = _validate_dequant_local_chain(root)
    maxpool_candidate = validate_maxpool_server_candidate(
        root,
        root
        / "artifacts/operator_config_validation/r5-server-candidates/"
        "maxpool-node0002-guarded-wave0-v1",
    )
    node0004_candidate = validate_node0004_server_candidate(
        root,
        root
        / "artifacts/operator_config_validation/r5-server-candidates/"
        "node0004-nopp-r1-v2",
    )
    legacy_gemm_mappings = [
        _validate_patched_mapping(
            root,
            "artifacts/operator_config_validation/r5-patched-mapping-evidence/"
            f"{name}-strict-frozen-fab056-v1",
        )
        for name in (
            "prefill_gemm_local",
            "prefill_gemm_local_qkt",
            "prefill_gemm_ring_4slice",
        )
    ]
    maxpool_padding_contract = validate_maxpool_zero_padding_contract(
        root, root / "contracts/maxpool_uint8_zero_padding_contract.json"
    )
    maxpool_strict_manifest = validate_materialized_strict_config(
        root
        / "configs/native_ndp_sim/"
        "maxpool_config_16_16_16_stride2_padding1_strict_v1"
    )
    legacy_maxpool_mapping = _validate_patched_mapping(
        root,
        "artifacts/operator_config_validation/r5-patched-mapping-evidence/"
        "maxpool-16-16-strict-frozen-dc65-v1",
    )
    ref_commits = [
        item.get("commit")
        for item in repos_lock.get("repositories", [])
        if isinstance(item, Mapping) and item.get("name") == "ndp-sim-ref"
    ]
    if len(ref_commits) != 1:
        raise ProjectClosureError("repos.lock does not pin exactly one ndp-sim-ref")
    if {
        patched_mapping["patchset_sha256"],
        patched_execplan["patchset_sha256"],
        node0004_mapping["patchset_sha256"],
        node0004_execplan["patchset_sha256"],
        maxpool_mapping["patchset_sha256"],
        maxpool_execplan["patchset_sha256"],
        *(item["patchset_sha256"] for item in legacy_gemm_mappings),
        legacy_maxpool_mapping["patchset_sha256"],
        patchset["patchset_sha256"],
    } != {patchset["patchset_sha256"]}:
        raise ProjectClosureError("patched mapping/execplan identities differ")
    if (
        node0004_mapping["source_config_sha256"]
        != node0004_execplan["source_config_sha256"]
        or node0004_contract.get("candidate_scope", {}).get("formal_target_config")
        is not False
        or node0004_contract.get("candidate_scope", {}).get("server_execution_claim")
        is not False
    ):
        raise ProjectClosureError("node-0004 candidate identity/scope differs")
    if (
        maxpool_mapping["source_config_sha256"]
        != maxpool_execplan["source_config_sha256"]
        or maxpool_candidate.get("valid") is not True
        or node0004_candidate.get("valid") is not True
    ):
        raise ProjectClosureError("matrix-complete local server candidates differ")
    for item in legacy_gemm_mappings:
        origin = item.get("cache", {}).get("seed", {}).get("origin", {})
        if (
            item.get("mapping_mode") != "frozen-zero-penalty"
            or item.get("penalty") != 0
            or item.get("fallback_used") is not False
            or item.get("cache", {}).get("policy") != "frozen"
            or origin.get("repository") != "ndp-sim-ref"
            or origin.get("commit") != ref_commits[0]
        ):
            raise ProjectClosureError("legacy GEMM residual mapping identity differs")
    maxpool_origin = legacy_maxpool_mapping.get("cache", {}).get("seed", {}).get(
        "origin", {}
    )
    if (
        maxpool_padding_contract.get("authorization", {}).get(
            "formal_target_config"
        )
        is not False
        or maxpool_strict_manifest.get("adjudication", {}).get(
            "normalization_decision"
        )
        != "approved-explicit-zero-padding-operator-contract"
        or legacy_maxpool_mapping.get("mapping_mode") != "frozen-zero-penalty"
        or legacy_maxpool_mapping.get("penalty") != 0
        or legacy_maxpool_mapping.get("fallback_used") is not False
        or legacy_maxpool_mapping.get("cache", {}).get("policy") != "frozen"
        or maxpool_origin.get("repository") != "ndp-sim-ref"
        or maxpool_origin.get("commit") != ref_commits[0]
    ):
        raise ProjectClosureError("legacy MaxPool residual mapping identity differs")

    op_counts = Counter(item["op_type"] for item in graph["nodes"])
    hw_counts = Counter(item["hw_op_type"] for item in typed["hw_ops"])
    formal_ready = sum(
        item["formal_target_instance_allowed"] for item in typed["hw_ops"]
    )
    return {
        "schema": SCHEMA,
        "status": "local_formula_complete_emitters_and_rtl_semantics_gated",
        "model_sha256": graph["model_sha256"],
        "target_profile": patchset["target_profile"],
        "inputs": {
            "model_graph": _binding(root, "artifacts/w3/model_graph.json"),
            "runtime_golden": _binding(
                root, "artifacts/w3/golden_batch16/manifest.json"
            ),
            "subop_golden": _binding(
                root, "artifacts/w3/subop_batch16/manifest.json"
            ),
            "typed_lowering": _binding(
                root, "contracts/typed_config_parameter_contract.json"
            ),
            "hardware_approval": _binding(root, "contracts/hardware_approval.json"),
            "patchset": _binding(root, "contracts/ndp_patch_toolchain_v1.json"),
            "r5_lowering_bundle": _binding(
                root, "contracts/resnet50_r5_lowering_bundle.json"
            ),
            "r5_resolution_overlay": _binding(
                root, "contracts/resnet50_r5_resolution_overlay.json"
            ),
            "stage_config_system": _binding(
                root,
                "contracts/operator_config/stage_config_system_v1.json",
            ),
            "stage_json_derivation_matrix": _binding(
                root,
                "contracts/operator_config/"
                "stage_json_derivation_matrix_v1.json",
            ),
            "stage_state_lifetime": _binding(
                root,
                "contracts/operator_config/"
                "stage_state_lifetime_contract_v1.json",
            ),
            "operator_semantics_local_closure": _binding(
                root,
                "contracts/operator_config/"
                "operator_semantics_local_closure_v1.json",
            ),
            "minimal_two_stage_lifecycle": _binding(
                root,
                "contracts/operator_config/"
                "minimal_two_stage_lifecycle_v1.json",
            ),
            "node0004_strict_materialization": _binding(
                root,
                "configs/native_ndp_sim/node0004_accumulate_wave0_nopp_r1_strict_v1/manifest.json",
            ),
            "node0004_address_bound_materialization": _binding(
                root,
                "configs/native_ndp_sim/node0004_accumulate_wave0_nopp_r1_strict_address_bound_v1/manifest.json",
            ),
            "node0004_semantic_contract": _binding(
                root,
                "contracts/node0004_accumulate_wave0_nopp_r1_semantic_contract.json",
            ),
            "node0004_server_candidate": _binding(
                root,
                "artifacts/operator_config_validation/r5-server-candidates/"
                "node0004-nopp-r1-v2/candidate_manifest.json",
            ),
            "maxpool_node0002_semantic_contract": _binding(
                root,
                "contracts/maxpool_node0002_guarded_wave0_semantic_contract.json",
            ),
            "maxpool_node0002_server_candidate": _binding(
                root,
                "artifacts/operator_config_validation/r5-server-candidates/"
                "maxpool-node0002-guarded-wave0-v1/candidate_manifest.json",
            ),
            "maxpool_zero_padding_contract": _binding(
                root, "contracts/maxpool_uint8_zero_padding_contract.json"
            ),
            "maxpool_rtl_semantics_evidence": _binding(
                root, "contracts/maxpool_rtl_semantics_evidence.json"
            ),
            "maxpool_strict_materialization": _binding(
                root,
                "configs/native_ndp_sim/"
                "maxpool_config_16_16_16_stride2_padding1_strict_v1/manifest.json",
            ),
            "repository_lock": _binding(root, "repos.lock.json"),
        },
        "coverage": {
            "node_count": len(graph["nodes"]),
            "hw_op_count": len(typed["hw_ops"]),
            "runtime_edge_count": network["formal_runtime_edge_count"],
            "local_formula_match_count": len(replays),
            "internal_tensor_count": len(subop["internal_tensors"]),
            "operator_counts": dict(sorted(op_counts.items())),
            "hw_op_counts": dict(sorted(hw_counts.items())),
            "network_scenarios_pass": network["all_scenarios_pass"],
            "formal_target_config_ready_count": formal_ready,
            "local_lowering_resolved_count": lowering_bundle["coverage"][
                "local_lowering_resolved_count"
            ],
            "local_lowering_unresolved_count": lowering_bundle["coverage"][
                "local_lowering_unresolved_count"
            ],
            "candidate_config_emission_allowed_count": lowering_bundle["coverage"][
                "candidate_config_emission_allowed_count"
            ],
            "candidate_zero_copy_binding_allowed_count": lowering_bundle["coverage"][
                "candidate_zero_copy_binding_allowed_count"
            ],
            "candidate_config_stage_count": lowering_bundle["coverage"][
                "candidate_config_emission_allowed_count"
            ],
            "historical_candidate_config_stage_count": candidate_stage_count,
            "json_emitter_ready_count": lowering_bundle["coverage"][
                "json_emitter_ready_count"
            ],
            "rtl_semantics_compatible_count": lowering_bundle["coverage"][
                "rtl_semantics_compatible_count"
            ],
            "dynamic_release_ready_count": lowering_bundle["coverage"][
                "dynamic_release_ready_count"
            ],
            "formal_e4_pass_count": 0,
            "formal_e5_pass_count": 0,
            "server_e4_attempt_count": 3,
            "server_e4_first_dynamic_failure_count": 3,
            "server_e4_incomplete_count": 3,
            "server_e4_compile_infrastructure_failure_count": 1,
            "server_e4_compute_started_not_completed_count": 1,
            "server_e4_stock_tb_completion_mask_incompatible_count": 1,
            "server_e4_nonauthoritative_snapshot_count": 1,
            "server_e4_compile_fix_verified_snapshot_count": 1,
            "typed_lowering_request_count": lowering_bundle["coverage"][
                "request_count"
            ],
            "typed_lowering_request_set_sha256": lowering_bundle[
                "request_set_sha256"
            ],
            "local_candidate_execplan_chain_count": 2,
            "requant_numeric_classified_stage_count": 54,
            "requant_current_guard_compatible_stage_count": 33,
            "requant_current_guard_contradicted_stage_count": 21,
            "requant_materialized_e2_stage_count": 1,
            "local_two_stage_lifecycle_probe_count": 1,
            "historical_local_execplan_chain_count": 3,
            "matrix_complete_server_candidate_count": 0,
            "historical_matrix_complete_server_package_count": 2,
            "legacy_normalized_zero_penalty_mapping_count": 9,
            "legacy_normalized_mapping_remaining_count": 0,
        },
        "source_strategy": {
            "mode": "hash_bound_project_patchset",
            "active_ndp_sim_read_only": True,
            "base_commit": patchset["base_commit"],
            "patchset_id": patchset["patchset_id"],
            "patchset_sha256": patchset["patchset_sha256"],
            "patched_decode_mapping": patched_mapping,
            "patched_decode_execplan": patched_execplan,
            "patched_node0004_candidate": {
                "scope": (
                    "historical_experimental_liveness_smoke_only_"
                    "sa_int8_numeric_semantics_blocked"
                ),
                "mapping": node0004_mapping,
                "execplan": node0004_execplan,
                "server_candidate": node0004_candidate,
                "semantic_contract_sha256": _sha256(
                    root
                    / "contracts/node0004_accumulate_wave0_nopp_r1_semantic_contract.json"
                ),
            },
            "patched_maxpool_node0002_candidate": {
                "scope": (
                    "historical_matrix_complete_candidate_only_"
                    "ga_int8_max_numeric_and_flow_blocked"
                ),
                "mapping": maxpool_mapping,
                "execplan": maxpool_execplan,
                "server_candidate": maxpool_candidate,
                "semantic_contract_sha256": _sha256(
                    root
                    / "contracts/maxpool_node0002_guarded_wave0_semantic_contract.json"
                ),
            },
            "dequant_node0077_local_candidate": dequant_local_chain,
            "requant_node0001_local_candidate": (
                requant_node0001_local_chain
            ),
            "requant_family_numeric_classification": (
                requant_family_classification
            ),
            "minimal_two_stage_lifecycle": {
                "status": minimal_two_stage["status"],
                "stage_count": 2,
                "producer_consumer_alias": True,
                "independent_config_reload": True,
                "same_mask_barrier_count": 2,
                "repeat_num": 2,
                "dual_golden_bit_exact": True,
                "candidate_release": False,
                "formal_target_config": False,
                "full_network_projection_allowed": False,
                "artifact": minimal_two_stage["artifact"],
            },
            "legacy_gemm_mapping_residuals": {
                "status": "all_legacy_mapping_residuals_closed_with_hash_bound_semantics_and_pinned_caches",
                "reference_commit": ref_commits[0],
                "mappings": legacy_gemm_mappings,
                "maxpool": {
                    "mapping": legacy_maxpool_mapping,
                    "padding_contract_sha256": maxpool_padding_contract[
                        "contract_sha256"
                    ],
                    "scope": "legacy_mapping_closed_not_formal_not_server_run",
                },
                "remaining": [],
            },
        },
        "hardware_layout_authority": {
            "approval_status": approval.get("status"),
            "approval_scope": approval.get("approval_scope"),
            "approval_id": approval.get("approval_id"),
            "deferred_to_w5": approval.get("deferred_to_w5", []),
            "note": "physical-layout approval does not prove per-operator configuration or RTL numerics",
        },
        "blockers": [
            {
                "blocker_id": blocker_id,
                "affected_stage_count": blocker_counts[blocker_id],
                "effective_unresolved_stage_count": effective_blocker_counts[blocker_id],
                "locally_resolved_application_count": resolution_overlay.get(
                    "application_counts", {}
                ).get(blocker_id, 0),
                **typed["blockers"][blocker_id],
            }
            for blocker_id in sorted(
                blocker_counts,
                key=lambda value: (-blocker_counts[value], value),
            )
        ],
        "gates": {
            "w3_independent_formula_replay": "passed_78_of_78",
            "w4_network_layout_and_lifetime_software_audit": "passed_2_scenarios",
            "r5_patched_toolchain_identity": "passed",
            "r5_typed_lowering_requests": "passed_133_of_133_fail_closed",
            "r5_local_resolution_overlay": (
                "passed_5_of_133_local_resolutions_"
                "two_candidate_json_one_zero_copy"
            ),
            "r5_current_rtl_semantic_gate": (
                "dequant_and_exact_node0001_requant_candidate_json_local_e2_"
                "zero_formal_zero_dynamic_release"
            ),
            "r5_dequant_node0077_local_chain": (
                "passed_e2_stage_candidate_materialized_"
                "server_e4_first_dynamic_failure_e5_blocked"
            ),
            "r5_dequant_node0077_dynamic_e4": (
                "first_dynamic_failure_compute_started_not_completed_"
                "zero_formal_d_no_numeric_verdict"
            ),
            "r5_requant_node0001_local_chain": (
                "passed_e2_24_occurrence_48_stage_config_set_"
                "server_e4_stock_tb_completion_mask_incompatible_e5_blocked"
            ),
            "r5_requant_node0001_dynamic_e4": (
                "two_formal_failures_latest_all_48_stages_complete_"
                "stock_tb_tracker_timeout_zero_formal_d"
            ),
            "r5_requant_node0001_v2_partial_snapshot": (
                "nonauthoritative_compile_repair_verified_sim_started_"
                "same_run_as_final_return_not_an_additional_e4_attempt"
            ),
            "r5_requant_family_numeric_classification": (
                "passed_54_of_54_w3_standard_formula_"
                "33_guard_compatible_21_guard_contradicted_"
                "node0001_only_materialized"
            ),
            "r5_minimal_two_stage_lifecycle": (
                "passed_local_e2_alias_config_reload_barrier_"
                "termination_dual_golden_full_network_projection_blocked"
            ),
            "r5_node0004_candidate_local_chain": (
                "historical_matrix_complete_liveness_smoke_"
                "current_sa_int8_semantics_blocked"
            ),
            "r5_maxpool_node0002_local_chain": (
                "historical_guarded_matrix_complete_package_"
                "current_ga_int8_max_semantics_blocked"
            ),
            "r3_legacy_normalized_mapping": "passed_9_of_9_zero_penalty",
            "r5_full_resnet_target_configuration": "blocked_0_of_133_formal",
            "r6_local_numerical_boundary": "passed_formula_scope_only",
            "r6_formal_rtl_e4": (
                "zero_pass_three_formal_attempts_"
                "dequant_compute_incomplete_requant_compile_infrastructure_"
                "requant_stock_tb_mask_incompatible"
            ),
            "r6_formal_rtl_e5": "not_run_requires_two_e4_runs",
            "r7_full_network_package": "blocked_by_r5_r6",
            "r8_full_network_rtl": "blocked_by_r7_and_server",
            "r9_release": "blocked_by_r8",
        },
        "stage_records": stage_records,
        "next_execution_order": [
            "do not generate Dequant E5; its first stock-RTL E4 reached Start Comp on 28 slices but timed out before any Comp Finish or formal D",
            "do not rerun the full Requant v2 package; all 48 stages completed but the non-mask-aware stock TB tracker timed out before SCA_D, so run the prepared slice0+slice1 atomic two-stage package next",
            "classify the remaining Requant stages against the exact positive-multiplier, zero-output-zero-point and guarded-input preconditions before generalization",
            "close one representative per missing hardware family with strict mapping and local E2 evidence",
            "generalize MaxPool beyond node0002 only after representative E4 and repeated E5 server passes",
            "generate all 133 target stages and re-run the 78-node address/lifetime audit",
            "assemble and execute the full-network server package twice before release",
        ],
    }


def validate_project_closure(value: Mapping[str, Any], project_root: Path) -> None:
    expected = build_project_closure(project_root)
    if value != expected:
        raise ProjectClosureError("project closure report differs from current hash-bound inputs")


__all__ = [
    "ProjectClosureError",
    "build_project_closure",
    "validate_project_closure",
]
