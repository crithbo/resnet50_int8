from __future__ import annotations

import json
import unittest
from unittest import mock
from pathlib import Path

from resnet50_pipeline.conv_node0004_composite_c1_predesign import (
    CONTRACT_PATH,
    validate_contract,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / CONTRACT_PATH


class ConvNode0004CompositeC1PredesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.report = validate_contract(CONTRACT, ROOT)

    def test_fresh_full_w3_accumulate_oracle(self) -> None:
        numeric = self.contract["numeric_oracle"]
        self.assertEqual(numeric["full_w3_mismatch_count"], 0)
        self.assertEqual(numeric["formal_element_count"], 3_211_264)
        self.assertTrue(numeric["correction_equals_bias"])

    def test_receipt_validator_does_not_repeat_numeric_analysis(self) -> None:
        refresh = self.contract["receipt_only_integration_refresh"]
        self.assertFalse(refresh["numeric_analysis_repeated"])
        with mock.patch(
            "resnet50_pipeline.conv_node0004_composite_c1_predesign."
            "_numeric_oracle",
            side_effect=AssertionError("numeric replay must not run"),
        ):
            report = validate_contract(CONTRACT, ROOT)
        self.assertFalse(report["numeric_analysis_repeated"])
        self.assertFalse(report["conclusion_changed"])

    def test_symbolic_address_roundtrip_boundaries(self) -> None:
        for tile_id, q, k in [
            (0, 0, 0),
            (0, 25_087, 63),
            (127, 0, 0),
            (127, 25_087, 63),
            (73, 12_345, 17),
        ]:
            lane = q % 8
            spatial = q // 8
            oh, ow = divmod(spatial, 56)
            n, group = divmod(tile_id, 8)
            oc = 8 * group + lane
            product_index = q * 64 + k
            self.assertGreaterEqual(product_index, 0)
            self.assertLess(product_index, 1_605_632)
            logical_product_index = (
                (((n * 64 + oc) * 56 + oh) * 56 + ow) * 64 + k
            )
            self.assertGreaterEqual(logical_product_index, 0)
            self.assertLess(logical_product_index, 205_520_896)

    def test_oc8_tile_capacity_and_full_layer_lower_bound(self) -> None:
        memory = self.contract["schedule"]["memory"]
        self.assertEqual(memory["tile_residency_bytes"], 13_046_304)
        self.assertLess(
            memory["tile_residency_bytes"],
            memory["per_slice_capacity_bytes"],
        )
        self.assertGreater(
            memory["full_product_scratch_bytes"],
            memory["aggregate_28_slice_capacity_bytes"],
        )
        self.assertEqual(
            self.contract["schedule"]["tile"]["waves_over_28_slices"],
            [28, 28, 28, 28, 16],
        )

    def test_tree_and_correction_schedule(self) -> None:
        tree = self.contract["schedule"]["tree"]
        self.assertEqual(tree["widths"], [64, 32, 16, 8, 4, 2, 1])
        self.assertEqual(tree["odd_tail_count"], 0)
        self.assertEqual(len(tree["stages"]), 6)
        self.assertTrue(
            all(stage["opcode_value"] == 14 for stage in tree["stages"])
        )
        self.assertEqual(
            self.contract["schedule"]["correction_leaf"]["node0004_formula"],
            "bias[oc]",
        )

    def test_first_physical_blocker_and_no_emission(self) -> None:
        self.assertEqual(
            self.report["first_physical_blocker"],
            "B_CONV_C1_SA_SCALAR_PRODUCT_MATERIALIZER_AND_TERMINAL",
        )
        self.assertFalse(self.report["complete_target"])
        self.assertEqual(self.report["package_release"], "NONE")
        self.assertTrue(
            all(
                value is False
                for key, value in self.contract["emission"].items()
                if key.endswith("_generated")
            )
        )


if __name__ == "__main__":
    unittest.main()
