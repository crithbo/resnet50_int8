from __future__ import annotations

import copy
import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


SCHEMA = "resnet50-operator-semantics-local-closure-v1"
CONTRACT_PATH = (
    "contracts/operator_config/operator_semantics_local_closure_v1.json"
)
EVIDENCE_PATHS = {
    "stage_operator_semantics_audit": (
        "contracts/operator_config/stage_operator_semantics_audit_v1.json"
    ),
    "stage_config_system": (
        "contracts/operator_config/stage_config_system_v1.json"
    ),
    "stage_json_derivation_matrix": (
        "contracts/operator_config/stage_json_derivation_matrix_v1.json"
    ),
    "gap_d_index_schedule": (
        "contracts/operator_config/gap_d_index_schedule_v1.json"
    ),
    "gap_ga_accumulator_state": (
        "contracts/operator_config/gap_ga_accumulator_state_v1.json"
    ),
    "node0004_requant_semantics": (
        "contracts/operator_config/node0004_requant_semantics_evidence_v1.json"
    ),
    "ga_int32_input_domain_matrix": (
        "contracts/operator_config/ga_int32_input_domain_matrix_v1.json"
    ),
    "stage_state_lifetime": (
        "contracts/operator_config/stage_state_lifetime_contract_v1.json"
    ),
    "minimal_two_stage_lifecycle": (
        "contracts/operator_config/minimal_two_stage_lifecycle_v1.json"
    ),
    "dequant_semantics": (
        "contracts/operator_config/"
        "node0077_dequant_semantics_evidence_v5.json"
    ),
    "dequant_local_e2": (
        "artifacts/operator_config_validation/"
        "r5-dequant-node0077-e2-v5/local_e2_report.json"
    ),
    "requant_node0001_contract": (
        "contracts/operator_config/"
        "requant_node0001_two_stage_contract_v1.json"
    ),
    "requant_node0001_local_e2": (
        "artifacts/operator_config_validation/"
        "r5-requant-node0001-two-stage-e2-v1/local_e2_report.json"
    ),
    "requant_node0001_stage_candidate": (
        "configs/stage_codegen/"
        "hwop-0001-01-requant-v1/manifest.json"
    ),
    "requant_family_contract": (
        "contracts/operator_config/"
        "requant_family_classification_v1.json"
    ),
    "requant_family_report": (
        "artifacts/operator_config_validation/"
        "r5-requant-family-classification-v1/report.json"
    ),
}
PACKAGE_ROOT = (
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "gap_hwop0071_sum_probe_v7"
)
PACKAGE_ZIP = f"{PACKAGE_ROOT}.zip"
PACKAGE_SHA = f"{PACKAGE_ZIP}.sha256"
PACKAGE_MANIFEST = f"{PACKAGE_ROOT}/TEST_PACKAGE_MANIFEST.json"
PACKAGE_ZIP_SHA256 = (
    "c4462033fc4d59ad71121639daed70de1185c5f294264bc3847d22b6bc481893"
)


class OperatorSemanticsLocalClosureError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise OperatorSemanticsLocalClosureError(
            f"cannot load local closure input {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise OperatorSemanticsLocalClosureError(
            f"local closure JSON root must be an object: {path}"
        )
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise OperatorSemanticsLocalClosureError(
            f"required local closure input is missing: {relative}"
        )
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _assert_self_hash(
    value: Mapping[str, Any], field: str, *, label: str
) -> None:
    expected = value.get(field)
    if not isinstance(expected, str) or len(expected) != 64:
        raise OperatorSemanticsLocalClosureError(
            f"{label} has no canonical self hash"
        )
    payload = copy.deepcopy(dict(value))
    if label == "stage_operator_semantics_audit":
        payload[field] = ""
    else:
        del payload[field]
    actual = sha256_bytes(canonical_json_bytes(payload))
    if actual != expected:
        raise OperatorSemanticsLocalClosureError(
            f"{label} canonical self hash differs"
        )


