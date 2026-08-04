from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.gap_node0071_return_analysis import (
    analyze_gap_node0071_return,
)


ROOT = Path(__file__).resolve().parents[1]
RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_node0071_gap_hw_v1_return.zip"
)


class GapNode0071ReturnAnalysisTest(unittest.TestCase):
    def test_missing_observer_is_first_divergence_and_gate_fails_closed(
        self,
    ) -> None:
        if not RETURN.is_file():
            self.skipTest("user-supplied node0071 return is not present")
        report = analyze_gap_node0071_return(ROOT, RETURN)
        self.assertEqual(
            report["first_divergence"]["classification"],
            "PACKAGE_COMPILE_INCLUDE_PATH_MISSING",
        )
        self.assertEqual(
            report["fail_closed_adjudication"]["classification"],
            "V1_RESULT_GATE_FAIL_CLOSED_CONFIRMED",
        )
        self.assertEqual(
            report["execution_status"]["compile_exit_status"], 2
        )
        self.assertEqual(
            report["execution_status"]["simulation_exit_status"], 125
        )
        self.assertEqual(
            report["execution_status"]["formal_dynamic_readback_count"], 0
        )
        self.assertEqual(
            report["fail_closed_adjudication"]["missing_count"], 48
        )
        self.assertTrue(
            report["repair_adjudication"]["package_side_legal_fix_confirmed"]
        )
        self.assertFalse(
            report["repair_adjudication"]["server_file_write_required"]
        )
        self.assertTrue(
            report["endpoint_impact"][
                "producer_storage_base_offset_coverage_preserved"
            ]
        )
        self.assertFalse(
            report["endpoint_impact"]["integrated_endpoint_closed"]
        )


if __name__ == "__main__":
    unittest.main()
