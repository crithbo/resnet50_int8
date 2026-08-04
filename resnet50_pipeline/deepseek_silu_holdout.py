from __future__ import annotations

import json
import importlib
import math
import os
import re
import shutil
import struct
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .deepseek_onnx_validation import (
    DeepSeekOnnxValidationError,
    build_deepseek_crop_contract,
    build_deepseek_prefill_stage_audit,
)
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .ndpsim_native import _native_module, load_native_execution_plan


SCHEMA = "deepseek-silu-holdout-roundtrip-v1"
HOLDOUT_NAME = "ds_silu_v6"
ARTIFACT_ROOT = (
    "artifacts/operator_config_validation/ds_silu_v6"
)
GRAPH_PATH = f"{ARTIFACT_ROOT}/{HOLDOUT_NAME}.json"
CONTRACT_PATH = (
    "contracts/operator_config/deepseek_silu_holdout_roundtrip_v6.json"
)
READ_RECEIPT_PATH = (
    "contracts/operator_config/"
    "deepseek_onnx_stage_validation_read_receipt_v1.json"
)
CROP_CONTRACT_PATH = (
    "contracts/operator_config/deepseek_ndpsim_crop_contract_v1.json"
)
PREFILL_AUDIT_PATH = (
    "contracts/operator_config/deepseek_onnx_prefill_stage_audit_v1.json"
)
ONNX_INVENTORY_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/onnx_graph_inventory.json"
)
PREFILL_GRAPH_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/layer0_prefill.generated.json"
)
OP_FRAGMENT_PATH = (
    "ndp-sim/model_execplan/op_json/prefill_silu_fp16MN_fp32MN.json"
)
TRUSTED_JSON_PATH = "ndp-sim/jsons/prefill_silu_fp16MN_fp32MN.json"
STATIC_JSON_SHA256 = (
    "08101bdc82d615741d6262db57098b3ba"
    "3acd04cc427c1d0c1297cc68da5cdbd"
)
OP_TYPE = "prefill_silu_fp16MN_fp32MN"
ALL_28_MASK = (1 << 28) - 1
ALL_28_MASK_TEXT = "0b" + ("1" * 28)
TARGET_SHAPE = (1, 32, 64)
SOURCE_SHAPE = (1, 32, 8)
EXPECTED_DIFF_PATHS = {
    "dram_loop_configs.LC1.end",
    "dram_loop_configs.LC2.end",
    "stream_engine.stream0.base_addr",
    "stream_engine.stream0.dim_stride[1]",
    "stream_engine.stream2.base_addr",
    "stream_engine.stream2.dim_stride[1]",
}
VISUALIZATION_EXCLUSIONS = {"config/op0/placement.png"}
MAPPING_SEED = 42
PYTHON_HASH_SEED = 0


class DeepSeekSiluHoldoutError(DeepSeekOnnxValidationError):
    pass


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekSiluHoldoutError(
            f"cannot parse JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DeepSeekSiluHoldoutError(
            f"JSON root must be an object: {path}"
        )
    return value


