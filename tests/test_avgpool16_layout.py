from __future__ import annotations

import unittest

import numpy as np

from resnet50_pipeline.add16_layout import (
    QLinearAddBatch16PhysicalLayout,
    QLinearAddChannel16PhysicalLayout,
)
from resnet50_pipeline.avgpool16_layout import (
    GlobalAveragePoolBatch16PhysicalLayout,
    GlobalAveragePoolChannel16PhysicalLayout,
)
from resnet50_pipeline.golden.subops import _requantize, global_average_sum


class GlobalAveragePool16PhysicalLayoutTests(unittest.TestCase):
    def _micro_case(self) -> dict[str, np.ndarray]:
        rng = np.random.default_rng(20260712)
        activation = rng.integers(0, 256, size=(3, 5, 2, 3), dtype=np.uint8)
        x_scale = np.array([0.025], dtype=np.float32)
        x_zero_point = np.array([111], dtype=np.uint8)
        y_scale = np.array([0.04], dtype=np.float32)
        y_zero_point = np.array([97], dtype=np.uint8)
        accumulator = global_average_sum(activation, int(x_zero_point[0]))
        multiplier = np.array(
            [x_scale[0] / (y_scale[0] * np.float32(2 * 3))], dtype=np.float32
        )
        output = _requantize(accumulator, multiplier, int(y_zero_point[0]))
        return {
            "activation": activation,
            "x_scale": x_scale,
            "x_zero_point": x_zero_point,
            "y_scale": y_scale,
            "y_zero_point": y_zero_point,
            "accumulator": accumulator,
            "output": output,
        }

    @staticmethod
    def _ids() -> dict[str, str]:
        return {
            "A": "gap_input",
            "x_scale": "gap_x_scale",
            "x_zero_point": "gap_x_zp",
            "y_scale": "gap_y_scale",
            "y_zero_point": "gap_y_zp",
            "multiplier": "gap_multiplier",
            "P": "gap_centered_sum",
            "D": "gap_output",
        }

    def test_round_trip_reduction_coordinates_records_and_flatten(self) -> None:
        values = self._micro_case()
        for layout in (
            GlobalAveragePoolBatch16PhysicalLayout(),
            GlobalAveragePoolChannel16PhysicalLayout(),
        ):
            bundle = layout.forward(**values, tensor_ids=self._ids())
            recovered = layout.inverse(bundle)
            expected = {
                "gap_input": values["activation"],
                "gap_x_scale": values["x_scale"],
                "gap_x_zp": values["x_zero_point"],
                "gap_y_scale": values["y_scale"],
                "gap_y_zp": values["y_zero_point"],
                "gap_multiplier": np.array(
                    [values["x_scale"][0] / (values["y_scale"][0] * 6)],
                    dtype=np.float32,
                ),
                "gap_centered_sum": values["accumulator"],
                "gap_output": values["output"],
            }
            for tensor_id, logical in expected.items():
                np.testing.assert_array_equal(recovered[tensor_id], logical)

            report = layout.validate(bundle)
            self.assertEqual(report["region_count"], 128)
            self.assertEqual(report["spatial_size"], 6)
            reduction = layout.explain_reduction(bundle, batch=2, channel=4)
            self.assertEqual(len(reduction["input_elements"]), 6)
            self.assertEqual(
                reduction["sum_slice_id"], 2 if layout.topology == "batch" else 4
            )
            p = layout.explain_coordinate(
                bundle, "gap_centered_sum", (2, 4, 0, 0)
            )
            self.assertEqual(len(p["addresses"]), 4)
            scale = layout.explain_coordinate(bundle, "gap_x_scale", (0,))
            self.assertEqual(scale["slice_ids"], tuple(range(16)))
            self.assertEqual(len(scale["addresses"]), 64)

            flatten = layout.prove_flatten_output_alias(
                bundle, output_shape=(3, 5), axis=1
            )
            self.assertTrue(flatten["zero_copy"])
            self.assertTrue(flatten["byte_order_unchanged"])
            self.assertEqual(
                flatten["base_addresses"],
                [bundle.region("D", slice_id).base_address for slice_id in range(16)],
            )
            records = {record.port: record for record in bundle.layout_records()}
            self.assertEqual(records["P"].logical_dtype, "int32")
            self.assertEqual(
                records["P"].packing["spatial_reduction"],
                "sum_centered_then_requantize",
            )

    def _add_producer(self, layout, output: np.ndarray):
        return layout.forward(
            a=output,
            a_scale=np.array([1.0], dtype=np.float32),
            a_zero_point=np.array([111], dtype=np.uint8),
            b=np.zeros_like(output),
            b_scale=np.array([1.0], dtype=np.float32),
            b_zero_point=np.array([0], dtype=np.uint8),
            y_scale=np.array([0.025], dtype=np.float32),
            y_zero_point=np.array([111], dtype=np.uint8),
            output=output,
            tensor_ids={"D": "gap_input"},
        )

    def test_add_producer_layout_compatibility_and_exact_alias(self) -> None:
        values = self._micro_case()
        profiles = (
            (
                GlobalAveragePoolBatch16PhysicalLayout(),
                QLinearAddBatch16PhysicalLayout(),
            ),
            (
                GlobalAveragePoolChannel16PhysicalLayout(),
                QLinearAddChannel16PhysicalLayout(),
            ),
        )
        for pool_layout, add_layout in profiles:
            producer = self._add_producer(add_layout, values["activation"])
            unaliased = pool_layout.forward(**values, tensor_ids=self._ids())
            proof = pool_layout.prove_input_compatibility(producer, unaliased)
            self.assertTrue(proof["compatible"])
            self.assertTrue(proof["memory_plan_rebase_required"])

            bases = tuple(
                producer.region("D", slice_id).base_address for slice_id in range(16)
            )
            aliased = pool_layout.forward(
                **values,
                tensor_ids=self._ids(),
                input_base_addresses=bases,
            )
            exact = pool_layout.prove_input_compatibility(
                producer, aliased, require_same_base=True
            )
            self.assertTrue(exact["exact_alias"])
            record = {item.port: item for item in aliased.layout_records()}["A"]
            self.assertEqual(record.alias_of, "gap_input")

    def test_formal_plan_and_corruption_failures(self) -> None:
        for layout in (
            GlobalAveragePoolBatch16PhysicalLayout(),
            GlobalAveragePoolChannel16PhysicalLayout(),
        ):
            plan = layout.plan(input_shape=(16, 2048, 7, 7), channels_last=0)
            self.assertEqual(plan["output_shape"], (16, 2048, 1, 1))
            self.assertEqual(plan["spatial_size"], 49)
            self.assertLess(plan["per_slice_used_bytes"], plan["capacity_bytes"])

        values = self._micro_case()
        batch_layout = GlobalAveragePoolBatch16PhysicalLayout()
        batch = batch_layout.forward(**values)
        tail = bytearray(batch.read("A", 0))
        tail[5] ^= 1
        batch.payloads[("A", 0)] = bytes(tail)
        with self.assertRaisesRegex(ValueError, "A channel tail is corrupted"):
            batch_layout.validate(batch)

        channel_layout = GlobalAveragePoolChannel16PhysicalLayout()
        channel = channel_layout.forward(**values)
        inactive = bytearray(channel.read("D", 5))
        inactive[0] ^= 1
        channel.payloads[("D", 5)] = bytes(inactive)
        with self.assertRaisesRegex(ValueError, "D channel tail is corrupted"):
            channel_layout.validate(channel)

        replicated = batch_layout.forward(**values)
        multiplier = bytearray(replicated.read("multiplier", 3))
        multiplier[0] ^= 1
        replicated.payloads[("multiplier", 3)] = bytes(multiplier)
        with self.assertRaisesRegex(
            ValueError, "replicated GlobalAveragePool port multiplier differs"
        ):
            batch_layout.validate(replicated)

        with self.assertRaisesRegex(ValueError, "channels_last=0"):
            batch_layout.plan(input_shape=(3, 5, 2, 3), channels_last=1)
        with self.assertRaisesRegex(TypeError, "accumulator must be int32"):
            bad = dict(values)
            bad["accumulator"] = values["accumulator"].astype(np.int64)
            batch_layout.forward(**bad)
        with self.assertRaisesRegex(ValueError, "outside its slice"):
            batch_layout.forward(
                **values, input_base_addresses=tuple(range(16))
            )


if __name__ == "__main__":
    unittest.main()
