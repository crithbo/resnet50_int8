from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_validator import OperatorConfigValidator
from .r5_lowering_bundle import validate_r5_lowering_bundle
from .stage_operator_semantics_audit import (
    GA_INT8_MAX_FLOW_BLOCKER,
    GA_INT8_MAX_NUMERIC_BLOCKER,
    GA_INT32_TO_FP32_DOMAIN_BLOCKER,
    GAP_D_INDEX_BLOCKER,
    GAP_GA_ACCUM_STATE_BLOCKER,
    SA_INT8_CSA_NUMERIC_BLOCKER,
    StageOperatorSemanticsAuditError,
    require_gap_d_index_coverage,
)


CATALOG_SCHEMA = "resnet50-stage-config-backend-catalog-v1"
SCHEDULE_SCHEMA = "resnet50-ndp-schedule-ir-v1"
MANIFEST_SCHEMA = "resnet50-stage-config-candidate-manifest-v1"


class StageConfigBackendError(ValueError):
    pass


class StageConfigBlocked(StageConfigBackendError):
    def __init__(self, request_id: str, blockers: list[str]) -> None:
        self.request_id = request_id
        self.blockers = blockers
        super().__init__(f"stage config emission blocked: {request_id}: {blockers}")


_CATALOG: dict[str, dict[str, Any]] = {
    "MaxPoolUint8": {
        "status": "draft_emitter_implemented_rtl_semantics_blocked",
        "template_paths": [
            "configs/native_ndp_sim/"
            "maxpool_config_16_112_112_stride2_padding1_strict_v1/config.json",
            "configs/native_ndp_sim/"
            "maxpool_config_16_16_16_stride2_padding1_strict_v1/config.json",
        ],
        "remaining_blockers": [
            GA_INT8_MAX_NUMERIC_BLOCKER,
            GA_INT8_MAX_FLOW_BLOCKER,
            "B_SERVER_E4_E5",
        ],
    },
    "View": {
        "status": "zero_copy_binding_implemented",
        "template_paths": [],
        "remaining_blockers": ["B_SERVER_E4_E5_ADJACENT_LAYOUT"],
    },
    "ConvInt32Accumulate": {
        "status": "project_added_wave0_static_evidence_emitter_blocked",
        "template_paths": [
            "configs/native_ndp_sim/"
            "node0004_accumulate_wave0_nopp_r1_strict_v1/config.json"
        ],
        "evidence_paths": [
            "contracts/operator_config/"
            "node0004_conv_schedule_evidence_v1.json"
        ],
        "remaining_blockers": [
            SA_INT8_CSA_NUMERIC_BLOCKER,
            "B_CONV_BIAS_PSUM",
            "B_CONV_INT8_SA",
            "B_CONV_FULL_3WAVE_SCHEDULE",
            "B_CONV_DERIVED_WAVES_VALIDATION",
        ],
    },
    "RequantizeUint8": {
        "status": "candidate_emitter_implemented_local_e2_exact_node0001",
        "template_paths": [
            "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json",
            "ndp-sim/jsons/prefill_silu_fp16MN_fp32MN.json",
        ],
        "evidence_paths": [
            "contracts/operator_config/"
            "requant_node0001_two_stage_contract_v1.json",
            "configs/native_ndp_sim/"
            "node0001_requant_two_stage_v1/manifest.json",
            "artifacts/operator_config_validation/"
            "r5-requant-node0001-two-stage-e2-v1/local_e2_report.json",
            "contracts/operator_config/"
            "requant_family_classification_v1.json",
            "artifacts/operator_config_validation/"
            "r5-requant-family-classification-v1/report.json",
        ],
        "remaining_blockers": [
            "B_REQUANT_SHAPE_LIFETIME_MATERIALIZED_E2",
            "B_REQUANT_NONZERO_ZP_SIGNED_DOMAIN",
            "B_REQUANT_MAGIC_ZP_TIE_PARITY",
            "B_REQUANT_MATMUL_2D_LAYOUT",
            "B_REQUANT_SERVER_E4_E5",
        ],
    },
    "QLinearAddUint8": {
        "status": "related_template_evidence_available_emitter_blocked",
        "template_paths": ["ndp-sim/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json"],
        "remaining_blockers": ["B_ADD_DUAL_QDOMAIN", "B_ADD_REQUANT_E5"],
    },
    "QuantizeLinear": {
        "status": "related_template_evidence_available_emitter_blocked",
        "template_paths": ["ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json"],
        "remaining_blockers": ["B_QUANT_INPUT_DTYPE_PATH", "B_QUANT_E5"],
    },
    "DequantizeLinear": {
        "status": "candidate_emitter_implemented_local_e2",
        "template_paths": [
            "configs/native_ndp_sim/"
            "resnet50_dequant_node0077_uint8_fp32_strict_v5/config.json"
        ],
        "template_derivations": {
            (
                "configs/native_ndp_sim/"
                "resnet50_dequant_node0077_uint8_fp32_strict_v5/config.json"
            ): {
                "kind": "contract_derived_local_e2_candidate",
                "source_path": (
                    "ndp-sim/jsons/"
                    "add_dequant_uint8CWH_uint8CWH_fp32CWH.json"
                ),
                "evidence_paths": [
                    "contracts/operator_config/"
                    "node0077_dequant_generation_receipt_v5.json",
                    "contracts/operator_config/"
                    "node0077_dequant_semantics_evidence_v5.json",
                    "artifacts/operator_config_validation/"
                    "r5-dequant-node0077-e2-v5/local_e2_report.json",
                ],
            }
        },
        "evidence_paths": [
            "contracts/operator_config/"
            "node0077_dequant_generation_receipt_v5.json",
            "contracts/operator_config/"
            "node0077_dequant_semantics_evidence_v5.json",
            "artifacts/operator_config_validation/"
            "r5-dequant-node0077-e2-v5/local_e2_report.json",
        ],
        "remaining_blockers": ["B_DEQUANT_SERVER_E4_E5"],
    },
    "GlobalAverageSumInt32": {
        "status": "candidate_emitter_blocked_by_lc_value_semantics",
        "template_paths": [
            "configs/native_ndp_sim/"
            "avgpool_config_2048_7_7_strict_v1/config.json"
        ],
        "evidence_paths": [
            "contracts/operator_config/"
            "gap_sum_zero_padding_contract_v1.json",
            "contracts/operator_config/"
            "deepseek_reduction_rules_v1.json",
            "contracts/operator_config/"
            "stage_operator_semantics_audit_v1.json",
        ],
        "remaining_blockers": [
            GAP_D_INDEX_BLOCKER,
            GAP_GA_ACCUM_STATE_BLOCKER,
            "B_SERVER_E4_E5",
        ],
    },
    "AverageRequantizeUint8": {
        "status": "related_template_evidence_available_emitter_blocked",
        "template_paths": [
            "ndp-sim/jsons/avgpool_config_2048_7_7.json",
            "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json",
        ],
        "remaining_blockers": [
            GA_INT32_TO_FP32_DOMAIN_BLOCKER,
            "B_GAP_DIVISION_REQUANT",
            "B_GAP_E5",
        ],
    },
    "MatMulInt32Accumulate": {
        "status": "special_array_template_evidence_available_emitter_blocked",
        "template_paths": [
            "configs/native_ndp_sim/prefill_gemm_local_strict_v1/config.json",
            "configs/native_ndp_sim/prefill_gemm_ring_4slice_strict_v1/config.json",
        ],
        "remaining_blockers": [
            SA_INT8_CSA_NUMERIC_BLOCKER,
            "B_MATMUL_INT8_SA_RECIPE",
            "B_MATMUL_TAIL_E5",
        ],
    },
}


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StageConfigBackendError(f"cannot parse JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise StageConfigBackendError(f"JSON root must be an object: {path}")
    return value


def _request_hash(request: Mapping[str, Any]) -> str:
    payload = {key: deepcopy(value) for key, value in request.items() if key != "request_sha256"}
    return sha256_bytes(canonical_json_bytes(payload))


def _request(
    bundle: Mapping[str, Any], request_id: str
) -> dict[str, Any]:
    matches = [
        item
        for item in bundle.get("requests", [])
        if isinstance(item, Mapping) and item.get("request_id") == request_id
    ]
    if len(matches) != 1:
        raise StageConfigBackendError(f"expected exactly one lowering request: {request_id}")
    value = dict(matches[0])
    if value.get("request_sha256") != _request_hash(value):
        raise StageConfigBackendError(f"lowering request hash differs: {request_id}")
    return value


def _resolution(
    bundle: Mapping[str, Any], request_id: str
) -> dict[str, Any]:
    matches = [
        item
        for item in bundle.get("effective_resolutions", [])
        if isinstance(item, Mapping) and item.get("request_id") == request_id
    ]
    if len(matches) != 1:
        raise StageConfigBackendError(
            f"expected exactly one effective resolution: {request_id}"
        )
    return dict(matches[0])


def build_stage_backend_catalog(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    authority_path = (
        root / "contracts/operator_config/operator_config_authority_v1.json"
    )
    if not authority_path.is_file():
        raise StageConfigBackendError(
            "operator configuration authority contract is missing"
        )
    families: dict[str, Any] = {}
    for hw_op_type, entry in sorted(_CATALOG.items()):
        template_records = []
        for relative in entry["template_paths"]:
            path = root / relative
            template_record: dict[str, Any] = {
                "path": relative,
                "exists": path.is_file(),
                "sha256": sha256_file(path) if path.is_file() else None,
            }
            derivation = entry.get("template_derivations", {}).get(relative)
            if derivation is not None:
                source_relative = str(derivation["source_path"])
                source_path = root / source_relative
                template_record["derivation"] = {
                    "kind": derivation["kind"],
                    "source": {
                        "path": source_relative,
                        "exists": source_path.is_file(),
                        "sha256": (
                            sha256_file(source_path)
                            if source_path.is_file()
                            else None
                        ),
                    },
                    "evidence": [
                        {
                            "path": evidence_relative,
                            "exists": (root / evidence_relative).is_file(),
                            "sha256": (
                                sha256_file(root / evidence_relative)
                                if (root / evidence_relative).is_file()
                                else None
                            ),
                        }
                        for evidence_relative in derivation["evidence_paths"]
                    ],
                }
            template_records.append(template_record)
        evidence_records = []
        for relative in entry.get("evidence_paths", []):
            path = root / relative
            evidence_records.append(
                {
                    "path": relative,
                    "exists": path.is_file(),
                    "sha256": sha256_file(path) if path.is_file() else None,
                }
            )
        families[hw_op_type] = {
            **entry,
            "templates": template_records,
            "evidence": evidence_records,
            "template_paths": None,
        }
        del families[hw_op_type]["template_paths"]
        families[hw_op_type].pop("evidence_paths", None)
        families[hw_op_type].pop("template_derivations", None)
    payload: dict[str, Any] = {
        "schema": CATALOG_SCHEMA,
        "configuration_authority": {
            "path": authority_path.relative_to(root).as_posix(),
            "sha256": sha256_file(authority_path),
        },
        "policy": {
            "address_unbound_candidate_only": True,
            "formal_target_config_emission": False,
            "unsupported_family_fails_closed": True,
            "template_presence_does_not_clear_semantic_blockers": True,
            "user_authorized_reference_config_correctness_is_accepted": True,
            "authority_is_scoped_by_upstream_git_provenance": True,
            "project_added_configs_are_not_implicitly_accepted": True,
            "reference_correctness_does_not_preapprove_derived_changes": True,
            "server_e4_e5_required_for_family_promotion": True,
        },
        "summary": {
            "hw_op_type_count": len(families),
            "candidate_emitter_count": sum(
                entry["status"].startswith("candidate_emitter_implemented")
                for entry in families.values()
            ),
            "draft_json_emitter_count": sum(
                entry["status"].startswith("draft_emitter_implemented")
                for entry in families.values()
            ),
            "zero_copy_emitter_count": sum(
                entry["status"] == "zero_copy_binding_implemented"
                for entry in families.values()
            ),
        },
        "families": families,
    }
    payload["catalog_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def _maxpool_schedule(
    root: Path,
    request: Mapping[str, Any],
    resolution: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    geometry = request.get("logical_geometry")
    if not isinstance(geometry, Mapping):
        raise StageConfigBackendError("MaxPool logical geometry is missing")
    expected = {
        "attributes": {
            "auto_pad": "NOTSET",
            "ceil_mode": 0,
            "kernel_shape": [3, 3],
            "pads": [1, 1, 1, 1],
            "storage_order": 0,
            "strides": [2, 2],
        },
        "input_dtypes": ["uint8"],
        "input_shapes": [[16, 64, 112, 112]],
        "output_dtypes": ["uint8"],
        "output_shapes": [[16, 64, 56, 56]],
    }
    if dict(geometry) != expected:
        raise StageConfigBlocked(
            str(request["request_id"]), ["B_MAXPOOL_UNSUPPORTED_LOGICAL_SIGNATURE"]
        )
    if resolution.get("candidate_config_emission_allowed") is not True:
        raise StageConfigBlocked(
            str(request["request_id"]),
            list(
                resolution.get("effective_blockers")
                or ["B_LOCAL_LOWERING"]
            ),
        )

    template_path = (
        root
        / "configs/native_ndp_sim/"
        "maxpool_config_16_112_112_stride2_padding1_strict_v1/config.json"
    )
    template = _load_object(template_path)
    report = OperatorConfigValidator().validate(
        template,
        source=str(template_path),
        development_mode=True,
    )
    if not report.valid:
        raise StageConfigBackendError(
            f"strict MaxPool template no longer validates: {report.to_dict()['first_error']}"
        )
    streams = template.get("stream_engine", {})
    read_stream = next(
        (
            value
            for value in streams.values()
            if isinstance(value, Mapping) and value.get("target") == "A"
        ),
        None,
    )
    write_stream = next(
        (
            value
            for value in streams.values()
            if isinstance(value, Mapping) and value.get("target") == "D"
        ),
        None,
    )
    if read_stream is None or write_stream is None:
        raise StageConfigBackendError("MaxPool template lacks unique A/D stream bindings")
    tile_count = 16 * (64 // 16)
    waves = [min(28, tile_count - start) for start in range(0, tile_count, 28)]
    schedule = {
        "schema": SCHEDULE_SCHEMA,
        "request_id": request["request_id"],
        "request_sha256": request["request_sha256"],
        "hw_op_type": "MaxPoolUint8",
        "stage_role": request["identity"]["stage"],
        "logical_geometry": deepcopy(dict(geometry)),
        "physical_schedule": {
            "layout": "C4HWC4 transported as local HWC16 payload",
            "local_input_tile": [112, 112, 16],
            "local_output_tile": [56, 56, 16],
            "batch_count": 16,
            "channel_tile_count": 4,
            "logical_tile_count": tile_count,
            "slice_capacity_per_wave": 28,
            "wave_active_slice_counts": waves,
            "relative_input_base_addr": read_stream["base_addr"],
            "relative_output_base_addr": write_stream["base_addr"],
            "address_binding": "deferred_to_model_execplan",
        },
        "dataflow": {
            "read_target": "A",
            "write_target": "D",
            "padding_value": read_stream.get("padding_reg_value"),
            "padding_enable": read_stream.get("padding_enable"),
            "tailing_enable": read_stream.get("tailing_enable"),
            "pingpong_enabled": any(
                bool(value.get("ping_pong"))
                for value in streams.values()
                if isinstance(value, Mapping)
            ),
            "compute_array": "general_array",
            "operator": "uint8 max",
        },
        "template": {
            "path": template_path.relative_to(root).as_posix(),
            "sha256": sha256_file(template_path),
            "strict_validation": "passed",
        },
        "emission": {
            "kind": "address_unbound_candidate",
            "formal_target_config": False,
            "semantic_patches": [],
            "remaining_blockers": list(
                resolution.get("formal_release_blockers") or ["B_SERVER_E4_E5"]
            ),
        },
    }
    schedule["schedule_sha256"] = sha256_bytes(canonical_json_bytes(schedule))
    return schedule, template, template_path


def _gap_sum_schedule(
    root: Path,
    request: Mapping[str, Any],
    resolution: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    geometry = request.get("logical_geometry")
    expected = {
        "attributes": {"channels_last": 0},
        "input_dtypes": ["uint8", "uint8"],
        "input_shapes": [[16, 2048, 7, 7], [1]],
        "output_dtypes": ["int32"],
        "output_shapes": [[16, 2048, 1, 1]],
        "reduction": {
            "axes": [2, 3],
            "keepdims": True,
            "spatial_element_count": 49,
        },
    }
    parameters = {
        str(item.get("name")): item
        for item in request.get("typed_parameters", [])
        if isinstance(item, Mapping)
    }
    if (
        not isinstance(geometry, Mapping)
        or dict(geometry) != expected
        or parameters.get("x_zero_point", {})
        .get("value", {})
        .get("scalar")
        != 0
    ):
        raise StageConfigBlocked(
            str(request["request_id"]),
            ["B_GAP_UNSUPPORTED_LOGICAL_OR_ZERO_POINT_SIGNATURE"],
        )
    if resolution.get("candidate_config_emission_allowed") is not True:
        raise StageConfigBlocked(
            str(request["request_id"]),
            list(
                resolution.get("effective_blockers")
                or ["B_GAP_LOCAL_LOWERING"]
            ),
        )
    required_resolutions = {
        "B_EXECPLAN_TYPED_TRANSPORT",
        "B_GAP_CENTERED_SUM",
        "B_LAYOUT_APPROVAL",
        "B_SUM_COMPLETION",
        "B_SUM_CROSS_SLICE",
    }
    if not required_resolutions <= set(
        resolution.get("resolved_blockers", {})
    ):
        raise StageConfigBlocked(
            str(request["request_id"]),
            sorted(
                required_resolutions
                - set(resolution.get("resolved_blockers", {}))
            ),
        )

    template_path = (
        root
        / "configs/native_ndp_sim/"
        "avgpool_config_2048_7_7_strict_v1/config.json"
    )
    template = _load_object(template_path)
    report = OperatorConfigValidator().validate(
        template,
        source=str(template_path),
        development_mode=True,
    )
    if not report.valid:
        raise StageConfigBackendError(
            "strict GAP template no longer validates: "
            f"{report.to_dict()['first_error']}"
        )
    try:
        require_gap_d_index_coverage(template, request)
    except StageOperatorSemanticsAuditError as error:
        raise StageConfigBlocked(
            str(request["request_id"]),
            [GAP_D_INDEX_BLOCKER],
        ) from error
    streams = template.get("stream_engine", {})
    read_stream = next(
        (
            value
            for value in streams.values()
            if isinstance(value, Mapping)
            and value.get("target") == "A"
            and value.get("mode") == "read"
        ),
        None,
    )
    write_stream = next(
        (
            value
            for value in streams.values()
            if isinstance(value, Mapping)
            and value.get("target") == "D"
            and value.get("mode") == "write"
        ),
        None,
    )
    if read_stream is None or write_stream is None:
        raise StageConfigBackendError(
            "GAP template lacks unique A-read/D-write streams"
        )
    completion = report.to_dict().get("facts", {}).get("completion")
    if (
        not isinstance(completion, Mapping)
        or 0 not in completion.get("possible_last_indices", [])
    ):
        raise StageConfigBackendError(
            "GAP template terminal chain no longer reaches zero"
        )
    schedule = {
        "schema": SCHEDULE_SCHEMA,
        "request_id": request["request_id"],
        "request_sha256": request["request_sha256"],
        "hw_op_type": "GlobalAverageSumInt32",
        "stage_role": request["identity"]["stage"],
        "logical_geometry": deepcopy(dict(geometry)),
        "typed_parameter_consumption": {
            "x_zero_point": {
                "value": 0,
                "mode": "compile_time_specialization",
                "effect": (
                    "sum(uint8(x)-0) is emitted as uint8-to-int32 sum and "
                    "zero padding"
                ),
            }
        },
        "physical_schedule": {
            "partition": (
                "one complete NCHW batch sample per active slice; spatial "
                "reduction domain is never split"
            ),
            "batch_count": 16,
            "active_slice_count": 16,
            "slice_capacity_per_wave": 28,
            "wave_active_slice_counts": [16],
            "idle_slice_count": 12,
            "local_input_shape": [2048, 7, 7],
            "local_output_shape": [2048, 1, 1],
            "local_input_bytes": 2048 * 7 * 7,
            "local_output_bytes": 2048 * 4,
            "cross_slice_reduction": False,
            "relative_input_base_addr": read_stream["base_addr"],
            "relative_output_base_addr": write_stream["base_addr"],
            "address_binding": "deferred_to_model_execplan",
        },
        "dataflow": {
            "read_target": "A",
            "write_target": "D",
            "compute_array": "general_array",
            "operator": "eight-lane uint8-to-int32 spatial sum",
            "lane_count": 8,
            "spatial_element_count": 49,
            "padding_value": read_stream.get("padding_reg_value"),
            "completion": deepcopy(dict(completion)),
        },
        "template": {
            "path": template_path.relative_to(root).as_posix(),
            "sha256": sha256_file(template_path),
            "strict_validation": "passed",
            "semantic_relation": (
                "authorized exact upstream template, strict materialization"
            ),
        },
        "emission": {
            "kind": "address_unbound_candidate",
            "formal_target_config": False,
            "semantic_patches": [],
            "remaining_blockers": list(
                resolution.get("formal_release_blockers")
                or ["B_SERVER_E4_E5"]
            ),
        },
    }
    schedule["schedule_sha256"] = sha256_bytes(
        canonical_json_bytes(schedule)
    )
    return schedule, template, template_path


def _dequant_schedule(
    root: Path,
    request: Mapping[str, Any],
    resolution: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    geometry = request.get("logical_geometry")
    expected_geometry = {
        "attributes": {},
        "input_dtypes": ["uint8", "float32", "uint8"],
        "input_shapes": [[16, 1000], [1], [1]],
        "output_dtypes": ["float32"],
        "output_shapes": [[16, 1000]],
    }
    parameters = {
        str(item.get("name")): item
        for item in request.get("typed_parameters", [])
        if isinstance(item, Mapping)
    }
    scale = parameters.get("x_scale", {}).get("value", {})
    zero_point = parameters.get("x_zero_point", {}).get("value", {})
    if (
        not isinstance(geometry, Mapping)
        or dict(geometry) != expected_geometry
        or scale.get("dtype") != "float32"
        or scale.get("shape") != [1]
        or scale.get("float32_bits") != "0x3e01622d"
        or scale.get("value_sha256")
        != "6534c0c5032330f35810bae2a281831411b0597bb0016323624670793dfa12af"
        or zero_point.get("dtype") != "uint8"
        or zero_point.get("shape") != [1]
        or zero_point.get("scalar") != 60
        or zero_point.get("value_sha256")
        != "dabd3aff769f07eb2965401eb029974ebba3407afd02b26ddb564ea5f8efae72"
    ):
        raise StageConfigBlocked(
            str(request["request_id"]),
            ["B_DEQUANT_UNSUPPORTED_LOGICAL_OR_QPARAM_SIGNATURE"],
        )
    if resolution.get("candidate_config_emission_allowed") is not True:
        raise StageConfigBlocked(
            str(request["request_id"]),
            list(
                resolution.get("effective_blockers")
                or ["B_DEQUANT_LOCAL_E2"]
            ),
        )
    required_resolutions = {
        "B_DEQUANT_STANDALONE",
        "B_EXECPLAN_TYPED_TRANSPORT",
        "B_LAYOUT_APPROVAL",
    }
    if not required_resolutions <= set(resolution.get("resolved_blockers", {})):
        raise StageConfigBlocked(
            str(request["request_id"]),
            ["B_DEQUANT_RESOLUTION_PROVENANCE"],
        )

    template_path = (
        root
        / "configs/native_ndp_sim/"
        "resnet50_dequant_node0077_uint8_fp32_strict_v5/config.json"
    )
    template = _load_object(template_path)
    report = OperatorConfigValidator().validate(
        template,
        source=str(template_path),
        development_mode=True,
    )
    if not report.valid:
        raise StageConfigBackendError(
            "strict Dequant template no longer validates: "
            f"{report.to_dict()['first_error']}"
        )
    e2_path = (
        root
        / "artifacts/operator_config_validation/"
        "r5-dequant-node0077-e2-v5/local_e2_report.json"
    )
    e2 = _load_object(e2_path)
    if (
        e2.get("status") != "local_e2_passed_server_e4_e5_pending"
        or e2.get("candidate_release") is not False
        or e2.get("mapping", {}).get("encoded_bitstream_constants_verified")
        is not True
        or e2.get("materialized_roundtrip", {}).get("valid") is not True
        or e2.get("remaining_blockers") != ["B_DEQUANT_SERVER_E4_E5"]
    ):
        raise StageConfigBackendError("Dequant local E2 evidence differs")

    schedule = {
        "schema": SCHEDULE_SCHEMA,
        "request_id": request["request_id"],
        "request_sha256": request["request_sha256"],
        "hw_op_type": "DequantizeLinear",
        "stage_role": request["identity"]["stage"],
        "logical_geometry": deepcopy(dict(geometry)),
        "numeric_order": {
            "formula": "(float32(uint8(x))-60.0f)*float32(x_scale)",
            "first_rounding_point": "fp32 subtract",
            "second_rounding_point": "fp32 multiply",
            "single_affine_mac_allowed": False,
            "w3_bit_exact_element_count": 16000,
            "affine_mac_counterexample_count": 12976,
        },
        "typed_parameter_consumption": {
            "x_scale": {
                "parameter_id": parameters["x_scale"]["parameter_id"],
                "float32_bits": "0x3e01622d",
                "target": "PE10/PE12/PE30/PE32.inport1.constant",
            },
            "x_zero_point": {
                "parameter_id": parameters["x_zero_point"]["parameter_id"],
                "scalar": 60,
                "derived_negative_fp32_bits": "0xc2700000",
                "target": "PE00/PE02/PE20/PE22.inport1.constant",
            },
            "affine_offset": {
                "parameter_id": parameters["affine_offset"]["parameter_id"],
                "consumed": False,
                "reason": (
                    "historical affine offset changes ONNX rounding order and "
                    "is retained only as a typed counterexample"
                ),
            },
        },
        "physical_schedule": {
            "layout_profile": "w4_group4x7_batch_channel28_candidate_v1",
            "hardware_shape_cwh": [16, 47, 1],
            "slice_count": 28,
            "valid_elements_per_slice": 750,
            "hardware_elements_per_slice": 752,
            "a_bytes_per_slice": 752,
            "d_bytes_per_slice": 3008,
            "a_transaction_bytes": 16,
            "d_transaction_bytes": 64,
            "occurrences_per_slice": 47,
            "a_tail_bytes": "3c3c",
            "d_tail_fp32_bits": ["0x00000000", "0x00000000"],
            "address_binding": "deferred_to_model_execplan",
        },
        "dataflow": {
            "read_target": "A",
            "write_target": "D",
            "compute_array": "general_array",
            "outbuffer_path": "normal_non_transout",
            "first_stage": ["PE00", "PE02", "PE20", "PE22"],
            "first_stage_opcode": "add",
            "second_stage": ["PE10", "PE12", "PE30", "PE32"],
            "second_stage_opcode": "mul",
            "links": [
                ["PE00", "PE10"],
                ["PE02", "PE12"],
                ["PE20", "PE30"],
                ["PE22", "PE32"],
            ],
            "output_mask": [0, 1, 0, 1, 0, 1, 0, 1],
        },
        "template": {
            "path": template_path.relative_to(root).as_posix(),
            "sha256": sha256_file(template_path),
            "strict_validation": "passed",
            "semantic_relation": (
                "exact node-0077 local-E2 standalone materialization derived "
                "from the authorized embedded Dequant branch"
            ),
        },
        "local_e2": {
            "path": e2_path.relative_to(root).as_posix(),
            "sha256": sha256_file(e2_path),
            "status": e2["status"],
            "two_isolated_toolchains": True,
            "encoded_physical_pe_constants_verified": True,
        },
        "emission": {
            "kind": "address_unbound_candidate",
            "formal_target_config": False,
            "candidate_release": False,
            "semantic_patches": [],
            "remaining_blockers": ["B_DEQUANT_SERVER_E4_E5"],
        },
    }
    schedule["schedule_sha256"] = sha256_bytes(canonical_json_bytes(schedule))
    return schedule, template, template_path


def _requant_schedule(
    root: Path,
    request: Mapping[str, Any],
    resolution: Mapping[str, Any],
) -> tuple[dict[str, Any], None, None]:
    expected_geometry = {
        "attributes": {
            "auto_pad": "NOTSET",
            "dilations": [1, 1],
            "group": 1,
            "kernel_shape": [7, 7],
            "pads": [3, 3, 3, 3],
            "strides": [2, 2],
        },
        "input_dtypes": ["int32", "float32", "float32", "float32", "uint8"],
        "input_shapes": [
            [16, 64, 112, 112],
            [1],
            [64],
            [1],
            [1],
        ],
        "output_dtypes": ["uint8"],
        "output_shapes": [[16, 64, 112, 112]],
    }
    parameters = {
        str(item.get("name")): item
        for item in request.get("typed_parameters", [])
        if isinstance(item, Mapping)
    }
    multiplier = parameters.get("requant_multiplier", {}).get("value", {})
    zero_point = parameters.get("y_zero_point", {}).get("value", {})
    if (
        request.get("request_id") != "r5:hwop-0001-01"
        or request.get("logical_geometry") != expected_geometry
        or multiplier.get("dtype") != "float32"
        or multiplier.get("shape") != [64]
        or multiplier.get("value_sha256")
        != "7ed3f7e123f3f68c86a141ea0fa562a694ed8bfd4a5014907f8e551ff76e9790"
        or multiplier.get("minimum", 0) <= 0
        or zero_point.get("dtype") != "uint8"
        or zero_point.get("shape") != [1]
        or zero_point.get("scalar") != 0
    ):
        raise StageConfigBlocked(
            str(request["request_id"]),
            ["B_REQUANT_UNSUPPORTED_LOGICAL_OR_QPARAM_SIGNATURE"],
        )
    if resolution.get("candidate_config_emission_allowed") is not True:
        raise StageConfigBlocked(
            str(request["request_id"]),
            list(
                resolution.get("effective_blockers")
                or ["B_REQUANT_NODE0001_LOCAL_E2"]
            ),
        )
    required_resolutions = {
        "B_EXECPLAN_TYPED_TRANSPORT",
        "B_LAYOUT_APPROVAL",
        "B_REQUANT_TARGET_NUMERICS",
    }
    if not required_resolutions <= set(resolution.get("resolved_blockers", {})):
        raise StageConfigBlocked(
            str(request["request_id"]),
            ["B_REQUANT_RESOLUTION_PROVENANCE"],
        )

    config_root = (
        root / "configs/native_ndp_sim/node0001_requant_two_stage_v1"
    )
    config_manifest_path = config_root / "manifest.json"
    e2_path = (
        root
        / "artifacts/operator_config_validation/"
        "r5-requant-node0001-two-stage-e2-v1/local_e2_report.json"
    )
    contract_path = (
        root
        / "contracts/operator_config/"
        "requant_node0001_two_stage_contract_v1.json"
    )
    config_manifest = _load_object(config_manifest_path)
    e2 = _load_object(e2_path)
    contract = _load_object(contract_path)
    files = config_manifest.get("files")
    if (
        config_manifest.get("candidate_release") is not False
        or config_manifest.get("formal_target_config") is not False
        or not isinstance(files, Mapping)
        or len(files) != 10
        or e2.get("status")
        != "NODE0001_REQUANT_TWO_STAGE_LOCAL_E2_COMPLETE"
        or e2.get("candidate_release") is not False
        or e2.get("numeric_evidence", {}).get("final_uint8_mismatch_count")
        != 0
        or e2.get("materialized_roundtrip", {}).get(
            "bitstream_decoded_stage_count"
        )
        != 48
        or e2.get("materialized_roundtrip", {}).get(
            "consumer_intermediate_external_preload_count"
        )
        != 0
        or e2.get("lifecycle", {}).get("barrier_count") != 48
        or e2.get("remaining_blocker") != "B_REQUANT_SERVER_E4_E5"
        or contract.get("status") != "LOCAL_E2_COMPLETE_DYNAMIC_PENDING"
        or contract.get("remaining_blockers")
        != ["B_REQUANT_SERVER_E4_E5"]
    ):
        raise StageConfigBackendError("node-0001 Requant local E2 evidence differs")
    config_bindings: list[dict[str, Any]] = []
    for relative, record in sorted(files.items()):
        path = config_root / str(relative)
        if (
            not isinstance(record, Mapping)
            or not path.is_file()
            or record.get("sha256") != sha256_file(path)
            or record.get("size_bytes") != path.stat().st_size
        ):
            raise StageConfigBackendError(
                f"node-0001 Requant config binding differs: {relative}"
            )
        config_bindings.append(
            {
                "path": str(relative),
                "sha256": record["sha256"],
                "size_bytes": record["size_bytes"],
            }
        )

    schedule: dict[str, Any] = {
        "schema": SCHEDULE_SCHEMA,
        "request_id": request["request_id"],
        "request_sha256": request["request_sha256"],
        "hw_op_type": "RequantizeUint8",
        "stage_role": request["identity"]["stage"],
        "logical_geometry": deepcopy(expected_geometry),
        "numeric_order": {
            "formula": (
                "guard=max(fp32_convert(acc),+0); "
                "scaled=fp32(guard*multiplier[c]); "
                "q=saturate_uint8(round_to_nearest_even(scaled))"
            ),
            "direct_negative_int32_to_requant_mac_allowed": False,
            "guard_sfu_breakpoints": "65x+0.0",
            "guard_sfu_slope0_bits": "0x00000000",
            "guard_sfu_slope65_bits": "0x3f800000",
            "round_magic_bits": "0x4b400000",
            "w3_bit_exact_element_count": 12_845_056,
            "w3_negative_element_count": 3_246_544,
            "w3_minus_one_element_count": 80,
        },
        "typed_parameter_consumption": {
            "requant_multiplier": {
                "parameter_id": parameters["requant_multiplier"][
                    "parameter_id"
                ],
                "value_sha256": multiplier["value_sha256"],
                "physical_binding": (
                    "eight round_saturate MAC lanes in each of eight "
                    "channel-shard configs"
                ),
            },
            "y_zero_point": {
                "parameter_id": parameters["y_zero_point"]["parameter_id"],
                "scalar": 0,
                "specialization_required": True,
            },
        },
        "physical_schedule": {
            "layout_profile": "w4_28slice_hwc8_node0001_v1",
            "logical_shape": [16, 64, 112, 112],
            "occurrence_shape": [1, 12544, 8],
            "wave_count": 3,
            "channel_shard_count": 8,
            "occurrence_count": 24,
            "physical_stage_count": 48,
            "per_slice_persistent_slot_count": 6,
            "guard_intermediate_slot_count": 1,
            "target_rows_per_bank": 6144,
            "address_binding": (
                "hash-bound W4 per-slice lifetime allocator in isolated E2"
            ),
        },
        "dataflow": {
            "guard": {
                "input_dtype": "int32",
                "output_dtype": "fp32",
                "inport_conversion": "int32tofp32",
                "active_pe_count": 8,
                "opcode": "sfu_activation",
                "outbuffer": "normal_non_transout",
            },
            "round_saturate": {
                "input_dtype": "fp32",
                "output_dtype": "uint8",
                "inport_conversion": "all_disabled",
                "active_mac_count": 8,
                "active_int32_sub_count": 8,
                "outport_conversion": "int32touint8",
                "outbuffer": "normal_non_transout",
            },
            "producer_consumer_same_slice_same_address": True,
            "consumer_intermediate_sca_preload_count": 0,
        },
        "config_set": {
            "source_root": config_root.relative_to(root).as_posix(),
            "manifest": {
                "path": config_manifest_path.relative_to(root).as_posix(),
                "sha256": sha256_file(config_manifest_path),
            },
            "file_count": len(config_bindings),
            "files": config_bindings,
        },
        "local_e2": {
            "path": e2_path.relative_to(root).as_posix(),
            "sha256": sha256_file(e2_path),
            "semantic_contract": {
                "path": contract_path.relative_to(root).as_posix(),
                "sha256": sha256_file(contract_path),
            },
            "two_isolated_toolchains": True,
            "decoded_bitstream_stage_count": 48,
        },
        "emission": {
            "kind": "address_unbound_multi_config_candidate",
            "formal_target_config": False,
            "candidate_release": False,
            "server_package": False,
            "remaining_blockers": ["B_REQUANT_SERVER_E4_E5"],
        },
    }
    schedule["schedule_sha256"] = sha256_bytes(canonical_json_bytes(schedule))
    return schedule, None, None


def lower_stage_request(
    project_root: Path,
    bundle: Mapping[str, Any],
    request_id: str,
) -> tuple[dict[str, Any], dict[str, Any] | None, Path | None]:
    root = project_root.resolve()
    request = _request(bundle, request_id)
    resolution = _resolution(bundle, request_id)
    hw_op_type = str(request.get("identity", {}).get("hw_op_type"))
    if hw_op_type == "MaxPoolUint8":
        return _maxpool_schedule(root, request, resolution)
    if hw_op_type == "GlobalAverageSumInt32":
        return _gap_sum_schedule(root, request, resolution)
    if hw_op_type == "DequantizeLinear":
        return _dequant_schedule(root, request, resolution)
    if hw_op_type == "RequantizeUint8":
        return _requant_schedule(root, request, resolution)
    if hw_op_type == "View":
        if resolution.get("candidate_zero_copy_binding_allowed") is not True:
            raise StageConfigBlocked(
                request_id,
                list(resolution.get("unresolved_blockers") or ["B_VIEW_LAYOUT"]),
            )
        schedule = {
            "schema": SCHEDULE_SCHEMA,
            "request_id": request_id,
            "request_sha256": request["request_sha256"],
            "hw_op_type": "View",
            "stage_role": request["identity"]["stage"],
            "logical_geometry": deepcopy(request["logical_geometry"]),
            "physical_schedule": {
                "kind": "zero_copy_alias",
                "address_binding": "input allocation aliases output allocation",
            },
            "dataflow": {"compute_array": None, "operator": "identity view"},
            "template": None,
            "emission": {
                "kind": "zero_copy_binding",
                "formal_target_config": False,
                "semantic_patches": [],
                "remaining_blockers": list(
                    resolution.get("formal_release_blockers")
                    or ["B_SERVER_E4_E5_ADJACENT_LAYOUT"]
                ),
            },
        }
        schedule["schedule_sha256"] = sha256_bytes(canonical_json_bytes(schedule))
        return schedule, None, None
    catalog = _CATALOG.get(hw_op_type)
    blockers = (
        list(catalog["remaining_blockers"])
        if catalog is not None
        else ["B_UNSUPPORTED_HW_OP_TYPE"]
    )
    raise StageConfigBlocked(request_id, blockers)


def materialize_stage_candidate(
    project_root: Path,
    *,
    lowering_bundle_path: Path,
    request_id: str,
    output_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    bundle_path = lowering_bundle_path.resolve()
    bundle = _load_object(bundle_path)
    validate_r5_lowering_bundle(bundle, root)
    destination = output_root.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise StageConfigBackendError(
            f"refusing to overwrite non-empty stage candidate directory: {destination}"
        )
    destination.mkdir(parents=True, exist_ok=True)

    schedule, config, source_path = lower_stage_request(root, bundle, request_id)
    schedule_path = destination / "schedule_ir.json"
    schedule_path.write_text(
        json.dumps(schedule, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    config_record: dict[str, Any] | None = None
    config_set_record: dict[str, Any] | None = None
    if config is not None and source_path is not None:
        config_path = destination / "config.json"
        shutil.copyfile(source_path, config_path)
        reloaded = _load_object(config_path)
        report = OperatorConfigValidator().validate(
            reloaded, source=str(config_path), development_mode=True
        )
        if not report.valid or reloaded != config:
            raise StageConfigBackendError("materialized candidate config validation differs")
        config_record = {
            "path": "config.json",
            "sha256": sha256_file(config_path),
            "source_path": source_path.relative_to(root).as_posix(),
            "source_sha256": sha256_file(source_path),
            "semantic_identity": reloaded == config,
            "strict_validation": "passed",
        }
    config_set = schedule.get("config_set")
    if isinstance(config_set, Mapping):
        source_root_value = config_set.get("source_root")
        source_files = config_set.get("files")
        if (
            not isinstance(source_root_value, str)
            or not isinstance(source_files, list)
            or not source_files
        ):
            raise StageConfigBackendError(
                "multi-config schedule lacks a closed source file set"
            )
        source_root = (root / source_root_value).resolve()
        try:
            source_root.relative_to(root)
        except ValueError as error:
            raise StageConfigBackendError(
                "multi-config source root escapes project root"
            ) from error
        config_set_root = destination / "config_set"
        config_set_root.mkdir()
        copied: list[dict[str, Any]] = []
        for item in source_files:
            if (
                not isinstance(item, Mapping)
                or not isinstance(item.get("path"), str)
            ):
                raise StageConfigBackendError(
                    "multi-config source binding is malformed"
                )
            relative = Path(str(item["path"]))
            if relative.is_absolute() or ".." in relative.parts:
                raise StageConfigBackendError(
                    f"multi-config relative path is unsafe: {relative}"
                )
            source = source_root / relative
            target = config_set_root / relative
            if (
                not source.is_file()
                or item.get("sha256") != sha256_file(source)
                or item.get("size_bytes") != source.stat().st_size
            ):
                raise StageConfigBackendError(
                    f"multi-config source identity differs: {relative}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if target.suffix.lower() == ".json":
                payload = _load_object(target)
                validation = OperatorConfigValidator().validate(
                    payload, source=str(target), development_mode=True
                )
                if not validation.valid:
                    raise StageConfigBackendError(
                        "materialized multi-config JSON validation differs: "
                        f"{relative}: {validation.to_dict()['first_error']}"
                    )
            copied.append(
                {
                    "path": (Path("config_set") / relative).as_posix(),
                    "sha256": sha256_file(target),
                    "size_bytes": target.stat().st_size,
                    "source_path": (
                        Path(source_root_value) / relative
                    ).as_posix(),
                }
            )
        config_set_record = {
            "source_root": source_root_value,
            "file_count": len(copied),
            "files": copied,
            "semantic_identity": True,
            "strict_json_validation": "passed",
        }
    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "status": "candidate_address_unbound_not_formal",
        "request_id": request_id,
        "lowering_bundle": {
            "path": bundle_path.relative_to(root).as_posix(),
            "sha256": sha256_file(bundle_path),
            "request_set_sha256": bundle["request_set_sha256"],
        },
        "schedule_ir": {
            "path": "schedule_ir.json",
            "sha256": sha256_file(schedule_path),
            "semantic_sha256": schedule["schedule_sha256"],
        },
        "operator_config": config_record,
        "operator_config_set": config_set_record,
        "claims": {
            "formal_target_config": False,
            "hardware_execution": False,
            "hardware_numeric_match": False,
            "server_e4_e5_required": True,
        },
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def write_stage_backend_catalog(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "StageConfigBackendError",
    "StageConfigBlocked",
    "build_stage_backend_catalog",
    "lower_stage_request",
    "materialize_stage_candidate",
    "write_stage_backend_catalog",
]
