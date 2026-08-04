from __future__ import annotations

import unittest

from tools.build_gap_repair_test_package import (
    DEFAULT_OUTPUT_REL,
    INSTALL_NAME,
    ROOT,
    _run_script,
    validate_package,
)


class BuildGapRepairTestPackageTests(unittest.TestCase):
    def test_checked_v9_package_is_exact_and_repair_scoped(self) -> None:
        report = validate_package(ROOT, ROOT / DEFAULT_OUTPUT_REL)
        self.assertEqual(
            report["status"], "server_repair_test_package_validated"
        )
        self.assertEqual(report["functional_rtl_file_count"], 2)
        self.assertEqual(
            report["expected_return_zip"], f"{INSTALL_NAME}_return.zip"
        )
        self.assertTrue(report["zip_audit"]["exact_file_set"])

    def test_run_script_installs_and_restores_with_identity(self) -> None:
        script = _run_script(INSTALL_NAME)
        self.assertIn("--action install", script)
        self.assertIn("--action restore", script)
        self.assertIn("rtl_installed=1", script)
        self.assertIn("trap restore_rtl_on_exit EXIT", script)
        self.assertIn("server_identity_post_restore.json", script)
        self.assertIn("rtl_patch_restore_report.json", script)
        self.assertIn("server_identity_post_run.json", script)

    def test_run_script_uses_new_config_and_no_waveforms(self) -> None:
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
