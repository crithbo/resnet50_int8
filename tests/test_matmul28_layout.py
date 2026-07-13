from __future__ import annotations

import unittest

import numpy as np

from resnet50_pipeline.golden.subops import _requantize, matmul_accumulator
from resnet50_pipeline.matmul28_layout import QLinearMatMulPhysicalLayout
from resnet50_pipeline.memory import LEGACY_DRAM_GEOMETRY16
from resnet50_pipeline.profile28 import (
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
)
from resnet50_pipeline.simple_layout import QuantizeLinearPhysicalLayout
from resnet50_pipeline.topology28 import HIGH_RING_OWNERS, LOW_RING_OWNERS, TOPOLOGY28
from tools.verify_w4_matmul28_layout import build_report


class QLinearMatMul28PhysicalLayoutTests(unittest.TestCase):
    @staticmethod
    def _ids(shared_input: str = "matmul_A") -> dict[str, str]:
        return {
            "A": shared_input,
            "a_scale": "matmul_a_scale",
            "a_zero_point": "matmul_a_zp",
            "B": "matmul_B",
            "b_scale": "matmul_b_scale",
            "b_zero_point": "matmul_b_zp",
            "y_scale": "matmul_y_scale",
            "y_zero_point": "matmul_y_zp",
            "multiplier": "matmul_multiplier",
            "P": "matmul_P",
            "D": "matmul_D",
        }

    @staticmethod
    def _case(
        *, reduction: int = 5, outputs: int = 7, weight_dtype: str = "int8"
    ) -> dict[str, np.ndarray]:
        rng = np.random.default_rng(20260713 + reduction * 31 + outputs)
        activation = rng.integers(0, 256, size=(16, reduction), dtype=np.uint8)
        if weight_dtype == "int8":
            weight = rng.integers(
                -20, 21, size=(reduction, outputs), dtype=np.int16
            ).astype(np.int8)
            b_zero_point = np.array([-2], dtype=np.int8)
        else:
            weight = rng.integers(
                0, 256, size=(reduction, outputs), dtype=np.uint8
            )
            b_zero_point = np.array([121], dtype=np.uint8)
        a_scale = np.array([0.025], dtype=np.float32)
        a_zero_point = np.array([111], dtype=np.uint8)
        b_scale = np.array([0.0125], dtype=np.float32)
        y_scale = np.array([0.04], dtype=np.float32)
        y_zero_point = np.array([97], dtype=np.uint8)
        accumulator = matmul_accumulator(
            activation, weight, int(a_zero_point[0]), b_zero_point
        )
        multiplier = np.array(
            [a_scale[0] * b_scale[0] / y_scale[0]], dtype=np.float32
        )
        output = _requantize(accumulator, multiplier, int(y_zero_point[0]))
        return {
            "activation": activation,
            "weight": weight,
            "a_scale": a_scale,
            "a_zero_point": a_zero_point,
            "b_scale": b_scale,
            "b_zero_point": b_zero_point,
            "y_scale": y_scale,
            "y_zero_point": y_zero_point,
            "accumulator": accumulator,
            "output": output,
        }

    def _assert_roundtrip(
        self,
        layout: QLinearMatMulPhysicalLayout,
        values: dict[str, np.ndarray],
    ) -> object:
        ids = self._ids()
        bundle = layout.forward(**values, tensor_ids=ids)
        recovered = layout.inverse(bundle)
        port_values = {
            "A": values["activation"],
            "a_scale": values["a_scale"],
            "a_zero_point": values["a_zero_point"],
            "B": values["weight"],
            "b_scale": values["b_scale"],
            "b_zero_point": values["b_zero_point"],
            "y_scale": values["y_scale"],
            "y_zero_point": values["y_zero_point"],
            "multiplier": np.array(
                [
                    values["a_scale"][0]
                    * values["b_scale"][0]
                    / values["y_scale"][0]
                ],
                dtype=np.float32,
            ),
            "P": values["accumulator"],
            "D": values["output"],
        }
        for port, logical in port_values.items():
            np.testing.assert_array_equal(recovered[ids[port]], logical)
        result = layout.validate(bundle)
        self.assertEqual(result["slice_count"], 28)
        self.assertEqual(result["region_count"], 11 * 28)
        return bundle

    def test_group4x7_roundtrip_tails_boundaries_coordinates_and_records(self) -> None:
        layout = QLinearMatMulPhysicalLayout()
        values = self._case(reduction=5, outputs=7)
        bundle = self._assert_roundtrip(layout, values)
        plan = bundle.metadata["plan"]
        self.assertEqual(plan["k_tile"], 2)
        self.assertEqual(plan["o_tile"], 2)
        self.assertEqual(plan["owner_order"], HIGH_RING_OWNERS)

        sample_15_a = layout.explain_coordinate(bundle, "matmul_A", (15, 4))
        self.assertEqual(len(sample_15_a), 1)
        self.assertEqual(sample_15_a[0]["slice_id"], HIGH_RING_OWNERS[6][2])
        self.assertEqual(sample_15_a[0]["physical_coordinate"], (1, 0))
        copied_b = layout.explain_coordinate(bundle, "matmul_B", (4, 6))
        self.assertEqual(
            tuple(item["slice_id"] for item in copied_b),
            tuple(owners[3] for owners in HIGH_RING_OWNERS),
        )
        accumulator = layout.explain_coordinate(bundle, "matmul_P", (2, 6))
        self.assertEqual(len(accumulator), 4)
        self.assertEqual(accumulator[0]["slice_id"], HIGH_RING_OWNERS[0][3])
        self.assertEqual(accumulator[0]["semantic"], "final_accumulator")

        group_two_a = bundle.region("A", HIGH_RING_OWNERS[2][0])
        self.assertEqual((group_two_a.sample_start, group_two_a.sample_count), (6, 2))
        self.assertEqual(group_two_a.storage_sample_count, 3)
        last_b = bundle.region("B", HIGH_RING_OWNERS[0][3])
        self.assertEqual(last_b.feature_count, 1)
        inactive_a = bundle.region("A", HIGH_RING_OWNERS[0][3])
        self.assertFalse(inactive_a.active)

        records = {record.port: record for record in bundle.layout_records()}
        self.assertEqual(records["A"].logical_dtype, "uint8")
        self.assertEqual(records["B"].logical_dtype, "int8")
        self.assertEqual(records["P"].logical_dtype, "int32")
        self.assertEqual(records["A"].packing["byte_order"], "little")
        self.assertEqual(
            records["P"].packing["psum_boundary"],
            "final_int32_accumulator_after_complete_K",
        )
        self.assertEqual(records["B"].partition["owner_order"], HIGH_RING_OWNERS)

        step = layout.explain_reduction_step(
            bundle, sample_id=15, output_feature=6, step=1
        )
        expected_output_owner = HIGH_RING_OWNERS[6][3]
        self.assertEqual(step["output_owner_slice"], expected_output_owner)
        self.assertEqual(
            step["input_owner_slice"],
            TOPOLOGY28.high_ring_for_group(6).next(expected_output_owner),
        )
        self.assertEqual(step["route_source"], "explicit_RTL_HIGH_or_LOW_next_map")

    def test_global_low_roundtrip_uint8_B_and_determinism(self) -> None:
        layout = QLinearMatMulPhysicalLayout(GLOBAL_RING28_PROFILE)
        values = self._case(reduction=29, outputs=31, weight_dtype="uint8")
        first = self._assert_roundtrip(layout, values)
        second = layout.forward(**values, tensor_ids=self._ids())
        self.assertEqual(first.payloads, second.payloads)
        self.assertEqual(first.metadata["plan"]["owner_order"], LOW_RING_OWNERS)
        self.assertEqual(first.metadata["plan"]["k_tile"], 2)
        self.assertEqual(first.metadata["plan"]["o_tile"], 2)

        a = layout.explain_coordinate(first, "matmul_A", (15, 28))
        self.assertEqual(a[0]["slice_id"], LOW_RING_OWNERS[14])
        b = layout.explain_coordinate(first, "matmul_B", (28, 30))
        self.assertEqual(len(b), 1)
        self.assertEqual(b[0]["slice_id"], LOW_RING_OWNERS[15])
        final_step = layout.explain_reduction_step(
            first, sample_id=0, output_feature=30, step=27
        )
        self.assertTrue(final_step["last"])
        self.assertIn(final_step["input_owner_slice"], LOW_RING_OWNERS)

    def test_quantize_D_alias_and_explicit_group_to_global_transition(self) -> None:
        values = self._case(reduction=9, outputs=11)
        for profile_id in (
            GROUP4X7_BATCH_CHANNEL28_PROFILE,
            GLOBAL_RING28_PROFILE,
        ):
            quant_layout = QuantizeLinearPhysicalLayout(profile_id)
            quant = quant_layout.forward(
                input_tensor=values["activation"].astype(np.float32),
                scale=np.array([1.0], dtype=np.float32),
                zero_point=values["a_zero_point"],
                output_tensor=values["activation"],
                tensor_ids={"D": "shared_quantized_flatten"},
            )
            input_bases = tuple(
                quant.region("D", slice_id).base_address for slice_id in range(28)
            )
            layout = QLinearMatMulPhysicalLayout(profile_id)
            matmul = layout.forward(
                **values,
                tensor_ids=self._ids("shared_quantized_flatten"),
                input_base_addresses=input_bases,
            )
            proof = layout.prove_quantize_input_compatibility(
                quant,
                matmul,
                producer_tensor_id="shared_quantized_flatten",
                require_same_base=True,
            )
            self.assertTrue(proof["byte_compatible"])
            self.assertTrue(proof["exact_alias"])
            self.assertFalse(
                layout.classify_quantize_input_transition(
                    quant,
                    matmul,
                    producer_tensor_id="shared_quantized_flatten",
                )["transition_required"]
            )

        group_quant = QuantizeLinearPhysicalLayout().forward(
            input_tensor=values["activation"].astype(np.float32),
            scale=np.array([1.0], dtype=np.float32),
            zero_point=values["a_zero_point"],
            output_tensor=values["activation"],
            tensor_ids={"D": "shared_quantized_flatten"},
        )
        global_layout = QLinearMatMulPhysicalLayout(GLOBAL_RING28_PROFILE)
        global_matmul = global_layout.forward(
            **values, tensor_ids=self._ids("shared_quantized_flatten")
        )
        transition = global_layout.classify_quantize_input_transition(
            group_quant,
            global_matmul,
            producer_tensor_id="shared_quantized_flatten",
        )
        self.assertTrue(transition["transition_required"])
        self.assertEqual(
            transition["transition"],
            "group4x7_to_global_low_relayout_after_GAP_before_MatMul",
        )

    def test_formal_head_plan_capacity_and_scalar_qparam_fact(self) -> None:
        group = QLinearMatMulPhysicalLayout()
        global_layout = QLinearMatMulPhysicalLayout(GLOBAL_RING28_PROFILE)
        group_plan = group.plan(
            activation_shape=(16, 2048),
            weight_shape=(2048, 1000),
            weight_dtype="int8",
        )
        global_plan = global_layout.plan(
            activation_shape=(16, 2048),
            weight_shape=(2048, 1000),
            weight_dtype="int8",
        )
        self.assertEqual((group_plan["k_tile"], group_plan["o_tile"]), (512, 250))
        self.assertEqual((global_plan["k_tile"], global_plan["o_tile"]), (74, 36))
        self.assertLess(group_plan["per_slice_used_bytes"], group_plan["capacity_bytes"])
        self.assertLess(global_plan["per_slice_used_bytes"], global_plan["capacity_bytes"])
        self.assertEqual(group_plan["physical_shapes"]["B"], (2048, 250))
        self.assertEqual(global_plan["physical_shapes"]["B"], (2048, 36))
        report = group.capacity_report(
            activation_shape=(16, 2048), weight_shape=(2048, 1000)
        )
        self.assertTrue(report["fits"])
        self.assertTrue(report["candidate_unapproved"])

        values = self._case()
        bundle = group.forward(**values)
        self.assertEqual(bundle.placement("matmul_b_scale").logical_shape, (1,))
        self.assertEqual(bundle.placement("matmul_b_zero_point").logical_shape, (1,))
        self.assertEqual(bundle.placement("matmul_weight").dtype, "int8")
        self.assertEqual(bundle.placement("matmul_accumulator").dtype, "int32")

    def test_tail_qparam_weight_copy_and_alignment_corruption_fail_closed(self) -> None:
        layout = QLinearMatMulPhysicalLayout()
        values = self._case(reduction=5, outputs=7)

        a_bundle = layout.forward(**values)
        a_slice = HIGH_RING_OWNERS[2][0]
        a_region = a_bundle.region("A", a_slice)
        a_payload = bytearray(a_bundle.read("A", a_slice))
        inactive_sample_offset = a_region.sample_count * a_region.physical_shape[1]
        a_payload[inactive_sample_offset] ^= 1
        a_bundle.payloads[("A", a_slice)] = bytes(a_payload)
        with self.assertRaisesRegex(ValueError, "A feature/sample tail is corrupted"):
            layout.validate(a_bundle)

        b_bundle = layout.forward(**values)
        copied_slice = HIGH_RING_OWNERS[1][0]
        b_payload = bytearray(b_bundle.read("B", copied_slice))
        b_payload[0] ^= 1
        b_bundle.payloads[("B", copied_slice)] = bytes(b_payload)
        with self.assertRaisesRegex(ValueError, "B owner 0 differs across HIGH groups"):
            layout.validate(b_bundle)

        qparam_bundle = layout.forward(**values)
        qparam_payload = bytearray(qparam_bundle.read("b_scale", 4))
        qparam_payload[0] ^= 1
        qparam_bundle.payloads[("b_scale", 4)] = bytes(qparam_payload)
        with self.assertRaisesRegex(ValueError, "b_scale differs between slices"):
            layout.validate(qparam_bundle)

        aligned_bundle = layout.forward(**values)
        a_region = aligned_bundle.region("A", 0)
        self.assertLess(a_region.payload_bytes, a_region.size_bytes)
        aligned_payload = bytearray(aligned_bundle.read("A", 0))
        aligned_payload[-1] = 1
        aligned_bundle.payloads[("A", 0)] = bytes(aligned_payload)
        with self.assertRaisesRegex(ValueError, "alignment padding is corrupted"):
            layout.validate(aligned_bundle)

    def test_invalid_profiles_geometry_shapes_qparams_and_aliases(self) -> None:
        with self.assertRaisesRegex(Exception, "unsupported profile28"):
            QLinearMatMulPhysicalLayout("w4_qlinearmatmul_ring16_candidate_v1")
        with self.assertRaisesRegex(ValueError, "TARGET_DRAM_GEOMETRY28"):
            QLinearMatMulPhysicalLayout(geometry=LEGACY_DRAM_GEOMETRY16)
        layout = QLinearMatMulPhysicalLayout()
        with self.assertRaisesRegex(ValueError, "batch=16"):
            layout.plan(activation_shape=(15, 5), weight_shape=(5, 7))
        with self.assertRaisesRegex(ValueError, "reduction dimension"):
            layout.plan(activation_shape=(16, 5), weight_shape=(4, 7))
        with self.assertRaisesRegex(TypeError, "int8 or uint8"):
            layout.plan(
                activation_shape=(16, 5),
                weight_shape=(5, 7),
                weight_dtype="int16",
            )
        values = self._case()
        bad_weight = {**values, "weight": values["weight"].astype(np.int16)}
        with self.assertRaisesRegex(TypeError, "rank-2 int8 or uint8"):
            layout.forward(**bad_weight)
        bad_zp = {**values, "b_zero_point": values["b_zero_point"].astype(np.int16)}
        with self.assertRaisesRegex(TypeError, "b_zero_point"):
            layout.forward(**bad_zp)
        with self.assertRaisesRegex(ValueError, "contain 28 addresses"):
            layout.forward(**values, input_base_addresses=(0,) * 16)

    def test_candidate_report_is_small_deterministic_and_not_gate_authority(self) -> None:
        first = build_report()
        second = build_report()
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "candidate_unapproved")
        self.assertFalse(first["hardware_approval"])
        self.assertFalse(first["g4_passed"])
        self.assertFalse(first["w5_authorized"])
        self.assertEqual(first["formal_onnx_contract"]["B"], "int8 [2048,1000]")
        self.assertEqual(
            set(first["profiles"]),
            {
                GROUP4X7_BATCH_CHANNEL28_PROFILE,
                GLOBAL_RING28_PROFILE,
            },
        )
        for evidence in first["profiles"].values():
            self.assertTrue(evidence["micro_bit_exact_roundtrip"])
            self.assertTrue(evidence["deterministic_payload"])
            self.assertTrue(evidence["formal_head_capacity"]["fits"])


if __name__ == "__main__":
    unittest.main()
