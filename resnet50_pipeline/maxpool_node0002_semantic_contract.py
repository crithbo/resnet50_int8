from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_validator import TargetProfile
from .r5_lowering_bundle import validate_r5_lowering_bundle


SCHEMA = "operator-config-semantic-contract-v1"
NODE_ID = "node-0002"
REQUEST_ID = "r5:hwop-0002-00"
PRODUCER_REQUEST_ID = "r5:hwop-0001-01"
OP_TYPE = "maxpool_config_16_112_112_stride2_padding1"


class MaxPoolNode0002SemanticContractError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MaxPoolNode0002SemanticContractError(f"JSON root must be an object: {path}")
    return value


def _request(bundle: Mapping[str, Any], request_id: str) -> Mapping[str, Any]:
    matches = [
        item
        for item in bundle.get("requests", [])
        if isinstance(item, Mapping) and item.get("request_id") == request_id
    ]
    if len(matches) != 1:
        raise MaxPoolNode0002SemanticContractError(
            f"expected one lowering request: {request_id}"
        )
    return matches[0]


def _parameter(request: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    matches = [
        item
        for item in request.get("typed_parameters", [])
        if isinstance(item, Mapping) and item.get("name") == name
    ]
    if len(matches) != 1 or matches[0].get("resolution") != "derived":
        raise MaxPoolNode0002SemanticContractError(
            f"expected one derived producer parameter: {name}"
        )
    value = matches[0].get("value")
    if not isinstance(value, Mapping) or value.get("value_kind") != "scalar":
        raise MaxPoolNode0002SemanticContractError(
            f"producer parameter is not a typed scalar: {name}"
        )
    return matches[0]


def _typed_value(parameter: Mapping[str, Any]) -> dict[str, Any]:
    return deepcopy(dict(parameter["value"]))


def build_maxpool_node0002_semantic_contract(
    project_root: Path,
    *,
    graph_withbaseaddr: Path,
    mapping_bundle: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    graph_path = graph_withbaseaddr.resolve()
    mapping_root = mapping_bundle.resolve()
    lowering_path = root / "contracts/resnet50_r5_lowering_bundle.json"
    overlay_path = root / "contracts/resnet50_r5_resolution_overlay.json"
    guarded_path = (
        root
        / "artifacts/operator_config_validation/r5-maxpool-node0002-guarded-wave0-v1/manifest.json"
    )
    request_proof_path = (
        root
        / "artifacts/operator_config_validation/r5-patched-execplan-evidence/"
        "maxpool-node0002-guarded-wave0-v3/request_address_validation_report.json"
    )
    lowering = _load(lowering_path)
    validate_r5_lowering_bundle(lowering, root)
    graph = _load(graph_path)
    guarded = _load(guarded_path)
    request_proof = _load(request_proof_path)
    mapping_evidence = _load(mapping_root / "mapping_evidence.json")
    mapping_manifest = _load(mapping_root / "bundle_manifest.json")

    operators = graph.get("operators")
    if (
        not isinstance(operators, list)
        or len(operators) != 1
        or not isinstance(operators[0], Mapping)
        or operators[0].get("id") != "op0"
        or operators[0].get("type") != OP_TYPE
    ):
        raise MaxPoolNode0002SemanticContractError(
            "withbaseaddr graph is not the node-0002 guarded MaxPool candidate"
        )
    op = operators[0]
    storage = op.get("inputs", {}).get("A", {}).get("logical_storage")
    output_storage = op.get("output", {}).get("logical_storage")
    if (
        set(op.get("inputs", {})) != {"A"}
        or op.get("inputs", {}).get("A", {}).get("dtype") != "uint8"
        or op.get("output", {}).get("dtype") != "uint8"
        or not isinstance(storage, Mapping)
        or storage.get("schema") != "maxpool-guarded-c4hwc4-storage-v1"
        or storage.get("payload_offset_bytes") != 452
        or storage.get("allocation_bytes") != 201_168
        or not isinstance(output_storage, Mapping)
        or output_storage.get("schema") != "maxpool-c4hwc4-output-v1"
    ):
        raise MaxPoolNode0002SemanticContractError("guarded MaxPool storage ABI differs")
    if (
        mapping_manifest.get("summary", {}).get("valid") is not True
        or mapping_manifest.get("summary", {}).get("penalty") != 0.0
        or mapping_manifest.get("summary", {}).get("fallback_used") is not False
        or mapping_evidence.get("source_config", {}).get("sha256")
        != mapping_manifest.get("source_config_sha256")
        or mapping_manifest.get("mapping_evidence_sha256")
        != sha256_file(mapping_root / "mapping_evidence.json")
    ):
        raise MaxPoolNode0002SemanticContractError(
            "mapping bundle is not the exact zero-penalty candidate"
        )
    if (
        guarded.get("summary", {}).get("independent_mismatch_count") != 0
        or request_proof.get("valid") is not True
        or request_proof.get("facts", {}).get("request_count_with_multiplicity")
        != 1_517_936
    ):
        raise MaxPoolNode0002SemanticContractError(
            "guarded numeric/request proof differs"
        )

    request = _request(lowering, REQUEST_ID)
    producer = _request(lowering, PRODUCER_REQUEST_ID)
    if (
        request.get("identity", {}).get("node_id") != NODE_ID
        or request.get("identity", {}).get("hw_op_type") != "MaxPoolUint8"
        or request.get("emission_policy", {}).get("formal_target_instance_allowed")
        is not False
    ):
        raise MaxPoolNode0002SemanticContractError("MaxPool lowering identity differs")
    effective = [
        item
        for item in lowering.get("effective_resolutions", [])
        if isinstance(item, Mapping) and item.get("request_id") == REQUEST_ID
    ]
    if (
        len(effective) != 1
        or effective[0].get("candidate_config_emission_allowed") is not False
        or effective[0].get("formal_target_instance_allowed") is not False
        or effective[0].get("readiness_axes")
        != {
            "json_emitter_ready": True,
            "rtl_semantics_compatible": False,
            "dynamic_release_ready": False,
        }
        or effective[0].get("rtl_semantic_blockers")
        != ["B_GA_INT8_MAX_FLOW", "B_GA_INT8_MAX_NUMERIC"]
    ):
        raise MaxPoolNode0002SemanticContractError(
            "MaxPool effective lowering resolution differs"
        )
    producer_outputs = producer.get("ports", {}).get("outputs", [])
    inputs = request.get("ports", {}).get("inputs", [])
    if (
        len(producer_outputs) != 1
        or len(inputs) != 1
        or producer_outputs[0].get("tensor_id") != inputs[0].get("tensor_id")
        or producer_outputs[0].get("identity_sha256")
        != inputs[0].get("identity_sha256")
    ):
        raise MaxPoolNode0002SemanticContractError(
            "MaxPool qparams are not linked to the exact producer tensor"
        )
    scale = _parameter(producer, "y_scale")
    zero_point = _parameter(producer, "y_zero_point")
    if scale["value"].get("scalar") != 0.021563487127423286:
        raise MaxPoolNode0002SemanticContractError("MaxPool producer scale differs")
    if zero_point["value"].get("scalar") != 0:
        raise MaxPoolNode0002SemanticContractError("MaxPool producer zero point differs")

    source = (
        f"{lowering['schema']}:{producer['request_id']}@{producer['request_sha256']}"
        f"->{request['request_id']}@{request['request_sha256']}"
    )
    qbinding = {
        "scale": _typed_value(scale),
        "zero_point": _typed_value(zero_point),
        "source": source,
    }
    contract: dict[str, Any] = {
        "schema": SCHEMA,
        "graph_sha256": sha256_file(graph_path),
        "target_profile": asdict(TargetProfile()),
        "candidate_scope": {
            "node_id": NODE_ID,
            "wave_index": 0,
            "slice_count": 28,
            "remaining_tiles": 36,
            "formal_target_config": False,
            "server_execution_claim": False,
            "current_semantics_compatible": False,
            "current_semantic_blockers": [
                "B_GA_INT8_MAX_FLOW",
                "B_GA_INT8_MAX_NUMERIC",
            ],
            "purpose": (
                "hash-bound guarded C4HWC4 MaxPool historical package; "
                "current RTL semantic release is blocked"
            ),
        },
        "source_identities": {
            "typed_lowering_bundle_sha256": sha256_file(lowering_path),
            "typed_lowering_request_set_sha256": lowering["request_set_sha256"],
            "producer_request_sha256": producer["request_sha256"],
            "maxpool_request_sha256": request["request_sha256"],
            "resolution_overlay_sha256": sha256_file(overlay_path),
            "guarded_transport_manifest_sha256": sha256_file(guarded_path),
            "request_address_proof_sha256": sha256_file(request_proof_path),
            "mapping_bundle_manifest_sha256": sha256_file(
                mapping_root / "bundle_manifest.json"
            ),
        },
        "operators": {
            "op0": {
                "op_type": OP_TYPE,
                "layouts": {
                    "A": (
                        "UINT8 guarded C4HWC4; coordinate origin (1,1); "
                        "452-byte prefix, 200704-byte payload, 12-byte suffix"
                    ),
                    "D": "UINT8 C4HWC4 [C/4,H,W,4]; 56x56x16; 50176 bytes",
                },
                "qparams": {
                    "policy": "explicit",
                    "bindings": {"A": deepcopy(qbinding), "D": deepcopy(qbinding)},
                },
                "stage": {
                    "role": "node-0002 UINT8 3x3 stride-2 MaxPool wave 0 candidate",
                    "dependencies": [],
                },
                "tail": {"policy": "exact"},
                "provenance": {
                    "source_config": {
                        "artifact": "mapping_evidence/op0/source_config.json",
                        "sha256": sha256_file(mapping_root / "source_config.json"),
                    },
                    "mapping_evidence": {
                        "artifact": "mapping_evidence/op0/mapping_evidence.json",
                        "sha256": sha256_file(mapping_root / "mapping_evidence.json"),
                    },
                },
            }
        },
    }
    contract["contract_sha256"] = sha256_bytes(canonical_json_bytes(contract))
    return contract


def validate_maxpool_node0002_semantic_contract(
    value: Mapping[str, Any],
    project_root: Path,
    *,
    graph_withbaseaddr: Path,
    mapping_bundle: Path,
) -> None:
    expected = build_maxpool_node0002_semantic_contract(
        project_root,
        graph_withbaseaddr=graph_withbaseaddr,
        mapping_bundle=mapping_bundle,
    )
    if value != expected:
        raise MaxPoolNode0002SemanticContractError(
            "node-0002 MaxPool semantic contract differs from hash-bound inputs"
        )


__all__ = [
    "MaxPoolNode0002SemanticContractError",
    "build_maxpool_node0002_semantic_contract",
    "validate_maxpool_node0002_semantic_contract",
]
