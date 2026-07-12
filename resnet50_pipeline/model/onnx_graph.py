from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from onnx import numpy_helper, shape_inference

from ..hashing import sha256_file


@dataclass(frozen=True)
class TensorInfo:
    tensor_id: str
    onnx_name: str
    kind: str
    dtype: str
    shape: tuple[int | str, ...]
    shape_source: str
    producer_node_id: str | None
    consumer_node_ids: tuple[str, ...]
    initializer_sha256: str | None = None


@dataclass(frozen=True)
class NodeInfo:
    node_id: str
    graph_index: int
    onnx_name: str
    op_type: str
    input_tensor_ids: tuple[str, ...]
    output_tensor_ids: tuple[str, ...]
    attributes: dict[str, Any]


@dataclass(frozen=True)
class ModelGraphCatalog:
    model_path: str
    model_sha256: str
    ir_version: int
    opsets: tuple[tuple[str, int], ...]
    tensors: tuple[TensorInfo, ...]
    nodes: tuple[NodeInfo, ...]
    graph_input_ids: tuple[str, ...]
    graph_output_ids: tuple[str, ...]
    schema_version: str = "0.1"

    def validate(self) -> None:
        if self.schema_version != "0.1":
            raise ValueError(f"unsupported model graph catalog schema: {self.schema_version}")
        tensor_ids = [item.tensor_id for item in self.tensors]
        node_ids = [item.node_id for item in self.nodes]
        if len(tensor_ids) != len(set(tensor_ids)):
            raise ValueError("tensor stable ID collision")
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("node stable ID collision")
        known_tensors = set(tensor_ids)
        known_nodes = set(node_ids)
        if not set(self.graph_input_ids + self.graph_output_ids) <= known_tensors:
            raise ValueError("graph interface references an unknown tensor")
        for node in self.nodes:
            if not set(node.input_tensor_ids + node.output_tensor_ids) <= known_tensors:
                raise ValueError(f"{node.node_id} references an unknown tensor")
        for tensor in self.tensors:
            if tensor.producer_node_id is not None and tensor.producer_node_id not in known_nodes:
                raise ValueError(f"{tensor.tensor_id} has an unknown producer")
            if not set(tensor.consumer_node_ids) <= known_nodes:
                raise ValueError(f"{tensor.tensor_id} has an unknown consumer")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @property
    def operator_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(item.op_type for item in self.nodes).items()))


def _tensor_id(name: str) -> str:
    if not name:
        raise ValueError("empty optional ONNX values do not have tensor IDs")
    return "tensor-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]


def _shape_and_dtype(value_info: onnx.ValueInfoProto) -> tuple[tuple[int | str, ...], str]:
    tensor_type = value_info.type.tensor_type
    if not tensor_type.HasField("shape"):
        return (), "unknown"
    shape: list[int | str] = []
    for dimension in tensor_type.shape.dim:
        if dimension.HasField("dim_value"):
            shape.append(int(dimension.dim_value))
        elif dimension.HasField("dim_param") and dimension.dim_param:
            shape.append(dimension.dim_param)
        else:
            shape.append("?")
    if tensor_type.elem_type:
        dtype = str(np.dtype(onnx.helper.tensor_dtype_to_np_dtype(tensor_type.elem_type)))
    else:
        dtype = "unknown"
    return tuple(shape), dtype


def _jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, onnx.GraphProto):
        return {"name": value.name, "node_count": len(value.node)}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _broadcast_shape(left: tuple[int | str, ...], right: tuple[int | str, ...]) -> tuple[int | str, ...]:
    result: list[int | str] = []
    for a, b in zip(reversed(left), reversed(right), strict=False):
        if a == 1:
            result.append(b)
        elif b == 1 or a == b:
            result.append(a)
        else:
            raise ValueError(f"cannot broadcast symbolic dimensions {a!r} and {b!r}")
    longer = left if len(left) > len(right) else right
    result.extend(reversed(longer[: abs(len(left) - len(right))]))
    return tuple(reversed(result))


