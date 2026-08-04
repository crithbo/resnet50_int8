from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_adjudication import normalize_known_legacy_expressions
from .target_config_audit import validate_maxpool_shape_linkage


SCHEMA = "maxpool-uint8-zero-padding-contract-v1"
DEFAULT_SOURCE_CONFIG = "ndp-sim/jsons/maxpool_config_16_16_16_stride2_padding1.json"
SOURCE_CONFIGS = {
    DEFAULT_SOURCE_CONFIG: {
        "local_shape": [16, 16, 16],
        "sample_shape": [1, 16, 16, 16],
        "scope": "legacy_isolated_shape",
    },
    "ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json": {
        "local_shape": [16, 112, 112],
        "sample_shape": [1, 112, 112, 16],
        "scope": "resnet50_node_0002_local_tile",
    },
}
MODEL_GRAPH = "artifacts/w3/model_graph.json"
RTL_SEMANTICS_EVIDENCE = "contracts/maxpool_rtl_semantics_evidence.json"
NODE_ID = "node-0002"
INPUT_TENSOR_ID = "tensor-f6c1a8fb6fd529e8"


class MaxPoolPaddingContractError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MaxPoolPaddingContractError(f"cannot read JSON: {path}") from error
    if not isinstance(value, dict):
        raise MaxPoolPaddingContractError(f"JSON root must be an object: {path}")
    return value


def build_maxpool_zero_padding_contract(
    project_root: Path,
    source_config: str = DEFAULT_SOURCE_CONFIG,
) -> dict[str, Any]:
    root = project_root.resolve()
    shape_scope = SOURCE_CONFIGS.get(source_config)
    if shape_scope is None:
        raise MaxPoolPaddingContractError(
            f"unsupported MaxPool padding source: {source_config}"
        )
    source_path = root / source_config
    graph_path = root / MODEL_GRAPH
    rtl_evidence_path = root / RTL_SEMANTICS_EVIDENCE
    for path in (source_path, graph_path, rtl_evidence_path):
        if not path.is_file():
            raise MaxPoolPaddingContractError(f"required padding evidence is missing: {path}")

    source = _load(source_path)
    local_channels, local_height, local_width = shape_scope["local_shape"]
    validate_maxpool_shape_linkage(
        source,
        channels=int(local_channels),
        height=int(local_height),
        width=int(local_width),
        kernel=3,
        stride=2,
        padding=1,
    )
    normalized, changes = normalize_known_legacy_expressions(source)
    if len(changes) != 1 or (
        changes[0].kind,
        changes[0].path,
        changes[0].before,
        changes[0].after,
    ) != (
        "explicit_zero_padding",
        "$.stream_engine.stream0.padding_reg_value",
        None,
        0,
    ):
        raise MaxPoolPaddingContractError("MaxPool padding normalization set differs")

    graph = _load(graph_path)
    nodes = [item for item in graph.get("nodes", []) if item.get("node_id") == NODE_ID]
    tensors = [
        item
        for item in graph.get("tensors", [])
        if item.get("tensor_id") == INPUT_TENSOR_ID
    ]
    if (
        len(nodes) != 1
        or nodes[0].get("op_type") != "MaxPool"
        or nodes[0].get("input_tensor_ids") != [INPUT_TENSOR_ID]
        or nodes[0].get("attributes", {}).get("kernel_shape") != [3, 3]
        or nodes[0].get("attributes", {}).get("strides") != [2, 2]
        or nodes[0].get("attributes", {}).get("pads") != [1, 1, 1, 1]
        or len(tensors) != 1
        or tensors[0].get("dtype") != "uint8"
        or tensors[0].get("shape") != ["N", 64, 112, 112]
    ):
        raise MaxPoolPaddingContractError("W3 MaxPool UINT8 identity differs")

    rtl_evidence = _load(rtl_evidence_path)
    source_identity = rtl_evidence.get("source_identity", {})
    arithmetic_source = source_identity.get("arithmetic_path", {})
    padding_source = source_identity.get("padding_path", {})
    arithmetic_proof = rtl_evidence.get("arithmetic_proof", {})
    padding_replacement = rtl_evidence.get("padding_replacement", {})
    if (
        rtl_evidence.get("schema") != "maxpool-rtl-semantics-evidence-v1"
        or rtl_evidence.get("status") != "passed_static_and_isolated_kernel_only"
        or rtl_evidence.get("operator") != "MaxPoolUint8"
        or not isinstance(arithmetic_source, Mapping)
        or arithmetic_source.get("path")
        != "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/GA_PE_Float_CSA.v"
        or arithmetic_source.get("sha256")
        != "5bcc09111624f403cc2aab291f79fd32a6dd40ce7d9624db6306f8cde94906dc"
        or not isinstance(padding_source, Mapping)
        or padding_source.get("path")
        != "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_RD_Stream_Engine/RD_Data_Channel.sv"
        or padding_source.get("sha256")
        != "87d1c9a05e8a1a51a5b78f7838962b381da74e7d471297b6da68f8a449aefe08"
        or arithmetic_proof.get("input_pairs") != 65_536
        or arithmetic_proof.get("byte_lane_checks") != 262_144
        or arithmetic_proof.get("stdout_sha256")
        != "05c6a9da3c917974bc988021fa89496b270541b90624fa6094ae061392a3ebf1"
    ):
        raise MaxPoolPaddingContractError("tracked RTL semantic evidence identity differs")

    padding_assignment = (
        "rd_chl_queue_rd_padding_mask[PADDING_INDEX] ? mse_padding_reg_value"
    )
    if padding_replacement.get("assignment") != padding_assignment:
        raise MaxPoolPaddingContractError("tracked RTL padding assignment differs")
    for source in (arithmetic_source, padding_source):
        local_source = root / str(source["path"])
        if local_source.is_file() and sha256_file(local_source) != source["sha256"]:
            raise MaxPoolPaddingContractError(
                f"available local RTL differs from tracked evidence: {source['path']}"
            )
    local_padding = root / str(padding_source["path"])
    if (
        local_padding.is_file()
        and padding_assignment not in local_padding.read_text(encoding="utf-8")
    ):
        raise MaxPoolPaddingContractError("available local RTL padding assignment differs")

    source_sha = sha256_file(source_path)
    normalized_canonical_sha = sha256_bytes(canonical_json_bytes(normalized))
    operator_semantics = {
        "operator": "MaxPool",
        "logical_dtype": "uint8",
        "value_domain": [0, 255],
        "max_identity": 0,
        "reason": (
            "zero is the minimum UINT8 value, so replacing an excluded spatial "
            "border with byte 0 cannot increase a MaxPool result"
        ),
        "sample_shape": list(shape_scope["sample_shape"]),
        "kernel_shape": [3, 3],
        "strides": [2, 2],
        "pads": [1, 1, 1, 1],
    }
    # Preserve the already published 16x16 contract byte-for-byte.  The
    # model-exact contract carries the additional scope marker.
    if source_config != DEFAULT_SOURCE_CONFIG:
        operator_semantics["shape_scope"] = shape_scope["scope"]
    return {
        "schema": SCHEMA,
        "status": "approved_for_one_hash_bound_legacy_normalization",
        "authorization": {
            "source_path": source_config,
            "source_sha256": source_sha,
            "normalized_canonical_sha256": normalized_canonical_sha,
            "json_path": "$.stream_engine.stream0.padding_reg_value",
            "before": None,
            "after": 0,
            "scope": "strict materialization and local mapping evidence only",
            "formal_target_config": False,
            "server_execution_claim": False,
        },
        "operator_semantics": operator_semantics,
        "evidence": {
            "model_graph": {
                "path": MODEL_GRAPH,
                "sha256": sha256_file(graph_path),
                "model_sha256": graph.get("model_sha256"),
                "node_id": NODE_ID,
                "input_tensor_id": INPUT_TENSOR_ID,
            },
            "rtl_semantics_record": {
                "path": RTL_SEMANTICS_EVIDENCE,
                "sha256": sha256_file(rtl_evidence_path),
                "arithmetic_source_sha256": arithmetic_source["sha256"],
                "padding_source_sha256": padding_source["sha256"],
                "input_pairs": 65_536,
                "byte_lane_checks": 262_144,
                "assignment": padding_assignment,
            },
        },
        "contract_sha256": "",
    }


