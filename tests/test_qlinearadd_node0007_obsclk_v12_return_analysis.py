from __future__ import annotations

import unittest

from tools import analyze_qlinearadd_node0007_obsclk_v12_return as analyzer


class QLinearAddNode0007ObsclkV12ReturnTests(unittest.TestCase):
    def test_return_is_nonauthoritative_and_dynamic_failure(self) -> None:
        report = analyzer.analyze()
        self.assertEqual(report["errors"], [])
        self.assertFalse(report["return_receipt"]["formal_receipt_valid"])
        self.assertFalse(report["return_receipt"]["adjacent_sidecar_exists"])
        self.assertFalse(report["return_receipt"]["return_manifest_present"])
        self.assertEqual(report["execution"]["compile_exit_status"], 0)
        self.assertEqual(report["execution"]["simulation_exit_status"], 125)
        self.assertEqual(report["formal_d"]["observed_count"], 0)
        self.assertEqual(report["formal_d"]["missing_count"], 28)

    def test_unbounded_clock_emitter_is_proven(self) -> None:
        report = analyzer.analyze()
        self.assertTrue(report["package_defect"]["static_source_proof"])
        self.assertTrue(
            report["package_defect"]["dynamic_arbitrary_active_cycle_proof"]
        )
        self.assertTrue(report["observer"]["clk_sg_proven_alive_after_exec_start"])
        self.assertEqual(
            report["observer"]["first_request_chain_samples_returned"], 0
        )
        self.assertGreater(
            report["package_defect"]["minimum_budget_multiple"], 100
        )


if __name__ == "__main__":
    unittest.main()
