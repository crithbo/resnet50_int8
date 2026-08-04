from __future__ import annotations

import json
import unittest
from pathlib import Path

from resnet50_pipeline.node0075_materializer_blocking_leaf import (
    REPORT_SCHEMA,
    TEST_ID,
    build_dynamic_evidence,
    validate_report,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0075-materializer-blocking-leaf-v1/report.json"
)


class Node0075MaterializerBlockingLeafTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_current_disk_reproduces_recorded_evidence(self) -> None:
        self.assertEqual(self.report["dynamic_evidence"], build_dynamic_evidence(ROOT))

    def test_report_is_fail_closed(self) -> None:
        result = validate_report(ROOT, self.report)
        self.assertEqual(result["schema"], REPORT_SCHEMA)
        self.assertEqual(result["test_id"], TEST_ID)
        self.assertEqual(result["status"], "PASS_FAIL_CLOSED")
        self.assertEqual(result["package_release"], "NONE")

    def test_reload_receipt_is_actual_not_theoretical(self) -> None:
        accounting = self.report["dynamic_evidence"]["reload_accounting"]
        self.assertEqual(accounting["authorized_minimum_passes"], 8)
        self.assertEqual(accounting["actual_materialized_passes"], 0)
        self.assertEqual(accounting["actual_accepted_traffic_bytes"], 0)
        self.assertEqual(
            accounting["if_unblocked_exactly_8_passes"]["accepted_traffic_bytes"],
            262144,
        )


if __name__ == "__main__":
    unittest.main()

