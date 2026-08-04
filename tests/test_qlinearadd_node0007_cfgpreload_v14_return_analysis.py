from __future__ import annotations

import unittest

from tools import analyze_qlinearadd_node0007_cfgpreload_v14_return as analyzer


class QLinearAddNode0007CfgPreloadV14ReturnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = analyzer.analyze()

    def test_internal_receipt_is_valid_without_adjacent_sidecar(self) -> None:
        receipt = self.report["return_receipt"]
        self.assertFalse(receipt["adjacent_sidecar_exists"])
        self.assertTrue(receipt["formal_internal_receipt_valid"])
        self.assertEqual(self.report["errors"], [])

    def test_two_dequant_stages_finish_then_relocation_hangs(self) -> None:
        execution = self.report["execution"]
        self.assertEqual(execution["comp_finish_count"], 2)
        self.assertEqual(execution["exec_start_count"], 3)
        self.assertEqual(execution["third_exec_gconfig"], 154)
        progress = self.report["progress_adjudication"]
        self.assertTrue(progress["qualified_counters_flat"])
        self.assertGreater(progress["complete_stall_windows"], 38)

    def test_dynamic_boundary_matches_d_buffer_undersupply(self) -> None:
        cause = self.report["hang_root_cause"]
        self.assertEqual(
            cause["classification"],
            "QADD_D_BUFFER_TRANSACTION_SUPPLY_UNDERSUPPLY",
        )
        for record in cause["v14_supply_records"].values():
            self.assertEqual(record["transaction_bytes"], 32)
            self.assertEqual(record["supplied_bytes"], 16)
            self.assertFalse(record["conservation_valid"])

    def test_formal_d_fails_closed(self) -> None:
        formal = self.report["formal_d_and_result_gate"]
        self.assertEqual(formal["observed_count"], 0)
        self.assertEqual(formal["missing_count"], 28)
        self.assertFalse(formal["all_terms_true"])
        self.assertFalse(formal["E3"])


if __name__ == "__main__":
    unittest.main()
