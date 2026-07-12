from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

from ..model import ModelGraphCatalog, NodeInfo


@dataclass(frozen=True)
class HwOpInfo:
    hw_op_id: str
    node_id: str
    stage: str
    op_type: str
    input_tensor_ids: tuple[str, ...]
    output_tensor_ids: tuple[str, ...]
    predecessor_hw_op_ids: tuple[str, ...]


@dataclass(frozen=True)
class LoweringManifest:
    model_sha256: str
    hw_ops: tuple[HwOpInfo, ...]
    internal_tensor_ids: tuple[str, ...]
    schema_version: str = "0.1"

    def validate(self, graph: ModelGraphCatalog) -> None:
        if self.schema_version != "0.1":
            raise ValueError("unsupported lowering schema")
        node_ids = {item.node_id for item in graph.nodes}
        graph_tensor_ids = {item.tensor_id for item in graph.tensors}
        tensor_ids = graph_tensor_ids | set(self.internal_tensor_ids)
        hw_ids = [item.hw_op_id for item in self.hw_ops]
        if len(hw_ids) != len(set(hw_ids)):
            raise ValueError("duplicate hw_op stable ID")
        seen: set[str] = set()
        lowered_nodes: set[str] = set()
        for item in self.hw_ops:
            if item.node_id not in node_ids:
                raise ValueError(f"{item.hw_op_id} references an unknown node")
            if not set(item.input_tensor_ids + item.output_tensor_ids) <= tensor_ids:
                raise ValueError(f"{item.hw_op_id} references an unknown tensor")
            if not set(item.predecessor_hw_op_ids) <= seen:
                raise ValueError(f"{item.hw_op_id} has a non-topological predecessor")
            seen.add(item.hw_op_id)
            lowered_nodes.add(item.node_id)
        if lowered_nodes != node_ids:
            raise ValueError("not every ONNX node has a lowering")

    def to_dict(self, graph: ModelGraphCatalog) -> dict[str, object]:
        self.validate(graph)
        return {
            "schema_version": self.schema_version,
            "model_sha256": self.model_sha256,
            "internal_tensor_ids": list(self.internal_tensor_ids),
            "hw_ops": [asdict(item) for item in self.hw_ops],
        }

    def for_node(self, node_id: str) -> tuple[HwOpInfo, ...]:
        return tuple(item for item in self.hw_ops if item.node_id == node_id)


Lowerer = Callable[[NodeInfo], tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...]]


def _single(stage: str, op_type: str) -> Lowerer:
    return lambda node: ((stage, op_type, node.input_tensor_ids, node.output_tensor_ids),)


def _two_stage(
    node: NodeInfo,
    *,
    first_stage: str,
    first_type: str,
    second_stage: str,
    second_type: str,
    first_inputs: tuple[int, ...],
    second_parameter_inputs: tuple[int, ...],
) -> tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...]:
    internal = f"tensor-internal-{node.node_id}-{first_stage}"
    return (
        (
            first_stage,
            first_type,
            tuple(node.input_tensor_ids[index] for index in first_inputs),
            (internal,),
        ),
        (
            second_stage,
            second_type,
            (internal,)
            + tuple(node.input_tensor_ids[index] for index in second_parameter_inputs),
            node.output_tensor_ids,
        ),
    )


def _conv(node: NodeInfo):
    return _two_stage(
        node,
        first_stage="accumulate",
        first_type="ConvInt32Accumulate",
        second_stage="requantize",
        second_type="RequantizeUint8",
        first_inputs=(0, 2, 3, 5, 8),
        second_parameter_inputs=(1, 4, 6, 7),
    )


def _global_average_pool(node: NodeInfo):
    return _two_stage(
        node,
        first_stage="sum",
        first_type="GlobalAverageSumInt32",
        second_stage="requantize",
        second_type="AverageRequantizeUint8",
        first_inputs=(0, 2),
        second_parameter_inputs=(1, 3, 4),
    )


def _matmul(node: NodeInfo):
    return _two_stage(
        node,
        first_stage="accumulate",
        first_type="MatMulInt32Accumulate",
        second_stage="requantize",
        second_type="RequantizeUint8",
        first_inputs=(0, 2, 3, 5),
        second_parameter_inputs=(1, 4, 6, 7),
    )


REGISTRY: dict[str, Lowerer] = {
    "QuantizeLinear": _single("quantize", "QuantizeLinear"),
    "QLinearConv": _conv,
    "MaxPool": _single("pool", "MaxPoolUint8"),
    "QLinearAdd": _single("add_requantize", "QLinearAddUint8"),
    "QLinearGlobalAveragePool": _global_average_pool,
    "Flatten": _single("view", "View"),
    "QLinearMatMul": _matmul,
    "DequantizeLinear": _single("dequantize", "DequantizeLinear"),
}


def lower_model_graph(graph: ModelGraphCatalog) -> LoweringManifest:
    hw_ops: list[HwOpInfo] = []
    internal_tensors: list[str] = []
    for node in graph.nodes:
        try:
            stages = REGISTRY[node.op_type](node)
        except KeyError as error:
            raise ValueError(f"no lowering plugin for ONNX op {node.op_type}") from error
        predecessors: tuple[str, ...] = ()
        for stage_index, (stage, op_type, inputs, outputs) in enumerate(stages):
            hw_op_id = f"hwop-{node.graph_index:04d}-{stage_index:02d}"
            for tensor_id in outputs:
                if tensor_id.startswith("tensor-internal-"):
                    internal_tensors.append(tensor_id)
            hw_ops.append(
                HwOpInfo(
                    hw_op_id=hw_op_id,
                    node_id=node.node_id,
                    stage=stage,
                    op_type=op_type,
                    input_tensor_ids=inputs,
                    output_tensor_ids=outputs,
                    predecessor_hw_op_ids=predecessors,
                )
            )
            predecessors = (hw_op_id,)
    manifest = LoweringManifest(
        model_sha256=graph.model_sha256,
        hw_ops=tuple(hw_ops),
        internal_tensor_ids=tuple(internal_tensors),
    )
    manifest.validate(graph)
    return manifest
