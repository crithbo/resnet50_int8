from __future__ import annotations

import json
import re
import struct
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .deepseek_silu_holdout import _compute_native_mapping_penalty
from .deepseek_native_e2 import run_double_isolated_native_graph
from .deepseek_config_length_audit import (
    build_deepseek_config_length_audit,
)
from .deepseek_onnx_validation import build_deepseek_crop_contract
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .ndpsim_native import load_native_execution_plan


ARTIFACT_ROOT = "artifacts/operator_config_validation/ds_rms_v1"
GRAPH_NAME = "ds_rms_v1"
GRAPH_PATH = f"{ARTIFACT_ROOT}/{GRAPH_NAME}.json"
CONTRACT_PATH = (
    "contracts/operator_config/deepseek_rmsnorm_validation_v1.json"
)
READ_RECEIPT_PATH = (
    "contracts/operator_config/deepseek_rmsnorm_read_receipt_v1.json"
)
READ_RECEIPT_SHA256 = (
    "2aba2651a33888a0242920df76aa881b"
    "6c689bf2f81e7f8d8c37a6e52c5e5c8b"
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
RMSNORM_FRAGMENT_PATH = "ndp-sim/model_execplan/op_json/rmsnorm.json"
GAMMA_FRAGMENT_PATH = (
    "ndp-sim/model_execplan/op_json/"
    "prefill_mul_fp32MN_fp32N_fp16MN.json"
)
TRUSTED_PACKAGE_GRAPH_PATH = (
    "jsons/rmsnorm/rmsnorm_withbaseaddr.json"
)
OPERATOR_TYPES = (
    "prefill_summac_fp32MN_fp32MN",
    "prefill_remote_sum_fp32MN_fp32MN",
    "prefill_mac_SFU_fp32MN_fp32MN",
    "prefill_mul_fp32MN_fp32M_fp32MN",
    "prefill_mul_fp32MN_fp32N_fp16MN",
)
ALL_28_MASK = "0b" + ("1" * 28)


class DeepSeekRmsNormValidationError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekRmsNormValidationError(
            f"cannot parse RMSNorm evidence JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DeepSeekRmsNormValidationError(
            f"JSON root must be an object: {path}"
        )
    return value


def _onnx_anchor(root: Path) -> dict[str, Any]:
    inventory = _load(root / ONNX_INVENTORY_PATH)
    nodes = inventory.get("graph", {}).get("nodes")
    if not isinstance(nodes, list):
        raise DeepSeekRmsNormValidationError(
            "ONNX graph node inventory is malformed"
        )
    matches = [
        item
        for item in nodes
        if isinstance(item, Mapping)
        and item.get("index") == 9
        and item.get("name")
        == "/model/layers.0/input_layernorm/LayerNorm"
    ]
    if len(matches) != 1:
        raise DeepSeekRmsNormValidationError(
            "ONNX layer-0 input RMSNorm anchor differs"
        )
    node = matches[0]
    attributes = {
        str(item.get("name")): item.get("value")
        for item in node.get("attributes", [])
        if isinstance(item, Mapping)
    }
    if (
        node.get("op_type") != "SimplifiedLayerNormalization"
        or attributes.get("axis") != -1
        or abs(float(attributes.get("epsilon", 0.0)) - 1.0e-6)
        > 1.0e-12
        or node.get("inputs", [None, None])[1]
        != "model.layers.0.input_layernorm.weight"
    ):
        raise DeepSeekRmsNormValidationError(
            "ONNX SimplifiedLayerNormalization semantics differ"
        )
    return deepcopy(dict(node))


def _without_base_addresses(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _without_base_addresses(item)
            for key, item in value.items()
            if key != "base_addr"
        }
    if isinstance(value, list):
        return [_without_base_addresses(item) for item in value]
    return deepcopy(value)


def build_rmsnorm_graph(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    receipt = root / READ_RECEIPT_PATH
    if (
        not receipt.is_file()
        or sha256_file(receipt) != READ_RECEIPT_SHA256
        or _load(receipt).get("receipt_status")
        != "RMSNORM_FIVE_STAGE_MATERIALIZATION_READY"
    ):
        raise DeepSeekRmsNormValidationError(
            "RMSNorm mandatory-read receipt differs"
        )
    crop = build_deepseek_crop_contract(root)
    derived = crop.get("model_dimensions", {}).get("derived", {})
    if (
        derived.get("hidden_elements_per_slice") != 32
        or derived.get("active_slice_count") != 28
    ):
        raise DeepSeekRmsNormValidationError(
            "crop contract does not derive 28x32 hidden elements"
        )
    _onnx_anchor(root)

    native_core = _load(root / RMSNORM_FRAGMENT_PATH)
    native_gamma = _load(root / GAMMA_FRAGMENT_PATH)
    if [
        item.get("type")
        for item in native_core.get("operators", [])
        if isinstance(item, Mapping)
    ] != list(OPERATOR_TYPES[:4]):
        raise DeepSeekRmsNormValidationError(
            "native four-stage RMS core differs"
        )
    gamma_ops = native_gamma.get("operators")
    if (
        not isinstance(gamma_ops, list)
        or len(gamma_ops) != 1
        or gamma_ops[0].get("type") != OPERATOR_TYPES[4]
    ):
        raise DeepSeekRmsNormValidationError(
            "native RMSNorm gamma stage differs"
        )

    raw_prefill = _load(root / RAW_PREFILL_GRAPH_PATH)
    raw_operators = raw_prefill.get("operators")
    if not isinstance(raw_operators, list) or len(raw_operators) < 5:
        raise DeepSeekRmsNormValidationError(
            "raw prefill graph is missing RMSNorm stages"
        )
    raw_selected = deepcopy(raw_operators[:5])
    if (
        raw_selected[1].get("used_slices")
        != "0b1000000000000000000000000000"
        or raw_selected[1].get("inputs", {}).get("A", {}).get("shape")
        != [1, "used_slices", "sequence_length"]
        or "type"
        in raw_selected[1].get("inputs", {}).get("A", {})
        or raw_selected[2].get("inputs", {}).get("A", {}).get("type")
        != "slice0"
    ):
        raise DeepSeekRmsNormValidationError(
            "upstream raw RMSNorm topology boundary differs"
        )

    prefill = _load(root / PREFILL_GRAPH_PATH)
    operators = prefill.get("operators")
    if not isinstance(operators, list) or len(operators) < 5:
        raise DeepSeekRmsNormValidationError(
            "generated prefill graph is missing RMSNorm stages"
        )
    selected = deepcopy(operators[:5])
    if [item.get("type") for item in selected] != list(OPERATOR_TYPES):
        raise DeepSeekRmsNormValidationError(
            "prefill RMSNorm five-stage type sequence differs"
        )
    if [item.get("id") for item in selected] != [
        f"op{index}" for index in range(5)
    ]:
        raise DeepSeekRmsNormValidationError(
            "prefill RMSNorm stage IDs differ"
        )
    if (
        selected[0].get("used_slices") != ALL_28_MASK
        or selected[1].get("used_slices") != ALL_28_MASK
        or any(
            selected[index].get("used_slices") != ALL_28_MASK
            for index in (2, 3, 4)
        )
    ):
        raise DeepSeekRmsNormValidationError(
            "prefill RMSNorm slice masks differ"
    )
    if (
        selected[1].get("inputs", {}).get("A", {}).get("source")
        != "op0"
        or selected[1].get("inputs", {}).get("A", {}).get("shape")
        != [1, "slice_per_head", "sequence_length"]
        or selected[1].get("inputs", {}).get("A", {}).get("type")
        != "slice0"
        or selected[2].get("inputs", {}).get("A", {}).get("source")
        != "op1"
        or "type" in selected[2].get("inputs", {}).get("A", {})
        or selected[3].get("inputs", {}).get("B", {}).get("source")
        != "op2"
        or selected[4].get("inputs", {}).get("B", {}).get("source")
        != "op3"
    ):
        raise DeepSeekRmsNormValidationError(
            "prefill RMSNorm typed dependency chain differs"
        )

    trusted_package = _load(root / TRUSTED_PACKAGE_GRAPH_PATH)
    trusted_core = trusted_package.get("operators")
    if (
        not isinstance(trusted_core, list)
        or len(trusted_core) != 4
        or [item.get("type") for item in trusted_core]
        != list(OPERATOR_TYPES[:4])
    ):
        raise DeepSeekRmsNormValidationError(
            "trusted RMSNorm package topology differs"
        )
    normalized_core = _without_base_addresses(trusted_core)
    if (
        normalized_core[1].get("used_slices") != ALL_28_MASK
        or normalized_core[1].get("inputs", {}).get("A", {}).get("shape")
        != [1, 4, 32]
        or normalized_core[1].get("inputs", {}).get("A", {}).get("type")
        != "slice0"
        or normalized_core[2].get("used_slices") != ALL_28_MASK
        or "type"
        in normalized_core[2].get("inputs", {}).get("A", {})
    ):
        raise DeepSeekRmsNormValidationError(
            "trusted RMSNorm grouped remote-sum semantics differ"
        )
    resolved_core = load_native_execution_plan(
        root, root / PREFILL_GRAPH_PATH
    )["operators"][:4]
    if (
        resolved_core[1]["inputs"]["A"]["shape"] != [1, 4, 32]
        or resolved_core[1]["inputs"]["A"]["type"] != "slice0"
        or resolved_core[2]["inputs"]["A"]["shape"] != [896, 1, 32]
        or resolved_core[2]["inputs"]["A"]["type"] is not None
    ):
        raise DeepSeekRmsNormValidationError(
            "active RMSNorm Stage does not normalize to trusted topology"
        )
    resolved_five = load_native_execution_plan(
        root, root / PREFILL_GRAPH_PATH
    )["operators"][:5]
    for index, operator in enumerate(selected):
        for port, spec in operator.get("inputs", {}).items():
            spec["shape"] = deepcopy(
                resolved_five[index]["inputs"][port]["shape"]
            )
        operator["output"]["shape"] = deepcopy(
            resolved_five[index]["output"]["shape"]
        )
    params = deepcopy(prefill.get("params"))
    if not isinstance(params, dict):
        raise DeepSeekRmsNormValidationError(
            "prefill parameter block is malformed"
        )
    params["target_op"] = "rmsnorm_five_stage_validation"
    return {
        "params": params,
        "used_slices": ALL_28_MASK,
        "operators": selected,
    }


def validate_rmsnorm_graph(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_rmsnorm_graph(project_root):
        raise DeepSeekRmsNormValidationError(
            "RMSNorm graph differs from ONNX/crop/native-stage evidence"
        )


def materialize_rmsnorm_native_e2(
    project_root: Path, python_executable: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    graph = build_rmsnorm_graph(root)
    validate_rmsnorm_graph(graph, root)
    return run_double_isolated_native_graph(
        project_root=root,
        artifact_root_relative=ARTIFACT_ROOT,
        graph_name=GRAPH_NAME,
        graph=graph,
        operator_types=OPERATOR_TYPES,
        sfu_types=("REC_SQRT",),
        python_executable=python_executable.resolve(),
    )


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise DeepSeekRmsNormValidationError(
            f"required RMSNorm evidence is missing: {relative}"
        )
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _ga_opcodes(config: Mapping[str, Any]) -> list[str]:
    pe_array = config.get("general_array", {}).get("PE_array")
    if not isinstance(pe_array, Mapping):
        raise DeepSeekRmsNormValidationError(
            "RMSNorm materialized JSON has no GA PE_array"
        )
    return sorted(
        {
            str(value.get("alu_opcode"))
            for value in pe_array.values()
            if isinstance(value, Mapping)
        }
    )


def _build_rmsnorm_partial_contract_legacy(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    graph = build_rmsnorm_graph(root)
    graph_path = root / GRAPH_PATH
    if _load(graph_path) != graph:
        raise DeepSeekRmsNormValidationError(
            "RMSNorm v1 graph differs from current evidence"
        )
    normalized = load_native_execution_plan(root, graph_path)
    output_relative = (
        f"{ARTIFACT_ROOT}/a/t/model_execplan/output/{GRAPH_NAME}"
    )
    output = root / output_relative
    stdout_relative = f"{ARTIFACT_ROOT}/a/native_stdout.log"
    stderr_relative = f"{ARTIFACT_ROOT}/a/native_stderr.log"
    stdout = (root / stdout_relative).read_text(encoding="utf-8")
    stderr = (root / stderr_relative).read_text(encoding="utf-8")
    expected_failure = (
        "Input manifest base_addr source slice is not available in "
        "assignment: operator=op2, input=A, write_slice=27, "
        "source_slice=0"
    )
    if (
        "Parsed operators: 5" not in stdout
        or "Generated commands: 313" not in stdout
        or expected_failure not in stderr
    ):
        raise DeepSeekRmsNormValidationError(
            "RMSNorm v1 native failure identity differs"
        )

    configs: list[dict[str, Any]] = []
    mapping_penalties: dict[str, float] = {}
    for index, op_type in enumerate(OPERATOR_TYPES):
        op_id = f"op{index}"
        config_relative = (
            f"{output_relative}/jsons/{op_id}_{op_type}.json"
        )
        review_relative = (
            f"{output_relative}/config/{op_id}/mapping_review.json"
        )
        config = _load(root / config_relative)
        review = _load(root / review_relative)
        penalty = _compute_native_mapping_penalty(root, review)
        if penalty != 0:
            raise DeepSeekRmsNormValidationError(
                f"{op_id} partial mapping penalty is {penalty}"
            )
        mapping_penalties[op_id] = penalty
        configs.append(config)

    if _ga_opcodes(configs[0]) != ["mul", "summac"]:
        raise DeepSeekRmsNormValidationError(
            "RMSNorm local square/summac topology differs"
        )
    if _ga_opcodes(configs[1]) != ["sum"]:
        raise DeepSeekRmsNormValidationError(
            "RMSNorm remote-sum topology differs"
        )
    if _ga_opcodes(configs[2]) != ["mac", "rec_sqrt"]:
        raise DeepSeekRmsNormValidationError(
            "RMSNorm mean/epsilon/reciprocal-sqrt topology differs"
        )
    if _ga_opcodes(configs[3]) != ["mul"] or _ga_opcodes(
        configs[4]
    ) != ["mul"]:
        raise DeepSeekRmsNormValidationError(
            "RMSNorm factor/gamma multiply topology differs"
        )
    if (
        configs[4].get("general_array", {})
        .get("outport", {})
        .get("fp32tofp16")
        != "true"
    ):
        raise DeepSeekRmsNormValidationError(
            "RMSNorm gamma stage fp32-to-fp16 conversion differs"
        )

    remote = configs[1]
    remote_lc = remote.get("dram_loop_configs", {})
    remote_stream = remote.get("stream_engine", {}).get("stream0", {})
    if (
        remote_lc.get("LC0", {}).get("end") != 4
        or remote_lc.get("LC1", {}).get("end") != 28
        or remote_stream.get("idx_size") != [31, 0, None]
    ):
        raise DeepSeekRmsNormValidationError(
            "RMSNorm remote-sum occurrence domain differs"
        )
    transaction_bytes = 32
    required_read_bytes = 4 * 28 * transaction_bytes
    producer_bytes_per_slice = 1 * 1 * 32 * 4
    if (
        required_read_bytes != 3584
        or producer_bytes_per_slice != 128
        or required_read_bytes
        != producer_bytes_per_slice * 28
    ):
        raise DeepSeekRmsNormValidationError(
            "RMSNorm remote-sum byte equation differs"
        )

    op2_pe = configs[2].get("general_array", {}).get("PE_array", {})
    mac_lanes = [
        value
        for value in op2_pe.values()
        if isinstance(value, Mapping)
        and value.get("alu_opcode") == "mac"
    ]
    if (
        len(mac_lanes) != 8
        or {
            lane.get("inport1", {}).get("constant")
            for lane in mac_lanes
        }
        != {"1.0 / 896"}
        or {
            lane.get("inport2", {}).get("constant")
            for lane in mac_lanes
        }
        != {1.0e-6}
    ):
        raise DeepSeekRmsNormValidationError(
            "RMSNorm 1/896 or epsilon constants differ"
        )

    payload: dict[str, Any] = {
        "schema": "deepseek-rmsnorm-five-stage-validation-v1",
        "status": "BLOCKED_BEFORE_LOCAL_E2_ACCEPTANCE",
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
            "prefill_graph": _binding(root, PREFILL_GRAPH_PATH),
            "rmsnorm_fragment": _binding(root, RMSNORM_FRAGMENT_PATH),
            "gamma_fragment": _binding(root, GAMMA_FRAGMENT_PATH),
            "isolated_graph": _binding(root, GRAPH_PATH),
        },
        "onnx_to_stage": {
            "onnx_anchor": _onnx_anchor(root),
            "crop_derived_hidden_size": 896,
            "active_slice_count": 28,
            "hidden_elements_per_slice": 32,
            "fused_semantics": (
                "gamma * x / sqrt(mean(x*x, axis=-1) + 1e-6)"
            ),
            "native_stage_sequence": list(OPERATOR_TYPES),
            "gamma_is_separate_stage": True,
            "native_normalized_graph": normalized,
        },
        "trusted_json_semantics_observed": {
            "op0": {
                "role": "per-slice square-and-sum",
                "ga_opcodes": _ga_opcodes(configs[0]),
            },
            "op1": {
                "role": "28-slice remote sum",
                "ga_opcodes": _ga_opcodes(configs[1]),
            },
            "op2": {
                "role": "divide-by-896 plus epsilon plus reciprocal sqrt",
                "ga_opcodes": _ga_opcodes(configs[2]),
                "mac_lane_count": len(mac_lanes),
                "mean_constant": "1.0 / 896",
                "epsilon": 1.0e-6,
            },
            "op3": {
                "role": "broadcast reciprocal RMS over x",
                "ga_opcodes": _ga_opcodes(configs[3]),
            },
            "op4": {
                "role": "gamma multiply and fp32-to-fp16",
                "ga_opcodes": _ga_opcodes(configs[4]),
                "fp32tofp16": True,
            },
        },
        "partial_native_v1": {
            "classification": "NONAUTHORITATIVE_PARTIAL_RUN",
            "natural_completion": False,
            "returncode": 1,
            "parsed_operator_count": 5,
            "generated_command_count_before_failure": 313,
            "mapping_exact_penalties": mapping_penalties,
            "stdout": _binding(root, stdout_relative),
            "stderr": _binding(root, stderr_relative),
            "materialized_jsons_and_bitstreams_are_diagnostic_only": True,
        },
        "blockers": [
            {
                "id": "B_DS_RMSNORM_LEADER_SLICE_ROUTING",
                "classification": "STAGE_LIFECYCLE_SEMANTICS",
                "evidence": {
                    "op1_enabled_output_slices": [27],
                    "op2_input_special_type": "slice0",
                    "op2_write_slice": 27,
                    "requested_source_slice": 0,
                    "available_source_slices": [27],
                    "native_failure": expected_failure,
                },
                "closure_required": (
                    "the remote-sum leader identity and the following "
                    "broadcast router must name the same physical slice"
                ),
            },
            {
                "id": "B_DS_RMSNORM_REMOTE_SUM_GATHER",
                "classification": "ADDRESS_LIFETIME_SEMANTICS",
                "evidence": {
                    "producer_slice_count": 28,
                    "producer_bytes_per_slice": producer_bytes_per_slice,
                    "consumer_slice_count": 1,
                    "transaction_bytes": transaction_bytes,
                    "LC0_iterations": 4,
                    "LC1_iterations": 28,
                    "required_read_bytes": required_read_bytes,
                    "same_slice_available_bytes": producer_bytes_per_slice,
                    "required_to_available_ratio": 28,
                    "cross_slice_route_proven": False,
                },
                "closure_required": (
                    "prove a real 28-source-slice gather or materialize an "
                    "equivalent contiguous leader-slice staging allocation"
                ),
            },
            {
                "id": "B_DS_RMSNORM_CONTROL_FIELD_RESOLUTION",
                "classification": "EXECPLAN_CONTROL_PROVENANCE",
                "evidence": {
                    "unresolved_control_name_count": 8,
                    "unresolved_field_family": (
                        "ga_pe*.general_array.PE_array.PE."
                        "inport1.constant"
                    ),
                    "materialized_json_contains_expected_constants": True,
                    "full_lifecycle_proven": False,
                },
                "closure_required": (
                    "the final lifecycle must either resolve these control "
                    "fields or prove they are config-load-owned and require "
                    "no dynamic Write_Reg update"
                ),
            },
        ],
        "policy_result": {
            "individual_trusted_jsons_invalidated": False,
            "onnx_to_five_stage_semantic_decomposition_closed": True,
            "five_stage_json_lifecycle_accepted": False,
            "advance_to_server_test": False,
            "maximum_evidence_level": "E2_BLOCKED",
        },
        "rule_ids": [
            "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
            "CDA-CONFIG-FULL-REBUILD-PROVENANCE-001",
            "CDA-DEEPSEEK-MODEL-IDENTITY-001",
            "CDA-DEEPSEEK-CROP-EXPLICIT-001",
            "CDA-DEEPSEEK-ONNX-STAGE-DAG-001",
            "CDA-DEEPSEEK-STAGE-JSON-ORACLE-001",
            "CDA-DEEPSEEK-CROSS-SLICE-ROUTE-001",
        ],
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def _rmsnorm_double_run_summary(root: Path) -> dict[str, Any]:
    run_roots = {
        name: root / ARTIFACT_ROOT / name for name in ("a", "b")
    }
    receipts = {
        name: _load(path / "native_run_receipt.json")
        for name, path in run_roots.items()
    }
    deterministic: dict[str, dict[str, Any]] = {}
    for name, receipt in receipts.items():
        if (
            receipt.get("returncode") != 0
            or receipt.get("parsed_operator_count") != 5
            or receipt.get("initial_mapping_cache_file_count") != 0
            or set(receipt.get("mapping_exact_penalties", {}).values())
            != {0.0}
        ):
            raise DeepSeekRmsNormValidationError(
                f"RMSNorm normalized run {name} receipt differs"
            )
        determinism = receipt.get("mapping_determinism", {})
        if (
            determinism.get("random_seed") != 42
            or determinism.get("python_hash_seed") != 0
            or determinism.get("native_source_modified") is not False
        ):
            raise DeepSeekRmsNormValidationError(
                f"RMSNorm normalized run {name} determinism differs"
            )
        deterministic[name] = {
            item["path"]: item
            for item in receipt.get("output_files", [])
            if item.get("path")
            not in {
                f"config/op{index}/placement.png"
                for index in range(5)
            }
        }
    if deterministic["a"] != deterministic["b"]:
        raise DeepSeekRmsNormValidationError(
            "RMSNorm normalized deterministic outputs differ"
        )
    return {
        "run_a": _binding(
            root, f"{ARTIFACT_ROOT}/a/native_run_receipt.json"
        ),
        "run_b": _binding(
            root, f"{ARTIFACT_ROOT}/b/native_run_receipt.json"
        ),
        "returncode": 0,
        "parsed_operator_count": 5,
        "output_file_count_per_run": 61,
        "deterministic_file_count": len(deterministic["a"]),
        "mapping_exact_penalties": receipts["a"][
            "mapping_exact_penalties"
        ],
        "empty_mapping_cache_at_start": True,
        "random_seed": 42,
        "python_hash_seed": 0,
        "deterministic_outputs_byte_identical": True,
    }


def _rmsnorm_sca_d_summary(root: Path, output_relative: str) -> dict[str, Any]:
    value = _load(root / output_relative / "sca_cfg_D.json")
    expected_lengths = {
        "op0": 8,
        "op1": 8,
        "op2": 8,
        "op3": 256,
        "op4": 128,
    }
    result: dict[str, Any] = {}
    for op_id, expected_length in expected_lengths.items():
        entries = [
            item
            for key, item in value.items()
            if re.fullmatch(fr"{op_id}_matrixD_slice\d+", key)
            and isinstance(item, Mapping)
        ]
        lengths = {int(item["length"]) for item in entries}
        if len(entries) != 28 or lengths != {expected_length}:
            raise DeepSeekRmsNormValidationError(
                f"RMSNorm {op_id} SCA_D coverage differs"
            )
        result[op_id] = {
            "slice_count": 28,
            "lines_128b_per_slice": expected_length,
        }
    return result


def _count_fp32_payload(bitstream_64b: Path, value: float) -> int:
    bits = f"{struct.unpack('<I', struct.pack('<f', value))[0]:032b}"
    stream = "".join(
        line.strip()
        for line in bitstream_64b.read_text(
            encoding="ascii"
        ).splitlines()
        if line.strip()
    )
    return stream.count(bits)


def build_rmsnorm_blocker_contract(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    graph = build_rmsnorm_graph(root)
    graph_path = root / GRAPH_PATH
    if _load(graph_path) != graph:
        raise DeepSeekRmsNormValidationError(
            "RMSNorm normalized graph differs from current evidence"
        )
    output_relative = (
        f"{ARTIFACT_ROOT}/a/t/model_execplan/output/{GRAPH_NAME}"
    )
    output = root / output_relative
    raw_graph = _load(root / RAW_PREFILL_GRAPH_PATH)
    raw_ops = raw_graph["operators"][:5]
    normalized_ops = load_native_execution_plan(root, graph_path)[
        "operators"
    ]
    raw_gap = {
        "raw_op1_used_slices": raw_ops[1]["used_slices"],
        "normalized_op1_used_slices": normalized_ops[1]["used_slices"],
        "raw_op1_A_shape": raw_ops[1]["inputs"]["A"]["shape"],
        "normalized_op1_A_shape": normalized_ops[1]["inputs"]["A"]["shape"],
        "raw_op1_A_type": raw_ops[1]["inputs"]["A"].get("type"),
        "normalized_op1_A_type": normalized_ops[1]["inputs"]["A"].get(
            "type"
        ),
        "raw_op2_A_type": raw_ops[2]["inputs"]["A"].get("type"),
        "normalized_op2_A_type": normalized_ops[2]["inputs"]["A"].get(
            "type"
        ),
    }
    expected_gap = {
        "raw_op1_used_slices": "0b1000000000000000000000000000",
        "normalized_op1_used_slices": ALL_28_MASK,
        "raw_op1_A_shape": [1, "used_slices", "sequence_length"],
        "normalized_op1_A_shape": [1, 4, 32],
        "raw_op1_A_type": None,
        "normalized_op1_A_type": "slice0",
        "raw_op2_A_type": "slice0",
        "normalized_op2_A_type": None,
    }
    if raw_gap != expected_gap:
        raise DeepSeekRmsNormValidationError(
            "RMSNorm raw-to-normalized topology gap differs"
        )
    with_addresses = _load(
        output / f"{GRAPH_NAME}_withbaseaddr.json"
    )
    trusted = _load(root / TRUSTED_PACKAGE_GRAPH_PATH)
    if with_addresses["operators"][:4] != trusted["operators"]:
        raise DeepSeekRmsNormValidationError(
            "RMSNorm normalized first four address-bound stages differ "
            "from the trusted package"
        )
    configs = [
        _load(
            output
            / "jsons"
            / f"op{index}_{op_type}.json"
        )
        for index, op_type in enumerate(OPERATOR_TYPES)
    ]
    if (
        _ga_opcodes(configs[0]) != ["mul", "summac"]
        or _ga_opcodes(configs[1]) != ["sum"]
        or _ga_opcodes(configs[2]) != ["mac", "rec_sqrt"]
        or _ga_opcodes(configs[3]) != ["mul"]
        or _ga_opcodes(configs[4]) != ["mul"]
        or configs[4].get("general_array", {})
        .get("outport", {})
        .get("fp32tofp16")
        != "true"
    ):
        raise DeepSeekRmsNormValidationError(
            "RMSNorm normalized materialized topology differs"
        )
    op2_64b = (
        output
        / "config/op2"
        / f"op2_{OPERATOR_TYPES[2]}_bitstream_64b.bin"
    )
    mean_count = _count_fp32_payload(op2_64b, 1.0 / 896.0)
    epsilon_count = _count_fp32_payload(op2_64b, 1.0e-6)
    if mean_count != 8 or epsilon_count != 8:
        raise DeepSeekRmsNormValidationError(
            "RMSNorm final op2 bitstream constants differ"
        )
    config_length = build_deepseek_config_length_audit(root)["families"][
        "rmsnorm"
    ]
    if config_length["status"] != "CLOSED":
        raise DeepSeekRmsNormValidationError(
            "RMSNorm Load_Config length is not closed"
        )
    payload: dict[str, Any] = {
        "schema": "deepseek-rmsnorm-five-stage-validation-v1",
        "status": "LOCAL_E2_ACTIVE_STAGE_PRODUCER_CONFORMANT",
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
            "raw_rmsnorm_fragment": _binding(
                root, RMSNORM_FRAGMENT_PATH
            ),
            "trusted_package_graph": _binding(
                root, TRUSTED_PACKAGE_GRAPH_PATH
            ),
            "gamma_fragment": _binding(root, GAMMA_FRAGMENT_PATH),
            "normalized_graph": _binding(root, GRAPH_PATH),
        },
        "onnx_to_stage": {
            "onnx_anchor": _onnx_anchor(root),
            "crop_derived_hidden_size": 896,
            "active_slice_count": 28,
            "hidden_elements_per_slice": 32,
            "fused_semantics": (
                "gamma * x / sqrt(mean(x*x, axis=-1) + 1e-6)"
            ),
            "normalized_stage_sequence": list(OPERATOR_TYPES),
            "raw_to_normalized_topology_gap": raw_gap,
            "grouped_remote_sum": {
                "head_count": 7,
                "slices_per_head": 4,
                "op1_active_slices": 28,
                "op1_A_shape": [1, 4, 32],
                "op1_relative_source_selector": "slice0",
                "op2_global_source_selector": None,
            },
        },
        "stage_json_bitstream_lifecycle": {
            "native_double_run": _rmsnorm_double_run_summary(root),
            "first_four_address_bound_stages_match_trusted_package": True,
            "materialized_ga_opcodes": {
                f"op{index}": _ga_opcodes(config)
                for index, config in enumerate(configs)
            },
            "op4_fp32tofp16": True,
            "op2_config_loaded_constants": {
                "mean_1_div_896_fp32_occurrences": mean_count,
                "epsilon_1e_minus_6_fp32_occurrences": epsilon_count,
                "expected_physical_mac_lane_count": 8,
                "unresolved_dynamic_control_names_are_config_load_owned": True,
            },
            "config_length": config_length,
            "sca_d": _rmsnorm_sca_d_summary(root, output_relative),
            "structurally_complete": True,
            "rule_normalized_lifecycle_accepted": True,
        },
        "closed_previous_blockers": [
            "B_DS_RMSNORM_LEADER_SLICE_ROUTING",
            "B_DS_RMSNORM_REMOTE_SUM_GATHER",
            "B_DS_RMSNORM_CONTROL_FIELD_RESOLUTION",
            "B_DS_RMSNORM_STAGE_TOPOLOGY_GAP",
        ],
        "blockers": [],
        "policy_result": {
            "individual_trusted_jsons_invalidated": False,
            "onnx_to_five_stage_semantic_decomposition_closed": True,
            "rule_normalized_five_stage_lifecycle_accepted": True,
            "upstream_raw_stage_is_active_stage": False,
            "active_stage_is_sufficient_for_automatic_generation": True,
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
            "CDA-DEEPSEEK-CONFIG-LENGTH-PADDING-001",
            "CDA-DEEPSEEK-RMSNORM-GROUPED-REMOTE-SUM-001",
            "CDA-DEEPSEEK-RMSNORM-STAGE-TOPOLOGY-OWNER-001",
        ],
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_rmsnorm_blocker_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_rmsnorm_blocker_contract(project_root):
        raise DeepSeekRmsNormValidationError(
            "RMSNorm blocker contract differs from current evidence"
        )


__all__ = [
    "ARTIFACT_ROOT",
    "CONTRACT_PATH",
    "DeepSeekRmsNormValidationError",
    "GRAPH_NAME",
    "GRAPH_PATH",
    "OPERATOR_TYPES",
    "build_rmsnorm_graph",
    "build_rmsnorm_blocker_contract",
    "materialize_rmsnorm_native_e2",
    "validate_rmsnorm_graph",
    "validate_rmsnorm_blocker_contract",
]
