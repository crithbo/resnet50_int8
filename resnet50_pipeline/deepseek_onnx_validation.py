from __future__ import annotations

import ast
import importlib
import json
import math
import struct
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .deepseek_stage_ir import validate_deepseek_stage_ir
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .ndpsim_native import _native_module, load_native_execution_plan


CROP_SCHEMA = "deepseek-ndpsim-explicit-crop-contract-v1"
STAGE_MAPPING_SCHEMA = "deepseek-onnx-to-ndpsim-stage-mapping-v1"
PREFILL_STAGE_AUDIT_SCHEMA = "deepseek-onnx-prefill-stage-audit-v1"
OFFICIAL_SOURCE_CONFIG_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/source/"
    "official_model/config.json"
)
ONNX_CONVERSION_CONFIG_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/source/config.json"
)
TARGET_CONFIG_PATH = "ndp-sim/generate_python_golden/config.json"
WEIGHT_CROP_PRODUCER_PATH = "ndp-sim/generate_python_golden/weight_gen.py"
LAYER_CONSUMER_PATH = (
    "ndp-sim/generate_python_golden/decode_data_loader.py"
)
READ_RECEIPT_PATH = (
    "contracts/operator_config/"
    "deepseek_onnx_stage_validation_read_receipt_v1.json"
)
SPECIALTY_RULE_PATH = ".agents/rules/DeepSeek_ONNX到Stage验证规则.md"
ONNX_INVENTORY_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/onnx_graph_inventory.json"
)
DECODE_PROGRAM_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/layer0_decode.generated.json"
)
CROP_CONTRACT_PATH = (
    "contracts/operator_config/deepseek_ndpsim_crop_contract_v1.json"
)
STAGE_IR_PATH = (
    "contracts/operator_config/deepseek_stage_ir_crosswalk_v1.json"
)
DECODE_PROGRAM_PRODUCER_PATH = (
    "ndp-sim/generate_python_golden/generate_decode_program_json.py"
)
DECODE_GOLDEN_PATH = "ndp-sim/generate_python_golden/decode_ops.py"
DECODE_GEMV_LOCAL_CONFIG = "ndp-sim/jsons/decode_gemv_local.json"
PREFILL_PROGRAM_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/layer0_prefill.generated.json"
)
PREFILL_PROGRAM_LISTING_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/"
    "layer0_prefill.generated_op_listing.json"
)
PREFILL_PROGRAM_PRODUCER_PATH = (
    "ndp-sim/model_execplan/gen_layer0_oplist.py"
)
PREFILL_NUMERIC_GOLDEN_PATH = (
    "ndp-sim/generate_python_golden/"
    "deepseek1.5b_3_time_golden_smallsize_0527.py"
)
PREFILL_RELAYOUT_LAYER_PATH = (
    "ndp-sim/generate_python_golden/single_op_data/relayout_layer0.py"
)
PREFILL_RELAYOUT_RMSNORM_PATH = (
    "ndp-sim/generate_python_golden/single_op_data/relayout_rmsnorm.py"
)
PREFILL_RELAYOUT_KV_MUL_PATH = (
    "ndp-sim/generate_python_golden/single_op_data/"
    "relayout_mul_MN_N_kv.py"
)
PREFILL_RELAYOUT_REGULAR_PATH = (
    "ndp-sim/generate_python_golden/single_op_data/relayout_regular.py"
)
PREFILL_RELAYOUT_GEMM_LOCAL_PATH = (
    "ndp-sim/generate_python_golden/single_op_data/relayout_gemm_local.py"
)
PREFILL_SOFTMAX_SCALE_PATH = (
    "ndp-sim/generate_python_golden/softmax_scale.bin"
)
PREFILL_QKT_CONFIG_PATH = "ndp-sim/jsons/prefill_gemm_local_qkt.json"
PREFILL_REMOTE4_CONFIG_PATH = (
    "ndp-sim/jsons/prefill_remote_sum_4slice_fp32MN_fp32MN.json"
)
PREFILL_SCALE_MASK_CONFIG_PATH = (
    "ndp-sim/jsons/prefill_mac_fp32MN_fp32MN_fp32MN.json"
)

SOURCE_MODEL = {
    "hidden_size": 1536,
    "intermediate_size": 8960,
    "num_attention_heads": 12,
    "num_key_value_heads": 2,
    "head_dim": 128,
    "num_hidden_layers": 28,
}
TARGET_MODEL = {
    "hidden_size": 896,
    "intermediate_size": 1792,
    "num_attention_heads": 7,
    "num_key_value_heads": 1,
    "head_dim": 128,
    "num_hidden_layers": 1,
    "used_slices": 28,
    "slice_per_head": 4,
}
SEMANTIC_MODEL_FIELDS = (
    "architectures",
    "attention_dropout",
    "bos_token_id",
    "eos_token_id",
    "hidden_act",
    "hidden_size",
    "intermediate_size",
    "max_position_embeddings",
    "max_window_layers",
    "model_type",
    "num_attention_heads",
    "num_hidden_layers",
    "num_key_value_heads",
    "rms_norm_eps",
    "rope_theta",
    "tie_word_embeddings",
    "torch_dtype",
    "use_cache",
    "use_mrope",
    "use_sliding_window",
    "vocab_size",
)


class DeepSeekOnnxValidationError(ValueError):
    pass


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekOnnxValidationError(
            f"cannot parse JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DeepSeekOnnxValidationError(
            f"JSON root must be an object: {path}"
        )
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise DeepSeekOnnxValidationError(
            f"required crop evidence is missing: {relative}"
        )
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _validate_read_receipt(project_root: Path) -> dict[str, Any]:
    receipt = _load_object(project_root / READ_RECEIPT_PATH)
    sections = (
        "rules_read",
        "native_sources_read",
        "prefill_graph_fragments_read",
        "trusted_prefill_jsons_inspected",
        "project_consumers_read",
        "machine_inputs_bound",
    )
    checked = 0
    for section in sections:
        entries = receipt.get(section)
        if not isinstance(entries, list):
            raise DeepSeekOnnxValidationError(
                f"read receipt section is missing: {section}"
            )
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise DeepSeekOnnxValidationError(
                    f"read receipt entry is malformed: {section}"
                )
            relative = entry.get("path")
            expected_size = entry.get("size_bytes")
            expected_sha = entry.get("sha256")
            if (
                not isinstance(relative, str)
                or not isinstance(expected_size, int)
                or not isinstance(expected_sha, str)
            ):
                raise DeepSeekOnnxValidationError(
                    f"read receipt binding is malformed: {section}"
                )
            actual = _binding(project_root, relative)
            if (
                actual["size_bytes"] != expected_size
                or actual["sha256"] != expected_sha
            ):
                raise DeepSeekOnnxValidationError(
                    f"read receipt binding differs: {relative}"
                )
            checked += 1
    if receipt.get("receipt_status") != "SILU_HOLDOUT_MATERIALIZATION_READY":
        raise DeepSeekOnnxValidationError(
            "read receipt status does not authorize the current DeepSeek "
            "prefill audit and isolated SiLU materialization"
        )
    return {"checked_file_count": checked, "status": receipt["receipt_status"]}


def _require_model_values(
    actual: Mapping[str, Any],
    expected: Mapping[str, int],
    *,
    label: str,
) -> None:
    for key, expected_value in expected.items():
        value = actual.get(key)
        if isinstance(value, bool) or value != expected_value:
            raise DeepSeekOnnxValidationError(
                f"{label} {key} differs: {value!r} != {expected_value}"
            )


