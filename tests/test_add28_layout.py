from __future__ import annotations

import unittest
from dataclasses import replace

import numpy as np

from resnet50_pipeline.add28_layout import QLinearAddPhysicalLayout
from resnet50_pipeline.conv28_layout import QLinearConvPhysicalLayout
from resnet50_pipeline.errors import ContractError
from resnet50_pipeline.matmul28_layout import QLinearMatMulPhysicalLayout
from resnet50_pipeline.memory import LEGACY_DRAM_GEOMETRY16
from resnet50_pipeline.profile28 import (
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
)
from resnet50_pipeline.topology28 import HIGH_RING_OWNERS, LOW_RING_OWNERS
from tools.verify_w4_add28_layout import build_report


def _requant_add(
    a: np.ndarray,
    b: np.ndarray,
    *,
    a_scale: np.ndarray,
    a_zero_point: np.ndarray,
    b_scale: np.ndarray,
    b_zero_point: np.ndarray,
    y_scale: np.ndarray,
    y_zero_point: np.ndarray,
) -> np.ndarray:
    left = (a.astype(np.int32) - int(a_zero_point[0])).astype(np.float32)
    right = (b.astype(np.int32) - int(b_zero_point[0])).astype(np.float32)
    real = left * a_scale[0] + right * b_scale[0]
    shifted = np.rint(real / y_scale[0]).astype(np.int64) + int(y_zero_point[0])
    return np.clip(shifted, 0, 255).astype(np.uint8)


def _case(
    *,
    features: int = 5,
    height: int = 3,
    width: int = 2,
    dense_broadcast: bool = False,
) -> dict[str, np.ndarray]:
    if dense_broadcast:
        a = np.arange(16 * features, dtype=np.uint16).astype(np.uint8).reshape(
            16, features
        )
        b = (np.arange(features, dtype=np.uint16) * 3 + 7).astype(np.uint8)
    else:
        a = np.arange(
            16 * features * height * width, dtype=np.uint16
        ).astype(np.uint8).reshape(16, features, height, width)
        b = (a.astype(np.uint16) * 5 + 17).astype(np.uint8)
    qparams = {
        "a_scale": np.array([0.03125], dtype=np.float32),
        "a_zero_point": np.array([111], dtype=np.uint8),
        "b_scale": np.array([0.0625], dtype=np.float32),
        "b_zero_point": np.array([123], dtype=np.uint8),
        "y_scale": np.array([0.046875], dtype=np.float32),
        "y_zero_point": np.array([97], dtype=np.uint8),
    }
    output = _requant_add(a, b, **qparams)
    return {"a": a, "b": b, "output": output, **qparams}


def _ids(prefix: str = "add", *, a_id: str | None = None, b_id: str | None = None):
    return {
        "A": a_id or f"{prefix}_A",
        "a_scale": f"{prefix}_a_scale",
        "a_zero_point": f"{prefix}_a_zp",
        "B": b_id or f"{prefix}_B",
        "b_scale": f"{prefix}_b_scale",
        "b_zero_point": f"{prefix}_b_zp",
        "y_scale": f"{prefix}_y_scale",
        "y_zero_point": f"{prefix}_y_zp",
        "D": f"{prefix}_D",
    }


def _bases(layout: QLinearAddPhysicalLayout, offset: int) -> tuple[int, ...]:
    return tuple(
        layout.geometry.slice_base(slice_id) + offset for slice_id in range(28)
    )


