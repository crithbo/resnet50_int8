from __future__ import annotations

import json
import math
import re
import struct
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .deepseek_native_e2 import run_double_isolated_native_graph
from .deepseek_onnx_validation import build_deepseek_crop_contract
from .deepseek_silu_holdout import _compute_native_mapping_penalty
from .deepseek_softmax_numeric import (
    CONTRACT_PATH as SOFTMAX_NUMERIC_CONTRACT_PATH,
    build_softmax_numeric_contract,
)
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .ndpsim_native import load_native_execution_plan


ARTIFACT_ROOT = "artifacts/operator_config_validation/ds_softmax_v1"
GRAPH_NAME = "ds_softmax_v1"
GRAPH_PATH = f"{ARTIFACT_ROOT}/{GRAPH_NAME}.json"
CONTRACT_PATH = (
    "contracts/operator_config/deepseek_softmax_validation_v1.json"
)
READ_RECEIPT_PATH = (
    "contracts/operator_config/deepseek_softmax_read_receipt_v1.json"
)
READ_RECEIPT_SHA256 = (
    "6cd05e46c499980bc5a8936ca848ed8a"
    "41ec926c07e999e5fb2b10512de98128"
)
PREFILL_GRAPH_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/"
    "layer0_prefill.rule_normalized.json"
)
RAW_PREFILL_GRAPH_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/layer0_prefill.generated.json"
)
STAGE_PRODUCER_CONTRACT_PATH = (
    "contracts/operator_config/"
    "deepseek_prefill_rule_normalized_stage_v1.json"
)
ONNX_INVENTORY_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/onnx_graph_inventory.json"
)
SOFTMAX_FRAGMENT_PATH = "ndp-sim/model_execplan/op_json/softmax.json"
TRUSTED_PACKAGE_GRAPH_PATH = "jsons/softmax/softmax_withbaseaddr.json"
SOFTMAX_SCALE_PATH = (
    "ndp-sim/generate_python_golden/softmax_scale.bin"
)
SOFTMAX_RULE_PATH = ".agents/rules/DeepSeek_Softmax增量规则.md"
OPERATOR_TYPES = (
    "prefill_mac_fp32MN_fp32MN_fp32MN",
    "prefill_max_fp32MN_fp32MN",
    "prefill_sub_SFU_fp32MN_fp32M_fp32MN",
    "prefill_sum_rec_fp32MN_fp32MN",
    "prefill_mul_fp32MN_fp32M_fp16MN",
)
ALL_28_MASK = "0b" + ("1" * 28)
MASK_LAYOUT_HINT = "softmax_mask_reuse_rows"
EXP_LAYOUT_HINT = "softmax_exp_m8_n_interleave"


class DeepSeekSoftmaxValidationError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekSoftmaxValidationError(
            f"cannot parse Softmax evidence JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DeepSeekSoftmaxValidationError(
            f"JSON root must be an object: {path}"
        )
    return value


def _onnx_anchor(root: Path) -> dict[str, Any]:
    inventory = _load(root / ONNX_INVENTORY_PATH)
    nodes = inventory.get("graph", {}).get("nodes")
    matches = [
        item
        for item in nodes
        if isinstance(item, Mapping)
        and item.get("index") == 12
        and item.get("name")
        == "/model/layers.0/attn/GroupQueryAttention"
    ] if isinstance(nodes, list) else []
    if len(matches) != 1:
        raise DeepSeekSoftmaxValidationError(
            "ONNX layer-0 fused GQA/Softmax anchor differs"
        )
    node = matches[0]
    attributes = {
        str(item.get("name")): item.get("value")
        for item in node.get("attributes", [])
        if isinstance(item, Mapping)
    }
    expected_fp32_scale = struct.unpack(
        "<f", struct.pack("<f", 1.0 / math.sqrt(128.0))
    )[0]
    if (
        node.get("op_type") != "GroupQueryAttention"
        or attributes.get("num_heads") != 12
        or attributes.get("kv_num_heads") != 2
        or attributes.get("scale") != expected_fp32_scale
    ):
        raise DeepSeekSoftmaxValidationError(
            "ONNX fused GQA scale/head semantics differ"
        )
    return deepcopy(dict(node))