def _with_contract_sha(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["contract_sha256"] = ""
    result["contract_sha256"] = sha256_bytes(canonical_json_bytes(result))
    return result


def write_maxpool_zero_padding_contract(
    project_root: Path,
    output_path: Path,
    source_config: str = DEFAULT_SOURCE_CONFIG,
) -> dict[str, Any]:
    output = output_path.resolve()
    value = _with_contract_sha(
        build_maxpool_zero_padding_contract(project_root, source_config)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    validate_maxpool_zero_padding_contract(project_root, output)
    return value


def validate_maxpool_zero_padding_contract(
    project_root: Path, contract_path: Path
) -> dict[str, Any]:
    actual = _load(contract_path.resolve())
    authorization = actual.get("authorization")
    if not isinstance(authorization, Mapping):
        raise MaxPoolPaddingContractError("MaxPool padding authorization is missing")
    source_config = authorization.get("source_path")
    if not isinstance(source_config, str):
        raise MaxPoolPaddingContractError("MaxPool padding source path is missing")
    expected = _with_contract_sha(
        build_maxpool_zero_padding_contract(project_root, source_config)
    )
    if actual != expected:
        raise MaxPoolPaddingContractError(
            "MaxPool zero-padding contract differs from current hash-bound evidence"
        )
    return actual


__all__ = [
    "SCHEMA",
    "DEFAULT_SOURCE_CONFIG",
    "SOURCE_CONFIGS",
    "MaxPoolPaddingContractError",
    "build_maxpool_zero_padding_contract",
    "validate_maxpool_zero_padding_contract",
    "write_maxpool_zero_padding_contract",
]
