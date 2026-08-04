from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.requant_family_classification import (
    CONTRACT_PATH,
    RECEIPT_PATH,
    REPORT_PATH,
    RequantFamilyClassificationError,
    build_requant_family_classification,
    validate_requant_family_classification,
    validate_requant_family_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class RequantFamilyClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = build_requant_family_classification(ROOT)

    def test_all_54_requests_have_exact_standard_w3_replay(self) -> None:
        summary = self.value["summary"]
        self.assertEqual(summary["requant_stage_count"], 54)
        self.assertEqual(
            summary["standard_w3_golden_exact_stage_count"], 54
        )
        self.assertEqual(
            summary["standard_w3_golden_mismatch_stage_count"], 0
        )
        self.assertEqual(
            summary["positive_finite_multiplier_stage_count"], 54
        )
        self.assertTrue(
            all(
                record["w3"][
                    "standard_round_then_add_zp_mismatch_count"
                ]
                == 0
                for record in self.value["records"]
            )
        )

    def test_current_guard_contract_has_an_exact_33_21_partition(
        self,
    ) -> None:
        summary = self.value["summary"]
        self.assertEqual(summary["zero_output_zero_point_stage_count"], 33)
        self.assertEqual(
            summary["nonzero_output_zero_point_stage_count"], 21
        )
        self.assertEqual(
            summary["current_guard_numeric_compatible_stage_count"], 33
        )
        self.assertEqual(
            summary["current_guard_contradicted_stage_count"], 21
        )
        compatible = [
            record
            for record in self.value["records"]
            if record["qparams"]["y_zero_point"] == 0
        ]
        contradicted = [
            record
            for record in self.value["records"]
            if record["qparams"]["y_zero_point"] != 0
        ]
        self.assertTrue(
            all(
                record["w3"]["node0001_guard_recipe_mismatch_count"]
                == 0
                for record in compatible
            )
        )
        self.assertTrue(
            all(
                record["w3"]["node0001_guard_recipe_mismatch_count"]
                > 0
                for record in contradicted
            )
        )

    def test_odd_zero_point_tie_parity_counterexample_is_preserved(
        self,
    ) -> None:
        summary = self.value["summary"]
        self.assertEqual(
            summary["magic_rounding_counterexample_stage_ids"],
            ["r5:hwop-0014-01"],
        )
        node0014 = next(
            record
            for record in self.value["records"]
            if record["request_id"] == "r5:hwop-0014-01"
        )
        self.assertEqual(
            node0014["w3"]["authorized_magic_mismatch_count"], 32
        )
        self.assertIn(
            "B_REQUANT_MAGIC_ZP_TIE_PARITY", node0014["blockers"]
        )

    def test_only_node0001_is_currently_emission_authorized(self) -> None:
        summary = self.value["summary"]
        self.assertEqual(
            summary["full_materialized_local_e2_stage_count"], 1
        )
        self.assertEqual(
            summary[
                "numeric_compatible_physical_e2_pending_stage_count"
            ],
            32,
        )
        self.assertEqual(
            summary["candidate_json_emission_allowed_count"], 1
        )
        emitted = [
            record["request_id"]
            for record in self.value["records"]
            if record["candidate_json_emission_allowed"]
        ]
        self.assertEqual(emitted, ["r5:hwop-0001-01"])
        self.assertFalse(self.value["candidate_release"])
        self.assertFalse(self.value["formal_target_instance_allowed"])

    def test_node0075_2d_layout_is_not_assumed_from_hwc8(self) -> None:
        node0075 = next(
            record
            for record in self.value["records"]
            if record["request_id"] == "r5:hwop-0075-01"
        )
        self.assertEqual(node0075["logical_shape"], [16, 1000])
        self.assertEqual(node0075["channel_tail_mod8"], 0)
        self.assertIn(
            "B_REQUANT_MATMUL_2D_LAYOUT", node0075["blockers"]
        )

    def test_checked_assets_and_tamper_fail_closed(self) -> None:
        report = json.loads(
            (ROOT / REPORT_PATH).read_text(encoding="utf-8")
        )
        contract = json.loads(
            (ROOT / CONTRACT_PATH).read_text(encoding="utf-8")
        )
        validate_requant_family_classification(report, ROOT)
        validate_requant_family_contract(contract, ROOT)
        tampered = copy.deepcopy(report)
        tampered["summary"]["current_guard_contradicted_stage_count"] = 20
        with self.assertRaises(RequantFamilyClassificationError):
            validate_requant_family_classification(tampered, ROOT)

    def test_nonsemantic_active_plan_is_not_a_numeric_input(self) -> None:
        receipt = json.loads(
            (ROOT / RECEIPT_PATH).read_text(encoding="utf-8")
        )
        labels = {
            item["label"]
            for item in receipt["read_receipt"]
        }
        self.assertNotIn("active_plan", labels)


if __name__ == "__main__":
    unittest.main()
