from __future__ import annotations

import unittest

from tools import analyze_qlinearadd_node0007_obsrate_v13_return as analyzer


class QLinearAddNode0007ObsrateV13ReturnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = analyzer.analyze()

    def test_return_is_integrity_valid_but_formal_receipt_missing(self) -> None:
        report = self.report
        self.assertEqual(report["errors"], [])
        self.assertFalse(report["return_receipt"]["formal_receipt_valid"])
        self.assertFalse(report["return_receipt"]["adjacent_sidecar_exists"])
        self.assertTrue(
            report["return_receipt"]["diagnostic_evidence_consumable"]
        )
        self.assertTrue(report["zip_and_allowlist"]["return_manifest_exact_set"])
        self.assertEqual(
            report["zip_and_allowlist"]["required_missing_count"], 28
        )

    def test_long_run_is_a_proven_hang_not_unfinished_work(self) -> None:
        report = self.report
        self.assertEqual(report["execution"]["simulation_exit_status"], 125)
        self.assertGreater(report["execution"]["simulation_seconds"], 3300)
        chain = report["qualified_first_request_chain"]
        self.assertTrue(chain["shared_heartbeat_gate"])
        self.assertTrue(chain["clock_monotonically_alive"])
        self.assertTrue(chain["slice_start_seen"])
        self.assertTrue(chain["lc_enable_always_zero"])
        self.assertTrue(chain["all_qualified_downstream_counters_zero"])
        self.assertGreaterEqual(
            chain["flat_qualified_cycles"],
            7 * chain["stall_window_cycles"],
        )

    def test_sca_config_preload_omission_is_deterministic_root_cause(self) -> None:
        root_cause = self.report["hang_root_cause"]
        self.assertEqual(
            root_cause["classification"],
            "SCA_CONFIG_PRELOAD_MATERIALIZATION_OMISSION",
        )
        self.assertTrue(root_cause["all_six_config_preloads_missing"])
        self.assertTrue(root_cause["all_six_bitstream_files_packaged"])
        self.assertTrue(root_cause["all_six_execplan_load_config_commands_valid"])
        self.assertTrue(root_cause["rtl_enable_equation_present"])

    def test_formal_result_gate_fails_closed(self) -> None:
        formal = self.report["formal_d_and_result_gate"]
        self.assertEqual(formal["observed_count"], 0)
        self.assertEqual(formal["missing_count"], 28)
        self.assertFalse(formal["all_terms_true"])
        self.assertFalse(formal["E3"])
        self.assertFalse(formal["E4"])
        self.assertFalse(formal["E5"])


if __name__ == "__main__":
    unittest.main()
