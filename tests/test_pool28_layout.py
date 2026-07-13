from __future__ import annotations

import unittest

import numpy as np

from resnet50_pipeline.memory import LEGACY_DRAM_GEOMETRY16
from resnet50_pipeline.pool28_layout import (
    GLOBAL_AVERAGE_POOL_LAYOUT_IDS,
    MAXPOOL_LAYOUT_IDS,
    GlobalAveragePoolPhysicalLayout,
    MaxPoolPhysicalLayout,
)
from resnet50_pipeline.profile28 import (
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
    GROUP_SAMPLE_COUNTS,
)
from resnet50_pipeline.topology28 import HIGH_RING_OWNERS, LOW_RING_OWNERS


def _maxpool_reference(
    activation: np.ndarray,
    *,
    kernel_shape: tuple[int, int],
    strides: tuple[int, int],
    pads: tuple[int, int, int, int],
    dilations: tuple[int, int] = (1, 1),
    padding_value: int = 0,
) -> np.ndarray:
    n, channels, height, width = activation.shape
    effective_h = (kernel_shape[0] - 1) * dilations[0] + 1
    effective_w = (kernel_shape[1] - 1) * dilations[1] + 1
    out_h = (height + pads[0] + pads[2] - effective_h) // strides[0] + 1
    out_w = (width + pads[1] + pads[3] - effective_w) // strides[1] + 1
    output = np.empty((n, channels, out_h, out_w), dtype=np.uint8)
    for batch in range(n):
        for channel in range(channels):
            for oh in range(out_h):
                for ow in range(out_w):
                    values = []
                    for kh in range(kernel_shape[0]):
                        ih = oh * strides[0] + kh * dilations[0] - pads[0]
                        for kw in range(kernel_shape[1]):
                            iw = ow * strides[1] + kw * dilations[1] - pads[1]
                            values.append(
                                int(activation[batch, channel, ih, iw])
                                if 0 <= ih < height and 0 <= iw < width
                                else padding_value
                            )
                    output[batch, channel, oh, ow] = max(values)
    return output


def _gap_case(output_rank: int = 4) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(20260713)
    activation = rng.integers(0, 256, size=(16, 5, 2, 3), dtype=np.uint8)
    x_scale = np.array([0.025], dtype=np.float32)
    x_zero_point = np.array([111], dtype=np.uint8)
    y_scale = np.array([0.04], dtype=np.float32)
    y_zero_point = np.array([97], dtype=np.uint8)
    accumulator = np.sum(
        activation.astype(np.int32) - int(x_zero_point[0]),
        axis=(2, 3),
        keepdims=True,
        dtype=np.int64,
    ).astype(np.int32)
    multiplier = np.float32(x_scale[0]) / (
        np.float32(y_scale[0]) * np.float32(6)
    )
    output = np.clip(
        np.rint(accumulator.astype(np.float32) * multiplier).astype(np.int64)
        + int(y_zero_point[0]),
        0,
        255,
    ).astype(np.uint8)
    if output_rank == 2:
        accumulator = accumulator.reshape(16, 5)
        output = output.reshape(16, 5)
    return {
        "activation": activation,
        "x_scale": x_scale,
        "x_zero_point": x_zero_point,
        "y_scale": y_scale,
        "y_zero_point": y_zero_point,
        "accumulator": accumulator,
        "output": output,
    }


