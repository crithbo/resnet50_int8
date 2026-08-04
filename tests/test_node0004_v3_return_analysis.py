from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.node0004_v3_return_analysis import (
    analyze_node0004_v3_return,
)


ROOT = Path(__file__).resolve().parents[1]
RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_n4_hw_v3_obs_return.zip"
)


class Node0004V3ReturnAnalysisTest(unittest.TestCase):
    def test_rtl_interface_mismatch_is_first_divergence(self) -> None:
        if not RETURN.is_file():
            self.skipTest("user-supplied v3 return is not present")
        report = analyze_node0004_v3_return(ROOT, RETURN)
        self.assertEqual(
            report["first_divergence"]["classification"],
            "SERVER_RTL_INTERFACE_COMPILE_MISMATCH",
        )
        self.assertTrue(
            report["first_divergence"][
                "observer_include_proven_before_divergence"
            ]
        )
        self.assertFalse(report["execution"]["joint_gate_pass"])
        self.assertEqual(report["execution"]["missing_count"], 320)
        self.assertEqual(report["execution"]["formal_readback_produced_count"], 0)
        self.assertFalse(
            report["adjudication"]["package_side_legal_fix_available"]
        )
        self.assertEqual(report["package_release"], "NONE")
        self.assertFalse(report["claim_boundary"]["numeric_analysis_repeated"])


if __name__ == "__main__":
    unittest.main()
