from __future__ import annotations

import unittest

import numpy as np

from resnet50_pipeline.add16_layout import (
    QLinearAddBatch16PhysicalLayout,
    QLinearAddChannel16PhysicalLayout,
)
from resnet50_pipeline.conv16_layout import ConvBatch16PhysicalLayout
from resnet50_pipeline.conv16_ring_layout import ConvRing16PhysicalLayout
from resnet50_pipeline.golden.subops import _qlinear_add


class QLinearAdd16PhysicalLayoutTests(unittest.TestCase):
    def _residual_case(self) -> dict[str, np.ndarray]:
        rng = np.random.default_rng(20260712)
        values = {
            "a": rng.integers(0, 256, size=(3, 5, 2, 3), dtype=np.uint8),
            "a_scale": np.array([0.025], dtype=np.float32),
            "a_zero_point": np.array([111], dtype=np.uint8),
            "b": rng.integers(0, 256, size=(3, 5, 2, 3), dtype=np.uint8),
            "b_scale": np.array([0.04], dtype=np.float32),
            "b_zero_point": np.array([97], dtype=np.uint8),
            "y_scale": np.array([0.03], dtype=np.float32),
            "y_zero_point": np.array([103], dtype=np.uint8),
        }
        values["output"] = _qlinear_add(
            [
                values["a"],
                values["a_scale"],
                values["a_zero_point"],
                values["b"],
                values["b_scale"],
                values["b_zero_point"],
                values["y_scale"],
                values["y_zero_point"],
            ]
        )
        return values

    @staticmethod
    def _ids() -> dict[str, str]:
        return {
            "A": "residual_main",
            "B": "residual_skip",
            "a_scale": "main_scale",
            "a_zero_point": "main_zp",
            "b_scale": "skip_scale",
            "b_zero_point": "skip_zp",
            "y_scale": "sum_scale",
            "y_zero_point": "sum_zp",
            "D": "residual_sum",
        }

    def test_residual_round_trip_qparams_coordinates_and_records(self) -> None:
        values = self._residual_case()
        for layout in (
            QLinearAddBatch16PhysicalLayout(),
            QLinearAddChannel16PhysicalLayout(),
        ):
            bundle = layout.forward(**values, tensor_ids=self._ids())
            expected = {
                self._ids()[port]: values["output" if port == "D" else port.lower()]
                for port in bundle.metadata["port_order"]
            }
            recovered = layout.inverse(bundle)
            for tensor_id, logical in expected.items():
                np.testing.assert_array_equal(recovered[tensor_id], logical)

            self.assertEqual(bundle.metadata["broadcast_mode"], "same_shape")
            self.assertEqual(bundle.metadata["tails"]["A"], 111)
            self.assertEqual(bundle.metadata["tails"]["B"], 97)
            self.assertEqual(bundle.metadata["tails"]["D"], 103)
            self.assertEqual(layout.validate(bundle)["region_count"], 144)

            d = layout.explain_coordinate(bundle, "residual_sum", (2, 4, 1, 2))
            expected_slice = 2 if layout.topology == "batch" else 4
            self.assertEqual(d["slice_ids"], (expected_slice,))
            scale = layout.explain_coordinate(bundle, "main_scale", (0,))
            self.assertEqual(scale["slice_ids"], tuple(range(16)))
            self.assertEqual(len(scale["addresses"]), 16 * 4)

            records = {record.port: record for record in bundle.layout_records()}
            self.assertEqual(records["A"].contract_status, "candidate")
            self.assertEqual(records["A"].packing["broadcast_mode"], "same_shape")
            self.assertEqual(
                records["a_scale"].partition["policy"],
                "replicated_on_every_slice",
            )

    def test_dense_vector_broadcast_round_trip_and_owner_mapping(self) -> None:
        rng = np.random.default_rng(17)
        a = rng.integers(0, 256, size=(3, 7), dtype=np.uint8)
        b = rng.integers(0, 256, size=(7,), dtype=np.uint8)
        qparams = {
            "a_scale": np.array([0.02], dtype=np.float32),
            "a_zero_point": np.array([109], dtype=np.uint8),
            "b_scale": np.array([0.03], dtype=np.float32),
            "b_zero_point": np.array([91], dtype=np.uint8),
            "y_scale": np.array([0.04], dtype=np.float32),
            "y_zero_point": np.array([100], dtype=np.uint8),
        }
        output = _qlinear_add(
            [
                a,
                qparams["a_scale"],
                qparams["a_zero_point"],
                b,
                qparams["b_scale"],
                qparams["b_zero_point"],
                qparams["y_scale"],
                qparams["y_zero_point"],
            ]
        )
        batch_layout = QLinearAddBatch16PhysicalLayout()
        channel_layout = QLinearAddChannel16PhysicalLayout()
        batch = batch_layout.forward(a=a, b=b, output=output, **qparams)
        channel = channel_layout.forward(a=a, b=b, output=output, **qparams)

        for layout, bundle in ((batch_layout, batch), (channel_layout, channel)):
            self.assertEqual(bundle.metadata["broadcast_mode"], "dense_vector_broadcast")
            np.testing.assert_array_equal(layout.inverse_port(bundle, "A"), a)
            np.testing.assert_array_equal(layout.inverse_port(bundle, "B"), b)
            np.testing.assert_array_equal(layout.inverse_port(bundle, "D"), output)

        self.assertEqual(batch.metadata["ports"]["B"]["placement"], "replicated")
        self.assertEqual(channel.metadata["ports"]["B"]["placement"], "channel")
        batch_b = batch_layout.explain_coordinate(batch, "add_input_b", (6,))
        self.assertEqual(batch_b["slice_ids"], tuple(range(16)))
        channel_b = channel_layout.explain_coordinate(channel, "add_input_b", (6,))
        self.assertEqual(channel_b["slice_ids"], (6,))

    def _conv_producer(self, layout, output: np.ndarray, tensor_id: str, y_zp: int):
        n, channels, height, width = output.shape
        activation = np.zeros((n, 1, height, width), dtype=np.uint8)
        return layout.forward(
            activation=activation,
            weight=np.zeros((channels, 1, 1, 1), dtype=np.int8),
            bias=np.zeros(channels, dtype=np.int32),
            w_scale=np.ones(channels, dtype=np.float32),
            w_zero_point=np.zeros(channels, dtype=np.int8),
            x_scale=np.array([1.0], dtype=np.float32),
            x_zero_point=np.array([0], dtype=np.uint8),
            y_scale=np.array([1.0], dtype=np.float32),
            y_zero_point=np.array([y_zp], dtype=np.uint8),
            accumulator=np.zeros(output.shape, dtype=np.int32),
            output=output,
            tensor_ids={"D": tensor_id},
        )

    def test_both_residual_producers_layout_compatible_and_alias_explicit(self) -> None:
        values = self._residual_case()
        profiles = (
            (QLinearAddBatch16PhysicalLayout(), ConvBatch16PhysicalLayout()),
            (QLinearAddChannel16PhysicalLayout(), ConvRing16PhysicalLayout()),
        )
        for add_layout, conv_layout in profiles:
            producer_a = self._conv_producer(
                conv_layout, values["a"], "residual_main", 111
            )
            producer_b = self._conv_producer(
                conv_layout, values["b"], "residual_skip", 97
            )
            unaliased = add_layout.forward(
                **values,
                tensor_ids=self._ids(),
            )
            for port, producer in (("A", producer_a), ("B", producer_b)):
                proof = add_layout.prove_input_compatibility(
                    producer, unaliased, port
                )
                self.assertTrue(proof["compatible"])
                self.assertTrue(proof["all_physical_bytes_equal"])
                self.assertTrue(proof["memory_plan_rebase_required"])

                addresses = tuple(
                    producer.region("D", slice_id).base_address
                    for slice_id in range(16)
                )
                aliased = add_layout.forward(
                    **values,
                    tensor_ids=self._ids(),
                    input_base_addresses={port: addresses},
                )
                exact = add_layout.prove_input_compatibility(
                    producer, aliased, port, require_same_base=True
                )
                self.assertTrue(exact["exact_alias"])
                self.assertFalse(exact["memory_plan_rebase_required"])
                record = {item.port: item for item in aliased.layout_records()}[port]
                self.assertEqual(record.alias_of, self._ids()[port])
                self.assertTrue(record.packing["input_alias_requested"])

            both_addresses = {
                port: tuple(
                    producer.region("D", slice_id).base_address
                    for slice_id in range(16)
                )
                for port, producer in (("A", producer_a), ("B", producer_b))
            }
            with self.assertRaisesRegex(ValueError, "A/B physical regions overlap"):
                add_layout.forward(
                    **values,
                    tensor_ids=self._ids(),
                    input_base_addresses=both_addresses,
                )

    def test_corruption_and_unsupported_broadcast_fail(self) -> None:
        values = self._residual_case()
        batch_layout = QLinearAddBatch16PhysicalLayout()
        batch = batch_layout.forward(**values)
        payload = bytearray(batch.read("A", 0))
        payload[5] ^= 1
        batch.payloads[("A", 0)] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "A feature tail is corrupted"):
            batch_layout.validate(batch)

        replicated = batch_layout.forward(**values)
        scale = bytearray(replicated.read("a_scale", 3))
        scale[0] ^= 1
        replicated.payloads[("a_scale", 3)] = bytes(scale)
        with self.assertRaisesRegex(ValueError, "replicated Add port a_scale differs"):
            batch_layout.validate(replicated)

        channel_layout = QLinearAddChannel16PhysicalLayout()
        channel = channel_layout.forward(**values)
        inactive = bytearray(channel.read("B", 5))
        inactive[0] ^= 1
        channel.payloads[("B", 5)] = bytes(inactive)
        with self.assertRaisesRegex(ValueError, "B feature tail is corrupted"):
            channel_layout.validate(channel)

        with self.assertRaisesRegex(ValueError, "formal Add supports"):
            batch_layout.plan(a_shape=(3, 5, 2, 3), b_shape=(1, 5, 1, 1))
        with self.assertRaisesRegex(ValueError, "outside its slice"):
            batch_layout.forward(
                **values,
                input_base_addresses={"A": tuple(range(16))},
            )


if __name__ == "__main__":
    unittest.main()
