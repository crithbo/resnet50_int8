from __future__ import annotations

import copy
import unittest
from pathlib import Path

from resnet50_pipeline.int8_sa_rtl_repair_acceptance import (
    INT32_MAX,
    INT32_MIN,
    build_int8_sa_rtl_repair_acceptance,
    compare_three_models,
    proposal_signed18_chunk,
    validate_active_rule_receipts,
)


class Int8SaRtlRepairAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.report = build_int8_sa_rtl_repair_acceptance(cls.root)

    def test_three_model_columns_keep_stock_as_negative_control(self) -> None:
        comparison = compare_three_models([1, 1, 1, 1], [1, 1, 1, 1])
        self.assertEqual(comparison["target"]["s32"], 4)
        self.assertEqual(comparison["models"]["stock_four_lane"]["s32"], 6)
        self.assertEqual(comparison["models"]["proposal_signed18"]["s32"], 4)
        self.assertEqual(
            comparison["models"]["serialized_one_product"]["s32"], 4
        )

    def test_signed18_covers_full_legal_dot4_range(self) -> None:
        positive = proposal_signed18_chunk([127] * 4, [255] * 4)
        negative = proposal_signed18_chunk([-128] * 4, [255] * 4)
        self.assertEqual(positive["dot4_s18"], 129540)
        self.assertEqual(negative["dot4_s18"], -130560)

    def test_psum32_accumulation_wraps_modulo_2_to_32(self) -> None:
        positive = proposal_signed18_chunk([1], [1], INT32_MAX)
        negative = proposal_signed18_chunk([-1], [1], INT32_MIN)
        self.assertEqual(positive["result_s32"], INT32_MIN)
        self.assertEqual(negative["result_s32"], INT32_MAX)
        self.assertEqual(positive["result_bits"], "0x80000000")
        self.assertEqual(negative["result_bits"], "0x7fffffff")

    def test_k_tails_bias_and_nonzero_zero_point(self) -> None:
        for length in (1, 2, 3, 5, 6, 7):
            weights = [(-1) ** index * (index + 1) for index in range(length)]
            activations = [114 + index for index in range(length)]
            comparison = compare_three_models(
                weights,
                activations,
                x_zero_point=114,
                bias=-12345,
            )
            self.assertTrue(
                comparison["models"]["proposal_signed18"]["matches_target"]
            )
            self.assertTrue(
                comparison["models"]["serialized_one_product"]["matches_target"]
            )

    def test_exhaustive_and_legal_boundary_proofs_pass(self) -> None:
        exhaustive = self.report["small_domain_exhaustive"]
        boundary = self.report["legal_boundary_proof"]
        self.assertEqual(exhaustive["status"], "PASS")
        self.assertEqual(exhaustive["proposal_mismatch_count"], 0)
        self.assertEqual(exhaustive["serialized_mismatch_count"], 0)
        self.assertGreater(exhaustive["stock_mismatch_count"], 0)
        self.assertEqual(
            boundary["single_product_full_domain"]["case_count"], 256 * 256
        )
        self.assertEqual(
            boundary["four_lane_corner_cross_product"][
                "observed_dot4_s18_range"
            ],
            [-130560, 129540],
        )

    def test_contract_remains_fail_closed_and_local_only(self) -> None:
        self.assertFalse(self.report["candidate_release"])
        self.assertFalse(self.report["server_package_allowed"])
        self.assertFalse(self.report["functional_rtl_modified"])
        self.assertFalse(self.report["target_json_generated"])
        self.assertIsNone(
            self.report["future_rtl_identity_input_interface"]["current_binding"]
        )

    def test_active_rule_is_current_match_fail_closed(self) -> None:
        result = validate_active_rule_receipts(self.root, self.report)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(
            result["active_rule_results"][0]["current_matches"]
        )

        stale = copy.deepcopy(self.report)
        stale["receipt_policy"]["active_rule_current_match"][0][
            "sha256"
        ] = "0" * 64
        with self.assertRaises(ValueError):
            validate_active_rule_receipts(self.root, stale)

    def test_plan_receipt_is_mutable_historical_provenance(self) -> None:
        historical = copy.deepcopy(self.report)
        historical["receipt_policy"]["mutable_provenance"][0][
            "sha256_at_generation"
        ] = "0" * 64
        result = validate_active_rule_receipts(self.root, historical)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(
            result["mutable_provenance_results"][0]["current_matches"]
        )


if __name__ == "__main__":
    unittest.main()