class MaxPool28PhysicalLayoutTests(unittest.TestCase):
    def _case(self) -> tuple[np.ndarray, np.ndarray, dict[str, tuple[int, ...]]]:
        activation = np.arange(16 * 5 * 5 * 6, dtype=np.uint16).astype(
            np.uint8
        ).reshape(16, 5, 5, 6)
        attributes = {
            "kernel_shape": (3, 3),
            "strides": (2, 2),
            "pads": (1, 1, 1, 1),
        }
        output = _maxpool_reference(activation, **attributes)
        return activation, output, attributes

    def test_group4x7_roundtrip_owner_groups_tail_and_coordinates(self) -> None:
        activation, output, attributes = self._case()
        layout = MaxPoolPhysicalLayout()
        bundle = layout.forward(
            activation=activation,
            output=output,
            input_tail_value=101,
            output_tail_value=103,
            spatial_padding_value=0,
            tensor_ids={"A": "conv0_D", "D": "pool0_D"},
            **attributes,
        )
        recovered = layout.inverse(bundle)
        np.testing.assert_array_equal(recovered["conv0_D"], activation)
        np.testing.assert_array_equal(recovered["pool0_D"], output)
        self.assertEqual(bundle.contract, MAXPOOL_LAYOUT_IDS[layout.profile_id])
        self.assertEqual(bundle.geometry.slice_count, 28)
        self.assertEqual(bundle.metadata["channel_tile"], 2)
        self.assertEqual(bundle.metadata["semantics"]["input_tail_value"], 101)
        self.assertEqual(bundle.metadata["semantics"]["output_tail_value"], 103)
        self.assertTrue(bundle.metadata["semantics"]["tail_is_not_spatial_boundary"])

        for group_id, (owners, sample_count) in enumerate(
            zip(HIGH_RING_OWNERS, GROUP_SAMPLE_COUNTS, strict=True)
        ):
            for owner_step, slice_id in enumerate(owners):
                region = bundle.region("A", slice_id)
                self.assertEqual(region.group_id, group_id)
                self.assertEqual(region.owner_step, owner_step)
                self.assertEqual(region.sample_count, sample_count)
                self.assertEqual(region.storage_sample_count, 3)
        self.assertFalse(bundle.region("A", HIGH_RING_OWNERS[0][3]).active)
        self.assertEqual(bundle.region("A", HIGH_RING_OWNERS[0][2]).feature_count, 1)

        coordinate = layout.explain_coordinate(bundle, "conv0_D", (15, 4, 3, 5))
        self.assertEqual(coordinate[0]["slice_id"], HIGH_RING_OWNERS[6][2])
        self.assertEqual(coordinate[0]["physical_coordinate"], (1, 3, 5, 0))
        boundary = layout.explain_window(
            bundle,
            batch=0,
            channel=0,
            output_h=0,
            output_w=0,
            kernel_h=0,
            kernel_w=0,
        )
        self.assertEqual(boundary["semantic"], "spatial_padding")
        self.assertEqual(boundary["value"], 0)
        data = layout.explain_window(
            bundle,
            batch=0,
            channel=0,
            output_h=0,
            output_w=0,
            kernel_h=1,
            kernel_w=1,
        )
        self.assertEqual(data["logical_coordinate"], (0, 0, 0, 0))
        proof = layout.prove_a_d_compatibility(bundle)
        self.assertTrue(proof["compatible"])
        self.assertFalse(proof["exact_alias"])
        self.assertEqual(layout.validate(bundle)["region_count"], 56)

    def test_global_low_profile_roundtrip_owner_order_and_c_tail(self) -> None:
        activation, output, attributes = self._case()
        layout = MaxPoolPhysicalLayout(profile_id=GLOBAL_RING28_PROFILE)
        bundle = layout.forward(
            activation=activation,
            output=output,
            input_tail_value=77,
            **attributes,
        )
        np.testing.assert_array_equal(layout.inverse(bundle)["maxpool_input"], activation)
        np.testing.assert_array_equal(layout.inverse(bundle)["maxpool_output"], output)
        self.assertEqual(bundle.metadata["channel_tile"], 1)
        for owner_step, slice_id in enumerate(LOW_RING_OWNERS):
            self.assertEqual(bundle.region("A", slice_id).owner_step, owner_step)
        self.assertTrue(bundle.region("A", LOW_RING_OWNERS[4]).active)
        self.assertFalse(bundle.region("A", LOW_RING_OWNERS[5]).active)
        explanation = layout.explain_coordinate(
            bundle, "maxpool_input", (15, 4, 3, 5)
        )
        self.assertEqual(explanation[0]["slice_id"], LOW_RING_OWNERS[4])
        records = {item.port: item for item in bundle.layout_records()}
        self.assertEqual(
            records["A"].partition["low_ring_owners"], list(LOW_RING_OWNERS)
        )
        self.assertEqual(records["A"].packing["geometry_status"], "candidate_unapproved")

    def test_formal_conv0_plan_both_profiles_and_capacity(self) -> None:
        kwargs = {
            "input_shape": (16, 64, 112, 112),
            "kernel_shape": (3, 3),
            "strides": (2, 2),
            "pads": (1, 1, 1, 1),
        }
        for profile in (
            GROUP4X7_BATCH_CHANNEL28_PROFILE,
            GLOBAL_RING28_PROFILE,
        ):
            layout = MaxPoolPhysicalLayout(profile_id=profile)
            plan = layout.plan(**kwargs)
            self.assertEqual(plan["output_shape"], (16, 64, 56, 56))
            self.assertTrue(plan["fits"])
            self.assertLess(plan["per_slice_used_bytes"], plan["capacity_bytes"])
            self.assertTrue(plan["a_d_owner_compatible"])
            self.assertFalse(plan["hardware_approval"])
            capacity = layout.capacity_report(**kwargs)
            self.assertGreater(capacity["margin_bytes"], 0)
            self.assertTrue(capacity["candidate_unapproved"])

    def test_padding_and_metadata_corruption_fail_closed(self) -> None:
        activation, output, attributes = self._case()
        layout = MaxPoolPhysicalLayout()
        bundle = layout.forward(
            activation=activation,
            output=output,
            input_tail_value=101,
            **attributes,
        )
        # Group 2 owns only two samples but reserves three physical sample slots.
        slice_id = HIGH_RING_OWNERS[2][0]
        region = bundle.region("A", slice_id)
        payload = bytearray(bundle.read("A", slice_id))
        inactive_sample_offset = 2 * 5 * 6 * 2
        self.assertEqual(payload[inactive_sample_offset], 101)
        payload[inactive_sample_offset] ^= 1
        bundle.payloads[("A", slice_id)] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "tail for port A is corrupted"):
            layout.validate(bundle)

        clean = layout.forward(
            activation=activation,
            output=output,
            input_tail_value=101,
            **attributes,
        )
        clean.metadata["channel_tile"] = 999
        with self.assertRaisesRegex(ValueError, "channel_tile"):
            layout.validate(clean)
        with self.assertRaisesRegex(ValueError, "ceil_mode=0"):
            layout.plan(
                input_shape=(16, 64, 112, 112),
                kernel_shape=(3, 3),
                ceil_mode=1,
            )


