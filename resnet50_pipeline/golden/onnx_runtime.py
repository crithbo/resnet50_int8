from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import onnx
import onnxruntime as ort
from onnx import helper

from ..hashing import sha256_file
from ..model import ModelGraphCatalog, load_model_graph


def _value_info(tensor) -> onnx.ValueInfoProto:
    if tensor.dtype == "unknown" or not tensor.shape:
        raise ValueError(f"cannot expose output with unknown type/shape: {tensor.onnx_name}")
    elem_type = helper.np_dtype_to_tensor_dtype(np.dtype(tensor.dtype))
    shape = [None if item == "?" else item for item in tensor.shape]
    return helper.make_tensor_value_info(tensor.onnx_name, elem_type, shape)


def _session_options() -> ort.SessionOptions:
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.enable_mem_pattern = False
    options.enable_cpu_mem_arena = False
    return options


def run_all_node_outputs(
    model_path: Path,
    input_data: np.ndarray,
    output_root: Path,
    *,
    expected_sha256: str | None = None,
    catalog: ModelGraphCatalog | None = None,
) -> dict[str, Any]:
    graph = catalog or load_model_graph(model_path, expected_sha256=expected_sha256)
    if graph.model_sha256 != sha256_file(model_path):
        raise ValueError("catalog model hash differs from the runtime model")
    by_id = {item.tensor_id: item for item in graph.tensors}
    model = onnx.load(model_path, load_external_data=True)
    existing_outputs = {item.name for item in model.graph.output}
    requested_ids: list[str] = []
    for node in graph.nodes:
        for tensor_id in node.output_tensor_ids:
            requested_ids.append(tensor_id)
            tensor = by_id[tensor_id]
            if tensor.onnx_name not in existing_outputs:
                model.graph.output.append(_value_info(tensor))
                existing_outputs.add(tensor.onnx_name)
    onnx.checker.check_model(model)

    graph_inputs = [by_id[item] for item in graph.graph_input_ids]
    if len(graph_inputs) != 1:
        raise ValueError("W3 runtime currently requires exactly one graph input")
    input_tensor = graph_inputs[0]
    if str(input_data.dtype) != input_tensor.dtype:
        raise TypeError(
            f"input dtype mismatch: expected {input_tensor.dtype}, got {input_data.dtype}"
        )
    expected_tail = input_tensor.shape[1:]
    if tuple(input_data.shape[1:]) != expected_tail:
        raise ValueError(
            f"input shape mismatch after batch axis: expected {expected_tail}, got {input_data.shape[1:]}"
        )

    output_names = [by_id[item].onnx_name for item in requested_ids]
    session = ort.InferenceSession(
        model.SerializeToString(),
        sess_options=_session_options(),
        providers=["CPUExecutionProvider"],
    )
    values = session.run(output_names, {input_tensor.onnx_name: input_data})

    root = output_root.resolve()
    root.parent.mkdir(parents=True, exist_ok=True)
    if root.exists():
        raise FileExistsError(f"golden output root already exists: {root}")
    with tempfile.TemporaryDirectory(prefix=f".{root.name}-", dir=root.parent) as temporary:
        staging = Path(temporary) / root.name
        tensor_dir = staging / "tensors"
        tensor_dir.mkdir(parents=True)
        artifacts: dict[str, dict[str, Any]] = {}

        def save_tensor(tensor_id: str, value: np.ndarray, role: str) -> None:
            path = tensor_dir / f"{tensor_id}.npy"
            np.save(path, np.ascontiguousarray(value), allow_pickle=False)
            artifacts[tensor_id] = {
                "path": path.relative_to(staging).as_posix(),
                "sha256": sha256_file(path),
                "dtype": str(value.dtype),
                "shape": list(value.shape),
                "role": role,
                "onnx_name": by_id[tensor_id].onnx_name,
            }

        save_tensor(input_tensor.tensor_id, input_data, "graph_input")
        for tensor_id, value in zip(requested_ids, values, strict=True):
            save_tensor(tensor_id, value, "node_output")
        manifest = {
            "schema_version": "0.1",
            "model_sha256": graph.model_sha256,
            "runtime": {
                "onnxruntime_version": ort.__version__,
                "providers": session.get_providers(),
                "graph_optimization": "ORT_DISABLE_ALL",
                "execution_mode": "ORT_SEQUENTIAL",
                "intra_op_threads": 1,
                "inter_op_threads": 1,
            },
            "tensors": artifacts,
            "initializers": {
                item.tensor_id: {
                    "onnx_name": item.onnx_name,
                    "sha256": item.initializer_sha256,
                    "dtype": item.dtype,
                    "shape": list(item.shape),
                }
                for item in graph.tensors
                if item.kind == "initializer"
            },
            "nodes": [
                {
                    "node_id": node.node_id,
                    "onnx_name": node.onnx_name,
                    "op_type": node.op_type,
                    "input_tensor_ids": list(node.input_tensor_ids),
                    "output_tensor_ids": list(node.output_tensor_ids),
                }
                for node in graph.nodes
            ],
        }
        manifest_path = staging / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(staging, root)
    return manifest
