from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.gap_node0071_v2_rerun_receipt import (
    audit_gap_node0071_v2_rerun_receipt,
)


ROOT = Path(__file__).resolve().parents[1]


class GapNode0071V2RerunReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = audit_gap_node0071_v2_rerun_receipt(ROOT)

    def test_package_identity_and_crc_are_bound(self) -> None:
        identity = self.report["package_identity"]
        self.assertTrue(identity["zip_crc_valid"])
        self.assertTrue(identity["sidecar_content_valid"])
        self.assertEqual(identity["zip_file_count"], 123)

    def test_old_slice_rst_interface_is_not_bound(self) -> None:
        boundary = self.report["package_boundary"]
        self.assertFalse(boundary["binds_old_slice_rst_interface"])
        self.assertFalse(
            boundary["requires_package_update_after_server_rtl_fix"]
        )
        self.assertEqual(
            boundary["old_interface_token_hits"],
            {"slice_rst": [], "SA_PE_Mul_Array": [], "SA_ALU": []},
        )

    def test_no_functional_rtl_or_server_install_is_present(self) -> None:
        boundary = self.report["package_boundary"]
        self.assertFalse(boundary["functional_rtl_modified"])
        self.assertEqual(boundary["server_rtl_entries"], 0)
        self.assertEqual(
            boundary["server_tb_or_observer_install_entries"], 0
        )
        self.assertTrue(boundary["observer_read_only"])

    def test_rerun_entry_and_return_identity_are_frozen(self) -> None:
        runtime = self.report["runtime_boundary"]
        self.assertEqual(
            runtime["server_command"],
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        )
        self.assertEqual(
            runtime["expected_return_zip"],
            "r5_n71_gap_v2_obs_return.zip",
        )
        self.assertEqual(
            runtime["expected_return_sidecar"],
            "r5_n71_gap_v2_obs_return.zip.sha256",
        )

    def test_receipt_only_boundary_is_preserved(self) -> None:
        claim = self.report["claim_boundary"]
        self.assertTrue(claim["receipt_only"])
        self.assertFalse(claim["numeric_analysis_repeated"])
        self.assertFalse(claim["package_rebuilt_or_modified"])
        self.assertFalse(claim["server_files_inspected"])


if __name__ == "__main__":
    unittest.main()
