from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .deepseek_native_e2 import run_double_isolated_native_graph
from .deepseek_onnx_validation import build_deepseek_crop_contract
from .deepseek_silu_holdout import _compute_native_mapping_penalty
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .ndpsim_native import load_native_execution_plan
from .ndp_config_length import (
    analyze_config_length,
    parse_load_config_length,
)


ARTIFACT_ROOT = "artifacts/operator_config_validation/ds_gemv_ffn_gate_v1"
GRAPH_NAME = "ds_gemv_ffn_gate_v1"
GRAPH_PATH = f"{ARTIFACT_ROOT}/{GRAPH_NAME}.json"
CONTRACT_PATH = (
    "contracts/operator_config/deepseek_gemv_validation_v1.json"
)
READ_RECEIPT_PATH = (
    "contracts/operator_config/deepseek_gemv_read_receipt_v1.json"
)
READ_RECEIPT_SHA256 = (
    "2f697eb0aa02887108df029a55a76f47"
    "c05224d565ce57c58af4da4edabe364f"
)
NUMERIC_AUDIT_PATH = (
    "contracts/operator_config/deepseek_gemv_numeric_audit_v1.json"
)
NUMERIC_AUDIT_FILE_SHA256 = (
    "1f4be49a59549c3f2a87832128df0848"
    "bfb859ed1805322f69676c7f067deaf2"
)
NUMERIC_AUDIT_INTERNAL_SHA256 = (
    "a86d061c54d000179c9d0a5fbdf3ada"
    "fd1ac0b2c6fdcb59a9ab601b2e0d5ee55"
)
DECODE_GRAPH_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/layer0_decode.generated.json"
)
ONNX_INVENTORY_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/onnx_graph_inventory.json"
)
NATIVE_TEMPLATE_PATH = "ndp-sim/jsons/decode_gemv_ring.json"
RELAYOUT_PATH = (
    "ndp-sim/generate_python_golden/single_op_data/relayout_gemv.py"
)
HWVERIFIED_MANIFEST_PATH = (
    "ndp-sim/generate_python_golden/"
    "python_golden_decode_hwverified/manifest.json"
)
OPERATOR_TYPE = "decode_gemv_ring"
ALL_28_MASK = "0b" + ("1" * 28)


class DeepSeekGemvValidationError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekGemvValidationError(
            f"cannot parse GEMV evidence JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DeepSeekGemvValidationError(
            f"JSON root must be an object: {path}"
        )
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise DeepSeekGemvValidationError(
            f"required GEMV evidence is missing: {relative}"
        )
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _onnx_anchor(root: Path) -> dict[str, Any]:
    inventory = _load(root / ONNX_INVENTORY_PATH)
    graph = inventory.get("graph")
    if not isinstance(graph, Mapping):
        raise DeepSeekGemvValidationError(
            "ONNX inventory graph is missing"
        )
    nodes = graph.get("nodes")
    matches = [
        item
        for item in nodes
        if isinstance(item, Mapping)
        and item.get("index") == 15
        and item.get("name")
        == "/model/layers.0/mlp/gate_proj/MatMul"
    ] if isinstance(nodes, list) else []
    if len(matches) != 1 or matches[0].get("op_type") != "MatMul":
        raise DeepSeekGemvValidationError(
            "ONNX layer-0 FFN gate MatMul anchor differs"
        )
    return deepcopy(dict(matches[0]))


def _numeric_audit(root: Path) -> dict[str, Any]:
    path = root / NUMERIC_AUDIT_PATH
    value = _load(path)
    unhashed = dict(value)
    internal_hash = unhashed.pop("audit_sha256", None)
    if (
        sha256_file(path) != NUMERIC_AUDIT_FILE_SHA256
        or internal_hash != NUMERIC_AUDIT_INTERNAL_SHA256
        or internal_hash
        != sha256_bytes(canonical_json_bytes(unhashed))
        or value.get("comparison", {}).get(
            "bitwise_fp16_mismatch_count"
        ) != 0
        or not value.get("comparison", {}).get(
            "bitwise_fp16_equal"
        )
    ):
        raise DeepSeekGemvValidationError(
            "GEMV numeric audit differs"
        )
    return value


