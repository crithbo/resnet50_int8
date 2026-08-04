from __future__ import annotations

import unittest

from tools.build_gap_stock_rtl_decision_test_package import (
    DEFAULT_OUTPUT_REL,
    INSTALL_NAME,
    ROOT,
    _run_script,
    validate_package,
)


class BuildGapStockRtlDecisionPackageTests(unittest.TestCase):
    def test_checked_v10_package_is_exact_and_contains_no_functional_rtl(
        self,
    ) -> None:
        report = validate_package(ROOT, ROOT / DEFAULT_OUTPUT_REL)
        self.assertEqual(
            report["status"],
            "server_stock_rtl_decision_test_package_validated",
        )
        self.assertEqual(report["functional_rtl_file_count"], 0)
        self.assertEqual(
            report["expected_return_zip"], f"{INSTALL_NAME}_return.zip"
        )
        self.assertTrue(report["zip_audit"]["exact_file_set"])

    def test_run_script_never_installs_or_restores_functional_rtl(self) -> None:
        script = _run_script(INSTALL_NAME)
        self.assertNotIn("install_gap_ga_rtl_repair.py", script)
        self.assertNotIn("--action install", script)
        self.assertNotIn("--action restore", script)
        self.assertNotIn("rtl_patch", script)
        self.assertIn("verify_gap_stock_rtl_identity.py", script)
        self.assertIn("stock_rtl_identity_receipt.json", script)
        self.assertIn("server_identity_post_run.json", script)

    def test_run_script_uses_corrected_config_and_no_waveforms(self) -> None:
        script = _run_script(INSTALL_NAME)
        self.assertIn(
            f"+SCA_CFG=install/cfg_pkg/{INSTALL_NAME}/sca_cfg.json", script
        )
        self.assertIn(
            f"+SCA_CFG_D=install/cfg_pkg/{INSTALL_NAME}/sca_cfg_D.json", script
        )
        self.assertIn("DUMP_VCD=0", script)
        self.assertIn("DUMP_FSDB=0", script)
        self.assertIn("TB_DUMP_FSDB=0", script)
        self.assertNotIn("DUMP_FSDB=1", script)


if __name__ == "__main__":
    unittest.main()
