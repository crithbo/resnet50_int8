from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "resnet50-flatten-shared-endpoint-manifest-v1"
REPORT_SCHEMA = "resnet50-flatten-shared-endpoint-validation-v1"
STATUS = "ENDPOINT_BINDING_PENDING"
BYTE_SPAN = 131072
INPUT_STRIDES = [8192, 4, 4, 4]
OUTPUT_STRIDES = [8192, 4]
CONSUMER_FINAL_FIELDS = (
    "final_storage_identity",
    "final_producer_base",
    "final_view_offset",
    "final_consumer_base",
    "final_read_coverage",
    "final_accepted_lifetime",
)

SOURCE_IDENTITIES = {
    "producer_contract": {
        "path": "contracts/operator_config/node0072_dequant_config_only_correctness_baseline_v1.json",
        "sha256": "cf5172db59a0a7c294e49445f63cd7c61919c3aa4640af180799d2dcef42c60f",
    },
    "producer_local_e2_report": {
        "path": "artifacts/operator_config_validation/r5-dequant-node0072-config-only-e2-v1/local_e2_report.json",
        "sha256": "50e30f52bcc95fb3f3e89b2690bc163c77b4de3d77474dd9fecb569ed5176a43",
    },
    "view_metadata": {
        "path": "configs/view/node0073_zero_copy_view_v1.json",
        "sha256": "a63655c339ab68b7edad6d7c9a30776d369749dda80d3b5661152ec07582bddc",
    },
    "view_contract": {
        "path": "contracts/operator_config/flatten_node0073_physical_view_v1.json",
        "sha256": "067351563c40fb1b95e63f3b327e9758f19c49c72d3c48b348d223426ada9851",
    },
    "consumer_rounding_discriminator": {
        "path": "contracts/operator_config/exact_uint8_quant_tail_rounding_discriminator_v1.json",
        "sha256": "82ab3276a8ae9ee35aeda366756dd4525dfac77c6e3ed40cf395d7a011f8a477",
    },
}

RULE_RECEIPTS = {
    ".agents/rules/生成前必读索引.md": (
        "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f"
    ),
    ".agents/rules/算子配置规则.md": (
        "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171"
    ),
    ".agents/rules/Flatten_View算子配置规则.md": (
        "28ba3a92fecbb83149d494867429c34aa3124040a5c59fe99c4b9481feb3b7ee"
    ),
}

PLAN_RECEIPT = {
    "path": ".agents/plan.md",
    "sha256": "f9a3ce73baa73346c144f14bf005262f0b0caaf66d981da157a5a11c0a703183",
    "mutable_provenance": True,
    "semantic_gate": False,
}


