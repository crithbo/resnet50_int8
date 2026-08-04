from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_adjudication import normalize_known_legacy_expressions
from .operator_config_corpus import build_operator_config_authority
from .typed_config_parameters import validate_typed_config_parameter_contract


SCHEMA = "gap-sum-uint8-zero-padding-contract-v1"
SOURCE_CONFIG = "ndp-sim/jsons/avgpool_config_2048_7_7.json"
TYPED_CONFIG_CONTRACT = "contracts/typed_config_parameter_contract.json"
AUTHORITY_CONTRACT = (
    "contracts/operator_config/operator_config_authority_v1.json"
)
RTL_SEMANTICS_EVIDENCE = "contracts/maxpool_rtl_semantics_evidence.json"
REQUEST_ID = "r5:hwop-0071-00"
HW_OP_ID = "hwop-0071-00"
GA_SUM_KEYS = ("PE00", "PE02", "PE10", "PE12", "PE20", "PE22", "PE30", "PE32")


class GapSumPaddingContractError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GapSumPaddingContractError(f"cannot parse JSON: {path}") from error
    if not isinstance(value, dict):
        raise GapSumPaddingContractError(f"JSON root must be an object: {path}")
    return value


def _with_contract_sha(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["contract_sha256"] = ""
    result["contract_sha256"] = sha256_bytes(canonical_json_bytes(result))
    return result


def build_gap_sum_zero_padding_contract(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    source_path = root / SOURCE_CONFIG
    typed_path = root / TYPED_CONFIG_CONTRACT
    authority_path = root / AUTHORITY_CONTRACT
    rtl_path = root / RTL_SEMANTICS_EVIDENCE
    for path in (source_path, typed_path, authority_path, rtl_path):
        if not path.is_file():
            raise GapSumPaddingContractError(
                f"required GAP padding evidence is missing: {path}"
            )

    authority = _load(authority_path)
    if authority != build_operator_config_authority(root):
        raise GapSumPaddingContractError(
            "configuration authority contract is stale"
        )
    authority_records = [
        item
        for item in authority.get("records", [])
        if isinstance(item, Mapping) and item.get("path") == SOURCE_CONFIG
    ]
    if (
        len(authority_records) != 1
        or authority_records[0].get("configuration_correctness")
        != "user_authorized_correct_reference"
        or authority_records[0].get("sha256") != sha256_file(source_path)
        or authority_records[0].get("provenance", {}).get("kind")
        != "pinned_upstream_exact_blob"
    ):
        raise GapSumPaddingContractError(
            "GAP source is not an authorized exact upstream reference"
        )

    typed = _load(typed_path)
    validate_typed_config_parameter_contract(typed)
    stages = [
        item
        for item in typed.get("hw_ops", [])
        if isinstance(item, Mapping) and item.get("hw_op_id") == HW_OP_ID
    ]
    if len(stages) != 1:
        raise GapSumPaddingContractError("GAP typed stage is not unique")
    stage = stages[0]
    geometry = stage.get("logical_geometry")
    parameters = {
        str(item.get("name")): item
        for item in stage.get("parameters", [])
        if isinstance(item, Mapping)
    }
    if (
        stage.get("hw_op_type") != "GlobalAverageSumInt32"
        or geometry
        != {
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
        }
        or parameters.get("x_zero_point", {}).get("value", {}).get("scalar")
        != 0
    ):
        raise GapSumPaddingContractError(
            "GAP exact geometry or zero-point identity differs"
        )

    source = _load(source_path)
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
        raise GapSumPaddingContractError(
            "GAP padding normalization set differs"
        )
    stream = source.get("stream_engine", {}).get("stream0")
    ga = source.get("general_array")
    if (
        source.get("CONFIG") != "11011101"
        or not isinstance(stream, Mapping)
        or stream.get("target") != "A"
        or stream.get("mode") != "read"
        or stream.get("padding_enable") != [0, 1, 0]
        or stream.get("padding_reg_value") is not None
        or stream.get("idx_padding_range", {}).get("low_bound")
        != [None, 0, None]
        or stream.get("idx_padding_range", {}).get("up_bound")
        != [None, 48, None]
        or not isinstance(ga, Mapping)
        or ga.get("inport", {}).get("inport0", {}).get("uint8toint32")
        != "true"
        or ga.get("outport", {}).get("int32touint8") != "false"
    ):
        raise GapSumPaddingContractError(
            "GAP source stream/conversion topology differs"
        )
    pe_array = ga.get("PE_array")
    if (
        not isinstance(pe_array, Mapping)
        or set(pe_array) != set(GA_SUM_KEYS)
        or any(
            pe_array[key].get("alu_opcode") != "int32_sum"
            or pe_array[key].get("inport0", {}).get("src_id") != 0
            or pe_array[key].get("inport0", {}).get("mode") != "buffer"
            for key in GA_SUM_KEYS
        )
    ):
        raise GapSumPaddingContractError(
            "GAP eight-lane int32-sum topology differs"
        )

    rtl = _load(rtl_path)
    padding_source = rtl.get("source_identity", {}).get("padding_path")
    padding_replacement = rtl.get("padding_replacement")
    assignment = (
        "rd_chl_queue_rd_padding_mask[PADDING_INDEX] ? mse_padding_reg_value"
    )
    if (
        rtl.get("schema") != "maxpool-rtl-semantics-evidence-v1"
        or not isinstance(padding_source, Mapping)
        or padding_source.get("path")
        != "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_RD_Stream_Engine/RD_Data_Channel.sv"
        or padding_source.get("sha256")
        != "87d1c9a05e8a1a51a5b78f7838962b381da74e7d471297b6da68f8a449aefe08"
        or not isinstance(padding_replacement, Mapping)
        or padding_replacement.get("assignment") != assignment
    ):
        raise GapSumPaddingContractError(
            "shared stream padding RTL evidence differs"
        )
    local_padding = root / str(padding_source["path"])
    if local_padding.is_file():
        if (
            sha256_file(local_padding) != padding_source["sha256"]
            or assignment
            not in local_padding.read_text(encoding="utf-8")
        ):
            raise GapSumPaddingContractError(
                "available padding RTL differs from tracked evidence"
            )

    return {
        "schema": SCHEMA,
        "status": "approved_for_exact_gap_sum_strict_normalization",
        "authorization": {
            "source_path": SOURCE_CONFIG,
            "source_sha256": sha256_file(source_path),
            "source_authority_sha256": authority["authority_sha256"],
            "normalized_canonical_sha256": sha256_bytes(
                canonical_json_bytes(normalized)
            ),
            "json_path": "$.stream_engine.stream0.padding_reg_value",
            "before": None,
            "after": 0,
            "scope": (
                "strict materialization of r5:hwop-0071-00 only; "
                "no server execution claim"
            ),
            "formal_target_config": False,
            "server_execution_claim": False,
        },
        "operator_semantics": {
            "request_id": REQUEST_ID,
            "operator": "GlobalAverageSumInt32",
            "input_shape": [16, 2048, 7, 7],
            "output_shape": [16, 2048, 1, 1],
            "input_dtype": "uint8",
            "output_dtype": "int32",
            "input_zero_point": 0,
            "spatial_element_count": 49,
            "lane_count": 8,
            "lane_opcode": "int32_sum",
            "additive_identity_byte": 0,
            "reason": (
                "the exact request has x_zero_point=0, uint8 is converted to "
                "int32 before eight-lane summation, and zero is the additive "
                "identity for masked positions"
            ),
        },
        "evidence": {
            "typed_config_parameter_contract": {
                "path": TYPED_CONFIG_CONTRACT,
                "sha256": sha256_file(typed_path),
                "hw_op_id": HW_OP_ID,
                "stage_sha256": sha256_bytes(canonical_json_bytes(stage)),
            },
            "configuration_authority": {
                "path": AUTHORITY_CONTRACT,
                "sha256": sha256_file(authority_path),
                "source_provenance": authority_records[0]["provenance"],
            },
            "shared_stream_padding_rtl": {
                "path": RTL_SEMANTICS_EVIDENCE,
                "sha256": sha256_file(rtl_path),
                "padding_source": dict(padding_source),
                "assignment": assignment,
            },
        },
        "contract_sha256": "",
    }


def write_gap_sum_zero_padding_contract(
    project_root: Path, output_path: Path
) -> dict[str, Any]:
    value = _with_contract_sha(
        build_gap_sum_zero_padding_contract(project_root)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    validate_gap_sum_zero_padding_contract(project_root, output_path)
    return value


def validate_gap_sum_zero_padding_contract(
    project_root: Path, contract_path: Path
) -> dict[str, Any]:
    actual = _load(contract_path.resolve())
    expected = _with_contract_sha(
        build_gap_sum_zero_padding_contract(project_root)
    )
    if actual != expected:
        raise GapSumPaddingContractError(
            "GAP zero-padding contract differs from current evidence"
        )
    return actual


__all__ = [
    "SCHEMA",
    "GapSumPaddingContractError",
    "build_gap_sum_zero_padding_contract",
    "validate_gap_sum_zero_padding_contract",
    "write_gap_sum_zero_padding_contract",
]
