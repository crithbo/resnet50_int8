from __future__ import annotations

import unittest

from tools.analyze_qlinearadd_node0007_nested_lc_v4_return import (
    DEFAULT_RETURN,
    analyze,
)


class QLinearAddNestedLcV4ReturnAnalysisTest(unittest.TestCase):
    def test_interrupted_return_is_bound_and_progress_is_fail_closed(self) -> None:
        if not DEFAULT_RETURN.is_file():
            self.skipTest("user-provided v4 return is unavailable")
        report = analyze(DEFAULT_RETURN)
        self.assertTrue(report["valid_return_receipt"])
        self.assertTrue(report["source_package_binding"]["matches"])
        self.assertTrue(report["source_package_binding"]["manifest_three_way_equal"])
        self.assertTrue(report["return_integrity"]["crc_clean"])
        self.assertTrue(report["return_integrity"]["allowlist_exact"])
        self.assertTrue(report["preflight"]["valid"])
        dynamic = report["dynamic_result"]
        self.assertEqual(dynamic["compile_exit_status"], 0)
        self.assertEqual(dynamic["simulation_exit_status"], 125)
        self.assertTrue(dynamic["first_slice_started"])
        self.assertFalse(dynamic["natural_terminal"])
        self.assertEqual(dynamic["observed_readback_count"], 0)
        self.assertEqual(dynamic["missing_count"], 28)
        self.assertEqual(dynamic["mismatch_byte_count"], 0)
        self.assertFalse(dynamic["mismatch_is_evaluable"])
        progress = report["progress_adjudication"]
        self.assertEqual(
            progress["status"],
            "INSUFFICIENT_TO_DISTINGUISH_PROGRESS_FROM_STALL",
        )
        self.assertFalse(progress["two_monotonic_windows_proven"])
        self.assertFalse(progress["stalled_beyond_window_proven"])
        self.assertEqual(
            report["first_divergence"]["last_proven_boundary"],
            "op_a_dequant Start_Comp / slice start",
        )
        self.assertEqual(
            report["hang_root_cause"]["status"],
            "UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT",
        )
        self.assertEqual(
            report["workload_scale"]["total_request_count_with_multiplicity"],
            37_352_448,
        )
        self.assertTrue(report["static_execution_audit"]["valid"])
        self.assertFalse(report["numeric_analysis"]["repeated"])
        self.assertFalse(report["evidence_adjudication"]["E3"]["pass"])
        self.assertFalse(report["evidence_adjudication"]["E4"]["pass"])
        self.assertFalse(report["evidence_adjudication"]["E5"]["pass"])


if __name__ == "__main__":
    unittest.main()
