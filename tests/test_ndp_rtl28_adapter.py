from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

from resnet50_pipeline.adapters.ndp_rtl28_functional import (
    NdpRtl28FunctionalAdapter,
)
from resnet50_pipeline.conv28_layout import QLinearConvPhysicalLayout
from resnet50_pipeline.errors import PipelineError
from resnet50_pipeline.golden.qlinear_conv import qlinear_conv_scalar
from resnet50_pipeline.profile28 import (
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
    sample_to_group,
)
from resnet50_pipeline.topology28 import Direction, TOPOLOGY28


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PADS = (1, 1, 1, 1)


def _fixture() -> dict[str, np.ndarray]:
    activation = (
        (np.arange(16 * 5, dtype=np.uint16) * 13 + 41) % 251
    ).astype(np.uint8).reshape(16, 5, 1, 1)
    weight = (
        (np.arange(5 * 5 * 2 * 2, dtype=np.int16) * 5) % 17 - 8
    ).astype(np.int8).reshape(5, 5, 2, 2)
    return {
        "activation": activation,
        "weight": weight,
        "bias": np.array([31, -27, 9, 43, -18], dtype=np.int32),
        "w_scale": np.array([0.017, 0.029, 0.041, 0.053, 0.067], dtype=np.float32),
        "w_zero_point": np.zeros(5, dtype=np.int8),
        "x_scale": np.array([0.03125], dtype=np.float32),
        "x_zero_point": np.array([117], dtype=np.uint8),
        "y_scale": np.array([0.073], dtype=np.float32),
        "y_zero_point": np.array([93], dtype=np.uint8),
    }


def _golden(values: dict[str, np.ndarray]):
    return qlinear_conv_scalar(
        values["activation"],
        values["weight"],
        bias=values["bias"],
        w_scale=values["w_scale"],
        w_zero_point=values["w_zero_point"],
        x_scale=values["x_scale"],
        x_zero_point=values["x_zero_point"],
        y_scale=values["y_scale"],
        y_zero_point=values["y_zero_point"],
        pads=PADS,
    )


def _bundle(profile_id: str):
    values = _fixture()
    golden = _golden(values)
    layout = QLinearConvPhysicalLayout(profile_id=profile_id)
    bundle = layout.forward(
        **values,
        accumulator=np.zeros_like(golden.accumulator),
        output=np.full_like(golden.output, values["y_zero_point"][0]),
        pads=PADS,
        tensor_ids={
            "A": "rtl28_a",
            "B": "rtl28_b",
            "bias": "rtl28_bias",
            "w_scale": "rtl28_ws",
            "w_zero_point": "rtl28_wz",
            "x_scale": "rtl28_xs",
            "x_zero_point": "rtl28_xz",
            "y_scale": "rtl28_ys",
            "y_zero_point": "rtl28_yz",
            "P": "rtl28_p",
            "D": "rtl28_d",
        },
    )
    return values, golden, layout, bundle


