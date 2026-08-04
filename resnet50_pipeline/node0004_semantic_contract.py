from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .address_bound_config import validate_address_bound_config
from .operator_config_validator import TargetProfile
from .r5_lowering_bundle import validate_r5_lowering_bundle


SCHEMA = "operator-config-semantic-contract-v1"
NODE_ID = "node-0004"
OP_TYPE = "node0004_accumulate_wave0_nopp_r1"
ACCUMULATE_REQUEST = "r5:hwop-0004-00"
REQUANT_REQUEST = "r5:hwop-0004-01"


class Node0004SemanticContractError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Node0004SemanticContractError(f"JSON root must be an object: {path}")
    return value


def _request(bundle: Mapping[str, Any], request_id: str) -> Mapping[str, Any]:
    requests = bundle.get("requests")
    if not isinstance(requests, list):
        raise Node0004SemanticContractError("typed lowering requests are missing")
    matches = [item for item in requests if isinstance(item, Mapping) and item.get("request_id") == request_id]
    if len(matches) != 1:
        raise Node0004SemanticContractError(f"expected one lowering request: {request_id}")
    return matches[0]


def _parameter(request: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    parameters = request.get("typed_parameters")
    if not isinstance(parameters, list):
        raise Node0004SemanticContractError("typed parameter list is missing")
    matches = [item for item in parameters if isinstance(item, Mapping) and item.get("name") == name]
    if len(matches) != 1:
        raise Node0004SemanticContractError(
            f"expected one {name} parameter in {request.get('request_id')}"
        )
    if matches[0].get("resolution") != "derived":
        raise Node0004SemanticContractError(f"typed parameter {name} is not derived")
    return matches[0]


def _typed_value(parameter: Mapping[str, Any]) -> dict[str, Any]:
    value = parameter.get("value")
    if not isinstance(value, Mapping):
        raise Node0004SemanticContractError("typed parameter value is missing")
    return deepcopy(dict(value))


def _scalar(parameter: Mapping[str, Any], *, positive: bool) -> int | float:
    value = _typed_value(parameter)
    if value.get("value_kind") != "scalar" or value.get("shape") != [1]:
        raise Node0004SemanticContractError("expected a scalar typed parameter")
    scalar = value.get("scalar")
    if isinstance(scalar, bool) or not isinstance(scalar, (int, float)):
        raise Node0004SemanticContractError("typed scalar value is malformed")
    if positive and scalar <= 0:
        raise Node0004SemanticContractError("typed scale must be positive")
    return scalar


def build_node0004_semantic_contract(
    project_root: Path,
    *,
    graph_withbaseaddr: Path,
    mapping_bundle: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    graph_path = graph_withbaseaddr.resolve()
    mapping_root = mapping_bundle.resolve()
    lowering_path = root / "contracts/resnet50_r5_lowering_bundle.json"
    materialization_path = (
        root
        / "configs/native_ndp_sim/node0004_accumulate_wave0_nopp_r1_strict_v1/manifest.json"
    )
    address_bound_root = (
        root
        / "configs/native_ndp_sim/node0004_accumulate_wave0_nopp_r1_strict_address_bound_v1"
    )
    lowering = _load(lowering_path)
    validate_r5_lowering_bundle(lowering, root)
    graph = _load(graph_path)
    materialization = _load(materialization_path)
    address_bound = validate_address_bound_config(address_bound_root, project_root=root)
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
        raise Node0004SemanticContractError("withbaseaddr graph is not the node-0004 nopp candidate")
    op = operators[0]
    if set(op.get("inputs", {})) != {"A", "B", "C"} or op.get("output", {}).get("dtype") != "int32":
        raise Node0004SemanticContractError("node-0004 candidate port contract differs")
    if materialization.get("status") != "strict_config_materialized_from_bit_equivalent_cleanup":
        raise Node0004SemanticContractError("strict config materialization is not approved")
    if (
        mapping_manifest.get("summary", {}).get("valid") is not True
        or mapping_manifest.get("summary", {}).get("penalty") != 0.0
        or mapping_manifest.get("summary", {}).get("fallback_used") is not False
        or mapping_evidence.get("source_config", {}).get("sha256")
        != address_bound.get("bound_config", {}).get("sha256")
    ):
        raise Node0004SemanticContractError("mapping bundle is not the strict zero-penalty candidate")
    if mapping_manifest.get("mapping_evidence_sha256") != sha256_file(mapping_root / "mapping_evidence.json"):
        raise Node0004SemanticContractError("mapping evidence identity differs")

    accumulate = _request(lowering, ACCUMULATE_REQUEST)
    requant = _request(lowering, REQUANT_REQUEST)
    for request, stage in ((accumulate, "accumulate"), (requant, "requantize")):
        if (
            request.get("identity", {}).get("node_id") != NODE_ID
            or request.get("identity", {}).get("stage") != stage
            or request.get("emission_policy", {}).get("formal_target_instance_allowed") is not False
        ):
            raise Node0004SemanticContractError(f"lowering identity/policy differs for {stage}")

    x_scale = _parameter(requant, "x_scale")
    x_zero_point = _parameter(accumulate, "x_zero_point")
    w_scale = _parameter(requant, "w_scale")
    w_zero_point = _parameter(accumulate, "w_zero_point")
    request_identity = (
        f"{lowering['schema']}:"
        f"{accumulate['request_id']}@{accumulate['request_sha256']}+"
        f"{requant['request_id']}@{requant['request_sha256']}"
    )
    contract: dict[str, Any] = {
        "schema": SCHEMA,
        "graph_sha256": sha256_file(graph_path),
        "target_profile": asdict(TargetProfile()),
        "candidate_scope": {
            "node_id": NODE_ID,
            "revision": "nopp_r1",
            "formal_target_config": False,
            "server_execution_claim": False,
            "purpose": "single-stage zero-ping-pong accumulate smoke",
        },
        "source_identities": {
            "typed_lowering_bundle_sha256": sha256_file(lowering_path),
            "typed_lowering_request_set_sha256": lowering["request_set_sha256"],
            "accumulate_request_sha256": accumulate["request_sha256"],
            "requant_request_sha256": requant["request_sha256"],
            "strict_config_materialization_sha256": sha256_file(materialization_path),
            "address_bound_materialization_sha256": sha256_file(
                address_bound_root / "manifest.json"
            ),
            "mapping_bundle_manifest_sha256": sha256_file(mapping_root / "bundle_manifest.json"),
        },
        "operators": {
            "op0": {
                "op_type": OP_TYPE,
                "layouts": {
                    "A": "signed-A Conv28 weight tile; local K16 x global C64; int8 K-major/C-minor",
                    "B": "unsigned-B Conv28 activation tile; one logical sample; HWC with C64",
                    "C": "INT32 bias vector; local K16",
                    "D": "INT32 partial-sum tile; one logical sample; HWK-local K16",
                },
                "qparams": {
                    "policy": "explicit",
                    "bindings": {
                        "A": {
                            "scale": _typed_value(w_scale),
                            "zero_point": _typed_value(w_zero_point),
                            "source": request_identity,
                        },
                        "B": {
                            "scale": _scalar(x_scale, positive=True),
                            "zero_point": _scalar(x_zero_point, positive=False),
                            "source": request_identity,
                        },
                    },
                },
                "stage": {
                    "role": "QLinearConv INT32 accumulate wave 0; candidate-only",
                    "dependencies": [],
                },
                "tail": {
                    "policy": "explicit",
                    "bindings": {
                        "A": {"block_elements": 16, "valid_last": 16},
                        "B": {"block_elements": 16, "valid_last": 16},
                        "C": {"block_elements": 4, "valid_last": 4},
                        "D": {"block_elements": 4, "valid_last": 4},
                    },
                },
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


def validate_node0004_semantic_contract(
    value: Mapping[str, Any],
    project_root: Path,
    *,
    graph_withbaseaddr: Path,
    mapping_bundle: Path,
) -> None:
    expected = build_node0004_semantic_contract(
        project_root,
        graph_withbaseaddr=graph_withbaseaddr,
        mapping_bundle=mapping_bundle,
    )
    if value != expected:
        raise Node0004SemanticContractError(
            "node-0004 semantic contract differs from hash-bound inputs"
        )


__all__ = [
    "Node0004SemanticContractError",
    "build_node0004_semantic_contract",
    "validate_node0004_semantic_contract",
]