def _package_receipt(root: Path) -> dict[str, Any]:
    package_root = root / PACKAGE_ROOT
    manifest_path = root / PACKAGE_MANIFEST
    zip_path = root / PACKAGE_ZIP
    sha_path = root / PACKAGE_SHA
    if (
        not package_root.is_dir()
        or not manifest_path.is_file()
        or not zip_path.is_file()
        or not sha_path.is_file()
    ):
        raise OperatorSemanticsLocalClosureError(
            "GAP v7 server package directory/ZIP/SHA is incomplete"
        )
    manifest = _load(manifest_path)
    files = manifest.get("files")
    if (
        manifest.get("schema") != "resnet50-gap-probe-test-package-v7"
        or manifest.get("status") != "server_test_package_ready"
        or manifest.get("install_name") != "gap_hwop0071_sum_probe_v7"
        or not isinstance(files, Mapping)
        or len(files) != 119
    ):
        raise OperatorSemanticsLocalClosureError(
            "GAP v7 server package manifest identity differs"
        )
    actual_payload: dict[str, dict[str, Any]] = {}
    for path in sorted(package_root.rglob("*")):
        if path.is_symlink():
            raise OperatorSemanticsLocalClosureError(
                "GAP v7 server package contains a symlink"
            )
        if not path.is_file():
            continue
        relative = path.relative_to(package_root).as_posix()
        if relative == "TEST_PACKAGE_MANIFEST.json":
            continue
        actual_payload[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    if actual_payload != files:
        raise OperatorSemanticsLocalClosureError(
            "GAP v7 server package payload differs from manifest"
        )
    forbidden_rtl = [
        relative
        for relative in files
        if Path(relative).suffix.lower() in {".v", ".sv"}
    ]
    if forbidden_rtl:
        raise OperatorSemanticsLocalClosureError(
            "GAP v7 server package includes functional RTL"
        )

    expected_zip_names = {
        f"{package_root.name}/{path.relative_to(package_root).as_posix()}"
        for path in package_root.rglob("*")
        if path.is_file()
    }
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if (
            len(names) != 120
            or len(names) != len(set(names))
            or set(names) != expected_zip_names
        ):
            raise OperatorSemanticsLocalClosureError(
                "GAP v7 server ZIP file set differs"
            )
        for name in names:
            parts = PurePosixPath(name).parts
            if not parts or parts[0] != package_root.name:
                raise OperatorSemanticsLocalClosureError(
                    f"GAP v7 server ZIP path differs: {name}"
                )
            local_path = package_root.joinpath(*parts[1:])
            if (
                hashlib.sha256(archive.read(name)).hexdigest()
                != sha256_file(local_path)
            ):
                raise OperatorSemanticsLocalClosureError(
                    f"GAP v7 server ZIP payload differs: {name}"
                )
    zip_sha = sha256_file(zip_path)
    if (
        zip_sha != PACKAGE_ZIP_SHA256
        or sha_path.read_text(encoding="ascii")
        != f"{zip_sha}  {zip_path.name}\n"
    ):
        raise OperatorSemanticsLocalClosureError(
            "GAP v7 server ZIP SHA identity differs"
        )
    policy = manifest.get("probe_policy", {})
    return_policy = manifest.get("return_policy", {})
    if (
        policy.get("functional_rtl_v_or_sv_included") is not False
        or policy.get("functional_rtl_modified_by_installer") is not False
        or policy.get("observer_is_read_only") is not True
        or policy.get("ga_accumulator_event_limit") != 512
        or policy.get("waveforms_explicitly_disabled")
        != {"DUMP_VCD": 0, "DUMP_FSDB": 0, "TB_DUMP_FSDB": 0}
        or return_policy.get("allowlist_only") is not True
        or return_policy.get("waveforms_forbidden") is not True
    ):
        raise OperatorSemanticsLocalClosureError(
            "GAP v7 server package safety policy differs"
        )
    return {
        "status": "validated_ready_for_server",
        "manifest": _binding(root, PACKAGE_MANIFEST),
        "zip": _binding(root, PACKAGE_ZIP),
        "sha256_sidecar": _binding(root, PACKAGE_SHA),
        "zip_entry_count": 120,
        "payload_file_count": 119,
        "functional_rtl_v_or_sv_included": False,
        "functional_rtl_modified_by_installer": False,
        "waveforms_enabled": False,
        "expected_return_files": [
            "gap_hwop0071_sum_probe_v7_return.zip",
            "gap_hwop0071_sum_probe_v7_return.zip.sha256",
        ],
    }


def build_operator_semantics_local_closure(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    values = {
        name: _load(root / relative)
        for name, relative in EVIDENCE_PATHS.items()
    }
    hash_fields = {
        "stage_config_system": "system_sha256",
        "dequant_local_e2": "report_sha256",
        "requant_node0001_local_e2": "report_sha256",
        "requant_node0001_stage_candidate": "manifest_sha256",
        "requant_family_report": "report_sha256",
    }
    for name, value in values.items():
        hash_field = hash_fields.get(name, "contract_sha256")
        _assert_self_hash(value, hash_field, label=name)

    audit = values["stage_operator_semantics_audit"]
    system = values["stage_config_system"]
    matrix = values["stage_json_derivation_matrix"]
    gap_d = values["gap_d_index_schedule"]
    gap_ga = values["gap_ga_accumulator_state"]
    requant_counterexample = values["node0004_requant_semantics"]
    ga_domain = values["ga_int32_input_domain_matrix"]
    state = values["stage_state_lifetime"]
    two_stage = values["minimal_two_stage_lifecycle"]
    dequant = values["dequant_semantics"]
    dequant_e2 = values["dequant_local_e2"]
    requant_contract = values["requant_node0001_contract"]
    requant_e2 = values["requant_node0001_local_e2"]
    requant_candidate = values["requant_node0001_stage_candidate"]
    requant_family_contract = values["requant_family_contract"]
    requant_family = values["requant_family_report"]
    package = _package_receipt(root)

    finding_counts = Counter(
        str(item.get("classification"))
        for item in audit.get("findings", [])
        if isinstance(item, Mapping)
    )
    if (
        finding_counts != {"RTL_PROVEN": 20, "CONTRADICTED": 8}
        or system.get("summary", {}).get("stage_count") != 133
        or system.get("summary", {}).get("candidate_json_ready_count") != 2
        or system.get("summary", {}).get("formal_release_stage_count") != 0
        or matrix.get("summary", {}).get("json_leaf_count") != 1784
        or matrix.get("summary", {}).get("current_candidate_json_count") != 1
        or gap_d.get("release", {}).get("resolved_blocker")
        != "B_GAP_D_INDEX_CARRIER_SEMANTICS"
        or gap_ga.get("state_transition_counterexample", {}).get(
            "classification"
        )
        != "CONTRADICTED"
        or requant_counterexample.get("bit_accurate_rtl_replay", {})
        .get("verdict", {})
        .get("rtl_semantics_compatible")
        is not False
        or ga_domain.get("summary", {}).get("stage_count") != 55
        or state.get("ordered_config_plan", {}).get("stage_count") != 133
        or state.get("minimal_two_stage_lifecycle", {}).get(
            "dual_golden_bit_exact"
        )
        is not True
        or state.get("minimal_two_stage_lifecycle", {}).get(
            "full_network_projection_allowed"
        )
        is not False
        or two_stage.get("status")
        != "local_e2_complete_dynamic_hardware_pending"
        or two_stage.get("candidate_release") is not False
        or two_stage.get("formal_target_config") is not False
        or two_stage.get("server_package") is not False
        or dequant.get("status")
        != "local_e2_candidate_dynamic_e4_e5_pending"
        or dequant.get("candidate_release") is not False
        or dequant_e2.get("status")
        != "local_e2_passed_server_e4_e5_pending"
        or dequant_e2.get("candidate_release") is not False
        or dequant_e2.get("mapping", {}).get(
            "encoded_bitstream_constants_verified"
        )
        is not True
        or dequant_e2.get("materialized_roundtrip", {}).get("valid")
        is not True
        or requant_contract.get("status")
        != "LOCAL_E2_COMPLETE_DYNAMIC_PENDING"
        or requant_contract.get("candidate_release") is not False
        or requant_contract.get("remaining_blockers")
        != ["B_REQUANT_SERVER_E4_E5"]
        or requant_e2.get("status")
        != "NODE0001_REQUANT_TWO_STAGE_LOCAL_E2_COMPLETE"
        or requant_e2.get("request_id") != "r5:hwop-0001-01"
        or requant_e2.get("candidate_release") is not False
        or requant_e2.get("formal_target_instance_allowed") is not False
        or requant_e2.get("server_package") is not False
        or requant_e2.get("dynamic_baseline") != "NO_DYNAMIC_BASELINE"
        or requant_e2.get("remaining_blocker")
        != "B_REQUANT_SERVER_E4_E5"
        or requant_e2.get("numeric_evidence", {}).get("element_count")
        != 12_845_056
        or requant_e2.get("numeric_evidence", {}).get("full_w3_bit_exact")
        is not True
        or requant_e2.get("numeric_evidence", {}).get(
            "final_uint8_mismatch_count"
        )
        != 0
        or requant_e2.get("materialized_roundtrip", {}).get(
            "all_materialized_json_strict_valid"
        )
        is not True
        or requant_e2.get("materialized_roundtrip", {}).get(
            "all_producer_consumer_addresses_identical"
        )
        is not True
        or requant_e2.get("materialized_roundtrip", {}).get(
            "occurrence_count"
        )
        != 24
        or requant_e2.get("materialized_roundtrip", {}).get("stage_count")
        != 48
        or requant_e2.get("materialized_roundtrip", {}).get(
            "bitstream_decoded_stage_count"
        )
        != 48
        or requant_e2.get("materialized_roundtrip", {}).get(
            "guard_sfu_load_count"
        )
        != 1
        or requant_e2.get("materialized_roundtrip", {}).get(
            "consumer_intermediate_external_preload_count"
        )
        != 0
        or requant_e2.get("lifecycle", {}).get("barrier_count") != 48
        or requant_e2.get("lifecycle", {}).get("repeat_num") != 48
        or requant_e2.get("native_double_rebuild", {}).get(
            "deterministic_files_byte_identical"
        )
        is not True
        or requant_candidate.get("status")
        != "candidate_address_unbound_not_formal"
        or requant_candidate.get("request_id") != "r5:hwop-0001-01"
        or requant_candidate.get("claims", {}).get("formal_target_config")
        is not False
        or requant_candidate.get("claims", {}).get("hardware_execution")
        is not False
        or requant_candidate.get("operator_config") is not None
        or requant_candidate.get("operator_config_set", {}).get("file_count")
        != 10
        or requant_candidate.get("operator_config_set", {}).get(
            "semantic_identity"
        )
        is not True
        or requant_candidate.get("operator_config_set", {}).get(
            "strict_json_validation"
        )
        != "passed"
        or requant_family_contract.get("status")
        != "NUMERIC_CLASSIFICATION_COMPLETE_PHYSICAL_GENERALIZATION_FAIL_CLOSED"
        or requant_family_contract.get("counts")
        != {
            "total": 54,
            "node0001_full_local_e2": 1,
            "numeric_compatible_physical_e2_pending": 32,
            "current_guard_contradicted": 21,
        }
        or requant_family_contract.get(
            "candidate_json_emission_allowed_ids"
        )
        != ["r5:hwop-0001-01"]
        or requant_family.get("summary", {}).get(
            "standard_w3_golden_exact_stage_count"
        )
        != 54
        or requant_family.get("summary", {}).get(
            "current_guard_numeric_compatible_stage_count"
        )
        != 33
        or requant_family.get("summary", {}).get(
            "current_guard_contradicted_stage_count"
        )
        != 21
        or requant_family.get("summary", {}).get(
            "magic_rounding_counterexample_stage_ids"
        )
        != ["r5:hwop-0014-01"]
        or requant_family.get("emission_boundary", {}).get(
            "node0001_remains_the_only_materialized_candidate"
        )
        is not True
    ):
        raise OperatorSemanticsLocalClosureError(
            "local semantic closure invariants differ"
        )
    gap_stage = next(
        item
        for item in matrix["stages"]
        if item["request_id"] == "r5:hwop-0071-00"
    )
    if (
        gap_stage.get("locally_resolved_blockers")
        != ["B_GAP_D_INDEX_CARRIER_SEMANTICS"]
        or gap_stage.get("stage_blockers") != ["B_GAP_GA_ACCUM_STATE"]
    ):
        raise OperatorSemanticsLocalClosureError(
            "GAP derivation matrix does not consume the D-index resolution"
        )

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": (
            "local_static_analysis_dequant_requant_and_minimal_two_stage_"
            "e2_closed_formal_release_blocked"
        ),
        "inputs": {
            name: _binding(root, relative)
            for name, relative in EVIDENCE_PATHS.items()
        },
        "summary": {
            "stage_count": 133,
            "stage_family_count": 10,
            "audit_finding_count": sum(finding_counts.values()),
            "rtl_proven_finding_count": finding_counts["RTL_PROVEN"],
            "contradicted_finding_count": finding_counts["CONTRADICTED"],
            "representative_derivation_stage_count": 5,
            "projected_json_leaf_count": 1784,
            "gap_d_index_locally_resolved": True,
            "ga_int32_exact_w3_stage_count": 55,
            "ga_int32_counterexample_hit_stage_count": ga_domain["summary"][
                "known_counterexample_hit_stage_count"
            ],
            "sa_stage_count": state["sa_control_boundary"]["stage_count"],
            "conv_shape_signature_count": state["sa_control_boundary"][
                "conv_shape_signature_count"
            ],
            "typed_tensor_edge_count": state["typed_tensor_dag"][
                "edge_count"
            ],
            "logical_view_alias_count": state["ordered_config_plan"][
                "logical_alias_stage_count"
            ],
            "selected_n2n_config_count": state["n2n"][
                "selected_n2n_config_count"
            ],
            "minimal_two_stage_lifecycle_count": 1,
            "candidate_json_count": 2,
            "requant_family_numeric_classified_stage_count": 54,
            "requant_family_current_guard_compatible_stage_count": 33,
            "requant_family_current_guard_contradicted_stage_count": 21,
            "requant_family_materialized_e2_stage_count": 1,
            "formal_release_stage_count": 0,
            "server_test_package_count": 1,
        },
        "closed_local_work": {
            "json_to_rtl": {
                "stable_findings": 28,
                "rtl_proven": 20,
                "contradicted": 8,
                "scope": [
                    "LC and LC_PE",
                    "MSE read/write",
                    "padding and tail",
                    "buffer",
                    "SA",
                    "GA",
                    "N2N",
                ],
            },
            "stage_to_json": {
                "representatives": [
                    "MaxPoolUint8",
                    "GlobalAverageSumInt32",
                    "RequantizeUint8",
                    "View",
                    "DequantizeLinear",
                ],
                "all_projection_leaves_owned": True,
                "gap_projection_uses_corrected_d_index_config": True,
                "gap_remaining_blockers": ["B_GAP_GA_ACCUM_STATE"],
            },
            "dequantize_linear": {
                "request_id": "r5:hwop-0077-00",
                "local_evidence_level": "E2",
                "candidate_json_materialized": True,
                "candidate_release": False,
                "w3_element_count": dequant_e2["numeric"]["element_count"],
                "w3_bit_exact": dequant_e2["numeric"][
                    "two_stage_bit_exact"
                ],
                "affine_mac_mismatch_count": dequant_e2["numeric"][
                    "affine_mac_bit_mismatch_count"
                ],
                "materialized_roundtrip": dequant_e2[
                    "materialized_roundtrip"
                ]["valid"],
                "encoded_physical_pe_constants_verified": dequant_e2[
                    "mapping"
                ]["encoded_bitstream_constants_verified"],
                "remaining_blockers": dequant_e2["remaining_blockers"],
            },
            "requantize_uint8_node0001": {
                "request_id": "r5:hwop-0001-01",
                "local_evidence_level": "E2",
                "candidate_json_set_materialized": True,
                "candidate_release": False,
                "w3_element_count": requant_e2["numeric_evidence"][
                    "element_count"
                ],
                "w3_bit_exact": requant_e2["numeric_evidence"][
                    "full_w3_bit_exact"
                ],
                "occurrence_count": requant_e2[
                    "materialized_roundtrip"
                ]["occurrence_count"],
                "physical_stage_count": requant_e2[
                    "materialized_roundtrip"
                ]["stage_count"],
                "bitstream_decoded_stage_count": requant_e2[
                    "materialized_roundtrip"
                ]["bitstream_decoded_stage_count"],
                "deterministic_rebuild_file_count": requant_e2[
                    "native_double_rebuild"
                ]["deterministic_file_count"],
                "consumer_intermediate_preload_count": requant_e2[
                    "materialized_roundtrip"
                ]["consumer_intermediate_external_preload_count"],
                "remaining_blockers": ["B_REQUANT_SERVER_E4_E5"],
            },
            "requantize_uint8_family": {
                "request_count": requant_family["summary"][
                    "requant_stage_count"
                ],
                "w3_element_count": requant_family["summary"][
                    "w3_element_count"
                ],
                "standard_w3_golden_exact_stage_count": requant_family[
                    "summary"
                ]["standard_w3_golden_exact_stage_count"],
                "zero_point_zero_numeric_compatible_stage_count": (
                    requant_family["summary"][
                        "current_guard_numeric_compatible_stage_count"
                    ]
                ),
                "nonzero_zero_point_guard_contradicted_stage_count": (
                    requant_family["summary"][
                        "current_guard_contradicted_stage_count"
                    ]
                ),
                "guard_recipe_mismatch_count_for_nonzero_zp": (
                    requant_family["summary"][
                        "guard_recipe_mismatch_count_for_nonzero_zp"
                    ]
                ),
                "odd_zero_point_magic_counterexample_stage_ids": (
                    requant_family["summary"][
                        "magic_rounding_counterexample_stage_ids"
                    ]
                ),
                "physical_materialized_e2_stage_count": requant_family[
                    "summary"
                ]["full_materialized_local_e2_stage_count"],
                "new_json_emission_allowed": False,
                "candidate_release": False,
            },
            "gap_d_index": {
                "resolved_blocker": gap_d["release"]["resolved_blocker"],
                "transaction_count": gap_d["numeric_carrier"]["coverage"][
                    "derived_distinct_transaction_bases"
                ],
                "distinct_bias_count": gap_d["numeric_carrier"][
                    "distinct_bias_count"
                ],
                "native_mapping_penalty": gap_d["native_mapping"][
                    "total_penalty"
                ],
            },
            "requant_input_domain": {
                "exact_stage_count": ga_domain["summary"]["stage_count"],
                "exact_element_count": ga_domain["summary"][
                    "total_element_count"
                ],
                "counterexample_hit_stage_count": ga_domain["summary"][
                    "known_counterexample_hit_stage_count"
                ],
                "minus_one_element_count": ga_domain["summary"][
                    "minus_one_element_count"
                ],
                "int_min_element_count": ga_domain["summary"][
                    "int_min_element_count"
                ],
                "blocker_retained": ga_domain["summary"][
                    "retained_blocker"
                ],
            },
            "state_lifetime": {
                "ordered_stage_count": state["ordered_config_plan"][
                    "stage_count"
                ],
                "typed_tensor_edge_count": state["typed_tensor_dag"][
                    "edge_count"
                ],
                "view_exact_byte_equal": state["view"][
                    "exact_byte_equal"
                ],
                "view_logical_zero_copy_proven": state["view"][
                    "logical_zero_copy_proven"
                ],
                "view_physical_zero_copy_proven": state["view"][
                    "physical_zero_copy_proven"
                ],
                "conv_shape_signature_count": state[
                    "sa_control_boundary"
                ]["conv_shape_signature_count"],
                "matmul_mnk": state["sa_control_boundary"][
                    "matmul_logical_signature"
                ]["mnk"],
                "n2n_selected": False,
            },
            "minimal_two_stage_lifecycle": {
                "status": state["minimal_two_stage_lifecycle"]["status"],
                "synthetic_probe_only": True,
                "stage_count": state["minimal_two_stage_lifecycle"][
                    "stage_count"
                ],
                "runtime_sequence": state["minimal_two_stage_lifecycle"][
                    "runtime_sequence"
                ],
                "producer_consumer_alias": True,
                "producer_backed_input_preloaded": False,
                "independent_config_reload": True,
                "repeat_start_barrier_completion_count": 2,
                "dual_golden_bit_exact": True,
                "full_network_projection_allowed": False,
            },
        },
        "remaining_gates": {
            "server_required_now": [],
            "server_required_after_user_authorization": [
                {
                    "gate": "DEQUANT_E4_E5_READBACK",
                    "blocker": "B_DEQUANT_SERVER_E4_E5",
                    "local_e2_proven": True,
                    "package_generated": False,
                    "required_readback": (
                        "28 slices x 752 fp32 values; first 750 bit-exact "
                        "to W3 shard golden and final two +0.0f"
                    ),
                },
                {
                    "gate": "REQUANT_NODE0001_E4_E5_READBACK",
                    "blocker": "B_REQUANT_SERVER_E4_E5",
                    "local_e2_proven": True,
                    "package_generated": False,
                    "required_readback": (
                        "24 occurrences across 48 barrierized stages; historical "
                        "guard values use same-clock accepted-MSE4-write observer, "
                        "final uint8 uses formal SCA_D, and each slice's last "
                        "resident guard uses unique-address formal D; the three "
                        "evidence classes must remain distinct"
                    ),
                    "transient_alias_policy": (
                        "CDA-REQUANT-TRANSIENT-GUARD-E4-001"
                    ),
                },
            ],
            "frozen_server_gates": [
                {
                    "gate": "GAP_GA_EXACT_RUNTIME_OCCURRENCE",
                    "blocker": "B_GAP_GA_ACCUM_STATE",
                    "status": "frozen_by_user",
                    "static_state_counterexample_proven": True,
                    "exact_runtime_occurrence_proven": False,
                    "package": package,
                }
            ],
            "requires_functional_rtl_or_target_decision": [
                "GA int32-to-fp32 conversion for -1 and INT_MIN",
                "GA int32_sum invalid outbuffer-slot reuse",
                "SA INT8 CSA double-shift arithmetic",
                "GA INT8 max numeric/flow path",
            ],
            "requires_released_physical_configs_first": [
                "per-stage CONFIG update/reuse/disable sequence",
                "buffer allocation, byte offset and lifetime",
                "View physical alias identity",
                "physical Conv/MatMul tile, wave, psum and tail schedules",
                "binding the proven two-stage lifecycle invariant to each real "
                "producer/consumer pair",
            ],
            "not_selected": [
                "N2N for current ResNet50 typed plan",
                "functional RTL modification in the diagnostic package",
            ],
        },
        "claim_boundary": {
            "local_analysis_complete_for_plan_0_3_current_scope": True,
            "candidate_json_release_allowed": False,
            "formal_target_release_allowed": False,
            "reason": (
                "all safe static comparisons and exact local tensor-domain "
                "replays in the current read-only RTL scope are bound, including "
                "the DequantizeLinear and exact node0001 RequantizeUint8 local "
                "E2 candidates plus one synthetic native two-stage producer/"
                "consumer lifecycle. Formal release still "
                "requires separately authorized E4/E5 readback; frozen GAP work "
                "and unrelated RTL defects remain independent."
            ),
        },
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_operator_semantics_local_closure(
    value: Mapping[str, Any], project_root: Path
) -> None:
    expected = build_operator_semantics_local_closure(project_root)
    if value != expected:
        raise OperatorSemanticsLocalClosureError(
            "operator semantics local closure differs from hash-bound inputs"
        )


def write_operator_semantics_local_closure(
    path: Path, value: Mapping[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "CONTRACT_PATH",
    "OperatorSemanticsLocalClosureError",
    "SCHEMA",
    "build_operator_semantics_local_closure",
    "validate_operator_semantics_local_closure",
    "write_operator_semantics_local_closure",
]
