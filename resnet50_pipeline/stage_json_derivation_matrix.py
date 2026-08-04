from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .gap_d_index_schedule import validate_gap_d_index_schedule_contract
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .r5_lowering_bundle import validate_r5_lowering_bundle


SCHEMA = "resnet50-stage-json-derivation-matrix-v1"
CONTRACT_PATH = (
    "contracts/operator_config/stage_json_derivation_matrix_v1.json"
)


class StageJsonDerivationMatrixError(ValueError):
    pass


_OWNERS = {
    "CONFIG": "config_state_sequence",
    "dram_loop_configs": "logical_schedule",
    "processing_element": "logical_schedule",
    "lc_pe_configs": "logical_schedule",
    "stream_engine": "physical_schedule_and_boundary",
    "scratchpad": "buffer_lifetime",
    "buffer_config": "buffer_lifetime",
    "buffer_loop_configs": "buffer_lifetime",
    "special_array": "numeric_kernel_and_physical_layout",
    "general_array": "numeric_kernel",
    "n2n": "communication_schedule",
}


_REPRESENTATIVES: dict[str, dict[str, Any]] = {
    "r5:hwop-0002-00": {
        "kind": "strict_structural_emitter_projection",
        "config_path": (
            "configs/native_ndp_sim/"
            "maxpool_config_16_112_112_stride2_padding1_strict_v1/"
            "config.json"
        ),
        "source_path": (
            "ndp-sim/jsons/"
            "maxpool_config_16_112_112_stride2_padding1.json"
        ),
        "materialization_manifest": (
            "configs/native_ndp_sim/"
            "maxpool_config_16_112_112_stride2_padding1_strict_v1/"
            "manifest.json"
        ),
        "expected_hw_op_type": "MaxPoolUint8",
        "expected_geometry": {
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
        },
    },
    "r5:hwop-0071-00": {
        "kind": "strict_structural_emitter_projection",
        "config_path": (
            "configs/stage_codegen/"
            "hwop-0071-00-d-index-v1/config.json"
        ),
        "source_path": "ndp-sim/jsons/avgpool_config_2048_7_7.json",
        "materialization_manifest": (
            "configs/stage_codegen/"
            "hwop-0071-00-d-index-v1/manifest.json"
        ),
        "derived_evidence": (
            "contracts/operator_config/gap_d_index_schedule_v1.json"
        ),
        "expected_hw_op_type": "GlobalAverageSumInt32",
        "expected_geometry": {
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
        },
    },
    "r5:hwop-0004-01": {
        "kind": "authorized_template_projection_parameterization_pending",
        "config_path": "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json",
        "source_path": "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json",
        "materialization_manifest": None,
        "expected_hw_op_type": "RequantizeUint8",
        "expected_geometry": {
            "attributes": {
                "auto_pad": "NOTSET",
                "dilations": [1, 1],
                "group": 1,
                "kernel_shape": [1, 1],
                "pads": [0, 0, 0, 0],
                "strides": [1, 1],
            },
            "input_dtypes": [
                "int32",
                "float32",
                "float32",
                "float32",
                "uint8",
            ],
            "input_shapes": [
                [16, 64, 56, 56],
                [1],
                [64],
                [1],
                [1],
            ],
            "output_dtypes": ["uint8"],
            "output_shapes": [[16, 64, 56, 56]],
        },
    },
    "r5:hwop-0073-00": {
        "kind": "zero_copy_alias_no_json",
        "config_path": None,
        "source_path": None,
        "materialization_manifest": None,
        "expected_hw_op_type": "View",
        "expected_geometry": {
            "attributes": {"axis": 1},
            "input_dtypes": ["float32"],
            "input_shapes": [[16, 2048, 1, 1]],
            "output_dtypes": ["float32"],
            "output_shapes": [[16, 2048]],
            "view": {"axis": 1, "logical_zero_copy_candidate": True},
        },
    },
    "r5:hwop-0077-00": {
        "kind": "local_e2_derived_candidate_projection",
        "config_path": (
            "configs/native_ndp_sim/"
            "resnet50_dequant_node0077_uint8_fp32_strict_v5/config.json"
        ),
        "source_path": (
            "ndp-sim/jsons/"
            "add_dequant_uint8CWH_uint8CWH_fp32CWH.json"
        ),
        "materialization_manifest": (
            "artifacts/operator_config_validation/"
            "r5-dequant-node0077-e2-v5/manifest.json"
        ),
        "materialization_kind": "local_e2_derived_candidate",
        "derived_evidence": (
            "contracts/operator_config/"
            "node0077_dequant_semantics_evidence_v5.json"
        ),
        "expected_hw_op_type": "DequantizeLinear",
        "expected_geometry": {
            "attributes": {},
            "input_dtypes": ["uint8", "float32", "uint8"],
            "input_shapes": [[16, 1000], [1], [1]],
            "output_dtypes": ["float32"],
            "output_shapes": [[16, 1000]],
        },
    },
}


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StageJsonDerivationMatrixError(
            f"cannot parse JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise StageJsonDerivationMatrixError(
            f"JSON root must be an object: {path}"
        )
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise StageJsonDerivationMatrixError(
            f"required derivation input is missing: {relative}"
        )
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def flatten_json_leaves(
    value: Any, path: str = "$"
) -> list[tuple[str, Any]]:
    if isinstance(value, Mapping):
        result: list[tuple[str, Any]] = []
        for key, child in value.items():
            result.extend(flatten_json_leaves(child, f"{path}.{key}"))
        return result
    if isinstance(value, list):
        result = []
        for index, child in enumerate(value):
            result.extend(flatten_json_leaves(child, f"{path}[{index}]"))
        return result
    return [(path, copy.deepcopy(value))]