class GlobalAveragePool28PhysicalLayoutTests(unittest.TestCase):
    @staticmethod
    def _ids() -> dict[str, str]:
        return {
            "A": "gap_A",
            "x_scale": "gap_x_scale",
            "x_zero_point": "gap_x_zp",
            "y_scale": "gap_y_scale",
            "y_zero_point": "gap_y_zp",
            "multiplier": "gap_multiplier",
            "P": "gap_centered_sum",
            "D": "gap_D",
        }

    def test_group4x7_rank4_roundtrip_qparams_sum_and_owner_path(self) -> None:
        values = _gap_case(4)
        layout = GlobalAveragePoolPhysicalLayout()
        bundle = layout.forward(**values, tensor_ids=self._ids())
        recovered = layout.inverse(bundle)
        expected = {
            "gap_A": values["activation"],
            "gap_x_scale": values["x_scale"],
            "gap_x_zp": values["x_zero_point"],
            "gap_y_scale": values["y_scale"],
            "gap_y_zp": values["y_zero_point"],
            "gap_centered_sum": values["accumulator"],
            "gap_D": values["output"],
        }
        for tensor_id, array in expected.items():
            np.testing.assert_array_equal(recovered[tensor_id], array)
        expected_multiplier = np.array(
            [values["x_scale"][0] / (values["y_scale"][0] * np.float32(6))],
            dtype=np.float32,
        )
        np.testing.assert_array_equal(recovered["gap_multiplier"], expected_multiplier)
        self.assertEqual(
            bundle.contract, GLOBAL_AVERAGE_POOL_LAYOUT_IDS[layout.profile_id]
        )
        self.assertEqual(bundle.metadata["spatial_size"], 6)
        self.assertFalse(bundle.metadata["cross_group_reduction"])
        self.assertEqual(bundle.region("A", HIGH_RING_OWNERS[2][0]).sample_count, 2)
        self.assertEqual(bundle.region("P", HIGH_RING_OWNERS[2][0]).sample_count, 2)
        self.assertEqual(bundle.region("D", HIGH_RING_OWNERS[2][0]).sample_count, 2)
        self.assertTrue(layout.prove_owner_local_reduction(bundle)["compatible"])
        reduction = layout.explain_reduction(bundle, batch=15, channel=4)
        self.assertEqual(len(reduction["input_elements"]), 6)
        self.assertEqual(reduction["sum_slice_id"], HIGH_RING_OWNERS[6][2])
        scale = layout.explain_coordinate(bundle, "gap_x_scale", (0,))
        self.assertEqual(len(scale), 28 * 4)
        self.assertEqual({item["slice_id"] for item in scale}, set(range(28)))
        report = layout.validate(bundle)
        self.assertEqual(report["region_count"], 224)
        self.assertEqual(report["owner_local_reduction"], "true")

    def test_global_low_rank2_roundtrip_and_owner_compatibility(self) -> None:
        values = _gap_case(2)
        layout = GlobalAveragePoolPhysicalLayout(profile_id=GLOBAL_RING28_PROFILE)
        bundle = layout.forward(**values)
        recovered = layout.inverse(bundle)
        np.testing.assert_array_equal(recovered["globalavgpool_input"], values["activation"])
        np.testing.assert_array_equal(
            recovered["globalavgpool_centered_sum"], values["accumulator"]
        )
        np.testing.assert_array_equal(recovered["globalavgpool_output"], values["output"])
        self.assertEqual(bundle.metadata["output_shape"], (16, 5))
        self.assertEqual(bundle.region("P", LOW_RING_OWNERS[0]).physical_shape, (16, 1))
        for owner_step, slice_id in enumerate(LOW_RING_OWNERS):
            self.assertEqual(bundle.region("A", slice_id).owner_step, owner_step)
            self.assertEqual(bundle.region("P", slice_id).owner_step, owner_step)
            self.assertEqual(bundle.region("D", slice_id).owner_step, owner_step)
        explanation = layout.explain_coordinate(
            bundle, "globalavgpool_output", (15, 4)
        )
        self.assertEqual(explanation[0]["slice_id"], LOW_RING_OWNERS[4])
        self.assertFalse(bundle.region("D", LOW_RING_OWNERS[5]).active)
        self.assertTrue(layout.prove_owner_local_reduction(bundle)["compatible"])

    def test_formal_resnet_gap_plan_both_profiles_and_both_output_ranks(self) -> None:
        for profile in (
            GROUP4X7_BATCH_CHANNEL28_PROFILE,
            GLOBAL_RING28_PROFILE,
        ):
            layout = GlobalAveragePoolPhysicalLayout(profile_id=profile)
            for rank, output_shape in (
                (4, (16, 2048, 1, 1)),
                (2, (16, 2048)),
            ):
                plan = layout.plan(
                    input_shape=(16, 2048, 7, 7), output_rank=rank
                )
                self.assertEqual(plan["output_shape"], output_shape)
                self.assertEqual(plan["spatial_size"], 49)
                self.assertTrue(plan["fits"])
                self.assertFalse(plan["cross_group_reduction"])
                self.assertLess(plan["per_slice_used_bytes"], plan["capacity_bytes"])
                self.assertGreater(
                    layout.capacity_report(
                        input_shape=(16, 2048, 7, 7), output_rank=rank
                    )["margin_bytes"],
                    0,
                )

    def test_tail_qparam_sum_and_output_corruption_fail_closed(self) -> None:
        values = _gap_case(4)
        layout = GlobalAveragePoolPhysicalLayout()
        tail_bundle = layout.forward(**values)
        slice_id = HIGH_RING_OWNERS[2][0]
        payload = bytearray(tail_bundle.read("A", slice_id))
        inactive_sample_offset = 2 * 2 * 3 * 2
        self.assertEqual(payload[inactive_sample_offset], 111)
        payload[inactive_sample_offset] ^= 1
        tail_bundle.payloads[("A", slice_id)] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "tail for port A is corrupted"):
            layout.validate(tail_bundle)

        qparam_bundle = layout.forward(**values)
        payload = bytearray(qparam_bundle.read("x_scale", 3))
        payload[0] ^= 1
        qparam_bundle.payloads[("x_scale", 3)] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "replicated Pool port x_scale differs"):
            layout.validate(qparam_bundle)

        sum_bundle = layout.forward(**values)
        payload = bytearray(sum_bundle.read("P", HIGH_RING_OWNERS[0][0]))
        payload[0] ^= 1
        sum_bundle.payloads[("P", HIGH_RING_OWNERS[0][0])] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "centered INT32 sum is inconsistent"):
            layout.validate(sum_bundle)

        output_bundle = layout.forward(**values)
        payload = bytearray(output_bundle.read("D", HIGH_RING_OWNERS[0][0]))
        payload[0] ^= 1
        output_bundle.payloads[("D", HIGH_RING_OWNERS[0][0])] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "requantized D is inconsistent"):
            layout.validate(output_bundle)

    def test_invalid_geometry_qparams_and_shapes_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "TARGET_DRAM_GEOMETRY28"):
            GlobalAveragePoolPhysicalLayout(geometry=LEGACY_DRAM_GEOMETRY16)
        with self.assertRaisesRegex(ValueError, "TARGET_DRAM_GEOMETRY28"):
            MaxPoolPhysicalLayout(geometry=LEGACY_DRAM_GEOMETRY16)
        values = _gap_case(4)
        layout = GlobalAveragePoolPhysicalLayout()
        bad = dict(values)
        bad["x_scale"] = np.array([0.0], dtype=np.float32)
        with self.assertRaisesRegex(ValueError, "positive and finite"):
            layout.forward(**bad)
        bad = dict(values)
        bad["accumulator"] = values["accumulator"].astype(np.int64)
        with self.assertRaisesRegex(TypeError, "rank-2/4 int32"):
            layout.forward(**bad)
        with self.assertRaisesRegex(ValueError, "batch=16"):
            layout.plan(input_shape=(1, 2048, 7, 7))


if __name__ == "__main__":
    unittest.main()
