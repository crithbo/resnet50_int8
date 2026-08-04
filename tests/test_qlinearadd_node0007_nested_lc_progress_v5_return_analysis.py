from __future__ import annotations

import unittest

from tools.analyze_qlinearadd_node0007_nested_lc_progress_v5_return import (
    analyze,
)


class QLinearAddNode0007ProgressV5ReturnAnalysisTests(unittest.TestCase):
    def test_compile_include_failure_is_bound_and_not_a_node_hang_result(self) -> None:
        report = analyze(
            __import__(
                "tools.analyze_qlinearadd_node0007_nested_lc_progress_v5_return",
                fromlist=["DEFAULT_RETURN"],
            ).DEFAULT_RETURN
        )
        self.assertTrue(report["valid_return_receipt"], report["receipt_errors"])
        self.assertTrue(report["return_input"]["sidecar_matches"])
        self.assertTrue(report["source_package_binding"]["matches"])
        self.assertTrue(report["return_integrity"]["crc_clean"])
        self.assertTrue(report["return_integrity"]["zip_exact_set"])
        self.assertTrue(report["return_integrity"]["allowlist_exact"])
        self.assertEqual(report["dynamic_result"]["compile_exit_status"], 2)
        self.assertFalse(report["dynamic_result"]["simulation_started"])
        self.assertFalse(report["dynamic_result"]["dynamic_attempt_counted"])
        self.assertEqual(
            report["progress_adjudication"]["status"],
            "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
        )
        self.assertEqual(
            report["first_divergence"]["code"],
            "OBSERVER_INCLUDE_SOURCE_NOT_FOUND_AT_COMPILE",
        )
        self.assertTrue(report["first_divergence"]["compile_macro_enabled"])
        self.assertEqual(
            report["first_divergence"]["missing_source"],
            "native_return_observer.svh",
        )
        self.assertTrue(
            report["first_divergence"]["exact_package_side_legal_fix"]
        )
        self.assertEqual(report["progress_evidence"]["qualified_window_count"], 0)
        self.assertFalse(report["numeric_analysis"]["repeated"])


if __name__ == "__main__":
    unittest.main()