def validate_representative_signature(
    request_id: str, geometry: Mapping[str, Any]
) -> None:
    spec = _REPRESENTATIVES.get(request_id)
    if spec is None:
        raise StageJsonDerivationMatrixError(
            f"unsupported representative request: {request_id}"
        )
    if dict(geometry) != spec["expected_geometry"]:
        raise StageJsonDerivationMatrixError(
            f"representative logical geometry differs: {request_id}"
        )


def _top_module(path: str) -> str:
    if not path.startswith("$."):
        raise StageJsonDerivationMatrixError(
            f"JSON leaf path is not absolute: {path}"
        )
    module = path[2:].split(".", 1)[0].split("[", 1)[0]
    if module not in _OWNERS:
        raise StageJsonDerivationMatrixError(
            f"JSON leaf has no semantic owner: {path}"
        )
    return module


def _source_rule(
    request_id: str,
    path: str,
    module: str,
    value: Any,
) -> dict[str, Any]:
    if path.endswith(".base_addr"):
        return {
            "source_kind": "late_bound_address",
            "equation_rule_id": "DERIVE-ADDR-LATE-BOUND-001",
            "equation": (
                "allocation_base + wave_or_tile_byte_offset; reference value "
                "is never copied into a target instance"
            ),
            "emission_value_policy": "replace_reference_with_late_bound_value",
            "typed_parameter_refs": [],
            "evidence_level": "RTL_PROVEN",
        }
    if module == "CONFIG":
        return {
            "source_kind": "derived_schedule",
            "equation_rule_id": "DERIVE-CONFIG-STATE-001",
            "equation": (
                "ordered stage state transition selects update/reuse/disable"
            ),
            "emission_value_policy": "derive_from_ordered_stage_plan",
            "typed_parameter_refs": [],
            "evidence_level": "RTL_PROVEN",
        }
    if module in {
        "dram_loop_configs",
        "processing_element",
        "lc_pe_configs",
    }:
        return {
            "source_kind": "typed_geometry_equation",
            "equation_rule_id": "DERIVE-LOOP-PE-SCHEDULE-001",
            "equation": (
                "loop bounds, strides and terminal propagation derive from "
                "logical geometry and the physical tile schedule"
            ),
            "emission_value_policy": "derive_for_exact_signature",
            "typed_parameter_refs": [],
            "evidence_level": "RTL_PROVEN",
        }
    if module == "stream_engine":
        typed_refs = (
            ["x_zero_point"]
            if request_id == "r5:hwop-0071-00"
            and path.endswith(".padding_reg_value")
            else []
        )
        return {
            "source_kind": (
                "typed_parameter_equation"
                if typed_refs
                else "typed_geometry_equation"
            ),
            "equation_rule_id": "DERIVE-STREAM-BOUNDARY-001",
            "equation": (
                "target/dtype/index sizes/strides/padding/tailing derive from "
                "typed geometry, layout and boundary policy"
            ),
            "emission_value_policy": "derive_for_exact_signature",
            "typed_parameter_refs": typed_refs,
            "evidence_level": "RTL_PROVEN",
        }
    if module in {
        "scratchpad",
        "buffer_config",
        "buffer_loop_configs",
    }:
        return {
            "source_kind": "derived_schedule",
            "equation_rule_id": "DERIVE-BUFFER-LIFETIME-001",
            "equation": (
                "buffer enable/source/full/last/ping-pong derive from producer "
                "placement and lifetime"
            ),
            "emission_value_policy": "derive_from_lifetime_plan",
            "typed_parameter_refs": [],
            "evidence_level": "RTL_PROVEN",
        }
    if module == "special_array":
        return {
            "source_kind": "numeric_kernel_schedule",
            "equation_rule_id": "DERIVE-SA-KERNEL-001",
            "equation": (
                "SA topology, dtype, psum/bias and terminal fields derive from "
                "the typed dot-product kernel and physical layout"
            ),
            "emission_value_policy": "derive_from_hardware_validated_recipe",
            "typed_parameter_refs": [],
            "evidence_level": "RTL_PROVEN",
        }
    if module == "general_array":
        typed_refs: list[str] = []
        equation_rule_id = "DERIVE-GA-KERNEL-001"
        equation = (
            "opcode, routes, modes and terminal thresholds derive "
            "from the hardware-validated GA recipe"
        )
        emission_value_policy = "derive_from_hardware_validated_recipe"
        if request_id == "r5:hwop-0004-01" and ".constant" in path:
            typed_refs = [
                "x_scale",
                "w_scale",
                "y_scale",
                "y_zero_point",
                "requant_multiplier",
            ]
            equation_rule_id = "DERIVE-REQUANT-CONSTANTS-001"
            equation = (
                "lane constants derive from typed qparams and the bit-accurate "
                "requant equation"
            )
            emission_value_policy = "parameterize_before_emission"
        elif request_id == "r5:hwop-0077-00" and ".constant" in path:
            if any(f".{pe}." in path for pe in ("PE00", "PE02", "PE20", "PE22")):
                typed_refs = ["x_zero_point"]
            elif any(
                f".{pe}." in path
                for pe in ("PE10", "PE12", "PE30", "PE32")
            ):
                typed_refs = ["x_scale"]
            equation_rule_id = "DERIVE-DEQUANT-TWO-STAGE-001"
            equation = (
                "first-stage constants derive from float32(-x_zero_point); "
                "second-stage constants preserve float32 x_scale, with "
                "subtract then multiply rounding order"
            )
            emission_value_policy = "derive_from_typed_dequant_parameters"
        return {
            "source_kind": (
                "typed_parameter_equation"
                if typed_refs
                else "numeric_kernel_schedule"
            ),
            "equation_rule_id": equation_rule_id,
            "equation": equation,
            "emission_value_policy": emission_value_policy,
            "typed_parameter_refs": typed_refs,
            "evidence_level": (
                "CONTRADICTED"
                if request_id
                in {"r5:hwop-0002-00", "r5:hwop-0004-01"}
                else "RTL_PROVEN"
            ),
        }
    if module == "n2n":
        return {
            "source_kind": "communication_schedule",
            "equation_rule_id": "DERIVE-N2N-SCHEDULE-001",
            "equation": (
                "enable/selectors/mem_loop derive only from an explicit "
                "cross-slice material-transfer schedule"
            ),
            "emission_value_policy": "derive_from_explicit_copy_schedule",
            "typed_parameter_refs": [],
            "evidence_level": "RTL_PROVEN",
        }
    raise StageJsonDerivationMatrixError(f"unhandled JSON module: {module}")


