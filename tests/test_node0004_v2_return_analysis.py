from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.node0004_v2_return_analysis import (
    analyze_node0004_v2_return,
)


ROOT = Path(__file__).resolve().parents[1]
RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_node0004_hw_v2_failclosed_return.zip"
)


class Node0004V2ReturnAnalysisTest(unittest.TestCase):
    def test_missing_observer_is_first_divergence_and_gate_fails_closed(
        self,
    ) -> None:
        if not RETURN.is_file():
            self.skipTest("user-supplied v2 return is not present")
        report = analyze_node0004_v2_return(ROOT, RETURN)
        self.assertEqual(
            report["first_divergence"]["classification"],
            "PACKAGE_COMPILE_INCLUDE_PATH_MISSING",
        )
        self.assertEqual(
            report["fail_closed_adjudication"]["classification"],
            "V2_RESULT_GATE_FAIL_CLOSED_CONFIRMED",
        )
        self.assertEqual(
            report["fail_closed_adjudication"]["missing_count"], 320
        )
        self.assertTrue(
            report["repair_adjudication"]["package_side_legal_fix_confirmed"]
        )
        self.assertFalse(
            report["repair_adjudication"]["server_file_write_required"]
        )
        self.assertEqual(
            report["execution_status"]["formal_dynamic_readback_count"], 0
        )


if __name__ == "__main__":
    unittest.main()
