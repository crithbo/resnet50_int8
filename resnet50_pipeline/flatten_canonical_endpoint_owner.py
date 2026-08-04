from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from resnet50_pipeline.hashing import canonical_json_bytes, sha256_bytes, sha256_file


CANONICAL_RELATIVE = Path(
    "contracts/operator_config/resnet50_node0072_node0074_shared_endpoint_v1.json"
)
PROJECTION_RELATIVE = Path(
    "contracts/operator_config/"
    "node0072_node0073_node0074_shared_endpoint_manifest_v1.json"
)
VIEW_METADATA_RELATIVE = Path("configs/view/node0073_zero_copy_view_v1.json")
VIEW_CONTRACT_RELATIVE = Path(
    "contracts/operator_config/flatten_node0073_physical_view_v1.json"
)
VIEW_REPORT_RELATIVE = Path(
    "artifacts/operator_config_validation/"
    "r5-flatten-node0073-view-v1/validation_report.json"
)
VIEW_RULE_RELATIVE = Path(".agents/rules/Flatten_View算子配置规则.md")
COMMON_RULE_RELATIVE = Path(".agents/rules/算子配置规则.md")
ROUTING_INDEX_RELATIVE = Path(".agents/rules/生成前必读索引.md")
PLAN_RELATIVE = Path(".agents/plan.md")

DEQUANT_SECTION_SHA256 = (
    "e372f7b0fa434845a8199830c3c46a9467fc71d5687fa103750a86408191b371"
)
QUANTIZE_SECTION_SHA256 = (
    "08b2e7fdc5a7e1b642b8dab45bc157a465342aceffd8d5ff331e52d8749c36ac"
)
STORAGE_ID = (
    "r5:activation:node-0072:D:tensor-50c285690f899b1b:"
    "slice-sharded-28x4736-v1"
)
PLAN_SHA256 = "53bd530998d6a3a57d5ac63302067d66ca46bef3e0e7b4adcba3bb1fbdcf7c35"
READY_STATUS = "ALL_OWNER_SECTIONS_PRESENT_ENDPOINT_BINDING_BLOCKED"
LOGICAL_BYTES = 131072

EXPECTED_SOURCE_SHA256 = {
    PROJECTION_RELATIVE.as_posix():
        "3d9589db8505502ad575c68b2eeab65c62a645842b78b29ca35ab0547886fbb9",
    VIEW_METADATA_RELATIVE.as_posix():
        "a63655c339ab68b7edad6d7c9a30776d369749dda80d3b5661152ec07582bddc",
    VIEW_CONTRACT_RELATIVE.as_posix():
        "067351563c40fb1b95e63f3b327e9758f19c49c72d3c48b348d223426ada9851",
    VIEW_REPORT_RELATIVE.as_posix():
        "62b92ffad44bc89ea6e6a97c6f77110170e208ccefde0f63ffed1cabea61b13c",
    VIEW_RULE_RELATIVE.as_posix():
        "28ba3a92fecbb83149d494867429c34aa3124040a5c59fe99c4b9481feb3b7ee",
    COMMON_RULE_RELATIVE.as_posix():
        "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
    ROUTING_INDEX_RELATIVE.as_posix():
        "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
}


