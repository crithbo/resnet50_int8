from __future__ import annotations

import unittest

import numpy as np

from resnet50_pipeline.conv16_layout import ConvBatch16PhysicalLayout
from resnet50_pipeline.conv16_ring_layout import ConvRing16PhysicalLayout
from resnet50_pipeline.maxpool16_layout import (
    MaxPoolBatch16PhysicalLayout,
    MaxPoolChannel16PhysicalLayout,
)


def maxpool_reference(
    activation: np.ndarray,
    *,
    kernel_shape: tuple[int, int],
    strides: tuple[int, int],
    pads: tuple[int, int, int, int],
    padding_value: int = 0,
) -> np.ndarray:
    n, channels, height, width = activation.shape
    output_h = (height + pads[0] + pads[2] - kernel_shape[0]) // strides[0] + 1
    output_w = (width + pads[1] + pads[3] - kernel_shape[1]) // strides[1] + 1
    output = np.empty((n, channels, output_h, output_w), dtype=np.uint8)
    for batch in range(n):
        for channel in range(channels):
            for oh in range(output_h):
                for ow in range(output_w):
                    values: list[int] = []
                    for kh in range(kernel_shape[0]):
                        ih = oh * strides[0] + kh - pads[0]
                        for kw in range(kernel_shape[1]):
                            iw = ow * strides[1] + kw - pads[1]
                            values.append(
                                int(activation[batch, channel, ih, iw])
                                if 0 <= ih < height and 0 <= iw < width
                                else padding_value
                            )
                    output[batch, channel, oh, ow] = max(values)
    return output


