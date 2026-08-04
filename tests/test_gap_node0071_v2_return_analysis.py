from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.gap_node0071_v2_return_analysis import (
    GapNode0071V2ReturnAnalysisError,
    analyze_gap_node0071_v2_return,
)


ROOT = Path(__file__).resolve().parents[1]
RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_n71_gap_v2_obs_return.zip"
)


class GapNode0071V2ReturnAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = analyze_gap_node0071_v2_return(ROOT, RETURN)

    def test_return_and_source_identities_are_bound(self) -> None:
        self.assertTrue(self.report["return_identity"]["identity_match"])
        self.assertTrue(
            self.report["bound_source_package"]["sidecar_content_valid"]
        )
        self.assertTrue(
            self.report["bound_source_package"][
                "returned_package_manifest_byte_equal"
            ]
        )

    def test_readbacks_are_absent_and_gate_fails_closed(self) -> None:
        self.assertTrue(
            self.report["preflight"][
                "runtime_readback_targets_absent_in_source_zip"
            ]
        )
        self.assertTrue(
            self.report["preflight"][
                "runtime_readback_targets_absent_post_install"
            ]
        )
        self.assertEqual(
            self.report["fail_closed_adjudication"]["missing_count"], 48
        )
        self.assertFalse(
            self.report["fail_closed_adjudication"]["gate_conjunction"][
                "all_terms_true"
            ]
        )

    def test_observer_transport_passed_before_server_rtl_failure(self) -> None:
        self.assertTrue(
            self.report["observer_transport"]["observer_include_parsed"]
        )
        self.assertTrue(
            self.report["observer_transport"]["xmr_static_gate_valid"]
        )
        self.assertEqual(
            self.report["first_divergence"]["undefined_port"], "slice_rst"
        )
        self.assertEqual(
            self.report["first_divergence"]["instance_module"],
            "SA_PE_Mul_Array",
        )

    def test_next_package_is_not_authorized(self) -> None:
        self.assertFalse(
            self.report["repair_adjudication"][
                "package_side_legal_fix_confirmed"
            ]
        )
        self.assertFalse(
            self.report["repair_adjudication"][
                "fresh_next_package_authorized"
            ]
        )
        self.assertFalse(
            self.report["claim_boundary"]["numeric_analysis_repeated"]
        )

    def test_wrong_return_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            wrong = Path(temporary) / "wrong.zip"
            wrong.write_bytes(b"not a formal return")
            with self.assertRaises(GapNode0071V2ReturnAnalysisError):
                analyze_gap_node0071_v2_return(ROOT, wrong)


if __name__ == "__main__":
    unittest.main()
