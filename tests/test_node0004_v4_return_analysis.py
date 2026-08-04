from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.node0004_v4_return_analysis import (
    analyze_node0004_v4_return,
)


ROOT = Path(__file__).resolve().parents[1]
RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_n4_hw_v4_rootbind_return.zip"
)


class Node0004V4ReturnAnalysisTest(unittest.TestCase):
    def test_timeout_with_disabled_observer_is_fail_closed(self) -> None:
        if not RETURN.is_file():
            self.skipTest("user-supplied v4 return is not present")
        report = analyze_node0004_v4_return(ROOT, RETURN)
        self.assertTrue(
            report["return_identity"]["sidecar"]["formal_receipt_valid"]
        )
        self.assertTrue(report["compile_and_elaboration"]["compile_succeeded"])
        self.assertTrue(report["simulation"]["all_86_matrices_loaded"])
        self.assertEqual(report["simulation"]["cannot_open_count"], 0)
        self.assertEqual(
            report["first_divergence"]["first_observed_bad"][
                "classification"
            ],
            "EXTERNAL_RUNNER_TIMEOUT",
        )
        self.assertEqual(
            report["first_divergence"]["first_evidence_gap"][
                "classification"
            ],
            "PACKAGE_OBSERVER_RUNTIME_BINDING_AND_RETURN_MISSING",
        )
        self.assertFalse(
            report["first_divergence"]["rtl_deadlock_claim_allowed"]
        )
        self.assertEqual(report["formal_d_readback"]["missing_count"], 320)
        self.assertFalse(report["joint_result_gate"]["pass"])
        self.assertEqual(
            report["package_release"]["status"], "PACKAGE_READY_NOT_RUN"
        )
        self.assertFalse(
            report["claim_boundary"]["numeric_analysis_repeated"]
        )


if __name__ == "__main__":
    unittest.main()
