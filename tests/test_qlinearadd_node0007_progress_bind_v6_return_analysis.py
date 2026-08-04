from __future__ import annotations

import unittest

from tools.analyze_qlinearadd_node0007_nested_lc_progress_bind_v6_return import (
    DEFAULT_RETURN,
    analyze,
)


class QLinearAddNode0007ProgressBindV6ReturnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = analyze(DEFAULT_RETURN)

    def test_formal_return_receipt_is_valid(self) -> None:
        self.assertTrue(self.report["valid_return_receipt"], self.report)
        self.assertEqual(self.report["analysis_errors"], [])
        self.assertTrue(self.report["return_integrity"]["allowlist_exact"])
        self.assertEqual(
            self.report["return_integrity"]["required_missing_count"], 28
        )

    def test_qualified_progress_proves_stall(self) -> None:
        progress = self.report["progress_evidence"]
        self.assertTrue(progress["qualified_event_source_verified"])
        self.assertEqual(progress["qualified_advancing_window_count"], 0)
        self.assertGreaterEqual(progress["complete_stall_window_count"], 22)
        self.assertTrue(progress["all_req_rdata_wdata_zero"])
        self.assertEqual(progress["completion_count"], 0)
        self.assertEqual(
            self.report["manual_defensive_canonical_adjudication"]["decision"],
            "LONG_RUNNING_HANG_AT_OP_A_DEQUANT_START_COMP_TO_FIRST_MSE_REQUEST",
        )

    def test_hang_is_proven_but_shared_lc0_root_cause_is_not(self) -> None:
        root = self.report["hang_root_cause"]
        self.assertFalse(root["functional_root_cause_proven"])
        self.assertEqual(
            root["shared_root_candidate"]["disposition"],
            "REFUTED_AS_A_SUFFICIENT_ZERO_REQUEST_ROOT_CAUSE",
        )
        self.assertTrue(
            root["candidate_refutation"][
                "initial_write_index_does_not_wait_for_ga_data"
            ]
        )
        self.assertTrue(root["not_fixed_by_longer_timeout"])
        self.assertEqual(
            self.report["package_release"]["status"], "NONE"
        )
        self.assertEqual(
            self.report["blocker_delta"]["v8_status"],
            (
                "QUARANTINED_NOT_RUN_SAME_FROZEN_WORKLOAD_"
                "HAS_PROVEN_DYNAMIC_HANG"
            ),
        )
        self.assertFalse(self.report["numeric_analysis"]["repeated"])


if __name__ == "__main__":
    unittest.main()
