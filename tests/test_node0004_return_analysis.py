from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.node0004_return_analysis import (
    analyze_node0004_return,
)


ROOT = Path(__file__).resolve().parents[1]
RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_node0004_hw_v1_return.zip"
)


class Node0004ReturnAnalysisTest(unittest.TestCase):
    def test_compile_failure_and_gate_fail_open_are_bound(self) -> None:
        if not RETURN.is_file():
            self.skipTest("user-supplied return ZIP is not present")
        report = analyze_node0004_return(ROOT, RETURN)
        self.assertEqual(
            report["first_divergence"]["classification"],
            "SERVER_SOURCE_MERGE_CONFLICT_COMPILE_FAILURE",
        )
        self.assertEqual(
            report["result_gate_adjudication"]["classification"],
            "PACKAGE_RESULT_GATE_FAIL_OPEN",
        )
        self.assertEqual(
            report["result_gate_adjudication"][
                "runtime_targets_preloaded_in_package"
            ],
            320,
        )
        self.assertFalse(
            report["result_gate_adjudication"][
                "returned_pass_is_dynamic_evidence"
            ]
        )
        self.assertEqual(
            report["execution_status"]["formal_dynamic_readback_count"], 0
        )


if __name__ == "__main__":
    unittest.main()
