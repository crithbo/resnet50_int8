from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import onnx
from onnx import AttributeProto, TensorProto, TypeProto


DEFAULT_MODEL = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/source/onnx/model_fp16.onnx"
)
DEFAULT_OUTPUT = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/onnx_graph_inventory.json"
)
EXPECTED_SHA256 = (
    "0e0f94186141f35235f2cdfc880bd2007faf0e82f8212cd8fedeb2b2fc98f14e"
)


class GraphInspectionError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(8 * 1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _dim(dim: Any) -> int | str | None:
    kind = dim.WhichOneof("value")
    if kind == "dim_value":
        return int(dim.dim_value)
    if kind == "dim_param":
        return str(dim.dim_param)
    return None


def _value_info(value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"name": str(value.name)}
    type_proto = value.type
    kind = type_proto.WhichOneof("value")
    result["type_kind"] = kind
    if kind == "tensor_type":
        tensor = type_proto.tensor_type
        result["elem_type"] = int(tensor.elem_type)
        result["elem_type_name"] = TensorProto.DataType.Name(
            int(tensor.elem_type)
        )
        result["shape"] = [_dim(item) for item in tensor.shape.dim]
    elif kind == "sequence_type":
        result["sequence_elem_kind"] = (
            type_proto.sequence_type.elem_type.WhichOneof("value")
        )
    elif kind == "optional_type":
        result["optional_elem_kind"] = (
            type_proto.optional_type.elem_type.WhichOneof("value")
        )
    return result


def _tensor_descriptor(tensor: TensorProto) -> dict[str, Any]:
    return {
        "name": str(tensor.name),
        "dims": [int(value) for value in tensor.dims],
        "data_type": int(tensor.data_type),
        "data_type_name": TensorProto.DataType.Name(int(tensor.data_type)),
        "data_location": TensorProto.DataLocation.Name(
            int(tensor.data_location)
        ),
        "external_data": {
            str(item.key): str(item.value)
            for item in tensor.external_data
        },
        "raw_data_bytes": len(tensor.raw_data),
        "float_data_count": len(tensor.float_data),
        "int32_data_count": len(tensor.int32_data),
        "int64_data_count": len(tensor.int64_data),
        "double_data_count": len(tensor.double_data),
        "uint64_data_count": len(tensor.uint64_data),
    }


def _attribute(attribute: AttributeProto) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": str(attribute.name),
        "type": AttributeProto.AttributeType.Name(int(attribute.type)),
    }
    if attribute.type == AttributeProto.FLOAT:
        result["value"] = float(attribute.f)
    elif attribute.type == AttributeProto.INT:
        result["value"] = int(attribute.i)
    elif attribute.type == AttributeProto.STRING:
        result["value"] = bytes(attribute.s).decode(
            "utf-8", errors="backslashreplace"
        )
    elif attribute.type == AttributeProto.FLOATS:
        result["value"] = [float(value) for value in attribute.floats]
    elif attribute.type == AttributeProto.INTS:
        result["value"] = [int(value) for value in attribute.ints]
    elif attribute.type == AttributeProto.STRINGS:
        result["value"] = [
            bytes(value).decode("utf-8", errors="backslashreplace")
            for value in attribute.strings
        ]
    elif attribute.type == AttributeProto.TENSOR:
        result["tensor"] = _tensor_descriptor(attribute.t)
    elif attribute.type == AttributeProto.TENSORS:
        result["tensors"] = [
            _tensor_descriptor(value) for value in attribute.tensors
        ]
    elif attribute.type == AttributeProto.GRAPH:
        result["graph"] = {
            "name": str(attribute.g.name),
            "node_count": len(attribute.g.node),
        }
    elif attribute.type == AttributeProto.GRAPHS:
        result["graphs"] = [
            {"name": str(value.name), "node_count": len(value.node)}
            for value in attribute.graphs
        ]
    elif attribute.type == AttributeProto.TYPE_PROTO:
        result["type_proto_kind"] = attribute.tp.WhichOneof("value")
    elif attribute.type == AttributeProto.TYPE_PROTOS:
        result["type_proto_kinds"] = [
            value.WhichOneof("value") for value in attribute.type_protos
        ]
    return result


def inspect_graph(model_path: Path) -> dict[str, Any]:
    actual_hash = _sha256(model_path)
    if actual_hash != EXPECTED_SHA256:
        raise GraphInspectionError(
            f"ONNX graph identity differs: {actual_hash}"
        )
    model = onnx.load_model(model_path, load_external_data=False)
    graph = model.graph
    nodes = [
        {
            "index": index,
            "name": str(node.name),
            "op_type": str(node.op_type),
            "domain": str(node.domain),
            "inputs": [str(value) for value in node.input],
            "outputs": [str(value) for value in node.output],
            "attributes": [
                _attribute(attribute) for attribute in node.attribute
            ],
        }
        for index, node in enumerate(graph.node)
    ]
    op_counts = Counter(node["op_type"] for node in nodes)
    initializers = [
        _tensor_descriptor(value) for value in graph.initializer
    ]
    external_initializers = sum(
        bool(value["external_data"]) for value in initializers
    )
    embedded_initializer_bytes = sum(
        int(value["raw_data_bytes"]) for value in initializers
    )
    return {
        "schema": "deepseek-onnx-graph-inventory-v1",
        "source": {
            "path": model_path.as_posix(),
            "size_bytes": model_path.stat().st_size,
            "sha256": actual_hash,
            "load_external_data": False,
            "identity_classification": "SEMANTIC_MODEL_MATCH",
            "original_source_identity": False,
        },
        "model": {
            "ir_version": int(model.ir_version),
            "producer_name": str(model.producer_name),
            "producer_version": str(model.producer_version),
            "domain": str(model.domain),
            "model_version": int(model.model_version),
            "doc_string": str(model.doc_string),
            "opset_import": [
                {"domain": str(item.domain), "version": int(item.version)}
                for item in model.opset_import
            ],
            "metadata_props": {
                str(item.key): str(item.value)
                for item in model.metadata_props
            },
        },
        "graph": {
            "name": str(graph.name),
            "doc_string": str(graph.doc_string),
            "node_count": len(nodes),
            "initializer_count": len(initializers),
            "external_initializer_count": external_initializers,
            "embedded_initializer_raw_bytes": embedded_initializer_bytes,
            "input_count": len(graph.input),
            "output_count": len(graph.output),
            "value_info_count": len(graph.value_info),
            "sparse_initializer_count": len(graph.sparse_initializer),
            "op_type_counts": dict(sorted(op_counts.items())),
            "inputs": [_value_info(value) for value in graph.input],
            "outputs": [_value_info(value) for value in graph.output],
            "value_info": [
                _value_info(value) for value in graph.value_info
            ],
            "initializers": initializers,
            "nodes": nodes,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect the pinned DeepSeek ONNX graph without loading its "
            "external tensor data."
        )
    )
    parser.add_argument("--model", type=Path, default=Path(DEFAULT_MODEL))
    parser.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    value = inspect_graph(args.model.resolve())
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)
    print(
        f"nodes={value['graph']['node_count']} "
        f"initializers={value['graph']['initializer_count']} "
        f"value_info={value['graph']['value_info_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
