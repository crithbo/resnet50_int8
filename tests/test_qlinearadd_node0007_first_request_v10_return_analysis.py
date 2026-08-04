from __future__ import annotations

import unittest

from tools import analyze_qlinearadd_node0007_first_request_chain_v10_return as analyzer


class QLinearAddNode0007FirstRequestV10ReturnTests(unittest.TestCase):
    def test_return_is_valid_diagnostic_failure(self) -> None:
        report = analyzer.analyze()
        self.assertEqual(report["errors"], [])
        self.assertEqual(
            report["status"],
            "VALID_DIAGNOSTIC_RETURN_FUNCTIONAL_RESULT_FAILED",
        )
        self.assertEqual(report["execution"]["compile_exit_status"], 0)
        self.assertEqual(report["execution"]["simulation_exit_status"], 125)
        self.assertEqual(report["execution"]["signal"], "INT")
        self.assertFalse(report["execution"]["natural_terminal"])
        self.assertEqual(report["formal_d"]["observed_count"], 0)
        self.assertEqual(report["formal_d"]["missing_count"], 28)

    def test_hang_and_observer_gap_are_separate(self) -> None:
        report = analyzer.analyze()
        self.assertGreaterEqual(report["progress"]["completed_stall_windows"], 16)
        self.assertEqual(
            report["progress"]["first_request_chain_sample_count"], 0
        )
        self.assertEqual(
            report["hang_root_cause"]["diagnostic_root_cause"],
            "DETERMINISTIC_OBSERVER_CLOCK_DOMAIN_BINDING_ERROR",
        )
        self.assertEqual(
            report["hang_root_cause"]["functional_root_cause"],
            "UNRESOLVED_INSIDE_EXEC_START_TO_FIRST_REQUEST",
        )
        self.assertFalse(report["stage_gates"]["E3"])


if __name__ == "__main__":
    unittest.main()
