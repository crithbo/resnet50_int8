from __future__ import annotations

import unittest

from tools.validate_qlinearadd_node0007_nested_lc_progress_bind_v6_server_package import (
    validate,
)


class QLinearAddNode0007ProgressBindV6PackageTests(unittest.TestCase):
    def test_package_local_observer_binding_is_exact_and_fail_closed(self) -> None:
        report = validate()
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["claim"], "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX")
        self.assertFalse(report["functional_fix"])
        self.assertEqual(report["server_rtl_entries"], 0)
        self.assertEqual(report["server_tb_or_observer_entries"], 1)
        self.assertTrue(report["observer_package_local_include_bound"])
        self.assertTrue(report["observer_enable_macro_bound"])
        self.assertEqual(report["return_allowlist_count"], 46)
        self.assertTrue(report["progress_allowlist_exact_required"])
        self.assertTrue(report["workload_equal_to_v5_except_install_namespace"])
        self.assertEqual(report["preloaded_runtime_readback_target_count"], 0)
        self.assertFalse(report["numeric_analysis_repeated"])
        self.assertTrue(report["consumed_reuse_assets"])
        self.assertFalse(report["server_action"])


if __name__ == "__main__":
    unittest.main()
