from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "conv_node0004_v25_return_analysis"
LOCAL = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5-node0004-transout-threshold-fix-c0-v5"
    / "local_rebuild_report.json"
)
ZIP = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5-server-test-packages"
    / "r5_n4_hw_v26_transout_threshold_fix.zip"
)
ZIP_SHA256 = "94beb61460e033fbf8ec7afd4cd64e38cd23681fb894df9960bd3cb4be962ddb"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class Node0004V25ReturnV26TransoutFixTest(unittest.TestCase):
    def test_v25_return_proves_threshold_root_cause(self) -> None:
        report = load(OUT / "report.json")
        self.assertTrue(report["valid"])
        self.assertEqual(
            report["HANG_ROOT_CAUSE"]["status"],
            "DETERMINISTIC_CONFIG_ERROR",
        )
        self.assertEqual(
            report["qualified_evidence"]["terminal_index_histogram"],
            {"4": 64, "5": 192},
        )
        self.assertTrue(
            all(
                report["qualified_evidence"]["terminal_checks"].values()
            )
        )
        self.assertFalse(report["RETURN_ANALYSIS"]["joint_result_gate"])

    def test_local_rebuild_changes_one_leaf_and_releases_all(self) -> None:
        report = load(LOCAL)
        self.assertEqual(
            report["authorized_leaf_changes"],
            [
                {
                    "path": "special_array.transout_last_index",
                    "owner": "Conv/SA integration owner",
                    "input": (
                        "256 v25 qualified terminal accepts: index5 x192, "
                        "index4 x64; configured threshold2 ignored all 256"
                    ),
                    "formula": "max accepted terminal last_index",
                    "old": 2,
                    "new": 5,
                }
            ],
        )
        self.assertEqual(report["old_ignored_occurrences"], 256)
        self.assertEqual(report["new_released_occurrences"], 256)

    def test_v26_final_zip_gate(self) -> None:
        report = load(OUT / "v26_final_zip_self_audit.json")
        self.assertTrue(report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"])
        self.assertEqual(report["error_count"], 0)
        self.assertTrue(report["all_required_negative_controls_fail_closed"])
        self.assertTrue(
            report["runtime_preservation"]["all_matrices_byte_identical"]
        )
        self.assertEqual(
            hashlib.sha256(ZIP.read_bytes()).hexdigest(), ZIP_SHA256
        )


if __name__ == "__main__":
    unittest.main()
