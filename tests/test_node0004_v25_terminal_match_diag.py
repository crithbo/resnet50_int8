from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "conv_node0004_v24_return_analysis"
ZIP = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5-server-test-packages"
    / "r5_n4_hw_v25_terminal_match_diag.zip"
)
ZIP_SHA256 = "e4aaf762a3b434a78dfc4af276b48405f84b6dbaee1dad224282ac7b14fb1eab"


def load(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


class Node0004V25TerminalMatchDiagnosticTest(unittest.TestCase):
    def test_v24_return_gate_remains_fail_closed(self) -> None:
        report = load("report.json")
        analysis = report["return_analysis"]
        self.assertTrue(report["valid"])
        self.assertEqual(analysis["compile_exit_status"], 0)
        self.assertEqual(analysis["run_exit_status"], 0)
        self.assertFalse(analysis["natural_terminal"])
        self.assertEqual(analysis["formal_d_present"], 0)
        self.assertEqual(analysis["formal_d_missing"], 320)
        self.assertFalse(analysis["joint_result_gate"])

    def test_focused_hdl_gate_and_required_negatives(self) -> None:
        report = load("v25_observer_scope.json")
        self.assertTrue(report["valid"])
        self.assertEqual(
            report["focused_compatible_frontend"]["positive"]["exit_code"], 0
        )
        for name in (
            "delete_counter_declaration",
            "typo_counter_use",
            "delete_qualified_update",
        ):
            self.assertTrue(
                report["negative_controls"][name]["failed_closed"], name
            )

    def test_final_zip_current_rule_gate(self) -> None:
        report = load("v25_final_zip_self_audit.json")
        self.assertTrue(report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"])
        self.assertEqual(report["error_count"], 0)
        self.assertTrue(report["all_required_negative_controls_fail_closed"])
        digest = hashlib.sha256(ZIP.read_bytes()).hexdigest()
        self.assertEqual(digest, ZIP_SHA256)
        self.assertEqual(report["zip"]["sha256"], ZIP_SHA256)


if __name__ == "__main__":
    unittest.main()
