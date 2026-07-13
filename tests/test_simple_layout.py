from __future__ import annotations

import unittest
from dataclasses import asdict

import numpy as np

import resnet50_pipeline.layout as public_layout
from resnet50_pipeline.errors import ContractError
from resnet50_pipeline.memory import (
    LEGACY_DRAM_GEOMETRY16,
    TARGET_DRAM_GEOMETRY28,
)
from resnet50_pipeline.profile28 import (
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
)
from resnet50_pipeline.records import ObjectManifest, TensorRecord
from resnet50_pipeline.simple_layout import (
    DequantizeLinearPhysicalLayout,
    QuantizeLinearPhysicalLayout,
    ZeroCopyViewLayout,
)
from resnet50_pipeline.topology28 import HIGH_RING_OWNERS, LOW_RING_OWNERS


class Rtl28SimpleOperatorPhysicalLayoutTests(unittest.TestCase):
    def test_group4x7_minimal_tail_round_trip_records_and_coordinates(self) -> None:
        layout = QuantizeLinearPhysicalLayout()
        logical_input = np.arange(16 * 5 * 2, dtype=np.float32).reshape(16, 5, 2, 1)
        logical_output = np.arange(16 * 5 * 2, dtype=np.uint8).reshape(16, 5, 2, 1)
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
        self.assertEqual(report["target_family"], "rtl28")
        self.assertEqual(report["slice_count"], 28)
        self.assertEqual(report["region_count"], 112)
        self.assertGreater(report["tail_bytes"], 0)

        first = layout.explain_coordinate(bundle, "tensor-input", (0, 0, 1, 0))
        self.assertEqual(first[0]["slice_id"], HIGH_RING_OWNERS[0][0])
        self.assertEqual(first[0]["physical_coordinate"], (0, 1, 0, 0))
        last = layout.explain_coordinate(bundle, "tensor-input", (15, 4, 1, 0))
        self.assertEqual(last[0]["slice_id"], HIGH_RING_OWNERS[6][2])
        self.assertEqual(last[0]["group_id"], 6)
        self.assertEqual(last[0]["physical_coordinate"], (1, 1, 0, 0))
        scale = layout.explain_coordinate(bundle, "tensor-scale", (0,))
        self.assertEqual(len(scale), 28 * 4)
        self.assertEqual({item["slice_id"] for item in scale}, set(range(28)))

        two_sample_group = bundle.region("D", HIGH_RING_OWNERS[2][0])
        self.assertEqual(two_sample_group.sample_count, 2)
        self.assertEqual(two_sample_group.storage_sample_count, 3)
        self.assertEqual(two_sample_group.physical_shape, (3, 2, 1, 2))
        records = {record.port: record for record in bundle.layout_records()}
        self.assertEqual(
            records["A"].partition["policy"],
            "seven_high_groups_sample_and_feature_partition",
        )
        self.assertEqual(records["A"].partition["batch_group_sample_counts"], [3, 3, 2, 2, 2, 2, 2])
        self.assertEqual(records["scale"].partition["policy"], "replicated_on_every_rtl28_slice")
        self.assertEqual(records["D"].packing["byte_order"], "little")
        self.assertEqual(records["D"].packing["address_order_status"], "candidate_unapproved")
        self.assertEqual(len(records["D"].base_addresses), 28)

        manifest = ObjectManifest(
            tensors=[
                TensorRecord(record.tensor_id, record.logical_dtype or "unknown", record.logical_shape)
                for record in records.values()
            ],
            layouts=list(records.values()),
        )
        restored = ObjectManifest.from_dict(manifest.to_dict())
        self.assertEqual(
            [asdict(item) for item in restored.layouts],
            [asdict(item) for item in manifest.layouts],
        )

    def test_formal_resnet_input_shape_round_trip(self) -> None:
        layout = QuantizeLinearPhysicalLayout()
        logical_input = np.zeros((16, 3, 224, 224), dtype=np.float32)
        logical_output = np.full((16, 3, 224, 224), 114, dtype=np.uint8)
        bundle = layout.forward(
            input_tensor=logical_input,
            scale=np.array([0.018], dtype=np.float32),
            zero_point=np.array([114], dtype=np.uint8),
            output_tensor=logical_output,
        )
        recovered = layout.inverse(bundle)
        np.testing.assert_array_equal(recovered["quantize_input"], logical_input)
        np.testing.assert_array_equal(recovered["quantize_output"], logical_output)
        self.assertEqual(bundle.placement("quantize_input").feature_tile, 1)
        self.assertEqual(
            bundle.region("A", HIGH_RING_OWNERS[0][0]).physical_shape,
            (3, 224, 224, 1),
        )
        self.assertFalse(bundle.region("A", HIGH_RING_OWNERS[0][3]).active)

    def test_formal_dequantize_flatten_quantize_chain_is_zero_copy(self) -> None:
        dequantize = DequantizeLinearPhysicalLayout()
        quantized = np.arange(16 * 2048, dtype=np.uint16).astype(np.uint8).reshape(
            16, 2048, 1, 1
        )
        floating = (quantized.astype(np.float32) - 97.0) * np.float32(0.0625)
        bundle = dequantize.forward(
            input_tensor=quantized,
            scale=np.array([0.0625], dtype=np.float32),
            zero_point=np.array([97], dtype=np.uint8),
            output_tensor=floating,
            tensor_ids={
                "A": "tensor-pool-quantized",
                "scale": "tensor-pool-scale",
                "zero_point": "tensor-pool-zero-point",
                "D": "tensor-pool-float",
            },
        )
        view = ZeroCopyViewLayout()
        proof = view.forward(
            source_bundle=bundle,
            source_tensor_id="tensor-pool-float",
            output_tensor_id="tensor-flatten",
            output_shape=(16, 2048),
            axis=1,
        )
        recovered = view.inverse(proof)
        np.testing.assert_array_equal(recovered["tensor-pool-float"], floating)
        np.testing.assert_array_equal(recovered["tensor-flatten"], floating.reshape(16, 2048))
        record = proof.layout_record()
        self.assertEqual(record.alias_of, "tensor-pool-float")
        self.assertTrue(record.packing["zero_copy"])
        source_bases = tuple(
            bundle.region("D", slice_id).base_address for slice_id in range(28)
        )
        self.assertEqual(record.base_addresses, source_bases)
        explanation = view.explain_coordinate(proof, (15, 1025))
        self.assertEqual(explanation[0]["slice_id"], HIGH_RING_OWNERS[6][2])
        self.assertEqual(explanation[0]["source_coordinate"], (15, 1025, 0, 0))
        self.assertTrue(all(item["semantic"] == "zero_copy_alias" for item in explanation))

        requantize = QuantizeLinearPhysicalLayout()
        flattened = floating.reshape(16, 2048)
        requantized = np.rint(flattened / np.float32(0.125)).clip(0, 255).astype(np.uint8)
        next_bundle = requantize.forward(
            input_tensor=flattened,
            scale=np.array([0.125], dtype=np.float32),
            zero_point=np.array([0], dtype=np.uint8),
            output_tensor=requantized,
        )
        np.testing.assert_array_equal(
            requantize.inverse(next_bundle)["quantize_input"], flattened
        )

    def test_global_low_ring_profile_round_trip_and_owner_order(self) -> None:
        layout = DequantizeLinearPhysicalLayout(profile_id=GLOBAL_RING28_PROFILE)
        quantized = np.arange(16 * 31, dtype=np.uint16).astype(np.uint8).reshape(16, 31)
        floating = (quantized.astype(np.float32) - 11.0) * np.float32(0.5)
        bundle = layout.forward(
            input_tensor=quantized,
            scale=np.array([0.5], dtype=np.float32),
            zero_point=np.array([11], dtype=np.uint8),
            output_tensor=floating,
        )
        recovered = layout.inverse(bundle)
        np.testing.assert_array_equal(recovered["dequantize_input"], quantized)
        np.testing.assert_array_equal(recovered["dequantize_output"], floating)
        self.assertEqual(bundle.placement("dequantize_input").feature_tile, 2)
        coordinate = layout.explain_coordinate(bundle, "dequantize_input", (7, 30))
        self.assertEqual(coordinate[0]["slice_id"], LOW_RING_OWNERS[15])
        self.assertIsNone(coordinate[0]["group_id"])
        self.assertEqual(coordinate[0]["owner_step"], 15)
        self.assertEqual(coordinate[0]["physical_coordinate"], (7, 0))
        records = {record.port: record for record in bundle.layout_records()}
        self.assertEqual(records["A"].partition["policy"], "global_low_ring_feature_partition")
        self.assertEqual(records["A"].partition["low_ring_owners"], list(LOW_RING_OWNERS))

        shaped_input = quantized.reshape(16, 31, 1, 1)
        shaped_output = floating.reshape(16, 31, 1, 1)
        shaped_bundle = layout.forward(
            input_tensor=shaped_input,
            scale=np.array([0.5], dtype=np.float32),
            zero_point=np.array([11], dtype=np.uint8),
            output_tensor=shaped_output,
        )
        view = ZeroCopyViewLayout(profile_id=GLOBAL_RING28_PROFILE)
        proof = view.forward(
            source_bundle=shaped_bundle,
            source_tensor_id="dequantize_output",
            output_tensor_id="global-flatten",
            output_shape=(16, 31),
        )
        np.testing.assert_array_equal(
            view.inverse(proof)["global-flatten"], floating
        )
        self.assertEqual(
            view.explain_coordinate(proof, (7, 30))[0]["slice_id"],
            LOW_RING_OWNERS[15],
        )

    def test_corruption_invalid_profile_batch_geometry_and_view_fail_closed(self) -> None:
        with self.assertRaisesRegex(ContractError, "unsupported profile28"):
            QuantizeLinearPhysicalLayout(profile_id="legacy16")
        with self.assertRaisesRegex(ValueError, "TARGET_DRAM_GEOMETRY28"):
            QuantizeLinearPhysicalLayout(geometry=LEGACY_DRAM_GEOMETRY16)

        layout = QuantizeLinearPhysicalLayout()
        with self.assertRaisesRegex(ValueError, "batch=16"):
            layout.forward(
                input_tensor=np.zeros((15, 5), dtype=np.float32),
                scale=np.array([1.0], dtype=np.float32),
                zero_point=np.array([3], dtype=np.uint8),
                output_tensor=np.zeros((15, 5), dtype=np.uint8),
            )

        bundle = layout.forward(
            input_tensor=np.zeros((16, 5), dtype=np.float32),
            scale=np.array([1.0], dtype=np.float32),
            zero_point=np.array([3], dtype=np.uint8),
            output_tensor=np.zeros((16, 5), dtype=np.uint8),
        )
        slice_id = HIGH_RING_OWNERS[2][0]
        region = bundle.region("D", slice_id)
        payload = bytearray(bundle.read("D", slice_id))
        payload[region.physical_shape[1] * region.sample_count] = 9
        bundle.payloads[("D", slice_id)] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "tail.*corrupted"):
            layout.validate(bundle)

        qparam_bundle = layout.forward(
            input_tensor=np.zeros((16, 5), dtype=np.float32),
            scale=np.array([1.0], dtype=np.float32),
            zero_point=np.array([3], dtype=np.uint8),
            output_tensor=np.zeros((16, 5), dtype=np.uint8),
        )
        payload = bytearray(qparam_bundle.read("scale", 1))
        payload[:4] = np.asarray([2.0], dtype="<f4").tobytes()
        qparam_bundle.payloads[("scale", 1)] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "differs between slices"):
            layout.validate(qparam_bundle)

        clean = DequantizeLinearPhysicalLayout().forward(
            input_tensor=np.zeros((16, 8, 2, 1), dtype=np.uint8),
            scale=np.array([1.0], dtype=np.float32),
            zero_point=np.array([0], dtype=np.uint8),
            output_tensor=np.zeros((16, 8, 2, 1), dtype=np.float32),
        )
        view = ZeroCopyViewLayout()
        with self.assertRaisesRegex(ValueError, "singleton spatial"):
            view.forward(
                source_bundle=clean,
                source_tensor_id="dequantize_output",
                output_tensor_id="bad-view",
                output_shape=(16, 16),
                axis=1,
            )
        with self.assertRaisesRegex(ValueError, "profile must match"):
            ZeroCopyViewLayout(profile_id=GLOBAL_RING28_PROFILE).forward(
                source_bundle=clean,
                source_tensor_id="dequantize_output",
                output_tensor_id="bad-profile",
                output_shape=(16, 8),
                axis=1,
            )

    def test_public_layout_api_exposes_current_simple_contracts_only(self) -> None:
        self.assertIs(
            public_layout.QuantizeLinearPhysicalLayout,
            QuantizeLinearPhysicalLayout,
        )
        self.assertIs(
            public_layout.DequantizeLinearPhysicalLayout,
            DequantizeLinearPhysicalLayout,
        )
        self.assertIs(public_layout.ZeroCopyViewLayout, ZeroCopyViewLayout)
        self.assertFalse(hasattr(public_layout, "ConvBatch16PhysicalLayout"))
        self.assertEqual(
            QuantizeLinearPhysicalLayout().profile_id,
            GROUP4X7_BATCH_CHANNEL28_PROFILE,
        )


if __name__ == "__main__":
    unittest.main()
