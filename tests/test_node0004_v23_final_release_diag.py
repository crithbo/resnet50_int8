from __future__ import annotations

import json
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n4_hw_v23_final_release_diag.zip"
)
AUDIT_PATH = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-node0004-v23-final-release-diagnostic"
    / "final_zip_rule_self_audit.json"
)
ROOT_NAME = "r5_n4_hw_v23_final_release_diag"


class Node0004V23FinalReleaseDiagnosticTest(unittest.TestCase):
    def test_final_audit_and_all_negatives(self) -> None:
        audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        self.assertTrue(audit["FINAL_ZIP_RULE_SELF_AUDIT_PASS"])
        self.assertEqual(audit["error_count"], 0)
        self.assertTrue(audit["all_required_negative_controls_fail_closed"])
        negatives = audit["negative_controls"]
        for name, result in negatives.items():
            if name == "all_failed_closed":
                continue
            self.assertTrue(result["failed_closed"], name)
            self.assertEqual(result["observed_exit_code"], 1, name)

    def test_observer_tracks_release_edges_not_occupancy_formula(self) -> None:
        member = f"{ROOT_NAME}/tb_probe/native_return_observer.svh"
        with zipfile.ZipFile(ZIP_PATH) as archive:
            observer = archive.read(member).decode("utf-8")
        for token in (
            "FINAL_RELEASE_EDGE_V1",
            "FINAL_RELEASE_BOUNDARY_V1",
            "sa_pe_inport_last_matched",
            "alu_result_last_bit",
            "sa_pe_alu_result_last_matched",
            "alu2ob_wr_handshake",
            "ob_out_rd_ready",
            "initial_port_wr_ptr",
            "ob2alu_rd_ptr",
            "alu2ob_wr_ptr",
            "ob_out_rd_ptr",
            "sa_pe_outbuffer_port_valid_bit",
        ):
            self.assertIn(token, observer)
        self.assertNotIn("4*initial_accept+1*alu_accept", observer)

    def test_package_remains_diagnostic_only_and_frozen(self) -> None:
        member = f"{ROOT_NAME}/package_manifest.json"
        with zipfile.ZipFile(ZIP_PATH) as archive:
            manifest = json.loads(archive.read(member))
        self.assertEqual(
            manifest["classification"], "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
        )
        self.assertFalse(manifest["candidate_release"])
        self.assertFalse(manifest["numeric_analysis_repeated"])
        self.assertFalse(manifest["node0004_workload_rebuilt"])
        self.assertFalse(manifest["configuration_rebuilt_in_this_successor"])
        self.assertFalse(manifest["functional_rtl_modified"])
        self.assertEqual(manifest["server_rtl_entries"], 0)


if __name__ == "__main__":
    unittest.main()
