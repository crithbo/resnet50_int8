from __future__ import annotations

import unittest

from tools.validate_qlinearadd_node0007_progress_canonical_v8 import (
    validate_final_zip,
)


class QLinearAddNode0007ProgressCanonicalV8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validate_final_zip()

    def test_final_zip_rule_self_audit_passes(self) -> None:
        self.assertTrue(
            self.report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"], self.report
        )
        self.assertEqual(self.report["errors"], [])
        self.assertEqual(self.report["error_count"], 0)
        self.assertEqual(
            self.report["status"], "CANONICAL_DECISION_RULE_VALIDATED"
        )

    def test_all_negative_controls_fail_closed(self) -> None:
        self.assertTrue(
            self.report["all_required_negative_controls_fail_closed"]
        )
        for family in (
            "four_way_negative_controls",
            "canonical_negative_controls",
        ):
            for name, receipt in self.report[family].items():
                with self.subTest(family=family, name=name):
                    self.assertTrue(receipt["failed_closed"])

    def test_receipt_only_and_frozen_workload(self) -> None:
        self.assertTrue(self.report["frozen_workload_equivalence"]["valid"])
        self.assertFalse(self.report["numeric_analysis_repeated"])
        self.assertFalse(self.report["workload_analysis_repeated"])
        self.assertFalse(self.report["server_action"])


if __name__ == "__main__":
    unittest.main()
