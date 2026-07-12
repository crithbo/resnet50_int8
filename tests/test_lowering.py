from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from resnet50_pipeline.hashing import canonical_json_bytes
from resnet50_pipeline.lowering import lower_model_graph
from resnet50_pipeline.model import load_model_graph


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL = PROJECT_ROOT / "artifacts" / "reference_model" / "resnet50-v1-12-int8.onnx"
MODEL_SHA256 = "c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0"


class LoweringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = load_model_graph(MODEL, expected_sha256=MODEL_SHA256)
        cls.lowering = lower_model_graph(cls.graph)

    def test_every_resnet_node_has_stable_lowering(self) -> None:
        self.assertEqual(len(self.lowering.hw_ops), 133)
        self.assertEqual(len(self.lowering.internal_tensor_ids), 55)
        self.assertEqual(
            Counter(item.op_type for item in self.lowering.hw_ops)["ConvInt32Accumulate"],
            53,
        )
        for node in self.graph.nodes:
            lowered = self.lowering.for_node(node.node_id)
            self.assertTrue(lowered)
            self.assertEqual(lowered[-1].output_tensor_ids, node.output_tensor_ids)

    def test_multistage_ops_have_explicit_internal_edges(self) -> None:
        for node in self.graph.nodes:
            lowered = self.lowering.for_node(node.node_id)
            if node.op_type in {"QLinearConv", "QLinearGlobalAveragePool", "QLinearMatMul"}:
                self.assertEqual(len(lowered), 2)
                self.assertEqual(lowered[0].output_tensor_ids, lowered[1].input_tensor_ids[:1])
                self.assertEqual(lowered[1].predecessor_hw_op_ids, (lowered[0].hw_op_id,))
            else:
                self.assertEqual(len(lowered), 1)

    def test_lowering_is_reproducible(self) -> None:
        second = lower_model_graph(self.graph)
        self.assertEqual(
            canonical_json_bytes(self.lowering.to_dict(self.graph)),
            canonical_json_bytes(second.to_dict(self.graph)),
        )


if __name__ == "__main__":
    unittest.main()