class QLinearAdd28PhysicalLayoutTests(unittest.TestCase):
    def _assert_roundtrip(
        self,
        layout: QLinearAddPhysicalLayout,
        values: dict[str, np.ndarray],
        *,
        tensor_ids: dict[str, str] | None = None,
        input_base_addresses: dict[str, tuple[int, ...]] | None = None,
    ):
        ids = tensor_ids or _ids()
        bundle = layout.forward(
            **values,
            tensor_ids=ids,
            input_base_addresses=input_base_addresses,
        )
        recovered = layout.inverse(bundle)
        source = {
            "A": values["a"],
            "a_scale": values["a_scale"],
            "a_zero_point": values["a_zero_point"],
            "B": values["b"],
            "b_scale": values["b_scale"],
            "b_zero_point": values["b_zero_point"],
            "y_scale": values["y_scale"],
            "y_zero_point": values["y_zero_point"],
            "D": values["output"],
        }
        for port, logical in source.items():
            np.testing.assert_array_equal(recovered[ids[port]], logical)
        report = layout.validate(bundle)
        self.assertEqual(report["slice_count"], 28)
        self.assertEqual(report["region_count"], 9 * 28)
        return bundle

    def test_group4x7_residual_roundtrip_independent_qparams_tails_and_coordinates(self):
        layout = QLinearAddPhysicalLayout()
        values = _case(features=5)
        ids = _ids("residual")
        bundle = self._assert_roundtrip(layout, values, tensor_ids=ids)
        plan = bundle.metadata["plan"]
        self.assertEqual(plan["broadcast_mode"], "same_shape")
        self.assertEqual(plan["feature_tile"], 2)
        self.assertEqual(plan["owner_order"], HIGH_RING_OWNERS)
        self.assertNotEqual(values["a_scale"][0], values["b_scale"][0])
        self.assertNotEqual(values["a_zero_point"][0], values["b_zero_point"][0])

        # Sample 15 is local slot 1 in group 6; feature 4 is owner step 2.
        record = layout.explain_coordinate(bundle, ids["A"], (15, 4, 2, 1))[0]
        self.assertEqual(record["slice_id"], HIGH_RING_OWNERS[6][2])
        self.assertEqual(record["physical_coordinate"], (1, 2, 1, 0))
        self.assertEqual(len(layout.explain_coordinate(bundle, ids["a_scale"], (0,))), 28)

        owner = HIGH_RING_OWNERS[2][2]
        region = bundle.region("A", owner)
        self.assertEqual((region.sample_start, region.sample_count), (6, 2))
        local_a = layout._read_array(bundle, "A", owner)
        local_b = layout._read_array(bundle, "B", owner)
        local_d = layout._read_array(bundle, "D", owner)
        self.assertTrue(np.all(local_a[:, :, :, 1] == values["a_zero_point"][0]))
        self.assertTrue(np.all(local_b[:, :, :, 1] == values["b_zero_point"][0]))
        self.assertTrue(np.all(local_d[:, :, :, 1] == values["y_zero_point"][0]))
        records = {item.port: item for item in bundle.layout_records()}
        self.assertTrue(records["A"].packing["independent_input_qparams"])
        self.assertEqual(records["D"].packing["physical_order"], "NHWF-local")

    def test_global_residual_roundtrip_owner_order_and_determinism(self):
        layout = QLinearAddPhysicalLayout(GLOBAL_RING28_PROFILE)
        values = _case(features=31, height=2, width=1)
        first = self._assert_roundtrip(layout, values)
        second = layout.forward(**values, tensor_ids=_ids())
        self.assertEqual(first.payloads, second.payloads)
        self.assertEqual(first.metadata["plan"]["owner_order"], LOW_RING_OWNERS)
        self.assertEqual(first.metadata["plan"]["feature_tile"], 2)
        record = layout.explain_coordinate(first, "add_A", (15, 30, 1, 0))[0]
        self.assertEqual(record["slice_id"], LOW_RING_OWNERS[15])
        self.assertEqual(record["physical_coordinate"], (15, 1, 0, 0))

    def test_dense_vector_broadcast_both_profiles_and_replica_rules(self):
        values = _case(features=7, dense_broadcast=True)
        for profile in (
            GROUP4X7_BATCH_CHANNEL28_PROFILE,
            GLOBAL_RING28_PROFILE,
        ):
            with self.subTest(profile=profile):
                layout = QLinearAddPhysicalLayout(profile)
                bundle = self._assert_roundtrip(layout, values)
                self.assertEqual(
                    bundle.metadata["broadcast_mode"], "dense_vector_broadcast"
                )
                records = layout.explain_coordinate(bundle, "add_B", (6,))
                if profile == GROUP4X7_BATCH_CHANNEL28_PROFILE:
                    self.assertEqual(len(records), 7)
                    self.assertEqual(
                        tuple(item["slice_id"] for item in records),
                        tuple(owners[3] for owners in HIGH_RING_OWNERS),
                    )
                    payload = bundle.read("B", HIGH_RING_OWNERS[0][3])
                    self.assertTrue(
                        all(
                            bundle.read("B", HIGH_RING_OWNERS[group][3]) == payload
                            for group in range(1, 7)
                        )
                    )
                else:
                    self.assertEqual(len(records), 1)
                    self.assertEqual(records[0]["slice_id"], LOW_RING_OWNERS[6])

    def test_all_formal_resnet_shapes_fit_both_profiles(self):
        residual_shapes = (
            (16, 256, 56, 56),
            (16, 512, 28, 28),
            (16, 1024, 14, 14),
            (16, 2048, 7, 7),
        )
        for profile in (
            GROUP4X7_BATCH_CHANNEL28_PROFILE,
            GLOBAL_RING28_PROFILE,
        ):
            layout = QLinearAddPhysicalLayout(profile)
            for shape in residual_shapes:
                with self.subTest(profile=profile, shape=shape):
                    report = layout.capacity_report(a_shape=shape, b_shape=shape)
                    self.assertTrue(report["fits"])
                    self.assertGreater(report["capacity_margin_bytes"], 0)
                    self.assertEqual(report["broadcast_mode"], "same_shape")
            dense = layout.capacity_report(a_shape=(16, 1000), b_shape=(1000,))
            self.assertTrue(dense["fits"])
            self.assertEqual(dense["broadcast_mode"], "dense_vector_broadcast")

    @staticmethod
    def _conv_producer(output: np.ndarray, tensor_id: str, tail: int):
        outputs = output.shape[1]
        values = {
            "activation": np.zeros((16, 1, output.shape[2], output.shape[3]), np.uint8),
            "weight": np.zeros((outputs, 1, 1, 1), np.int8),
            "bias": np.zeros(outputs, np.int32),
            "w_scale": np.ones(outputs, np.float32),
            "w_zero_point": np.zeros(outputs, np.int8),
            "x_scale": np.array([1.0], np.float32),
            "x_zero_point": np.array([0], np.uint8),
            "y_scale": np.array([1.0], np.float32),
            "y_zero_point": np.array([tail], np.uint8),
            "accumulator": np.zeros(output.shape, np.int32),
            "output": output,
        }
        ids = {
            "A": f"{tensor_id}_conv_A",
            "B": f"{tensor_id}_conv_B",
            "bias": f"{tensor_id}_bias",
            "w_scale": f"{tensor_id}_ws",
            "w_zero_point": f"{tensor_id}_wz",
            "x_scale": f"{tensor_id}_xs",
            "x_zero_point": f"{tensor_id}_xz",
            "y_scale": f"{tensor_id}_ys",
            "y_zero_point": f"{tensor_id}_yz",
            "P": f"{tensor_id}_P",
            "D": tensor_id,
        }
        return QLinearConvPhysicalLayout().forward(**values, tensor_ids=ids)

    def test_two_conv_branches_are_byte_compatible_but_default_aliases_conflict(self):
        layout = QLinearAddPhysicalLayout()
        values = _case(features=5)
        ids = _ids("sum", a_id="branch_a", b_id="branch_b")
        bundle = layout.forward(**values, tensor_ids=ids)
        producer_a = self._conv_producer(values["a"], "branch_a", 111)
        producer_b = self._conv_producer(values["b"], "branch_b", 123)
        proof_a = layout.prove_input_compatibility(producer_a, bundle, "A")
        proof_b = layout.prove_input_compatibility(producer_b, bundle, "B")
        self.assertTrue(proof_a["compatible"] and proof_b["compatible"])
        self.assertFalse(proof_a["exact_alias"] or proof_b["exact_alias"])
        self.assertTrue(proof_a["memory_plan_rebase_required"])

        # Both independent producer layouts default D to the same offset.  Treating
        # both as simultaneous zero-copy aliases must fail instead of overwriting one.
        with self.assertRaisesRegex(ValueError, "simultaneous A/B alias regions overlap"):
            layout.forward(
                **values,
                tensor_ids=ids,
                input_base_addresses={
                    "A": tuple(
                        producer_a.region("D", slice_id).base_address
                        for slice_id in range(28)
                    ),
                    "B": tuple(
                        producer_b.region("D", slice_id).base_address
                        for slice_id in range(28)
                    ),
                },
            )

    def test_distinct_live_producer_ranges_allow_two_exact_aliases(self):
        layout = QLinearAddPhysicalLayout()
        values = _case(features=5)
        zeros = np.zeros_like(values["a"])

        def producer(prefix: str, output: np.ndarray, output_tail: int, offset=None):
            qparams = {
                "a_scale": np.array([0.125], np.float32),
                "a_zero_point": np.array([10], np.uint8),
                "b_scale": np.array([0.25], np.float32),
                "b_zero_point": np.array([20], np.uint8),
                "y_scale": np.array([0.5], np.float32),
                "y_zero_point": np.array([output_tail], np.uint8),
            }
            ids = _ids(prefix)
            ids["D"] = prefix
            return layout.forward(
                a=zeros,
                b=zeros,
                output=output,
                **qparams,
                tensor_ids=ids,
                input_base_addresses=(
                    None if offset is None else {"A": _bases(layout, offset)}
                ),
            )

        producer_a = producer("branch_a", values["a"], 111)
        producer_b = producer("branch_b", values["b"], 123, 1 << 20)
        ids = _ids("consumer", a_id="branch_a", b_id="branch_b")
        consumer = self._assert_roundtrip(
            layout,
            values,
            tensor_ids=ids,
            input_base_addresses={
                "A": tuple(
                    producer_a.region("D", slice_id).base_address
                    for slice_id in range(28)
                ),
                "B": tuple(
                    producer_b.region("D", slice_id).base_address
                    for slice_id in range(28)
                ),
            },
        )
        proof = layout.prove_simultaneous_alias_safety(
            producer_a, producer_b, consumer
        )
        self.assertTrue(proof["exact_alias_A"])
        self.assertTrue(proof["exact_alias_B"])
        self.assertTrue(proof["all_slice_ranges_non_overlapping"])
        self.assertEqual(len(proof["checked_ranges"]), 28)

    def test_matmul_D_is_dense_add_A_compatible(self):
        layout = QLinearAddPhysicalLayout()
        values = _case(features=7, dense_broadcast=True)
        reduction = 5
        matmul = QLinearMatMulPhysicalLayout()
        matmul_ids = {
            "A": "mm_A",
            "a_scale": "mm_as",
            "a_zero_point": "mm_az",
            "B": "mm_B",
            "b_scale": "mm_bs",
            "b_zero_point": "mm_bz",
            "y_scale": "mm_ys",
            "y_zero_point": "mm_yz",
            "multiplier": "mm_mul",
            "P": "mm_P",
            "D": "dense_activation",
        }
        producer = matmul.forward(
            activation=np.zeros((16, reduction), np.uint8),
            weight=np.zeros((reduction, 7), np.int8),
            a_scale=np.array([1.0], np.float32),
            a_zero_point=np.array([0], np.uint8),
            b_scale=np.array([1.0], np.float32),
            b_zero_point=np.array([0], np.int8),
            y_scale=np.array([1.0], np.float32),
            y_zero_point=values["a_zero_point"],
            accumulator=np.zeros((16, 7), np.int32),
            output=values["a"],
            tensor_ids=matmul_ids,
        )
        ids = _ids("dense", a_id="dense_activation")
        consumer = layout.forward(**values, tensor_ids=ids)
        proof = layout.prove_input_compatibility(producer, consumer, "A")
        self.assertTrue(proof["compatible"])
        self.assertFalse(proof["exact_alias"])

    def test_corruption_and_invalid_contracts_fail_closed(self):
        layout = QLinearAddPhysicalLayout()
        values = _case(features=5)
        bundle = layout.forward(**values, tensor_ids=_ids())

        owner = HIGH_RING_OWNERS[0][2]
        payloads = dict(bundle.payloads)
        damaged = bytearray(payloads[("A", owner)])
        damaged[-1] = 1
        payloads[("A", owner)] = bytes(damaged)
        with self.assertRaisesRegex(ValueError, "alignment padding"):
            layout.validate(replace(bundle, payloads=payloads))

        payloads = dict(bundle.payloads)
        damaged = bytearray(payloads[("a_scale", 1)])
        damaged[0] ^= 1
        payloads[("a_scale", 1)] = bytes(damaged)
        with self.assertRaisesRegex(ValueError, "replicated a_scale"):
            layout.validate(replace(bundle, payloads=payloads))

        with self.assertRaises(ContractError):
            QLinearAddPhysicalLayout("legacy16")
        with self.assertRaisesRegex(ValueError, "TARGET_DRAM_GEOMETRY28"):
            QLinearAddPhysicalLayout(geometry=LEGACY_DRAM_GEOMETRY16)
        with self.assertRaisesRegex(ValueError, "equal rank-2/rank-4"):
            layout.plan(a_shape=(16, 5, 3, 2), b_shape=(5,))
        with self.assertRaisesRegex(ValueError, "batch=16"):
            layout.plan(a_shape=(15, 5), b_shape=(15, 5))
        with self.assertRaisesRegex(TypeError, "A/B/D must be uint8"):
            layout.forward(**{**values, "a": values["a"].astype(np.int8)})
        with self.assertRaisesRegex(ValueError, "positive and finite"):
            layout.forward(
                **{**values, "a_scale": np.array([0.0], dtype=np.float32)}
            )
        with self.assertRaisesRegex(ValueError, "unique"):
            duplicate = _ids()
            duplicate["B"] = duplicate["A"]
            layout.forward(**values, tensor_ids=duplicate)
        with self.assertRaisesRegex(ValueError, "not aligned"):
            layout.forward(
                **values,
                input_base_addresses={"A": _bases(layout, 1)},
            )

    def test_candidate_report_is_deterministic_and_has_no_gate_authority(self):
        first = build_report()
        second = build_report()
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "candidate_unapproved")
        self.assertFalse(first["hardware_approval"])
        self.assertFalse(first["g4_passed"])
        self.assertFalse(first["w5_authorized"])
        self.assertEqual(first["formal_resnet"]["add_node_count"], 17)
        self.assertEqual(first["formal_resnet"]["residual_same_shape_count"], 16)
        self.assertEqual(first["formal_resnet"]["dense_vector_broadcast_count"], 1)
        self.assertTrue(
            first["alias_policy"]["overlapping_dual_alias_rejected"]
        )


if __name__ == "__main__":
    unittest.main()
