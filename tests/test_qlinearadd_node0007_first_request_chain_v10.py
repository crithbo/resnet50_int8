from __future__ import annotations

import unittest

from tools.validate_qlinearadd_node0007_first_request_chain_v10 import (
    validate_final_zip,
)


class QLinearAddNode0007FirstRequestChainV10Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validate_final_zip(write_report=False)

    def test_final_zip_current_rule_self_audit_passes(self) -> None:
        self.assertTrue(
            self.report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"], self.report
        )
        self.assertEqual(self.report["errors"], [])
        self.assertEqual(self.report["error_count"], 0)
        self.assertEqual(self.report["status"], "PACKAGE_READY_NOT_RUN")

    def test_frozen_workload_is_byte_equivalent(self) -> None:
        self.assertTrue(
            self.report["frozen_workload_equivalence"]["valid"]
        )
        self.assertFalse(self.report["numeric_analysis_repeated"])
        self.assertFalse(self.report["workload_analysis_repeated"])
        self.assertTrue(self.report["consumed_reuse_assets"])
        self.assertFalse(self.report["functional_fix"])

    def test_all_negative_controls_fail_closed(self) -> None:
        self.assertTrue(
            self.report["all_required_negative_controls_fail_closed"]
        )
        for family in (
            "four_way_and_chain_negative_controls",
            "canonical_negative_controls",
        ):
            for name, receipt in self.report[family].items():
                with self.subTest(family=family, name=name):
                    self.assertEqual(receipt["exit_code"], 1)
                    self.assertTrue(receipt["failed_closed"])

    def test_required_current_rule_ids_are_bound(self) -> None:
        self.assertIn(
            "CDA-QADD-FIRST-REQUEST-HANG-"
            "INTERNAL-READY-OBSERVABILITY-001",
            self.report["qlinearadd_rule_ids"],
        )
        self.assertIn(
            "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
            self.report["server_rule_ids"],
        )
        self.assertIn(
            "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
            self.report["server_rule_ids"],
        )


if __name__ == "__main__":
    unittest.main()
