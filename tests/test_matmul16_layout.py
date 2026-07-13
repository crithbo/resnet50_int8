from __future__ import annotations

import unittest

import numpy as np

from resnet50_pipeline.add16_layout import (
    QLinearAddBatch16PhysicalLayout,
    QLinearAddChannel16PhysicalLayout,
)
from resnet50_pipeline.golden.subops import _requantize, matmul_accumulator
from resnet50_pipeline.matmul16_layout import (
    QLinearMatMulBatch16PhysicalLayout,
    QLinearMatMulRing16PhysicalLayout,
)
from resnet50_pipeline.simple16_layout import QuantizeLinearPhysicalLayout


class QLinearMatMul16PhysicalLayoutTests(unittest.TestCase):
    def _micro_case(self, *, reduction: int = 5) -> dict[str, np.ndarray]:
        rng = np.random.default_rng(20260712 + reduction)
        activation = rng.integers(0, 256, size=(3, reduction), dtype=np.uint8)
        weight = rng.integers(-20, 21, size=(reduction, 7), dtype=np.int16).astype(
            np.int8
        )
        x_scale = np.array([0.025], dtype=np.float32)
        x_zero_point = np.array([111], dtype=np.uint8)
        w_scale = np.array([0.0125], dtype=np.float32)
        w_zero_point = np.array([-2], dtype=np.int8)
        y_scale = np.array([0.04], dtype=np.float32)
        y_zero_point = np.array([97], dtype=np.uint8)
        accumulator = matmul_accumulator(
            activation, weight, int(x_zero_point[0]), w_zero_point
        )
        multiplier = np.array(
            [x_scale[0] * w_scale[0] / y_scale[0]], dtype=np.float32
        )
        output = _requantize(accumulator, multiplier, int(y_zero_point[0]))
        return {
            "activation": activation,
            "weight": weight,
            "x_scale": x_scale,
            "x_zero_point": x_zero_point,
            "w_scale": w_scale,
            "w_zero_point": w_zero_point,
            "y_scale": y_scale,
            "y_zero_point": y_zero_point,
            "accumulator": accumulator,
            "output": output,
        }

    @staticmethod
    def _ids() -> dict[str, str]:
        return {
            "A": "matmul_input",
            "x_scale": "matmul_x_scale",
            "x_zero_point": "matmul_x_zp",
            "B": "matmul_weight",
            "w_scale": "matmul_w_scale",
            "w_zero_point": "matmul_w_zp",
            "y_scale": "matmul_y_scale",
            "y_zero_point": "matmul_y_zp",
            "multiplier": "matmul_multiplier",
            "P": "matmul_accumulator",
            "D": "matmul_output",
        }

    def test_profiles_round_trip_coordinates_records_and_ring_steps(self) -> None:
        values = self._micro_case()
        profiles = (
            QLinearMatMulBatch16PhysicalLayout(),
            QLinearMatMulRing16PhysicalLayout(),
        )
        expected = {
            "matmul_input": values["activation"],
            "matmul_weight": values["weight"],
            "matmul_x_scale": values["x_scale"],
            "matmul_x_zp": values["x_zero_point"],
            "matmul_w_scale": values["w_scale"],
            "matmul_w_zp": values["w_zero_point"],
            "matmul_y_scale": values["y_scale"],
            "matmul_y_zp": values["y_zero_point"],
            "matmul_multiplier": np.array(
                [values["x_scale"][0] * values["w_scale"][0] / values["y_scale"][0]],
                dtype=np.float32,
            ),
            "matmul_accumulator": values["accumulator"],
            "matmul_output": values["output"],
        }
        for layout in profiles:
            bundle = layout.forward(**values, tensor_ids=self._ids())
            recovered = layout.inverse(bundle)
            for tensor_id, logical in expected.items():
                np.testing.assert_array_equal(recovered[tensor_id], logical)
            self.assertEqual(layout.validate(bundle)["region_count"], 176)

            a = layout.explain_coordinate(bundle, "matmul_input", (2, 4))
            self.assertEqual(a["slice_ids"], (2,) if layout.topology == "batch" else (4,))
            b = layout.explain_coordinate(bundle, "matmul_weight", (4, 6))
            self.assertEqual(
                b["slice_ids"], tuple(range(16)) if layout.topology == "batch" else (6,)
            )
            p = layout.explain_coordinate(bundle, "matmul_accumulator", (2, 6))
            self.assertEqual(len(p["addresses"]), 4)
            records = {record.port: record for record in bundle.layout_records()}
            self.assertEqual(records["P"].logical_dtype, "int32")
            self.assertEqual(
                records["P"].packing["psum_boundary"],
                "final_int32_accumulator_after_full_K",
            )

        ring_layout = profiles[1]
        ring = ring_layout.forward(**values, tensor_ids=self._ids())
        first = ring_layout.explain_ring_step(ring, output_feature=6, step=0)
        self.assertEqual(first["output_owner_slice"], 6)
        self.assertEqual(first["input_slice"], 6)
        self.assertFalse(first["has_data"])
        wrapped = ring_layout.explain_ring_step(ring, output_feature=6, step=10)
        self.assertEqual(wrapped["input_slice"], 0)
        self.assertTrue(wrapped["has_data"])
        self.assertTrue(
            ring_layout.explain_ring_step(ring, output_feature=6, step=15)["last"]
        )

    def test_quantize_input_and_dense_add_output_compatibility(self) -> None:
        values = self._micro_case(reduction=8)
        values["x_zero_point"] = np.array([0], dtype=np.uint8)
        values["accumulator"] = matmul_accumulator(
            values["activation"], values["weight"], 0, values["w_zero_point"]
        )
        values["output"] = _requantize(
            values["accumulator"],
            np.array(
                [
                    values["x_scale"][0]
                    * values["w_scale"][0]
                    / values["y_scale"][0]
                ],
                dtype=np.float32,
            ),
            int(values["y_zero_point"][0]),
        )
        quant = QuantizeLinearPhysicalLayout()
        quant_bundle = quant.forward(
            input_tensor=values["activation"].astype(np.float32),
            scale=np.array([1.0], dtype=np.float32),
            zero_point=np.array([0], dtype=np.uint8),
            output_tensor=values["activation"],
            tensor_ids={"D": "matmul_input"},
        )
        batch_layout = QLinearMatMulBatch16PhysicalLayout()
        input_bases = tuple(
            quant_bundle.region("D", slice_id).base_address for slice_id in range(16)
        )
        batch = batch_layout.forward(
            **values,
            tensor_ids=self._ids(),
            input_base_addresses=input_bases,
        )
        proof = batch_layout.prove_batch_quantize_input_alias(quant_bundle, batch)
        self.assertTrue(proof["exact_alias"])

        profiles = (
            (batch_layout, batch, QLinearAddBatch16PhysicalLayout()),
            (
                QLinearMatMulRing16PhysicalLayout(),
                None,
                QLinearAddChannel16PhysicalLayout(),
            ),
        )
        for matmul_layout, bundle, add_layout in profiles:
            if bundle is None:
                bundle = matmul_layout.forward(**values, tensor_ids=self._ids())
            output_bases = tuple(
                bundle.region("D", slice_id).base_address for slice_id in range(16)
            )
            bias = np.zeros(values["output"].shape[1], dtype=np.uint8)
            add_bundle = add_layout.forward(
                a=values["output"],
                a_scale=values["y_scale"],
                a_zero_point=values["y_zero_point"],
                b=bias,
                b_scale=np.array([1.0], dtype=np.float32),
                b_zero_point=np.array([0], dtype=np.uint8),
                y_scale=values["y_scale"],
                y_zero_point=values["y_zero_point"],
                output=values["output"],
                tensor_ids={"A": "matmul_output"},
                input_base_addresses={"A": output_bases},
            )
            output_proof = add_layout.prove_input_compatibility(
                bundle, add_bundle, "A", require_same_base=True
            )
            self.assertTrue(output_proof["exact_alias"])

        with self.assertRaisesRegex(ValueError, "explicit batch-to-K relayout"):
            QLinearMatMulRing16PhysicalLayout().prove_batch_quantize_input_alias(
                quant_bundle,
                QLinearMatMulRing16PhysicalLayout().forward(
                    **values, tensor_ids=self._ids()
                ),
            )

    def test_formal_plan_tail_and_invalid_contracts(self) -> None:
        batch_layout = QLinearMatMulBatch16PhysicalLayout()
        ring_layout = QLinearMatMulRing16PhysicalLayout()
        batch_plan = batch_layout.plan(
            activation_shape=(16, 2048), weight_shape=(2048, 1000)
        )
        ring_plan = ring_layout.plan(
            activation_shape=(16, 2048), weight_shape=(2048, 1000)
        )
        self.assertEqual(batch_plan["output_shape"], (16, 1000))
        self.assertEqual(batch_plan["o_padded"], 1000)
        self.assertEqual(ring_plan["k_tile"], 128)
        self.assertEqual(ring_plan["o_tile"], 63)
        self.assertEqual(ring_plan["o_padded"], 1008)
        self.assertLess(batch_plan["per_slice_used_bytes"], batch_plan["capacity_bytes"])
        self.assertLess(ring_plan["per_slice_used_bytes"], ring_plan["capacity_bytes"])

        values = self._micro_case()
        batch = batch_layout.forward(**values)
        a_tail = bytearray(batch.read("A", 0))
        a_tail[5] ^= 1
        batch.payloads[("A", 0)] = bytes(a_tail)
        with self.assertRaisesRegex(ValueError, "A K tail is corrupted"):
            batch_layout.validate(batch)

        ring = ring_layout.forward(**values)
        inactive = bytearray(ring.read("A", 5))
        inactive[0] ^= 1
        ring.payloads[("A", 5)] = bytes(inactive)
        with self.assertRaisesRegex(ValueError, "A K tail is corrupted"):
            ring_layout.validate(ring)

        replicated = batch_layout.forward(**values)
        scale = bytearray(replicated.read("w_scale", 3))
        scale[0] ^= 1
        replicated.payloads[("w_scale", 3)] = bytes(scale)
        with self.assertRaisesRegex(ValueError, "replicated MatMul port w_scale differs"):
            batch_layout.validate(replicated)

        with self.assertRaisesRegex(ValueError, "reduction dimension"):
            batch_layout.plan(activation_shape=(3, 5), weight_shape=(4, 7))
        with self.assertRaisesRegex(TypeError, "weight must be rank-2 int8"):
            bad = dict(values)
            bad["weight"] = values["weight"].astype(np.int16)
            batch_layout.forward(**bad)


if __name__ == "__main__":
    unittest.main()