def _manifest_case(root: Path) -> dict[str, Any]:
    manifest = _load(root / HWVERIFIED_MANIFEST_PATH)
    operators = manifest.get("instances")
    matches = [
        item
        for item in operators
        if isinstance(item, Mapping)
        and item.get("instance_id") == "ffn_gate_gemv"
        and item.get("op_name") == OPERATOR_TYPE
    ] if isinstance(operators, list) else []
    if len(matches) != 1:
        raise DeepSeekGemvValidationError(
            "hwverified FFN gate GEMV manifest case differs"
        )
    case = deepcopy(dict(matches[0]))
    if (
        case.get("slice_policy") != "gemv_ring"
        or case.get("inputs", [])[0].get("shape")
        != [896, 1792, 1]
        or case.get("inputs", [])[1].get("shape")
        != [896, 1, 1]
        or case.get("output", {}).get("shape")
        != [1792, 1, 1]
    ):
        raise DeepSeekGemvValidationError(
            "hwverified FFN gate GEMV shapes differ"
        )
    return case


def build_gemv_graph(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    receipt = root / READ_RECEIPT_PATH
    if (
        not receipt.is_file()
        or sha256_file(receipt) != READ_RECEIPT_SHA256
        or _load(receipt).get("receipt_status")
        != "GEMV_FFN_GATE_MATERIALIZATION_READY"
    ):
        raise DeepSeekGemvValidationError(
            "GEMV mandatory-read receipt differs"
        )
    crop = build_deepseek_crop_contract(root)
    target = crop.get("model_dimensions", {}).get("target", {})
    derived = crop.get("model_dimensions", {}).get("derived", {})
    if (
        target.get("hidden_size") != 896
        or target.get("intermediate_size") != 1792
        or derived.get("active_slice_count") != 28
    ):
        raise DeepSeekGemvValidationError(
            "crop contract does not derive the FFN gate target"
        )
    _onnx_anchor(root)
    _manifest_case(root)
    _numeric_audit(root)

    decode = _load(root / DECODE_GRAPH_PATH)
    operators = decode.get("operators")
    if not isinstance(operators, list) or len(operators) <= 37:
        raise DeepSeekGemvValidationError(
            "decode graph is missing FFN gate op37"
        )
    op = deepcopy(operators[37])
    if (
        op.get("id") != "op37"
        or op.get("type") != OPERATOR_TYPE
        or op.get("used_slices") != ALL_28_MASK
        or op.get("inputs", {}).get("A", {}).get("source") != "op36"
        or op.get("inputs", {}).get("B", {}).get("source")
        != {"type": "external"}
        or op.get("inputs", {}).get("B'", {}).get("source")
        != {"type": "external"}
    ):
        raise DeepSeekGemvValidationError(
            "decode FFN gate Stage IR differs"
        )
    op["id"] = "op0"
    op["inputs"]["A"]["source"] = {"type": "external"}
    params = decode.get("params")
    if not isinstance(params, dict):
        raise DeepSeekGemvValidationError(
            "decode parameter block is malformed"
        )
    return {
        "params": deepcopy(params),
        "used_slices": 28,
        "operators": [op],
    }


def validate_gemv_graph(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_gemv_graph(project_root):
        raise DeepSeekGemvValidationError(
            "GEMV graph differs from ONNX/crop/decode-stage evidence"
        )


def materialize_gemv_native_e2(
    project_root: Path, python_executable: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    graph = build_gemv_graph(root)
    validate_gemv_graph(graph, root)
    return run_double_isolated_native_graph(
        project_root=root,
        artifact_root_relative=ARTIFACT_ROOT,
        graph_name=GRAPH_NAME,
        graph=graph,
        operator_types=(OPERATOR_TYPE,),
        python_executable=python_executable.resolve(),
        mapping_seed=42,
        inject_bitstream_seed=True,
    )


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
            ) != 42
            or not receipt.get("mapping_determinism", {}).get(
                "explicit_bitstream_seed_injected"
            )
            or receipt_hash
            != sha256_bytes(canonical_json_bytes(unhashed))
        ):
            raise DeepSeekGemvValidationError(
                f"GEMV native run {run_name} receipt differs"
            )
        output_files = receipt.get("output_files")
        if not isinstance(output_files, list):
            raise DeepSeekGemvValidationError(
                f"GEMV native run {run_name} output set differs"
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
        raise DeepSeekGemvValidationError(
            "GEMV isolated native deterministic outputs differ"
        )
    output_files = _load(
        root / f"{ARTIFACT_ROOT}/a/native_run_receipt.json"
    )["output_files"]
    return {
        "runs": receipts,
        "output_file_count_per_run": len(output_files),
        "deterministic_file_count": len(manifests["a"]),
        "excluded_visualization_count": 1,
        "deterministic_outputs_byte_identical": True,
        "native_source_modified": False,
        "empty_cache_at_start": True,
        "random_seed": 42,
        "python_hash_seed": 0,
    }


def _load_config_length(
    explained: Path,
    bitstream_64b: Path,
    bitstream_128b: Path,
) -> dict[str, Any]:
    programmed = parse_load_config_length(explained, "op0")
    analysis = analyze_config_length(
        bitstream_64b,
        bitstream_128b,
        programmed,
    )
    return {
        **analysis,
        "generated_load_config_length_64bit_words": analysis[
            "programmed_load_config_length_64bit_words"
        ],
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
    if len(entries) != 28 or lengths != {8}:
        raise DeepSeekGemvValidationError(
            "GEMV SCA_D output coverage differs"
        )
    return {
        "slice_count": 28,
        "lines_128b_per_slice": 8,
        "bytes_per_slice": 128,
        "total_valid_bytes": 3584,
    }


def build_gemv_validation_contract(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    graph = build_gemv_graph(root)
    graph_path = root / GRAPH_PATH
    if _load(graph_path) != graph:
        raise DeepSeekGemvValidationError(
            "GEMV v1 graph differs from current evidence"
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
        raise DeepSeekGemvValidationError(
            "GEMV generated mapping penalty differs"
        )
    with_addresses = _load(
        output / f"{GRAPH_NAME}_withbaseaddr.json"
    )
    op = with_addresses["operators"][0]
    a_base = int(op["inputs"]["A"]["base_addr"], 16)
    b_base = int(op["inputs"]["B"]["base_addr"], 16)
    bp_base = int(op["inputs"]["B'"]["base_addr"], 16)
    d_base = int(op["output"]["base_addr"], 16)
    if (
        (a_base, b_base, bp_base, d_base)
        != (0x0, 0x40, 0xE040, 0x1C040)
    ):
        raise DeepSeekGemvValidationError(
            "GEMV B/B-prime independent address plan differs"
        )
    ring = generated_json.get("n2n", {}).get("neighbor_stream0", {})
    if (
        ring.get("mem_loop") != 28
        or ring.get("src_slice_sel") != 0
        or ring.get("dst_slice_sel") != 0
    ):
        raise DeepSeekGemvValidationError(
            "GEMV 28-slice ring control differs"
        )
    config_bitstream_128b = (
        output
        / "install/cfg_pkg"
        / f"op0_{OPERATOR_TYPE}_bitstream_128b.bin"
    )
    config_bitstream_64b = (
        output
        / "config/op0"
        / f"op0_{OPERATOR_TYPE}_bitstream_64b.bin"
    )
    config_length = _load_config_length(
        output / "instructions_explained.txt",
        config_bitstream_64b,
        config_bitstream_128b,
    )
    config_blocked = not config_length[
        "matches_rtl_padding_contract"
    ]
    audit = _numeric_audit(root)
    blockers: list[dict[str, Any]] = []
    if config_blocked:
        blockers.append(
            {
                "id": "B_DS_GEMV_CONFIG_LENGTH_PADDING",
                "class": "EXECPLAN_LIFECYCLE",
                "status": "OPEN",
                "reason": (
                    "Load_Config counts the zero high-half padding "
                    "slot instead of the meaningful 64-bit words"
                ),
                "evidence": config_length,
            }
        )
    payload: dict[str, Any] = {
        "schema": "deepseek-gemv-ffn-gate-validation-v1",
        "status": (
            "BLOCKED_AT_CONFIG_LENGTH_PADDING"
            if blockers
            else "LOCAL_E2_REFERENCE_CONFORMANT"
        ),
        "candidate_release": False,
        "formal_target_config": False,
        "server_package_generated": False,
        "identity_boundary": {
            "onnx_repository_classification": "SEMANTIC_MODEL_MATCH",
            "original_source_identity": False,
            "direct_onnx_shape_equals_stage": False,
            "crop_contract_required": True,
            "numeric_oracle_classification": (
                "TRUSTED_CROP_DERIVED_HWVERIFIED_NUMERIC_ORACLE"
            ),
        },
        "inputs": {
            "read_receipt": _binding(root, READ_RECEIPT_PATH),
            "crop_contract": _binding(
                root,
                "contracts/operator_config/"
                "deepseek_ndpsim_crop_contract_v1.json",
            ),
            "onnx_inventory": _binding(root, ONNX_INVENTORY_PATH),
            "decode_graph": _binding(root, DECODE_GRAPH_PATH),
            "native_template": _binding(
                root, NATIVE_TEMPLATE_PATH
            ),
            "relayout_consumer": _binding(root, RELAYOUT_PATH),
            "hwverified_manifest": _binding(
                root, HWVERIFIED_MANIFEST_PATH
            ),
            "numeric_audit": _binding(root, NUMERIC_AUDIT_PATH),
            "isolated_graph": _binding(root, GRAPH_PATH),
        },
        "onnx_to_stage": {
            "anchor": _onnx_anchor(root),
            "source_formula": (
                "[batch,sequence,1536] @ [1536,8960] "
                "-> [batch,sequence,8960]"
            ),
            "crop_decode_formula": (
                "[896,1792].T @ [896] -> [1792]"
            ),
            "hardware_slice_formula": (
                "28 slices; A[32,1,1], B+B'[896,1,64], "
                "D[1,1,64] per slice"
            ),
            "raw_stage_requires_layout_normalization": False,
            "native_normalized_graph": normalized,
        },
        "numeric_oracle": audit,
        "address_layout_and_occurrence": {
            "logical_shapes": {
                "A": [32, 1, 1],
                "B_plus_B_prime": [896, 1, 64],
                "D": [1, 1, 64],
            },
            "per_slice_bytes": {
                "A": 64,
                "B": 57344,
                "B_prime": 57344,
                "D": 128,
            },
            "base_addresses": {
                "A": "0x00000000",
                "B": "0x00000040",
                "B_prime": "0x0000E040",
                "D": "0x0001C040",
            },
            "B_and_B_prime_are_independent_half_allocations": True,
            "ring": {
                "participating_slice_count": 28,
                "n2n_mem_loop": 28,
                "src_slice_sel": 0,
                "dst_slice_sel": 0,
            },
            "sca_d": _sca_d_summary(root, output_relative),
        },
        "stage_json_bitstream_lifecycle": {
            "native_double_run": _native_double_run_summary(root),
            "mapping_review": _binding(root, mapping_relative),
            "mapping_exact_penalty": mapping_penalty,
            "generated_json": _binding(
                root, generated_json_relative
            ),
            "generated_bitstream": _binding(
                root,
                config_bitstream_128b.relative_to(root).as_posix(),
            ),
            "config_length": config_length,
            "structurally_complete": True,
            "semantically_accepted": not blockers,
        },
        "blockers": blockers,
        "policy_result": {
            "raw_stage_is_sufficient_for_json_generation": True,
            "numeric_formula_bitwise_closed": True,
            "B_Bprime_address_split_closed": True,
            "ring_control_closed": True,
            "load_config_length_closed": not config_blocked,
            "local_e2_reference_conformant": not blockers,
            "advance_to_server_test": False,
        },
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_gemv_validation_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    rebuilt = build_gemv_validation_contract(project_root)
    if value != rebuilt:
        raise DeepSeekGemvValidationError(
            "GEMV validation contract differs from current evidence"
        )


__all__ = [
    "ARTIFACT_ROOT",
    "CONTRACT_PATH",
    "DeepSeekGemvValidationError",
    "GRAPH_PATH",
    "OPERATOR_TYPE",
    "build_gemv_graph",
    "build_gemv_validation_contract",
    "materialize_gemv_native_e2",
    "validate_gemv_graph",
    "validate_gemv_validation_contract",
]
