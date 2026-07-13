from __future__ import annotations

import unittest

import numpy as np

from resnet50_pipeline.errors import ContractError
from resnet50_pipeline.memory import (
    LEGACY_DRAM_GEOMETRY16,
    TARGET_DRAM_GEOMETRY28,
)
from resnet50_pipeline.profile28 import (
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
)
from resnet50_pipeline.conv28_layout import QLinearConvPhysicalLayout
from resnet50_pipeline.topology28 import HIGH_RING_OWNERS, LOW_RING_OWNERS


def _case(
    *,
    channels: int = 5,
    outputs: int = 7,
    height: int = 3,
    width: int = 2,
    kernel: tuple[int, int] = (2, 1),
) -> dict[str, np.ndarray]:
    activation = np.arange(
        16 * channels * height * width, dtype=np.uint16
    ).astype(np.uint8).reshape(16, channels, height, width)
    weight = (
        np.arange(outputs * channels * kernel[0] * kernel[1], dtype=np.int16)
        % 101
        - 50
    ).astype(np.int8).reshape(outputs, channels, *kernel)
    output_shape = (16, outputs, height - kernel[0] + 1, width - kernel[1] + 1)
    accumulator = np.arange(np.prod(output_shape), dtype=np.int32).reshape(
        output_shape
    )
    output = np.arange(np.prod(output_shape), dtype=np.uint16).astype(
        np.uint8
    ).reshape(output_shape)
    return {
        "activation": activation,
        "weight": weight,
        "bias": np.arange(outputs, dtype=np.int32) - 3,
        "w_scale": np.linspace(0.125, 0.875, outputs, dtype=np.float32),
        "w_zero_point": (np.arange(outputs, dtype=np.int16) - 3).astype(np.int8),
        "x_scale": np.array([0.25], dtype=np.float32),
        "x_zero_point": np.array([113], dtype=np.uint8),
        "y_scale": np.array([0.5], dtype=np.float32),
        "y_zero_point": np.array([127], dtype=np.uint8),
        "accumulator": accumulator,
        "output": output,
    }


