from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass

from ..model import ModelGraphCatalog
from .registry import LoweringManifest


LEGACY_GENERATORS = {
    "QuantizeLinear": "quantizelinear",
    "QLinearConv": "qlinear_conv_plan",
    "MaxPool": "max_pool2d_plan",
    "QLinearAdd": "qlinear_add_plan",
    "QLinearGlobalAveragePool": "qlinear_avg_pool2d_plan",
    "QLinearMatMul": "qlinear_matmul_plan",
    "DequantizeLinear": "dequantizelinear",
}

LEGACY_COUNTS = {
    "QuantizeLinear": 2,
    "QLinearConv": 53,
    "MaxPool": 1,
    "QLinearAdd": 17,
    "QLinearGlobalAveragePool": 1,
    "QLinearMatMul": 1,
    "DequantizeLinear": 2,
}


@dataclass(frozen=True)
class LegacyPrimitiveMapping:
    primitive_index: int
    node_id: str
    node_graph_index: int
    onnx_name: str
    onnx_op_type: str
    legacy_generator: str
    hw_op_ids: tuple[str, ...]


def map_legacy_77(
    graph: ModelGraphCatalog, lowering: LoweringManifest
) -> tuple[LegacyPrimitiveMapping, ...]:
    mappings: list[LegacyPrimitiveMapping] = []
    for node in graph.nodes:
        if node.op_type == "Flatten":
            continue
        try:
            generator = LEGACY_GENERATORS[node.op_type]
        except KeyError as error:
            raise ValueError(f"no legacy ResNet primitive for {node.op_type}") from error
        mappings.append(
            LegacyPrimitiveMapping(
                primitive_index=len(mappings),
                node_id=node.node_id,
                node_graph_index=node.graph_index,
                onnx_name=node.onnx_name,
                onnx_op_type=node.op_type,
                legacy_generator=generator,
                hw_op_ids=tuple(
                    item.hw_op_id for item in lowering.for_node(node.node_id)
                ),
            )
        )
    counts = Counter(item.onnx_op_type for item in mappings)
    if len(mappings) != 77 or dict(counts) != LEGACY_COUNTS:
        raise ValueError(
            f"legacy primitive coverage mismatch: count={len(mappings)}, ops={dict(counts)}"
        )
    return tuple(mappings)


def legacy_mapping_dict(
    graph: ModelGraphCatalog, lowering: LoweringManifest
) -> dict[str, object]:
    mappings = map_legacy_77(graph, lowering)
    flatten = [item for item in graph.nodes if item.op_type == "Flatten"]
    return {
        "schema_version": "0.1",
        "source": "CGRA_SIM/testing/resnet-50-int8/gen_execu_plan_ver1.py",
        "model_sha256": graph.model_sha256,
        "primitive_count": len(mappings),
        "excluded_zero_copy_nodes": [item.node_id for item in flatten],
        "mappings": [asdict(item) for item in mappings],
    }