class MaxPool16PhysicalLayoutTests(unittest.TestCase):
    def _case(self):
        activation = (
            np.arange(3 * 5 * 5 * 6, dtype=np.uint16).astype(np.uint8).reshape(3, 5, 5, 6)
        )
        attributes = {
            "kernel_shape": (3, 3),
            "strides": (2, 2),
            "pads": (1, 1, 1, 1),
        }
        output = maxpool_reference(activation, **attributes)
        return activation, output, attributes

    def test_batch_and_channel_profiles_round_trip_and_explain_windows(self) -> None:
        activation, output, attributes = self._case()
        batch_layout = MaxPoolBatch16PhysicalLayout()
        channel_layout = MaxPoolChannel16PhysicalLayout()
        batch = batch_layout.forward(
            activation=activation,
            output=output,
            spatial_padding_value=0,
            input_tail_value=101,
            **attributes,
        )
        channel = channel_layout.forward(
            activation=activation,
            output=output,
            spatial_padding_value=0,
            input_tail_value=101,
            **attributes,
        )
        np.testing.assert_array_equal(batch_layout.inverse_port(batch, "A"), activation)
        np.testing.assert_array_equal(batch_layout.inverse_port(batch, "D"), output)
        np.testing.assert_array_equal(channel_layout.inverse_port(channel, "A"), activation)
        np.testing.assert_array_equal(channel_layout.inverse_port(channel, "D"), output)
        np.testing.assert_array_equal(
            batch_layout.inverse_port(batch, "A"), channel_layout.inverse_port(channel, "A")
        )
        np.testing.assert_array_equal(
            batch_layout.inverse_port(batch, "D"), channel_layout.inverse_port(channel, "D")
        )
        self.assertEqual(batch.metadata["channel_tile"], 8)
        self.assertEqual(channel.metadata["channel_tile"], 1)
        self.assertEqual(batch_layout.validate(batch)["region_count"], 32)
        self.assertEqual(channel_layout.validate(channel)["region_count"], 32)

        batch_coordinate = batch_layout.explain_coordinate(
            batch, "maxpool_input", (2, 4, 3, 5)
        )
        self.assertEqual(batch_coordinate["slice_id"], 2)
        self.assertEqual(batch_coordinate["physical_coordinate"], (3, 5, 4))
        channel_coordinate = channel_layout.explain_coordinate(
            channel, "maxpool_input", (2, 4, 3, 5)
        )
        self.assertEqual(channel_coordinate["slice_id"], 4)
        self.assertEqual(channel_coordinate["physical_coordinate"], (2, 3, 5, 0))
        padding = batch_layout.explain_window(
            batch,
            batch=0,
            channel=0,
            output_h=0,
            output_w=0,
            kernel_h=0,
            kernel_w=0,
        )
        self.assertEqual(padding["semantic"], "spatial_padding")
        self.assertEqual(padding["value"], 0)
        data = channel_layout.explain_window(
            channel,
            batch=1,
            channel=3,
            output_h=0,
            output_w=0,
            kernel_h=1,
            kernel_w=1,
        )
        self.assertEqual(data["logical_coordinate"], (1, 3, 0, 0))
        records = {item.port: item for item in channel.layout_records()}
        self.assertEqual(
            records["A"].partition["policy"],
            "contiguous_channel_partition_across_slices",
        )
        self.assertEqual(records["A"].packing["spatial_padding_value"], 0)

    def test_conv_output_aliases_matching_maxpool_input_profiles(self) -> None:
        activation, pool_output, attributes = self._case()
        n, channels, height, width = activation.shape
        weight = np.zeros((channels, channels, 1, 1), dtype=np.int8)
        conv_values = {
            "activation": np.zeros((n, channels, height, width), dtype=np.uint8),
            "weight": weight,
            "bias": np.zeros(channels, dtype=np.int32),
            "w_scale": np.full(channels, 0.02, dtype=np.float32),
            "w_zero_point": np.zeros(channels, dtype=np.int8),
            "x_scale": np.array([0.025], dtype=np.float32),
            "x_zero_point": np.array([111], dtype=np.uint8),
            "y_scale": np.array([0.04], dtype=np.float32),
            "y_zero_point": np.array([101], dtype=np.uint8),
            "accumulator": np.zeros_like(activation, dtype=np.int32),
            "output": activation,
            "tensor_ids": {"D": "conv-output"},
        }
        batch_conv_layout = ConvBatch16PhysicalLayout()
        ring_conv_layout = ConvRing16PhysicalLayout()
        batch_conv = batch_conv_layout.forward(**conv_values)
        ring_conv = ring_conv_layout.forward(**conv_values)
        batch_pool_layout = MaxPoolBatch16PhysicalLayout()
        channel_pool_layout = MaxPoolChannel16PhysicalLayout()
        tensor_ids = {"A": "conv-output", "D": "pool-output"}
        batch_pool = batch_pool_layout.forward(
            activation=activation,
            output=pool_output,
            input_tail_value=101,
            tensor_ids=tensor_ids,
            input_base_addresses=tuple(
                batch_conv.region("D", slice_id).base_address for slice_id in range(16)
            ),
            **attributes,
        )
        channel_pool = channel_pool_layout.forward(
            activation=activation,
            output=pool_output,
            input_tail_value=101,
            tensor_ids=tensor_ids,
            input_base_addresses=tuple(
                ring_conv.region("D", slice_id).base_address for slice_id in range(16)
            ),
            **attributes,
        )
        self.assertTrue(
            batch_pool_layout.prove_conv_input_alias(batch_conv, batch_pool)["compatible"]
        )
        self.assertTrue(
            channel_pool_layout.prove_conv_input_alias(ring_conv, channel_pool)[
                "compatible"
            ]
        )
        self.assertEqual(
            batch_pool.region("A", 0).base_address,
            batch_conv.region("D", 0).base_address,
        )
        self.assertEqual(
            channel_pool.region("A", 7).base_address,
            ring_conv.region("D", 7).base_address,
        )

    def test_formal_shape_plan_and_invalid_or_corrupt_inputs_fail(self) -> None:
        batch = MaxPoolBatch16PhysicalLayout()
        channel = MaxPoolChannel16PhysicalLayout()
        kwargs = {
            "input_shape": (16, 64, 112, 112),
            "kernel_shape": (3, 3),
            "strides": (2, 2),
            "pads": (1, 1, 1, 1),
        }
        batch_plan = batch.plan(**kwargs)
        channel_plan = channel.plan(**kwargs)
        self.assertEqual(batch_plan["output_shape"], (16, 64, 56, 56))
        self.assertEqual(channel_plan["output_shape"], (16, 64, 56, 56))
        self.assertLess(batch_plan["per_slice_used_bytes"], batch_plan["capacity_bytes"])
        self.assertLess(channel_plan["per_slice_used_bytes"], channel_plan["capacity_bytes"])
        with self.assertRaisesRegex(ValueError, "ceil_mode=0"):
            batch.plan(**kwargs, ceil_mode=1)
        with self.assertRaisesRegex(ValueError, "storage_order=0"):
            channel.plan(**kwargs, storage_order=1)

        activation, output, attributes = self._case()
        bundle = batch.forward(
            activation=activation,
            output=output,
            input_tail_value=101,
            **attributes,
        )
        payload = bytearray(bundle.read("A", 0))
        payload[5] = 0
        bundle.payloads[("A", 0)] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "input channel tail is corrupted"):
            batch.validate(bundle)
        with self.assertRaisesRegex(ValueError, "common slice offset"):
            channel.forward(
                activation=activation,
                output=output,
                input_base_addresses=tuple(
                    channel.geometry.slice_base(index) + (16 if index == 1 else 0)
                    for index in range(16)
                ),
                **attributes,
            )


if __name__ == "__main__":
    unittest.main()