def _legal_domain(value: Any) -> dict[str, Any]:
    if value is None:
        kind = "null"
    elif isinstance(value, bool):
        kind = "boolean"
    elif isinstance(value, int):
        kind = "integer"
    elif isinstance(value, float):
        kind = "number"
    elif isinstance(value, str):
        kind = "string_or_enum"
    else:
        raise StageJsonDerivationMatrixError(
            f"unsupported JSON leaf value: {value!r}"
        )
    return {
        "kind": kind,
        "current_reference_value_valid": True,
        "constraint_source": (
            "strict validator plus encoder/register/RTL audit; exact enum/range "
            "remains owned by the referenced rule"
        ),
    }


def _rtl_consumers(module: str) -> list[str]:
    return {
        "CONFIG": ["config register update/reuse/clear sequence"],
        "dram_loop_configs": ["IGA_LC_Config", "IGA_LC_Counter"],
        "processing_element": ["IGA_PE_Config", "IGA_PE_ALU"],
        "lc_pe_configs": ["IGA_PE_Config", "IGA_PE_ALU"],
        "stream_engine": [
            "Stream_Engine_Config",
            "Memory/Buffer Address Generators",
        ],
        "scratchpad": [
            "Buffer_Manager_Cluster_Config",
            "Buffer_Manager",
        ],
        "buffer_config": [
            "Buffer_Manager_Cluster_Config",
            "Buffer_Manager",
        ],
        "buffer_loop_configs": [
            "Buffer_Manager_Cluster_Config",
            "Buffer_Manager",
        ],
        "special_array": ["Specialized_Array_Config", "SA_PE"],
        "general_array": ["GA_Inport_Config", "GA_PE_Config", "GA_PE_ALU"],
        "n2n": ["Stream_Engine_Config", "NSE_Controller"],
    }[module]


