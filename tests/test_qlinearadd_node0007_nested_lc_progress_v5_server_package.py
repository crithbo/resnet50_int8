from __future__ import annotations

import unittest

from tools.validate_qlinearadd_node0007_nested_lc_progress_v5_server_package import (
    validate,
)


class QLinearAddNode0007NestedLCProgressV5PackageTests(unittest.TestCase):
    def test_diagnostic_package_is_fail_closed_and_workload_frozen(self) -> None:
        report = validate()
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(
            report["warnings"],
            ["mutable read receipt drift: .agents/plan.md"],
        )
        self.assertEqual(report["claim"], "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX")
        self.assertFalse(report["functional_fix"])
        self.assertTrue(report["workload_equal_to_v4_except_install_namespace"])
        self.assertEqual(report["preloaded_runtime_readback_target_count"], 0)
        self.assertEqual(report["return_allowlist_count"], 45)
        self.assertTrue(report["progress_allowlist_exact_required"])
        self.assertFalse(report["numeric_analysis_repeated"])
        self.assertTrue(report["consumed_reuse_assets"])
        self.assertFalse(report["server_action"])


if __name__ == "__main__":
    unittest.main()