class FlattenSharedEndpointError(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _content_sha256(value: Mapping[str, Any], field: str) -> str:
    projected = dict(value)
    projected.pop(field, None)
    encoded = json.dumps(
        projected, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FlattenSharedEndpointError(f"cannot load JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise FlattenSharedEndpointError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _load_frozen_sources(root: Path) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for name, identity in SOURCE_IDENTITIES.items():
        path = root / identity["path"]
        actual = _sha256_file(path)
        if actual != identity["sha256"]:
            raise FlattenSharedEndpointError(
                f"frozen source identity differs for {name}: {actual}"
            )
        loaded[name] = _load_object(path)
    for path_text, expected in RULE_RECEIPTS.items():
        actual = _sha256_file(root / path_text)
        if actual != expected:
            raise FlattenSharedEndpointError(
                f"rule receipt differs for {path_text}: {actual}"
            )
    if _sha256_file(root / PLAN_RECEIPT["path"]) != PLAN_RECEIPT["sha256"]:
        raise FlattenSharedEndpointError("mutable plan provenance receipt differs")
    return loaded


def _validate_source_semantics(sources: Mapping[str, Mapping[str, Any]]) -> None:
    producer = sources["producer_contract"]
    handoff = producer.get("node0073_integrated_binding_handoff", {})
    logical = handoff.get("logical_contract", {})
    physical = handoff.get("physical_contract", {})
    coverage = handoff.get("final_written_byte_coverage", {})
    completion = handoff.get("final_write_completion", {})
    if producer.get("status") != "CONFIG_ONLY_CORRECTNESS_BASELINE":
        raise FlattenSharedEndpointError("node0072 standalone status differs")
    if (
        logical.get("shape") != [16, 2048, 1, 1]
        or logical.get("byte_strides") != INPUT_STRIDES
        or logical.get("logical_span_bytes") != BYTE_SPAN
        or physical.get("valid_logical_bytes") != BYTE_SPAN
    ):
        raise FlattenSharedEndpointError("node0072 logical handoff differs")
    slices = physical.get("slice_bindings")
    if not isinstance(slices, list) or len(slices) != 28:
        raise FlattenSharedEndpointError("node0072 must expose 28 standalone slices")
    if any(
        item.get("written_byte_coverage", {}).get("complete") is not True
        for item in slices
    ):
        raise FlattenSharedEndpointError("node0072 standalone slice coverage incomplete")
    if (
        coverage.get("logical_valid_bytes") != BYTE_SPAN
        or coverage.get("logical_inverse_complete") is not True
        or completion.get("config_bound_simulator_all_physical_d_writes_complete")
        is not True
        or completion.get("dynamic_hardware_final_write_accepted") is not False
        or completion.get("integrated_node0072_to_node0073_lifetime_accepted")
        is not False
        or handoff.get("integrated_binding_status") != "UNRESOLVED"
    ):
        raise FlattenSharedEndpointError("node0072 standalone/integrated boundary differs")

    view = sources["view_metadata"]
    view_contract = sources["view_contract"]
    tensors = view.get("logical_tensors", {})
    materialization = view.get("materialization", {})
    replay = view.get("input_replay_policy", {})
    if (
        tensors.get("byte_count") != BYTE_SPAN
        or tensors.get("element_count") != 32768
        or tensors.get("input", {}).get("byte_strides") != INPUT_STRIDES
        or tensors.get("output", {}).get("byte_strides") != OUTPUT_STRIDES
        or materialization.get("kind") != "execplan_metadata_zero_copy_alias"
        or materialization.get("emit_arithmetic_json") is not False
        or materialization.get("hardware_memory_request_count") != 0
        or replay.get("copy_enabled") is not False
        or replay.get("input_or_constant_replay_enabled") is not False
    ):
        raise FlattenSharedEndpointError("frozen node0073 zero-copy contract differs")
    if (
        view_contract.get("status") != STATUS
        or view_contract.get("claim_enabled") is not False
        or view_contract.get("claim_label") is not None
        or view_contract.get("local_e2", {}).get("independent") is not False
        or view_contract.get("local_e2", {}).get("integrated_target") is not False
    ):
        raise FlattenSharedEndpointError("node0073 fail-closed claim boundary differs")

    consumer = sources["consumer_rounding_discriminator"]
    dependency = consumer.get("node0074_flatten_endpoint_dependency", {})
    if (
        dependency.get("blocked_by") != "B_QUANT_NODE0074_EXACT_DIVISION"
        or dependency.get("status")
        != "DEPENDENCY_RECORDED_ENDPOINT_NOT_MATERIALIZED"
        or dependency.get("target_endpoint_claimed") is not False
        or dependency.get("provisional_address_allowed") is not False
    ):
        raise FlattenSharedEndpointError("node0074 exact-division boundary differs")
    nonnull = [field for field in CONSUMER_FINAL_FIELDS if dependency.get(field) is not None]
    if nonnull:
        raise FlattenSharedEndpointError(
            "node0074 final endpoint fields must remain null: " + ", ".join(nonnull)
        )


def build_manifest(root: Path) -> dict[str, Any]:
    sources = _load_frozen_sources(root)
    _validate_source_semantics(sources)
    producer_handoff = sources["producer_contract"][
        "node0073_integrated_binding_handoff"
    ]
    physical = producer_handoff["physical_contract"]
    consumer_dependency = sources["consumer_rounding_discriminator"][
        "node0074_flatten_endpoint_dependency"
    ]

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "claim_label": None,
        "claim_enabled": False,
        "integrated_target_local_e2": False,
        "numeric_analysis_repeated": False,
        "reused_assets_consumed": True,
        "reuse_scope": {
            "node0072": "accepted standalone D addressed handoff only",
            "node0073": "frozen metadata-only zero-copy and 32768-element mapping",
            "node0074": "exact-division discriminator and null endpoint dependency",
            "deferred_tests": [
                "node0072 numeric/config-bound rerun",
                "node0073 32768-element address mapping rerun",
                "node0074 arithmetic target generation",
            ],
        },
        "chain": [
            {
                "node_id": "node-0072",
                "request_id": "r5:hwop-0072-00",
                "port": "D",
                "tensor_id": "tensor-50c285690f899b1b",
                "role": "storage producer",
            },
            {
                "node_id": "node-0073",
                "request_id": "r5:hwop-0073-00",
                "role": "metadata-only zero-copy alias",
                "view_delta_bytes": 0,
            },
            {
                "node_id": "node-0074",
                "request_id": "r5:hwop-0074-00",
                "port": "A",
                "tensor_id": "tensor-9b1363d3baf474c8",
                "role": "read-only consumer",
            },
        ],
        "required_shared_endpoint": {
            "storage_relation": "same storage_id and allocation owner",
            "address_equation": (
                "node0074_A_base+consumer_byte_offset="
                "node0072_D_base+producer_byte_offset+0"
            ),
            "byte_span": BYTE_SPAN,
            "producer_write_coverage_bytes": BYTE_SPAN,
            "consumer_read_coverage_bytes": BYTE_SPAN,
            "producer_byte_strides": INPUT_STRIDES,
            "consumer_byte_strides": OUTPUT_STRIDES,
            "order": "C",
            "dtype": "float32",
            "allocator_plan_required": True,
            "addressed_graph_required": True,
            "producer_layout_required": True,
            "consumer_layout_required": True,
        },
        "producer_standalone_evidence": {
            "scope": "not a shared multi-operator allocation certificate",
            "allocation_owner": producer_handoff["storage_owner"],
            "storage_id": None,
            "logical_valid_write_coverage_bytes": BYTE_SPAN,
            "physical_written_span_bytes": physical["physical_written_span_bytes"],
            "padding_bytes": physical["padding_bytes"],
            "slice_d_base_addresses": [
                item["physical_d_base_addr"] for item in physical["slice_bindings"]
            ],
            "slice_write_coverage_complete": True,
            "addressed_asset_hashes": producer_handoff["addressed_asset_hashes"],
            "dynamic_final_write_accepted": False,
            "integrated_lifetime_accepted": False,
        },
        "view_alias": {
            "allocation_owner": "activation_allocator_for_node0072_D",
            "allocates": False,
            "releases": False,
            "copies": False,
            "replays": False,
            "arithmetic_json": False,
            "hardware_requests": 0,
            "required_view_delta_bytes": 0,
        },
        "consumer_endpoint": {
            field: consumer_dependency[field] for field in CONSUMER_FINAL_FIELDS
        },
        "shared_endpoint_binding": {
            "storage_id": None,
            "allocation_owner_request_id": None,
            "allocation_base": None,
            "producer_byte_offset": None,
            "consumer_byte_offset": None,
            "same_storage_proven": False,
            "same_base_plus_offset_proven": False,
            "producer_integrated_write_coverage": None,
            "consumer_integrated_read_coverage": None,
            "accepted_lifetime_proven": False,
            "no_pending_or_replayed_consumer_reads_at_release": None,
            "allocator_plan": None,
            "consumer_addressed_execplan": None,
            "consumer_layout_contract": None,
        },
        "accepted_lifetime_contract": {
            "event_sequence": [
                "allocation.bind_accepted",
                "node0073.view_alias_bind_accepted",
                "node0072.final_output_write_accepted",
                "node0072.completion_accepted",
                "node0074.first_input_data_accepted",
                "node0074.final_input_data_accepted",
                "allocation.release_accepted",
            ],
            "release_precondition": (
                "node0074.final_input_data_accepted and no pending/replayed "
                "node0074-A reads"
            ),
            "final_certificate": None,
        },
        "dependency_bindings": {
            "source_assets": SOURCE_IDENTITIES,
            "rules": {
                path: {"sha256": sha256} for path, sha256 in RULE_RECEIPTS.items()
            },
            "plan": PLAN_RECEIPT,
            "shared_allocator_plan": None,
            "shared_addressed_graph": None,
            "shared_execplan": None,
            "consumer_layout": None,
        },
        "blockers": {
            "B_VIEW_PRODUCER_ALLOCATION": {
                "status": "DEFERRED_TO_INTEGRATION",
                "delta": (
                    "narrowed by accepted node0072 standalone allocation, 28 slice "
                    "bases and complete write coverage; shared allocator and dynamic "
                    "final-write acceptance remain missing"
                ),
            },
            "B_VIEW_CONSUMER_ALLOCATION": {
                "status": "OPEN",
                "owner": "node0074 Quantize",
            },
            "B_VIEW_BYTE_OFFSET_IDENTITY": {
                "status": "OPEN",
                "owner": "shared allocator/addressed execplan integration",
            },
            "B_VIEW_BUFFER_LIFETIME": {
                "status": "OPEN",
                "owner": "shared execplan accepted-handshake integration",
            },
            "B_QUANT_NODE0074_EXACT_DIVISION": {
                "status": "OPEN",
                "owner": "node0074 Quantize",
                "blocks_consumer_endpoint": True,
            },
            "B_QUANT_NODE0074_FLATTEN_ENDPOINT_BINDING": {
                "status": "OPEN",
                "owner": "node0074 Quantize plus shared integration",
            },
        },
        "package_release": {
            "state": "NOT_BUILT",
            "server_package": False,
            "lease": None,
            "upload_or_run": False,
        },
        "claim_boundary": (
            "CONFIG_ONLY_CORRECTNESS_BASELINE is not enabled. The shared endpoint "
            "and integrated target local E2 remain unclaimed until node0074 exact "
            "division and all final addressed allocator/layout/lifetime fields pass."
        ),
    }
    manifest["manifest_content_sha256"] = _content_sha256(
        manifest, "manifest_content_sha256"
    )
    return manifest


def validate_manifest(manifest: Mapping[str, Any], root: Path) -> dict[str, Any]:
    sources = _load_frozen_sources(root)
    _validate_source_semantics(sources)
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(manifest.get("schema") == SCHEMA, "schema differs")
    require(manifest.get("status") == STATUS, "status must remain pending")
    require(manifest.get("claim_label") is None, "claim_label must remain null")
    require(manifest.get("claim_enabled") is False, "claim must remain disabled")
    require(
        manifest.get("integrated_target_local_e2") is False,
        "integrated target local E2 must remain false",
    )
    require(
        manifest.get("numeric_analysis_repeated") is False,
        "numeric analysis must not be repeated",
    )
    require(
        manifest.get("reused_assets_consumed") is True,
        "frozen reuse assets must be consumed",
    )
    required = manifest.get("required_shared_endpoint", {})
    require(required.get("byte_span") == BYTE_SPAN, "required byte span differs")
    require(
        required.get("producer_write_coverage_bytes") == BYTE_SPAN,
        "producer required write coverage differs",
    )
    require(
        required.get("consumer_read_coverage_bytes") == BYTE_SPAN,
        "consumer required read coverage differs",
    )
    producer = manifest.get("producer_standalone_evidence", {})
    require(
        producer.get("logical_valid_write_coverage_bytes") == BYTE_SPAN,
        "producer standalone logical coverage differs",
    )
    require(
        len(producer.get("slice_d_base_addresses", [])) == 28,
        "producer standalone slice bases differ",
    )
    require(
        producer.get("dynamic_final_write_accepted") is False,
        "dynamic final write may not be promoted",
    )
    alias = manifest.get("view_alias", {})
    require(alias.get("copies") is False, "copy fallback is forbidden")
    require(alias.get("replays") is False, "replay fallback is forbidden")
    require(alias.get("arithmetic_json") is False, "arithmetic JSON is forbidden")
    require(alias.get("hardware_requests") == 0, "View hardware request is forbidden")
    consumer = manifest.get("consumer_endpoint", {})
    for field in CONSUMER_FINAL_FIELDS:
        require(consumer.get(field) is None, f"consumer {field} must remain null")
    shared = manifest.get("shared_endpoint_binding", {})
    for field in (
        "storage_id",
        "allocation_owner_request_id",
        "allocation_base",
        "producer_byte_offset",
        "consumer_byte_offset",
        "producer_integrated_write_coverage",
        "consumer_integrated_read_coverage",
        "no_pending_or_replayed_consumer_reads_at_release",
        "allocator_plan",
        "consumer_addressed_execplan",
        "consumer_layout_contract",
    ):
        require(shared.get(field) is None, f"shared endpoint {field} must remain null")
    require(
        shared.get("same_storage_proven") is False,
        "same-storage proof may not be promoted",
    )
    require(
        shared.get("same_base_plus_offset_proven") is False,
        "base+offset proof may not be promoted",
    )
    require(
        shared.get("accepted_lifetime_proven") is False,
        "accepted lifetime proof may not be promoted",
    )
    require(
        manifest.get("package_release", {}).get("server_package") is False,
        "server package must not be generated",
    )
    expected_content_hash = _content_sha256(manifest, "manifest_content_sha256")
    require(
        manifest.get("manifest_content_sha256") == expected_content_hash,
        "manifest content hash differs",
    )
    if errors:
        raise FlattenSharedEndpointError("; ".join(errors))

    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "valid": True,
        "status": STATUS,
        "claim_label": None,
        "claim_enabled": False,
        "integrated_target_local_e2": False,
        "numeric_analysis_repeated": False,
        "reused_assets_consumed": True,
        "producer_standalone_write_coverage_bytes": BYTE_SPAN,
        "consumer_final_endpoint_null_field_count": len(CONSUMER_FINAL_FIELDS),
        "same_storage_proven": False,
        "same_base_plus_offset_proven": False,
        "accepted_lifetime_proven": False,
        "copy_or_replay_materialized": False,
        "arithmetic_json_generated": False,
        "server_package_generated": False,
        "open_blockers": list(manifest["blockers"]),
    }
    report["report_content_sha256"] = _content_sha256(
        report, "report_content_sha256"
    )
    return report


def build_assets(
    root: Path,
    *,
    contract_path: Path | None = None,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    if contract_path is None:
        contract_path = (
            root
            / "contracts/operator_config/"
            "node0072_node0073_node0074_shared_endpoint_manifest_v1.json"
        )
    if artifact_root is None:
        artifact_root = (
            root
            / "artifacts/operator_config_validation/"
            "r5-flatten-shared-endpoint-v1"
        )
    manifest = build_manifest(root)
    report = validate_manifest(manifest, root)
    _write_json(contract_path, manifest)
    report_path = artifact_root / "validation_report.json"
    _write_json(report_path, report)
    artifact_manifest = {
        "schema": "resnet50-flatten-shared-endpoint-artifact-manifest-v1",
        "status": STATUS,
        "files": {
            contract_path.relative_to(root).as_posix(): _sha256_file(contract_path),
            report_path.relative_to(root).as_posix(): _sha256_file(report_path),
        },
        "server_package": False,
    }
    artifact_manifest["manifest_content_sha256"] = _content_sha256(
        artifact_manifest, "manifest_content_sha256"
    )
    artifact_manifest_path = artifact_root / "manifest.json"
    _write_json(artifact_manifest_path, artifact_manifest)
    return {
        "contract": contract_path.relative_to(root).as_posix(),
        "contract_sha256": _sha256_file(contract_path),
        "validation_report": report_path.relative_to(root).as_posix(),
        "validation_report_sha256": _sha256_file(report_path),
        "artifact_manifest": artifact_manifest_path.relative_to(root).as_posix(),
        "artifact_manifest_sha256": _sha256_file(artifact_manifest_path),
        "status": STATUS,
        "integrated_target_local_e2": False,
        "numeric_analysis_repeated": False,
        "reused_assets_consumed": True,
        "server_package": False,
    }
