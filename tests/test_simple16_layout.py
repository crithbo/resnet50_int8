from __future__ import annotations

import unittest
from dataclasses import asdict

import numpy as np

from resnet50_pipeline.simple16_layout import (
    DequantizeLinearPhysicalLayout,
    QuantizeLinearPhysicalLayout,
    ZeroCopyViewLayout,
)
from resnet50_pipeline.records import ObjectManifest, TensorRecord


class LegacySimple16PhysicalLayoutTests(unittest.TestCase):
    def test_quantize_minimal_tail_round_trip_manifest_and_provenance(self) -> None:
        layout = QuantizeLinearPhysicalLayout()
        logical_input = np.arange(30, dtype=np.float32).reshape(3, 2, 5)
        logical_output = np.arange(30, dtype=np.uint8).reshape(3, 2, 5)
        tensor_ids = {
            "A": "tensor-input",
            "scale": "tensor-scale",
            "zero_point": "tensor-zero-point",
            "D": "tensor-output",
        }
        bundle = layout.forward(
            input_tensor=logical_input,
            scale=np.array([0.25], dtype=np.float32),
            zero_point=np.array([117], dtype=np.uint8),
            output_tensor=logical_output,
            tensor_ids=tensor_ids,
        )

        recovered = layout.inverse(bundle)
        np.testing.assert_array_equal(recovered["tensor-input"], logical_input)
        np.testing.assert_array_equal(recovered["tensor-output"], logical_output)
        np.testing.assert_array_equal(
            recovered["tensor-scale"], np.array([0.25], dtype=np.float32)
        )
        np.testing.assert_array_equal(
            recovered["tensor-zero-point"], np.array([117], dtype=np.uint8)
        )
        report = layout.validate(bundle)
        self.assertEqual(report["slice_count"], 16)
        self.assertEqual(report["port_count"], 4)
        self.assertEqual(report["region_count"], 64)

        input_bytes = layout.explain_coordinate(bundle, "tensor-input", (2, 1, 4))
        self.assertEqual(len(input_bytes), 4)
        self.assertTrue(all(item["slice_id"] == 2 for item in input_bytes))
        self.assertEqual([item["element_byte"] for item in input_bytes], [0, 1, 2, 3])
        scale_bytes = layout.explain_coordinate(bundle, "tensor-scale", (0,))
        self.assertEqual(len(scale_bytes), 16 * 4)
        self.assertEqual({item["slice_id"] for item in scale_bytes}, set(range(16)))

        inactive = bundle.region("A", 3)
        self.assertFalse(inactive.active)
        self.assertEqual(bundle.read("A", 3), bytes(inactive.size_bytes))
        records = {item.port: item for item in bundle.layout_records()}
        self.assertEqual(records["A"].contract_status, "candidate")
        self.assertEqual(records["A"].partition["policy"], "one_batch_item_per_slice")
        self.assertEqual(records["scale"].partition["policy"], "replicated_on_every_slice")
        self.assertEqual(records["D"].packing["byte_order"], "little")
        self.assertEqual(len(records["D"].base_addresses), 16)
        objects = ObjectManifest(
            tensors=[
                TensorRecord(item.tensor_id, item.logical_dtype or "unknown", item.logical_shape)
                for item in records.values()
            ],
            layouts=list(records.values()),
        )
        restored = ObjectManifest.from_dict(objects.to_dict())
        self.assertEqual(
            [asdict(item) for item in restored.layouts],
            [asdict(item) for item in objects.layouts],
        )

    def test_formal_resnet_quantize_shape_round_trip(self) -> None:
        layout = QuantizeLinearPhysicalLayout()
        logical_input = np.zeros((16, 3, 224, 224), dtype=np.float32)
        logical_output = np.full((16, 3, 224, 224), 123, dtype=np.uint8)
        bundle = layout.forward(
            input_tensor=logical_input,
            scale=np.array([0.018], dtype=np.float32),
            zero_point=np.array([114], dtype=np.uint8),
            output_tensor=logical_output,
        )

        recovered = layout.inverse(bundle)
        np.testing.assert_array_equal(recovered["quantize_input"], logical_input)
        np.testing.assert_array_equal(recovered["quantize_output"], logical_output)
        self.assertEqual(bundle.region("A", 0).payload_bytes, 3 * 224 * 224 * 4)
        self.assertEqual(bundle.region("D", 15).payload_bytes, 3 * 224 * 224)

    def test_dense_tail_and_formal_flatten_are_reversible(self) -> None:
        dequantize = DequantizeLinearPhysicalLayout()
        dense_input = np.arange(16 * 1000, dtype=np.uint16).astype(np.uint8).reshape(16, 1000)
        dense_output = (dense_input.astype(np.float32) - 101.0) * np.float32(0.03125)
        dense_bundle = dequantize.forward(
            input_tensor=dense_input,
            scale=np.array([0.03125], dtype=np.float32),
            zero_point=np.array([101], dtype=np.uint8),
            output_tensor=dense_output,
        )
        dense_recovered = dequantize.inverse(dense_bundle)
        np.testing.assert_array_equal(dense_recovered["dequantize_input"], dense_input)
        np.testing.assert_array_equal(dense_recovered["dequantize_output"], dense_output)
        self.assertEqual(dense_bundle.region("A", 0).payload_bytes, 1000)
        self.assertEqual(dense_bundle.region("A", 0).size_bytes, 1008)

        pool_input = np.arange(16 * 2048, dtype=np.uint16).astype(np.uint8).reshape(
            16, 2048, 1, 1
        )
        pool_output = (pool_input.astype(np.float32) - 97.0) * np.float32(0.0625)
        pool_bundle = dequantize.forward(
            input_tensor=pool_input,
            scale=np.array([0.0625], dtype=np.float32),
            zero_point=np.array([97], dtype=np.uint8),
            output_tensor=pool_output,
            tensor_ids={
                "A": "tensor-pool-quantized",
                "scale": "tensor-pool-scale",
                "zero_point": "tensor-pool-zero-point",
                "D": "tensor-pool-float",
            },
        )
        view = ZeroCopyViewLayout()
        proof = view.forward(
            source_bundle=pool_bundle,
            source_tensor_id="tensor-pool-float",
            output_tensor_id="tensor-flatten",
            output_shape=(16, 2048),
            axis=1,
        )
        recovered = view.inverse(proof)
        np.testing.assert_array_equal(recovered["tensor-pool-float"], pool_output)
        np.testing.assert_array_equal(
            recovered["tensor-flatten"], pool_output.reshape(16, 2048)
        )
        report = view.validate(proof)
        self.assertTrue(report["zero_copy"])
        record = proof.layout_record()
        self.assertEqual(record.alias_of, "tensor-pool-float")
        self.assertTrue(record.packing["zero_copy"])
        source_bases = tuple(
            pool_bundle.region("D", slice_id).base_address for slice_id in range(16)
        )
        self.assertEqual(record.base_addresses, source_bases)
        explanation = view.explain_coordinate(proof, (7, 1025))
        self.assertEqual(len(explanation), 4)
        self.assertEqual(explanation[0]["slice_id"], 7)
        self.assertEqual(explanation[0]["source_coordinate"], (7, 1025, 0, 0))
        self.assertTrue(all(item["semantic"] == "zero_copy_alias" for item in explanation))

    def test_corruption_and_unsupported_view_fail_before_downstream_use(self) -> None:
        layout = QuantizeLinearPhysicalLayout()
        bundle = layout.forward(
            input_tensor=np.zeros((1, 3), dtype=np.float32),
            scale=np.array([1.0], dtype=np.float32),
            zero_point=np.array([0], dtype=np.uint8),
            output_tensor=np.zeros((1, 3), dtype=np.uint8),
        )
        payload = bytearray(bundle.read("D", 0))
        payload[-1] = 1
        bundle.payloads[("D", 0)] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "alignment padding is corrupted"):
            layout.validate(bundle)

        clean = DequantizeLinearPhysicalLayout().forward(
            input_tensor=np.zeros((16, 2, 1, 1), dtype=np.uint8),
            scale=np.array([1.0], dtype=np.float32),
            zero_point=np.array([0], dtype=np.uint8),
            output_tensor=np.zeros((16, 2, 1, 1), dtype=np.float32),
        )
        view = ZeroCopyViewLayout()
        with self.assertRaisesRegex(ValueError, "requires axis=1"):
            view.forward(
                source_bundle=clean,
                source_tensor_id="dequantize_output",
                output_tensor_id="bad-view",
                output_shape=(32, 1),
                axis=2,
            )
        with self.assertRaisesRegex(ValueError, "output shape"):
            view.forward(
                source_bundle=clean,
                source_tensor_id="dequantize_output",
                output_tensor_id="bad-shape",
                output_shape=(16, 3),
                axis=1,
            )


if __name__ == "__main__":
    unittest.main()
