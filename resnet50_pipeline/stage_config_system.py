from __future__ import annotations

import json
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .deepseek_primitive_rules import validate_deepseek_primitive_rules
from .deepseek_reduction_rules import validate_deepseek_reduction_rules
from .deepseek_stage_ir import validate_deepseek_stage_ir
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_corpus import build_operator_config_authority
from .r5_lowering_bundle import validate_r5_lowering_bundle
from .stage_config_backend import build_stage_backend_catalog


SCHEMA = "resnet50-stage-to-operator-config-system-v1"


class StageConfigSystemError(ValueError):
    pass


_EXPECTED_STAGE_COUNTS = {
    "AverageRequantizeUint8": 1,
    "ConvInt32Accumulate": 53,
    "DequantizeLinear": 2,
    "GlobalAverageSumInt32": 1,
    "MatMulInt32Accumulate": 1,
    "MaxPoolUint8": 1,
    "QLinearAddUint8": 17,
    "QuantizeLinear": 2,
    "RequantizeUint8": 54,
    "View": 1,
}


_FIELD_OWNERSHIP = {
    "CONFIG": {
        "owner": "config_state_sequence",
        "rule": (
            "emit explicit update/reuse/disable transitions across ordered stages; "
            "never infer state from the presence of a module body"
        ),
    },
    "dram_loop_configs": {
        "owner": "logical_schedule",
        "rule": (
            "derive starts, ends, strides, last-index and terminal propagation from "
            "the exact loop nest and tile geometry"
        ),
    },
    "processing_element": {
        "owner": "logical_schedule",
        "rule": (
            "derive loop sources, aggregation and terminal routing from producer/"
            "consumer dependencies"
        ),
    },
    "stream_engine": {
        "owner": "physical_schedule_and_boundary",
        "rule": (
            "derive target, dtype, index modes, padding/tailing, keep/full boundaries "
            "and ping-pong policy; base_addr remains late-bound"
        ),
    },
    "scratchpad": {
        "owner": "buffer_lifetime",
        "rule": (
            "derive buffer ownership, source routing and reuse from the scheduled "
            "lifetime graph"
        ),
    },
    "special_array": {
        "owner": "numeric_kernel_and_physical_layout",
        "rule": (
            "derive SA dtype, inport/outport layout, bias/psum lifecycle and "
            "non-symmetric physical orientation from the exact kernel"
        ),
    },
    "general_array": {
        "owner": "numeric_kernel",
        "rule": (
            "derive opcode, conversions and constants only from typed parameters "
            "and a hardware-validated arithmetic recipe"
        ),
    },
    "n2n": {
        "owner": "communication_schedule",
        "rule": (
            "derive neighbor/ring/reduction topology and completion from an explicit "
            "cross-slice communication schedule"
        ),
    },
}

_IMPLEMENTATION_BRANCHES = [
    {
        "branch": "ga_affine_and_requant",
        "families": [
            "RequantizeUint8",
            "QLinearAddUint8",
            "QuantizeLinear",
            "DequantizeLinear",
            "AverageRequantizeUint8",
        ],
        "shared_work": (
            "typed affine constants, GA lane placement, elementwise traversal, "
            "rounding/saturation and full-batch wave dispatch"
        ),
        "priority": 2,
    },
    {
        "branch": "ga_reduction",
        "families": ["GlobalAverageSumInt32"],
        "shared_work": (
            "exact reduction topology, padding identity, cross-slice completion "
            "and reduction-to-requant state handoff"
        ),
        "priority": 1,
    },
    {
        "branch": "sa_int8_accumulation",
        "families": ["ConvInt32Accumulate", "MatMulInt32Accumulate"],
        "shared_work": (
            "INT8 SA port orientation, bias/psum lifecycle, full-wave schedule "
            "and tail handling"
        ),
        "priority": 3,
    },
    {
        "branch": "control_only_or_alias",
        "families": ["MaxPoolUint8", "View"],
        "shared_work": "already implemented exact MaxPool candidate and View alias",
        "priority": 0,
    },
]


