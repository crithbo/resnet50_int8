from __future__ import annotations

import unittest

from tools.validate_qlinearadd_node0007_progress_canonical_v7 import (
    validate_final_zip,
)


class QLinearAddNode0007ProgressCanonicalV7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validate_final_zip()

    def test_final_zip_satisfies_canonical_and_default_progress_rules(
        self,
    ) -> None:
        self.assertTrue(self.report["valid"], self.report)
        self.assertEqual(
            self.report["status"], "CANONICAL_DECISION_RULE_VALIDATED"
        )
        self.assertTrue(
            self.report["default_progress_diagnostics_validated"]
        )
        self.assertTrue(
            self.report["four_way_observer_binding_preserved"]
        )

    def test_all_canonical_negative_controls_fail_closed(self) -> None:
        self.assertTrue(
            self.report["all_canonical_negative_controls_fail_closed"]
        )
        for name, receipt in self.report["negative_controls"].items():
            with self.subTest(name=name):
                self.assertTrue(receipt["failed_closed"])

    def test_v6_is_quarantined_and_workload_is_unchanged(self) -> None:
        self.assertTrue(self.report["source_v6_quarantined"])
        self.assertTrue(self.report["frozen_workload_equivalence"]["valid"])
        self.assertFalse(self.report["numeric_analysis_repeated"])
        self.assertFalse(self.report["workload_analysis_repeated"])
        self.assertFalse(self.report["server_action"])


if __name__ == "__main__":
    unittest.main()
