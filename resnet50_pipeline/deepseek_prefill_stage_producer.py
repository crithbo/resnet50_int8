from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .deepseek_onnx_validation import build_deepseek_crop_contract
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


SCHEMA = "deepseek-prefill-rule-normalized-stage-producer-v1"
RAW_GRAPH_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/layer0_prefill.generated.json"
)
OP_LISTING_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/"
    "layer0_prefill.generated_op_listing.json"
)
OUTPUT_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/"
    "layer0_prefill.rule_normalized.json"
)
CONTRACT_PATH = (
    "contracts/operator_config/"
    "deepseek_prefill_rule_normalized_stage_v1.json"
)
RMS_RULE_PATH = ".agents/rules/DeepSeek_RMSNorm增量规则.md"
SOFTMAX_RULE_PATH = ".agents/rules/DeepSeek_Softmax增量规则.md"
LIFECYCLE_RULE_PATH = ".agents/rules/DeepSeek_码流生命周期增量规则.md"

ALL_28_MASK = "0b" + ("1" * 28)
RAW_SINGLE_LEADER_MASK = "0b1" + ("0" * 27)
GEMM_A_LAYOUT_HINT = "reorder(m8,n2)->(n2,m8)"
GEMM_B_LAYOUT_HINT = "reorder(n8,m2)->(m2,n8)"
SOFTMAX_MASK_LAYOUT_HINT = "softmax_mask_reuse_rows"
SOFTMAX_EXP_LAYOUT_HINT = "softmax_exp_m8_n_interleave"


