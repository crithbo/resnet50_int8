from __future__ import annotations

import unittest

from tools.audit_qlinearadd_node0007_v10_local_semantics import audit


class QLinearAddNode0007V10LocalSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = audit(write_report=False)

    def test_frozen_chain_has_no_deterministic_static_error(self) -> None:
        self.assertTrue(self.report["valid"], self.report["errors"])
        self.assertEqual(self.report["error_count"], 0)
        self.assertEqual(
            self.report["facts"]["adjudication"],
            "LOCAL_EXHAUSTIVE_REAUDIT_NO_DETERMINISTIC_ERROR_FOUND",
        )

    def test_numeric_and_workload_analysis_were_not_repeated(self) -> None:
        self.assertFalse(self.report["facts"]["numeric_analysis_repeated"])
        self.assertFalse(self.report["facts"]["workload_analysis_repeated"])
        self.assertTrue(self.report["facts"]["consumed_reuse_assets"])

    def test_first_mse0_match_retains_only_outer_keep_operand(self) -> None:
        self.assertEqual(
            self.report["facts"]["first_match_release"],
            {
                "port2_LC13_buffer": True,
                "port1_LC2_keep_le_2": True,
                "port0_PE3_keep_le_1": False,
            },
        )

    def test_semantic_mutations_fail_closed(self) -> None:
        for mutation in (
            "start_level_to_pulse",
            "lc2_src_to_zero",
            "mse_port_order_swap",
            "mse_keep_threshold0_zero",
            "fifo_reset_nonempty",
            "ag_initial_not_ready",
            "buffer_mask_flip",
            "terminal_nonzero",
        ):
            with self.subTest(mutation=mutation):
                report = audit(write_report=False, mutation=mutation)
                self.assertFalse(report["valid"], report)
                self.assertGreater(report["error_count"], 0)


if __name__ == "__main__":
    unittest.main()