def _write_object(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise DeepSeekSiluHoldoutError(f"required file is missing: {relative}")
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _relative_binding(base: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(base).as_posix()
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _find_unique(
    items: list[Any], *, key: str, value: Any, label: str
) -> Mapping[str, Any]:
    matches = [
        item
        for item in items
        if isinstance(item, Mapping) and item.get(key) == value
    ]
    if len(matches) != 1:
        raise DeepSeekSiluHoldoutError(
            f"{label} does not resolve uniquely: {key}={value!r}"
        )
    return matches[0]


def _onnx_silu_nodes(inventory: Mapping[str, Any]) -> list[dict[str, Any]]:
    nodes = inventory.get("graph", {}).get("nodes", [])
    if not isinstance(nodes, list):
        raise DeepSeekSiluHoldoutError("ONNX graph node inventory is malformed")
    expected = (
        (
            17,
            "/model/layers.0/mlp/act_fn/Sigmoid",
            "Sigmoid",
            ["/model/layers.0/mlp/gate_proj/MatMul/output_0"],
        ),
        (
            18,
            "/model/layers.0/mlp/act_fn/Mul",
            "Mul",
            [
                "/model/layers.0/mlp/gate_proj/MatMul/output_0",
                "/model/layers.0/mlp/act_fn/Sigmoid/output_0",
            ],
        ),
    )
    result: list[dict[str, Any]] = []
    for index, name, op_type, inputs in expected:
        node = _find_unique(nodes, key="name", value=name, label="ONNX node")
        if (
            node.get("index") != index
            or node.get("op_type") != op_type
            or node.get("inputs") != inputs
        ):
            raise DeepSeekSiluHoldoutError(
                f"ONNX SiLU node differs: {name}"
            )
        result.append(
            {
                "index": index,
                "name": name,
                "op_type": op_type,
                "inputs": deepcopy(inputs),
                "outputs": deepcopy(node.get("outputs")),
            }
        )
    return result


def build_silu_graph(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    crop = build_deepseek_crop_contract(root)
    derived = crop.get("model_dimensions", {}).get("derived", {})
    if (
        derived.get("intermediate_elements_per_slice") != 64
        or derived.get("active_slice_count") != 28
    ):
        raise DeepSeekSiluHoldoutError(
            "crop contract does not derive 64 intermediate elements on 28 slices"
        )

    inventory = _load_object(root / ONNX_INVENTORY_PATH)
    _onnx_silu_nodes(inventory)
    full_graph = _load_object(root / PREFILL_GRAPH_PATH)
    operators = full_graph.get("operators")
    if not isinstance(operators, list):
        raise DeepSeekSiluHoldoutError("prefill graph operators are malformed")
    op39 = _find_unique(
        operators, key="id", value="op39", label="prefill SiLU occurrence"
    )
    if op39.get("type") != OP_TYPE:
        raise DeepSeekSiluHoldoutError("prefill op39 is no longer the SiLU stage")
    inputs = op39.get("inputs")
    output = op39.get("output")
    if not isinstance(inputs, Mapping) or not isinstance(output, Mapping):
        raise DeepSeekSiluHoldoutError("prefill SiLU IO is malformed")
    input_a = inputs.get("A")
    if not isinstance(input_a, Mapping):
        raise DeepSeekSiluHoldoutError("prefill SiLU input A is missing")
    if (
        input_a.get("dtype") != "fp16"
        or input_a.get("source") != "op37"
        or input_a.get("remapping") is not None
        or output.get("remapping") is not None
    ):
        raise DeepSeekSiluHoldoutError(
            "prefill SiLU occurrence no longer has the expected typed edge"
        )

    fragment = _load_object(root / OP_FRAGMENT_PATH)
    fragment_ops = fragment.get("operators")
    if not isinstance(fragment_ops, list):
        raise DeepSeekSiluHoldoutError("SiLU op_json fragment is malformed")
    fragment_op = _find_unique(
        fragment_ops, key="id", value="op0", label="SiLU op_json operator"
    )
    if (
        fragment_op.get("type") != OP_TYPE
        or fragment_op.get("used_slices") != ALL_28_MASK_TEXT
    ):
        raise DeepSeekSiluHoldoutError("SiLU op_json identity differs")

    graph = {
        "params": {
            "hidden_size": 896,
            "intermediate_size": 1792,
            "num_attention_heads": 7,
            "num_key_value_heads": 1,
            "head_dim": 128,
            "num_hidden_layers": 1,
            "sequence_length": 32,
            "slice_per_head": 4,
            "used_slices": 28,
            "target_op": "silu_holdout",
        },
        "used_slices": ALL_28_MASK_TEXT,
        "operators": [
            {
                "id": "op0",
                "type": OP_TYPE,
                "used_slices": ALL_28_MASK_TEXT,
                "inputs": {
                    "A": {
                        "shape": list(TARGET_SHAPE),
                        "dtype": "fp16",
                        "remapping": None,
                        "source": {"type": "external"},
                    }
                },
                "output": {
                    "shape": list(TARGET_SHAPE),
                    "dtype": "fp32",
                    "remapping": None,
                },
            }
        ],
    }
    normalized_path = root / ARTIFACT_ROOT / "_graph_validation_tmp.json"
    # Do not write a pre-generation temporary file. Instead, the caller writes
    # the graph once and then calls validate_silu_graph_payload/native parsing.
    _ = normalized_path
    return graph


def validate_silu_graph_payload(
    value: Mapping[str, Any], project_root: Path
) -> None:
    expected = build_silu_graph(project_root)
    if value != expected:
        raise DeepSeekSiluHoldoutError(
            "DeepSeek SiLU holdout graph differs from ONNX/crop/Stage evidence"
        )


def _copy_tree_without_runtime_state(source: Path, target: Path) -> None:
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "*.pyo", "mapping_cache", "output"
        ),
    )


def _build_tool_copy(root: Path, run_dir: Path) -> tuple[Path, dict[str, Any]]:
    tool_root = run_dir / "t"
    if tool_root.exists():
        raise DeepSeekSiluHoldoutError(
            f"isolated tool target already exists: {tool_root}"
        )
    tool_root.mkdir(parents=True)
    _copy_tree_without_runtime_state(
        root / "ndp-sim" / "bitstream", tool_root / "bitstream"
    )
    _copy_tree_without_runtime_state(
        root / "ndp-sim" / "model_execplan" / "src",
        tool_root / "model_execplan" / "src",
    )
    _copy_tree_without_runtime_state(
        root / "ndp-sim" / "model_execplan" / "config",
        tool_root / "model_execplan" / "config",
    )
    (tool_root / "model_execplan").mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        root / "ndp-sim" / "model_execplan" / "main.py",
        tool_root / "model_execplan" / "main.py",
    )
    (tool_root / "jsons").mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        root / TRUSTED_JSON_PATH,
        tool_root / "jsons" / f"{OP_TYPE}.json",
    )

    cache_dir = tool_root / "bitstream" / "config" / "mapping_cache"
    cache_initial_files = (
        sorted(path.name for path in cache_dir.iterdir())
        if cache_dir.is_dir()
        else []
    )
    if cache_initial_files:
        raise DeepSeekSiluHoldoutError(
            f"isolated mapper cache is not empty: {cache_initial_files}"
        )

    source_files = sorted(
        path
        for path in tool_root.rglob("*")
        if path.is_file()
    )
    manifest = {
        "schema": "deepseek-silu-isolated-tool-copy-v1",
        "source_checkout": {
            "path": "ndp-sim",
            "active_checkout_mutated": False,
        },
        "cache_initial_file_count": 0,
        "files": [
            _relative_binding(tool_root, path) for path in source_files
        ],
    }
    manifest["manifest_sha256"] = sha256_bytes(
        canonical_json_bytes(manifest)
    )
    _write_object(run_dir / "tool_source_manifest.json", manifest)
    return tool_root, manifest


