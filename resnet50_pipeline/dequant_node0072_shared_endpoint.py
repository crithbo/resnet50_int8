from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from resnet50_pipeline.hashing import canonical_json_bytes, sha256_bytes, sha256_file


MANIFEST_RELATIVE = Path(
    "contracts/operator_config/resnet50_node0072_node0074_shared_endpoint_v1.json"
)
NODE0072_CONTRACT_RELATIVE = Path(
    "contracts/operator_config/"
    "node0072_dequant_config_only_correctness_baseline_v1.json"
)
NODE0072_REPORT_RELATIVE = Path(
    "artifacts/operator_config_validation/"
    "r5-dequant-node0072-config-only-e2-v1/local_e2_report.json"
)
DEQUANT_RULE_RELATIVE = Path(".agents/rules/DequantizeLinear算子配置规则.md")
COMMON_RULE_RELATIVE = Path(".agents/rules/算子配置规则.md")
ROUTING_INDEX_RELATIVE = Path(".agents/rules/生成前必读索引.md")
REUSE_POLICY_RELATIVE = Path(
    "contracts/operator_config/resnet50_reuse_first_integration_policy_v1.json"
)

EXPECTED_SOURCE_SHA256 = {
    NODE0072_CONTRACT_RELATIVE.as_posix():
        "cf5172db59a0a7c294e49445f63cd7c61919c3aa4640af180799d2dcef42c60f",
    NODE0072_REPORT_RELATIVE.as_posix():
        "50e30f52bcc95fb3f3e89b2690bc163c77b4de3d77474dd9fecb569ed5176a43",
    DEQUANT_RULE_RELATIVE.as_posix():
        "f8cf7d2a041426f2b3348f3d02b570e3e559fe1a77c643a8393e77a2583e15a1",
    COMMON_RULE_RELATIVE.as_posix():
        "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
    ROUTING_INDEX_RELATIVE.as_posix():
        "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
    REUSE_POLICY_RELATIVE.as_posix():
        "c8886c946a15e281e2b9fc40c3e37523cc00d3aab330131572887f3d64de6960",
}

SLICE_COUNT = 28
WORDS_PER_SLICE = 1184
BYTES_PER_SLICE = 4736
LOGICAL_BYTES = 131072
PHYSICAL_BYTES = 132608
PADDING_BYTES = 1536
SLICE_ADDRESS_STRIDE = 0x02000000
SLICE0_D_BASE = 0x000004A0
STORAGE_ID = (
    "r5:activation:node-0072:D:tensor-50c285690f899b1b:"
    "slice-sharded-28x4736-v1"
)


class DequantSharedEndpointError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DequantSharedEndpointError(f"{path} is not a JSON object")
    return value


def _section_content_sha256(section: dict[str, Any]) -> str:
    body = deepcopy(section)
    body.pop("owner_section_content_sha256", None)
    return sha256_bytes(canonical_json_bytes(body))


def _source_map(section: dict[str, Any]) -> dict[str, str]:
    sources = section.get("immutable_sources")
    if not isinstance(sources, list):
        raise DequantSharedEndpointError("Dequant immutable_sources is not a list")
    result: dict[str, str] = {}
    for item in sources:
        if not isinstance(item, dict):
            raise DequantSharedEndpointError("Dequant source entry is not an object")
        path = str(item.get("path"))
        if path in result:
            raise DequantSharedEndpointError(f"duplicate Dequant source path: {path}")
        result[path] = str(item.get("sha256"))
    return result


def _expected_valid_bytes(slice_id: int) -> int:
    remaining = LOGICAL_BYTES - slice_id * BYTES_PER_SLICE
    return max(0, min(BYTES_PER_SLICE, remaining))


