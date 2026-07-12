from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from resnet50_pipeline.hashing import canonical_json_bytes
from resnet50_pipeline.model import load_model_graph


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL = PROJECT_ROOT / "artifacts" / "reference_model" / "resnet50-v1-12-int8.onnx"
MODEL_SHA256 = "c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0"


class OnnxGraphCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_model_graph(MODEL, expected_sha256=MODEL_SHA256)

    def test_formal_model_counts_and_interfaces(self) -> None:
        catalog = self.catalog
        self.assertEqual(catalog.model_sha256, MODEL_SHA256)
        self.assertEqual(catalog.model_path, "artifacts/reference_model/resnet50-v1-12-int8.onnx")
        self.assertEqual(catalog.ir_version, 4)
        self.assertEqual(dict(catalog.opsets)[""], 12)
        self.assertEqual(len(catalog.nodes), 78)
        self.assertEqual(
            catalog.operator_counts,
            {
                "DequantizeLinear": 2,
                "Flatten": 1,
                "MaxPool": 1,
                "QLinearAdd": 17,
                "QLinearConv": 53,
                "QLinearGlobalAveragePool": 1,
                "QLinearMatMul": 1,
                "QuantizeLinear": 2,
            },
        )
        kinds = Counter(item.kind for item in catalog.tensors)
        self.assertEqual(kinds["initializer"], 366)
        inputs = [item for item in catalog.tensors if item.tensor_id in catalog.graph_input_ids]
        outputs = [item for item in catalog.tensors if item.tensor_id in catalog.graph_output_ids]
        self.assertEqual([(item.onnx_name, item.dtype, item.shape) for item in inputs], [("data", "float32", ("N", 3, 224, 224))])
        self.assertEqual([(item.onnx_name, item.dtype, item.shape) for item in outputs], [("resnetv17_dense0_fwd", "float32", ("N", 1000))])

    def test_every_node_reference_and_inferred_output_is_auditable(self) -> None:
        catalog = self.catalog
        by_id = {item.tensor_id: item for item in catalog.tensors}
        for node in catalog.nodes:
            self.assertTrue(node.output_tensor_ids)
            for tensor_id in node.input_tensor_ids + node.output_tensor_ids:
                self.assertIn(tensor_id, by_id)
            for tensor_id in node.output_tensor_ids:
                tensor = by_id[tensor_id]
                self.assertNotEqual(tensor.dtype, "unknown")
                self.assertTrue(tensor.shape)
                self.assertEqual(tensor.producer_node_id, node.node_id)
        self.assertTrue(any(len(item.consumer_node_ids) > 1 for item in catalog.tensors))
        self.assertTrue(any(item.shape_source == "supplemental" for item in catalog.tensors))

    def test_stable_ids_and_catalog_are_reproducible(self) -> None:
        second = load_model_graph(MODEL, expected_sha256=MODEL_SHA256)
        self.assertEqual(canonical_json_bytes(self.catalog.to_dict()), canonical_json_bytes(second.to_dict()))

    def test_model_hash_mismatch_fails_before_parsing(self) -> None:
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            load_model_graph(MODEL, expected_sha256="0" * 64)


if __name__ == "__main__":
    unittest.main()
