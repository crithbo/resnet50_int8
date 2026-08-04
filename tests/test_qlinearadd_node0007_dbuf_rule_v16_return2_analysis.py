from __future__ import annotations

import unittest
from pathlib import Path

from tools.analyze_qlinearadd_node0007_dbuf_rule_v16_return2 import analyze


RETURN = Path(
    "C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/"
    "msg/file/2026-08/r5_qadd_n7_dbuf_rule_v16_return (2).zip"
)


@unittest.skipUnless(RETURN.is_file(), "formal v16 return2 is not present")
class QLinearAddNode0007DBufRuleV16Return2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = analyze(RETURN)

    def test_integrity_and_source_binding(self) -> None:
        self.assertTrue(self.report["valid_internal_return_evidence"])
        self.assertTrue(self.report["integrity"]["return_exact_set"])
        self.assertTrue(self.report["integrity"]["manifest_allowlist_subset"])
        self.assertTrue(self.report["source_package"]["manifest_byte_equal"])

    def test_actual_stage3_hang_not_old_vcs_screenshot(self) -> None:
        progress = self.report["progress_adjudication"]
        self.assertTrue(progress["stage1_complete"])
        self.assertTrue(progress["stage2_complete"])
        self.assertEqual(progress["hang_stage"], "op_relocation_pad")
        self.assertGreaterEqual(progress["complete_flat_stall_windows"], 3)

    def test_canonical_reset_bug_and_formal_d_fail_closed(self) -> None:
        self.assertTrue(
            self.report["canonical_adjudication"][
                "cross_stage_active_cycle_reset_detected"
            ]
        )
        self.assertFalse(
            self.report["canonical_adjudication"]["execution_authoritative"]
        )
        self.assertEqual(self.report["formal_readback"]["missing"], 28)
        self.assertFalse(
            self.report["formal_readback"]["mismatch_zero_evaluable"]
        )


if __name__ == "__main__":
    unittest.main()