def _crop_rules() -> list[dict[str, Any]]:
    return [
        {
            "tensor_family": "attention_or_ffn_norm_weight",
            "source_shape": [1536],
            "target_shape": [896],
            "axis_slices": [[0, 896]],
            "consumer_layout": "Fortran-order, trailing singleton axes allowed",
        },
        {
            "tensor_family": "attention_q_or_output_weight",
            "source_shape": [1536, 1536],
            "target_shape": [896, 896],
            "axis_slices": [[0, 896], [0, 896]],
            "consumer_layout": "Fortran-order",
        },
        {
            "tensor_family": "attention_k_or_v_weight",
            "source_shape": [1536, 256],
            "target_shape": [896, 128],
            "axis_slices": [[0, 896], [0, 128]],
            "consumer_layout": "Fortran-order",
        },
        {
            "tensor_family": "ffn_gate_or_up_weight",
            "source_shape": [1536, 8960],
            "target_shape": [896, 1792],
            "axis_slices": [[0, 896], [0, 1792]],
            "consumer_layout": "Fortran-order",
        },
        {
            "tensor_family": "ffn_down_weight",
            "source_shape": [8960, 1536],
            "target_shape": [1792, 896],
            "axis_slices": [[0, 1792], [0, 896]],
            "consumer_layout": "Fortran-order",
        },
        {
            "tensor_family": "attention_q_bias",
            "source_shape": [1536],
            "target_shape": [896],
            "axis_slices": [[0, 896]],
            "consumer_layout": "Fortran-order",
        },
        {
            "tensor_family": "attention_k_or_v_bias",
            "source_shape": [256],
            "target_shape": [128],
            "axis_slices": [[0, 128]],
            "consumer_layout": "Fortran-order",
        },
    ]


def _validate_crop_rules(rules: list[dict[str, Any]]) -> None:
    if len(rules) != 7:
        raise DeepSeekOnnxValidationError("crop rule inventory differs")
    names: set[str] = set()
    for rule in rules:
        name = str(rule["tensor_family"])
        if name in names:
            raise DeepSeekOnnxValidationError(
                f"duplicate crop tensor family: {name}"
            )
        names.add(name)
        source_shape = rule["source_shape"]
        target_shape = rule["target_shape"]
        slices = rule["axis_slices"]
        if not (
            isinstance(source_shape, list)
            and isinstance(target_shape, list)
            and isinstance(slices, list)
            and len(source_shape) == len(target_shape) == len(slices)
        ):
            raise DeepSeekOnnxValidationError(
                f"crop rank differs for {name}"
            )
        for axis, (source_dim, target_dim, bounds) in enumerate(
            zip(source_shape, target_shape, slices, strict=True)
        ):
            if (
                not isinstance(bounds, list)
                or len(bounds) != 2
                or bounds[0] != 0
                or bounds[1] != target_dim
                or target_dim > source_dim
            ):
                raise DeepSeekOnnxValidationError(
                    f"crop bounds differ for {name} axis {axis}"
                )


def _validate_source_implementation(
    crop_source: str, layer_consumer_source: str
) -> None:
    required_crop_fragments = (
        'orig_weights_folder = os.path.join(base_dir, "DeepSeek-R1-Distill-Qwen-1.5B-f16")',
        "orig_tensor_sq[:H_TGT]",
        "orig_tensor_sq[:H_TGT, :H_TGT]",
        "orig_tensor_sq[:H_TGT, :new_d1]",
        "orig_tensor_sq[:H_TGT, :I_TGT]",
        "orig_tensor_sq[:I_TGT, :H_TGT]",
        "tensor.flatten(order='F').tofile(filepath)",
    )
    missing_crop = [
        fragment
        for fragment in required_crop_fragments
        if fragment not in crop_source
    ]
    if missing_crop:
        raise DeepSeekOnnxValidationError(
            "weight crop implementation differs; missing fragments: "
            + repr(missing_crop)
        )
    required_consumer_fragments = (
        'pfx = f"blk.{layer_idx}"',
        "w = load_layer_weights(0)",
        'data.reshape(dims, order="F")',
    )
    missing_consumer = [
        fragment
        for fragment in required_consumer_fragments
        if fragment not in layer_consumer_source
    ]
    if missing_consumer:
        raise DeepSeekOnnxValidationError(
            "layer-0 consumer differs; missing fragments: "
            + repr(missing_consumer)
        )


