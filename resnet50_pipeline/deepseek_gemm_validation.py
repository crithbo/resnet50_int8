from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .deepseek_native_e2 import run_double_isolated_native_graph
from .deepseek_gemm_numeric import (
    CONTRACT_PATH as GEMM_NUMERIC_CONTRACT_PATH,
    build_gemm_numeric_contract,
)
from .deepseek_onnx_validation import build_deepseek_crop_contract
from .deepseek_silu_holdout import _compute_native_mapping_penalty
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .ndpsim_native import load_native_execution_plan
from .ndp_config_length import (
    analyze_config_length,
    parse_load_config_length,
)


ARTIFACT_ROOT = "artifacts/operator_config_validation/ds_gemm_ffn_gate_v1"
GRAPH_NAME = "ds_gemm_ffn_gate_v1"
GRAPH_PATH = f"{ARTIFACT_ROOT}/{GRAPH_NAME}.json"
CONTRACT_PATH = (
    "contracts/operator_config/deepseek_gemm_validation_v1.json"
)
READ_RECEIPT_PATH = (
    "contracts/operator_config/deepseek_gemm_read_receipt_v1.json"
)
READ_RECEIPT_SHA256 = (
    "88c812049d0ee1f99de9fea135541795d"
    "c13b1d115ad87fcf334938c3aee6bd8"
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
NATIVE_FRAGMENT_PATH = (
    "ndp-sim/model_execplan/op_json/gemm_ring_ffn_gate.json"
)
TRUSTED_PACKAGE_GRAPH_PATH = (
    "jsons/gemm_ring_fnn/gemm_ring_fnn_withbaseaddr.json"
)
TRUSTED_EXECPLAN_PATH = "jsons/gemm_ring_fnn/install/execplan.txt"
TRUSTED_EXPLAINED_PATH = "jsons/gemm_ring_fnn/instructions_explained.txt"
TRUSTED_BITSTREAM_PATH = (
    "jsons/gemm_ring_fnn/install/cfg_pkg/"
    "prefill_gemm_ring_4slice_bitstream_128b.bin"
)
NATIVE_TEMPLATE_PATH = "ndp-sim/jsons/prefill_gemm_ring_4slice.json"
RELAYOUT_PATH = (
    "ndp-sim/generate_python_golden/single_op_data/"
    "relayout_gemm_ring.py"
)
OPERATOR_TYPE = "prefill_gemm_ring_4slice"
ALL_28_MASK = "0b" + ("1" * 28)
A_LAYOUT_HINT = "reorder(m8,n2)->(n2,m8)"
B_LAYOUT_HINT = "reorder(n8,m2)->(m2,n8)"


class DeepSeekGemmValidationError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekGemmValidationError(
            f"cannot parse GEMM evidence JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DeepSeekGemmValidationError(
            f"JSON root must be an object: {path}"
        )
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise DeepSeekGemmValidationError(
            f"required GEMM evidence is missing: {relative}"
        )
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


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


def _onnx_anchor(root: Path) -> dict[str, Any]:
    inventory = _load(root / ONNX_INVENTORY_PATH)
    graph = inventory.get("graph")
    if not isinstance(graph, Mapping):
        raise DeepSeekGemmValidationError("ONNX inventory graph is missing")
    nodes = graph.get("nodes")
    matches = [
        item
        for item in nodes
        if isinstance(item, Mapping)
        and item.get("index") == 15
        and item.get("name")
        == "/model/layers.0/mlp/gate_proj/MatMul"
    ] if isinstance(nodes, list) else []
    if len(matches) != 1:
        raise DeepSeekGemmValidationError(
            "ONNX layer-0 FFN gate MatMul anchor differs"
        )
    node = deepcopy(dict(matches[0]))
    expected_weight = "model.layers.0.mlp.gate_proj.MatMul.weight"
    if (
        node.get("op_type") != "MatMul"
        or node.get("inputs", [None, None])[1] != expected_weight
    ):
        raise DeepSeekGemmValidationError(
            "ONNX layer-0 FFN gate MatMul inputs differ"
        )
    initializers = graph.get("initializers")
    weights = [
        item
        for item in initializers
        if isinstance(item, Mapping)
        and item.get("name") == expected_weight
    ] if isinstance(initializers, list) else []
    if len(weights) != 1:
        raise DeepSeekGemmValidationError(
            "ONNX layer-0 FFN gate weight initializer differs"
        )
    weight = deepcopy(dict(weights[0]))
    if (
        weight.get("dims") != [1536, 8960]
        or weight.get("data_type_name") != "FLOAT16"
        or weight.get("data_location") != "EXTERNAL"
        or weight.get("external_data", {}).get("location")
        != "model_fp16.onnx_data"
        or weight.get("external_data", {}).get("length")
        != "27525120"
    ):
        raise DeepSeekGemmValidationError(
            "ONNX layer-0 FFN gate weight metadata differs"
        )
    return {"node": node, "weight_initializer": weight}


def _trusted_graph_without_addresses(root: Path) -> dict[str, Any]:
    return _strip_base_addresses(
        _load(root / TRUSTED_PACKAGE_GRAPH_PATH)
    )


def build_raw_gemm_stage_graph(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    receipt = root / READ_RECEIPT_PATH
    if (
        not receipt.is_file()
        or sha256_file(receipt) != READ_RECEIPT_SHA256
        or _load(receipt).get("receipt_status")
        != "GEMM_FFN_GATE_MATERIALIZATION_READY"
    ):
        raise DeepSeekGemmValidationError(
            "GEMM mandatory-read receipt differs"
        )
    crop = build_deepseek_crop_contract(root)
    target = crop.get("model_dimensions", {}).get("target", {})
    derived = crop.get("model_dimensions", {}).get("derived", {})
    if (
        target.get("hidden_size") != 896
        or target.get("intermediate_size") != 1792
        or derived.get("active_slice_count") != 28
    ):
        raise DeepSeekGemmValidationError(
            "crop contract does not derive the FFN gate target"
        )
    _onnx_anchor(root)

    prefill = _load(root / RAW_PREFILL_GRAPH_PATH)
    if prefill.get("params", {}).get("sequence_length") != 32:
        raise DeepSeekGemmValidationError(
            "prefill graph does not bind the sequence-length-32 crop"
        )
    operators = prefill.get("operators")
    if not isinstance(operators, list) or len(operators) <= 37:
        raise DeepSeekGemmValidationError(
            "prefill graph is missing FFN gate op37"
        )
    op = deepcopy(operators[37])
    if (
        op.get("id") != "op37"
        or op.get("type") != OPERATOR_TYPE
        or op.get("used_slices") != ALL_28_MASK
        or op.get("inputs", {}).get("A", {}).get("source") != "op36"
        or op.get("inputs", {}).get("B", {}).get("source")
        != {"type": "external"}
    ):
        raise DeepSeekGemmValidationError(
            "prefill FFN gate Stage IR differs"
        )
    op["id"] = "op0"
    op["inputs"]["A"]["source"] = "external"

    trusted = _trusted_graph_without_addresses(root)
    params = trusted.get("params")
    if not isinstance(params, dict):
        raise DeepSeekGemmValidationError(
            "trusted FFN graph parameter block is malformed"
        )
    graph = {
        "params": deepcopy(params),
        "used_slices": 28,
        "operators": [op],
    }
    trusted_op = trusted.get("operators", [{}])[0]
    raw_op = graph["operators"][0]
    raw_a = raw_op["inputs"]["A"]
    raw_b = raw_op["inputs"]["B"]
    trusted_a = trusted_op.get("inputs", {}).get("A", {})
    trusted_b = trusted_op.get("inputs", {}).get("B", {})
    if (
        raw_a.get("write_reg_hint") is not None
        or raw_b.get("write_reg_hint") is not None
        or trusted_a.get("write_reg_hint") != A_LAYOUT_HINT
        or trusted_b.get("write_reg_hint") != B_LAYOUT_HINT
    ):
        raise DeepSeekGemmValidationError(
            "raw/trusted FFN layout-hint boundary differs"
        )
    return graph


def build_gemm_graph(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    raw_graph = build_raw_gemm_stage_graph(root)
    active_prefill = _load(root / PREFILL_GRAPH_PATH)
    active_ops = active_prefill.get("operators")
    if not isinstance(active_ops, list) or len(active_ops) <= 37:
        raise DeepSeekGemmValidationError(
            "active prefill graph is missing FFN gate op37"
        )
    active_op = deepcopy(active_ops[37])
    if (
        active_op.get("id") != "op37"
        or active_op.get("type") != OPERATOR_TYPE
        or active_op.get("inputs", {}).get("A", {}).get(
            "write_reg_hint"
        )
        != A_LAYOUT_HINT
        or active_op.get("inputs", {}).get("B", {}).get(
            "write_reg_hint"
        )
        != B_LAYOUT_HINT
    ):
        raise DeepSeekGemmValidationError(
            "active FFN gate Stage does not own required layout hints"
        )
    active_op["id"] = "op0"
    active_op["inputs"]["A"]["source"] = "external"
    graph = {
        "params": deepcopy(raw_graph["params"]),
        "used_slices": raw_graph["used_slices"],
        "operators": [active_op],
    }
    trusted = _trusted_graph_without_addresses(root)
    if graph != trusted:
        raise DeepSeekGemmValidationError(
            "rule-normalized FFN gate graph differs from trusted package"
        )
    return graph


def validate_gemm_graph(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_gemm_graph(project_root):
        raise DeepSeekGemmValidationError(
            "GEMM graph differs from ONNX/crop/native-stage evidence"
        )


def materialize_gemm_native_e2(
    project_root: Path, python_executable: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    graph = build_gemm_graph(root)
    validate_gemm_graph(graph, root)
    return run_double_isolated_native_graph(
        project_root=root,
        artifact_root_relative=ARTIFACT_ROOT,
        graph_name=GRAPH_NAME,
        graph=graph,
        operator_types=(OPERATOR_TYPE,),
        python_executable=python_executable.resolve(),
        mapping_seed=19,
        inject_bitstream_seed=True,
    )


def _recursive_diff(
    trusted: Any, generated: Any, path: str = ""
) -> list[dict[str, Any]]:
    if isinstance(trusted, Mapping) and isinstance(generated, Mapping):
        result: list[dict[str, Any]] = []
        for key in sorted(set(trusted) | set(generated)):
            child = f"{path}.{key}" if path else str(key)
            if key not in trusted:
                result.append(
                    {
                        "path": child,
                        "trusted": "<missing>",
                        "generated": generated[key],
                    }
                )
            elif key not in generated:
                result.append(
                    {
                        "path": child,
                        "trusted": trusted[key],
                        "generated": "<missing>",
                    }
                )
            else:
                result.extend(
                    _recursive_diff(trusted[key], generated[key], child)
                )
        return result
    if isinstance(trusted, list) and isinstance(generated, list):
        return [] if trusted == generated else [
            {"path": path, "trusted": trusted, "generated": generated}
        ]
    return [] if trusted == generated else [
        {"path": path, "trusted": trusted, "generated": generated}
    ]


def _decode_lifecycle(path: Path) -> dict[str, Any]:
    lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if re.match(r"^\d{4}\s+<", line)
    ]
    return {
        "command_count": len(lines),
        "clock_enable_count": sum(
            "Clock_Enable" in line for line in lines
        ),
        "load_config_count": sum(
            "Load_Config for operator op0" in line for line in lines
        ),
        "write_reg_count": sum("Write_Reg" in line for line in lines),
        "start_comp_count": sum(
            "Start_Comp for operator op0" in line for line in lines
        ),
        "event_order": [
            kind
            for line in lines
            for kind in ("Load_Config", "Start_Comp")
            if f"{kind} for operator op0" in line
        ],
    }


def _instruction_comparison(
    trusted_path: Path, generated_path: Path
) -> dict[str, Any]:
    trusted = [
        line
        for line in trusted_path.read_text(
            encoding="utf-8"
        ).splitlines()
        if re.match(r"^\d{4}\s+<", line)
    ]
    generated = [
        line
        for line in generated_path.read_text(
            encoding="utf-8"
        ).splitlines()
        if re.match(r"^\d{4}\s+<", line)
    ]
    differences = [
        {
            "command_index": index,
            "trusted": trusted_line,
            "generated": generated_line,
        }
        for index, (trusted_line, generated_line) in enumerate(
            zip(trusted, generated)
        )
        if trusted_line != generated_line
    ]
    if len(trusted) != len(generated):
        raise DeepSeekGemmValidationError(
            "GEMM trusted/generated instruction counts differ"
        )
    if differences:
        raise DeepSeekGemmValidationError(
            "GEMM generated instructions differ from the trusted package"
        )
    return {
        "command_count": len(trusted),
        "difference_count": 0,
        "differences": differences,
        "all_write_reg_and_start_comp_commands_equal": True,
        "all_commands_equal": True,
    }


def _config_length_comparison(
    trusted_bitstream: Path,
    generated_bitstream_64b: Path,
    generated_bitstream: Path,
    trusted_explained: Path,
    generated_explained: Path,
    trusted_lifecycle: Mapping[str, Any],
    generated_lifecycle: Mapping[str, Any],
) -> dict[str, Any]:
    trusted_programmed = parse_load_config_length(
        trusted_explained, "op0"
    )
    generated_programmed = parse_load_config_length(
        generated_explained, "op0"
    )
    generated = analyze_config_length(
        generated_bitstream_64b,
        generated_bitstream,
        generated_programmed,
    )
    trusted_rows = len(
        [
            line
            for line in trusted_bitstream.read_text(
                encoding="ascii"
            ).splitlines()
            if line.strip()
        ]
    )
    if (
        trusted_rows != 30
        or generated["physical_128bit_rows"] != 30
        or generated["source_64bit_word_count"] != 59
        or trusted_programmed != 59
        or not generated["matches_rtl_padding_contract"]
    ):
        raise DeepSeekGemmValidationError(
            "GEMM padded config-bitstream boundary differs"
        )
    if (
        trusted_lifecycle.get("command_count") != 111
        or generated_lifecycle.get("command_count") != 111
    ):
        raise DeepSeekGemmValidationError(
            "GEMM lifecycle command count differs"
        )
    return {
        "physical_128bit_rows": trusted_rows,
        "source_64bit_word_count": generated[
            "source_64bit_word_count"
        ],
        "physical_64bit_transport_slots": generated[
            "physical_64bit_transport_slots"
        ],
        "last_row_high_half_is_transport_padding": generated[
            "last_row_high_half_is_transport_padding"
        ],
        "padding_classification": generated[
            "padding_classification"
        ],
        "trusted_load_config_length_64bit_words": trusted_programmed,
        "generated_load_config_length_64bit_words": generated_programmed,
        "generated_128bit_packing_matches_64bit_source": generated[
            "packing_matches_64bit_source"
        ],
        "trusted_matches_64bit_source_word_count": True,
        "generated_counts_padded_storage_slots": False,
        "rtl_boundary": (
            "global_config_manager stores gconfig_len_sent="
            "gexec2gconfig_len-1 and suppresses the final high half "
            "when the length is odd; bitstream/parse.py 64-bit output "
            "owns the meaningful source-word count"
        ),
    }


def _native_double_run_summary(root: Path) -> dict[str, Any]:
    manifests: dict[str, dict[str, tuple[str, int]]] = {}
    receipts: dict[str, dict[str, Any]] = {}
    for run_name in ("a", "b"):
        relative = (
            f"{ARTIFACT_ROOT}/{run_name}/native_run_receipt.json"
        )
        receipt = _load(root / relative)
        unhashed = dict(receipt)
        receipt_hash = unhashed.pop("receipt_sha256", None)
        if (
            receipt.get("returncode") != 0
            or receipt.get("parsed_operator_count") != 1
            or receipt.get("initial_mapping_cache_file_count") != 0
            or receipt.get("mapping_exact_penalties") != {"op0": 0.0}
            or receipt.get("mapping_determinism", {}).get(
                "random_seed"
            ) != 19
            or not receipt.get("mapping_determinism", {}).get(
                "explicit_bitstream_seed_injected"
            )
            or receipt_hash
            != sha256_bytes(canonical_json_bytes(unhashed))
        ):
            raise DeepSeekGemmValidationError(
                f"GEMM native run {run_name} receipt differs"
            )
        output_files = receipt.get("output_files")
        if not isinstance(output_files, list):
            raise DeepSeekGemmValidationError(
                f"GEMM native run {run_name} output set differs"
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
        receipts[run_name] = {
            "binding": _binding(root, relative),
            "receipt_sha256": receipt_hash,
            "mapping_exact_penalties": {"op0": 0.0},
        }
    if manifests["a"] != manifests["b"]:
        raise DeepSeekGemmValidationError(
            "GEMM isolated native deterministic outputs differ"
        )
    return {
        "runs": receipts,
        "output_file_count_per_run": len(
            _load(
                root
                / f"{ARTIFACT_ROOT}/a/native_run_receipt.json"
            )["output_files"]
        ),
        "deterministic_file_count": len(manifests["a"]),
        "excluded_visualization_count": 1,
        "deterministic_outputs_byte_identical": True,
        "native_source_modified": False,
        "empty_cache_at_start": True,
        "random_seed": 19,
        "python_hash_seed": 0,
    }


def _sca_d_summary(root: Path, output_relative: str) -> dict[str, Any]:
    value = _load(root / output_relative / "sca_cfg_D.json")
    entries = [
        item
        for key, item in value.items()
        if re.fullmatch(r"op0_matrixD_slice\d+", key)
        and isinstance(item, Mapping)
    ]
    lengths = {int(item["length"]) for item in entries}
    if len(entries) != 28 or lengths != {256}:
        raise DeepSeekGemmValidationError(
            "GEMM SCA_D output coverage differs"
        )
    return {
        "slice_count": 28,
        "lines_128b_per_slice": 256,
        "bytes_per_slice": 4096,
        "total_valid_bytes": 114688,
    }


def build_gemm_validation_contract(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    raw_graph = build_raw_gemm_stage_graph(root)
    graph = build_gemm_graph(root)
    graph_path = root / GRAPH_PATH
    if _load(graph_path) != graph:
        raise DeepSeekGemmValidationError(
            "GEMM v1 graph differs from current evidence"
        )
    normalized = load_native_execution_plan(root, graph_path)
    output_relative = (
        f"{ARTIFACT_ROOT}/a/t/model_execplan/output/{GRAPH_NAME}"
    )
    output = root / output_relative
    generated_json_relative = (
        f"{output_relative}/jsons/op0_{OPERATOR_TYPE}.json"
    )
    generated_json = _load(root / generated_json_relative)
    mapping_relative = (
        f"{output_relative}/config/op0/mapping_review.json"
    )
    mapping_penalty = _compute_native_mapping_penalty(
        root, _load(root / mapping_relative)
    )
    if mapping_penalty != 0:
        raise DeepSeekGemmValidationError(
            "GEMM generated mapping penalty differs"
        )
    native_template = _load(root / NATIVE_TEMPLATE_PATH)
    generated_lifecycle = _decode_lifecycle(
        output / "instructions_explained.txt"
    )
    trusted_lifecycle = _decode_lifecycle(
        root / TRUSTED_EXPLAINED_PATH
    )
    if (
        generated_lifecycle["event_order"]
        != ["Load_Config", "Start_Comp"]
        or trusted_lifecycle["event_order"]
        != ["Load_Config", "Start_Comp"]
    ):
        raise DeepSeekGemmValidationError(
            "GEMM lifecycle order differs"
        )
    generated_with_addresses = _load(
        output / f"{GRAPH_NAME}_withbaseaddr.json"
    )
    trusted_with_addresses = _load(
        root / TRUSTED_PACKAGE_GRAPH_PATH
    )
    address_diffs = _recursive_diff(
        trusted_with_addresses, generated_with_addresses
    )
    generated_bitstream = (
        output
        / "install/cfg_pkg"
        / f"op0_{OPERATOR_TYPE}_bitstream_128b.bin"
    )
    generated_bitstream_64b = (
        output
        / "config/op0"
        / f"op0_{OPERATOR_TYPE}_bitstream_64b.bin"
    )
    trusted_bitstream = root / TRUSTED_BITSTREAM_PATH
    bitstream_equal = (
        generated_bitstream.read_bytes()
        == trusted_bitstream.read_bytes()
    )
    instruction_comparison = _instruction_comparison(
        root / TRUSTED_EXPLAINED_PATH,
        output / "instructions_explained.txt",
    )
    config_length_comparison = _config_length_comparison(
        trusted_bitstream,
        generated_bitstream_64b,
        generated_bitstream,
        root / TRUSTED_EXPLAINED_PATH,
        output / "instructions_explained.txt",
        trusted_lifecycle,
        generated_lifecycle,
    )
    template_diff = _recursive_diff(native_template, generated_json)
    raw_op = raw_graph["operators"][0]
    numeric_contract = build_gemm_numeric_contract(root)
    if _load(root / GEMM_NUMERIC_CONTRACT_PATH) != numeric_contract:
        raise DeepSeekGemmValidationError(
            "GEMM numeric contract differs from current payload"
        )
    payload: dict[str, Any] = {
        "schema": "deepseek-gemm-ffn-gate-validation-v1",
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
            "native_fragment": _binding(
                root, NATIVE_FRAGMENT_PATH
            ),
            "relayout_consumer": _binding(root, RELAYOUT_PATH),
            "trusted_native_template": _binding(
                root, NATIVE_TEMPLATE_PATH
            ),
            "trusted_package_graph": _binding(
                root, TRUSTED_PACKAGE_GRAPH_PATH
            ),
            "isolated_graph": _binding(root, GRAPH_PATH),
            "synthetic_numeric_contract": _binding(
                root, GEMM_NUMERIC_CONTRACT_PATH
            ),
        },
        "onnx_to_stage": {
            "anchor": _onnx_anchor(root),
            "source_formula": (
                "[batch, sequence, 1536] @ [1536, 8960] "
                "-> [batch, sequence, 8960]"
            ),
            "crop_formula": (
                "[1,32,896] @ [896,1792] -> [1,32,1792]"
            ),
            "hardware_slice_formula": (
                "28 slices; A[32,32,1], B[896,1,64], "
                "D[1,32,64] per slice"
            ),
            "raw_stage_graph": raw_graph,
            "raw_stage_matches_trusted_graph": False,
            "raw_stage_missing_layout_hints": {
                "A": raw_op["inputs"]["A"]["write_reg_hint"],
                "B": raw_op["inputs"]["B"]["write_reg_hint"],
            },
            "active_stage_graph": normalized,
            "active_stage_matches_trusted_graph": True,
        },
        "layout_and_occurrence_contract": {
            "relayout": {
                "A_input": "L8,K2,L4",
                "B_weight": "N8,K2,N4",
                "D_output": "L8,N8,L4,N4",
            },
            "required_write_reg_hints": {
                "A": A_LAYOUT_HINT,
                "B": B_LAYOUT_HINT,
            },
            "per_slice": {
                "A_shape": [32, 32, 1],
                "A_bytes": 2048,
                "B_shape": [896, 1, 64],
                "B_bytes": 114688,
                "D_shape": [1, 32, 64],
                "D_bytes": 4096,
            },
            "ring": {
                "participating_slice_count": 28,
                "n2n_mem_loop": generated_json["n2n"][
                    "neighbor_stream0"
                ]["mem_loop"],
                "src_slice_sel": generated_json["n2n"][
                    "neighbor_stream0"
                ]["src_slice_sel"],
                "dst_slice_sel": generated_json["n2n"][
                    "neighbor_stream0"
                ]["dst_slice_sel"],
            },
            "B_and_B_prime_share_logical_allocation": (
                generated_with_addresses["operators"][0]["inputs"]["B"][
                    "base_addr"
                ]
                == generated_with_addresses["operators"][0]["inputs"]["B'"][
                    "base_addr"
                ]
            ),
            "sca_d": _sca_d_summary(root, output_relative),
        },
        "stage_json_bitstream_lifecycle": {
            "native_double_run": _native_double_run_summary(root),
            "mapping_review": _binding(root, mapping_relative),
            "mapping_exact_penalty": mapping_penalty,
            "generated_json": _binding(
                root, generated_json_relative
            ),
            "trusted_template_diff": template_diff,
            "generated_lifecycle": generated_lifecycle,
            "trusted_lifecycle": trusted_lifecycle,
            "instruction_comparison": instruction_comparison,
            "config_length_comparison": config_length_comparison,
            "address_bound_graph_diff": address_diffs,
            "generated_bitstream": _binding(
                root,
                generated_bitstream.relative_to(root).as_posix(),
            ),
            "trusted_bitstream": _binding(
                root, TRUSTED_BITSTREAM_PATH
            ),
            "bitstream_byte_equal": bitstream_equal,
            "structurally_complete": True,
            "config_semantics_accepted": True,
        },
        "trusted_numeric_payload_boundary": {
            "onnx_external_weight_payload_downloaded": False,
            "trusted_package_tensor_payload_available": False,
            "numerical_golden_available": False,
        },
        "synthetic_numeric_e2": numeric_contract,
        "closed_blockers": [
            "B_DS_GEMM_LAYOUT_HINT_STAGE_GAP",
            "B_DS_GEMM_NUMERIC_PAYLOAD_EVIDENCE",
        ],
        "blockers": [],
        "policy_result": {
            "upstream_raw_stage_is_active_stage": False,
            "active_stage_is_sufficient_for_automatic_generation": True,
            "local_json_bitstream_rebuild_complete": True,
            "load_config_length_matches_trusted_oracle": True,
            "local_numeric_closure_complete": True,
            "local_e2_reference_conformant": True,
            "advance_to_server_test": False,
        },
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_gemm_validation_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    rebuilt = build_gemm_validation_contract(project_root)
    if value != rebuilt:
        raise DeepSeekGemmValidationError(
            "GEMM validation contract differs from current evidence"
        )


__all__ = [
    "ARTIFACT_ROOT",
    "CONTRACT_PATH",
    "DeepSeekGemmValidationError",
    "GRAPH_PATH",
    "OPERATOR_TYPE",
    "build_gemm_graph",
    "build_gemm_validation_contract",
    "build_raw_gemm_stage_graph",
    "materialize_gemm_native_e2",
    "validate_gemm_graph",
    "validate_gemm_validation_contract",
]