class NdpRtl28FunctionalAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = NdpRtl28FunctionalAdapter(
            PROJECT_ROOT / "NDPFuncModel",
            python_executable=Path(sys.executable),
            timeout_seconds=60,
        )

    def _assert_ring_address_provenance(self, result, bundle) -> None:
        target_geometry = bundle.plan.geometry
        shadow_geometry = result.address_map.shadow_geometry
        self.assertLess(shadow_geometry.total_bytes, 64 * 1024 * 1024)
        self.assertEqual(shadow_geometry.slice_count, 28)
        for plan in result.probe_plans:
            probe = plan.probe
            self.assertEqual(len(probe.ring_segment_ends), len(plan.source_owners))
            self.assertEqual(
                shadow_geometry.decode(probe.output_address).slice_id,
                plan.destination_owner,
            )
            self.assertEqual(
                result.address_map.to_target(probe.output_address),
                plan.target_output_address,
            )
            self.assertEqual(
                target_geometry.decode(plan.target_output_address).slice_id,
                plan.destination_owner,
            )
            start = 0
            for source_owner, end in zip(
                plan.source_owners, probe.ring_segment_ends, strict=True
            ):
                self.assertGreater(end, start)
                self.assertEqual((end - start) % 2, 0)
                for lane in range(start, end):
                    if probe.branch_mask[lane]:
                        continue
                    a_target = result.address_map.to_target(
                        probe.activation_addresses[lane]
                    )
                    b_target = result.address_map.to_target(
                        probe.weight_addresses[lane]
                    )
                    self.assertEqual(
                        target_geometry.decode(a_target).slice_id, source_owner
                    )
                    self.assertEqual(
                        target_geometry.decode(b_target).slice_id,
                        plan.destination_owner,
                    )
                start = end

    def _assert_functional_result(self, result, golden, values, layout) -> None:
        np.testing.assert_array_equal(result.accumulator, golden.accumulator)
        np.testing.assert_array_equal(result.output, golden.output)
        np.testing.assert_array_equal(result.inverse_output, golden.output)
        np.testing.assert_array_equal(
            layout.inverse_port(result.updated_bundle, "D"), golden.output
        )
        self.assertEqual(len(result.probe_plans), golden.accumulator.size)
        self.assertEqual(
            len(result.physical_probe.int8_dot_probes), golden.accumulator.size
        )
        self.assertTrue(all(item["hash_matches"] for item in result.physical_probe.regions))
        self.assertTrue(np.any(values["weight"] < 0))
        self.assertGreater(len(set(float(item) for item in values["w_scale"])), 1)
        self.assertNotEqual(float(values["x_scale"][0]), float(values["y_scale"][0]))
        for item in result.physical_probe.int8_dot_probes:
            self.assertEqual(item["output_before"], int(values["y_zero_point"][0]))
            self.assertEqual(item["output_after"], item["requantized_output"])
            self.assertEqual(
                item["execution_path"],
                [
                    "DRAM",
                    "input_buffer",
                    "SpecialPEA",
                    "ActivationUnit",
                    "output_buffer",
                    "DRAM",
                ],
            )

    def test_group4x7_exercises_all_seven_real_high_rings(self) -> None:
        values, golden, layout, bundle = _bundle(
            GROUP4X7_BATCH_CHANNEL28_PROFILE
        )
        self.assertEqual((bundle.plan.c_tile, bundle.plan.k_tile), (2, 2))
        self.assertTrue(
            all(
                bundle.region("A", ring.owners[3]).logical_count == 0
                for ring in TOPOLOGY28.high_rings
            )
        )
        result = self.adapter.run_qlinear_conv(layout, bundle)
        self._assert_functional_result(result, golden, values, layout)
        self._assert_ring_address_provenance(result, bundle)

        self.assertEqual({plan.ring_kind for plan in result.probe_plans}, {"HIGH"})
        self.assertEqual({plan.group_id for plan in result.probe_plans}, set(range(7)))
        for plan in result.probe_plans:
            n, k, _, _ = plan.probe.logical_output_coordinate
            group_id = sample_to_group(n).group_id
            ring = TOPOLOGY28.high_ring_for_group(group_id)
            destination = ring.owners[k // bundle.plan.k_tile]
            self.assertEqual(plan.group_id, group_id)
            self.assertEqual(plan.destination_owner, destination)
            self.assertEqual(
                plan.source_owners, ring.traverse(destination, Direction.PREV)
            )
            self.assertEqual(len(plan.source_owners), 4)
            self.assertEqual(len(plan.channel_ranges), 4)
        self.assertTrue(
            any(any(plan.probe.branch_mask) for plan in result.probe_plans)
        )

    def test_global_profile_exercises_explicit_low_ring_representative(self) -> None:
        values, golden, layout, bundle = _bundle(GLOBAL_RING28_PROFILE)
        self.assertEqual((bundle.plan.c_tile, bundle.plan.k_tile), (1, 1))
        result = self.adapter.run_qlinear_conv(layout, bundle)
        self._assert_functional_result(result, golden, values, layout)
        self._assert_ring_address_provenance(result, bundle)

        self.assertEqual({plan.ring_kind for plan in result.probe_plans}, {"LOW"})
        self.assertEqual({plan.group_id for plan in result.probe_plans}, {None})
        for plan in result.probe_plans:
            _, k, _, _ = plan.probe.logical_output_coordinate
            destination = TOPOLOGY28.low_ring.owners[k]
            self.assertEqual(plan.destination_owner, destination)
            self.assertEqual(
                plan.source_owners,
                TOPOLOGY28.low_ring.traverse(destination, Direction.PREV),
            )
            self.assertEqual(len(plan.source_owners), 28)
            self.assertEqual(len(plan.channel_ranges), 28)
            self.assertEqual(sum(count for _, count in plan.channel_ranges), 5)
        self.assertEqual(
            set(result.probe_plans[0].source_owners),
            set(TOPOLOGY28.low_ring.owners),
        )
        self.assertTrue(
            all(
                len(item["partial_accumulators"]) == 28
                and [state["last"] for state in item["ring_loop_states"]]
                == [0] * 27 + [1]
                for item in result.physical_probe.int8_dot_probes
            )
        )

    def test_nonzero_weight_zero_point_fails_closed(self) -> None:
        values = _fixture()
        values["w_zero_point"] = np.array([0, 0, -2, 0, 0], dtype=np.int8)
        golden = _golden(values)
        layout = QLinearConvPhysicalLayout()
        bundle = layout.forward(
            **values,
            accumulator=np.zeros_like(golden.accumulator),
            output=np.full_like(golden.output, values["y_zero_point"][0]),
            pads=PADS,
        )
        with self.assertRaisesRegex(PipelineError, "approved hardware rule"):
            self.adapter.build_probe_plans(layout, bundle)


if __name__ == "__main__":
    unittest.main()
