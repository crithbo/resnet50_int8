from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.lowering import lower_model_graph, map_legacy_77
from resnet50_pipeline.model import load_model_graph


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL = PROJECT_ROOT / "artifacts" / "reference_model" / "resnet50-v1-12-int8.onnx"


class LegacyMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = load_model_graph(MODEL)
        cls.lowering = lower_model_graph(cls.graph)
        cls.mapping = map_legacy_77(cls.graph, cls.lowering)

    def test_old_77_primitive_order_maps_every_non_view_node(self) -> None:
        self.assertEqual(len(self.mapping), 77)
        self.assertEqual(
            [item.primitive_index for item in self.mapping], list(range(77))
        )
        self.assertEqual(self.mapping[0].legacy_generator, "quantizelinear")
        self.assertEqual(self.mapping[-1].legacy_generator, "dequantizelinear")
        mapped_nodes = {item.node_id for item in self.mapping}
        excluded = [item for item in self.graph.nodes if item.node_id not in mapped_nodes]
        self.assertEqual([(item.graph_index, item.op_type) for item in excluded], [(73, "Flatten")])

    def test_each_legacy_primitive_points_to_current_semantic_hw_ops(self) -> None:
        for item in self.mapping:
            expected = tuple(
                hw_op.hw_op_id for hw_op in self.lowering.for_node(item.node_id)
            )
            self.assertEqual(item.hw_op_ids, expected)
            if item.onnx_op_type in {
                "QLinearConv",
                "QLinearGlobalAveragePool",
                "QLinearMatMul",
            }:
                self.assertEqual(len(item.hw_op_ids), 2)
            else:
                self.assertEqual(len(item.hw_op_ids), 1)


if __name__ == "__main__":
    unittest.main()