def _run_native_once(
    root: Path,
    graph: Mapping[str, Any],
    run_name: str,
    python_executable: Path,
) -> dict[str, Any]:
    run_dir = root / ARTIFACT_ROOT / run_name
    if run_dir.exists():
        raise DeepSeekSiluHoldoutError(
            f"isolated run target already exists: {run_dir}"
        )
    run_dir.mkdir(parents=True)
    tool_root, source_manifest = _build_tool_copy(root, run_dir)
    input_dir = tool_root / "input"
    input_dir.mkdir(parents=True)
    graph_path = input_dir / f"{HOLDOUT_NAME}.json"
    _write_object(graph_path, graph)
    seed_hook_dir = run_dir / "seed_hook"
    seed_hook_dir.mkdir()
    seed_hook_path = seed_hook_dir / "sitecustomize.py"
    seed_hook_path.write_text(
        "import random\n"
        f"random.seed({MAPPING_SEED})\n",
        encoding="utf-8",
    )

    command = [
        str(python_executable),
        str(tool_root / "model_execplan" / "main.py"),
        str(graph_path),
    ]
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": str(PYTHON_HASH_SEED),
        "PYTHONPATH": os.pathsep.join(
            filter(
                None,
                (
                    str(seed_hook_dir.resolve()),
                    os.environ.get("PYTHONPATH"),
                ),
            )
        ),
    }
    completed = subprocess.run(
        command,
        cwd=tool_root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )
    stdout_path = run_dir / "native_stdout.log"
    stderr_path = run_dir / "native_stderr.log"
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise DeepSeekSiluHoldoutError(
            f"native model_execplan failed in {run_name}: "
            f"rc={completed.returncode}"
        )
    if "Parsed operators: 1" not in completed.stdout:
        raise DeepSeekSiluHoldoutError(
            f"native pipeline did not complete one operator in {run_name}"
        )

    output_dir = (
        tool_root / "model_execplan" / "output" / HOLDOUT_NAME
    )
    _validate_required_output_set(output_dir)
    mapping_review = _load_object(
        output_dir / "config" / "op0" / "mapping_review.json"
    )
    mapping_penalty = _compute_native_mapping_penalty(
        root, mapping_review
    )
    if mapping_penalty != 0:
        raise DeepSeekSiluHoldoutError(
            f"native mapper exact penalty is {mapping_penalty} "
            f"in {run_name}, expected 0"
        )
    cache_dir = tool_root / "bitstream" / "config" / "mapping_cache"
    cache_files = (
        sorted(path for path in cache_dir.iterdir() if path.is_file())
        if cache_dir.is_dir()
        else []
    )
    if len(cache_files) != 1:
        raise DeepSeekSiluHoldoutError(
            f"native mapper did not create exactly one cache receipt in {run_name}"
        )
    receipt = {
        "schema": "deepseek-silu-native-run-receipt-v1",
        "run_name": run_name,
        "command": [
            "<python>",
            "t/model_execplan/main.py",
            f"t/input/{HOLDOUT_NAME}.json",
        ],
        "returncode": completed.returncode,
        "mapping_exact_penalty": mapping_penalty,
        "mapping_determinism": {
            "seed": MAPPING_SEED,
            "python_hash_seed": PYTHON_HASH_SEED,
            "mechanism": "isolated PYTHONPATH sitecustomize hook",
            "native_source_modified": False,
            "hook": _relative_binding(run_dir, seed_hook_path),
        },
        "initial_mapping_cache_file_count": 0,
        "post_run_mapping_cache": [
            _relative_binding(tool_root, path) for path in cache_files
        ],
        "tool_source_manifest": {
            "path": "tool_source_manifest.json",
            "sha256": source_manifest["manifest_sha256"],
        },
        "stdout": _relative_binding(run_dir, stdout_path),
        "stderr": _relative_binding(run_dir, stderr_path),
        "output_root": output_dir.relative_to(run_dir).as_posix(),
        "output_files": [
            _relative_binding(output_dir, path)
            for path in sorted(output_dir.rglob("*"))
            if path.is_file()
        ],
    }
    receipt["receipt_sha256"] = sha256_bytes(canonical_json_bytes(receipt))
    _write_object(run_dir / "native_run_receipt.json", receipt)
    return receipt


def _required_output_paths() -> set[str]:
    stem = f"op0_{OP_TYPE}"
    return {
        f"jsons/{stem}.json",
        "config/op0/parsed_bitstream.txt",
        "config/op0/mapping_review.json",
        "config/op0/detailed_dump.txt",
        "config/op0/placement.png",
        "config/op0/modules_dump_64b.bin",
        "config/op0/modules_dump_128b.bin",
        f"config/op0/{stem}_bitstream_64b.bin",
        f"config/op0/{stem}_bitstream_128b.bin",
        "install/execplan.txt",
        "install/execplan_op0.txt",
        f"install/cfg_pkg/{stem}_bitstream_128b.bin",
        "install/cfg_pkg/SiLU.txt",
        "instructions_explained.txt",
        "sca_cfg.json",
        "sca_cfg_D.json",
        f"{HOLDOUT_NAME}_withbaseaddr.json",
    }


def _validate_required_output_set(output_dir: Path) -> None:
    if not output_dir.is_dir():
        raise DeepSeekSiluHoldoutError(
            f"native output directory is missing: {output_dir}"
        )
    actual = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    missing = sorted(_required_output_paths() - actual)
    if missing:
        raise DeepSeekSiluHoldoutError(
            f"native pipeline silently omitted required artifacts: {missing}"
        )
    for relative in (
        "config/op0/parsed_bitstream.txt",
        "config/op0/mapping_review.json",
        "install/execplan.txt",
        "sca_cfg.json",
        "sca_cfg_D.json",
    ):
        if (output_dir / relative).stat().st_size <= 0:
            raise DeepSeekSiluHoldoutError(
                f"required native artifact is empty: {relative}"
            )


def _file_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _compare_isolated_outputs(
    output_a: Path, output_b: Path
) -> dict[str, Any]:
    files_a = _file_map(output_a)
    files_b = _file_map(output_b)
    if set(files_a) != set(files_b):
        raise DeepSeekSiluHoldoutError(
            "isolated native output file sets differ"
        )
    deterministic_paths = sorted(set(files_a) - VISUALIZATION_EXCLUSIONS)
    mismatches = [
        path
        for path in deterministic_paths
        if files_a[path] != files_b[path]
    ]
    if mismatches:
        raise DeepSeekSiluHoldoutError(
            f"isolated native deterministic outputs differ: {mismatches}"
        )
    return {
        "same_relative_file_set": True,
        "relative_file_count": len(files_a),
        "deterministic_file_count": len(deterministic_paths),
        "deterministic_files_byte_identical": True,
        "registered_visualization_exclusions": sorted(
            VISUALIZATION_EXCLUSIONS
        ),
        "visualization_hashes": {
            path: {
                "run_a": files_a[path],
                "run_b": files_b[path],
            }
            for path in sorted(VISUALIZATION_EXCLUSIONS)
        },
    }


def _json_diff_paths(
    before: Any, after: Any, prefix: str = ""
) -> list[dict[str, Any]]:
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        paths: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            child = f"{prefix}.{key}" if prefix else str(key)
            if key not in before:
                paths.append(
                    {"path": child, "before": "<missing>", "after": after[key]}
                )
            elif key not in after:
                paths.append(
                    {"path": child, "before": before[key], "after": "<missing>"}
                )
            else:
                paths.extend(_json_diff_paths(before[key], after[key], child))
        return paths
    if isinstance(before, list) and isinstance(after, list):
        paths = []
        for index in range(max(len(before), len(after))):
            child = f"{prefix}[{index}]"
            if index >= len(before):
                paths.append(
                    {
                        "path": child,
                        "before": "<missing>",
                        "after": after[index],
                    }
                )
            elif index >= len(after):
                paths.append(
                    {
                        "path": child,
                        "before": before[index],
                        "after": "<missing>",
                    }
                )
            else:
                paths.extend(
                    _json_diff_paths(before[index], after[index], child)
                )
        return paths
    if before != after:
        return [{"path": prefix, "before": before, "after": after}]
    return []


