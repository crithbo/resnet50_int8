from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from resnet50_pipeline.conv16_layout import ConvBatch16PhysicalLayout
from resnet50_pipeline.conv16_ring_layout import ConvRing16PhysicalLayout
from resnet50_pipeline.conv_coverage import (
    conv_shape_families,
    deterministic_layout_case,
    validate_family_plans,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_GRAPH = PROJECT_ROOT / "artifacts" / "w3" / "model_graph.json"


class ConvCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(MODEL_GRAPH.read_text(encoding="utf-8"))
        cls.families = conv_shape_families(cls.catalog, batch_size=16)

    def test_formal_53_conv_nodes_group_into_20_stable_families(self) -> None:
        self.assertEqual(len(self.families), 20)
        self.assertEqual(sum(len(family.node_ids) for family in self.families), 53)
        self.assertEqual(len({family.family_id for family in self.families}), 20)
        repeated = conv_shape_families(self.catalog, batch_size=16)
        self.assertEqual(self.families, repeated)
        self.assertEqual({family.group for family in self.families}, {1})
        self.assertEqual(
            {(family.weight_shape[2], family.weight_shape[3]) for family in self.families},
            {(1, 1), (3, 3), (7, 7)},
        )
        self.assertEqual({family.strides for family in self.families}, {(1, 1), (2, 2)})

    def test_all_family_plans_fit_and_cover_each_owner_exactly_once(self) -> None:
        batch = ConvBatch16PhysicalLayout()
        ring = ConvRing16PhysicalLayout()
        reports = [validate_family_plans(family, batch, ring) for family in self.families]
        self.assertTrue(
            all(report["batch"]["capacity_margin_bytes"] > 0 for report in reports)
        )
        self.assertTrue(
            all(report["ring"]["capacity_margin_bytes"] > 0 for report in reports)
        )
        self.assertTrue(
            all(report["ring"]["all_owner_ranges_exact"] for report in reports)
        )
        self.assertTrue(
            all(report["ring"]["all_ring_orders_are_permutations"] for report in reports)
        )

    def test_deterministic_family_pattern_round_trips_through_both_profiles(self) -> None:
        family = min(
            self.families,
            key=lambda item: np.prod(item.weight_shape)
            + np.prod(item.output_shape[1:]),
        )
        values = deterministic_layout_case(family, batch_size=1)
        batch_layout = ConvBatch16PhysicalLayout()
        ring_layout = ConvRing16PhysicalLayout()
        batch = batch_layout.forward(**values)
        ring = ring_layout.forward(**values)
        expected = {
            "A": values["activation"],
            "B": values["weight"],
            "bias": values["bias"],
            "w_scale": values["w_scale"],
            "w_zero_point": values["w_zero_point"],
            "x_scale": values["x_scale"],
            "x_zero_point": values["x_zero_point"],
            "y_scale": values["y_scale"],
            "y_zero_point": values["y_zero_point"],
            "multiplier": values["x_scale"][0]
            * values["w_scale"]
            / values["y_scale"][0],
            "P": values["accumulator"],
            "D": values["output"],
        }
        for port, logical in expected.items():
            batch_value = batch_layout.inverse_port(batch, port)
            ring_value = ring_layout.inverse_port(ring, port)
            np.testing.assert_array_equal(batch_value, logical)
            np.testing.assert_array_equal(ring_value, logical)
            np.testing.assert_array_equal(batch_value, ring_value)


if __name__ == "__main__":
    unittest.main()