def validate_manifest(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = _read_json(root / MANIFEST_RELATIVE)
    if manifest.get("schema") != "resnet50-shared-endpoint-owner-manifest-v1":
        raise DequantSharedEndpointError("shared endpoint schema differs")
    if manifest.get("status") != "PARTIAL_DEQUANT_PRODUCER_SECTION_READY":
        raise DequantSharedEndpointError("shared endpoint status differs")
    if manifest.get("chain") != [
        "node-0072:D",
        "node-0073:metadata-alias",
        "node-0074:A",
    ]:
        raise DequantSharedEndpointError("shared endpoint chain differs")

    sections = manifest.get("owner_sections")
    if not isinstance(sections, dict) or set(sections) != {"DequantizeLinear"}:
        raise DequantSharedEndpointError(
            "this asset must contain only the Dequant-owned section"
        )
    section = sections["DequantizeLinear"]
    if section.get("owner_family") != "DequantizeLinear":
        raise DequantSharedEndpointError("Dequant owner family differs")
    if section.get("owner_node") != "node-0072":
        raise DequantSharedEndpointError("Dequant owner node differs")
    if section.get("reuse_status") != "REUSE_ACCEPTED_FOR_INTEGRATION":
        raise DequantSharedEndpointError("Dequant reuse status differs")
    if section.get("reuse_class") != "EXACT_FULL_OPERATOR":
        raise DequantSharedEndpointError("Dequant reuse class differs")
    if section.get("numeric_analysis_repeated") is not False:
        raise DequantSharedEndpointError("manifest must not repeat numeric analysis")
    if section.get("operator_e2_retested") is not False:
        raise DequantSharedEndpointError("manifest must not repeat operator E2")

    source_map = _source_map(section)
    if source_map != EXPECTED_SOURCE_SHA256:
        raise DequantSharedEndpointError("Dequant immutable source set differs")
    for relative, expected_sha in EXPECTED_SOURCE_SHA256.items():
        actual = sha256_file(root / relative)
        if actual != expected_sha:
            raise DequantSharedEndpointError(
                f"immutable Dequant source drifted: {relative}"
            )

    expected_section_sha = _section_content_sha256(section)
    if section.get("owner_section_content_sha256") != expected_section_sha:
        raise DequantSharedEndpointError("Dequant owner section self-hash differs")

    storage = section.get("storage_identity", {})
    if (
        storage.get("storage_id") != STORAGE_ID
        or storage.get("allocation_owner") != "r5:hwop-0072-00:D"
        or storage.get("tensor_id") != "tensor-50c285690f899b1b"
        or storage.get("dtype") != "float32"
        or storage.get("logical_shape") != [16, 2048, 1, 1]
        or storage.get("logical_byte_strides") != [8192, 4, 4, 4]
        or storage.get("logical_element_count") != 32768
        or storage.get("logical_valid_byte_span") != LOGICAL_BYTES
        or storage.get("byte_offset_within_allocation") != 0
        or storage.get("physical_address_space") != "NDP_PER_SLICE_DDR"
    ):
        raise DequantSharedEndpointError("Dequant storage identity differs")

    base = section.get("base_and_offset", {})
    if (
        base.get("slice_count") != SLICE_COUNT
        or base.get("slice0_base_addr") != "0x000004a0"
        or base.get("slice_address_stride_bytes") != SLICE_ADDRESS_STRIDE
        or base.get("base_formula")
        != "D_base(slice)=0x000004a0+(slice_id<<25)"
        or base.get("consumer_required_view_byte_offset") != 0
    ):
        raise DequantSharedEndpointError("Dequant base/offset contract differs")

    coverage = section.get("coverage", {})
    records = coverage.get("slice_records")
    if not isinstance(records, list) or len(records) != SLICE_COUNT:
        raise DequantSharedEndpointError("Dequant slice coverage count differs")
    valid_total = 0
    padding_total = 0
    for slice_id, record in enumerate(records):
        expected_base = SLICE0_D_BASE + slice_id * SLICE_ADDRESS_STRIDE
        expected_valid = _expected_valid_bytes(slice_id)
        expected_padding = BYTES_PER_SLICE - expected_valid
        expected = {
            "slice_id": slice_id,
            "physical_d_base_addr": f"0x{expected_base:08x}",
            "allocation_byte_offset": 0,
            "physical_written_bytes": BYTES_PER_SLICE,
            "valid_logical_byte_offset": slice_id * BYTES_PER_SLICE,
            "valid_logical_bytes": expected_valid,
            "physical_padding_bytes": expected_padding,
            "final_written_byte_coverage_complete": True,
            "final_written_byte_coverage_unique": True,
        }
        if record != expected:
            raise DequantSharedEndpointError(
                f"Dequant slice coverage differs at slice {slice_id}"
            )
        valid_total += expected_valid
        padding_total += expected_padding
    if (
        coverage.get("physical_written_bytes") != PHYSICAL_BYTES
        or coverage.get("logical_valid_bytes") != LOGICAL_BYTES
        or coverage.get("physical_padding_bytes") != PADDING_BYTES
        or valid_total != LOGICAL_BYTES
        or padding_total != PADDING_BYTES
        or coverage.get("logical_inverse_complete") is not True
        or coverage.get("logical_inverse_unique") is not True
    ):
        raise DequantSharedEndpointError("Dequant aggregate coverage differs")

    accepted = section.get("final_accepted_write_completion", {})
    if accepted != {
        "evidence_scope": "FROZEN_NODE0072_LOCAL_E2_REUSED_NOT_RERUN",
        "static_validator_completion_path_accepted": True,
        "execplan_start_and_all_slice_d_address_writes_accepted": True,
        "config_bound_simulator_all_physical_d_writes_complete": True,
        "dynamic_hardware_final_write_accepted": False,
        "integrated_node0072_to_node0073_completion_accepted": False,
    }:
        raise DequantSharedEndpointError(
            "Dequant final accepted write/completion evidence differs"
        )

    lifetime = section.get("visibility_and_lifetime", {})
    if (
        lifetime.get("producer_visibility_event")
        != "node0072 final D write accepted AND node0072 completion accepted"
        or lifetime.get("required_release_event")
        != (
            "node0074 final A input-data accepted AND no pending/replayed read; "
            "fallback=node0074 completion accepted"
        )
        or lifetime.get("shared_multi_operator_barrier_materialized") is not False
        or lifetime.get("integrated_visibility_lifetime_status")
        != "DEFERRED_TO_INTEGRATION"
    ):
        raise DequantSharedEndpointError("Dequant visibility/lifetime differs")

    consumer = section.get("consumer_match_requirements", {})
    if (
        consumer.get("required_storage_id") != STORAGE_ID
        or consumer.get("required_view_byte_offset") != 0
        or consumer.get("required_valid_read_bytes") != LOGICAL_BYTES
        or consumer.get("flatten_input_strides") != [8192, 4, 4, 4]
        or consumer.get("flatten_output_strides") != [8192, 4]
        or consumer.get("flatten_section_present") is not False
        or consumer.get("quantize_section_present") is not False
    ):
        raise DequantSharedEndpointError("Dequant consumer requirements differ")

    claims = section.get("claim_boundary", {})
    if (
        claims.get("dequant_local_e2_preserved") is not True
        or claims.get("integrated_endpoint_closed") is not False
        or claims.get("counts_as_new_e2") is not False
        or claims.get("counts_as_e4_or_e5") is not False
        or claims.get("counts_as_formal_three_party_node") is not False
    ):
        raise DequantSharedEndpointError("Dequant claim boundary differs")

    if manifest.get("required_missing_owner_sections") != [
        "Flatten_View",
        "QuantizeLinear",
    ]:
        raise DequantSharedEndpointError("missing owner section list differs")
    if manifest.get("integrated_endpoint_closed") is not False:
        raise DequantSharedEndpointError("integrated endpoint must remain open")
    if manifest.get("server_package_generated") is not False:
        raise DequantSharedEndpointError("shared endpoint must not generate a package")

    return {
        "schema": "dequant-node0072-shared-endpoint-validation-v1",
        "valid": True,
        "manifest_path": MANIFEST_RELATIVE.as_posix(),
        "manifest_sha256": sha256_file(root / MANIFEST_RELATIVE),
        "dequant_owner_section_sha256": expected_section_sha,
        "immutable_source_count": len(source_map),
        "slice_count": SLICE_COUNT,
        "logical_valid_bytes": valid_total,
        "physical_written_bytes": PHYSICAL_BYTES,
        "physical_padding_bytes": padding_total,
        "same_storage_id_frozen": True,
        "base_offset_frozen": True,
        "final_write_completion_reused": True,
        "integrated_visibility_lifetime_status": "DEFERRED_TO_INTEGRATION",
        "numeric_analysis_repeated": False,
        "operator_e2_retested": False,
        "integrated_endpoint_closed": False,
    }


__all__ = [
    "DequantSharedEndpointError",
    "MANIFEST_RELATIVE",
    "STORAGE_ID",
    "validate_manifest",
]
