from __future__ import annotations

import unittest

from tools import validate_qlinearadd_node0007_config_preload_v14 as validator


class QLinearAddNode0007ConfigPreloadV14Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validator.validate_final_zip(write_report=False)

    def test_final_zip_rule_self_audit_passes(self) -> None:
        report = self.report
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["error_count"], 0)
        self.assertTrue(report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"])
        self.assertTrue(report["all_required_negative_controls_fail_closed"])
        self.assertEqual(report["status"], "PACKAGE_READY_NOT_RUN")

    def test_six_preloads_and_wrong_fields_fail_closed(self) -> None:
        controls = self.report["config_preload_negative_controls"]
        self.assertEqual(len(controls), 9)
        self.assertTrue(
            all(
                item["exit_code"] == 1 and item["failed_closed"]
                for item in controls.values()
            )
        )

    def test_frozen_semantics_were_not_recomputed(self) -> None:
        report = self.report
        self.assertFalse(report["numeric_analysis_repeated"])
        self.assertFalse(report["workload_analysis_repeated"])
        self.assertFalse(report["config_numeric_analysis_repeated"])
        self.assertTrue(report["consumed_reuse_assets"])
        self.assertEqual(
            report["functional_fix_scope"],
            "SCA_CONFIG_PRELOAD_MATERIALIZATION_ONLY",
        )


if __name__ == "__main__":
    unittest.main()