def _row_blockers(
    request_id: str, module: str, stage_blockers: list[str]
) -> list[str]:
    if request_id == "r5:hwop-0002-00" and module == "general_array":
        return [
            blocker
            for blocker in stage_blockers
            if blocker.startswith("B_GA_INT8_MAX_")
        ]
    if request_id == "r5:hwop-0071-00":
        if module in {
            "dram_loop_configs",
            "processing_element",
            "lc_pe_configs",
            "stream_engine",
        }:
            return [
                blocker
                for blocker in stage_blockers
                if blocker == "B_GAP_D_INDEX_CARRIER_SEMANTICS"
            ]
        if module == "general_array":
            return [
                blocker
                for blocker in stage_blockers
                if blocker == "B_GAP_GA_ACCUM_STATE"
            ]
    if request_id == "r5:hwop-0004-01" and module == "general_array":
        return [
            blocker
            for blocker in stage_blockers
            if blocker == "B_GA_INT32TOFP32_INPUT_DOMAIN"
        ]
    return []


def _authority_record(
    authority: Mapping[str, Any], source_path: str
) -> dict[str, Any]:
    matches = [
        item
        for item in authority.get("records", [])
        if isinstance(item, Mapping) and item.get("path") == source_path
    ]
    if len(matches) != 1:
        raise StageJsonDerivationMatrixError(
            f"configuration authority record is not unique: {source_path}"
        )
    record = dict(matches[0])
    if (
        record.get("configuration_correctness")
        != "user_authorized_correct_reference"
        or "rule_extraction" not in record.get("allowed_uses", [])
    ):
        raise StageJsonDerivationMatrixError(
            f"configuration source is not an authorized rule reference: "
            f"{source_path}"
        )
    return record


