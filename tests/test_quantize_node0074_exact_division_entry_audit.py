from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.quantize_node0074_exact_division_entry_audit import (
    validate_contract,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "contracts/operator_config/quantize_node0074_exact_division_entry_audit_v1.json"
)


class QuantizeNode0074ExactDivisionEntryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validate_contract(CONTRACT, ROOT)

    def test_direct_exact_division_entry_is_absent(self) -> None:
        audit = self.report["native_entry_audit"]
        self.assertEqual(audit["direct_binary32_division"], "ABSENT")
        self.assertFalse(audit["complete_equivalent_route"])

    def test_same_scale_reciprocal_mul_has_uint8_visible_counterexample(self) -> None:
        counterexample = self.report[
            "same_scale_sequential_reciprocal_counterexample"
        ]
        self.assertEqual(counterexample["divide_then_rne_uint8"], 159)
        self.assertEqual(counterexample["reciprocal_mul_then_rne_uint8"], 158)
        self.assertEqual(counterexample["separation"], 1)

    def test_frozen_w3_coincidence_does_not_authorize_target(self) -> None:
        observation = self.report["frozen_w3_route_observation"]
        self.assertEqual(
            observation[
                "exact_division_vs_sequential_reciprocal_mul_scaled_bit_mismatches"
            ],
            720,
        )
        self.assertEqual(
            observation[
                "exact_division_vs_sequential_reciprocal_mul_final_uint8_mismatches"
            ],
            0,
        )
        self.assertTrue(observation["exact_division_matches_formal_output"])
        self.assertFalse(observation["authorizes_target"])

    def test_endpoint_owned_fields_remain_null(self) -> None:
        endpoint = self.report["endpoint_binding"]
        self.assertTrue(endpoint["all_owned_fields_null"])
        self.assertTrue(
            all(value is None for value in endpoint["node0074_owned_fields"].values())
        )
        self.assertFalse(endpoint["provisional_address_allowed"])
        self.assertFalse(endpoint["target_endpoint_claimed"])
        canonical = self.report["canonical_endpoint_integration"]
        self.assertEqual(
            canonical["dequant_owner_section_content_sha256"],
            "e372f7b0fa434845a8199830c3c46a9467fc71d5687fa103750a86408191b371",
        )
        self.assertTrue(canonical["quantize_only_update"])
        self.assertTrue(canonical["consumer_owned_fields_all_null"])
        self.assertFalse(canonical["integrated_endpoint_closed"])

    def test_no_accepted_retest_or_outputs(self) -> None:
        accounting = self.report["analysis_accounting"]
        self.assertFalse(accounting["accepted_numeric_analysis_repeated"])
        self.assertFalse(accounting["node0004_analysis_repeated"])
        self.assertFalse(accounting["accepted_primitive_retested"])
        self.assertTrue(accounting["reuse_assets_consumed"])
        self.assertTrue(
            all(item["retested"] is False for item in self.report["reused_evidence"])
        )
        self.assertTrue(
            all(value is False for value in self.report["generated_outputs"].values())
        )
        self.assertEqual(self.report["package_release"], "NONE")


if __name__ == "__main__":
    unittest.main()