def _layers(
    *,
    reference_topology: str,
    logical_schedule: str,
    physical_schedule: str,
    numeric_kernel: str,
    boundary: str,
    config_state: str,
    json_emission: str,
) -> dict[str, str]:
    return {
        "logical_geometry": "derived_from_typed_lowering_request",
        "typed_parameters": "derived_with_hash_bound_provenance",
        "reference_topology": reference_topology,
        "logical_schedule": logical_schedule,
        "physical_schedule": physical_schedule,
        "numeric_kernel": numeric_kernel,
        "boundary_keep_tail": boundary,
        "config_state_sequence": config_state,
        "address_binding": "late_bound_after_address_remapping",
        "json_emission": json_emission,
        "formal_release": "blocked_until_independent_golden_and_server_e4_e5",
    }


_FAMILY_RULES: dict[str, dict[str, Any]] = {
    "MaxPoolUint8": {
        "reference_relation": "exact_operator_and_exact_resnet_shape",
        "schedule_rule": "NCHW uint8 3x3 stride2 pad1; C16 tiles; waves [28,28,8]",
        "numeric_rule": "unsigned uint8 max with zero padding identity",
        "emission_mode": "candidate_json",
        "candidate_scope": ["r5:hwop-0002-00"],
        "candidate_blockers": [],
        "formal_release_blockers": ["B_SERVER_E4_E5"],
        "layers": _layers(
            reference_topology="closed_for_exact_node0002",
            logical_schedule="closed_for_exact_node0002",
            physical_schedule="closed_for_exact_node0002",
            numeric_kernel="closed_by_unsigned_max_and_padding_contract",
            boundary="closed_for_exact_node0002",
            config_state="closed_for_single_stage_candidate",
            json_emission="implemented_for_exact_node0002",
        ),
        "next_action": "run the complete candidate twice and preserve DDR readback",
    },
    "View": {
        "reference_relation": "no_compute_alias",
        "schedule_rule": "output allocation aliases the input allocation",
        "numeric_rule": "identity",
        "emission_mode": "zero_copy_binding",
        "candidate_scope": ["r5:hwop-0073-00"],
        "candidate_blockers": [],
        "formal_release_blockers": ["B_SERVER_E4_E5_ADJACENT_LAYOUT"],
        "layers": _layers(
            reference_topology="not_applicable",
            logical_schedule="closed_zero_copy",
            physical_schedule="closed_zero_copy",
            numeric_kernel="not_applicable",
            boundary="inherited_from_adjacent_stages",
            config_state="not_applicable",
            json_emission="not_applicable_zero_copy_binding",
        ),
        "next_action": "validate adjacent producer and consumer address identity",
    },
    "ConvInt32Accumulate": {
        "reference_relation": "project_added_failed_diagnostic_not_authorized_reference",
        "schedule_rule": (
            "derive convolution loops, K16 output-channel tiles, spatial traversal, "
            "psum accumulation and wave partition from geometry"
        ),
        "numeric_rule": (
            "signed int8 weight x centered uint8 activation + int32 bias -> int32 psum"
        ),
        "emission_mode": "blocked",
        "candidate_scope": [],
        "candidate_blockers": [
            "B_CONV_BIAS_PSUM",
            "B_CONV_INT8_SA",
            "B_CONV_FULL_3WAVE_SCHEDULE",
            "B_CONV_DERIVED_WAVES_VALIDATION",
        ],
        "formal_release_blockers": ["B_SERVER_E4_E5"],
        "layers": _layers(
            reference_topology="blocked_node0004_is_not_upstream_authorized",
            logical_schedule="blocked_full_conv_shape_rules_missing",
            physical_schedule="blocked_full_wave_and_psum_lifecycle_missing",
            numeric_kernel="blocked_int8_sa_bias_psum_recipe_not_independently_closed",
            boundary="blocked_conv_padding_stride_and_tail_generalization",
            config_state="blocked_cross_wave_state_sequence",
            json_emission="blocked",
        ),
        "next_action": (
            "derive SA/LC/stream semantics from upstream templates, RTL and register "
            "map, then independently review node0004 and reproduce all three waves"
        ),
    },
    "RequantizeUint8": {
        "reference_relation": (
            "authorized_quant_and_sfu_primitives_composed_with_exact_node0001_e2"
        ),
        "schedule_rule": (
            "exact node0001: three waves times eight channel shards; each occurrence "
            "uses a same-slice guard producer followed by a round/saturate consumer"
        ),
        "numeric_rule": (
            "guard=max(fp32_convert(acc),+0); "
            "scaled=fp32(guard*positive_multiplier[channel]); "
            "uint8=saturate(round_to_nearest_even(scaled)); output zero-point is zero"
        ),
        "emission_mode": "candidate_json",
        "candidate_scope": ["r5:hwop-0001-01"],
        "candidate_blockers": [],
        "formal_release_blockers": ["B_REQUANT_SERVER_E4_E5"],
        "layers": _layers(
            reference_topology="closed_for_exact_node0001_two_primitive_composition",
            logical_schedule="closed_for_exact_node0001_24_occurrence_48_stage_graph",
            physical_schedule="closed_for_exact_node0001_w4_slice_lifetimes",
            numeric_kernel="closed_for_exact_positive_multiplier_yzp0_guarded_path",
            boundary="closed_for_exact_node0001_hwc8_three_wave_geometry",
            config_state="closed_by_48_barriers_one_shared_sfu_load_and_no_consumer_preload",
            json_emission="candidate_json_exact_scope_non_formal",
        ),
        "next_action": (
            "the separately authorized test-repair task must run stock-RTL E4/E5 "
            "for exact node0001 before any formal target-config claim"
        ),
    },
    "QLinearAddUint8": {
        "reference_relation": "authorized_related_add_dequant_template_not_exact_output",
        "schedule_rule": "elementwise dual-input broadcast-free traversal",
        "numeric_rule": (
            "requantize both uint8 domains into the output domain, add and saturate"
        ),
        "emission_mode": "blocked",
        "candidate_scope": [],
        "candidate_blockers": ["B_ADD_DUAL_QDOMAIN", "B_ADD_REQUANT_E5"],
        "formal_release_blockers": ["B_SERVER_E4_E5"],
        "layers": _layers(
            reference_topology="related_template_only",
            logical_schedule="blocked_exact_uint8_add_schedule",
            physical_schedule="blocked_dual_input_layout_and_transport",
            numeric_kernel="blocked_dual_qdomain_uint8_output_recipe",
            boundary="blocked_shape_and_tail_rules",
            config_state="blocked",
            json_emission="blocked",
        ),
        "next_action": (
            "extract the two affine branches from add_dequant, derive uint8 output "
            "requant and reproduce one residual Add stage"
        ),
    },
    "QuantizeLinear": {
        "reference_relation": "authorized_int32_to_uint8_template_input_dtype_mismatch",
        "schedule_rule": "elementwise traversal of the exact input tensor",
        "numeric_rule": "round(x/y_scale)+y_zero_point then saturate uint8",
        "emission_mode": "blocked",
        "candidate_scope": [],
        "candidate_blockers": [
            "B_QUANT_INPUT_DTYPE_PATH",
            "B_QUANT_ROUNDING_EXECUTION",
        ],
        "formal_release_blockers": ["B_SERVER_E4_E5"],
        "layers": _layers(
            reference_topology="related_template_only",
            logical_schedule="blocked_fp32_input_shape_schedule",
            physical_schedule="blocked_fp32_input_transport",
            numeric_kernel="blocked_fp32_to_uint8_rounding_recipe",
            boundary="blocked_shape_and_tail_rules",
            config_state="blocked",
            json_emission="blocked",
        ),
        "next_action": (
            "find or derive an authorized fp32-input GA path and reverse-reproduce "
            "rounding for both QuantizeLinear stages"
        ),
    },
    "DequantizeLinear": {
        "reference_relation": (
            "authorized_embedded_branch_plus_exact_node0077_local_e2_materialization"
        ),
        "schedule_rule": (
            "exact node0077 high4 layout: 28 slices, 47 occurrences, "
            "16 uint8 inputs to 16 fp32 outputs per occurrence"
        ),
        "numeric_rule": (
            "two-stage fp32 subtract-then-multiply; affine MAC is bitwise rejected"
        ),
        "emission_mode": "candidate_json",
        "candidate_scope": ["r5:hwop-0077-00"],
        "candidate_blockers": [],
        "formal_release_blockers": ["B_DEQUANT_SERVER_E4_E5"],
        "layers": _layers(
            reference_topology="authorized_branch_invariants_hash_bound",
            logical_schedule="closed_exact_node0077_uint8_to_fp32",
            physical_schedule="closed_28x752_high4_normal_outbuffer",
            numeric_kernel="closed_two_stage_w3_bit_exact",
            boundary="closed_750_prefix_plus_two_neutral_tail",
            config_state="closed_single_stage_full_config",
            json_emission="candidate_json_exact_scope_non_formal",
        ),
        "next_action": (
            "run exact 28-slice server E3/E4/E5 readback; no server package is "
            "authorized by the current local-only task"
        ),
    },
    "GlobalAverageSumInt32": {
        "reference_relation": (
            "authorized_exact_upstream_template_but_resnet_d_index_"
            "carrier_contradicted"
        ),
        "schedule_rule": "reduce each 7x7 channel plane into int32 centered sum",
        "numeric_rule": "sum(uint8(x)-x_zero_point) across 49 spatial elements",
        "emission_mode": "blocked",
        "candidate_scope": [],
        "candidate_blockers": ["B_GAP_D_INDEX_CARRIER_SEMANTICS"],
        "formal_release_blockers": [
            "B_GAP_D_INDEX_CARRIER_SEMANTICS",
            "B_SERVER_E4_E5",
        ],
        "layers": _layers(
            reference_topology=(
                "authorized_exact_template_but_not_resnet_stage_equivalence"
            ),
            logical_schedule="closed_for_exact_16x2048x7x7_local_reduction",
            physical_schedule=(
                "blocked_d_index_carrier_reaches_1_of_256_output_blocks"
            ),
            numeric_kernel=(
                "closed_for_exact_x_zero_point_zero_eight_lane_int32_sum"
            ),
            boundary=(
                "closed_zero_padding_and_49_element_local_tail"
            ),
            config_state=(
                "single_stage_closed_reduction_to_requant_handoff_separate"
            ),
            json_emission=(
                "blocked_by_B_GAP_D_INDEX_CARRIER_SEMANTICS"
            ),
        ),
        "next_action": (
            "derive and prove an explicit 0..255 numeric D index carrier, "
            "then regenerate mapping, bitstream, execplan and package under "
            "a new identity"
        ),
    },
    "AverageRequantizeUint8": {
        "reference_relation": "authorized_avgpool_plus_quant_templates_composed",
        "schedule_rule": "consume one int32 sum per channel and emit uint8",
        "numeric_rule": (
            "requantize with x_scale/(y_scale*49), add y_zero_point and saturate"
        ),
        "emission_mode": "blocked",
        "candidate_scope": [],
        "candidate_blockers": ["B_GAP_DIVISION_REQUANT", "B_GAP_E5"],
        "formal_release_blockers": ["B_SERVER_E4_E5"],
        "layers": _layers(
            reference_topology="composition_not_yet_reproduced",
            logical_schedule="blocked_predecessor_sum_contract",
            physical_schedule="blocked_composed_instance",
            numeric_kernel="formula_derived_template_composition_unproven",
            boundary="blocked_2048_channel_tail",
            config_state="blocked_sum_to_requant_sequence",
            json_emission="blocked",
        ),
        "next_action": (
            "compose the authorized avgpool and quant arithmetic paths, then "
            "reverse-reproduce the exact 49-element divisor"
        ),
    },
    "MatMulInt32Accumulate": {
        "reference_relation": "authorized_fp16_gemm_templates_int8_dtype_and_tail_mismatch",
        "schedule_rule": "M16 x N1000 x K2048 with explicit N and K tail handling",
        "numeric_rule": "centered uint8 x signed int8 -> int32 accumulation",
        "emission_mode": "blocked",
        "candidate_scope": [],
        "candidate_blockers": ["B_MATMUL_INT8_SA_RECIPE", "B_MATMUL_TAIL_E5"],
        "formal_release_blockers": ["B_SERVER_E4_E5"],
        "layers": _layers(
            reference_topology="fp16_sa_topology_reference_only",
            logical_schedule="blocked_int8_mnk_schedule",
            physical_schedule="blocked_n1000_tail_and_psum",
            numeric_kernel="blocked_int8_sa_accumulation",
            boundary="blocked_n1000_tail",
            config_state="blocked_psum_sequence",
            json_emission="blocked",
        ),
        "next_action": (
            "derive INT8 SA semantics independently from RTL and reuse only the "
            "authorized GEMM loop/topology relationships"
        ),
    },
}


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StageConfigSystemError(f"cannot parse JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise StageConfigSystemError(f"JSON root must be an object: {path}")
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise StageConfigSystemError(f"required system input is missing: {relative}")
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _template_authority(
    root: Path,
    template: Mapping[str, Any],
    authority_by_path: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    relative = str(template["path"])
    path = root / relative
    if not path.is_file() or template.get("sha256") != sha256_file(path):
        raise StageConfigSystemError(f"catalog template identity differs: {relative}")
    source_relative = relative
    materialization: dict[str, Any] | None = None
    if relative.endswith("/config.json"):
        manifest_path = path.parent / "manifest.json"
        if manifest_path.is_file():
            manifest = _load(manifest_path)
            source = manifest.get("source")
            normalized = manifest.get("normalized")
            if (
                manifest.get("schema")
                != "operator-config-strict-materialization-v1"
                or not isinstance(source, Mapping)
                or not isinstance(normalized, Mapping)
                or normalized.get("sha256") != sha256_file(path)
                or not isinstance(source.get("path"), str)
            ):
                raise StageConfigSystemError(
                    f"strict template materialization differs: {relative}"
                )
            source_relative = str(source["path"])
            source_path = root / source_relative
            if (
                not source_path.is_file()
                or source.get("sha256") != sha256_file(source_path)
            ):
                raise StageConfigSystemError(
                    f"strict template source identity differs: {source_relative}"
                )
            materialization = {
                "kind": "bit_equivalent_strict_materialization",
                "manifest": _binding(
                    root, manifest_path.relative_to(root).as_posix()
                ),
                "source_rewrite_performed": manifest.get(
                    "source_rewrite_performed"
                ),
                "changes": deepcopy(manifest.get("changes", [])),
            }
        else:
            derivation = template.get("derivation")
            if (
                not isinstance(derivation, Mapping)
                or derivation.get("kind")
                != "contract_derived_local_e2_candidate"
            ):
                raise StageConfigSystemError(
                    f"config template lacks strict or derived provenance: {relative}"
                )
            source = derivation.get("source")
            evidence = derivation.get("evidence")
            if (
                not isinstance(source, Mapping)
                or not isinstance(source.get("path"), str)
                or source.get("exists") is not True
                or not isinstance(evidence, list)
                or not evidence
            ):
                raise StageConfigSystemError(
                    f"derived template provenance differs: {relative}"
                )
            source_relative = str(source["path"])
            source_path = root / source_relative
            if (
                not source_path.is_file()
                or source.get("sha256") != sha256_file(source_path)
                or any(
                    not isinstance(item, Mapping)
                    or item.get("exists") is not True
                    or not isinstance(item.get("path"), str)
                    or not (root / str(item["path"])).is_file()
                    or item.get("sha256")
                    != sha256_file(root / str(item["path"]))
                    for item in evidence
                )
            ):
                raise StageConfigSystemError(
                    f"derived template evidence identity differs: {relative}"
                )
            materialization = {
                "kind": "contract_derived_local_e2_candidate",
                "source_rewrite_performed": True,
                "evidence": deepcopy(evidence),
            }
    authority = authority_by_path.get(source_relative)
    if authority is None:
        raise StageConfigSystemError(
            f"template source lacks authority classification: {source_relative}"
        )
    derived_candidate = (
        materialization is not None
        and materialization.get("kind")
        == "contract_derived_local_e2_candidate"
    )
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "source_path": source_relative,
        "source_sha256": authority["sha256"],
        "source_provenance": deepcopy(authority["provenance"]),
        "accepted_as_correct_reference": (
            not derived_candidate
            and
            authority["configuration_correctness"]
            == "user_authorized_correct_reference"
        ),
        "derived_candidate_local_e2_bound": derived_candidate,
        "evidence_class": authority["evidence_class"],
        "materialization": materialization,
    }


def _parameter_record(value: Mapping[str, Any]) -> dict[str, Any]:
    parameter_value = value.get("value")
    if not isinstance(parameter_value, Mapping):
        raise StageConfigSystemError("typed parameter lacks value contract")
    result = {
        "parameter_id": value.get("parameter_id"),
        "name": value.get("name"),
        "parameter_kind": value.get("parameter_kind"),
        "formula": value.get("formula"),
        "resolution": value.get("resolution"),
        "value_kind": parameter_value.get("value_kind"),
        "dtype": parameter_value.get("dtype"),
        "shape": deepcopy(parameter_value.get("shape")),
        "element_count": parameter_value.get("element_count"),
        "value_sha256": parameter_value.get("value_sha256"),
        "provenance": deepcopy(value.get("provenance")),
    }
    if "scalar" in parameter_value:
        result["scalar"] = parameter_value["scalar"]
    if "float32_bits" in parameter_value:
        result["float32_bits"] = parameter_value["float32_bits"]
    return result


def build_stage_config_system(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    lowering_rel = "contracts/resnet50_r5_lowering_bundle.json"
    catalog_rel = "contracts/operator_config/stage_backend_catalog_v1.json"
    authority_rel = "contracts/operator_config/operator_config_authority_v1.json"
    deepseek_stage_ir_rel = (
        "contracts/operator_config/deepseek_stage_ir_crosswalk_v1.json"
    )
    deepseek_reduction_rel = (
        "contracts/operator_config/deepseek_reduction_rules_v1.json"
    )
    deepseek_primitive_rel = (
        "contracts/operator_config/deepseek_primitive_rules_v1.json"
    )
    lowering = _load(root / lowering_rel)
    validate_r5_lowering_bundle(lowering, root)
    catalog = _load(root / catalog_rel)
    rebuilt_catalog = build_stage_backend_catalog(root)
    if catalog != rebuilt_catalog:
        raise StageConfigSystemError("checked stage backend catalog is stale")
    authority = _load(root / authority_rel)
    if authority != build_operator_config_authority(root):
        raise StageConfigSystemError("checked configuration authority is stale")
    authority_by_path = {
        str(item["path"]): item
        for item in authority.get("records", [])
        if isinstance(item, Mapping)
    }
    deepseek_stage_ir = _load(root / deepseek_stage_ir_rel)
    validate_deepseek_stage_ir(deepseek_stage_ir, root)
    deepseek_reduction = _load(root / deepseek_reduction_rel)
    validate_deepseek_reduction_rules(deepseek_reduction, root)
    deepseek_primitive = _load(root / deepseek_primitive_rel)
    validate_deepseek_primitive_rules(deepseek_primitive, root)
    families = catalog.get("families")
    if not isinstance(families, Mapping) or set(families) != set(_FAMILY_RULES):
        raise StageConfigSystemError("backend family set differs from system rules")
    requests = lowering.get("requests")
    resolutions = lowering.get("effective_resolutions")
    if not isinstance(requests, list) or not isinstance(resolutions, list):
        raise StageConfigSystemError("lowering bundle lacks requests/resolutions")
    resolution_by_id = {
        str(item["request_id"]): item
        for item in resolutions
        if isinstance(item, Mapping)
    }
    counts = Counter(
        str(item.get("identity", {}).get("hw_op_type"))
        for item in requests
        if isinstance(item, Mapping)
    )
    if dict(sorted(counts.items())) != _EXPECTED_STAGE_COUNTS:
        raise StageConfigSystemError(
            f"stage family counts differ: {dict(sorted(counts.items()))}"
        )

    family_records: dict[str, Any] = {}
    template_authority_cache: dict[str, dict[str, Any]] = {}
    for family_name, family in sorted(families.items()):
        templates = []
        for template in family.get("templates", []):
            if not isinstance(template, Mapping):
                raise StageConfigSystemError("malformed catalog template record")
            relative = str(template["path"])
            record = template_authority_cache.get(relative)
            if record is None:
                record = _template_authority(root, template, authority_by_path)
                template_authority_cache[relative] = record
            templates.append(deepcopy(record))
        rules = deepcopy(_FAMILY_RULES[family_name])
        family_records[family_name] = {
            "request_count": counts[family_name],
            "backend_status": family.get("status"),
            "reference_relation": rules["reference_relation"],
            "reference_templates": templates,
            "all_reference_templates_authorized": bool(templates)
            and all(
                item["accepted_as_correct_reference"] for item in templates
            ),
            "schedule_rule": rules["schedule_rule"],
            "numeric_rule": rules["numeric_rule"],
            "rule_layers": rules["layers"],
            "emission": {
                "mode": rules["emission_mode"],
                "candidate_scope": rules["candidate_scope"],
                "candidate_blockers": rules["candidate_blockers"],
                "formal_release_blockers": rules[
                    "formal_release_blockers"
                ],
            },
            "evidence": deepcopy(family.get("evidence", [])),
            "next_action": rules["next_action"],
        }

    stage_plans: list[dict[str, Any]] = []
    readiness_counts: Counter[str] = Counter()
    family_blockers: dict[str, Counter[str]] = defaultdict(Counter)
    family_shape_variants: dict[
        str, dict[str, dict[str, Any]]
    ] = defaultdict(dict)
    for request in requests:
        if not isinstance(request, Mapping):
            raise StageConfigSystemError("malformed lowering request")
        request_id = str(request["request_id"])
        identity = request.get("identity")
        if not isinstance(identity, Mapping):
            raise StageConfigSystemError(f"request identity is missing: {request_id}")
        family_name = str(identity.get("hw_op_type"))
        rules = _FAMILY_RULES[family_name]
        resolution = resolution_by_id.get(request_id)
        if not isinstance(resolution, Mapping):
            raise StageConfigSystemError(
                f"effective resolution is missing: {request_id}"
            )
        bundle_blockers = [
            str(item) for item in resolution.get("effective_blockers", [])
        ]
        candidate_blockers = sorted(
            set(bundle_blockers) | set(rules["candidate_blockers"])
        )
        if (
            rules["emission_mode"] == "candidate_json"
            and request_id in rules["candidate_scope"]
            and resolution.get("candidate_config_emission_allowed") is True
        ):
            readiness = "candidate_json_ready_non_formal"
            candidate_blockers = []
        elif (
            rules["emission_mode"] == "zero_copy_binding"
            and request_id in rules["candidate_scope"]
            and resolution.get("candidate_zero_copy_binding_allowed") is True
        ):
            readiness = "zero_copy_binding_ready_non_formal"
            candidate_blockers = []
        else:
            readiness = "blocked"
        readiness_axes = resolution.get("readiness_axes")
        if not isinstance(readiness_axes, Mapping) or set(readiness_axes) != {
            "json_emitter_ready",
            "rtl_semantics_compatible",
            "dynamic_release_ready",
        }:
            raise StageConfigSystemError(
                f"readiness axes are missing: {request_id}"
            )
        readiness_counts[readiness] += 1
        family_blockers[family_name].update(candidate_blockers)
        typed_parameters = request.get("typed_parameters", [])
        if not isinstance(typed_parameters, list):
            raise StageConfigSystemError(
                f"typed parameters are malformed: {request_id}"
            )
        shape_signature = sha256_bytes(
            canonical_json_bytes(request["logical_geometry"])
        )
        parameter_schema = [
            {
                "name": item.get("name"),
                "parameter_kind": item.get("parameter_kind"),
                "formula": item.get("formula"),
                "dtype": item.get("value", {}).get("dtype"),
                "shape": deepcopy(item.get("value", {}).get("shape")),
                "value_kind": item.get("value", {}).get("value_kind"),
            }
            for item in typed_parameters
            if isinstance(item, Mapping)
        ]
        parameter_schema_sha256 = sha256_bytes(
            canonical_json_bytes(parameter_schema)
        )
        variant = family_shape_variants[family_name].get(shape_signature)
        if variant is None:
            variant = {
                "shape_signature_sha256": shape_signature,
                "logical_geometry": deepcopy(request["logical_geometry"]),
                "request_ids": [],
                "typed_parameter_schema_sha256": set(),
            }
            family_shape_variants[family_name][shape_signature] = variant
        variant["request_ids"].append(request_id)
        variant["typed_parameter_schema_sha256"].add(
            parameter_schema_sha256
        )
        stage_plans.append(
            {
                "request_id": request_id,
                "request_sha256": request["request_sha256"],
                "ordinal": request["ordinal"],
                "identity": deepcopy(identity),
                "predecessor_hw_op_ids": deepcopy(
                    request.get("predecessor_hw_op_ids", [])
                ),
                "logical_geometry": deepcopy(request["logical_geometry"]),
                "shape_signature_sha256": shape_signature,
                "typed_parameter_schema_sha256": parameter_schema_sha256,
                "typed_parameters": [
                    _parameter_record(item)
                    for item in typed_parameters
                    if isinstance(item, Mapping)
                ],
                "family_rule": family_name,
                "readiness": readiness,
                "readiness_axes": deepcopy(dict(readiness_axes)),
                "candidate_blockers": candidate_blockers,
                "formal_release_allowed": False,
                "formal_release_blockers": sorted(
                    set(candidate_blockers)
                    | set(rules["formal_release_blockers"])
                ),
            }
        )

    for family_name, counter in family_blockers.items():
        family_records[family_name]["observed_stage_blockers"] = [
            {"blocker": blocker, "stage_count": count}
            for blocker, count in sorted(counter.items())
        ]
    for family_name, variants in family_shape_variants.items():
        records = []
        for signature, variant in sorted(variants.items()):
            parameter_schemas = sorted(
                variant.pop("typed_parameter_schema_sha256")
            )
            records.append(
                {
                    **variant,
                    "request_count": len(variant["request_ids"]),
                    "typed_parameter_schema_sha256": parameter_schemas,
                }
            )
        family_records[family_name]["shape_variant_count"] = len(records)
        family_records[family_name]["shape_variants"] = records
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "complete_stage_coverage_partial_emitter_implementation",
        "inputs": {
            "lowering_bundle": _binding(root, lowering_rel),
            "backend_catalog": _binding(root, catalog_rel),
            "configuration_authority": _binding(root, authority_rel),
            "deepseek_stage_ir": _binding(root, deepseek_stage_ir_rel),
            "deepseek_reduction_rules": _binding(
                root, deepseek_reduction_rel
            ),
            "deepseek_primitive_rules": _binding(
                root, deepseek_primitive_rel
            ),
        },
        "pipeline": [
            "typed_lowering_request",
            "operator_family_rule_selection",
            "logical_schedule_derivation",
            "physical_slice_wave_and_buffer_schedule",
            "numeric_kernel_and_typed_constant_binding",
            "cross_stage_config_state_sequence",
            "strict_address_unbound_json_emission",
            "address_binding_mapping_bitstream_execplan_sca_validation",
            "independent_golden_and_server_e4_e5_release",
        ],
        "field_ownership": deepcopy(_FIELD_OWNERSHIP),
        "implementation_branches": deepcopy(_IMPLEMENTATION_BRANCHES),
        "policy": {
            "every_stage_has_exactly_one_plan": True,
            "every_json_field_has_one_semantic_owner": True,
            "only_git_authorized_templates_may_close_reference_correctness": True,
            "project_added_node0004_is_diagnostic_only": True,
            "deepseek_rules_must_reverse_bind_authorized_templates": True,
            "deepseek_primitive_transfer_is_structural_only": True,
            "native_ndpsim_owns_supported_graph_to_execplan_flow": True,
            "project_must_not_duplicate_native_operator_generator": True,
            "addresses_are_late_bound": True,
            "unknown_or_unclosed_rules_fail_closed": True,
            "candidate_and_formal_release_are_separate": True,
            "json_emitter_rtl_compatibility_and_dynamic_release_are_separate": True,
            "candidate_json_requires_emitter_and_rtl_compatibility": True,
        },
        "summary": {
            "stage_count": len(stage_plans),
            "family_count": len(family_records),
            "family_stage_counts": dict(sorted(counts.items())),
            "candidate_json_ready_count": readiness_counts[
                "candidate_json_ready_non_formal"
            ],
            "zero_copy_binding_ready_count": readiness_counts[
                "zero_copy_binding_ready_non_formal"
            ],
            "blocked_stage_count": readiness_counts["blocked"],
            "formal_release_stage_count": 0,
            "json_emitter_ready_count": sum(
                item["readiness_axes"]["json_emitter_ready"]
                for item in stage_plans
            ),
            "rtl_semantics_compatible_count": sum(
                item["readiness_axes"]["rtl_semantics_compatible"]
                for item in stage_plans
            ),
            "dynamic_release_ready_count": sum(
                item["readiness_axes"]["dynamic_release_ready"]
                for item in stage_plans
            ),
        },
        "families": family_records,
        "stage_plans": stage_plans,
    }
    payload["system_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def validate_stage_config_system(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_stage_config_system(project_root):
        raise StageConfigSystemError(
            "stage-to-operator-config system differs from current inputs"
        )


def write_stage_config_system(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "SCHEMA",
    "StageConfigSystemError",
    "build_stage_config_system",
    "validate_stage_config_system",
    "write_stage_config_system",
]