def build_stage_json_derivation_matrix(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    lowering_rel = "contracts/resnet50_r5_lowering_bundle.json"
    audit_rel = (
        "contracts/operator_config/stage_operator_semantics_audit_v1.json"
    )
    system_rel = "contracts/operator_config/stage_config_system_v1.json"
    authority_rel = (
        "contracts/operator_config/operator_config_authority_v1.json"
    )
    lowering_path = root / lowering_rel
    lowering = _load(lowering_path)
    validate_r5_lowering_bundle(lowering, root)
    audit = _load(root / audit_rel)
    system = _load(root / system_rel)
    authority = _load(root / authority_rel)
    gap_d_rel = "contracts/operator_config/gap_d_index_schedule_v1.json"
    gap_d = _load(root / gap_d_rel)
    validate_gap_d_index_schedule_contract(gap_d, root)

    requests = {
        str(item["request_id"]): item
        for item in lowering.get("requests", [])
        if isinstance(item, Mapping)
    }
    resolutions = {
        str(item["request_id"]): item
        for item in lowering.get("effective_resolutions", [])
        if isinstance(item, Mapping)
    }
    finding_classes = {
        str(item.get("issue_id")): str(item.get("classification"))
        for item in audit.get("findings", [])
        if isinstance(item, Mapping)
    }
    if finding_classes.get("CDA-GAP-GA-ACCUM-STATE-001") != "CONTRADICTED":
        raise StageJsonDerivationMatrixError(
            "GAP accumulator finding is not current"
        )
    if system.get("summary", {}).get("stage_count") != 133:
        raise StageJsonDerivationMatrixError(
            "stage configuration system is not the 133-stage system"
        )

    stage_records: list[dict[str, Any]] = []
    source_kind_counts: Counter[str] = Counter()
    owner_counts: Counter[str] = Counter()
    json_leaf_total = 0
    for request_id, spec in _REPRESENTATIVES.items():
        request = requests.get(request_id)
        resolution = resolutions.get(request_id)
        if not isinstance(request, Mapping) or not isinstance(
            resolution, Mapping
        ):
            raise StageJsonDerivationMatrixError(
                f"representative lowering record is missing: {request_id}"
            )
        if (
            request.get("identity", {}).get("hw_op_type")
            != spec["expected_hw_op_type"]
        ):
            raise StageJsonDerivationMatrixError(
                f"representative family differs: {request_id}"
            )
        validate_representative_signature(
            request_id, request["logical_geometry"]
        )
        stage_blockers = [
            str(value) for value in resolution["effective_blockers"]
        ]
        locally_resolved_blockers: list[str] = []
        if request_id == "r5:hwop-0071-00":
            if (
                gap_d.get("status")
                != "d_index_static_and_native_mapping_closed_ga_accumulator_blocked"
                or gap_d.get("native_mapping", {}).get("total_penalty")
                not in (0, 0.0)
            ):
                raise StageJsonDerivationMatrixError(
                    "GAP D-index local resolution is not release-quality static evidence"
                )
            locally_resolved_blockers = [
                "B_GAP_D_INDEX_CARRIER_SEMANTICS"
            ]
            stage_blockers = [
                blocker
                for blocker in stage_blockers
                if blocker not in locally_resolved_blockers
            ]
        record: dict[str, Any] = {
            "request_id": request_id,
            "request_sha256": request["request_sha256"],
            "identity": copy.deepcopy(request["identity"]),
            "logical_geometry_sha256": sha256_bytes(
                canonical_json_bytes(request["logical_geometry"])
            ),
            "matrix_kind": spec["kind"],
            "readiness_axes": copy.deepcopy(resolution["readiness_axes"]),
            "stage_blockers": stage_blockers,
            "locally_resolved_blockers": locally_resolved_blockers,
            "formal_release_allowed": False,
        }
        if spec["config_path"] is None:
            record.update(
                {
                    "json_projection": None,
                    "json_leaf_count": 0,
                    "json_leaf_set_sha256": sha256_bytes(b""),
                    "full_json_leaf_coverage": True,
                    "alias_fields": [
                        {
                            "field": "input_tensor_identity",
                            "source_kind": "typed_port_identity",
                            "status": "proven",
                        },
                        {
                            "field": "output_tensor_identity",
                            "source_kind": "typed_port_identity",
                            "status": "proven",
                        },
                        {
                            "field": "axis",
                            "source_kind": "typed_attribute",
                            "value": 1,
                            "status": "proven",
                        },
                        {
                            "field": "allocation_and_byte_offset_identity",
                            "source_kind": "cross_stage_lifetime",
                            "status": "blocked",
                            "blockers": stage_blockers
                            or ["B_VIEW_ADJACENT_LAYOUT_LIFETIME"],
                        },
                    ],
                    "rows": [],
                }
            )
            stage_records.append(record)
            continue

        config_path = str(spec["config_path"])
        source_path = str(spec["source_path"])
        config = _load(root / config_path)
        authority_record = _authority_record(authority, source_path)
        leaves = flatten_json_leaves(config)
        rows: list[dict[str, Any]] = []
        leaf_hash_lines: list[str] = []
        for ordinal, (path, value) in enumerate(leaves):
            module = _top_module(path)
            rule = _source_rule(request_id, path, module, value)
            source_kind_counts[rule["source_kind"]] += 1
            owner_counts[_OWNERS[module]] += 1
            leaf_hash = sha256_bytes(canonical_json_bytes(value))
            leaf_hash_lines.append(f"{path}\0{leaf_hash}")
            rows.append(
                {
                    "row_id": f"{request_id}:leaf-{ordinal:04d}",
                    "json_path": path,
                    "reference_value": value,
                    "reference_value_sha256": leaf_hash,
                    "semantic_owner": _OWNERS[module],
                    "json_module": module,
                    **rule,
                    "legal_domain": _legal_domain(value),
                    "encoder_binding": {
                        "status": "bound_by_native_config_module",
                        "module": module,
                        "field_path": path,
                    },
                    "rtl_consumers": _rtl_consumers(module),
                    "local_blockers": _row_blockers(
                        request_id, module, stage_blockers
                    ),
                    "stage_gate_inherited": bool(stage_blockers),
                }
            )
        json_leaf_total += len(rows)
        projection: dict[str, Any] = {
            "path": config_path,
            "sha256": sha256_file(root / config_path),
            "source_authority": {
                "path": source_path,
                "sha256": authority_record["sha256"],
                "configuration_correctness": authority_record[
                    "configuration_correctness"
                ],
                "derived_candidate_requires_validation": authority_record[
                    "derived_candidate_requires_validation"
                ],
            },
            "use": (
                "complete leaf projection for derivation/reverse binding; "
                "not target emission authority"
            ),
        }
        materialization = spec["materialization_manifest"]
        if materialization is not None:
            materialization_key = (
                "derived_candidate_materialization"
                if spec.get("materialization_kind")
                == "local_e2_derived_candidate"
                else "strict_materialization"
            )
            projection[materialization_key] = _binding(
                root, str(materialization)
            )
        derived_evidence = spec.get("derived_evidence")
        if derived_evidence is not None:
            projection["derived_evidence"] = _binding(
                root, str(derived_evidence)
            )
        record.update(
            {
                "json_projection": projection,
                "json_leaf_count": len(rows),
                "json_leaf_set_sha256": sha256_bytes(
                    "\n".join(leaf_hash_lines).encode("utf-8")
                ),
                "full_json_leaf_coverage": len(rows) == len(leaves),
                "alias_fields": [],
                "rows": rows,
            }
        )
        stage_records.append(record)

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "five_representative_derivation_matrices_complete_release_blocked",
        "inputs": {
            "lowering_bundle": _binding(root, lowering_rel),
            "stage_operator_semantics_audit": _binding(root, audit_rel),
            "stage_config_system": _binding(root, system_rel),
            "configuration_authority": _binding(root, authority_rel),
            "gap_d_index_schedule": _binding(root, gap_d_rel),
        },
        "policy": {
            "every_projected_json_leaf_has_exactly_one_owner": True,
            "reference_value_is_not_target_emission_authority": True,
            "absolute_addresses_are_always_late_bound": True,
            "typed_geometry_change_must_rederive_or_fail_closed": True,
            "view_is_alias_only_and_emits_no_json": True,
            "rtl_semantic_blocker_overrides_structural_emitter": True,
            "unknown_source_kind_or_owner_fails_closed": True,
        },
        "summary": {
            "representative_stage_count": len(stage_records),
            "json_projection_count": sum(
                item["json_projection"] is not None
                for item in stage_records
            ),
            "alias_projection_count": sum(
                item["json_projection"] is None
                for item in stage_records
            ),
            "json_leaf_count": json_leaf_total,
            "fully_covered_projection_count": sum(
                item["full_json_leaf_coverage"] for item in stage_records
            ),
            "current_candidate_json_count": sum(
                bool(item["readiness_axes"]["json_emitter_ready"])
                and bool(item["readiness_axes"]["rtl_semantics_compatible"])
                for item in stage_records
            ),
            "source_kind_counts": dict(sorted(source_kind_counts.items())),
            "owner_counts": dict(sorted(owner_counts.items())),
        },
        "stages": stage_records,
        "next_expansion": {
            "request_id": "r5:hwop-0004-01",
            "gate": (
                "replace authorized quant template constants and geometry with "
                "typed qparam/shape equations, then pass bit-accurate RTL replay"
            ),
        },
    }
    payload["contract_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def validate_stage_json_derivation_matrix(
    value: Mapping[str, Any], project_root: Path
) -> None:
    expected = build_stage_json_derivation_matrix(project_root)
    if value != expected:
        raise StageJsonDerivationMatrixError(
            "stage JSON derivation matrix differs from current hash-bound inputs"
        )


def write_stage_json_derivation_matrix(
    path: Path, value: Mapping[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "CONTRACT_PATH",
    "SCHEMA",
    "StageJsonDerivationMatrixError",
    "build_stage_json_derivation_matrix",
    "flatten_json_leaves",
    "validate_representative_signature",
    "validate_stage_json_derivation_matrix",
    "write_stage_json_derivation_matrix",
]
