"""Fail-closed complete-JSON regeneration audit for ResNet50 QuantizeLinear.

This module intentionally stops before target emission when any strict JSON
leaf is unresolved.  The pinned upstream INT32->UINT8 JSON is treated as an
exact reference only for its own source instance and as a field/primitive
oracle for the two FP32->UINT8 ResNet50 stages.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "resnet50-quantize-linear-complete-json-regeneration-v1"
ARTIFACT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5_complete_json_regeneration_v1/quantize_linear"
)
SOURCE_TEMPLATE_REL = Path(
    "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json"
)
SOURCE_COMMIT = "ec12424516ae0304228dd2321d4e604fe225e04e"
SOURCE_BLOB = "959e759e81eea358f52680c091f2dfa1535f564d"
SOURCE_SHA256 = "db638f0640e74217e80e61350a2fe400f7b495e2201f17c39915328cdd455ba2"
CURRENT_NODE75_ZIP_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_n75_0cc_bankrow_v9.zip"
)
CURRENT_NODE75_ZIP_SHA256 = (
    "f0034876998f636ea0cdd473f830daed896cc7b315fdb73ab617e59d6f3c8165"
)
PUBLIC_POLICY_REL = Path(
    "contracts/operator_config/complete_json_generation_contract_v1.json"
)
PUBLIC_CANDIDATE_VALIDATOR_REL = Path(
    "tools/validate_complete_operator_json_candidate.py"
)
PUBLIC_FAMILY_AUDITOR_REL = Path(
    "tools/audit_complete_operator_json_family_set.py"
)
PUBLIC_SCHEMA_RELS = (
    Path("schemas/operator_config_complete_json_candidate_v1.schema.json"),
    Path("schemas/operator_config_field_provenance_ledger_v1.schema.json"),
    Path("schemas/operator_config_handler_capability_v1.schema.json"),
    Path("schemas/operator_config_current_test_diff_v1.schema.json"),
    Path("schemas/operator_config_composition_boundary_v1.schema.json"),
    Path("schemas/operator_config_complete_json_family_set_v1.schema.json"),
)

ALLOWED_ORIGINS = {
    "REFERENCE_EXACT",
    "MODEL_DERIVED",
    "RTL_DERIVED",
    "ENCODER_DERIVED",
    "ADDRESS_PLANNER_DERIVED",
    "SCHEDULE_DERIVED",
    "EXPLICIT_DISABLED",
    "UNRESOLVED",
}
ABSENCE_STATES = {
    "SOURCE_ABSENT_NOT_APPLICABLE",
    "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
    "EXPLICIT_NULL_INACTIVE",
    "EXPLICIT_ZERO",
    "TARGET_REQUIRED_DERIVED",
}


class QuantizeCompleteJsonError(ValueError):
    """Raised when a source identity or fail-closed invariant is violated."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QuantizeCompleteJsonError(f"JSON root must be an object: {path}")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def pointer_escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def flatten_json(value: Any, pointer: str = "") -> list[tuple[str, Any]]:
    """Return one record for every primitive JSON leaf, including nulls."""
    leaves: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            leaves.extend(flatten_json(child, f"{pointer}/{pointer_escape(key)}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            leaves.extend(flatten_json(child, f"{pointer}/{index}"))
    else:
        leaves.append((pointer or "/", value))
    return leaves


def _find_request(bundle: dict[str, Any], request_id: str) -> dict[str, Any]:
    for request in bundle["requests"]:
        if request["request_id"] == request_id:
            return request
    raise QuantizeCompleteJsonError(f"missing lowering request: {request_id}")


def _find_edge(
    lifetime: dict[str, Any], producer: str, consumer: str
) -> dict[str, Any]:
    for edge in lifetime["typed_tensor_dag"]["edges"]:
        if (
            edge["producer_request_id"] == producer
            and edge["consumer_request_id"] == consumer
        ):
            return edge
    raise QuantizeCompleteJsonError(f"missing DAG edge: {producer}->{consumer}")


def _typed_param(request: dict[str, Any], name: str) -> dict[str, Any]:
    for item in request["typed_parameters"]:
        if item["name"] == name:
            return item
    raise QuantizeCompleteJsonError(
        f"missing typed parameter {name}: {request['request_id']}"
    )


def _logical_tensor(port: dict[str, Any]) -> dict[str, Any]:
    shape = list(port["shape"])
    elements = 1
    for extent in shape:
        elements *= extent
    dtype = port["dtype"]
    itemsize = {"float32": 4, "uint8": 1}[dtype]
    return {
        "tensor_id": port["tensor_id"],
        "dtype": dtype,
        "shape": shape,
        "element_count": elements,
        "logical_bytes": elements * itemsize,
    }


def build_stage_inventory(root: Path) -> dict[str, Any]:
    bundle = load_json(root / "contracts/resnet50_r5_lowering_bundle.json")
    lifetime = load_json(
        root / "contracts/operator_config/stage_state_lifetime_contract_v1.json"
    )
    stages = []
    specifications = [
        {
            "request_id": "r5:hwop-0000-00",
            "signature": "fp32_nchw_16x3x224x224_to_u8_per_tensor_zp114",
            "logical_layout": "NCHW_CONTIGUOUS",
            "producer": "GRAPH_INPUT",
            "consumer": "r5:hwop-0001-00",
            "execution_disposition": "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED",
            "address_owner": "shared allocator/address planner for hwop-0000 D",
        },
        {
            "request_id": "r5:hwop-0074-00",
            "signature": "approved_u8_alias_16x2048_no_quant_config",
            "logical_layout": "NC_CONTIGUOUS",
            "producer": "r5:hwop-0073-00",
            "consumer": "r5:hwop-0075-00",
            "execution_disposition": "APPROVED_EQUIVALENT_NO_TARGET_JSON",
            "address_owner": "node0071 producer plus node0075 integration allocator/execplan",
        },
    ]
    for spec in specifications:
        request = _find_request(bundle, spec["request_id"])
        input_tensor = _logical_tensor(request["ports"]["inputs"][0])
        output_tensor = _logical_tensor(request["ports"]["outputs"][0])
        scale = _typed_param(request, "y_scale")
        zero_point = _typed_param(request, "y_zero_point")
        if spec["producer"] == "GRAPH_INPUT":
            input_edge = next(
                item
                for item in lifetime["typed_tensor_dag"]["external_inputs"]
                if item["consumer_request_id"] == spec["request_id"]
            )
        else:
            input_edge = _find_edge(lifetime, spec["producer"], spec["request_id"])
        output_edge = _find_edge(
            lifetime, spec["request_id"], spec["consumer"]
        )
        stages.append(
            {
                "request_id": request["request_id"],
                "hw_op_id": request["identity"]["hw_op_id"],
                "hw_op_type": request["identity"]["hw_op_type"],
                "node_id": request["identity"]["node_id"],
                "onnx_name": request["identity"]["onnx_name"],
                "op": "QuantizeLinear",
                "materialized_consumer_signature": spec["signature"],
                "execution_disposition": spec["execution_disposition"],
                "input": input_tensor,
                "output": output_tensor,
                "layout": {
                    "logical": spec["logical_layout"],
                    "hardware_profile_approved": True,
                    "target_schedule_materialized": False,
                },
                "qparams": {
                    "granularity": "per_tensor",
                    "axis": None,
                    "scale_dtype": scale["value"]["dtype"],
                    "scale_bits": scale["value"]["float32_bits"],
                    "scale_scalar": scale["value"]["scalar"],
                    "scale_sha256": scale["value"]["value_sha256"],
                    "zero_point_dtype": zero_point["value"]["dtype"],
                    "zero_point": zero_point["value"]["scalar"],
                    "zero_point_sha256": zero_point["value"]["value_sha256"],
                },
                "padding_tail": {
                    "input_transaction_bytes": 32,
                    "input_transaction_tail_bytes": input_tensor["logical_bytes"] % 32,
                    "output_transaction_bytes": 32,
                    "output_transaction_tail_bytes": output_tensor["logical_bytes"] % 32,
                    "hardware_tile_tail": "UNRESOLVED_NO_TARGET_SCHEDULE",
                    "implicit_zero_or_padding_allowed": False,
                },
                "dag": {
                    "producer": spec["producer"],
                    "consumer": spec["consumer"],
                    "input_edge": input_edge,
                    "output_edge": output_edge,
                },
                "lifetime": {
                    "accepted_lifetime_materialized": False,
                    "implicit_prior_state_allowed": False,
                    "output_physical_allocation_status": output_edge[
                        "physical_allocation_status"
                    ],
                },
                "address_owner": spec["address_owner"],
                "request_sha256": request["request_sha256"],
            }
        )
    return {
        "schema": f"{SCHEMA}-stage-inventory",
        "family": "quantize_linear",
        "stage_count": len(stages),
        "equivalence_class_count": len(
            {item["materialized_consumer_signature"] for item in stages}
        ),
        "stages": stages,
    }


def build_reference_applicability(root: Path) -> dict[str, Any]:
    corpus = load_json(root / "contracts/operator_config/ndpsim_json_corpus_v1.json")
    by_id = {item["template_id"]: item for item in corpus["templates"]}
    selected = [
        (
            "quant_from_buffer_int32MN_uint8MN",
            "C",
            "same GA/LC/Buffer hardware blocks and UINT8 pack, but INT32 ingress, "
            "fixed [1,32,32] schedule, fixed constants, and no exact FP32 division",
        ),
        (
            "prefill_sum_rec_fp32MN_fp32MN",
            "C",
            "FP32 GA/SFU REC entry exists, but it is reduction+approximate REC and "
            "does not preserve the elementwise exact-division boundary",
        ),
        (
            "decode_sum_rec_fp32N_fp32N",
            "C",
            "decode REC is an approximate SFU primitive, not exact binary32 divide",
        ),
        (
            "prefill_mul_fp32MN_fp32M_fp32MN",
            "C",
            "raw FP32 ingress and multiply transport exist; reciprocal-MUL is "
            "bit-exactly contradicted for node0074",
        ),
    ]
    references = []
    for template_id, grade, reason in selected:
        item = by_id[template_id]
        references.append(
            {
                "template_id": template_id,
                "path": item["path"],
                "sha256": item["sha256"],
                "source_commit": item["configuration_authority"]["provenance"][
                    "pinned_commit"
                ],
                "source_blob": item["configuration_authority"]["provenance"][
                    "pinned_git_blob_oid"
                ],
                "self_instance_grade": "A",
                "target_grade": grade,
                "applies_to_target_stages": [
                    "r5:hwop-0000-00",
                    "r5:hwop-0074-00",
                ],
                "reason": reason,
                "authority_boundary": (
                    "exact only for unchanged source instance; target derivation "
                    "requires independent proof"
                ),
            }
        )
    project_added = []
    for rel in (
        "ndp-sim/jsons/MatMulInt32Accumulate.json",
        "ndp-sim/jsons/Node0075RequantScaleInt32ToFp32.json",
        "ndp-sim/jsons/Node0075RequantRoundFp32ToUint8.json",
        "ndp-sim/jsons/node0004_accumulate_wave0.json",
        "ndp-sim/jsons/node0004_accumulate_wave0_nopp_r1.json",
    ):
        path = root / rel
        if path.is_file():
            project_added.append(
                {
                    "path": rel,
                    "sha256": sha256_file(path),
                    "target_grade": "D",
                    "authority": "PROJECT_ADDED_OR_UNTRACKED_NO_UPSTREAM_AUTHORITY",
                    "used_for_target_derivation": False,
                }
            )
    return {
        "schema": f"{SCHEMA}-reference-applicability",
        "grading": {
            "A": "exact replay of the exact source instance",
            "B": "same numeric primitive with only shape difference",
            "C": "same hardware block but numeric or dtype difference",
            "D": "project-added, untracked, or otherwise lacks upstream authority",
        },
        "corpus_template_count": len(corpus["templates"]),
        "direct_division_template_count": 0,
        "selected_references": references,
        "project_added_excluded": project_added,
        "target_grade_summary": dict(
            sorted(Counter(item["target_grade"] for item in references).items())
        ),
        "reuse_class": "STRUCTURE_OR_PRIMITIVE_ONLY",
    }


def build_handler_capability(root: Path) -> dict[str, Any]:
    handler_path = (
        root
        / "ndp-sim/model_execplan/src/execution_plan_generator/control_registers.py"
    )
    handler = handler_path.read_text(encoding="utf-8")
    registry_path = root / "ndp-sim/model_execplan/config/operator_base_info.json"
    registry = load_json(registry_path)["operators"]
    mapper_path = root / "ndp-sim/address_remapping/tests/test_solver.py"
    mapper_text = mapper_path.read_text(encoding="utf-8")
    encoder_path = root / "ndp-sim/bitstream/config/general.py"
    encoder_text = encoder_path.read_text(encoding="utf-8")
    if "Placeholder for quant_from_buffer_int32MN_uint8MN" not in handler:
        raise QuantizeCompleteJsonError("quant handler boundary changed")
    if 'assertNotIn("quant_from_buffer_int32MN_uint8MN", registry)' not in mapper_text:
        raise QuantizeCompleteJsonError("quant mapper boundary changed")
    if re.search(r"[\"'](?:f?div|divide)[\"']", encoder_text, re.IGNORECASE):
        raise QuantizeCompleteJsonError("encoder may now expose division")
    static_template = load_json(root / SOURCE_TEMPLATE_REL)
    static_stride = static_template["stream_engine"]["stream2"]["dim_stride"][1]
    handler_stride = registry["quant_from_buffer_int32MN_uint8MN"]["initial_size"][
        "D"
    ][2] * 32
    matrix = {
        "exact_replay": {
            "status": "SOURCE_INSTANCE_ONLY",
            "target_supported": False,
            "reason": "only pinned INT32 [1,32,32] source JSON is authoritative",
        },
        "shape": {
            "status": "CONTRADICTED_PLACEHOLDER_NOT_GENERALIZATION",
            "target_supported": False,
            "reason": "rank-3 placeholder formulas do not authorize rank-4/rank-2 targets",
        },
        "dtype": {
            "status": "PARTIAL_PRIMITIVE_ONLY",
            "target_supported": False,
            "reason": "raw FP32 GA ingress exists, but exact FP32 division does not",
        },
        "qparam": {
            "status": "ABSENT",
            "target_supported": False,
            "reason": "handler transports no scale, zero-point, or magic constants",
        },
        "layout": {
            "status": "MODEL_PROFILE_RESOLVED_TARGET_SCHEDULE_UNRESOLVED",
            "target_supported": False,
        },
        "address": {
            "status": "CONTRADICTED_FOR_NATIVE_HANDLER_MATERIALIZATION",
            "target_supported": False,
            "static_stream2_dim_stride_1": static_stride,
            "handler_materialized_stream2_dim_stride_1": handler_stride,
            "coverage_consequence": (
                "known formal return observed 256/1024 bytes per slice when "
                "the handler overwrote the static non-base field"
            ),
        },
        "cross_stage_schedule": {
            "status": "NO_GENERIC_QUANTIZE_TRANSPORT",
            "target_supported": False,
            "node0074_exception": (
                "approved-equivalent arithmetic elimination; not Quantize support"
            ),
        },
    }
    return {
        "schema": f"{SCHEMA}-handler-capability",
        "template_registry_present": True,
        "handler_present": True,
        "handler_class": "PLACEHOLDER",
        "mapper_registered": False,
        "direct_binary32_division_opcode": None,
        "rec_opcode": 17,
        "matrix": matrix,
        "source_receipts": [
            _receipt(root, handler_path.relative_to(root), "semantic_current_match"),
            _receipt(root, registry_path.relative_to(root), "semantic_current_match"),
            _receipt(root, mapper_path.relative_to(root), "semantic_current_match"),
            _receipt(root, encoder_path.relative_to(root), "semantic_current_match"),
        ],
        "first_unavoidable_capability": "EXACT_BINARY32_DIVIDE_RNE",
    }


def _ledger_resolution(pointer: str, source_value: Any) -> dict[str, Any]:
    if pointer == "/general_array/inport/inport0/int32tofp32":
        return {
            "target_value": False,
            "origin": "RTL_DERIVED",
            "applicability": "TARGET_FP32_RAW_INGRESS_REQUIRES_CONVERSION_DISABLED",
            "exactness_axes": ["target_input_dtype"],
            "derivation": "FP32 input must not pass through INT32-to-FP32 conversion",
            "current_consumer_equation": "GA_in0 = raw_binary32(A_word)",
            "status": "TARGET_REQUIRED_DERIVED",
            "absence_state": "TARGET_REQUIRED_DERIVED",
        }
    if pointer.startswith("/general_array/inport/inport0/") and pointer.rsplit("/", 1)[
        -1
    ] in {
        "fp16tofp32",
        "bf16tofp32",
        "uint8tofp32",
        "uint8toint32",
    }:
        return {
            "target_value": False,
            "origin": "EXPLICIT_DISABLED",
            "applicability": "NON_FP32_INGRESS_CONVERSION_DISABLED",
            "exactness_axes": ["target_input_dtype"],
            "derivation": "target ingress is already FP32",
            "current_consumer_equation": "exactly one GA ingress interpretation",
            "status": "RESOLVED",
            "absence_state": "EXPLICIT_ZERO",
        }
    if pointer == "/general_array/outport/int32touint8":
        return {
            "target_value": True,
            "origin": "REFERENCE_EXACT",
            "applicability": "MATCHING_UINT8_SATURATION_PACK_PRIMITIVE",
            "exactness_axes": ["output_dtype", "signed_saturate_u8", "packing"],
            "derivation": "reuse exact output conversion primitive only",
            "current_consumer_equation": "D=pack4(saturate_signed_int32_to_u8(q))",
            "status": "RESOLVED_PRIMITIVE_ONLY",
            "absence_state": None,
        }
    if pointer in {
        "/general_array/outport/fp32tofp16",
        "/general_array/outport/fp32tobf16",
    }:
        return {
            "target_value": False,
            "origin": "EXPLICIT_DISABLED",
            "applicability": "NON_TARGET_OUTPUT_CONVERSION_DISABLED",
            "exactness_axes": ["output_dtype"],
            "derivation": "target output dtype is UINT8",
            "current_consumer_equation": "no FP16/BF16 output conversion",
            "status": "RESOLVED",
            "absence_state": "EXPLICIT_ZERO",
        }
    return {
        "target_value": None,
        "origin": "UNRESOLVED",
        "applicability": "SOURCE_INSTANCE_VALUE_NOT_AUTHORIZED_FOR_FP32_TARGET",
        "exactness_axes": [],
        "derivation": (
            "requires a proved exact-divider topology plus target shape/schedule/"
            "address materialization"
        ),
        "current_consumer_equation": "UNRESOLVED_TARGET_CONSUMER_EQUATION",
        "status": "UNRESOLVED",
        "absence_state": (
            "SOURCE_ABSENT_UNKNOWN_FOR_TARGET"
            if pointer.startswith("/general_array/PE_array/")
            else None
        ),
    }


def build_ledger(root: Path, inventory: dict[str, Any]) -> dict[str, Any]:
    source = load_json(root / SOURCE_TEMPLATE_REL)
    leaves = flatten_json(source)
    if len(leaves) != 516:
        raise QuantizeCompleteJsonError(
            f"source template leaf count changed: {len(leaves)}"
        )
    records = []
    for stage in inventory["stages"]:
        for pointer, value in leaves:
            resolution = _ledger_resolution(pointer, value)
            records.append(
                {
                    "stage_id": stage["request_id"],
                    "json_pointer": pointer,
                    "target_value": resolution["target_value"],
                    "origin": resolution["origin"],
                    "source": {
                        "repo": "ndp-sim",
                        "commit": SOURCE_COMMIT,
                        "blob": SOURCE_BLOB,
                        "path": SOURCE_TEMPLATE_REL.as_posix(),
                        "json_pointer": pointer,
                        "value": value,
                    },
                    "applicability": resolution["applicability"],
                    "exactness_axes": resolution["exactness_axes"],
                    "derivation": resolution["derivation"],
                    "current_consumer_equation": resolution[
                        "current_consumer_equation"
                    ],
                    "source_presence": "PRESENT",
                    "absence_state": resolution["absence_state"],
                    "status": resolution["status"],
                }
            )
    unresolved = [item for item in records if item["origin"] == "UNRESOLVED"]
    return {
        "schema": f"{SCHEMA}-field-provenance-ledger",
        "source_template": {
            "path": SOURCE_TEMPLATE_REL.as_posix(),
            "commit": SOURCE_COMMIT,
            "blob": SOURCE_BLOB,
            "sha256": SOURCE_SHA256,
            "leaf_count": len(leaves),
        },
        "target_stage_count": len(inventory["stages"]),
        "ledger_entry_count": len(records),
        "expected_ledger_entry_count": len(leaves) * len(inventory["stages"]),
        "allowed_origins": sorted(ALLOWED_ORIGINS),
        "absence_state_vocabulary": sorted(ABSENCE_STATES),
        "unresolved_count": len(unresolved),
        "resolved_count": len(records) - len(unresolved),
        "records": records,
    }


def _zip_member_json(archive: zipfile.ZipFile, suffix: str) -> dict[str, Any]:
    matches = [name for name in archive.namelist() if name.endswith(suffix)]
    if len(matches) != 1:
        raise QuantizeCompleteJsonError(
            f"expected exactly one ZIP member ending {suffix}: {matches}"
        )
    value = json.loads(archive.read(matches[0]).decode("utf-8"))
    if not isinstance(value, dict):
        raise QuantizeCompleteJsonError(f"ZIP JSON member is not object: {matches[0]}")
    return value


def build_current_test_diff(root: Path) -> dict[str, Any]:
    package = root / CURRENT_NODE75_ZIP_REL
    if sha256_file(package) != CURRENT_NODE75_ZIP_SHA256:
        raise QuantizeCompleteJsonError("current node0071-node0075 ZIP identity changed")
    with zipfile.ZipFile(package, "r") as archive:
        names = archive.namelist()
        manifest = _zip_member_json(archive, "/TEST_PACKAGE_MANIFEST.json")
        execplan = _zip_member_json(archive, "/p/execplan.json")
    quant_members = [
        name
        for name in names
        if "quantizelinear" in name.lower()
        or "quant_from_buffer" in name.lower()
        or "node0074" in name.lower()
    ]
    a_coverage = manifest["a_coverage"]
    first_pass = a_coverage["passes"][0]
    unique_first_pass_bytes = sum(
        item["accepted_occurrence_count"] * 32
        for item in first_pass["slice_records"]
    )
    categories = {
        "same": [
            {
                "scope": "node0074 logical output versus node0075 A",
                "fields": ["dtype=uint8", "shape=[16,2048]", "logical_bytes=32768"],
                "evidence": (
                    "approved-equivalent contract plus package configured A coverage"
                ),
            }
        ],
        "intentional_derivation": [
            {
                "scope": "node0074",
                "difference": "Quantize strict JSON/config/execplan occurrence absent",
                "reason": (
                    "approved-equivalent paired Dequant/View/Quant elimination; "
                    "node0075 reads original node0071 UINT8 storage"
                ),
                "suspected_defect": False,
            },
            {
                "scope": "node0000",
                "difference": "no current Quantize package/config to compare",
                "reason": (
                    "current operator packages consume already-quantized external "
                    "UINT8 inputs and do not claim graph-input Quantize coverage"
                ),
                "suspected_defect": False,
            },
        ],
        "suspected_current_defect": [
            {
                "scope": "native quant handler materialization, not current package",
                "json_pointer": "/stream_engine/stream2/dim_stride/1",
                "static_value": 256,
                "handler_materialized_value_for_source_shape": 1024,
                "effect": (
                    "known 256/1024-byte formal-D coverage per slice; violates "
                    "non-base field ownership if used without explicit authorization"
                ),
                "explains_current_package_blocker": False,
            }
        ],
        "new_candidate_defect": [],
        "dynamic_only": [
            {
                "scope": "node0071->node0075 v9",
                "items": [
                    "actual producer completion before pass00 first A read",
                    "8192 actual accepted A request/data events and hashes",
                    "natural terminal",
                    "144 formal D conjunction",
                ],
                "config_difference_explanation_allowed": False,
            }
        ],
    }
    return {
        "schema": f"{SCHEMA}-current-test-diff",
        "current_quantize_package_count": 0,
        "current_consuming_package": {
            "path": CURRENT_NODE75_ZIP_REL.as_posix(),
            "bytes": package.stat().st_size,
            "sha256": CURRENT_NODE75_ZIP_SHA256,
            "status": manifest["status"],
            "candidate_release": manifest["candidate_release"],
            "stage_count": manifest["stage_count"],
            "quantize_named_members": quant_members,
            "execplan_line_count": execplan["combined"]["line_count_128bit"],
            "node0075_a": {
                "configured_occurrence_count": a_coverage[
                    "accepted_occurrence_count"
                ],
                "configured_traffic_bytes": a_coverage["accepted_traffic_bytes"],
                "pass_count": len(a_coverage["passes"]),
                "first_pass_unique_bytes": unique_first_pass_bytes,
                "first_slice_base": first_pass["slice_records"][0]["base_addr"],
                "last_slice_base": first_pass["slice_records"][-1]["base_addr"],
                "dynamic_acceptance_proven": False,
            },
        },
        "comparison_categories": categories,
        "suspected_current_config_issue_count": len(
            categories["suspected_current_defect"]
        ),
        "new_candidate_defect_count": 0,
        "excluded_non_config_blockers": categories["dynamic_only"],
    }


def _receipt(root: Path, rel: Path | str, gate: str) -> dict[str, Any]:
    rel_path = Path(rel)
    path = root / rel_path
    return {
        "path": rel_path.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "gate": gate,
    }


def source_receipts(root: Path) -> list[dict[str, Any]]:
    semantic = [
        ".agents/agent.md",
        ".agents/rules/生成前必读索引.md",
        ".agents/rules/算子配置规则.md",
        ".agents/rules/NDP硬件字段语义.md",
        ".agents/rules/精确UINT8量化尾专项规则.md",
        "contracts/resnet50_r5_lowering_bundle.json",
        "contracts/typed_config_parameter_contract.json",
        "contracts/operator_config/stage_state_lifetime_contract_v1.json",
        "contracts/operator_config/ndpsim_json_corpus_v1.json",
        "contracts/operator_config/operator_config_authority_v1.json",
        "contracts/operator_config/quantize_node0074_exact_division_reuse_audit_v2.json",
        "contracts/operator_config/quantize_node0074_dq_view_q_identity_fusion_v1.json",
        "contracts/operator_config/resnet50_node0072_node0074_shared_endpoint_v1.json",
        SOURCE_TEMPLATE_REL.as_posix(),
        "ndp-sim/model_execplan/config/operator_base_info.json",
        "ndp-sim/model_execplan/src/execution_plan_generator/control_registers.py",
        "ndp-sim/address_remapping/tests/test_solver.py",
        "ndp-sim/bitstream/config/general.py",
        ".agents/task_records/20260727_human_mac_v3_fd2_formal_return_analysis.md",
        ".agents/task_records/20260805_node0075_v5_return_bankrow_cloud_v9_package_ready.md",
        PUBLIC_POLICY_REL.as_posix(),
        PUBLIC_CANDIDATE_VALIDATOR_REL.as_posix(),
        PUBLIC_FAMILY_AUDITOR_REL.as_posix(),
    ]
    semantic.extend(path.as_posix() for path in PUBLIC_SCHEMA_RELS)
    receipts = [_receipt(root, item, "semantic_current_match") for item in semantic]
    receipts.append(_receipt(root, ".agents/plan.md", "mutable_provenance_only"))
    receipts.append(_receipt(root, CURRENT_NODE75_ZIP_REL, "read_only_current_test"))
    return receipts


def build_complete_json_manifest(
    inventory: dict[str, Any], ledger: dict[str, Any]
) -> dict[str, Any]:
    per_stage = []
    for stage in inventory["stages"]:
        count = sum(
            1
            for item in ledger["records"]
            if item["stage_id"] == stage["request_id"]
            and item["origin"] == "UNRESOLVED"
        )
        per_stage.append(
            {
                "stage_id": stage["request_id"],
                "materialized": False,
                "unresolved_leaf_count": count,
                "status": (
                    "APPROVED_EQUIVALENT_NO_TARGET_JSON"
                    if stage["request_id"] == "r5:hwop-0074-00"
                    else "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED"
                ),
                "first_unavoidable_capability": "EXACT_BINARY32_DIVIDE_RNE",
            }
        )
    return {
        "schema": f"{SCHEMA}-complete-json-manifest",
        "strict_complete_json_required": True,
        "materialized_target_count": 0,
        "materialization_allowed": False,
        "reason": "one or more required target leaves are UNRESOLVED",
        "source_file_preserved": True,
        "source_file_modified": False,
        "targets": per_stage,
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def _bound(root: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
    }


def _public_source_entry(pointer: str, value: Any) -> dict[str, Any]:
    return {
        "json_pointer": pointer,
        "target_value": value,
        "origin": "REFERENCE_EXACT",
        "applicability_class": "UNRESOLVED",
        "exactness_axes": {
            "op": False,
            "dtype": False,
            "shape": False,
            "layout": False,
            "qparams": False,
            "topology": True,
            "address": False,
            "schedule": False,
            "consumer": False,
        },
        "owner": "quantize_linear family owner",
        "consumer_equation": (
            "source replay leaf only; no FP32 QuantizeLinear target consumer "
            "equation is authorized"
        ),
        "derivation_receipt": None,
        "source": {
            "path": SOURCE_TEMPLATE_REL.as_posix(),
            "commit": SOURCE_COMMIT,
            "blob_oid": SOURCE_BLOB,
            "file_sha256": SOURCE_SHA256,
            "json_pointer": pointer,
            "value": value,
        },
        "negative_control_ids": [
            "NC_QUANT_INT32_INGRESS_IS_NOT_FP32",
            "NC_QUANT_REC_MUL_159_VS_158",
        ],
        "status": "UNRESOLVED",
    }


def _public_source_absences(stage: dict[str, Any]) -> list[dict[str, str]]:
    owner = "quantize_linear family owner"
    shape_token = "x".join(str(item) for item in stage["output"]["shape"])
    return [
        {
            "target_json_pointer": (
                "/general_array/PE_array/"
                "exact_binary32_divide_rne/alu_opcode"
            ),
            "state": "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
            "reason": (
                "no exact binary32 division opcode or proved bit-exact "
                "composition exists for the target"
            ),
            "owner": owner,
        },
        {
            "target_json_pointer": (
                "/general_array/PE_array/"
                "exact_binary32_divide_rne/scale_bits"
            ),
            "state": "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
            "reason": (
                f"target scale {stage['qparams']['scale_bits']} requires typed "
                "per-stage constant transport"
            ),
            "owner": owner,
        },
        {
            "target_json_pointer": "/loop_control/target_shape",
            "state": "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
            "reason": (
                f"target shape {shape_token} requires a non-placeholder schedule"
            ),
            "owner": "native handler or authorized schedule materializer",
        },
        {
            "target_json_pointer": "/stream_engine/target_addresses",
            "state": "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
            "reason": (
                "target base/offset/coverage/lifetime remain allocator owned and "
                "cannot be copied from the source instance"
            ),
            "owner": "shared address planner and lifetime owner",
        },
    ]


def _public_handler_document(root: Path, leaves: list[tuple[str, Any]]) -> dict[str, Any]:
    handler_rel = Path(
        "ndp-sim/model_execplan/src/execution_plan_generator/"
        "control_registers.py"
    )
    false_evidence = {
        "exact_replay": (
            "The pinned source is exact only for INT32 [1,32,32], not either "
            "FP32 QuantizeLinear target."
        ),
        "shape": (
            "The placeholder handler updates a fixed rank-3 loop/stride subset "
            "and has no rank-4 or rank-2 target proof."
        ),
        "dtype": (
            "The source enables INT32-to-FP32 ingress; the targets require raw "
            "FP32 plus exact binary32 division."
        ),
        "qparam": (
            "The handler transports neither target scale bits nor arbitrary "
            "UINT8 zero point."
        ),
        "layout": (
            "No target NCHW/NC hardware schedule is materialized by the "
            "placeholder handler."
        ),
        "address": (
            "The handler changes stream2.dim_stride[1] from source 256 to 1024 "
            "without a target address/coverage proof."
        ),
        "cross_stage_schedule": (
            "No generic typed Quantize transport or visibility/lifetime schedule "
            "is registered; node0074's graph equivalence is not handler support."
        ),
    }
    changed = [
        "shape",
        "dtype",
        "qparam",
        "layout",
        "address",
        "cross_stage_schedule",
    ]
    return {
        "schema": "operator_config_handler_capability_v1",
        "family": "quantize_linear",
        "handler": {
            "kind": "PLACEHOLDER",
            "path": handler_rel.as_posix(),
            "sha256": sha256_file(root / handler_rel),
            "source_span": (
                "quant_from_buffer_int32MN_uint8MN placeholder branch"
            ),
        },
        "capabilities": {
            axis: {"supported": False, "evidence": false_evidence[axis]}
            for axis in (
                "exact_replay",
                "shape",
                "dtype",
                "qparam",
                "layout",
                "address",
                "cross_stage_schedule",
            )
        },
        "dependent_leaves": [
            {
                "json_pointer": pointer,
                "axes": changed,
                "covered_by": (
                    "no authorized target handler; source leaf remains "
                    "diagnostic-only"
                ),
                "status": "UNCOVERED",
            }
            for pointer, _ in leaves
        ],
        "claim_boundary": (
            "Static handler capability audit only; all source projection leaves "
            "remain uncovered for the FP32 QuantizeLinear targets."
        ),
    }


def _public_composition_document(stage: dict[str, Any]) -> dict[str, Any]:
    byte_count = stage["input"]["logical_bytes"]
    return {
        "schema": "operator_config_composition_boundary_v1",
        "family": "quantize_linear",
        "boundaries": [
            {
                "boundary_id": (
                    f"{stage['hw_op_id']}:fp32_ingress_to_exact_divide"
                ),
                "producer_dtype": "float32",
                "consumer_dtype": "float32",
                "shape": json.dumps(stage["input"]["shape"], separators=(",", ":")),
                "layout": stage["layout"]["logical"],
                "producer_byte_set": f"contiguous[0,{byte_count})",
                "consumer_required_byte_set": f"contiguous[0,{byte_count})",
                "transaction_bytes": 32,
                "tag_last": "UNRESOLVED_NO_TARGET_SCHEDULE",
                "clock_handshake": "UNRESOLVED_NO_COMPOSITE_RUNTIME_PRODUCER",
                "lifetime_visibility": "UNRESOLVED_NO_ADDRESS_BOUND_LIFETIME",
                "qparam_rounding": (
                    "binary32 x/scale -> RNE ties-even -> add zp -> clamp_u8; "
                    "exact divide primitive is absent"
                ),
                "status": "UNRESOLVED",
                "evidence": [
                    (
                        "contracts/operator_config/"
                        "quantize_node0074_exact_division_reuse_audit_v2.json"
                    ),
                    (
                        "ndp-sim/bitstream/config/general.py exposes REC but no "
                        "exact DIV opcode"
                    ),
                ],
            }
        ],
        "claim_boundary": (
            "Prospective primitive-composition boundary only; no composite "
            "target JSON or runtime path is materialized."
        ),
    }


def _public_current_diff_document(
    stage: dict[str, Any],
    leaves: list[tuple[str, Any]],
) -> dict[str, Any]:
    node0074 = stage["hw_op_id"] == "hwop-0074-00"
    latest = (
        "Current node0071-node0075 v9 package intentionally omits Quantize "
        "through approved-equivalent paired elimination."
        if node0074
        else (
            "No current graph-input Quantize configuration exists; scoped "
            "operator packages consume already-quantized external UINT8."
        )
    )
    entries = [
        {
            "json_pointer": pointer,
            "candidate_value": value,
            "current_value_present": False,
            "current_value": None,
            "classification": "CURRENT_ABSENT",
            "reason": (
                "no current target Quantize JSON exists; another family or the "
                "nearest upstream template is not a baseline"
            ),
            "evidence": [
                (
                    "artifacts/operator_config_validation/"
                    "r5-server-test-packages/r5_n71_n75_0cc_bankrow_v9.zip"
                    if node0074
                    else "contracts/resnet50_r5_lowering_bundle.json"
                )
            ],
        }
        for pointer, value in leaves
    ]
    blockers = [
        {
            "blocker_id": "B_QUANT_TAIL_EXACT_FP32_DIVISION",
            "classification": "CONFIG_EXCLUDED",
            "candidate_json_pointers": [],
            "reason": (
                "The first divergence is a missing exact binary32 divide "
                "capability, not a difference in a current Quantize config."
            ),
            "evidence": [
                (
                    "contracts/operator_config/"
                    "quantize_node0074_exact_division_reuse_audit_v2.json"
                )
            ],
        }
    ]
    if node0074:
        blockers.append(
            {
                "blocker_id": "B_NODE0071_NODE0075_DYNAMIC_ACCEPTANCE",
                "classification": "DYNAMIC_ONLY",
                "candidate_json_pointers": [],
                "reason": (
                    "producer visibility, accepted A events, natural terminal, "
                    "and formal D cannot be explained by Quantize JSON omission"
                ),
                "evidence": [
                    (
                        "artifacts/operator_config_validation/"
                        "r5-server-test-packages/r5_n71_n75_0cc_bankrow_v9.zip"
                    )
                ],
            }
        )
    return {
        "schema": "operator_config_current_test_diff_v1",
        "family": "quantize_linear",
        "candidate_json_sha256": SOURCE_SHA256,
        "current_identity": {
            "available": False,
            "path": None,
            "sha256": None,
            "package_or_record": (
                CURRENT_NODE75_ZIP_REL.as_posix() if node0074 else None
            ),
            "latest_result": latest,
        },
        "entries": entries,
        "blocker_attribution": blockers,
        "claim_boundary": (
            "Leaf-complete comparison to the absence of a current target "
            "Quantize JSON; package/observer/RTL dynamic issues are excluded."
        ),
    }


def build_public_gate_documents(
    root: Path,
    output: Path,
    inventory: dict[str, Any],
) -> list[str]:
    source = load_json(root / SOURCE_TEMPLATE_REL)
    leaves = flatten_json(source)
    handler = _public_handler_document(root, leaves)
    handler_path = output / "public_gate/handler_capability.json"
    _write_json(handler_path, handler)
    generated: list[str] = [
        handler_path.relative_to(output).as_posix(),
    ]
    contract_paths: list[Path] = []
    for stage in inventory["stages"]:
        stage_id = stage["hw_op_id"]
        ledger = {
            "schema": "operator_config_field_provenance_ledger_v1",
            "family": "quantize_linear",
            "candidate_json_sha256": SOURCE_SHA256,
            "entries": [
                _public_source_entry(pointer, value) for pointer, value in leaves
            ],
            "source_absences": _public_source_absences(stage),
            "claim_boundary": (
                "All 516 leaves bind the pinned INT32 source projection only; "
                "none is promoted to an FP32 QuantizeLinear target leaf."
            ),
        }
        ledger_path = output / f"public_gate/{stage_id}/field_provenance_ledger.json"
        _write_json(ledger_path, ledger)
        composition = _public_composition_document(stage)
        composition_path = output / f"public_gate/{stage_id}/composition_boundary.json"
        _write_json(composition_path, composition)
        diff = _public_current_diff_document(stage, leaves)
        diff_path = output / f"public_gate/{stage_id}/current_test_diff.json"
        _write_json(diff_path, diff)
        contract = {
            "schema": "operator_config_complete_json_candidate_v1",
            "family": "quantize_linear",
            "candidate_status": "BLOCKED",
            "reference_class": "C",
            "changed_axes": [
                "shape",
                "dtype",
                "qparam",
                "layout",
                "address",
                "cross_stage_schedule",
            ],
            "target_hw_op_types": ["QuantizeLinear"],
            "stage_ids": [stage_id],
            "candidate_json": _bound(root, root / SOURCE_TEMPLATE_REL),
            "field_provenance_ledger": _bound(root, ledger_path),
            "handler_capability": _bound(root, handler_path),
            "current_test_diff": _bound(root, diff_path),
            "composition": {
                "required": True,
                "boundary": _bound(root, composition_path),
            },
            "artifact_root": output.relative_to(root).as_posix(),
            "claim_boundary": (
                "BLOCKED diagnostic contract. candidate_json binds the unchanged "
                "pinned INT32 source instance for leaf enumeration only; it is "
                "not a materialized FP32 QuantizeLinear target."
            ),
        }
        contract_path = output / f"public_gate/{stage_id}/candidate_contract.json"
        _write_json(contract_path, contract)
        contract_paths.append(contract_path)
        generated.extend(
            [
                ledger_path.relative_to(output).as_posix(),
                composition_path.relative_to(output).as_posix(),
                diff_path.relative_to(output).as_posix(),
                contract_path.relative_to(output).as_posix(),
            ]
        )
    family_set = {
        "schema": "operator_config_complete_json_family_set_v1",
        "family": "quantize_linear",
        "target_hw_op_types": ["QuantizeLinear"],
        "candidate_contracts": [
            _bound(root, path) for path in contract_paths
        ],
        "no_config_stages": [],
        "claim_boundary": (
            "Covers both QuantizeLinear lowering stages exactly once with "
            "BLOCKED diagnostic contracts; no View no-config exemption is used."
        ),
    }
    family_set_path = output / "family_set.json"
    _write_json(family_set_path, family_set)
    generated.append(family_set_path.relative_to(output).as_posix())
    return generated


def build_artifacts(root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    output = output_dir or (root / ARTIFACT_REL)
    if sha256_file(root / SOURCE_TEMPLATE_REL) != SOURCE_SHA256:
        raise QuantizeCompleteJsonError("pinned quant source JSON identity changed")
    inventory = build_stage_inventory(root)
    references = build_reference_applicability(root)
    handler = build_handler_capability(root)
    ledger = build_ledger(root, inventory)
    current_diff = build_current_test_diff(root)
    complete_manifest = build_complete_json_manifest(inventory, ledger)
    outputs = {
        "complete_json/manifest.json": complete_manifest,
        "stage_inventory.json": inventory,
        "field_provenance_ledger.json": ledger,
        "reference_applicability.json": references,
        "handler_capability.json": handler,
        "current_test_diff.json": current_diff,
    }
    for rel, value in outputs.items():
        _write_json(output / rel, value)
    public_gate_outputs = build_public_gate_documents(root, output, inventory)
    receipts = source_receipts(root)
    artifact_receipts = [
        _receipt(root, (output / rel).relative_to(root), "generated_artifact")
        for rel in [*outputs, *public_gate_outputs]
    ]
    report = {
        "schema": SCHEMA,
        "status": "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED",
        "family": "quantize_linear",
        "analysis_owner_thread": "019fa2c0-572b-7f21-ac5a-96e773dde534",
        "delegation_source_thread": "019fd276-14c5-7800-94db-87ebfb9ce632",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "stage_count": inventory["stage_count"],
        "equivalence_class_count": inventory["equivalence_class_count"],
        "target_hw_op_types": ["QuantizeLinear"],
        "family_set": {
            "path": (output / "family_set.json").relative_to(root).as_posix(),
            "stage_ids": [stage["hw_op_id"] for stage in inventory["stages"]],
            "covered_exactly_once": True,
            "no_config_stage_count": 0,
        },
        "source_template_leaf_count": ledger["source_template"]["leaf_count"],
        "ledger_entry_count": ledger["ledger_entry_count"],
        "unresolved_count": ledger["unresolved_count"],
        "materialized_target_count": 0,
        "first_divergence": {
            "capability": "EXACT_BINARY32_DIVIDE_RNE",
            "blockers": [
                "B_QUANT_TAIL_EXACT_FP32_DIVISION",
                "B_QUANT_FP32_INPUT_PATH",
                "B_EXECPLAN_TYPED_TRANSPORT",
            ],
            "why_first": (
                "the target requires correctly-rounded binary32 x/scale before "
                "RNE/zp/saturation; no direct or bit-exact composed entry exists"
            ),
        },
        "node0074_boundary": {
            "reuse_class": "APPROVED_EQUIVALENT",
            "target_json_required_on_frozen_execution_path": False,
            "generic_divider_blocker_closed": False,
            "current_package_uses_original_uint8_storage": True,
        },
        "current_test_findings": {
            "suspected_config_issue_count": current_diff[
                "suspected_current_config_issue_count"
            ],
            "suspected_issue_is_in_current_package": False,
            "current_package_blocker_explained_by_quant_config_difference": False,
            "dynamic_only_count": len(
                current_diff["comparison_categories"]["dynamic_only"]
            ),
        },
        "rule_ids": [
            "CDA-NATIVE-REFERENCE-FIELD-APPLICABILITY-001",
            "CDA-NATIVE-HANDLER-CAPABILITY-MATRIX-001",
            "CDA-NATIVE-COMPOSITION-BOUNDARY-001",
            "CDA-CONFIG-SEMANTIC-OWNERSHIP-001",
            "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001",
            "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
            "CDA-REUSE-FIRST-DEFERRED-RETEST-001",
            "CDA-QUANT-TAIL-NUMERIC-ORDER-001",
            "CDA-QUANT-TAIL-ZP-AFTER-ROUND-001",
            "CDA-QUANT-TAIL-CAPABILITY-MATRIX-001",
        ],
        "rule_delta_proposal": {
            "required": False,
            "classification": "RULE_CONFIRMATION",
            "reason": (
                "The refreshed shared validator separates structural errors from "
                "completion blockers and reports contract_valid=true, "
                "blocked_valid=true, pass=false for this legitimate blocked family. "
                "The family auditor preserves 2/2 coverage while keeping family "
                "completion false."
            ),
        },
        "analysis_accounting": {
            "numeric_analysis_repeated": False,
            "w3_or_golden_repeated": False,
            "dequant_or_view_primitive_retested": False,
            "reuse_assets_consumed": True,
            "functional_rtl_modified": False,
            "server_files_inspected": False,
            "server_package_generated_or_modified": False,
            "server_upload_or_run": False,
        },
        "claim_boundary": (
            "Static source/consumer/config-provenance and public complete-JSON "
            "gate audit only. No target strict JSON, mapping, bitstream, execplan, "
            "SCA, E2, E3, E4, E5, or package."
        ),
        "package_release": "NONE",
        "source_receipts": receipts,
        "artifact_receipts": artifact_receipts,
    }
    _write_json(output / "report.json", report)
    return report


def _iter_target_json_files(complete_dir: Path) -> Iterable[Path]:
    for path in complete_dir.rglob("*.json"):
        if path.name != "manifest.json":
            yield path


def validate_artifacts(root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    output = output_dir or (root / ARTIFACT_REL)
    report = load_json(output / "report.json")
    inventory = load_json(output / "stage_inventory.json")
    ledger = load_json(output / "field_provenance_ledger.json")
    references = load_json(output / "reference_applicability.json")
    handler = load_json(output / "handler_capability.json")
    current_diff = load_json(output / "current_test_diff.json")
    manifest = load_json(output / "complete_json/manifest.json")
    errors: list[str] = []
    if inventory["stage_count"] != 2 or inventory["equivalence_class_count"] != 2:
        errors.append("stage/equivalence-class coverage is not 2/2")
    if ledger["source_template"]["leaf_count"] != 516:
        errors.append("source template leaf count is not 516")
    if ledger["ledger_entry_count"] != 1032:
        errors.append("ledger does not cover 516 leaves x 2 stages")
    keys = {(item["stage_id"], item["json_pointer"]) for item in ledger["records"]}
    if len(keys) != ledger["ledger_entry_count"]:
        errors.append("ledger contains duplicate stage/pointer entries")
    bad_origins = sorted(
        {item["origin"] for item in ledger["records"]} - ALLOWED_ORIGINS
    )
    if bad_origins:
        errors.append(f"disallowed origins: {bad_origins}")
    unresolved = sum(
        item["origin"] == "UNRESOLVED" for item in ledger["records"]
    )
    if unresolved != ledger["unresolved_count"] or unresolved == 0:
        errors.append("unresolved ledger count is inconsistent or unexpectedly zero")
    source = load_json(root / SOURCE_TEMPLATE_REL)
    source_leaves = dict(flatten_json(source))
    for item in ledger["records"]:
        pointer = item["json_pointer"]
        if pointer not in source_leaves:
            errors.append(f"ledger pointer missing from source: {pointer}")
            break
        if item["source"]["value"] != source_leaves[pointer]:
            errors.append(f"ledger source value mismatch: {pointer}")
            break
    if manifest["materialized_target_count"] != 0:
        errors.append("blocked run claims materialized target")
    leaked_targets = [str(path) for path in _iter_target_json_files(output / "complete_json")]
    if leaked_targets:
        errors.append(f"blocked run emitted target JSON: {leaked_targets}")
    if references["reuse_class"] != "STRUCTURE_OR_PRIMITIVE_ONLY":
        errors.append("reference reuse class is too strong")
    if handler["handler_class"] != "PLACEHOLDER" or handler["mapper_registered"]:
        errors.append("handler/mapper capability boundary changed")
    if handler["direct_binary32_division_opcode"] is not None:
        errors.append("report unexpectedly claims a division opcode")
    if current_diff["current_quantize_package_count"] != 0:
        errors.append("current package is mislabeled as a Quantize package")
    if current_diff["comparison_categories"]["new_candidate_defect"]:
        errors.append("candidate defects cannot exist without a candidate")
    if report["materialized_target_count"] != 0 or report["package_release"] != "NONE":
        errors.append("report violates blocked release boundary")
    for receipt in report["source_receipts"]:
        path = root / receipt["path"]
        if not path.is_file():
            errors.append(f"missing source receipt: {receipt['path']}")
            continue
        if receipt["gate"] == "mutable_provenance_only":
            continue
        if sha256_file(path) != receipt["sha256"]:
            errors.append(f"source receipt changed: {receipt['path']}")
    try:
        output.relative_to(root)
    except ValueError:
        if not errors:
            errors.append(
                "public-gate validation requires an artifact root inside the "
                "workspace"
            )
        raise QuantizeCompleteJsonError("; ".join(errors))
    from tools.audit_complete_operator_json_family_set import audit_family_set
    from tools.validate_complete_operator_json_candidate import (
        validate as validate_public_candidate,
    )

    public_candidate_reports = []
    for stage in inventory["stages"]:
        contract_path = (
            output
            / "public_gate"
            / stage["hw_op_id"]
            / "candidate_contract.json"
        )
        public_report = validate_public_candidate(
            workspace_root=root,
            contract_path=contract_path,
            authority_path=(
                root
                / "contracts/operator_config/operator_config_authority_v1.json"
            ),
            policy_path=root / PUBLIC_POLICY_REL,
            lowering_path=root / "contracts/resnet50_r5_lowering_bundle.json",
        )
        public_candidate_reports.append(public_report)
        if public_report.get("candidate_status") != "BLOCKED":
            errors.append(
                f"public candidate is not BLOCKED: {stage['hw_op_id']}"
            )
        if public_report.get("stage_count") != 1:
            errors.append(
                f"public candidate stage binding is not singular: "
                f"{stage['hw_op_id']}"
            )
        if public_report.get("candidate_leaf_count") != 516:
            errors.append(
                f"public candidate source projection leaf count changed: "
                f"{stage['hw_op_id']}"
            )
        if public_report.get("ledger_leaf_count") != 516:
            errors.append(
                f"public ledger is not leaf complete: {stage['hw_op_id']}"
            )
        if public_report.get("handler", {}).get("uncovered_count") != 516:
            errors.append(
                f"public handler dependency set is not fail closed: "
                f"{stage['hw_op_id']}"
            )
        if public_report.get("composition", {}).get("unresolved_count") != 1:
            errors.append(
                f"public composition blocker is not singular: "
                f"{stage['hw_op_id']}"
            )
        if public_report.get("errors") != []:
            errors.append(
                f"public validator behavior changed: {stage['hw_op_id']}: "
                f"{public_report.get('errors')}"
            )
        if public_report.get("contract_valid") is not True:
            errors.append(
                f"public BLOCKED contract is structurally invalid: "
                f"{stage['hw_op_id']}"
            )
        if public_report.get("blocked_valid") is not True:
            errors.append(
                f"public BLOCKED contract lacks completion blockers: "
                f"{stage['hw_op_id']}"
            )
        if not public_report.get("completion_blockers"):
            errors.append(
                f"public completion blocker set is empty: {stage['hw_op_id']}"
            )
        if public_report.get("pass") is not False:
            errors.append(
                f"public BLOCKED candidate unexpectedly passed: "
                f"{stage['hw_op_id']}"
            )
    family_audit = audit_family_set(
        workspace_root=root,
        manifest_path=output / "family_set.json",
        authority_path=(
            root / "contracts/operator_config/operator_config_authority_v1.json"
        ),
        policy_path=root / PUBLIC_POLICY_REL,
        lowering_path=root / "contracts/resnet50_r5_lowering_bundle.json",
    )
    if family_audit.get("expected_stage_count") != 2:
        errors.append("public family-set expected stage count is not two")
    if family_audit.get("covered_stage_count") != 2:
        errors.append("public family-set does not cover both stages")
    if family_audit.get("missing_stage_ids"):
        errors.append(
            f"public family-set has missing stages: "
            f"{family_audit['missing_stage_ids']}"
        )
    if family_audit.get("unexpected_stage_ids"):
        errors.append(
            f"public family-set has unexpected stages: "
            f"{family_audit['unexpected_stage_ids']}"
        )
    if family_audit.get("pass") is not False:
        errors.append("public family-set unexpectedly passed BLOCKED candidates")
    validation = {
        "schema": f"{SCHEMA}-validation",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "stage_count": inventory["stage_count"],
        "equivalence_class_count": inventory["equivalence_class_count"],
        "ledger_entry_count": ledger["ledger_entry_count"],
        "unresolved_count": ledger["unresolved_count"],
        "materialized_target_count": manifest["materialized_target_count"],
        "package_release": report["package_release"],
        "public_candidate_contract_count": len(public_candidate_reports),
        "public_candidate_validator_expected_fail_closed": all(
            item.get("contract_valid") is True
            and item.get("blocked_valid") is True
            and item.get("pass") is False
            for item in public_candidate_reports
        ),
        "public_family_set_expected_stage_count": family_audit.get(
            "expected_stage_count"
        ),
        "public_family_set_covered_stage_count": family_audit.get(
            "covered_stage_count"
        ),
        "public_family_set_complete": family_audit.get("pass"),
    }
    if errors:
        raise QuantizeCompleteJsonError("; ".join(errors))
    return validation