class FlattenCanonicalOwnerError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FlattenCanonicalOwnerError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise FlattenCanonicalOwnerError(f"{path} is not a JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _owner_section_sha256(section: Mapping[str, Any]) -> str:
    body = deepcopy(dict(section))
    body.pop("owner_section_content_sha256", None)
    return sha256_bytes(canonical_json_bytes(body))


def _assert_foreign_owners_immutable(manifest: Mapping[str, Any]) -> None:
    sections = manifest.get("owner_sections")
    if not isinstance(sections, Mapping):
        raise FlattenCanonicalOwnerError("canonical owner_sections is not an object")
    dequant = sections.get("DequantizeLinear")
    if not isinstance(dequant, Mapping):
        raise FlattenCanonicalOwnerError("canonical DequantizeLinear section is missing")
    stored = dequant.get("owner_section_content_sha256")
    calculated = _owner_section_sha256(dequant)
    if stored != DEQUANT_SECTION_SHA256 or calculated != DEQUANT_SECTION_SHA256:
        raise FlattenCanonicalOwnerError(
            f"Dequant section identity differs: stored={stored}, calculated={calculated}"
        )
    quantize = sections.get("QuantizeLinear")
    if not isinstance(quantize, Mapping):
        raise FlattenCanonicalOwnerError("canonical QuantizeLinear section is missing")
    stored_quantize = quantize.get("owner_section_content_sha256")
    calculated_quantize = _owner_section_sha256(quantize)
    if (
        stored_quantize != QUANTIZE_SECTION_SHA256
        or calculated_quantize != QUANTIZE_SECTION_SHA256
    ):
        raise FlattenCanonicalOwnerError(
            "Quantize section identity differs: "
            f"stored={stored_quantize}, calculated={calculated_quantize}"
        )
    endpoint = quantize.get("consumer_owned_endpoint_fields", {})
    if set(endpoint) != {
        "final_storage_identity",
        "final_producer_base",
        "final_view_offset",
        "final_consumer_base",
        "final_read_coverage",
        "final_accepted_lifetime",
    } or any(value is not None for value in endpoint.values()):
        raise FlattenCanonicalOwnerError(
            "Quantize consumer final endpoint fields must all remain null"
        )


def _assert_frozen_sources(root: Path) -> None:
    for relative, expected in EXPECTED_SOURCE_SHA256.items():
        actual = sha256_file(root / relative)
        if actual != expected:
            raise FlattenCanonicalOwnerError(
                f"frozen Flatten/View source differs: {relative} ({actual})"
            )
    projection = _read_json(root / PROJECTION_RELATIVE)
    if (
        projection.get("status") != "ENDPOINT_BINDING_PENDING"
        or projection.get("numeric_analysis_repeated") is not False
        or projection.get("reused_assets_consumed") is not True
        or projection.get("integrated_target_local_e2") is not False
    ):
        raise FlattenCanonicalOwnerError("read-only View projection boundary differs")
    view = _read_json(root / VIEW_METADATA_RELATIVE)
    logical = view.get("logical_tensors", {})
    materialization = view.get("materialization", {})
    replay = view.get("input_replay_policy", {})
    if (
        logical.get("element_count") != 32768
        or logical.get("byte_count") != LOGICAL_BYTES
        or logical.get("input", {}).get("byte_strides") != [8192, 4, 4, 4]
        or logical.get("output", {}).get("byte_strides") != [8192, 4]
        or materialization.get("kind") != "execplan_metadata_zero_copy_alias"
        or materialization.get("emit_arithmetic_json") is not False
        or materialization.get("hardware_instruction_count") != 0
        or materialization.get("hardware_memory_request_count") != 0
        or replay.get("copy_enabled") is not False
        or replay.get("input_or_constant_replay_enabled") is not False
    ):
        raise FlattenCanonicalOwnerError("frozen View metadata semantics differ")


def build_flatten_owner_section(root: Path) -> dict[str, Any]:
    _assert_frozen_sources(root)
    section: dict[str, Any] = {
        "owner_family": "Flatten_View",
        "owner_node": "node-0073",
        "owner_hwop": "r5:hwop-0073-00",
        "owner_role": "metadata-only physical alias",
        "owner_section_content_sha256": "",
        "reuse_status": "REUSE_ACCEPTED_FOR_INTEGRATION",
        "reuse_class": "EXACT_METADATA_ONLY_VIEW",
        "numeric_analysis_repeated": False,
        "element_address_mapping_retested": False,
        "consumed_reuse_assets": True,
        "immutable_sources": [
            {
                "path": relative,
                "sha256": sha256,
                "role": (
                    "read-only requirement/View projection"
                    if relative == PROJECTION_RELATIVE.as_posix()
                    else "frozen Flatten/View source receipt"
                ),
            }
            for relative, sha256 in EXPECTED_SOURCE_SHA256.items()
        ],
        "rule_ids": [
            "CDA-REUSE-FIRST-DEFERRED-RETEST-001",
            "CDA-VIEW-METADATA-ONLY-001",
            "CDA-VIEW-PHYSICAL-IDENTITY-001",
            "CDA-VIEW-ENDPOINT-COVERAGE-001",
            "CDA-VIEW-ACCEPTED-LIFETIME-001",
            "CDA-VIEW-INTEGRATED-CLAIM-BOUNDARY-001",
        ],
        "metadata_alias": {
            "input_tensor_id": "tensor-50c285690f899b1b",
            "output_tensor_id": "tensor-9b1363d3baf474c8",
            "dtype": "float32",
            "input_shape": [16, 2048, 1, 1],
            "output_shape": [16, 2048],
            "input_byte_strides": [8192, 4, 4, 4],
            "output_byte_strides": [8192, 4],
            "linear_order": "C",
            "logical_element_count": 32768,
            "logical_byte_span": LOGICAL_BYTES,
            "required_storage_id": STORAGE_ID,
            "producer_byte_offset": 0,
            "view_byte_offset_delta": 0,
            "consumer_required_byte_offset": 0,
            "address_equation": (
                "node0073_output_addr(n,c)="
                "node0072_D_addr(n,c,0,0)=D_base(slice)+local_byte"
            ),
            "mapping_proof_reused_not_recomputed": True,
        },
        "materialization": {
            "kind": "execplan_metadata_zero_copy_alias",
            "arithmetic_json_generated": False,
            "mapping_or_bitstream_generated": False,
            "hardware_instruction_count": 0,
            "hardware_memory_request_count": 0,
            "copy_enabled": False,
            "replay_enabled": False,
            "host_precomputed_internal_or_final_tensor_enabled": False,
        },
        "allocation_ownership": {
            "allocation_owner": "r5:hwop-0072-00:D",
            "allocation_owner_storage_id": STORAGE_ID,
            "view_owns_allocation": False,
            "view_may_allocate": False,
            "view_may_relocate": False,
            "view_may_release": False,
            "consumer_role": "read-only borrower",
        },
        "endpoint_requirements": {
            "same_storage_id_required": True,
            "identical_per_slice_base_required": True,
            "base_plus_offset_delta_bytes": 0,
            "producer_final_valid_write_bytes_required": LOGICAL_BYTES,
            "consumer_final_valid_read_bytes_required": LOGICAL_BYTES,
            "producer_occurrence_address_proof_reused": True,
            "consumer_occurrence_address_proof_present": False,
            "allocator_plan_present": False,
            "shared_multi_operator_addressed_execplan_present": False,
            "quantize_owner_section_present": True,
        },
        "accepted_lifetime_requirement": {
            "producer_visibility_event": (
                "node0072 final D write accepted AND node0072 completion accepted"
            ),
            "consumer_first_legal_read": "after producer_visibility_event",
            "release_precondition": (
                "node0074 final A input-data accepted AND no pending/replayed read"
            ),
            "conservative_release_fallback": "node0074 completion accepted",
            "copy_or_replay_fallback_allowed": False,
            "integrated_lifetime_certificate_present": False,
        },
        "claim_boundary": {
            "view_projection_ready": True,
            "producer_plus_view_ready": True,
            "quantize_section_present": True,
            "quantize_exact_division_pending": True,
            "integrated_endpoint_closed": False,
            "integrated_target_local_e2": False,
            "claim_label": None,
            "counts_as_new_e2": False,
            "counts_as_e4_or_e5": False,
        },
        "package_release": {
            "state": "NONE",
            "server_package_generated": False,
            "server_files_inspected": False,
            "server_upload_or_run": False,
            "server_lease": False,
        },
    }
    section["owner_section_content_sha256"] = _owner_section_sha256(section)
    return section


def update_canonical_manifest(root: Path) -> dict[str, Any]:
    root = root.resolve()
    canonical_path = root / CANONICAL_RELATIVE
    manifest = _read_json(canonical_path)
    if manifest.get("schema") != "resnet50-shared-endpoint-owner-manifest-v1":
        raise FlattenCanonicalOwnerError("canonical schema differs")
    _assert_foreign_owners_immutable(manifest)
    _assert_frozen_sources(root)

    sections = manifest["owner_sections"]
    existing = sections.get("Flatten_View")
    expected = build_flatten_owner_section(root)
    if existing is not None and existing != expected:
        raise FlattenCanonicalOwnerError("existing Flatten_View owner section differs")
    sections["Flatten_View"] = expected
    manifest["status"] = READY_STATUS
    manifest["control_plane_receipt"] = {
        "path": PLAN_RELATIVE.as_posix(),
        "sha256": PLAN_SHA256,
        "sections_read": ["0", "0.1"],
        "mutable_provenance_only": True,
    }
    manifest["required_missing_owner_sections"] = []
    manifest["cross_owner_gates"] = {
        "owner_sections_present": "DEQUANT_FLATTEN_QUANTIZE_PRESENT",
        "producer_view_projection": "READY",
        "quantize_exact_division": "OPEN",
        "same_storage_match": "BLOCKED_BY_NULL_QUANTIZE_ENDPOINT",
        "base_plus_offset_match": "BLOCKED_BY_NULL_QUANTIZE_ENDPOINT",
        "producer_write_vs_consumer_read_coverage": (
            "PRODUCER_READY_CONSUMER_PENDING_EXACT_DIVISION"
        ),
        "accepted_visibility_lifetime": (
            "PENDING_CONSUMER_AND_SHARED_MULTI_OPERATOR_ALLOCATOR_EXECPLAN"
        ),
    }
    manifest["integrated_endpoint_closed"] = False
    manifest["server_package_generated"] = False
    manifest["claim_boundary"] = (
        "DequantizeLinear, Flatten/View and QuantizeLinear owner sections are "
        "present and immutable. QuantizeLinear exact division leaves all six "
        "consumer endpoint fields null; consumer occurrence/address coverage and "
        "the shared allocator/execplan/lifetime certificate remain pending. No "
        "integrated E2, E4/E5 or package claim is enabled."
    )
    _assert_foreign_owners_immutable(manifest)
    _write_json(canonical_path, manifest)
    report = validate_canonical_manifest(root)
    return report


def validate_canonical_manifest(root: Path) -> dict[str, Any]:
    root = root.resolve()
    _assert_frozen_sources(root)
    manifest = _read_json(root / CANONICAL_RELATIVE)
    _assert_foreign_owners_immutable(manifest)
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(
        manifest.get("schema") == "resnet50-shared-endpoint-owner-manifest-v1",
        "canonical schema differs",
    )
    require(manifest.get("status") == READY_STATUS, "canonical ready status differs")
    sections = manifest.get("owner_sections", {})
    require(
        set(sections) == {"DequantizeLinear", "Flatten_View", "QuantizeLinear"},
        "all three owner sections must be present",
    )
    view = sections.get("Flatten_View", {})
    require(
        view.get("owner_section_content_sha256") == _owner_section_sha256(view),
        "Flatten_View owner section self-hash differs",
    )
    require(
        view.get("numeric_analysis_repeated") is False,
        "numeric analysis must not be repeated",
    )
    require(
        view.get("element_address_mapping_retested") is False,
        "32768-element mapping must not be retested",
    )
    alias = view.get("metadata_alias", {})
    require(alias.get("required_storage_id") == STORAGE_ID, "storage projection differs")
    require(alias.get("input_byte_strides") == [8192, 4, 4, 4], "input strides differ")
    require(alias.get("output_byte_strides") == [8192, 4], "output strides differ")
    require(alias.get("view_byte_offset_delta") == 0, "View offset must be zero")
    require(alias.get("logical_byte_span") == LOGICAL_BYTES, "View byte span differs")
    materialization = view.get("materialization", {})
    require(materialization.get("copy_enabled") is False, "copy must remain disabled")
    require(materialization.get("replay_enabled") is False, "replay must remain disabled")
    require(
        materialization.get("hardware_memory_request_count") == 0,
        "View request count must remain zero",
    )
    allocation = view.get("allocation_ownership", {})
    require(
        allocation.get("allocation_owner") == "r5:hwop-0072-00:D",
        "allocation owner differs",
    )
    require(allocation.get("view_may_allocate") is False, "View may not allocate")
    require(allocation.get("view_may_relocate") is False, "View may not relocate")
    require(allocation.get("view_may_release") is False, "View may not release")
    endpoint = view.get("endpoint_requirements", {})
    require(
        endpoint.get("consumer_occurrence_address_proof_present") is False,
        "consumer occurrence proof may not be fabricated",
    )
    require(
        endpoint.get("quantize_owner_section_present") is True,
        "Quantize owner section presence differs",
    )
    lifetime = view.get("accepted_lifetime_requirement", {})
    require(
        lifetime.get("integrated_lifetime_certificate_present") is False,
        "integrated lifetime may not be promoted",
    )
    require(
        lifetime.get("copy_or_replay_fallback_allowed") is False,
        "copy/replay lifetime fallback is forbidden",
    )
    claim = view.get("claim_boundary", {})
    require(claim.get("producer_plus_view_ready") is True, "producer+view gate differs")
    require(
        claim.get("quantize_section_present") is True,
        "Quantize owner section presence differs",
    )
    require(
        claim.get("quantize_exact_division_pending") is True,
        "Quantize exact division must remain pending",
    )
    require(
        claim.get("integrated_target_local_e2") is False,
        "integrated target local E2 must remain false",
    )
    require(claim.get("claim_label") is None, "claim label must remain null")
    require(
        manifest.get("required_missing_owner_sections") == [],
        "missing owner section list differs",
    )
    gates = manifest.get("cross_owner_gates", {})
    require(
        gates.get("owner_sections_present")
        == "DEQUANT_FLATTEN_QUANTIZE_PRESENT",
        "three-owner presence gate differs",
    )
    require(gates.get("producer_view_projection") == "READY", "View gate differs")
    require(
        gates.get("same_storage_match") == "BLOCKED_BY_NULL_QUANTIZE_ENDPOINT",
        "same-storage gate overclaimed",
    )
    require(
        gates.get("base_plus_offset_match")
        == "BLOCKED_BY_NULL_QUANTIZE_ENDPOINT",
        "base+offset gate overclaimed",
    )
    require(
        gates.get("producer_write_vs_consumer_read_coverage")
        == "PRODUCER_READY_CONSUMER_PENDING_EXACT_DIVISION",
        "coverage gate overclaimed",
    )
    require(
        gates.get("quantize_exact_division") == "OPEN",
        "exact-division gate must remain open",
    )
    require(
        manifest.get("integrated_endpoint_closed") is False,
        "integrated endpoint must remain open",
    )
    require(
        manifest.get("server_package_generated") is False,
        "server package must not be generated",
    )
    if errors:
        raise FlattenCanonicalOwnerError("; ".join(errors))

    return {
        "schema": "flatten-canonical-endpoint-owner-validation-v1",
        "valid": True,
        "canonical_path": CANONICAL_RELATIVE.as_posix(),
        "canonical_sha256": sha256_file(root / CANONICAL_RELATIVE),
        "dequant_owner_section_sha256": DEQUANT_SECTION_SHA256,
        "dequant_owner_section_unchanged": True,
        "quantize_owner_section_sha256": QUANTIZE_SECTION_SHA256,
        "quantize_owner_section_unchanged": True,
        "flatten_view_owner_section_sha256": view["owner_section_content_sha256"],
        "owner_sections_present": [
            "DequantizeLinear",
            "Flatten_View",
            "QuantizeLinear",
        ],
        "producer_view_projection_ready": True,
        "quantize_exact_division": "OPEN",
        "consumer_final_endpoint_null_field_count": 6,
        "required_missing_owner_sections": [],
        "cross_owner_gate": "THREE_SECTIONS_PRESENT_ENDPOINT_BINDING_BLOCKED",
        "numeric_analysis_repeated": False,
        "element_address_mapping_retested": False,
        "reused_assets_consumed": True,
        "integrated_endpoint_closed": False,
        "integrated_target_local_e2": False,
        "server_package_generated": False,
    }


def write_validation_receipt(root: Path, report: Mapping[str, Any]) -> Path:
    path = (
        root
        / "artifacts/operator_config_validation/"
        "r5-flatten-canonical-endpoint-owner-v1/validation_report.json"
    )
    _write_json(path, report)
    return path


__all__ = [
    "CANONICAL_RELATIVE",
    "DEQUANT_SECTION_SHA256",
    "QUANTIZE_SECTION_SHA256",
    "FlattenCanonicalOwnerError",
    "build_flatten_owner_section",
    "update_canonical_manifest",
    "validate_canonical_manifest",
    "write_validation_receipt",
]
