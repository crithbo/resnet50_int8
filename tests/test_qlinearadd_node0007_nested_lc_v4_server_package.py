from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.qlinearadd_node0007_server_runtime import preflight
from tools.validate_qlinearadd_node0007_nested_lc_v4_server_package import (
    audit,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_qadd_n7_nested_lc_v4"
)


class QLinearAddNode0007NestedLCV4ServerPackageTest(unittest.TestCase):
    def test_package_boundary_when_materialized(self) -> None:
        if not PACKAGE.is_dir():
            self.skipTest("fresh nested-LC package is not built")
        report = preflight(PACKAGE)
        self.assertTrue(report["valid"])
        self.assertEqual(report["readback_count"], 28)
        self.assertTrue(report["formal_readback_targets_absent"])
        manifest = json.loads(
            (PACKAGE / "TEST_PACKAGE_MANIFEST.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["install_name"], PACKAGE.name)
        self.assertEqual(manifest["server_rtl_entries"], 0)
        self.assertFalse(manifest["functional_rtl_modified"])
        self.assertFalse(manifest["candidate_release"])
        self.assertFalse(manifest["numeric_analysis_repeated"])

    def test_zip_exact_set_when_materialized(self) -> None:
        if not PACKAGE.with_suffix(".zip").is_file():
            self.skipTest("fresh nested-LC package ZIP is not built")
        report = audit()
        self.assertTrue(report["valid"], report["errors"])
        self.assertTrue(report["zip_crc_clean"])
        self.assertTrue(report["zip_package_exact_set"])
        self.assertEqual(report["preloaded_runtime_d_target_count"], 0)
        self.assertEqual(report["rtl_or_tb_entry_count"], 0)
        self.assertTrue(report["contract_cycle_break"]["valid"])


if __name__ == "__main__":
    unittest.main()
