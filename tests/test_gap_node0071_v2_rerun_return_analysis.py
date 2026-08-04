from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.gap_node0071_v2_rerun_return_analysis import (
    GapNode0071V2RerunReturnAnalysisError,
    analyze_gap_node0071_v2_rerun_return,
)


ROOT = Path(__file__).resolve().parents[1]
RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_n71_gap_v2_obs_return(1).zip"
)


class GapNode0071V2RerunReturnAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = analyze_gap_node0071_v2_rerun_return(
            ROOT, RETURN
        )

    def test_filename_suffix_does_not_create_new_identity(self) -> None:
        identity = self.report["return_identity"]
        self.assertTrue(identity["physical_filename_suffix_ignored"])
        self.assertEqual(
            identity["logical_return_name"],
            "r5_n71_gap_v2_obs_return",
        )
        self.assertTrue(
            identity[
                "identity_bound_by_content_manifest_and_source_sha"
            ]
        )

    def test_missing_exact_sidecar_fails_formal_claim(self) -> None:
        identity = self.report["return_identity"]
        self.assertFalse(identity["exact_sidecar_present"])
        self.assertFalse(identity["formal_receipt_claim_pass"])
        self.assertEqual(
            identity["sidecar_blocker"],
            "RETURN_SIDECAR_NOT_PROVIDED",
        )

    def test_dynamic_first_divergence_is_server_rtl_syntax(self) -> None:
        dynamic = self.report["first_divergence"][
            "dynamic_execution_first_divergence"
        ]
        self.assertEqual(
            dynamic["classification"],
            "SERVER_RTL_SYNTAX_ERROR_BEFORE_TESTBENCH_AND_SIMULATION",
        )
        self.assertEqual(
            dynamic["reported_source"], "SA_PE_Float_Control.v"
        )
        self.assertEqual(dynamic["reported_source_line"], 51)
        self.assertFalse(dynamic["observer_include_parsed"])

    def test_gate_rejects_zero_readback_result(self) -> None:
        gate = self.report["fail_closed_adjudication"]
        self.assertEqual(gate["missing_count"], 48)
        self.assertEqual(gate["mismatch_byte_count"], 0)
        self.assertFalse(gate["gate_conjunction"]["all_terms_true"])
        self.assertFalse(gate["formal_claim_pass"])

    def test_no_numeric_or_package_rebuild_is_authorized(self) -> None:
        claim = self.report["claim_boundary"]
        repair = self.report["repair_adjudication"]
        self.assertFalse(claim["numeric_analysis_repeated"])
        self.assertFalse(claim["workload_rebuilt"])
        self.assertFalse(
            repair["package_side_legal_fix_confirmed"]
        )
        self.assertFalse(repair["fresh_next_package_authorized"])

    def test_wrong_return_content_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            wrong = Path(temporary) / "copy(1).zip"
            wrong.write_bytes(b"not the returned evidence")
            with self.assertRaises(
                GapNode0071V2RerunReturnAnalysisError
            ):
                analyze_gap_node0071_v2_rerun_return(ROOT, wrong)


if __name__ == "__main__":
    unittest.main()
