from __future__ import annotations

import unittest

from tools.analyze_gap_node0071_v3_return import RETURN_ZIP, analyze


class GapNode0071V3ReturnAnalysisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = analyze(RETURN_ZIP)

    def test_return_fails_closed_at_timeout(self) -> None:
        report = self.report
        self.assertEqual(
            report["status"], "LONG_RUNNING_HANG_PENDING_ROOT_CAUSE"
        )
        self.assertEqual(report["execution"]["compile_exit_status"], 0)
        self.assertEqual(report["execution"]["simulation_exit_status"], 125)
        self.assertEqual(report["execution"]["runner_exit_status"], 124)
        self.assertFalse(report["execution"]["natural_terminal"])
        self.assertEqual(report["formal_readback"]["present_count"], 0)
        self.assertEqual(report["formal_readback"]["missing_count"], 48)
        self.assertFalse(
            report["formal_readback"]["zero_mismatch_evaluable"]
        )

    def test_progress_and_static_boundaries(self) -> None:
        report = self.report
        self.assertEqual(
            report["progress_adjudication"]["classification"],
            "INSUFFICIENT_TO_DISTINGUISH_PROGRESS_FROM_STALL",
        )
        self.assertEqual(
            report["hang_root_cause"], "UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT"
        )
        self.assertFalse(
            report["static_audit"]["rtl_completion_chain"][
                "deterministic_defect_proven"
            ]
        )
        self.assertEqual(
            report["static_audit"]["opcode_counts"],
            {
                "load_config": 8,
                "start_comp": 8,
                "barrier": 8,
                "clock_enable": 1,
            },
        )
        self.assertFalse(report["declarations"]["numeric_analysis_repeated"])


if __name__ == "__main__":
    unittest.main()
