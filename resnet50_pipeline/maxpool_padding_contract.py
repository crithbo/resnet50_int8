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
CURRENT_PADDING_RTL_RECEIPT = (
    "contracts/operator_config/maxpool_padding_rtl_current_receipt_v1.json"
)
CURRENT_RTL_REPOSITORY = "https://github.com/xlsjdjdk/Trassic2.0_RTL.git"
CURRENT_RTL_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
CURRENT_PADDING_AUTHORITY = (
    "Trassic2.0_RTL/code/NDP_rtl/Slice/LSU/Stream_Engine/"
    "Memory_Stream_Engine/Memory_RD_Stream_Engine/RD_Data_Channel.sv"
)
CURRENT_PADDING_MIRROR = (
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Memory_RD_Stream_Engine/RD_Data_Channel.sv"
)
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


def _checkout_head(repository: Path) -> str:
    git_dir = repository / ".git"
    head_path = git_dir / "HEAD"
    try:
        head = head_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise MaxPoolPaddingContractError(
            f"cannot read RTL checkout HEAD: {head_path}"
        ) from error
    if not head.startswith("ref: "):
        return head
    ref = head.removeprefix("ref: ").strip()
    ref_path = git_dir / ref
    if ref_path.is_file():
        return ref_path.read_text(encoding="utf-8").strip()
    packed_refs = git_dir / "packed-refs"
    if packed_refs.is_file():
        for line in packed_refs.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith(("#", "^")):
                commit, name = line.split(" ", 1)
                if name == ref:
                    return commit
    raise MaxPoolPaddingContractError(
        f"cannot resolve RTL checkout ref {ref!r}"
    )


def build_maxpool_padding_rtl_current_receipt(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    authority_path = root / CURRENT_PADDING_AUTHORITY
    mirror_path = root / CURRENT_PADDING_MIRROR
    legacy_paths = (
        root / "contracts/maxpool_uint8_zero_padding_contract.json",
        root / "contracts/maxpool_node0002_zero_padding_contract.json",
    )
    for path in (authority_path, mirror_path, *legacy_paths):
        if not path.is_file():
            raise MaxPoolPaddingContractError(
                f"required MaxPool padding receipt input is missing: {path}"
            )
    checkout_head = _checkout_head(root / "Trassic2.0_RTL")
    if checkout_head != CURRENT_RTL_COMMIT:
        raise MaxPoolPaddingContractError(
            "current RTL checkout commit differs from the MaxPool padding receipt"
        )
    authority_sha = sha256_file(authority_path)
    mirror_sha = sha256_file(mirror_path)
    if authority_sha != mirror_sha or authority_path.read_bytes() != mirror_path.read_bytes():
        raise MaxPoolPaddingContractError(
            "current cloud-authority checkout and NDP_copy01 padding RTL differ"
        )
    lines = authority_path.read_text(encoding="utf-8").splitlines()
    assignment_lines = [
        index + 1
        for index, line in enumerate(lines)
        if "assign rd_data_chl_data[PADDING_INDEX]" in line
    ]
    if assignment_lines != [288]:
        raise MaxPoolPaddingContractError(
            "current padding substitution assignment is not unique at line 288"
        )
    source_fragment = " ".join(line.strip() for line in lines[287:290])
    required_fragments = (
        "rd_chl_queue_rd_padding_mask[PADDING_INDEX] ? mse_padding_reg_value",
        "rd_chl_queue_rd_branch_mask[PADDING_INDEX] ? {`DDR_DATA_MIN_WIDTH{1'b0}}",
        "rd_chl_ib_data[rd_chl_ib_sel][`DDR_DATA_MIN_WIDTH*PADDING_INDEX +: `DDR_DATA_MIN_WIDTH]",
    )
    if not all(fragment in source_fragment for fragment in required_fragments):
        raise MaxPoolPaddingContractError(
            "current RD_Data_Channel padding substitution equation differs"
        )
    legacy_contracts = []
    for path in legacy_paths:
        value = _load(path)
        contract_sha = value.get("contract_sha256")
        if not isinstance(contract_sha, str) or len(contract_sha) != 64:
            raise MaxPoolPaddingContractError(
                f"legacy MaxPool contract lacks its internal receipt: {path}"
            )
        legacy_contracts.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "contract_sha256": contract_sha,
            }
        )
    return {
        "schema": "maxpool-padding-rtl-current-receipt-v1",
        "status": "CURRENT_CLOUD_AUTHORITY_AND_LOCAL_MIRROR_MATCH",
        "legacy_contract_bindings": legacy_contracts,
        "cloud_authority_checkout": {
            "repository": CURRENT_RTL_REPOSITORY,
            "commit": checkout_head,
            "path": CURRENT_PADDING_AUTHORITY,
            "size_bytes": authority_path.stat().st_size,
            "sha256": authority_sha,
        },
        "local_runtime_mirror": {
            "path": CURRENT_PADDING_MIRROR,
            "size_bytes": mirror_path.stat().st_size,
            "sha256": mirror_sha,
            "byte_equal_to_cloud_authority_checkout": True,
        },
        "padding_substitution": {
            "source_line_span": [288, 290],
            "priority": [
                "padding_mask selects configured padding byte",
                "branch_or_tail_mask selects zero",
                "otherwise select DDR input byte",
            ],
            "equation": (
                "padding_mask ? padding_value : "
                "branch_or_tail_mask ? zero : ddr_data"
            ),
            "source_fragment": source_fragment,
        },
        "claim_boundary": (
            "Read-only current RTL identity and padding substitution receipt. "
            "No MaxPool numeric-rule, functional-RTL, mapping, bitstream, "
            "execplan, SCA, server-package, or dynamic result claim."
        ),
    }


def validate_maxpool_padding_rtl_current_receipt(
    project_root: Path,
    receipt_path: Path,
) -> dict[str, Any]:
    actual = _load(receipt_path.resolve())
    expected = build_maxpool_padding_rtl_current_receipt(project_root)
    if actual != expected:
        raise MaxPoolPaddingContractError(
            "MaxPool current padding RTL receipt differs from current evidence"
        )
    return actual


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
    for source in (arithmetic_source,):
        local_source = root / str(source["path"])
        if local_source.is_file() and sha256_file(local_source) != source["sha256"]:
            raise MaxPoolPaddingContractError(
                f"available local RTL differs from tracked evidence: {source['path']}"
            )
    validate_maxpool_padding_rtl_current_receipt(
        root, root / CURRENT_PADDING_RTL_RECEIPT
    )

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
    "CURRENT_PADDING_RTL_RECEIPT",
    "MaxPoolPaddingContractError",
    "build_maxpool_padding_rtl_current_receipt",
    "build_maxpool_zero_padding_contract",
    "validate_maxpool_padding_rtl_current_receipt",
    "validate_maxpool_zero_padding_contract",
    "write_maxpool_zero_padding_contract",
]