def _conv_output_shape(
    input_shape: tuple[int | str, ...],
    weight_shape: tuple[int | str, ...],
    attributes: dict[str, Any],
) -> tuple[int | str, ...]:
    if len(input_shape) != 4 or len(weight_shape) != 4:
        raise ValueError("QLinearConv supplemental inference requires rank-4 tensors")
    strides = attributes.get("strides", [1, 1])
    dilations = attributes.get("dilations", [1, 1])
    pads = attributes.get("pads", [0, 0, 0, 0])
    spatial: list[int | str] = []
    for axis in range(2):
        size = input_shape[axis + 2]
        kernel = weight_shape[axis + 2]
        if not isinstance(size, int) or not isinstance(kernel, int):
            spatial.append("?")
        else:
            effective = (kernel - 1) * int(dilations[axis]) + 1
            spatial.append(
                (size + int(pads[axis]) + int(pads[axis + 2]) - effective)
                // int(strides[axis])
                + 1
            )
    return input_shape[0], weight_shape[0], spatial[0], spatial[1]


def _supplemental_output_shapes(
    node: onnx.NodeProto,
    known: dict[str, tuple[tuple[int | str, ...], str]],
) -> list[tuple[tuple[int | str, ...], str]]:
    attrs = {
        attribute.name: _jsonable(onnx.helper.get_attribute_value(attribute))
        for attribute in node.attribute
    }
    get = lambda index: known[node.input[index]]
    if node.op_type in {"QuantizeLinear", "DequantizeLinear", "MaxPool", "Flatten"}:
        shape, dtype = get(0)
        if node.op_type == "QuantizeLinear":
            dtype = get(2)[1]
        elif node.op_type == "DequantizeLinear":
            dtype = "float32"
        elif node.op_type == "Flatten":
            axis = int(attrs.get("axis", 1))
            before = shape[:axis]
            after = shape[axis:]
            left: int | str = int(np.prod(before)) if all(isinstance(v, int) for v in before) else before[0]
            right: int | str = int(np.prod(after)) if all(isinstance(v, int) for v in after) else "?"
            shape = (left, right)
        return [(shape, dtype)]
    if node.op_type == "QLinearConv":
        return [(_conv_output_shape(get(0)[0], get(3)[0], attrs), get(7)[1])]
    if node.op_type == "QLinearAdd":
        return [(_broadcast_shape(get(0)[0], get(3)[0]), get(7)[1])]
    if node.op_type == "QLinearGlobalAveragePool":
        shape = get(0)[0]
        return [((shape[0], shape[1], 1, 1), get(4)[1])]
    if node.op_type == "QLinearMatMul":
        left, right = get(0)[0], get(3)[0]
        return [((left[-2], right[-1]), get(7)[1])]
    return []