class DeepSeekPrefillStageProducerError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekPrefillStageProducerError(
            f"cannot parse DeepSeek Stage producer input: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DeepSeekPrefillStageProducerError(
            f"DeepSeek Stage producer input is not an object: {path}"
        )
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise DeepSeekPrefillStageProducerError(
            f"required DeepSeek Stage producer input is missing: {relative}"
        )
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _operators_by_id(graph: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    operators = graph.get("operators")
    if not isinstance(operators, list):
        raise DeepSeekPrefillStageProducerError(
            "raw prefill graph has no operators list"
        )
    result: dict[str, dict[str, Any]] = {}
    for value in operators:
        if not isinstance(value, dict) or not isinstance(
            value.get("id"), str
        ):
            raise DeepSeekPrefillStageProducerError(
                "raw prefill graph has a malformed operator"
            )
        op_id = str(value["id"])
        if op_id in result:
            raise DeepSeekPrefillStageProducerError(
                f"raw prefill graph repeats operator {op_id}"
            )
        result[op_id] = value
    return result


def _ids_for_label(
    listing: Mapping[str, Any], label: str
) -> list[str]:
    return sorted(
        [
            str(op_id)
            for op_id, value in listing.items()
            if value == label
        ],
        key=lambda value: int(value.removeprefix("op")),
    )


def _record_change(
    changes: list[dict[str, Any]],
    path: str,
    before: Any,
    after: Any,
    rule_id: str,
) -> None:
    changes.append(
        {
            "path": path,
            "before": deepcopy(before),
            "after": deepcopy(after),
            "rule_id": rule_id,
        }
    )


def build_rule_normalized_prefill_stage(
    project_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root = project_root.resolve()
    crop = build_deepseek_crop_contract(root)
    target = crop.get("model_dimensions", {}).get("target", {})
    derived = crop.get("model_dimensions", {}).get("derived", {})
    if (
        target.get("hidden_size") != 896
        or target.get("intermediate_size") != 1792
        or target.get("num_attention_heads") != 7
        or target.get("num_key_value_heads") != 1
        or derived.get("active_slice_count") != 28
    ):
        raise DeepSeekPrefillStageProducerError(
            "crop contract does not authorize the normalized prefill Stage"
        )

    raw = _load(root / RAW_GRAPH_PATH)
    listing = _load(root / OP_LISTING_PATH)
    graph = deepcopy(raw)
    operators = _operators_by_id(graph)
    if set(operators) != set(listing):
        raise DeepSeekPrefillStageProducerError(
            "prefill graph and source listing operator IDs differ"
        )

    rms_remote_ids = _ids_for_label(listing, "rmsnorm::op1")
    rms_sfu_ids = _ids_for_label(listing, "rmsnorm::op2")
    if rms_remote_ids != ["op1", "op33"] or rms_sfu_ids != [
        "op2",
        "op34",
    ]:
        raise DeepSeekPrefillStageProducerError(
            "prefill RMSNorm occurrences differ"
        )

    changes: list[dict[str, Any]] = []
    rms_rule = "CDA-DEEPSEEK-RMSNORM-STAGE-TOPOLOGY-OWNER-001"
    for remote_id, sfu_id in zip(
        rms_remote_ids, rms_sfu_ids, strict=True
    ):
        remote = operators[remote_id]
        sfu = operators[sfu_id]
        remote_a = remote.get("inputs", {}).get("A")
        sfu_a = sfu.get("inputs", {}).get("A")
        expected_source = f"op{int(remote_id[2:]) - 1}"
        if (
            remote.get("type")
            != "prefill_remote_sum_fp32MN_fp32MN"
            or remote.get("used_slices") != RAW_SINGLE_LEADER_MASK
            or not isinstance(remote_a, dict)
            or remote_a.get("shape")
            != [1, "used_slices", "sequence_length"]
            or remote_a.get("source") != expected_source
            or "type" in remote_a
            or sfu.get("type") != "prefill_mac_SFU_fp32MN_fp32MN"
            or not isinstance(sfu_a, dict)
            or sfu_a.get("source") != remote_id
            or sfu_a.get("type") != "slice0"
        ):
            raise DeepSeekPrefillStageProducerError(
                f"raw RMSNorm occurrence differs at {remote_id}/{sfu_id}"
            )
        _record_change(
            changes,
            f"operators.{remote_id}.used_slices",
            remote["used_slices"],
            ALL_28_MASK,
            rms_rule,
        )
        remote["used_slices"] = ALL_28_MASK
        _record_change(
            changes,
            f"operators.{remote_id}.inputs.A.shape",
            remote_a["shape"],
            [1, "slice_per_head", "sequence_length"],
            rms_rule,
        )
        remote_a["shape"] = [1, "slice_per_head", "sequence_length"]
        _record_change(
            changes,
            f"operators.{remote_id}.inputs.A.type",
            "<missing>",
            "slice0",
            rms_rule,
        )
        remote_a["type"] = "slice0"
        _record_change(
            changes,
            f"operators.{sfu_id}.inputs.A.type",
            "slice0",
            "<missing>",
            rms_rule,
        )
        sfu_a.pop("type")

    softmax_mac_ids = _ids_for_label(listing, "softmax::op0")
    softmax_exp_ids = _ids_for_label(listing, "softmax::op2")
    if softmax_mac_ids != ["op24"] or softmax_exp_ids != ["op26"]:
        raise DeepSeekPrefillStageProducerError(
            "prefill Softmax occurrences differ"
        )
    softmax_mac_c = operators["op24"].get("inputs", {}).get("C")
    softmax_exp_a = operators["op26"].get("inputs", {}).get("A")
    if (
        not isinstance(softmax_mac_c, dict)
        or softmax_mac_c.get("write_reg_hint") is not None
        or not isinstance(softmax_exp_a, dict)
        or softmax_exp_a.get("write_reg_hint") is not None
    ):
        raise DeepSeekPrefillStageProducerError(
            "raw Softmax layout-hint boundary differs"
        )
    _record_change(
        changes,
        "operators.op24.inputs.C.write_reg_hint",
        "<missing>",
        SOFTMAX_MASK_LAYOUT_HINT,
        "CDA-DEEPSEEK-SOFTMAX-MASK-STRIDE-OWNER-001",
    )
    softmax_mac_c["write_reg_hint"] = SOFTMAX_MASK_LAYOUT_HINT
    _record_change(
        changes,
        "operators.op26.inputs.A.write_reg_hint",
        "<missing>",
        SOFTMAX_EXP_LAYOUT_HINT,
        "CDA-DEEPSEEK-SOFTMAX-EXP-BUFFER-LAYOUT-001",
    )
    softmax_exp_a["write_reg_hint"] = SOFTMAX_EXP_LAYOUT_HINT

    gemm_ids = _ids_for_label(listing, "gemm_ring_ffn_gate::op0")
    if gemm_ids != ["op37"]:
        raise DeepSeekPrefillStageProducerError(
            "prefill FFN gate GEMM occurrence differs"
        )
    gemm = operators["op37"]
    gemm_a = gemm.get("inputs", {}).get("A")
    gemm_b = gemm.get("inputs", {}).get("B")
    if (
        gemm.get("type") != "prefill_gemm_ring_4slice"
        or not isinstance(gemm_a, dict)
        or gemm_a.get("write_reg_hint") is not None
        or not isinstance(gemm_b, dict)
        or gemm_b.get("write_reg_hint") is not None
    ):
        raise DeepSeekPrefillStageProducerError(
            "raw FFN gate GEMM layout-hint boundary differs"
        )
    _record_change(
        changes,
        "operators.op37.inputs.A.write_reg_hint",
        None,
        GEMM_A_LAYOUT_HINT,
        "CDA-DEEPSEEK-LAYOUT-HINT-OWNER-001",
    )
    gemm_a["write_reg_hint"] = GEMM_A_LAYOUT_HINT
    _record_change(
        changes,
        "operators.op37.inputs.B.write_reg_hint",
        None,
        GEMM_B_LAYOUT_HINT,
        "CDA-DEEPSEEK-LAYOUT-HINT-OWNER-001",
    )
    gemm_b["write_reg_hint"] = GEMM_B_LAYOUT_HINT

    if len(changes) != 12:
        raise DeepSeekPrefillStageProducerError(
            f"normalized Stage change count differs: {len(changes)}"
        )
    return graph, changes


def build_prefill_stage_producer_contract(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    graph, changes = build_rule_normalized_prefill_stage(root)
    output = root / OUTPUT_PATH
    if not output.is_file() or _load(output) != graph:
        raise DeepSeekPrefillStageProducerError(
            "checked normalized prefill Stage differs from producer"
        )
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "LOCAL_E2_ACTIVE_STAGE_PRODUCER_READY",
        "candidate_release": False,
        "formal_target_config": False,
        "server_package_generated": False,
        "identity_boundary": {
            "onnx_repository_classification": "SEMANTIC_MODEL_MATCH",
            "original_source_identity": False,
            "crop_contract_required": True,
        },
        "inputs": {
            "raw_prefill_graph": _binding(root, RAW_GRAPH_PATH),
            "operator_listing": _binding(root, OP_LISTING_PATH),
            "crop_contract": _binding(
                root,
                "contracts/operator_config/"
                "deepseek_ndpsim_crop_contract_v1.json",
            ),
            "rmsnorm_rule": _binding(root, RMS_RULE_PATH),
            "softmax_rule": _binding(root, SOFTMAX_RULE_PATH),
            "lifecycle_rule": _binding(root, LIFECYCLE_RULE_PATH),
        },
        "output": _binding(root, OUTPUT_PATH),
        "normalization_changes": changes,
        "normalization_change_count": len(changes),
        "closed_blockers": [
            "B_DS_RMSNORM_STAGE_TOPOLOGY_GAP",
            "B_DS_SOFTMAX_STAGE_LAYOUT_HINT_GAP",
            "B_DS_GEMM_LAYOUT_HINT_STAGE_GAP",
        ],
        "upstream_boundary": {
            "raw_upstream_graph_modified": False,
            "raw_upstream_graph_is_active_stage_output": False,
            "rule_normalized_output_is_active_stage_output": True,
            "unlisted_leaf_changes_allowed": False,
        },
        "rule_ids": sorted(
            {str(item["rule_id"]) for item in changes}
        ),
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_prefill_stage_producer_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_prefill_stage_producer_contract(project_root):
        raise DeepSeekPrefillStageProducerError(
            "DeepSeek prefill Stage producer contract differs"
        )


__all__ = [
    "CONTRACT_PATH",
    "DeepSeekPrefillStageProducerError",
    "GEMM_A_LAYOUT_HINT",
    "GEMM_B_LAYOUT_HINT",
    "OUTPUT_PATH",
    "SOFTMAX_EXP_LAYOUT_HINT",
    "SOFTMAX_MASK_LAYOUT_HINT",
    "build_prefill_stage_producer_contract",
    "build_rule_normalized_prefill_stage",
    "validate_prefill_stage_producer_contract",
]