def _parse_base_addr(value: Any) -> int:
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        raise DeepSeekSiluHoldoutError(
            f"base_addr has unsupported type: {type(value)}"
        )
    text = value.strip().replace("_", "")
    return int(text, 0)


def _pack_dim_stride(port0: int, port1: int, port2: int) -> int:
    for value in (port0, port1, port2):
        if not (0 <= value < (1 << 20)):
            raise DeepSeekSiluHoldoutError(
                f"dim stride does not fit u20: {value}"
            )
    return (port2 << 40) | (port1 << 20) | port0


def validate_silu_materialized_json_payload(
    payload: Mapping[str, Any], project_root: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    trusted = _load_object(root / TRUSTED_JSON_PATH)
    if sha256_file(root / TRUSTED_JSON_PATH) != STATIC_JSON_SHA256:
        raise DeepSeekSiluHoldoutError("trusted SiLU JSON identity differs")
    diffs = _json_diff_paths(trusted, payload)
    diff_paths = {item["path"] for item in diffs}
    if diff_paths != EXPECTED_DIFF_PATHS:
        raise DeepSeekSiluHoldoutError(
            "materialized SiLU JSON changed unauthorized leaves: "
            f"{sorted(diff_paths)}"
        )

    lc = payload.get("dram_loop_configs")
    streams = payload.get("stream_engine")
    if not isinstance(lc, Mapping) or not isinstance(streams, Mapping):
        raise DeepSeekSiluHoldoutError(
            "materialized SiLU JSON is missing LC or stream_engine"
        )
    if (
        lc.get("LC0", {}).get("end") != 4
        or lc.get("LC1", {}).get("end") != 32
        or lc.get("LC2", {}).get("end") != 64
    ):
        raise DeepSeekSiluHoldoutError(
            "materialized SiLU LC domains differ from [M/8,N/2,N]"
        )
    read = streams.get("stream0")
    write = streams.get("stream2")
    if not isinstance(read, Mapping) or not isinstance(write, Mapping):
        raise DeepSeekSiluHoldoutError("SiLU A/D streams are missing")
    if read.get("dim_stride") != [32, 1024, None]:
        raise DeepSeekSiluHoldoutError("SiLU read dim_stride differs")
    if write.get("dim_stride") != [32, 2048, None]:
        raise DeepSeekSiluHoldoutError("SiLU write dim_stride differs")

    read_sizes = [
        1 if item is None else int(item) + 1
        for item in read.get("idx_size", [])
    ]
    write_sizes = [
        1 if item is None else int(item) + 1
        for item in write.get("idx_size", [])
    ]
    read_transaction_bytes = math.prod(read_sizes)
    write_transaction_bytes = math.prod(write_sizes)
    read_occurrences = 4 * 32
    write_occurrences = 4 * 64
    input_bytes = math.prod(TARGET_SHAPE) * 2
    output_bytes = math.prod(TARGET_SHAPE) * 4
    if (
        read_transaction_bytes != 32
        or write_transaction_bytes != 32
        or read_transaction_bytes * read_occurrences != input_bytes
        or write_transaction_bytes * write_occurrences != output_bytes
    ):
        raise DeepSeekSiluHoldoutError(
            "SiLU memory transaction byte conservation failed"
        )
    read_spatial = list(read.get("buf_spatial_stride", []))
    write_spatial = list(write.get("buf_spatial_stride", []))
    if (
        read.get("buf_spatial_size") != 16
        or write.get("buf_spatial_size") != 16
        or len(set(read_spatial)) != 16
        or len(set(write_spatial)) != 16
    ):
        raise DeepSeekSiluHoldoutError(
            "SiLU Buffer AG spatial coverage is not 16 unique bytes"
        )
    if {
        (value >> 2, value & 0x3) for value in read_spatial
    } != {
        (bank, byte)
        for bank in range(8)
        for byte in range(2)
    }:
        raise DeepSeekSiluHoldoutError(
            "SiLU input Buffer AG does not cover two bytes on eight banks"
        )

    general = payload.get("general_array")
    if not isinstance(general, Mapping):
        raise DeepSeekSiluHoldoutError("SiLU GA config is missing")
    inport0 = general.get("inport", {}).get("inport0", {})
    outport = general.get("outport", {})
    pe_array = general.get("PE_array", {})
    if (
        inport0.get("fp16tofp32") != "true"
        or outport.get("fp32tofp16") != "false"
        or len(pe_array) != 8
        or any(
            not isinstance(pe, Mapping)
            or pe.get("alu_opcode") != "sfu_activation"
            or pe.get("transout_last_index") is not None
            for pe in pe_array.values()
        )
    ):
        raise DeepSeekSiluHoldoutError(
            "SiLU GA conversion/opcode/normal-outbuffer semantics differ"
        )
    if payload.get("n2n") not in (None, {}):
        raise DeepSeekSiluHoldoutError("isolated SiLU must not enable N2N")

    return {
        "authorized_diff": diffs,
        "read_transaction_bytes": read_transaction_bytes,
        "read_occurrences_per_slice": read_occurrences,
        "read_supply_bytes_per_slice": input_bytes,
        "write_transaction_bytes": write_transaction_bytes,
        "write_occurrences_per_slice": write_occurrences,
        "write_coverage_bytes_per_slice": output_bytes,
        "read_buffer_bank_byte_pairs": [
            {"bank": bank, "byte": byte}
            for bank, byte in sorted(
                (value >> 2, value & 0x3) for value in read_spatial
            )
        ],
        "write_spatial_stride": write_spatial,
        "ga_active_pe_count": len(pe_array),
        "ga_output_path": "normal_outbuffer_non_transout",
        "input_base_addr_slice0": _parse_base_addr(read.get("base_addr")),
        "output_base_addr_slice0": _parse_base_addr(write.get("base_addr")),
    }


def _mapping_dict(mapping_review: Mapping[str, Any]) -> dict[str, str]:
    rows = mapping_review.get("node_to_resource")
    if not isinstance(rows, list):
        raise DeepSeekSiluHoldoutError("mapping_review node_to_resource is missing")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise DeepSeekSiluHoldoutError("mapping_review row is malformed")
        node = row.get("node")
        resource = row.get("resource")
        if not isinstance(node, str) or not isinstance(resource, str):
            raise DeepSeekSiluHoldoutError("mapping_review node/resource is malformed")
        if node in result:
            raise DeepSeekSiluHoldoutError(
                f"mapping_review contains duplicate node: {node}"
            )
        result[node] = resource
    return result


def _native_bitstream_mapper_module(root: Path) -> Any:
    source_root = (root / "ndp-sim").resolve()
    source_text = str(source_root)
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    module = importlib.import_module("bitstream.config.mapper")
    module_path = Path(str(getattr(module, "__file__", ""))).resolve()
    try:
        module_path.relative_to(source_root)
    except ValueError as error:
        raise DeepSeekSiluHoldoutError(
            f"imported bitstream mapper from another repository: {module_path}"
        ) from error
    return module


def _compute_native_mapping_penalty(
    root: Path, mapping_review: Mapping[str, Any]
) -> float:
    mapping = _mapping_dict(mapping_review)
    connection_rows = mapping_review.get("connection_mapping")
    if not isinstance(connection_rows, list):
        raise DeepSeekSiluHoldoutError(
            "mapping_review connection_mapping is missing"
        )
    module = _native_bitstream_mapper_module(root)
    mapper = module.Mapper()
    mapper.node_to_resource = dict(mapping)
    constraints = [
        mapper.LCtoLCConstraint(),
        mapper.LCtoROWLCConstraint(),
        mapper.LCtoStreamConstraint(),
        mapper.LCtoPEConstraint(),
        mapper.PEtoPEConstraint(),
        mapper.PEtoStreamConstraint(),
        mapper.LCtoStreamConstraint(),
        mapper.ROWLCtoColLCConstraint(),
    ]
    cost = 0.0
    for row in connection_rows:
        if not isinstance(row, Mapping):
            raise DeepSeekSiluHoldoutError(
                "mapping_review connection row is malformed"
            )
        src = row.get("src_node")
        dst = row.get("dst_node")
        if not isinstance(src, str) or not isinstance(dst, str):
            raise DeepSeekSiluHoldoutError(
                "mapping_review connection endpoints are malformed"
            )
        if src not in mapping or dst not in mapping:
            cost += 10000.0 * sum(
                node not in mapping for node in (src, dst)
            )
            continue
        if (
            row.get("src_resource") != mapping[src]
            or row.get("dst_resource") != mapping[dst]
        ):
            raise DeepSeekSiluHoldoutError(
                f"mapping_review connection/resource view differs: {src}->{dst}"
            )
        src_type, src_index = mapper.parse_resource(mapping[src])
        dst_type, dst_index = mapper.parse_resource(mapping[dst])
        cost += sum(
            constraint.penalty(
                src_type, src_index, dst_type, dst_index
            )
            for constraint in constraints
        )
    for node, row_resource in mapping.items():
        if ".ROW_LC" not in node:
            continue
        group = node.split(".", maxsplit=1)[0]
        col_node = f"{group}.COL_LC"
        col_resource = mapping.get(col_node)
        if col_resource is None:
            continue
        if (
            row_resource.startswith("ROW_LC")
            and col_resource.startswith("COL_LC")
            and int(row_resource[6:]) != int(col_resource[6:])
        ):
            cost += 10000.0
    return cost


def _extract_field_value(
    register_db: Any, register_values: Mapping[int, int], field_key: str
) -> int:
    binding = register_db.get_field(field_key)
    if binding is None:
        raise DeepSeekSiluHoldoutError(
            f"decoded register field is missing: {field_key}"
        )
    value = 0
    seen = False
    for segment in binding.segments:
        overlap_low = max(segment.low, binding.field_low)
        overlap_high = min(segment.high, binding.field_high)
        if overlap_low > overlap_high:
            continue
        if segment.address not in register_values:
            continue
        seen = True
        width = overlap_high - overlap_low + 1
        segment_offset = overlap_low - segment.low
        field_offset = overlap_low - binding.field_low
        chunk = (
            int(register_values[segment.address]) >> segment_offset
        ) & ((1 << width) - 1)
        value |= chunk << field_offset
    if not seen:
        raise DeepSeekSiluHoldoutError(
            f"decoded register field has no words: {field_key}"
        )
    return value


def _decode_selected_fields(
    root: Path, output_dir: Path, payload: Mapping[str, Any]
) -> dict[str, int]:
    register_module = _native_module(
        root, "execution_plan_generator.register_mapping"
    )
    decoder_module = _native_module(
        root, "execution_plan_generator.config_stream_decoder"
    )
    register_db = register_module.load_register_mapping(
        register_map_csv=(
            root
            / "ndp-sim/model_execplan/config/register_map_with_groups1.csv"
        ),
        config_output_csv=(
            root / "ndp-sim/model_execplan/config/config_output.csv"
        ),
    )
    parsed_path = output_dir / "config/op0/parsed_bitstream.txt"
    stream = decoder_module._load_template_from_bitstream_file(
        {"bitstream_file": parsed_path.name},
        parsed_path.parent,
        register_db,
    )
    state = decoder_module.decode_initial_register_state(stream, register_db)
    mapping = _mapping_dict(
        _load_object(output_dir / "config/op0/mapping_review.json")
    )
    keys: dict[str, str] = {}
    for logical in ("DRAM_LC.LC0", "DRAM_LC.LC1", "DRAM_LC.LC2"):
        resource = mapping.get(logical)
        if not isinstance(resource, str) or not re.fullmatch(r"LC\d+", resource):
            raise DeepSeekSiluHoldoutError(
                f"mapping_review lacks physical LC for {logical}"
            )
        keys[f"{logical}.end"] = (
            f"iga_lc{resource[2:]}.dram_loop_configs.end"
        )
    keys["read.dim_stride"] = "rd_stream0.stream_engine.stream.dim_stride"
    keys["write.dim_stride"] = "wr_stream0.stream_engine.stream.dim_stride"
    keys["read.base_addr"] = "rd_stream0.stream_engine.stream.base_addr"
    keys["write.base_addr"] = "wr_stream0.stream_engine.stream.base_addr"

    decoded = {
        label: _extract_field_value(
            register_db, state.register_values, field_key
        )
        for label, field_key in keys.items()
    }
    expected = {
        "DRAM_LC.LC0.end": 4,
        "DRAM_LC.LC1.end": 32,
        "DRAM_LC.LC2.end": 64,
        "read.dim_stride": _pack_dim_stride(0, 1024, 32),
        "write.dim_stride": _pack_dim_stride(0, 2048, 32),
        "read.base_addr": _parse_base_addr(
            payload["stream_engine"]["stream0"]["base_addr"]
        ),
        "write.base_addr": _parse_base_addr(
            payload["stream_engine"]["stream2"]["base_addr"]
        ),
    }
    if decoded != expected:
        raise DeepSeekSiluHoldoutError(
            f"decoded SiLU fields differ: decoded={decoded}, expected={expected}"
        )
    return decoded


def _decode_execplan_lifecycle(output_dir: Path) -> dict[str, Any]:
    explanation_path = output_dir / "instructions_explained.txt"
    lines = [
        line
        for line in explanation_path.read_text(encoding="utf-8").splitlines()
        if re.match(r"^\d{4}\s+<", line)
    ]
    if not lines:
        raise DeepSeekSiluHoldoutError("execplan explanation has no commands")
    clauses = []
    for line in lines:
        if "Clock_Enable" in line:
            clauses.append("Clock_Enable")
        elif "Load_Config SFU" in line:
            clauses.append("Load_Config_SFU")
        elif "Load_Config for operator" in line:
            clauses.append("Load_Config")
        elif "Write_Reg" in line:
            clauses.append("Write_Reg")
        elif "Start_Comp" in line:
            clauses.append("Start_Comp")
        else:
            clauses.append("Unknown")
    if clauses[0] != "Clock_Enable":
        raise DeepSeekSiluHoldoutError("execplan does not start with Clock_Enable")
    if clauses.count("Load_Config") != 1:
        raise DeepSeekSiluHoldoutError(
            "execplan does not contain exactly one main Load_Config"
        )
    if clauses.count("Load_Config_SFU") != 1:
        raise DeepSeekSiluHoldoutError(
            "execplan does not contain exactly one SiLU SFU Load_Config"
        )
    if clauses[-1] != "Start_Comp" or clauses.count("Start_Comp") != 1:
        raise DeepSeekSiluHoldoutError(
            "execplan does not terminate with one Start_Comp"
        )
    load_main = clauses.index("Load_Config")
    load_sfu = clauses.index("Load_Config_SFU")
    start = clauses.index("Start_Comp")
    if not (0 < load_main < load_sfu < start):
        raise DeepSeekSiluHoldoutError(
            "execplan Load_Config/SFU/Start_Comp order differs"
        )
    unknown = [index for index, clause in enumerate(clauses) if clause == "Unknown"]
    if unknown:
        raise DeepSeekSiluHoldoutError(
            f"execplan contains unclassified commands: {unknown}"
        )
    return {
        "command_count": len(clauses),
        "clock_enable_count": clauses.count("Clock_Enable"),
        "load_config_count": clauses.count("Load_Config"),
        "load_sfu_config_count": clauses.count("Load_Config_SFU"),
        "write_reg_count": clauses.count("Write_Reg"),
        "start_comp_count": clauses.count("Start_Comp"),
        "ordered_command_classes": clauses,
        "slice_mask": ALL_28_MASK_TEXT,
    }


def _validate_sca(output_dir: Path) -> dict[str, Any]:
    sca = _load_object(output_dir / "sca_cfg.json")
    sca_d = _load_object(output_dir / "sca_cfg_D.json")
    a_entries = sorted(
        key for key in sca if re.fullmatch(r"op0_matrixA_slice\d+", key)
    )
    d_entries = sorted(
        key for key in sca_d if re.fullmatch(r"op0_matrixD_slice\d+", key)
    )
    if len(a_entries) != 28 or len(d_entries) != 28:
        raise DeepSeekSiluHoldoutError(
            "SiLU SCA does not cover 28 A and 28 D slices"
        )
    d_lengths = {sca_d[key].get("length") for key in d_entries}
    if d_lengths != {512}:
        raise DeepSeekSiluHoldoutError(
            f"SiLU D readback length differs from 512 lines: {d_lengths}"
        )
    if "op0_config" not in sca or "op0_sfu_config" not in sca:
        raise DeepSeekSiluHoldoutError(
            "SiLU SCA is missing main or SFU config payload"
        )
    stem = f"op0_{OP_TYPE}"
    config_path = (
        output_dir / f"install/cfg_pkg/{stem}_bitstream_128b.bin"
    )
    sfu_path = output_dir / "install/cfg_pkg/SiLU.txt"
    if sha256_file(sfu_path) != sha256_file(
        output_dir.parents[1]
        / "config"
        / "SFU_Coeff"
        / "SiLU.txt"
    ):
        raise DeepSeekSiluHoldoutError(
            "installed SiLU coefficient payload differs from the isolated source"
        )
    config_length = sum(
        1
        for line in config_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ) * 2
    if config_length <= 0:
        raise DeepSeekSiluHoldoutError("SiLU regenerated config_length is zero")
    return {
        "input_a_slice_entries": len(a_entries),
        "output_d_slice_entries": len(d_entries),
        "output_d_128bit_lines_per_slice": 512,
        "main_config_present": True,
        "sfu_config_present": True,
        "regenerated_config_length_64bit_words": config_length,
        "sfu_config_length_64bit_words": sum(
            1
            for line in sfu_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        * 2,
    }


def _numeric_golden() -> dict[str, Any]:
    inputs = np.asarray(
        [-8.0, -4.0, -1.0, -0.5, 0.0, 0.5, 1.0, 4.0, 8.0],
        dtype=np.float16,
    )
    x = inputs.astype(np.float32)
    outputs = x / (np.float32(1.0) + np.exp(-x, dtype=np.float32))

    def fp16_bits(value: np.float16) -> str:
        return f"0x{int(value.view(np.uint16)):04x}"

    def fp32_bits(value: np.float32) -> str:
        return (
            "0x"
            + struct.pack("<f", float(value))[::-1].hex()
        )

    return {
        "formula": "y = fp32(fp16(x)) * sigmoid(fp32(fp16(x)))",
        "onnx_nodes": [
            "/model/layers.0/mlp/act_fn/Sigmoid",
            "/model/layers.0/mlp/act_fn/Mul",
        ],
        "input_dtype": "fp16",
        "output_dtype": "fp32",
        "samples": [
            {
                "input_fp16_bits": fp16_bits(inputs[index]),
                "input_value": float(x[index]),
                "expected_fp32_bits": fp32_bits(outputs[index]),
                "expected_value": float(outputs[index]),
            }
            for index in range(len(inputs))
        ],
        "hardware_numeric_accuracy_claimed": False,
        "scope": (
            "independent ONNX semantic golden only; stock-RTL SFU "
            "approximation accuracy remains outside local E2"
        ),
    }


def materialize_and_run_silu_holdout(
    project_root: Path, python_executable: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    artifact_root = root / ARTIFACT_ROOT
    if artifact_root.exists():
        raise DeepSeekSiluHoldoutError(
            f"holdout artifact root already exists: {artifact_root}"
        )
    graph = build_silu_graph(root)
    artifact_root.mkdir(parents=True)
    graph_path = root / GRAPH_PATH
    _write_object(graph_path, graph)
    validate_silu_graph_payload(graph, root)
    normalized = load_native_execution_plan(root, graph_path)
    normalized_ops = normalized.get("operators", [])
    if (
        len(normalized_ops) != 1
        or normalized_ops[0].get("type") != OP_TYPE
        or normalized_ops[0].get("used_slices") != ALL_28_MASK_TEXT
        or normalized_ops[0].get("inputs", {}).get("A", {}).get("shape")
        != list(TARGET_SHAPE)
        or normalized_ops[0].get("output", {}).get("shape")
        != list(TARGET_SHAPE)
    ):
        raise DeepSeekSiluHoldoutError(
            "native parser does not preserve the isolated SiLU Stage contract"
        )

    run_a = _run_native_once(root, graph, "a", python_executable)
    run_b = _run_native_once(root, graph, "b", python_executable)
    output_a = (
        root
        / ARTIFACT_ROOT
        / "a/t/model_execplan/output"
        / HOLDOUT_NAME
    )
    output_b = (
        root
        / ARTIFACT_ROOT
        / "b/t/model_execplan/output"
        / HOLDOUT_NAME
    )
    comparison = _compare_isolated_outputs(output_a, output_b)
    contract = build_silu_holdout_contract(root)
    _write_object(root / CONTRACT_PATH, contract)
    return {
        "graph": _binding(root, GRAPH_PATH),
        "run_a_receipt_sha256": run_a["receipt_sha256"],
        "run_b_receipt_sha256": run_b["receipt_sha256"],
        "comparison": comparison,
        "contract": _binding(root, CONTRACT_PATH),
    }


def build_silu_holdout_contract(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    crop = build_deepseek_crop_contract(root)
    prefill_audit = build_deepseek_prefill_stage_audit(root)
    expected_attention_blockers = {
        "B_DS_PREFILL_TOP_LEVEL_SLICE_MASK_ENCODING",
        "B_DS_PREFILL_REMOTE_REDUCTION_BYTE_EXTENT",
        "B_DS_PREFILL_LEADER_SLICE_ROUTING",
        "B_DS_PREFILL_EXTERNAL_ALIAS_MANIFEST",
    }
    if set(prefill_audit.get("semantic_blocker_ids", [])) != expected_attention_blockers:
        raise DeepSeekSiluHoldoutError(
            "prefill attention blockers differ; holdout scope must be re-adjudicated"
        )
    graph = _load_object(root / GRAPH_PATH)
    validate_silu_graph_payload(graph, root)
    normalized = load_native_execution_plan(root, root / GRAPH_PATH)
    inventory = _load_object(root / ONNX_INVENTORY_PATH)
    onnx_nodes = _onnx_silu_nodes(inventory)

    run_roots = {
        "run_a": root / ARTIFACT_ROOT / "a",
        "run_b": root / ARTIFACT_ROOT / "b",
    }
    receipts = {
        name: _load_object(run_root / "native_run_receipt.json")
        for name, run_root in run_roots.items()
    }
    outputs = {
        name: (
            run_root
            / "t/model_execplan/output"
            / HOLDOUT_NAME
        )
        for name, run_root in run_roots.items()
    }
    for output in outputs.values():
        _validate_required_output_set(output)
    comparison = _compare_isolated_outputs(
        outputs["run_a"], outputs["run_b"]
    )
    materialized_path = (
        outputs["run_a"] / f"jsons/op0_{OP_TYPE}.json"
    )
    materialized = _load_object(materialized_path)
    materialized_audit = validate_silu_materialized_json_payload(
        materialized, root
    )
    decoded_fields = _decode_selected_fields(
        root, outputs["run_a"], materialized
    )
    lifecycle = _decode_execplan_lifecycle(outputs["run_a"])
    sca = _validate_sca(outputs["run_a"])

    source_manifest_a = _load_object(
        run_roots["run_a"] / "tool_source_manifest.json"
    )
    source_manifest_b = _load_object(
        run_roots["run_b"] / "tool_source_manifest.json"
    )
    source_manifest_a_without_hash = deepcopy(source_manifest_a)
    source_manifest_b_without_hash = deepcopy(source_manifest_b)
    source_manifest_a_without_hash.pop("manifest_sha256", None)
    source_manifest_b_without_hash.pop("manifest_sha256", None)
    if source_manifest_a_without_hash != source_manifest_b_without_hash:
        raise DeepSeekSiluHoldoutError(
            "isolated tool source manifests differ"
        )
    if (
        receipts["run_a"].get("mapping_exact_penalty") != 0
        or receipts["run_b"].get("mapping_exact_penalty") != 0
        or receipts["run_a"].get("initial_mapping_cache_file_count") != 0
        or receipts["run_b"].get("initial_mapping_cache_file_count") != 0
    ):
        raise DeepSeekSiluHoldoutError(
            "isolated mapping did not start empty and finish at exact penalty=0"
        )
    for run_name, receipt in receipts.items():
        determinism = receipt.get("mapping_determinism")
        if (
            not isinstance(determinism, Mapping)
            or determinism.get("seed") != MAPPING_SEED
            or determinism.get("python_hash_seed") != PYTHON_HASH_SEED
            or determinism.get("mechanism")
            != "isolated PYTHONPATH sitecustomize hook"
            or determinism.get("native_source_modified") is not False
        ):
            raise DeepSeekSiluHoldoutError(
                f"{run_name} did not bind the deterministic mapping harness"
            )

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "LOCAL_E2_REFERENCE_CONFORMANT",
        "candidate_release": False,
        "formal_target_config": False,
        "server_package_generated": False,
        "identity_boundary": {
            "onnx_repository_classification": "SEMANTIC_MODEL_MATCH",
            "original_source_identity": False,
            "direct_onnx_shape_equals_stage": False,
            "crop_contract_required": True,
            "crop_contract_status": crop.get("status"),
        },
        "inputs": {
            "read_receipt": _binding(root, READ_RECEIPT_PATH),
            "crop_contract": _binding(root, CROP_CONTRACT_PATH),
            "prefill_audit": _binding(root, PREFILL_AUDIT_PATH),
            "onnx_inventory": _binding(root, ONNX_INVENTORY_PATH),
            "prefill_graph": _binding(root, PREFILL_GRAPH_PATH),
            "silu_op_fragment": _binding(root, OP_FRAGMENT_PATH),
            "trusted_static_json": _binding(root, TRUSTED_JSON_PATH),
            "isolated_graph": _binding(root, GRAPH_PATH),
        },
        "onnx_to_stage": {
            "onnx_nodes": onnx_nodes,
            "fused_semantic_operator": "SiLU(x)=x*Sigmoid(x)",
            "native_prefill_occurrence": "op39",
            "isolated_occurrence": "op0",
            "source_shape": [1, 32, 8],
            "crop_derived_shape": list(TARGET_SHAPE),
            "shape_derivation": "1792 intermediate elements / 28 slices = 64",
            "input_dtype": "fp16",
            "output_dtype": "fp32",
            "input_source": "isolated external stand-in for full-graph op37",
            "used_slices_mask": ALL_28_MASK_TEXT,
            "qparam": "not-applicable",
            "padding": "disabled",
            "tailing": "disabled",
            "n2n": "disabled",
        },
        "native_normalized_graph": normalized,
        "stage_to_json": {
            "classification": "DERIVED_INSTANCE_VALIDATED",
            "trusted_initial_shape": list(SOURCE_SHAPE),
            "target_shape": list(TARGET_SHAPE),
            "shape_owned_updates": {
                "LC0.end": 4,
                "LC1.end": 32,
                "LC2.end": 64,
                "read_dim_stride": [32, 1024, None],
                "write_dim_stride": [32, 2048, None],
            },
            "planner_owned_updates": [
                "stream_engine.stream0.base_addr",
                "stream_engine.stream2.base_addr",
            ],
            "materialized_json": _relative_binding(
                outputs["run_a"], materialized_path
            ),
            "materialized_audit": materialized_audit,
        },
        "json_to_bitstream_roundtrip": {
            "decoded_selected_fields": decoded_fields,
            "lifecycle": lifecycle,
            "sca": sca,
            "required_output_paths": sorted(_required_output_paths()),
        },
        "isolated_rebuilds": {
            "mapping_seed": MAPPING_SEED,
            "python_hash_seed": PYTHON_HASH_SEED,
            "mapping_seed_scope": (
                "harness-only; native source files remain byte-identical"
            ),
            "run_a": {
                "run_receipt": _relative_binding(
                    run_roots["run_a"],
                    run_roots["run_a"] / "native_run_receipt.json",
                ),
                "tool_source_manifest": _relative_binding(
                    run_roots["run_a"],
                    run_roots["run_a"] / "tool_source_manifest.json",
                ),
            },
            "run_b": {
                "run_receipt": _relative_binding(
                    run_roots["run_b"],
                    run_roots["run_b"] / "native_run_receipt.json",
                ),
                "tool_source_manifest": _relative_binding(
                    run_roots["run_b"],
                    run_roots["run_b"] / "tool_source_manifest.json",
                ),
            },
            "comparison": comparison,
        },
        "independent_numeric_golden": _numeric_golden(),
        "full_layer_blockers_not_bypassed": sorted(
            expected_attention_blockers
        ),
        "release_boundary": {
            "maximum_evidence_level": "E2",
            "hardware_dynamic_closed": False,
            "E4": False,
            "E5": False,
            "scope": (
                "one isolated crop-derived SiLU holdout only; not the full "
                "DeepSeek layer and not a formal target config"
            ),
        },
        "rule_ids": [
            "CDA-CONFIG-SEMANTIC-OWNERSHIP-001",
            "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
            "CDA-CONFIG-FULL-REBUILD-PROVENANCE-001",
            "CDA-DEEPSEEK-MODEL-IDENTITY-001",
            "CDA-DEEPSEEK-CROP-EXPLICIT-001",
            "CDA-DEEPSEEK-ONNX-STAGE-DAG-001",
            "CDA-DEEPSEEK-STAGE-JSON-ORACLE-001",
            "CDA-DEEPSEEK-HOLDOUT-ROUNDTRIP-001",
        ],
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_silu_holdout_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_silu_holdout_contract(project_root):
        raise DeepSeekSiluHoldoutError(
            "DeepSeek SiLU holdout contract differs from current evidence"
        )


def validate_bound_bitstream(
    bitstream_path: Path, expected_sha256: str
) -> None:
    if sha256_file(bitstream_path) != expected_sha256:
        raise DeepSeekSiluHoldoutError(
            "DeepSeek SiLU bitstream identity differs"
        )


__all__ = [
    "ARTIFACT_ROOT",
    "CONTRACT_PATH",
    "DeepSeekSiluHoldoutError",
    "build_silu_graph",
    "build_silu_holdout_contract",
    "materialize_and_run_silu_holdout",
    "validate_bound_bitstream",
    "validate_silu_graph_payload",
    "validate_silu_holdout_contract",
    "validate_silu_materialized_json_payload",
]