class Rtl28QLinearConvPhysicalLayoutTests(unittest.TestCase):
    def test_group4x7_round_trip_tail_records_and_coordinate_formula(self) -> None:
        layout = QLinearConvPhysicalLayout()
        values = _case()
        tensor_ids = {
            "A": "a",
            "B": "b",
            "bias": "bias",
            "w_scale": "ws",
            "w_zero_point": "wz",
            "x_scale": "xs",
            "x_zero_point": "xz",
            "y_scale": "ys",
            "y_zero_point": "yz",
            "P": "psum",
            "D": "d",
        }
        bundle = layout.forward(**values, tensor_ids=tensor_ids)
        recovered = layout.inverse(bundle)
        for port, tensor_id in tensor_ids.items():
            np.testing.assert_array_equal(recovered[tensor_id], values[
                {
                    "A": "activation",
                    "B": "weight",
                    "P": "accumulator",
                    "D": "output",
                }.get(port, port)
            ])

        report = layout.validate(bundle)
        self.assertEqual(report["target_family"], "rtl28")
        self.assertEqual(report["slice_count"], 28)
        self.assertEqual(report["region_count"], 28 * 11)
        self.assertGreater(report["semantic_tail_elements"], 0)
        self.assertIs(bundle.plan.geometry, TARGET_DRAM_GEOMETRY28)
        self.assertEqual(bundle.plan.c_tile, 2)
        self.assertEqual(bundle.plan.k_tile, 2)
        self.assertEqual(bundle.plan.c_padded, 16)

        # N=15 belongs to the final two-sample group. C=4 is owner step 2.
        a_address = layout.explain_coordinate(bundle, "a", (15, 4, 2, 1))
        self.assertEqual(a_address[0]["slice_id"], HIGH_RING_OWNERS[6][2])
        self.assertEqual(a_address[0]["group_id"], 6)
        self.assertEqual(a_address[0]["physical_coordinate"], (1, 2, 1, 0))

        # K-owned static data is copied at the same owner step in all 7 rings.
        b_address = layout.explain_coordinate(bundle, "b", (6, 4, 1, 0))
        self.assertEqual(
            tuple(item["slice_id"] for item in b_address),
            tuple(ring[3] for ring in HIGH_RING_OWNERS),
        )
        self.assertTrue(
            all(item["semantic"] == "replicated_static_weight" for item in b_address)
        )
        psum = layout.explain_coordinate(bundle, "psum", (2, 6, 1, 1))
        self.assertEqual(psum[0]["slice_id"], HIGH_RING_OWNERS[0][3])
        self.assertEqual(psum[0]["physical_coordinate"], (2, 1, 1, 0))

        two_sample = bundle.region("D", HIGH_RING_OWNERS[2][0])
        self.assertEqual(two_sample.sample_count, 2)
        self.assertEqual(two_sample.storage_sample_count, 3)
        self.assertEqual(two_sample.physical_shape, (3, 2, 2, 2))

        records = {record.port: record for record in bundle.layout_records()}
        self.assertEqual(records["A"].partition["axis"], 1)
        self.assertEqual(records["B"].partition["axis"], 0)
        self.assertEqual(records["B"].partition["owner_axis"], "K")
        self.assertEqual(records["A"].partition["owner_tile"], 2)
        self.assertEqual(
            records["B"].partition["high_ring_owners"],
            [list(item) for item in HIGH_RING_OWNERS],
        )
        self.assertTrue(
            records["B"].partition["static_k_data_replicated_across_groups"]
        )
        self.assertEqual(records["B"].packing["byte_order"], "little")
        self.assertEqual(
            records["D"].packing["address_order_status"],
            "candidate_unapproved",
        )

    def test_per_channel_weight_c_tail_and_k_tail_are_unambiguous(self) -> None:
        layout = QLinearConvPhysicalLayout()
        values = _case()
        bundle = layout.forward(**values)
        # owner step 0 has K0/K1: each valid row uses its own w_zp for C tail.
        owner = HIGH_RING_OWNERS[0][0]
        b = layout._read_array(bundle, "B", owner)
        np.testing.assert_array_equal(b[:, :, 0, 5:], values["w_zero_point"][0])
        np.testing.assert_array_equal(b[:, :, 1, 5:], values["w_zero_point"][1])
        # owner step 3 owns K6 and one invalid K slot. Invalid K is deterministic 0.
        last_owner = HIGH_RING_OWNERS[0][3]
        last_b = layout._read_array(bundle, "B", last_owner)
        np.testing.assert_array_equal(
            last_b[:, :, 0, 5:], values["w_zero_point"][6]
        )
        self.assertTrue(np.all(last_b[:, :, 1, :] == 0))
        self.assertEqual(layout.validate(bundle)["profile_id"], layout.profile_id)

    def test_global_low_ring_round_trip_and_owner_order(self) -> None:
        layout = QLinearConvPhysicalLayout(profile_id=GLOBAL_RING28_PROFILE)
        values = _case(channels=31, outputs=29, height=2, width=1, kernel=(1, 1))
        bundle = layout.forward(**values)
        recovered = layout.inverse(bundle)
        np.testing.assert_array_equal(recovered["conv_a"], values["activation"])
        np.testing.assert_array_equal(recovered["conv_b"], values["weight"])
        np.testing.assert_array_equal(recovered["conv_bias"], values["bias"])
        np.testing.assert_array_equal(recovered["conv_p"], values["accumulator"])
        np.testing.assert_array_equal(recovered["conv_d"], values["output"])
        self.assertEqual(bundle.plan.c_tile, 2)
        self.assertEqual(bundle.plan.k_tile, 2)
        self.assertEqual(bundle.plan.storage_sample_count, 16)

        a = layout.explain_coordinate(bundle, "conv_a", (7, 30, 1, 0))
        self.assertEqual(a[0]["slice_id"], LOW_RING_OWNERS[15])
        self.assertEqual(a[0]["owner_step"], 15)
        self.assertEqual(a[0]["physical_coordinate"], (7, 1, 0, 0))
        b = layout.explain_coordinate(bundle, "conv_b", (28, 30, 0, 0))
        self.assertEqual(b[0]["slice_id"], LOW_RING_OWNERS[14])
        self.assertEqual(len(b), 1)
        self.assertEqual(b[0]["semantic"], "partitioned_static_weight")
        record = {item.port: item for item in bundle.layout_records()}["D"]
        self.assertEqual(record.partition["low_ring_owners"], list(LOW_RING_OWNERS))

    def test_corruption_and_legacy_configuration_fail_closed(self) -> None:
        with self.assertRaisesRegex(ContractError, "unsupported profile28"):
            QLinearConvPhysicalLayout(profile_id="legacy16")
        with self.assertRaisesRegex(ValueError, "TARGET_DRAM_GEOMETRY28"):
            QLinearConvPhysicalLayout(geometry=LEGACY_DRAM_GEOMETRY16)
        layout = QLinearConvPhysicalLayout()
        with self.assertRaisesRegex(ValueError, "batch=16"):
            layout.plan(
                activation_shape=(15, 3, 8, 8),
                weight_shape=(8, 3, 3, 3),
            )
        bad_scale = _case()
        bad_scale["w_scale"] = bad_scale["w_scale"].copy()
        bad_scale["w_scale"][0] = 0.0
        with self.assertRaisesRegex(ValueError, "positive and finite"):
            layout.forward(**bad_scale)

        # Inactive third sample slot in a two-sample group must remain x_zp.
        bundle = layout.forward(**_case())
        owner = HIGH_RING_OWNERS[2][0]
        region = bundle.region("A", owner)
        payload = bytearray(bundle.read("A", owner))
        local = np.frombuffer(
            payload, dtype=np.uint8, count=region.payload_bytes
        ).reshape(region.physical_shape)
        local[2, 0, 0, 0] = 9
        bundle.payloads[("A", owner)] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "A semantic tail"):
            layout.validate(bundle)

        # Valid-K B C-tail must equal that exact output channel's zero-point.
        bundle = layout.forward(**_case())
        owner = HIGH_RING_OWNERS[0][0]
        region = bundle.region("B", owner)
        payload = bytearray(bundle.read("B", owner))
        local = np.frombuffer(
            payload, dtype=np.int8, count=region.payload_bytes
        ).reshape(region.physical_shape)
        local[0, 0, 0, 5] = np.int8(local[0, 0, 0, 5] + 1)
        bundle.payloads[("B", owner)] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "per-channel C-tail"):
            layout.validate(bundle)

        # A valid static byte still has to match its six group replicas.
        bundle = layout.forward(**_case())
        owner = HIGH_RING_OWNERS[1][0]
        payload = bytearray(bundle.read("bias", owner))
        payload[0] ^= 1
        bundle.payloads[("bias", owner)] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "differs across groups"):
            layout.validate(bundle)

        # Every scalar qparam is replicated on all 28 slices.
        bundle = layout.forward(**_case())
        payload = bytearray(bundle.read("x_scale", 1))
        payload[:4] = np.asarray([2.0], dtype="<f4").tobytes()
        bundle.payloads[("x_scale", 1)] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "differs between slices"):
            layout.validate(bundle)

        # The anonymous bytes added only for 16-byte alignment remain zero.
        bundle = layout.forward(**_case())
        region = bundle.region("x_zero_point", 0)
        self.assertGreater(region.size_bytes, region.payload_bytes)
        payload = bytearray(bundle.read("x_zero_point", 0))
        payload[region.payload_bytes] = 1
        bundle.payloads[("x_zero_point", 0)] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "alignment padding"):
            layout.validate(bundle)

    def test_formal_conv0_terminal_and_downsample_plans_do_not_allocate(self) -> None:
        layout = QLinearConvPhysicalLayout()
        conv0 = layout.formal_plan(
            activation_shape=(16, 3, 224, 224),
            weight_shape=(64, 3, 7, 7),
            strides=(2, 2),
            pads=(3, 3, 3, 3),
        )
        self.assertEqual(conv0.output_shape, (16, 64, 112, 112))
        self.assertEqual((conv0.c_tile, conv0.k_tile, conv0.c_padded), (1, 16, 16))
        self.assertTrue(conv0.capacity_report()["fits"])
        self.assertLess(conv0.per_slice_used_bytes, conv0.per_slice_capacity_bytes)

        terminal = layout.capacity(
            activation_shape=(16, 512, 7, 7),
            weight_shape=(2048, 512, 1, 1),
        )
        self.assertTrue(terminal["fits"])
        self.assertEqual(terminal["slice_count"], 28)

        downsample = layout.plan(
            activation_shape=(16, 512, 28, 28),
            weight_shape=(1024, 512, 1, 1),
            strides=(2, 2),
        )
        self.assertEqual(downsample.output_shape, (16, 1024, 14, 14))
        self.assertTrue(downsample.capacity_report()["fits"])
        self.assertEqual(downsample.port("B").physical_shape, (1, 1, 256, 512))

        global_plan = QLinearConvPhysicalLayout(
            profile_id=GLOBAL_RING28_PROFILE
        ).plan(
            activation_shape=(16, 512, 7, 7),
            weight_shape=(2048, 512, 1, 1),
        )
        self.assertEqual(global_plan.profile_id, GLOBAL_RING28_PROFILE)
        self.assertEqual(global_plan.c_tile, 19)
        self.assertEqual(global_plan.k_tile, 74)
        self.assertTrue(global_plan.capacity_report()["fits"])

    def test_deterministic_forward_payloads(self) -> None:
        layout = QLinearConvPhysicalLayout(
            profile_id=GROUP4X7_BATCH_CHANNEL28_PROFILE
        )
        first = layout.forward(**_case())
        second = layout.forward(**_case())
        self.assertEqual(first.plan, second.plan)
        self.assertEqual(first.regions, second.regions)
        self.assertEqual(first.payloads, second.payloads)


if __name__ == "__main__":
    unittest.main()