def _strip_base_addresses(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_base_addresses(item)
            for key, item in value.items()
            if key != "base_addr"
        }
    if isinstance(value, list):
        return [_strip_base_addresses(item) for item in value]
    return value


def _strip_graph_only_fields(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_graph_only_fields(item)
            for key, item in value.items()
            if key not in {"base_addr", "write_reg_hint"}
        }
    if isinstance(value, list):
        return [_strip_graph_only_fields(item) for item in value]
    return value


def build_softmax_graph(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    receipt = root / READ_RECEIPT_PATH
    if (
        not receipt.is_file()
        or sha256_file(receipt) != READ_RECEIPT_SHA256
        or _load(receipt).get("receipt_status")
        != "SOFTMAX_FIVE_STAGE_MATERIALIZATION_READY"
    ):
        raise DeepSeekSoftmaxValidationError(
            "Softmax mandatory-read receipt differs"
        )
    crop = build_deepseek_crop_contract(root)
    derived = crop.get("model_dimensions", {}).get("derived", {})
    target = crop.get("model_dimensions", {}).get("target", {})
    if (
        derived.get("active_slice_count") != 28
        or target.get("num_attention_heads") != 7
        or target.get("head_dim") != 128
    ):
        raise DeepSeekSoftmaxValidationError(
            "crop contract does not derive 7 heads x 4 slices at S=32"
        )
    _onnx_anchor(root)

    scale_data = (root / SOFTMAX_SCALE_PATH).read_bytes()
    expected_scale = struct.unpack(
        "<f", struct.pack("<f", 1.0 / math.sqrt(128.0))
    )[0]
    if (
        len(scale_data) != 4
        or struct.unpack("<f", scale_data)[0] != expected_scale
    ):
        raise DeepSeekSoftmaxValidationError(
            "native Softmax scale is not fp32(1/sqrt(128))"
        )

    fragment = _load(root / SOFTMAX_FRAGMENT_PATH)
    fragment_ops = fragment.get("operators")
    if (
        not isinstance(fragment_ops, list)
        or [item.get("type") for item in fragment_ops]
        != list(OPERATOR_TYPES)
        or fragment_ops[0].get("inputs", {}).get("A", {}).get("type")
        != "slice4"
    ):
        raise DeepSeekSoftmaxValidationError(
            "native Softmax fragment differs"
        )

    prefill = _load(root / PREFILL_GRAPH_PATH)
    all_ops = prefill.get("operators")
    if not isinstance(all_ops, list) or len(all_ops) < 29:
        raise DeepSeekSoftmaxValidationError(
            "prefill graph is missing Softmax stages"
        )
    selected = deepcopy(all_ops[24:29])
    if [item.get("type") for item in selected] != list(OPERATOR_TYPES):
        raise DeepSeekSoftmaxValidationError(
            "prefill Softmax stage sequence differs"
        )
    if (
        selected[0].get("inputs", {}).get("A", {}).get("source")
        != "op23"
        or selected[0].get("inputs", {}).get("A", {}).get("type")
        != "slice4"
        or selected[2].get("inputs", {}).get("B", {}).get("source")
        != "op25"
        or selected[4].get("inputs", {}).get("B", {}).get("source")
        != "op27"
    ):
        raise DeepSeekSoftmaxValidationError(
            "prefill Softmax typed dependencies differ"
        )

    old_to_new = {
        str(item["id"]): f"op{index}"
        for index, item in enumerate(selected)
    }
    for index, item in enumerate(selected):
        item["id"] = f"op{index}"
        for spec in item.get("inputs", {}).values():
            if not isinstance(spec, dict):
                continue
            source = spec.get("source")
            if isinstance(source, str) and source in old_to_new:
                spec["source"] = old_to_new[source]
    # The isolated graph starts after the upstream four-slice-per-head
    # replication boundary. Its external A payload must satisfy that
    # representation contract, so no unresolved slice4 route remains here.
    selected[0]["inputs"]["A"]["source"] = {"type": "external"}
    selected[0]["inputs"]["A"].pop("type", None)
    if (
        selected[0]["inputs"]["C"].get("write_reg_hint")
        != MASK_LAYOUT_HINT
        or selected[2]["inputs"]["A"].get("write_reg_hint")
        != EXP_LAYOUT_HINT
    ):
        raise DeepSeekSoftmaxValidationError(
            "active Softmax Stage does not own required layout hints"
        )

    prefill_params = prefill.get("params")
    if not isinstance(prefill_params, dict):
        raise DeepSeekSoftmaxValidationError(
            "prefill parameter block is malformed"
        )
    trusted = _strip_base_addresses(
        _load(root / TRUSTED_PACKAGE_GRAPH_PATH)
    )
    params = trusted.get("params")
    if (
        not isinstance(params, dict)
        or any(
            prefill_params.get(key) != value
            for key, value in params.items()
            if key != "target_op"
        )
    ):
        raise DeepSeekSoftmaxValidationError(
            "trusted Softmax parameter subset differs from prefill"
        )
    graph = {
        "params": deepcopy(params),
        "used_slices": 28,
        "operators": selected,
    }
    if _strip_graph_only_fields(graph) != trusted:
        raise DeepSeekSoftmaxValidationError(
            "rule-normalized isolated Softmax graph differs from trusted package"
        )
    return graph


def build_raw_softmax_stage_graph(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    active = build_softmax_graph(root)
    raw_prefill = _load(root / RAW_PREFILL_GRAPH_PATH)
    raw_ops = raw_prefill.get("operators")
    if not isinstance(raw_ops, list) or len(raw_ops) < 29:
        raise DeepSeekSoftmaxValidationError(
            "raw prefill graph is missing Softmax stages"
        )
    graph = deepcopy(active)
    graph["operators"][0]["inputs"]["C"].pop("write_reg_hint")
    graph["operators"][2]["inputs"]["A"].pop("write_reg_hint")
    if (
        raw_ops[24].get("inputs", {}).get("C", {}).get(
            "write_reg_hint"
        )
        is not None
        or raw_ops[26].get("inputs", {}).get("A", {}).get(
            "write_reg_hint"
        )
        is not None
    ):
        raise DeepSeekSoftmaxValidationError(
            "upstream raw Softmax layout-hint boundary differs"
        )
    return graph


def validate_softmax_graph(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_softmax_graph(project_root):
        raise DeepSeekSoftmaxValidationError(
            "Softmax graph differs from ONNX/crop/native-stage evidence"
        )


def materialize_softmax_native_e2(
    project_root: Path, python_executable: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    graph = build_softmax_graph(root)
    validate_softmax_graph(graph, root)
    return run_double_isolated_native_graph(
        project_root=root,
        artifact_root_relative=ARTIFACT_ROOT,
        graph_name=GRAPH_NAME,
        graph=graph,
        operator_types=OPERATOR_TYPES,
        sfu_types=("Ex", "REC"),
        python_executable=python_executable.resolve(),
    )


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise DeepSeekSoftmaxValidationError(
            f"required Softmax evidence is missing: {relative}"
        )
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _recursive_diff(
    trusted: Any, generated: Any, path: str = ""
) -> list[dict[str, Any]]:
    if isinstance(trusted, Mapping) and isinstance(generated, Mapping):
        diffs: list[dict[str, Any]] = []
        keys = sorted(set(trusted) | set(generated))
        for key in keys:
            next_path = f"{path}.{key}" if path else str(key)
            if key not in trusted:
                diffs.append(
                    {
                        "path": next_path,
                        "trusted": "<missing>",
                        "generated": generated[key],
                    }
                )
            elif key not in generated:
                diffs.append(
                    {
                        "path": next_path,
                        "trusted": trusted[key],
                        "generated": "<missing>",
                    }
                )
            else:
                diffs.extend(
                    _recursive_diff(
                        trusted[key], generated[key], next_path
                    )
                )
        return diffs
    if isinstance(trusted, list) and isinstance(generated, list):
        if trusted == generated:
            return []
        return [
            {
                "path": path,
                "trusted": trusted,
                "generated": generated,
            }
        ]
    if trusted != generated:
        return [
            {
                "path": path,
                "trusted": trusted,
                "generated": generated,
            }
        ]
    return []


def _materialized_oracle_comparison(
    root: Path, output_relative: str
) -> dict[str, Any]:
    output = root / output_relative
    comparisons: list[dict[str, Any]] = []
    expected_diff_by_op = {
        f"op{index}": [] for index in range(len(OPERATOR_TYPES))
    }
    sca_d = _load(output / "sca_cfg_D.json")
    expected_lengths = (256, 8, 256, 8, 128)
    for index, op_type in enumerate(OPERATOR_TYPES):
        op_id = f"op{index}"
        generated_relative = (
            f"{output_relative}/jsons/{op_id}_{op_type}.json"
        )
        trusted_relative = (
            f"jsons/softmax/jsons/{op_id}_{op_type}.json"
        )
        review_relative = (
            f"{output_relative}/config/{op_id}/mapping_review.json"
        )
        generated = _load(root / generated_relative)
        trusted = _load(root / trusted_relative)
        diffs = _recursive_diff(trusted, generated)
        penalty = _compute_native_mapping_penalty(
            root, _load(root / review_relative)
        )
        d_entries = [
            value
            for key, value in sca_d.items()
            if re.fullmatch(rf"{op_id}_matrixD_slice\d+", key)
            and isinstance(value, Mapping)
        ]
        d_lengths = {
            int(value.get("length")) for value in d_entries
        }
        if (
            diffs != expected_diff_by_op[op_id]
            or penalty != 0
            or len(d_entries) != 28
            or d_lengths != {expected_lengths[index]}
        ):
            raise DeepSeekSoftmaxValidationError(
                f"{op_id} trusted materialized comparison differs"
            )
        comparisons.append(
            {
                "op_id": op_id,
                "op_type": op_type,
                "trusted_json": _binding(root, trusted_relative),
                "generated_json": _binding(
                    root, generated_relative
                ),
                "mapping_review": _binding(
                    root, review_relative
                ),
                "mapping_exact_penalty": penalty,
                "semantic_differences": diffs,
                "canonical_json_equal": not diffs,
                "sca_d_slice_count": len(d_entries),
                "sca_d_lines_128b_per_slice": expected_lengths[
                    index
                ],
            }
        )
    return {
        "operator_comparisons": comparisons,
        "matching_operator_ids": [
            f"op{index}" for index in range(len(OPERATOR_TYPES))
        ],
        "divergent_operator_ids": [],
        "trusted_package_invalidated": False,
        "generated_package_accepted": True,
    }


def _decode_lifecycle(path: Path) -> dict[str, Any]:
    lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if re.match(r"^\d{4}\s+<", line)
    ]
    event_order: list[str] = []
    per_op: dict[str, dict[str, int]] = {
        f"op{index}": {
            "load_config_count": 0,
            "load_sfu_count": 0,
            "write_reg_count": 0,
            "start_comp_count": 0,
        }
        for index in range(5)
    }
    for line in lines:
        match = re.search(
            r"Load_Config SFU for operator (op\d+)", line
        )
        if match:
            op_id = match.group(1)
            event_order.append(f"Load_Config_SFU:{op_id}")
            per_op[op_id]["load_sfu_count"] += 1
            continue
        match = re.search(
            r"(Load_Config|Start_Comp) for operator (op\d+)", line
        )
        if match:
            kind, op_id = match.groups()
            event_order.append(f"{kind}:{op_id}")
            key = (
                "load_config_count"
                if kind == "Load_Config"
                else "start_comp_count"
            )
            per_op[op_id][key] += 1
        if "Write_Reg" in line:
            match = re.search(r"operator (op\d+)", line)
            if not match:
                raise DeepSeekSoftmaxValidationError(
                    "Softmax execplan contains unattributed Write_Reg"
                )
            per_op[match.group(1)]["write_reg_count"] += 1
    return {
        "command_count": len(lines),
        "clock_enable_count": sum(
            "Clock_Enable" in line for line in lines
        ),
        "event_order": event_order,
        "per_operator": per_op,
    }


def _native_double_run_summary(root: Path) -> dict[str, Any]:
    receipts: dict[str, dict[str, Any]] = {}
    manifests: dict[str, dict[str, tuple[str, int]]] = {}
    for run_name in ("a", "b"):
        relative = (
            f"{ARTIFACT_ROOT}/{run_name}/native_run_receipt.json"
        )
        receipt = _load(root / relative)
        unhashed = dict(receipt)
        receipt_hash = unhashed.pop("receipt_sha256", None)
        expected_penalties = {
            f"op{index}": 0.0 for index in range(5)
        }
        if (
            receipt.get("returncode") != 0
            or receipt.get("parsed_operator_count") != 5
            or receipt.get("initial_mapping_cache_file_count") != 0
            or receipt.get("mapping_exact_penalties")
            != expected_penalties
            or receipt_hash
            != sha256_bytes(canonical_json_bytes(unhashed))
        ):
            raise DeepSeekSoftmaxValidationError(
                f"Softmax native run {run_name} receipt differs"
            )
        output_files = receipt.get("output_files")
        if not isinstance(output_files, list) or len(output_files) != 62:
            raise DeepSeekSoftmaxValidationError(
                f"Softmax native run {run_name} output set differs"
            )
        manifests[run_name] = {
            str(item["path"]): (
                str(item["sha256"]),
                int(item["size_bytes"]),
            )
            for item in output_files
            if isinstance(item, Mapping)
            and not str(item.get("path", "")).endswith(
                "/placement.png"
            )
        }
        if len(manifests[run_name]) != 57:
            raise DeepSeekSoftmaxValidationError(
                f"Softmax native run {run_name} deterministic set differs"
            )
        receipts[run_name] = {
            "binding": _binding(root, relative),
            "receipt_sha256": receipt_hash,
            "mapping_exact_penalties": expected_penalties,
        }
    if manifests["a"] != manifests["b"]:
        raise DeepSeekSoftmaxValidationError(
            "Softmax isolated native deterministic outputs differ"
        )
    return {
        "runs": receipts,
        "output_file_count_per_run": 62,
        "deterministic_file_count": 57,
        "excluded_visualization_count": 5,
        "deterministic_outputs_byte_identical": True,
        "native_source_modified": False,
        "empty_cache_at_start": True,
        "random_seed": 42,
        "python_hash_seed": 0,
    }


def _placeholder_summary(root: Path) -> dict[str, Any]:
    install_files = [
        path
        for path in (root / "jsons/softmax/install").rglob(
            "matrix_*"
        )
        if path.is_file()
    ]
    output_files = [
        path
        for path in (root / "jsons/softmax/output_softmax").rglob(
            "*"
        )
        if path.is_file()
    ]
    if (
        len(install_files) != 1092
        or any(path.stat().st_size != 0 for path in install_files)
        or len(output_files) != 140
        or any(path.stat().st_size != 0 for path in output_files)
    ):
        raise DeepSeekSoftmaxValidationError(
            "trusted Softmax placeholder payload boundary differs"
        )
    return {
        "install_tensor_file_count": len(install_files),
        "zero_length_install_tensor_file_count": len(install_files),
        "output_tensor_file_count": len(output_files),
        "zero_length_output_tensor_file_count": len(output_files),
        "numerical_golden_available": False,
    }


def build_softmax_blocker_contract(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    raw_graph = build_raw_softmax_stage_graph(root)
    graph = build_softmax_graph(root)
    graph_path = root / GRAPH_PATH
    if _load(graph_path) != graph:
        raise DeepSeekSoftmaxValidationError(
            "Softmax v1 graph differs from current evidence"
        )
    normalized = load_native_execution_plan(root, graph_path)
    output_relative = (
        f"{ARTIFACT_ROOT}/a/t/model_execplan/output/{GRAPH_NAME}"
    )
    generated_lifecycle = _decode_lifecycle(
        root / output_relative / "instructions_explained.txt"
    )
    trusted_lifecycle = _decode_lifecycle(
        root / "jsons/softmax/instructions_explained.txt"
    )
    expected_events = [
        "Load_Config:op0",
        "Start_Comp:op0",
        "Load_Config:op1",
        "Start_Comp:op1",
        "Load_Config:op2",
        "Load_Config_SFU:op2",
        "Start_Comp:op2",
        "Load_Config:op3",
        "Load_Config_SFU:op3",
        "Start_Comp:op3",
        "Load_Config:op4",
        "Start_Comp:op4",
    ]
    if (
        generated_lifecycle["command_count"] != 364
        or trusted_lifecycle["command_count"] != 392
        or generated_lifecycle["event_order"] != expected_events
        or trusted_lifecycle["event_order"] != expected_events
    ):
        raise DeepSeekSoftmaxValidationError(
            "Softmax lifecycle comparison differs"
        )
    comparison = _materialized_oracle_comparison(
        root, output_relative
    )
    placeholders = _placeholder_summary(root)
    numeric_contract = build_softmax_numeric_contract(root)
    if _load(root / SOFTMAX_NUMERIC_CONTRACT_PATH) != numeric_contract:
        raise DeepSeekSoftmaxValidationError(
            "Softmax numeric contract differs from current payload"
        )
    native_runs = _native_double_run_summary(root)

    payload: dict[str, Any] = {
        "schema": "deepseek-softmax-five-stage-validation-v1",
        "status": "LOCAL_E2_REFERENCE_CONFORMANT",
        "candidate_release": False,
        "formal_target_config": False,
        "server_package_generated": False,
        "identity_boundary": {
            "onnx_repository_classification": "SEMANTIC_MODEL_MATCH",
            "original_source_identity": False,
            "direct_onnx_shape_equals_stage": False,
            "crop_contract_required": True,
        },
        "inputs": {
            "read_receipt": _binding(root, READ_RECEIPT_PATH),
            "crop_contract": _binding(
                root,
                "contracts/operator_config/"
                "deepseek_ndpsim_crop_contract_v1.json",
            ),
            "onnx_inventory": _binding(root, ONNX_INVENTORY_PATH),
            "raw_prefill_graph": _binding(
                root, RAW_PREFILL_GRAPH_PATH
            ),
            "active_prefill_stage": _binding(root, PREFILL_GRAPH_PATH),
            "active_stage_producer_contract": _binding(
                root, STAGE_PRODUCER_CONTRACT_PATH
            ),
            "softmax_fragment": _binding(
                root, SOFTMAX_FRAGMENT_PATH
            ),
            "softmax_scale": _binding(root, SOFTMAX_SCALE_PATH),
            "softmax_rule": _binding(root, SOFTMAX_RULE_PATH),
            "trusted_package_graph": _binding(
                root, TRUSTED_PACKAGE_GRAPH_PATH
            ),
            "isolated_graph": _binding(root, GRAPH_PATH),
            "synthetic_numeric_contract": _binding(
                root, SOFTMAX_NUMERIC_CONTRACT_PATH
            ),
        },
        "onnx_to_stage": {
            "onnx_anchor": _onnx_anchor(root),
            "softmax_is_fused_inside_gqa": True,
            "crop_derived_q_heads": 7,
            "head_dim": 128,
            "sequence_length": 32,
            "attention_scale_fp32": struct.unpack(
                "<f", (root / SOFTMAX_SCALE_PATH).read_bytes()
            )[0],
            "row_formula": (
                "exp(scale*qk + mask - row_max) / "
                "sum(exp(scale*qk + mask - row_max), key_axis)"
            ),
            "native_stage_sequence": list(OPERATOR_TYPES),
            "raw_stage_graph": raw_graph,
            "raw_stage_missing_layout_hints": {
                "op0_C": raw_graph["operators"][0]["inputs"]["C"].get(
                    "write_reg_hint"
                ),
                "op2_A": raw_graph["operators"][2]["inputs"]["A"].get(
                    "write_reg_hint"
                ),
            },
            "required_layout_hints": {
                "op0_C": MASK_LAYOUT_HINT,
                "op2_A": EXP_LAYOUT_HINT,
            },
            "native_normalized_graph": normalized,
            "isolated_input_representation_contract": (
                "the external op0.A score matrix is already replicated "
                "onto all four slices of each crop-derived attention head"
            ),
        },
        "stage_json_bitstream_lifecycle": {
            "trusted_materialized_oracle_comparison": comparison,
            "generated_lifecycle": generated_lifecycle,
            "trusted_lifecycle": trusted_lifecycle,
            "write_count_difference_classification": (
                "not independently semantic; current generator elides "
                "more unchanged writes, so acceptance depends on decoded "
                "end state and materialized JSON equality"
            ),
            "native_double_run": native_runs,
            "structurally_complete": True,
            "rule_normalized_config_accepted": True,
        },
        "trusted_numeric_payload_boundary": placeholders,
        "synthetic_numeric_e2": numeric_contract,
        "closed_findings": [
            {
                "id": "B_DS_SOFTMAX_MASK_C_STRIDE_ORACLE_DIVERGENCE",
                "closure": (
                    "op0 C carries the explicit mask-reuse hint and the "
                    "rebuilt dim_stride equals [32,512,null]"
                ),
            },
            {
                "id": (
                    "B_DS_SOFTMAX_EXP_INPUT_BANK_LAYOUT_"
                    "ORACLE_DIVERGENCE"
                ),
                "closure": (
                    "op2 A carries the explicit m8/n interleave hint and "
                    "the rebuilt buffer-bank order equals the trusted JSON"
                ),
            },
            {
                "id": "B_DS_SOFTMAX_STAGE_LAYOUT_HINT_GAP",
                "closure": (
                    "the active Stage producer emits both registered "
                    "layout hints; the upstream raw graph remains read-only"
                ),
            },
            {
                "id": "B_DS_SOFTMAX_NUMERIC_PAYLOAD_EVIDENCE",
                "closure": (
                    "245 non-empty deterministic synthetic logical and "
                    "physical payloads cover seven heads, all four slice "
                    "replicas and all five stages; formula, causal mask, "
                    "row normalization and native relayout all pass"
                ),
            },
        ],
        "blockers": [],
        "policy_result": {
            "individual_trusted_jsons_invalidated": False,
            "onnx_to_five_stage_decomposition_closed": True,
            "upstream_raw_stage_is_active_stage": False,
            "active_stage_is_sufficient": True,
            "rule_normalized_graph_matches_trusted_graph_precedent": True,
            "double_isolated_rebuild_deterministic": True,
            "materialized_json_matches_trusted_oracle": True,
            "rule_normalized_five_stage_lifecycle_accepted": True,
            "local_numeric_closure_complete": True,
            "local_e2_reference_conformant": True,
            "advance_to_server_test": False,
            "maximum_evidence_level": "E2",
        },
        "rule_ids": [
            "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
            "CDA-CONFIG-FULL-REBUILD-PROVENANCE-001",
            "CDA-DEEPSEEK-MODEL-IDENTITY-001",
            "CDA-DEEPSEEK-CROP-EXPLICIT-001",
            "CDA-DEEPSEEK-ONNX-STAGE-DAG-001",
            "CDA-DEEPSEEK-STAGE-JSON-ORACLE-001",
            "CDA-DEEPSEEK-SOFTMAX-MASK-STRIDE-OWNER-001",
            "CDA-DEEPSEEK-SOFTMAX-EXP-BUFFER-LAYOUT-001",
            "CDA-DEEPSEEK-SOFTMAX-NORMALIZED-ROUNDTRIP-001",
            "CDA-DEEPSEEK-SOFTMAX-PAYLOAD-COVERAGE-001",
        ],
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_softmax_blocker_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_softmax_blocker_contract(project_root):
        raise DeepSeekSoftmaxValidationError(
            "Softmax blocker contract differs from current evidence"
        )


__all__ = [
    "ARTIFACT_ROOT",
    "CONTRACT_PATH",
    "DeepSeekSoftmaxValidationError",
    "GRAPH_NAME",
    "GRAPH_PATH",
    "MASK_LAYOUT_HINT",
    "EXP_LAYOUT_HINT",
    "OPERATOR_TYPES",
    "build_softmax_blocker_contract",
    "build_softmax_graph",
    "build_raw_softmax_stage_graph",
    "materialize_softmax_native_e2",
    "validate_softmax_blocker_contract",
    "validate_softmax_graph",
]
