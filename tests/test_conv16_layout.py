from __future__ import annotations

import unittest

import numpy as np

from resnet50_pipeline.conv16_layout import ConvBatch16PhysicalLayout
from resnet50_pipeline.conv16_ring_layout import ConvRing16PhysicalLayout
from resnet50_pipeline.golden.qlinear_conv import qlinear_conv_im2col


class ConvBatch16PhysicalLayoutTests(unittest.TestCase):
    def _micro_case(self):
        rng = np.random.default_rng(20260712)
        activation = rng.integers(0, 256, size=(3, 5, 5, 6), dtype=np.uint8)
        weight = rng.integers(-20, 21, size=(7, 5, 3, 3), dtype=np.int16).astype(
            np.int8
        )
        bias = np.array([-70, -30, 0, 20, 50, 90, -110], dtype=np.int32)
        w_scale = np.array(
            [0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04], dtype=np.float32
        )
        w_zero_point = np.array([-3, -2, -1, 0, 1, 2, 3], dtype=np.int8)
        x_scale = np.array([0.025], dtype=np.float32)
        x_zero_point = np.array([111], dtype=np.uint8)
        y_scale = np.array([0.04], dtype=np.float32)
        y_zero_point = np.array([99], dtype=np.uint8)
        golden = qlinear_conv_im2col(
            activation,
            weight,
            x_scale=x_scale,
            x_zero_point=x_zero_point,
            w_scale=w_scale,
            w_zero_point=w_zero_point,
            y_scale=y_scale,
            y_zero_point=y_zero_point,
            bias=bias,
            strides=(2, 1),
            pads=(1, 1, 1, 1),
        )
        return {
            "activation": activation,
            "weight": weight,
            "bias": bias,
            "w_scale": w_scale,
            "w_zero_point": w_zero_point,
            "x_scale": x_scale,
            "x_zero_point": x_zero_point,
            "y_scale": y_scale,
            "y_zero_point": y_zero_point,
            "accumulator": golden.accumulator,
            "output": golden.output,
            "strides": (2, 1),
            "pads": (1, 1, 1, 1),
        }

    def test_micro_tail_round_trip_records_and_coordinates(self) -> None:
        values = self._micro_case()
        layout = ConvBatch16PhysicalLayout()
        bundle = layout.forward(**values)
        recovered = layout.inverse(bundle)
        expected = {
            "conv_activation": values["activation"],
            "conv_weight": values["weight"],
            "conv_bias": values["bias"],
            "conv_w_scale": values["w_scale"],
            "conv_w_zero_point": values["w_zero_point"],
            "conv_x_scale": values["x_scale"],
            "conv_x_zero_point": values["x_zero_point"],
            "conv_y_scale": values["y_scale"],
            "conv_y_zero_point": values["y_zero_point"],
            "conv_accumulator": values["accumulator"],
            "conv_output": values["output"],
        }
        for tensor_id, logical in expected.items():
            np.testing.assert_array_equal(recovered[tensor_id], logical)
        np.testing.assert_array_equal(
            recovered["conv_multiplier"],
            values["x_scale"][0] * values["w_scale"] / values["y_scale"][0],
        )

        self.assertEqual(bundle.metadata["slice_topology"], "batch_parallel_one_item_per_slice")
        self.assertEqual(bundle.metadata["im2col_mode"], "address_generator")
        self.assertEqual(bundle.metadata["c_padded"], 8)
        self.assertEqual(bundle.metadata["k_padded"], 8)
        report = layout.validate(bundle)
        self.assertEqual(report["slice_count"], 16)
        self.assertEqual(report["port_count"], 12)
        self.assertEqual(report["region_count"], 192)

        a = layout.explain_coordinate(bundle, "conv_activation", (2, 4, 3, 5))
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]["slice_id"], 2)
        self.assertEqual(a[0]["physical_coordinate"], (3, 5, 4))
        b = layout.explain_coordinate(bundle, "conv_weight", (6, 4, 2, 1))
        self.assertEqual(len(b), 16)
        self.assertEqual({item["slice_id"] for item in b}, set(range(16)))
        self.assertEqual(b[0]["physical_coordinate"], (2, 1, 6, 4))

        padding = layout.explain_window(
            bundle,
            batch=0,
            output_h=0,
            output_w=0,
            kernel_h=0,
            kernel_w=0,
            channel=0,
        )
        self.assertEqual(padding["semantic"], "padding")
        self.assertEqual(padding["value"], int(values["x_zero_point"][0]))
        data = layout.explain_window(
            bundle,
            batch=0,
            output_h=0,
            output_w=0,
            kernel_h=1,
            kernel_w=1,
            channel=3,
        )
        self.assertEqual(data["semantic"], "data")
        self.assertEqual(data["logical_coordinate"], (0, 3, 0, 0))
        self.assertIsInstance(data["address"], int)

        records = {record.port: record for record in bundle.layout_records()}
        self.assertEqual(records["A"].contract_status, "candidate")
        self.assertEqual(records["A"].partition["policy"], "one_batch_item_per_slice")
        self.assertEqual(records["A"].packing["physical_axis_order"], "HWC_padded")
        self.assertEqual(records["A"].packing["im2col_mode"], "address_generator")
        self.assertEqual(records["B"].partition["policy"], "replicated_on_every_slice")
        self.assertEqual(records["P"].packing["physical_axis_order"], "HWK_padded")

    def test_conv0_formal_shape_plan_and_single_sample_equivalent_round_trip(self) -> None:
        layout = ConvBatch16PhysicalLayout()
        plan = layout.plan(
            activation_shape=(16, 3, 224, 224),
            weight_shape=(64, 3, 7, 7),
            strides=(2, 2),
            pads=(3, 3, 3, 3),
        )
        self.assertEqual(plan["output_shape"], (16, 64, 112, 112))
        self.assertEqual(plan["c_padded"], 8)
        self.assertEqual(plan["k_padded"], 64)
        self.assertEqual(plan["raw_sizes"]["A"], 224 * 224 * 8)
        self.assertEqual(plan["raw_sizes"]["P"], 112 * 112 * 64 * 4)
        self.assertEqual(plan["raw_sizes"]["D"], 112 * 112 * 64)
        self.assertLess(plan["per_slice_used_bytes"], plan["capacity_bytes"])

        activation = np.zeros((1, 3, 224, 224), dtype=np.uint8)
        weight = np.zeros((64, 3, 7, 7), dtype=np.int8)
        accumulator = np.zeros((1, 64, 112, 112), dtype=np.int32)
        output = np.full((1, 64, 112, 112), 101, dtype=np.uint8)
        bundle = layout.forward(
            activation=activation,
            weight=weight,
            bias=np.zeros(64, dtype=np.int32),
            w_scale=np.full(64, 0.02, dtype=np.float32),
            w_zero_point=np.zeros(64, dtype=np.int8),
            x_scale=np.array([0.025], dtype=np.float32),
            x_zero_point=np.array([113], dtype=np.uint8),
            y_scale=np.array([0.04], dtype=np.float32),
            y_zero_point=np.array([101], dtype=np.uint8),
            accumulator=accumulator,
            output=output,
            strides=(2, 2),
            pads=(3, 3, 3, 3),
        )
        np.testing.assert_array_equal(layout.inverse_port(bundle, "A"), activation)
        np.testing.assert_array_equal(layout.inverse_port(bundle, "B"), weight)
        np.testing.assert_array_equal(layout.inverse_port(bundle, "P"), accumulator)
        np.testing.assert_array_equal(layout.inverse_port(bundle, "D"), output)
        self.assertFalse(bundle.region("A", 1).active)
        self.assertFalse(bundle.region("P", 15).active)
        self.assertEqual(bundle.region("A", 0).size_bytes, plan["raw_sizes"]["A"])

    def test_tail_corruption_and_unsupported_contract_fail(self) -> None:
        values = self._micro_case()
        layout = ConvBatch16PhysicalLayout()
        bundle = layout.forward(**values)
        payload = bytearray(bundle.read("A", 0))
        payload[5] = 0
        bundle.payloads[("A", 0)] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "activation C tail is corrupted"):
            layout.validate(bundle)

        with self.assertRaisesRegex(ValueError, "group=1 only"):
            layout.plan(
                activation_shape=(1, 4, 5, 5),
                weight_shape=(4, 2, 3, 3),
                group=2,
            )
        with self.assertRaisesRegex(TypeError, "inferred NCHW output shape"):
            clean = self._micro_case()
            clean["accumulator"] = clean["accumulator"][:, :, :-1]
            layout.forward(**clean)

    def test_ring_profile_round_trip_matches_batch_profile(self) -> None:
        values = self._micro_case()
        batch_layout = ConvBatch16PhysicalLayout()
        ring_layout = ConvRing16PhysicalLayout()
        batch = batch_layout.forward(**values)
        ring = ring_layout.forward(**values)
        batch_inverse = batch_layout.inverse(batch)
        ring_inverse = ring_layout.inverse(ring)
        self.assertEqual(set(batch_inverse), set(ring_inverse))
        for tensor_id in batch_inverse:
            np.testing.assert_array_equal(ring_inverse[tensor_id], batch_inverse[tensor_id])

        self.assertEqual(ring.metadata["slice_topology"], "ring_C_activation_K_output_partition")
        self.assertEqual(ring.metadata["c_tile"], 1)
        self.assertEqual(ring.metadata["k_tile"], 1)
        report = ring_layout.validate(ring)
        self.assertEqual(report["ring_steps"], 16)
        self.assertEqual(report["region_count"], 192)
        a = ring_layout.explain_coordinate(ring, "conv_activation", (2, 4, 3, 5))
        self.assertEqual(a[0]["slice_id"], 4)
        self.assertEqual(a[0]["physical_coordinate"], (2, 3, 5, 0))
        b = ring_layout.explain_coordinate(ring, "conv_weight", (6, 4, 2, 1))
        self.assertEqual(b[0]["slice_id"], 6)
        self.assertEqual(b[0]["physical_coordinate"], (2, 1, 0, 4))

        first = ring_layout.explain_ring_step(ring, output_channel=0, step=0)
        self.assertEqual(first["k_owner_slice"], 0)
        self.assertEqual(first["activation_slice"], 0)
        self.assertEqual(first["channel_range"], (0, 1))
        self.assertTrue(first["has_data"])
        empty = ring_layout.explain_ring_step(ring, output_channel=0, step=5)
        self.assertEqual(empty["activation_slice"], 5)
        self.assertEqual(empty["channel_range"], (5, 5))
        self.assertFalse(empty["has_data"])
        last = ring_layout.explain_ring_step(ring, output_channel=0, step=15)
        self.assertTrue(last["last"])
        wrapped = ring_layout.explain_ring_step(ring, output_channel=6, step=10)
        self.assertEqual(wrapped["k_owner_slice"], 6)
        self.assertEqual(wrapped["activation_slice"], 0)
        self.assertTrue(wrapped["has_data"])

        records = {record.port: record for record in ring.layout_records()}
        self.assertEqual(
            records["A"].partition["policy"], "contiguous_c_partition_across_ring"
        )
        self.assertEqual(
            records["B"].partition["policy"],
            "contiguous_k_owner_partition_across_ring",
        )
        self.assertEqual(records["x_scale"].partition["policy"], "replicated_on_every_slice")

    def test_ring_conv0_formal_shape_and_tail_corruption(self) -> None:
        layout = ConvRing16PhysicalLayout()
        plan = layout.plan(
            activation_shape=(16, 3, 224, 224),
            weight_shape=(64, 3, 7, 7),
            strides=(2, 2),
            pads=(3, 3, 3, 3),
        )
        self.assertEqual(plan["output_shape"], (16, 64, 112, 112))
        self.assertEqual(plan["c_tile"], 1)
        self.assertEqual(plan["k_tile"], 4)
        self.assertEqual(plan["c_padded"], 16)
        self.assertEqual(plan["k_padded"], 64)
        self.assertLess(plan["per_slice_used_bytes"], plan["capacity_bytes"])

        values = self._micro_case()
        bundle = layout.forward(**values)
        payload = bytearray(bundle.read("A", 5))
        payload[0] = 0
        bundle.payloads[("A", 5)] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "activation C tail is corrupted"):
            layout.validate(bundle)

        replicated = layout.forward(**values)
        scale = bytearray(replicated.read("x_scale", 3))
        scale[0] ^= 1
        replicated.payloads[("x_scale", 3)] = bytes(scale)
        with self.assertRaisesRegex(ValueError, "replicated scalar port x_scale"):
            layout.validate(replicated)


if __name__ == "__main__":
    unittest.main()