def load_model_graph(model_path: Path, *, expected_sha256: str | None = None) -> ModelGraphCatalog:
    path = model_path.resolve()
    digest = sha256_file(path)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(f"model SHA-256 mismatch: expected {expected_sha256}, got {digest}")
    model = onnx.load(path, load_external_data=True)
    onnx.checker.check_model(model)
    inferred = shape_inference.infer_shapes(model, strict_mode=True, data_prop=True)

    node_ids = [f"node-{index:04d}" for index in range(len(inferred.graph.node))]
    producer: dict[str, str] = {}
    consumers: dict[str, list[str]] = {}
    ordered_names: list[str] = []

    def remember(name: str) -> None:
        if name and name not in ordered_names:
            ordered_names.append(name)

    for item in inferred.graph.input:
        remember(item.name)
    for item in inferred.graph.initializer:
        remember(item.name)
    for index, node in enumerate(inferred.graph.node):
        for name in node.input:
            if name:
                remember(name)
                consumers.setdefault(name, []).append(node_ids[index])
        for name in node.output:
            if name:
                remember(name)
                if name in producer:
                    raise ValueError(f"ONNX tensor has multiple producers: {name}")
                producer[name] = node_ids[index]
    for item in inferred.graph.output:
        remember(item.name)
    for item in inferred.graph.value_info:
        remember(item.name)

    value_info = {
        item.name: item
        for item in (*inferred.graph.input, *inferred.graph.value_info, *inferred.graph.output)
    }
    initializers = {item.name: item for item in inferred.graph.initializer}
    supplemental: dict[str, tuple[tuple[int | str, ...], str]] = {}
    known: dict[str, tuple[tuple[int | str, ...], str]] = {}
    for name, item in value_info.items():
        shape, dtype = _shape_and_dtype(item)
        if shape and dtype != "unknown":
            known[name] = (shape, dtype)
    for name, initializer in initializers.items():
        array = numpy_helper.to_array(initializer, base_dir=str(path.parent))
        known[name] = (tuple(int(item) for item in array.shape), str(array.dtype))
    for node in inferred.graph.node:
        missing = [name for name in node.output if name and name not in known]
        if not missing:
            continue
        outputs = _supplemental_output_shapes(node, known)
        if len(outputs) != len([name for name in node.output if name]):
            continue
        for name, metadata in zip((name for name in node.output if name), outputs):
            known[name] = metadata
            supplemental[name] = metadata
    graph_inputs = {item.name for item in inferred.graph.input}
    graph_outputs = {item.name for item in inferred.graph.output}
    tensors: list[TensorInfo] = []
    for name in ordered_names:
        initializer = initializers.get(name)
        if initializer is not None:
            array = np.ascontiguousarray(numpy_helper.to_array(initializer, base_dir=str(path.parent)))
            shape = tuple(int(item) for item in array.shape)
            dtype = str(array.dtype)
            kind = "initializer"
            shape_source = "initializer"
            initializer_sha256 = hashlib.sha256(array.tobytes(order="C")).hexdigest()
        else:
            info = value_info.get(name)
            if name in supplemental:
                shape, dtype = supplemental[name]
                shape_source = "supplemental"
            else:
                shape, dtype = ((), "unknown") if info is None else _shape_and_dtype(info)
                shape_source = "onnx_inference" if info is not None else "unknown"
            kind = (
                "graph_input"
                if name in graph_inputs
                else "graph_output"
                if name in graph_outputs
                else "intermediate"
            )
            initializer_sha256 = None
        tensors.append(
            TensorInfo(
                tensor_id=_tensor_id(name),
                onnx_name=name,
                kind=kind,
                dtype=dtype,
                shape=shape,
                shape_source=shape_source,
                producer_node_id=producer.get(name),
                consumer_node_ids=tuple(consumers.get(name, ())),
                initializer_sha256=initializer_sha256,
            )
        )

    nodes = tuple(
        NodeInfo(
            node_id=node_ids[index],
            graph_index=index,
            onnx_name=node.name,
            op_type=node.op_type,
            input_tensor_ids=tuple(_tensor_id(name) for name in node.input if name),
            output_tensor_ids=tuple(_tensor_id(name) for name in node.output if name),
            attributes={
                attribute.name: _jsonable(onnx.helper.get_attribute_value(attribute))
                for attribute in node.attribute
            },
        )
        for index, node in enumerate(inferred.graph.node)
    )
    catalog = ModelGraphCatalog(
        model_path=(
            path.relative_to(Path.cwd().resolve()).as_posix()
            if path.is_relative_to(Path.cwd().resolve())
            else path.name
        ),
        model_sha256=digest,
        ir_version=int(inferred.ir_version),
        opsets=tuple((item.domain, int(item.version)) for item in inferred.opset_import),
        tensors=tuple(tensors),
        nodes=nodes,
        graph_input_ids=tuple(_tensor_id(item.name) for item in inferred.graph.input),
        graph_output_ids=tuple(_tensor_id(item.name) for item in inferred.graph.output),
    )
    catalog.validate()
    return catalog
