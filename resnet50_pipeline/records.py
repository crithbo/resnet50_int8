from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class TensorRecord:
    tensor_id: str
    dtype: str
    shape: tuple[int | str, ...]


@dataclass(frozen=True)
class NodeRecord:
    node_id: str
    op_type: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]


@dataclass(frozen=True)
class HwOpRecord:
    hw_op_id: str
    node_id: str
    op_type: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]


@dataclass(frozen=True)
class LayoutRecord:
    layout_id: str
    tensor_id: str
    transform: str
    contract_status: str
    port: str | None = None
    logical_shape: tuple[int | str, ...] = ()
    logical_dtype: str | None = None
    partition: dict[str, Any] = field(default_factory=dict)
    packing: dict[str, Any] = field(default_factory=dict)
    base_addresses: tuple[int, ...] = ()
    inverse_status: str | None = None
    alias_of: str | None = None


@dataclass(frozen=True)
class ConfigRecord:
    config_id: str
    hw_op_id: str
    backend: str
    config_version: str


@dataclass(frozen=True)
class ExecutionRecord:
    execution_id: str
    hw_op_id: str
    config_id: str
    backend: str


@dataclass(frozen=True)
class ResultRecord:
    result_id: str
    execution_id: str
    tensor_id: str
    domain: str


@dataclass
class ObjectManifest:
    tensors: list[TensorRecord] = field(default_factory=list)
    nodes: list[NodeRecord] = field(default_factory=list)
    hw_ops: list[HwOpRecord] = field(default_factory=list)
    layouts: list[LayoutRecord] = field(default_factory=list)
    configs: list[ConfigRecord] = field(default_factory=list)
    executions: list[ExecutionRecord] = field(default_factory=list)
    results: list[ResultRecord] = field(default_factory=list)

    @staticmethod
    def _unique(values: list[str], kind: str) -> set[str]:
        if len(values) != len(set(values)):
            raise ValueError(f"duplicate {kind} stable ID")
        return set(values)

    def validate(self) -> None:
        tensor_ids = self._unique([item.tensor_id for item in self.tensors], "tensor")
        node_ids = self._unique([item.node_id for item in self.nodes], "node")
        hw_op_ids = self._unique([item.hw_op_id for item in self.hw_ops], "hw_op")
        layout_ids = self._unique([item.layout_id for item in self.layouts], "layout")
        config_ids = self._unique([item.config_id for item in self.configs], "config")
        execution_ids = self._unique(
            [item.execution_id for item in self.executions], "execution"
        )
        self._unique([item.result_id for item in self.results], "result")

        del layout_ids
        for node in self.nodes:
            unknown = (set(node.inputs) | set(node.outputs)) - tensor_ids
            if unknown:
                raise ValueError(f"node {node.node_id} references unknown tensors: {sorted(unknown)}")
        for hw_op in self.hw_ops:
            if hw_op.node_id not in node_ids:
                raise ValueError(f"hw_op {hw_op.hw_op_id} references unknown node")
            unknown = (set(hw_op.inputs) | set(hw_op.outputs)) - tensor_ids
            if unknown:
                raise ValueError(f"hw_op {hw_op.hw_op_id} references unknown tensors")
        for layout in self.layouts:
            if layout.tensor_id not in tensor_ids:
                raise ValueError(f"layout {layout.layout_id} references unknown tensor")
        for config in self.configs:
            if config.hw_op_id not in hw_op_ids:
                raise ValueError(f"config {config.config_id} references unknown hw_op")
        for execution in self.executions:
            if execution.hw_op_id not in hw_op_ids or execution.config_id not in config_ids:
                raise ValueError(f"execution {execution.execution_id} has an invalid reference")
        for result in self.results:
            if result.execution_id not in execution_ids or result.tensor_id not in tensor_ids:
                raise ValueError(f"result {result.result_id} has an invalid reference")

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        self.validate()
        return {
            "tensors": [asdict(item) for item in self.tensors],
            "nodes": [asdict(item) for item in self.nodes],
            "hw_ops": [asdict(item) for item in self.hw_ops],
            "layouts": [asdict(item) for item in self.layouts],
            "configs": [asdict(item) for item in self.configs],
            "executions": [asdict(item) for item in self.executions],
            "results": [asdict(item) for item in self.results],
        }

    @classmethod
    def from_dict(cls, value: dict[str, list[dict[str, Any]]]) -> "ObjectManifest":
        manifest = cls(
            tensors=[TensorRecord(**{**item, "shape": tuple(item["shape"])}) for item in value["tensors"]],
            nodes=[
                NodeRecord(
                    **{**item, "inputs": tuple(item["inputs"]), "outputs": tuple(item["outputs"])}
                )
                for item in value["nodes"]
            ],
            hw_ops=[
                HwOpRecord(
                    **{**item, "inputs": tuple(item["inputs"]), "outputs": tuple(item["outputs"])}
                )
                for item in value["hw_ops"]
            ],
            layouts=[
                LayoutRecord(
                    **{
                        **item,
                        "logical_shape": tuple(item.get("logical_shape", ())),
                        "base_addresses": tuple(item.get("base_addresses", ())),
                    }
                )
                for item in value["layouts"]
            ],
            configs=[ConfigRecord(**item) for item in value["configs"]],
            executions=[ExecutionRecord(**item) for item in value["executions"]],
            results=[ResultRecord(**item) for item in value["results"]],
        )
        manifest.validate()
        return manifest


def mock_object_manifest(graph: dict[str, Any]) -> ObjectManifest:
    tensors = [
        TensorRecord(item["tensor_id"], item["dtype"], tuple(item["shape"]))
        for item in graph["tensors"]
    ]
    nodes = [
        NodeRecord(item["node_id"], item["op_type"], tuple(item["inputs"]), tuple(item["outputs"]))
        for item in graph["nodes"]
    ]
    node = nodes[0]
    hw_op = HwOpRecord("hwop-0000", node.node_id, node.op_type, node.inputs, node.outputs)
    objects = ObjectManifest(
        tensors=tensors,
        nodes=nodes,
        hw_ops=[hw_op],
        layouts=[
            LayoutRecord("layout-input", node.inputs[0], "identity", "approved_for_w0_only"),
            LayoutRecord("layout-output", node.outputs[0], "identity", "approved_for_w0_only"),
        ],
        configs=[ConfigRecord("config-0000", hw_op.hw_op_id, "mock", "mock-0.1")],
        executions=[ExecutionRecord("exec-0000", hw_op.hw_op_id, "config-0000", "mock")],
        results=[ResultRecord("result-0000", "exec-0000", node.outputs[0], "logical")],
    )
    objects.validate()
    return objects
