from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.node0004_v3_return2_analysis import (
    analyze_node0004_v3_return2,
)


ROOT = Path(__file__).resolve().parents[1]
RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_n4_hw_v3_obs_return(2).zip"
)


class Node0004V3Return2AnalysisTest(unittest.TestCase):
    def test_stale_install_namespace_is_execution_first_divergence(self) -> None:
        if not RETURN.is_file():
            self.skipTest("user-supplied v3 return (2) is not present")
        report = analyze_node0004_v3_return2(ROOT, RETURN)
        self.assertFalse(
            report["external_sidecar_and_formal_receipt"][
                "formal_receipt_valid"
            ]
        )
        self.assertTrue(
            report["compile_and_elaboration"]["compile_succeeded"]
        )
        self.assertEqual(
            report["first_divergence"]["execution"]["classification"],
            "PACKAGE_SCA_INSTALL_NAMESPACE_MISMATCH",
        )
        self.assertEqual(
            report["first_divergence"]["execution"][
                "source_package_stale_inventory"
            ]["stale_path_leaf_count"],
            846,
        )
        self.assertEqual(report["formal_d_readback"]["missing_count"], 320)
        self.assertFalse(report["joint_result_gate"]["pass"])
        self.assertFalse(report["evidence_adjudication"]["E3"]["pass"])
        self.assertTrue(
            report["adjudication"]["package_side_legal_fix_available"]
        )
        self.assertEqual(
            report["package_release"]["status"], "PACKAGE_READY_NOT_RUN"
        )
        self.assertFalse(
            report["claim_boundary"]["numeric_analysis_repeated"]
        )


if __name__ == "__main__":
    unittest.main()