def build_deepseek_crop_contract(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    receipt_validation = _validate_read_receipt(root)
    official_source = _load_object(root / OFFICIAL_SOURCE_CONFIG_PATH)
    onnx_conversion = _load_object(root / ONNX_CONVERSION_CONFIG_PATH)
    target = _load_object(root / TARGET_CONFIG_PATH)
    _require_model_values(
        official_source,
        {
            key: value
            for key, value in SOURCE_MODEL.items()
            if key != "head_dim"
        },
        label="source model",
    )
    _require_model_values(
        onnx_conversion,
        {
            key: value
            for key, value in SOURCE_MODEL.items()
            if key != "head_dim"
        },
        label="ONNX conversion model",
    )
    source_head_dim = (
        official_source["hidden_size"]
        // official_source["num_attention_heads"]
    )
    if (
        official_source["hidden_size"]
        % official_source["num_attention_heads"]
        != 0
        or source_head_dim != SOURCE_MODEL["head_dim"]
    ):
        raise DeepSeekOnnxValidationError(
            "source head_dim cannot be derived as 128"
        )
    _require_model_values(target, TARGET_MODEL, label="NDP target")
    semantic_differences = {
        field: {
            "official": deepcopy(official_source.get(field)),
            "onnx_conversion": deepcopy(onnx_conversion.get(field)),
        }
        for field in SEMANTIC_MODEL_FIELDS
        if official_source.get(field) != onnx_conversion.get(field)
    }
    if semantic_differences:
        raise DeepSeekOnnxValidationError(
            "ONNX conversion semantic model fields differ: "
            + repr(semantic_differences)
        )
    if (
        onnx_conversion.get("_name_or_path")
        != "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"
    ):
        raise DeepSeekOnnxValidationError(
            "ONNX conversion declared source differs"
        )
    if official_source.get("use_sliding_window") is not False:
        raise DeepSeekOnnxValidationError(
            "sliding-window delta is not proven inactive"
        )

    if (
        target["num_attention_heads"] * target["head_dim"]
        != target["hidden_size"]
    ):
        raise DeepSeekOnnxValidationError(
            "target query heads do not cover hidden_size"
        )
    if (
        target["num_key_value_heads"] * target["head_dim"] != 128
    ):
        raise DeepSeekOnnxValidationError(
            "target KV heads do not produce the 128-wide crop"
        )
    if (
        target["num_attention_heads"] * target["slice_per_head"]
        != target["used_slices"]
    ):
        raise DeepSeekOnnxValidationError(
            "target head-to-slice topology differs"
        )
    if target["hidden_size"] % target["used_slices"] != 0:
        raise DeepSeekOnnxValidationError(
            "target hidden_size is not exactly divisible by used_slices"
        )
    if target["intermediate_size"] % target["used_slices"] != 0:
        raise DeepSeekOnnxValidationError(
            "target intermediate_size is not exactly divisible by used_slices"
        )

    crop_source_path = root / WEIGHT_CROP_PRODUCER_PATH
    layer_consumer_path = root / LAYER_CONSUMER_PATH
    crop_source = crop_source_path.read_text(encoding="utf-8")
    layer_consumer_source = layer_consumer_path.read_text(encoding="utf-8")
    _validate_source_implementation(crop_source, layer_consumer_source)

    crop_rules = _crop_rules()
    _validate_crop_rules(crop_rules)
    payload: dict[str, Any] = {
        "schema": CROP_SCHEMA,
        "status": "explicit_crop_contract_locally_closed",
        "identity_boundary": {
            "onnx_identity_classification": "SEMANTIC_MODEL_MATCH",
            "original_source_identity": False,
            "ndpsim_weight_origin_proven": False,
            "direct_equal_shape_claim": False,
            "crop_required": True,
        },
        "inputs": {
            "read_receipt": _binding(root, READ_RECEIPT_PATH),
            "specialty_rule": _binding(root, SPECIALTY_RULE_PATH),
            "official_source_model_config": _binding(
                root, OFFICIAL_SOURCE_CONFIG_PATH
            ),
            "onnx_conversion_config": _binding(
                root, ONNX_CONVERSION_CONFIG_PATH
            ),
            "target_ndp_config": _binding(root, TARGET_CONFIG_PATH),
            "weight_crop_producer": _binding(
                root, WEIGHT_CROP_PRODUCER_PATH
            ),
            "layer0_consumer": _binding(root, LAYER_CONSUMER_PATH),
        },
        "read_receipt_validation": receipt_validation,
        "model_dimensions": {
            "source": deepcopy(SOURCE_MODEL),
            "target": deepcopy(TARGET_MODEL),
            "derived": {
                "query_width": 896,
                "kv_width": 128,
                "hidden_elements_per_slice": 32,
                "intermediate_elements_per_slice": 64,
                "active_slice_count": 28,
            },
        },
        "semantic_model_match": {
            "exact_fields": list(SEMANTIC_MODEL_FIELDS),
            "conversion_declared_source": onnx_conversion.get(
                "_name_or_path"
            ),
            "non_semantic_or_inactive_deltas": {
                "sliding_window": {
                    "official": official_source.get("sliding_window"),
                    "onnx_conversion": onnx_conversion.get(
                        "sliding_window"
                    ),
                    "inactive_because_use_sliding_window": False,
                },
                "transformers_version": {
                    "official": official_source.get(
                        "transformers_version"
                    ),
                    "onnx_conversion": onnx_conversion.get(
                        "transformers_version"
                    ),
                },
            },
        },
        "layer_selection": {
            "source_layer_count": 28,
            "target_layer_count": 1,
            "selected_source_layers": [0],
            "crop_producer_removes_unselected_layers": False,
            "consumer_selects_layer0_by_name": True,
            "rule": (
                "dimension cropping and layer selection are separate; "
                "num_hidden_layers=1 alone is not layer-selection evidence"
            ),
        },
        "tensor_crop_rules": crop_rules,
        "layout": {
            "raw_weight_input": "numpy reshape(order='F')",
            "cropped_weight_output": "numpy flatten(order='F')",
            "decode_consumer": "numpy reshape(order='F')",
            "axis_order_change": False,
        },
        "release_boundary": {
            "maximum_evidence_level": "E2",
            "formal_target_config": False,
            "server_dynamic_claim": False,
            "open_confirmation": [
                "ONNX Community conversion is not proven as the byte-identical source of ndp-sim extracted weights.",
                "The crop contract must remain explicit until its model/source provenance is independently confirmed.",
            ],
        },
        "rule_ids": [
            "CDA-DEEPSEEK-MODEL-IDENTITY-001",
            "CDA-DEEPSEEK-CROP-EXPLICIT-001",
        ],
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_deepseek_crop_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_deepseek_crop_contract(project_root):
        raise DeepSeekOnnxValidationError(
            "DeepSeek crop contract differs from current evidence"
        )


def write_deepseek_crop_contract(
    path: Path, value: Mapping[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _node_by_name(
    inventory: Mapping[str, Any], name: str
) -> Mapping[str, Any]:
    matches = [
        item
        for item in inventory.get("graph", {}).get("nodes", [])
        if isinstance(item, Mapping) and item.get("name") == name
    ]
    if len(matches) != 1:
        raise DeepSeekOnnxValidationError(
            f"ONNX graph does not contain exactly one node: {name}"
        )
    return matches[0]


def _attribute_map(node: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(item["name"]): deepcopy(item.get("value"))
        for item in node.get("attributes", [])
        if isinstance(item, Mapping) and "value" in item
    }


def _operator_by_id(
    graph: Mapping[str, Any], operator_id: str
) -> Mapping[str, Any]:
    matches = [
        item
        for item in graph.get("operators", [])
        if isinstance(item, Mapping) and item.get("id") == operator_id
    ]
    if len(matches) != 1:
        raise DeepSeekOnnxValidationError(
            f"decode graph does not contain exactly one operator: "
            f"{operator_id}"
        )
    return matches[0]


def _source_operator(
    graph: Mapping[str, Any], operator_id: str, port: str
) -> str | None:
    operator = _operator_by_id(graph, operator_id)
    source = operator.get("inputs", {}).get(port, {}).get("source")
    if not isinstance(source, Mapping):
        raise DeepSeekOnnxValidationError(
            f"decode source is malformed: {operator_id}:{port}"
        )
    if source.get("type") == "external":
        return None
    return str(source.get("operator_id"))


def _slice_count(operator: Mapping[str, Any]) -> int:
    mask = operator.get("used_slices")
    if not isinstance(mask, str) or not mask.startswith("0b"):
        raise DeepSeekOnnxValidationError(
            f"decode slice mask is malformed: {operator.get('id')}"
        )
    return int(mask[2:], 2).bit_count()


def _load_decode_module(root: Path) -> Any:
    module_dir = root / "ndp-sim/generate_python_golden"
    module_dir_text = str(module_dir.resolve())
    if module_dir_text not in sys.path:
        sys.path.insert(0, module_dir_text)
    module = importlib.import_module("decode_ops")
    module_path = Path(str(getattr(module, "__file__", ""))).resolve()
    if module_path != (root / DECODE_GOLDEN_PATH).resolve():
        raise DeepSeekOnnxValidationError(
            f"decode_ops imported from another source: {module_path}"
        )
    return module


def _softmax_partition_counterexample(root: Path) -> dict[str, Any]:
    decode_ops = _load_decode_module(root)
    heads = 7
    slices_per_head = 4
    attention_length = 32
    scores = np.arange(
        attention_length * heads, dtype=np.float32
    ).reshape(attention_length, heads, order="F")
    maxima = decode_ops.head_local_maxima(
        scores, heads, slices_per_head
    )
    width = attention_length // slices_per_head
    centered = np.empty_like(scores)
    for head in range(heads):
        for local_slice in range(slices_per_head):
            start = local_slice * width
            end = (local_slice + 1) * width
            centered[start:end, head] = (
                scores[start:end, head] - maxima[local_slice, head]
            )
    exponentials = np.exp(centered).astype(np.float32)
    reciprocals = decode_ops.head_local_sum_reciprocals(
        exponentials, heads, slices_per_head
    )
    probabilities = np.empty_like(exponentials)
    for head in range(heads):
        for local_slice in range(slices_per_head):
            start = local_slice * width
            end = (local_slice + 1) * width
            probabilities[start:end, head] = (
                exponentials[start:end, head]
                * reciprocals[local_slice, head]
            )
    per_head_sums = probabilities.sum(axis=0, dtype=np.float64)
    if not np.allclose(per_head_sums, slices_per_head):
        raise DeepSeekOnnxValidationError(
            "decode softmax counterexample no longer exposes local "
            "normalization"
        )
    return {
        "input_shape": [attention_length, heads],
        "slices_per_head": slices_per_head,
        "local_width": width,
        "actual_probability_sum_per_head": [
            float(value) for value in per_head_sums
        ],
        "required_probability_sum_per_head": [1.0] * heads,
        "counterexample_proven": True,
    }


def _manifest_load_count(program_source: str) -> dict[str, int]:
    tree = ast.parse(program_source)
    stores = 0
    loads = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "manifest":
            if isinstance(node.ctx, ast.Store):
                stores += 1
            elif isinstance(node.ctx, ast.Load):
                loads += 1
    return {"stores": stores, "loads_after_parse": loads}


def _initializer_by_name(
    inventory: Mapping[str, Any], name: str
) -> Mapping[str, Any]:
    matches = [
        item
        for item in inventory.get("graph", {}).get("initializers", [])
        if isinstance(item, Mapping) and item.get("name") == name
    ]
    if len(matches) != 1:
        raise DeepSeekOnnxValidationError(
            f"ONNX initializer does not resolve uniquely: {name}"
        )
    return matches[0]


def build_deepseek_onnx_stage_mapping(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    receipt_validation = _validate_read_receipt(root)
    crop_contract = _load_object(root / CROP_CONTRACT_PATH)
    validate_deepseek_crop_contract(crop_contract, root)
    inventory = _load_object(root / ONNX_INVENTORY_PATH)
    stage_ir = _load_object(root / STAGE_IR_PATH)
    validate_deepseek_stage_ir(stage_ir, root)
    decode_graph = load_native_execution_plan(root, DECODE_PROGRAM_PATH)
    program_source = (root / DECODE_PROGRAM_PRODUCER_PATH).read_text(
        encoding="utf-8"
    )
    golden_source = (root / DECODE_GOLDEN_PATH).read_text(
        encoding="utf-8"
    )

    graph_summary = inventory.get("graph", {})
    expected_counts = {
        "Add": 28,
        "Cast": 3,
        "Constant": 2,
        "Gather": 2,
        "GroupQueryAttention": 28,
        "MatMul": 141,
        "Mul": 56,
        "ReduceSum": 1,
        "Shape": 1,
        "Sigmoid": 28,
        "SimplifiedLayerNormalization": 1,
        "SkipSimplifiedLayerNormalization": 56,
        "Sub": 1,
    }
    if (
        graph_summary.get("node_count") != 348
        or graph_summary.get("op_type_counts") != expected_counts
    ):
        raise DeepSeekOnnxValidationError(
            "pinned ONNX graph inventory differs"
        )

    layer0_names = [
        "/model/layers.0/input_layernorm/LayerNorm",
        "/model/layers.0/attn/qkv_proj/MatMul",
        "/model/layers.0/attn/qkv_proj/Add",
        "/model/layers.0/attn/GroupQueryAttention",
        "/model/layers.0/attn/o_proj/MatMul",
        "/model/layers.0/post_attention_layernorm/SkipLayerNorm",
        "/model/layers.0/mlp/gate_proj/MatMul",
        "/model/layers.0/mlp/up_proj/MatMul",
        "/model/layers.0/mlp/act_fn/Sigmoid",
        "/model/layers.0/mlp/act_fn/Mul",
        "/model/layers.0/mlp/Mul",
        "/model/layers.0/mlp/down_proj/MatMul",
    ]
    layer0_nodes = [_node_by_name(inventory, name) for name in layer0_names]
    if [int(item["index"]) for item in layer0_nodes] != list(range(9, 21)):
        raise DeepSeekOnnxValidationError(
            "ONNX layer0 node order differs"
        )
    gqa = layer0_nodes[3]
    gqa_attributes = _attribute_map(gqa)
    expected_scale = 1.0 / math.sqrt(128.0)
    if (
        gqa.get("domain") != "com.microsoft"
        or gqa_attributes.get("num_heads") != 12
        or gqa_attributes.get("kv_num_heads") != 2
        or gqa_attributes.get("do_rotary") != 1
        or gqa_attributes.get("rotary_interleaved") != 0
        or not math.isclose(
            float(gqa_attributes.get("scale")),
            expected_scale,
            rel_tol=0.0,
            abs_tol=1e-8,
        )
    ):
        raise DeepSeekOnnxValidationError(
            "ONNX GQA attributes differ"
        )

    qkv_weight = _initializer_by_name(
        inventory, "model.layers.0.attn.qkv_proj.MatMul.weight"
    )
    qkv_bias = _initializer_by_name(
        inventory, "model.layers.0.attn.qkv_proj.Add.bias"
    )
    if qkv_weight.get("dims") != [1536, 2048]:
        raise DeepSeekOnnxValidationError("ONNX fused QKV weight differs")
    if qkv_bias.get("dims") != [2048]:
        raise DeepSeekOnnxValidationError("ONNX fused QKV bias differs")

    operators = decode_graph.get("operators", [])
    if len(operators) != 43:
        raise DeepSeekOnnxValidationError(
            f"decode Stage DAG count differs: {len(operators)}"
        )
    stage_counts = Counter(
        str(item["type"])
        for item in operators
        if isinstance(item, Mapping)
    )
    unique_stage_types = sorted(stage_counts)
    authority: dict[str, Any] = {}
    for stage_type in unique_stage_types:
        crosswalk = stage_ir.get("template_crosswalk", {}).get(stage_type)
        if (
            not isinstance(crosswalk, Mapping)
            or crosswalk.get("configuration_authority", {}).get(
                "accepted_as_correct_reference"
            )
            is not True
            or crosswalk.get("configuration_authority", {}).get(
                "provenance", {}
            ).get("kind")
            != "pinned_upstream_exact_blob"
        ):
            raise DeepSeekOnnxValidationError(
                f"decode stage lacks trusted JSON authority: {stage_type}"
            )
        authority[stage_type] = deepcopy(
            crosswalk["configuration_authority"]
        )

    decode_ops = _load_decode_module(root)
    registry_mismatches = [
        {
            "stage_type": spec.name,
            "registry_hardware_json": spec.hardware_json,
            "exact_stage_json": f"{spec.name}.json",
        }
        for spec in decode_ops.SUPPORTED_DECODE_OPERATORS
        if spec.hardware_json != f"{spec.name}.json"
    ]
    if not registry_mismatches:
        raise DeepSeekOnnxValidationError(
            "expected decode registry JSON identity counterexamples missing"
        )

    gemv_local = _load_object(root / DECODE_GEMV_LOCAL_CONFIG)
    gemv_ga_ops = sorted(
        {
            str(value.get("alu_opcode"))
            for value in gemv_local.get("general_array", {})
            .get("PE_array", {})
            .values()
            if isinstance(value, Mapping)
        }
    )
    if gemv_local.get("n2n") is not None or gemv_ga_ops != ["sum"]:
        raise DeepSeekOnnxValidationError(
            "decode GEMV-local topology differs"
        )

    manifest_usage = _manifest_load_count(program_source)
    if manifest_usage != {"stores": 1, "loads_after_parse": 0}:
        raise DeepSeekOnnxValidationError(
            "decode program manifest usage differs"
        )
    required_golden_fragments = {
        "qkt_unscaled": (
            "scores_fp32 = gemv_fp32_accumulate("
        ),
        "qkt_remote_scalar": (
            "op23_out = np.asarray([remote_sum_fp32("
            "attn_scores_2d.reshape(-1))]"
        ),
        "sv_uses_current_v_not_softmax": (
            "(sv_weight.reshape(head_dim, attention_length, heads, "
            "order=\"F\"),\n          v_cur.reshape("
        ),
        "attention_residual_uses_q_bias": (
            "op31_out = _elementwise_add(op30_out, res_q)"
        ),
    }
    missing_fragments = [
        name
        for name, fragment in required_golden_fragments.items()
        if fragment not in golden_source
    ]
    if missing_fragments:
        raise DeepSeekOnnxValidationError(
            "decode golden counterexample source differs: "
            + repr(missing_fragments)
        )

    softmax_counterexample = _softmax_partition_counterexample(root)
    kv_stage_ids = ["op10", "op11", "op12", "op13", "op14", "op15", "op20"]
    kv_stage_slice_counts = {
        operator_id: _slice_count(
            _operator_by_id(decode_graph, operator_id)
        )
        for operator_id in kv_stage_ids
    }
    if kv_stage_slice_counts != {
        operator_id: (1 if operator_id == "op11" else 28)
        for operator_id in kv_stage_ids
    }:
        raise DeepSeekOnnxValidationError(
            "decode KV stage slice masks differ"
        )

    qkv_shared_input = {
        "q_projection_source": _source_operator(
            decode_graph, "op5", "A"
        ),
        "k_projection_source": _source_operator(
            decode_graph, "op15", "A"
        ),
        "v_projection_source": _source_operator(
            decode_graph, "op20", "A"
        ),
        "second_kv_norm_source": _source_operator(
            decode_graph, "op10", "A"
        ),
    }
    if qkv_shared_input != {
        "q_projection_source": "op4",
        "k_projection_source": "op14",
        "v_projection_source": "op14",
        "second_kv_norm_source": None,
    }:
        raise DeepSeekOnnxValidationError(
            "decode QKV source topology differs"
        )

    open_provenance = [
        {
            "id": "B_DS_ONNX_ORIGINAL_SOURCE_IDENTITY",
            "blocks_local_semantic_audit": False,
            "blocks_release_identity": True,
        },
        {
            "id": "B_DS_QKV_FUSED_EXTRACTION_IDENTITY",
            "blocks_local_semantic_audit": False,
            "blocks_release_identity": True,
            "evidence": {
                "onnx_weight_shape": [1536, 2048],
                "onnx_bias_shape": [2048],
                "semantic_ranges": {
                    "Q": [0, 1536],
                    "K": [1536, 1792],
                    "V": [1792, 2048],
                },
                "ndp_target_widths": {"Q": 896, "K": 128, "V": 128},
                "byte_extraction_proven": False,
            },
        },
    ]
    blockers = [
        {
            "id": "B_DS_QKV_SHARED_NORMALIZED_INPUT_IDENTITY",
            "classification": "STAGE_DAG",
            "evidence": qkv_shared_input,
        },
        {
            "id": "B_DS_KV_GQA_REPLICATION_IDENTITY",
            "classification": "TENSOR_LAYOUT",
            "evidence": {
                "logical_kv_width": 128,
                "logical_kv_heads": 1,
                "query_heads": 7,
                "slice_per_head": 4,
                "expected_physical_occurrences_if_replicated": 28,
                "program_slice_counts": kv_stage_slice_counts,
                "op15_output_per_slice": [1, 1, 32],
                "replication_manifest_bound": False,
            },
        },
        {
            "id": "B_DS_GQA_SCALE_MISSING",
            "classification": "NUMERIC_SEMANTICS",
            "evidence": {
                "onnx_scale": float(gqa_attributes["scale"]),
                "required_formula": "1/sqrt(head_dim)",
                "head_dim": 128,
                "decode_gemv_local_ga_opcodes": gemv_ga_ops,
                "decode_gemv_local_n2n": gemv_local.get("n2n"),
                "explicit_scale_stage": False,
            },
        },
        {
            "id": "B_DS_QKT_VECTOR_REDUCTION_ROUTE",
            "classification": "STAGE_DAG",
            "evidence": {
                "partial_stage": "op22",
                "consumer_stage": "op23",
                "partial_stage_slices": _slice_count(
                    _operator_by_id(decode_graph, "op22")
                ),
                "consumer_stage_slices": _slice_count(
                    _operator_by_id(decode_graph, "op23")
                ),
                "source": _source_operator(
                    decode_graph, "op23", "A"
                ),
                "route_or_n2n_proven": False,
            },
        },
        {
            "id": "B_DS_SOFTMAX_GLOBAL_NORMALIZATION",
            "classification": "NUMERIC_SEMANTICS",
            "evidence": softmax_counterexample,
        },
        {
            "id": "B_DS_DECODE_PROGRAM_GOLDEN_PARITY",
            "classification": "GOLDEN",
            "evidence": {
                "program_op23_output_shape": _operator_by_id(
                    decode_graph, "op23"
                )["output"]["shape"],
                "golden_op23_is_scalar": True,
                "program_op29_a_source": _source_operator(
                    decode_graph, "op29", "A"
                ),
                "golden_attn_sv_uses_op28": False,
            },
        },
        {
            "id": "B_DS_RESIDUAL_TENSOR_IDENTITY",
            "classification": "TENSOR_BINDING",
            "evidence": {
                "program_manifest_usage": manifest_usage,
                "op31_external_port": "A",
                "golden_op31_actual_value": "res_q (Q bias)",
                "required_value": "layer input residual",
            },
        },
        {
            "id": "B_DS_CURRENT_TOKEN_KV_LIFECYCLE",
            "classification": "LIFETIME",
            "evidence": {
                "past_length": 32,
                "onnx_total_length_after_current_token": 33,
                "ndp_decode_attention_length": 32,
                "current_k_stage": "op19",
                "current_v_stage": "op21",
                "qkt_k_source": _source_operator(
                    decode_graph, "op22", "B"
                ),
                "sv_v_source": _source_operator(
                    decode_graph, "op29", "B"
                ),
                "current_kv_visible_to_attention": False,
            },
        },
        {
            "id": "B_DS_DECODE_REGISTRY_JSON_IDENTITY",
            "classification": "CONFIG_PROVENANCE",
            "evidence": {
                "mismatch_count": len(registry_mismatches),
                "mismatches": registry_mismatches,
            },
        },
    ]

    payload: dict[str, Any] = {
        "schema": STAGE_MAPPING_SCHEMA,
        "status": "blocked_before_stage_to_json_generation",
        "candidate_release": False,
        "maximum_evidence_level": "E2",
        "inputs": {
            "read_receipt": _binding(root, READ_RECEIPT_PATH),
            "specialty_rule": _binding(root, SPECIALTY_RULE_PATH),
            "crop_contract": _binding(root, CROP_CONTRACT_PATH),
            "onnx_inventory": _binding(root, ONNX_INVENTORY_PATH),
            "decode_program": _binding(root, DECODE_PROGRAM_PATH),
            "decode_program_producer": _binding(
                root, DECODE_PROGRAM_PRODUCER_PATH
            ),
            "decode_golden": _binding(root, DECODE_GOLDEN_PATH),
            "trusted_stage_ir": _binding(root, STAGE_IR_PATH),
            "decode_gemv_local_json": _binding(
                root, DECODE_GEMV_LOCAL_CONFIG
            ),
        },
        "read_receipt_validation": receipt_validation,
        "onnx_layer0": {
            "node_indices": [int(item["index"]) for item in layer0_nodes],
            "node_names": layer0_names,
            "node_types": [str(item["op_type"]) for item in layer0_nodes],
            "gqa_attributes": gqa_attributes,
            "qkv_weight": deepcopy(dict(qkv_weight)),
            "qkv_bias": deepcopy(dict(qkv_bias)),
        },
        "ndpsim_stage_dag": {
            "operator_count": len(operators),
            "stage_type_counts": dict(sorted(stage_counts.items())),
            "unique_stage_type_count": len(unique_stage_types),
            "all_stage_types_have_trusted_json_authority": True,
            "trusted_stage_types": unique_stage_types,
        },
        "structurally_mapped_groups": [
            {
                "semantic": "input RMSNorm",
                "onnx_nodes": [layer0_names[0]],
                "ndp_stages": ["op0", "op1", "op2", "op3", "op4"],
                "status": "STRUCTURAL_MATCH",
            },
            {
                "semantic": "fused QKV projection and bias",
                "onnx_nodes": layer0_names[1:3],
                "ndp_stages": [
                    "op5",
                    "op6",
                    "op15",
                    "op16",
                    "op20",
                    "op21",
                ],
                "status": "BLOCKED",
            },
            {
                "semantic": "GQA RoPE, QKT, mask, Softmax and SV",
                "onnx_nodes": [layer0_names[3]],
                "ndp_stages": [
                    f"op{index}" for index in range(7, 30)
                ],
                "status": "BLOCKED",
            },
            {
                "semantic": "attention output projection and residual RMSNorm",
                "onnx_nodes": layer0_names[4:6],
                "ndp_stages": [
                    f"op{index}" for index in range(30, 37)
                ],
                "status": "BLOCKED",
            },
            {
                "semantic": "SwiGLU MLP and residual",
                "onnx_nodes": layer0_names[6:12],
                "ndp_stages": [
                    f"op{index}" for index in range(37, 43)
                ],
                "status": "STRUCTURAL_MATCH_WITH_NUMERIC_GATE_OPEN",
            },
        ],
        "blockers": blockers,
        "blocker_ids": [item["id"] for item in blockers],
        "open_provenance_confirmations": open_provenance,
        "policy_result": {
            "onnx_to_stage_ir_ready": False,
            "stage_to_json_forward_generation_allowed": False,
            "trusted_individual_json_semantics_invalidated": False,
            "reason": (
                "the individual JSON oracle remains trusted, but the current "
                "43-stage decode composition and golden do not implement the "
                "pinned ONNX layer semantics"
            ),
            "next_action": (
                "close tensor identity, QKV split/crop, KV slice mask, GQA "
                "scale, cross-slice reduction, global softmax, current-KV "
                "lifetime and program/golden parity before materializing "
                "representative stage JSON"
            ),
        },
        "rule_ids": [
            "CDA-DEEPSEEK-MODEL-IDENTITY-001",
            "CDA-DEEPSEEK-CROP-EXPLICIT-001",
            "CDA-DEEPSEEK-ONNX-STAGE-DAG-001",
            "CDA-DEEPSEEK-STAGE-JSON-ORACLE-001",
        ],
    }
    payload["mapping_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_deepseek_onnx_stage_mapping(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_deepseek_onnx_stage_mapping(project_root):
        raise DeepSeekOnnxValidationError(
            "DeepSeek ONNX-to-stage mapping differs from current evidence"
        )


def _native_prefill_plan_and_addresses(
    root: Path,
) -> tuple[Any, Any]:
    loader = _native_module(
        root, "execution_plan_generator.json_loader"
    )
    planner_module = _native_module(
        root, "execution_plan_generator.address_planner"
    )
    graph_path = root / PREFILL_PROGRAM_PATH
    try:
        plan = loader.load_execution_plan_json(graph_path)
        addresses = planner_module.AddressPlanner().plan(plan)
    except Exception as error:
        raise DeepSeekOnnxValidationError(
            f"native prefill address audit failed: {error}"
        ) from error
    return plan, addresses


def _native_source_slice_map(
    root: Path,
    *,
    consumer: Any,
    port: str,
) -> dict[int, int]:
    routing = _native_module(
        root, "execution_plan_generator.slice_routing"
    )
    tensor = consumer.inputs[port]
    return {
        slice_id: routing.resolve_io_base_addr_source_slice(
            op_type=consumer.op_type,
            io_type=tensor.special_type,
            write_slice_id=slice_id,
            io_role="input",
            io_name=port,
        )
        for slice_id in consumer.enabled_slice_ids()
    }


def _float32_from_int(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", value & 0xFFFFFFFF))[0]


def build_deepseek_prefill_stage_audit(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    receipt_validation = _validate_read_receipt(root)
    raw_graph = _load_object(root / PREFILL_PROGRAM_PATH)
    listing = _load_object(root / PREFILL_PROGRAM_LISTING_PATH)
    normalized = load_native_execution_plan(root, PREFILL_PROGRAM_PATH)
    inventory = _load_object(root / ONNX_INVENTORY_PATH)
    crop_contract = _load_object(root / CROP_CONTRACT_PATH)
    validate_deepseek_crop_contract(crop_contract, root)

    raw_operators = raw_graph.get("operators")
    operators = normalized.get("operators")
    if (
        not isinstance(raw_operators, list)
        or not isinstance(operators, list)
        or len(raw_operators) != 43
        or len(operators) != 43
        or len(listing) != 43
    ):
        raise DeepSeekOnnxValidationError(
            "prefill 43-stage graph or listing differs"
        )
    if raw_graph.get("used_slices") != 28:
        raise DeepSeekOnnxValidationError(
            "prefill raw top-level used_slices counterexample differs"
        )

    plan, addresses = _native_prefill_plan_and_addresses(root)
    native_by_id = {item.op_id: item for item in plan.operators}
    if len(native_by_id) != 43:
        raise DeepSeekOnnxValidationError(
            "native prefill operator IDs are not unique"
        )

    parsed_top_level_slices = plan.enabled_slice_ids()
    if parsed_top_level_slices != [2, 3, 4]:
        raise DeepSeekOnnxValidationError(
            "native parsing of top-level decimal 28 differs"
        )

    qkt = native_by_id["op22"]
    remote = native_by_id["op23"]
    scale_mask = native_by_id["op24"]
    remote_tensor_name = addresses.operator_io_to_tensor["op23.input.A"]
    remote_assignment = addresses.assignments[remote_tensor_name]
    requested_remote_bytes = (
        math.prod(remote.inputs["A"].shape) * 4
    )
    if (
        remote_tensor_name != "op22.output.D"
        or remote_assignment.size_bytes != 4096
        or requested_remote_bytes != 16384
    ):
        raise DeepSeekOnnxValidationError(
            "prefill QKT-to-remote byte-extent counterexample differs"
        )

    leader_routes: list[dict[str, Any]] = []
    for producer_id, consumer_id in (
        ("op1", "op2"),
        ("op11", "op12"),
        ("op23", "op24"),
        ("op33", "op34"),
    ):
        producer = native_by_id[producer_id]
        consumer = native_by_id[consumer_id]
        mapped = _native_source_slice_map(
            root, consumer=consumer, port="A"
        )
        producer_slices = set(producer.enabled_slice_ids())
        requested_slices = set(mapped.values())
        leader_routes.append(
            {
                "producer": producer_id,
                "consumer": consumer_id,
                "consumer_input_type": consumer.inputs["A"].special_type,
                "producer_enabled_slices": sorted(producer_slices),
                "consumer_source_slices": sorted(requested_slices),
                "missing_source_slices": sorted(
                    requested_slices - producer_slices
                ),
            }
        )
    if not all(item["missing_source_slices"] for item in leader_routes):
        raise DeepSeekOnnxValidationError(
            "expected prefill leader-slice routing mismatch is missing"
        )

    gqa = _node_by_name(
        inventory, "/model/layers.0/attn/GroupQueryAttention"
    )
    gqa_scale = float(_attribute_map(gqa)["scale"])
    scale_bytes = (root / PREFILL_SOFTMAX_SCALE_PATH).read_bytes()
    if len(scale_bytes) != 4:
        raise DeepSeekOnnxValidationError(
            "prefill softmax scale file is not one fp32"
        )
    scale_file_value = struct.unpack("<f", scale_bytes)[0]
    scale_config = _load_object(root / PREFILL_SCALE_MASK_CONFIG_PATH)
    scale_constants = {
        str(pe.get("inport1", {}).get("constant"))
        for pe in scale_config.get("general_array", {})
        .get("PE_array", {})
        .values()
        if isinstance(pe, Mapping)
    }
    if scale_constants != {"0x3db504f3"}:
        raise DeepSeekOnnxValidationError(
            "prefill scale-mask JSON constants differ"
        )
    scale_json_value = _float32_from_int(int("3db504f3", 16))
    expected_scale = 1.0 / math.sqrt(128.0)
    for value in (gqa_scale, scale_file_value, scale_json_value):
        if not math.isclose(
            value, expected_scale, rel_tol=0.0, abs_tol=1e-8
        ):
            raise DeepSeekOnnxValidationError(
                "prefill attention scale differs from 1/sqrt(128)"
            )

    qkt_config = _load_object(root / PREFILL_QKT_CONFIG_PATH)
    remote_config = _load_object(root / PREFILL_REMOTE4_CONFIG_PATH)
    if qkt_config.get("n2n") is not None or remote_config.get("n2n") is not None:
        raise DeepSeekOnnxValidationError(
            "prefill QKT/remote topology counterexample differs"
        )

    layer_source = (root / PREFILL_RELAYOUT_LAYER_PATH).read_text(
        encoding="utf-8"
    )
    rms_source = (root / PREFILL_RELAYOUT_RMSNORM_PATH).read_text(
        encoding="utf-8"
    )
    kv_mul_source = (root / PREFILL_RELAYOUT_KV_MUL_PATH).read_text(
        encoding="utf-8"
    )
    regular_source = (root / PREFILL_RELAYOUT_REGULAR_PATH).read_text(
        encoding="utf-8"
    )
    gemm_local_source = (
        root / PREFILL_RELAYOUT_GEMM_LOCAL_PATH
    ).read_text(encoding="utf-8")
    numeric_source = (root / PREFILL_NUMERIC_GOLDEN_PATH).read_text(
        encoding="utf-8"
    )
    relayout_fragments = {
        "kv_rms_derived_from_layer_input": (
            '"rmsnorm_kv": ("rmsnorm", '
            '"blk.0_norm-0_op-rms_norm_kv")'
        ),
        "kv_mul_derived_from_attention_norm": (
            '"mul_fp32mn_fp32n_fp16mn_kv": '
            '("mul_MN_N_kv", "blk.0_attn_norm-0_op-mul")'
        ),
        "kv_padding_formula": (
            'return model_params["kv_padding"] * '
            'model_params["slice_per_head"]'
        ),
        "kv_head_replication": (
            "slices_to_distribute = base_slices * num_heads"
        ),
        "remote_data_comes_from_golden_files": (
            '"remote_sum_fp32mn_fp32mn": '
            '("gemm_local", '
            '"blk.0_node_0_attn_scores_op-remote_sum")'
        ),
        "qkv_golden_shared_norm_k": (
            'store.get(f"{lid}.attn_k.weight"), '
            'store.get(f"attn_norm-{layer_id}")'
        ),
        "qkv_golden_shared_norm_v": (
            'store.get(f"{lid}.attn_v.weight"), '
            'store.get(f"attn_norm-{layer_id}")'
        ),
    }
    fragment_sources = {
        "kv_rms_derived_from_layer_input": layer_source,
        "kv_mul_derived_from_attention_norm": layer_source,
        "kv_padding_formula": kv_mul_source,
        "kv_head_replication": regular_source,
        "remote_data_comes_from_golden_files": layer_source,
        "qkv_golden_shared_norm_k": numeric_source,
        "qkv_golden_shared_norm_v": numeric_source,
    }
    missing_fragments = [
        name
        for name, fragment in relayout_fragments.items()
        if fragment not in fragment_sources[name]
    ]
    if missing_fragments:
        raise DeepSeekOnnxValidationError(
            "prefill relayout/golden evidence differs: "
            + repr(missing_fragments)
        )
    if (
        "slices_per_head = MODEL_PARAMS[\"slice_per_head\"]"
        not in gemm_local_source
        or "global_idx = h_idx * slices_per_head + i"
        not in gemm_local_source
        or "padded = np.zeros((padded_N, phys_M)"
        not in rms_source
    ):
        raise DeepSeekOnnxValidationError(
            "prefill partial/padding relayout evidence differs"
        )

    prefill_sources = {
        "q_projection": _source_operator(normalized, "op5", "A"),
        "k_projection": _source_operator(normalized, "op15", "A"),
        "v_projection": _source_operator(normalized, "op20", "A"),
        "kv_rms_external": _source_operator(normalized, "op10", "A"),
        "qkt_q": _source_operator(normalized, "op22", "A"),
        "qkt_k": _source_operator(normalized, "op22", "B"),
        "sv_probability": _source_operator(normalized, "op29", "A"),
        "sv_value": _source_operator(normalized, "op29", "B"),
    }
    expected_sources = {
        "q_projection": "op4",
        "k_projection": "op14",
        "v_projection": "op14",
        "kv_rms_external": None,
        "qkt_q": "op9",
        "qkt_k": "op19",
        "sv_probability": "op28",
        "sv_value": "op21",
    }
    if prefill_sources != expected_sources:
        raise DeepSeekOnnxValidationError(
            "prefill stage source topology differs"
        )

    softmax_chain = [
        {
            "operator_id": operator_id,
            "type": _operator_by_id(normalized, operator_id)["type"],
            "output_shape": _operator_by_id(
                normalized, operator_id
            )["output"]["shape"],
        }
        for operator_id in ("op24", "op25", "op26", "op27", "op28")
    ]
    if [item["type"] for item in softmax_chain] != [
        "prefill_mac_fp32MN_fp32MN_fp32MN",
        "prefill_max_fp32MN_fp32MN",
        "prefill_sub_SFU_fp32MN_fp32M_fp32MN",
        "prefill_sum_rec_fp32MN_fp32MN",
        "prefill_mul_fp32MN_fp32M_fp16MN",
    ]:
        raise DeepSeekOnnxValidationError(
            "prefill softmax Stage DAG differs"
        )

    blockers = [
        {
            "id": "B_DS_PREFILL_TOP_LEVEL_SLICE_MASK_ENCODING",
            "classification": "STAGE_DAG_ENCODING",
            "evidence": {
                "raw_value": raw_graph["used_slices"],
                "raw_value_intended_as_count": 28,
                "native_enabled_slices": parsed_top_level_slices,
                "required_mask": "0b1111111111111111111111111111",
            },
        },
        {
            "id": "B_DS_PREFILL_REMOTE_REDUCTION_BYTE_EXTENT",
            "classification": "STAGE_DAG_LIFETIME",
            "evidence": {
                "producer": "op22",
                "consumer": "op23",
                "aliased_tensor": remote_tensor_name,
                "producer_allocation_bytes": remote_assignment.size_bytes,
                "consumer_requested_bytes": requested_remote_bytes,
                "extent_ratio": (
                    requested_remote_bytes
                    / remote_assignment.size_bytes
                ),
                "qkt_n2n": qkt_config.get("n2n"),
                "remote_n2n": remote_config.get("n2n"),
                "runtime_peer_slice_gather_proven": False,
            },
        },
        {
            "id": "B_DS_PREFILL_LEADER_SLICE_ROUTING",
            "classification": "STAGE_DAG_ROUTING",
            "evidence": leader_routes,
        },
        {
            "id": "B_DS_PREFILL_EXTERNAL_ALIAS_MANIFEST",
            "classification": "TENSOR_BINDING",
            "evidence": {
                "program_sources": prefill_sources,
                "relayout_alias_evidence_present": True,
                "graph_or_manifest_binds_aliases": False,
                "residual_op31_is_external": (
                    _source_operator(normalized, "op31", "A") is None
                ),
                "rule": (
                    "hard-coded relayout filenames are evidence of intent, "
                    "not a runtime producer/consumer identity contract"
                ),
            },
        },
    ]
    open_provenance = [
        {
            "id": "B_DS_ONNX_ORIGINAL_SOURCE_IDENTITY",
            "blocks_local_semantic_audit": False,
            "blocks_release_identity": True,
        },
        {
            "id": "B_DS_QKV_FUSED_EXTRACTION_IDENTITY",
            "blocks_local_semantic_audit": False,
            "blocks_release_identity": True,
        },
    ]

    payload: dict[str, Any] = {
        "schema": PREFILL_STAGE_AUDIT_SCHEMA,
        "status": "blocked_before_stage_to_json_generation",
        "candidate_release": False,
        "maximum_evidence_level": "E2",
        "read_receipt_validation": receipt_validation,
        "inputs": {
            "prefill_program": _binding(root, PREFILL_PROGRAM_PATH),
            "prefill_program_listing": _binding(
                root, PREFILL_PROGRAM_LISTING_PATH
            ),
            "prefill_program_producer": _binding(
                root, PREFILL_PROGRAM_PRODUCER_PATH
            ),
            "crop_contract": _binding(root, CROP_CONTRACT_PATH),
            "onnx_inventory": _binding(root, ONNX_INVENTORY_PATH),
            "numeric_golden": _binding(
                root, PREFILL_NUMERIC_GOLDEN_PATH
            ),
            "qkt_json": _binding(root, PREFILL_QKT_CONFIG_PATH),
            "remote4_json": _binding(
                root, PREFILL_REMOTE4_CONFIG_PATH
            ),
            "scale_mask_json": _binding(
                root, PREFILL_SCALE_MASK_CONFIG_PATH
            ),
        },
        "stage_graph": {
            "operator_count": 43,
            "raw_top_level_used_slices": raw_graph["used_slices"],
            "native_top_level_enabled_slices": parsed_top_level_slices,
            "program_sources": prefill_sources,
        },
        "locally_closed_semantics": {
            "gqa_scale": {
                "formula": "1/sqrt(128)",
                "onnx": gqa_scale,
                "softmax_scale_bin": scale_file_value,
                "trusted_json_constant": scale_json_value,
                "closed": True,
            },
            "softmax_key_axis": {
                "sequence_length": 32,
                "chain": softmax_chain,
                "full_key_axis_per_slice": True,
                "normalization_sum_equals_one_if_remote_input_valid": True,
                "closed_unconditionally": False,
            },
            "gqa_kv_replication": {
                "logical_kv_heads": 1,
                "query_heads": 7,
                "slice_per_head": 4,
                "physical_slice_occurrences": 28,
                "relayout_replication_formula_present": True,
                "closed_at_relayout_formula_level": True,
            },
            "prefill_current_kv_sources": {
                "qkt_k_source": prefill_sources["qkt_k"],
                "sv_v_source": prefill_sources["sv_value"],
                "current_k_stage": "op19",
                "current_v_stage": "op21",
                "closed_at_program_source_level": True,
            },
        },
        "semantic_blockers": blockers,
        "semantic_blocker_ids": [item["id"] for item in blockers],
        "open_provenance_confirmations": open_provenance,
        "policy_result": {
            "onnx_to_prefill_stage_ready": False,
            "stage_to_json_forward_generation_allowed": False,
            "trusted_individual_json_semantics_invalidated": False,
            "reason": (
                "prefill closes the scale, softmax-axis, GQA replication "
                "formula and current-KV source intent, but its generated "
                "runtime graph lacks a valid remote-reduction byte route, "
                "uses incompatible leader/source-slice IDs, encodes the "
                "top-level slice count as a mask, and leaves relayout aliases "
                "outside the graph identity contract"
            ),
        },
        "rule_ids": [
            "CDA-DEEPSEEK-MODEL-IDENTITY-001",
            "CDA-DEEPSEEK-CROP-EXPLICIT-001",
            "CDA-DEEPSEEK-ONNX-STAGE-DAG-001",
            "CDA-DEEPSEEK-QKV-ALIAS-001",
            "CDA-DEEPSEEK-ATTENTION-NUMERIC-001",
            "CDA-DEEPSEEK-CROSS-SLICE-ROUTE-001",
            "CDA-DEEPSEEK-PROGRAM-GOLDEN-PARITY-001",
            "CDA-DEEPSEEK-KV-LIFETIME-001",
        ],
    }
    payload["audit_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_deepseek_prefill_stage_audit(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_deepseek_prefill_stage_audit(project_root):
        raise DeepSeekOnnxValidationError(
            "DeepSeek prefill Stage audit differs from current evidence"
        )


def write_deepseek_prefill_stage_audit(
    path: Path, value: Mapping[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_deepseek_onnx_stage_mapping(
    path: Path, value: Mapping[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "CROP_SCHEMA",
    "PREFILL_STAGE_AUDIT_SCHEMA",
    "STAGE_MAPPING_SCHEMA",
    "DeepSeekOnnxValidationError",
    "build_deepseek_crop_contract",
    "build_deepseek_onnx_stage_mapping",
    "build_deepseek_prefill_stage_audit",
    "validate_deepseek_crop_contract",
    "validate_deepseek_onnx_stage_mapping",
    "validate_deepseek_prefill_stage_audit",
    "write_deepseek_crop_contract",
    "write_deepseek_onnx_stage_mapping",
    "write_deepseek_prefill_stage_audit",
]
